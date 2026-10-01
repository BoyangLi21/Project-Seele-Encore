"""Same actually captured mesh/palette posed in Blender, with no mocap substitution."""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,required=True);ap.add_argument('--candidate',type=Path);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
out=args.directory.resolve();comparisons=json.loads((out/'same_pose_float32_comparisons.json').read_text('utf8'))
selected=max(comparisons['samples'],key=lambda r:max(c['same_native_palette_world_max_delta_blocks'] for c in r['same_pose_reference_comparisons']))['frame']
identity=None;sample=None
with (out/'actual_rigged_skin.jsonl').open('r',encoding='utf8') as reader:
    for line in reader:
        row=json.loads(line)
        if row['kind']=='actual-parsed-weighted-resource':identity=row
        if row['kind']=='actual-weighted-emit-vertices' and row['frame']==selected:sample=row;break
if identity is None or sample is None:raise ValueError('Actual same-pose record missing')
bpy.ops.wm.read_factory_settings(use_empty=True)
axes=np.array([[1.,0,0],[0,0,-1],[0,1,0]]);mapping=np.eye(4);mapping[:3,:3]=axes*5;inverse=np.linalg.inv(mapping)
vertices=np.asarray(identity['decoded_vertices'],dtype=np.float32).reshape(-1,8);native=vertices[:,:3].astype(float)*[-1/16,1/16,1/16];points=native@mapping[:3,:3].T
ids=np.asarray(identity['parsed_indices']).reshape(-1,4);weights=np.asarray(identity['parsed_weights'],dtype=np.float32).reshape(-1,4)
if args.candidate:
    candidate=json.loads(args.candidate.read_text('utf8'))
    if not np.array_equal(np.asarray(candidate['parts']['root']['vertices'],np.float32),vertices.reshape(-1)):raise ValueError('Candidate changes actual source geometry')
    ids=np.asarray(candidate['skin']['indices']).reshape(-1,4);weights=np.asarray(candidate['skin']['weights'],np.float32).reshape(-1,4)
names=identity['bones'];arm=bpy.data.armatures.new('Actual native palette');rig=bpy.data.objects.new('Actual native palette',arm);bpy.context.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for i,n in enumerate(names):b=arm.edit_bones.new(n);b.head=(0,0,i*.001);b.tail=(0,0,i*.001+.1)
bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False)
mesh=bpy.data.meshes.new('Actual opened resource vertices');mesh.from_pydata(points.tolist(),[],np.arange(len(points)).reshape(-1,3).tolist());mesh.update();obj=bpy.data.objects.new('Actual opened resource vertices',mesh);bpy.context.collection.objects.link(obj)
groups=[obj.vertex_groups.new(name=n) for n in names]
for vertex,(bones,ws) in enumerate(zip(ids,weights)):
    for bone,w in zip(bones,ws):
        if w>0:groups[bone].add([vertex],float(w),'REPLACE')
modifier=obj.modifiers.new('Actual captured same-pose preserve volume','ARMATURE');modifier.object=rig;modifier.use_deform_preserve_volume=True
matrices=[]
for n,p in zip(names,sample['actual_palette']):
    if n!=p['bone']:raise ValueError('Actual named palette order mismatch')
    m=np.asarray(p['actual_root_relative_matrix_column_major'],dtype=np.float32).reshape(4,4).T.astype(float);matrices.append(m)
    delta=Matrix((mapping@m@inverse).tolist());rig.pose.bones[n].matrix_basis=arm.bones[n].matrix_local.inverted()@delta@arm.bones[n].matrix_local
bpy.context.view_layer.update();evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());actual_mesh=evaluated.to_mesh();actual=np.asarray([list(v.co) for v in actual_mesh.vertices]);evaluated.to_mesh_clear()
def product(a,b):
    return np.concatenate((a[...,:1]*b[...,:1]-(a[...,1:]*b[...,1:]).sum(-1,keepdims=True),a[...,:1]*b[...,1:]+b[...,:1]*a[...,1:]+np.cross(a[...,1:],b[...,1:])),axis=-1)
def dq(rule):
    qs=np.asarray([p['actual_real_quaternion_xyzw'] for p in sample['actual_palette']])[:,[3,0,1,2]];ds=np.asarray([p['actual_dual_quaternion_xyzw'] for p in sample['actual_palette']])[:,[3,0,1,2]]
    q=qs[ids];d=ds[ids]
    if rule=='first_slot':ref=q[:,0]
    elif rule=='dominant':ref=q[np.arange(len(q)),np.argmax(weights,axis=1)]
    else:ref=None
    if ref is None:
        running=np.zeros((len(q),4));sign=np.empty(weights.shape)
        for k in range(4):sign[:,k]=np.where((running*q[:,k]).sum(1)<0,-1.,1.);running+=q[:,k]*(weights[:,k]*sign[:,k])[:,None]
    else:sign=np.where((q*ref[:,None]).sum(2)<0,-1.,1.)
    qr=(q*(weights*sign)[...,None]).sum(1);qd=(d*(weights*sign)[...,None]).sum(1);length=np.linalg.norm(qr,axis=1)[:,None];qr/=length;qd/=length;qd-=qr*(qr*qd).sum(1)[:,None]
    translation=2*product(qd,qr*np.array([1,-1,-1,-1]))[:,1:];v=2*np.cross(qr[:,1:],native);result=native+qr[:,:1]*v+np.cross(qr[:,1:],v)+translation
    return result@mapping[:3,:3].T
rows=[]
for rule in ('first_slot','dominant','running_sum'):
    predicted=dq(rule);error=np.linalg.norm(predicted-actual,axis=1);worst=int(error.argmax());rows.append(dict(rule=rule,maximum_error_blender_blocks=float(error[worst]),worst_vertex=worst,actual_blender=actual[worst].tolist(),prediction=predicted[worst].tolist(),bones=[names[b] for b in ids[worst]],weights=weights[worst].tolist()))
report=dict(actual_native_frame=selected,source_bytes_sha256=identity['source_bytes_sha256'],same_actual_geometry_vertices=len(points),actual_named_palette=names,comparisons=rows,
    counterfactual_candidate_binding=str(args.candidate) if args.candidate else None,
    scope='Actual native mesh/decoded weights and this exact actual native root-relative bone palette posed through Blender armature preserve-volume. No unrelated DCC pose, different game pose, or artist acceptance inferred.',
    scaled_lbs_bones=sum(bool(p['scaled_lbs_branch']) for p in sample['actual_palette']))
(out/('same_pose_blender_candidate_C.json' if args.candidate else 'same_pose_blender_comparison.json')).write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report,indent=2))
