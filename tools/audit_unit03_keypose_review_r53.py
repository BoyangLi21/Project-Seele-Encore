"""Read back native keypose payloads against the previously inspected full surface."""
import argparse
import json
from pathlib import Path
import zipfile
import numpy as np
from scipy.spatial.transform import Rotation
from build_unit03_source_rig_r53 import posed


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser(__doc__)
    for n in ('review', 'candidate', 'client'):
        ap.add_argument('--'+n, type=Path, required=True)
    a = ap.parse_args()
    mesh = read(a.review/'resources/assets/projectseele/mesh/eva_un01.mesh.json')
    body = read(a.review/'runtime/eva_body_r44.json')
    bones = {b['name']: b for b in body['rigs']['4']}
    baseline = np.load(a.candidate/'KEYPOSES.npz')
    result = {}
    for name, rows in read(a.review/'keyposes.json')['poses'].items():
        actual = posed(mesh, bones, {n: Rotation.from_quat(r['rotation_xyzw']).as_matrix() for n, r in rows.items()},
                       {n: np.array(r['position']) for n, r in rows.items()})
        result[name] = {part: float(np.abs(points-baseline[name+'__'+part]).max()) for part, points in actual.items()}
    assert max(max(r.values()) for r in result.values()) < 1e-10
    actual_body = read(a.client/'projectseele-local-maps/eva_body_r44.json')
    preservation = {}
    for field in ('rigs', 'rig_support', 'carrier_hulls', 'eye_positions', 'stance_clips_by_rig', 'locomotion_contract_r43'):
        for key in ('0', '1', '2', '3'):
            preservation[field+'_'+key] = body[field].get(key) == actual_body[field].get(key)
    for field in actual_body.keys()-{'rigs','rig_support','carrier_hulls','eye_positions','stance_clips_by_rig','locomotion_contract_r43','unit03_review_scope_r53'}:
        preservation['body_'+field] = body[field] == actual_body[field]
    physics = read(a.review/'runtime/articulated_bodies_r35.json')
    actual_physics = read(a.client/'projectseele-local-maps/articulated_bodies_r35.json')
    for key in ('0', '1', '2', '3', 'sachiel'):
        preservation['physics_'+key] = physics['models'].get(key) == actual_physics['models'].get(key)
    with zipfile.ZipFile(a.client/'mods/projectseele-0.1.0-all.jar') as z:
        for key in range(3):
            preservation['hand_'+str(key)] = (a.review/f'hands/unit0{key}/hand_rig_contract.json').read_bytes() == z.read(f'assets/projectseele/hand_rigs/unit0{key}/hand_rig_contract.json')
    assert all(preservation.values())
    report = dict(keypose_max_native_error={n: max(r.values()) for n, r in result.items()}, unchanged_other_rigs=preservation,
                  native_visual_not_yet_run=True, gameplay_not_admitted=True,
                  jab_hand_scope='Source-rest hand; bounded fist is a separate unaccepted visual review pose')
    (a.review/'POSE_AND_PRESERVATION_GATES.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
