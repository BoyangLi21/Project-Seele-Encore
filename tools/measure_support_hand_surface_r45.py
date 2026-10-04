"""Calibrate the current support hand's real surface against native submissions.

No hand mesh, rig, pose, world, or runtime profile is changed. The result is
contact-authoring data, not an accepted replacement animation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from scipy.spatial import ConvexHull
from eva_hand_rig_math_r45 import controls, matrices
from rebind_anatomical_hand_r45 import dq_pose


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--native', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    assert not args.out.exists()
    contract_path = args.candidate / 'hand_rig_contract.json'
    contract = json.loads(contract_path.read_text('utf8'))
    name = f"eva_unit0{contract['rig']}"
    mesh_path = args.candidate / (name + '_anatomical_hands_r45.mesh.json')
    geo_path = args.candidate / (name + '.geo.json')
    mesh = json.loads(mesh_path.read_text('utf8'))
    geo = json.loads(geo_path.read_text('utf8'))
    predicted = {}
    for side in ('l', 'r'):
        bone = 'hand_' + side
        part, skin = mesh['parts'][bone], mesh['jointSkins'][bone]
        points = (np.array(part['vertices']).reshape(-1, mesh['stride'])[:, :3] + part['pivot']) * [-1, 1, 1] / 16
        names = list(skin['influences'])
        weights = np.array([skin['influences'][n] for n in names]).T
        pose = matrices(geo, contract, side, controls(contract, 'support', side))
        transforms = [pose[n] @ np.array(skin['inverseBindColumnMajor'][n]).reshape(4, 4).T for n in names]
        predicted[side] = dq_pose(points, weights, transforms)
    static = {}
    palette = None
    rows = []
    for line in (args.native / 'hand_vertices.jsonl').open(encoding='utf8'):
        r = json.loads(line)
        if r['kind'] == 'actual_static_part_geometry':
            static[r['resource_part']] = r
        elif r['kind'] == 'final_named_palette':
            palette = r
        elif r['kind'] == 'actual_cpu_submitted_part' and r['bone'] in ('hand_l', 'hand_r'):
            assert palette['frame'] == r['frame']
            assert r['loaded_resource_sha256'] == hashlib.sha256(mesh_path.read_bytes()).hexdigest()
            values = np.array(static[r['resource_part']]['original_part_xyz']).reshape(-1, 3)
            changes = np.array(r['submitted_position_changes_index_xyz']).reshape(-1, 4)
            values[changes[:, 0].astype(int)] = changes[:, 1:]
            values = (values + r['part_pivot_authored']) * [-1, 1, 1] / 16
            side = r['bone'][-1]
            local_error = float(np.abs(values - predicted[side]).max())
            rows.append(dict(tick=r['tick'], side=side, stance=palette['stance'],
                             actual_support_pose_error_body_blocks=local_error))
    assert rows
    maximum = max(r['actual_support_pose_error_body_blocks'] for r in rows)
    hulls = {side: values[ConvexHull(values).vertices].tolist() for side, values in predicted.items()}
    result = dict(scope='Full current DQ support-hand surface, compared with every supplied native hand submission',
                  source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (contract_path, mesh_path, geo_path)},
                  pose='support', units='body_model_blocks_before_render_scale',
                  actual_maximum_local_error=maximum, actual_support_pose_reproduced=maximum < .001,
                  hull_vertices=hulls, rows=rows, native_contact_corrected=False, art_accepted=False)
    args.out.mkdir(parents=True)
    (args.out / 'support_surface.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(dict(samples=len(rows),maximum_local_error=maximum,
                          hull_counts={k: len(v) for k, v in hulls.items()}, matched=maximum < .001)))


if __name__ == '__main__':
    main()
