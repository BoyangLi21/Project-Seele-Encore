"""Sloped funicular platforms and graded footpaths from one capture, as one cell patch.

A funicular stops on its grade, so the platform floor follows the rail in half
steps and the door trigger sits under each edge cell. A footpath is searched
over (column, walking height) states: each step moves one column and at most half
a block, so the result needs no jump; fill and cut are costed against the
captured ground. Nothing here opens the actual world; release_map_patch.py
installs the patch.
"""
import argparse
import heapq
import json
import math
from pathlib import Path

import numpy as np

from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_rail_corridor import DOOR_TRIGGER, door_scan
from plan_station_access_corridor import CapturedSurface
from query_blocks import AIR

FLOOR, EDGE, SLAB = 'minecraft:smooth_stone', 'minecraft:yellow_concrete', 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
BODY, FENCE = 'minecraft:stone_bricks', 'minecraft:light_gray_stained_glass'
PATH, PATH_SLAB = 'minecraft:polished_andesite', 'minecraft:polished_andesite_slab[type=bottom,waterlogged=false]'
LEAVES = ('_leaves',)
OPEN = AIR | PLANTS
# Track-bed finish beside the ballast may become platform; ballast, rails and devices may not.
BED = {'minecraft:stone_bricks', 'minecraft:stone_brick_slab', 'minecraft:light_gray_concrete', 'minecraft:smooth_stone',
       'minecraft:smooth_stone_slab', 'minecraft:stone_brick_wall', 'minecraft:andesite_slab'}


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1), 'utf8')


def kind(state):
    return state.split('[')[0]


def natural(state):
    k = kind(state)
    return k in SOIL or k in OPEN or k.endswith(LEAVES)


class Patch:
    def __init__(self, source):
        self.source, self.rows, self.errors = source, {}, []

    def put(self, cell, state, purpose, allowed=None):
        before = self.source.state(*cell)
        if cell in self.rows:
            if self.rows[cell]['after'] != state:
                self.errors.append(['Two parts of the design disagree', list(cell), self.rows[cell]['after'], state])
            return
        if before == state:
            return
        if not natural(before) and not (allowed and kind(before) in allowed):
            self.errors.append(['Design meets a built block', list(cell), before, purpose])
            return
        self.rows[cell] = dict(pos=list(cell), before=before, after=state, purpose=purpose)

    def clear(self, cell, purpose):
        state = self.source.state(*cell)
        if kind(state) in AIR:
            return
        self.put(cell, 'minecraft:air', purpose)

    def support(self, x, y, z, purpose):
        """Fill open space under a deck down to the first solid block."""
        while kind(self.source.state(x, y, z)) in OPEN or kind(self.source.state(x, y, z)).endswith(LEAVES):
            self.put((x, y, z), BODY, purpose)
            y -= 1


def surface(state, y):
    """Walking height on a block: a bottom slab gives half a block."""
    return y + (.5 if 'type=bottom' in state else 1.0)


def ground(source, x, z, top=200, bottom=-60):
    """Highest solid, non-plant block in a column, with its walking height."""
    for y in range(top, bottom, -1):
        state = source.state(x, y, z)
        k = kind(state)
        if k in OPEN or k.endswith(LEAVES):
            continue
        return y, state
    return None, None


def platform_cells(item):
    """Columns of one platform with their walking height, edge and rim roles."""
    p, q = item['from'], item['to']
    start, finish = np.array([p[0] + .5, p[2] + .5]), np.array([q[0] + .5, q[2] + .5])
    delta = finish - start
    length = float(np.linalg.norm(delta))
    along = delta / length
    out = np.array([-along[1], along[0]]) * item['side']
    clearance, width = item.get('clearance', 1.35), item.get('width', 3.0)
    rail = lambda run: p[1] + (q[1] - p[1]) * min(max(run, 0), length) / length
    cells = {}
    low = np.minimum(start, finish) - width - clearance - 3
    high = np.maximum(start, finish) + width + clearance + 3
    for x in range(math.floor(low[0]), math.ceil(high[0])):
        for z in range(math.floor(low[1]), math.ceil(high[1])):
            corners = np.array([[x + i, z + j] for i in (0, 1) for j in (0, 1)]) - start
            lateral = corners @ out
            run = (np.array([x + .5, z + .5]) - start) @ along
            if lateral.min() < item.get('gap', .9) or lateral.max() > clearance + width or run < -1 or run > length + 1:
                continue
            if lateral.min() < clearance:
                # A diagonal edge leaves a triangle under the doors; its floor stays at or under the car floor.
                if 0 <= run <= length:
                    cells[x, z] = dict(walk=math.floor((rail(run) + 1) * 2 + 1e-9) / 2, gap=True, edge=False, reach=False, rim=False, end=False, run=run)
                continue
            # Rounding up keeps each buried trigger inside the band MTR scans at every door
            # along the grade; the floor then stands at most half a block above the car floor.
            walk = math.ceil((rail(run) + 1) * 2 - 1e-9) / 2
            edge = lateral.min() < clearance + 1
            reach = lateral.min() < clearance + 2
            end = run < 0 or run > length
            rim = lateral.max() > clearance + width - 1 or end
            cells[x, z] = dict(walk=walk, gap=False, edge=edge and not end, reach=reach and not end and not rim, rim=rim, end=end, run=run)
    return cells, (start, along, out, length, rail)


def platform(source, patch, item, report, opened):
    cells, (start, along, out, length, rail) = platform_cells(item)
    triggers = set()
    for (x, z), c in cells.items():
        c = dict(c, rim=c['rim'] and (x, z) not in opened)
        walk = c['walk']
        top = math.ceil(walk) - 1
        if c['rim']:
            # The fence stands on a full block; nobody walks the rim.
            patch.put((x, top, z), BODY, 'platform rim', BED)
            patch.put((x, top + 1, z), FENCE, 'platform fence', BED)
            patch.support(x, top - 1, z, 'platform body')
            continue
        half = walk != math.floor(walk)
        floor = SLAB if half else EDGE if c['edge'] else FLOOR
        if c['gap']:
            patch.put((x, top, z), SLAB if half else FLOOR, 'platform gap fill', BED | {'minecraft:gravel'})
            if half:
                patch.put((x, top - 1, z), BODY, 'platform body', BED | {'minecraft:gravel'})
            for level in range(top + 1, top + 3):
                patch.clear((x, level, z), 'platform clearance')
            continue
        patch.put((x, top, z), floor, 'platform floor', BED)
        below = top - 1
        if c['edge'] or c['reach']:
            # A diagonal edge row leaves gaps in MTR's axis-aligned scan, so the second row carries triggers too.
            patch.put((x, below, z), DOOR_TRIGGER, 'platform door trigger', BED)
            triggers.add((x, below, z))
        elif half:
            patch.put((x, below, z), BODY, 'platform body', BED)
        patch.support(x, below - 1, z, 'platform body')
        for level in range(top + 1, top + 4):
            patch.clear((x, level, z), 'platform clearance')
    span = item.get('door_half_span', .875)
    clearance = item.get('clearance', 1.35)
    stops = np.arange(span, length - span, .5)
    for s in stops:
        point, level = start + along * s, round(rail(s))
        scan = list(door_scan(point, along, out, level, span))
        if any(c in triggers for c in scan):
            continue
        # MTR samples its scan box in whole steps, so on a 22.5 degree track a door can miss the
        # edge row; such a stop takes a trigger in the bed under the car's platform side.
        floor = [c for c in scan if c[1] == level - 1 and c not in patch.rows and ('[' not in source.state(*c) or 'type=bottom' in source.state(*c))
                 and kind(source.state(*c)) not in AIR and kind(source.state(*c)) in BED | {'minecraft:gravel', 'minecraft:stone'}]
        if floor:
            c = max(floor, key=lambda q: (np.array([q[0] + .5, q[2] + .5]) - start) @ out)
            patch.put(c, DOOR_TRIGGER, 'platform door trigger', BED | {'minecraft:gravel'})
            triggers.add(c)
    near = far = 0
    for s in stops:
        point, level = start + along * s, round(rail(s))
        near += any(c in triggers for c in door_scan(point, along, out, level, span))
        far += any(c in triggers for c in door_scan(point, along, -out, level, span))
    if near != len(stops) or far:
        patch.errors.append(['Door reach', item['name'], near, len(stops), far])
    report.append(dict(name=item['name'], length=length, cells=len(cells), triggers=len(triggers), doors_checked=len(stops),
                       doors_in_reach=near, far_side_in_reach=far))
    return cells


def footpath(source, patch, spec, item, rails, report, platforms):
    """Least-cost graded walk from a platform exit to a public surface."""
    x0, z0, x1, z1 = item['box']
    net = np.load(spec['network'])
    nx, nz = int(net['bounds'][0]), int(net['bounds'][1])
    public = (net['road'] | net['walk'])[z0 - nz:z1 - nz + 1, x0 - nx:x1 - nx + 1]
    shape = (z1 - z0 + 1, x1 - x0 + 1)
    land = np.full(shape, np.nan)
    blocked = np.zeros(shape, bool)
    goal, kept = {}, set()
    walkable = set(item.get('walkable', ()))
    # An existing platform is walked as built: its rim is an exit, not a column to pave.
    taken = {cell for name, cells in platforms.items() for cell in cells if name not in spec.get('existing', {})}
    near_rail = rails(np.stack(np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(z0, z1 + 1) + .5), -1).reshape(-1, 2)).reshape(shape)
    for z in range(z0, z1 + 1):
        for x in range(x0, x1 + 1):
            y, state = ground(source, x, z)
            i, j = z - z0, x - x0
            if y is None:
                blocked[i, j] = True
                continue
            land[i, j] = surface(state, y)
            k = kind(state)
            if public[i, j] and k not in SOIL or k in item.get('goal_states', ()) and item.get('goal_box', (x, z, x, z))[0] <= x <= item.get('goal_box', (x, z, x, z))[2] and item.get('goal_box', (x, z, x, z))[1] <= z <= item.get('goal_box', (x, z, x, z))[3]:
                goal[x, z] = land[i, j]
            if (x, z) in taken or near_rail[i, j] < item.get('rail_clearance', 3.6) or k in ('minecraft:water',) or k.endswith('_log'):
                blocked[i, j] = True
            elif k in walkable:
                kept.add((x, z))
            elif k not in SOIL and not public[i, j] and (x, z) not in goal:
                blocked[i, j] = True
    goal = {c: h for c, h in goal.items() if not blocked[c[1] - z0, c[0] - x0]}
    if item.get('goal_near'):
        gx, gz, radius = item['goal_near']
        goal = {c: h for c, h in goal.items() if math.hypot(c[0] - gx, c[1] - gz) <= radius}
    fill_w, cut_w = item.get('fill_cost', 1.2), item.get('cut_cost', 1.6)
    # Any outer rim column may become the exit; the search starts from all of them.
    exits = {c: v['walk'] for c, v in platforms[item['platform']].items() if v['rim'] and not v['end']}
    if item.get('exit_run'):
        lo, hi = item['exit_run']
        exits = {c: h for c, h in exits.items() if lo <= platforms[item['platform']][c]['run'] <= hi}
    dist, prev = {(x, z, h): 0.0 for (x, z), h in exits.items()}, {}
    heap = [(0.0, x, z, h) for (x, z), h in exits.items()]
    heapq.heapify(heap)
    found = None
    while heap:
        d, x, z, h = heapq.heappop(heap)
        if d > dist.get((x, z, h), 1e18):
            continue
        if (x, z) in goal and abs(goal[x, z] - h) < .01:
            found = (x, z, h)
            break
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            u, w = x + dx, z + dz
            if not (x0 <= u <= x1 and z0 <= w <= z1) or blocked[w - z0, u - x0]:
                continue
            g = land[w - z0, u - x0]
            for dh in (-.5, 0, .5):
                k = h + dh
                fill, cut = k - g, g - k
                if fill > item.get('max_fill', 5) or cut > item.get('max_cut', 3):
                    continue
                if ((u, w) in goal or (u, w) in kept) and abs(g - k) > .01 and not item.get('regrade_public'):
                    continue
                cost = 1 + .15 * (dh != 0) + fill_w * max(0, fill) + cut_w * max(0, cut)
                if d + cost < dist.get((u, w, k), 1e18):
                    dist[u, w, k] = d + cost
                    prev[u, w, k] = (x, z, h)
                    heapq.heappush(heap, (d + cost, u, w, k))
    if found is None:
        patch.errors.append(['No graded footpath', item['name']])
        return
    line = [found]
    while line[-1] in prev:
        line.append(prev[line[-1]])
    line.reverse()
    paved = {}
    for n, (x, z, h) in enumerate(line):
        paved.setdefault((x, z), h)
        # A second column beside the line keeps the walk two wide where the ground allows.
        a = line[min(n + 1, len(line) - 1)]
        b = line[max(n - 1, 0)]
        dx, dz = a[0] - b[0], a[1] - b[1]
        side = (int(np.sign(-dz)), int(np.sign(dx))) if (dx or dz) else (0, 0)
        for s in (side, (-side[0], -side[1])):
            u, w = x + s[0], z + s[1]
            if s != (0, 0) and x0 <= u <= x1 and z0 <= w <= z1 and not blocked[w - z0, u - x0] and (u, w) not in goal:
                paved.setdefault((u, w), h)
                break
    for (x, z), h in paved.items():
        if (x, z) in goal and abs(goal[x, z] - h) < .01 or (x, z) in taken or (x, z) in kept:
            continue
        top = math.ceil(h) - 1
        half = h != math.floor(h)
        patch.put((x, top, z), PATH_SLAB if half else PATH, 'footpath')
        if half:
            patch.put((x, top - 1, z), PATH, 'footpath body')
        patch.support(x, top - (2 if half else 1), z, 'footpath body')
        for level in range(top + 1, top + 4):
            patch.clear((x, level, z), 'footpath clearance')
    rises = [abs(b[2] - a[2]) for a, b in zip(line, line[1:])]
    report.append(dict(name=item['name'], exit=list(line[0][:2]), cells=len(line), paved=len(paved), start=list(line[0]), end=list(line[-1]),
                       rise=line[-1][2] - line[0][2], max_step=max(rises or [0]), line=[list(c) for c in line]))


def author(a):
    spec = read(a.config)
    source = CapturedSurface(spec['source'], partial=True)
    patch = Patch(source)
    samples = [np.array(r['points'])[:, [0, 2]] for r in read(spec['track_samples']) if r['mode'] == 'TRAIN']
    extra = [np.array(r['points'])[:, [0, 2]] for r in read(spec['other_rails'])] if spec.get('other_rails') else []
    points = np.vstack(samples + extra)
    from scipy.spatial import cKDTree
    tree = cKDTree(points)
    rails = lambda xz: tree.query(xz)[0]
    report = dict(platforms=[], paths=[])
    platforms = {item['name']: platform_cells(item)[0] for item in spec['platforms'] + list(spec.get('existing', {}).values())}
    for item in spec['paths']:
        footpath(source, patch, spec, item, rails, report['paths'], platforms)
    opened = {tuple(p['exit']) for p in report['paths']}
    for item in spec['platforms']:
        platform(source, patch, item, report['platforms'], opened)
    a.out.mkdir(parents=True, exist_ok=True)
    report.update(errors=patch.errors[:40], cells=len(patch.rows), world_written=False)
    write(a.out / 'station-check.json', report)
    write(a.out / 'patch.json', dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'],
                                     edits=[patch.rows[c] for c in sorted(patch.rows)], native_snapshot=spec['native_snapshot'],
                                     error_reports=[str(a.out / 'station-check.json')], views_reviewed_by_root=False,
                                     continuation_work=spec['continuation_work']))
    print(json.dumps(dict(cells=len(patch.rows), platforms=report['platforms'],
                          paths=[{k: v for k, v in p.items() if k != 'line'} for p in report['paths']], errors=patch.errors[:8]), ensure_ascii=False))
    if patch.errors:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('author',))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    globals()[args.mode](args)
