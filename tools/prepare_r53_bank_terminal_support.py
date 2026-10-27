"""Reconnect terminal rail braces around the existing bank head release stroke.

Retains measured feet, web welds, sections, rail source and original clocks.
Writes a resource candidate only; never edits a world or entity.
"""
import argparse
import copy
import json
import math
from pathlib import Path

import numpy as np
from build_r53_carrier_rear_guides import BASIS, beam


SLIDING = {'capture_structure', 'upper_bearing', 'lower_bearing', 'side_bearing', 'transfer_slider'}


def prepare(source, hardware):
    result = copy.deepcopy(source)
    mounts = {m['id']: m for m in hardware['mounts']}
    changed, retained = [], []
    for route in result['routes']:
        root = np.asarray(route['root_end'])
        for name, mount in mounts.items():
            rows = [p for p in result['pieces'] if p['leg'] == route['leg']
                    and p['mount'] == name and p['name'].endswith('/support')]
            row = max(rows, key=lambda p: int(p['name'].split('/')[-2]))
            xyz = np.asarray(row['triangles_rgb']).reshape(-1, 6)[:, :3] + row['origin']
            assert len(xyz) == 36, 'Expected the original single terminal brace'
            head = root + BASIS @ np.asarray(mount['ball']) + [0, 7 - .35, 0]
            parts = [p for p in hardware['parts'] if p['frame'] == name]
            local = [np.asarray(p['triangles_rgb']).reshape(-1, 6)[:, :3] for p in parts]
            xmin = head[0] - max(v[:, 0].max() for v in local)
            xmax = head[0] - min(v[:, 0].min() for v in local)
            if xyz[:, 0].max() <= xmin or xyz[:, 0].min() >= xmax:
                retained.append(row['name'])
                continue
            start = np.unique(xyz[:6], axis=0).mean(0)
            end = np.unique(xyz[6:12], axis=0).mean(0)
            assert start[1] < end[1] and abs(end[0] - head[0]) > .6
            # The return traversal occupies the same release envelope in
            # reverse. The outer leg stays at the measured foot's X; the
            # cross member goes behind every real stator/captured-head facet.
            rearmost = max(head[2] - v[:, 2].min() + (.65 if p['role'] in SLIDING else 0)
                           for p, v in zip(parts, local))
            back = math.ceil((rearmost + .5 + .06) * 20) / 20
            # The original foot is embedded in the existing equipment wall.
            # Keep its original brace axis until outside that same wall face;
            # subsequent members stay on the equipment side, not inside it.
            exit_x = math.floor(start[0]) - .15 if start[0] > end[0] else math.ceil(start[0]) + .15
            fraction = (exit_x - start[0]) / (end[0] - start[0])
            assert 0 < fraction < 1
            wall_exit = start + (end - start) * fraction
            elbow_a = np.asarray([exit_x, end[1], back])
            elbow_b = np.asarray([end[0], end[1], back])
            row['origin'] = [0, 0, 0]
            row['triangles_rgb'] = (beam(start, wall_exit, .12) + beam(wall_exit, elbow_a, .12)
                                    + beam(elbow_a, elbow_b, .12) + beam(elbow_b, end, .12))
            changed.append(dict(name=row['name'], retained_foot_joint=start.tolist(), retained_web_joint=end.tolist(),
                                retained_wall_exit=wall_exit.tolist(), elbow_a=elbow_a.tolist(),
                                elbow_b=elbow_b.tolist(), section_m=.12))
    assert len(changed) == 3 and len(retained) == 3
    assert all('/rear_l/' in p['name'] for p in changed)
    result['bank_terminal_support_refit'] = dict(version=1, joints=changed,
                                                retained_clear_vertical_braces=retained,
                                                original_head_clock_unchanged=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('source', 'hardware', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    result = prepare(json.loads(args.source.read_text('utf8')), json.loads(args.hardware.read_text('utf8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(',', ':')), encoding='utf8')
    print('Prepared three terminal braces; original feet/webs, three opposite braces and all motion clocks retained.')
