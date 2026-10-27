"""Retarget existing grounded performances to the measured UN00 rig; stage only."""
import argparse
import copy
import json
from pathlib import Path

import numpy as np
from build_unit03_source_rig_r53 import donor_basis, retarget_frame, decode_frame, matrix
from stage_unit03_production_r53 import complete_upper_clip


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf8')


def stage(client, output):
    source = client / 'projectseele-local-maps'
    body = read(source / 'eva_body_r44.json')
    destination = read(source / 'eva_gameplay_r44_3.json')
    donor = read(source / 'eva_gameplay_r44_1.json')
    bones = {b['name']: b for b in body['rigs']['3']}
    bases, lengths = donor_basis(body['rigs']['1'], bones)
    # Existing support vertices are the actual UN00 sole hull, not rig1 feet.
    sole_mesh = {'parts': {}}
    for side in ('l', 'r'):
        name = 'foot_' + side
        points = np.asarray(body['rig_support']['3'][name], dtype=float)
        vertices = np.zeros((len(points), 8))
        vertices[:, :3] = points * [-1, 1, 1]
        sole_mesh['parts'][name] = {'pivot': [0, 0, 0], 'vertices': vertices.ravel().tolist()}
    final_names = destination['bones']
    if not set(donor['bones']).issubset(bones):
        raise ValueError('UN00 must contain every donor body channel')
    counts = {}

    def convert(label, clip, names):
        result = copy.deepcopy(clip)
        result['frames'] = []
        for frame in clip['frames']:
            transformed, _ = retarget_frame(frame, names, bases, lengths, bones, sole_mesh)
            for contact in transformed.pop('unit03_contact_review_r53', {}).values():
                if not contact['reachable']:
                    raise ValueError('UN00 sole target unreachable in ' + label)
            channels = dict(zip(names, transformed['rotation_wxyz']))
            transformed['rotation_wxyz'] = [channels.get(n, [1, 0, 0, 0]) for n in final_names]
            result['frames'].append(transformed)
        counts[label] = len(result['frames'])
        print(label, counts[label], flush=True)
        return result

    stance = body['stance_clips_by_rig']['3']
    if stance['bones'] != final_names:
        raise ValueError('UN00 stance and gameplay channel order differs')
    reference = body['stance_clips_by_rig']['1']
    for name in ('idle', 'walk', 'run', 'dash_run'):
        clip = reference['clips'][name]
        if clip.get('r48_upper_body_only'):
            clip = complete_upper_clip(clip, reference['bones'], body['motion']['clips'][name], body['motion']['bones'])
        stance['clips'][name] = convert(name, clip, reference['bones'])
    for name in ('jab', 'cross', 'hook', 'heavy', 'shove', 'stomp', 'guard', 'advance', 'retreat', 'left', 'right'):
        key = 'r32_' + name
        destination['clips'][key] = convert(key, donor['clips'][key], donor['bones'])

    offsets = {}
    for side in ('l', 'r'):
        points = np.asarray(body['rig_support']['3']['foot_' + side]) / 16
        sole = points[points[:, 1] <= np.quantile(points[:, 1], .2)]
        toe = sole[sole[:, 2] <= np.quantile(sole[:, 2], .35)].mean(0)
        pivot = np.asarray(bones['foot_' + side]['pivot']) * [-1, 1, 1] / 16
        offsets[side] = (toe - pivot).tolist()
    contracts = {}
    for name in ('walk', 'run', 'dash_run'):
        clip = stance['clips'][name]
        travel = abs(clip.get('root_travel_m', [0, 0, 0])[-1]) * 35
        if name == 'dash_run':
            travel = body['locomotion_contract_r43']['1'][name]['runtime_stride_blocks_r44']
        if not 1 <= travel <= 200:
            raise ValueError('Missing authored travel distance for ' + name)
        mask = [f.get('foot_contact', [False, False]) for f in clip['frames']]
        curves = {side: [] for side in ('l', 'r')}
        phases = {}
        for frame in clip['frames']:
            rotations, positions = decode_frame(frame, final_names)
            for side in ('l', 'r'):
                part = 'foot_' + side
                pivot = np.asarray(bones[part]['pivot']) * [-1, 1, 1] / 16
                point = pivot + offsets[side]
                curves[side].append((matrix(bones, part, {}, rotations, positions) @ np.r_[point, 1])[:3].tolist())
        for index, side in enumerate(('l', 'r')):
            starts = [i / (len(mask) - 1) for i, value in enumerate(mask) if value[index] and (i == 0 or not mask[i - 1][index])]
            phases[side] = {'forward': starts, 'reverse': [1 - p for p in reversed(starts)]}
        contracts[name] = dict(stride_blocks=travel, runtime_stride_blocks_r44=travel,
                               source_duration_seconds=clip['duration_seconds'], contacts=phases,
                               support_mask_r44=mask, forefoot_curves_r44=curves, forefoot_offsets_r44=offsets)
    body['locomotion_contract_r43']['3'] = contracts
    body['un00_ground_motion_r54'] = {'donor': 1, 'destination': 3, 'surface_unchanged': True}
    destination['support_toes'] = offsets
    destination['un00_ground_motion_r54'] = {'measured_rig': 3, 'grounded_clips': list(counts)}
    write(output / 'eva_body_r44.json', body)
    write(output / 'eva_gameplay_r44_3.json', destination)
    write(output / 'motion_result.json', {'frames': counts, 'source_surface_changed': False, 'installed': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    stage(arguments.client, arguments.out)
