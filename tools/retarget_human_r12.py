"""Retarget measured full-body joint directions to the EVA and Angel proportions.

The unwarped result retains the source pelvis travel. Scene placement/contact
warping is a separate step so source motion is inspectable before constraints.
"""
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
import build_eva_body_r05 as eva
import author_first_battle_r10 as battle

UP=np.array([0.,1,0]);UNIT=5/16
def unit(v,fallback=(0,1,0)):
 v=np.asarray(v,float);n=np.linalg.norm(v);return v/n if n>1e-8 else np.array(fallback,float)
def axes(up,right):
 y=unit(up);x=unit(np.asarray(right)-y*np.dot(right,y),(1,0,0));return np.column_stack((x,y,np.cross(x,y)))

def solve_ik(p,a,bone,c,joint,target,pole,orientation,reference_axis=None):
 P=p.rig.P if isinstance(p,battle.AngelPose) else eva.P;shoulder=p.point(a);u=joint-P[a];v=P[c]-joint;la=np.linalg.norm(u);lb=np.linalg.norm(v);d=np.asarray(target)-shoulder;length=np.linalg.norm(d);direction=unit(d);distance=np.clip(length,abs(la-lb)+.001,la+lb-.001)
 along=(la*la-lb*lb+distance*distance)/(2*distance);height=np.sqrt(max(0,la*la-along*along));bend=unit(np.asarray(pole)-direction*np.dot(pole,direction),(0,0,1));elbow=shoulder+along*direction+height*bend;axis=unit(np.cross(elbow-shoulder,target-elbow),(1,0,0));rest=unit(np.cross(u,v),(1,0,0))
 if rest[0]<0:rest=-rest
 reference=p.matrix(a)[:3,:3]@rest if reference_axis is None else reference_axis
 if axis@reference<0:axis=-axis
 priors={n:R.from_matrix(p.matrix(n)[:3,:3]) for n in [a,bone]}
 def orient(n,original,wanted):
  prior=priors[n];swing=eva.arc(prior.apply(original),wanted);p.setq(n,R.from_matrix(p.parent(n)[:3,:3]).inv()*swing*prior)
 orient(a,u,elbow-shoulder);actual=(p.parent(bone)@np.r_[joint,1])[:3];orient(bone,v,np.asarray(target)-actual);delta=joint-P[bone];p.setp(bone,delta-p.q[bone].apply(delta));p.setq(c,R.from_matrix(p.parent(c)[:3,:3]).inv()*orientation)
 return float(np.linalg.norm(p.point(c)-target))

class Human:
 def __init__(self,path):
  d=np.load(path);self.names=list(d['names']);self.index={n:i for i,n in enumerate(self.names)};self.positions=d['positions'];self.rotations=d['rotations'];self.fps=float(d['fps']);self.frames=len(self.positions);self.path=str(path)
  bnr='UpperArm_L' in self.index;tuffles='Hip' in self.index
  self.map={'hip':'Hip' if tuffles else 'Hips','spine':'LowerSpine' if tuffles else 'Spine','chest':'Chest' if bnr or tuffles else 'Spine1','neck':'Neck','head':'Head','head_end':'Head_End'}
  for side,word in [('l','Left'),('r','Right')]:
   for key,bn,cm in [('shoulder','UpperArm_','Arm'),('elbow','LowerArm_','ForeArm'),('wrist','Hand_','Hand'),('hip','UpperLeg_','UpLeg'),('knee','LowerLeg_','Leg'),('ankle','Foot_','Foot'),('toe','Toes_','ToeBase')]:
    self.map[key+'_'+side]=side.upper()+{'shoulder':'Shoulder','elbow':'Forearm','wrist':'Hand','hip':'Thigh','knee':'Shin','ankle':'Foot','toe':'Toe'}[key] if tuffles else bn+side.upper() if bnr else word+cm
   self.map['finger_'+side]=side.upper()+'Finger2' if tuffles else ('Hand_'+side.upper()+'_End') if bnr else word+'FingerBase'
   self.map['toe_end_'+side]=side.upper()+'Toe_End' if tuffles else ('Toes_'+side.upper()+'_End') if bnr else word+'ToeBase_End'
   if not bnr and not tuffles:self.map['thumb_'+side]=side.upper()+'Thumb'
   if tuffles:self.map['thumb_'+side]=side.upper()+'Finger0'
  self.reference_frame=0 if bnr or tuffles else 1 # CMU BVH frame zero is a calibration pose.
  p=self.positions;start=self.reference_frame;across=(p[start:start+12,self.index[self.map['shoulder_l']]]-p[start:start+12,self.index[self.map['shoulder_r']]]).mean(0);forward=unit(np.cross(across,UP)*(1,0,1),(0,0,1))
  angle=np.arctan2(forward[0],-forward[2]);self.basis=R.from_euler('y',angle)
  self.reference=self.positions[start,self.index[self.map['hip']]].copy();self.reference[1]=0
  self.floor=min(np.percentile(p[:,self.index[self.map['ankle_'+s]],1],3) for s in ['l','r'])
  self.height=float(np.percentile(p[:,self.index['Head_End'],1]-np.minimum(p[:,self.index[self.map['toe_l']],1],p[:,self.index[self.map['toe_r']],1]),95))
  self.lengths={}
  self.hinge_local={}
  for side in ['l','r']:
   for a,b in [('hip','knee'),('knee','ankle'),('shoulder','elbow'),('elbow','wrist')]:self.lengths[a+'_'+side]=float(np.median(np.linalg.norm(p[:,self.index[self.map[a+'_'+side]]]-p[:,self.index[self.map[b+'_'+side]]],axis=1)))
   for limb,a,b,c in [('arm','shoulder','elbow','wrist'),('leg','hip','knee','ankle')]:
    u=p[:,self.index[self.map[b+'_'+side]]]-p[:,self.index[self.map[a+'_'+side]]];v=p[:,self.index[self.map[c+'_'+side]]]-p[:,self.index[self.map[b+'_'+side]]];u/=np.maximum(1e-9,np.linalg.norm(u,axis=1,keepdims=True));v/=np.maximum(1e-9,np.linalg.norm(v,axis=1,keepdims=True));normal=np.cross(u,v);f=int(np.linalg.norm(normal,axis=1).argmax());self.hinge_local[limb+'_'+side]=R.from_quat(self.rotations[f,self.index[self.map[a+'_'+side]]]).inv().apply(unit(normal[f]))
 def sample(self,frame,basis=None):
  c=self.basis if basis is None else basis;f=np.clip(frame,0,self.frames-1);a=int(f);b=min(a+1,self.frames-1);u=f-a;raw=self.positions[a]*(1-u)+self.positions[b]*u
  points={key:c.apply(raw[self.index[name]]-self.reference) for key,name in self.map.items()};qs={key:c*R.from_quat(self.rotations[a,self.index[name]]) for key,name in self.map.items()}
  if u>0:qs={key:Slerp([0,1],R.concatenate([q,c*R.from_quat(self.rotations[b,self.index[self.map[key]]])]))([u])[0] for key,q in qs.items()}
  return points,qs

class Retarget:
 def __init__(self,human,angel=False,calibrated_trunk=False):
  self.human=human;self.angel=angel;self.calibrated_trunk=calibrated_trunk;self.rig=battle.ANGEL if angel else eva;self.P=self.rig.P;self.parent=self.rig.parents if angel else eva.parents
  self.ref,self.refq=human.sample(human.reference_frame)
  self.foot_reference={}
  for side in ['l','r']:
   direction=self.ref['toe_'+side]-self.ref['ankle_'+side];self.foot_reference[side]=R.from_euler('y',np.arctan2(-direction[0],-direction[2]))
  self.knees={s:self.P['shin_'+s] if angel else eva.K[s] for s in ['l','r']};self.elbows={s:self.P['forearm_'+s] if angel else eva.E[s] for s in ['l','r']}
  self.hand_reference={}
  self.limb_reference={}
  for side in ['l','r']:
   forward=unit(self.ref['finger_'+side]-self.ref['wrist_'+side]);across=self.ref.get('thumb_'+side,self.ref['elbow_'+side])-self.ref['wrist_'+side]
   if np.linalg.norm(np.cross(forward,across))<.05:
    candidates=[self.refq['wrist_'+side].apply(v) for v in np.eye(3)];across=min(candidates,key=lambda v:abs(v@forward))
   rest_forward=unit(self.P['hand_'+side]-self.elbows[side]) if angel else unit(eva.P['finger_middle_'+side]-self.P['hand_'+side]);rest_across=np.array([1.,0,0]) if angel else eva.P['finger_index_'+side]-eva.P['finger_little_'+side]
   hand_basis=None if angel else getattr(eva,'anatomical_hand_basis_r45',None)
   if hand_basis is not None:
    rest_forward=unit(np.asarray(hand_basis[side]['longitudinal_bind'],float));rest_across=np.asarray(hand_basis[side]['across_bind'],float)
   self.hand_reference[side]=R.from_matrix(axes(forward,across)@axes(rest_forward,rest_across).T)
   for limb,a,mid,end,bone,lower,joint in [('arm','shoulder','elbow','wrist','arm_','forearm_',self.elbows[side]),('leg','hip','knee','ankle','leg_','shin_',self.knees[side])]:
    u=joint-self.P[bone+side];v=self.P[('hand_' if limb=='arm' else 'foot_')+side]-joint;rest_axis=unit(np.cross(u,v),(1,0,0))
    if rest_axis[0]<0:rest_axis=-rest_axis
    axis=self.refq[a+'_'+side].apply(self.human.hinge_local[limb+'_'+side]);du=self.ref[mid+'_'+side]-self.ref[a+'_'+side];dv=self.ref[end+'_'+side]-self.ref[mid+'_'+side]
    self.limb_reference[bone+side]=(a+'_'+side,R.from_matrix(axes(du,axis)@axes(u,rest_axis).T));self.limb_reference[lower+side]=(mid+'_'+side,R.from_matrix(axes(dv,axis)@axes(v,rest_axis).T))
  self.leg_scales={s:(np.linalg.norm(self.knees[s]-self.P['leg_'+s])+np.linalg.norm(self.P['foot_'+s]-self.knees[s]))/(human.lengths['hip_'+s]+human.lengths['knee_'+s]) for s in ['l','r']};self.leg_scale=np.mean(list(self.leg_scales.values()))
  self.feet={}
  if angel:
   for s in ['l','r']:
    index=battle.ANGEL.names.index('foot_'+s);w=np.sum(np.where(battle.ANGEL.ids==index,battle.ANGEL.weights,0),axis=1);self.feet[s]=battle.ANGEL.vertices[w>.6]-self.P['foot_'+s]
  else:self.feet=eva.feet
 def pose(self,frame,root_warp=None,support='feet'):
  src,qsrc=self.human.sample(frame);p=battle.ANGEL.pose() if self.angel else battle.hero_copy(eva.idle)
  p.setq('root',R.identity());p.setp('root',[0,0,0]);right=src['hip_r']-src['hip_l'];lower=R.from_matrix(axes(src['spine']-src['hip'],right));chest_up=src['neck']-src['chest']
  # CMU's Neck joint shares the Spine1 position. A zero vector would silently
  # freeze the chest upright, destroying the recorded torso action.
  if np.linalg.norm(chest_up)<1e-5:chest_up=src['head']-src['chest']
  upper=R.from_matrix(axes(chest_up,src['shoulder_r']-src['shoulder_l']))
  if self.calibrated_trunk:
   lower=qsrc['hip']*self.refq['hip'].inv()
   ref_up=self.ref['neck']-self.ref['chest']
   if np.linalg.norm(ref_up)<1e-5:ref_up=self.ref['head']-self.ref['chest']
   upper=upper*R.from_matrix(axes(ref_up,self.ref['shoulder_r']-self.ref['shoulder_l'])).inv()
  # The leg pivots are children of root on this rig. Pelvis rotation must
  # move those attachment points as well as the visible lower torso.
  p.setq('root',lower);p.setq('torso_lower',R.identity());p.setq('torso_upper',lower.inv()*upper)
  p.setq('neck',R.identity());head=qsrc['head']*self.refq['head'].inv();p.setq('head',R.from_matrix(p.parent('head')[:3,:3]).inv()*head)
  source_hip=(src['hip_l']+src['hip_r'])*.5
  hip=np.array([0,(source_hip[1]-self.human.floor)*self.leg_scale,0]);hip[1]+=np.mean([-self.feet[s][:,1].min() for s in ['l','r']]);actual=(p.point('leg_l')+p.point('leg_r'))/2;p.setp('root',hip-actual)
  delta=source_hip*self.leg_scale;delta[1]=0
  if root_warp is not None:delta=np.asarray(root_warp,float)
  contacts={};foot_goals={};hand_goals={};errors={}
  foot_info={};lowering=0.
  sole_height={s:min(src['toe_'+s][1],src['toe_end_'+s][1]) for s in ['l','r']};ground=min(sole_height.values())
  for side in ['l','r']:
   key='ankle_'+side;orientation=qsrc[key]*self.refq[key].inv()*self.foot_reference[side];target=p.point('leg_'+side)+(src[key]-src['hip_'+side])*self.leg_scales[side]
   if support!='feet':
    a=self.P['leg_'+side];b=self.knees[side];c=self.P['foot_'+side];target=p.point('leg_'+side)+unit(src['knee_'+side]-src['hip_'+side])*np.linalg.norm(b-a)+unit(src[key]-src['knee_'+side])*np.linalg.norm(c-b)
   # An ankle rising during heel roll is not a foot leaving the floor. Use
   # the captured toe support for these grounded fight clips instead.
   lift=max(0,(sole_height[side]-ground)*self.leg_scale);floor_offset=-orientation.apply(self.feet[side])[:,1].min();contact=lift<self.leg_scale*self.human.height*.026
   if support=='feet':
    if contact:target[1]=floor_offset
    else:target[1]=max(target[1],floor_offset+.02)
   origin=p.point('leg_'+side);length=np.linalg.norm(self.knees[side]-self.P['leg_'+side])+np.linalg.norm(self.P['foot_'+side]-self.knees[side]);horizontal=np.linalg.norm((target-origin)[[0,2]])
   available=np.sqrt(max(0,(length-.05)**2-horizontal**2))
   if contact and support=='feet':lowering=min(lowering,target[1]+available-origin[1])
   foot_info[side]=(orientation,target,lift,contact)
  if lowering<0:p.setp('root',p.p['root']+[0,lowering,0])
  for side in ['l','r']:
   orientation,target,lift,contact=foot_info[side]
   if not contact:target[1]+=lowering
   contacts[side]=contact;pole=src['knee_'+side]-src['hip_'+side]
   for name in ['leg_'+side,'shin_'+side]:
    key,reference=self.limb_reference[name];world=qsrc[key]*self.refq[key].inv()*reference;p.setq(name,R.from_matrix(p.parent(name)[:3,:3]).inv()*world)
   if not self.angel:p.setq('ankle_'+side,R.identity())
   err=solve_ik(p,'leg_'+side,'shin_'+side,'foot_'+side,self.knees[side],target,pole,orientation,qsrc['hip_'+side].apply(self.human.hinge_local['leg_'+side]))
   foot_goals[side]=target;errors['foot_'+side]=err*UNIT
   a=self.P['arm_'+side];e=self.elbows[side];h=self.P['hand_'+side];du=unit(src['elbow_'+side]-src['shoulder_'+side]);dv=unit(src['wrist_'+side]-src['elbow_'+side]);target=p.point('arm_'+side)+du*np.linalg.norm(e-a)+dv*np.linalg.norm(h-e)
   orientation=qsrc['wrist_'+side]*self.refq['wrist_'+side].inv()*self.hand_reference[side]
   for name in ['arm_'+side,'forearm_'+side]:
    key,reference=self.limb_reference[name];world=qsrc[key]*self.refq[key].inv()*reference;p.setq(name,R.from_matrix(p.parent(name)[:3,:3]).inv()*world)
   if not self.angel:
    for n in ['wrist_'+side,'hand_'+side]:p.setq(n,R.identity());p.setp(n,[0,0,0])
    for n in eva.rig:
     if n.startswith('finger_') and n.endswith('_'+side):p.setq(n,battle.fist.q.get(n,p.q[n]))
   err=solve_ik(p,'arm_'+side,'forearm_'+side,'hand_'+side,self.elbows[side],target,du,orientation,qsrc['shoulder_'+side].apply(self.human.hinge_local['arm_'+side]))
   hand_goals[side]=target;errors['hand_'+side]=err*UNIT
  if support in ['body','fall']:
   if self.angel:minimum=p.skin()[:,1].min()
   else:
    import author_eva_rifle_stances_r06 as mesh
    names=['torso_lower','leg_l','leg_r','shin_l','shin_r','foot_l','foot_r'] if support=='body' else ['torso_lower','torso_upper','head','arm_l','arm_r','forearm_l','forearm_r','hand_l','hand_r','leg_l','leg_r','shin_l','shin_r','foot_l','foot_r']
    minimum=mesh.floor(p,names)
   if support=='body' or minimum<0:p.setp('root',p.p['root']+[0,-minimum,0])
  return p,delta,dict(contacts=contacts,feet=foot_goals,hands=hand_goals,errors=errors,source_frame=float(frame))
