"""Blender evaluator audit of the actual paired rig and saved mesh surfaces."""
from pathlib import Path
import argparse,json,sys
import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/blocking_v1')
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]if'--'in sys.argv else[]);OUT=args.out.resolve();fixture=json.loads((OUT/'fixture.json').read_text('utf8'));records=[]
manifest=json.loads(bpy.context.scene.get('source_manifest','{}'));design=manifest.get('design','blocking_v1')
for frame in range(1,bpy.context.scene.frame_end+1):
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();row=dict(frame=frame,time=(frame-1)/30,actors={})
    for data in fixture['actors']:
        name=data['name'];author=bpy.data.objects[name+'_AUTHOR'].evaluated_get(deps);rig=bpy.data.objects[name+'_DEFORM'].evaluated_get(deps);state=dict(endpoints={},soles={},com=None)
        mesh_obj=bpy.data.objects[name+'_actual_mesh'].evaluated_get(deps);evaluated_mesh=mesh_obj.to_mesh();actual_vertices=np.asarray([list(mesh_obj.matrix_world@v.co)for v in evaluated_mesh.vertices]);state['actual_whole_mesh_minimum_z']=float(actual_vertices[:,2].min());ids=np.asarray(data['influences']);weights=np.asarray(data['weights']);bone_indices={b['name']:i for i,b in enumerate(data['bones'])}
        for side in('l','r'):
            for family,end,lower in[('arm','hand_','forearm_'),('leg','foot_','shin_')]:
                bone=author.pose.bones[lower+side];point=author.matrix_world@bone.tail;target=bpy.data.objects[name+'_IK_'+end+side].evaluated_get(deps).matrix_world.translation
                state['endpoints'][end+side]=dict(actual=list(point),target=list(target),error=float((point-target).length))
            deform=rig.pose.bones['foot_'+side].matrix@rig.data.bones['foot_'+side].matrix_local.inverted();points=np.asarray(data['toes'][side]['vertices']);world=np.c_[points,np.ones(len(points))]@np.asarray(deform).T
            mask=np.where(ids==bone_indices['foot_'+side],weights,0).sum(1)>.8;actual_foot=actual_vertices[mask];minimum=float(actual_foot[:,2].min());support=actual_foot[actual_foot[:,2]<=minimum+.12]
            state['soles'][side]=dict(minimum_z=float(world[:,2].min()),actual_skin_minimum_z=minimum,actual_floor_patch_xy=support[:,:2].tolist(),toe_goal=list(bpy.data.objects[name+'_CTRL_foot_'+side].evaluated_get(deps).matrix_world.translation))
        total=0.;com=Vector((0,0,0))
        for bone,mass in data['masses'].items():
            transform=rig.pose.bones[bone].matrix@rig.data.bones[bone].matrix_local.inverted();com+=(transform@Vector(data['mass_centres'][bone]))*mass;total+=mass
        state['com']=list(com/total);state['com_scope']='Mass-centre estimate from current articulated-body profile and saved mesh; not measured actor COM or force simulation.';row['actors'][name]=state
        # The selected NPC contact vertex is evaluated through the actual
        # saved armature modifier, rather than treated as a rigid chest marker.
        if data['key']=='sachiel':
            index=data['chest_surface']['vertex'];row['npc_surface_actual']=actual_vertices[index].tolist()
            marker=bpy.data.objects.get('CONTACT_incoming')
            if marker is not None:row['npc_incoming_actual']=actual_vertices[marker['actual_mesh_vertex']].tolist()
        if data['key']=='1':
            transform=rig.pose.bones['hand_r'].matrix@rig.data.bones['hand_r'].matrix_local.inverted();row['hero_contact_actual']=list(transform@Vector(data['hands']['r']['surface']))
            transform=rig.pose.bones['hand_l'].matrix@rig.data.bones['hand_l'].matrix_local.inverted();row['hero_parry_actual']=list(transform@Vector(data['hands']['l']['surface']))
            for side in('l','r'):
                vertex=data['hands'][side].get('contact_vertex')
                if vertex is not None:row['hero_closed_mesh_'+side]=actual_vertices[vertex].tolist()
        mesh_obj.to_mesh_clear()
    row['contact_distance']=float(np.linalg.norm(np.asarray(row['hero_contact_actual'])-row['npc_surface_actual']));records.append(row)
metrics={}
for name in('eva_unit01','sachiel'):
    errors={bone:max(r['actors'][name]['endpoints'][bone]['error']for r in records)for bone in('hand_l','hand_r','foot_l','foot_r')}
    minimum=min(r['actors'][name]['soles'][s]['minimum_z']for r in records for s in('l','r'))
    minimum_skin=min(r['actors'][name]['soles'][s]['actual_skin_minimum_z']for r in records for s in('l','r'))
    metrics[name]=dict(maximum_IK_endpoint_errors=errors,minimum_actual_rigid_sole_z=minimum,minimum_actual_skin_sole_z=minimum_skin,minimum_actual_whole_mesh_z=min(r['actors'][name]['actual_whole_mesh_minimum_z']for r in records))
lo,hi=(1.13,1.17)if design=='video_counter_v2'else(3.68,3.75)
impact=[r['contact_distance']for r in records if lo<=r['time']<=hi]
result=dict(blender=bpy.app.version_string,metrics=metrics,impact_palm_centre_to_npc_skin_vertex=dict(samples=len(impact),minimum=min(impact),maximum=max(impact),scope='NPC actual skin vertex versus rigid palm vertex centroid. Full clenched-knuckle first-contact/penetration is not certified.'),
    quality='NEW BLOCKING: NOT ACCEPTED. This audit measures evaluator/mesh geometry, not artistic quality or runtime inputs.',records=records)
if any('hero_closed_mesh_r'in r for r in records):
    distances=[float(np.linalg.norm(np.asarray(r['hero_closed_mesh_r'])-r['npc_surface_actual']))for r in records if lo<=r['time']<=hi]
    result.pop('impact_palm_centre_to_npc_skin_vertex',None);result['impact_closed_surface_to_npc_skin_vertex']=dict(samples=len(distances),minimum=min(distances),maximum=max(distances),scope='Actual saved skin vertex of the closed fist versus NPC actual saved skin vertex. Whole-surface first-contact/penetration and force simulation not certified.')
(OUT/'contact_com_audit.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps({k:v for k,v in result.items()if k!='records'}),flush=True)
