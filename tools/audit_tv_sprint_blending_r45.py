"""Measure the isolated sprint supplement against unchanged run world joints.

This is a double-precision, pre-terrain FK comparison, not native gameplay or
mesh acceptance. It includes between-key samples and normal-run transitions.
"""
from pathlib import Path
import argparse, json, hashlib
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_captured_arm_support_r45 import Pose


def blend(doc, a, b, weight):
    result = Pose(doc, a)
    other = Pose(doc, b)
    for name in result.rig:
        delta = result.rot[name].inv() * other.rot[name]
        result.rot[name] = result.rot[name] * R.from_rotvec(delta.as_rotvec() * weight)
        result.pos[name] = result.pos[name] * (1-weight) + other.pos[name] * weight
    result.cache.clear()
    return result


def encode(doc, pose):
    rotations = []
    for name in doc['bones']:
        x, y, z, w = pose.rot[name].as_quat()
        rotations.append([w, -x, -y, z])
    return dict(rotation_wxyz=rotations,
                root_m=(pose.pos['root'] * [-1, 1, 1] / 7).tolist(),
                bone_position_xyz={name: (v * [-1, 1, 1] * 16).tolist()
                                   for name, v in pose.pos.items() if name != 'root'})


def main():
    parser = argparse.ArgumentParser()
    for name in ('body', 'supplements', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    body = json.loads(args.body.read_text('utf8'))
    results = []
    for rig in range(3):
        source = body['stance_clips_by_rig'][str(rig)]
        path = args.supplements / f'eva_tv_sprint_supplement_{rig}.json'
        supplement = json.loads(path.read_text('utf8'))
        doc = dict(bones=source['bones'], rig_contract_r44=body['rigs'][str(rig)])
        run, sprint = source['clips']['run'], supplement['clips']['tv_sprint']
        assert run['duration_seconds'] == sprint['duration_seconds']
        assert len(run['frames']) == len(sprint['frames'])
        worst, samples = {}, 0
        for index in range(len(run['frames'])-1):
            for fraction in (0, .25, .5, .75, 1):
                original = blend(doc, run['frames'][index], run['frames'][index+1], fraction)
                fast = blend(doc, sprint['frames'][index], sprint['frames'][index+1], fraction)
                for weight in (0, .25, .5, .75, 1):
                    mixed = blend(doc, encode(doc, original), encode(doc, fast), weight)
                    samples += 1
                    for side in ('l', 'r'):
                        for part in ('leg_', 'shin_', 'foot_'):
                            name = part+side
                            error = float(np.linalg.norm(mixed.point(name)-original.point(name)))
                            if name not in worst or error > worst[name]['body_blocks']:
                                worst[name] = dict(body_blocks=error, render_blocks=error*5,
                                                   frame=index, fraction=fraction, blend=weight)
        results.append(dict(rig=rig, samples=samples, worst_joint_displacement=worst,
                            supplement_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    result = dict(scope='FK local slerp/linear translation before runtime contact correction',
                  actual_gameplay=False, mesh_surface_verified=False, art_accepted=False,
                  rigs=results, production_changed=False)
    args.out.write_text(json.dumps(result, indent=2), 'utf8')
    print(json.dumps([dict(rig=r['rig'], samples=r['samples'],
                           worst_render_blocks=max(x['render_blocks'] for x in r['worst_joint_displacement'].values()))
                      for r in results]))


if __name__ == '__main__':
    main()
