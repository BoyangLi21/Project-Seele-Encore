"""Refresh declared personnel nodes after R53 corridor and lift repairs.

Only inherited public nodes and the explicit authored access-cell list are
eligible. Native lift journeys and player train guidance remain typed edges.
"""
from pathlib import Path
import argparse
import collections
import gzip
import hashlib
import heapq
import json
import math

from query_blocks import AIR, iter_selected_sections


def unpack(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def encode(data):
    return gzip.compress(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode(), mtime=0)


def dijkstra(backwards, seeds, keys=None, fixed=None, initial=None):
    n = len(backwards)
    distance = [math.inf] * n if initial is None else initial[0][:]
    parent = [-1] * n if initial is None else initial[1][:]
    source = [-1] * n if initial is None else initial[2][:]
    queue = []
    for node in seeds:
        if initial is None:
            distance[node], parent[node], source[node] = 0., node, node
        heapq.heappush(queue, (distance[node], node))
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != distance[node]:
            continue
        for previous, length in backwards[node]:
            if keys is not None and keys[previous] != keys[node]:
                continue
            if fixed is not None and fixed[previous]:
                continue
            candidate = cost + length
            if candidate >= distance[previous]:
                continue
            distance[previous], parent[previous], source[previous] = candidate, node, source[node]
            heapq.heappush(queue, (candidate, previous))
    return distance, parent, source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--access', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--medical-only', action='store_true', help='Retain all outside node validity and edges; refresh only the installed R54 medical room')
    args = parser.parse_args()
    world, out = args.world.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    graph = unpack(world / 'nerv_routes_r24.json.gz')
    npc = unpack(world / 'r53_personnel_walking_graph.json.gz')
    assert [row[:3] for row in graph['nodes']] == npc['nodes']
    coords = [tuple(row) for row in npc['nodes']]
    inherited = len(coords)
    inherited_active = graph.get('node_active', [True] * inherited)[:]
    lookup = {point: i for i, point in enumerate(coords)}
    assert len(lookup) == len(coords)
    access = json.loads(args.access.read_text('utf8'))
    permitted = access['whole_hall_walk_cells'][:]
    for stair in access.get('authored_stairs', []):
        permitted.extend(stair)
    # The declared handoff bands include unchanged floor cells as well as
    # newly placed panels. A patch-only list omits the old shaft doorway.
    for hall in access['lobby_paths']:
        for x0, x1, z0, z1 in hall.get('bands') or []:
            permitted.extend([x, hall['y'], z] for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    lifts = json.loads((world / 'personnel_lifts_r52.json').read_text('utf8'))
    requested_landings = []
    direction = {'north': (0, -1), 'south': (0, 1), 'east': (1, 0), 'west': (-1, 0)}
    for lift in lifts['lifts']:
        for floor in lift['floors']:
            dx, dz = direction[floor['exit']]
            x, _, z = floor['cabin']
            point = (x + dx * 5, floor['approach_y'], z + dz * 5)
            requested_landings.append((lift, floor, point))
            permitted.append(list(point))
    medical_path = world / 'r54_medical_wards.json'
    medical = json.loads(medical_path.read_text('utf8')) if medical_path.exists() else None
    def in_medical(point):
        x, y, z = point
        return -49 <= x <= -7 and y == -527 and 377 <= z <= 407
    def near_medical(point):
        x, y, z = point
        return -50 <= x <= -6 and y == -527 and 376 <= z <= 408
    if args.medical_only:
        assert medical is not None, 'Installed R54 medical declaration required'
    if medical:
        for room in [medical['lobby']] + medical['rooms']:
            x0, x1, z0, z1 = room['bounds']
            permitted.extend([x, room['floor'] + 1, z]
                             for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
        for room in medical['rooms']:
            x, y, z = room['entry']
            permitted.extend([[x - 1, y, z], [x, y, z]])
    if args.medical_only:
        permitted = [p for p in permitted if in_medical(p)]
        permitted.extend(list(p) for p in coords if in_medical(p))
    for point in map(tuple, permitted):
        if point not in lookup:
            lookup[point] = len(coords)
            coords.append(point)

    wanted = collections.defaultdict(set)
    selected = collections.defaultdict(set)
    for x, y, z in coords:
        if args.medical_only and not near_medical((x, y, z)):
            continue
        for sy in (y - 1, y, y + 1):
            point = (x, sy, z)
            key = (x // 16, z // 16, sy // 16)
            wanted[key].add(point)
            selected[key[:2]].add(key[2])
    states = {}
    for cx, cz, sy, palette, indices in iter_selected_sections(world, graph['dimension'], selected):
        for point in wanted[cx, cz, sy]:
            x, y, z = point
            states[point] = palette[int(indices[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)])]
    shapes = json.loads((world / 'native_collision_shapes.json').read_text('utf8'))
    # Already measured native shape of the ceiling/floor light in this repair.
    shapes['projectseele:nerv_strip_light[lit=true]'] = [[0, 0, 0, 1, 1, 1]]
    operations = {}
    for lift in lifts['lifts']:
        for floor in lift['floors']:
            for role in ('landing_doors', 'cabin_doors'):
                for cell in floor[role]:
                    operations[tuple(cell['pos'])] = 'minecraft:air'
    command_doors = world / 'r52/headquarters_command_doors.json'
    for door in json.loads(command_doors.read_text('utf8'))['doors']:
        for point in door['aperture']:
            operations[tuple(point)] = 'minecraft:air'
    for gate in json.loads((world / 'r44_public_station_gates.json').read_text('utf8'))['gates']:
        operations[tuple(gate['position'])] = gate['open_state']
    for door in lifts['office_access']['room_controls']['pilot_guard_doors']:
        x, y, z = door['lower']
        for dy in (0, 1):
            point = (x, y + dy, z)
            if point in states:
                operations[point] = states[point].replace('open=false', 'open=true')
    for x, y, z in ((24, -516, 254), (28, -541, 282), (48, -541, 282)):
        for dy in (0, 1):
            point = (x, y + dy, z)
            if states.get(point, '').startswith('projectseele:city_personnel_door['):
                operations[point] = states[point].replace('open=false', 'open=true')
    if medical:
        for room in medical['rooms']:
            x, y, z = room['entry']
            for xx in (x - 1, x):
                for yy in (y, y + 1):
                    point = (xx, yy, z)
                    if states.get(point, '').startswith('projectseele:city_personnel_door['):
                        operations[point] = states[point].replace('open=false', 'open=true')
    unknown = collections.Counter()

    def shape(state):
        if state in shapes:
            return shapes[state]
        if state.split('[')[0] in AIR | {'minecraft:light'}:
            return []
        if state.startswith('mtr:escalator_step[') and 'orientation=flat' in state:
            return [[0, 0, 0, 1, .9375, 1]]
        unknown[state] += 1
        return None

    def free(boxes, height):
        return boxes is not None and not any(b[3] > .205 and b[0] < .795 and b[5] > .205 and b[2] < .795 and b[4] > .01 and b[1] < height for b in boxes)

    safe, foot, head = [], [], []
    rejected = []
    for index, point in enumerate(coords):
        x, y, z = point
        if args.medical_only and not near_medical(point):
            safe.append(inherited_active[index]);foot.append(None);head.append(None)
            continue
        actual = [states.get((x, y + dy, z), 'UNMEASURED') for dy in (-1, 0, 1)]
        operated = [operations.get((x, y + dy, z), s) for dy, s in zip((-1, 0, 1), actual)]
        floor, f, h = map(shape, operated)
        supported = floor is not None and any(.9 <= b[4] <= 1.001 and b[0] <= .5 <= b[3] and b[2] <= .5 <= b[5] for b in floor)
        valid = supported and free(f, 1) and free(h, .79) and not any(s.startswith(('minecraft:water', 'minecraft:lava', 'projectseele:lcl')) for s in actual[1:])
        if args.medical_only and not in_medical(point):
            valid = inherited_active[index]
        safe.append(valid)
        foot.append(f)
        head.append(h)
        if not valid:
            rejected.append({'point': list(point), 'actual': actual})

    # Old edges already exclude operating railway gauge, counterflow and roofs.
    if args.medical_only:
        # Inside and crossing edges are rebuilt below. A snapshot of a distant
        # moving lift must never revoke an inherited route or revive a retired one.
        edges = {(a, b): float(cost) for a, b, cost in npc['walking_edges']
                 if not in_medical(coords[a]) and not in_medical(coords[b])}
        inherited_outside_edges = dict(edges)
    else:
        edges = {(a, b): float(cost) for a, b, cost in npc['walking_edges'] if safe[a] and safe[b]}

    def boundary(boxes, dx, dz, height, low):
        if boxes is None:
            return True
        axis, tangent, positive = (0 if dx else 2), (2 if dx else 0), dx + dz > 0
        return any(b[tangent] < .795 and b[tangent + 3] > .205 and (b[axis + 3] > .795 if positive else b[axis] < .205) and b[4] > (.6 if low else .01) and b[1] < height for b in boxes)

    for i in sorted({lookup[tuple(point)] for point in permitted}):
        if not safe[i]:
            continue
        x, y, z = coords[i]
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            j = lookup.get((x + dx, y, z + dz))
            if j is None or not safe[j]:
                continue
            if any(boundary(bs, sx, sz, height, low) for bs, sx, sz, height, low in ((foot[i], dx, dz, 1.79, True), (head[i], dx, dz, .79, False), (foot[j], -dx, -dz, 1.79, True), (head[j], -dx, -dz, .79, False))):
                continue
            edges[i, j] = edges[j, i] = 1.

    for stair in access.get('authored_stairs', []):
        if args.medical_only:
            continue
        for a, b in zip(stair, stair[1:]):
            i, j = lookup[tuple(a)], lookup[tuple(b)]
            assert abs(a[1]-b[1]) <= 1 and abs(a[0]-b[0])+abs(a[2]-b[2]) == 1
            if safe[i] and safe[j]:
                edges[i, j] = edges[j, i] = math.dist(a,b)
    landings, lift_edges, issues = [], [], []
    for lift, floor, point in requested_landings:
        node = lookup[point]
        if not safe[node]:
            issues.append({'kind': 'invalid_landing', 'lift': lift['id'], 'point': point})
        landings.append({'lift_id': lift['id'], 'label': floor['label'], 'node': node, 'requested': list(point), 'actual': list(point), 'restricted': floor.get('restricted', False)})
    for lift in lifts['lifts']:
        local = [r for r in landings if r['lift_id'] == lift['id']]
        for a in local:
            for b in local:
                if a != b:
                    lift_edges.append({'id': lift['id'], 'a': a['node'], 'b': b['node']})
    train = [row for row in graph['transport_edges'] if safe[row['from']] and safe[row['to']]]
    if args.medical_only:
        lift_edges = graph['lift_edges']
        landings = graph['named_lift_landings']
        train = graph['transport_edges']
    backwards = [[] for _ in coords]
    for (a, b), cost in edges.items():
        backwards[b].append((a, cost))
    player_backwards = [row[:] for row in backwards]
    for edge in lift_edges:
        a, b = edge['a'], edge['b']
        player_backwards[b].append((a, 5. + abs(coords[a][1] - coords[b][1]) / 8.))
    for edge in train:
        player_backwards[edge['to']].append((edge['from'], 20.))
    goal_results = []
    for goal in graph['goals']:
        if not safe[goal['node']]:
            issues.append({'kind': 'invalid_goal', 'goal': goal})
        goal_results.append(dijkstra(player_backwards, [goal['node']]))
    active = [safe[i] and all(math.isfinite(row[0][i]) for row in goal_results) for i in range(len(coords))]
    if args.medical_only:
        outside_reachability_losses = [list(point) for i, point in enumerate(coords[:inherited])
                                       if not in_medical(point) and inherited_active[i] and not active[i]]
        assert not outside_reachability_losses, ('Medical change disconnects inherited outside routes', outside_reachability_losses[:12])
        for i, point in enumerate(coords):
            if not in_medical(point):
                assert i < inherited, 'No outside additions in medical-only mode'
                active[i] = inherited_active[i]
        assert {(a, b): cost for (a, b), cost in edges.items()
                if not in_medical(coords[a]) and not in_medical(coords[b])} == inherited_outside_edges
    for landing in landings:
        if not active[landing['node']]:
            issues.append({'kind': 'disconnected_landing', 'landing': landing})
    graph.update(nodes=[list(point) + [row[1][i] if active[i] else i for row in goal_results] for i, point in enumerate(coords)], node_active=active, lift_edges=lift_edges, lift_landings=[r['actual'] for r in landings], named_lift_landings=landings, transport_edges=train, native_verified=False,
                 source='R53 current static readback: retained declared public nodes, authored access cells and all29 actual native lift landing approaches. Original rail-gauge and directional conveyor exclusions retained.')
    raw = encode(graph)
    (out / 'nerv_routes_r24.json.gz').write_bytes(raw)

    def floor_key(point):
        x, y, z = point
        if y >= 70:
            return 'original_surface_pavilion/75'
        if y < -1150:
            return 'terminal/' + str(-1230 if abs(y + 1230) < 4 else y)
        if y < -970:
            return 'deep_hangar/' + str(min((-1088, -1030, -1014, -987), key=lambda t: abs(t - y)))
        if z < 100 and -474 <= y <= -432:
            return 'original_experiment/' + str(min((-468, -442), key=lambda t: abs(t - y)))
        if 442 <= z <= 546 and -575 <= y <= -542:
            return 'headquarters_station/-559'
        if -577 <= y <= -415 and 235 <= z <= 448:
            return 'pyramid/' + str(min((-554, -541, -535, -527, -516, -513, -512, -502, -499, -485, -481, -471, -457, -434, -433, -422), key=lambda t: abs(t - y)))
        return 'original_retained/' + str(y)

    keys = list(map(floor_key, coords))
    seeds = [r['node'] for r in landings if active[r['node']]]
    distance, parent, source = dijkstra(backwards, seeds, keys=keys)
    fixed = list(map(math.isfinite, distance))
    distance, parent, source = dijkstra(backwards, [i for i, valid in enumerate(fixed) if valid], fixed=fixed, initial=(distance, parent, source))
    table, unresolved = [], []
    for i, point in enumerate(coords):
        if not active[i] or not math.isfinite(distance[i]):
            table.append(None)
            if active[i]:
                unresolved.append(list(point))
            continue
        table.append({'next': list(coords[parent[i]]), 'nearest_landing': list(coords[source[i]]), 'walking_metres': distance[i], 'floor_key': keys[i], 'requires_floor_transfer': not fixed[i]})
    nearest = {'graph_sha256': hashlib.sha256(raw).hexdigest(), 'same_floor': True, 'same_floor_schema': 3, 'node_floor_keys': keys, 'nodes': table, 'unresolved_coordinates': unresolved, 'native_verified': False, 'source': 'Actual walking edges only; same-floor native lift approach preferred. Stairs marked; no TRAIN or lift-journey edge treated as walking.'}
    (out / 'nearest_lift_paths_r44.json.gz').write_bytes(encode(nearest))
    npc.update(nodes=[list(p) for p in coords], walking_edges=[[a, b, cost] for (a, b), cost in edges.items()], native_lift_edges=lift_edges, native_lift_landings=landings, train_edges=[], native_verified=False)
    (out / 'r53_personnel_walking_graph.json.gz').write_bytes(encode(npc))
    report = {'world_written': False, 'inherited_nodes': inherited, 'added_explicit_nodes': len(coords) - inherited, 'physically_valid_nodes': sum(safe), 'active_nodes': sum(active), 'goal_reachable_counts': [sum(map(math.isfinite, row[0])) for row in goal_results], 'goal_reachability': [[math.isfinite(row[0][g['node']]) for g in graph['goals']] for row in goal_results], 'native_lift_landings': len(landings), 'walking_edges': len(edges), 'player_train_edges': len(train), 'npc_train_edges': 0, 'unknown_states': dict(unknown), 'issues': issues, 'nearest_lift_unresolved': len(unresolved), 'rejected_nodes': rejected}
    if args.medical_only:
        report.update(scope='Installed R54 medical room only; original outside active flags, walking edges and transport edges inherited',
                      outside_active_added=0,outside_active_removed=0,outside_walking_edges_unchanged=True,
                      outside_reachability_losses=outside_reachability_losses)
    (out / 'REVIEW.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps({k: v for k, v in report.items() if k != 'rejected_nodes'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
