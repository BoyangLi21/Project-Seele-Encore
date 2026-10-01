"""Whole saved mesh, final FK and continuity of an actual legs scene."""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.out.resolve();data=json.loads((out/'fixture.json').read_text('utf8'))['actors'][0];actor=data['name'];rig=bpy.data.objects[actor+'_DEFORM'];author=bpy.data.objects[actor+'_AUTHOR'];obj=bpy.data.objects[actor+'_actual_mesh'];baked=json.loads((out/'baked_world_matrices.json').read_text('utf8'));rows=[];maximum=0.;reference=author.data.bones['pelvis'].head_local.copy();bpy.context.scene.frame_set(0);bpy.context.view_layer.update();root0=author.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones['pelvis'].head.copy()
contacts_path=out/'contact_pass_receipt.json';contact_rows=json.loads(contacts_path.read_text('utf8'))['records'] if contacts_path.exists() else None
names=[b['name'] for b in data['bones']];influences=np.asarray(data['influences']);weights=np.asarray(data['weights']);owners=np.asarray(names)[influences[np.arange(len(influences)),np.argmax(weights,axis=1)]]
contact_masks={}
for side in ('l','r'):
    contact_masks['foot_'+side]=(owners=='foot_'+side)
    contact_masks['hand_'+side]=np.asarray([n=='hand_'+side or n.startswith('finger_') and n.endswith('_'+side) for n in owners])

def hull(points):
    values=sorted(set(tuple(v) for v in points))
    if len(values)<3:return values
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower=[]
    for p in values:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(values):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]

def signed_hull_margin(p,polygon):
    if len(polygon)<3:return None
    return min(((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))/np.linalg.norm(np.asarray(b)-a) for a,b in zip(polygon,polygon[1:]+polygon[:1]))
for frame in range(1,len(baked)+1):
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();solved=rig.evaluated_get(deps);mesh_obj=obj.evaluated_get(deps);mesh=mesh_obj.to_mesh();points=np.empty((len(mesh.vertices),3),dtype=np.float32);mesh.vertices.foreach_get('co',points.reshape(-1));mesh_obj.to_mesh_clear();actual=np.array(mesh_obj.matrix_world);points=points@actual[:3,:3].T+actual[:3,3];worst=int(np.argmin(points[:,2]));error=0
    for n,m in baked[frame-1]['actors'][actor]['deform'].items():error=max(error,float(np.max(np.abs(np.asarray(solved.pose.bones[n].matrix@rig.data.bones[n].matrix_local.inverted())-m))))
    maximum=max(maximum,error);feet={}
    for side in('l','r'):
        matrix=solved.pose.bones['foot_'+side].matrix@rig.data.bones['foot_'+side].matrix_local.inverted();foot=np.asarray(data['toes'][side]['vertices']);posed=foot@np.asarray(matrix)[:3,:3].T+np.asarray(matrix)[:3,3];feet[side]=dict(minimum_z=float(posed[:,2].min()),ankle=list(solved.pose.bones['foot_'+side].head))
    total=0.;com=Vector((0,0,0))
    for bone,mass in data['masses'].items():
        transform=solved.pose.bones[bone].matrix@rig.data.bones[bone].matrix_local.inverted();com+=(transform@Vector(data['mass_centres'][bone]))*mass;total+=mass
    com=np.asarray(com/total);patches=[];support={}
    for side in ('l','r'):
        for family in ('foot','hand'):
            marker=family+'_'+side;allowed=True if contact_rows is None else contact_rows[frame-1]['source_contacts'][marker]
            mask=contact_masks[marker]
            values=points[mask];bottom=float(values[:,2].min())
            patch=values[values[:,2]<=bottom+.08,:2] if allowed and abs(bottom-.015)<=.10 else np.empty((0,2))
            patches.extend(patch.tolist());support[marker]=dict(actual_bottom_z=bottom,source_contact=bool(allowed),actual_ground_patch_points=len(patch))
    polygon=hull(patches)
    owner=names[data['influences'][worst][int(np.argmax(data['weights'][worst]))]];rows.append(dict(frame=frame,time=(frame-1)/30,whole_mesh_minimum_z=float(points[worst,2]),worst_vertex=worst,owner=owner,world=points[worst].tolist(),feet=feet,root=baked[frame-1]['actors'][actor]['root'],saved_matrix_error=error,
        mass_model_com_estimate=com.tolist(),actual_contact_patches=support,actual_support_hull_xy=polygon,estimated_static_com_support_margin_blocks=signed_hull_margin(com[:2],polygon)))
result=dict(blender=bpy.app.version_string,frames=len(rows),frame0_author_pelvis=list(root0),target_bind_pelvis=list(reference),frame0_offset_from_bind=list(reference-root0),frame0_scope='Candidate without neutral key0 extrapolates the first human pose; this is not a second neutral calibration',maximum_saved_matrix_error=maximum,minimum_whole_mesh_z=min(r['whole_mesh_minimum_z']for r in rows),first_mesh_floor_failure=next((r for r in rows if r['whole_mesh_minimum_z']<-.05),None),records=rows,scope='Actually reopened saved evaluator/rigid mesh. COM is an articulated mass-profile estimate and hull is the actual ground patch; dynamic force/ZMP stability is not inferred from the static margin. Native seam stitching, server displacement and GPU unverified; source/retarget provenance does not imply artistic acceptance.')
(out/'saved_skin_fk_audit.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps({k:v for k,v in result.items()if k!='records'},indent=2))
