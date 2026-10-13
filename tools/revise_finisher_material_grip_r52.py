"""Independent continuous material regrip; retain the already checked late action."""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
from r52_motion_core import selected,read,UNIT,MIRROR,ease,hand_controls
from author_finisher_r52 import world
from calibrated_arm_r52 import solve
from revise_finisher_body_r52 import preserve_hinges,rotation_mix
from bake_finisher_r52 import anchors,sole_point


def set_global(pose,name,matrix):
    local=np.linalg.inv(pose.parent(name))@matrix;rotation=local[:3,:3];pivot=pose.rig.P[name]
    pose.setq(name,R.from_matrix(rotation));pose.setp(name,local[:3,3]-pivot+rotation@pivot)


def face_basis(triangle):
    x=triangle[1]-triangle[0];x/=np.linalg.norm(x)
    z=np.cross(x,triangle[2]-triangle[0]);z/=np.linalg.norm(z)
    return np.column_stack([x,np.cross(z,x),z])


parser=argparse.ArgumentParser(description=__doc__)
for name in ('body','assets','angel-rig','source','regrip-probes','out'):
    parser.add_argument('--'+name,type=Path,required=True)
parser.add_argument('--revision',default='grip1',choices=['grip1','grip2'])
parser.add_argument('--transport-hand-frame',action='store_true')
parser.add_argument('--late-angel-arc',action='store_true')
args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
output=args.out/f'first_battle_r52_body3_{args.revision}.json';assert not output.exists()
_,hero,angel=selected(args.body,args.assets,args.angel_rig);old=read(args.source);candidate=copy.deepcopy(old)
probe=next(r for r in read(args.regrip_probes)['rows'] if r['case']==3)
base=angel.decode(probe['angel_frame'],old['angel']['bones'])
root=np.array(old['angel']['root_blocks'][720]);triangle_index=probe['angel_contact_triangle'];vertex=probe['hero_contact_vertex']
face=(base.surface()*UNIT+root).reshape(-1,3,3)[triangle_index]
point=np.array(probe['angel_surface_point']);uv=np.linalg.lstsq(np.column_stack([face[1]-face[0],face[2]-face[0]]),point-face[0],rcond=None)[0]
bary=np.array([1-uv.sum(),*uv]);normal=np.array(probe['hand_surface_point'])-point;normal/=np.linalg.norm(normal)
local_normal=face_basis(face).T@normal;baseline=anchors(old,hero);rows=[]
static_hand=hero.decode(probe['eva_frame'],old['eva']['bones'])
static_hand_orientation=R.from_matrix(static_hand.matrix('hand_l')[:3,:3])
for index in range(342,750):
    t=index/60;ah=ease((t-5.7)/.8)*(1-ease((t-12.12)/.35));eh=ease((t-5.7)/.8)*(1-ease((t-12.05)/.35))
    if args.late_angel_arc:ah*=ease((t-11.65)/.35)
    if max(ah,eh)<1e-10:continue
    h=hero.decode(old['eva']['frames'][index],old['eva']['bones']);a=angel.decode(old['angel']['frames'][index],old['angel']['bones'])
    hr=np.array(old['eva']['root_blocks'][index]);ar=np.array(old['angel']['root_blocks'][index])
    orientation_a=R.from_matrix(a.matrix('hand_l')[:3,:3]);upper=R.from_matrix(a.matrix('arm_l')[:3,:3])
    a.setq('arm_l',R.from_matrix(a.parent('arm_l')[:3,:3]).inv()*R.from_euler('xy',[2*ah,8*ah],degrees=True)*upper)
    preserve_hinges(a)
    desired_a=R.from_euler('y',-105,degrees=True)*R.from_euler('x',45,degrees=True)
    a.setq('hand_l',R.from_matrix(a.parent('hand_l')[:3,:3]).inv()*rotation_mix(orientation_a,desired_a,ah))
    grip=copy.deepcopy(h);hand_controls(grip,'grab','relaxed')
    for name in h.q:
        if name.startswith('r45_hand_l_'):h.setq(name,rotation_mix(h.q[name],grip.q[name],eh))
    actual_face=(a.surface()*UNIT+ar).reshape(-1,3,3)[triangle_index]
    if args.transport_hand_frame:
        original_orientation=R.from_matrix(h.matrix('hand_l')[:3,:3])
        desired=R.from_matrix(face_basis(actual_face)@face_basis(face).T)*static_hand_orientation
        h.setq('hand_l',R.from_matrix(h.parent('hand_l')[:3,:3]).inv()*rotation_mix(original_orientation,desired,eh))
    original=(h.surface(['hand_l'])*MIRROR*UNIT+hr)[vertex]
    contact=bary@actual_face;direction=face_basis(actual_face)@local_normal
    destination=contact+direction*.005
    wanted=original*(1-eh)+destination*eh
    orientation=R.from_matrix(h.matrix('hand_l')[:3,:3]);goal=h.point('hand_l')+(wanted-original)*MIRROR/UNIT
    solver=None
    for _ in range(4):
        origin=h.point('arm_l');axis=h.point('hand_l')-origin;axis/=np.linalg.norm(axis)
        elbow=h.point('arm_l',hero.elbows['l'])-origin;normal=np.cross(axis,elbow);normal/=np.linalg.norm(normal)
        h.r52_elbow_normals={'l':normal};h.r52_elbow_directions={'l':axis}
        solver=solve(h,hero.P,'arm_l','forearm_l','hand_l',hero.elbows['l'],goal,
                     R.from_euler('y',90,degrees=True).apply([-.8,-.45,-.35]),[1,0,0],orientation)
        preserve_hinges(h);h.setq('hand_l',R.from_matrix(h.parent('hand_l')[:3,:3]).inv()*orientation)
        actual=(h.surface(['hand_l'])*MIRROR*UNIT+hr)[vertex];error=wanted-actual;goal+=error*MIRROR/UNIT
    # Small elbow-plane clearance leaves the solved material contact and the
    # complete hand/finger world transforms intact, rather than detaching it.
    wrist=h.matrix('hand_l').copy();origin=h.point('arm_l');axis=h.point('hand_l')-origin;axis/=np.linalg.norm(axis)
    turn=np.eye(4);turn[:3,:3]=R.from_rotvec(axis*np.radians(-5*eh)).as_matrix();turn[:3,3]=origin-turn[:3,:3]@origin
    set_global(h,'arm_l',turn@h.matrix('arm_l'));set_global(h,'hand_l',wrist)
    for role,p,rr,rig in [('eva',h,hr,hero),('angel',a,ar,angel)]:
        candidate[role]['frames'][index]=p.encode(old[role]['bones'],old[role]['frames'][index]['foot_contact'])
        for side in ('l','r'):
            candidate[role]['hand_'+side+'_blocks'][index]=world(p,rr,'hand_'+side).tolist()
            candidate[role]['foot_'+side+'_blocks'][index]=sole_point(p,rr,side).tolist()
        if role=='eva':
            for channel,(bone,rest) in baseline.items():candidate[role][channel][index]=world(p,rr,bone,rest).tolist()
        else:
            for channel,bone,rest in [('eye_blocks','head',angel.eye),('core_blocks','torso_upper',angel.core),('waist_blocks','torso_lower',angel.waist)]:candidate[role][channel][index]=world(p,rr,bone,rest).tolist()
    if index%6==0 or index in (696,720,735,749):
        rows.append(dict(frame=index,seconds=t,angel_weight=ah,eva_weight=eh,material_gap_blocks=float(np.linalg.norm(actual-contact)),material_target_error_blocks=float(np.linalg.norm(error)),solver=solver))
    if index%60==0:print('Authored material regrip',index,flush=True)
assert all(old[role]['frames'][index]==candidate[role]['frames'][index] and old[role]['root_blocks'][index]==candidate[role]['root_blocks'][index] for role in ('eva','angel') for index in range(750,1117))
assert candidate['camera']==old['camera']
candidate['r52_finisher_rebuild']['grip_revision']='material '+args.revision+'; changed early source only, late367 pose/root frames exact'
output.write_text(json.dumps(candidate,separators=(',',':')),'utf8')
report=dict(source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),changed_window=[342,749],late367_pose_root_frames_exact=True,camera_unchanged=True,
    transported_hand_frame=args.transport_hand_frame,late_angel_arc=args.late_angel_arc,
    actor_scales_changed=False,bone_lengths_changed=False,material_anchor=dict(hero_vertex=vertex,angel_triangle=triangle_index,barycentric=bary.tolist(),gap_blocks=.005),samples=rows,native_verified=False,user_accepted=False)
(args.out/'MATERIAL_GRIP_REVISION.json').write_text(json.dumps(report,indent=2,default=lambda value:value.item() if isinstance(value,np.generic) else value.tolist()),'utf8')
print(output,flush=True)
