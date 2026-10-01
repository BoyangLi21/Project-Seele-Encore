"""CPU inspect actual saved evaluated fist surfaces, preserving their geometry."""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np
from mathutils import Vector

ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);args.out.mkdir(parents=True,exist_ok=True)
candidate=args.candidate;fixture=json.loads((candidate/'fixture.json').read_text('utf8'));data=fixture['actors'][0];actor=data['name'];records=json.loads((candidate/'contact_pass_receipt.json').read_text('utf8'))['records'];card=fixture['source_motion_card'];names=[b['name']for b in data['bones']];ids=np.asarray(data['influences']);weights=np.asarray(data['weights']);owner=ids[np.arange(len(ids)),weights.argmax(1)];faces=np.asarray(data['faces']);receipt=[]
for segment in card['segments']:
    if segment['label']=='guard':continue
    chosen=[r for r in records if r['raw_frame']is not None and segment['candidate_frames'][0]<=r['raw_frame']<=segment['candidate_frames'][1]];record=chosen[round(segment['runtime_contact_phase']*(len(chosen)-1))];frame=record['frame'];side=segment['leading_side']
    bpy.ops.wm.open_mainfile(filepath=str(candidate/'rokoko_continuous_legs_r44.blend'));scene=bpy.context.scene;scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    author=bpy.data.objects[actor+'_AUTHOR'].evaluated_get(deps);obj=bpy.data.objects[actor+'_actual_mesh'].evaluated_get(deps);mesh=obj.to_mesh();world=np.asarray([list(obj.matrix_world@v.co)for v in mesh.vertices]);obj.to_mesh_clear()
    hand=author.pose.bones['hand_'+side].matrix.copy();origin=np.asarray(hand.translation);rotation=np.asarray(hand.to_3x3());points=(world-origin)@rotation
    for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
    included=[];colors=((.38,.13,.60,1),(.12,.62,.23,1),(.12,.57,.83,1),(.92,.43,.10,1))
    for index,name in enumerate(names):
        if not(name=='hand_'+side or name.startswith('finger_')and name.endswith('_'+side)):continue
        selected=faces[np.all(owner[faces]==index,axis=1)];unique=np.unique(selected)
        if not len(unique):continue
        mapping={int(v):i for i,v in enumerate(unique)};part=bpy.data.meshes.new(name);part.from_pydata(points[unique].tolist(),[],[[mapping[int(v)]for v in face]for face in selected]);part.update();obj=bpy.data.objects.new(name,part);bpy.context.collection.objects.link(obj)
        color=colors[0 if name.startswith('hand_')else 3 if '_distal_'in name else 2 if '_tip_'in name else 1];mat=bpy.data.materials.new(name);mat.use_nodes=True
        mat.node_tree.nodes.clear();shader=mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled');output=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');shader.inputs['Base Color'].default_value=color;mat.node_tree.links.new(shader.outputs['BSDF'],output.inputs['Surface']);part.materials.append(mat);included.extend(unique.tolist())
    shape=points[np.unique(included)];centre=Vector((shape.min(0)+shape.max(0))*.5);span=float(np.ptp(shape,axis=0).max())
    scene.world.color=(.10,.12,.15);light_data=bpy.data.lights.new('Actual fist surface area','AREA');light_data.energy=1400;light_data.size=10;light=bpy.data.objects.new('Actual fist surface area',light_data);bpy.context.collection.objects.link(light);light.location=centre+Vector((5,-6,8));light.rotation_euler=(centre-light.location).to_track_quat('-Z','Y').to_euler()
    cam_data=bpy.data.cameras.new('Actual fist surface view');cam=bpy.data.objects.new('Actual fist surface view',cam_data);bpy.context.collection.objects.link(cam);scene.camera=cam;cam_data.type='ORTHO';cam_data.ortho_scale=span*1.35
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=4;scene.cycles.max_bounces=1;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=2;scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100
    for view,direction in(('dorsal',(4,-6,4)),('palm',(-4,6,-3))):
        cam.location=centre+Vector(direction).normalized()*span*3;cam.rotation_euler=(centre-cam.location).to_track_quat('-Z','Y').to_euler();destination=args.out/(segment['label']+'_'+view+'.png');scene.render.filepath=str(destination);bpy.ops.render.render(write_still=True)
        receipt.append(dict(clip=segment['label'],author_frame=frame,side=side,view=view,file=str(destination),vertices=len(shape),scope='Actual saved source evaluated hand/finger surfaces, rigidly transformed to hand frame for inspection. No reconstructed fist, final native seam skin, GPU or contact acceptance inferred.'))
(args.out/'actual_authored_fist_receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');print('Completed actual source fists',args.out,flush=True)
