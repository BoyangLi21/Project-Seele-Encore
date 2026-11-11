"""Ground the hanging edges round a raised platform: fill the trench inside its ring road, put earth under
decks that float over the slope, and run 1:1 slopes out from the new ground, in the style of the
outer slopes the terrain round them already has.

Sites (JSON list):
- {"plateau": [x0, z0, x1, z1], "level": 79}: columns lower than level are filled up to it (grass on top);
- {"deck": [x0, z0, x1, z1], "y": [lo, hi]}: a built block with open space under it whose lowest cell is in
  y lo..hi gets earth up to the cell below it;
- {"exclude": [x0, z0, x1, z1]}: nothing changes there (viaducts, shafts, another task's plates).
Only open cells and plants above the old ground are filled; columns with anything built between the old
ground and the new one, water and unloaded chunks stay, and the slope eases down to them.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import ndimage

import terrain_regrade as tr


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--sites', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--box', type=int, nargs=4, required=True, help='x0 x1 z0 z1 read and regraded')
    p.add_argument('--y', type=int, nargs=2, default=[20, 130])
    p.add_argument('--reach', type=float, default=30, help='longest 1:1 slope run out from the new ground')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    sites = json.loads(a.sites.read_text('utf8'))
    box = tr.Box(a.world, a.box[0], a.box[1], a.y[0], a.y[1], a.box[2], a.box[3])
    x0, y0, z0 = box.origin
    k = box.kind_grid()
    nz, nx = k.shape[1:]
    ground = tr.top_of(k == tr.SOIL, y0)
    yy = np.arange(k.shape[0])[:, None, None] + y0
    built = k == tr.BUILT
    above = built & (yy > ground[None])
    has_above = above.any(0)
    first = np.where(has_above, np.argmax(above, 0) + y0, 10 ** 4)

    def rect(r):
        m = np.zeros((nz, nx), bool)
        m[max(0, r[1] - z0):max(0, r[3] + 1 - z0), max(0, r[0] - x0):max(0, r[2] + 1 - x0)] = True
        return m

    excluded = np.zeros((nz, nx), bool)
    target = ground.astype(float).copy()
    deck = np.zeros((nz, nx), bool)
    plateau = np.zeros((nz, nx), bool)
    for s in sites:
        if 'exclude' in s:
            excluded |= rect(s['exclude'])
    for s in sites:
        if 'deck' in s:
            lo, hi = s['y']
            m = rect(s['deck']) & (first >= lo) & (first <= hi) & (first - ground >= 2) & ~excluded
            deck |= m
            # a railing or kerb on the deck's edge hangs lower than the deck's underside: earth stops at
            # the underside of the deck beside it, not at the railing's foot
            under = ndimage.minimum_filter(np.where(m, first - 1, 10 ** 4), size=5)
            target = np.where(m, np.maximum(target, under), target)
    for s in sites:
        if 'plateau' in s:
            m = rect(s['plateau']) & ~excluded
            plateau |= m
            # a column with a building on it keeps it; earth only rises to just under its lowest cell
            lvl = np.where(has_above, np.minimum(s['level'], first - 1), s['level'])
            target = np.where(m, np.maximum(ground, lvl), target)
            # the railing column of a deck right beside the filled ground fills to that ground, so no slot
            # opens between the deck's side and the new grass
            rim = deck & ndimage.binary_dilation(m, iterations=1) & ~m
            target = np.where(rim, np.maximum(target, lvl), target)
    # water buried under the ground (springs under stone) does not matter, only water at the surface
    fluid = ((k == tr.FLUID) & (yy >= ground[None])).any(0)
    raised = (target > ground) & box.loaded
    # columns that may not be filled: something built between the old ground and the new top (other
    # than the deck itself), water, unloaded or excluded chunks
    in_fill = built & (yy > ground[None]) & (yy <= np.maximum(target, ground)[None])
    blocked = in_fill.any(0) | fluid | ~box.loaded | excluded
    # 1:1 slopes out from every raised column
    cone = np.full((nz, nx), -1e9)
    src = raised & ~blocked
    for lvl in range(int(target[src].min()) if src.any() else 0, int(target[src].max()) + 1 if src.any() else 0):
        s = src & (target >= lvl)
        if not s.any():
            continue
        d = ndimage.distance_transform_edt(~s)
        cone = np.maximum(cone, np.where(d <= a.reach, lvl - d, -1e9))
    # built columns outside the fill (roads, rails, houses, piers) and their neighbours stay; the slope
    # eases down so it never stands more than one cell above them
    keep = (has_above & ~deck & ~plateau) | blocked
    dkeep = ndimage.distance_transform_edt(~keep)
    cone = np.minimum(cone, ground + np.maximum(0, dkeep - 1))
    target = np.where(raised & ~blocked, target, np.maximum(ground, np.where(keep, ground, np.round(cone))))
    target = np.maximum(target, ground)
    frozen = blocked & ~(raised & ~blocked)
    change_cols = (target > ground) & ~frozen
    # replant open new ground at the density of the woods round it, away from decks and buildings
    near_built = ndimage.binary_dilation(has_above | deck, iterations=3)
    plant = change_cols & ~near_built
    keepout = ndimage.binary_dilation(has_above | deck | fluid, iterations=2)
    chance = tr.local_tree_chances(box, 24, counts=~(deck | plateau))
    new_ids, change = tr.apply_heights(box, ground, target, frozen, plant=plant, plant_keepout=keepout, chance=chance)
    rows = tr.rows_between(box, new_ids)
    tr.write_rows(a.out / 'rows.json', rows)
    after = tr.top_of(box.kinds[new_ids] == tr.SOIL, y0)
    np.savez_compressed(a.out / 'heights.npz', origin=np.array(box.origin), before=ground, after=after, deck=deck, plateau=plateau, frozen=frozen)
    fill = (after - ground)[change]
    report = dict(cells=len(rows), columns_changed=int(change.sum()), deck_columns=int(deck.sum()), plateau_columns_raised=int((plateau & change).sum()),
                  max_fill=int(fill.max()) if fill.size else 0, mean_fill=round(float(fill.mean()), 2) if fill.size else 0,
                  short_of_target=int(((target > ground) & ~frozen & (after < target)).sum()),
                  after_states=Counter(r[4].split('[')[0] for r in rows).most_common(10),
                  before_states=Counter(r[3].split('[')[0] for r in rows).most_common(10))
    (a.out / 'report.json').write_text(json.dumps(report, indent=1), 'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
