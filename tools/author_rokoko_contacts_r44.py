"""Private physical contact pass over the saved official retarget.

The raw v4 remains untouched. Explicit bridges retain the measured source's
local FK, then actual target soles/palms own a separate native two-bone IK
pass. No frame-wise root translation or whole-body floor lift is applied.
"""
from pathlib import Path
import argparse, hashlib, json, math, sys
import bpy, numpy as np
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
ap = argparse.ArgumentParser()
ap.add_argument('--raw', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--bridge', type=int, default=12)
ap.add_argument('--surface-support', action='store_true')
ap.add_argument('--armored-prone', action='store_true')
ap.add_argument('--coupled-body-support', action='store_true')
ap.add_argument('--elbow-bearing', action='store_true')
ap.add_argument('--checkpoint-every', type=int, default=120)
ap.add_argument('--surface-hulls', type=Path)
ap.add_argument('--combat-fists', action='store_true')
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
raw, out = args.raw.resolve(), args.out.resolve()
out.mkdir(parents=True, exist_ok=True)
fixture = json.loads((raw/'fixture.json').read_text('utf8'))
data = fixture['actors'][0]
name=data['name']
author = bpy.data.objects[name+'_AUTHOR']
deform = bpy.data.objects[name+'_DEFORM']
source = bpy.data.objects['ACCAD_continuous_original']
mesh = bpy.data.objects[name+'_actual_mesh']
scene = bpy.context.scene
aliases = json.loads(author['aliases_json'])
alias_repairs=[]
for side in ('l','r'):
    for name,owner in (('wrist_'+side,'forearm_'+side),('ankle_'+side,'shin_'+side)):
        if name in aliases and aliases[name]!=owner:
            alias_repairs.append(dict(bone=name,wrong_inherited_owner=aliases[name],actual_anatomical_owner=owner))
            aliases[name]=owner
author['aliases_json']=json.dumps(aliases)
card = fixture.get('source_motion_card') or json.loads((ROOT/'artifacts/rebuild_r44/combat/locomotion_sequence_v2/source_card.json').read_text('utf8'))
labels = {f:s['label'] for s in card['segments'] for f in range(s['candidate_frames'][0],s['candidate_frames'][1]+1)}
cuts = {s['candidate_frames'][0] for s in card['segments'][1:]}
rows = []
for frame in range(1, scene.frame_end+1):
    scene.frame_set(frame); bpy.context.view_layer.update()
    support_role=1. if labels[frame] in ('to_prone','prone_hold','crawl','from_prone') else 0.
    rows.append(dict(raw_frame=frame, label=labels[frame],support_authority_weight=support_role,
                     local={b.name:b.matrix_basis.copy() for b in author.pose.bones},
                     source={n:source.matrix_world@source.pose.bones[n].head for n in
                             ('Hips','Spine1','LeftArm','LeftForeArm','LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase','LeftToeBase_End','RightArm','RightForeArm','RightUpLeg','RightLeg','RightFoot','RightToeBase','RightToeBase_End','LeftHand','RightHand')}))

lying=[r for r in rows if r['label']=='prone_hold']
prone_reference=dict(hips=float(np.median([r['source']['Hips'].z for r in lying])),chest=float(np.median([r['source']['Spine1'].z for r in lying]))) if lying else None
leg_scale=sum(data['joints']['leg_l']['lengths'])/(source.data.bones['LeftUpLeg'].length+source.data.bones['LeftLeg'].length)
torso_scale=(author.data.bones['chest'].head_local-author.data.bones['pelvis'].head_local).length/(source.data.bones['Spine1'].head_local-source.data.bones['Hips'].head_local).length

def mix_matrix(a,b,u):
    p,q,s=a.decompose(); p1,q1,s1=b.decompose()
    return Matrix.LocRotScale(p.lerp(p1,u), q.slerp(q1,u), s.lerp(s1,u))

sequence=[]; bridges=[]
for i,row in enumerate(rows):
    if row['raw_frame'] in cuts:
        begin=len(sequence)+1
        for k in range(1,args.bridge+1):
            u=k/(args.bridge+1); u=u*u*u*(u*(u*6-15)+10)
            a=rows[i-1]
            sequence.append(dict(raw_frame=None, label='bridge:'+a['label']+'->'+row['label'],
                                 support_authority_weight=a['support_authority_weight']*(1-u)+row['support_authority_weight']*u,
                                 local={n:mix_matrix(a['local'][n],row['local'][n],u) for n in row['local']},
                                 source={n:a['source'][n].lerp(row['source'][n],u) for n in row['source']}))
        bridges.append(dict(candidate_frames=[begin,len(sequence)],source_boundary=[i,i+1],
                            method='Explicit 0.4s whole local-FK bridge; contacts solved independently',
                            quality='Authored bridge, not captured footage'))
    sequence.append(row)

# Measure palm from actual hand-owned mesh vertices around the metacarpals.
# The v13 fixture's contact offset is a closed-fist vertex and is unsuitable
# for prone support. Do not reuse that semantic label as a palm measurement.
palm={};vertices=np.asarray(data['vertices']);ids=np.asarray(data['influences']);weights=np.asarray(data['weights'])
dominant=ids[np.arange(len(ids)),np.argmax(weights,axis=1)]
surface_cache=None;bearing_geometry={};foot_patch_indices={}
if args.surface_hulls:
    directory=args.surface_hulls.resolve()
    receipt=json.loads((directory/'rigid_floor_extrema_receipt.json').read_text('utf8'))
    if (receipt['actor']!=data['name'] or receipt['mesh_sha256']!=data['mesh_sha256']
        or receipt['geo_sha256']!=data['geo_sha256']
        or receipt['original_neutral_vertices_sha256']!=hashlib.sha256(vertices.astype(np.float64).tobytes()).hexdigest()):
        raise ValueError('Plane extrema do not belong to this actual neutral geometry')
    surface_cache=np.load(directory/'rigid_floor_extrema.npz',allow_pickle=False)
def surface_points(bone,shape):
    key='full__'+bone
    return surface_cache[key]if surface_cache is not None and key in surface_cache else np.unique(shape,axis=0)
ventral={}
limb_geometry={}
head_index=next(i for i,b in enumerate(data['bones']) if b['name']=='head')
head_geometry=surface_points('head',vertices[dominant==head_index])
body_geometry=[]
for bone,alias in (('torso_lower','pelvis'),('torso_upper','chest'),('pylon_l','chest'),('pylon_r','chest')):
    if any(b['name']==bone for b in data['bones']):
        index=next(i for i,b in enumerate(data['bones'])if b['name']==bone);body_geometry.append((bone,alias,surface_points(bone,vertices[dominant==index])))
for side in ('l','r'):
    for prefix in ('arm_','forearm_','leg_','shin_','hand_'):
        bone=prefix+side;index=next(i for i,b in enumerate(data['bones']) if b['name']==bone)
        limb_geometry[bone]=surface_points(bone,vertices[dominant==index])
        key='proximal__'+bone
        if surface_cache is not None and key in surface_cache:bearing_geometry[bone]=surface_cache[key]
for name in ('torso_lower','torso_upper'):
    index=next(i for i,b in enumerate(data['bones']) if b['name']==name)
    owned=np.flatnonzero(dominant==index)
    vertex=owned[int(np.argmax(vertices[owned,1]))]
    ventral[name]=dict(vertex=int(vertex),neutral_point=Vector(vertices[vertex]))
for side in ('l','r'):
    rest=author.data.bones; hand=rest['hand_'+side]
    long=(rest['finger_middle_'+side].head_local-hand.head_local).normalized()
    across=(rest['finger_little_'+side].head_local-rest['finger_index_'+side].head_local).normalized()
    normal=across.cross(long).normalized()
    if (rest['finger_middle_tip_'+side].head_local-rest['finger_middle_'+side].head_local).dot(normal)<0:normal.negate()
    own=next(i for i,b in enumerate(data['bones']) if b['name']=='hand_'+side)
    owned=(ids[np.arange(len(ids)),np.argmax(weights,axis=1)]==own)
    delta=vertices-np.asarray(hand.head_local);distance=(rest['finger_middle_'+side].head_local-hand.head_local).length
    along=delta@np.asarray(long);depth=delta@np.asarray(normal)
    selected=np.flatnonzero(owned&(along>=distance*.15)&(along<=distance*.90))
    if len(selected)<3:raise ValueError('Actual palm patch cannot be measured '+side)
    # Actual extremal palm plane, not an averaged point through the solid
    # hand thickness. Averaging the inner 20% put other real hand triangles
    # 0.3--1.5 blocks below the nominal contact surface after orientation.
    owned_ids=np.flatnonzero(owned)
    contact_vertex=owned_ids[int(np.argmax(depth[owned_ids]))]
    surface=np.asarray([contact_vertex])
    measured=vertices[contact_vertex]
    palm[side]=dict(rest=Vector(measured),long=long,normal=normal,
                    vertex_ids=surface.tolist(),offset=Vector(measured)-hand.head_local)

author.animation_data_clear();deform.animation_data_clear()
for b in author.pose.bones:
    for c in list(b.constraints):b.constraints.remove(c)
targets={};poles={};checks=[]
for side in ('l','r'):
    for family,lower,end in (('leg','shin_','foot_'),('arm','forearm_','hand_')):
        obj=bpy.data.objects.new('R44_CONTACT_'+end+side,None);bpy.context.collection.objects.link(obj)
        obj.hide_render=True;obj.rotation_mode='QUATERNION';targets[end+side]=obj
        c=author.pose.bones[lower+side].constraints.new('IK');c.target=obj;c.chain_count=2;c.use_stretch=False;c.iterations=120
        if family=='leg':
            pole=bpy.data.objects.new('R44_CONTACT_POLE_'+side,None);bpy.context.collection.objects.link(pole)
            pole.hide_render=True;poles[side]=pole;c.pole_target=pole
            c.pole_angle=author['rigify_pole_leg_'+side]
        for n in (('leg_' if family=='leg' else 'arm_')+side,lower+side):
            b=author.pose.bones[n];b.ik_stretch=0;b.use_ik_limit_x=False;b.lock_ik_y=False;b.lock_ik_z=False
        c=author.pose.bones[end+side].constraints.new('COPY_ROTATION');c.target=obj;c.owner_space='WORLD';c.target_space='WORLD'

anchors={};previous={};previous_bend={};previous_axis={};baked=[];hips=author.data.bones['pelvis'].head_local.copy()
coupled_previous=None;palm_support_state={'l':0.,'r':0.}
hand_owned_shapes={side:{bone['name']:surface_points(bone['name'],vertices[dominant==index])for index,bone in enumerate(data['bones'])
                        if bone['name']=='hand_'+side or bone['name'].startswith('finger_')and bone['name'].endswith('_'+side)}for side in ('l','r')}
foot_solver_geometry={s:np.asarray(data['toes'][s]['vertices'])for s in('l','r')}
if surface_cache is not None:
    for side in('l','r'):
        whole=surface_cache['boot__'+side];front=surface_cache['forefoot__'+side]
        foot_solver_geometry[side]=np.concatenate((whole,front))
        foot_patch_indices[side]=np.arange(len(whole),len(whole)+len(front))
for frame,row in enumerate(sequence,1):
    if frame%120==0:print('Author whole-body contact',frame,'of',len(sequence),row['label'],flush=True)
    scene.frame_set(frame)
    for n,m in row['local'].items():author.pose.bones[n].matrix_basis=m
    # Evaluate FK with the new IK temporarily disabled, so every target starts
    # from the independent official-retarget result for this same frame.
    for b in author.pose.bones:
        for c in b.constraints:c.influence=0
    bpy.context.view_layer.update()
    fk={n:b.matrix.copy() for n,b in author.pose.bones.items()}
    captured_head_rotation=fk['head'].to_quaternion()
    unadapted_root=fk['pelvis'].translation.copy();surface_amount=0.;pelvis_surface_delta=0.;chest_surface_angle=0.
    if args.surface_support and row['support_authority_weight']>0 and prone_reference is not None:
        pelvic_rigid=fk['pelvis']@author.data.bones['pelvis'].matrix_local.inverted()
        anterior=(pelvic_rigid.to_3x3()@Vector((0,1,0))).normalized()
        surface_amount=max(0.,min(1.,(-.75-anterior.z)/.20));surface_amount=surface_amount*surface_amount*(3-2*surface_amount)*row['support_authority_weight']
        if surface_amount>0:
            patch=fk['pelvis']@author.data.bones['pelvis'].matrix_local.inverted()@ventral['torso_lower']['neutral_point']
            # A11 raises the body over its forearms. Preserve that measured
            # height relative to the independently verified A9 prone hold;
            # do not force all crawling chest/belly surfaces onto the floor.
            belly_height=patch.z if args.coupled_body_support else .015+max(0.,row['source']['Hips'].z-prone_reference['hips'])*leg_scale
            pelvis_surface_delta=(belly_height-patch.z)*surface_amount
            local=row['local']['pelvis'].copy()
            local.translation+=author.data.bones['pelvis'].matrix_local.to_3x3().inverted()@Vector((0,0,pelvis_surface_delta))
            row['local']['pelvis']=local;author.pose.bones['pelvis'].matrix_basis=local
            bpy.context.view_layer.update();fk={n:b.matrix.copy() for n,b in author.pose.bones.items()}
            c=fk['chest'].translation.copy();patch=fk['chest']@author.data.bones['chest'].matrix_local.inverted()@ventral['torso_upper']['neutral_point']
            lever=patch-c;axis=(fk['chest'].to_3x3()@Vector((1,0,0))).normalized()
            chest_height=.015+max(0.,row['source']['Spine1'].z-prone_reference['chest'])*torso_scale
            target_height=patch.z*(1-surface_amount)+chest_height*surface_amount
            best=(float('inf'),0.)
            # A9 is naked-human capture. Driving the EVA chest ventral vertex
            # to that same zero height discarded captured thorax pitch and
            # penetrated its torso-owned shoulder towers (F1122: -4.322 m).
            # Armored support retains captured chest orientation; the pelvis
            # and actual elbow/knee surface chains still solve independently.
            for theta in ([0.] if args.armored_prone else np.linspace(-45,45,181)):
                posed=c+Quaternion(axis,math.radians(float(theta)))@lever
                cost=(posed.z-target_height)**2+.00005*theta*theta
                if cost<best[0]:best=(cost,float(theta))
            chest_surface_angle=best[1]
            change=Quaternion(axis,math.radians(chest_surface_angle))
            wanted=(change@fk['chest'].to_quaternion()).to_matrix().to_4x4();wanted.translation=c
            rest=author.data.bones['chest'];parent=rest.parent
            local=rest.matrix_local.inverted()@parent.matrix_local@fk['pelvis'].inverted()@wanted
            row['local']['chest']=local;author.pose.bones['chest'].matrix_basis=local
            bpy.context.view_layer.update();fk={n:b.matrix.copy() for n,b in author.pose.bones.items()}
    goals={};contacts={};source_vel={};hand_blends={};foot_contact_weights={};foot_plants={}
    for side,word in (('l','Left'),('r','Right')):
        foot='foot_'+side;rigid=fk[foot]@author.data.bones[foot].matrix_local.inverted()
        sole=np.asarray(data['toes'][side]['vertices']);pose=sole@np.asarray(rigid)[:3,:3].T+np.asarray(rigid)[:3,3]
        marker=min((row['source'][word+n] for n in ('ToeBase','ToeBase_End')),key=lambda v:v.z)
        prev=sequence[max(0,frame-2)]['source'][word+'ToeBase_End']
        following=sequence[min(len(sequence)-1,frame)]['source'][word+'ToeBase_End']
        speed=(following-prev).xy.length*15
        vertical_speed=(following.z-prev.z)*15
        # A toe marker that is rising several centimetres per frame is not
        # a planted contact merely because it remains below nine centimetres.
        # Standing/crawl floor contacts and toe-off use the same source-time
        # trajectory. Fast sliding is allowed in low postures; lift is not.
        lift_authority=max(0.,min(1.,(.25-abs(vertical_speed))/.20))
        stationarity=max(0.,min(1.,(.45-speed)/.30)) if row['support_authority_weight']==0 else 1.
        contact_weight=max(0.,min(1.,(.04-marker.z)/.025))*lift_authority*stationarity
        contact=contact_weight>1e-5
        plant=contact and speed<.25
        contact_weight=contact_weight*contact_weight*(3-2*contact_weight)
        foot_contact_weights[side]=contact_weight;foot_plants[side]=plant
        contacts[foot]=contact;source_vel[foot]=speed
        ankle=fk[foot].translation.copy();orientation=fk[foot].to_quaternion()
        at=int(np.argmin(pose[:,2]));lowest=Vector(pose[at])
        if plant:
            if foot not in anchors:
                anchors[foot]=dict(surface=lowest.copy(),local=Vector(sole[at]))
                anchors[foot]['surface'].z=.015
            patch=rigid@anchors[foot]['local'];shift=anchors[foot]['surface']-patch
            # Vertical sole collision uses the entire actual boot, while the
            # planted horizontal patch permits normal heel/toe rolling.
            shift.z=(.015-lowest.z)*contact_weight;ankle+=shift
        else:
            anchors.pop(foot,None)
            if contact:ankle.z+=(.015-lowest.z)*contact_weight
        if lowest.z<.015:ankle.z=max(ankle.z,fk[foot].translation.z+.015-lowest.z)
        target=targets[foot];target.location=ankle;target.rotation_quaternion=orientation;goals[foot]=ankle.copy()
        hand='hand_'+side;original=fk[hand].to_quaternion();rigid=fk[hand]@author.data.bones[hand].matrix_local.inverted()
        surface=rigid@palm[side]['rest'];original_surface=surface.copy()
        hand_height=row['source'][word+'Hand'].z
        elbow_height=row['source'][word+'ForeArm'].z
        def smooth_contact(x):
            x=max(0.,min(1.,x));return x*x*x*(x*(x*6-15)+10)
        elbow_weight=(smooth_contact((.10-elbow_height)/.055)*smooth_contact((hand_height-elbow_height-.005)/.045)
                      *row['support_authority_weight']) if args.elbow_bearing else 0.
        blend=max(0.,min(1.,(.20-hand_height)/.12));blend=blend*blend*(3-2*blend)
        blend*=smooth_contact((.72-row['source']['Hips'].z)/.16)
        blend*=1-elbow_weight
        # Supporting contact is a physical transfer over time. A threshold
        # crossing must not swap a raised wrist directly for a planted palm.
        if frame==1:palm_support_state[side]=blend
        else:palm_support_state[side]+=max(-1/18,min(1/18,blend-palm_support_state[side]))
        blend=palm_support_state[side]
        contact=blend>1e-5
        hand_blends[side]=blend if contact else 0.
        contacts[hand]=contact
        if contact:
            own=Matrix((palm[side]['long'].cross(palm[side]['normal']).normalized(),palm[side]['long'],palm[side]['normal'])).transposed()
            # The capture has no finger/palm axis. Near a vertical forearm,
            # projecting a guessed finger axis flipped the palm by 162 deg.
            # An independently authored support palm points toward the body's
            # head, while its anatomical normal faces the contact plane.
            direction=fk['head'].translation-fk['pelvis'].translation;direction.z=0
            if direction.length<.001:direction=Vector((0,1,0))
            direction.normalize();down=Vector((0,0,-1));wanted=Matrix((direction.cross(down).normalized(),direction,down)).transposed()
            orientation=wanted.to_quaternion()@own.to_quaternion().inverted()@author.data.bones[hand].matrix_local.to_quaternion()
            hand_previous=sequence[max(0,frame-2)]['source'][word+'Hand']
            hand_next=sequence[min(len(sequence)-1,frame)]['source'][word+'Hand']
            hand_speed=(hand_next-hand_previous).xy.length*15
            if hand not in anchors or hand_speed>.25:anchors[hand]=dict(surface=surface.copy())
            surface=anchors[hand]['surface'].copy();surface.z=.03
            orientation=original.slerp(orientation,blend)
            surface=original_surface.lerp(surface,blend)
            change=orientation@author.data.bones[hand].matrix_local.to_quaternion().inverted()
            ankle=surface-change@palm[side]['offset']
        else:
            anchors.pop(hand,None);orientation=original;ankle=fk[hand].translation.copy()
            if elbow_weight>0:
                human_arm=(row['source'][word+'ForeArm']-row['source'][word+'Arm']).length+(row['source'][word+'Hand']-row['source'][word+'ForeArm']).length
                scale=sum(data['joints']['arm_'+side]['lengths'])/max(human_arm,1e-5)
                # The captured wrist rises above the supporting elbow. Keep
                # that relation on the long EVA forearm; do not force both
                # palms down and turn prone crawling into repeated pushups.
                desired_surface=.015+(hand_height-elbow_height)*scale
                ankle.z+=(desired_surface-surface.z)*elbow_weight
        target=targets[hand];target.location=ankle;target.rotation_quaternion=orientation;goals[hand]=ankle.copy()
    for b in author.pose.bones:
        for c in b.constraints:c.influence=1
    # The EVA's shoulder/arm-to-leg ratios differ from this performer. Hold
    # the raw pelvis POSITION and all four end-effector goals, then solve a
    # small whole-body lean for actual arm reach. This is not a frame-wise
    # floor translation and is recorded as authored target-body adaptation.
    active=[s for s in ('l','r') if contacts['hand_'+s]]
    root_tilt=(0.,0.);body_change=Quaternion()
    if active:
        origin=fk['pelvis'].translation
        shoulders={s:fk['arm_'+s].translation for s in active}
        lengths={s:sum(data['joints']['arm_'+s]['lengths'])*.995 for s in active}
        belly_points=[]
        if surface_amount>0:
            for name,alias in (('torso_lower','pelvis'),('torso_upper','chest')):
                belly_points.append(fk[alias]@author.data.bones[alias].matrix_local.inverted()@ventral[name]['neutral_point'])
        def lean_cost(pitch,roll):
            change=Quaternion((1,0,0),math.radians(pitch))@Quaternion((0,1,0),math.radians(roll))
            error=sum(max(0.,(goals['hand_'+s]-(origin+change@(shoulders[s]-origin))).length-lengths[s])**2 for s in active)
            error+=10*surface_amount*sum(((origin+change@(point-origin)).z-point.z)**2 for point in belly_points)
            return error+.00005*(pitch*pitch+roll*roll)
        best=(lean_cost(0,0),0.,0.)
        for pitch in range(-75,76,15):
            for roll in range(-45,46,15):
                cost=lean_cost(pitch,roll)
                if cost<best[0]:best=(cost,float(pitch),float(roll))
        for step in (5.,1.):
            centre=best
            for dp in (-2,-1,0,1,2):
                for dr in (-2,-1,0,1,2):
                    pitch=centre[1]+dp*step;roll=centre[2]+dr*step;cost=lean_cost(pitch,roll)
                    if cost<best[0]:best=(cost,pitch,roll)
        root_tilt=best[1:]
        change=Quaternion((1,0,0),math.radians(best[1]))@Quaternion((0,1,0),math.radians(best[2]))
        body_change=change.copy()
        rotation=change@fk['pelvis'].to_quaternion()
        wanted=rotation.to_matrix().to_4x4();wanted.translation=origin
        row['local']['pelvis']=author.data.bones['pelvis'].matrix_local.inverted()@wanted
        author.pose.bones['pelvis'].matrix_basis=row['local']['pelvis']
        for side in ('l','r'):
            hand='hand_'+side
            if not contacts[hand]:
                targets[hand].location=origin+change@(fk[hand].translation-origin)
                targets[hand].rotation_quaternion=change@fk[hand].to_quaternion()
                goals[hand]=targets[hand].location.copy()
    for side in ('l','r'):
        h=fk['leg_'+side].translation;k=fk['shin_'+side].translation;a=goals['foot_'+side]
        axis=(a-h).normalized();bend=k-h-axis*(k-h).dot(axis)
        if bend.length<.001:bend=Vector((0,1,0))
        poles[side].location=k+bend.normalized()*12
    # Fingers are absent from ACCAD. Author an open supporting palm with the
    # measured three phalanges in their real flexion plane, never retain the
    # closed-fist surface label inherited from the fighting fixture.
    for side in ('l','r'):
        rest=author.data.bones;hand='hand_'+side
        rotation=targets[hand].rotation_quaternion;change=rotation@rest[hand].matrix_local.to_quaternion().inverted()
        parent_rotations={hand:rotation}
        for digit in ('index','middle','ring','little','thumb'):
            chain=[f'finger_{digit}{suffix}_{side}' for suffix in ('','_tip','_distal')]
            chain=[n for n in chain if n in rest]
            for n in chain:
                b=rest[n];direction=(b.tail_local-b.head_local).normalized()
                flat=palm[side]['long']
                if digit=='thumb':flat=(rest['finger_index_'+side].head_local-b.head_local).normalized()
                wanted=change@direction.rotation_difference(flat)@b.matrix_local.to_quaternion()
                parent=b.parent.name;baseline=parent_rotations[parent]@rest[parent].matrix_local.to_quaternion().inverted()@b.matrix_local.to_quaternion()
                p=author.pose.bones[n];p.rotation_mode='QUATERNION'
                original=row['local'][n].to_quaternion()
                p.rotation_quaternion=original.slerp(baseline.inverted()@wanted,hand_blends[side])
                parent_rotations[n]=baseline@p.rotation_quaternion;row['local'][n]=p.matrix_basis.copy()
    if args.combat_fists:
        from blender_combat_fist_r44 import apply as combat_fist
        for side in('l','r'):combat_fist(author,targets,row,side,1.)
    # A fixed native IK pole angle discarded the retarget's axial roll and
    # produced a 92-degree armour twist at F261. Solve these same measured
    # two-bone chains analytically, carrying the original world bone roll by
    # the minimal directional quaternion. This is a positional contact solve,
    # not a per-bone angle multiplier or blanket smoothing operation.
    pelvis_world=author.data.bones['pelvis'].matrix_local@author.pose.bones['pelvis'].matrix_basis
    coupled=None
    if args.coupled_body_support:
        from blender_coupled_contact_r44 import solve as coupled_solve
        # Include the actual authored phalanges, in the hand's neutral space.
        # A palm-only floor objective let extended fingertips enter the floor.
        bpy.context.view_layer.update();posed=author.evaluated_get(bpy.context.evaluated_depsgraph_get())
        for side in ('l','r'):
            hand='hand_'+side;neutralized=author.data.bones[hand].matrix_local@posed.pose.bones[hand].matrix.inverted();shapes=[]
            for bone,shape in hand_owned_shapes[side].items():
                if len(shape)==0:continue
                transform=neutralized@posed.pose.bones[bone].matrix@author.data.bones[bone].matrix_local.inverted()
                shapes.append(shape@np.asarray(transform)[:3,:3].T+np.asarray(transform)[:3,3])
            limb_geometry[hand]=np.concatenate(shapes)
        body_transform=body_change.to_matrix().to_4x4();origin=fk['pelvis'].translation;body_transform.translation=origin-body_change@origin
        coupled=coupled_solve({n:body_transform@m for n,m in fk.items()},author.data.bones,data,limb_geometry,
                              foot_solver_geometry,body_geometry,goals,
                              {n:target.rotation_quaternion.copy()for n,target in targets.items()},row['source'],coupled_previous,
                              support_amount=surface_amount,foot_contact_weights=foot_contact_weights,hand_contact_weights=hand_blends,
                              previous_planes=previous_bend,previous_axes=previous_axis,
                              bearing_geometry=bearing_geometry,foot_patch_indices=foot_patch_indices)
        coupled_previous=coupled;shift=coupled['shift'];pelvis_world.translation+=shift
        row['local']['pelvis']=author.data.bones['pelvis'].matrix_local.inverted()@pelvis_world;author.pose.bones['pelvis'].matrix_basis=row['local']['pelvis']
        for m in fk.values():m.translation+=shift
        goals=coupled['goals']
        for n,target in targets.items():target.location=goals[n];target.rotation_quaternion=coupled['orientations'][n]
    else:coupled_previous=None
    bend_readback={}
    for family,side in [(family,side) for side in ('l','r') for family in ('leg','arm')]:
        upper=('leg_' if family=='leg' else 'arm_')+side
        lower=('shin_' if family=='leg' else 'forearm_')+side
        end=('foot_' if family=='leg' else 'hand_')+side
        for n in (lower,end):
            for c in author.pose.bones[n].constraints:c.influence=0
        origin=fk['pelvis'].translation
        h=origin+body_change@(fk[upper].translation-origin)
        k_raw=origin+body_change@(fk[lower].translation-origin)
        a_raw=origin+body_change@(fk[end].translation-origin)
        target=goals[end];direction=target-h;distance=direction.length;direction.normalize()
        lu,ll=data['joints'][family+'_'+side]['lengths']
        reach=max(abs(lu-ll)+1e-5,min(lu+ll-1e-5,distance))
        along=(lu*lu-ll*ll+reach*reach)/(2*reach)
        height=math.sqrt(max(0.,lu*lu-along*along))
        raw_axis=(a_raw-h).normalized()
        raw_bend=k_raw-h-raw_axis*(k_raw-h).dot(raw_axis)
        word='Left' if side=='l' else 'Right'
        segments=('UpLeg','Leg','Foot') if family=='leg' else ('Arm','ForeArm','Hand')
        sh=row['source'][word+segments[0]];sk=row['source'][word+segments[1]];sa=row['source'][word+segments[2]]
        source_axis=(sa-sh).normalized();source_bend=sk-sh-source_axis*(sk-sh).dot(source_axis)
        source_bend_length=source_bend.length
        confidence=min(1.,(source_bend_length/max(.03*(sk-sh).length,1e-5))**2,
                       (raw_bend.length/max(.08*min(lu,ll),1e-5))**2)
        bend=raw_axis.rotation_difference(direction)@raw_bend
        transported=None
        limb=family+'_'+side
        if limb in previous_bend:
            transport=previous_axis[limb].rotation_difference(direction)
            transported=transport@previous_bend[limb]
            transported-=direction*transported.dot(direction);transported.normalize()
        if raw_bend.length<1e-5:
            bend=transported.copy() if transported is not None else Vector((0,1,0))-direction*direction.y
        else:
            bend.normalize()
            if transported is not None and confidence<1:
                # Parallel transport the previous anatomical plane along the
                # new hip-to-ankle axis, then move around that axis only to
                # the extent the source's knee bend is actually observable.
                angle=math.atan2(direction.dot(transported.cross(bend)),transported.dot(bend))
                bend=Quaternion(direction,angle*confidence)@transported
        bend.normalize();previous_bend[limb]=bend.copy();previous_axis[limb]=direction.copy()
        bend_readback[limb]=dict(actual_source_joint_bend_length_metres=source_bend_length,raw_target_joint_bend_length=raw_bend.length,source_bend_confidence=confidence,
                                transported_previous_plane=list(transported) if transported is not None else None,
                                chosen_anatomical_plane=list(bend),hip_ankle_axis=list(direction))
        a=h+direction*reach;centre=h+direction*along
        source_contact_height=sk.z
        low_family=row['support_authority_weight']>0
        limit=.08 if family=='arm' else .10
        contact_weight=max(0.,min(1.,(limit-source_contact_height)/.045))*surface_amount if low_family else 0.
        def chain_geometry(normal):
            joint=centre+normal*height
            qu=(k_raw-h).normalized().rotation_difference((joint-h).normalized())@body_change@fk[upper].to_quaternion()
            ql=(a_raw-k_raw).normalized().rotation_difference((a-joint).normalized())@body_change@fk[lower].to_quaternion()
            minima=[]
            for bone,point,q in ((upper,h,qu),(lower,joint,ql)):
                m=q.to_matrix().to_4x4();m.translation=point;delta=m@author.data.bones[bone].matrix_local.inverted()
                shape=limb_geometry[bone];posed=shape@np.asarray(delta)[:3,:3].T+np.asarray(delta)[:3,3]
                minima.append(float(posed[:,2].min()))
            return joint,qu,ql,minima
        k,q_upper,q_lower,minima=chain_geometry(bend)
        contact_circle_angle=0.
        if family=='arm' and coupled is None and (min(minima)<.013 or contact_weight>0):
            best=None
            # The joint lies on the intersection circle of the two measured
            # limb-length spheres. Choose that circle's actual mesh contact,
            # retaining both endpoints and all limb lengths. No body lift,
            # wrist-only floor lock, or angle gain can satisfy this constraint.
            for theta in np.linspace(-math.pi/6,math.pi/6,25):
                normal=Quaternion(direction,float(theta))@bend
                joint,qu,ql,trial=chain_geometry(normal)
                penetration=max(0.,.015-min(trial))
                temporal=0. if transported is None else (normal-transported).length_squared
                cost=1e7*penetration*penetration+contact_weight*(trial[1]-.015)**2+.2*theta*theta+.5*temporal
                if best is None or cost<best[0]:best=(cost,float(theta),normal,joint,qu,ql,trial)
            for theta in np.linspace(best[1]-math.pi/72,best[1]+math.pi/72,21):
                normal=Quaternion(direction,float(theta))@bend
                joint,qu,ql,trial=chain_geometry(normal);penetration=max(0.,.015-min(trial))
                temporal=0. if transported is None else (normal-transported).length_squared
                cost=1e7*penetration*penetration+contact_weight*(trial[1]-.015)**2+.2*theta*theta+.5*temporal
                if cost<best[0]:best=(cost,float(theta),normal,joint,qu,ql,trial)
            _,contact_circle_angle,bend,k,q_upper,q_lower,minima=best
            previous_bend[limb]=bend.copy()
        bend_readback[limb]['actual_mesh_contact_circle_degrees']=math.degrees(contact_circle_angle)
        bend_readback[limb]['actual_upper_and_lower_mesh_minimum_z']=minima
        bend_readback[limb]['source_surface_support_weight']=contact_weight
        if coupled is not None:
            result=coupled['limbs'][limb];h=result['upper'];k=result['joint'];a=result['end'];q_upper=result['upper_rotation'];q_lower=result['lower_rotation'];minima=result['minima']
            actual_axis=(a-h).normalized();actual_bend=k-h-actual_axis*(k-h).dot(actual_axis)
            if actual_bend.length>1e-6:previous_bend[limb]=actual_bend.normalized();previous_axis[limb]=actual_axis
            bend_readback[limb]['coupled_actual_upper_lower_minimum_z']=minima
            bend_readback[limb]['coupled_reach_error_blocks']=result['reach_error']
        desired_chain={}
        for n,position,orientation in ((upper,h,q_upper),(lower,k,q_lower),(end,a,targets[end].rotation_quaternion)):
            m=orientation.to_matrix().to_4x4();m.translation=position;desired_chain[n]=m
            rest=author.data.bones[n];parent=rest.parent
            body_transform=body_change.to_matrix().to_4x4();body_transform.translation=origin-body_change@origin
            parent_world=desired_chain.get(parent.name,pelvis_world if parent.name=='pelvis' else body_transform@fk[parent.name])
            local=rest.matrix_local.inverted()@parent.matrix_local@parent_world.inverted()@m
            author.pose.bones[n].matrix_basis=local;row['local'][n]=local.copy()
    # The source's gaze is absolute. A chest-surface adaptation must not add
    # another head pitch. Keep that gaze, then use the actual helmet geometry
    # to solve only the neck/head hinge if its long EVA horn reaches the floor.
    head_angle=0.;head_bottom=None
    if low_family:
        bpy.context.view_layer.update();posed_author=author.evaluated_get(bpy.context.evaluated_depsgraph_get())
        head_position=posed_author.pose.bones['head'].head.copy()
        rest=author.data.bones['head'];parent=rest.parent;parent_world=posed_author.pose.bones[parent.name].matrix.copy()
        axis=captured_head_rotation@Vector((1,0,0))
        best=None
        for theta in np.linspace(-90,90,361):
            orientation=Quaternion(axis,math.radians(float(theta)))@captured_head_rotation
            m=orientation.to_matrix().to_4x4();m.translation=head_position;delta=m@rest.matrix_local.inverted()
            points=head_geometry@np.asarray(delta)[:3,:3].T+np.asarray(delta)[:3,3];bottom=float(points[:,2].min())
            cost=1e7*max(0.,.015-bottom)**2+.00001*theta*theta
            if best is None or cost<best[0]:best=(cost,float(theta),bottom,m)
        _,head_angle,head_bottom,desired_head=best
        local=rest.matrix_local.inverted()@parent.matrix_local@parent_world.inverted()@desired_head
        author.pose.bones['head'].matrix_basis=local;row['local']['head']=local.copy()
    bpy.context.view_layer.update();solved=author.evaluated_get(bpy.context.evaluated_depsgraph_get())
    matrices={n:solved.pose.bones[n].matrix@author.data.bones[n].matrix_local.inverted() for n in author.data.bones.keys()}
    desired={n:matrices[aliases[n]]@deform.data.bones[n].matrix_local for n in aliases}
    error={n:(solved.pose.bones[n].head-p).length for n,p in goals.items()}
    root_delta=(solved.pose.bones['pelvis'].head-unadapted_root).length
    for bone in deform.data.bones:
        n=bone.name;parent=bone.parent
        local=bone.matrix_local.inverted()@desired[n] if parent is None else bone.matrix_local.inverted()@parent.matrix_local@desired[parent.name].inverted()@desired[n]
        p=deform.pose.bones[n];p.rotation_mode='QUATERNION';p.matrix_basis=local
        if n in previous and p.rotation_quaternion.dot(previous[n])<0:p.rotation_quaternion.negate()
        previous[n]=p.rotation_quaternion.copy()
        for channel in ('location','rotation_quaternion','scale'):p.keyframe_insert(channel,frame=frame)
    # AUTHOR remains an editable keyed constraint scene as well as DEFORM bake.
    for n,m in row['local'].items():
        p=author.pose.bones[n];p.matrix_basis=m
        for channel in ('location','rotation_quaternion','scale'):p.keyframe_insert(channel,frame=frame)
    for target in targets.values():
        for channel in ('location','rotation_quaternion'):target.keyframe_insert(channel,frame=frame)
    for pole in poles.values():pole.keyframe_insert('location',frame=frame)
    root=solved.pose.bones['pelvis'].head-hips;root.z=0
    baked.append(dict(frame=frame,time=(frame-1)/30,actors={data['name']:dict(root=list(root),yaw=0,
                    deform={n:[list(r) for r in matrices[aliases[n]]] for n in aliases},controls={})}))
    checks.append(dict(frame=frame,raw_frame=row['raw_frame'],label=row['label'],source_contacts=contacts,
                       continuous_palm_support_weights=dict(hand_blends),
                       source_forefoot_speed_metres_per_second=source_vel,actual_ik_goal_error_blocks=error,
                       source_sole_contact_weights=foot_contact_weights,source_horizontal_foot_plants=foot_plants,
                       authored_body_lean_degrees=list(root_tilt),
                       limb_bend_plane_readback=bend_readback,
                       semantic_prone_body_support=dict(weight=surface_amount,pelvis_vertical_adaptation_blocks=pelvis_surface_delta,chest_hinge_adaptation_degrees=chest_surface_angle),
                       actual_helmet_support_constraint=dict(captured_gaze_world_quaternion=list(captured_head_rotation),head_hinge_adaptation_degrees=head_angle,actual_head_mesh_minimum_z=head_bottom),
                       coupled_surface_support=dict(parameters=list(coupled['parameters']),cost=coupled['cost'],pelvis_translation=list(coupled['shift']))if coupled is not None else None,
                       root_position_delta_from_raw_blocks=root_delta))
    if args.checkpoint_every > 0 and frame % args.checkpoint_every == 0:
        # A private partial scene is evidence of completed authoring only;
        # it is never the final export or an accepted clip.
        checkpoint = out / 'partial_checkpoint'
        checkpoint.mkdir(exist_ok=True)
        partial_fixture = dict(fixture)
        partial_fixture['duration'] = frame / 30
        partial_fixture['quality'] = 'INCOMPLETE private author checkpoint; not a candidate export.'
        partial_fixture['source_motion_card'] = card
        partial_fixture['authored_target_bridges'] = bridges
        for filename, value in (('fixture.json', partial_fixture),
                                ('baked_world_matrices.json', baked),
                                ('contact_pass_receipt.json', dict(records=checks, frames=frame, complete=False))):
            temporary = checkpoint / (filename + '.tmp')
            temporary.write_text(json.dumps(value, separators=(',', ':')), 'utf8')
            temporary.replace(checkpoint / filename)
        end = scene.frame_end
        scene.frame_end = frame
        bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint / 'rokoko_continuous_legs_r44.blend'))
        scene.frame_end = end
        (checkpoint / 'completed_frame.txt').write_text(str(frame), 'ascii')
        print('Durable partial author checkpoint', frame, flush=True)
scene.frame_start=1;scene.frame_end=len(sequence);scene.frame_set(1)
fixture['duration']=len(sequence)/30;fixture['quality']='UNAPPROVED target sole/palm IK candidate. Native/rendering/COM/collisions pending.'
fixture['source_motion_card']=card
fixture['authored_target_bridges']=bridges
(out/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8')
(out/'baked_world_matrices.json').write_text(json.dumps(baked,separators=(',',':')),'utf8')
(out/'contact_pass_receipt.json').write_text(json.dumps(dict(raw_scene_sha256=hashlib.sha256((raw/'rokoko_continuous_legs_r44.blend').read_bytes()).hexdigest(),
    frames=len(sequence),seconds=len(sequence)/30,bridges=bridges,
    actual_palm_measurements={s:dict(surface=list(p['rest']),vertex_ids=p['vertex_ids']) for s,p in palm.items()},
    maximum_root_position_change_blocks=max(r['root_position_delta_from_raw_blocks'] for r in checks),
    maximum_ik_goal_error_blocks=max(v for r in checks for v in r['actual_ik_goal_error_blocks'].values()),records=checks,
    semantic_body_support_enabled=args.surface_support,
    armored_prone_preserves_captured_chest_orientation=args.armored_prone,
    whole_body_contact_solve_enabled=args.coupled_body_support,
    actual_source_prone_height_reference_metres=prone_reference,
    repaired_inherited_anatomical_aliases=alias_repairs,
    actual_leg_height_scale=leg_scale,actual_torso_height_scale=torso_scale,
    actual_ventral_support_patches={n:dict(vertex=p['vertex'],neutral_point=list(p['neutral_point'])) for n,p in ventral.items()},
    scope='Physical target end-effector pass. With surface support disabled raw root is unchanged; enabled body support adapts pelvis/chest from measured ventral geometry only during source-confirmed low horizontal prone. No final whole-mesh minimum lift. Source-contact heuristic and authored bridges are explicit, not captured approval.',
    unverified=['COM inside support hull','actual native terrain/network/GPU','finger surface self-collision','full artistic acceptance']),indent=2),'utf8')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'rokoko_continuous_legs_r44.blend'))
print('Saved contact body',len(sequence),'frames',flush=True)
