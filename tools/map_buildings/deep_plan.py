"""Rows that take a swallowed building away and close the slope over its place.

The building is the flooded set of building blocks above its floor (deep_check.building_set).
Over its columns the new ground height comes from the terrain around it (inverse-distance
average of the ground 1..4 columns outside); below it earth (grass, three dirt, then stone),
above it air. Only the building's own blocks, open cells and natural cells are written.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, is_natural, short, base
from e5_plan import is_building, is_veg
import deep_check as dc

GRASS, DIRT, STONE, AIRS = 'minecraft:grass_block[snowy=false]', 'minecraft:dirt', 'minecraft:stone', 'minecraft:air'
w = dc.w


def ground(x, z, top):
    y = top
    while y > top - 80:
        s = w.get(x, y, z)
        if s is None:
            return None
        if is_natural(s):
            return y
        if not (is_open(s) or is_veg(s)):
            return None          # built over: not a ground sample
        y -= 1
    return None


def plan_building(b):
    cells = dc.building_set(b)
    if b.get('blocks'):     # take only these blocks (a leftover pad next to a road the flood would reach)
        cells = {c for c in cells if base(w.get(*c)).split(':')[-1] in b['blocks']}
    cols = {(x, z) for x, y, z in cells}
    x0 = min(c[0] for c in cols); x1 = max(c[0] for c in cols)
    z0 = min(c[1] for c in cols); z1 = max(c[1] for c in cols)
    F, hi = b['floor'], max(y for _, y, _ in cells) + 1
    samples = []
    for x in range(x0 - 4, x1 + 5):
        for z in range(z0 - 4, z1 + 5):
            if (x, z) in cols:
                continue
            d = min(max(abs(x - cx), abs(z - cz)) for cx, cz in cols) if len(cols) < 400 else 1
            if 1 <= d <= 4:
                g = ground(x, z, hi + 20)
                if g is not None:
                    samples.append((x, z, g))
    rows = {}
    for (x, z) in cols:
        num = den = 0.0
        for sx, sz, g in samples:
            wgt = 1.0 / ((sx - x) ** 2 + (sz - z) ** 2)
            num += wgt * g
            den += wgt
        S = round(num / den) if den else F
        for y in range(F + 1, max(hi, S) + 1):
            cur = w.get(x, y, z)
            if (x, y, z) not in cells and not (is_open(cur) or is_natural(cur)):
                continue
            want = GRASS if y == S else DIRT if S - 3 <= y < S else STONE if y < S else AIRS
            if y > S and cur in ('minecraft:air', 'minecraft:cave_air'):
                continue
            if cur != want and not (want == STONE and is_natural(cur) and (x, y, z) not in cells):
                rows[x, y, z] = [x, y, z, cur, want]
    blend(rows, cols)
    tidy(rows, cols, cells, heights=b.get("set_heights"))
    if b.get('drop_signs'):
        drop_signs(rows, b, F, hi)
    keep_be = bool(b.get('drop_signs'))
    return [r for r in rows.values() if (keep_be or not w.block_entity(*r[:3])) and r[3] != r[4]], len(samples)


def drop_signs(rows, b, F, hi):
    """Signs and banners left in a closed ruin go too (the writer then needs --allow-block-entities):
    each becomes what most of its six neighbours are after the fill."""
    x0, z0, x1, z1 = b['bbox']

    def after(c):
        return rows[c][4] if c in rows else w.get(*c)
    for x in range(x0 - 2, x1 + 3):
        for z in range(z0 - 2, z1 + 3):
            for y in range(F - 2, hi + 8):
                s = w.get(x, y, z) or ''
                if not any(k in s for k in ('_sign', '_banner')):
                    continue
                around = Counter(after(n) for n in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)))
                fill = next((a for a, _ in around.most_common() if a and not any(k in a for k in ('_sign', '_banner'))), AIRS)
                if not (is_open(fill) or is_natural(fill)):
                    fill = AIRS
                if base(fill) == 'minecraft:grass_block' and not is_open(after((x, y + 1, z)) or AIRS):
                    fill = DIRT         # buried: earth, not turf
                rows[x, y, z] = [x, y, z, s, fill]


def tidy(rows, cols, cells, reach=18, heights=None):
    """After the fill: no lone pillar or 1-2 column island, and no step of two or more next to a
    changed column. Natural terraces are contour steps; a raised column with fewer than two
    neighbours at its height is lowered to its second-highest neighbour, then every step of two
    or more beside a changed column is eased by raising the lower side to one below. Only
    natural ground, the ruin's own blocks and open cells are touched; a column with a tree on it
    keeps its height."""
    def get(c):
        return rows[c][4] if c in rows else w.get(*c)

    def set_(c, after):
        cur = w.get(*c)
        if c in rows:
            rows[c][4] = after
        elif cur != after:
            rows[c] = [*c, cur, after]

    def top(x, z):
        y = 200
        while y > -64:
            s = get((x, y, z))
            if s is None:
                return None
            if not (is_open(s) or is_veg(s)):
                return y if (is_natural(s) or (x, y, z) in cells) else None
            y -= 1
        return None
    region = set()
    for (x, z) in cols:
        for dx in range(-reach, reach + 1):
            for dz in range(-reach, reach + 1):
                region.add((x + dx, z + dz))
    H = {}
    for c in region:
        t = top(*c)
        if t is not None:
            H[c] = t
    changed_cols = {(r[0], r[2]) for r in rows.values()}
    nb4 = lambda c: ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1))

    def lower(c, t):
        x, z = c
        if is_veg(get((x, H[c] + 1, z)) or '') and '_log' in (get((x, H[c] + 1, z)) or ''):
            return False
        for y in range(t + 1, H[c] + 1):
            set_((x, y, z), AIRS)
        s = get((x, t, z))
        if s and (is_natural(s) or (x, t, z) in cells):
            set_((x, t, z), GRASS)
        H[c] = t
        changed_cols.add(c)
        return True

    def raise_(c, t):
        x, z = c
        for y in range(H[c] + 1, t + 1):
            if not (is_open(get((x, y, z))) or is_veg(get((x, y, z)))):
                return False
        if base(get((x, H[c], z))) == 'minecraft:grass_block':
            set_((x, H[c], z), DIRT)
        for y in range(H[c] + 1, t + 1):
            set_((x, y, z), GRASS if y == t else DIRT)
        H[c] = t
        changed_cols.add(c)
        return True
    for _ in range(12):
        moved = 0
        for c in list(H):
            ns = [H[n] for n in nb4(c) if n in H]
            if len(ns) < 4:
                continue
            if sum(h >= H[c] for h in ns) < 2:
                t = sorted(ns)[-2]
                if t < H[c] and lower(c, t):
                    moved += 1
        # straighten contours: a one-column jog in a terrace edge shows a single dirt face that reads as
        # a lone post, so each changed column takes the median height of its 3x3 neighbourhood
        for c in list(H):
            if c not in changed_cols:
                continue
            box = sorted(H[n] for n in ((c[0] + dx, c[1] + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)) if n in H)
            if len(box) < 9:
                continue
            m = box[4]
            if m > H[c] and raise_(c, m):
                moved += 1
            elif m < H[c] and lower(c, m):
                moved += 1
        for c in list(H):
            if c not in changed_cols:
                continue
            for n in nb4(c):
                if n in H and H[c] - H[n] >= 2 and raise_(n, H[c] - 1):
                    moved += 1
        if not moved:
            break
    for c in list(H):      # the median can leave a lone column behind on its last round
        ns = [H[n] for n in nb4(c) if n in H]
        if len(ns) == 4 and sum(h >= H[c] for h in ns) < 2:
            t = sorted(ns)[-2]
            if t < H[c]:
                lower(c, t)
    for x, z, t in heights or ():     # a reviewer's spot fix: these columns end at this ground height
        c = (x, z)
        if c in H and t > H[c]:
            raise_(c, t)
        elif c in H and t < H[c]:
            lower(c, t)


def blend(rows, cols, reach=16):
    """Raise the natural ground around the closed footprint to a 1:1 slope, so no new earth step is
    more than one block high (grass on top, dirt under); open cells and plants only."""
    def top(x, z, start):
        y = start
        while y > -64:
            s = rows[x, y, z][4] if (x, y, z) in rows else w.get(x, y, z)
            if s is None:
                return None
            if not (is_open(s) or is_veg(s)):
                return y if is_natural(s) else None
            y -= 1
        return None
    height = {}
    for (x, z) in cols:
        t = top(x, z, 200)
        if t is not None:
            height[x, z] = t
    ring = set()
    for (x, z) in cols:
        for dx in range(-reach, reach + 1):
            for dz in range(-reach, reach + 1):
                if (x + dx, z + dz) not in cols:
                    ring.add((x + dx, z + dz))
    cur = {}
    for c in ring:
        t = top(c[0], c[1], 200)
        if t is not None:
            cur[c] = t
    changed = True
    want = dict(cur)
    while changed:
        changed = False
        for c in want:
            lim = max((height.get(n, want.get(n, -999)) for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1))), default=-999) - 1
            if lim > want[c]:
                want[c] = lim
                changed = True
    for (x, z), t in want.items():
        y0 = cur[x, z]
        if t <= y0:
            continue
        if base(w.get(x, y0, z)) == 'minecraft:grass_block':
            rows[x, y0, z] = [x, y0, z, w.get(x, y0, z), DIRT]
        for y in range(y0 + 1, t + 1):
            s = w.get(x, y, z)
            if not (is_open(s) or is_veg(s)):
                break
            rows[x, y, z] = [x, y, z, s, GRASS if y == t else DIRT]


if __name__ == '__main__':
    # argv[1]: ids from deep_check's list, or a .json file of specs {id, bbox [x0,z0,x1,z1], floor, roof}
    if sys.argv[1].endswith('.json'):
        chosen = json.load(open(sys.argv[1], encoding='utf8'))
    else:
        ids = sys.argv[1].split(',')
        chosen = [b for b in dc.deep if b['id'] in ids]
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    # buildings are planned one after another over the result of the earlier ones: the world reader
    # sees the planned blocks, and a cell planned twice keeps its original block and the last new one
    combined, report = {}, []
    raw_get = w.get
    w.get = lambda x, y, z: combined[x, y, z][4] if (x, y, z) in combined else raw_get(x, y, z)
    for b in chosen:
        rows, ns = plan_building(b)
        bes = [r[:3] for r in rows if w.block_entity(*r[:3])]
        kinds = Counter(short(r[3]) + '->' + short(r[4]) for r in rows)
        report.append(dict(id=b['id'], bbox=b['bbox'], cells=len(rows), samples=ns, block_entities=bes, kinds=dict(kinds.most_common(10))))
        print(b['id'], len(rows), 'samples', ns, 'BE', len(bes), kinds.most_common(6))
        for r in rows:
            k = tuple(r[:3])
            combined[k] = [*k, combined[k][3] if k in combined else r[3], r[4]]
    w.get = raw_get
    allrows = [r for r in combined.values() if r[3] != r[4]]
    (out / 'rows.json').write_text(json.dumps(allrows), 'utf8')
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf8')
    print('total', len(allrows))
