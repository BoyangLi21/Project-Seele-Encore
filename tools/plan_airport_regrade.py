"""Uncover a paved pad buried by later terrain; by default the NERV airport (x350..1350, z-177..86, pavement top y72) from the hill laid over it.

The pavement runs complete under the hill: a later terrain pass covered its north quarter
(about 61,000 columns, up to y118) and left sheer cut faces round the rest. Everything natural
above the pavement goes; outside it the hill is cut back to a slope of about 1 in 1.5 with a
three-block verge, rounded at the crest, and replanted. Built columns stay as they are.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr

PAVEMENT = {'minecraft:gray_concrete', 'minecraft:black_concrete', 'minecraft:white_concrete', 'minecraft:yellow_concrete',
            'minecraft:light_gray_concrete'}
APRON_Y = 72


def noise(shape, sigma, rng):
    f = ndimage.gaussian_filter(rng.standard_normal(shape), sigma)
    return f / (f.std() + 1e-9)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--slope', type=float, default=.68)
    p.add_argument('--verge', type=float, default=3)
    p.add_argument('--box', type=int, nargs=4, default=[180, 1530, -350, 250], help='x0 x1 z0 z1 of the area read and regraded')
    p.add_argument('--apron-y', type=int, default=APRON_Y, help='top of the pavement')
    p.add_argument('--keep', type=Path, help='JSON list of [x0, z0, x1, z1] boxes another task owns; they and 8 columns round them stay as they are')
    a = p.parse_args()
    globals()["APRON_Y"] = a.apron_y
    a.out.mkdir(parents=True, exist_ok=True)
    box = tr.Box(a.world, a.box[0], a.box[1], APRON_Y - 17, 215, a.box[2], a.box[3])
    x0, y0, z0 = box.origin
    k = box.kind_grid()
    names = np.array([s.split('[')[0] for s in box.palette])
    pave = np.isin(names, list(PAVEMENT))
    foot = pave[box.ids[APRON_Y - y0]] | pave[box.ids[APRON_Y - 1 - y0]]
    lab, n = ndimage.label(foot)
    foot = ndimage.binary_fill_holes(lab == np.argmax(np.bincount(lab.ravel())[1:]) + 1)
    ground = tr.top_of(k == tr.SOIL, y0)
    built = (k == tr.BUILT) | (k == tr.FLUID)
    # Built blocks on or under the apron belong to it; outside, every built column and its neighbours stay.
    outside_built = built.copy()
    outside_built[:APRON_Y - y0 + 1, foot] = False
    built_cols = outside_built.any(0)
    frozen = ndimage.binary_dilation(built_cols, iterations=4) | ~box.loaded
    if a.keep:
        for bx0, bz0, bx1, bz1 in json.loads(a.keep.read_text('utf8')):
            frozen[max(0, bz0 - 8 - z0):max(0, bz1 + 9 - z0), max(0, bx0 - 8 - x0):max(0, bx1 + 9 - x0)] = True
    rng = np.random.default_rng(11)
    dist = ndimage.distance_transform_edt(~foot)
    s = a.slope * (1 + .12 * noise(foot.shape, 18, rng))
    cap = APRON_Y + np.maximum(0, dist - a.verge) * s + 1.2 * noise(foot.shape, 6, rng) * np.clip((dist - a.verge) / 8, 0, 1)
    cut = tr.softmin(ground.astype(float), cap, 2.5)
    fill = np.maximum(ground, APRON_Y - .9 * np.maximum(0, dist - 1.5))
    target = np.where(ground > APRON_Y, cut, fill)
    # Next to a kept column the new ground climbs back to the old one instead of leaving a step.
    dfroz = ndimage.distance_transform_edt(~frozen)
    target = np.maximum(target, ground - a.slope * 1.3 * dfroz)
    target = np.where(foot, np.minimum(ground, APRON_Y), target)
    target = np.where(frozen & ~foot, ground, target)
    # On the apron: natural blocks above the pavement only, around buildings standing on it nothing.
    on_apron_built = built.copy()
    on_apron_built[:APRON_Y - y0 + 1] = False
    keep_on_apron = ndimage.binary_dilation(on_apron_built.any(0) & foot, iterations=3)
    target = np.where(foot & keep_on_apron, ground, target)
    frozen_all = frozen & ~foot | foot & keep_on_apron
    plant = (dist >= a.verge + 3) & ~ndimage.binary_dilation(frozen, iterations=3)
    keepout = ndimage.binary_dilation(foot, iterations=2) | frozen
    new_ids, change = tr.apply_heights(box, ground, target, frozen_all, plant=plant, plant_keepout=keepout, chance=tr.local_tree_chances(box, 24))
    rows = tr.rows_between(box, new_ids)
    tr.write_rows(a.out / 'rows.json', rows)
    after_ground = tr.top_of(box.kinds[new_ids] == tr.SOIL, y0)
    np.savez_compressed(a.out / 'heights.npz', origin=np.array(box.origin), foot=foot, frozen=frozen_all, before=ground, after=after_ground, target=target)
    still = (foot & ((box.kinds[new_ids[APRON_Y - y0 + 1:]] == tr.SOIL) | (box.kinds[new_ids[APRON_Y - y0 + 1:]] == tr.SOFT)).any(0))
    from collections import Counter
    report = dict(cells=len(rows), columns_changed=int(change.sum()), footprint_columns=int(foot.sum()),
                  footprint_x=[int(np.nonzero(foot.any(0))[0].min() + x0), int(np.nonzero(foot.any(0))[0].max() + x0)],
                  footprint_z=[int(np.nonzero(foot.any(1))[0].min() + z0), int(np.nonzero(foot.any(1))[0].max() + z0)],
                  apron_columns_still_covered=int(still.sum()), frozen_columns=int(frozen_all.sum()),
                  after_states=Counter(r[4].split('[')[0] for r in rows).most_common(12),
                  before_states=Counter(r[3].split('[')[0] for r in rows).most_common(12),
                  max_cut=int((ground - after_ground)[change].max()), max_fill=int((after_ground - ground)[change].max()))
    (a.out / 'report.json').write_text(json.dumps(report, indent=1), 'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
