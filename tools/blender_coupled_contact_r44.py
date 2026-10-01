"""Whole-body contact solve over real rigid surfaces, with source-plane fidelity.

Pelvis translation, foot rollover and limb planes are coupled. This is a
private authoring solve; it does not translate the finished mesh to minZ=0.
"""
import math
import numpy as np
from mathutils import Matrix,Quaternion,Vector


def solve(fk,rest,data,limb_geometry,foot_geometry,body_geometry,goals,orientations,source,previous=None,
          support_amount=1.,foot_contact_weights=None,hand_contact_weights=None,previous_planes=None,previous_axes=None,
          bearing_geometry=None,foot_patch_indices=None):
    previous_pose=previous if isinstance(previous,dict) else None
    previous=previous_pose['parameters'] if previous_pose is not None else previous
    limbs={};feet={}
    for side,word in (('l','Left'),('r','Right')):
        foot='foot_'+side;q=orientations[foot];a=goals[foot];m=q.to_matrix().to_4x4();m.translation=a
        delta=m@rest[foot].matrix_local.inverted();shape=foot_geometry[side]
        points=shape@np.asarray(delta)[:3,:3].T+np.asarray(delta)[:3,3]
        # A horizontal crawling body bears on the actual forefoot/instep.
        # Heel rise is allowed; whole-boot collision is a separate inequality.
        front=(foot_patch_indices or{}).get(side)
        if front is None:front=np.flatnonzero(shape[:,1]>=np.percentile(shape[:,1],85))
        toe_authority=support_amount*max(0.,min(1.,(.09-min(source[word+'ToeBase'].z,source[word+'ToeBase_End'].z))/.06))
        index=int(np.argmin(points[:,2]));front_index=int(front[np.argmin(points[front,2])]);patch=Vector(points[index]).lerp(Vector(points[front_index]),toe_authority)
        feet[side]=dict(shape=shape,q=q,a=a,patch=patch,patch_ids=front,index=index,front_index=front_index,toe_authority=toe_authority,
                       contact_mode='continuous-boot-to-forefoot-instep',axis=(delta.to_3x3()@Vector((1,0,0))).normalized())
        for family in ('leg','arm'):
            upper=('leg_'if family=='leg'else'arm_')+side;lower=('shin_'if family=='leg'else'forearm_')+side;end=('foot_'if family=='leg'else'hand_')+side
            h=fk[upper].translation;k=fk[lower].translation;a_raw=fk[end].translation;raw_axis=(a_raw-h).normalized()
            bend=k-h-raw_axis*(k-h).dot(raw_axis)
            if bend.length<1e-5:bend=Vector((0,1,0))-raw_axis*raw_axis.y
            raw_bend_length=bend.length;bend.normalize();source_joint=source[word+('Leg'if family=='leg'else'ForeArm')]
            limb=family+'_'+side
            if previous_planes and limb in previous_planes:
                transported=previous_axes[limb].rotation_difference(raw_axis)@previous_planes[limb];transported-=raw_axis*transported.dot(raw_axis);transported.normalize()
                confidence=min(1.,(raw_bend_length/max(.08*min(data['joints'][limb]['lengths']),1e-5))**2)
                angle=math.atan2(raw_axis.dot(transported.cross(bend)),transported.dot(bend));bend=Quaternion(raw_axis,angle*confidence)@transported
            threshold=.10 if family=='leg'else.08
            support=max(0.,min(1.,(threshold-source_joint.z)/.045))*support_amount
            # Support is the proximal elbow/knee surface, not whichever distal
            # wrist/ankle vertex happens to be the whole lower limb minimum.
            shape=limb_geometry[lower];joint=np.asarray(data['joints'][family+'_'+side]['joint']);tip=np.asarray(data['joints'][family+'_'+side]['end']);axis=tip-joint;length=np.linalg.norm(axis);axis/=max(length,1e-8)
            longitudinal=(shape-joint)@axis;patch=shape[(longitudinal>=-length*.1)&(longitudinal<=length*.25)]
            if not len(patch):patch=shape[np.argsort(np.linalg.norm(shape-joint,axis=1))[:max(3,len(shape)//10)]]
            if bearing_geometry and lower in bearing_geometry:patch=bearing_geometry[lower]
            source_upper=source[word+('UpLeg'if family=='leg'else'Arm')]
            source_end=source[word+('Foot'if family=='leg'else'Hand')]
            source_first=(source_joint-source_upper).normalized()
            source_second=(source_end-source_joint).normalized()
            source_cos=max(-1.,min(1.,source_first.dot(source_second)))
            u,v=data['joints'][family+'_'+side]['lengths']
            captured_reach=math.sqrt(max(1e-8,u*u+v*v+2*u*v*source_cos))
            limbs[family+'_'+side]=dict(upper=upper,lower=lower,end=end,h=h,k=k,a=a_raw,axis=raw_axis,bend=bend,
                                       captured_flexion_degrees=math.degrees(math.acos(source_cos)),captured_reach=captured_reach,
                                       lengths=data['joints'][family+'_'+side]['lengths'],support=support,support_patch=patch)
    def posed_min(shape,bone,point,rotation):
        m=rotation.to_matrix().to_4x4();m.translation=point;delta=m@rest[bone].matrix_local.inverted();points=shape@np.asarray(delta)[:3,:3].T+np.asarray(delta)[:3,3]
        return float(points[:,2].min())
    def evaluate(x,readback=False,residual=False):
        shift=Vector(x[:3]);targets={n:p.copy()for n,p in goals.items()};rotations=dict(orientations)
        errors=list(math.sqrt(.15)*x[:3])+list(math.sqrt(.8)*x[3:5])+list(math.sqrt(2)*x[5:9])+list(math.sqrt(2)*x[9:15])+list(math.sqrt(.4)*x[15:]);report={}
        for side,at in (('l',3),('r',4)):
            f=feet[side];foot='foot_'+side;q=Quaternion(f['axis'],float(x[at]))@f['q'];m=q.to_matrix().to_4x4();m.translation=f['a'];delta=m@rest[foot].matrix_local.inverted()
            points=f['shape']@np.asarray(delta)[:3,:3].T+np.asarray(delta)[:3,3]
            weight=(foot_contact_weights or {}).get(side,1.)
            # In low posture the captured human toe and the much longer EVA
            # boot cannot both keep a fixed ankle and a fixed whole sole.
            # Fit each physical ankle jointly with pelvis and boot rollover.
            offset=Vector(x[9:12] if side=='l' else x[12:15])
            targets[foot]=f['a']+offset;rotations[foot]=q
        for side,at in (('l',15),('r',18)):
            hand='hand_'+side;targets[hand]+=Vector(x[at:at+3]);weight=(hand_contact_weights or {}).get(side,0.)
        for i,(name,l)in enumerate(limbs.items()):
            h=l['h']+shift;a=targets[l['end']];u,v=l['lengths'];vector=a-h;distance=vector.length;direction=vector.normalized();reach=max(abs(u-v)+1e-5,min(u+v-1e-5,distance))
            errors.append(math.sqrt(10000)*(distance-reach));along=(u*u-v*v+reach*reach)/(2*reach);height=math.sqrt(max(0,u*u-along*along))
            # Floor/reach inequalities alone made F178's bent swing knee
            # become almost straight at F179 (63 deg versus source26 deg).
            # Preserve the measured source hinge through its actual target
            # sphere distance. This couples pelvis/ankle contact geometry;
            # it is not a post-bake angle clamp or a pose gain.
            errors.append(math.sqrt(80 if name.startswith('leg_') else 20)*(reach-l['captured_reach']))
            plane=l['axis'].rotation_difference(direction)@l['bend'];plane-=direction*plane.dot(direction);plane.normalize();plane=Quaternion(direction,float(x[5+i]))@plane
            k=h+direction*along+plane*height;end=h+direction*reach
            qu=(l['k']-l['h']).normalized().rotation_difference((k-h).normalized())@fk[l['upper']].to_quaternion()
            ql=(l['a']-l['k']).normalized().rotation_difference((end-k).normalized())@fk[l['lower']].to_quaternion()
            low=[posed_min(limb_geometry[l['upper']],l['upper'],h,qu),posed_min(limb_geometry[l['lower']],l['lower'],k,ql)]
            bearing=posed_min(l['support_patch'],l['lower'],k,ql)
            errors.extend((math.sqrt(5000000)*max(0.,.015-min(low)),math.sqrt(400*l['support'])*(bearing-.015)))
            side=name[-1];effector=l['end']
            if name.startswith('leg_'):
                shape=feet[side]['shape'];patch=shape[feet[side]['patch_ids']];weight=(foot_contact_weights or {}).get(side,1.)
                # Captured ankle FK belongs to its actual lower limb. A
                # separate world orientation limiter made source3deg become
                # local42deg at F205 when this IK changed the shin direction.
                # Transport the captured relative ankle with the solved shin;
                # authored boot rollover remains a separate anatomical DOF.
                parent_change=ql@fk[l['lower']].to_quaternion().inverted()
                rotations[effector]=parent_change@rotations[effector]
                posed=rotations[effector].to_matrix().to_4x4();posed.translation=end
                delta=posed@rest[effector].matrix_local.inverted()
                real=shape@np.asarray(delta)[:3,:3].T+np.asarray(delta)[:3,3]
                f=feet[side]
                actual_patch=Vector(real[f['index']]).lerp(Vector(real[f['front_index']]),f['toe_authority'])
                errors.extend(math.sqrt(400*weight)*(np.asarray(actual_patch)[:2]-np.asarray(f['patch'])[:2]))
            else:
                shape=limb_geometry[effector];patch=shape;weight=(hand_contact_weights or {}).get(side,0.)
            # FK uses the sphere-clamped endpoint when a goal is unreachable.
            # Evaluate that actual submitted boot/hand, never the ideal goal.
            bottom=posed_min(shape,effector,end,rotations[effector]);patch_min=posed_min(patch,effector,end,rotations[effector])
            if name.startswith('leg_'):patch_min=(1-feet[side]['toe_authority'])*bottom+feet[side]['toe_authority']*patch_min
            errors.extend((math.sqrt(5000000)*max(0.,.015-bottom),math.sqrt(400*weight)*(patch_min-.015)))
            report[name]=dict(upper=h,joint=k,end=end,upper_rotation=qu,lower_rotation=ql,minima=low,reach_error=distance-reach,source_contact_weight=l['support'],proximal_support_minimum_z=bearing,
                              actual_flexion_degrees=math.degrees(math.acos(max(-1.,min(1.,((k-h).normalized()).dot((end-k).normalized()))))),
                              captured_flexion_degrees=l['captured_flexion_degrees'],captured_hinge_reach_blocks=l['captured_reach'],
                              actual_effector_minimum_z=bottom,actual_effector_patch_minimum_z=patch_min,
                              foot_contact_mode=feet[side]['contact_mode'] if name.startswith('leg_') else None)
        for bone,alias,shape in body_geometry:
            m=fk[alias].copy();m.translation+=shift;delta=m@rest[alias].matrix_local.inverted();points=shape@np.asarray(delta)[:3,:3].T+np.asarray(delta)[:3,3]
            errors.append(math.sqrt(5000000)*max(0.,.015-float(points[:,2].min())))
        if previous is not None:errors.extend(math.sqrt(1.5)*(x-previous))
        errors=np.asarray(errors);cost=float(errors@errors)
        if residual:return errors
        return (cost,shift,targets,rotations,report)if readback else cost
    x=np.zeros(21)if previous is None else np.asarray(previous).copy();best=evaluate(x)
    # Coupled steps can cross a narrow feasible corridor that single-variable
    # moves cannot enter. Damped least squares acts on actual surface/reach
    # residuals; captured knee-plane variables remain fixed at zero.
    active=[0,1,2,3,4,6,8,9,10,11,12,13,14,15,16,17,18,19,20];damping=.01
    def intersection(value,lower,upper,world_lower,world_upper):
        low=np.maximum(lower,world_lower);high=np.minimum(upper,world_upper)
        # Empty intersections expose a physically infeasible rate window.
        # Keep the anatomical control bounds; no out-of-range hidden repair.
        return np.where(low<=high,np.clip(value,np.minimum(low,high),np.maximum(low,high)),np.clip(value,lower,upper))
    def bound(trial):
        trial[:3]=np.clip(trial[:3],-8,8);trial[3:5]=np.clip(trial[3:5],-math.pi/2,math.pi/2)
        trial[5:9]=np.clip(trial[5:9],-math.pi/6,math.pi/6);trial[9:]=np.clip(trial[9:],-5,5)
        trial[5]=trial[7]=0.
        if previous_pose is not None:
            # The capture baseline moves every frame. Bounding only the
            # correction x allowed a planted end to dive when that baseline
            # changed. Bound actual world goals/orientations before FK.
            pelvis_centre=np.asarray(previous_pose['pelvis_world'])-np.asarray(fk['pelvis'].translation)
            trial[:3]=intersection(trial[:3],-8,8,pelvis_centre-[8,8,2],pelvis_centre+[8,8,2])
            trial[5:9]=np.clip(trial[5:9],previous[5:9]-.12,previous[5:9]+.12)
            # Limit the authored ankle rollover relative to captured FK, not
            # the performer's natural world rotation. Source21deg was being
            # capped to9deg at F205 while the parent moved35deg.
            trial[3:5]=np.clip(trial[3:5],previous[3:5]-.14,previous[3:5]+.14)
            base=goals
            for side,at in (('l',9),('r',12)):
                centre=np.asarray(previous_pose['goals']['foot_'+side])-np.asarray(base['foot_'+side]);trial[at:at+3]=intersection(trial[at:at+3],-5,5,centre-[8,8,2],centre+[8,8,2])
            for side,at in (('l',15),('r',18)):
                centre=np.asarray(previous_pose['goals']['hand_'+side])-np.asarray(goals['hand_'+side]);trial[at:at+3]=intersection(trial[at:at+3],-5,5,centre-[8,8,2],centre+[8,8,2])
        return trial
    for iteration in range(28):
        if iteration==0:x=bound(x);best=evaluate(x)
        error=evaluate(x,residual=True);columns=[]
        for i in active:
            step=.002 if i<3 or i>=9 else .001;trial=x.copy();trial[i]+=step;columns.append((evaluate(trial,residual=True)-error)/step)
        jacobian=np.asarray(columns).T
        try:delta=np.linalg.solve(jacobian.T@jacobian+np.eye(len(active))*damping,-jacobian.T@error)
        except np.linalg.LinAlgError:break
        improved=False
        for amount in (1.,.5,.25,.125):
            trial=x.copy();trial[active]+=delta*amount;trial=bound(trial)
            value=evaluate(trial)
            if value<best:x=trial;best=value;damping=max(1e-5,damping*.5);improved=True;break
        if not improved:damping*=10
        if np.linalg.norm(delta)<1e-4 or damping>1e6:break
    # Deterministic coordinate descent, warm-started by the previous actual
    # solution. Every search evaluates mesh, reach, source plane and support.
    for spatial,angular in ((2.,.35),(1.,.175),(.5,.0875),(.25,.04),(.125,.02)):
        steps=[spatial]*3+[angular]*6+[spatial]*12
        for sweep in range(3):
            changed=False
            for i,step in enumerate(steps):
                # The two captured knee planes are observable. Do not trade
                # their anatomical direction for numerical floor clearance.
                # Fit the pelvis and the actual rolling boot contact instead.
                if i in (5,7):continue
                for sign in (-1,1):
                    trial=x.copy();trial[i]+=sign*step
                    # Bounds limit physical adaptation, not a pose multiplier.
                    if np.max(np.abs(bound(trial.copy())-trial))>1e-6:continue
                    value=evaluate(trial)
                    if value<best:x=trial;best=value;changed=True
            if not changed:break
    value,shift,targets,rotations,report=evaluate(x,True)
    return dict(parameters=x,shift=shift,goals=targets,orientations=rotations,limbs=report,cost=value,pelvis_world=fk['pelvis'].translation+shift)
