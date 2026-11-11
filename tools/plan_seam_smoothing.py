"""Smooth selected terrain seams from scan_terrain_seams.py into the slopes either side.

Each seam gets a band as wide as its step needs (three columns per block of step, 8 to 24
either side). Inside the band the ground moves toward a Gaussian-smoothed copy of itself,
fully at the seam line and not at all at the band edge, so the two terrain passes meet in a
ramp instead of a wall. Built columns and their neighbours keep their height, and the new
ground climbs back to theirs at a slope of one. Changed slopes lose cut trees and are
replanted. Seams whose bands overlap are planned together.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr


def bands(seams, pad):
    boxes = []
    for s in seams:
        w = int(np.clip(3 * s.get('max', 3), 8, 24))
        boxes.append([s['x'][0] - w - pad, s['z'][0] - w - pad, s['x'][1] + w + pad, s['z'][1] + w + pad, [s], w])
    merged = True
    while merged:
        merged = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]:
                    boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]), a[4] + b[4], max(a[5], b[5])]
                    del boxes[j]
                    merged = True
                    break
            if merged:
                break
    return boxes


def residual(g):
    """Largest neighbour step not explained by the steps two columns either side."""
    out = np.zeros(g.shape, np.int32)
    for axis in (0, 1):
        st = np.diff(g, axis=axis)
        sp = np.pad(st, [(3, 3) if ax == axis else (0, 0) for ax in range(2)], mode='edge')
        take = lambda o: np.take(sp, np.arange(3 + o, 3 + o + st.shape[axis]), axis=axis)
        trend = np.median(np.stack([take(-2), take(-1), take(1), take(2)]), 0)
        r = (st - np.round(trend)).astype(np.int32)
        full = np.zeros(g.shape, np.int32)
        idx = [slice(None)] * 2
        idx[axis] = slice(0, -1)
        full[tuple(idx)] = r
        out = np.where(np.abs(full) > np.abs(out), full, out)
    return out


def plan_group(world, x0, z0, x1, z1, seams, w, ylo, yhi, seed):
    box = tr.Box(world, x0, x1, ylo, yhi, z0, z1)
    by = box.origin[1]
    k = box.kind_grid()
    ground = tr.top_of(k == tr.SOIL, by)
    built = (k == tr.BUILT) | (k == tr.FLUID)
    # anything built from eight below the ground up freezes the column (tunnels deeper down do not)
    yy = np.arange(k.shape[0])[:, None, None] + by
    near_ground = built & (yy >= ground[None] - 8)
    frozen = ndimage.binary_dilation(near_ground.any(0), iterations=3) | ~box.loaded | (ground < by + 4) | (ground > yhi - 4)
    seam = np.zeros(ground.shape, bool)
    r = np.abs(residual(ground))
    for s in seams:
        sx0, sx1 = s['x'][0] - x0, s['x'][1] - x0
        sz0, sz1 = s['z'][0] - z0, s['z'][1] - z0
        sub = np.zeros(ground.shape, bool)
        sub[max(0, sz0 - 3):sz1 + 4, max(0, sx0 - 3):sx1 + 4] = True
        seam |= sub & (r >= 2) & ~frozen
    dist = ndimage.distance_transform_edt(~seam)
    t = np.clip(1 - dist / w, 0, 1)
    taper = t * t * (3 - 2 * t)
    g = ground.astype(float)
    smooth = ndimage.gaussian_filter(g, w / 2.5, mode='nearest')
    target = g + taper * (smooth - g)
    dfroz = ndimage.distance_transform_edt(~frozen)
    target = np.clip(target, g - dfroz, g + dfroz)
    target = np.where(frozen, g, target)
    plant = (taper > 0) & (dfroz > 4)
    keepout = frozen
    # replant only as densely as the forest stood around the band before
    chance = tr.local_tree_chances(box)
    new_ids, change = tr.apply_heights(box, ground, target, frozen, rng_seed=seed, plant=plant, plant_keepout=keepout, chance=chance)
    after = tr.top_of(box.kinds[new_ids] == tr.SOIL, by)
    band = taper > .5
    before_r = int((r[band] >= 3).sum())
    after_r = int((np.abs(residual(after))[band] >= 3).sum())
    return tr.rows_between(box, new_ids), dict(box=[x0, z0, x1, z1], seams=[s['id'] for s in seams], band=w, columns_changed=int(change.sum()),
                                               steps_ge3_in_band_before=before_r, steps_ge3_in_band_after=after_r,
                                               max_cut=int((ground - after)[change].max()) if change.any() else 0,
                                               max_fill=int((after - ground)[change].max()) if change.any() else 0), (ground, after, frozen, taper, box.origin)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--seams', type=Path, required=True)
    p.add_argument('--ids', type=int, nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    allseams = {s['id']: s for s in json.loads(a.seams.read_text('utf8'))['seams']}
    chosen = [allseams[i] for i in a.ids]
    rows, groups = [], []
    for n, (x0, z0, x1, z1, members, w) in enumerate(bands(chosen, 6)):
        import scan_surface_columns  # noqa: F401  (keeps the scan palette rules importable alongside)
        rr, rep, arrays = plan_group(a.world, x0, z0, x1, z1, members, w, -64, 250, 100 + n)
        np.savez_compressed(a.out / f'group-{n:02d}.npz', before=arrays[0], after=arrays[1], frozen=arrays[2], taper=arrays[3], origin=np.array(arrays[4]))
        rows += rr
        groups.append(rep)
        print(json.dumps(rep), flush=True)
    seen = set()
    for row in rows:
        key = tuple(row[:3])
        if key in seen:
            raise SystemExit(f'{key} planned twice')
        seen.add(key)
    tr.write_rows(a.out / 'rows.json', rows)
    (a.out / 'report.json').write_text(json.dumps(dict(cells=len(rows), groups=groups), indent=1), 'utf8')
    print(json.dumps(dict(cells=len(rows), groups=len(groups))))


if __name__ == '__main__':
    main()
