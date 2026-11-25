"""Buried stairs left by the code-slim stair scan (main's decisions of 2026-11-25):

  python buried_fix.py <out dir> [--houses | --shaft]

--houses: only the two houses; --shaft: only the shaft (its wall cells in city lift original96/66's space go to
held.json, written with write_deep_cells --original96-66-shaft-wall).

Reads BUILDINGS_WORLD. Writes rows.json and report.json.

1. The glass stair shaft at x -191..-175, z 81..97 (a 15 x 15 stairwell from the surface down through the GeoFront
   roof to a closed floor at y -112; y 42-73 of it is packed with ground, the stairs buried inside). It stays buried:
   everything of it above y CAP_Y goes, a light grey concrete cover fills its whole 17 x 17 outline at CAP_Y, and the
   ground within 8 blocks is graded to meet the cover (at distance d the ground top lies within CAP_Y +- d). The part
   seen from inside the GeoFront is untouched.
2. Two houses the hillside half buries (the rooms and attics hold ground, the hill lies on the back roof slope):
   x 125..145, z -682..-666 (floor slab y 69) and the pair at x 37..62, z -630..-594 (floor slab y 71). A house is
   the 4-connected set of columns holding a non-ground block between floor + 1 and floor + 14, grown from a roof cell.
   - Inside a house column every ground block above the floor goes (rooms, attic, ground lying on the roof).
   - Around it the hill steps back: within 3 columns ground above the floor level goes, further out the ground top may
     rise one block per column (45 degrees); the new top of each cut column is grass.
   - A tree with any log in the cut goes whole: its connected logs, and every leaf whose nearest log is one of them.
Only ground blocks (stone, dirt, grass, ores, plants, logs, leaves) are ever removed; anything built stays.
"""
import json, sys
from collections import Counter, deque
from pathlib import Path
from mca import REGION, World
from float_fix import guards

AIR = 'minecraft:air'
GRASS = 'minecraft:grass_block[snowy=false]'
DIRT = 'minecraft:dirt'
CAP = 'minecraft:light_gray_concrete'

SHAFT = (-191, -175, 81, 97)
SHAFT_TOP = 86
CAP_Y = 68
BLEND = 8

HOUSES = [dict(name='x125-145 z-682', floor=69, seeds=[(138, -679), (144, -679)]),
          dict(name='x37-62 z-630', floor=71, seeds=[(43, -616)])]
HOUSE_SPAN = 14          # a house column holds a built block within floor + 1 .. floor + 14
SETBACK = 3
SLOPE_REACH = 22         # columns past the setback the 45 degree slope may need

PLANTS = ('grass', 'tall_grass', 'fern', 'large_fern', 'dandelion', 'poppy', 'azure_bluet', 'oxeye_daisy', 'cornflower',
          'sweet_berry_bush', 'dead_bush', 'azalea', 'flowering_azalea', 'moss_carpet', 'snow', 'vine')
SOLID_GROUND = ('stone', 'dirt', 'grass_block', 'coarse_dirt', 'rooted_dirt', 'podzol', 'gravel', 'granite', 'diorite',
                'andesite', 'tuff', 'moss_block', 'clay', 'sand', 'mud')


def name(s):
    return (s or '').split('[')[0].split(':')[-1]


def is_air(s):
    return name(s) in ('air', 'cave_air', 'void_air')


def is_log(s):
    return name(s).endswith('_log')


def is_leaf(s):
    return name(s).endswith('_leaves')


def is_ground(s):
    n = name(s)
    return n in SOLID_GROUND or n in PLANTS or n.endswith(('_ore', '_log', '_leaves'))


def is_solid_ground(s):
    n = name(s)
    return n in SOLID_GROUND or n.endswith('_ore')


class Plan:
    def __init__(self, w):
        self.w = w
        self.want = {}                      # (x, y, z) -> new state
        self.parts = Counter()
        self.footprint = set()           # house and shaft columns (their own walls hold them up)
        self.keepout = set()             # footprint plus the setback: no tree may stand here
        self.zone = set()                # every column the work reshapes (trees there are checked)

    def get(self, x, y, z):
        p = (x, y, z)
        return self.want[p] if p in self.want else self.w.get(x, y, z)

    def put(self, p, state, part):
        if self.w.get(*p) == state:
            self.want.pop(p, None)
            return
        self.want[p] = state
        self.parts[part] += 1


def top_solid(plan, x, z, hi, lo):
    """Highest block in hi..lo that is neither air nor a plant/log/leaf (the ground or something built)."""
    for y in range(hi, lo - 1, -1):
        s = plan.get(x, y, z)
        if s is None:
            return None
        if is_air(s) or name(s) in PLANTS or is_log(s) or is_leaf(s):
            continue
        return y
    return lo - 1


def built_between(w, x, z, lo, hi):
    for y in range(lo, hi + 1):
        s = w.get(x, y, z)
        if s is None:
            return False
        if not is_air(s) and not is_ground(s):
            return True
    return False


def house(plan, h, report):
    w, floor = plan.w, h['floor']
    seen, queue = set(), deque(h['seeds'])
    while queue:
        x, z = queue.popleft()
        if (x, z) in seen or not built_between(w, x, z, floor + 1, floor + HOUSE_SPAN):
            continue
        seen.add((x, z))
        if len(seen) > 4000:
            raise SystemExit(f'{h["name"]}: the house outline runs away')
        queue.extend([(x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)])
    plan.footprint |= seen
    plan.keepout |= seen
    plan.zone |= seen
    xs, zs = [p[0] for p in seen], [p[1] for p in seen]
    hi = floor + HOUSE_SPAN + 20
    # inside: every ground block above the floor
    for x, z in seen:
        for y in range(floor + 1, hi):
            if is_ground(w.get(x, y, z)):
                plan.put((x, y, z), AIR, 'house inside')
    # around: setback, then 45 degrees
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    reach = SETBACK + SLOPE_REACH
    dist = {}
    queue = deque((p, 0) for p in seen)
    while queue:
        (x, z), d = queue.popleft()
        if (x, z) in dist:
            continue
        dist[x, z] = d
        if d < reach:
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    q = (x + dx, z + dz)
                    if q not in dist:
                        queue.append((q, d + 1))
    cut_cols = 0
    for (x, z), d in dist.items():
        if d == 0:
            continue
        allowed = floor if d <= SETBACK else floor + d - SETBACK
        plan.zone.add((x, z))
        if d <= SETBACK:
            plan.keepout.add((x, z))
        removed = False
        for y in range(allowed + 1, hi):
            s = w.get(x, y, z)
            if s is not None and is_ground(s) and not is_log(s) and not is_leaf(s):
                plan.put((x, y, z), AIR, 'hill cut')
                removed = True
        if removed:
            cut_cols += 1
            y = top_solid(plan, x, z, allowed, floor - 6)
            if y is not None and y >= floor - 6 and is_solid_ground(plan.get(x, y, z)):
                plan.put((x, y, z), GRASS, 'hill cut')
    report.append(dict(house=h['name'], columns=len(seen), box=[x0, x1, z0, z1], cut_columns=cut_cols))


def shaft(plan, report):
    w = plan.w
    x0, x1, z0, z1 = SHAFT
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            plan.footprint.add((x, z))
            plan.keepout.add((x, z))
            plan.zone.add((x, z))
            for y in range(CAP_Y + 1, SHAFT_TOP + 1):
                plan.put((x, y, z), AIR, 'shaft above cover')
            plan.put((x, CAP_Y, z), CAP, 'shaft cover')
    graded = Counter()
    for x in range(x0 - BLEND, x1 + BLEND + 1):
        for z in range(z0 - BLEND, z1 + BLEND + 1):
            if x0 <= x <= x1 and z0 <= z <= z1:
                continue
            d = max(x0 - x, x - x1, z0 - z, z - z1, 0)
            lo, hi = CAP_Y - d, CAP_Y + d
            plan.zone.add((x, z))
            if built_between(w, x, z, CAP_Y - BLEND - 2, CAP_Y + BLEND + 12):
                graded['skipped (built)'] += 1
                continue
            top = top_solid(plan, x, z, CAP_Y + BLEND + 12, CAP_Y - BLEND - 4)
            if top > hi:
                for y in range(hi + 1, CAP_Y + BLEND + 13):
                    t = w.get(x, y, z)
                    if is_ground(t) and not is_log(t) and not is_leaf(t):
                        plan.put((x, y, z), AIR, 'shaft grading')
                plan.put((x, hi, z), GRASS, 'shaft grading')
                graded['cut'] += 1
            elif top < lo:
                for y in range(top + 1, lo):
                    plan.put((x, y, z), DIRT, 'shaft grading')
                plan.put((x, top, z), DIRT, 'shaft grading') if name(w.get(x, top, z)) == 'grass_block' else None
                plan.put((x, lo, z), GRASS, 'shaft grading')
                # plants standing on the old top would now be buried; lift nothing, just clear them
                for y in range(lo + 1, lo + 3):
                    if name(w.get(x, y, z)) in PLANTS:
                        plan.put((x, y, z), AIR, 'shaft grading')
                graded['filled'] += 1
    report.append(dict(shaft=SHAFT, cover_y=CAP_Y, graded=dict(graded)))


def trees(plan):
    """Trees standing in reshaped columns. A tree is its 26-connected logs plus every leaf whose nearest log (within 4) is
    one of them. If its trunk base no longer sits on the ground top, the whole tree moves down (or up) onto the new
    ground; a tree touching the house, its setback or the shaft goes whole. Unchanged trees stay as they are."""
    w = plan.w
    logs = set()
    for x, z in plan.zone:
        for y in range(40, 110):
            if is_log(w.get(x, y, z)):
                logs.add((x, y, z))
    comps, owner = [], {}
    for start in logs:
        if start in owner:
            continue
        comp, queue = set(), deque([start])
        while queue:
            p = queue.popleft()
            if p in comp:
                continue
            comp.add(p)
            x, y, z = p
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        q = (x + dx, y + dy, z + dz)
                        if q not in comp and is_log(w.get(*q)):
                            queue.append(q)
        i = len(comps)
        comps.append(comp)
        for p in comp:
            owner[p] = i
    R = 4
    leaves = [set() for _ in comps]
    cand = set()
    for x, y, z in owner:
        for dx in range(-R, R + 1):
            for dy in range(-R, R + 1):
                for dz in range(-R, R + 1):
                    cand.add((x + dx, y + dy, z + dz))
    for x, y, z in cand:
        if not is_leaf(w.get(x, y, z)):
            continue
        for r in range(1, R + 1):
            hit = None
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    for dz in range(-r, r + 1):
                        if max(abs(dx), abs(dy), abs(dz)) == r and hit is None:
                            q = (x + dx, y + dy, z + dz)
                            if is_log(w.get(*q)):
                                hit = q
            if hit is not None:
                if hit in owner:
                    leaves[owner[hit]].add((x, y, z))
                break
    clears, places, stat = set(), {}, Counter()
    for i, comp in enumerate(comps):
        base = min(comp, key=lambda p: (p[1], p[0], p[2]))
        bx, by, bz = base
        ground = top_solid(plan, bx, bz, by + 6, by - 30)
        dy = ground + 1 - by
        cols = {(x, z) for x, y, z in comp}
        if dy == 0 and not (cols & plan.footprint):
            stat['unchanged'] += 1
            continue
        body = comp | leaves[i]
        clears |= body
        if cols & plan.keepout:
            stat['removed'] += 1
            continue
        stat['moved'] += 1
        for p in body:
            q = (p[0], p[1] + dy, p[2])
            if (q[0], q[2]) in plan.keepout:
                continue
            places[q] = w.get(*p)
    for p in clears:
        plan.put(p, AIR, 'trees')
    placed = 0
    for q, state in places.items():
        cur = plan.get(*q)
        if is_air(cur) or name(cur) in PLANTS:
            plan.put(q, state, 'trees')
            placed += 1
    stat['blocks cleared'] = len(clears)
    stat['blocks placed'] = placed
    return dict(stat)


def floating(plan):
    """Built blocks left with air under them by the cut (reported, never removed)."""
    out = []
    w = plan.w
    for (x, y, z), s in plan.want.items():
        if not is_air(s):
            continue
        if (x, z) in plan.footprint:
            continue
        above = plan.get(x, y + 1, z)
        if above and not is_air(above) and not is_ground(above):
            out.append([x, y + 1, z, above])
    return out


def main(out, parts=('shaft', 'houses')):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    w = World(REGION)
    plan = Plan(w)
    report = []
    if 'shaft' in parts:
        shaft(plan, report)
    if 'houses' in parts:
        for h in HOUSES:
            house(plan, h, report)
    tree_report = trees(plan)
    fl = floating(plan)
    water = sorted({p for p in plan.want for q in [(p[0] + 1, p[1], p[2]), (p[0] - 1, p[1], p[2]), (p[0], p[1], p[2] + 1),
                                                   (p[0], p[1], p[2] - 1), (p[0], p[1] + 1, p[2])]
                    if name(w.get(*q)) in ('water', 'lava') and q not in plan.want})
    rows = []
    for (x, y, z), want in sorted(plan.want.items()):
        cur = w.get(x, y, z)
        if cur is None:
            raise SystemExit(f'{x},{y},{z} not generated')
        if cur == want:
            continue
        if w.block_entity(x, y, z):
            raise SystemExit(f'{x},{y},{z} {cur} carries a block entity')
        rows.append([x, y, z, cur, want])
    protected = set()
    for g in guards():
        if hasattr(g, 'inside'):
            protected |= g.inside([tuple(r[:3]) for r in rows])
    held = [r for r in rows if tuple(r[:3]) in protected]
    rows = [r for r in rows if tuple(r[:3]) not in protected]
    for g in guards():
        g.assert_positions([tuple(r[:3]) for r in rows])
    (out / 'held.json').write_text(json.dumps(held), 'utf8')
    kinds = Counter((name(r[3]), name(r[4])) for r in rows)
    (out / 'rows.json').write_text(json.dumps(rows), 'utf8')
    xs, ys, zs = zip(*[r[:3] for r in rows])
    rep = dict(rows=len(rows), held=len(held), held_box=[min(r[i] for r in held) for i in range(3)] + [max(r[i] for r in held) for i in range(3)] if held else None, parts=dict(plan.parts), areas=report, trees=tree_report,
               floating=fl[:40], floating_count=len(fl), water_next_to_change=len(water),
               box=[min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)],
               kinds=[[a, b, n] for (a, b), n in kinds.most_common(30)])
    (out / 'report.json').write_text(json.dumps(rep, indent=1), 'utf8')
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], ('houses',) if '--houses' in sys.argv else ('shaft',) if '--shaft' in sys.argv else ('shaft', 'houses'))
