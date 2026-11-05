"""Re-own armour plates that the Unit-01 pack builder tore in two at the elbow.

make_tiger_unit01_pack.py assigns the arm chain triangle by triangle at the
elbow cut, so the small detached elbow plate straddling that line ends up half
on the upper arm and half on the forearm and splits apart whenever the elbow
bends.  This moves every small component spanning arm_X/forearm_X wholly onto
the forearm (the elbow guard rides the forearm) and leaves the continuous
shells alone.

python fix_eva_plates.py in.mesh.json out.mesh.json
"""
import json
import sys

import numpy as np

SMALL = 60


def tris(part, stride):
    v = np.array(part['vertices'], float).reshape(-1, stride)
    v[:, :3] += np.array(part['pivot'], float)
    return v.reshape(-1, 3, stride)


def components(tri_list):
    keys = {}
    parent = list(range(len(tri_list)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for t, tri in enumerate(tri_list):
        for p in tri[:, :3]:
            k = tuple(np.round(p, 3))
            if k in keys:
                parent[find(t)] = find(keys[k])
            else:
                keys[k] = t
    groups = {}
    for t in range(len(tri_list)):
        groups.setdefault(find(t), []).append(t)
    return list(groups.values())


def main():
    src, out = sys.argv[1], sys.argv[2]
    mesh = json.load(open(src, encoding='utf8'))
    stride = mesh['stride']
    parts = mesh['parts']
    for side in 'lr':
        upper, lower = 'arm_' + side, 'forearm_' + side
        a, b = tris(parts[upper], stride), tris(parts[lower], stride)
        union = list(a) + list(b)
        owner = [upper] * len(a) + [lower] * len(b)
        move = set()
        for comp in components(union):
            owners = {owner[t] for t in comp}
            if len(owners) == 2 and len(comp) <= SMALL:
                moved = [t for t in comp if owner[t] == upper]
                move.update(moved)
                ys = np.concatenate([union[t][:, 1] for t in comp])
                print('%s: plate of %d triangles (y %.1f..%.1f), %d moved to %s'
                      % (side, len(comp), ys.min(), ys.max(), len(moved), lower))
        if not move:
            continue
        keep = [union[t] for t in range(len(a)) if t not in move]
        gain = [union[t] for t in sorted(move)]
        for name, rows in ((upper, keep), (lower, list(b) + gain)):
            pv = np.array(parts[name]['pivot'], float)
            arr = np.array(rows).reshape(-1, stride).copy()
            arr[:, :3] -= pv
            parts[name]['vertices'] = [round(float(x), 6) for x in arr.ravel()]
    json.dump(mesh, open(out, 'w', encoding='utf8'), separators=(',', ':'))
    print('wrote', out)


if __name__ == '__main__':
    main()
