"""Convert declared roads to TrafficCraft blocks.

Surfaces go from half-block steps to eighth-block layers: `asphalt` below, `asphalt_slope
[layers=k]` on top. Steps are smoothed into ramps of at most two layers per block and never
move a surface more than half a block from where it was, so doors, platforms and bridges
still meet it. Footways become `concrete` one layer above the carriageway beside them, with
no half-block kerb. Markings follow Japanese practice: a yellow solid centre line on mountain
roads, a white dashed one in town, white edge lines beside footways, none on lanes under four
blocks wide and none inside junctions. Each marking carries its paint colour as a block entity.
Only paving, slabs, plants and air are replaced; anything else is reported and left.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_station_access_corridor import CapturedSurface
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

LAYERS = 8
MAX_STEP = 2            # layers between neighbours, 25%
DRIFT = 4               # layers a surface may move from where it was
WHITE, YELLOW = 0, 4
DASH = 5                # painted, then the same unpainted
TOWN_BUILDINGS, TOWN_RADIUS = 4, 40
ENTITY = 'trafficcraft:colored_block_entity'
REPLACEABLE = PAVEMENT | AIR | PLANTS | SOIL | {'minecraft:light', 'minecraft:snow'}
# Facing that puts pattern 23's offset line on a side: it lies east when the texture faces north.
EDGE_FACING = {(1, 0): 'north', (0, 1): 'east', (-1, 0): 'south', (0, -1): 'west'}


def paved(state):
    """A road surface block, ours or TrafficCraft's, so a converted road can be converted again."""
    return state.split('[')[0] in PAVEMENT or state.startswith('trafficcraft:')


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1), 'utf8')


def smooth(height, walk, joined, passes=40):
    """Ramps instead of half-block steps: relax towards the neighbours' mean, staying within
    DRIFT of the original, then round and limit each step to MAX_STEP layers."""
    h = height.astype(float)
    low, high = height - DRIFT, height + DRIFT
    for _ in range(passes):
        total, count = np.zeros_like(h), np.zeros_like(h)
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            n = np.roll(h, shift, axis)
            ok = np.roll(joined[axis][..., 0 if shift == 1 else 1], 0)
            total += np.where(ok, n, 0)
            count += ok
        h = np.where(walk & (count > 0), np.clip((h + total) / (1 + count), low, high), h)
    out = np.rint(h).astype(int)
    for _ in range(10 * passes):
        changed = False
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            n = np.roll(out, shift, axis)
            ok = joined[axis][..., 0 if shift == 1 else 1]
            too_high = ok & (out > n + MAX_STEP)
            if too_high.any():
                out[too_high] = n[too_high] + MAX_STEP
                changed = True
        if not changed:
            break
    return out


def adjacency(walk, grade):
    """Neighbour pairs that are one surface (within half a block), per axis and direction."""
    joined = []
    for axis in (0, 1):
        forward = walk & np.roll(walk, 1, axis) & (np.abs(grade - np.roll(grade, 1, axis)) <= 1)
        backward = walk & np.roll(walk, -1, axis) & (np.abs(grade - np.roll(grade, -1, axis)) <= 1)
        if axis == 0:
            forward[0], backward[-1] = False, False
        else:
            forward[:, 0], backward[:, -1] = False, False
        joined.append(np.stack([forward, backward], -1))
    return joined


def direction(road, iz, ix, radius=4):
    """Principal axis of the carriageway around a cell, and how clearly it runs one way."""
    z0, x0 = max(0, iz - radius), max(0, ix - radius)
    zz, xx = np.nonzero(road[z0:iz + radius + 1, x0:ix + radius + 1])
    if len(xx) < 4:
        return None, 0.0
    pts = np.c_[xx + x0 - ix, zz + z0 - iz].astype(float)
    pts -= pts.mean(0)
    w, v = np.linalg.eigh(pts.T @ pts)
    return v[:, 1], float(1 - w[0] / max(w[1], 1e-9))


def convert(a):
    spec = read(a.config)
    source = CapturedSurface(spec['source'], partial=True)
    sx, sz, sX, sZ = source.bounds
    x0, z0, x1, z1 = spec.get('bounds', [sx, sz, sX, sZ])
    with np.load(spec['network']) as f:
        net = {k: f[k] for k in ('walk', 'road', 'grade2', 'bounds')}
    ax, az = map(int, net['bounds'][:2])
    window = np.s_[z0 - az:z1 - az + 1, x0 - ax:x1 - ax + 1]
    walk, road, grade = net['walk'][window].copy(), net['road'][window] & net['walk'][window], net['grade2'][window].astype(int)
    full = source.measured['full'][z0 - sz:z1 - sz + 1, x0 - sx:x1 - sx + 1]
    walk &= full
    road &= walk
    joined = adjacency(walk, grade)
    height = 4 * grade + 8                     # eighths: grade2 is twice the foot height minus two
    surface = smooth(height, walk, joined)
    # Footways ride one layer over the surface they share with the carriageway: a kerb of an
    # eighth, the same everywhere, so footway meets footway without a step.
    surface = np.where(walk & ~road, surface + 1, surface)

    catalog = [r for r in read(spec['catalog']) if r.get('occupied_bounds') and r.get('kind') == 'building']
    centres = np.array([[(r['occupied_bounds'][0] + r['occupied_bounds'][3]) / 2, (r['occupied_bounds'][2] + r['occupied_bounds'][5]) / 2] for r in catalog])

    # Markings: centre and edge lines from the carriageway's own shape. The centre is the ridge
    # of the distance to the kerbs, so it stays one continuous chain round bends; near 45 degrees
    # it is drawn with the corner-to-corner pattern so the cells join at their corners.
    edge = distance_transform_edt(np.pad(road, 1))[1:-1, 1:-1]
    marks = {}
    shape_ = road.shape

    def value(jz, jx):
        return edge[jz, jx] if 0 <= jz < shape_[0] and 0 <= jx < shape_[1] else 0.0

    for iz, ix in np.argwhere(road):
        half = edge[max(0, iz - 4):iz + 5, max(0, ix - 4):ix + 5].max()
        width = 2 * half - 1
        if width < 4:
            continue                           # narrow lanes carry no lines
        # The window must be long against the width, or a wide road looks the same every way.
        axis, clarity = direction(road, iz, ix, radius=max(5, int(round(2.5 * half))))
        if axis is None or clarity < .65:
            continue                           # a junction or a plaza
        if axis[0] < 0 or (axis[0] == 0 and axis[1] < 0):
            axis = -axis
        perp = np.rint([-axis[1], axis[0]]).astype(int)
        x, z = ix + x0, iz + z0
        here = edge[iz, ix]
        # One cell of the two in the middle of an even width: not below the one behind, above the one ahead.
        centre = here >= value(iz - perp[1], ix - perp[0]) and here > value(iz + perp[1], ix + perp[0]) and here > 1
        angle = math.degrees(math.atan2(axis[1], axis[0]))          # -90..90, z runs south
        if abs(abs(angle) - 45) < 22.5:
            pattern, facing = 24, ('north' if angle < 0 else 'east')  # '/' runs north-east; turned, north-west
        else:
            pattern, facing = 1, ('east' if abs(angle) < 45 else 'north')
        if centre:
            town = len(centres) and np.sum(np.hypot(*(centres - [x, z]).T) < TOWN_RADIUS) >= TOWN_BUILDINGS
            s = int(math.floor(x * axis[0] + z * axis[1]))
            if not town:
                marks[iz, ix] = (pattern, facing, YELLOW)
            elif (s // DASH) % 2 == 0:
                marks[iz, ix] = (pattern, facing, WHITE)
        elif here == 1:
            for side in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                jz, jx = iz + side[1], ix + side[0]
                if 0 <= jz < shape_[0] and 0 <= jx < shape_[1] and walk[jz, jx] and not road[jz, jx]:
                    marks[iz, ix] = (23, EDGE_FACING[side], WHITE)
                    break

    rows, skipped = {}, Counter()
    paint = {tuple(int(d[k]) for k in 'xyz'): int(d.get('color', -1)) for d in source.devices if str(d.get('id')) == ENTITY}

    def put(x, y, z, state, purpose, entity=None):
        before = source.state(x, y, z)
        if before == state:
            if entity is not None and paint.get((x, y, z)) != entity:
                skipped['paint colour differs on an unchanged marking'] += 1
            return True
        if before.split('[')[0] not in REPLACEABLE and not before.startswith('trafficcraft:'):
            skipped[before.split('[')[0]] += 1
            return False
        row = dict(pos=[x, y, z], before=before, after=state, purpose=purpose)
        if entity is not None:
            row['block_entity'] = dict(id=ENTITY, color=entity)
        rows[x, y, z] = row
        return True

    for iz, ix in np.argwhere(walk):
        x, z = int(ix + x0), int(iz + z0)
        g = int(grade[iz, ix])
        old_y = (g + 1) // 2                   # the block the current surface sits on
        h = int(surface[iz, ix])
        top, part = divmod(h, LAYERS)
        carriage = bool(road[iz, ix])
        solid = 'trafficcraft:asphalt' if carriage else 'trafficcraft:concrete'
        slope = 'trafficcraft:asphalt_slope' if carriage else 'trafficcraft:concrete_slope'
        mark = marks.get((iz, ix))
        # States are written in full, as the game saves them, so readbacks stay exact.
        if not any(paved(source.state(x, y, z)) for y in (old_y - 1, old_y, old_y + 1)):
            skipped['no paving at the declared height'] += 1
            continue
        base = top - 1
        for y in range(min(base, old_y), base):
            put(x, y, z, solid, 'road base')
        if part == 0:
            if mark:
                put(x, base, z, f'trafficcraft:asphalt_pattern_{mark[0]}[facing={mark[1]}]', 'road marking', mark[2])
            else:
                put(x, base, z, solid, 'road surface')
            cap = base + 1
        else:
            put(x, base, z, solid, 'road surface')
            if mark:
                put(x, top, z, f'trafficcraft:asphalt_slope_pattern_{mark[0]}[facing={mark[1]},layers={part},waterlogged=false]', 'road marking', mark[2])
            else:
                put(x, top, z, f'{slope}[layers={part},waterlogged=false]', 'road surface')
            cap = top + 1
        # The old surface may stand above the new one: clear what is left of it.
        for y in range(cap, old_y + 2):
            if paved(source.state(x, y, z)):
                put(x, y, z, 'minecraft:air', 'old surface removed')

    steps = []
    for axis in (0, 1):
        # A kerb between carriageway and footway is one layer more than the slope allows.
        ok = joined[axis][..., 0] & (road == np.roll(road, 1, axis))
        d = np.abs(surface - np.roll(surface, 1, axis))[ok]
        steps.append(int(d.max()) if len(d) else 0)
    report = dict(errors=[] if max(steps) <= MAX_STEP else [f'Step over {MAX_STEP} layers'], cells=len(rows), walk=int(walk.sum()),
                  carriageway=int(road.sum()), markings=len(marks), marking_colours=dict(Counter(m[2] for m in marks.values())),
                  largest_step=max(steps), skipped=dict(skipped.most_common(12)), world_written=False)
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / 'conversion-check.json', report)
    write(a.out / 'patch.json', dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'],
          edits=[rows[k] for k in sorted(rows)], native_snapshot=spec['native_snapshot'], error_reports=[str(a.out / 'conversion-check.json')],
          views_reviewed_by_root=False, continuation_work=spec['continuation_work']))
    print(json.dumps({k: report[k] for k in ('cells', 'walk', 'carriageway', 'markings', 'marking_colours', 'largest_step', 'skipped')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    convert(parser.parse_args())
