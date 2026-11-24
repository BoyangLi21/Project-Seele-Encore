"""Trees in Unit-00's way at the Yashima shield station (the site's shield_wait_port), as a list for the writer.

  python yashima_shield_trees.py <out dir>

Unit-00's collision box is 17 blocks wide, so it is held off its station by any crown that rises above the deck
within reach. Every tree with a log or a leaf above the deck (y 175 and up) within RADIUS blocks of the port goes
whole: its connected logs, and the leaves nearer to its logs than to a kept tree's. The ground under a removed trunk
becomes grass like the slope around it. Reads the port from tv_encounter_sites_r45.json in BUILDINGS_WORLD and writes
rows.json and report.json.
"""
import json, math, sys
from collections import deque
from pathlib import Path
from mca import REGION, World, WORLD
from float_fix import guards

RADIUS = 12
DECK_TOP = 175            # first open layer over the deck
SEARCH = 18
GRASS = 'minecraft:grass_block[snowy=false]'


def is_log(s):
    return bool(s) and (s.split('[')[0].endswith('_log') or s.split('[')[0].endswith('_wood'))


def is_leaf(s):
    return bool(s) and 'leaves' in s


def main(out):
    site = json.loads(Path(WORLD, 'tv_encounter_sites_r45.json').read_text('utf8'))['sites']['ramiel']
    px, py, pz = site['shield_wait_port']
    w = World(REGION)
    cx, cz = int(math.floor(px)), int(math.floor(pz))
    ylo, yhi = int(py) - 20, int(py) + 30
    logs = {(x, y, z) for x in range(cx - SEARCH, cx + SEARCH + 1) for z in range(cz - SEARCH, cz + SEARCH + 1)
            for y in range(ylo, yhi) if is_log(w.get(x, y, z))}
    tree_of, trees = {}, []
    for start in sorted(logs):
        if start in tree_of:
            continue
        members, q = set(), deque([start])
        while q:
            c = q.popleft()
            if c in members or c not in logs:
                continue
            members.add(c)
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q.append((c[0] + d[0], c[1] + d[1], c[2] + d[2]))
        for c in members:
            tree_of[c] = len(trees)
        trees.append(dict(logs=members, leaves=set()))
    # each leaf to the nearest tree (Chebyshev distance to its logs, up to 5)
    for x in range(cx - SEARCH - 5, cx + SEARCH + 6):
        for z in range(cz - SEARCH - 5, cz + SEARCH + 6):
            for y in range(ylo, yhi + 6):
                if not is_leaf(w.get(x, y, z)):
                    continue
                best, owner = 6, None
                for dx in range(-5, 6):
                    for dy in range(-5, 6):
                        for dz in range(-5, 6):
                            t = tree_of.get((x + dx, y + dy, z + dz))
                            if t is not None and max(abs(dx), abs(dy), abs(dz)) < best:
                                best, owner = max(abs(dx), abs(dy), abs(dz)), t
                if owner is not None:
                    trees[owner]['leaves'].add((x, y, z))
    within = lambda c: c[1] >= DECK_TOP and math.hypot(c[0] + .5 - px, c[2] + .5 - pz) <= RADIUS
    gs = guards()
    rows, report = [], []
    for t in trees:
        cells = t['logs'] | t['leaves']
        if not any(within(c) for c in cells):
            continue
        root = min(t['logs'], key=lambda c: c[1])
        report.append(dict(trunk=[root[0], root[2]], base_y=root[1], top_y=max(c[1] for c in cells), logs=len(t['logs']), leaves=len(t['leaves']),
                           distance=round(math.hypot(root[0] + .5 - px, root[2] + .5 - pz), 1),
                           side='north' if root[2] + .5 < pz else 'south'))
        for c in sorted(cells):
            rows.append([*c, w.get(*c), 'minecraft:air'])
        under = (root[0], root[1] - 1, root[2])
        s = w.get(*under) or ''
        if s.split('[')[0] in ('minecraft:dirt', 'minecraft:coarse_dirt', 'minecraft:podzol', 'minecraft:rooted_dirt'):
            rows.append([*under, s, GRASS])
    for r in rows:
        if w.block_entity(*r[:3]):
            raise SystemExit(f'{r[:3]} carries a block entity')
        for g in gs:
            g.assert_positions([tuple(r[:3])])
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    summary = dict(port=[px, py, pz], radius=RADIUS, rows=len(rows), trees=report)
    (Path(out) / 'report.json').write_text(json.dumps(summary, indent=1), 'utf8')
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
