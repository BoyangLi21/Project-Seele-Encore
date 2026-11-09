"""Lay out the GeoFront spiral railway: floor station, up the dome wall, valley station, old-lift terminus.

Writes a config for plan_rail_corridor.py's `native` mode. Nothing is written to the world
here. The track climbs the inside of the dome at the height the measured ceiling allows,
carries on through the rock once the dome has run out, and is checked with MTR's own
rail geometry before the engine ever sees it.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter

from plan_rail_corridor import ANGLES, rail_shape
from prepare_mtr_member_patch_r52 import Parser

CENTRE = (30.0, 327.0)              # dome axis, on the headquarters
HEADROOM = 12                       # rail to dome rock
END_RADIUS = 1272                   # the circle the buried last part of the spiral keeps to
FLOOR_Y, VALLEY_Y, BRIDGE_Y, TERMINUS_Y = -468, 72, 79, 62
TAIL_Y = 48                         # stays under the road the tail crosses at z 430, at street level
SPEED = 1600                        # km/h: the speed test reached 1,662 on the same engine
SW = (-1 / math.sqrt(2), 1 / math.sqrt(2))


def angle_name(degrees):
    return ANGLES[int(round((degrees % 360) / 22.5)) % 16]


def ceiling_lookup(path):
    with np.load(path) as saved:
        roof, height = saved['roof'].astype(float), saved['height']
        x0, z0 = saved['origin'].tolist()
    good = height > 60
    weight = uniform_filter(good.astype(float), size=31)
    level = uniform_filter(np.where(good, roof, 0.0), size=31)
    smooth = np.where(weight > .2, level / np.maximum(weight, 1e-6), -9999.0)
    def ceiling(x, z):
        i, j = int(round(z - z0)), int(round(x - x0))
        return smooth[i, j] if 0 <= i < smooth.shape[0] and 0 <= j < smooth.shape[1] else -9999.0
    return ceiling


def radius_for(ceiling, theta, y):
    """Walk out from inside the dome to where its ceiling drops to HEADROOM above the rail.

    Walking outwards stops at the wall, so another cavern beyond the rim is never mistaken for it.
    """
    u, v = math.cos(theta), math.sin(theta)
    for r in range(700, 2000, 4):
        if ceiling(CENTRE[0] + r * u, CENTRE[1] + r * v) < y + HEADROOM:
            return max(r - 4, END_RADIUS)
    return END_RADIUS


def spiral_nodes(ceiling, start_y, end_y):
    """Nodes every 22.5 degrees of heading, turning left, from the south-east of the wall."""
    headings = [22.5 - 22.5 * i for i in range(21)]
    bearing = [math.radians(h + 90) for h in headings]
    # Two passes: heights depend on the length of the path, which depends on the radii the heights give.
    radii = [1500.0] * len(headings)
    for _ in range(4):
        lengths = [0.0]
        for i in range(1, len(headings)):
            lengths.append(lengths[-1] + (radii[i - 1] + radii[i]) / 2 * math.radians(22.5))
        heights = [start_y + (end_y - start_y) * s / lengths[-1] for s in lengths]
        measured = np.array([radius_for(ceiling, t, y) for t, y in zip(bearing, heights)], float)
        # The wall is not a perfect circle: a light average keeps each 22.5-degree rail drawable and stays on the rock.
        padded = np.concatenate([measured[:1], measured, measured[-1:]])
        fit = np.convolve(padded, [.25, .5, .25], mode='valid')
        radii = np.maximum.accumulate(np.maximum(fit, END_RADIUS)[::-1])[::-1].tolist()
    return [dict(x=round(CENTRE[0] + r * math.cos(t)), y=round(y), z=round(CENTRE[1] + r * math.sin(t)), heading=h % 360, radius=r)
            for r, t, y, h in zip(radii, bearing, heights, headings)]


def rail(id_, a, b, kind='rail'):
    row = {'id': id_, 'kind': kind, 'from': [a['x'], a['y'], a['z']], 'to': [b['x'], b['y'], b['z']],
           'from_angle': angle_name(a['heading']), 'to_angle': angle_name(b['heading'] + 180), 'vertical_radius': 400}
    if kind == 'rail':
        row.update(speed=SPEED, reverse_speed=SPEED)
    return row


def node(x, y, z, heading):
    return dict(x=x, y=y, z=z, heading=heading)


def layout(a):
    ceiling = ceiling_lookup(a.columns)
    # Floor station on a south-west heading, its siding behind it.
    # MTR draws no path from a siding that touches the platform, so a plain rail sits between them.
    siding_start, siding_end = node(-440, FLOOR_Y, 830, 135), node(-490, FLOOR_Y, 880, 135)
    platform_start, platform_end = node(-510, FLOOR_Y, 900, 135), node(-574, FLOOR_Y, 964, 135)
    valley_east, valley_west = node(1060, VALLEY_Y, 278, 180), node(970, VALLEY_Y, 278, 180)
    # The valley road is crossed by a bridge; the line then drops into the rock under the street grid.
    bridge_east, bridge_west = node(858, BRIDGE_Y, 278, 180), node(826, BRIDGE_Y, 278, 180)
    tunnel_level = node(600, TERMINUS_Y, 278, 180)
    terminus_east, terminus_west = node(238, TERMINUS_Y, 278, 180), node(148, TERMINUS_Y, 278, 180)
    spiral = spiral_nodes(ceiling, FLOOR_Y + 2, TAIL_Y)
    # A rail joining two headings 22.5 degrees apart has its chord along the heading between them.
    last = spiral[-1]
    along = math.radians(last['heading'] - 11.25)
    reach = (last['z'] - 498) / -math.sin(along)
    arrival = node(round(last['x'] + reach * math.cos(along)), TAIL_Y + 2, 498, last['heading'] - 22.5)
    chain = spiral + [arrival, valley_east]
    rails = [rail('siding', siding_start, siding_end, 'siding'), rail('to-platform', siding_end, platform_start),
             rail('P-floor', platform_start, platform_end, 'platform'),
             rail('to-wall', platform_end, spiral[0])]
    for i, (p, q) in enumerate(zip(chain[:-1], chain[1:])):
        rails.append(rail(f'spiral-{i:02d}', p, q))
    rails += [rail('P-valley', valley_east, valley_west, 'platform'), rail('to-bridge', valley_west, bridge_east), rail('bridge', bridge_east, bridge_west), rail('to-tunnel', bridge_west, tunnel_level), rail('to-terminus', tunnel_level, terminus_east),
              rail('P-terminus', terminus_east, terminus_west, 'platform')]
    bad, tight, total = [], math.inf, 0.0
    for row in rails:
        shape = rail_shape((row['from'][0], row['from'][2]), row['from_angle'], (row['to'][0], row['to'][2]), row['to_angle'])
        if shape is None:
            bad.append(row['id'])
            continue
        points, radius = shape
        tight = min(tight, radius)
        print(row['id'], row.get('kind'), round(radius) if not math.isinf(radius) else 'straight', row['from'], row['to'])
        total += float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
    if bad:
        raise SystemExit(f'No MTR curve for {bad}')
    sidings = [p for p in (Path(a.snapshot) / 'projectseele/geofront/sidings').rglob('*') if p.is_file()]
    sample = next(s for s in (Parser(p.read_bytes()).node().value for p in sidings) if s['vehicleCars'] and s['transportMode'] == 'TRAIN' and 'eidan' in s['vehicleCars'][0]['vehicleId'])
    cars = [dict(id=c['vehicleId'], length=c['length'], width=c['width'], bogie1=c['bogie1Position'], bogie2=c['bogie2Position'],
                 padding1=c['couplingPadding1'], padding2=c['couplingPadding2']) for c in sample['vehicleCars']]
    stations = [dict(id='S-floor', name='GeoFront 地底站', color=0xB5452C, min=[-586, FLOOR_Y - 6, 892], max=[-498, FLOOR_Y + 14, 976]),
                dict(id='S-valley', name='箱根山谷站', color=0xB5452C, min=[962, VALLEY_Y - 6, 268], max=[1068, VALLEY_Y + 14, 288]),
                dict(id='S-terminus', name='总部人员出口站', color=0xB5452C, min=[140, TERMINUS_Y - 6, 268], max=[246, TERMINUS_Y + 14, 288])]
    line = dict(id='GS', name='GeoFront 螺旋线', color=0xB5452C, siding='siding', cars=cars, trains=1, repeat=True, steady=True, frequency=4, dwell=12000,
                platforms=['P-floor', 'P-valley', 'P-terminus', 'P-valley', 'P-floor'])
    spec = dict(id=a.id, label='GeoFront 螺旋线', native_snapshot=str(a.snapshot), rails=rails, stations=stations, lines=[line], warmup_seconds=900)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(spec, ensure_ascii=False, indent=1), 'utf8')
    rise = VALLEY_Y - FLOOR_Y
    print(json.dumps(dict(rails=len(rails), total_length=round(total), tightest_radius=None if math.isinf(tight) else round(tight), rise=rise,
                          spiral=[(n['x'], n['y'], n['z'], n['radius']) for n in spiral]), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--columns', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--out', type=Path, required=True)
    layout(parser.parse_args())
