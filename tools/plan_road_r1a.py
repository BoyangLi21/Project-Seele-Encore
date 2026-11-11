"""R1-A: take up isolated road fragments and undeclare declared roads that were never paved.

Inputs are a full capture, the declared network and the reviewed dead-end list (road_dead_ends_*).
Fragment: the declared walk+road piece holding the end, when it is not the main network; every
paving block in it (TrafficCraft or old pavement within 3 below to 1 above the declared feet) goes
back to the natural top of the untouched columns around it, layers above that become air.
Unbuilt: from the end, declared cells with no paving near the declared height are undeclared; nothing
is written to the world for them.
Outputs: rows.json for write_deep_cells.py, network.npz, sites.json (per end), check.json.
usage: plan_road_r1a.py <capture> <network.npz> <r1-ends.json> <outdir>"""
import json
import sys
from collections import Counter, deque
from pathlib import Path

import numpy as np
from scipy import ndimage

from plan_station_access_corridor import CapturedSurface
from verify_hakone_network_candidate import PAVEMENT

cap = CapturedSurface(sys.argv[1], partial=True)
net = np.load(sys.argv[2])
network = {k: net[k].copy() for k in net.files}
ends = json.load(open(sys.argv[3], encoding='utf8'))
out = Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
ax, az = map(int, network['bounds'][:2])
road, walk, g2 = network['road'], network['walk'], network['grade2']
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
NATURAL = ('minecraft:grass_block', 'minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:stone', 'minecraft:gravel', 'minecraft:sand',
           'minecraft:podzol', 'minecraft:andesite', 'minecraft:granite', 'minecraft:diorite', 'minecraft:moss_block', 'minecraft:rooted_dirt')
PLANTS = ('grass', 'fern', 'flower', 'bush', 'dandelion', 'poppy', 'tulip', 'orchid', 'allium', 'bluet', 'daisy', 'cornflower', 'lily')
S8 = np.ones((3, 3))


def name(s):
    return s.split('[')[0]


def paving(s):
    return s.startswith('trafficcraft:') or name(s) in PAVEMENT


def feet(x, z):
    return g2[z - az, x - ax] / 2 + 1


def paving_ys(x, z, f):
    return [y for y in range(int(np.floor(f)) - 3, int(np.floor(f)) + 2) if paving(cap.state(x, y, z))]


UNBUILT = False  # 28 of the 30 'unbuilt' ends turned out paved under viaducts or against walls; they go to the per-end list.
walk_lab, _ = ndimage.label(walk | road, S8)
sizes = np.bincount(walk_lab.ravel())
main = int(np.argmax(sizes[1:]) + 1)
writes, sites, notes = {}, [], Counter()
taken = set()


def natural_top(x, y, z, skip):
    seen = Counter()
    for r in (1, 2, 3):
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if max(abs(dx), abs(dz)) != r or (x + dx, z + dz) in skip:
                    continue
                for yy in range(y + 3, y - 5, -1):
                    n = name(cap.state(x + dx, yy, z + dz))
                    if n in AIR or n.endswith(PLANTS) or n.endswith(('_leaves', '_log')):
                        continue
                    if n in NATURAL:
                        seen['minecraft:grass_block[snowy=false]' if n == 'minecraft:grass_block' else n] += 1
                    break
        if seen:
            return seen.most_common(1)[0][0]
    return None


def nearest_declared(x, z, mask, r=3):
    for d in range(r + 1):
        for dx in range(-d, d + 1):
            for dz in range(-d, d + 1):
                if mask[z + dz - az, x + dx - ax]:
                    return x + dx, z + dz
    return None


for e in ends:
    if e['kind'] == 'fragment':
        p = nearest_declared(e['x'], e['z'], road | walk)
        if p is None:
            notes[f"fragment end #{e['id']} with no declared cell within 3"] += 1
            continue
        c = int(walk_lab[p[1] - az, p[0] - ax])
        if c in taken:
            sites.append(dict(id=e['id'], kind='fragment', same_as_component=c))
            continue
        taken.add(c)
        if c == main:
            # A road stub inside the main walking area: the road declaration goes, the ground stays.
            rl, _ = ndimage.label(road, S8)
            k = rl[p[1] - az, p[0] - ax]
            zz, xx = np.nonzero(rl == k)
            road[zz, xx] = False
            sites.append(dict(id=e['id'], kind='fragment', action='road declaration dropped, footway kept', cells=0, columns=len(zz)))
            continue
        zz, xx = np.nonzero(walk_lab == c)
        cols = {(int(x + ax), int(z + az)) for z, x in zip(zz, xx)}
        # Undeclared paving touching the piece at a similar height belongs to it too.
        frontier = deque((q, 0) for q in cols)
        while frontier:
            (x, z), depth = frontier.popleft()
            if depth >= 2:
                continue
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    q = (x + dx, z + dz)
                    if q in cols or walk[q[1] - az, q[0] - ax] or road[q[1] - az, q[0] - ax]:
                        continue
                    if paving_ys(q[0], q[1], feet(x, z)):
                        g2[q[1] - az, q[0] - ax] = g2[z - az, x - ax]
                        cols.add(q)
                        frontier.append((q, depth + 1))
        n0 = len(writes)
        for (x, z) in sorted(cols):
            f = feet(x, z)
            ys = paving_ys(x, z, f)
            if not ys:
                continue
            base = min(ys)
            above = name(cap.state(x, max(ys) + 1, z))
            buried = above in NATURAL
            for y in sorted(ys) + [y for y in range(max(ys) + 1, max(ys) + 2) if name(cap.state(x, y, z)).endswith(PLANTS)]:
                s = cap.state(x, y, z)
                if buried:
                    # Paving under later terrain: fill like the ground around it so no pocket or buried grass is left.
                    under = name(cap.state(x, y - 1, z))
                    after = 'minecraft:stone' if under == 'minecraft:stone' and above == 'minecraft:stone' else 'minecraft:dirt'
                elif y == base:
                    below = name(cap.state(x, y - 1, z))
                    after = natural_top(x, y, z, cols) if below not in AIR else 'minecraft:air'
                    if after is None:
                        after = 'minecraft:grass_block[snowy=false]' if below in ('minecraft:dirt', 'minecraft:grass_block') else (below if below in NATURAL else 'minecraft:air')
                else:
                    after = 'minecraft:air'
                if s != after:
                    writes[x, y, z] = [x, y, z, s, after]
            if buried:
                notes['buried paving columns filled'] += 1
            elif above not in AIR and not above.endswith(PLANTS):
                notes[f'kept above paving: {above}'] += 1
        for (x, z) in cols:
            walk[z - az, x - ax] = road[z - az, x - ax] = False
        xs = [a for a, _ in cols]
        zs = [b for _, b in cols]
        sites.append(dict(id=e['id'], kind='fragment', action='taken up, ground restored', component=c, columns=len(cols), cells=len(writes) - n0,
                          box=[min(xs), min(zs), max(xs), max(zs)]))
    elif e['kind'] == 'unbuilt' and UNBUILT:
        p = nearest_declared(e['x'], e['z'], road)
        if p is None:
            notes['unbuilt end with no road cell'] += 1
            continue
        seen, frontier = set(), deque([p])
        while frontier and len(seen) < 5000:
            x, z = frontier.popleft()
            if (x, z) in seen:
                continue
            if paving_ys(x, z, feet(x, z)):
                continue
            seen.add((x, z))
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    q = (x + dx, z + dz)
                    if q not in seen and (road[q[1] - az, q[0] - ax] or walk[q[1] - az, q[0] - ax]):
                        frontier.append(q)
        new = [q for q in seen if road[q[1] - az, q[0] - ax] or walk[q[1] - az, q[0] - ax]]
        for (x, z) in new:
            walk[z - az, x - ax] = road[z - az, x - ax] = False
        sites.append(dict(id=e['id'], kind='unbuilt', action='undeclared, world untouched', cells=0, columns=len(new),
                          hit_limit=len(seen) >= 5000))
rows = list(writes.values())
json.dump(rows, open(out / 'rows.json', 'w', encoding='utf8'))
np.savez_compressed(out / 'network.npz', **network)
json.dump(sites, open(out / 'sites.json', 'w', encoding='utf8'), ensure_ascii=False, indent=0)
check = dict(errors=[], cells=len(rows), after=Counter(name(r[4]) for r in rows), before=Counter(name(r[3]) for r in rows), notes=notes,
             undeclared_columns=int(sum(s.get('columns', 0) for s in sites)))
json.dump(check, open(out / 'check.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print(json.dumps(check, ensure_ascii=False))
