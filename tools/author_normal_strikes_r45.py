"""Two complete captured strikes aligned to one guard and anatomical support.

Remove the capture's initial stance difference, not its dynamic hip/shoulder
motion. Foot rolls keep a forefoot contact; root and all limbs are authored
together. Candidate only; attack damage/timing remain the existing contract.
"""
from pathlib import Path
import argparse,copy,hashlib,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from scipy.interpolate import PchipInterpolator
import author_gameplay_motion_r32 as common
import author_locomotion_r43 as locomotion
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy
from author_combat_performance_r36 import mix,ease
from study_combat_performance_r36 import decode
from rebuild_stance_hinges_r41 import reconstruct,reachable_root
from author_combat_bundle_r44 import maintain_joint_centres

p=argparse.ArgumentParser();p.add_argument('--body',type=Path,required=True);p.add_argument('--profiles',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--rig',type=int,default=1);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
for file in a.profiles.glob('*.json'):shutil.copy2(file,a.out/file.name)
common.BODY=json.loads(a.body.read_text());actor=Actor(a.rig);path=next(a.out/f'eva_gameplay_r{rev}_{a.rig}.json'for rev in [44,43,42,32]if(a.out/f'eva_gameplay_r{rev}_{a.rig}.json').exists());d=json.loads(path.read_text());guardclip=d['clips']['r32_guard'];guard=decode(actor,d,guardclip['frames'][len(guardclip['frames'])//2]);maintain_joint_centres(actor,guard)
facing=(guard.point('hand_l')+guard.point('hand_r')-guard.point('leg_l')-guard.point('leg_r'))*.5
guard_yaw=float(np.arctan2(facing[0],-facing[2]));common.rotate_stage(guard,actor.rig,R.from_euler('y',guard_yaw))
# The old guard was the sole capture left in a different forward frame.
# Rotate its entire loop once, so action entry and recovery share that frame.
for f in guardclip['frames']:
 pose=decode(actor,d,f);common.rotate_stage(pose,actor.rig,R.from_euler('y',guard_yaw));f.update(actor.rig.encode(pose,tuple(f.get('foot_contact',[True,True])),d['bones']))
locomotion.OUT=a.out/'capture';(locomotion.OUT/'source').mkdir(parents=True)
hip=lambda pose:(pose.point('leg_l')+pose.point('leg_r'))*.5
toes={s:np.asarray(d['support_toes'][s])*16 for s in ['l','r']};anchors={s:guard.point('foot_'+s)+R.from_matrix(guard.matrix('foot_'+s)[:3,:3]).apply(toes[s])for s in ['l','r']};rows=[]
for label,file,first,contact,last,side in [('jab','Male2_E1_JabLeft.bvh',20,36,64,'l'),('cross','Male2_E6_HookRight.bvh',14,33,59,'r')]:
 source=locomotion.SOURCE/file;human=locomotion.human(source);retarget=AnatomicalRetarget(human)
 def source_pose(frame):
  pose,travel,_=retarget.pose(frame,support='air');return anatomy(actor,pose,closure=1),travel
 reference,_=source_pose(first+1);refhip=hip(reference);guardhip=hip(guard);first_source,_=human.sample(first+1)
 old=d['clips']['r32_'+label];frames=[];count=101;curve=PchipInterpolator([0,float(old['contact_phase']),1],[first+1,contact+1,last+1]);previous={s:guard.q['leg_'+s]for s in ['l','r']};root_angles=[];joint_errors=[]
 for t in np.linspace(0,1,count):
  at=float(curve(t));src,_=source_pose(at);pose=copy.deepcopy(guard)
  for n in pose.q:pose.setq(n,guard.q[n]*reference.q[n].inv()*src.q[n])
  # Hip position is an anatomical point, not the high model root marker.
  desired=guardhip+(hip(src)-refhip);pose.setp('root',pose.p['root']+desired-hip(pose))
  maintain_joint_centres(actor,pose)
  weight=ease(t/.16)*(1-ease((t-.66)/.34));pose=mix(copy.deepcopy(guard),pose,weight)
  goals={};orientations={}
  for s in ['l','r']:
   q=R.from_matrix(pose.matrix('foot_'+s)[:3,:3]);orientations[s]=q;target=anchors[s]-q.apply(toes[s]);target[1]=-q.apply(actor.feet[s])[:,1].min();goals[s]=target
  reachable_root(actor,pose,goals)
  for s in ['l','r']:
   joint_errors.append(reconstruct(actor,pose,s,goals[s],orientations[s],previous[s]));previous[s]=pose.q['leg_'+s]
  maintain_joint_centres(actor,pose);root_angles.append(float(np.degrees((guard.q['root'].inv()*pose.q['root']).magnitude())));frames.append(actor.rig.encode(pose,(True,True),d['bones']))
 old.update(frames=frames,trajectory_m=[[0,0,0]for _ in frames],step_contacts=[[True,True]for _ in frames],stance_locked=True,leading_side=side,support='Common anatomical guard with relative captured whole-body performance and forefoot support')
 rows.append(dict(clip=label,source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_frames=[first,contact,last],maximum_root_rotation_from_guard_deg=max(root_angles),maximum_ankle_error_world_blocks=max(joint_errors)*5/16,duration_seconds=old['duration_seconds'],damage_changed=False,native_passed=False,visual_accepted=False))
d['r45_common_stance_strikes']=dict(guard_frame_alignment_degrees=float(np.degrees(guard_yaw)),clips=rows);path.write_text(json.dumps(d,separators=(',',':')),encoding='utf8');(a.out/'strike_authoring.json').write_text(json.dumps(d['r45_common_stance_strikes'],indent=2),encoding='utf8');print(json.dumps(d['r45_common_stance_strikes']))
