"""Continuous paired closure and anatomical arm chains for the existing scene.

Reference direction: TV episode 02, forward engagement, core assault, then
Sachiel's desperate embrace and one final explosion. This is original game
blocking, not official motion capture. Mesh/UV topology and the final cached
enclosure are preserved; a new continuous lead-in removes the hard handoff.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import struct
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as R, Slerp
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from anatomical_hinge_r35 import solve
from author_combat_bundle_r44 import maintain_joint_centres
import author_first_battle_r10 as b
from preview_first_battle_r12 import angel_pose
from bake_envelopment_candidate_r40 import write_hero, rigid_fit
import author_eva_rifle_stances_r06 as surface


def ease(t):
    t = float(np.clip(t, 0, 1))
    return float(np.clip(t*t*t*(10+t*(-15+6*t)), 0, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.runtime/'first_battle_r44.json'
    original_path = args.out/'before_first_battle_r44.json'
    if not original_path.exists():
        original_path.write_bytes(target.read_bytes())
        (args.out/'before_sachiel_wrap_r14.bin').write_bytes((args.runtime/'sachiel_wrap_r14.bin').read_bytes())
    original = json.loads(original_path.read_text(encoding='utf-8'))
    result = copy.deepcopy(original)
    common.BODY = json.loads((args.runtime/'eva_body_r44.json').read_text(encoding='utf-8'))
    common.NAMES = common.BODY['motion']['bones']
    actor = Actor(1)
    names = original['eva']['bones']
    neutral_doc = common.BODY['stance_clips_by_rig']['1']
    neutral = actor.rig.decode(neutral_doc['clips']['idle']['frames'][0], neutral_doc['bones'])
    changed = []
    for i, frame in enumerate(original['eva']['frames']):
        pose = actor.rig.decode(frame, names)
        prior = copy.deepcopy(pose)
        core_weight=ease((i-332)/24)*(1-ease((i-460)/29))
        if core_weight>0:
            cycle=((i-360)/42)%1
            hit=ease(cycle/.50) if cycle<.50 else 1-ease((cycle-.50)/.50)
            supported=actor.pose(lean=-42-5*hit,drop=55,shift=0)
            supported.setp('root',supported.p['root']+[0,0,-45-3*hit])
            feet={s:actor.foot_base[s].copy()for s in ('l','r')}
            actor.solve_feet(supported,feet)
            core=(np.asarray(original['angel']['core_blocks'][i])-np.asarray(original['eva']['root_blocks'][i]))*b.HEROMIRROR/b.UNIT
            shoulder=supported.point('arm_r')
            chamber=shoulder+np.array([7,30,8])
            contact=core+np.array([0,5,8])
            goals={'l':core+np.array([-25,17,7]),'r':chamber*(1-hit)+contact*hit}
            actor.solve_hands(supported,goals)
            for n in names:
                if n.startswith('finger_'):
                    supported.setq(n,prior.q[n])
                pose.setq(n,Slerp([0,1],R.concatenate([prior.q[n],supported.q[n]]))(core_weight))
                pose.setp(n,prior.p[n]*(1-core_weight)+supported.p[n]*core_weight)
            # The planted surface belongs to this current rig, not the old
            # movie's five-metres-high sole guide curves.
            minimum=min(float(surface.vertices(pose,'foot_'+s)[:,1].min())for s in ('l','r'))
            pose.setp('root',pose.p['root']+[0,-minimum*core_weight,0])
        if i>=450:
            # Keep actual planted feet during the embrace. The old wrap body
            # inherited an airborne leg pose while only its mantle was baked.
            actor.solve_feet(pose,{s:actor.foot_base[s].copy()for s in ('l','r')})
            minimum=min(float(surface.vertices(pose,'foot_'+s)[:,1].min())for s in ('l','r'))
            pose.setp('root',pose.p['root']+[0,-minimum,0])
        release = ease((i-558)/90)
        for side, sign in (('l', -1), ('r', 1)):
            shoulder = pose.point('arm_'+side)
            hand = pose.point('hand_'+side)
            original_elbow = pose.point('forearm_'+side, actor.elbows[side])
            direction = hand-shoulder
            direction /= max(np.linalg.norm(direction), 1e-8)
            pole = original_elbow-shoulder
            pole -= direction*(pole@direction)
            if np.linalg.norm(pole) < .1:
                pole = pose.matrix('torso_upper')[:3, :3] @ np.array([sign*.6, 0, -1])
            if release > 0:
                hand = hand*(1-release)+(shoulder+np.array([sign*5.5, -58.5, -1.5]))*release
                pole = pole*(1-release)+np.array([sign*.12, 0, -1])*np.linalg.norm(pole)*release
            palm = R.from_matrix(pose.matrix('hand_'+side)[:3, :3])
            solve(pose, actor.P, 'arm_'+side, 'forearm_'+side, 'hand_'+side,
                  actor.elbows[side], hand, pole, [1, 0, 0], palm)
            if release > 0:
                for n in ('wrist_'+side, 'hand_'+side):
                    pose.setq(n, Slerp([0, 1], R.concatenate([pose.q[n], neutral.q[n]]))(release))
            if i in (0, 150, 210, 320, 440, 488, 489, 558, 600, 690):
                changed.append(dict(frame=i, side=side,
                                    original_hand=prior.point('hand_'+side).tolist(),
                                    final_hand=pose.point('hand_'+side).tolist(),
                                    original_elbow=original_elbow.tolist(),
                                    final_elbow=pose.point('forearm_'+side, actor.elbows[side]).tolist(),
                                    post_explosion_release=release))
        maintain_joint_centres(actor, pose)
        write_hero(original, result, i, pose)
        if i>558:
            settled=np.asarray(original['eva']['root_blocks'][558])
            delta=settled-np.asarray(original['eva']['root_blocks'][i])
            for channel, points in result['eva'].items():
                if channel.endswith('_blocks'):
                    points[i]=(np.asarray(points[i])+delta).tolist()
        result['eva']['frames'][i] = actor.rig.encode(pose, bone_names=names)

    raw = (args.out/'before_sachiel_wrap_r14.bin').read_bytes()
    start, count, fps, unique, full, base = struct.unpack('>6i', raw[4:28])
    if (start, count, fps) != (489, 70, 30):
        raise ValueError('Retain the known source wrapping surface')
    indices = np.frombuffer(raw, dtype='>i4', count=full, offset=60)
    old = np.frombuffer(raw, dtype='>f4', offset=60+full*12).reshape(count, unique, 3).astype(float)
    # The initial cache uses the exact original mesh ordering for its first
    # base vertices. Added subdivision vertices inherit nearby surface deltas.
    angel_mesh = json.loads((b.eva.PACK/'mesh/sachiel.mesh.json').read_text(encoding='utf-8'))
    av = np.asarray(angel_mesh['parts']['root']['vertices']).reshape(-1, 8)
    _, original_inverse = np.unique(np.round(av[:, :3]*[-1, 1, 1], 6), axis=0, return_inverse=True)
    if len(original_inverse) != base:
        raise ValueError('Original angel surface ordering differs')

    def source_surface(index):
        p = angel_pose(original['angel']['frames'][index], original['angel']['bones'])
        points = p.skin()*b.UNIT+np.asarray(original['angel']['root_blocks'][index])
        return points[original_inverse]

    at_start = source_surface(start)
    reference = np.empty_like(old[0])
    reference[:] = old[0]
    reference[indices[:base]] = at_start
    # A barycentric-like local displacement interpolation covers new vertices
    # without snapping added triangles to a different limb or world origin.
    tree = cKDTree(at_start)
    distances, near = tree.query(old[0], k=4)
    weights = 1/np.maximum(distances, .03)**2
    weights /= weights.sum(1, keepdims=True)
    known = np.zeros(unique, bool)
    known[indices[:base]] = True
    reference[~known] = (at_start[near[~known]]*weights[~known, :, None]).sum(1)
    new_start = 450
    initial = source_surface(new_start)
    expanded_initial = reference+((initial[near]-at_start[near])*weights[:, :, None]).sum(1)
    expanded_initial[indices[:base]] = initial
    turn, _ = rigid_fit(expanded_initial, old[0])
    centre = expanded_initial.mean(0)
    end_centre = old[0].mean(0)
    turned = turn.apply(expanded_initial-centre)+end_centre
    residual = old[0]-turned
    rotation = Slerp([0, 1], R.concatenate([R.identity(), turn]))
    landmark_tree = cKDTree(expanded_initial)
    landmarks = {n:int(landmark_tree.query(np.asarray(points[new_start]))[1])
                 for n, points in original['angel'].items()
                 if n.endswith('_blocks') and n != 'root_blocks'}
    lead = []
    for index in range(new_start, start):
        u = ease((index-new_start)/(start-new_start))
        # The legacy weighted skeleton flips its DQS blend near frames 487/488.
        # Use a continuous rigid turn plus gradual soft residual instead of
        # inheriting that discontinuity into the new approach.
        expanded = rotation(u).apply(expanded_initial-centre)+centre*(1-u)+end_centre*u+residual*u
        for name, vertex in landmarks.items():
            result['angel'][name][index] = expanded[vertex].tolist()
        lead.append(expanded)
    positions = np.concatenate([np.asarray(lead), old], axis=0).astype('>f4')
    output = args.runtime/'sachiel_wrap_r14.bin'
    header = raw[:4]+struct.pack('>6i', new_start, len(positions), fps, unique, full, base)+raw[28:60]
    output.write_bytes(header+raw[60:60+full*12]+positions.tobytes())
    result['surface_deformation_r14'] = hashlib.sha256(output.read_bytes()).hexdigest()
    result['r49_paired_contact'] = dict(reference='TV episode 02: grounded core assault, desperate continuous wrap, final explosion only',
            production='original game blocking; anatomical joint chains and same-topology surface continuity',
            wrap_start_frame=new_start, wrap_full_start_frame=start, wrap_end_frame=558,
            pose_after_explosion='arms return continuously to measured neutral, not a reversed attack frame',
            root_teleport_added=False, damage_or_event_clock_changed=False, native_verified=False)
    target.write_text(json.dumps(result, separators=(',', ':')), encoding='utf-8')
    report = dict(changed_arms=changed, cache_before_start=start, cache_after_start=new_start,
                  cache_full_frames=len(positions), original_mesh_UV_preserved=True,
                  max_lead_vertex_step=float(np.linalg.norm(np.diff(positions.astype(float)[:40], axis=0), axis=2).max()),
                  native_verified=False, user_art_accepted=False)
    (args.out/'REPORT.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'changed_arms'}))


if __name__ == '__main__':
    main()
