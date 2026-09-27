"""Compare native Blender BVH import with the existing source decoder, all frames."""
from pathlib import Path
import sys,json,hashlib,subprocess
import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
OUT=ROOT/'artifacts/world_combat_r40/body_lab/source_bvh'
OUT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'external-assets/incoming/mocap/eva-action-source-r02/tuffles/HaleyTufflesPremadeMocapPack/BVH Converted/Combat/ArmsJabBoxer.bvh'
subprocess.run(['C:/Python314/python.exe','-c',
    'import sys;sys.path.insert(0,sys.argv[1]);from bvh_motion_r12 import load_bvh,save_npz;save_npz(sys.argv[3],load_bvh(sys.argv[2]))',
    str(ROOT/'tools'),str(SOURCE),str(OUT/'project_decoded.npz')],check=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.preferences.addon_enable(module='io_anim_bvh')
bpy.ops.import_anim.bvh(filepath=str(SOURCE),axis_forward='Y',axis_up='Z',global_scale=1,
                        frame_start=1,use_fps_scale=False,update_scene_fps=False)
arm=bpy.context.object
decoded=np.load(OUT/'project_decoded.npz')
decoded_names=list(decoded['names'])
native=[];errors=[];names=[n for n in decoded_names if n in arm.pose.bones]
for f in range(len(decoded['positions'])):
    bpy.context.scene.frame_set(f+1);bpy.context.view_layer.update()
    row={}
    for n in names:
        point=arm.matrix_world@arm.pose.bones[n].head
        row[n]=list(point)
        errors.append((Vector(decoded['positions'][f,decoded_names.index(n)])-point).length)
    native.append(row)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'original_capture.blend'))
result=dict(source=str(SOURCE),sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            frames=len(native),nodes=len(names),maximum_error_source_units=max(errors),
            p95_error_source_units=float(np.percentile(errors,95)),
            native_importer=str(Path(bpy.utils.script_paths()[0])/'addons_core/io_anim_bvh'),
            kind='independent built-in importer versus project decoder',passed=max(errors)<.01)
(OUT/'native_frames.json').write_text(json.dumps(native,separators=(',',':')))
(OUT/'comparison.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
