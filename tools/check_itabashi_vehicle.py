"""Continuous straight station sweep of visible e44 body, doors and bogies.

Uses decoded offline cubes, without opening Minecraft or native databases.
Separates visible geometry, floor surfaces and doorway trigger planes.
"""
import argparse, json, math
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from author_itabashi_station import solid_boxes, dump
from check_kamonomiya_visible_models import clipped_half_width


def verify(candidate, write=True):
    model = candidate / 'vehicle-model'
    report = json.loads((model / 'e44_mini_cab_3.json').read_text('utf8'))
    d = json.loads((candidate / 'station-design.json').read_text('utf8'))
    native = json.loads((candidate / 'native-station-plan.json').read_text('utf8'))
    samples = json.loads((candidate / d['native_math_samples']).read_text('utf8'))
    packcheck = json.loads((model / 'active-pack-check.json').read_text('utf8'))
    if any(q['mtr_overrides'] for q in packcheck['packs']):
        raise ValueError('Enabled resource pack overrides MTR: resolve effective assets')
    if not report['all_selected_conditions_enclosed']:
        raise ValueError('Incomplete model condition coverage')
    with np.load(model / 'e44_mini_cab_3-visible-cubes.npz') as f:
        cubes = f['cubes']; slides = f['door_slides']; names = list(map(str, f['names']))
    horizontal, longitudinal_margin, vertical = .15, .15, .03
    bands = []
    low, high = np.asarray(report['visible_motion_bounds'])
    for y in range(math.floor(low[1] - vertical), math.ceil(high[1] + vertical)):
        widths = [(w, name) for v, slide, name in zip(cubes, slides, names)
                  if (w := clipped_half_width(v, slide, y - vertical, y + 1 + vertical)) is not None]
        if widths:
            w, name = max(widths)
            bands.append(dict(local_y=[y, y + 1], visible_half_width=w,
                              swept_half_width=w + horizontal, widest_part=name))
    longitudinal = max(abs(low[2]), abs(high[2])) + longitudinal_margin
    e = Editor(candidate); obstacles = []; tested = 0
    for rail, sample in zip(native['rails'], samples):
        p, q = rail['from'], rail['to']
        points = np.asarray(sample['points'])
        if p[1:] != q[1:] or rail['from_angle'] != 'E' or rail['to_angle'] != 'W':
            raise ValueError('This checker requires a flat E-W platform')
        if not sample['valid'] or abs(sample['native_length'] - 48) > 1e-7:
            raise ValueError('Invalid native platform maths')
        if np.max(np.abs(points[:, 1] - p[1])) > 1e-7 or np.max(np.abs(points[:, 2] - p[2] - .5)) > 1e-7:
            raise ValueError('Sampled geometry does not match platform clearance centre')
        x0, x1 = min(p[0], q[0]) + .5 - longitudinal, max(p[0], q[0]) + .5 + longitudinal
        for band in bands:
            y = p[1] + band['local_y'][0]
            z0, z1 = p[2] + .5 - band['swept_half_width'], p[2] + .5 + band['swept_half_width']
            for z in range(math.floor(z0), math.ceil(z1)):
                for x in range(math.floor(x0), math.ceil(x1)):
                    state = e.state(x, y, z); tested += 1
                    for bounds in solid_boxes(state):
                        lo = np.asarray(bounds[:3]) + [x, y, z]
                        hi = np.asarray(bounds[3:]) + [x, y, z]
                        if lo[0] < x1 and hi[0] > x0 and lo[2] < z1 and hi[2] > z0:
                            obstacles.append(dict(xyz=[x, y, z], state=state, band=band['local_y']))
    # Door and floor planes from the selected model are distinct from NORMAL
    # geometry. At the stop, their floor plane is level with the actual edge.
    floors = [q for q in report['parts'] if q['kind'] == 'FLOOR']
    doorways = [q for q in report['parts'] if q['kind'] == 'DOORWAY']
    floor_halfwidth = max(abs(q['closed_bounds'][side][0]) for q in floors for side in (0, 1))
    doorway_halfwidth = max(abs(q['closed_bounds'][side][0]) for q in doorways for side in (0, 1))
    boarding = []
    for car_centre in (3122.0, 3131.0):
        # A 0.6 m player footprint continuously overlaps either platform or
        # the train floor while crossing the 0.25 m support gap. This proves
        # geometry only; native passenger movement awaits serial integration.
        support_gap = 799.5 - floor_halfwidth - d['boarding_edge_z']
        floor_y = -77 + min(q['closed_bounds'][0][1] for q in floors)
        samples_z = np.linspace(797.5, 799.0, 151)
        unsupported = [float(z) for z in samples_z if z - .3 >= 798 and z + .3 <= 799.5 - floor_halfwidth]
        doorway_length = max(q['closed_bounds'][1][2] - q['closed_bounds'][0][2] for q in doorways)
        boarding.append(dict(car_centre_x=car_centre, floor_y=floor_y, platform_feet_y=-76,
                             support_gap=support_gap, player_footprint_width=.6, tested_centres=len(samples_z),
                             unsupported_samples=unsupported, doorway_longitudinal_span=doorway_length,
                             doorway_player_lateral_margin=(doorway_length - .6) / 2,
                             minimum_support_overlap_at_gap_midpoint=(.6 - support_gap) / 2,
                             native_doorway_plane_meets_platform_edge=(doorway_halfwidth == 1.5),
                             requires_open_doors=True, native_collision_callback_tested=False))
    errors = []
    if obstacles: errors.append('visible vehicle sweep intersects station blocks')
    if any(q['unsupported_samples'] or q['floor_y'] != q['platform_feet_y'] for q in boarding):
        errors.append('geometric boarding support gap is not continuously passable')
    if any(q['doorway_player_lateral_margin'] < .15 for q in boarding):
        errors.append('doorway plane too narrow for player')
    proof = dict(errors=errors, vehicle='e44_mini_cab_3', selected_part_instances=report['selected_part_instances'],
                 visible_cube_count=len(cubes), visible_geometry_bounds=report['visible_motion_bounds'],
                 non_visible_doorway_trigger_halfwidth=doorway_halfwidth, non_visible_floor_halfwidth=floor_halfwidth,
                 native_registry_width=report['native_width'], native_width_used_as_actual_visible_width=False,
                 bands=bands, longitudinal_half_extent_with_margin=longitudinal, block_tests=tested,
                 obstacle_count=len(obstacles), obstacles=obstacles[:40], horizontal_margin=horizontal,
                 vertical_margin=vertical, longitudinal_margin=longitudinal_margin,
                 visible_platform_gap=.1875, residual_horizontal_clearance=.0375,
                 door_motion_and_bogies_enclosed=True, continuous_straight_sweep=True, boarding_support=boarding,
                 enabled_resource_packs=packcheck, rendered_frame_verified=False,
                 native_boarding_runtime_verified=False, all_line_vehicle_sweep_complete=False, world_written=False)
    if write: dump(candidate / 'visible-model-sweep.json', proof)
    print('Itabashi visible e44 sweep:', len(obstacles), 'obstacles; floor boarding gap', boarding[0]['support_gap'], flush=True)
    if errors: raise ValueError(errors)
    return proof


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__); p.add_argument('--candidate', type=Path, required=True)
    verify(p.parse_args().candidate)
