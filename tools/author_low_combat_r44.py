"""Constrain the signed source performance to the five actual low stances.

This is an adaptation of the recorded standing performances, not a claim of
separate crouching/prone mocap. The support hand and bearing legs belong to the
low stance; the attacking chain follows the same source phase and hinge plane.
Never writes the source or a running bundle.
"""
from pathlib import Path
import argparse,copy,hashlib,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from study_combat_performance_r36 import decode
from author_combat_bundle_r44 import arm,maintain_joint_centres
from rebuild_stance_hinges_r41 import reconstruct,reachable_root

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/combat'
LABELS=('jab','cross','hook','heavy','knife_forward','knife_reverse')


def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def smooth(t):
    t=np.clip(t,0,1);return t*t*t*(10+t*(-15+6*t))


def rotmix(a,b,w):return Slerp([0,1],R.concatenate([a,b]))([np.clip(w,0,1)])[0]


def floor(pose,support):
    return min(float((np.asarray(points)@pose.matrix(name)[1,:3]+pose.matrix(name)[1,3]).min())
               for name,points in support.items() if name in pose.q)


def rectify_low_stances(actor,document,support):
    """Keep actual foot endpoints; select the knee branch above the floor.

    The old prone endpoints kept feet at zero while both knees bent below the
    plane. Raising the entire body would create a floating chest and feet.
    """
    reports=[]
    for label in ('unarmed_stance','rifle_stance'):
        clip=document['clips'][label];frames=[];minimum=1e9;maximum_displacement=0.
        for i,frame in enumerate(clip['frames']):
            pose=decode(actor,document,frame);before=pose.p['root'].copy()
            for side in ('l','r'):
                upper='leg_'+side;end='foot_'+side;goal=pose.point(end).copy();orientation=R.from_matrix(pose.matrix(end)[:3,:3])
                reconstruct(actor,pose,side,goal,orientation,pose.q[upper])
                hip=pose.point(upper);line=goal-hip;line/=max(np.linalg.norm(line),1e-9)
                knee=(pose.matrix(upper)@np.r_[actor.knees[side],1])[:3]
                bend=knee-hip-line*((knee-hip)@line)
                # A vertical leg uses the original forward bend. As it becomes
                # horizontal the supporting knee must point above the plane.
                up=np.array([0.,1.,0.]);up-=line*(up@line)
                front=np.array([0.,0.,-1.]);front-=line*(front@line)
                weight=smooth((i/(len(clip['frames'])-1)-1/3)/(2/3))
                desired=up*weight+front*(1-weight)
                if np.linalg.norm(bend)>1e-8 and np.linalg.norm(desired)>1e-8:
                    bend/=np.linalg.norm(bend);desired/=np.linalg.norm(desired)
                    angle=np.arctan2(line@np.cross(bend,desired),np.clip(bend@desired,-1,1))
                    authored=R.from_rotvec(line*angle)*R.from_matrix(pose.matrix(upper)[:3,:3])
                    local=R.from_matrix(pose.parent(upper)[:3,:3]).inv()*authored
                    reconstruct(actor,pose,side,goal,orientation,local)
            maintain_joint_centres(actor,pose);minimum=min(minimum,floor(pose,support));maximum_displacement=max(maximum_displacement,float(np.linalg.norm(pose.p['root']-before)))
            frames.append(actor.rig.encode(pose,tuple(frame.get('foot_contact',[True,True])),document['bones']))
        document['clips'][label]={**clip,'frames':frames}
        reports.append(dict(clip=label,minimum_body_floor_model_units=minimum,maximum_root_displacement_model_units=maximum_displacement))
    return reports


def constrained(actor,profile,stance_document,label,stance,support):
    source=profile['clips']['r32_'+label];base=decode(actor,stance_document,stance_document['clips']['unarmed_stance']['frames'][60 if stance=='crouch' else 180])
    reference=decode(actor,profile,source['frames'][0]);leading=source['leading_side'];bearing='r' if leading=='l' else 'l'
    foot_goals={s:base.point('foot_'+s).copy() for s in ('l','r')}
    foot_rotations={s:R.from_matrix(base.matrix('foot_'+s)[:3,:3]) for s in ('l','r')}
    output=[];max_arm=0.;max_foot=0.;min_floor=1e9;max_root=0.;support_slip=0.
    for i,frame in enumerate(source['frames']):
        captured=decode(actor,profile,frame);pose=copy.deepcopy(base);t=i/(len(source['frames'])-1)
        envelope=smooth(t/.16)*(1-smooth((t-.88)/.12))
        # Keep the low-stance pelvis/legs. Trunk articulation is the captured
        # change relative to its neutral frame, constrained by the bearing pose.
        for name in ('torso_lower','torso_upper','head'):
            delta=reference.q[name].inv()*captured.q[name]
            amount=(.30 if stance=='crouch' else .10)*envelope
            pose.setq(name,base.q[name]*rotmix(R.identity(),delta,amount))
        pelvis=(captured.point('leg_l')+captured.point('leg_r')-reference.point('leg_l')-reference.point('leg_r'))*.5
        pose.setp('root',base.p['root']+pelvis*np.array([.10,.05,.10])*envelope)
        reachable_root(actor,pose,foot_goals)
        for side in ('l','r'):
            max_foot=max(max_foot,reconstruct(actor,pose,side,foot_goals[side],foot_rotations[side],base.q['leg_'+side]))
        sides=(leading,) if stance=='prone' else ('l','r')
        for side in sides:
            upper='arm_'+side;hand='hand_'+side
            relative=captured.point(hand)-captured.point(upper)
            relative[1]*=.42 if stance=='crouch' else .20
            goal=base.point(hand)*(1-envelope)+(pose.point(upper)+relative)*envelope
            original=R.from_matrix(base.matrix(upper)[:3,:3]);authored=R.from_matrix(captured.matrix(upper)[:3,:3])
            world=rotmix(original,authored,envelope)
            orientation=rotmix(R.from_matrix(base.matrix(hand)[:3,:3]),R.from_matrix(captured.matrix(hand)[:3,:3]),envelope)
            # The analytic chain terminates at the hand pivot. A second wrist
            # rotation about a displaced pivot changes the chain length, so
            # absorb its world orientation into the solved hand instead.
            pose.setq('wrist_'+side,R.identity())
            max_arm=max(max_arm,arm(actor,pose,side,goal,orientation,world))
            # Source finger axes and opposed thumb are complete for this rig.
            for name in pose.q:
                if name.startswith('finger_') and name.endswith('_'+side):
                    pose.setq(name,rotmix(base.q[name],captured.q[name],envelope))
        if stance=='prone':
            # A ground-bearing palm stays open and at the stance's world point.
            # Resolve it after the captured torso change, never copy a standing
            # guard over this support surface.
            hand='hand_'+bearing;upper='arm_'+bearing
            pose.setq('wrist_'+bearing,R.identity())
            max_arm=max(max_arm,arm(actor,pose,bearing,base.point(hand),R.from_matrix(base.matrix(hand)[:3,:3]),R.from_matrix(base.matrix(upper)[:3,:3])))
            support_slip=max(support_slip,float(np.linalg.norm(pose.point(hand)-base.point(hand))))
        if label.startswith('knife_'):
            pose.setq('knife',captured.q['knife']);pose.setp('knife',captured.p['knife'])
        maintain_joint_centres(actor,pose)
        # The grounded body includes the prone chest; a rigid-foot-only lift
        # would bury it. This tiny correction is recorded, never hidden.
        lowest=floor(pose,support);pose.setp('root',pose.p['root']+[0,-lowest,0])
        min_floor=min(min_floor,floor(pose,support));max_root=max(max_root,float(np.linalg.norm(pose.p['root']-base.p['root'])))
        output.append(actor.rig.encode(pose,(True,True),profile['bones']))
    result=copy.deepcopy(source);result.update(frames=output,trajectory_m=[[0,0,0]]*len(output),
        step_contacts=[[True,True]]*len(output),stance_locked=True,
        support_bones_r44=['foot_l','foot_r'] if stance=='crouch' else ['torso_lower','torso_upper','foot_l','foot_r','hand_'+bearing],
        adaptation_r44=dict(source_clip='r32_'+label,source_stance='unarmed_stance',stance=stance,
            method='Recorded source phase/anatomical arm frame into actual low stance; fixed legs and independent prone bearing palm; full fingers and opposed thumb',
            separate_low_mocap=False))
    if 'contact_bone' not in result:
        name='hand_'+leading;result['contact_bone']=name
        result['contact_point_model']=((actor.P[name]+(actor.P['finger_middle_'+leading]-actor.P[name])*.55)*[-1,1,1]).tolist()
    report=dict(clip=stance+'_'+label,frames=len(output),maximum_arm_target_error_model_units=max_arm,
                maximum_foot_target_error_model_units=max_foot,minimum_body_floor_model_units=min_floor,
                maximum_root_adjustment_model_units=max_root,bearing_hand_pivot_error_model_units=support_slip)
    return result,report


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ART/'locomotion_warp/motion');ap.add_argument('--output',type=Path,default=ART/'low_attack_bundle/motion');args=ap.parse_args()
    if args.source.resolve()==args.output.resolve():raise ValueError('Source and candidate must differ')
    if (args.output/'combat_bundle_r44.json').exists():raise ValueError('An existing signed candidate is frozen; choose a new output directory')
    args.output.mkdir(parents=True,exist_ok=True);manifest=json.loads((args.source/'combat_bundle_r44.json').read_text('utf8'));reports=[]
    for name in manifest['files']:shutil.copy2(args.source/name,args.output/name)
    body=json.loads((args.source/'eva_body_r44.json').read_text('utf8'));common.BODY=body
    stance_reports=[]
    for key in range(5):
        actor=Actor(key);file=args.source/f'eva_gameplay_r44_{key}.json';profile=json.loads(file.read_text('utf8'));candidate=copy.deepcopy(profile)
        support=body.get('rig_support',{}).get(str(key),body['support'])
        repaired=rectify_low_stances(actor,body['stance_clips_by_rig'][str(key)],support)
        stance_reports.extend(dict(rig=key,**report) for report in repaired)
        for stance in ('crouch','prone'):
            for label in LABELS:
                clip,report=constrained(actor,profile,body['stance_clips_by_rig'][str(key)],label,stance,support)
                candidate['clips']['r32_'+stance+'_'+label]=clip;reports.append(dict(rig=key,**report))
                candidate['sources'][stance+'_'+label]=dict(performance=profile['sources'].get(label,profile.get('r44_provenance',{})),
                    body_sha256=sha(args.source/'eva_body_r44.json'),stance='R43 actual rig-specific unarmed stance',
                    adaptation='Constrained low-stance adaptation; no separate low-attack capture claimed')
        candidate['low_attack_revision_r44']=1
        (args.output/file.name).write_text(json.dumps(candidate,ensure_ascii=False,separators=(',',':')),'utf8')
        print('Authored constrained low actions:',key,flush=True)
    body['r44_low_attack_contract']=dict(revision=1,reference_body_sha256=sha(args.source/'eva_body_r44.json'),
        source_performance_bundle=manifest['bundle_id'],status='Candidate: mathematical read-back, actual low-input/network/mesh review still required')
    (args.output/'eva_body_r44.json').write_text(json.dumps(body,ensure_ascii=False,separators=(',',':')),'utf8')
    files={name:sha(args.output/name) for name in manifest['files']};identity=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    manifest.update(bundle_id='R44-'+identity[:16],files=files);(args.output/'combat_bundle_r44.json').write_text(json.dumps(manifest,indent=2),'utf8')
    report=dict(bundle=manifest['bundle_id'],source_bundle=json.loads((args.source/'combat_bundle_r44.json').read_text('utf8'))['bundle_id'],reports=reports,stance_repairs=stance_reports,
        scope='Source-backed constrained low-stance adaptation. Not separate low mocap, real inputs, final GPU pixels, or artistic acceptance.')
    (args.output.parent/'low_attack_authoring.json').write_text(json.dumps(report,indent=2),'utf8');print('Signed isolated low bundle:',manifest['bundle_id'],flush=True)


if __name__=='__main__':main()
