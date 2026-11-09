"""Blocks under and around the GeoFront spiral railway, from the MTR engine's own track samples.

Reads the saved world and writes rows for write_deep_cells; nothing is written to the world
here. Natural ground, plants and trees may be cut. Anything else in the way is a conflict:
it is reported and left alone, so the plan can be moved rather than the facility.
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

import numpy as np

from map_pipeline.launch_protection import load as load_launch
from query_blocks import iter_selected_sections
from write_deep_cells import split_rows

DIM = 'projectseele:geofront'
CENTRE = np.array([30.0, 327.0])
AIR = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}
NATURAL = {'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block', 'minecraft:andesite', 'minecraft:diorite', 'minecraft:granite',
           'minecraft:deepslate', 'minecraft:tuff', 'minecraft:gravel', 'minecraft:coarse_dirt', 'minecraft:podzol', 'minecraft:sand', 'minecraft:clay',
           'minecraft:moss_block', 'minecraft:rooted_dirt', 'minecraft:mud', 'minecraft:grass', 'minecraft:tall_grass', 'minecraft:fern',
           'minecraft:large_fern', 'minecraft:dandelion', 'minecraft:poppy', 'minecraft:azure_bluet', 'minecraft:oxeye_daisy', 'minecraft:cornflower',
           'minecraft:lily_of_the_valley', 'minecraft:dead_bush', 'minecraft:sweet_berry_bush', 'minecraft:vine', 'minecraft:moss_carpet', 'minecraft:snow'}
DECK = 'minecraft:gray_concrete'
FILL = 'minecraft:stone_bricks'
WALL = 'minecraft:light_gray_concrete'
RAILING = 'minecraft:light_gray_stained_glass'
LAMP = 'minecraft:sea_lantern'
DOOR_TRIGGER = 'mtr:platform[door_type=none,facing=north,side=0]'
AIR_STATE = 'minecraft:air'
CLEAR_HEIGHT = 7
MAX_FILL = 12
MAX_HANGER = 80
MAX_PIER = 40


DOME_LINING = {'projectseele:nerv_structural_panel', 'projectseele:nerv_shaft_panel', 'minecraft:black_concrete'}


def natural(name, x, z):
    if name in DOME_LINING:         # the dome's own facing panels; inside the rim the same blocks are buildings
        return math.hypot(x - CENTRE[0], z - CENTRE[1]) > 1000
    return name in NATURAL or name.endswith(('_leaves', '_log', '_wood'))


class World:
    """Block states of a set of sections, read once through the project's reader."""
    def __init__(self, path, cells):
        wanted = defaultdict(set)
        for x, y, z in cells:
            wanted[x >> 4, z >> 4].add(y >> 4)
        self.sections = {}
        for cx, cz, sy, palette, ids in iter_selected_sections(path, DIM, wanted, skip_unfinished=False):
            self.sections[cx, sy, cz] = (palette, np.asarray(ids).reshape(-1))

    def state(self, x, y, z):
        found = self.sections.get((x >> 4, y >> 4, z >> 4))
        if found is None:
            return None
        palette, ids = found
        return palette[int(ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)])]


def columns_of(samples):
    """Per column under the track: the nearest sample's deck level, heading and lateral position."""
    columns = {}
    for rail in samples:
        points = np.array(rail['points'])
        if len(points) < 2:
            continue
        tangent = np.gradient(points[:, [0, 2]], axis=0)
        tangent /= np.maximum(np.linalg.norm(tangent, axis=1, keepdims=True), 1e-9)
        normal = np.stack([-tangent[:, 1], tangent[:, 0]], axis=1)
        for point, along, side in zip(points, tangent, normal):
            for w in np.arange(-3.5, 3.51, .25):
                x, z = (math.floor(v) for v in point[[0, 2]] + side * w)
                level = math.floor(point[1]) - 1
                if (x, z) not in columns or abs(w) < columns[x, z]['w']:
                    outward = np.sign((point[[0, 2]] - CENTRE) @ side) or 1.0
                    columns[x, z] = dict(w=abs(w), signed=float(w * outward), deck=level, rail=rail['id'], kind=rail['kind'], along=along.tolist())
    return columns


def platform_cells(put, item):
    """Platform floor beside a straight rail, after the corridor tool's layout: the trigger sits under the yellow edge."""
    p, q, y = item['from'], item['to'], item['from'][1]
    start = np.array([p[0] + .5, p[2] + .5])
    delta = np.array([q[0] + .5, q[2] + .5]) - start
    length = float(np.linalg.norm(delta))
    along = delta / length
    out = np.array([-along[1], along[0]]) * item['side']
    clearance, width = 1.35, 3.5
    low, high = np.minimum(start, start + delta) - width - 5, np.maximum(start, start + delta) + width + 5
    for x in range(math.floor(low[0]), math.ceil(high[0])):
        for z in range(math.floor(low[1]), math.ceil(high[1])):
            corners = np.array([[x + i, z + j] for i in (0, 1) for j in (0, 1)]) - start
            lateral = corners @ out
            run = (np.array([x + .5, z + .5]) - start) @ along
            if lateral.min() < clearance or lateral.max() > clearance + width or run < 0 or run > length:
                continue
            edge = lateral.min() < clearance + 1
            rim = lateral.max() > clearance + width - 1
            put((x, y, z), 'minecraft:yellow_concrete' if edge else 'minecraft:stone_bricks' if rim else 'minecraft:smooth_stone', 'platform floor')
            put((x, y - 1, z), DOOR_TRIGGER if edge else DECK, 'platform body')
            if rim and not edge:
                put((x, y + 1, z), RAILING, 'platform fence')
            for level in range(y + 2 if rim and not edge else y + 1, y + 5):
                put((x, level, z), AIR_STATE, 'platform clearance')


def terminus_stairs(put):
    """Nineteen steps from the terminus up to the pavement on the south side of the street."""
    for z in range(285, 288):
        for i in range(19):
            x, y = 170 - i, 62 + i
            put((x, y, z), 'minecraft:stone_brick_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]', 'stairs')
            for level in range(y + 1, y + 4):
                put((x, level, z), AIR_STATE, 'stairs headroom')
            if i < 18:
                put((x, y - 1, z), FILL, 'stairs base')
    for x in range(171, 175):       # landing, joining the platform to the foot of the stairs
        for z in range(284, 288):
            put((x, 62, z), 'minecraft:smooth_stone', 'landing')
            put((x, 61, z), DECK, 'landing base')
            for level in range(63, 67):
                put((x, level, z), AIR_STATE, 'landing headroom')
    put((172, 67, 286), LAMP, 'landing lamp')
    for x in range(153, 157):       # the only opening in the pavement gets a fence
        put((x, 81, 284), RAILING, 'pavement fence')
        put((x, 81, 288), RAILING, 'pavement fence')
    for z in range(285, 288):
        put((157, 81, z), RAILING, 'pavement fence')


def plan(a):
    spec = json.loads(a.config.read_text('utf8'))
    samples = json.loads(a.samples.read_text('utf8'))
    columns = columns_of(samples)
    planned, reasons = {}, Counter()

    def put(cell, state, why):
        # Solid work outranks clearance, so a deck is never carved away by a neighbouring section.
        if cell in planned and state == AIR_STATE:
            return
        planned[cell] = (state, why)

    for (x, z), c in columns.items():
        d = c['deck']
        if c['w'] <= 2.5:
            put((x, d, z), DECK, 'deck')
            for level in range(d + 1, d + 1 + CLEAR_HEIGHT):
                put((x, level, z), AIR_STATE, 'clearance')
    for item in a.platforms:
        platform_cells(put, item)
    terminus_stairs(put)

    world = World(a.world, set(planned) | {(x, y, z) for (x, z), c in columns.items() for y in range(c['deck'] - MAX_PIER - 2, c['deck'] + MAX_HANGER + 2)})
    # Supports, now that the rock is known: a bank on the floor, a hanger to the dome elsewhere, a railing on the open side.
    lamp_step = defaultdict(int)
    pier_cells = set()
    unsupported = Counter()
    for (x, z), c in sorted(columns.items()):
        d = c['deck']
        name = (world.state(x, d - 1, z) or 'minecraft:stone').split('[')[0]
        open_below = name in AIR
        if c['w'] <= 2.5 and open_below:
            depth = next((k for k in range(1, MAX_FILL + 1) if (world.state(x, d - k, z) or 'minecraft:stone').split('[')[0] not in AIR), None)
            ground = None if depth is None else (world.state(x, d - depth, z) or 'minecraft:stone').split('[')[0]
            if ground == 'minecraft:water' and (x + z) % 24 < 3:      # a pier through the lake down to its bed
                bed = next((k for k in range(depth, MAX_PIER) if (world.state(x, d - k, z) or 'minecraft:stone').split('[')[0] != 'minecraft:water'), None)
                if bed is not None:
                    for k in range(1, bed):
                        pier_cells.add((x, d - k, z))
                        put((x, d - k, z), FILL, 'pier')
            # A bank stands only on natural ground: over a road the deck spans as a bridge.
            if ground is not None and natural(ground, x, z):
                for k in range(1, depth):
                    put((x, d - k, z), FILL, 'bank')
        if 2.5 < c['w'] <= 3.5:
            outer = c['signed'] > 0
            above = next((k for k in range(CLEAR_HEIGHT + 1, MAX_HANGER) if (world.state(x, d + k, z) or 'minecraft:stone').split('[')[0] not in AIR), None)
            if outer and open_below and above is not None:
                for k in range(0, above):
                    put((x, d + k, z), WALL, 'hanger')
                lamp_step[c['rail']] += 1
                if lamp_step[c['rail']] % 48 == 0:
                    planned[x, d + 4, z] = (LAMP, 'hanger lamp')
            elif outer and open_below:
                unsupported[c['rail']] += 1
            elif not outer and open_below:
                put((x, d, z), DECK, 'deck edge')
                put((x, d + 1, z), RAILING, 'railing')

    guard = load_launch(a.world)
    edits, conflicts, tally = [], Counter(), Counter()
    where = defaultdict(list)
    cells = sorted(planned)
    extra = World(a.world, cells)
    for x, y, z in cells:
        state, why = planned[x, y, z]
        before = extra.state(x, y, z)
        if before is None:
            conflicts['chunk section missing'] += 1
            continue
        name = before.split('[')[0]
        try:
            guard.assert_positions([(x, y, z)])
        except ValueError:
            conflicts['launch volume'] += 1
            where['launch volume'].append((x, y, z))
            continue
        if name in AIR and state == AIR_STATE:
            continue
        if before == state:
            continue
        if name not in AIR and not natural(name, x, z) and not ((x, y, z) in pier_cells and name == 'minecraft:water'):
            key = why + ' on ' + name
            conflicts[key] += 1
            where[key].append((x, y, z))
            continue
        edits.append([x, y, z, before, state])
        tally[why] += 1
    a.out.mkdir(parents=True, exist_ok=True)
    batches = split_rows(edits, a.out)
    groups = Counter()
    span = {}
    for key, found in where.items():
        for x, y, z in found:
            rail = columns.get((x, z), {}).get('rail', 'station')
            k = rail + ' | ' + key.split(' on ')[1]
            groups[k] += 1
            b = span.setdefault(k, [x, y, z, x, y, z])
            span[k] = [min(b[0], x), min(b[1], y), min(b[2], z), max(b[3], x), max(b[4], y), max(b[5], z)]
    report = dict(conflict_groups={k: [n, span[k]] for k, n in groups.most_common()}, cells=len(edits), kinds=dict(tally), conflicts=dict(conflicts), conflict_examples={k: v[:6] for k, v in where.items()},
                  unsupported_outer_columns=dict(unsupported), batches=batches, world_written=False, spec=spec['id'])
    (a.out / 'report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False), 'utf8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--samples', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    arguments.platforms = [dict(**{k: v for k, v in r.items() if k in ('from', 'to')}, side=-1) for r in json.loads(arguments.config.read_text('utf8'))['rails'] if r['kind'] == 'platform']
    plan(arguments)
