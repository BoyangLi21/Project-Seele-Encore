"""Explicit pending-only folded anchors with two native feet for long spans.

No World edits. Each weld-to-foot path is bounded separately; both paths and
their combined steel length remain in the candidate, never an admission flag.
"""
import argparse
from collections import Counter
import itertools
import json
import math
from pathlib import Path
import numpy as np
from upright_native_anchor_selection_r53 import (AIR, BEARING, Gates, Ownership,
    MeasuredWorld, NativeBearingCells, finite_face, path_clear, read, require, retained_banks,
    retained_city, sha, source_check, source_folded_paths, verify_applied)


def length(path):
    return float(sum(np.linalg.norm(b-a) for a, b in zip(path, path[1:])))


def triangle_brace(main, second):
    """The shared normal exit is the apex, separated real wall faces the base."""
    apex = main[1]
    base = np.linalg.norm(main[-1]-second[-1])
    area = np.linalg.norm(np.cross(main[-1]-apex, second[-1]-apex))/2
    return base >= 1.5 and area >= .75


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'sockets', 'gates', 'gate-interface', 'terminal-seats',
                 'lining-npz', 'applied-receipt', 'native-shapes', 'resume-current',
                 'bank-plan', 'deep-applied', 'exclude-slots', 'model', 'head-transfer', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--maximum-path', type=float, default=8.)
    p.add_argument('--wall-search-radius', type=float)
    p.add_argument('--allow-reinforced-long-brackets', action='store_true')
    p.add_argument('--relocation-receipt', type=Path)
    p.add_argument('--allow-explicit-gate-update', action='store_true')
    p.add_argument('--additional-lining-npz', type=Path)
    p.add_argument('--additional-applied-receipt', type=Path)
    a = p.parse_args()
    search_radius = a.maximum_path if a.wall_search_radius is None else a.wall_search_radius
    require(0 < search_radius <= a.maximum_path, 'Wall lookup radius must remain inside the actual path limit')
    require(0 < a.maximum_path <= (20 if a.allow_reinforced_long_brackets else 8),
            'Long brackets need explicit opt-in; 20m is the absolute path limit')
    require(not a.output.exists() and not a.output.resolve().is_relative_to(a.base.resolve()), 'Fresh non-World output required')
    lining_sha = verify_applied(a.base, a.lining_npz, a.applied_receipt)
    source, prior, terminal, shapes = map(read, (a.sockets, a.resume_current, a.terminal_seats, a.native_shapes))
    proof = source_check(source, a.model, a.head_transfer)
    expected = dict(model_source_sha256=source['model_source_sha256'],
                    directory_geometry_sha256=source['directory_geometry_sha256'],
                    head_transfer_source_sha256=source['head_transfer_source_sha256'],
                    lining_npz_sha256=lining_sha, terminal_seats_sha256=sha(a.terminal_seats),
                    native_shapes_sha256=sha(a.native_shapes))
    require(prior['world'] == str(a.base.resolve()) and all(prior[k] == v for k, v in expected.items()), 'Resume must be this current source/world')
    moved = set()
    if prior['socket_requests_sha256'] != sha(a.sockets):
        require(a.relocation_receipt is not None, 'Changed sockets need precise relocation receipt')
        relocation = read(a.relocation_receipt)
        require(relocation['input_sockets_sha256'] == prior['socket_requests_sha256']
                and relocation['sha256'] == sha(a.sockets), 'Relocation must descend from resumed socket source')
        moved = {r['socket_id'] for r in relocation['relocated']}
        require(moved <= {r['socket_id'] for r in prior['pending']}, 'Never relocate an accepted/terminal socket')
    if prior['gate_candidate_sha256'] != sha(a.gates) or prior['gate_interface_sha256'] != sha(a.gate_interface):
        require(a.allow_explicit_gate_update, 'Gate changes require explicit current interface update')
    plan, deep = read(a.bank_plan), read(a.deep_applied)
    require(plan.get('world_written') and plan.get('full_component_exact_readback')
            and plan.get('source') == 'frozen original bank geometry' and deep.get('dy') == -384
            and deep.get('world_written') and deep.get('complete_source_and_target_exact_readback'), 'Original bank ownership required')
    gates, owned = Gates(a.gates, a.gate_interface), Ownership(a.lining_npz)
    require(bool(a.additional_lining_npz) == bool(a.additional_applied_receipt), 'Additional ownership needs its exact Root APPLIED receipt')
    additional_lining_sha = None
    if a.additional_lining_npz:
        additional_lining_sha = verify_applied(a.base, a.additional_lining_npz, a.additional_applied_receipt)
        additional = Ownership(a.additional_lining_npz)
        original = owned
        class AppliedUnion:
            def expected(self, position):
                return additional.expected(position) or original.expected(position)
        owned = AppliedUnion()
    gates.proxies.update(tuple(c['position']) for c in read(a.exclude_slots)['changes'])
    requests = {r['socket_id']: r for r in source['sockets']}
    prior_seats = {r['socket_id']: r for r in prior['seats']}
    terminal_ids = {r['socket_id'] for r in terminal['seats']}
    require(terminal_ids <= prior_seats.keys() and not terminal_ids & moved, 'All proven terminal18 are immutable')
    world = MeasuredWorld(a.base, 'projectseele:geofront')
    span = math.ceil(a.maximum_path)+1
    pending_rows = [r for k, r in requests.items() if k not in prior_seats]
    for r in pending_rows:
        origin = np.floor(r['rail_bearing']).astype(int)
        world.box(tuple(origin-span), tuple(origin+span))
    for r in prior_seats.values():
        world.box(tuple(r['at']), tuple(r['at']))
    world.load()
    seats = []
    prior_sha = sha(a.resume_current)
    for key, r in prior_seats.items():
        state = world.block(tuple(r['at']))
        native = [np.asarray(b)+np.tile(r['at'], 2) for b in shapes.get(state, [])]
        require(state == r['state'] and finite_face(native, r['bearing'], r['normal']), f'Preserved actual face changed: {key}')
        # Terminals have a stronger exact full moving/fixed hatch source proof.
        require(key in terminal_ids or not gates.excludes_cell(r['at']), f'Preserved face enters current gate envelope: {key}')
        seats.append(dict(r, preserved_clearance_receipt_sha256=prior_sha))
    cells = NativeBearingCells(world)
    pending = []
    for count, row in enumerate(pending_rows, 1):
        origin = np.asarray(row['rail_bearing']); outward = np.asarray(row['normal']); near = origin+outward*.12
        prefix_clear, prefix_reason = path_clear([origin, near], None, world, shapes, gates)
        if not prefix_clear:
            pending.append(dict(socket_id=row['socket_id'], leg=row['leg'], side=row['side'], rail_bearing=row['rail_bearing'],
                reason='current_source_normal_exit_blocked_before_any_wall_choice', failures={prefix_reason: 1}))
            if count % 50 == 0:
                print(f'pending only {count}/{len(pending_rows)} selected={len(seats)} unresolved={len(pending)}', flush=True)
            if count % 25 == 0:
                a.output.parent.mkdir(parents=True, exist_ok=True)
                a.output.with_suffix('.PROGRESS.json').write_text(json.dumps(dict(seats=seats, pending=pending, processed=count)), 'utf8')
            continue
        floor = np.floor(origin).astype(int); faces = []; failures = Counter()
        for at in cells.near(origin, math.ceil(search_radius)+1):
            if sum((np.asarray(at)-floor)**2) > (search_radius+1.8)**2:
                continue
            expected_state = owned.expected(at)
            purpose = 'applied_current_lining' if expected_state else 'retained_original_bank_or_connector' if retained_banks(at) else 'retained_original_city_shaft' if retained_city(at) else None
            if purpose is None:
                continue
            state = world.block(at)
            if state not in BEARING or state not in shapes or (expected_state and expected_state != state) or gates.excludes_cell(at):
                continue
            for raw in shapes[state]:
                box = np.asarray(raw)+np.tile(at, 2)
                for axis in range(3):
                    if any(box[j+3]-box[j] < .400001 for j in range(3) if j != axis):
                        continue
                    for sign in (-1, 1):
                        face = np.clip(near, box[:3]+.2, box[3:]-.2); face[axis] = box[axis+3] if sign > 0 else box[axis]
                        normal = np.zeros(3); normal[axis] = sign
                        distance = float(np.linalg.norm(face-origin))
                        if not .15 <= distance <= a.maximum_path or (origin-face)[axis]*sign <= .2:
                            continue
                        faces.append((distance, at, state, face, normal, purpose))
        faces.sort(key=lambda c: (c[0], c[1]))
        chosen = None
        for distance, at, state, face, normal, purpose in faces:
            # The real finite width, not a renamed thin rod, controls collision.
            long = distance > 7.5
            width = .25 if long else .12
            radius = math.sqrt(2)*width/2+.0002
            for path in source_folded_paths(row, face, normal, proof, a.maximum_path, radius):
                total = length(path)
                if total > 8 and not long:
                    continue
                clear, reason = path_clear(path, at, world, shapes, gates, radius)
                if not clear:
                    failures[reason] += 1
                    continue
                second = None
                if long:
                    if not a.allow_reinforced_long_brackets:
                        continue
                    for other_distance, other_at, other_state, other_face, other_normal, other_purpose in faces:
                        # Both feet remain on the explicitly applied lining for long spans.
                        separation = float(np.linalg.norm(other_face-face))
                        if purpose != 'applied_current_lining' or other_purpose != purpose or not 1.5 <= separation <= 4.5:
                            continue
                        for branch in source_folded_paths(row, other_face, other_normal, proof, a.maximum_path, radius):
                            if not triangle_brace(path, branch):
                                continue
                            branch_clear, _ = path_clear(branch, other_at, world, shapes, gates, radius)
                            if branch_clear:
                                second = dict(at=list(map(int, other_at)), state=other_state, bearing=other_face.tolist(), normal=other_normal.tolist(),
                                              connector_via_world=[x.tolist() for x in branch[1:-1]], connector_path_length_m=length(branch),
                                              selected_by=other_purpose, native_capsule_clear=True, native_seat_width_m=.35)
                                break
                        if second:
                            break
                    if not second:
                        failures['no_second_actual_lining_face_with_clear_triangular_brace'] += 1
                        continue
                chosen = dict(socket_id=row['socket_id'], at=list(map(int, at)), state=state, bearing=face.tolist(), normal=normal.tolist(),
                              connector_via_world=[x.tolist() for x in path[1:-1]], connector_path_length_m=total, connector_distance_m=distance,
                              finite_connector_limit_m=a.maximum_path, connector_width_m=width, native_seat_width_m=.35 if long else .2,
                              actual_weld_normal=row['normal'], source_exit_metres=.12, selected_by=purpose,
                              capture_halfspace_source_checked=True, native_capsule_clear=True, complete_gate_envelope_clear=True,
                              full_carrier_mesh_admission_pending=True, secondary_native_seat=second,
                              combined_steel_length_m=total+(second['connector_path_length_m']-.12 if second else 0))
                break
            if chosen:
                break
        if chosen:
            seats.append(chosen)
        else:
            pending.append(dict(socket_id=row['socket_id'], leg=row['leg'], side=row['side'], rail_bearing=row['rail_bearing'],
                                reason='no_bounded_source_clear_owned_face_triangle_in_searched_radius', wall_search_radius_m=search_radius,
                                owned_native_faces=len(faces), failures=dict(failures)))
        if count % 50 == 0:
            print(f'pending only {count}/{len(pending_rows)} selected={len(seats)} unresolved={len(pending)}', flush=True)
        if count % 25 == 0:
            a.output.parent.mkdir(parents=True, exist_ok=True)
            a.output.with_suffix('.PROGRESS.json').write_text(json.dumps(dict(seats=seats, pending=pending, processed=count)), 'utf8')
    result = dict(prior, status='CURRENT_PENDING_REINFORCED_NATIVE_FACE_CANDIDATE', seats=seats, pending=pending,
                  socket_requests_sha256=sha(a.sockets), gate_candidate_sha256=sha(a.gates), gate_interface_sha256=sha(a.gate_interface),
                  explicit_current_resume_sha256=sha(a.resume_current), preserved_current_seats=len(prior_seats),
                  finite_connector_limit_m=a.maximum_path, reinforcement_width_m=.25,
                  wall_search_radius_m=search_radius,
                  reinforcement_policy='Each actual weld-to-native-foot path <= selected limit. Two distinct native lining faces, finite normal exit, >=0.25m main and diagonal strut for long spans; total metal is reported separately.',
                  pending_final_full_carrier_and_fixed_steel_source_review=True,
                  relocated_pending_socket_ids=sorted(moved), world_written=False, production_enable=False)
    result['additional_lining_npz_sha256'] = additional_lining_sha
    result['additional_applied_receipt_sha256'] = sha(a.additional_applied_receipt) if a.additional_applied_receipt else None
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n', 'utf8')
    print(json.dumps(dict(output=str(a.output), seats=len(seats), pending=len(pending))), flush=True)


if __name__ == '__main__':
    main()
