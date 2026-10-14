"""Root's finite two-main-lift civil candidate; plans only, never writes WORLD.

Reads exact current blocks/typed BEs through query_blocks. Original native
cars, device moves and Root civil surfaces are composed into one final map.
Unknown materials, unknown BEs and missing source preconditions stay HOLD.
"""
from __future__ import annotations
import argparse
import collections
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path

import nbtlib
from query_blocks import read_box, iter_block_entities, AIR

ROOT = Path(__file__).resolve().parents[1]
DIM = 'projectseele:geofront'
STRUCT = 'projectseele:nerv_structural_panel'
FLOOR = 'projectseele:nerv_floor_panel'
WALL = 'projectseele:nerv_wall_panel'
VOID = 'minecraft:air'
SUPPORTS = [(6, -666, 251), (6, -667, 255), (12, -666, 251), (12, -667, 255)]
MAIN = 's20-command-rear-x12-z253-v4'
EAST = 'r25-east-command-gallery'
HQ = [-541, -516, -512, -502]
NATURAL = AIR | {'minecraft:stone', 'minecraft:deepslate', 'minecraft:deepslate[axis=y]', 'minecraft:dirt'}
ARCHITECTURE = {
    STRUCT, FLOOR, WALL, 'projectseele:nerv_machine_panel', 'projectseele:nerv_machine_edge',
    'projectseele:nerv_shaft_panel', 'projectseele:clear_glass', 'projectseele:nerv_pyramid_panel',
    'projectseele:nerv_strip_light[lit=true]', 'projectseele:nerv_ceiling_light[hanging=true,lit=true]',
    'projectseele:tv_utility_lift_ceiling_r45', 'projectseele:tv_staff_lift_panel_r45',
    'minecraft:polished_deepslate', 'minecraft:deepslate_bricks', 'minecraft:deepslate_tiles',
    'minecraft:smooth_stone', 'minecraft:polished_andesite', 'minecraft:polished_basalt[axis=y]',
    'minecraft:sea_lantern', 'minecraft:gray_stained_glass', 'minecraft:light_gray_stained_glass',
    'minecraft:light_gray_concrete', 'minecraft:gray_concrete', 'minecraft:black_concrete',
    'minecraft:red_concrete', 'minecraft:white_concrete', 'minecraft:orange_concrete',
    'minecraft:red_terracotta', 'minecraft:iron_block', 'minecraft:polished_blackstone',
    'minecraft:polished_blackstone_bricks',
}
RETIRED_SHAFT = NATURAL | {STRUCT, 'minecraft:polished_deepslate', 'minecraft:deepslate_bricks',
    'minecraft:deepslate_tiles', 'minecraft:smooth_stone', 'minecraft:black_concrete',
    'minecraft:polished_basalt[axis=y]', 'minecraft:sea_lantern', 'minecraft:orange_concrete'}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == '.gz' else data)


def points(lo, hi):
    for y in range(lo[1], hi[1] + 1):
        for z in range(lo[2], hi[2] + 1):
            for x in range(lo[0], hi[0] + 1):
                yield x, y, z


class Candidate:
    def __init__(self, world):
        self.world = world
        self.before = {}
        self.tags = {}
        self.after = {}
        self.owners = {}
        self.holds = []
        self.read_boxes = []
        self.known_device_points = set()
        self.known_car_points = set()
        self.owned_source_states = {}

    def read(self, lo, hi):
        self.before.update(read_box(self.world, DIM, lo, hi))
        self.tags.update(iter_block_entities(self.world, DIM, lo, hi))
        self.read_boxes.append([lo, hi])

    def old(self, point):
        point = tuple(point)
        if point not in self.before:
            self.read(point, point)
        return self.before.get(point, '__UNREAD__')

    def put(self, point, target, owner):
        point = tuple(point)
        before = self.old(point)
        allowed = RETIRED_SHAFT if owner == 'retired_terminal_short_shaft' else NATURAL | ARCHITECTURE
        terminal_old_call = point == (9, -845, 251) and before == 'minecraft:polished_blackstone_button[face=wall,facing=south,powered=false]' and target == VOID
        if before not in allowed and self.owned_source_states.get(point) != before and not terminal_old_call:
            self.holds.append(dict(kind='unknown_function_or_material', pos=point, before=before, requested=target, owner=owner))
        self.after[point] = target
        self.owners[point] = owner

    def fill(self, lo, hi, target, owner):
        for point in points(lo, hi):
            self.put(point, target, owner)

    def final(self, point):
        return self.after.get(tuple(point), self.old(tuple(point)))


def build(world, lift_candidate, out):
    interface = json.loads((lift_candidate / 'CIVIL_NATIVE_DEVICE_INTERFACE.json').read_text('utf8'))
    be_doc = json.loads((lift_candidate / 'NATIVE_BLOCK_ENTITY_PATCH.json').read_text('utf8'))
    groups = json.loads((lift_candidate / 'NATIVE_GROUP_METADATA_PATCH.json').read_text('utf8'))
    manifest = json.loads((lift_candidate / 'personnel_lifts_CANDIDATE_NOT_INSTALLED.json').read_text('utf8'))
    need(manifest['epoch'] == 53 and not manifest['ready'], 'Root epoch53 uninstalled native candidate required')
    need(manifest['main_lifts']['command_rear']['shaft_translation'] == [-3, 0], 'This civil layout is only Root cabin9/controller6')
    need(all(manifest['main_lifts'][key]['hangar_floor'] == -603 for key in ('command_rear', 'east_gallery')), 'Root hangar level differs')
    need(manifest['main_lifts']['command_rear']['terminal_floor'] == -846, 'Root Terminal level differs')
    # Root's exact final call-location correction preserves the original
    # quartz stair at the rigidly translated prototype call position.
    for binding in manifest['lifts']:
        if binding['id'] == MAIN:
            floor = next(f for f in binding['floors'] if f['cabin'][1] == -502)
            need(len(floor['calls']) == 1 and floor['calls'][0]['position'] == [6, -501, 258], 'Unexpected highest main-floor call candidate')
            floor['calls'][0]['position'] = [6, -501, 257]
    for row in interface['devices']:
        if row['owner_lift'] == MAIN and row['role'] == 'moved_external_call' and row['target'] == [6, -501, 258]:
            row['target'] = [6, -501, 257]
    c = Candidate(world)
    for box in [((6, -848, 250), (12, -497, 256)), ((63, -605, 299), (69, -452, 305)),
                ((9, -847, 243), (15, -796, 249)), ((6, -848, 257), (15, -842, 262)),
                ((6, -605, 257), (12, -599, 291)), ((62, -605, 305), (70, -599, 310))]:
        c.read(*box)
    for y in HQ:
        c.read((6, y - 2, 257), (15, y + 3, 262))
    for car in interface['cabins']:
        c.read(*map(tuple, car['source_box']))
        c.read(*map(tuple, car['target_box']))
        c.known_car_points.update(tuple(row['source']) for row in car['cells'])
        c.known_car_points.update(tuple(row['target']) for row in car['cells'])
        c.owned_source_states.update((tuple(row['source']), row['state']) for row in car['cells'])
    for row in interface['devices']:
        c.known_device_points.add(tuple(row['target']))
        if row.get('source_precondition_storage') == 'CURRENT_WORLD_STATE_MUST_MATCH_SOURCE_STATE':
            c.known_device_points.add(tuple(row['source']))
            c.owned_source_states[tuple(row['source'])] = row['source_state']
    source_tags, target_tags = {}, {}
    for row in be_doc['operations']:
        target = tuple(row['target_position'])
        target_tags[target] = nbtlib.parse_nbt(row['target_nbt'])
        c.known_device_points.add(target)
        if row.get('source_precondition_storage') == 'CURRENT_WORLD_BLOCK_ENTITY':
            source = tuple(row['source_position'])
            c.read(source, source)
            before = c.tags.get(source)
            if before is None or before.snbt() != row['source_nbt']:
                c.holds.append(dict(kind='original_BE_precondition_changed', pos=source))
            source_tags[source] = before
            c.known_device_points.add(source)
    current_caps = nbtlib.load(world / 'dimensions/projectseele/geofront/data/capabilities.dat')
    native_groups = current_caps['data']['movingelevators:elevator_groups']
    for row in groups['operations']:
        if row['source_key'] not in native_groups or native_groups[row['source_key']].snbt() != row['before_snbt']:
            c.holds.append(dict(kind='native_group_precondition_changed', key=row['source_key']))
    for key, expected in groups['preserve_other_group_hashes'].items():
        if key not in native_groups or sha(native_groups[key].snbt().encode()) != expected:
            c.holds.append(dict(kind='other_native_group_precondition_changed', key=key))

    # Source-only original car cells are accounted for before civil and target
    # car layers. An uncovered restoration is HOLD, never an inferred floor.
    car_targets = {tuple(row['target']) for car in interface['cabins'] for row in car['cells']}
    source_only_cars = []
    for car in interface['cabins']:
        for row in car['cells']:
            p = tuple(row['source'])
            if c.old(p) != row['state']:
                c.holds.append(dict(kind='original_car_precondition_changed', pos=p, expected=row['state'], actual=c.old(p)))
            if p not in car_targets:
                source_only_cars.append(p)
                c.put(p, VOID, 'retired_original_car_source_only')

    # Complete new main shaft, original-car sweep kept empty until last layer.
    for x, y, z in points((6, -848, 250), (12, -497, 256)):
        boundary = x in (6, 12) or z in (250, 256) or y in (-848, -497)
        value = STRUCT if boundary else VOID
        if boundary and c.old((x, y, z)) == 'projectseele:nerv_pyramid_panel':
            value = 'projectseele:nerv_pyramid_panel'
        c.put((x, y, z), value, 'main_full_shaft')
    # East upper car/shaft/floors remain authored. Only extend below its former
    # bottom -555; removing the old fixed bottom opens the continuous sweep.
    for x, y, z in points((63, -605, 299), (69, -555, 305)):
        boundary = x in (63, 69) or z in (299, 305) or y == -605
        c.put((x, y, z), STRUCT if boundary else VOID, 'east_lower_extension')

    # Root-defined high hangar connector: narrowed to three cells, preserving
    # its complete outer envelope and the existing column at x8/z288.
    c.fill((6, -604, 257), (12, -599, 287), WALL, 'hangar_link_shell')
    c.fill((6, -604, 257), (12, -604, 287), FLOOR, 'hangar_link_floor')
    c.fill((9, -603, 258), (11, -600, 287), VOID, 'hangar_link_clear')
    # At the five-wide native door, the short vestibule reaches the three-wide
    # corridor without silently narrowing the moving leaf itself.
    c.fill((7, -603, 257), (11, -600, 258), VOID, 'hangar_link_door_vestibule')
    c.fill((9, -603, 288), (11, -600, 288), VOID, 'hangar_observation_explicit_opening')

    # The two closely spaced HQ stops retain original two-cell human headroom;
    # a generic four-high tunnel here would erase the next floor.
    for y in HQ:
        owner = 'hq_landing_' + str(y)
        if y == -502:
            c.fill((9, y - 1, 258), (14, y - 1, 259), FLOOR, owner)
            c.fill((9, y, 258), (13, y + 1, 259), VOID, owner)
        else:
            c.fill((7, y - 1, 257), (14, y - 1, 259), FLOOR, owner)
            c.fill((8, y, 258), (13, y + 1, 259), VOID, owner)
            c.fill((7, y, 258), (7, y + 1, 259), WALL, owner)
        c.fill((14, y, 258), (14, y + 1, 259), WALL, owner)
        c.fill((12, y, 257), (14, y + 2, 257), STRUCT, 'retire_old_hq_door_plane')
        # Do not touch x9/z260. The existing three-wide x11..13 handoff is
        # retained and checked below, including its own original ceiling.

    # Terminal short source shaft has explicit retirement authority. No BE or
    # unrecognised room material may be hidden by this fill.
    c.fill((9, -847, 243), (15, -796, 249), 'minecraft:stone', 'retired_terminal_short_shaft')
    c.fill((7, -847, 257), (14, -847, 260), 'minecraft:polished_deepslate', 'terminal_foyer_floor')
    c.fill((7, -846, 257), (14, -843, 260), VOID, 'terminal_foyer_clear')
    c.fill((12, -846, 257), (14, -843, 257), STRUCT, 'terminal_retired_door_reveal')

    # Every declared new main landing receives a real threshold and a closed
    # outer leaf unless the one original native car is parked there.
    parked = {car['lift_id']: car['parked_after'] for car in interface['cabins']}
    for binding in manifest['lifts']:
        if binding['id'] not in (MAIN, EAST):
            continue
        for floor in binding['floors']:
            if binding['id'] == EAST and floor['cabin'][1] != -603:
                continue
            x, y, z = floor['cabin']
            c.fill((x - 2, y - 1, z + 3), (x + 2, y - 1, z + 4), FLOOR, 'native_threshold')
            c.fill((x - 2, y, z + 3), (x + 2, y + 2, z + 3), VOID, 'native_wall_aperture')
            for side in (x - 3, x + 3):
                c.fill((side, y, z + 4), (side, y + 2, z + 4), STRUCT, 'native_full_landing_jamb')
            c.fill((x - 3, y + 3, z + 4), (x + 3, y + 3, z + 4), STRUCT, 'native_landing_lintel')
            for leaf in floor['landing_doors']:
                c.put(leaf['pos'], VOID if parked[binding['id']] == y else leaf['closed_state'], 'native_outer_leaf')
            for leaf in floor['cabin_doors']:
                c.put(leaf['pos'], VOID, 'empty_floor_has_no_fixed_cabin_leaf')
    # Native control states and the original finite wall backing are composed
    # after room shells. No branch creates a replacement mechanism entity.
    facing = {'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0), 'west': (-1, 0, 0)}
    for row in interface['devices']:
        source, target = tuple(row['source']), tuple(row['target'])
        current_source = row.get('source_precondition_storage') == 'CURRENT_WORLD_STATE_MUST_MATCH_SOURCE_STATE'
        if current_source and c.old(source) != row['source_state']:
            c.holds.append(dict(kind='source_device_state_changed', pos=source, expected=row['source_state'], actual=c.old(source)))
        if current_source and source != target and row['role'] == 'moved_external_call':
            c.put(source, VOID, 'retired_original_call')
        c.put(target, row['target_state'], 'native_device')
        if 'external_call' in row['role'] and 'button[' in row['target_state']:
            direction = row['target_state'].split('facing=')[1].split(',')[0].split(']')[0]
            offset = facing[direction]
            backing = tuple(target[i] - offset[i] for i in range(3))
            source_backing = tuple(source[i] - offset[i] for i in range(3))
            if current_source and c.old(source_backing) not in NATURAL and c.old(source_backing) in ARCHITECTURE:
                c.put(backing, c.old(source_backing), 'original_call_backing')
            elif row['role'] == 'moved_external_call' and row.get('source_operation', '').startswith('RESTORE_FROZEN'):
                c.put(backing, STRUCT, 'terminal_call_backing_explicit_shaft_frame')
            else:
                c.holds.append(dict(kind='unknown_call_backing', pos=backing, source=source_backing))
    # Last geometry layer: the complete three original native cars. In-cabin
    # controls and original door openness are copied exactly, not reauthored.
    for car in interface['cabins']:
        for row in car['cells']:
            c.put(row['target'], row['state'], 'original_car_' + car['lift_id'])
    for y, value in [(-603, WALL), (-602, 'minecraft:black_concrete'), (-601, 'projectseele:clear_glass'),
                     (-600, WALL), (-599, STRUCT)]:
        c.put((64, y, 308), value, 'root_original_east_call_post')
    c.put((6, -501, 256), STRUCT, 'root_highest_call_shaft_backing')
    for point in SUPPORTS:
        c.put(point, STRUCT, 'root_exact_service_support_contact')

    # Compose typed BEs with no duplicate source deletion/target insertion.
    final_tags = dict(c.tags)
    for row in be_doc['operations']:
        if row.get('source_precondition_storage') == 'CURRENT_WORLD_BLOCK_ENTITY' and row['source_operation'] == 'MOVE_ORIGINAL_ONCE':
            final_tags.pop(tuple(row['source_position']), None)
    final_tags.update(target_tags)
    for point in target_tags:
        if point in c.tags and point not in source_tags:
            c.holds.append(dict(kind='other_block_entity_at_native_target', pos=point, id=str(c.tags[point].get('id', '')), nbt=c.tags[point].snbt()))
    for point, tag in c.tags.items():
        if c.after.get(point, c.old(point)) != c.old(point) and point not in source_tags and point not in target_tags:
            c.holds.append(dict(kind='other_block_entity_in_write_mask', pos=point, id=str(tag.get('id', '')), nbt=tag.snbt()))
    for point, tag in list(c.tags.items()):
        if 9 <= point[0] <= 15 and -847 <= point[1] <= -796 and 243 <= point[2] <= 249:
            c.holds.append(dict(kind='block_entity_in_retired_short_shaft', pos=point, id=str(tag.get('id', ''))))
    be_rows = []
    for point in sorted(set(source_tags) | set(target_tags)):
        before, after = c.tags.get(point), final_tags.get(point)
        be_rows.append(dict(pos=point, before_nbt=None if before is None else before.snbt(),
                            after_nbt=None if after is None else after.snbt(),
                            final_state=c.final(point), changed=(None if before is None else before.snbt()) != (None if after is None else after.snbt())))

    validation = validate(c, interface, manifest, source_only_cars)
    changed = [dict(pos=p, before=c.old(p), after=s, owner=c.owners[p]) for p, s in sorted(c.after.items()) if c.old(p) != s]
    unique_holds = {json.dumps(h, sort_keys=True): h for h in c.holds}
    holds = list(unique_holds.values())
    save(out / 'BLOCK_PATCH.json.gz', dict(status='CANDIDATE_NOT_APPLIED', cells=changed, inverse=[dict(pos=r['pos'], before=r['after'], after=r['before']) for r in changed]))
    save(out / 'BLOCK_ENTITY_FINAL.json', dict(status='CANDIDATE_NOT_APPLIED', source_operations=30, rows=be_rows))
    save(out / 'STATIC_VALIDATION.json', validation)
    save(out / 'HOLDS.json', holds)
    save(out / 'NATIVE_GROUP_METADATA_PATCH.json', groups)
    save(out / 'personnel_lifts_CANDIDATE_NOT_INSTALLED.json', manifest)
    save(out / 'CIVIL_NATIVE_DEVICE_INTERFACE.json', interface)
    save(out / 'WAYFINDING_INTERFACE_CANDIDATE.json', dict(ready=False, epoch=53, floor_call_updates=[dict(
        lift_id=MAIN, floor_y=-502, retired_call=[6, -501, 258], actual_call=[6, -501, 257],
        target_controller=[6, -502, 253], declared_approach=[10.5, -502, 258.5],
        existing_direction_board=[10, -500, 260], board_BE_preserved=True,
        instruction='Final derived wayfinding must use this same manifest call. No existing board BE was rewritten.')]))
    report = dict(world_written=False, ready=False, can_apply=False, authority='Root exact finite geometry; Root is sole world writer',
                  world=str(world), lift_candidate=str(lift_candidate), metadata_epoch=53, changed_blocks=len(changed),
                  composed_original_car_cells=sum(len(car['cells']) for car in interface['cabins']), composed_be_positions=len(be_rows),
                  changed_be_positions=sum(row['changed'] for row in be_rows), material_or_identity_holds=len(holds),
                  static_failures=len(validation['failures']), read_boxes=c.read_boxes,
                  needs=['Root reviews all HOLDs and static failures', 'Root combines exact inverse patches under its world lock',
                         'Native calls/riding/open-close and actual visuals after installation'],
                  inputs={str(p): sha(p.read_bytes()) for p in [lift_candidate / n for n in ('CIVIL_NATIVE_DEVICE_INTERFACE.json', 'NATIVE_BLOCK_ENTITY_PATCH.json', 'NATIVE_GROUP_METADATA_PATCH.json', 'personnel_lifts_CANDIDATE_NOT_INSTALLED.json')]})
    save(out / 'PLAN_REPORT.json', report)
    print(json.dumps({k: report[k] for k in ('world_written', 'changed_blocks', 'composed_original_car_cells', 'material_or_identity_holds', 'static_failures')}, ensure_ascii=False))
    return report


def validate(c, interface, manifest, source_only_cars):
    failures, routes = [], []
    shape_path = c.world / 'native_collision_shapes.json'
    shape_bytes = shape_path.read_bytes()
    shapes = json.loads(shape_bytes)
    missing_shapes = set()
    walk_cells = set()
    inactive_thresholds = set()
    interlocks = []
    def boxes(value):
        if value in AIR:
            return []
        if value not in shapes:
            missing_shapes.add(value)
            return None
        return shapes[value]
    def passable(value):
        return boxes(value) == []
    def bearing(value):
        collision = boxes(value)
        if collision is None:
            return False
        # Sample the complete cell wearing surface, including the original
        # 1/16-lower flat MTR step. Thin lamps/buttons cannot become supports.
        return all(any(b[0] <= x <= b[3] and b[2] <= z <= b[5] and .84 <= b[4] <= 1.01 for b in collision)
                   for x in (.08, .5, .92) for z in (.08, .5, .92))
    parked_by_id = {car['lift_id']: car['parked_after'] for car in interface['cabins']}
    for binding in manifest['lifts']:
        if binding['id'] not in (MAIN, EAST):
            continue
        for floor in binding['floors']:
            x, y, z = floor['cabin']
            if binding['id'] == EAST and y != -603:
                continue
            parked = parked_by_id[binding['id']] == y
            leaves_ok = all(c.final(leaf['pos']) == (VOID if parked else leaf['closed_state']) for leaf in floor['landing_doors'])
            def backed_jamb(xx, yy):
                point = (xx, yy, z + 4)
                if bearing(c.final(point)):
                    return True
                # Root places this one button directly on the inner shaft
                # pier, not on another floating full block in its own cell.
                return point == (6, -501, 257) and c.final(point) == 'minecraft:polished_blackstone_button[face=wall,facing=south,powered=false]' and c.final((6, -501, 256)) == STRUCT
            jambs_ok = all(backed_jamb(xx, yy) for xx in (x - 3, x + 3) for yy in range(y, y + 3))
            header_ok = all(bearing(c.final((xx, y + 3, z + 4))) for xx in range(x - 3, x + 4))
            interlocks.append(dict(lift=binding['id'], floor_y=y, original_car_here=parked, leaf_state_matches=leaves_ok,
                                   full_side_jambs=jambs_ok, solid_header=header_ok, empty_car_leaves_not_built=True))
            if not leaves_ok or not jambs_ok or not header_ok:
                failures.append(dict(kind='landing_interlock_enclosure_incomplete', lift=binding['id'], floor_y=y))
            if not parked and leaves_ok and jambs_ok and header_ok:
                inactive_thresholds.update((xx, y, z + 3) for xx in range(x - 2, x + 3))
    def corridor(name, xs, zs, y, height, allow_mtr=False):
        cases = []
        for x in xs:
            for z in zs:
                ground = c.final((x, y - 1, z))
                body = [c.final((x, yy, z)) for yy in range(y, y + height)]
                good = bearing(ground) and all(passable(v) for v in body)
                row = dict(pos=[x, y, z], floor=ground, body=body, static_clear=good)
                cases.append(row)
                if not good:
                    failures.append(dict(kind='floor_or_full_width_clearance', route=name, **row))
                else:
                    walk_cells.add((x, y, z))
        routes.append(dict(name=name, width_cells=len(xs), feet_y=y, clear_height=height, samples=cases,
                           inherited_native_collision_profiles=True, preserved_mtr_steps=allow_mtr))
    corridor('hangar_three_wide', range(9, 12), range(258, 289), -603, 4)
    corridor('hangar_existing_mtr_handoff', range(9, 12), range(289, 292), -603, 2, True)
    for y in HQ:
        corridor('hq_dogleg_west_to_east_' + str(y), range(9 if y == -502 else 8, 14), range(258, 260), y, 2)
        corridor('hq_original_three_wide_handoff_' + str(y), range(11, 14), range(260, 262), y, 2)
        for yy in (y, y + 1, y + 2):
            if c.final((9, yy, 260)) != c.old((9, yy, 260)):
                failures.append(dict(kind='protected_hq_shape_changed', pos=[9, yy, 260]))
    for point in ((8, -503, 258), (8, -503, 259), (7, -502, 258), (7, -502, 259), (6, -501, 258)):
        if c.final(point) != c.old(point):
            failures.append(dict(kind='protected_original_quartz_stair_changed', pos=point))
    corridor('terminal_inner_foyer', range(7, 15), range(258, 261), -846, 4)
    corridor('terminal_original_hall_handoff', range(10, 15), range(261, 263), -846, 3)
    corridor('east_hangar_original_handoff', range(65, 68), range(307, 310), -603, 2)
    # Fixed native occupancy sensor must see one parked original car, not a
    # newly laid floor at every stop. This is the real production floor rule.
    car_rows = []
    for binding in manifest['lifts']:
        detected = []
        for floor in binding['floors']:
            x, y, z = floor['cabin']
            full = all(c.final((xx, y - 1, zz)) in ('minecraft:polished_deepslate', STRUCT, 'movingelevators:button_block')
                       for xx in range(x - 2, x + 3) for zz in range(z - 2, z + 3))
            if full:
                detected.append(y)
        expected = next(car['parked_after'] for car in interface['cabins'] if car['lift_id'] == binding['id'])
        if detected != [expected]:
            failures.append(dict(kind='native_original_car_count', lift=binding['id'], detected=detected, expected=[expected]))
        car_rows.append(dict(lift=binding['id'], detected=detected, expected=[expected]))
    for point in SUPPORTS:
        if c.final(point) != STRUCT:
            failures.append(dict(kind='support_contact_not_full_structural', pos=point))
    for y in range(-603, -598):
        if c.final((8, y, 288)) != c.old((8, y, 288)):
            failures.append(dict(kind='observation_column_changed', pos=[8, y, 288]))
    for y in range(-847, -842):
        for z in range(257, 263):
            if c.final((15, y, z)) != c.old((15, y, z)):
                failures.append(dict(kind='terminal_east_wall_changed', pos=[15, y, z]))
    edge_checks = []
    # Also inspect every usable cell on the explicitly constructed wearing
    # surfaces/thresholds, not only the selected route centre bands.
    for point, value in list(c.after.items()):
        owner = c.owners[point]
        if value not in (FLOOR, 'minecraft:polished_deepslate') or not (
                owner.startswith('hq_landing_') or owner in ('native_threshold', 'hangar_link_floor', 'terminal_foyer_floor')):
            continue
        x, y, z = point
        if (x, y + 1, z) not in inactive_thresholds and bearing(value) and passable(c.final((x, y + 1, z))) and passable(c.final((x, y + 2, z))):
            walk_cells.add((x, y + 1, z))
    boundary_sides = 0
    for x, y, z in sorted(walk_cells):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            other = (x + dx, y, z + dz)
            if other in walk_cells:
                continue
            boundary_sides += 1
            # A drop is checked only beside the explicitly declared walk mask.
            # No surrounding air is promoted to a new room or route.
            floor = c.final((other[0], y - 1, other[2]))
            lower = c.final((other[0], y - 2, other[2]))
            if bearing(floor) or bearing(lower):
                continue
            guarded = False
            for yy in (y, y + 1):
                for b in boxes(c.final((other[0], yy, other[2]))) or []:
                    if yy + b[4] > y + .6 and yy + b[1] < y + 1.8:
                        guarded = True
            row = dict(inside=[x, y, z], outside=list(other), adjacent_floor=floor, next_floor=lower, guarded=guarded)
            edge_checks.append(row)
            if not guarded:
                failures.append(dict(kind='unprotected_declared_walk_edge', **row))
    sweep_rows = []
    car_targets = {tuple(cell['target']) for car in interface['cabins'] for cell in car['cells']}
    for name, lo, hi in [('main', (7, -847, 251), (11, -498, 255)), ('east', (64, -604, 300), (68, -453, 304))]:
        occupied = []
        for point in points(lo, hi):
            if point in car_targets:
                continue
            collision = boxes(c.final(point))
            if collision is None or collision:
                occupied.append(dict(pos=point, state=c.final(point)))
        sweep_rows.append(dict(name=name, voxel_box=[lo, hi], original_car_cells_excluded=True, fixed_occupants=occupied))
        if occupied:
            failures.append(dict(kind='native_car_sweep_obstructed', lift=name, count=len(occupied), samples=occupied[:12]))
    backings = []
    for point, owner in c.owners.items():
        if owner != 'original_call_backing':
            continue
        attached = any(bearing(c.final((point[0] + dx, point[1] + dy, point[2] + dz)))
                       for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))
        backings.append(dict(pos=point, attached_to_adjacent_solid=attached))
        if not attached:
            failures.append(dict(kind='native_call_backing_floating', pos=point))
    for value in sorted(missing_shapes):
        failures.append(dict(kind='missing_inherited_native_collision_profile', state=value))
    return dict(failures=failures, routes=routes, native_floor_sensor=car_rows,
                support_contacts=[dict(pos=p, final=c.final(p)) for p in SUPPORTS],
                source_only_car_cells=source_only_cars,
                edges=edge_checks, declared_floor_cells_examined=len(walk_cells), boundary_sides_examined=boundary_sides,
                landing_interlocks=interlocks, inactive_native_threshold_cells=sorted(inactive_thresholds),
                native_car_sweeps=sweep_rows, call_backing_contacts=backings,
                native_shape_source=dict(path=str(shape_path), sha256=sha(shape_bytes), runtime_retested=False),
                limitations=['Static inherited native-shape/declared-floor checks only; no live native riding claim',
                             'No room identities inferred from air', 'Unchanged upper east/office mechanisms remain original'],
                world_written=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--lift-candidate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    need(out.is_relative_to((ROOT / '.Codex').resolve()) and not out.exists(), 'Fresh .Codex review output required')
    out.mkdir(parents=True)
    build(args.world.resolve(), args.lift_candidate.resolve(), out)


def prepare_root_application(world, candidate, receipt_directory):
    """Return a validated Painter and before/after capability bytes, NO writes.

    Root calls this while holding its one world lock, then owns Painter.apply,
    atomic metadata replacement, rollback and native/final-world readback.
    """
    import regional_voxels as vox
    world, candidate = Path(world).resolve(), Path(candidate).resolve()
    receipt_directory = Path(receipt_directory).resolve()
    need(receipt_directory.is_relative_to((ROOT / '.Codex').resolve()), 'Prepared receipt directory must stay inside .Codex')
    report = json.loads((candidate / 'PLAN_REPORT.json').read_text('utf8'))
    need(Path(report['world']).resolve() == world and report['metadata_epoch'] == 53
         and report['material_or_identity_holds'] == 0 and report['static_failures'] == 0,
         'Exact same-world reviewed candidate with no HOLDs/failures required')
    need(not json.loads((candidate / 'HOLDS.json').read_text('utf8')), 'Unresolved HOLDs cannot be prepared')
    patch = json.loads(gzip.decompress((candidate / 'BLOCK_PATCH.json.gz').read_bytes()))
    rows = patch['cells']
    need(len({tuple(row['pos']) for row in rows}) == len(rows), 'Single composed final state per voxel required')
    changed_positions = {tuple(row['pos']) for row in rows}
    vox.WORLD, vox.DIM, vox.OUT = world, DIM, receipt_directory
    painter = vox.Painter(vertical_bounds=(-960, 320))
    for row in rows:
        p = tuple(row['pos'])
        painter.match((*p, *p), row['before'], row['after'], row['owner'])
    be_rows = json.loads((candidate / 'BLOCK_ENTITY_FINAL.json').read_text('utf8'))['rows']
    for row in be_rows:
        p = tuple(row['pos'])
        found = dict(iter_block_entities(world, DIM, p, p)).get(p)
        actual = None if found is None else found.snbt()
        need(actual == row['before_nbt'], 'Typed BE precondition changed before Root preparation: ' + str(p))
        if not row['changed']:
            continue
        after = None if row['after_nbt'] is None else nbtlib.parse_nbt(row['after_nbt'])
        if p in changed_positions:
            if after is not None:
                painter.block_entities[p] = after
            # Painter removes the old BE at a changed block and adds only its
            # declared replacement. A null after is therefore explicit removal.
        else:
            need(after is not None, 'NBT-only deletion requires separate Root writer support')
            before = None if row['before_nbt'] is None else nbtlib.parse_nbt(row['before_nbt'])
            painter.update_block_entity(p, row['final_state'], before, after, 'root_two_main_lifts_native_nbt')
    group_doc = json.loads((candidate / 'NATIVE_GROUP_METADATA_PATCH.json').read_text('utf8'))
    caps_path = world / 'dimensions/projectseele/geofront/data/capabilities.dat'
    before_bytes = caps_path.read_bytes()
    caps = nbtlib.File.parse(io.BytesIO(gzip.decompress(before_bytes)))
    groups = caps['data']['movingelevators:elevator_groups']
    for row in group_doc['operations']:
        need(row['source_key'] in groups and groups[row['source_key']].snbt() == row['before_snbt'], 'Current original group precondition changed')
        need(row['target_key'] == row['source_key'] or row['target_key'] not in groups, 'Target native group is already owned')
    for key, expected in group_doc['preserve_other_group_hashes'].items():
        need(key in groups and sha(groups[key].snbt().encode()) == expected, 'Other native group changed: ' + key)
    replacements = [(r['source_key'], r['target_key'], nbtlib.parse_nbt(r['after_snbt'])) for r in group_doc['operations']]
    for source, target, _ in replacements:
        if source != target:
            del groups[source]
    for _, target, after in replacements:
        groups[target] = after
    encoded = io.BytesIO()
    caps.write(encoded)
    painter.meta.update(root_author=True, epoch=53, civil_candidate=str(candidate), complete_original_car_cells=450,
                        office_preserved=True, world_written=False, native_verified=False)
    return painter, dict(path=caps_path, before=before_bytes, after=gzip.compress(encoded.getvalue(), mtime=0),
                         before_sha256=sha(before_bytes), original_group_count=len(group_doc['operations']),
                         preserved_other_group_hashes=group_doc['preserve_other_group_hashes'])


if __name__ == '__main__':
    main()
