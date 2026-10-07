"""Import the two user FBX motions once and preserve measured rig/clock data."""
from pathlib import Path
import json,sys
import bpy
import numpy as np

out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=True)
sources=[('walk',Path('C:/Users/liboy/Desktop/新建文件夹/行走.fbx')),('run',Path('C:/Users/liboy/Desktop/新建文件夹/跑步.fbx'))]
reports=[]
for name,path in sources:
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(path))
    rigs=[o for o in bpy.data.objects if o.type=='ARMATURE'];scene=bpy.context.scene
    report=dict(name=name,source=str(path),source_bytes=path.stat().st_size,scene_fps=scene.render.fps/scene.render.fps_base,
                actions=[dict(name=a.name,frame_range=list(a.frame_range))for a in bpy.data.actions],rigs=[])
    for ri,rig in enumerate(rigs):
        bones=list(rig.data.bones);names=[b.name for b in bones]
        record=dict(name=rig.name,bones=[dict(name=b.name,parent=b.parent.name if b.parent else None,head=list(b.head_local),tail=list(b.tail_local))for b in bones],active_action=rig.animation_data.action.name if rig.animation_data and rig.animation_data.action else None)
        report['rigs'].append(record)
        action=rig.animation_data.action if rig.animation_data else None
        if action is None:continue
        start,end=map(float,action.frame_range);fps=scene.render.fps/scene.render.fps_base;duration=(end-start)/fps
        samples=max(2,round(duration*60)+1);positions=[];rotations=[]
        for frame in np.linspace(start,end,samples):
            scene.frame_set(int(frame),subframe=float(frame%1));p=[];q=[]
            for bone in bones:
                matrix=rig.matrix_world@rig.pose.bones[bone.name].matrix;p.append(list(matrix.translation));quat=matrix.to_quaternion();q.append([quat.x,quat.y,quat.z,quat.w])
            positions.append(p);rotations.append(q)
        bind=np.array([list((rig.matrix_world@b.matrix_local).translation)for b in bones]);bind_q=[]
        for b in bones:
            q=(rig.matrix_world@b.matrix_local).to_quaternion();bind_q.append([q.x,q.y,q.z,q.w])
        np.savez_compressed(out/f'{name}_rig{ri}.npz',names=names,positions=positions,rotations=rotations,bind_positions=bind,bind_rotations=bind_q,fps=60.,source=str(path),coordinate_system='Blender world Z up',source_fps=fps)
        record.update(duration_seconds=duration,export_samples=samples,position_extent=np.ptp(np.asarray(positions).reshape(-1,3),axis=0).tolist())
    (out/f'{name}_inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');reports.append(report)
    print(json.dumps(dict(name=name,rigs=len(rigs),bones=[len(r['bones'])for r in report['rigs']],actions=report['actions'],fps=report['scene_fps']),ensure_ascii=False))
(out/'INSPECTION.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
