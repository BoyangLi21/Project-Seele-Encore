"""E5: dead ends of a road mask by Zhang-Suen thinning, then spur tracing from each end to the first junction.
usage: road_dead_ends_scan.py <mask.npz with mask, bounds> <out.json> [min_spur]"""
import json
import sys

import numpy as np
from scipy import ndimage


def thin(img):
    img = img.copy().astype(np.uint8)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            p = np.pad(img, 1)
            P2, P3, P4, P5 = p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:]
            P6, P7, P8, P9 = p[2:, 1:-1], p[2:, :-2], p[1:-1, :-2], p[:-2, :-2]
            nb = [P2, P3, P4, P5, P6, P7, P8, P9]
            B = sum(n.astype(np.int16) for n in nb)
            seq = nb + [P2]
            A = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.int16) for i in range(8))
            if step == 0:
                c = (P2 * P4 * P6 == 0) & (P4 * P6 * P8 == 0)
            else:
                c = (P2 * P4 * P8 == 0) & (P2 * P6 * P8 == 0)
            rm = (img == 1) & (B >= 2) & (B <= 6) & (A == 1) & c
            if rm.any():
                img[rm] = 0
                changed = True
    return img.astype(bool)


def main():
    f = np.load(sys.argv[1])
    mask, (ax, az) = f['mask'].astype(bool), map(int, f['bounds'][:2])
    min_spur = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    mask = ndimage.binary_closing(mask, np.ones((3, 3)))  # 1-cell gaps between converted slabs
    sk = thin(mask)
    deg = ndimage.convolve(sk.astype(np.int16), np.ones((3, 3), np.int16), mode='constant') - 1
    deg[~sk] = 0
    ends = np.argwhere(sk & (deg == 1))
    lab, _ = ndimage.label(mask, np.ones((3, 3)))
    sizes = np.bincount(lab.ravel())
    rows = []
    for z, x in ends:
        # Walk the skeleton until a junction (degree >= 3) or another end.
        path, prev, cur = [(z, x)], None, (z, x)
        while True:
            nb = [(cur[0] + dz, cur[1] + dx) for dz in (-1, 0, 1) for dx in (-1, 0, 1) if (dz or dx)
                  and 0 <= cur[0] + dz < sk.shape[0] and 0 <= cur[1] + dx < sk.shape[1] and sk[cur[0] + dz, cur[1] + dx]
                  and (cur[0] + dz, cur[1] + dx) != prev and (cur[0] + dz, cur[1] + dx) not in path[-3:]]
            if len(nb) != 1 or deg[cur] >= 3 or len(path) > 4000:
                break
            prev, cur = cur, nb[0]
            path.append(cur)
        kind = 'junction' if deg[cur] >= 3 else 'isolated'
        spur = len(path)
        if kind == 'junction' and spur < min_spur:
            continue
        # Road width at the end: mask cells within 3 of the end.
        w = int(mask[max(0, z - 3):z + 4, max(0, x - 3):x + 4].sum())
        rows.append(dict(x=int(x + ax), z=int(z + az), spur=spur, to=kind, comp=int(lab[z, x]), comp_cells=int(sizes[lab[z, x]]), near=w,
                         back=[int(path[min(len(path) - 1, 8)][1] + ax), int(path[min(len(path) - 1, 8)][0] + az)]))
    json.dump(dict(ends=rows, skeleton_cells=int(sk.sum()), mask_cells=int(mask.sum())), open(sys.argv[2], 'w'), indent=0)
    np.save(sys.argv[2].replace('.json', '-skeleton.npy'), sk)
    print(len(rows), 'dead ends;', sum(r['to'] == 'isolated' for r in rows), 'on isolated pieces')


if __name__ == '__main__':
    main()
