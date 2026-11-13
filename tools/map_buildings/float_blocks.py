"""Blocks that hang in the air: everything not connected to the ground through touching blocks.

float_blocks.py <out.json> [workers]

Per region (with a 16-block margin read from the neighbours) every block that is not air, fluid,
light, barrier or structure void counts as solid. Support starts at the ground (each column's
solid run up from the bottom of the world), at the window border (it may hold on outside) and at
missing chunks, and spreads through face-touching solid blocks. Whatever solid block in the
region core is left unreached floats: canopies whose trunk is gone, lamps whose post was cut,
pieces of a half-demolished building, terrain crumbs. They are grouped into face-connected
pieces with size, box, height of the gap under them and their commonest blocks.
"""
import io, json, sys, zlib
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import nbtlib
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World, decode

Y0, Y1 = -128, 320
H = Y1 - Y0
P = 16
OPEN = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air', 'minecraft:water', 'minecraft:lava',
        'minecraft:light', 'minecraft:barrier', 'minecraft:structure_void', 'minecraft:bubble_column',
        'minecraft:moving_piston')


def is_solid(state):
    return state.split('[')[0] not in OPEN


def chunk_solid(buf, cx, cz):
    """[x, z, y] solid mask of one chunk, or None when the chunk is not generated."""
    i = 4 * ((cx & 31) + (cz & 31) * 32)
    if len(buf) < 8192:
        return None
    loc = int.from_bytes(buf[i:i + 3], 'big')
    if not loc:
        return None
    length = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
    root = nbtlib.File.parse(io.BytesIO(zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + length])))
    out = np.zeros((16, 16, H), bool)
    for s in root['sections']:
        sy = int(s['Y'])
        if 'block_states' not in s or sy * 16 + 16 <= Y0 or sy * 16 >= Y1:
            continue
        ids, pal = decode(s['block_states'])
        lut = np.array([is_solid(p) for p in pal], bool)
        cube = lut[ids].reshape(16, 16, 16).transpose(2, 1, 0)
        lo = sy * 16 - Y0
        a, b = max(lo, 0), min(lo + 16, H)
        out[:, :, a:b] = cube[:, :, a - lo:b - lo]
    return out


def work(args):
    folder, name = args
    rx, rz = (int(v) for v in name.split('.')[1:3])
    folder = Path(folder)
    bufs = {}

    def buf(a, b):
        if (a, b) not in bufs:
            p = folder / f'r.{a}.{b}.mca'
            bufs[a, b] = p.read_bytes() if p.exists() else b''
        return bufs[a, b]
    n = 512 + 2 * P
    solid = np.zeros((n, n, H), bool)
    missing = np.zeros((n, n), bool)
    have = False
    for lcx in range(-1, 33):
        for lcz in range(-1, 33):
            cx, cz = rx * 32 + lcx, rz * 32 + lcz
            c = chunk_solid(buf(cx >> 5, cz >> 5), cx, cz)
            x0, z0 = lcx * 16 + P, lcz * 16 + P
            if c is None:
                missing[x0:x0 + 16, z0:z0 + 16] = True
                continue
            if 0 <= lcx < 32 and 0 <= lcz < 32:
                have = True
            solid[x0:x0 + 16, z0:z0 + 16] = c
    if not have:
        return name, []
    reached = np.logical_and.accumulate(solid, axis=2)
    reached[0, :, :] = reached[-1, :, :] = True
    reached[:, 0, :] = reached[:, -1, :] = True
    reached[:, :, -1] = True
    reached[missing] = True
    reached &= solid | missing[:, :, None]
    flat_s, flat_r = solid.reshape(-1), reached.reshape(-1)
    steps = np.array([n * H, -n * H, H, -H, 1, -1], np.int64)
    # first frontier: reached blocks with an unreached solid neighbour
    todo = flat_s & ~flat_r
    frontier = np.flatnonzero(todo)
    if len(frontier):
        nb = frontier[:, None] + steps[None, :]
        hit = flat_r[nb].any(axis=1)
        frontier = frontier[hit]
        flat_r[frontier] = True
    while len(frontier):
        nb = (frontier[:, None] + steps[None, :]).reshape(-1)
        nb = nb[flat_s[nb] & ~flat_r[nb]]
        nb = np.unique(nb)
        flat_r[nb] = True
        frontier = nb
    left = solid & ~reached
    left[:P, :, :] = left[-P:, :, :] = False
    left[:, :P, :] = left[:, -P:, :] = False
    xs, zs, ys = np.nonzero(left)
    del solid, reached, left, flat_s, flat_r
    cells = set(zip(xs.tolist(), zs.tolist(), ys.tolist()))
    pieces = []
    w = World(str(folder))
    while cells:
        start = cells.pop()
        q, comp = deque([start]), [start]
        while q:
            x, z, y = q.popleft()
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                c = (x + d[0], z + d[1], y + d[2])
                if c in cells:
                    cells.remove(c)
                    q.append(c)
                    comp.append(c)
        wx = [rx * 512 + x - P for x, z, y in comp]
        wz = [rz * 512 + z - P for x, z, y in comp]
        wy = [y + Y0 for x, z, y in comp]
        kinds = Counter()
        for i in range(0, len(comp), max(1, len(comp) // 200)):
            s = w.get(wx[i], wy[i], wz[i]) or '?'
            kinds[s.split('[')[0].replace('minecraft:', '')] += 1
        # gap under the piece: from its lowest block down to the next solid block
        lo = min(range(len(comp)), key=lambda i: wy[i])
        gx, gy, gz = wx[lo], wy[lo], wz[lo]
        g = 0
        while g < 200 and not is_solid(w.get(gx, gy - 1 - g, gz) or 'minecraft:stone'):
            g += 1
        pieces.append(dict(size=len(comp), bbox=[min(wx), min(wy), min(wz), max(wx), max(wy), max(wz)],
                           at=[gx, gy, gz], gap=g, kinds=dict(kinds.most_common(5))))
    return name, pieces


def main(out, workers=5):
    names = sorted(p.name for p in Path(REGION).glob('r.*.mca'))
    allp = []
    with ProcessPoolExecutor(int(workers)) as ex:
        for k, (name, pieces) in enumerate(ex.map(work, [(REGION, nm) for nm in names])):
            allp += pieces
            if k % 20 == 0:
                print(k, len(names), name, len(pieces), 'total', len(allp), flush=True)
    json.dump(allp, open(out, 'w'))
    print('pieces', len(allp), 'blocks', sum(p['size'] for p in allp))


if __name__ == '__main__':
    main(*sys.argv[1:])
