"""Private full-body task adaptation against a frozen real receiver surface.

The source stroke/return and phalanges come from the reopened body-punch scene.
Both actual boots remain planted, and the measured mass model constrains COM.
This is authored task adaptation, not newly captured prone-punch motion.
"""
from pathlib import Path
import argparse,copy,hashlib,json,math,sys
import bpy,numpy as np
from mathutils import Matrix,Quaternion,Vector

ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--crouch',type=Path,required=True);ap.add_argument('--receiver',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
fixture=json.loads((args.source/'fixture.json').read_text());data=fixture['actors'][0];name=data['name'];author=bpy.data.objects[name+'_AUTHOR'];deform=bpy.data.objects[name+'_DEFORM'];rest=author.data.bones;aliases=json.loads(author['aliases_json']);scene=bpy.context.scene
card=fixture['source_motion_card'];old_records=json.loads((args.source/'contact_pass_receipt.json').read_text())['records'];source=[]
for frame in range(1,scene.frame_end+1):
    scene.frame_set(frame);bpy.context.view_layer.update();source.append({b.name:b.matrix.copy()for b in author.pose.bones})
crouch=json.loads((args.crouch/'baked_world_matrices.json').read_text())[18]['actors'][name]['deform'];seed=Matrix(crouch['torso_lower'])@rest['pelvis'].matrix_local
receiver=np.load(args.receiver/'receiver_full_surface.npz',allow_pickle=False);rv=receiver['vertices_actor_dcc'];rn=list(receiver['bones']);ro=receiver['owner'];tri=rv.reshape(-1,3,3);torso=np.isin(ro,[rn.index(n)for n in('torso_lower','torso_upper')]).reshape(-1,3).all(1)
surface=tri[torso];centres=surface.mean(1);chosen={}
def nearest_on_triangle(p,a,b,c):
    ab=b-a;ac=c-a;ap=p-a;d1=ab@ap;d2=ac@ap
    if d1<=0 and d2<=0:return a
    bp=p-b;d3=ab@bp;d4=ac@bp
    if d3>=0 and d4<=d3:return b
    vc=d1*d4-d3*d2
    if vc<=0 and d1>=0 and d3<=0:return a+d1/(d1-d3)*ab
    cp=p-c;d5=ab@cp;d6=ac@cp
    if d6>=0 and d5<=d6:return c
    vb=d5*d2-d1*d6
    if vb<=0 and d2>=0 and d6<=0:return a+d2/(d2-d6)*ac
    va=d3*d6-d5*d4
    if va<=0 and d4-d3>=0 and d5-d6>=0:return b+(d4-d3)/(d4-d3+d5-d6)*(c-b)
    denom=va+vb+vc
    if abs(denom)<1e-10:return(a+b+c)/3
    return a+ab*(vb/denom)+ac*(vc/denom)
for side,sign in(('l',-1),('r',1)):
    # A front-facing triangle of the real low torso, selected in the actor task frame.
    preferred=np.array([sign*4.,17.,13.]);closest=np.asarray([nearest_on_triangle(preferred,*t)for t in surface]);score=np.sum((closest-preferred)**2,axis=1);at=int(score.argmin());point=closest[at];normal=np.cross(surface[at,1]-surface[at,0],surface[at,2]-surface[at,0]);normal/=np.linalg.norm(normal)
    if normal@(-point)>0:pass
    else:normal=-normal
    chosen[side]=dict(point=Vector(point),normal=Vector(normal),triangle=surface[at].tolist(),torso_triangle_index=at)
neutral=np.asarray(data['vertices']);ids=np.asarray(data['influences']);weights=np.asarray(data['weights']);bone_names=[b['name']for b in data['bones']];owner=ids[np.arange(len(ids)),weights.argmax(1)]
cache=np.load(args.source/'floor_extrema/rigid_floor_extrema.npz');shapes={}
for bone in bone_names:
    key='full__'+bone
    if key in cache:shapes[bone]=cache[key]
    else:
        own=neutral[owner==bone_names.index(bone)]
        if len(own):shapes[bone]=np.unique(own,axis=0)

def posed(shape,delta):
    a=np.asarray(delta);return shape@a[:3,:3].T+a[:3,3]
def hull(points):
    values=sorted(set(tuple(p)for p in points));lo=[];hi=[]
    def cross(a,b,c):return(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    for sequence,result in((values,lo),(values[::-1],hi)):
        for p in sequence:
            while len(result)>1 and cross(result[-2],result[-1],p)<=0:result.pop()
            result.append(p)
    return lo[:-1]+hi[:-1]
def margins(point,polygon):
    return np.array([((b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0]))/np.linalg.norm(np.asarray(b)-a)for a,b in zip(polygon,polygon[1:]+polygon[:1])])
def set_local(pose,desired):
    local={}
    for bone in rest:
        parent=bone.parent;m=desired[bone.name]
        local[bone.name]=bone.matrix_local.inverted()@m if parent is None else bone.matrix_local.inverted()@parent.matrix_local@desired[parent.name].inverted()@m
        pose[bone.name].matrix_basis=local[bone.name]
    return local
def chain(reference,h,a,upper,lower,end,plane_reference):
    u,v=data['joints'][('leg_'if upper.startswith('leg_')else'arm_')+upper[-1]]['lengths'];delta=a-h;distance=delta.length;direction=delta.normalized();reach=max(abs(u-v)+1e-5,min(u+v-1e-5,distance));along=(u*u-v*v+reach*reach)/(2*reach);height=math.sqrt(max(0,u*u-along*along))
    refh=plane_reference[upper].translation;refk=plane_reference[lower].translation;refa=plane_reference[end].translation;axis=(refa-refh).normalized();plane=refk-refh-axis*(refk-refh).dot(axis)
    if plane.length<1e-5:plane=Vector((0,1,0))-axis*axis.y
    plane.normalize();plane=axis.rotation_difference(direction)@plane;plane-=direction*plane.dot(direction);plane.normalize();k=h+direction*along+plane*height;a=h+direction*reach
    qu=(reference[lower].translation-reference[upper].translation).normalized().rotation_difference((k-h).normalized())@reference[upper].to_quaternion();ql=(reference[end].translation-reference[lower].translation).normalized().rotation_difference((a-k).normalized())@reference[lower].to_quaternion()
    result={}
    for n,p,q in((upper,h,qu),(lower,k,ql)):
        m=q.to_matrix().to_4x4();m.translation=p;result[n]=m
    return result,a,distance-reach

# Immutable actual boot poses and the floor polygon belong to this whole task.
baseline=source[0];boots={};patches=[]
for side in('l','r'):
    foot='foot_'+side;captured=baseline[foot];receiver_centre=(chosen['l']['point']+chosen['r']['point'])*.5;forward=receiver_centre-captured.translation;forward.z=0;forward.normalize();yaw=math.atan2(-forward.x,forward.y);m=(Quaternion((0,0,1),yaw)@rest[foot].matrix_local.to_quaternion()).to_matrix().to_4x4();m.translation=captured.translation.copy();shape=neutral[owner==bone_names.index(foot)];p=posed(shape,m@rest[foot].matrix_local.inverted());m.translation.z+=.015-float(p[:,2].min());boots[foot]=m;p=posed(shape,m@rest[foot].matrix_local.inverted());patches.extend(p[p[:,2]<=.095,:2].tolist())
polygon=hull(patches);assert len(polygon)>=3
seed_fk={n:Matrix(crouch[next(k for k,v in aliases.items()if v==n)])@rest[n].matrix_local if n in aliases.values()else baseline[n].copy()for n in rest.keys()}
seed_fk['pelvis']=seed;seed_origin=seed.translation.copy();seed_origin.x=baseline['pelvis'].translation.x;seed_origin.y=baseline['pelvis'].translation.y;seed_origin.z-=9.
for b in author.pose.bones:
    for c in list(b.constraints):b.constraints.remove(c)
author.animation_data_clear();deform.animation_data_clear();previous_q={};records=[];baked=[];segment_info=[]
segments=[s for s in card['segments']if s['label']!='guard'];labels={r['frame']:r['label']for r in old_records};task_paths={}
for segment in segments:
    indices=[i for i,r in enumerate(old_records)if r['raw_frame']is not None and segment['candidate_frames'][0]<=r['raw_frame']<=segment['candidate_frames'][1]];side=segment['leading_side'];contact_i=indices[int(round(segment['runtime_contact_phase']*(len(indices)-1)))];contact=source[contact_i];target=chosen[side]['point'];direction=(target-Vector((target.x,8.,28.))).normalized();task_rotation=Vector((0,1,0)).rotation_difference(direction);hand='hand_'+side
    closed=[]
    for bone in shapes:
        if bone==hand or bone.startswith('finger_')and bone.endswith('_'+side):closed.extend(posed(shapes[bone],contact[aliases[bone]]@rest[aliases[bone]].matrix_local.inverted()).tolist())
    closed=np.asarray(closed);projection=(closed-np.asarray(contact[hand].translation))@np.asarray(task_rotation.inverted()@direction);surface_offset=Vector(closed[int(projection.argmax())])-contact[hand].translation;wrist_contact=target-task_rotation@surface_offset
    for i in indices:task_paths[i]=(task_rotation,wrist_contact+task_rotation@(source[i][hand].translation-contact[hand].translation),side,source[indices[0]]['pelvis'].to_quaternion(),indices[0],indices[-1])
    segment_info.append(dict(label=segment['label'],leading_side=side,contact_frame=contact_i+1,receiver_point=list(target),actual_closed_fist_vertex_offset=list(surface_offset),source_complete_frames=[indices[0]+1,indices[-1]+1]))

previous_x=np.array([0.,0.,0.,0.,0.,0.]);guard_path=next(iter(task_paths.values()))
for i,ref in enumerate(source):
    task_rotation,lead_goal,side,source_entry,segment_first,segment_last=task_paths.get(i,guard_path);segment_entry=i==segment_first
    if segment_entry:previous_x=np.zeros(6)
    x0=previous_x.copy();source_change=ref['pelvis'].to_quaternion()@source_entry.inverted();base_q=source_change@seed.to_quaternion()
    def evaluate(x,readback=False):
        q=Quaternion((1,0,0),float(x[3]))@Quaternion((0,1,0),float(x[4]))@base_q;p=seed_origin+Vector(x[:3]);body=q@ref['pelvis'].to_quaternion().inverted();transform=body.to_matrix().to_4x4();transform.translation=p-body@ref['pelvis'].translation;desired={n:transform@m for n,m in ref.items()};errors=[];reach_errors={}
        chest_axis=desired['chest'].to_quaternion()@rest['chest'].matrix_local.to_quaternion().inverted()@Vector((1,0,0));chest_q=Quaternion(chest_axis,float(x[5]));chest_transform=chest_q.to_matrix().to_4x4();chest_origin=desired['chest'].translation;chest_transform.translation=chest_origin-chest_q@chest_origin
        for n in desired:
            bone=rest[n];ancestor=bone
            while ancestor is not None and ancestor.name!='chest':ancestor=ancestor.parent
            if ancestor is not None:desired[n]=chest_transform@desired[n]
        for s in('l','r'):
            for family in('leg','arm'):
                upper=('leg_'if family=='leg'else'arm_')+s;lower=('shin_'if family=='leg'else'forearm_')+s;end=('foot_'if family=='leg'else'hand_')+s
                goal=boots[end].translation.copy()if family=='leg'else lead_goal.copy()if s==side else desired[end].translation.copy();chain_result,a,reach=chain(seed_fk if family=='leg'else desired,desired[upper].translation,goal,upper,lower,end,seed_fk if family=='leg'else desired);desired.update(chain_result);reach_errors[family+'_'+s]=reach;errors.append(100*reach)
                if family=='arm'and s==side and i in task_paths:
                    reach_limit=sum(data['joints']['arm_'+s]['lengths'])-.05
                    for future in range(i+1,min(segment_last,i+8)+1):
                        future_goal=task_paths[future][1]
                        errors.append(30*max(0.,(future_goal-desired[upper].translation).length-reach_limit))
                desired[end]=boots[end].copy()if family=='leg'else (task_rotation@ref[end].to_quaternion()).to_matrix().to_4x4()if s==side else desired[end].copy();desired[end].translation=a
                # Source finger local rotations inherit the actual solved hand.
                if family=='arm':
                    hand_delta=desired[end]@ref[end].inverted()
                    for n in ref:
                        if n.startswith('finger_')and n.endswith('_'+s):desired[n]=hand_delta@ref[n]
        # Keep the captured gaze while its actual neck position follows the body.
        head_position=desired['head'].translation.copy();desired['head']=ref['head'].to_quaternion().to_matrix().to_4x4();desired['head'].translation=head_position
        deltas={n:desired[aliases[n]]@rest[aliases[n]].matrix_local.inverted()for n in aliases};total=sum(data['masses'].values());com=sum(((deltas[n]@Vector(data['mass_centres'][n]))*m for n,m in data['masses'].items()),Vector((0,0,0)))/total;sm=margins(com,polygon);errors.extend(100*np.maximum(0.,.35-sm))
        minima={n:float(posed(shape,deltas[n])[:,2].min())for n,shape in shapes.items()if n in deltas and n not in('cannon','knife','lance','entry_plug')};errors.extend(150*np.maximum(0.,.015-np.array(list(minima.values()))));errors.extend(.15*x[:3]);errors.extend(.5*x[3:]);errors.extend(.25*(x-previous_x));err=np.asarray(errors)
        return(dict(desired=desired,deltas=deltas,com=list(com),support_margin=float(sm.min()),minima=minima,reach_errors=reach_errors,cost=float(err@err)),err)if readback else err
    x=x0;error=evaluate(x);cost=float(error@error);damping=.01
    for iteration in range(40):
        columns=[]
        for j in range(6):
            trial=x.copy();step=.002 if j<3 else .0005;trial[j]+=step;columns.append((evaluate(trial)-error)/step)
        jac=np.asarray(columns).T;delta=np.linalg.solve(jac.T@jac+np.eye(6)*damping,-jac.T@error);improved=False
        for amount in(1.,.5,.25,.125):
            trial=x+amount*delta;trial[:3]=np.clip(trial[:3],[-8,-15,-6],[8,12,5]);trial[3:]=np.clip(trial[3:],[-1.,-.45,-.9],[.7,.45,.9]);
            if not segment_entry:trial=np.clip(trial,previous_x-[.8,.8,.8,.12,.12,.12],previous_x+[.8,.8,.8,.12,.12,.12])
            e=evaluate(trial);c=float(e@e)
            if c<cost:x=trial;error=e;cost=c;damping=max(1e-5,damping*.5);improved=True;break
        if not improved:damping*=10
    report,_=evaluate(x,True);previous_x=x;desired=report.pop('desired');deltas=report.pop('deltas');set_local(author.pose.bones,desired)
    deform_desired={n:deltas[n]@deform.data.bones[n].matrix_local for n in aliases}
    for rig,wanted in((author,desired),(deform,deform_desired)):
        for bone in rig.data.bones:
            n=bone.name;parent=bone.parent;m=wanted[n];local=bone.matrix_local.inverted()@m if parent is None else bone.matrix_local.inverted()@parent.matrix_local@wanted[parent.name].inverted()@m;p=rig.pose.bones[n];p.rotation_mode='QUATERNION';p.matrix_basis=local;key=rig.name+n
            if key in previous_q and p.rotation_quaternion.dot(previous_q[key])<0:p.rotation_quaternion.negate()
            previous_q[key]=p.rotation_quaternion.copy()
            for channel in('location','rotation_quaternion','scale'):p.keyframe_insert(channel,frame=i+1)
    record=copy.deepcopy(old_records[i]);record['source_contacts'].update(foot_l=True,foot_r=True,hand_l=False,hand_r=False);record['source_sole_contact_weights']={'l':1.,'r':1.};record['source_horizontal_foot_plants']={'l':True,'r':True};record['actual_ik_goal_error_blocks']=report['reach_errors'];record['actual_low_receiver_task']=dict(**report,parameters=x.tolist(),static_mass_model=True,actual_receiver_tick_gap=1);records.append(record)
    root=desired['pelvis'].translation-rest['pelvis'].head_local;root.z=0;baked.append(dict(frame=i+1,time=i/30,actors={name:dict(root=list(root),yaw=0.,deform={n:[list(v)for v in m]for n,m in deltas.items()},controls={})}))
    if(i+1)%30==0:print('Full low receiver task',i+1,'COMmargin',report['support_margin'],'minZ',min(report['minima'].values()),flush=True)
fixture['quality']='PRIVATE UNAPPROVED source-based whole-body low receiver task; actual terrain, entry/exit and reactive contact remain open.';fixture['actual_low_receiver_task']=dict(receiver_directory=str(args.receiver.resolve()),source_crouch=str(args.crouch.resolve()),static_mass_support_polygon=polygon,segments=segment_info,source_stroke_not_recaptured=True,foot_task='Whole actual sole planes horizontal; toes point from retained source opening ankle centres towards the measured receiver contact-centre. Both boots planted during each stroke; entry/exit separate task still required.',anticipation_frames=8)
(out/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')));(out/'baked_world_matrices.json').write_text(json.dumps(baked,separators=(',',':')));receipt=json.loads((args.source/'contact_pass_receipt.json').read_text());receipt.update(records=records,actual_low_receiver_task=fixture['actual_low_receiver_task'],artistic_acceptance=False);(out/'contact_pass_receipt.json').write_text(json.dumps(receipt,separators=(',',':')));scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'rokoko_continuous_legs_r44.blend'));print('Saved complete low receiver adaptation',len(records),flush=True)
