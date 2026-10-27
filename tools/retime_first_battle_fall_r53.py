"""Bake a paired fall tempo candidate and retime its native sound/FX cues.

Works on a private clip only. Original actor/prop correspondence, event
ordering, duration and late sequence are retained. This is an authoring
candidate, not a runtime speed multiplier or a world installer.
"""
import argparse
import copy
import json
import zipfile
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator, CubicHermiteSpline
from scipy.optimize import brentq
from scipy.spatial.transform import Rotation as R, Slerp

from refine_first_battle_contacts_r53 import Pose, sha

# Preparation stays readable; loss of balance accelerates into the fall.
# The airborne follow-through finishes promptly, before the existing strikes.
TIME = np.array([8.55, 9.20, 9.60, 10.18, 10.72, 11.30, 12.75])
SOURCE = np.array([8.55, 9.20, 10., 11., 11.80, 12.10, 12.75])


def sample_linear(values, times):
    values = np.asarray(values)
    frame = np.clip(times*30, 0, len(values)-1)
    a = frame.astype(int)
    b = np.minimum(a+1, len(values)-1)
    w = (frame-a).reshape((-1,)+(1,)*(values.ndim-1))
    return values[a]*(1-w)+values[b]*w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clip', type=Path, required=True)
    ap.add_argument('--jar', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    clip = json.loads(args.clip.read_text('utf8'))
    if clip['fps'] != 30 or clip['duration_ticks'] != 460:
        raise ValueError('Expected the measured 23-second / 30 Hz source')
    args.out.mkdir(parents=True, exist_ok=False)
    result = copy.deepcopy(clip)
    result['fps'] = 60
    time = np.linspace(0, 23, 1381)
    slopes = PchipInterpolator(TIME, SOURCE).derivative()(TIME)
    slopes[0] = slopes[-1] = 1.
    spline = CubicHermiteSpline(TIME, SOURCE, slopes)
    def warp(t):
        return np.where((np.asarray(t) >= TIME[0]) & (np.asarray(t) <= TIME[-1]), spline(t), t)
    source = warp(time)
    before = np.arange(691)/30
    invert = lambda s: brentq(lambda t: float(warp(t))-s, 0, 23) if 0 < s < 23 else s
    with zipfile.ZipFile(args.jar) as archive:
        rigs = {}
        for role, name in [('eva', 'eva_unit01'), ('angel', 'sachiel')]:
            geo = json.loads(archive.read('assets/projectseele/geo/'+name+'.geo.json'))
            rigs[role] = {b['name']: b for b in geo['minecraft:geometry'][0]['bones']}
    for role in rigs:
        data = clip[role]
        names = data['bones']
        rotations = np.array([f['rotation_wxyz'] for f in data['frames']])
        sampled = np.empty((len(time), len(names), 4))
        for j in range(len(names)):
            q = R.from_quat(rotations[:, j, [1, 2, 3, 0]])
            sampled[:, j] = Slerp(before, q)(source).as_quat()[:, [3, 0, 1, 2]]
        root = sample_linear([f['root_m'] for f in data['frames']], source)
        offsets = {n: sample_linear([f.get('bone_position_xyz', {}).get(n, [0, 0, 0])
                                    for f in data['frames']], source) for n in names}
        frames = []
        for i in range(len(time)):
            frame = {'root_m': root[i].tolist(), 'rotation_wxyz': sampled[i].tolist(),
                     'bone_position_xyz': {n: v[i].tolist() for n, v in offsets.items() if np.any(v[i])}}
            # A quaternion interpolation does not linearly interpolate an
            # offset hinge. Rebuild the measured knee/elbow translations.
            pose = Pose(rigs[role], names, frame, role == 'eva')
            frames.append(pose.frame(frame, names))
        result[role]['frames'] = frames
        for name, values in data.items():
            if name.endswith('_blocks'):
                result[role][name] = sample_linear(values, source).tolist()
        if 'socket_outward_blocks' in data and 'socket_up_blocks' in data:
            outward = np.array(result[role]['socket_outward_blocks'])
            outward /= np.linalg.norm(outward, axis=1, keepdims=True)
            up = np.array(result[role]['socket_up_blocks'])
            up -= outward*np.sum(up*outward, axis=1, keepdims=True)
            up /= np.linalg.norm(up, axis=1, keepdims=True)
            result[role]['socket_outward_blocks'] = outward.tolist()
            result[role]['socket_up_blocks'] = up.tolist()
    cuts = clip['camera'].get('cuts', [])
    # Camera cuts remain cuts, never interpolated across their boundary.
    for name in ('position', 'target', 'fov'):
        values = np.asarray(clip['camera'][name])
        sampled = sample_linear(values, source)
        for cut in cuts:
            mask = (source*30 >= cut-1) & (source*30 < cut)
            sampled[mask] = values[cut-1]
        result['camera'][name] = sampled.tolist()
    result['camera']['cuts'] = [round(invert(c/30)*60) for c in cuts]
    cues = [19, 28, 53, 75, 99, 122, 160, 184, 255, 283, 307, 321, 354, 410, 428]
    old_remap = clip.get('event_tick_remap_r42', {})
    remap = {str(c): round(invert(old_remap.get(str(c), c)/20)*20) for c in cues}
    result['event_tick_remap_r42'] = remap
    result['landing_tick'] = round(invert(clip.get('landing_tick', 234)/20)*20)
    result['reference_seconds_r42'] = sample_linear(clip.get('reference_seconds_r42', before), source).tolist()
    result['paired_fall_tempo_r53'] = {
        'source_sha256': sha(args.clip), 'jar_sha256': sha(args.jar),
        'status': 'CANDIDATE_REQUIRES_NATIVE_CONTINUOUS_REVIEW',
        'clock_new_seconds': TIME.tolist(), 'clock_source_seconds': SOURCE.tolist(),
        'method': 'One monotonic paired clock; measured hinge centres; synchronized sound and FX cues',
    }
    target = args.out/'first_battle_r44.json'
    target.write_text(json.dumps(result, separators=(',', ':')), 'utf8')
    report = {'sha256': sha(target), 'event_ticks': remap,
              'landing_tick': result['landing_tick'],
              'max_source_rate': float(np.gradient(source, time).max()),
              'fall_seconds_before': [9.2, 11.8], 'fall_seconds_after': [9.2, float(invert(11.8))]}
    if np.diff(source).min() <= 0 or any(remap[str(c)] != c for c in cues if c >= 255):
        raise ValueError('Retiming changed a late cue or reversed the shared clock')
    (args.out/'tempo-report.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
