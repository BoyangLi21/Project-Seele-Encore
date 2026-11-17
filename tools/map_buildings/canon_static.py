"""Canon recolour of the older static buildings of Tokyo-3 (red brick, yellow and orange terracotta, sandstone):
the same buildings in the pale palette of the canon round. The M5 lots had their own pass (canon_recolour, T3);
this one takes every warm building block left above street level in and around the city.

  python canon_static.py <out dir> [survey]

Only building materials are mapped, each to a pale block of the same shape, so stairs, slabs and walls keep every
property. Concrete is left alone (road lines, traffic lights and the armament hazard bands use it), and so is natural
granite. Skipped: the lift-tower footprints (their bodies have their own lists and sync data), the two schools and the
shrine, and the canon homes, which were designed this round.
"""
import io, json, sys
from collections import Counter
from pathlib import Path
import nbtlib
from mca import REGION, WORLD, World, decode, raw_chunks
from city_body_sync import topology
from canon_recolour import KEEP_LOTS, HALF
from float_fix import guards

Y = 80
BOX = (-370, -60, 350, 620)                     # x0, z0, x1, z1: the city and its edge
TOP = 240
PLANS = Path('E:/eva-map-buildings/plans')
HOMES = ('homes-comfort', 'homes-kirisato', 'homes-rei', 'homes-travel')

WHITE, LGREY, GREY = 'white_concrete', 'light_gray_concrete', 'gray_concrete'
FULL = {'bricks': LGREY, 'terracotta': LGREY, 'red_terracotta': LGREY, 'orange_terracotta': LGREY,
        'brown_terracotta': GREY, 'yellow_terracotta': WHITE, 'pink_terracotta': WHITE, 'magenta_terracotta': LGREY,
        'smooth_sandstone': 'smooth_quartz', 'sandstone': 'smooth_quartz', 'cut_sandstone': 'smooth_quartz',
        'chiseled_sandstone': 'chiseled_quartz_block', 'red_sandstone': LGREY, 'smooth_red_sandstone': LGREY,
        'cut_red_sandstone': LGREY, 'chiseled_red_sandstone': LGREY, 'mud_bricks': LGREY, 'packed_mud': LGREY,
        'polished_granite': 'polished_diorite'}
SHAPED = {}                                     # same property set on both sides
for fam, pale in (('brick', 'polished_andesite'), ('sandstone', 'smooth_quartz'), ('smooth_sandstone', 'smooth_quartz'),
                  ('red_sandstone', 'polished_andesite'), ('smooth_red_sandstone', 'polished_andesite'),
                  ('mud_brick', 'polished_andesite'), ('polished_granite', 'polished_diorite')):
    SHAPED[fam + '_stairs'] = pale + '_stairs'
    SHAPED[fam + '_slab'] = pale + '_slab'
SHAPED['cut_sandstone_slab'] = 'smooth_quartz_slab'
SHAPED['cut_red_sandstone_slab'] = 'polished_andesite_slab'
for fam, pale in (('brick', 'andesite'), ('sandstone', 'diorite'), ('red_sandstone', 'andesite'), ('mud_brick', 'andesite')):
    SHAPED[fam + '_wall'] = pale + '_wall'


def pale(state):
    name, _, props = state.partition('[')
    base = name.split(':', 1)[1]
    if base in FULL and not props:
        return 'minecraft:' + FULL[base]
    if base in SHAPED:
        return 'minecraft:' + SHAPED[base] + ('[' + props if props else '')
    return None


def skipped_boxes():
    boxes = []
    for t in topology(WORLD).values():
        cx, cy, cz = t['centre']
        f = t['fp']
        boxes.append((cx + f[0] - 1, cz + f[2] - 1, cx + f[1] + 1, cz + f[3] + 1))
    for cx, cz in KEEP_LOTS:
        boxes.append((cx - HALF, cz - HALF, cx + HALF, cz + HALF))
    for h in HOMES:
        f = PLANS / h / 'rows.json'
        if f.exists():
            rows = json.load(open(f))
            xs, zs = [r[0] for r in rows], [r[2] for r in rows]
            boxes.append((min(xs) - 2, min(zs) - 2, max(xs) + 2, max(zs) + 2))
    return boxes


def main(out, survey=False):
    boxes = skipped_boxes()
    inside = lambda x, z: any(a <= x <= c and b <= z <= d for a, b, c, d in boxes)
    w = World(REGION)
    rows, stats, where = [], Counter(), Counter()
    for rx in range(BOX[0] >> 9, (BOX[2] >> 9) + 1):
        for rz in range(BOX[1] >> 9, (BOX[3] >> 9) + 1):
            f = Path(REGION) / f'r.{rx}.{rz}.mca'
            if not f.exists():
                continue
            for cx, cz, raw in raw_chunks(f):
                x0, z0 = cx * 16, cz * 16
                if x0 + 15 < BOX[0] or x0 > BOX[2] or z0 + 15 < BOX[1] or z0 > BOX[3]:
                    continue
                root = nbtlib.File.parse(io.BytesIO(raw))
                for s in root['sections']:
                    sy = int(s['Y'])
                    if sy * 16 + 15 <= Y or sy * 16 > TOP or 'block_states' not in s:
                        continue
                    ids, pal = decode(s['block_states'])
                    want = {i: pale(n) for i, n in enumerate(pal)}
                    want = {i: v for i, v in want.items() if v}
                    if not want:
                        continue
                    for idx in [k for k, v in enumerate(ids.tolist()) if v in want]:
                        y, z, x = sy * 16 + (idx >> 8), z0 + ((idx >> 4) & 15), x0 + (idx & 15)
                        if y <= Y or not (BOX[0] <= x <= BOX[2] and BOX[1] <= z <= BOX[3]) or inside(x, z):
                            continue
                        before = pal[ids[idx]]
                        if w.get(x, y, z) != before:              # the decoder and the reader must agree
                            stats['reader disagrees'] += 1
                            continue
                        rows.append([x, y, z, before, want[ids[idx]]])
                        stats[before.split('[')[0].split(':')[1]] += 1
                        where[(x // 32 * 32, z // 32 * 32)] += 1
    gs = guards()                                       # launch protection: raised tower volumes, shafts, the lift guards

    def allowed(r):
        try:
            for g in gs:
                g.assert_positions([tuple(r[:3])])
        except ValueError:
            return False
        return True
    kept = [r for r in rows if allowed(r)]
    stats['refused by the launch guards'] = len(rows) - len(kept)
    rows = kept
    for st in {r[4] for r in rows}:
        if '[' in st:
            props = st[st.index('[') + 1:-1].split(',')
            assert props == sorted(props), st
    print(len(rows), stats.most_common(20))
    print('busiest 32-cells', where.most_common(15))
    if survey:
        return
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (Path(out) / 'report.json').write_text(json.dumps(dict(rows=len(rows), blocks=stats, areas={f'{k[0]},{k[1]}': v for k, v in where.most_common()}), indent=1), 'utf8')


if __name__ == '__main__':
    main(sys.argv[1], len(sys.argv) > 2 and sys.argv[2] == 'survey')
