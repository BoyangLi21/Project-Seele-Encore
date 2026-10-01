"""Read actual saved layers at the observed F260/F261 armour discontinuity."""
from pathlib import Path
import argparse,json,math,sys
import bpy,numpy as np
from mathutils import Vector,Quaternion

ap=argparse.ArgumentParser();ap.add_argument('--raw',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--side',choices=('l','r'),default='r');args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
raw=args.raw.resolve();candidate=args.candidate.resolve()
side=args.side;word='Left' if side=='l' else 'Right';target_names=('leg_'+side,'shin_'+side,'foot_'+side);source_names=(word+'UpLeg',word+'Leg',word+'Foot')
receipt=json.loads((candidate/'contact_pass_receipt.json').read_text('utf8'));wanted=[r for r in receipt['records'] if r['frame'] in (260,261)]

def chain(rig,names):
    samples={}
    for name in names:
        b=rig.pose.bones[name];q=b.matrix.to_quaternion()
        samples[name]=dict(head=list(b.head),tail=list(b.tail),world_quaternion_wxyz=list(q),local_quaternion_wxyz=list(b.matrix_basis.to_quaternion()),world_matrix=[list(r) for r in b.matrix],local_matrix=[list(r) for r in b.matrix_basis])
    h=Vector(samples[names[0]]['head']);k=Vector(samples[names[1]]['head']);a=Vector(samples[names[2]]['head']);axis=(a-h).normalized();bend=k-h-axis*(k-h).dot(axis)
    return dict(bones=samples,knee_perpendicular_length=float(bend.length),knee_perpendicular_vector=list(bend),hip_ankle_axis=list(axis))

original=[]
bpy.ops.wm.open_mainfile(filepath=str(raw/'rokoko_continuous_legs_r44.blend'))
for row in wanted:
    bpy.context.scene.frame_set(row['raw_frame']);bpy.context.view_layer.update()
    source=bpy.data.objects['ACCAD_continuous_original'];author=bpy.data.objects['eva_unit01_AUTHOR']
    original.append(dict(candidate_frame=row['frame'],source_raw_frame=row['raw_frame'],source_actual_fk=chain(source,source_names),
                         original_official_target_fk=chain(author,target_names)))
bpy.ops.wm.open_mainfile(filepath=str(candidate/'rokoko_continuous_legs_r44.blend'))
fixture=json.loads((candidate/'fixture.json').read_text('utf8'))['actors'][0];names=[b['name'] for b in fixture['bones']];owner=np.asarray(fixture['influences'])[:,0]
shin_ids=np.flatnonzero(owner==names.index('shin_'+side))
for row,pre in zip(wanted,original):
    bpy.context.scene.frame_set(row['frame']);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    author=bpy.data.objects['eva_unit01_AUTHOR'].evaluated_get(deps);deform=bpy.data.objects['eva_unit01_DEFORM'].evaluated_get(deps)
    pre['actual_candidate_author']=chain(author,target_names)
    pre['actual_candidate_deform']=chain(deform,target_names)
    target=bpy.data.objects['R44_CONTACT_foot_'+side];pre['actual_end_effector_goal']=dict(position=list(target.location),quaternion=list(target.rotation_quaternion))
    pole=bpy.data.objects.get('R44_CONTACT_POLE_'+side);pre['actual_pole']=list(pole.location) if pole else None
    obj=bpy.data.objects['eva_unit01_actual_mesh'].evaluated_get(deps);mesh=obj.to_mesh();points=np.asarray([list(obj.matrix_world@v.co) for v in mesh.vertices]);obj.to_mesh_clear()
    pre['actual_mesh_right_shin_vertices']=[dict(index=int(i),world=points[i].tolist()) for i in shin_ids]

def rotation_delta(a,b):
    qa=Quaternion(a);qb=Quaternion(b);dot=abs(qa.dot(qb));return math.degrees(2*math.acos(max(-1,min(1,dot))))

deltas={}
for stage,stagenames in [('source_actual_fk',source_names),('original_official_target_fk',target_names),('actual_candidate_author',target_names),('actual_candidate_deform',target_names)]:
    values=[]
    for n in stagenames:
        a=original[0][stage]['bones'][n];b=original[1][stage]['bones'][n]
        values.append(dict(bone=n,actual_world_rotation_degrees=rotation_delta(a['world_quaternion_wxyz'],b['world_quaternion_wxyz']),
                           actual_local_rotation_degrees=rotation_delta(a['local_quaternion_wxyz'],b['local_quaternion_wxyz']),head_displacement=float(np.linalg.norm(np.asarray(b['head'])-a['head']))))
    deltas[stage]=values
report=dict(candidate=str(candidate),anatomical_side=side,frames=original,consecutive_deltas=deltas,
    scope='Actual saved source and original official FK at their exact raw-frame mapping, current contact author constraints/pose, local rotation and reloaded deform mesh. Native GPU unverified. Quaternion signs are removed by absolute dot solely to measure physical rotation; no sign change is a repair.')
(candidate/('first_twist_layer_readback_'+side+'.json')).write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps(dict(consecutive_deltas=deltas,source_bend_lengths=[r['source_actual_fk']['knee_perpendicular_length'] for r in original],original_target_bend_lengths=[r['original_official_target_fk']['knee_perpendicular_length'] for r in original]),indent=2))
