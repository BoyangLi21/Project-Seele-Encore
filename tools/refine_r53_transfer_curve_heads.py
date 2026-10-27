"""Refine installed transfer head/web steel on the declared original ramp.

Only source triangles change. Native seats, bridge strokes, route endpoints,
load calibration and the world remain untouched.
"""
import argparse
import copy
import json
import math
from pathlib import Path

import numpy as np

from build_r53_carrier_rear_guides import BASIS, FACES, guide_frame


def refine(rails, hardware, owner, directory):
    result = copy.deepcopy(rails)
    legs = {row['id']: row for row in directory['legs']}
    nodes = {row['id']: row for row in directory['nodes']}
    units = {row['variant']: row for row in owner['units']}
    mounts = {row['id']: row for row in hardware['mounts']}
    changed = 0
    added = 0
    max_bound = 0.
    for row in result['pieces']:
        if row['component'] not in ('head', 'web'):
            continue
        name = row['leg']
        assert name in legs and name.endswith('/original_incline')
        leg = legs[name]
        assert leg['motion'] == 'ORIGINAL_UPRIGHT_TRANSFER'
        variant = int(name.split('/')[0][4:])
        start = np.asarray(nodes[leg['from']]['foot_frame']['translation'])
        end = np.asarray(nodes[leg['to']]['foot_frame']['translation'])
        assert start[0] == end[0] and end[2] < start[2]
        root = np.asarray(units[variant]['bay_frame']['position'])
        assert np.linalg.norm((root - start)[[0, 1]]) < 1e-8
        horizontal, rise = start[2] - end[2], end[1] - start[1]
        profile = leg['ramp_profile']
        flat, run, blend = (profile[k] for k in ('flat_before', 'slope_run', 'blend'))
        mount = mounts[row['mount']]
        ball = np.asarray(mount['ball'])
        section = hardware['rail_head_section' if row['component'] == 'head' else 'rail_web_section']
        x0, y0, x1, y1 = section
        local = np.asarray([[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]])

        def frame(s):
            d = max(0., min(run, s - flat))
            rounded = lambda v: v * .5 - blend / (2 * math.pi) * math.sin(math.pi * v / blend)
            height = (rounded(d) if d < blend else run - blend - rounded(run - d)
                      if d > run - blend else d - blend * .5) * rise / (run - blend)
            scale = ((1 - math.cos(math.pi * d / blend)) * .5 if d < blend else
                     (1 - math.cos(math.pi * (run - d) / blend)) * .5 if d > run - blend else 1.)
            slope = rise * scale / (run - blend)
            q = guide_frame([0., slope, -1.])
            origin = root + [0., height, -s] + BASIS @ ball - q[:, 1] * .35 + [mount['side'] * .65, 7., 0.]
            return origin, q

        values = np.asarray(row['triangles_rgb']).reshape(-1, 6)
        assert len(values) == 36, 'Expected one original complete rail prism'
        xyz = values[:, :3] + row['origin']
        rings = [xyz[[0, 2, 1, 4]], xyz[[6, 7, 8, 11]]]
        distances = []
        for ring in rings:
            centre = ring.mean(0)
            low, high = 0., horizontal
            for _ in range(60):
                mid = (low + high) * .5
                o, q = frame(mid)
                if (local @ q.T + o).mean(0)[2] > centre[2]:
                    low = mid
                else:
                    high = mid
            distances.append((low + high) * .5)
        s0, s1 = distances
        _, q0 = frame(s0)
        _, q1 = frame(s1)
        if np.max(np.abs(q1 - q0)) < 1e-8:
            continue
        assert not row.get('bridge_gate'), 'Original sliding spans are on the flat lead'
        for s, ring in zip(distances, rings):
            o, q = frame(s)
            assert np.max(np.abs(local @ q.T + o - ring)) < .00002, 'Actual endpoint/source ramp differs'
        # |P''| plus the rotated offset bound encloses every section corner.
        acceleration = abs(rise) * math.pi / (2 * blend * (run - blend))
        jerk = abs(rise) * math.pi ** 2 / (2 * blend ** 2 * (run - blend))
        radius = max(abs(y0 - .35), abs(y1 - .35))
        second = acceleration + radius * (jerk + 6 * acceleration * acceleration)
        maximum_step = math.sqrt(8 * .00001 / second)
        count = max(2, math.ceil((s1 - s0) / maximum_step))
        sections = [rings[0]]
        for index in range(1, count):
            o, q = frame(s0 + (s1 - s0) * index / count)
            sections.append(local @ q.T + o)
        sections.append(rings[1])
        refined = np.concatenate([np.concatenate([a, b])[FACES] for a, b in zip(sections, sections[1:])])
        assert np.max(np.maximum(xyz.min(0) - refined.min(0), refined.max(0) - xyz.max(0))) < .001
        colour = values[0, 3:]
        assert np.max(np.abs(values[:, 3:] - colour)) == 0
        row['triangles_rgb'] = np.column_stack([refined - row['origin'], np.tile(colour, (len(refined), 1))]).ravel().tolist()
        changed += 1
        added += (count - 1) * 12
        max_bound = max(max_bound, second * ((s1 - s0) / count) ** 2 / 8)
    assert changed > 0
    result['curve_section_refinement'] = dict(maximum_chord_error_m=.00001,
        retained_original_end_faces=True, retained_sections_and_native_seats=True)
    return result, dict(refined_parts=changed, added_triangles=added, maximum_chord_bound_m=max_bound)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('rails', 'hardware', 'owner', 'directory', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text('utf8'))
    result, summary = refine(read(args.rails), read(args.hardware), read(args.owner), read(args.directory))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(',', ':')), 'utf8')
    print(json.dumps(summary))
