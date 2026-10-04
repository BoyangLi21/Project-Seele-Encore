"""Offline proposal surface gate and stills. Not a native/art approval."""
from pathlib import Path
import argparse,json,sys,hashlib
import bpy,numpy as np
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_native_knife_grip_r45 import crossing

p=argparse.ArgumentParser();p.add_argument('--proposal',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.out.mkdir(parents=True,exist_ok=False)
record=json.loads((a.proposal/'proposal.json').read_text('utf8'));source=Path(record['native_source']['candidate'])
contract_file=source/'hand_rig_contract.json'
assert hashlib.sha256(contract_file.read_bytes()).hexdigest()==record['native_source']['contract_sha256']
c=json.loads(contract_file.read_text('utf8'));d=np.load(a.proposal/'proposal.npz');hand=d['hand'];weapon=d['weapon']
hv=[Vector(v)for v in hand];wv=[Vector(v)for v in weapon]
hf=np.arange(len(hand)).reshape(-1,3);wf=np.arange(len(weapon)).reshape(-1,3)
ht=BVHTree.FromPolygons(hv,hf.tolist(),all_triangles=True);wt=BVHTree.FromPolygons(wv,wf.tolist(),all_triangles=True)
hits=[(int(h),int(w))for h,w in ht.overlap(wt)if crossing([hv[i]for i in hf[h]],[wv[i]for i in wf[w]])]
report=dict(side=record['side'],triangle_crossings=len(hits),hand_faces=sorted(set(h for h,w in hits)),
            weapon_faces=sorted(set(w for h,w in hits)),geometric_clear=not hits,native_tested=False,visual_accepted=False,
            scope='Entire proposed hand against unchanged weapon, in frozen native relative coordinates; no world installation')
(a.out/'surface_report.json').write_text(json.dumps(report,indent=2),'utf8')
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
for name,points,faces,colour in [('Hand',hand,hf,(.35,.19,.50,1)),('Unchanged rifle',weapon,wf,(.23,.28,.23,1))]:
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(points.tolist(),[],faces.tolist());mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    mat=bpy.data.materials.new(name);mat.diffuse_color=colour;mesh.materials.append(mat)
    for f in mesh.polygons:f.use_smooth=True
centre=Vector((hand.min(0)+hand.max(0))*.5);span=float(np.ptp(hand,axis=0).max())
h=c['hands'][record['side']];normal=Vector(h['palmar_normal_bind']);along=Vector(h['longitudinal_bind'])
q=record.get('local_rotation_xyzw',[0,0,0,1]);rotation=Quaternion((q[3],q[0],q[1],q[2]));normal=rotation@normal;along=rotation@along
across=normal.cross(along).normalized()
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True
scene.world=bpy.data.worlds.new('Diagnostic');scene.world.color=(.10,.12,.14)
scene.render.resolution_x=1000;scene.render.resolution_y=850;scene.render.resolution_percentage=100
for label,direction in [('palm',normal+across*.5-along*.1),('back',-normal+across*.5-along*.1),('side',across+normal*.2)]:
    camera=bpy.data.objects.new(label,bpy.data.cameras.new(label));bpy.context.collection.objects.link(camera);scene.camera=camera
    camera.data.type='ORTHO';camera.data.ortho_scale=span*1.65;camera.location=centre+direction.normalized()*span*3
    camera.rotation_euler=(centre-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str((a.out/(label+'.png')).resolve());bpy.ops.render.render(write_still=True)
print('Offline full-surface crossings',len(hits),'native/art NOT accepted',flush=True)
