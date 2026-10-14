"""Root-selected two-pipe bypass; mesh candidate only, never a World writer."""
from pathlib import Path
import argparse,hashlib,json,math,struct,shutil
import numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.Codex/map_complete_20261013/route_audit/service_bypass_candidate'
SOURCE=ROOT/'src/main/resources/assets/projectseele/mesh/legacy_running_heads_r52.json'
SOURCE_SHA='63fa3c8c4140a34557ee7a07f47a7bc82485900b68d669b11457ba6b1aee3f97'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA
source=json.loads(SOURCE.read_text(encoding='utf-8'))
original=np.array(source['parts']['legacy_original_retained']).reshape(-1,3,6)
origin=np.array(source['original_frame']['origin'])
world=original[:,:,:3]*[-1,1,-1]+origin
parent=list(range(len(world)))
def find(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
seen={}
for i,t in enumerate(world):
    for v in t:
        key=tuple(v)
        if key in seen:parent[find(i)]=find(seen[key])
        else:seen[key]=i
groups={}
for i in range(len(world)):groups.setdefault(find(i),[]).append(i)

removed=set();selected=[];components=[]
def add(name,triangles):components.append({'name':name,'frame':'world','role':'static','triangles_rgb':np.asarray(triangles).reshape(-1).tolist()})
def tri(a,b,c,color):
    a,b,c=map(np.asarray,(a,b,c));normal=np.cross(b-a,c-a);normal/=np.linalg.norm(normal)
    shade=.74+.26*max(0,float((normal*[-1,1,-1])@np.array([-.35,.82,-.45])))
    shaded=[round(v*shade)for v in color]
    return [[*a,*shaded],[*b,*shaded],[*c,*shaded]]
def rgb(hex):return [(hex>>16)&255,(hex>>8)&255,hex&255]
def box(lo,hi,color):
    p=np.array([[x,y,z] for x,y,z in [(lo[0],lo[1],lo[2]),(hi[0],lo[1],lo[2]),(hi[0],hi[1],lo[2]),(lo[0],hi[1],lo[2]),(lo[0],lo[1],hi[2]),(hi[0],lo[1],hi[2]),(hi[0],hi[1],hi[2]),(lo[0],hi[1],hi[2])]])
    return [tri(p[a],p[b],p[c],color)for a,b,c in [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(3,7,6),(3,6,2),(0,4,7),(0,7,3),(1,2,6),(1,6,5)]]
def pipe_y(z):
    # Exact original guide_y is linear in this approved local interval.
    old_z=88.5-z
    assert -206<=old_z<=-58
    return -443+32*(old_z+209)/154-231.76
def fraction(z):
    if z<247:t=(z-242.5)/4.5
    elif z>259:t=(263.5-z)/4.5
    else:return 1.,0.
    q=t*t*t*(10+t*(-15+6*t));dq=30*t*t*(1-t)*(1-t)/4.5
    return q,dq if z<247 else -dq
def cylinder(a,b,r,color):
    a=np.array(a);b=np.array(b);t=b-a;t/=np.linalg.norm(t);q=np.cross(t,[1,0,0]);q/=np.linalg.norm(q);s=np.cross(t,q);ring=[q*math.cos(i*math.pi/8)+s*math.sin(i*math.pi/8)for i in range(16)];out=[]
    for i in range(16):u=ring[i]*r;v=ring[(i+1)%16]*r;out += [tri(a+u,a+v,b+v,color),tri(a+u,b+v,b+u,color),tri(a,a+v,a+u,color),tri(b,b+u,b+v,color)]
    return out

for ids in groups.values():
    a=world[ids];lo=a.min(axis=(0,1));hi=a.max(axis=(0,1));centre=(lo+hi)/2;size=hi-lo
    pipe=any(abs(centre[0]-x)<1e-5 for x in [8.35,10.65])
    kind=None;take=[]
    if pipe and abs(size[0]-.6)<1e-5 and size[2]>100:
        kind='continuous_service_pipe'
        # Original rings are normal to the source centreline, at half-integer Z.
        k=-32/154;z=world[ids,:,2];y=world[ids,:,1]
        ring_z=(z+k*(y-pipe_y(253.5))+k*k*253.5)/(1+k*k)
        ring_z=np.round(ring_z*2)/2
        take=[ids[j]for j in range(len(ids))if ring_z[j].min()>=242.5 and ring_z[j].max()<=263.5]
    elif pipe and lo[2]>=242 and hi[2]<=264 and abs(size[0]-.78)<1e-5 and abs(size[2]-.44)<1e-5:kind='service_pipe_collar';take=ids
    elif pipe and lo[2]>=242 and hi[2]<=264 and abs(size[0]-.24)<1e-5 and abs(size[1]-.5)<1e-5:kind='old_collar_support';take=ids
    elif abs(lo[0]-8)<1e-5 and abs(hi[0]-11)<1e-5 and lo[2]<257 and hi[2]>250 and abs(size[1]-1.7)<1e-5:
        kind='inspection_case';take=ids
        moved=original[ids].copy();moved[:,:,:3]=world[ids]+[0,pipe_y(244.125)-pipe_y(251.125),-7]
        add('service_bypass/inspection_case_z244_125',moved)
    if take:
        removed.update(take);selected.append({'kind':kind,'original_component_triangle_count':len(ids),'removed_triangle_count':len(take),'original_world_extrema':[*lo,*hi]})
assert sum(r['kind']=='continuous_service_pipe'for r in selected)==2
assert sum(r['kind']=='service_pipe_collar'for r in selected)==4
assert sum(r['kind']=='old_collar_support'for r in selected)==4
assert sum(r['kind']=='inspection_case'for r in selected)==1

anchors=[]
for side,old_x,new_x,wall_x,block_x,normal in [('west',8.35,4.8,6,6,[-1,0,0]),('east',10.65,14.2,13,12,[1,0,0])]:
    rows=[];centres=[]
    for z in np.linspace(242.5,263.5,169):
        q,dq=fraction(z);c=np.array([old_x+(new_x-old_x)*q,pipe_y(z),z]);t=np.array([(new_x-old_x)*dq,-32/154,1.]);t/=np.linalg.norm(t);u=np.cross(t,[1,0,0]);u/=np.linalg.norm(u);v=np.cross(t,u)
        rows.append(np.array([c+.30*(u*math.cos(i*math.pi/8)+v*math.sin(i*math.pi/8))for i in range(16)]));centres.append(c)
    triangles=[];color=rgb(0xa12d34)
    for j in range(len(rows)-1):
        for i in range(16):k=(i+1)%16;triangles += [tri(rows[j][i],rows[j][k],rows[j+1][k],color),tri(rows[j][i],rows[j+1][k],rows[j+1][i],color)]
    for i in range(16):k=(i+1)%16;triangles += [tri(centres[0],rows[0][k],rows[0][i],color),tri(centres[-1],rows[-1][i],rows[-1][k],color)]
    add('service_bypass/'+side+'/pipe_r030',triangles)
    for z in [251.5,255.5]:
        y=pipe_y(z);add(f'service_bypass/{side}/collar/{z}',cylinder([new_x,y,z-.22],[new_x,y,z+.22],.39,rgb(0xb3bab4)))
        # A real cantilever below the collar, fastened to the external shaft wall.
        beam_y=y-.49;lo=[min(new_x,wall_x),beam_y-.12,z-.12];hi=[max(new_x,wall_x),beam_y+.12,z+.12]
        add(f'service_bypass/{side}/wall_bracket/{z}',box(lo,hi,rgb(0x414e68)))
        # The .24m square face is inside one declared solid wall block.
        support=[block_x,math.floor(beam_y),math.floor(z)];anchors.append({'at':support,'state':'projectseele:nerv_structural_panel','face_point':[wall_x,beam_y,z],'normal':normal,'half_width':.12,'half_height':.12,'bracket':f'service_bypass/{side}/wall_bracket/{z}'})

ids=sorted(removed);before=original[ids].reshape(-1)
removed_sha=hashlib.sha256(b''.join(struct.pack('>d',float(v))for v in before)).hexdigest()
document={'schema':'projectseele.r52.exact-legacy-service-bypass.v1','original_running_source_sha256':SOURCE_SHA,'target_part':'legacy_original_retained','original_target_triangle_count':len(original),'removed_triangle_indices':ids,'removed_triangles_f64be_sha256':removed_sha,'components':components,'native_wall_faces':anchors,'root_plan':{'shaft_physical_box':[6,-847,250,13,-497,257],'authorized_z':[242,264],'pipe_ring_join_z':[242.5,263.5],'constant_x_z':[247,259],'west_x':4.8,'east_x':14.2,'pipe_radius':.30,'collar_radius':.39},'world_written':False}
OUT.mkdir(parents=True,exist_ok=True);target=OUT/'legacy_service_bypass_r52.json';target.write_text(json.dumps(document,separators=(',',':'))+'\n',encoding='utf-8')
report={'status':'ROOT_SELECTED_MESH_PUBLISHED_NATIVE_WORLD_PENDING'if args.publish else'MESH_CANDIDATE_NATIVE_FACES_AND_CASE_DESTINATION_PENDING_ROOT','world_written':False,'source_sha256':SOURCE_SHA,'overlay_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'selected_original_components':selected,'removed_triangles':len(ids),'added_components':len(components),'added_triangles':sum(len(c['triangles_rgb'])//18 for c in components),'native_wall_faces':anchors,'case_candidate':{'old_z_centre':251.125,'new_z_centre':244.125,'same_slope_y_shift':pipe_y(244.125)-pipe_y(251.125)},'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(OUT/'CANDIDATE_RECEIPT.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items()if k not in ['selected_original_components','native_wall_faces']},indent=2))
if args.publish:
    production=ROOT/'src/main/resources/assets/projectseele/mesh/legacy_service_bypass_r52.json';shutil.copyfile(target,production);assert production.read_bytes()==target.read_bytes();print('Published exact mesh resource',production)
