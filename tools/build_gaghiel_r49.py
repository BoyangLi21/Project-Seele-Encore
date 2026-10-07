"""Root-authored marine creature, editable Blender rig and matching game skin.

All geometry, UVs and surface maps are constructed here. No official ripped
mesh or image is an input. TV episode 08 guides the silhouette and jaws;
the 100m encounter scale is a game adaptation.
"""
from pathlib import Path
import sys,json,math
import bpy
import numpy as np
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r49/gaghiel_model';OUT.mkdir(parents=True,exist_ok=True)
ASSETS=ROOT/'artifacts/rebuild_r49/assets/assets/projectseele'
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.fps=60
PALETTE=[(.78,.70,.46),(.055,.075,.065),(.34,.035,.07),(.94,.86,.62),(.75,.025,.012),(.012,.017,.013),(.72,.62,.39),(.08,.105,.085)]
image=bpy.data.images.new('Gaghiel authored surface',width=4096,height=2048,alpha=True)
yy,xx=np.mgrid[:2048,:4096];tile=(yy//1024)*4+(xx//1024);colour=np.asarray(PALETTE)[tile]
detail=(np.sin(xx*.023)*np.sin(yy*.017)+.4*np.sin(xx*.12+yy*.027))*.009
pixels=np.concatenate([np.clip(colour+detail[:,:,None],0,1),np.ones((2048,4096,1))],axis=2).astype(np.float32)
image.pixels.foreach_set(pixels.ravel());image.filepath_raw=str(ASSETS/'textures/entity/gaghiel_r49.png');image.file_format='PNG';image.save()
mat=bpy.data.materials.new('Marine ivory and flexible skin');mat.use_nodes=True
shader=mat.node_tree.nodes.get('Principled BSDF');shader.inputs['Roughness'].default_value=.47
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image;mat.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
bone_specs=[('root',None,(0,0,0)),('body','root',(0,0,0)),('head','body',(0,0,-23)),('jaw_lower','head',(0,-.5,-23))]
bone_specs += [(f'tail_{i}','body'if i==0 else f'tail_{i-1}',(0,0,z))for i,z in enumerate((12,20,30,40,49))]
bone_specs += [('fin_l','body',(-11,-1,-3)),('fin_r','body',(11,-1,-3)),('dorsal','body',(0,10,6))]
names=[n for n,_,_ in bone_specs];indices={n:i for i,n in enumerate(names)};objects=[];weights_by_object={}


def group_weights(point,owner):
    if owner!='skin':return{owner:1.}
    z=point[2];stations=[(-26,'head'),(-15,'body'),(8,'body'),(12,'tail_0'),(20,'tail_1'),(30,'tail_2'),(40,'tail_3'),(49,'tail_4')]
    if z<=stations[0][0]:return{'head':1.}
    for(za,na),(zb,nb)in zip(stations,stations[1:]):
        if z<=zb:
            t=(z-za)/(zb-za);t=t*t*(3-2*t)
            return{na:1.}if na==nb else{na:1-t,nb:t}
    return{'tail_4':1.}


def mesh_object(name,vertices,faces,palette,owner):
    v=np.asarray(vertices,float);mesh=bpy.data.meshes.new(name);mesh.from_pydata(v[:,[0,2,1]],[],faces);mesh.update()
    uv=mesh.uv_layers.new(name='SurfaceUV');col,row=palette%4,palette//4
    for poly in mesh.polygons:
        poly.use_smooth=True
        for li in poly.loop_indices:
            p=v[mesh.loops[li].vertex_index]
            uv.data[li].uv=((col+.06+.86*((p[2]+50)/110)%1)/4,(row+.07+.85*(math.atan2(p[1],p[0])/(2*math.pi)+.5))/2)
    mesh.materials.append(mat);obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);objects.append(obj)
    groups={}
    for i,p in enumerate(v):
        w=group_weights(p,owner)
        for bone,value in w.items():
            if value>1e-8:
                if bone not in groups:groups[bone]=obj.vertex_groups.new(name=bone)
                groups[bone].add([i],float(value),'REPLACE')
    weights_by_object[name]=[group_weights(p,owner)for p in v]
    return obj


def loft(name,stations,palette,owner='skin',rings=110,sides=64,half=None):
    st=np.asarray(stations,float);z=np.linspace(st[0,0],st[-1,0],rings);v=[];faces=[]
    angles=np.linspace(*(half or(0,2*math.pi)),sides,endpoint=half is not None)
    for zz in z:
        width=np.interp(zz,st[:,0],st[:,1]);height=np.interp(zz,st[:,0],st[:,2]);offset=np.interp(zz,st[:,0],st[:,3])
        for angle in angles:v.append([width*math.cos(angle),offset+height*math.sin(angle),zz])
    for i in range(rings-1):
        for j in range(sides-1 if half else sides):
            k=(j+1)%sides;a=i*sides+j;b=i*sides+k;c=(i+1)*sides+k;d=(i+1)*sides+j
            faces.append((a,b,c,d))
    return mesh_object(name,v,faces,palette,owner)


def sphere(name,centre,radius,palette,owner):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=1)
    obj=bpy.context.object;v=[np.asarray(centre)+np.asarray(x.co)*np.asarray(radius)for x in obj.data.vertices];faces=[tuple(p.vertices)for p in obj.data.polygons]
    bpy.data.objects.remove(obj,do_unlink=True);return mesh_object(name,v,faces,palette,owner)


def cone(name,base,tip,radius,palette,owner):
    base=np.asarray(base,float);tip=np.asarray(tip,float);axis=tip-base;axis/=np.linalg.norm(axis)
    across=np.cross(axis,[0,0,1]);across/=max(np.linalg.norm(across),1e-8);around=np.cross(axis,across)
    v=[base+radius*(math.cos(t)*across+math.sin(t)*around)for t in np.linspace(0,2*math.pi,12,endpoint=False)];v.append(tip)
    return mesh_object(name,v,[(j,(j+1)%12,12)for j in range(12)]+[tuple(range(11,-1,-1))],palette,owner)


body_stations=[(-25,10,7,0),(-16,15.5,12,0),(0,16,13,0),(12,10,9,0),(25,5,5,0),(40,2.2,2.8,0),(62,.16,.24,0)]
loft('Pale dorsal carapace',body_stations,0,'skin',110,64,(0,math.pi))
loft('Dark flexible underside',body_stations,1,'skin',110,64,(math.pi,2*math.pi))
loft('Upper elongated armored jaw',[(-45,.25,.6,1.6),(-42,3.5,1.8,1.6),(-37,7,3.8,1.4),(-30,11.3,6,1),(-23,13.5,8,0)],0,'head',64,48,(0,math.pi))
loft('Lower articulated jaw',[(-45,.22,.5,-.9),(-42,3.2,1.5,-.8),(-36,7.2,3.1,-.7),(-30,10.7,4.8,-.6),(-23,12,5.5,-.5)],6,'jaw_lower',64,48,(math.pi,2*math.pi))
loft('Upper mouth lining',[(-43,.8,.7,1.2),(-37,6.5,3.3,1.1),(-30,10.7,5.4,.8),(-23,12.8,7.4,0)],2,'head',48,40,(0,math.pi))
loft('Lower mouth lining',[(-43,.8,.7,-.7),(-36,6.7,2.7,-.6),(-30,10.1,4.3,-.5),(-23,11.4,5,-.5)],2,'jaw_lower',48,40,(math.pi,2*math.pi))
sphere('Dark throat',(0,0,-25),(9,7,3),5,'head');sphere('Exposed core',(0,1,-26),(5.5,5.5,2.5),4,'head')
for side in(-1,1):
    for j,z in enumerate(np.linspace(-41,-25,15)):
        width=float(np.interp(z,[-43,-34,-23],[2,11,13]));height=2.2+(j%3)*.6
        cone(f'Upper tooth {side} {j}',(side*width,.6,z),(side*(width-.7),-height,z+.25),.65,3,'head')
        cone(f'Lower tooth {side} {j}',(side*width,-1,z),(side*(width-.7),height-1,z+.25),.6,3,'jaw_lower')
    # Broad swept membrane fins, rather than a generic shark triangle.
    v=[];faces=[];rings=28;sides=24
    for i in range(rings):
        u=i/(rings-1);x=side*(10+22*u);lead=-11+23*u*u;trail=9+12*u-7*u*u
        for angle in np.linspace(0,2*math.pi,sides,endpoint=False):
            v.append((x,-1-1.8*u+(1.35*(1-u)+.04)*math.sin(angle),(lead+trail)/2+(trail-lead)/2*math.cos(angle)))
    for i in range(rings-1):
        for j in range(sides):faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
    mesh_object('Swept fin '+str(side),v,faces,0,'fin_l'if side<0 else'fin_r')
    for j,z in enumerate((-18,-13,-8)):cone('Gill spine '+str(side)+' '+str(j),(side*12,5,z),(side*17,8,z+5),1.1,0,'head'if z<-14 else'body')
mesh_object('Low dorsal ridge',[(0,10,-6),(-1,12,2),(0,18,14),(1,12,2),(0,5,31)],[(0,1,2),(0,2,3),(1,4,2),(3,2,4)],0,'dorsal')
loft('Flexible tail fin',[(35,2.8,2,0),(44,4,1.8,0),(51,3,1.3,0),(58,1.4,.7,0),(64,.08,.1,0)],7,'skin',40,20)
# The tiny mask belongs close to the jaw hinge, not as a pair of animal eyes.
sphere('Small Angel mask',(0,7.8,-25),(1.6,.7,2.2),3,'head')
for side in(-1,1):sphere('Mask eye '+str(side),(side*.6,8.25,-26),(.28,.16,.33),5,'head')

# Preserve an editable armature and the same explicit four-influence weights.
armature=bpy.data.armatures.new('Marine creature bones');rig=bpy.data.objects.new('Gaghiel rig',armature);bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for name,parent,p in bone_specs:
    bone=armature.edit_bones.new(name);bone.head=Vector((p[0],p[2],p[1]));bone.tail=bone.head+Vector((0,2,0))
    if parent:bone.parent=armature.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
for obj in objects:
    modifier=obj.modifiers.new('Actual four-influence deformation','ARMATURE');modifier.object=rig;modifier.use_deform_preserve_volume=True
    obj.parent=rig

vertices=[];joints=[];weights=[]
for obj in objects:
    mesh=obj.data;mesh.calc_loop_triangles();w=weights_by_object[obj.name]
    for tri in mesh.loop_triangles:
        for li in tri.loops:
            loop=mesh.loops[li];point=mesh.vertices[loop.vertex_index].co;normal=mesh.corner_normals[li].vector;uv=mesh.uv_layers.active.data[li].uv
            vertices.extend([point.x*16,point.z*16,point.y*16,uv.x,1-uv.y,normal.x,normal.z,normal.y])
            pairs=[(indices[n],v)for n,v in w[loop.vertex_index].items()if v>1e-8]
            pairs += [(pairs[0][0],0)]*(4-len(pairs));joints.extend(i for i,_ in pairs);weights.extend(v for _,v in pairs)
mesh_doc=dict(stride=8,parts={'root':{'pivot':[0,0,0],'vertices':np.round(vertices,6).tolist()}},
    skin={'bones':names,'indices':joints,'weights':np.round(weights,7).tolist()},
    source='Original R49 procedural marine anatomy; no third-party mesh or bitmap input',
    bounds_blocks=[[-32,-13,-45],[32,26,64]],anchors_blocks={'mouth':[0,0,-37],'core':[0,1,-26],'lower_jaw':[0,-.5,-23]})
geo=dict(format_version='1.12.0',**{'minecraft:geometry':[dict(description={'identifier':'geometry.gaghiel_r49','texture_width':4096,'texture_height':2048,'visible_bounds_width':140,'visible_bounds_height':100,'visible_bounds_offset':[0,0,0]},bones=[dict(name=n,**({'parent':p}if p else{}),pivot=(np.asarray(v)*16).tolist())for n,p,v in bone_specs])]})
for path,doc in[(ASSETS/'mesh/gaghiel_r49.mesh.json',mesh_doc),(ASSETS/'geo/gaghiel_r49.geo.json',geo),(ASSETS/'animations/gaghiel_r49.animation.json',{'format_version':'1.8.0','animations':{'animation.gaghiel.idle':{'loop':True,'animation_length':2,'bones':{}}}})]:
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(doc,separators=(',',':')),encoding='utf-8')
image.pack();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'gaghiel_r49.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'gaghiel_r49.glb'),export_format='GLB',export_animations=False,export_skins=True,export_apply=False)
report=dict(original_geometry=True,official_asset_inputs=[],triangles=len(vertices)//24,bones=names,surface_size=[4096,2048],native_verified=False,user_accepted=False)
(OUT/'SOURCE_AND_RIG.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
