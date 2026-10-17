"""Reference-directed water optics for the saved GeoFront promotional scene.

Run with Blender in background mode. This changes the photographic scene only:
camera transmission remains straight while Fresnel reflections describe water.
"""
from pathlib import Path
import argparse, json, gzip, sys
import bpy
from mathutils import Vector

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scene',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--width',type=int,default=1200);ap.add_argument('--samples',type=int,default=20);a=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    bpy.ops.wm.open_mainfile(filepath=str(a.scene));s=bpy.context.scene
    m=bpy.data.materials['Lake optical medium / final'];n=m.node_tree;n.nodes.clear()
    out=n.nodes.new('ShaderNodeOutputMaterial')
    clear=n.nodes.new('ShaderNodeBsdfTransparent');clear.inputs['Color'].default_value=(1,1,1,1)
    reflected=n.nodes.new('ShaderNodeBsdfGlossy');reflected.inputs['Color'].default_value=(.90,.96,1,1);reflected.inputs['Roughness'].default_value=.025
    fresnel=n.nodes.new('ShaderNodeFresnel');fresnel.inputs['IOR'].default_value=1.333
    reflect_amount=n.nodes.new('ShaderNodeMath');reflect_amount.operation='ADD';reflect_amount.inputs[1].default_value=.055;reflect_amount.use_clamp=True;n.links.new(fresnel.outputs[0],reflect_amount.inputs[0])
    surface=n.nodes.new('ShaderNodeMixShader');n.links.new(reflect_amount.outputs[0],surface.inputs[0]);n.links.new(clear.outputs[0],surface.inputs[1]);n.links.new(reflected.outputs[0],surface.inputs[2]);n.links.new(surface.outputs[0],out.inputs['Surface'])
    geo=n.nodes.new('ShaderNodeNewGeometry');noise=n.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=.7;noise.inputs['Detail'].default_value=2;n.links.new(geo.outputs['Position'],noise.inputs['Vector'])
    bump=n.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.65;bump.inputs['Distance'].default_value=.3;n.links.new(noise.outputs['Fac'],bump.inputs['Height']);n.links.new(bump.outputs[0],reflected.inputs['Normal']);n.links.new(bump.outputs[0],fresnel.inputs['Normal'])
    absorption=n.nodes.new('ShaderNodeVolumeAbsorption');absorption.inputs['Color'].default_value=(.35,.45,.48,1);absorption.inputs['Density'].default_value=.003
    scatter=n.nodes.new('ShaderNodeVolumeScatter');scatter.inputs['Color'].default_value=(.28,.38,.42,1);scatter.inputs['Density'].default_value=.00015
    volume=n.nodes.new('ShaderNodeAddShader');n.links.new(absorption.outputs[0],volume.inputs[0]);n.links.new(scatter.outputs[0],volume.inputs[1]);n.links.new(volume.outputs[0],out.inputs['Volume'])
    # Reference artwork uses visible warm slopes under a restrained water film.
    basin=bpy.data.materials['Native black basin / photographic concrete'].node_tree.nodes.get('Principled BSDF');basin.inputs['Base Color'].default_value=(.095,.066,.052,1);basin.inputs['Roughness'].default_value=.62
    pyr=bpy.data.objects['Native pyramid / continuous photographic cladding'];pn=pyr.data.materials[0].node_tree;p=pn.nodes.get('Principled BSDF');g=pn.nodes.new('ShaderNodeNewGeometry');xyz=pn.nodes.new('ShaderNodeSeparateXYZ');under=pn.nodes.new('ShaderNodeMath');under.operation='LESS_THAN';under.inputs[1].default_value=-6;pn.links.new(g.outputs['Position'],xyz.inputs[0]);pn.links.new(xyz.outputs['Z'],under.inputs[0])
    tint=pn.nodes.new('ShaderNodeMixRGB');tint.inputs[1].default_value=p.inputs['Base Color'].default_value;tint.inputs[2].default_value=(.085,.061,.049,1);pn.links.new(under.outputs[0],tint.inputs[0]);pn.links.new(tint.outputs[0],p.inputs['Base Color'])
    # Straight transmission reveals the true depth; clear the near bank with
    # the camera rather than deforming the accepted underwater geometry.
    s.camera.location=(390,-930,430);target=Vector((-35,-365,-10));s.camera.rotation_euler=(target-s.camera.location).to_track_quat('-Z','Y').to_euler();s.camera.data.lens=52
    # Mirror the latest installed foot lights and the larger native apex ring.
    base=a.scene.parents[2];delta=base/'lighting370/EXACT_DELTA.json.gz'
    if delta.exists():
        verts=[];faces=[]
        for row in json.loads(gzip.decompress(delta.read_bytes())):
            if row['reason']!='pyramid_lawn_foot_lighting':continue
            x,y,z=row['pos'];k=len(verts);verts.extend([(x,-z,y+467.03),(x+1,-z,y+467.03),(x+1,-z-1,y+467.03),(x,-z-1,y+467.03)]);faces.append((k,k+1,k+2,k+3))
        me=bpy.data.meshes.new('Installed native pyramid lawn lights');me.from_pydata(verts,[],faces);me.update();ob=bpy.data.objects.new(me.name,me);bpy.context.collection.objects.link(ob);me.materials.append(bpy.data.materials['Installed cyan lighting / sea lantern optical finish'])
        ring=bpy.data.objects.get('Installed underwater contour 9')
        if ring:
            r=14;h=-78+r*67/88+.06
            for point,co in zip(ring.data.splines[0].points,[(-80-r,-438-r,h),(-80+r,-438-r,h),(-80+r,-438+r,h),(-80-r,-438+r,h)]):point.co=(*co,1)
            ring.name='Installed underwater contour 14'
    # Studio panels light the architecture but must not become rectangular
    # objects reflected in the lake. Keep environment and scene reflections.
    for light in bpy.data.objects:
        if light.type=='LIGHT' and light.data.type=='AREA':
            light.data.specular_factor=0
            light.visible_glossy=False
            print('EXCLUDE STUDIO REFLECTION',light.name,flush=True)
    for n0 in bpy.data.materials['Distance haze'].node_tree.nodes:
        if n0.bl_idname=='ShaderNodeVectorMath' and n0.operation=='DISTANCE':n0.inputs[1].default_value=s.camera.location
    s.cycles.device='CPU';s.render.threads_mode='FIXED';s.render.threads=6;s.cycles.samples=a.samples;s.cycles.adaptive_threshold=.08;s.render.resolution_x=a.width;s.render.resolution_y=round(a.width*9/16);s.render.image_settings.color_depth='16' if a.width>1600 else '8';s.render.filepath=str(a.out.with_suffix('.png'))
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(a.out.with_suffix('.blend')),compress=True)
    a.out.with_suffix('.json').write_text(json.dumps(dict(source_scene=str(a.scene),native_save_modified=False,geometry_modified=False,camera_transmission='Straight, art-directed; no waterline bending',surface_reflection='Fresnel IOR 1.333 with subtle wave normals',absorption_density=.003,scatter_density=.00015),indent=2),'utf8')
    bpy.ops.render.render(write_still=True)
    print('CLEAR WATER COMPLETE',flush=True)

if __name__=='__main__':main()
