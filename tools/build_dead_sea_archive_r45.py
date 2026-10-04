"""Original, editable book and archive stand. No extracted official artwork."""
from pathlib import Path
import argparse,json,sys,math
import bpy,numpy as np
from mathutils import Vector
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
rng=np.random.default_rng(451);
pixels=np.clip(np.asarray([218,199,160])[None,None,:]+rng.normal(0,2,(2048,2048,1)),0,255).astype('uint8')
atlas=Image.fromarray(pixels);draw=ImageDraw.Draw(atlas)
font=ImageFont.truetype('C:/Windows/Fonts/times.ttf',30)
small=ImageFont.truetype('C:/Windows/Fonts/times.ttf',22)
draw.rectangle((0,0,1023,1023),fill=(37,32,31))
draw.rectangle((1024,0,1535,511),fill=(144,112,63))
draw.rectangle((1536,0,2047,511),fill=(53,59,60))
draw.rectangle((1024,512,1535,1023),fill=(137,115,82))
draw.rectangle((1536,512,2047,1023),fill=(91,62,36))
# Two independently drawn manuscript pages, with the traditional ten nodes.
draw.rectangle((65,1090,956,1970),outline=(117,83,40),width=3)
nodes=[(510,1190,'KETHER'),(700,1320,'CHOKMAH'),(320,1320,'BINAH'),(700,1480,'CHESED'),(320,1480,'GEBURAH'),(510,1540,'TIPHERETH'),(700,1710,'NETZACH'),(320,1710,'HOD'),(510,1800,'YESOD'),(510,1900,'MALKUTH')]
edges=[(0,1),(0,2),(0,5),(1,2),(1,3),(1,5),(2,4),(2,5),(3,4),(3,5),(3,6),(4,5),(4,7),(5,6),(5,7),(5,8),(6,7),(6,8),(6,9),(7,8),(7,9),(8,9)]
for u,v in edges:draw.line((nodes[u][0],nodes[u][1],nodes[v][0],nodes[v][1]),fill=(105,78,39),width=3)
for i,(x,y,name)in enumerate(nodes):
 draw.ellipse((x-35,y-35,x+35,y+35),fill=(217,196,156),outline=(101,68,30),width=3)
 draw.text((x,y),str(i+1),font=font,fill=(80,48,24),anchor='mm')
 draw.text((x,y+44),name,font=small,fill=(80,48,24),anchor='mm')
draw.text((510,1130),'ARBOR VITAE',font=font,fill=(79,47,27),anchor='mm')
draw.rectangle((1090,1090,1970,1970),outline=(117,83,40),width=3)
for row in range(19):
 y=1240+row*32
 for col in range(26-rng.integers(0,7)):
  x=1170+col*26
  draw.line((x,y,x+12,y+2),fill=(96,68,38),width=2)
  draw.line((x+4,y-7,x+4,y+6),fill=(96,68,38),width=2)
draw.text((1515,1140),'SECRETA / ARCHIVUM',font=font,fill=(79,47,27),anchor='mm')
atlas.save(a.out/'dead_sea_archive_r45.png')
UV={'leather':(.22,.78),'brass':(.625,.88),'metal':(.86,.87),'edge':(.625,.63),'spine':(.86,.63),'paper':(.76,.18)}
materials={}
for n,c in {'leather':(.045,.036,.034,1),'brass':(.45,.31,.11,1),'metal':(.075,.095,.10,1),'edge':(.52,.43,.28,1),'spine':(.15,.08,.04,1),'paper':(.72,.63,.44,1)}.items():
 m=bpy.data.materials.new(n);m.diffuse_color=c;materials[n]=m
def box(n,c,s,mat,bevel=.006):
 bpy.ops.mesh.primitive_cube_add(size=1,location=(c[0],-c[2],c[1]));o=bpy.context.object;o.name=n;o.scale=(s[0],s[2],s[1]);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(materials[mat])
 if bevel:
  b=o.modifiers.new('Machined edges','BEVEL');b.width=bevel;b.segments=3;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=b.name)
 return o
def cyl(n,c,r,depth,mat,vertices=32):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=(c[0],-c[2],c[1]));o=bpy.context.object;o.name=n;o.data.materials.append(materials[mat]);return o
box('Weighted plinth',(.5,.045,.5),(.74,.09,.70),'metal',.018)
box('Brass bottom datum',(.5,.095,.5),(.68,.016,.64),'brass')
for x in [.27,.73]:
 for z in [.29,.71]:
  cyl('Anchor bolt', (x,.115,z),.021,.018,'brass',16)
box('Archive pedestal',(.5,.565,.5),(.42,.92,.40),'metal',.024)
box('Inset leather field',(.5,.55,.285),(.28,.44,.018),'leather')
for x in [.31,.69]:box('Column rib',(x,.565,.5),(.019,.87,.38),'brass')
box('Display tray',(.5,1.055,.5),(.94,.07,.76),'metal',.015)
box('Felt rest',(.5,1.096,.5),(.90,.014,.72),'leather')
for z in [.19,.81]:box('Tray rim',(.5,1.12,z),(.92,.036,.018),'brass')
for x in [.04,.96]:box('Tray rim',(x,1.12,.5),(.018,.036,.64),'brass')
box('Book rear cover',(.5,1.145,.49),(.88,.033,.65),'leather',.016)
for x in [.07,.93]:box('Gilt cover edging',(x,1.166,.49),(.012,.008,.63),'brass',.002)
for z in [.175,.805]:box('Gilt cover edging',(.5,1.166,z),(.87,.008,.012),'brass',.002)
for i in range(68):
 y=1.174+i*.00135
 box('Individual folio %02d'%i,(.5,y,.49),(.835-.008*math.sin(i*1.33),.0011,.612-.003*math.cos(i)),'edge',0)
for x in [.088,.912]:
 for z in [.192,.788]:box('Embossed corner',(x,1.277,z),(.058,.019,.06),'brass')
for z in [.225,.355,.485,.615,.745]:
 cyl('Raised spine binding',(.5,1.263,z),.012,.029,'spine',20)
# Curved upper leaves have real page topology and original printed atlas UVs.
for side in [-1,1]:
 vs=[];fs=[];uv=[]
 for i in range(45):
  t=i/44;x=.5+side*(.012+.397*t);y=1.259+.038*math.sin(math.pi*t)-.018*t
  for j in range(25):
   z=.19+j/24*.60;vs.append((x,-z,y));px=(956-891*t if side<0 else 1090+880*t)/2048;py=(1970-880*j/24)/2048;uv.append((px,1-py))
 for i in range(44):
  for j in range(24):
   v=i*25+j;fs.append((v,v+1,v+26,v+25)if side>0 else(v+25,v+26,v+1,v))
 mesh=bpy.data.meshes.new('Curved manuscript');mesh.from_pydata(vs,[],fs);mesh.update();o=bpy.data.objects.new('Manuscript left'if side<0 else'Manuscript right',mesh);bpy.context.collection.objects.link(o);o.data.materials.append(materials['paper']);layer=mesh.uv_layers.new()
 for poly in mesh.polygons:
  poly.use_smooth=True
  for li in poly.loop_indices:layer.data[li].uv=uv[mesh.loops[li].vertex_index]
box('Book marker',(.5,1.27,.78),(.016,.003,.17),'spine',0)
verts=[]
for o in bpy.data.objects:
 if o.type!='MESH':continue
 o.data.calc_loop_triangles()
 for tri in o.data.loop_triangles:
  for vi,li in zip(tri.vertices,tri.loops):
   v=o.matrix_world@o.data.vertices[vi].co;n=o.matrix_world.to_3x3()@o.data.vertices[vi].normal
   uv=o.data.uv_layers.active.data[li].uv if o.name.startswith('Manuscript') else UV[o.data.materials[0].name]
   verts.extend([v.x,v.z,-v.y,uv[0],1-uv[1],n.x,n.z,-n.y])
data=dict(schema=45,stride=8,triangles=len(verts)//24,vertices=[round(v,6)for v in verts],bounds=[.03,0,.14,.97,1.31,.88],source='Original root model, traditional Tree of Life layout, no official extracted art')
(a.out/'dead_sea_archive_r45.mesh.json').write_text(json.dumps(data,separators=(',',':')),'utf8')
scene=bpy.context.scene;scene.world=bpy.data.worlds.new('Archive room');scene.world.color=(.08,.09,.10)
cam=bpy.data.objects.new('Model camera',bpy.data.cameras.new('Model camera'));bpy.context.collection.objects.link(cam);scene.camera=cam;cam.location=(2.1,-2.3,2.1);cam.rotation_euler=(Vector((.5,-.5,.7))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.65
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.render.filepath=str(a.out/'archive_model.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(a.out/'dead_sea_archive_r45.blend'))
(a.out/'receipt.json').write_text(json.dumps(dict(editable_source='dead_sea_archive_r45.blend',triangles=data['triangles'],individual_folios=68,curved_page_faces=2112,installed=False,native_visual=False),indent=2),'utf8')
