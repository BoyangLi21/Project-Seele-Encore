"""Cold map-edit guard for every Moving Elevators lift, read from the installed world.

Each elevator group carries its controller, cage size, offsets and floors, so the travel volume
is exact: the cage footprint from the lowest cage position to the top of the highest one. The
landing doors, call buttons and controllers of the personnel lifts, and the main lift's landing
doors and security gate, are protected as single cells. A buried shaft (the main lift was filled
by terrain up to y 88 before batch 385) is how a lift stops reaching a floor, so map work must
not write into any of these.
"""
import json
from pathlib import Path

import nbtlib

from map_pipeline.launch_protection import LaunchProtection

# ElevatorGroup saves its facing as the horizontal data value: south, west, north, east.
FACING = ('south', 'west', 'north', 'east')


def cage_anchor(x, z, facing, size_x, size_z, side, depth):
    """ElevatorGroup.getCageAnchorBlockPos in Moving Elevators 1.4.12, without the y term."""
    if facing == 'north':
        return x - size_x // 2 - side, z - size_z - depth
    if facing == 'south':
        return x - size_x // 2 + side, z + 1 + depth
    if facing == 'west':
        return x - size_x - depth, z - size_z // 2 + side
    return x + 1 + depth, z - size_z // 2 - side


def group_volumes(world):
    data = nbtlib.load(Path(world, 'dimensions/projectseele/geofront/data/capabilities.dat'))['data']
    groups = data.get('movingelevators:elevator_groups', {})
    boxes = []
    for key, entry in groups.items():
        g, pos = entry['group'], entry['pos']
        x, z, facing = int(pos['x']), int(pos['z']), FACING[int(pos['facing'])]
        sx, sy, sz = int(g['cageSizeX']), int(g['cageSizeY']), int(g['cageSizeZ'])
        ax, az = cage_anchor(x, z, facing, sx, sz, int(g['cageSideOffset']), int(g['cageDepthOffset']))
        floors = [int(f) for f in g['floors']]
        if not floors:
            continue
        low, high = min(floors) + int(g['cageHeightOffset']), max(floors) + int(g['cageHeightOffset']) + sy - 1
        boxes.append((f'lift shaft {key}', (ax, low, az, ax + sx - 1, high, az + sz - 1)))
        for y in floors:
            boxes.append((f'lift controller {key}@{y}', (x, y, z, x, y, z)))
    return boxes


def device_cells(world):
    cells = []
    path = Path(world, 'personnel_lifts_r52.json')
    if path.is_file():
        for lift in json.loads(path.read_text('utf8'))['lifts']:
            for floor in lift.get('floors', ()):
                points = [d['pos'] for d in floor.get('landing_doors', ())]
                points += [c['position'] for c in floor.get('calls', ())]
                points += [floor['controller']] if 'controller' in floor else []
                cells += [(f'lift device {lift["id"]}', tuple(int(v) for v in p)) for p in points]
    plan = Path(world, 'regional_plan.json')
    if plan.is_file():
        main = json.loads(plan.read_text('utf8')).get('main_lift')
        if main and main.get('exit') == 'north':
            (x, z), half = main['axis'], main['width'] // 2
            for y in main['stops']:
                # RegionalGatewayDirector: 7 x 5 landing door plane two blocks outside the cage.
                cells.append(('main lift landing doors', (x - 3, y, z - half - 2, x + 3, y + 4, z - half - 2)))
            cells.append(('main lift security gate', (x - 3, 81, 733, x + 3, 85, 733)))
    return [(name, b if len(b) == 6 else (*b, *b)) for name, b in cells]


def load(world):
    boxes = group_volumes(world) + device_cells(world)
    if not boxes:
        raise ValueError('Installed lift groups are required for map work')
    return LaunchProtection(boxes, dict(volumes=len(boxes)))
