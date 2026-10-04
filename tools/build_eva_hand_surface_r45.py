"""Root-authored continuous hand surface from the actual neutral source geometry.

Blender voxel union and controlled smoothing repair disconnected digit caps.
Game export preserves explicit inverse-bind matrices for every influence.
Candidates remain private until dynamic native and visual validation.
"""
from pathlib import Path
import argparse,json,sys
import bpy,bmesh,numpy as np
from mathutils import Matrix,Vector,Euler
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'run/resourcepacks/eva_real_model/assets/projectseele'
p=argparse.ArgumentParser();p.add_argument('--variant',type=int,choices=[0,1,2],default=1);p.add_argument('--out',type=Path,required=True)
p.add_argument('--surface-revision',type=int,choices=[4,5,6],default=6)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
name=f'eva_unit0{a.variant}';source=json.loads((PACK/f'mesh/{name}.mesh.json').read_text('utf8'));geo=json.loads((PACK/f'geo/{name}.geo.json').read_text('utf8'));bones={b['name']:b for b in geo['minecraft:geometry'][0]['bones']};cache={}
def bone_matrix(n):
 if n in cache:return cache[n].copy()
 b=bones[n];pivot=Vector(np.asarray(b['pivot'])*[-1,1,1]/16);rot=b.get('rotation',[0,0,0]);rx,ry,rz=np.deg2rad([-rot[0],-rot[1],rot[2]])
 # JOML rotationZYX and RenderUtils compose Rz*Ry*Rx. Blender's Euler
 # order setting has different semantics; explicit matrices keep the bind
 # identical to the actual native initial-snapshot rotation.
 rotation=Matrix.Rotation(float(rz),4,'Z')@Matrix.Rotation(float(ry),4,'Y')@Matrix.Rotation(float(rx),4,'X')
 m=Matrix.Translation(pivot)@rotation@Matrix.Translation(-pivot)
 if b.get('parent'):m=bone_matrix(b['parent'])@m
 cache[n]=m.copy();return m
AX=np.array([[1.,0,0],[0,0,-1],[0,1,0]])
def phalanx_surface(raw,part,n):
 """Closed elliptical phalanges, measured against this actual rig segment."""
 lo=raw[:,:3].min(0);hi=raw[:,:3].max(0);centre=(lo+hi)*.5
 if n.startswith('finger_thumb_'):
  side=n[-1];start=np.asarray(bones[n]['pivot'],float)
  tip=np.asarray(bones['finger_thumb_tip_'+side]['pivot'],float)
  direction=tip-start;length=np.linalg.norm(direction);direction/=length
  radial=np.array([1.,0,0]);radial-=direction*np.dot(radial,direction);radial/=np.linalg.norm(radial)
  other=np.cross(direction,radial);centre=direction*length*.72
  axis=direction;extent=length*1.45;rx=.95;rz=1.16
 else:
  axis=np.array([0.,1,0]);radial=np.array([1.,0,0]);other=np.array([0.,0,1.]);extent=hi[1]-lo[1];rx=(hi[0]-lo[0])*.5;rz=(hi[2]-lo[2])*.5
 cap=min(extent*.23,(rx+rz)*.45);straight=max(0,extent*.5-cap)
 pts=[];fs=[];slices=18;ring=24
 for i in range(slices+1):
  theta=np.pi*i/slices;along=np.cos(theta);radius=np.sin(theta)
  y=np.sign(along)*straight+cap*along
  for j in range(ring):
   phi=2*np.pi*j/ring;pts.append(centre+axis*y+radial*rx*radius*np.cos(phi)+other*rz*radius*np.sin(phi))
 for i in range(slices):
  for j in range(ring):
   k=i*ring+j;l=i*ring+(j+1)%ring;fs.append([k,l,l+ring,k+ring])
 pts=np.asarray(pts)+part['pivot'];m=np.asarray(bone_matrix(n));pts=pts*[-1,1,1]/16;pts=pts@m[:3,:3].T+m[:3,3]
 return pts,fs
export=dict(format_version=1,source='Root authored R45 continuous glove; private source derivative',model_height=source['model_height'],stride=8,parts={},jointSkins={},r37_mouth={'preserve_auto_joint_seams':True},hand_surface_r45=True)
receipts=[]
for side in ['l','r']:
 bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;verts=[];faces=[];labels=[];palette=[];uv=[];surfaces={};uv_sources={}
 for n,part in source['parts'].items():
  if not(n=='hand_'+side or n.startswith('finger_')and n.endswith('_'+side)):continue
  raw=np.asarray(part['vertices']).reshape(-1,source['stride']);xyz=(raw[:,:3]+part['pivot'])*[-1,1,1]/16;m=np.asarray(bone_matrix(n));xyz=xyz@m[:3,:3].T+m[:3,3]
  # The source palm is an open visual shell. Voxelizing its triangle soup
  # directly creates a lattice instead of a solid glove. Each anatomical
  # source segment first becomes a closed hull; fingers remain separate.
  partmesh=bmesh.new()
  if a.surface_revision>=6 and n.startswith('finger_'):
   shape,shape_faces=phalanx_surface(raw,part,n);partverts=[partmesh.verts.new(Vector(point))for point in shape@AX.T]
   for f in shape_faces:partmesh.faces.new([partverts[i]for i in f])
   bmesh.ops.remove_doubles(partmesh,verts=list(partmesh.verts),dist=1e-6)
  elif a.surface_revision>=6:
   # A clean bevelled palm replaces the imported open, folded shell. Its
   # dimensions and anatomical attachment positions stay within source bounds.
   low=raw[:,:3].min(0);high=raw[:,:3].max(0);centre=(low+high)*.5
   local=np.array([[x,y,z]for x in [low[0],high[0]]for y in [low[1],high[1]]for z in [low[2],high[2]]])+part['pivot'];local=local*[-1,1,1]/16;local=local@m[:3,:3].T+m[:3,3]
   partverts=[partmesh.verts.new(Vector(point))for point in local@AX.T];bmesh.ops.convex_hull(partmesh,input=partverts,use_existing_faces=False)
  else:
   partverts=[partmesh.verts.new(Vector(point)) for point in xyz@AX.T];bmesh.ops.convex_hull(partmesh,input=partverts,use_existing_faces=False)
  partmesh.verts.ensure_lookup_table()
  if a.surface_revision>=5 and not(a.surface_revision>=6 and n.startswith('finger_')):
   # Round each mechanical phalanx before union; smoothing a voxelised box
   # alone left sharp fingertips and a jagged thumb in the native prone pose.
   partmesh.edges.ensure_lookup_table()
   radius=.023 if n.startswith('finger_') else .055 if a.surface_revision>=6 else .036
   bmesh.ops.bevel(partmesh,geom=list(partmesh.edges),offset=radius,segments=5,affect='EDGES',clamp_overlap=True)
   partmesh.verts.ensure_lookup_table()
  offset=len(verts);local=np.asarray([v.co[:]for v in partmesh.verts]);verts.extend(local.tolist())
  partmesh.verts.index_update();local_faces=[[v.index for v in f.verts]for f in partmesh.faces]
  surfaces[n]=BVHTree.FromPolygons([Vector(v)for v in local@AX],local_faces,all_triangles=False)
  faces.extend([[offset+i for i in f]for f in local_faces]);labels.extend([n]*len(local));uv.extend([np.mean(raw[:,3:5],axis=0).tolist()]*len(local));partmesh.free()
  uv_sources[n]=(BVHTree.FromPolygons([Vector(v)for v in xyz],np.arange(len(xyz)).reshape(-1,3).tolist(),all_triangles=True),xyz,raw[:,3:5])
 mesh=bpy.data.meshes.new(name+'_hand_'+side);mesh.from_pydata(verts,[],faces);mesh.update();obj=bpy.data.objects.new(mesh.name,mesh);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
 # Surface resolution is 4cm at EVA scale5, rather than flat disconnected boxes.
 obj.data.remesh_voxel_size=.008 if a.surface_revision>=5 else .012;obj.data.remesh_voxel_adaptivity=0 if a.surface_revision>=5 else .12;bpy.ops.object.voxel_remesh()
 mod=obj.modifiers.new('Continuous glove relaxation','SMOOTH');mod.factor=.30 if a.surface_revision>=5 else .25;mod.iterations=4 if a.surface_revision>=5 else 2;bpy.ops.object.modifier_apply(modifier=mod.name)
 for poly in obj.data.polygons:poly.use_smooth=True
 obj.data.update();obj.data.calc_loop_triangles();points=np.asarray([v.co[:] for v in obj.data.vertices])@AX
 # Nearest original surface identifies anatomical region. Blend only adjacent
 # controls around their measured joints; every vertex has explicit weights.
 # Distance to a segment's complete closed surface, not its sparse hull
 # vertices: a palm face interior otherwise gets assigned to a fingertip.
 vertex_labels=[min(surfaces,key=lambda n:surfaces[n].find_nearest(Vector(v))[3])for v in points]
 palette=['hand_'+side]
 for digit in ['index','middle','ring','little','thumb']:
  palette.extend(n for n in ['finger_'+digit+'_'+side,'finger_'+digit+'_tip_'+side,'finger_'+digit+'_distal_'+side] if n in bones)
 weights=np.zeros((len(points),len(palette)));centres={n:np.asarray(bone_matrix(n)@Vector((*((np.asarray(bones[n]['pivot'])*[-1,1,1]/16).tolist()),1)))[:3] for n in palette}
 for i,(point,label) in enumerate(zip(points,vertex_labels)):
  owner=palette.index(label);weights[i,owner]=1
  if label.startswith('finger_'):
   digit=label.split('_')[1];chain=[n for n in ['hand_'+side,'finger_'+digit+'_'+side,'finger_'+digit+'_tip_'+side,'finger_'+digit+'_distal_'+side] if n in palette];at=chain.index(label)
   nearby=[]
   if at>0:nearby.append((chain[at-1],centres[label]))
   if at+1<len(chain):nearby.append((chain[at+1],centres[chain[at+1]]))
   for other,joint in nearby:
    distance=float(np.linalg.norm(point-joint));w=.5*max(0,1-distance/.065)
    if w>0:weights[i,owner]-=w;weights[i,palette.index(other)]+=w
 # Diffuse ownership through the continuous surface at joints. Triangle
 # copies later receive identical weights, preventing sharp label seams.
 edges=np.asarray([(e.vertices[0],e.vertices[1])for e in obj.data.edges],int)
 src=np.r_[edges[:,0],edges[:,1]];dst=np.r_[edges[:,1],edges[:,0]]
 degree=np.bincount(dst,minlength=len(points))[:,None]
 for _ in range(10):
  mean=np.zeros_like(weights);np.add.at(mean,dst,weights[src]);mean/=np.maximum(1,degree)
  weights=.65*weights+.35*mean
 weights/=weights.sum(1)[:,None]
 anchor=np.asarray(bones['hand_'+side]['pivot'],float);texture_uv=np.mean(np.asarray(uv),axis=0);packed=[];expanded=[];vertex_uv=[]
 for vi,point in enumerate(points):
  if a.surface_revision<5:vertex_uv.append(texture_uv);continue
  tree,positions,texcoords=uv_sources[vertex_labels[vi]];nearest,_,triangle,_=tree.find_nearest(Vector(point));ids=np.arange(triangle*3,triangle*3+3)
  triangle_xyz=positions[ids];edges_uv=np.stack((triangle_xyz[1]-triangle_xyz[0],triangle_xyz[2]-triangle_xyz[0]),axis=1)
  bary=np.linalg.lstsq(edges_uv,np.asarray(nearest)-triangle_xyz[0],rcond=None)[0];w=np.array([1-bary.sum(),*bary]);w=np.maximum(w,0);w/=max(w.sum(),1e-9)
  vertex_uv.append(w@texcoords[ids])
 for tri in obj.data.loop_triangles:
  for vi in tri.vertices:
   point=points[vi]*16*np.array([-1,1,1])-anchor;normal=np.asarray(obj.data.vertices[vi].normal)@AX;normal=normal*np.array([-1,1,1]);packed.extend([*point,*vertex_uv[vi],*normal]);expanded.append(int(vi))
 export['parts']['hand_'+side]={'pivot':anchor.tolist(),'vertices':np.round(packed,6).tolist()}
 export['jointSkins']['hand_'+side]={'influences':{n:np.round(weights[expanded,j],7).tolist() for j,n in enumerate(palette)},'inverseBindColumnMajor':{n:np.asarray(bone_matrix(n).inverted()).T.reshape(-1).tolist() for n in palette}}
 scene.world=bpy.data.worlds.new('Hand surface preview');scene.world.color=(.10,.12,.15);material=bpy.data.materials.new('Original violet blue glove');material.diffuse_color=(.24,.25,.48,1);obj.data.materials.append(material)
 camera=bpy.data.objects.new('Hand camera',bpy.data.cameras.new('Hand camera'));bpy.context.collection.objects.link(camera);scene.camera=camera;centre=Vector(np.mean(np.asarray([v.co[:]for v in obj.data.vertices]),axis=0));span=float(np.ptp(points,axis=0).max());camera.location=centre+Vector((2,-3,2)).normalized()*span*3;camera.rotation_euler=(centre-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=span*1.35
 scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.filepath=str(a.out/(name+'_neutral_'+side+'.png'));bpy.ops.render.render(write_still=True)
 bpy.ops.wm.save_as_mainfile(filepath=str(a.out/(name+'_hand_'+side+'.blend')))
 receipts.append(dict(side=side,surface_revision=a.surface_revision,vertices=len(points),triangles=len(obj.data.loop_triangles),max_weight_sum_error=float(np.abs(weights.sum(1)-1).max()),inverse_bind_controls=len(palette),uv='nearest original source triangle barycentric' if a.surface_revision>=5 else 'constant mean UV',native_dynamic_validation=False))
(a.out/(name+'_hands_r45.mesh.json')).write_text(json.dumps(export,separators=(',',':')),'utf8');(a.out/'candidate.json').write_text(json.dumps(dict(variant=a.variant,parts=receipts,installed=False,source_geometry=str(PACK/f'mesh/{name}.mesh.json'),source_rig=str(PACK/f'geo/{name}.geo.json'),native_art='PENDING'),indent=2),'utf8')
