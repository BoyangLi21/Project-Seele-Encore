"""Read supplied Blender rig without executing embedded scripts."""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np

p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(a.input.resolve()),load_ui=False,use_scripts=False)
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE');rows=[]
for bone in rig.pose.bones:
    limits=[]
    for c in bone.constraints:
        row=dict(type=c.type,name=c.name)
        if c.type=='LIMIT_ROTATION':row.update(space=c.owner_space,min_deg=[float(np.degrees(getattr(c,'min_'+s)))for s in 'xyz'],max_deg=[float(np.degrees(getattr(c,'max_'+s)))for s in 'xyz'],limited=[getattr(c,'use_limit_'+s)for s in 'xyz'])
        limits.append(row)
    rows.append(dict(name=bone.name,parent=bone.parent.name if bone.parent else None,head=list(bone.bone.head_local),tail=list(bone.bone.tail_local),constraints=limits))
meshes=[]
for obj in bpy.data.objects:
    if obj.type!='MESH':continue
    groups={g.index:g.name for g in obj.vertex_groups};counts={};maximum_influences=0
    for v in obj.data.vertices:
        maximum_influences=max(maximum_influences,len(v.groups))
        for g in v.groups:counts[groups[g.group]]=counts.get(groups[g.group],0)+1
    meshes.append(dict(name=obj.name,vertices=len(obj.data.vertices),faces=len(obj.data.polygons),maximum_influences=maximum_influences,groups=counts))
scene=bpy.context.scene;observed=[]
for frame,label in [(1,'open'),(22,'fist'),(184,'grab')]:
    scene.frame_set(frame);deps=bpy.context.evaluated_depsgraph_get();r=rig.evaluated_get(deps)
    observed.append(dict(frame=frame,label=label,actual_pose_bones={b.name:dict(head=list(b.head),tail=list(b.tail),matrix=[list(x)for x in b.matrix])for b in r.pose.bones}))
    scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=640;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.filepath=str((a.out/(label+'.png')).resolve());bpy.ops.render.render(write_still=True)
report=dict(input=str(a.input.resolve()),scripts_executed=False,rig=rig.name,bones=rows,meshes=meshes,existing_pose_samples=observed,
    observations=['Separate proximal/intermediate/distal chains','Local rotation constraints define motion DOFs','Each phalanx mesh is rigidly attached; this example does not demonstrate continuous organic/armour skin deformation','Thumb has separate CMC/MCP/IP control'],new_animation_or_video=False)
(a.out/'inspection.json').write_text(json.dumps(report,indent=2),'utf8');print('Inspected',len(rows),'bones',len(meshes),'meshes; no script execution or video')
