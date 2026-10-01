"""Undo only authored chest hinge to locate the pylon floor error stage."""
from pathlib import Path
import json,sys,argparse
import bpy,numpy as np
from mathutils import Quaternion,Vector
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.out
fixture=json.loads((out/'fixture.json').read_text('utf8'))['actors'][0];records=json.loads((out/'contact_pass_receipt.json').read_text('utf8'))['records']
rig=bpy.data.objects['eva_unit01_DEFORM'];author=bpy.data.objects['eva_unit01_AUTHOR'];vertices=np.asarray(fixture['vertices']);names=[b['name']for b in fixture['bones']];ids=np.asarray(fixture['influences']);weights=np.asarray(fixture['weights']);owners=ids[np.arange(len(ids)),weights.argmax(1)];rows=[]
for frame in (557,606,650,800,1122,1140):
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();row=records[frame-1];theta=row['semantic_prone_body_support']['chest_hinge_adaptation_degrees'];chest=author.pose.bones['chest'].matrix;axis=(chest.to_3x3()@Vector((1,0,0))).normalized()
    reverse=Quaternion(axis,np.radians(-theta)).to_matrix();pivot=np.array(chest.translation);values=[]
    for side in ('l','r'):
        bone='pylon_'+side;mask=owners==names.index(bone);delta=rig.pose.bones[bone].matrix@rig.data.bones[bone].matrix_local.inverted();points=vertices[mask]@np.asarray(delta)[:3,:3].T+np.asarray(delta)[:3,3]
        before=(points-pivot)@np.asarray(reverse).T+pivot
        values.append(dict(bone=bone,current_min_z=float(points[:,2].min()),without_authored_chest_hinge_min_z=float(before[:,2].min())))
    rows.append(dict(frame=frame,label=row['label'],chest_extra_degrees=theta,pelvis_delta=row['semantic_prone_body_support']['pelvis_vertical_adaptation_blocks'],pylons=values))
(out/'chest_armor_first_stage.json').write_text(json.dumps(dict(rows=rows,scope='Same saved pose undoing only the authored world chest hinge about its actual pivot; current pelvis adaptation is retained. This is stage isolation, not accepted alternate motion.'),indent=2),'utf8');print(json.dumps(rows))
