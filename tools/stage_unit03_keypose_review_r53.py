"""Stage a complete isolated review bundle; never install into a client or save."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import uuid
import zipfile

import numpy as np
from scipy.spatial.transform import Rotation
from build_unit03_source_rig_r53 import decode_frame, hand_pose


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(__doc__)
    for name in ('candidate', 'client', 'out'):
        ap.add_argument('--'+name, required=True, type=Path)
    a = ap.parse_args()
    a.out = a.out.resolve()
    a.out.mkdir(parents=True, exist_ok=False)
    src = a.client/'projectseele-local-maps'
    original = read(src/'combat_bundle_r44.json')
    original_manifest_hash = sha(src/'combat_bundle_r44.json')
    if original['revision'] != 44 or len(original['files']) < 28:
        raise ValueError('Expected complete active combat library, not a partial overlay')
    runtime = a.out/'runtime'
    runtime.mkdir()
    unchanged = {}
    for name, expected in original['files'].items():
        if Path(name).name != name or sha(src/name) != expected:
            raise ValueError('Source runtime identity mismatch: '+name)
        shutil.copyfile(src/name, runtime/name)
        unchanged[name] = expected
    for name in ('eva_body_r44.json', 'eva_gameplay_r44_4.json', 'articulated_bodies_r35.json'):
        shutil.copyfile(a.candidate/'projectseele-local-maps'/name, runtime/name)
        del unchanged[name]
    assets = a.out/'resources/assets/projectseele'
    shutil.copytree(a.candidate/'assets/projectseele', assets)
    shutil.copyfile(a.candidate/'pack.mcmeta', a.out/'resources/pack.mcmeta')
    marker = dict(name='unit03_source_review_r53', parent='root', pivot=[0, 0, 0])
    body = read(src/'eva_body_r44.json')
    candidate_body = read(a.candidate/'projectseele-local-maps/eva_body_r44.json')
    for field in ('rigs', 'rig_support', 'carrier_hulls', 'eye_positions', 'stance_clips_by_rig'):
        body.setdefault(field, {})['4'] = candidate_body[field]['4']
    body['locomotion_contract_r43'].pop('4', None)
    body['unit03_review_scope_r53'] = candidate_body['unit03_review_scope_r53']
    body['rigs']['4'].append(marker)
    bones = body['rigs']['4']
    write(runtime/'eva_body_r44.json', body)
    gameplay = read(runtime/'eva_gameplay_r44_4.json')
    gameplay['rig_contract_r44'] = bones
    write(runtime/'eva_gameplay_r44_4.json', gameplay)
    physics = read(src/'articulated_bodies_r35.json')
    physics['models']['4'] = read(a.candidate/'projectseele-local-maps/articulated_bodies_r35.json')['models']['4']
    physics['models']['4']['render_rig'] = bones
    write(runtime/'articulated_bodies_r35.json', physics)
    geo_path = assets/'geo/eva_un01.geo.json'
    geo = read(geo_path)
    geo['minecraft:geometry'][0]['bones'] = bones
    write(geo_path, geo)
    surface_path = assets/'eva/source_surface_r53.json'
    surface = read(surface_path)
    surface['models']['eva_un01']['resources']['geo'] = sha(geo_path)
    write(surface_path, surface)
    hands = a.out/'hands'
    with zipfile.ZipFile(a.client/'mods/projectseele-0.1.0-all.jar') as jar:
        for key in range(3):
            name = f'assets/projectseele/hand_rigs/unit0{key}/hand_rig_contract.json'
            p = hands/f'unit0{key}/hand_rig_contract.json'
            p.parent.mkdir(parents=True)
            p.write_bytes(jar.read(name))
    hand = read(assets/'hand_rigs/unit04/hand_rig_contract.json')
    write(hands/'unit04/hand_rig_contract.json', hand)
    # Current actual client has no captured locomotion directory. Never insert
    # the old rig4 captured clip into a newly measured skeleton.
    config = (a.client/'config/projectseele-runtime-r45.properties').read_text()
    captured_value = next((line.split('=', 1)[1].strip() for line in config.splitlines()
                           if line.startswith('captured_locomotion_directory=')), '')
    captured = a.out/'captured'
    captured.mkdir()
    if captured_value:
        capture_source = (a.client/captured_value).resolve()
        if not capture_source.is_relative_to(a.client.resolve()):
            raise ValueError('Captured source escaped actual client')
        for key in range(4):
            name = f'eva_locomotion_capture_r44_{key}.json'
            if (capture_source/name).is_file():
                shutil.copyfile(capture_source/name, captured/name)
    selection = read(a.candidate/'NATIVE_KEYPOSE_SELECTION.json')
    cases = {'source_rest': None, 'hand_fist': None, 'hand_open': None}
    cases.update({s['name']: s for s in selection['samples']})
    poses = {}
    for name, selected in cases.items():
        rotations = {}
        positions = {}
        for b in bones:
            angles = np.asarray(b.get('rotation', b.get('bindRotationDegrees', [0, 0, 0])))
            rotations[b['name']] = Rotation.from_euler('xyz', angles*[-1, -1, 1], degrees=True).as_matrix()
        if selected:
            r, positions = decode_frame(selected['frame'], selection['bones'])
            rotations.update(r)
        # The v7 geometry sheet's jab used source-rest hands. Review the bounded
        # fist independently, rather than silently combining two unreviewed poses.
        hand_selection = 'fist' if name == 'hand_fist' else 'open' if name == 'hand_open' else 'relaxed'
        rotations.update(hand_pose(hand, hand_selection))
        poses[name] = {b['name']: dict(rotation_xyzw=Rotation.from_matrix(rotations[b['name']]).as_quat().tolist(),
                                      position=positions.get(b['name'], np.zeros(3)).tolist()) for b in bones}
    write(a.out/'keyposes.json', dict(schema='projectseele.unit03-fixed-keyposes.r53.v1', poses=poses))
    manifest = copy.deepcopy(original)
    manifest['bundle_id'] = 'r53-unit03-isolated-fixed-keypose-review'
    manifest['files'] = {name: sha(runtime/name) for name in original['files']}
    manifest['review_only'] = True
    write(runtime/'combat_bundle_r44.json', manifest)
    with zipfile.ZipFile(a.out/'unit03-review-resources.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted((a.out/'resources').rglob('*')):
            if p.is_file():
                z.write(p, p.relative_to(a.out/'resources').as_posix())
    properties = {
        'projectseele.unit03ReviewDirectoryR53': str(a.out),
        'projectseele.combatBundleDirectory': str(runtime),
        'projectseele.bodyPoseReviewDirectory': str(runtime),
        'projectseele.gameplayReviewDirectory': str(runtime),
        'projectseele.bodyPhysicsProfiles': str(runtime/'articulated_bodies_r35.json'),
        'projectseele.handRigDirectoryR45': str(hands),
        'projectseele.capturedLocomotionDirectory': str(captured),
    }
    files = {p.relative_to(a.out).as_posix(): sha(p) for p in a.out.rglob('*') if p.is_file()}
    world = a.out/'isolated-client/saves/SEELE_R53_UNIT03_SOURCE_REVIEW'
    contract = dict(schema='projectseele.unit03-review-contract.r53.v1', scope='fixed_keyposes_only',
        combat_gameplay_admitted=False, marker='unit03_source_review_r53', rig=4,
        actor_uuid=str(uuid.uuid4()), world=str(world), properties=properties,
        files=files, runtime_names=sorted(original['files']), unchanged_runtime=unchanged,
        poses=sorted(poses), source_manifest_sha256=original_manifest_hash)
    write(a.out/'unit03_review_contract.json', contract)
    (a.out/'REVIEW_JVM_ARGS.txt').write_text('\n'.join('"-D'+k+'='+v+'"' for k, v in properties.items())+'\n', encoding='utf-8')
    assert original_manifest_hash == sha(src/'combat_bundle_r44.json')
    assert all(sha(src/n) == h for n, h in original['files'].items())
    assert all(sha(runtime/n) == h for n, h in unchanged.items())
    write(a.out/'STAGING_RECEIPT.json', dict(installed=False, world_created=False, runtime_files=len(manifest['files']),
        preserved_runtime=len(unchanged), resource_files=len(list(assets.rglob('*'))), poses=list(poses),
        actor_uuid=contract['actor_uuid'], complete_library=True, actual_source_unchanged=True,
        review_contract_sha256=sha(a.out/'unit03_review_contract.json')))
    print(json.dumps(dict(out=str(a.out), runtime_files=len(manifest['files']), poses=list(poses))))


if __name__ == '__main__':
    main()
