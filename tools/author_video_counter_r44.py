"""Paired counter authored from measured world trajectories, not joint copying.

The published 24-joint video estimate supplies the whole-body timing and limb
directions. EVA joint lengths, sockets, palm shape and boot sole are measured
independently. TV contact roles add the opponent, parry, impulse and recoil.
"""
from pathlib import Path
import math,json
import bpy
import numpy as np
from mathutils import Matrix,Quaternion,Vector

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/video_source/boxing'
SOURCES={name:np.load(SRC/(name+'_fk.npz'),allow_pickle=False)for name in('data6','data3','data7')}
Q90=Quaternion(Vector((0,0,1)),math.pi/2)


def ease(u):return(max(0,min(1,u)))**2*(3-2*max(0,min(1,u)))


def lerpkeys(keys,t):
    if t<=keys[0][0]:return float(keys[0][1])
    for(a,p),(b,q)in zip(keys,keys[1:]):
        if t<=b:return p+(q-p)*ease((t-a)/(b-a))
    return float(keys[-1][1])


def quat(yaw=0,pitch=0,roll=0):return Quaternion(Vector((0,0,1)),math.radians(yaw))@Quaternion(Vector((1,0,0)),math.radians(pitch))@Quaternion(Vector((0,1,0)),math.radians(roll))


def sample(name,index):
    source=SOURCES[name];p=source['positions'];r=source['rotations'];index=max(0,min(float(index),len(p)-1));a=int(index);b=min(a+1,len(p)-1);u=index-a
    points={str(n):Vector(p[a,i]*(1-u)+p[b,i]*u)for i,n in enumerate(source['names'])}
    rotations={str(n):Matrix(r[a,i].tolist()).to_quaternion().slerp(Matrix(r[b,i].tolist()).to_quaternion(),u)for i,n in enumerate(source['names'])}
    return points,rotations


def target_matrix(point,rotation):
    matrix=rotation.to_matrix().to_4x4();matrix.translation=point;return matrix


def hand_frame(data,rig,side,direction,normal):
    """Map anatomical palm axes; SMPL T-hand and EVA A-hand differ ~55 deg."""
    rest=rig.data.bones;hand=rest['hand_'+side]
    if 'finger_middle_'+side in rest:
        own_long=(rest['finger_middle_'+side].head_local-hand.head_local).normalized();across=(rest['finger_little_'+side].head_local-rest['finger_index_'+side].head_local).normalized();own_normal=across.cross(own_long).normalized()
        if(rest['finger_middle_tip_'+side].head_local-rest['finger_middle_'+side].head_local).dot(own_normal)<0:own_normal.negate()
    else:
        own_long=Vector(data['hands'][side]['offset']).normalized();own_normal=Vector((0,0,1));own_normal-=own_long*own_normal.dot(own_long);own_normal.normalize()
    direction=direction.normalized();normal-=direction*normal.dot(direction);normal.normalize();own_normal-=own_long*own_normal.dot(own_long);own_normal.normalize()
    origin=Matrix((own_long.cross(own_normal).normalized(),own_long,own_normal)).transposed();target=Matrix((direction.cross(normal).normalized(),direction,normal)).transposed()
    delta=target.to_quaternion()@origin.to_quaternion().inverted()
    return delta@hand.matrix_local.to_quaternion()


def blend_wrist_arc(shoulder,start_surface,end_surface,offset,w):
    """A release circles the shoulder; a straight chord folded the elbow."""
    if w<=0:return start_surface
    if w>=1:return end_surface
    a=start_surface-offset-shoulder;b=end_surface-offset-shoulder
    if min(a.length,b.length)<.01:return start_surface.lerp(end_surface,w)
    turn=a.normalized().rotation_difference(b.normalized());direction=Quaternion().slerp(turn,w)@a.normalized()
    return shoulder+direction*(a.length*(1-w)+b.length*w)+offset


def key(obj,frame):
    for path in('location','rotation_quaternion','scale'):obj.keyframe_insert(path,frame=frame)


def configure_fingers(data,rig,controls):
    # Finger IK with an unconstrained endpoint had no anatomical flexion plane.
    # Explicit measured knuckle axes now own flexion/opposition as a whole fist.
    for bone in rig.pose.bones:
        if bone.name.startswith('finger_'):
            for c in list(bone.constraints):bone.constraints.remove(c)
            bone.rotation_mode='QUATERNION'
    rig['fist_scope']='Measured palm-long/across/normal frame; three connected phalanges and opposing thumb; independently authored because video SMPL has no fingers.'
    if data['key']=='sachiel':
        # Sachiel's authored humerus/rest roll differs from the EVA roll. A
        # copied positive-only EVA hinge bound clipped a valid 25 m reach by
        # 1.7 m. Keep the single flexion axis, permit its measured signed range.
        for side in('l','r'):rig.pose.bones['forearm_'+side].ik_min_x=-2.8


def fist(data,rig,controls,side,closed,frame):
    rest=rig.data.bones;hand=rest['hand_'+side];delta=controls['hand_'+side].rotation_quaternion@hand.matrix_local.to_quaternion().inverted()
    root=hand.head_local;long=(rest['finger_middle_'+side].head_local-root).normalized() if 'finger_middle_'+side in rest else Vector((0,0,-1))
    if 'finger_little_'+side in rest:
        across=(rest['finger_little_'+side].head_local-rest['finger_index_'+side].head_local).normalized();normal=across.cross(long).normalized()
        curl=rest['finger_middle_tip_'+side].head_local-rest['finger_middle_'+side].head_local
        if curl.dot(normal)<0:normal.negate()
    else:normal=Vector((0,1,0));across=normal.cross(long)
    parent_world={'hand_'+side:controls['hand_'+side].rotation_quaternion}
    for digit in('index','middle','ring','little','thumb'):
        chain=[f'finger_{digit}{suffix}_{side}'for suffix in('','_tip','_distal')];chain=[n for n in chain if n in rest]
        for j,name in enumerate(chain):
            b=rest[name];original=(b.tail_local-b.head_local).normalized()
            if digit=='thumb':
                # The thumb lies over index/middle PIP, across the palm plane.
                across_to_index=(rest['finger_index_'+side].head_local-b.head_local).normalized()
                aim=(across_to_index*.78+normal*.62-long*.25).normalized() if j==0 else(across_to_index*.25-long*.85+normal*.4).normalized()
            else:
                angle=math.radians((48,140,190)[min(j,2)]);aim=(long*math.cos(angle)+normal*math.sin(angle)).normalized()
            direction=original.lerp(aim,closed).normalized();change=original.rotation_difference(direction)
            wanted=delta@change@b.matrix_local.to_quaternion();parent=b.parent.name
            parent_rotation=parent_world.get(parent,controls['hand_'+side].rotation_quaternion)
            baseline=parent_rotation@rest[parent].matrix_local.to_quaternion().inverted()@b.matrix_local.to_quaternion()
            pose=rig.pose.bones[name];pose.rotation_quaternion=baseline.inverted()@wanted;pose.keyframe_insert('rotation_quaternion',frame=frame);parent_world[name]=wanted


def motion(data,rig,controls,hips,frame,body_only=False):
    t=(frame-1)/30;hero=data['key']=='1';yaw=0 if hero else 180;facing=quat(yaw);rest=rig.data.bones
    # Source frame 30→35 is a .167 s rising counter, preserving its real burst.
    phase=lerpkeys([(0,72),(.24,73),(.5,74),(.84,75),(1.03,77),(1.13,80),(1.31,86),(1.55,93),(2.15,110),(3.1,132),(3.6,132)],t) if hero else lerpkeys([(0,45),(.22,55),(.38,63),(.6,73),(.8,80),(1.13,84),(3.6,100)],t)
    points,rotations=sample('data7'if hero else'data3',phase);initial,initial_rotations=sample('data7'if hero else'data3',72 if hero else 45)
    window_forward=initial_rotations['Pelvis']@Vector((1,0,0));window_rebase=Quaternion(Vector((0,0,1)),math.pi/2-math.atan2(window_forward.y,window_forward.x));source_facing=facing@window_rebase
    if hero:
        # Match a forward right cross, not data6's lateral rising hook. Its
        # measured 77→79 hand stroke supplies the task frame. One transform
        # carries body, limb directions, wrist planes and boots together.
        a,_=sample('data7',77);b,_=sample('data7',79);stroke=window_rebase@((b['R_Hand']-b['Pelvis'])-(a['R_Hand']-a['Pelvis']));task=Quaternion(Vector((0,0,1)),math.pi/2-math.atan2(stroke.y,stroke.x));source_facing=source_facing@task
    source_hips=(points['L_Hip']+points['R_Hip'])*.5;initial_hips=(initial['L_Hip']+initial['R_Hip'])*.5
    source_leg=sum(np.linalg.norm(SOURCES['data7'if hero else'data3']['offset'][i])for i in(2,3));leg_scale=sum(data['joints']['leg_l']['lengths'])/source_leg
    source_delta=points['Pelvis']-initial['Pelvis'];base=Vector((0,-3 if hero else 29,0))
    # One committed entry step precedes the load. Counter is an upper-body
    # rotation transmitted through a stance, not a drifting arm-only trajectory.
    if hero:base.y+=lerpkeys([(0,0),(.35,4),(.82,4.5),(1.13,6.5),(1.4,7),(2.2,6),(3.6,6)],t)
    else:base.y+=lerpkeys([(0,0),(1.13,0),(1.25,1.0),(1.5,5),(1.83,10),(2.05,11),(3.6,11)],t)
    # The paired stage owns horizontal COM travel and the world footfalls.
    # Adding reconstructed global video travel here pulled the retreating hips
    # laterally across those independently anchored feet.
    base.x=lerpkeys([(0,0),(.36,-1.0),(.9,-1.8),(1.13,.5),(1.4,1.0),(2.2,0),(3.6,0)],t)if hero else lerpkeys([(0,0),(1.13,0),(1.5,.8),(2.1,1.2),(3.6,0)],t)
    lowered=-3.5 if hero else-2.2
    pelvis_position=base+facing@hips+Vector((0,0,lowered+(source_hips.z-initial_hips.z)*leg_scale))
    if hero:pelvis_position.z+=lerpkeys([(0,0),(.24,-1),(.72,-4),(.94,-5.5),(1.13,0),(1.27,.4),(1.45,0),(3.6,0)],t)
    if not hero:pelvis_position.z+=lerpkeys([(0,0),(1.13,0),(1.3,-2),(1.54,-1.3),(1.83,-.3),(2.35,0),(3.6,0)],t)
    body={name:source_facing@rotations[source]@Q90.inverted()for name,source in(('pelvis','Pelvis'),('chest','Chest'),('head','Head'))}
    # Authored line of action and contact recoil are explicit paired stage
    # controls. The source's leg/arm directions are solved against these actual
    # displaced sockets, so changes propagate through the whole silhouette.
    if hero:
        # Source pelvis/chest already carry the measured counter rotation.
        # Adding a second authored yaw turned the chest ~68 degrees away from
        # the contact line. Keep a single twist owner and author compression.
        body['pelvis']=body['pelvis']@quat(0,-5)
        body['chest']=body['chest']@quat(0,lerpkeys([(0,-10),(.6,-16),(.94,-22),(1.13,-14),(1.36,-19),(2.2,-8),(3.6,-7)],t))
    else:
        # V10 had two twist owners on the receiver as well: the raw probing
        # source and the paired recoil. Its pelvis turned across its world
        # stance, then remained depressed during both recovery footfalls.
        # Receiver's designed compression/recovery now owns its body frame;
        # the published take remains the incoming hand/bend/timing reference.
        body['pelvis']=facing@quat(lerpkeys([(0,-3),(1.13,-3),(1.3,-10),(1.54,-8),(1.83,-4),(3.6,-3)],t),lerpkeys([(0,-2),(1.13,-2),(1.3,5),(1.54,2),(1.83,-2),(3.6,-2)],t))
        body['chest']=facing@quat(lerpkeys([(0,-5),(.4,7),(.65,9),(.95,-5),(1.13,-5),(1.3,-20),(1.54,-14),(1.83,-7),(3.6,-5)],t),lerpkeys([(0,-8),(1.13,-8),(1.28,20),(1.47,15),(1.83,-4),(2.35,-8),(3.6,-8)],t))
        body['head']=facing@quat()
    controls['pelvis'].matrix_world=target_matrix(pelvis_position,body['pelvis']@rest['pelvis'].matrix_local.to_quaternion())
    for part in('chest','head'):controls[part].rotation_quaternion=body[part]@rest[part].matrix_local.to_quaternion()
    # Evaluate body sockets before assigning limb world-space controls.
    bpy.context.view_layer.update();solved=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    if body_only:return base,yaw
    other=bpy.data.objects['sachiel_AUTHOR'if hero else'eva_unit01_AUTHOR'].evaluated_get(bpy.context.evaluated_depsgraph_get());look=other.pose.bones['head'].head-solved.pose.bones['head'].head
    # Captured facial orientation is a source reference; shared opponent gaze
    # owns the exchange. Keep independent head/chest roles while aiming at the
    # actual current head location supplied by the two-pass body preparation.
    if look.length>.1:
        look_yaw=-math.degrees(math.atan2(look.x,look.y));look_pitch=math.degrees(math.atan2(look.z,math.hypot(look.x,look.y)))
        delayed=lerpkeys([(0,0),(1.2,0),(1.37,15),(1.66,8),(2.25,0),(3.6,0)],t)if not hero else 0
        controls['head'].rotation_quaternion=quat(look_yaw,look_pitch+delayed)@rest['head'].matrix_local.to_quaternion();bpy.context.view_layer.update();solved=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    chest_matrix=solved.pose.bones['chest'].matrix@rest['chest'].matrix_local.inverted();pelvis_matrix=solved.pose.bones['pelvis'].matrix@rest['pelvis'].matrix_local.inverted()
    for side,source_side in(('l','L'),('r','R')):
        # Measured toe-to-ankle offset also applies in the opening stance:
        # the receiver's rear toe at local -7 placed its ankle 11.65 behind
        # the hip. Local -4 gives a reachable ankle without a root height fix.
        sign=-1 if side=='l'else 1;toe=Vector(data['toes'][side]['rest']);toe.x=sign*(5.8 if hero else 6.5);toe.y=(7 if side=='l'else-3)if hero else(-4 if side=='l'else 6)
        toe=facing@toe+Vector((0,-3 if hero else 29,0))
        # Video-derived source toes remain recorded in the A comparison. B
        # owns world anchors through its measured boots and authored footfalls;
        # root translation is not added to a planted toe target.
        # Deliberate entry/recoil footfalls replace source camera-space drift.
        if hero:
            start,end,travel=(.02,.32,4)if side=='l'else(1.26,1.66,7)
        # Retreat moves the forward right foot first. Moving the rear left
        # first compressed both knees into a crossing silhouette in v9.
        # The left/rear sole has a 4.4-block ankle offset. A 13-block
        # backward toe step placed its ankle 26.13 from the hip, beyond the
        # measured 25.245-block chain. Design a shorter rear follow step;
        # do not pull the whole pelvis down to compensate for an unreachable
        # independently chosen floor point.
        else:start,end,travel=(1.54,1.83,-10)if side=='l'else(1.23,1.5,-13)
        u=max(0,min(1,(t-start)/(end-start)));toe+=facing@Vector((0,travel*ease(u),0));swing=math.sin(math.pi*u)*(2.3 if hero else 3.1)if 0<u<1 else 0
        # Feet share the body's task frame for placement, but do not inherit
        # camera-estimate ankle yaw drift during an authored planted stance.
        source_orientation=source_facing@rotations[source_side+'_Ankle']@Q90.inverted()
        foot_euler=source_orientation.to_euler('XYZ');orientation=quat(yaw+sign*9,math.degrees(foot_euler.x)*.45,math.degrees(foot_euler.y)*.3)
        if hero and side=='r':orientation=orientation@quat(0,lerpkeys([(0,0),(.66,-7),(.93,-22),(1.13,-31),(1.35,-15),(1.64,0),(3.6,0)],t))
        foot_points=data['toes'][side]['vertices'];pivot=Vector(data['joints']['leg_'+side]['end']);patch=Vector(data['toes'][side]['offset']);low=min((orientation@(Vector(p)-pivot)).z for p in foot_points)
        toe.z=(orientation@patch).z-low+swing
        controls['foot_'+side].matrix_world=target_matrix(toe,orientation)
        hip_world=pelvis_matrix@Vector(data['joints']['leg_'+side]['upper']);source_knee=points[source_side+'_Knee']-source_hips;pole=hip_world+facing@Vector((sign*5,13,-15));pole.x+=source_knee.x*5
        controls['pole_leg_'+side].location=pole
        shoulder_world=chest_matrix@Vector(data['joints']['arm_'+side]['upper']);v1=points[source_side+'_Elbow']-points[source_side+'_Shoulder'];v2=points[source_side+'_Wrist']-points[source_side+'_Elbow'];lengths=data['joints']['arm_'+side]['lengths'];desired_elbow=shoulder_world+(source_facing@v1.normalized())*lengths[0];pivot_hand=desired_elbow+(source_facing@v2.normalized())*lengths[1]
        hand_direction=source_facing@(points[source_side+'_Hand']-points[source_side+'_Wrist']).normalized();palm_normal=source_facing@rotations[source_side+'_Wrist']@Vector((0,0,-1))
        hand_q=hand_frame(data,rig,side,hand_direction,palm_normal)
        guard_q=hand_frame(data,rig,side,facing@Vector((0,.3,1)),facing@Vector((0,1,-.3)))
        # The guard is built for this actual long-arm/shoulder silhouette.
        # The published boxing limb remains the stroke/bend reference, while
        # a bent forearm returns each hand to its own chest-side guard.
        stroke=ease((t-1.0)/.13)*(1-ease((t-1.18)/.25))if hero and side=='r'else 0
        hand_q=guard_q.slerp(hand_q,stroke)
        surface_offset=hand_q@rest['hand_'+side].matrix_local.to_quaternion().inverted()@Vector(data['hands'][side]['offset']);goal=pivot_hand+surface_offset
        guard=shoulder_world+facing@Vector((-sign*4,9,1 if hero else-7))
        guard_elbow=shoulder_world+facing@Vector((sign*3,3,-12))
        goal=guard
        desired_elbow=guard_elbow.lerp(desired_elbow,stroke)
        # The lead hand meets the actual submitted incoming hand surface, then
        # redirects outwards instead of leaving both actors' arms extended.
        if not hero and side=='r':
            common=Vector((lerpkeys([(.3,-10),(.6,-12),(.8,-12.5)],t),lerpkeys([(.3,13),(.6,9),(.8,9)],t),lerpkeys([(.3,47),(.6,46),(.8,44)],t)))
            w=ease((t-.3)/.15)*(1-ease((t-.8)/.23));goal=blend_wrist_arc(shoulder_world,goal,common,surface_offset,w)
        if hero and side=='l':
            incoming=bpy.data.objects['CONTACT_incoming'].location.copy()
            w=ease((t-.38)/.18)*(1-ease((t-.70)/.38));goal=blend_wrist_arc(shoulder_world,goal,incoming,surface_offset,w)
        if hero and side=='r':
            target=bpy.data.objects['CONTACT_chest'];point=target.location.copy()
            if t>=1.13 and'impact_point'not in target:target['impact_point']=list(point)
            if t>1.17 and'impact_point'in target:point=Vector(target['impact_point'])+Vector((-2.5*ease((t-1.17)/.16),3.0*ease((t-1.17)/.16),1.4*ease((t-1.17)/.16)))
            # Short contact and immediate recovery, with the original source
            # burst as the timing reference. No prolonged straight-arm hold.
            w=ease((t-1.0)/.13)*(1-ease((t-1.18)/.25));goal=goal.lerp(point,w)
            # Knuckles face along the rising punch; the wrist/forearm plane
            # follows the source while the actual palm controls stay rigid.
        controls['hand_'+side].matrix_world=target_matrix(goal,hand_q)
        line=goal-shoulder_world;projection=shoulder_world+line*max(0,min(1,(desired_elbow-shoulder_world).dot(line)/max(1e-8,line.length_squared)));bend=desired_elbow-projection
        if bend.length<.01:bend=facing@Vector((sign,0,-1))
        source_pole=desired_elbow+bend.normalized()*8
        guard_pole=shoulder_world+facing@Vector((sign*16,-4,-8))
        controls['pole_arm_'+side].location=guard_pole.lerp(source_pole,stroke)
        closed=.98 if hero else lerpkeys([(0,.62),(.3,.88),(.8,.94),(1.4,.52),(2.2,.75),(3.6,.82)],t)
        fist(data,rig,controls,side,closed,frame)
    for obj in controls.values():key(obj,frame)
    rig['source_take']='data7 video right cross, task frame from actual strike velocity'if hero else'data3 video guard/probing hand';rig['source_phase_frame']=float(phase);rig['window_heading_rebase_radians']=window_rebase.angle
    return base,yaw
