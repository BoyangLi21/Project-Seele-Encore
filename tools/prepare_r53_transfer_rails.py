"""Prepare actual three-channel track steel and reversible floor work, offline.

Inputs are the declared native route samples, measured query_blocks cells and
the selected complete carrier source. This never edits a save or starts Java.
"""
import argparse
import hashlib
import gzip
import json
import math
import zipfile
from pathlib import Path

import numpy as np
from build_r53_carrier_rear_guides import BASIS, FACES, beam, guide_frame, rgb, reduce_knots


def prepare(world, samples, measured, hardware_path, output):
    native = json.loads(samples.read_text('utf8'))
    owner = json.loads((world / 'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    directory = json.loads((world / 'ROOT_RUNTIME_DIRECTORY.json').read_text('utf8'))
    hardware = json.loads(hardware_path.read_text('utf8'))
    declared = {l['id']: l for l in directory['legs']}
    with zipfile.ZipFile(world.parents[1] / 'mods/projectseele-0.1.0-all.jar') as archive:
        carrier = json.loads(archive.read('assets/projectseele/mesh/carrier_mk2_r53.json'))
    assert carrier['source_triangles'] == 8727 and carrier['fitting']['source_faces_removed'] == 0
    deck = np.asarray(carrier['parts']['deck']).reshape(-1, 8)[:, :3]
    assert np.max(np.abs(deck[:, 0])) < 13
    solids = {'minecraft:iron_block', 'minecraft:light_gray_concrete', 'minecraft:black_concrete',
              'minecraft:deepslate[axis=y]', 'minecraft:polished_basalt[axis=y]',
              'minecraft:polished_blackstone', 'minecraft:oxidized_cut_copper', 'minecraft:sea_lantern',
              'projectseele:nerv_floor_panel', 'projectseele:nerv_structural_panel',
              'projectseele:nerv_machine_panel', 'projectseele:nerv_machine_edge',
              'projectseele:nerv_machine_hazard', 'projectseele:nerv_shaft_panel'}
    luminaires = {'projectseele:nerv_ceiling_light[hanging=true,lit=true]', 'projectseele:nerv_strip_light[lit=true]'}
    pieces, sockets, patches, route_rows, runtime_bays, gate_rows = [], [], [], [], [], []
    def steel_box(name, ident, mount, lo, hi, gate=None, motion=None):
        vertices = np.asarray([[x, y, z] for z in (lo[2], hi[2]) for y in (lo[1], hi[1]) for x in (lo[0], hi[0])])
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        indices = [i for a, b, c, d in faces for i in (a, b, c, a, c, d)]
        pieces.append(dict(name=name, leg=ident, mount=mount, component='support', origin=[0, 0, 0],
                           triangles_rgb=rgb(vertices[indices]), bridge_gate=gate, motion=motion))
    for leg in native['legs']:
        if not leg['leg'].endswith('/original_incline'):
            continue
        ident = leg['leg']; variant = int(ident[4]); spec = declared[ident]
        assert spec['motion'] == 'ORIGINAL_UPRIGHT_TRANSFER' and spec['rails'] == [f'rail/{ident}']
        unit = next(u for u in owner['units'] if u['variant'] == variant)
        source = leg['samples']; roots = np.asarray([s['root'] for s in source])
        tangents = np.asarray([s['tangent'] for s in source]); qs = np.asarray([guide_frame(t) for t in tangents])
        metres = np.asarray([s['metres'] for s in source]); cx = round(roots[0, 0] - .5)
        assert np.linalg.norm(roots[0] - unit['bay_frame']['position']) < 1e-8
        cells = {tuple(c[:3]): c[3] for c in json.loads((measured / f'unit{variant}-route-cells.json').read_text('utf8'))}
        protected = {tuple(c['position']) for c in unit['gantry']['supports'] + unit['carrier_support']}
        gate = next(g for g in owner['gates'] if g['resource'] == f'bay_{variant}_front')
        gate_rows.append(dict(resource=gate['resource'], visual=gate['visual'], frame=gate['frame']))
        steps = gate['collision_steps']
        if isinstance(steps, dict):
            steps = json.loads(gzip.decompress((world / steps['cells_file']).read_bytes()))
        moving = {tuple(c['position']) for row in steps for c in row}
        moving.difference_update(tuple(c) for c in gate.get('floor_seal_original_cells', []))
        before_patch = json.loads((measured / 'three-bay-tray-candidate' / f'unit{variant}' / 'forwardPatch.json').read_text('utf8'))
        changes = {tuple(c['pos']): c for c in before_patch}

        def put(at, state, purpose):
            assert at in cells and at not in protected, ('Unmeasured/protected equipment cell', at)
            assert at not in moving, ('Moving door cell must remain owner-controlled', at)
            old = cells[at]
            if old == state:
                return
            assert old == 'minecraft:air' or old in solids or old in luminaires, ('Unexpected existing equipment material', at, old)
            prior = changes.get(at)
            assert prior is None or prior['after'] == state, ('Conflicting equipment work', at)
            changes[at] = dict(pos=list(at), before=old, after=state, before_nbt=None, after_nbt=None, purpose=purpose)

        # A source-footprint sweep chooses the bottom. Permission comes from
        # the explicit original rail leg, never from the measured air cells.
        bottoms = {}
        for z in range(109, 304):
            occupied = roots[(roots[:, 2] >= z + deck[:, 2].min() - .25)
                             & (roots[:, 2] <= z + 1 + deck[:, 2].max() + .25)]
            assert len(occupied)
            lowest = occupied[:, 1].min() + deck[:, 1].min()
            bottom = math.floor(lowest - .75) - 1
            bottoms[z] = bottom
            for x in range(cx - 13, cx + 14):
                lowered_light = any(cells.get((x, y, z)) in luminaires
                                    for y in range(bottom + 1, math.floor(occupied[:, 1].max())))
                put((x, bottom, z), 'minecraft:sea_lantern' if lowered_light else 'projectseele:nerv_structural_panel',
                    'lowered_original_equipment_luminaire' if lowered_light else 'original_equipment_route_closed_bottom')
                for y in range(bottom + 1, math.floor(occupied[:, 1].max())):
                    at = (x, y, z)
                    if at not in moving and not cells.get(at, '').startswith('projectseele:lcl['):
                        put(at, 'minecraft:air', 'complete_original_deck_route_clearance')

        # The offset rear shoes reach each raised platform before the load
        # datum. Give their real low source members a side recess as well;
        # lowering only the central deck band would retain the known bank
        # obstruction at Unit01 (45,-1031,143).
        head_clearance = set()
        for mount in hardware['mounts']:
            ball = np.asarray(mount['ball'])
            origins = roots + BASIS @ ball - qs[:, :, 1] * .35 + [mount['side'] * .65, 7, 0]
            for part in hardware['parts']:
                if part['frame'] != mount['id']:
                    continue
                mesh = np.asarray(part['triangles_rgb']).reshape(-1, 6)[:, :3]
                points = np.einsum('nij,kj->nki', qs, mesh) + origins[:, None, :]
                low, high = points.min(1) - .15, points.max(1) + .15
                for lo, hi in zip(np.floor(low).astype(int), np.floor(high).astype(int)):
                    for x in range(lo[0], hi[0] + 1):
                        for y in range(lo[1], hi[1] + 1):
                            for z in range(lo[2], hi[2] + 1):
                                at = (x, y, z); old = cells.get(at)
                                head_clearance.add(at)
                                if at in moving or old is None or old == 'minecraft:air' or old.startswith('projectseele:lcl['):
                                    continue
                                assert abs(x + .5 - roots[0, 0]) < 16, ('Retain outer personnel path', at)
                                put(at, 'minecraft:air', 'actual_rear_shoe_offset_platform_recess')

        # The existing outer personnel floor remains in place. Close its
        # exposed underside at the equipment edge and fence the outside of
        # the complete head envelope, rather than narrowing the moving load.
        for z in range(109, 294):
            nominal = math.floor(roots[np.argmin(abs(roots[:, 2] - z)), 1])
            for x in (cx - 14, cx + 14):
                floor = [y for y in range(nominal - 6, nominal + 1) if cells.get((x, y, z)) in solids]
                if not floor:
                    continue
                for y in range(bottoms[z], max(floor)):
                    at = (x, y, z)
                    if at not in head_clearance and at not in moving and at not in protected and cells.get(at) == 'minecraft:air':
                        put(at, 'projectseele:nerv_structural_panel', 'original_equipment_tray_side_closure')
            for x in (cx - 17, cx + 17):
                floor = [y for y in range(nominal - 6, nominal + 1) if cells.get((x, y, z)) in solids]
                assert floor, ('Existing outer personnel floor required', ident, x, z)
                at = (x, max(floor) + 1, z)
                if cells.get(at) != 'minecraft:air':
                    continue
                inward = 'east=true,north=false,south=false,west=false' if x < cx else 'east=false,north=false,south=false,west=true'
                put(at, 'projectseele:nerv_edge_rail[' + inward + ']', 'existing_personnel_floor_equipment_edge_guard')

        # Each real rail head retains the current 7m transfer lift and 0.65m
        # inward motion. The original root, EVA and trajectory stay unchanged.
        for mount in hardware['mounts']:
            ball = np.asarray(mount['ball'])
            origins = roots + BASIS @ ball - qs[:, :, 1] * .35 + [mount['side'] * .65, 7, 0]
            origins[-1] -= tangents[-1] * .12
            local_sections = []
            for x0, y0, x1, y1 in (hardware['rail_head_section'], hardware['rail_web_section']):
                local_sections.extend([[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]])
            corners = np.einsum('nij,kj->nki', qs, np.asarray(local_sections)) + origins[:, None, :]
            keep = {i for i in reduce_knots(roots, corners) if 1 <= i <= len(source) - 1}
            keep.update([1, len(source) - 1])
            boundaries = {}
            for boundary in (294.5, 303.5):
                index = int(np.argmin(np.abs(origins[:, 2] - boundary)))
                keep.add(index); boundaries[index] = boundary
            keep = sorted(keep)
            bridge_rows = np.where((origins[:, 2] >= 294.3) & (origins[:, 2] <= 303.7))[0]
            track_x = float(origins[0, 0]); outward = 1 if track_x > roots[0, 0] else -1
            carriage_x = track_x - outward * .4
            storage_rows = np.where((origins[:, 2] >= 294.3) & (origins[:, 2] <= 326.3))[0]
            arm_top = float(np.min(corners[storage_rows, :, 1])) - .65
            arm_bottom = arm_top - .24
            next_support = 0.
            for i, j in zip(keep, keep[1:]):
                # Finite ground seats cover the initial 0.25m and final 0.12m.
                frames = qs[[i, j]]; origin = origins[[i, j]]
                centre_z = float(origin[:, 2].mean())
                bridge = 294.5 < centre_z < 303.5
                for component, section in [('head', hardware['rail_head_section']), ('web', hardware['rail_web_section'])]:
                    x0, y0, x1, y1 = section
                    local = np.asarray([[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]])
                    vertices = (np.einsum('nij,kj->nki', frames, local) + origin[:, None, :]).reshape(8, 3)
                    # World-Z mitres let the transverse bridge slide off a
                    # shared finite end face without opening a bearing gap.
                    for endpoint, index in enumerate((i, j)):
                        if index in boundaries:
                            for v in vertices[endpoint * 4:(endpoint + 1) * 4]:
                                v += tangents[index] * ((boundaries[index] - v[2]) / tangents[index, 2])
                    centre = vertices.mean(0)
                    name = f'transfer/{ident}/{mount["id"]}/{i}/{component}'
                    pieces.append(dict(name=name, leg=ident, mount=mount['id'], component=component,
                                       origin=centre.tolist(), triangles_rgb=rgb((vertices - centre)[FACES]),
                                       bridge_gate=gate['resource'] if bridge else None,
                                       motion='head' if bridge else None))
                if bridge or metres[i] < next_support:
                    continue
                # A finite vertical web seat bears on a measured full block
                # outside the complete original deck's X extent.
                point = origins[i] + qs[i, :, 1] * hardware['rail_web_section'][1]
                for boundary, side in ((294.5, -1), (303.5, 1)):
                    if abs(point[2] - boundary) < .3:
                        point = point + tangents[i] * ((boundary + side * .35 - point[2]) / tangents[i, 2])
                x, z = math.floor(point[0]), math.floor(point[2])
                bypass_slide = 303.4 < point[2] < 327
                if bypass_slide:
                    x = math.floor(track_x + outward * 1.5)
                seats = [(y, changes.get((a, y, c), {}).get('after', state)) for (a, y, c), state in cells.items()
                         if a == x and c == z and y + 1 < point[1]
                         and changes.get((a, y, c), {}).get('after', state) in solids]
                if not seats:
                    from query_blocks import read_box
                    column = read_box(world, 'projectseele:geofront', (x, math.floor(point[1]) - 14, z),
                                      (x, math.floor(point[1]) - 1, z))
                    cells.update(column)
                    seats = [(p[1], changes.get(p, {}).get('after', state)) for p, state in column.items()
                             if p[1] + 1 < point[1] and changes.get(p, {}).get('after', state) in solids]
                if not seats:
                    outward = 1 if point[0] > roots[0, 0] else -1
                    lo, hi = sorted([x, x + outward * 5])
                    margin = read_box(world, 'projectseele:geofront', (lo, math.floor(point[1]) - 14, z - 2),
                                      (hi, math.floor(point[1]) - 1, z + 2))
                    choices = [(float(np.linalg.norm(np.asarray([p[0] + .5, p[1] + 1, p[2] + .5]) - point)), p, state)
                               for p, state in margin.items() if state in solids and p[1] + 1 < point[1]]
                    assert choices, ('No measured structural seat in the explicit equipment margin', ident, point.tolist())
                    _, (x, y, z), state = min(choices)
                    seats = [(y, state)]
                assert seats, ('Measured original rail seat missing', ident, mount['id'], point.tolist())
                y, state = max(seats)
                start = np.asarray([min(x + .85, max(x + .15, point[0])), y + 1., z + .5])
                assert np.max(np.abs(start[[0, 2]] - [x + .5, z + .5])) < .46
                support_name = f'transfer/{ident}/{mount["id"]}/{i}/support'
                seat = start.copy();start[1] += .12
                steel_box(support_name + '/foot', ident, mount['id'],
                          [seat[0] - .12, seat[1], seat[2] - .12], [seat[0] + .12, seat[1] + .12, seat[2] + .12])
                if bypass_slide:
                    elbow = np.asarray([track_x + outward, max(arm_top + .3, point[1] - .4), point[2]])
                    triangles = beam(start, elbow, .12) + beam(elbow, point, .12)
                else:
                    triangles = beam(start, point, .12)
                pieces.append(dict(name=support_name, leg=ident, mount=mount['id'], component='support',
                                   origin=[0, 0, 0], triangles_rgb=triangles, bridge_gate=None))
                sockets.append(dict(leg=ident, mount=mount['id'], rail_piece=support_name + '/foot',
                                    anchor=dict(at=[x, y, z], state=state, bearing=seat.tolist(), normal=[0, 1, 0])))
                next_support = metres[i] + 8
            prefix = f'transfer/{ident}/{mount["id"]}/slide'
            steel_box(prefix + '/arm', ident, mount['id'],
                      [carriage_x - .6, arm_bottom, 294.5], [carriage_x + .6, arm_top, 312.5], gate['resource'], 'carriage')
            steel_box(prefix + '/runner', ident, mount['id'],
                      [carriage_x - .1, arm_bottom - .2, 303.7], [carriage_x + .1, arm_bottom, 326])
            for z in (295., 302.):
                nearest = int(np.argmin(abs(origins[:, 2] - z)))
                top = float(origins[nearest, 1] + qs[nearest, 1, 1] * hardware['rail_web_section'][1])
                steel_box(prefix + f'/cross_shoe_{int(z)}', ident, mount['id'],
                          [track_x - .15, arm_top, z - .2], [track_x + .15, top, z + .2], gate['resource'], 'head')
            for z in (305, 314, 324):
                x = math.floor(carriage_x)
                seats = [(y, changes.get((a, y, c), {}).get('after', state)) for (a, y, c), state in cells.items()
                         if a == x and c == z and y + 1 < arm_bottom - .2
                         and changes.get((a, y, c), {}).get('after', state) in solids]
                assert seats, ('Sliding bridge requires its actual retained floor', ident, x, z)
                y, state = max(seats); name = prefix + f'/post_{z}'
                steel_box(name, ident, mount['id'], [carriage_x - .1, y + 1., z + .4],
                          [carriage_x + .1, arm_bottom - .2, z + .6])
                sockets.append(dict(leg=ident, mount=mount['id'], rail_piece=name,
                                    anchor=dict(at=[x, y, z], state=state, bearing=[carriage_x, y + 1., z + .5], normal=[0, 1, 0])))
        runtime = json.loads((measured / 'three-bay-tray-candidate' / f'unit{variant}' / 'runtime-bay.json').read_text('utf8'))
        bank_local = BASIS @ (roots[-1] - roots[0])
        for number, (x, z) in enumerate([(-8.7, -10.8), (8., -10.8), (-11.1, 13.1), (10.6, 13.1)]):
            top = bank_local[1] - 4.0078125
            bottom = min(bottoms[math.floor(roots[-1, 2] - z + dz)] + 1 - roots[0, 1] for dz in (-.3, .3))
            vertices = np.asarray([[x + dx, y, bank_local[2] + z + dz]
                                   for dz in (-.3, .3) for y in (bottom, top) for dx in (-.3, .3)])
            # Match the established box order used by the bay support source.
            faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
            indices = [i for a, b, c, d in faces for i in (a, b, c, a, c, d)]
            runtime['rails'].append(dict(name=f'bank_foot_{number}', triangles_rgb=rgb(vertices[indices])))
        row = sorted(changes.values(), key=lambda c: c['pos'])
        target = output / f'unit{variant}'; target.mkdir(parents=True, exist_ok=True)
        (target / 'forwardPatch.json').write_text(json.dumps(row, separators=(',', ':')), 'utf8')
        (target / 'inversePatch.json').write_text(json.dumps([dict(pos=c['pos'], before=c['after'], after=c['before'],
            before_nbt=None, after_nbt=None) for c in row], separators=(',', ':')), 'utf8')
        patches.extend(row)
        runtime['cells'] = [dict(pos=c['pos'], state=c['after']) for c in row] + [dict(pos=c['position'], state=c['state']) for c in unit['gantry']['supports']]
        runtime_bays.append(runtime)
        route_rows.append(dict(leg=ident, variant=variant, root_start=roots[0].tolist(), root_end=roots[-1].tolist(),
                               floor_bottom_by_z=bottoms, original_cells_preserved=len(moving), edits=len(row)))
    output.mkdir(parents=True, exist_ok=True)
    doc = dict(schema='projectseele.r53.carrier-transfer-rails.v1', directory=native['directory'],
               hardware_sha256=hashlib.sha256(hardware_path.read_bytes()).hexdigest(),
               support_source='original_native_full_blocks', pieces=pieces, sockets=sockets, routes=route_rows,
               gates=gate_rows,
               bridge_inward_m=.8, bridge_slide_m=12, bridge_deploy_progress=[.9, .95, 1], ready_to_install=False)
    (output / 'transfer-rails.json').write_text(json.dumps(doc, separators=(',', ':')), 'utf8')
    (output / 'bay-trays.json').write_text(json.dumps(dict(schema='projectseele.r53.carrier-bay-trays.v1', bays=runtime_bays), separators=(',', ':')), 'utf8')
    print(json.dumps(dict(routes=len(route_rows), steel_parts=len(pieces), actual_supports=len(sockets),
                          changed_cells=len(patches), world_written=False)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('world', 'samples', 'measured', 'hardware', 'output'):
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args()
    prepare(a.world, a.samples, a.measured, a.hardware, a.output)
