"""Find building walls with natural terrain heaped against them (E5, buried houses).

A cell is flagged when a building block has natural terrain on one horizontal side and open
space (a room) on the opposite side, or when glass touches natural terrain. Classes per
cell: 0 open, 1 natural, 2 building, 3 glass, 9 unknown (ungenerated chunk).
"""
import sys, json, io, zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
import nbtlib
sys.path.insert(0, str(Path(__file__).parent))
from mca import decode
from blocks import is_open, is_natural, base

Y0, Y1 = -128, 320
H = Y1 - Y0
CLASS_CACHE = {}


def klass(state):
    k = CLASS_CACHE.get(state)
    if k is None:
        b = base(state)
        if is_open(state):
            k = 0
        elif is_natural(state):
            k = 1
        elif b.endswith('glass') or b.endswith('glass_pane'):
            k = 3
        else:
            k = 2
        CLASS_CACHE[state] = k
    return k


def chunk_classes(buf, cx, cz):
    i = 4 * ((cx & 31) + (cz & 31) * 32)
    if len(buf) < 8192:
        return None
    loc = int.from_bytes(buf[i:i + 3], 'big')
    if not loc:
        return None
    length = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
    root = nbtlib.File.parse(io.BytesIO(zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + length])))
    out = np.zeros((16, 16, H), np.int8)       # [x, z, y]; sections missing = air
    for s in root['sections']:
        sy = int(s['Y'])
        if 'block_states' not in s or sy * 16 + 16 <= Y0 or sy * 16 >= Y1:
            continue
        ids, pal = decode(s['block_states'])
        lut = np.array([klass(p) for p in pal], np.int8)
        cube = lut[ids].reshape(16, 16, 16)    # [y, z, x]
        cube = cube.transpose(2, 1, 0)         # [x, z, y]
        lo = sy * 16 - Y0
        a, b = max(lo, 0), min(lo + 16, H)
        out[:, :, a:b] = cube[:, :, a - lo:b - lo]
    return out


def region_array(folder, rx, rz):
    bufs = {}

    def buf(rrx, rrz):
        if (rrx, rrz) not in bufs:
            p = folder / f'r.{rrx}.{rrz}.mca'
            bufs[rrx, rrz] = p.read_bytes() if p.exists() else b''
        return bufs[rrx, rrz]

    arr = np.full((514, 514, H), 9, np.int8)
    have = False
    for lcx in range(-1, 33):
        for lcz in range(-1, 33):
            edge = lcx in (-1, 32) or lcz in (-1, 32)
            cx, cz = rx * 32 + lcx, rz * 32 + lcz
            c = chunk_classes(buf(cx >> 5, cz >> 5), cx, cz)
            if c is None:
                continue
            if not edge:
                have = True
            x0, z0 = lcx * 16 + 1, lcz * 16 + 1
            xs, zs = max(x0, 0), max(z0, 0)
            xe, ze = min(x0 + 16, 514), min(z0 + 16, 514)
            arr[xs:xe, zs:ze] = c[xs - x0:xe - x0, zs - z0:ze - z0]
    return arr if have else None


def work(args):
    folder, name = args
    folder = Path(folder)
    rx, rz = (int(v) for v in name.split('.')[1:3])
    arr = region_array(folder, rx, rz)
    if arr is None:
        return name, None
    core = arr[1:-1, 1:-1]
    solid = (arr == 1) | (arr == 2) | (arr == 3)
    # highest solid y per column (surface), -1 if none
    any_solid = solid.any(axis=2)
    top = np.where(any_solid, H - 1 - np.argmax(solid[:, :, ::-1], axis=2), -1)
    rows = []
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out = arr[1 + dx:513 + dx, 1 + dz:513 + dz]
        inn = arr[1 - dx:513 - dx, 1 - dz:513 - dz]
        building = (core == 2) | (core == 3)
        wall = building & (out == 1) & (inn == 0)
        glass = (core == 3) & (out == 1)
        hit = wall | glass
        xs, zs, ys = np.nonzero(hit)
        if not len(xs):
            continue
        out_top = top[1 + dx + xs, 1 + dz + zs]
        for x, z, y, ot, w, gl in zip(xs.tolist(), zs.tolist(), ys.tolist(), out_top.tolist(),
                                       wall[xs, zs, ys].tolist(), (core[xs, zs, ys] == 3).tolist()):
            if ot - y > 12:                    # deep underground: facilities, not houses
                continue
            # floor of the room behind the wall
            ix, iz = 1 - dx + x, 1 - dz + z
            col = arr[ix, iz, :y + 1]
            fl = -1
            if w:
                below = np.nonzero(col != 0)[0]
                fl = int(below[-1]) if len(below) else -1
            rows.append((rx * 512 + x, y + Y0, rz * 512 + z, dx, dz, ot + Y0, fl + Y0 if fl >= 0 else -999, int(w), int(gl)))
    return name, rows


if __name__ == '__main__':
    folder = Path(sys.argv[1])
    out = Path(sys.argv[2])
    names = [p.name for p in sorted(folder.glob('r.*.mca'))]
    allrows = []
    with ProcessPoolExecutor(6) as ex:
        for name, rows in ex.map(work, [(str(folder), n) for n in names]):
            if rows:
                allrows += rows
    np.save(out, np.array(allrows, np.int32).reshape(-1, 9))
    print('flagged', len(allrows))
