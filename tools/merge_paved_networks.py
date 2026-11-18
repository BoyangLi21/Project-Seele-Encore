"""Merge paved networks with the same bounds: road and walk are OR-ed; grade2 is taken from the first network that
paves the column. Writes a network and its road mask for road_dead_ends_scan.
usage: merge_paved_networks.py <out.npz> <mask.npz> <net.npz> [net.npz ...]"""
import sys

import numpy as np


def main():
    out, mask_out, *ins = sys.argv[1:]
    base = np.load(ins[0])
    road, walk, g2 = base['road'].copy(), base['walk'].copy(), base['grade2'].copy()
    for path in ins[1:]:
        n = np.load(path)
        if not np.array_equal(n['bounds'], base['bounds']) or n['road'].shape != road.shape:
            raise SystemExit(f'{path}: bounds differ')
        new = (n['walk'] | n['road']) & ~walk
        g2[new] = n['grade2'][new]
        road |= n['road']
        walk |= n['walk'] | n['road']
    np.savez_compressed(out, road=road, walk=walk, grade2=g2, bounds=base['bounds'])
    np.savez_compressed(mask_out, mask=road, bounds=base['bounds'])
    print(dict(road=int(road.sum()), walk=int(walk.sum())))


if __name__ == '__main__':
    main()
