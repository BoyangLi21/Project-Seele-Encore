"""Forest from the Ministry of the Environment vegetation survey (現存植生図2024, PDL 1.0).

`classes` rasterises the survey polygons onto the block grid as planting classes: conifer
plantation, pine, broadleaf, bamboo, shrub and open ground. `edits` plants them as a cell
patch: conical conifers in rows, irregular broadleaf, on natural soil only and clear of roads,
rails, cableways, buildings, stations and water. Existing trees stay.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
import sqlite3

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation
import shapely

from map_pipeline.launch_protection import load as load_launch_protection
from map_pipeline.native_rails import load_rails
from plan_ashi_landscape_r54 import PLANTS
from plan_station_access_corridor import CapturedSurface
from query_blocks import AIR

# Map frame: local equirectangular about the Sengokuhara anchor, 4 m per block (geography.json).
ANCHOR_LON, ANCHOR_LAT, ANCHOR_X, ANCHOR_Z = 139.0085, 35.2662, 30, 220
METRES_PER_BLOCK = 4.0
A, E2 = 6378137.0, 0.00669437999014

OPEN, CONIFER, PINE, BROADLEAF, BAMBOO, SHRUB, UNSURVEYED = 1, 2, 3, 4, 5, 6, 0
# Columns either side of a rail no tree may stand over: the train's body, or a swinging cabin.
RAIL_CLEARANCE = {'TRAIN': 4, 'CABLE_CAR': 6}
GROWS_ON = {'minecraft:grass_block', 'minecraft:dirt', 'minecraft:podzol', 'minecraft:coarse_dirt', 'minecraft:rooted_dirt'}
NAMES = {OPEN: 'open', CONIFER: 'conifer', PINE: 'pine', BROADLEAF: 'broadleaf', BAMBOO: 'bamboo', SHRUB: 'shrub', UNSURVEYED: 'unsurveyed'}


def planting_class(legend, group):
    """Planting class of one survey legend entry and its broad group."""
    if '竹' in legend or legend in ('メダケ群落', 'ハコネダケ群落', 'アズマネザサ群落'):
        return BAMBOO if '竹' in legend else SHRUB
    if legend == 'スギ・ヒノキ・サワラ植林' or 'モミ' in legend and 'モミジ' not in legend:
        return CONIFER
    if legend in ('クロマツ植林', 'アカマツ植林') or 'アカマツ群集' in legend:
        return PINE
    if '低木' in legend or 'ウツギ' in legend or '風衝' in legend:
        return SHRUB
    if legend in ('残存・植栽樹群地', '残存・植栽樹群をもった公園、墓地等', 'ケヤキ屋敷林', 'その他植林', 'クスノキ植林', 'ニセアカシア群落'):
        return BROADLEAF
    if group in ('ヤブツバキクラス域自然植生', 'ブナクラス域自然植生') and '草' not in legend and 'シモツケソウ' not in legend:
        return BROADLEAF
    if group in ('ヤブツバキクラス域代償植生', 'ブナクラス域代償植生') and any(t in legend for t in ('コナラ', 'ミズナラ', 'シデ', 'シイ', 'カシ', 'ブナ', 'ケヤキ', 'アカメガシワ')):
        return BROADLEAF
    return OPEN


def to_world(lon, lat):
    phi = math.radians(ANCHOR_LAT)
    w = 1 - E2 * math.sin(phi) ** 2
    meridian, normal = A * (1 - E2) / w ** 1.5, A / w ** .5
    x = ANCHOR_X + np.radians(lon - ANCHOR_LON) * normal * math.cos(phi) / METRES_PER_BLOCK
    z = ANCHOR_Z - np.radians(lat - ANCHOR_LAT) * meridian / METRES_PER_BLOCK
    return x, z


def from_world(x, z):
    phi = math.radians(ANCHOR_LAT)
    w = 1 - E2 * math.sin(phi) ** 2
    meridian, normal = A * (1 - E2) / w ** 1.5, A / w ** .5
    return ANCHOR_LON + math.degrees((x - ANCHOR_X) * METRES_PER_BLOCK / (normal * math.cos(phi))), ANCHOR_LAT - math.degrees((z - ANCHOR_Z) * METRES_PER_BLOCK / meridian)


def classes(a):
    spec = json.loads(a.config.read_text('utf8'))
    x0, z0, x1, z1 = spec['bounds']
    image = Image.new('L', (x1 - x0 + 1, z1 - z0 + 1), UNSURVEYED)
    draw = ImageDraw.Draw(image)
    west, north = from_world(x0, z0)
    east, south = from_world(x1 + 1, z1 + 1)
    polygons = []
    for path in spec['surveys']:
        table = Path(path).stem
        with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
            rows = db.execute(f'select v.geom, v."凡例名", v."植生区分" from "{table}" v join "rtree_{table}_geom" r on v.fid = r.id '
                              'where r.maxx >= ? and r.minx <= ? and r.maxy >= ? and r.miny <= ?', (west, east, south, north))
            for blob, legend, group in rows:
                flags = blob[3]
                envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(flags >> 1) & 7]
                polygons.append((shapely.from_wkb(bytes(blob[8 + envelope:])), planting_class(legend or '', group or '')))
    polygons.sort(key=lambda p: -p[0].area)        # holes hold smaller polygons, drawn after them
    counts = {}
    for shape, kind in polygons:
        for part in getattr(shape, 'geoms', [shape]):
            def pixels(ring):
                xs, zs = to_world(*np.asarray(ring.coords)[:, :2].T)
                return list(zip(xs - x0, zs - z0))
            draw.polygon(pixels(part.exterior), fill=kind)
            for hole in part.interiors:
                draw.polygon(pixels(hole), fill=UNSURVEYED)
        counts[NAMES[kind]] = counts.get(NAMES[kind], 0) + 1
    grid = np.asarray(image, np.uint8)
    a.out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out / 'classes.npz', bounds=np.array([x0, z0, x1, z1]), classes=grid)
    summary = dict(polygons=len(polygons), polygon_counts=counts, cells={NAMES[k]: int((grid == k).sum()) for k in NAMES}, world_written=False)
    (a.out / 'classes.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(summary, ensure_ascii=False))


def leaf(name):
    return f'minecraft:{name}_leaves[distance=1,persistent=true,waterlogged=false]'


def log(name):
    return f'minecraft:{name}_log[axis=y]'


def conifer(rng, tall, wood, needles):
    """Conical crown, narrowing layer by layer to a point; hollow, since inner leaves never show."""
    height = rng.randint(*tall)
    cells = [(0, k, 0, log(wood)) for k in range(1, height + 1)]
    base = rng.randint(2, 3)
    for k in range(base, height + 1):
        taper = (height + 1 - k) / max(1, height + 1 - base)
        # Never thinner than the four cells around the log, or the top of the trunk stands bare.
        radius = max(1.05, 2.6 * taper ** .85 * (1 if (k - base) % 2 == 0 else .72))
        reach = int(radius + .5)
        for dx in range(-reach, reach + 1):
            for dz in range(-reach, reach + 1):
                d = dx * dx + dz * dz
                if d <= radius * radius + .3 and d > (radius - 1.2) ** 2 and (dx or dz):
                    cells.append((dx, k, dz, leaf(needles)))
    # The leaf cap closes over the last log and the tip stands two above it.
    cells += [(dx, height + 1, dz, leaf(needles)) for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))]
    cells.append((0, height + 2, 0, leaf(needles)))
    return cells


def broadleaf(rng, kinds):
    """Irregular round crown, shell only."""
    wood, foliage = rng.choice(kinds)
    height = rng.randint(5, 8)
    radius = rng.uniform(2.2, 3.4)
    squash = rng.uniform(.65, .85)
    cells = [(0, k, 0, log(wood)) for k in range(1, height)]
    middle = height - .5
    reach = int(radius + 1)
    for dx in range(-reach, reach + 1):
        for dz in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                d = math.sqrt(dx * dx + dz * dz + (dy / squash) ** 2)
                if radius - 1.15 < d <= radius and rng.random() > .06:
                    cells.append((dx, int(middle + dy), dz, leaf(foliage)))
    return cells


def shrub(rng):
    wood, foliage = rng.choice((('oak', 'oak'), ('birch', 'birch')))
    cells = [(0, 1, 0, log(wood))]
    for dx in range(-1, 2):
        for dz in range(-1, 2):
            for dy in (1, 2):
                if (dx or dz or dy == 2) and abs(dx) + abs(dz) + dy < 4:
                    cells.append((dx, dy, dz, leaf(foliage)))
    return cells


def attached(cells, x0, z0):
    """Cells still joined to the trunk base; a crown shaved by a slope must not leave floating leaves."""
    index = {(x, y, z): s for x, y, z, s in cells}
    start = min((c for c in index if c[0] == x0 and c[2] == z0), key=lambda c: c[1])
    seen, frontier = {start}, [start]
    while frontier:
        following = []
        for x, y, z in frontier:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        n = (x + dx, y + dy, z + dz)
                        if n in index and n not in seen:
                            seen.add(n)
                            following.append(n)
        frontier = following
    return [(x, y, z, index[(x, y, z)]) for x, y, z in seen]


def in_launch_volume(guard, cells):
    """Whether any cell of a tree stands in the space an EVA launches through."""
    try:
        guard.assert_positions([c[:3] for c in cells])
    except ValueError:
        return True
    return False


def keep_outs(spec, source):
    """Columns nothing of a tree may stand over, columns already holding a tree, and the road columns."""
    x0, z0, x1, z1 = source.bounds
    top, highest, full = (source.measured[k] for k in ('top', 'highest', 'full'))
    top, highest = top.astype(int), highest.astype(int)
    authority = Path(spec['authority'])
    with np.load(spec.get('network', authority / 'network.npz')) as f:
        ax, az = map(int, f['bounds'][:2])
        walk = f['walk'][z0 - az:z1 - az + 1, x0 - ax:x1 - ax + 1]
    keep_out = walk | ~full | (top < -120)
    existing = np.zeros(top.shape, bool)
    structures = np.zeros(top.shape, bool)
    for iz, ix in np.argwhere(full & (highest > top)):
        x, z = int(ix + x0), int(iz + z0)
        for y in range(int(top[iz, ix]) + 1, int(highest[iz, ix]) + 1):
            name = source.state(x, y, z).split('[')[0]
            if name in AIR or name in PLANTS:
                continue
            if name.endswith(('_leaves', '_log')):
                existing[iz, ix] = True
            else:
                structures[iz, ix] = True
                break
    catalog = [r['occupied_bounds'] for r in json.loads((authority / 'catalog.json').read_text('utf8')) if r.get('occupied_bounds')]
    for b in catalog + json.loads((authority / 'station-volumes.json').read_text('utf8')):
        structures[max(0, b[2] - z0):max(0, b[5] - z0 + 1), max(0, b[0] - x0):max(0, b[3] - x0 + 1)] = True
    keep_out |= binary_dilation(structures, iterations=2)
    for rail in load_rails(spec['native_snapshot']):
        if rail['mode'] not in RAIL_CLEARANCE:
            continue
        p, q = np.array(rail['a'], float)[[0, 2]], np.array(rail['b'], float)[[0, 2]]
        reach = RAIL_CLEARANCE[rail['mode']]
        for t in np.linspace(0, 1, max(2, int(np.linalg.norm(q - p)) + 1)):
            jx, jz = (p + (q - p) * t).astype(int) - (x0, z0)
            keep_out[max(0, jz - reach):max(0, jz + reach + 1), max(0, jx - reach):max(0, jx + reach + 1)] = True
    # Areas left open whatever the survey says, such as the street grid of the retractable city.
    for a, b, c, d in spec.get('no_plant', ()):
        keep_out[max(0, b - z0):max(0, d - z0 + 1), max(0, a - x0):max(0, c - x0 + 1)] = True
    return keep_out, existing, walk


def edits(a):
    spec = json.loads(a.config.read_text('utf8'))
    source = CapturedSurface(spec['source'], partial=True)
    x0, z0, x1, z1 = source.bounds
    top, full = source.measured['top'].astype(int), source.measured['full']
    with np.load(spec['classes']) as f:
        cx, cz = map(int, f['bounds'][:2])
        kinds = f['classes'][z0 - cz:z1 - cz + 1, x0 - cx:x1 - cx + 1]
    keep_out, existing, walk = keep_outs(spec, source)
    guard = load_launch_protection(spec['launch_world']) if spec.get('launch_world') else None
    rng = random.Random(spec.get('seed', 1))
    spacing = {CONIFER: spec.get('conifer_spacing', 5), PINE: spec.get('pine_spacing', 7), BROADLEAF: spec.get('broadleaf_spacing', 7), BAMBOO: 9, SHRUB: spec.get('shrub_spacing', 9)}
    rows, trees = {}, Counter()

    def plant(kind):
        if kind == CONIFER:
            return conifer(rng, (11, 15), 'spruce', 'spruce') if rng.random() < .6 else conifer(rng, (10, 13), 'spruce', 'dark_oak')
        if kind == PINE:
            return broadleaf(rng, (('spruce', 'jungle'), ('oak', 'spruce')))
        if kind == SHRUB:
            return shrub(rng)
        return broadleaf(rng, (('oak', 'oak'), ('oak', 'oak'), ('birch', 'birch'), ('dark_oak', 'dark_oak')))
    for kind, step in spacing.items():
        loose = 3 if kind == CONIFER else step - 1      # plantations loosely keep their rows, broadleaf wanders
        for iz in range(0, top.shape[0], step):
            for ix in range(0, top.shape[1], step):
                jz, jx = iz + rng.randint(0, loose), ix + rng.randint(0, loose)
                if not (0 <= jz < top.shape[0] and 0 <= jx < top.shape[1]) or kinds[jz, jx] != kind or keep_out[jz, jx] or existing[jz, jx]:
                    continue
                if 'core' in spec and not (spec['core'][0] <= jx + x0 <= spec['core'][2] and spec['core'][1] <= jz + z0 <= spec['core'][3]):
                    continue                    # the margin is for crowns of trunks inside the core, so tiles join without a seam
                x, z, y = int(jx + x0), int(jz + z0), int(top[jz, jx])
                if source.state(x, y, z).split('[')[0] not in GROWS_ON:
                    continue
                cells = []
                ok = True
                for dx, dy, dz, state in plant(kind):
                    jjz, jjx = jz + dz, jx + dx
                    if not (0 <= jjz < top.shape[0] and 0 <= jjx < top.shape[1]) or keep_out[jjz, jjx]:
                        ok = False
                        break
                    here = (x + dx, y + dy, z + dz)
                    name = source.state(*here).split('[')[0]
                    if name in AIR or name in PLANTS:
                        if here not in rows:
                            cells.append((*here, state))
                    elif dx == 0 and dz == 0:
                        ok = False                  # the trunk itself must stand clear
                        break
                if not ok or len(cells) < 4:
                    continue
                if not any(c[0] == x and c[2] == z for c in cells):
                    continue
                if guard and in_launch_volume(guard, cells):
                    continue
                for cx_, cy_, cz_, state in attached(cells, x, z):
                    rows[cx_, cy_, cz_] = dict(pos=[cx_, cy_, cz_], before=source.state(cx_, cy_, cz_), after=state, purpose='forest ' + NAMES[kind])
                trees[NAMES[kind]] += 1
    a.out.mkdir(parents=True, exist_ok=True)
    land = full & (top > -120) & ~walk
    report = dict(errors=[], land_columns=int(land.sum()), forest_class_columns=int((land & np.isin(kinds, list(spacing))).sum()), trees=dict(trees),
                  total_trees=sum(trees.values()), cells=len(rows), cells_per_tree=round(len(rows) / max(1, sum(trees.values())), 1), world_written=False)
    (a.out / 'forest-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf8')
    (a.out / 'patch.json').write_text(json.dumps(dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'], edits=[rows[k] for k in sorted(rows)],
          native_snapshot=spec['native_snapshot'], error_reports=[str((a.out / 'forest-check.json').resolve())], views_reviewed_by_root=False, continuation_work=spec['continuation_work']), ensure_ascii=False), 'utf8')
    print(json.dumps(report, ensure_ascii=False))


def audit(a):
    """Read an installed forest back from a fresh capture: what stands, and whether it stands right."""
    spec = json.loads(a.config.read_text('utf8'))
    source = CapturedSurface(a.capture, partial=True)
    x0, z0, x1, z1 = source.bounds
    keep_out = keep_outs(spec, source)[0]
    cells = {tuple(e['pos']): e['after'] for e in json.loads((a.out / 'patch.json').read_text('utf8'))['edits'] if x0 <= e['pos'][0] <= x1 and z0 <= e['pos'][2] <= z1}
    absent = [p for p, s in cells.items() if source.state(*p) != s]
    over = [p for p in cells if keep_out[p[2] - z0, p[0] - x0]]
    rooted = {p for p, s in cells.items() if '_log[' in s and source.state(p[0], p[1] - 1, p[2]).split('[')[0] in GROWS_ON}
    seen, floating, trees = set(), [], 0
    for start in cells:
        if start in seen:
            continue
        group, frontier = {start}, [start]
        while frontier:
            x, y, z = frontier.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        n = (x + dx, y + dy, z + dz)
                        if n in cells and n not in group:
                            group.add(n)
                            frontier.append(n)
        seen |= group
        trees += 1
        if not group & rooted:
            floating.append(min(group))
    report = dict(errors=[f'{len(absent)} cells not as planned'] * bool(absent) + [f'{len(over)} cells over a keep-out column'] * bool(over) + [f'{len(floating)} groups with no trunk on soil'] * bool(floating),
                  cells=len(cells), tree_groups=trees, rooted_trunks=len(rooted), examples=dict(absent=absent[:5], over=over[:5], floating=floating[:5]), world_written=False)
    (a.out / 'forest-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('classes', 'edits', 'audit'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--capture', type=Path, help='audit: a capture taken after the install')
    arguments = parser.parse_args()
    globals()[arguments.mode](arguments)
