"""One pass per region: wall-against-terrain cells (walls.npy) and terrain inside enclosures (fill.npy)."""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from walls import H, Y0
from fill import region_array, reach, P, R


def work(args):
    folder, name = args
    rx, rz = (int(v) for v in name.split('.')[1:3])
    arr = region_array(Path(folder), rx, rz)
    if arr is None:
        return name, None, None
    core = arr[P:-P, P:-P]
    n = core.shape[0]
    solid = (arr == 1) | (arr == 2) | (arr == 3)
    top = np.where(solid.any(axis=2), H - 1 - np.argmax(solid[:, :, ::-1], axis=2), -1)
    del solid
    rows = []
    building = (core == 2) | (core == 3)
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out = arr[P + dx:P + n + dx, P + dz:P + n + dz]
        inn = arr[P - dx:P + n - dx, P - dz:P + n - dz]
        wall = building & (out == 1) & (inn == 0)
        glass = (core == 3) & (out == 1)
        xs, zs, ys = np.nonzero(wall | glass)
        for x, z, y in zip(xs.tolist(), zs.tolist(), ys.tolist()):
            ot = int(top[P + dx + x, P + dz + z])
            if ot - y > 12:
                continue
            w = bool(wall[x, z, y])
            fl = -999
            if w:
                col = arr[P - dx + x, P - dz + z, :y + 1]
                below = np.nonzero(col != 0)[0]
                fl = int(below[-1]) + Y0 if len(below) else -999
            rows.append((rx * 512 + x, y + Y0, rz * 512 + z, dx, dz, ot + Y0, fl, int(w), int(core[x, z, y] == 3)))
        del wall, glass
    del building
    inside = reach(arr, 0, 0, 1)
    xs, zs, ys = np.nonzero(inside)
    del inside
    keep = np.ones(len(xs), bool)
    for dx, dz, dy in ((0, 0, -1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)):
        alive = keep.copy()
        hit = np.zeros(len(xs), bool)
        for k in range(1, R + 1):
            yy = ys + dy * k
            ok = yy >= 0
            nb = np.full(len(xs), 9, np.int8)
            nb[ok] = arr[P + xs[ok] + dx * k, P + zs[ok] + dz * k, yy[ok]]
            hit |= alive & ((nb == 2) | (nb == 3))
            alive &= nb == 1
            if not alive.any():
                break
        keep &= hit
    xs, zs, ys = xs[keep], zs[keep], ys[keep]
    fill = np.stack([xs + rx * 512, ys + Y0, zs + rz * 512, top[P + xs, P + zs] + Y0], 1).astype(np.int32) if len(xs) else None
    return name, np.array(rows, np.int32).reshape(-1, 9) if rows else None, fill


if __name__ == '__main__':
    folder = Path(sys.argv[1])
    names = [p.name for p in sorted(folder.glob('r.*.mca'))]
    W, F = [], []
    done = 0
    with ProcessPoolExecutor(int(sys.argv[2])) as ex:
        for name, w, f in ex.map(work, [(str(folder), n) for n in names]):
            done += 1
            if w is not None: W.append(w)
            if f is not None: F.append(f)
            if done % 20 == 0: print(done, len(names), flush=True)
    np.save('walls.npy', np.concatenate(W) if W else np.zeros((0, 9), np.int32))
    np.save('fill.npy', np.concatenate(F) if F else np.zeros((0, 4), np.int32))
    print('walls', sum(len(a) for a in W), 'fill', sum(len(a) for a in F))
