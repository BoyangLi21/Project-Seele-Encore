"""Natural terrain inside a building's enclosure (E5: houses filled with dirt).

A natural cell counts as interior fill when, walking through natural cells only, it reaches a
building block within R cells in all four horizontal directions and upwards. Output rows:
x, y, z, top-of-column y (surface).
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import walls
from walls import chunk_classes, H, Y0

R = 12
P = 16


def region_array(folder, rx, rz):
    bufs = {}

    def buf(rrx, rrz):
        if (rrx, rrz) not in bufs:
            p = folder / f'r.{rrx}.{rrz}.mca'
            bufs[rrx, rrz] = p.read_bytes() if p.exists() else b''
        return bufs[rrx, rrz]

    n = 512 + 2 * P
    arr = np.full((n, n, H), 9, np.int8)
    have = False
    for lcx in range(-1, 33):
        for lcz in range(-1, 33):
            cx, cz = rx * 32 + lcx, rz * 32 + lcz
            c = chunk_classes(buf(cx >> 5, cz >> 5), cx, cz)
            if c is None:
                continue
            if 0 <= lcx < 32 and 0 <= lcz < 32:
                have = True
            x0, z0 = lcx * 16 + P, lcz * 16 + P
            arr[x0:x0 + 16, z0:z0 + 16] = c
    return arr if have else None


def reach(arr, dx, dz, dy):
    """Natural cells of the core that reach a building block through natural cells within R."""
    core = arr[P:-P, P:-P]
    alive = core == 1
    hit = np.zeros_like(alive)
    for k in range(1, R + 1):
        if dy > 0:
            nb = np.full_like(core, 9)
            nb[:, :, :H - k] = core[:, :, k:]
        elif dy < 0:
            nb = np.full_like(core, 9)
            nb[:, :, k:] = core[:, :, :H - k]
        else:
            nb = arr[P + dx * k:arr.shape[0] - P + dx * k, P + dz * k:arr.shape[1] - P + dz * k]
        hit |= alive & ((nb == 2) | (nb == 3))
        alive &= nb == 1
        if not alive.any():
            break
    return hit


def work(args):
    folder, name = args
    rx, rz = (int(v) for v in name.split('.')[1:3])
    arr = region_array(Path(folder), rx, rz)
    if arr is None:
        return name, None
    inside = reach(arr, 0, 0, 1)
    inside &= reach(arr, 0, 0, -1)
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if not inside.any():
            break
        inside &= reach(arr, dx, dz, 0)
    xs, zs, ys = np.nonzero(inside)
    if not len(xs):
        return name, None
    return name, np.stack([xs + rx * 512, ys + Y0, zs + rz * 512], 1).astype(np.int32)


if __name__ == '__main__':
    folder = Path(sys.argv[1])
    names = [p.name for p in sorted(folder.glob('r.*.mca'))]
    parts = []
    with ProcessPoolExecutor(int(sys.argv[3]) if len(sys.argv) > 3 else 5) as ex:
        for name, rows in ex.map(work, [(str(folder), n) for n in names]):
            if rows is not None:
                parts.append(rows)
    allrows = np.concatenate(parts) if parts else np.zeros((0, 3), np.int32)
    np.save(sys.argv[2], allrows)
    print('fill cells', len(allrows))
