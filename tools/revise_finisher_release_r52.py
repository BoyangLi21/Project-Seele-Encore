"""Release the obsolete wrist pressure, then recover the near hand to guard."""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
from r52_motion_core import selected,read,UNIT,MIRROR,ease,hand_controls,hand_carry
from author_finisher_r52 import world
from calibrated_arm_r52 import solve
from revise_finisher_body_r52 import preserve_hinges,rotation_mix
from bake_finisher_r52 import anchors,sole_point


def arm(rig,p,root,goal,orientation,previous):
    origin=previous.point('arm_l');direction=previous.point('hand_l')-origin;direction/=np.linalg.norm(direction)
    elbow=previous.point('arm_l',rig.elbows['l'])-origin;normal=np.cross(direction,elbow);normal/=np.linalg.norm(normal)
    p.r52_elbow_normals={'l':normal};p.r52_elbow_directions={'l':direction}
    p.setq('arm_l',previous.q['arm_l']);p.setq('forearm_l',previous.q['forearm_l'])
    mirror=np.ones(3) if rig.angel else MIRROR
    result=solve(p,rig.P,'arm_l','forearm_l','hand_l',rig.elbows['l'],(goal-root)*mirror/UNIT,
                 [-.8,-.45,-.35],[1,0,0],orientation)
    preserve_hinges(p);p.setq('hand_l',R.from_matrix(p.parent('hand_l')[:3,:3]).inv()*orientation)
    return result


parser=argparse.ArgumentParser(description=__doc__)
for name in ('body','assets','angel-rig','source','out'):
    parser.add_argument('--'+name,type=Path,required=True)
parser.add_argument('--revision',choices=['release1','release2','release3','release4','release5'],default='release1')
parser.add_argument('--leave-angel-source',action='store_true')
args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True);output=args.out/f'first_battle_r52_body3_{args.revision}.json';assert not output.exists()
_,hero,angel=selected(args.body,args.assets,args.angel_rig);old=read(args.source);candidate=copy.deepcopy(old)
baseline=anchors(old,hero);rows=[]
previous={role:rig.decode(old[role]['frames'][540],old[role]['bones']) for role,rig in [('eva',hero),('angel',angel)]}
end_a=angel.decode(old['angel']['frames'][750],old['angel']['bones'])
end_a_rotation=R.from_matrix(end_a.matrix('hand_l')[:3,:3])
guard_reference=hero.decode(old['eva']['frames'][792],old['eva']['bones'])
for index in range(540,750):
    t=index/60;h=hero.decode(old['eva']['frames'][index],old['eva']['bones']);a=angel.decode(old['angel']['frames'][index],old['angel']['bones'])
    hr=np.array(old['eva']['root_blocks'][index]);ar=np.array(old['angel']['root_blocks'][index])
    opening=ease((t-9)/.20);depart=ease((t-9.18)/.60);return_source=1-ease((t-12.05)/.45)
    recovery=ease((t-9.70)/.60);amount=depart*return_source
    source_hand_rotation=R.from_matrix(h.matrix('hand_l')[:3,:3])
    finger_target=copy.deepcopy(h);hand_controls(finger_target,'open','relaxed')
    relaxed=copy.deepcopy(h);hand_controls(relaxed,'relaxed','relaxed')
    for name in h.q:
        if name.startswith('r45_hand_l_'):
            opened=rotation_mix(h.q[name],finger_target.q[name],opening)
            final=rotation_mix(opened,relaxed.q[name],recovery)
            h.setq(name,rotation_mix(h.q[name],final,return_source))
    old_goal=world(h,hr,'hand_l');shoulder=world(h,hr,'arm_l')
    # Palm leaves the surface first; the elbow then folds toward a low guard.
    withdraw=old_goal+np.array([0,0,-8]) if args.revision=='release3' else old_goal+np.array([-3,3,-5])
    guard=shoulder+np.array([4,5,-9]) if args.revision=='release3' else shoulder+np.array([7,-7,-1])
    destination=withdraw*(1-recovery)+guard*recovery
    goal=old_goal*(1-amount)+destination*amount
    if args.revision in ('release4','release5'):
        wrist_departure=ease((t-9.18)/.87)*return_source
        weights=[('arm_l',wrist_departure),('forearm_l',recovery*return_source),('hand_l',wrist_departure)] if args.revision=='release5' else [('arm_l',recovery*return_source),('forearm_l',wrist_departure),('hand_l',wrist_departure)]
        for name,weight in weights:
            h.setq(name,rotation_mix(h.q[name],guard_reference.q[name],weight))
        preserve_hinges(h)
        h_result=dict(source_guard_frame=792,local_shoulder_blend=recovery*return_source,local_elbow_wrist_blend=wrist_departure,solver='Direct existing anatomical guard joint parameters; no IK branch selection')
    else:
        h_result=arm(hero,h,hr,goal,source_hand_rotation,previous['eva'])
        carry=copy.deepcopy(h);hand_carry(carry,('l',))
        carry_weight=(depart if args.revision=='release3' else recovery)*return_source
        desired=rotation_mix(source_hand_rotation,R.from_matrix(carry.matrix('hand_l')[:3,:3]),carry_weight)
        h.setq('hand_l',R.from_matrix(h.parent('hand_l')[:3,:3]).inv()*desired)
    # The released Angel folds its near arm toward the existing real palm
    # preparation pose. Back/hip body support and every root stay unchanged.
    prepare=ease((t-9.50)/1.30)*return_source
    a_old=world(a,ar,'hand_l');a_goal=a_old*(1-prepare)+np.array([-22,4.25,90])*prepare
    a_rotation=rotation_mix(R.from_matrix(a.matrix('hand_l')[:3,:3]),end_a_rotation,prepare)
    a_result=None;low=float((a.surface()*UNIT+ar)[:,1].min())
    if not args.leave_angel_source:
        a_result=arm(angel,a,ar,a_goal,a_rotation,previous['angel'])
        for _ in range(4):
            low=float((a.surface()*UNIT+ar)[:,1].min())
            if low>=-.001:break
            a_goal[1]+=-low+.025
            a_result=arm(angel,a,ar,a_goal,a_rotation,a)
    else:prepare=0
    for role,p,rr,rig in [('eva',h,hr,hero),('angel',a,ar,angel)]:
        if role=='angel' and args.leave_angel_source:continue
        candidate[role]['frames'][index]=p.encode(old[role]['bones'],old[role]['frames'][index]['foot_contact'])
        if role=='eva' and args.leave_angel_source:
            frame=candidate[role]['frames'][index];original=old[role]['frames'][index]
            changed=lambda n:n in ('arm_l','forearm_l','hand_l') or n.startswith('r45_hand_l_')
            for j,name in enumerate(old[role]['bones']):
                if not changed(name):frame['rotation_wxyz'][j]=copy.deepcopy(original['rotation_wxyz'][j])
            frame['root_m']=copy.deepcopy(original['root_m'])
            positions=copy.deepcopy(original.get('bone_position_xyz',{}))
            for name in list(positions):
                if changed(name):del positions[name]
            positions.update({n:v for n,v in frame.get('bone_position_xyz',{}).items() if changed(n)})
            frame['bone_position_xyz']=positions
            candidate[role]['hand_l_blocks'][index]=world(p,rr,'hand_l').tolist()
            continue
        for side in ('l','r'):
            candidate[role]['hand_'+side+'_blocks'][index]=world(p,rr,'hand_'+side).tolist();candidate[role]['foot_'+side+'_blocks'][index]=sole_point(p,rr,side).tolist()
        if role=='eva':
            for channel,(bone,point) in baseline.items():candidate[role][channel][index]=world(p,rr,bone,point).tolist()
        else:
            for channel,bone,point in [('eye_blocks','head',angel.eye),('core_blocks','torso_upper',angel.core),('waist_blocks','torso_lower',angel.waist)]:candidate[role][channel][index]=world(p,rr,bone,point).tolist()
    previous={'eva':h,'angel':a}
    if index%6==0 or index in (696,720,749):rows.append(dict(frame=index,seconds=t,opening=opening,departure=depart,guard_recovery=recovery,angel_preparation=prepare,angel_actual_skin_minimum_y_blocks=low,hero_solver=h_result,angel_solver=a_result))
    if index%60==0:print('Authored actual release',index,flush=True)
# Freeze the original endpoint and all already checked late samples.
for role in ('eva','angel'):
    candidate[role]['frames'][540]=copy.deepcopy(old[role]['frames'][540])
    for name,value in old[role].items():
        if name!='frames' and isinstance(value,list) and len(value)==1381:candidate[role][name][540]=copy.deepcopy(value[540])
    assert candidate[role]['root_blocks']==old[role]['root_blocks']
    assert all(candidate[role]['frames'][i]==old[role]['frames'][i] for i in range(750,1117))
assert candidate['camera']==old['camera']
candidate['r52_finisher_rebuild']['release_revision']=args.revision+': open fingers, palm departure, forearm guard recovery; original autonomous Angel rise retained; late367 exact'
output.write_text(json.dumps(candidate,separators=(',',':')),'utf8')
report=dict(source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),changed_frames=[541,749],root_positions_exact=True,late367_pose_root_frames_exact=True,camera2_exact=True,
    angel_entire_source_exact=args.leave_angel_source,other_hero_bones_preserved_exact=args.leave_angel_source,
    actor_scales_changed=False,bone_lengths_changed=False,finger_open_window=[9,9.2],palm_departure_window=[9.18,9.78],forearm_guard_window=[9.7,10.3],angel_arm_prepare_window=None if args.leave_angel_source else [9.5,10.8],samples=rows,native_verified=False,user_accepted=False)
(args.out/'RELEASE_REVISION_REPORT.json').write_text(json.dumps(report,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else v.tolist()),'utf8')
print(output,flush=True)
