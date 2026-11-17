"""Redo the restored top block of cut-back rows made before plan_road_r1_batch looked for neighbours' surfaces from above.

The old natural_top scanned neighbour columns from three blocks above the old deck, so an uphill neighbour gave
the rock inside the hill, and a wide cut found only paving within three columns and copied the stone under the
old road base, so the cut strip came back as bare stone. A row is redone when its after-state is the
restored top (a natural block with air above it after the cut); buried fills are left alone. The new top is the
most common exposed surface of the untouched columns around, read from the capture the cut was planned on.
Prints the changed rows; with <list.json> <out.json> also writes that write list with those after-states replaced.
usage: retop_cut_rows.py <capture> <rows-cut.json> <out-retop.json> [<list.json> <out-list.json>]"""
import json
import sys
from collections import Counter

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
rows = json.load(open(sys.argv[2], encoding='utf8'))
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
PLANTS = ('grass', 'fern', 'flower', 'tulip', 'sapling', 'bush', 'vine', 'roots', 'mushroom', 'snow', 'orchid', 'allium', 'bluet',
          'daisy', 'dandelion', 'poppy', 'cornflower', 'lily_of_the_valley', 'azalea')
NATURAL = ('minecraft:grass_block', 'minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:stone', 'minecraft:gravel', 'minecraft:sand',
           'minecraft:podzol', 'minecraft:andesite', 'minecraft:granite', 'minecraft:diorite', 'minecraft:moss_block', 'minecraft:rooted_dirt')


def name(s):
    return s.split('[')[0]


after = {tuple(r[:3]): r[4] for r in rows}
cols = {(r[0], r[2]) for r in rows}


def state_after(x, y, z):
    return after.get((x, y, z)) or cap.state(x, y, z)


def natural_top(x, y, z):
    seen = Counter()
    for r in range(1, 9):     # wide cuts have only paving within three columns
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if max(abs(dx), abs(dz)) != r or (x + dx, z + dz) in cols:
                    continue
                for yy in range(y + 16, y - 5, -1):
                    n = name(cap.state(x + dx, yy, z + dz))
                    if n in AIR or n.endswith(PLANTS) or n.endswith(('_leaves', '_log')):
                        continue
                    if n in NATURAL:
                        seen['minecraft:grass_block[snowy=false]' if n == 'minecraft:grass_block' else n] += 1
                    break
        if seen:
            return seen.most_common(1)[0][0]
    return None


changed = []
for r in rows:
    x, y, z, before, aft = r[:5]
    if name(aft) not in NATURAL or name(state_after(x, y + 1, z)) not in AIR:
        continue
    new = natural_top(x, y, z)
    if new and new != aft:
        changed.append([x, y, z, aft, new])
json.dump(changed, open(sys.argv[3], 'w', encoding='utf8'))
print(len(rows), 'cut rows', len(changed), 'tops redone', dict(Counter((name(c[3]), name(c[4])) for c in changed)))
if len(sys.argv) > 5:
    new = {tuple(c[:3]): c[4] for c in changed}
    lst = json.load(open(sys.argv[4], encoding='utf8'))
    n = 0
    for r in lst:
        k = tuple(r[:3])
        if k in new:
            r[4] = new[k]
            n += 1
    json.dump(lst, open(sys.argv[5], 'w', encoding='utf8'))
    print(sys.argv[5], 'after-states replaced', n, 'of', len(changed))
