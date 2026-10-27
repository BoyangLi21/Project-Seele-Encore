"""Stage the preserved v7 surface and complete retargeted UN01 runtime; never install."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np
from build_unit03_source_rig_r53 import donor_basis, retarget_frame, decode_frame, matrix
from connect_unit03_dorsal_r53 import connect, same_surface, power_profile

MARKER = 'unit03_source_production_r53'
LOWER = {'root', 'leg_l', 'leg_r', 'shin_l', 'shin_r', 'foot_l', 'foot_r', 'ankle_l', 'ankle_r'}


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf8')


def resource_identity(p):
    # Existing runtime/resource manifests require these identities to load.
    return hashlib.sha256(p.read_bytes()).hexdigest()


def complete_upper_clip(upper, names, base, base_names):
    """The R48 upper-body selection never owns the source walking legs."""
    clip = copy.deepcopy(upper)
    if len(upper['frames']) != len(base['frames']):
        raise ValueError('Upper/body frame clocks differ')
    for out, lower in zip(clip['frames'], base['frames']):
        lower_q = dict(zip(base_names, lower['rotation_wxyz']))
        for i, name in enumerate(names):
            if name in LOWER and name in lower_q:
                out['rotation_wxyz'][i] = lower_q[name]
        out['root_m'] = lower['root_m']
        out['foot_contact'] = lower['foot_contact']
        for name in LOWER - {'root'}:
            out.setdefault('bone_position_xyz', {}).pop(name, None)
            if name in lower.get('bone_position_xyz', {}):
                out['bone_position_xyz'][name] = lower['bone_position_xyz'][name]
    clip.pop('r48_upper_body_only', None)
    if 'root_travel_m' in base:
        clip['root_travel_m'] = base['root_travel_m']
    return clip


def main():
    parser = argparse.ArgumentParser(__doc__)
    for key in ('candidate', 'client', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    a = parser.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    source = a.client / 'projectseele-local-maps'
    runtime = a.out / 'runtime'
    runtime.mkdir()
    manifest = read(source / 'combat_bundle_r44.json')
    for name in manifest['files']:
        if Path(name).name != name:
            raise ValueError('Expected flat complete combat library')
        shutil.copyfile(source / name, runtime / name)
    assets = a.out / 'resources/assets/projectseele'
    shutil.copytree(a.candidate / 'assets/projectseele', assets)
    shutil.copyfile(a.candidate / 'pack.mcmeta', a.out / 'resources/pack.mcmeta')
    body = read(source / 'eva_body_r44.json')
    measured = read(a.candidate / 'projectseele-local-maps/eva_body_r44.json')
    geo = read(assets / 'geo/eva_un01.geo.json')
    mesh = read(assets / 'mesh/eva_un01.mesh.json')
    if mesh['triangleCount'] != 3909 or geo['minecraft:geometry'][0]['bones'] != measured['rigs']['4']:
        raise ValueError('Use the complete v7 source surface and its measured rig')
    bones = {b['name']: b for b in measured['rigs']['4']}
    if any(k not in bones for k in ('r30_elbow_socket_l', 'r30_elbow_socket_r', 'r30_knee_socket_l', 'r30_knee_socket_r')):
        raise ValueError('Measured limb sockets required')
    bones[MARKER] = dict(name=MARKER, parent='root', pivot=[0, 0, 0])
    dorsal, measured['rig_support']['4'], measured['carrier_hulls']['4'] = connect(mesh, bones)
    write(assets / 'mesh/eva_un01.mesh.json', mesh)
    profiles = read(source / 'eva_dorsal_r30.json')
    profiles['profiles']['eva_un01'] = dorsal
    write(runtime / 'eva_dorsal_r30.json', profiles)
    rig = list(bones.values())
    bases, lengths = donor_basis(body['rigs']['1'], bones)
    gameplay = read(source / 'eva_gameplay_r44_1.json')
    common_names = gameplay['bones']
    if not set(body['motion']['bones']).issubset(common_names) or not set(common_names).issubset(bones):
        raise ValueError('The source rig must own every donor action channel')
    sources = {k: (v, body['motion']['bones']) for k, v in body['motion']['clips'].items()}
    for key, value in body['stance_clips_by_rig']['1']['clips'].items():
        if value.get('r48_upper_body_only'):
            value = complete_upper_clip(value, body['stance_clips_by_rig']['1']['bones'],
                                        body['motion']['clips'][key], body['motion']['bones'])
        sources[key] = (value, body['stance_clips_by_rig']['1']['bones'])
    stance_names = set(sources)
    sources.update({k: (v, gameplay['bones']) for k, v in gameplay['clips'].items()})
    counts = {}
    contacts = {}
    retargeted = {}

    def convert(label, clip, names):
        result = copy.deepcopy(clip)
        result['frames'] = []
        worst = 0.0
        active = 0
        for frame in clip['frames']:
            transformed, _ = retarget_frame(frame, names, bases, lengths, bones, mesh)
            for pin in transformed.pop('unit03_contact_review_r53', {}).values():
                if not pin['reachable']:
                    raise ValueError('Unreachable measured leg in ' + label)
                worst = max(worst, abs(pin['sole_error_native']), pin['ankle_error_native'])
                active += 1
            channels = dict(zip(names, transformed['rotation_wxyz']))
            transformed['rotation_wxyz'] = [channels.get(n, [1, 0, 0, 0]) for n in common_names]
            result['frames'].append(transformed)
        counts[label] = len(result['frames'])
        contacts[label] = dict(solved_contacts=active, max_error_native=worst)
        print(label, len(result['frames']), flush=True)
        return result

    for key, (clip, names) in sources.items():
        retargeted[key] = convert(key, clip, names)
    for key in ('rig_support', 'carrier_hulls', 'eye_positions'):
        body.setdefault(key, {})['4'] = measured[key]['4']
    body['rigs']['4'] = rig
    body['stance_clips_by_rig']['4'] = dict(bones=common_names, clips={k: retargeted[k] for k in stance_names})
    body.pop('unit03_review_scope_r53', None)
    body['unit03_source_r53'] = dict(source_rig=1, destination_rig=4, source_surface='rig-v7', complete_actions=True)

    offsets = {}
    for side in ('l', 'r'):
        part = mesh['parts']['foot_' + side]
        points = (np.asarray(part['vertices']).reshape(-1, 8)[:, :3] + part['pivot']) * [-1, 1, 1] / 16
        sole = points[points[:, 1] <= np.quantile(points[:, 1], .2)]
        toe = sole[sole[:, 2] <= np.quantile(sole[:, 2], .35)].mean(0)
        offsets[side] = (toe - np.asarray(bones['foot_' + side]['pivot']) * [-1, 1, 1] / 16).tolist()
    stride = {}
    for key in ('walk', 'run', 'dash_run'):
        clip = retargeted[key]
        travel = abs(clip.get('root_travel_m', [0, 0, 0])[-1]) * 35
        if key == 'dash_run':
            travel = body['locomotion_contract_r43']['1'][key]['runtime_stride_blocks_r44']
        if not 1 <= travel <= 200:
            raise ValueError('Donor locomotion has no usable travel distance: ' + key)
        mask = [f.get('foot_contact', [False, False]) for f in clip['frames']]
        curves = {s: [] for s in ('l', 'r')}
        phases = {}
        for frame in clip['frames']:
            q, p = decode_frame(frame, common_names)
            for side in ('l', 'r'):
                pivot = np.asarray(bones['foot_' + side]['pivot']) * [-1, 1, 1] / 16
                point = pivot + offsets[side]
                curves[side].append((matrix(bones, 'foot_' + side, {}, q, p) @ np.r_[point, 1])[:3].tolist())
        for index, side in enumerate(('l', 'r')):
            begins = [i / (len(mask) - 1) for i, value in enumerate(mask) if value[index] and (i == 0 or not mask[i - 1][index])]
            phases[side] = dict(forward=begins, reverse=[1 - p for p in reversed(begins)])
        stride[key] = dict(stride_blocks=travel, runtime_stride_blocks_r44=travel,
                           source_duration_seconds=clip['duration_seconds'], contacts=phases,
                           support_mask_r44=mask, forefoot_curves_r44=curves, forefoot_offsets_r44=offsets)
    body['locomotion_contract_r43']['4'] = stride
    write(runtime / 'eva_body_r44.json', body)
    gameplay['rig_key'] = 4
    gameplay['rig_contract_r44'] = rig
    gameplay['clips'] = {k: retargeted[k] for k in gameplay['clips']}
    gameplay['support_toes'] = offsets
    gameplay['unit03_source_r53'] = dict(donor=1, source_surface='rig-v7', retargeted=True)
    write(runtime / 'eva_gameplay_r44_4.json', gameplay)
    physics = read(source / 'articulated_bodies_r35.json')
    physical = read(a.candidate / 'projectseele-local-maps/articulated_bodies_r35.json')['models']['4']
    physical['render_rig'] = rig
    recovery = physics['models']['1']['recovery']
    physical['recovery'] = convert('physical_recovery', recovery, recovery['bones'])
    physical['recovery']['bones'] = common_names
    physical.pop('recovery_review_pending', None)
    physics['models']['4'] = physical
    write(runtime / 'articulated_bodies_r35.json', physics)
    geo['minecraft:geometry'][0]['bones'] = rig
    write(assets / 'geo/eva_un01.geo.json', geo)
    surface = read(assets / 'eva/source_surface_r53.json')
    surface['models']['eva_un01']['resources']['geo'] = resource_identity(assets / 'geo/eva_un01.geo.json')
    surface['models']['eva_un01']['resources']['mesh'] = resource_identity(assets / 'mesh/eva_un01.mesh.json')
    surface['models']['eva_un01']['parts'] = len(mesh['parts'])
    with zipfile.ZipFile(a.client / 'mods/projectseele-0.1.0-all.jar') as jar:
        previous = json.loads(jar.read('assets/projectseele/eva/source_surface_r53.json'))
        surface['models'] = {**previous['models'], **surface['models']}
        power = json.loads(jar.read('assets/projectseele/motion/eva_power_ports_r48.json'))
        power['profiles']['4'] = power_profile(mesh)
        write(assets / 'motion/eva_power_ports_r48.json', power)
    write(assets / 'eva/source_surface_r53.json', surface)
    with zipfile.ZipFile(a.client / 'mods/projectseele-0.1.0-all.jar') as jar:
        for key in range(3):
            target = a.out / f'hands/unit0{key}/hand_rig_contract.json'
            target.parent.mkdir(parents=True)
            target.write_bytes(jar.read(f'assets/projectseele/hand_rigs/unit0{key}/hand_rig_contract.json'))
    target = a.out / 'hands/unit04/hand_rig_contract.json'
    target.parent.mkdir(parents=True)
    shutil.copyfile(assets / 'hand_rigs/unit04/hand_rig_contract.json', target)
    # The actual client currently uses ordinary motion. A future captured rig4
    # must retain the existing exact-rig check; old UN01 captures are not copied.
    manifest['bundle_id'] = 'r53-unit03-source-production-candidate'
    manifest['files'] = {name: resource_identity(runtime / name) for name in manifest['files']}
    write(runtime / 'combat_bundle_r44.json', manifest)
    with zipfile.ZipFile(a.out / 'unit03-source-resources.zip', 'w', zipfile.ZIP_DEFLATED) as pack:
        for p in sorted((a.out / 'resources').rglob('*')):
            if p.is_file():
                pack.write(p, p.relative_to(a.out / 'resources').as_posix())
    # One finite readback checks real channel/rig compatibility and unchanged surfaces.
    output_mesh = read(assets / 'mesh/eva_un01.mesh.json')
    assert same_surface(read(a.candidate / 'assets/projectseele/mesh/eva_un01.mesh.json'), output_mesh)
    assert read(runtime / 'eva_gameplay_r44_4.json')['rig_contract_r44'] == read(assets / 'geo/eva_un01.geo.json')['minecraft:geometry'][0]['bones']
    write(a.out / 'CONNECTION_RESULT.json', dict(surface_faces=output_mesh['triangleCount'],
          rig_bones=len(rig), stance_clips=len(stance_names), gameplay_clips=len(gameplay['clips']),
          frame_counts=counts, foot_contacts=contacts, world_written=False, installed=False))
    properties = {'projectseele.combatBundleDirectory': runtime, 'projectseele.bodyPoseReviewDirectory': runtime,
                  'projectseele.gameplayReviewDirectory': runtime, 'projectseele.bodyPhysicsProfiles': runtime / 'articulated_bodies_r35.json',
                  'projectseele.dorsalPoseReview': runtime / 'eva_dorsal_r30.json',
                  'projectseele.handRigDirectoryR45': a.out / 'hands'}
    (a.out / 'JVM_ARGS.txt').write_text('\n'.join(f'-D{k}={v.resolve().as_posix()}' for k, v in properties.items()) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
