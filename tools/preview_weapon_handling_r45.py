"""Offline whole-mesh draw/stow review; host exports, Blender only renders."""
from pathlib import Path
import argparse
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

def export(a):
    import author_gameplay_motion_r32 as common
    from author_combat_r35 import Actor
    from study_combat_performance_r36 import decode
    from eva_hand_rig_math_r45 import controls, matrices
    from rebind_anatomical_hand_r45 import dq_pose
    from author_knife_grasp_transition_r45 import equipment_controls
    a.out.mkdir(parents=True,exist_ok=False)
    c=json.loads((a.hand/'hand_rig_contract.json').read_text())
    profile=json.loads(a.profile.read_text())
    common.BODY=json.loads(a.body.read_text());common.NAMES=common.BODY['motion']['bones']
    actor=Actor(c['rig']);name=f"eva_unit0{c['rig']}"
    geo=json.loads((a.hand/(name+'.geo.json')).read_text())
    handmesh=json.loads((a.hand/(name+'_anatomical_hands_r45.mesh.json')).read_text())
    bodypath=a.hand/c['knife_mechanism_r45']['body_mesh']if 'knife_mechanism_r45'in c else ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/mesh/{name}.mesh.json'
    bodymesh=json.loads(bodypath.read_text())
    knife=json.loads((ROOT/c['knife_attachment_r45']['source_mesh']).read_text())
    selected={0,24,50,65,84,102,120};contacts=[]
    mechanism_parts={'pylon_l','r45_knife_hatch_l','r45_knife_carriage_l','r45_knife_actuator_l'}
    for index in range(121):
        frame=profile['clips']['r32_knife_draw']['frames'][index]
        pose=decode(actor,profile,frame);ms={n:pose.matrix(n).copy()for n in pose.q}
        for m in ms.values():m[:3,3]/=16
        if 'knife_mechanism_r45'in c:
            from scipy.spatial.transform import Rotation as R
            from author_knife_grasp_transition_r45 import ease
            mechanism=c['knife_mechanism_r45']
            t=index/120;w=float(ease((t-.12)/.16)*(1-ease((t-.64)/.08)))
            stored=np.array(mechanism['bones'][1]['pivot'])*[-1,1,1]/16 if len(mechanism['bones'])>=3 else None
            target=np.array(mechanism.get('presented_authored',[0,0,0]))*[-1,1,1]/16
            carrier_angle=mechanism.get('carriage_stored_pitch_degrees',0)*(1-w)-90*w
            carrier_centre=stored*(1-w)+target*w if stored is not None else None
            if carrier_centre is not None:carrier_centre[1]+=mechanism.get('carriage_lift_model',0)*np.sin(np.pi*w)/16
            for b in mechanism['bones']:
                pivot=np.array(b['pivot'])*[-1,1,1]/16
                offset=np.zeros(3)
                if 'hatch'in b['name']:
                    axis=np.asarray(mechanism.get('hinge_axis_native',[1,0,0]),float);axis/=np.linalg.norm(axis)
                    rot=R.from_rotvec(axis*np.radians(mechanism['hinge_native_degrees']*frame['handling_r45']['hatch_open'])).as_matrix()
                elif 'carriage'in b['name']:
                    rot=R.from_euler('x',carrier_angle,degrees=True).as_matrix();offset=carrier_centre-stored
                else:
                    pin=np.array(mechanism.get('carriage_actuator_offset_authored',[0,-5,6]))*[-1,1,1]/16
                    endpoint=carrier_centre+R.from_euler('x',carrier_angle,degrees=True).apply(pin)
                    direction=endpoint-pivot;length=np.linalg.norm(direction);direction/=length;axis=np.cross([0,1,0],direction);norm=np.linalg.norm(axis)
                    rotation=R.identity()if norm<1e-9 else R.from_rotvec(axis/norm*np.arccos(np.clip(direction[1],-1,1)))
                    rot=rotation.as_matrix()@np.diag([1,length*16/mechanism['actuator_length'],1])
                local=np.eye(4);local[:3,:3]=rot;local[:3,3]=pivot-rot@pivot+offset
                ms[b['name']]=ms[b['parent']]@local
        for side in ['l','r']:
            if side=='l':values=controls(c,'relaxed',side)
            else:values=equipment_controls(c,side,index/120)
            fk=matrices(geo,c,side,values)
            for digit in c['hands'][side]['digits'].values():
                for joint in digit['joints']:ms[joint['name']]=ms['hand_'+side]@fk[joint['name']]
        exports={};grip={}
        for asset,kind in [(bodymesh,'body'),(handmesh,'hand'),(knife,'knife')]:
            for part,data in asset['parts'].items():
                if index not in selected and kind=='body'and part not in mechanism_parts:continue
                if index not in selected and part=='hand_l':continue
                if kind=='body'and(part.startswith('finger_')or part.startswith('hand_')):continue
                if part not in ms:continue
                raw=np.asarray(data['vertices']).reshape(-1,8);v=(raw[:,:3]+data['pivot'])*[-1,1,1]/16
                skin=asset.get('jointSkins',{}).get(part)
                if skin:
                    palette=list(skin['influences']);w=np.array([skin['influences'][n]for n in palette]).T
                    transforms=[ms[n]@np.array(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette]
                    world=dq_pose(v,w,transforms)
                else:world=v@ms[part][:3,:3].T+ms[part][:3,3]
                if part in {'hand_r','knife'}|mechanism_parts:grip[part]=world
                if kind=='knife'and not frame['handling_r45']['knife_visible']:continue
                exports[kind+'__'+part]=world[:,[0,2,1]]*[5,-5,5]
        contacts.append(grip)
        if index in selected:
            np.savez_compressed(a.out/f'contact_{index:03}.npz',hand=grip['hand_r'],knife=grip['knife'])
            np.savez_compressed(a.out/f'body_{index:03}.npz',**exports)
    np.savez_compressed(a.out/'surfaces.npz',hands=np.asarray([r['hand_r']for r in contacts],dtype=np.float32),knives=np.asarray([r['knife']for r in contacts],dtype=np.float32))
    for part in mechanism_parts:
        if all(part in r for r in contacts):
            np.savez_compressed(a.out/(part+'_surfaces.npz'),vertices=np.asarray([r[part]for r in contacts],dtype=np.float32))
    (a.out/'scope.json').write_text(json.dumps(dict(scope='Offline actual asset geometry with exported candidate body/hand transforms; no native equipment, shader or gameplay acceptance',visual_accepted=False)),encoding='utf8')

def render(out):
    import bpy
    from mathutils import Vector
    for path in sorted(out.glob('body_*.npz')):
        bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
        for part,vertices in np.load(path).items():
            mesh=bpy.data.meshes.new(part);mesh.from_pydata(vertices.tolist(),[],np.arange(len(vertices)).reshape(-1,3).tolist());mesh.update()
            obj=bpy.data.objects.new(part,mesh);bpy.context.collection.objects.link(obj)
            material=bpy.data.materials.new(part);material.diffuse_color=(.12,.14,.18,1)if part.startswith('hand__')else(.25,.11,.39,1)if part.startswith('body__')else(.6,.6,.65,1)
            mesh.materials.append(material)
        for label,offset in [('front',(70,130,40)),('side',(120,30,35))]:
            cam=bpy.data.objects.new('Blocking camera',bpy.data.cameras.new('Blocking camera'));bpy.context.collection.objects.link(cam)
            scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=68
            target=Vector((0,0,31));cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
            scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True
            scene.world=bpy.data.worlds.new('Neutral');scene.world.color=(.07,.09,.11)
            scene.render.resolution_x=800;scene.render.resolution_y=900;scene.render.resolution_percentage=100
            scene.render.filepath=str((out/f'{path.stem}_{label}.png').resolve());bpy.ops.render.render(write_still=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    if '--'in sys.argv:
        a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);render(a.out)
    else:
        import subprocess
        p.add_argument('--body',type=Path,required=True);p.add_argument('--profile',type=Path,required=True);p.add_argument('--hand',type=Path,required=True)
        p.add_argument('--export-only',action='store_true')
        a=p.parse_args();export(a)
        if not a.export_only:
            subprocess.run(['C:/Program Files/Blender Foundation/Blender 5.1/blender.exe','-b','-t','4','--python-exit-code','1','--python',str(Path(__file__).resolve()),'--','--out',str(a.out)],check=True)

