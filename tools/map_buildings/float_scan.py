"""Floating buildings: building blocks with open space under them and natural ground or water further down.

Rows per underside cell: x, y (the building cell), z, gap (open cells below it), ground class
(1 natural, 5 water), ground y. Trees and plants count as open, so canopies are not buildings.
"""
import io, sys, zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
import nbtlib
sys.path.insert(0, str(Path(__file__).parent))
from mca import decode
from blocks import is_open, is_natural, base

Y0, Y1 = -128, 320
H = Y1 - Y0
P = 1
VEG = ('leaves', '_log', '_wood', 'mushroom_block', 'vine', 'azalea', 'bamboo', 'cactus')
CACHE = {}


def klass(state):
    k = CACHE.get(state)
    if k is None:
        b = base(state)
        if 'water' in b or 'kelp' in b or 'seagrass' in b:
            k = 5
        elif is_open(state) or any(v in b for v in VEG):
            k = 0
        elif is_natural(state):
            k = 1
        else:
            k = 2
        CACHE[state] = k
    return k


def chunk_classes(buf, cx, cz):
    if len(buf) < 8192:
        return None
    i = 4 * ((cx & 31) + (cz & 31) * 32)
    loc = int.from_bytes(buf[i:i + 3], 'big')
    if not loc:
        return None
    length = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
    root = nbtlib.File.parse(io.BytesIO(zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + length])))
    out = np.zeros((16, 16, H), np.int8)
    for s in root['sections']:
        sy = int(s['Y'])
        if 'block_states' not in s or sy * 16 + 16 <= Y0 or sy * 16 >= Y1:
            continue
        ids, pal = decode(s['block_states'])
        lut = np.array([klass(p) for p in pal], np.int8)
        cube = lut[ids].reshape(16, 16, 16).transpose(2, 1, 0)
        lo = sy * 16 - Y0
        a, b = max(lo, 0), min(lo + 16, H)
        out[:, :, a:b] = cube[:, :, a - lo:b - lo]
    return out


def work(args):
    folder, name = args
    rx, rz = (int(v) for v in name.split('.')[1:3])
    buf = (Path(folder) / name).read_bytes()
    rows = []
    for lcx in range(32):
        for lcz in range(32):
            c = chunk_classes(buf, rx * 32 + lcx, rz * 32 + lcz)
            if c is None:
                continue
            bld = c == 2
            under = np.zeros_like(bld)
            under[:, :, 1:] = bld[:, :, 1:] & (c[:, :, :-1] == 0)
            xs, zs, ys = np.nonzero(under)
            if not len(xs):
                continue
            gap = np.zeros(len(xs), np.int32)
            ground = np.zeros(len(xs), np.int8)
            alive = np.ones(len(xs), bool)
            for k in range(1, 64):
                yy = ys - k
                ok = alive & (yy >= 0)
                cls = np.full(len(xs), 9, np.int8)
                cls[ok] = c[xs[ok], zs[ok], yy[ok]]
                stop = alive & (cls != 0)
                ground[stop] = cls[stop]
                gap[stop] = k - 1
                alive &= cls == 0
                if not alive.any():
                    break
            keep = (ground == 1) | (ground == 5)
            for x, z, y, g, gr in zip(xs[keep].tolist(), zs[keep].tolist(), ys[keep].tolist(), gap[keep].tolist(), ground[keep].tolist()):
                rows.append((rx * 512 + lcx * 16 + x, y + Y0, rz * 512 + lcz * 16 + z, g, gr, y + Y0 - g - 1))
    return name, np.array(rows, np.int32).reshape(-1, 6) if rows else None


if __name__ == '__main__':
    folder = Path(sys.argv[1])
    names = [p.name for p in sorted(folder.glob('r.*.mca'))]
    parts, done = [], 0
    with ProcessPoolExecutor(int(sys.argv[2])) as ex:
        for name, r in ex.map(work, [(str(folder), n) for n in names]):
            done += 1
            if r is not None:
                parts.append(r)
            if done % 20 == 0:
                print(done, len(names), flush=True)
    allrows = np.concatenate(parts) if parts else np.zeros((0, 6), np.int32)
    np.save(Path(__file__).parent / 'float.npy', allrows)
    print('underside cells', len(allrows))
