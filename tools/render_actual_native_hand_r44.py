"""Actual submitted native hand triangles, with no reauthored pose or skin substitute."""
from pathlib import Path
import json,sys,math
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat/runtime_hands_basis/native_v1_stream_readback';scene=bpy.context.scene
axes=np.array([[1.,0,0],[0,0,-1],[0,1,0]])
for tick in (4086952,4087483,4087484):
    palette_file=OUT/f'v1_tick{tick}_palette.json'
    if not palette_file.exists():continue
    palette=json.loads(palette_file.read_text('utf8'));bones={b['name']:b for b in palette['bones']}
    for side in ('l','r'):
        bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
        hand=bones['hand_'+side];world=np.asarray(palette['model_to_world_column_major']).reshape(4,4).T
        handmat=np.asarray(hand['final_model_column_major']).reshape(4,4).T
        origin=(world@handmat@np.r_[hand['pivot_model'],1])[:3];allpoints=[]
        for file in OUT.glob(f'v1_tick{tick}_*_submitted.json'):
            row=json.loads(file.read_text('utf8'));name=row['bone']
            if not name.endswith('_'+side):continue
            points=(np.asarray(row['submitted_world_xyz']).reshape(-1,3)-origin)@axes.T
            allpoints.extend(points.tolist());mesh=bpy.data.meshes.new(name);mesh.from_pydata(points.tolist(),[],np.arange(len(points)).reshape(-1,3).tolist());mesh.update()
            obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
            color=(.32,.13,.60,1) if name.startswith('hand_') else (.10,.60,.18,1) if '_tip_'not in name and '_distal_'not in name else (.1,.55,.8,1) if '_tip_'in name else (.85,.43,.07,1)
            material=bpy.data.materials.new(name);material.diffuse_color=color;mesh.materials.append(material)
        points=np.asarray(allpoints);centre=(points.min(0)+points.max(0))*.5
        camera_data=bpy.data.cameras.new('Actual native hand view');camera=bpy.data.objects.new('Actual native hand view',camera_data);bpy.context.collection.objects.link(camera);scene.camera=camera
        camera.location=Vector(centre)+Vector((8,-10,8));camera.rotation_euler=(Vector(centre)-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=max(float(np.ptp(points,axis=0).max())*1.4,8)
        scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH'
        scene.world=bpy.data.worlds.new('Diagnostic background');scene.world.color=(.07,.09,.12)
        scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.filepath=str(OUT/f'actual_hand_v1_tick{tick}_{side}.png');bpy.ops.render.render(write_still=True)
        receipt=dict(actual_native_tick=tick,frame=palette['frame'],stance=palette['stance'],side=side,world_origin_for_precision_only=origin.tolist(),vertices=len(points),
                     scope='Actual CPU submitted world triangle positions from native v1, translated only to near origin for DCC numeric precision. No replacement pose, retarget, bind or skin algorithm. Purple palm; green proximal; blue middle; orange distal. Native raster/shading not reproduced.')
        (OUT/f'actual_hand_v1_tick{tick}_{side}.json').write_text(json.dumps(receipt,indent=2),'utf8')
