"""TV-referenced knife draw/stow blocking on the actual NERV rig.

Private authoring candidate. Draw reference: Netflix TV episode 3 clip at
33.4-34.8s, right hand across the left shoulder FRONT. Stow is a game-authored
inverse mechanism, not a claim that the reference shows a complete stow.
No damage, equip state, world, original geometry or release file is modified.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import shutil
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.spatial.transform import Rotation as R, Slerp, RotationSpline
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from author_combat_bundle_r44 import maintain_joint_centres
from anatomical_hinge_r35 import solve
from study_combat_performance_r36 import decode


def ease(x):
    x = np.clip(x, 0, 1)
    return x*x*x*(10+x*(-15+6*x))


def knife_frame(blade):
    y = -np.asarray(blade, float)
    y /= np.linalg.norm(y)
    # The hand's longitudinal direction is approximately -knife Z in this
    # measured grip. +X here bent the wrist backwards even though the handle
    # contact itself remained exact. The presented blade face must use -X.
    x = np.array([-1., 0, 0])
    x -= y*(x@y)
    x /= np.linalg.norm(x)
    return R.from_matrix(np.column_stack((x, y, np.cross(x, y))))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--body', type=Path, required=True)
    p.add_argument('--profiles', type=Path, required=True)
    p.add_argument('--hand', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--in-place', action='store_true', help='Author one rig into the supplied profile directory without copying the library')
    p.add_argument('--ready-centre',type=float,nargs=3,default=[25,111,-30])
    p.add_argument('--ready-pole',type=float,nargs=3,default=[1,0,-.5])
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=a.in_place)
    if a.in_place and a.out.resolve()!=a.profiles.resolve():
        raise ValueError('--in-place requires --out to equal --profiles')
    if not a.in_place:
        for f in a.profiles.glob('*.json'):
            shutil.copy2(f, a.out/f.name)
    body = json.loads(a.body.read_text(encoding='utf8'))
    hand = json.loads((a.hand/'hand_rig_contract.json').read_text(encoding='utf8'))
    common.BODY = body
    common.NAMES = body['motion']['bones']
    actor = Actor(hand['rig'])
    profile_path = next(a.out/f'eva_gameplay_r{rev}_{actor.key}.json'
                        for rev in (44, 43, 42, 32)
                        if (a.out/f'eva_gameplay_r{rev}_{actor.key}.json').is_file())
    profile = json.loads(profile_path.read_text(encoding='utf8'))
    base_doc = body['stance_clips_by_rig'][str(actor.key)]
    reference = base_doc['clips'].get('idle', base_doc['clips'].get('unarmed_stance'))
    if reference is None:
        raise ValueError('Per-unit standing reference is missing')
    base = decode(actor, base_doc, reference['frames'][0])
    maintain_joint_centres(actor, base)
    attachment = hand['knife_attachment_r45']
    grip = np.asarray(attachment['target_handle_centre'])*16
    handle = np.asarray(attachment['source_handle_centre'])*16
    install = R.from_quat(attachment['rotation_xyzw'])
    chest_inverse = np.linalg.inv(base.matrix('torso_upper'))
    start_rotation = R.from_matrix(chest_inverse[:3,:3]@base.matrix('hand_r')[:3, :3])
    start_centre = (chest_inverse@base.matrix('hand_r')@np.r_[grip, 1])[:3]
    rest_direction=base.point('hand_r')-base.point('arm_r')
    rest_direction/=np.linalg.norm(rest_direction)
    rest_pole=base.point('forearm_r',actor.elbows['r'])-base.point('arm_r')
    rest_pole-=rest_direction*(rest_pole@rest_direction)
    rest_pole/=np.linalg.norm(rest_pole)
    # The reference shows the grip presented forward at head height, with
    # blade pointing back into the left pylon, not a vertical overhead draw.
    dock = np.array([-18.8, 178., -34.])
    phases = np.array([0, .18, .27, .34, .42, .54, .62, .74, .87, 1.])
    # Reach around the hand's palmar side before docking. A direct diagonal
    # path intersects the presented handle while the fingers are still open.
    centres = np.array([start_centre, [12,140,-32],[-11,159,-35],
                        dock+[7,0,0],dock,dock,dock+[0,-2,-16],[3,154,-55],[24,125,-42],a.ready_centre])
    dock_rotation = knife_frame([0, 0, 1])*install.inv()
    extracted_rotation = knife_frame([0, .35, .94])*install.inv()
    ready_rotation = knife_frame([0, .94, -.34])*install.inv()
    reach_turn = Slerp([0, 1], R.concatenate([start_rotation, dock_rotation]))
    rotations = R.concatenate([start_rotation,reach_turn(.45),
        reach_turn(.85),
        dock_rotation,dock_rotation,dock_rotation,dock_rotation,extracted_rotation,
        ready_rotation, ready_rotation])
    rotation_curve = RotationSpline(phases, rotations)
    centre_curve = PchipInterpolator(phases, centres)
    rows, frames = [], []
    for t in np.linspace(0, 1, 121):
        pose = copy.deepcopy(base)
        thoracic=float(ease(t/.24)*(1-ease((t-.64)/.36)))
        shoulder_reach=float(ease((t-.05)/.27)*(1-ease((t-.72)/.28)))
        # The chest initiates the cross-body reach. The right shoulder then
        # protracts/elevates while the opposite shoulder counterbalances.
        # The gaze counter-rotates instead of being dragged with the thorax.
        pose.setq('torso_upper',base.q['torso_upper']*R.from_euler('yxz',[.22*thoracic,-.08*thoracic,-.035*thoracic]))
        pose.setq('clavicle_r',base.q['clavicle_r']*R.from_euler('yz',[.20*shoulder_reach,.05*shoulder_reach]))
        pose.setq('clavicle_l',base.q['clavicle_l']*R.from_euler('y',-.05*thoracic))
        pose.setq('arm_l',base.q['arm_l']*R.from_euler('x',-.055*thoracic))
        pose.setq('head',base.q['head']*R.from_euler('yx',[-.18*thoracic,-.045*shoulder_reach]))
        chest = pose.matrix('torso_upper')
        local_orientation=rotation_curve(t)
        dock_weight=float(ease((t-.30)/.04)*(1-ease((t-.62)/.05)))
        if dock_weight>0:
            local_orientation=Slerp([0,1],R.concatenate([local_orientation,dock_rotation]))(dock_weight)
        orientation = R.from_matrix(chest[:3,:3])*local_orientation
        centre = (chest@np.r_[centre_curve(t),1])[:3]
        wrist = centre-orientation.apply(grip-actor.P['hand_r'])
        release=float(ease((t-.70)/.30))
        reach=float(ease(t/.34))
        pole=(rest_pole*(1-reach)+np.array([.3,-1,-.4])*reach)*(1-release)+np.asarray(a.ready_pole)*release
        result = solve(pose, actor.P, 'arm_r', 'forearm_r', 'hand_r',
            actor.elbows['r'], wrist, pole, [1, 0, 0], orientation)
        # During free reach and recovery, the wrist is not a ball joint.
        # Keep the handle trajectory but allow its free orientation to follow
        # the forearm. The docked interval preserves the measured rack frame.
        if t<.34 or t>.70:
            longitudinal=np.asarray(hand['hands']['r']['longitudinal_bind'])
            for _ in range(6):
                forearm=pose.point('hand_r')-pose.point('forearm_r',actor.elbows['r']);forearm/=np.linalg.norm(forearm)
                palm_direction=orientation.apply(longitudinal)
                angle=np.arccos(np.clip(forearm@palm_direction,-1,1))
                if angle<=np.radians(45)+1e-6:break
                axis=np.cross(palm_direction,forearm);axis/=np.linalg.norm(axis)
                orientation=R.from_rotvec(axis*(angle-np.radians(45)))*orientation
                wrist=centre-orientation.apply(grip-actor.P['hand_r'])
                result=solve(pose,actor.P,'arm_r','forearm_r','hand_r',actor.elbows['r'],wrist,pole,[1,0,0],orientation)
        maintain_joint_centres(actor, pose)
        grip_world = (pose.matrix('hand_r')@np.r_[grip, 1])[:3]
        # Until the fingers close, the rack retains the knife. Afterwards
        # its complete transform belongs to the actual hand, without a snap.
        if t < .54 and hand.get('knife_mechanism_r45'):
            present=float(ease((t-.12)/.16))
            stored_pitch=np.radians(hand.get('knife_mechanism_r45',{}).get('carriage_stored_pitch_degrees',0))
            carrier=Slerp([0,1],R.concatenate([knife_frame([0,-np.cos(stored_pitch),-np.sin(stored_pitch)]),knife_frame([0,0,1])]))(present)
            world_rotation = R.from_matrix(chest[:3,:3])*carrier
            stored=np.asarray(hand['knife_mechanism_r45']['bones'][1]['pivot'])*[-1,1,1]
            carrier_centre=stored*(1-present)+dock*present
            carrier_centre[1]+=hand['knife_mechanism_r45'].get('carriage_lift_model',0)*np.sin(np.pi*present)
            world_centre = (chest@np.r_[carrier_centre,1])[:3]
        else:
            world_rotation = R.from_matrix(pose.matrix('hand_r')[:3, :3])*install
            world_centre = grip_world
        local = np.linalg.inv(pose.parent('knife'))
        local_rotation = R.from_matrix(local[:3, :3])*world_rotation
        local_centre = (local@np.r_[world_centre, 1])[:3]
        pivot = actor.P['knife']
        pose.setq('knife', local_rotation)
        pose.setp('knife', local_centre-pivot-local_rotation.apply(handle-pivot))
        frame = actor.rig.encode(pose, (True, True), profile['bones'])
        frame['handling_r45'] = dict(hand_closure=float(ease((t-.42)/.12)),
            knife_visible=bool(t>=.08), rack_owns=bool(t<.54),
            hatch_open=float(ease((t-.04)/.12)*(1-ease((t-.72)/.14))))
        frames.append(frame)
        forearm=pose.point('hand_r')-pose.point('forearm_r',actor.elbows['r']);forearm/=np.linalg.norm(forearm)
        hand_direction=pose.matrix('hand_r')[:3,:3]@np.asarray(hand['hands']['r']['longitudinal_bind'])
        wrist_bend=float(np.degrees(np.arccos(np.clip(forearm@hand_direction,-1,1))))
        rows.append(dict(phase=float(t), target_handle=centre.tolist(),wrist_bend_degrees=wrist_bend,
            thoracic_weight=thoracic,scapular_weight=shoulder_reach,
            actual_shoulder=pose.point('arm_r').tolist(),actual_elbow=pose.point('forearm_r',actor.elbows['r']).tolist(),
            actual_handle=grip_world.tolist(), end_error_model=float(np.linalg.norm(grip_world-centre)),
            elbow_angle=float(result['angle'])))
    for label, samples in [('knife_draw', frames), ('knife_stow', list(reversed(frames)))]:
        profile['clips']['r32_'+label] = dict(duration_seconds=2., frames=samples,
            trajectory_m=[[0,0,0]]*len(samples), step_contacts=[[True,True]]*len(samples),
            stance_locked=True, contact_phase=.54 if label=='knife_draw' else .46,
            support='Standing draw/stow, fixed anatomical joints; private blocking candidate')
    profile['weapon_handling_r45'] = dict(candidate_only=True,
        reference='https://www.youtube.com/watch?v=-olCiqsOXqM',
        inspected_seconds=[33.4,33.7,34.8], stow_original_game_adaptation=True,
        hand_contract_sha256=hashlib.sha256((a.hand/'hand_rig_contract.json').read_bytes()).hexdigest(),
        mechanism_geometry_complete=False, native_passed=False, visual_accepted=False)
    profile_path.write_text(json.dumps(profile,separators=(',',':')),encoding='utf8')
    (a.out/(f'handling_authoring_{actor.key}.json' if a.in_place else 'handling_authoring.json')).write_text(json.dumps(dict(samples=rows,
        maximum_hand_error_model=max(r['end_error_model'] for r in rows),
        reference=profile['weapon_handling_r45']),indent=2),encoding='utf8')
    print('Private draw/stow blocking exported; maximum hand target error:',max(r['end_error_model'] for r in rows))


if __name__ == '__main__':
    main()
