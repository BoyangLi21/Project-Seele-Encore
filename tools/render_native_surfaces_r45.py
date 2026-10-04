"""Inspect exact submitted body surfaces; no pose reauthoring or quality verdict."""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--witness',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--ticks',default='');p.add_argument('--parts',default='')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
palettes=[];geometry={}
for line in a.witness.open(encoding='utf8'):
    r=json.loads(line)
    if r['kind']=='final_named_palette':palettes.append(r)
    elif r['kind']=='actual_static_part_geometry':geometry[r['resource_part']]=r
assert len(palettes)>=3
chosen=[palettes[i]for i in dict.fromkeys([0,len(palettes)//2,len(palettes)-2])]
if a.ticks:chosen=[min(palettes,key=lambda row:abs(row['tick']-int(t)))for t in a.ticks.split(',')]
ticks={r['tick']for r in chosen};submissions={tick:[]for tick in ticks}
for line in a.witness.open(encoding='utf8'):
    r=json.loads(line)
    if r['kind']=='actual_cpu_submitted_part'and r['tick']in ticks:submissions[r['tick']].append(r)
AX=np.array([[1.,0,0],[0,0,-1],[0,1,0]]);receipts=[]
for palette in chosen:
    tick=palette['tick'];bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
    world=np.asarray(palette['model_to_world_column_major']).reshape(4,4).T;origin=world[:3,3];points=[];errors=[]
    for r in submissions[tick]:
        if a.parts and r['bone']not in a.parts.split(','):continue
        g=geometry[r['resource_part']];pts=np.asarray(g['original_part_xyz']).reshape(-1,3).copy()
        changes=np.asarray(r['submitted_position_changes_index_xyz']).reshape(-1,4)
        for c in changes:pts[int(c[0])]=c[1:]
        pts=(pts+r['part_pivot_authored'])*[-1,1,1]/16;matrix=np.asarray(r['mesh_to_world_column_major']).reshape(4,4).T
        actual=pts@matrix[:3,:3].T+matrix[:3,3];ids=np.asarray(r['actual_world_sample_vertex_indices'],int)
        error=float(np.abs(actual[ids]-np.asarray(r['actual_world_sample_xyz']).reshape(-1,3)).max());assert error<.01;errors.append(error)
        display=(actual-origin)@AX.T;points.extend(display)
        mesh=bpy.data.meshes.new(r['bone']);mesh.from_pydata(display.tolist(),[],np.arange(len(display)).reshape(-1,3).tolist());mesh.update()
        obj=bpy.data.objects.new(r['bone'],mesh);bpy.context.collection.objects.link(obj)
        mat=bpy.data.materials.new(r['bone']);mat.diffuse_color=(.21,.22,.45,1)if r['bone'].startswith('hand_')else(.26,.09,.43,1)
        mesh.materials.append(mat)
        for face in mesh.polygons:face.use_smooth=True
    pts=np.asarray(points);centre=Vector((pts.min(0)+pts.max(0))*.5);span=float(np.ptp(pts,axis=0).max())
    for label,direction in [('front',(2,-5,1.3)),('side',(5,-.2,1.3))]:
        cam=bpy.data.objects.new('Actual surface camera',bpy.data.cameras.new('Actual surface camera'));bpy.context.collection.objects.link(cam);scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=span*1.25
        cam.location=centre+Vector(direction).normalized()*span*3;cam.rotation_euler=(centre-cam.location).to_track_quat('-Z','Y').to_euler()
        scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.world=bpy.data.worlds.new('Diagnostic');scene.world.color=(.08,.10,.13)
        scene.render.resolution_x=800;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;file=a.out/f'actual_{tick}_{label}.png';scene.render.filepath=str(file);bpy.ops.render.render(write_still=True)
        receipts.append(dict(tick=tick,view=label,file=str(file),parts=[r['bone']for r in submissions[tick]],max_world_readback_error=max(errors),
            scope='Exact actual CPU submissions and final matrices; independently matched indexed world points. Flat diagnostic materials/camera only, not a native shader or artistic PASS.'))
(a.out/'receipt.json').write_text(json.dumps(receipts,indent=2),'utf8')
