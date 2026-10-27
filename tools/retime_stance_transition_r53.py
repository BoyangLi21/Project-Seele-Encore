"""Redistribute standing/crouching pose changes without changing their path.

Only the six original EVA stance clips are retimed. The same monotone clock is
used across all three rigs and both weapon states, preserving the standing,
crouching and prone endpoints. This emits a candidate, never installs it.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d


def quaternions(frames):
    q = np.asarray([f['rotation_wxyz'] for f in frames], dtype=float)
    return q / np.linalg.norm(q, axis=2, keepdims=True)


def angle(a, b):
    dot = np.abs(np.sum(a * b, axis=-1))
    return np.degrees(2 * np.arccos(np.clip(dot, 0, 1)))


def slerp(a, b, t):
    dot = np.sum(a * b, axis=-1, keepdims=True)
    b = np.where(dot < 0, -b, b)
    theta = np.arccos(np.clip(np.abs(dot), 0, 1))
    sine = np.sin(theta)
    curved = (np.sin((1 - t) * theta) * a + np.sin(t * theta) * b) / np.maximum(sine, 1e-12)
    out = np.where(sine > 1e-6, curved, (1 - t) * a + t * b)
    return out / np.linalg.norm(out, axis=-1, keepdims=True)


def sample(frames, q, position):
    if abs(position-round(position)) < 1e-10:
        return copy.deepcopy(frames[round(position)])
    lo = min(int(position), len(frames) - 1)
    hi = min(lo + 1, len(frames) - 1)
    t = position - lo
    if t < 1e-10:
        return copy.deepcopy(frames[lo])
    a, b = frames[lo], frames[hi]
    assert set(a) == set(b) == {'root_m', 'rotation_wxyz', 'foot_contact', 'bone_position_xyz'}
    assert a['foot_contact'] == b['foot_contact'], 'A contact event requires an explicit time mapping'
    out = copy.deepcopy(a)
    out['rotation_wxyz'] = slerp(q[lo], q[hi], t).tolist()
    out['root_m'] = ((1 - t) * np.asarray(a['root_m']) + t * np.asarray(b['root_m'])).tolist()
    out['bone_position_xyz'] = {
        n: ((1-t)*np.asarray(a['bone_position_xyz'].get(n,[0,0,0]))+t*np.asarray(b['bone_position_xyz'].get(n,[0,0,0]))).tolist()
        for n in sorted(set(a['bone_position_xyz']) | set(b['bone_position_xyz']))
    }
    return out


def endpoint_ease(t, width=.1):
    if t < width:
        u = t / width
        return width * (2*u*u-u*u*u)
    if t > 1-width:
        return 1-endpoint_ease(1-t, width)
    return t


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert args.body.resolve() != args.output.resolve()
    source = args.body.read_bytes()
    body = json.loads(source)
    selected = []
    for variant in ('0', '1', '2'):
        profile = body['stance_clips_by_rig'][variant]
        for name in ('unarmed_stance', 'rifle_stance'):
            clip = profile['clips'][name]
            assert len(clip['frames']) == 181 and not clip['loop']
            q = quaternions(clip['frames'])
            selected.append((variant, name, clip, q))
    # Use one clock so switching weapon or rig cannot shift the transition.
    effort = np.maximum.reduce([angle(q[1:61], q[:60]).max(1) for _, _, _, q in selected])
    density = gaussian_filter1d(effort, 2, mode='nearest') + effort.mean() * .25
    cumulative = np.r_[0, np.cumsum(density)]
    cumulative /= cumulative[-1]
    inverse = PchipInterpolator(cumulative, np.arange(61)/60)
    phases = np.array([float(inverse(endpoint_ease(i/60))) if i <= 60 else i/60 for i in range(181)])
    phases[0], phases[60], phases[120], phases[180] = 0, 1, 2, 3
    assert np.all(np.diff(phases) > 0)
    reports = []
    for variant, name, clip, q in selected:
        original = clip['frames']
        result = [sample(original, q, p*60) for p in phases]
        for i, j in ((0, 0), (60, 60), (120, 120), (180, 180)):
            assert result[i] == original[j]
        # Outside the standing/crouching interval every original key is exact.
        for i in range(60, 181):
            assert result[i] == original[i]
        after = quaternions(result)
        names = body['stance_clips_by_rig'][variant]['bones']
        measurements = {}
        for joint in ('leg_l', 'leg_r', 'shin_l', 'shin_r', 'torso_lower', 'root'):
            j = names.index(joint)
            measurements[joint] = {
                'before_degrees_per_stance_unit': float(angle(q[1:61,j], q[:60,j]).max()*60),
                'candidate_degrees_per_stance_unit': float(angle(after[1:61,j], after[:60,j]).max()*60),
            }
        clip['frames'] = result
        reports.append(dict(variant=variant, clip=name, joints=measurements))
    receipt = dict(schema='projectseele.r53.stance-timing.v1', source_sha256=hashlib.sha256(source).hexdigest(),
                   original_path_preserved=True, changed_interval=[0,1],
                   server_stance_speed_changed=False, endpoint_frames_preserved=[0,1,2,3],
                   source_stance_at_uniform_candidate_frames=phases.tolist(), measurements=reports)
    body['r53_stance_timing'] = {k:v for k,v in receipt.items() if k!='measurements'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(body, separators=(',',':')), encoding='utf-8')
    receipt['candidate_sha256'] = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix('.TIMING.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(dict(source=receipt['source_sha256'], candidate=receipt['candidate_sha256'],measurements=reports)))


if __name__ == '__main__':
    main()
