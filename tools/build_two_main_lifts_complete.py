"""Build review-only native lift metadata from the frozen delivered R50 archive.

No --apply mode, world writer, new cabin UUID, or third main lift exists here.
The output is restricted to .Codex. Root must merge exact NBT paths after its
own civil construction, then perform native readback before setting ready.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import io
import json
import re
from pathlib import Path
import tempfile
import uuid
import zipfile

import nbtlib

from query_blocks import read_box, iter_block_entities, AIR
from r52_spatial_plan import Frame
from facility_frame_nbt_r52 import block_entity_in_frame
from verify_main_r20 import entities

ROOT = Path(__file__).resolve().parents[1]
DIM = 'projectseele:geofront'
DIM_PATH = 'dimensions/projectseele/geofront'
CAPS = DIM_PATH + '/data/capabilities.dat'
MAIN = 's20-command-rear-x12-z253-v4'
EAST = 'r25-east-command-gallery'
OFFICE = 's23-commander-office-x28-z321-v1'
OTHER = {'s20-compact-cage-x93-z204-v4', 's20-surface-transit-v2', 'r25-west-observation'}
BASELINE = ROOT / 'artifacts/r52_personnel_lift_runtime/ORIGINAL_OFFICE_AND_DOORS.json'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', 'utf8')


def coordinate(tag):
    return tuple(int(tag[k]) for k in ('x', 'y', 'z'))


def snbt(tag):
    return tag.snbt()


def archive_evidence(archive, out):
    """Only finite original device/entity region evidence, never a playable world."""
    names = archive.namelist()
    found = [n for n in names if n.endswith('/' + CAPS)]
    need(len(found) == 1, 'One original GeoFront capability member required')
    prefix = found[0][:-len(CAPS)]
    members = [found[0]]
    members += [prefix + DIM_PATH + '/region/r.0.0.mca']
    # Original personnel actors are surveyed through the existing entity reader.
    members += [n for n in names if n.startswith(prefix + DIM_PATH + '/entities/') and n.endswith('.mca')]
    receipts = []
    for name in members:
        need(name in names, 'Missing original evidence member: ' + name)
        relative = Path(name[len(prefix):])
        need(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe archive evidence path')
        raw = archive.read(name)
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        receipts.append(dict(member=name, bytes=len(raw), sha256=sha(raw)))
    return prefix, receipts


def original_lift(evidence, groups, identity, cabin, controller, old_floors, exit_side, inside):
    key = f'{controller[0]};{controller[1]}'
    need(key in groups, 'Original native group missing: ' + key)
    saved = groups[key]
    native = saved['group']
    need(tuple(int(saved['pos'][k]) for k in ('x', 'z')) == controller, 'Original group axis differs')
    need(not bool(native['isMoving']), 'Moving native cage cannot be reset or guessed into a parked floor')
    need(list(map(int, native['floors'])) == old_floors, 'Original native floors differ: ' + key)
    need(len(native['floorData']) == len(old_floors), 'Native floor progress table is incomplete')
    expected = {'cageSizeX': 5, 'cageSizeY': 6, 'cageSizeZ': 5,
                'cageHeightOffset': -1, 'cageDepthOffset': 0, 'cageSideOffset': 0}
    need(all(int(native[k]) == value for k, value in expected.items()), 'Original cage dimensions/offsets need explicit review')
    need(int(saved['pos']['facing']) == (3 if identity != OFFICE else 1), 'Native group facing differs')
    parked = [y for y, data in zip(old_floors, native['floorData']) if bool(data['isCageAvailable'])]
    need(len(parked) == 1, 'Original stationary group must retain exactly one authored car')
    lo = (cabin[0] - 8, min(old_floors) - 2, cabin[1] - 8)
    hi = (cabin[0] + 8, max(old_floors) + 6, cabin[1] + 8)
    cells = read_box(evidence, DIM, lo, hi)
    tags = dict(iter_block_entities(evidence, DIM, lo, hi))
    need(all((controller[0], y, controller[1]) in tags for y in old_floors), 'Missing measured floor controller BE')
    return dict(id=identity, key=key, cabin=cabin, controller=controller, floors=old_floors,
                exit=exit_side, inside=inside, group=saved, parked=parked[0], cells=cells, tags=tags)


def state(lift, point):
    need(tuple(point) in lift['cells'], 'Unmeasured source point: ' + str(point))
    return lift['cells'][tuple(point)]


def floor_calls(lift, y, office):
    x, z = lift['cabin']
    if lift['id'] == EAST:
        positions = [(x - 1, y + 1, z + 6)]
    elif lift['id'] == OFFICE:
        positions = [tuple(p) for p in office['readers'] if p[1] == y + 1]
    else:
        positions = [(x - 3, y + 1, z + 5)]
    need(positions, 'No declared original floor call')
    calls = []
    for point in positions:
        before = state(lift, point)
        tag = lift['tags'].get(point)
        if before.startswith('minecraft:polished_blackstone_button['):
            kind = 'vanilla_button'
            facing = before.split('facing=')[1].split(',')[0].split(']')[0]
        elif tag is not None and str(tag['id']) == 'projectseele:nerv_access_reader':
            need(int(tag.get('Clearance', 0)) == 3, 'Original office clearance must remain highest')
            kind = 'seele_reader'
            facing = before.split('facing=')[1].split(',')[0].split(']')[0]
        else:
            raise ValueError(('Unrecognised original external call; do not invent a replacement', point, before))
        calls.append(dict(kind=kind, source=point, state=before, facing=facing, tag=tag))
    return calls


def door_cells(lift, y, distance, half):
    x, z = lift['cabin']
    dz = 1 if lift['exit'] == 'south' else -1
    return [(x + side, y + dy, z + dz * distance) for side in range(-half, half + 1) for dy in range(3)]


def closed_material(lift, distance, half):
    materials = set()
    for y in lift['floors']:
        for point in door_cells(lift, y, distance, half):
            value = state(lift, point)
            if 'stained_glass' in value:
                materials.add(value)
    if not materials:
        # The only original car is parked with its leaves open; absent cars
        # cannot supply a closed material. Read the actual production owner.
        source = ROOT / 'src/main/java/com/projectseele/world/S20PhysicalElevatorDirector.java'
        field = 'CABIN_DOOR' if distance == 2 else 'LANDING_DOOR'
        match = re.search(r'private static final BlockState ' + field + r'\s*=\s*Blocks\.([A-Z_]+)\.defaultBlockState\(\)', source.read_text('utf8'))
        need(match is not None and match[1].endswith('STAINED_GLASS'), 'No measured closed leaf or exact original production owner')
        material = 'minecraft:' + match[1].lower()
        lift.setdefault('closed_material_sources', {})[field] = dict(kind='exact_production_owner_for_open_original_leaves', source=str(source), sha256=digest(source), field=field)
        return material
    need(len(materials) == 1, 'Actual original closed door material is ambiguous')
    material = next(iter(materials))
    lift.setdefault('closed_material_sources', {})['CABIN_DOOR' if distance == 2 else 'LANDING_DOOR'] = dict(kind='measured_closed_original_leaf', state=material)
    return material


def create_lift(lift, mapping, dx, dz, new_hangar, office, be_patches, block_interfaces, cabin_interfaces):
    source_native = lift['group']['group']
    references = {(lift['controller'][0], old, lift['controller'][1]):
                  (lift['controller'][0] + dx, new, lift['controller'][1] + dz) for old, new in mapping.items()}
    new_key = f"{lift['controller'][0] + dx};{lift['controller'][1] + dz}"
    after = copy.deepcopy(lift['group'])
    after['pos']['x'] = type(after['pos']['x'])(lift['controller'][0] + dx)
    after['pos']['z'] = type(after['pos']['z'])(lift['controller'][1] + dz)
    rows = [(new, old, copy.deepcopy(source_native['floorData'][lift['floors'].index(old)])) for old, new in mapping.items()]
    if new_hangar is not None:
        need(new_hangar not in mapping.values(), 'Hangar stop must be its own added floor')
        prototype_y = -448 if lift['id'] == MAIN else -461
        added = copy.deepcopy(source_native['floorData'][lift['floors'].index(prototype_y)])
        added['name'] = type(added['name'])('机库上层观察廊')
        added['isCageAvailable'] = type(added['isCageAvailable'])(0)
        rows.append((new_hangar, prototype_y, added))
    rows.sort()
    after['group']['floors'] = nbtlib.IntArray([new for new, _, _ in rows])
    after['group']['floorData'] = nbtlib.List[nbtlib.Compound]([data for _, _, data in rows])
    need(sum(bool(d['isCageAvailable']) for d in after['group']['floorData']) == 1, 'Original car occupancy changed')
    for key in source_native:
        if key not in {'floors', 'floorData'}:
            need(snbt(after['group'][key]) == snbt(source_native[key]), 'Unexpected native progress/config reset: ' + key)

    landing_state = closed_material(lift, 4, 2)
    cabin_state = closed_material(lift, 2, 1)
    binding = dict(id=lift['id'], controller_side='east' if lift['id'] == OFFICE else 'west',
                   controller_facing='west' if lift['id'] == OFFICE else 'east',
                   inside_button_offset=lift['inside'], inside_display_offset=[lift['inside'][0], lift['inside'][1] + 1, lift['inside'][2]], floors=[])

    def emit_be(before, frame, category, refs=references):
        transformed = block_entity_in_frame(before, frame, reference_positions=refs)
        row = dict(owner_lift=lift['id'], kind=category, source_position=coordinate(before), target_position=coordinate(transformed),
                   source_nbt=snbt(before), source_nbt_sha256=sha(snbt(before).encode()), target_nbt=snbt(transformed),
                   source_operation='COPY_PROTOTYPE_DO_NOT_REMOVE' if category.startswith('new_') else 'MOVE_ORIGINAL_ONCE',
                   target_precondition='ROOT_MUST_READ_AFTER_CIVIL_CONSTRUCTION; no overwrite permission granted')
        be_patches.append(row)
        return transformed

    for new_y, old_y, progress in rows:
        added = new_hangar is not None and new_y == new_hangar
        frame = Frame(0, dx, new_y - old_y, dz)
        controller_source = (lift['controller'][0], old_y, lift['controller'][1])
        controller = frame.block(controller_source)
        original_controller = lift['tags'][controller_source]
        need(str(original_controller['id']) == 'movingelevators:elevator_tile', 'Wrong native floor-controller type')
        transformed = emit_be(original_controller, frame, 'new_floor_controller_from_original_prototype' if added else 'move_original_floor_controller')
        if added:
            transformed['data']['name'] = type(transformed['data']['name'])('机库上层观察廊')
            be_patches[-1]['target_nbt'] = snbt(transformed)
        controls = []
        for call in floor_calls(lift, old_y, office):
            target = frame.block(call['source'])
            controls.append(dict(kind=call['kind'], position=target, state=call['state'], facing=call['facing'], target_controller=controller))
            block_interfaces.append(dict(owner_lift=lift['id'], role='new_external_call' if added else 'moved_external_call',
                                         source=call['source'], source_state=call['state'], target=target, target_state=call['state']))
            if call['tag'] is not None:
                emit_be(call['tag'], frame, 'move_original_office_reader')
        restricted = (lift['id'] == MAIN and old_y == -566) or (lift['id'] == OFFICE and old_y in (-364, -340))
        floor = dict(label=str(progress['name']), cabin=frame.block((lift['cabin'][0], old_y, lift['cabin'][1])),
                     exit=lift['exit'], approach_y=new_y, controller=controller, calls=controls, restricted=restricted)
        for key, distance, half, material in [('landing_doors', 4, 2, landing_state), ('cabin_doors', 2, 1, cabin_state)]:
            floor[key] = [dict(pos=frame.block(p), closed_state=material) for p in door_cells(lift, old_y, distance, half)]
        binding['floors'].append(floor)
        block_interfaces.append(dict(owner_lift=lift['id'], role='new_controller' if added else 'moved_controller',
                                     source=controller_source, source_state=state(lift, controller_source),
                                     target=controller, target_state=state(lift, controller_source)))

    parked = lift['parked']
    car_frame = Frame(0, dx, mapping[parked] - parked, dz)
    car_lo = (lift['cabin'][0] - 2, parked - 1, lift['cabin'][1] - 2)
    car_hi = (lift['cabin'][0] + 2, parked + 4, lift['cabin'][1] + 2)
    voxels = []
    for y in range(car_lo[1], car_hi[1] + 1):
        for z in range(car_lo[2], car_hi[2] + 1):
            for x in range(car_lo[0], car_hi[0] + 1):
                p = (x, y, z)
                voxels.append(dict(source=p, target=car_frame.block(p), state=state(lift, p)))
                if p in lift['tags']:
                    emit_be(lift['tags'][p], car_frame, 'move_original_cabin_device')
    need(len(voxels) == 150, 'Complete original native car must contain 150 captured cells including interior air')
    cabin_interfaces.append(dict(lift_id=lift['id'], parked_before=parked, parked_after=mapping[parked],
                                 source_box=[car_lo, car_hi], target_box=car_frame.box(car_lo, car_hi), cells=voxels,
                                 new_cabin_created=False, ownership_note='Move original snapshot atomically; remove source-only cells after overlapping target placement'))
    if lift['id'] == OFFICE:
        frame = Frame(0, 0, mapping[-388] + 388, 0)
        for reader in office['room_controls']['gate_readers']:
            point = tuple(reader['position'])
            tag = lift['tags'].get(point)
            need(tag is not None and str(tag['id']) == 'projectseele:nerv_access_reader'
                 and int(tag.get('Clearance', 0)) == 3 and not bool(tag.get('Linked', 0)),
                 'Original two-sided office gate reader/clearance differs')
            emit_be(tag, frame, 'move_original_office_room_reader')
            for role, p in [('office_room_reader', point), ('office_room_reader_backing', tuple(reader['backing']))]:
                blocks_value = state(lift, p)
                block_interfaces.append(dict(owner_lift=lift['id'], role=role, source=p, source_state=blocks_value,
                                             target=frame.block(p), target_state=blocks_value))
        for door in office['room_controls']['gate']:
            x, y, z = door['lower']
            for p in [(x, y, z), (x, y + 1, z)]:
                blocks_value = state(lift, p)
                need('door' in blocks_value and blocks_value not in AIR, 'Original protected office gate leaf missing')
                block_interfaces.append(dict(owner_lift=lift['id'], role='office_room_gate', source=p, source_state=blocks_value,
                                             target=frame.block(p), target_state=blocks_value))
    return binding, dict(lift_id=lift['id'], path=['data', 'movingelevators:elevator_groups'], source_key=lift['key'], target_key=new_key,
                         before_snbt=snbt(lift['group']), after_snbt=snbt(after), floor_mapping={str(k): v for k, v in mapping.items()},
                         added_floor=new_hangar, parked_before=parked, parked_after=mapping[parked], preserved_native_progress=True)


def office_access(source, dy, hangar):
    result = copy.deepcopy(source)
    frame = Frame(0, 0, dy, 0)
    result['middle_y'] += dy
    result['readers'] = [frame.block(p) for p in source['readers']]
    result['middle_reader'] = frame.block(source['middle_reader'])
    for key in ('meeting_boxes', 'lift_room_boxes', 'landing_lease_box'):
        boxes = result[key] if key != 'landing_lease_box' else [result[key]]
        for box in boxes:
            box[1] += dy
            box[4] += dy
    controls = result['room_controls']
    for row in controls['gate']:
        row['lower'] = frame.block(row['lower'])
    for row in controls['gate_readers']:
        for key in ('position', 'backing'):
            row[key] = frame.block(row[key])
    for row in controls['pilot_guard_doors']:
        row['lower'] = hangar.block(row['lower'])
        row['facing'] = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}[row['facing']]
        row['approach_feet'] = [hangar.point(p) for p in row['approach_feet']]
    return result


def bind_current_stage(world, dy, group_patches, be_patches, blocks, cabins, blockers):
    """Bind exact preconditions after Root's three core component moves.

    No mutation occurs here. Frozen Terminal data restores the original removed
    stop; current native progress and typed device settings remain authoritative.
    """
    raw = (world / CAPS).read_bytes()
    current = nbtlib.File.parse(io.BytesIO(gzip.decompress(raw)))['data']['movingelevators:elevator_groups']
    references = {}
    for patch in group_patches:
        key = patch['source_key']
        need(key in current, 'Current source native group was already renamed: ' + key)
        need(patch['target_key'] == key or patch['target_key'] not in current, 'Target native group is already owned; do not overwrite it')
        before = current[key]
        need(not bool(before['group']['isMoving']), 'Current native group is moving; migration cannot reset it')
        frozen = nbtlib.parse_nbt(patch['before_snbt'])
        after = nbtlib.parse_nbt(patch['after_snbt'])
        expected = [int(old) + dy for old in patch['floor_mapping'] if not (patch['lift_id'] == MAIN and int(old) == -566)]
        need(list(map(int, before['group']['floors'])) == expected, 'Current core-stage floors differ: ' + key)
        actual_rows = {int(y): copy.deepcopy(v) for y, v in zip(before['group']['floors'], before['group']['floorData'])}
        need(sum(bool(v['isCageAvailable']) for v in actual_rows.values()) == 1, 'Current parked car progress is ambiguous')
        need(bool(actual_rows[patch['parked_after']]['isCageAvailable']), 'Current occupied car no longer matches the frozen original car')
        final_rows = []
        for y, original_row in zip(after['group']['floors'], after['group']['floorData']):
            yy = int(y)
            if yy in actual_rows:
                final_rows.append(actual_rows[yy])
            elif yy == patch['added_floor']:
                row = copy.deepcopy(actual_rows[-448 + dy if patch['lift_id'] == MAIN else -461 + dy])
                row['name'] = type(row['name'])('机库上层观察廊')
                row['isCageAvailable'] = type(row['isCageAvailable'])(0)
                final_rows.append(row)
            else:
                need(patch['lift_id'] == MAIN and yy == patch['floor_mapping']['-566']
                     and not bool(original_row['isCageAvailable']), 'Only the unoccupied original Terminal row may be restored from archive')
                final_rows.append(original_row)
        for field, value in before['group'].items():
            if field not in {'floors', 'floorData'}:
                after['group'][field] = copy.deepcopy(value)
        after['group']['floorData'] = nbtlib.List[nbtlib.Compound](final_rows)
        patch['frozen_source_group_snbt'] = snbt(frozen)
        patch['before_snbt'] = snbt(before)
        patch['after_snbt'] = snbt(after)
        patch['application_stage'] = 'CURRENT_WORLD_AFTER_TERMINAL_PYRAMID_HANGAR_CORE_MOVES'
        for y in before['group']['floors']:
            references[(int(before['pos']['x']), int(y), int(before['pos']['z']))] = (int(after['pos']['x']), int(y), int(after['pos']['z']))

    point_rows = {}
    for row in be_patches:
        frozen_source = tuple(row['source_position'])
        terminal = row['owner_lift'] == MAIN and frozen_source[1] == -566
        row['frozen_source_position'] = frozen_source
        row['frozen_source_nbt'] = row['source_nbt']
        if terminal:
            row['kind'] = 'restore_original_terminal_controller_from_frozen_archive'
            row['source_operation'] = 'RESTORE_FROZEN_ORIGINAL; NO_CURRENT_SOURCE_REMOVAL'
            row['source_precondition_storage'] = 'FROZEN_ARCHIVE_IDENTITY_EVIDENCE_ONLY'
            continue
        point = (frozen_source[0], frozen_source[1] + dy, frozen_source[2])
        point_rows.setdefault(point, []).append(row)
    if point_rows:
        lo = tuple(min(p[i] for p in point_rows) for i in range(3))
        hi = tuple(max(p[i] for p in point_rows) for i in range(3))
        actual_tags = dict(iter_block_entities(world, DIM, lo, hi))
        for point, rows in point_rows.items():
            need(point in actual_tags, 'Current original device missing after core move: ' + str(point))
            before = actual_tags[point]
            for row in rows:
                frozen_tag = nbtlib.parse_nbt(row['frozen_source_nbt'])
                need(str(before['id']) == str(frozen_tag['id']), 'Current device changed type; do not overwrite it')
                target = row['target_position']
                frame = Frame(0, target[0] - point[0], target[1] - point[1], target[2] - point[2])
                after = block_entity_in_frame(before, frame, reference_positions=references)
                if row['kind'] == 'new_floor_controller_from_original_prototype':
                    after['data']['name'] = type(after['data']['name'])('机库上层观察廊')
                row.update(source_position=point, source_nbt=snbt(before), source_nbt_sha256=sha(snbt(before).encode()), target_nbt=snbt(after),
                           source_precondition_storage='CURRENT_WORLD_BLOCK_ENTITY')
    for car in cabins:
        frozen_box = car['source_box']
        lo = (frozen_box[0][0], frozen_box[0][1] + dy, frozen_box[0][2])
        hi = (frozen_box[1][0], frozen_box[1][1] + dy, frozen_box[1][2])
        measured = read_box(world, DIM, lo, hi)
        for cell in car['cells']:
            p = tuple(cell['source'])
            current_p = (p[0], p[1] + dy, p[2])
            need(measured.get(current_p) == cell['state'], 'Current original cabin cell differs from frozen component: ' + str(current_p))
            cell['frozen_source'] = p
            cell['source'] = current_p
        car['frozen_source_box'] = frozen_box
        car['source_box'] = [lo, hi]
        car['application_stage'] = 'CURRENT_WORLD_AFTER_CORE_MOVES'
    for row in blocks:
        source = tuple(row['source'])
        row['frozen_source'] = source
        if row['owner_lift'] == MAIN and -566 <= source[1] <= -565:
            row['source_operation'] = 'RESTORE_FROZEN_ORIGINAL; NO_CURRENT_SOURCE_REMOVAL'
        else:
            row['source'] = (source[0], source[1] + dy, source[2])
            row['source_precondition_storage'] = 'CURRENT_WORLD_STATE_MUST_MATCH_SOURCE_STATE'
    # The old Terminal component had its own Z translation. Report, never
    # delete, any old floor controller now outside the current main-lift group.
    candidate = (9, -846, 246)
    orphan = dict(iter_block_entities(world, DIM, candidate, candidate)).get(candidate)
    orphan_report = None
    if orphan is not None and str(orphan['id']) == 'movingelevators:elevator_tile':
        orphan_report = dict(position=candidate, nbt=snbt(orphan), action='ROOT_MUST_RESOLVE_ORPHAN_SOURCE_CONTROLLER; NO_REMOVAL_AUTHORIZED')
        blockers.append('Original Terminal controller survives at the moved Terminal old axis and needs explicit Root retirement')
    preserved = {key: sha(snbt(value).encode()) for key, value in current.items() if key not in {p['source_key'] for p in group_patches}}
    return dict(world=str(world), capabilities_sha256=sha(raw), preserved_other_group_hashes=preserved, orphan_terminal_controller=orphan_report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-server-zip', type=Path, required=True)
    parser.add_argument('--current-world', type=Path, required=True, help='Read-only Root world after the three core component moves')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--epoch', type=int, required=True)
    parser.add_argument('--directory-fingerprint', required=True)
    parser.add_argument('--main-shift-x', type=int, default=-3)
    parser.add_argument('--main-shift-z', type=int, default=0)
    parser.add_argument('--headquarters-dy', type=int, default=-93)
    parser.add_argument('--hangar-y', type=int, default=-603)
    parser.add_argument('--terminal-y', type=int, default=-846)
    parser.add_argument('--office-contract', type=Path, default=BASELINE)
    parser.add_argument('--retained-lift-manifest', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    need(out.is_relative_to((ROOT / '.Codex').resolve()) and not out.exists(), 'Use a fresh review directory strictly inside this checkout .Codex')
    need(args.epoch > 0 and len(args.directory_fingerprint) == 64 and all(c in '0123456789abcdef' for c in args.directory_fingerprint), 'Explicit candidate epoch and SHA256 fingerprint required')
    need(args.terminal_y < args.hangar_y < -461 + args.headquarters_dy, 'Terminal, hangar and headquarters order differs')
    out.mkdir(parents=True)
    office = json.loads(args.office_contract.read_text('utf8'))['office_access']
    need(office['lift_id'] == OFFICE, 'Original office identity contract required')
    blockers = ['Final native world readback and all-floor riding not performed',
                'Root must author destination device/door/shaft preconditions and inverse patches',
                'Current stage preconditions must still match exactly when Root merges this candidate']
    if (args.main_shift_x, args.main_shift_z) == (-3, 0):
        blockers.append('Current main-axis candidate has 30 measured original fixed-mechanism intersections; do not install it without Root geometry resolution')
    group_patches, be_patches, blocks, cabins, bindings = [], [], [], [], []
    with zipfile.ZipFile(args.baseline_server_zip) as archive, tempfile.TemporaryDirectory(prefix='lift_read_evidence_', dir=out) as temp:
        evidence = Path(temp)
        prefix, members = archive_evidence(archive, evidence)
        raw_caps = (evidence / CAPS).read_bytes()
        caps = nbtlib.File.parse(io.BytesIO(gzip.decompress(raw_caps)))
        groups = caps['data']['movingelevators:elevator_groups']
        lifts = [original_lift(evidence, groups, MAIN, (12, 253), (9, 253), [-566, -448, -423, -419, -409], 'south', [-2, 1, 0]),
                 original_lift(evidence, groups, EAST, (66, 302), (63, 302), [-461, -448, -434, -420, -406, -392, -378, -364], 'south', [-2, 1, 0]),
                 original_lift(evidence, groups, OFFICE, (28, 321), (31, 321), [-388, -364, -340], 'north', [2, 1, 0])]
        for lift in lifts:
            mapping = {y: y + args.headquarters_dy for y in lift['floors']}
            if lift['id'] == MAIN:
                mapping[-566] = args.terminal_y
            dx, dz = (args.main_shift_x, args.main_shift_z) if lift['id'] == MAIN else (0, 0)
            binding, patch = create_lift(lift, mapping, dx, dz, None if lift['id'] == OFFICE else args.hangar_y,
                                         office, be_patches, blocks, cabins)
            bindings.append(binding)
            group_patches.append(patch)
        actors = entities(evidence)
        actor_review = []
        for identity, actor in actors.items():
            if str(actor.get('LiftId', '')) in {MAIN, EAST, OFFICE} or str(actor.get('id', '')) in {'projectseele:nerv_lift_door', 'projectseele:nerv_lift_cabin'}:
                actor_review.append(dict(uuid=str(uuid.UUID(int=sum((v & 0xffffffff) << (96 - 32 * i) for i, v in enumerate(identity)))), nbt=snbt(actor)))
        if actor_review:
            blockers.append('Existing lift-related entity graph requires explicit Root identity migration; no UUIDs or positions guessed')
        legacy_name = prefix + DIM_PATH + '/data/projectseele_s20_physical_elevators_v1.dat'
        if legacy_name in archive.namelist():
            blockers.append('Legacy physical-lift SavedData exists and needs explicit Runtime CurrentY/TargetY/Fingerprint migration')
        preserved = {key: sha(snbt(value).encode()) for key, value in groups.items() if key not in {p['source_key'] for p in group_patches}}
        write(out / 'ORIGINAL_ENTITY_REVIEW.json', dict(total_original_actor_ids=len(actors), lift_related=actor_review,
                                                       new_entities_created=0, original_entities_deleted=0, legacy_runtime_member_present=legacy_name in archive.namelist()))
    current_stage = bind_current_stage(args.current_world.resolve(), args.headquarters_dy, group_patches, be_patches, blocks, cabins, blockers)
    for binding in bindings:
        patch = next(p for p in group_patches if p['lift_id'] == binding['id'])
        actual = nbtlib.parse_nbt(patch['after_snbt'])['group']
        names = {int(y): str(row['name']) for y, row in zip(actual['floors'], actual['floorData'])}
        for floor in binding['floors']:
            floor['label'] = names[floor['cabin'][1]]
    need(len({tuple(row['target_position']) for row in be_patches}) == len(be_patches), 'Two owners target one native block entity')
    if args.retained_lift_manifest:
        retained = json.loads(args.retained_lift_manifest.read_text('utf8'))
        rows = retained['lifts']
        need({r['id'] for r in rows} == OTHER, 'Retained manifest must explicitly account for the other three original S20 lifts; no third main lift')
        bindings.extend(copy.deepcopy(rows))
    else:
        blockers.append('Other three original S20 lift bindings need explicit final-layout metadata; their native groups remain byte-identical in this patch')
    main_roles = {}
    for role, lift, dx, dz in [('command_rear', lifts[0], args.main_shift_x, args.main_shift_z), ('east_gallery', lifts[1], 0, 0)]:
        main_roles[role] = dict(lift_id=lift['id'], source_axis=dict(cabin=lift['cabin'], controller=lift['controller']), shaft_translation=[dx, dz],
                                headquarters_floors=[y + args.headquarters_dy for y in lift['floors'] if not (lift['id'] == MAIN and y == -566)], hangar_floor=args.hangar_y)
        if lift['id'] == MAIN:
            main_roles[role]['terminal_floor'] = args.terminal_y
    candidate = dict(schema='projectseele.r52.s20-lifts.v1', scope='s20_personnel_only', complete_replacement=True,
                     epoch=args.epoch, directory_fingerprint=args.directory_fingerprint, ready=False, main_lifts=main_roles,
                     lifts=bindings, office_access=office_access(office, args.headquarters_dy, Frame(180, 60, -236, 88)))
    write(out / 'personnel_lifts_CANDIDATE_NOT_INSTALLED.json', candidate)
    write(out / 'NATIVE_GROUP_METADATA_PATCH.json', dict(status='CANDIDATE_NOT_APPLIED', frozen_capabilities_sha256=sha(raw_caps),
                                                       current_stage=current_stage, operations=group_patches,
                                                       preserve_other_group_hashes=current_stage['preserved_other_group_hashes'],
                                                       merge_only=True, full_capabilities_replacement_forbidden=True))
    write(out / 'NATIVE_BLOCK_ENTITY_PATCH.json', dict(status='CANDIDATE_NOT_APPLIED', operations=be_patches))
    write(out / 'CIVIL_NATIVE_DEVICE_INTERFACE.json', dict(status='ROOT_CIVIL_INTERFACE_NOT_A_BLOCK_PATCH', devices=blocks, cabins=cabins,
                                                         closed_material_sources={lift['id']: lift['closed_material_sources'] for lift in lifts},
                                                         doors=[dict(lift_id=b['id'], floors=[dict(cabin=f['cabin'], landing_doors=f['landing_doors'], cabin_doors=f['cabin_doors']) for f in b['floors']]) for b in bindings]))
    report = dict(world_written=False, world_opened=False, source_archive=str(args.baseline_server_zip.resolve()),
                  source_archive_sha256=digest(args.baseline_server_zip), source_members=members, source_office_contract_sha256=digest(args.office_contract),
                  current_stage=current_stage,
                  source_script_sha256=digest(Path(__file__)), root_apply_supported=False, ready=False, blockers=blockers,
                  original_native_groups_migrated=len(group_patches), additional_main_lifts=0, new_native_floor_controllers=2,
                  original_cars_moved=len(cabins), original_car_voxels=sum(len(c['cells']) for c in cabins), native_be_operations=len(be_patches),
                  restored_original_terminal_controllers=1, preserved_group_keys=list(current_stage['preserved_other_group_hashes']),
                  outputs={p.name: digest(p) for p in out.glob('*.json')})
    write(out / 'BUILD_REPORT.json', report)
    print(json.dumps({k: report[k] for k in ('world_written', 'ready', 'original_native_groups_migrated', 'additional_main_lifts', 'original_car_voxels', 'native_be_operations', 'blockers')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
