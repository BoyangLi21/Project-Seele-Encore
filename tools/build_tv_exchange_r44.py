"""Blender-native paired blocking: world controls, actual joints and IK bake.

Execute only with Blender --background. The author/evaluator never initializes
a GPU renderer. Beauty review explicitly uses Cycles CPU and two threads.
"""
from pathlib import Path
import argparse,json,math,sys
from types import SimpleNamespace
import bpy
import numpy as np
from mathutils import Matrix,Quaternion,Vector
sys.path.insert(0,str(Path(bpy.utils.system_resource('SCRIPTS'))/'addons_core'))
from rigify.rigs.limbs.limb_rigs import BaseLimbRig

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/blocking_v1');ap.add_argument('--design',choices=('blocking_v1','video_counter_v2'),default='blocking_v1')
ap.add_argument('--readback',action='store_true');ap.add_argument('--render-frame',type=int);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]if'--'in sys.argv else[])
OUT=args.out.resolve();DATA=json.loads((OUT/'fixture.json').read_text('utf8'));FPS=30;END=109 if args.design=='video_counter_v2' else 241
C=Matrix(((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)));S=5/16
M=C.copy();M[0][0]*=S;M[1][2]*=S;M[2][1]*=S;MI=M.inverted()


def ease(x):
    x=max(0,min(1,x));return x*x*(3-2*x)


def curve(keys,t):
    if t<=keys[0][0]:return np.asarray(keys[0][1],float)
    times=np.asarray([k[0]for k in keys]);values=np.asarray([k[1]for k in keys],float);slopes=np.diff(values,axis=0)/np.diff(times).reshape((-1,)+(1,)*(values.ndim-1));tangents=np.zeros_like(values)
    for j in range(1,len(keys)-1):
        left,right=slopes[j-1],slopes[j];same=left*right>0;h0=times[j]-times[j-1];h1=times[j+1]-times[j]
        denominator=np.divide(2*h1+h0,left,out=np.zeros_like(left),where=same)+np.divide(h1+2*h0,right,out=np.zeros_like(right),where=same)
        tangents[j]=np.divide(3*(h0+h1),denominator,out=np.zeros_like(left),where=same)
    for j,((a,p),(b,q))in enumerate(zip(keys,keys[1:])):
        if t<=b:
            u=(t-a)/(b-a);return (2*u**3-3*u*u+1)*values[j]+(u**3-2*u*u+u)*(b-a)*tangents[j]+(-2*u**3+3*u*u)*values[j+1]+(u**3-u*u)*(b-a)*tangents[j+1]
    return np.asarray(keys[-1][1],float)


def scalar(keys,t):return float(curve(keys,t))


def transform(location,rotation):
    result=rotation.to_matrix().to_4x4();result.translation=Vector(location);return result


def rotation(yaw,pitch=0,roll=0):
    return Quaternion(Vector((0,0,1)),math.radians(yaw))@Quaternion(Vector((1,0,0)),math.radians(pitch))@Quaternion(Vector((0,1,0)),math.radians(roll))


def key(obj,frame):
    for path in('location','rotation_quaternion','scale'):obj.keyframe_insert(path,frame=frame)


def empty(name):
    obj=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(obj);obj.rotation_mode='QUATERNION';obj.empty_display_type='SPHERE';obj.empty_display_size=.7;obj.hide_render=True;return obj


def material(name,texture):
    m=bpy.data.materials.new(name);m.use_nodes=True;nodes=m.node_tree.nodes;shader=nodes.get('Principled BSDF');shader.inputs['Roughness'].default_value=.75
    tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(texture,check_existing=True);tex.image.pack();m.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color']);return m


def deform_rig(data):
    name=data['name'];arm=bpy.data.armatures.new(name+'_DEFORM');rig=bpy.data.objects.new(name+'_DEFORM',arm);bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for row in data['bones']:
        bone=arm.edit_bones.new(row['name']);bone.head=row['head'];bone.tail=Vector(row['head'])+Vector((0,0,.45));bone.use_connect=False
    for row in data['bones']:
        if row['parent']:arm.edit_bones[row['name']].parent=arm.edit_bones[row['parent']]
    bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False)
    mesh=bpy.data.meshes.new(name+'_actual_mesh');mesh.from_pydata(data['vertices'],[],data['faces']);mesh.update();obj=bpy.data.objects.new(name+'_actual_mesh',mesh);bpy.context.collection.objects.link(obj);obj.parent=rig
    uv=mesh.uv_layers.new(name='UVMap')
    for loop,value in zip(uv.data,data['uv']):loop.uv=(value[0],1-value[1])
    obj.data.materials.append(material(name+'_paint',data['texture']));groups=[obj.vertex_groups.new(name=b['name'])for b in data['bones']]
    for vertex,(ids,weights)in enumerate(zip(data['influences'],data['weights'])):
        for index,weight in zip(ids,weights):
            if weight>0:groups[index].add([vertex],weight,'REPLACE')
    modifier=obj.modifiers.new('Actual geometry armature','ARMATURE');modifier.object=rig;modifier.use_deform_preserve_volume=data['key']=='sachiel'
    rig['geometry_sha256']=data['geo_sha256'];rig['mesh_sha256']=data['mesh_sha256'];rig['skin_scope']=data['skin_scope'];return rig,obj


def motion_rig(data):
    heads={b['name']:Vector(b['head'])for b in data['bones']};arm=bpy.data.armatures.new(data['name']+'_AUTHOR');rig=bpy.data.objects.new(data['name']+'_AUTHOR',arm);bpy.context.collection.objects.link(rig)
    controls={};aliases={};bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    def bone(name,head,tail,parent=None,connected=False,hinge=False):
        b=arm.edit_bones.new(name);b.head=head;b.tail=tail;b.use_connect=connected
        if parent:b.parent=arm.edit_bones[parent]
        if hinge:
            axis=Vector((1,0,0));direction=(b.tail-b.head).normalized();axis-=direction*axis.dot(direction);axis.normalize();b.align_roll(axis);b.roll-=math.pi/2
        return b
    hips=(heads['leg_l']+heads['leg_r'])*.5;bone('pelvis',hips,hips+Vector((0,0,3)));bone('chest',heads['torso_upper'],heads['head'],'pelvis');bone('head',heads['head'],heads['head']+Vector((0,0,3)),'chest')
    aliases.update(root='pelvis',torso_lower='pelvis',torso_upper='chest',neck='chest',head='head')
    for side in('l','r'):
        for family,upper,lower,end,parent in[('arm','arm_','forearm_','hand_','chest'),('leg','leg_','shin_','foot_','pelvis')]:
            joint=data['joints'][family+'_'+side];bone(upper+side,joint['upper'],joint['joint'],parent,hinge=True);bone(lower+side,joint['joint'],joint['end'],upper+side,True,True)
            if family=='arm':
                fallback=heads[end+side]+Vector(data['hands'][side]['offset']);direction=(heads.get('finger_middle_'+side,fallback)-heads[end+side]).normalized();tail=heads[end+side]+direction*2
            else:tail=heads[end+side]+Vector((0,3,0))
            bone(end+side,joint['end'],tail,lower+side,True);aliases.update({upper+side:upper+side,lower+side:lower+side,end+side:end+side})
            aliases[('wrist_' if family=='arm' else 'ankle_')+side]=lower+side
        for digit in('index','middle','ring','little','thumb'):
            names=[f'finger_{digit}{suffix}_{side}'for suffix in('','_tip','_distal')];names=[n for n in names if n in heads]
            for i,name in enumerate(names):
                end=heads[names[i+1]] if i+1<len(names) else heads[name]+(heads[name]-heads[names[i-1]])*.6 if i else heads[name]+Vector((0,0,-1.2))
                bone(name,heads[name],end,'hand_'+side if i==0 else names[i-1],i>0);aliases[name]=name
            if 'finger_'+digit+'_axis_'+side in heads:aliases['finger_'+digit+'_axis_'+side]='hand_'+side
    bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False);rig.show_in_front=True
    for name in('pelvis','chest','head'):
        controls[name]=empty(data['name']+'_CTRL_'+name);constraint=rig.pose.bones[name].constraints.new('COPY_TRANSFORMS'if name=='pelvis'else'COPY_ROTATION');constraint.target=controls[name];constraint.owner_space='WORLD';constraint.target_space='WORLD'
    for side in('l','r'):
        for family,lower,end in[('arm','forearm_','hand_'),('leg','shin_','foot_')]:
            ctl=empty(data['name']+'_CTRL_'+end+side);target=empty(data['name']+'_IK_'+end+side);pole=empty(data['name']+'_POLE_'+family+'_'+side);controls[end+side]=ctl;controls['pole_'+family+'_'+side]=pole
            target.parent=ctl
            if family=='leg':target.location=-Vector(data['toes'][side]['offset'])
            else:
                rest=arm.bones[end+side].matrix_local;target.location=-(rest.to_3x3().inverted()@Vector(data['hands'][side]['offset']))
            constraint=rig.pose.bones[lower+side].constraints.new('IK');constraint.target=target;constraint.pole_target=pole;constraint.chain_count=2;constraint.use_stretch=False;constraint.iterations=120
            pair=[rig.pose.bones[('arm_'if family=='arm'else'leg_')+side],rig.pose.bones[lower+side]]
            elbow=BaseLimbRig.compute_elbow_vector(None,pair);helper=SimpleNamespace(params=SimpleNamespace(rotation_axis='x'),get_aux_axis=lambda b:b.z_axis)
            constraint.pole_angle=BaseLimbRig.compute_pole_angle(helper,pair,elbow)
            rig['rigify_pole_'+family+'_'+side]=constraint.pole_angle
            pose=rig.pose.bones[lower+side];pose.ik_stretch=0;pose.lock_ik_y=True;pose.lock_ik_z=True;pose.use_ik_limit_x=True
            # The actuator bone's signed X basis is measured after its roll
            # alignment. Here positive flexion bends the knee toward the pole;
            # applying the game's negative-X label directly locked it at .35.
            pose.ik_min_x=-.35;pose.ik_max_x=2.65 if family=='leg' else 2.8
            orient=rig.pose.bones[end+side].constraints.new('COPY_ROTATION');orient.target=ctl;orient.owner_space='WORLD';orient.target_space='WORLD'
            controls['target_'+end+side]=target
    for side in('l','r'):
        for digit in('index','middle','ring','little','thumb'):
            names=[f'finger_{digit}{suffix}_{side}'for suffix in('','_tip','_distal')];names=[n for n in names if n in arm.bones]
            if not names:continue
            target=empty(data['name']+'_GRASP_'+digit+'_'+side);target.parent=controls['hand_'+side];controls['finger_'+digit+'_'+side]=target
            constraint=rig.pose.bones[names[-1]].constraints.new('IK');constraint.target=target;constraint.chain_count=len(names);constraint.use_stretch=False;constraint.iterations=80
            for n in names:
                rig.pose.bones[n].ik_stretch=0
    for row in data['bones']:
        name=row['name']
        if name not in aliases:aliases[name]=aliases.get(row['parent'],'chest')
    aliases={name:value for name,value in aliases.items()if name in heads}
    rig['aliases_json']=json.dumps(aliases);rig['source']='New world target animation; actual measured elbow/knee centers, Blender native IK, no BVH rotations';return rig,controls,aliases,hips


def motion(data,rig,controls,hips,frame):
    if args.design=='video_counter_v2':
        from author_video_counter_r44 import motion as counter_motion
        return counter_motion(data,rig,controls,hips,frame)
    t=(frame-1)/FPS;hero=data['key']=='1';yaw=0 if hero else 180;facing=rotation(yaw);rest=rig.data.bones
    if hero:
        root_y=scalar([(0,-34),(.7,-32),(1.15,-27),(1.55,-17),(1.9,-7),(2.25,2),(2.55,6),(3.3,6),(3.68,8),(3.76,8),(3.95,10.2),(4.6,8.8),(8,8.8)],t)
        z=scalar([(0,-.35),(.7,-2.5),(1.15,-.2),(1.6,-.35),(2.1,-.2),(2.55,-1.6),(3.3,-.8),(3.68,-.5),(4.2,-.6),(8,-.35)],t)
        pelvis_yaw=scalar([(0,-4),(.7,-7),(1.2,0),(2.55,-10),(3.3,-12),(3.68,16),(4.05,8),(4.8,0),(8,0)],t)
        chest_yaw=scalar([(0,-4),(.7,-7),(1.2,0),(2.55,-14),(3.3,-20),(3.68,24),(4.05,10),(4.8,0),(8,0)],t)
        pelvis_pitch=scalar([(0,-1),(.7,-7),(1.25,-6),(2.55,-9),(3.3,-4),(3.68,-11),(3.76,-11),(3.95,-12),(4.6,-3),(8,-1)],t)
        pitch=scalar([(0,-5),(.7,-17),(1.25,-16),(2.25,-13),(2.55,-19),(3.3,-8),(3.68,-23),(3.76,-23),(3.95,-27),(4.6,-9),(8,-5)],t)
    else:
        root_y=scalar([(0,34),(3.72,34),(4.0,36),(4.35,38),(5.0,37.5),(8,37.5)],t);z=scalar([(0,-.3),(2.5,-1.0),(3.3,-.3),(3.67,-.3),(3.98,-2.1),(4.4,-.5),(8,-.5)],t)
        pelvis_yaw=scalar([(0,0),(2.5,-10),(3.08,8),(3.45,3),(3.67,3),(4.0,-12),(4.8,0),(8,0)],t);chest_yaw=scalar([(0,0),(2.5,-15),(3.08,12),(3.45,3),(3.67,3),(4.0,-18),(4.8,0),(8,0)],t)
        pelvis_pitch=scalar([(0,0),(3.08,-4),(3.67,-2),(3.8,5),(4.0,8),(4.8,-2),(8,0)],t)
        pitch=scalar([(0,-3),(2.55,-8),(3.08,-11),(3.45,-4),(3.67,-4),(3.80,12),(4.0,21),(4.4,9),(5.2,-3),(8,-3)],t)
    root=Vector((0,root_y,0));controls['pelvis'].matrix_world=transform(root+facing@hips+Vector((0,0,z)),rotation(yaw+pelvis_yaw,pelvis_pitch)@rest['pelvis'].matrix_local.to_quaternion())
    controls['chest'].rotation_quaternion=rotation(yaw+chest_yaw,pitch)@rest['chest'].matrix_local.to_quaternion()
    head_pitch=scalar([(0,0),(3.75,0),(4.0,hero and -1 or 16),(4.5,0),(8,0)],t)
    controls['head'].rotation_quaternion=rotation(yaw,head_pitch)@rest['head'].matrix_local.to_quaternion()
    for side in('l','r'):
        original=facing@Vector(data['toes'][side]['rest'])+Vector((0,-34 if hero else 34,0))
        if hero:
            steps=[(.82,1.17,-20),(1.58,1.92,3),(2.35,2.6,17.5)]if side=='l'else[(1.27,1.56,-9),(1.98,2.23,6),(4.2,4.65,12)]
        else:steps=[(3.88,4.27,original.y+8)]if side=='r'else[]
        toe=original.copy();pitch_foot=0
        for start,end,landing in steps:
            if t<start:break
            before=toe.copy()
            if t<end:
                u=(t-start)/(end-start);toe.y=before.y+(landing-before.y)*ease(u);toe.z=original.z+math.sin(math.pi*u)*(2.3 if hero else 2.0)
                pitch_foot=-28+(28+12)*ease(u*2) if u<.5 else 12*(1-ease((u-.5)*2));break
            toe.y=landing
        # Heel rises before each lift-off. Contact stays at the same toe point.
        for start,end,landing in steps:
            if start-.23<t<start:pitch_foot=-28*ease((t-(start-.23))/.23)
        if hero and side=='r' and 2.45<t<4.2:pitch_foot=scalar([(2.45,-15),(3.3,-24),(3.68,-34),(4.2,-28)],t)
        orientation=rotation(yaw,pitch_foot)
        patch=Vector(data['toes'][side]['offset']);points=np.asarray(data['toes'][side]['vertices']);pivot=Vector(data['joints']['leg_'+side]['end'])
        lowest=min((orientation@(Vector(point)-pivot)).z for point in points)
        # This is the physical sole bound for the chosen boot roll, not an
        # actor/root lift. Preserve the world toe X/Y and its swing height.
        toe.z+=((orientation@patch).z-lowest)-original.z
        controls['foot_'+side].location=toe;controls['foot_'+side].rotation_quaternion=orientation
        sign=-1 if side=='l' else 1
        controls['pole_leg_'+side].location=root+facing@Vector((sign*5,12,hips.z-14+z))
        controls['pole_arm_'+side].location=root+facing@Vector((sign*12,-2,hips.z+1+z))
    for side in('l','r'):
        sign=-1 if side=='l' else 1;shoulder=Vector(data['joints']['arm_'+side]['upper']);guard=root+facing@Vector((sign*9,8,hips.z+4))
        swing=math.sin(t*math.pi*3.2)*2*ease((t-1.15)/.15)*(1-ease((t-2.4)/.15))if hero else 0
        goal=guard+facing@Vector((0,swing,-abs(swing)*.3));direction=facing@Vector((0,.25,-.95));normal=facing@Vector((sign,0,0))
        if hero and side=='l':
            point=Vector((-7,24,45));w=ease((t-2.62)/.34)*(1-ease((t-3.35)/.55));goal=guard.lerp(point,w);direction=direction.lerp(Vector((0,0,1)),w);normal=normal.lerp(Vector((0,1,0)),w)
        if not hero and side=='r':
            point=Vector((-7,24,45));w=ease((t-2.55)/.53)*(1-ease((t-3.32)/.58));goal=guard.lerp(point,w);direction=direction.lerp(Vector((0,-1,0)),w);normal=normal.lerp(Vector((0,0,-1)),w)
        if hero and side=='r':
            # Independent NPC chest controller owns the real surface target.
            npc=bpy.data.objects.get('sachiel_AUTHOR')
            if npc:
                deps=bpy.context.evaluated_depsgraph_get();target=bpy.data.objects['CONTACT_chest'].evaluated_get(deps).matrix_world.translation.copy()
                marker=bpy.data.objects['CONTACT_chest']
                if t>=3.68 and 'impact_point'not in marker:marker['impact_point']=list(target)
                if t>3.75 and 'impact_point'in marker:
                    target=Vector(marker['impact_point'])+Vector((0,.75*ease((t-3.75)/.2),-.2*ease((t-3.75)/.2)))
                chamber=root+Vector((9,1,hips.z+5));wind=ease((t-3.08)/.25)*(1-ease((t-3.95)/.65));punch=ease((t-3.37)/.31)*(1-ease((t-3.95)/.50))
                goal=guard.lerp(chamber,wind).lerp(target,punch);direction=direction.lerp(Vector((0,1,0)),punch);normal=normal.lerp(Vector((0,0,-1)),punch)
        direction.normalize();normal-=direction*normal.dot(direction)
        if normal.length<1e-6:normal=Vector((0,1,0));normal-=direction*normal.dot(direction)
        normal.normalize();x=direction.cross(normal).normalized();orientation=Matrix((x,direction,normal)).transposed().to_quaternion()
        rest_hand=rest['hand_'+side].matrix_local.to_quaternion()
        # CTRL is the surface point; its IK child applies the palm-to-pivot
        # offset once. Subtracting it here too moved contact by half a metre.
        controls['hand_'+side].matrix_world=transform(goal,orientation)
        closure=scalar([(0,.32),(2.4,.25),(3.1,.65),(3.6,.94),(3.9,.94),(4.5,.4),(8,.3)],t)if hero else.35
        for digit in('index','middle','ring','little','thumb'):
            target=controls.get('finger_'+digit+'_'+side)
            if target is None:continue
            chain=[f'finger_{digit}{suffix}_{side}'for suffix in('','_tip','_distal')];chain=[n for n in chain if n in rest]
            tip=rest[chain[-1]].tail_local;local=rest_hand.inverted()@(tip-rest['hand_'+side].head_local)
            # End targets close around the measured palm, not an angle pasted
            # onto a different digit basis. Thumb opposes the index side.
            curled=Vector((local.x,.7,-1.0 if digit!='thumb'else-.6));target.location=local.lerp(curled,closure)
    for obj in controls.values():key(obj,frame)
    return root,yaw


def setup_scene():
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8;scene.render.threads_mode='FIXED';scene.render.threads=2;scene.render.resolution_x=1440;scene.render.resolution_y=810;scene.render.resolution_percentage=100;scene.render.fps=FPS;scene.frame_end=END
    scene.world=bpy.data.worlds.new('Review world');scene.world.color=(.2,.2,.2);scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.16,.18,.22,1)
    bpy.ops.mesh.primitive_plane_add(size=220);floor=bpy.context.object;floor.name='Contact floor';m=bpy.data.materials.new('Grey metre grid');m.use_nodes=True;nodes=m.node_tree.nodes;checker=nodes.new('ShaderNodeTexChecker');checker.inputs['Color1'].default_value=(.12,.14,.16,1);checker.inputs['Color2'].default_value=(.25,.28,.30,1);checker.inputs['Scale'].default_value=22;tex=nodes.new('ShaderNodeTexCoord');m.node_tree.links.new(tex.outputs['Generated'],checker.inputs['Vector']);m.node_tree.links.new(checker.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color']);floor.data.materials.append(m)
    for loc,power,size in[((-35,-25,100),90000,65),((50,40,85),65000,55)]:
        bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.shape='DISK';light.data.size=size;light.rotation_euler=(Vector((0,12,30))-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=(116,6,53));camera=bpy.context.object;camera.name='Fixed three-quarter full-body';camera.data.type='ORTHO';camera.data.ortho_scale=150;camera.rotation_euler=(Vector((0,8,36))-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
    scene.view_settings.view_transform='Standard';scene.render.image_settings.file_format='PNG';return scene


def multiply(q,p):
    return np.r_[q[0]*p[0]-q[1:]@p[1:],q[0]*p[1:]+p[0]*q[1:]+np.cross(q[1:],p[1:])]


def evaluated_surface(data,author,aliases,deps):
    index=data['chest_surface']['vertex'];point=Vector(data['vertices'][index]);solved=author.evaluated_get(deps);transforms=[]
    for slot,weight in zip(data['influences'][index],data['weights'][index]):
        name=data['bones'][slot]['name'];control=aliases[name];matrix=solved.pose.bones[control].matrix@author.data.bones[control].matrix_local.inverted()
        q=np.asarray(matrix.to_quaternion());dual=multiply(np.r_[0,list(matrix.translation)],q)*.5;transforms.append((weight,q,dual))
    reference=max(transforms,key=lambda row:row[0])[1];qsum=np.zeros(4);dsum=np.zeros(4)
    for weight,q,d in transforms:
        sign=1 if q@reference>=0 else-1;qsum+=q*weight*sign;dsum+=d*weight*sign
    norm=np.linalg.norm(qsum);qsum/=norm;dsum/=norm;dsum-=qsum*(qsum@dsum)
    position=Quaternion(qsum.tolist())@point;translation=2*multiply(dsum,qsum*np.array([1,-1,-1,-1]))[1:]
    return position+Vector(translation)


def bake():
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=setup_scene();actors={};records=[]
    for data in DATA['actors']:
        deform,obj=deform_rig(data);author,controls,aliases,hips=motion_rig(data);actors[data['key']]=(data,deform,obj,author,controls,aliases,hips)
    npc=actors['sachiel'];contact=empty('CONTACT_chest');contact['actual_mesh_vertex']=npc[0]['chest_surface']['vertex'];contact['target_scope']='Evaluated four-weight dual-quaternion surface, not rigid chest proxy'
    incoming=None
    if args.design=='video_counter_v2':
        incoming=empty('CONTACT_incoming');n=npc[0]['bones'];slot=next(i for i,b in enumerate(n)if b['name']=='hand_r');ids=np.asarray(npc[0]['influences']);weights=np.asarray(npc[0]['weights']);verts=np.asarray(npc[0]['vertices']);eligible=np.flatnonzero(np.where(ids==slot,weights,0).sum(1)>.9)
        pick=eligible[np.argmax(verts[eligible,1])];incoming['actual_mesh_vertex']=int(pick)
        from author_video_counter_r44 import configure_fingers
        for data,deform,obj,author,controls,aliases,hips in actors.values():configure_fingers(data,author,controls)
    previous={}
    for frame in range(1,END+1):
        scene.frame_set(frame);root_data={};row=dict(frame=frame,time=(frame-1)/FPS,actors={})
        if args.design=='video_counter_v2':
            from author_video_counter_r44 import motion as counter_motion
            h=actors['1'];counter_motion(h[0],h[3],h[4],h[6],frame,body_only=True)
        for key_actor in('sachiel','1'):
            data,deform,obj,author,controls,aliases,hips=actors[key_actor];root_data[key_actor]=motion(data,author,controls,hips,frame);bpy.context.view_layer.update()
            deps=bpy.context.evaluated_depsgraph_get()
            solved=author.evaluated_get(deps);matrices={}
            for pose_bone in author.pose.bones:
                name=pose_bone.name;value=solved.pose.bones[name].matrix@author.data.bones[name].matrix_local.inverted()
                # Bone roll evaluation can contain ~1e-5 numerical shear.
                # Runtime carries rigid quaternion/offset transforms, so use
                # the nearest rigid rotation while preserving this joint head.
                u,_,vh=np.linalg.svd(np.asarray(value.to_3x3(),dtype=float));q=u@vh
                if np.linalg.det(q)<0:u[:,-1]*=-1;q=u@vh
                rigid=Matrix(q.tolist()).to_4x4();rigid.translation=solved.pose.bones[name].head-rigid.to_3x3()@author.data.bones[name].head_local;matrices[name]=rigid
            desired={name:matrices[aliases[name]]@deform.data.bones[name].matrix_local for name in aliases}
            for bone in deform.data.bones:
                name=bone.name;parent=bone.parent;basis=bone.matrix_local.inverted()@desired[name]if parent is None else bone.matrix_local.inverted()@parent.matrix_local@desired[parent.name].inverted()@desired[name]
                pose=deform.pose.bones[name];pose.rotation_mode='QUATERNION';pose.matrix_basis=basis
                token=data['name']+name
                if token in previous and pose.rotation_quaternion.dot(previous[token])<0:pose.rotation_quaternion.negate()
                previous[token]=pose.rotation_quaternion.copy()
                for path in('location','rotation_quaternion','scale'):pose.keyframe_insert(path,frame=frame)
            bpy.context.view_layer.update()
            if key_actor=='sachiel':
                evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
                contact.location=evaluated.matrix_world@mesh.vertices[data['chest_surface']['vertex']].co
                if incoming is not None:incoming.location=evaluated.matrix_world@mesh.vertices[incoming['actual_mesh_vertex']].co;key(incoming,frame)
                evaluated.to_mesh_clear();key(contact,frame);bpy.context.view_layer.update()
            root,yaw=root_data[key_actor];row['actors'][data['name']]=dict(root=list(root),yaw=yaw,deform={name:[list(v)for v in matrices[aliases[name]]]for name in aliases},
                controls={name:list(obj.matrix_world.translation)for name,obj in controls.items()if name in('pelvis','chest','head','foot_l','foot_r','hand_l','hand_r')})
        records.append(row)
    scene['source_manifest']=json.dumps(dict(quality='NEW_BLOCKING_UNREVIEWED',design=args.design,direction='TV2 compression/engagement/contact-role reference; authored paired video-world-target counter'if incoming else 'TV2 compression/engagement/contact-role reference; original new punch exchange',no_bvh_rotation_copy=True,no_stretch=True,actual_measured_joints=True))
    scene.frame_set(36 if incoming else 111);bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'tv_exchange_blocking_r44.blend'));(OUT/'baked_world_matrices.json').write_text(json.dumps(records,separators=(',',':')),'utf8');print('Saved native paired IK blocking',len(records),'frames',flush=True)


def evaluate():
    scene=bpy.context.scene;rows=json.loads((OUT/'baked_world_matrices.json').read_text('utf8'));results=[]
    for frame in(1,10,18,24,29,32,35,36,39,45,60,80,109)if args.design=='video_counter_v2'else(1,22,36,48,58,76,91,104,112,118,130,160,241):
        scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();row=rows[frame-1]
        for data in DATA['actors']:
            rig=bpy.data.objects[data['name']+'_DEFORM'].evaluated_get(deps);maximum=0.;bad=[]
            for name,wanted in row['actors'][data['name']]['deform'].items():
                actual=rig.pose.bones[name].matrix@rig.data.bones[name].matrix_local.inverted();error=float(np.max(np.abs(np.asarray(actual)-wanted)));maximum=max(maximum,error)
                if error>.001:bad.append(dict(bone=name,error=error))
            results.append(dict(actor=data['name'],frame=frame,actual_saved_bone_matrix_error=maximum,bad=sorted(bad,key=lambda r:r['error'],reverse=True)[:8]))
    passed=all(r['actual_saved_bone_matrix_error']<.001 for r in results);file=OUT/('readback.json'if args.readback else'author_evaluation.json');file.write_text(json.dumps(dict(blender=bpy.app.version_string,passed=passed,samples=results,quality='Blocking evaluation only; no contact/COM/native/artistic acceptance inferred'),indent=2),'utf8');print('Actual saved/evaluated Blender matrix readback',passed,flush=True)


if __name__=='__main__':
    if not args.readback:bake()
    evaluate()
    if args.render_frame:
        scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.render.threads_mode='FIXED';scene.render.threads=2;scene.frame_set(args.render_frame);scene.render.filepath=str(OUT/f'blocking_{args.render_frame:04d}.png');bpy.ops.render.render(write_still=True)
