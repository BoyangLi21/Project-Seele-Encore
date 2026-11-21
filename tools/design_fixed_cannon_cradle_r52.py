"""Independent source-geometry proposal only. Never edit production code/world or the frozen gun grips."""
from pathlib import Path
import json,hashlib,struct,gzip,math
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.Codex/r52_operations/cradle_candidate'
CAL=ROOT/'.Codex/r52_operations/calibration_powered'
FACE=np.array([[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]])
def box(lo,hi):
    x,y,z=lo;X,Y,Z=hi
    return np.array([[x,y,z],[X,y,z],[X,Y,z],[x,Y,z],[x,y,Z],[X,y,Z],[X,Y,Z],[x,Y,Z]])[FACE]
def beam(a,b,radius,sides=12,inner=0):
    a,b=np.asarray(a),np.asarray(b);axis=b-a;axis/=np.linalg.norm(axis)
    u=np.cross(axis,[0,1,0])
    if np.linalg.norm(u)<.1:u=np.cross(axis,[1,0,0])
    u/=np.linalg.norm(u);v=np.cross(axis,u);angles=np.arange(sides)*2*np.pi/sides
    ring=np.cos(angles)[:,None]*u+np.sin(angles)[:,None]*v;verts=[]
    for i in range(sides):
        j=(i+1)%sides;p=a+ring[i]*radius;q=a+ring[j]*radius;r=b+ring[i]*radius;s=b+ring[j]*radius
        verts.extend([[p,q,r],[q,s,r]])
        if inner:
            P=a+ring[i]*inner;Q=a+ring[j]*inner;R=b+ring[i]*inner;S=b+ring[j]*inner
            verts.extend([[P,R,Q],[Q,R,S],[p,P,q],[q,P,Q],[r,s,R],[s,S,R]])
        else:verts.extend([[a,q,p],[b,r,s]])
    return np.asarray(verts)
def prism(top,normal,depth):
    bottom=top+normal*depth;out=[top,bottom[::-1]]
    for i in range(3):j=(i+1)%3;out.extend([[top[i],bottom[i],top[j]],[top[j],bottom[i],bottom[j]]])
    return np.asarray(out)
def sphere(centre,radius):
    rings=[]
    for i in range(9):
        a=np.pi*i/8;rings.append(np.array([np.array(centre)+radius*np.array([np.sin(a)*np.cos(b),np.cos(a),np.sin(a)*np.sin(b)]) for b in np.arange(16)*np.pi/8]))
    out=[]
    for i in range(8):
        for j in range(16):k=(j+1)%16;out.extend([[rings[i][j],rings[i+1][j],rings[i][k]],[rings[i][k],rings[i+1][j],rings[i+1][k]]])
    return np.asarray(out)
def write_cloud(path,parts):
    def word(s):b=s.encode();return struct.pack('>H',len(b))+b
    out=bytearray(struct.pack('>iii',0x52353243,1,len(parts)))
    for name,t in parts.items():
        v=np.asarray(t,dtype='>f4').reshape(-1,3);out+=word(name)+word(hashlib.sha256(v.tobytes()).hexdigest())+struct.pack('>i',len(v))+v.tobytes()
    path.write_bytes(gzip.compress(out))
def main():
    OUT.mkdir(parents=True,exist_ok=True);c=json.loads((CAL/'STATION_CANDIDATE.json').read_text());src=ROOT/'build/resources/main/assets/projectseele/mesh/positron_cannon_payload_r50.mesh.json';raw=json.loads(src.read_text());points=[];normals=[]
    for part in raw['parts'].values():
        v=np.asarray(part['vertices']).reshape(-1,raw['stride']);points.append(v[:,:3]+part['pivot']);normals.append(np.column_stack((-v[:,5],v[:,6],v[:,7])))
    points=np.concatenate(points);lo,hi=points.min(0),points.max(0);centre=(lo+hi)/2;centre[1]=lo[1];points=(points-centre)/16;points[:,0]*=-1;tri=points.reshape(-1,3,3)
    rotation=Rotation.from_quat(c['mesh_frame']['quaternion_xyzw']).as_matrix();normal=np.concatenate(normals).reshape(-1,3,3).mean(1)@rotation.T
    gun=np.array(c['mesh_frame']['translation'])+tri@rotation.T*8
    # Largest real downward-facing source material patch in each separated
    # barrel/receiver band; no legacy marker or invented grip is used.
    area=np.linalg.norm(np.cross(gun[:,1]-gun[:,0],gun[:,2]-gun[:,0]),axis=1)/2;centre_local=tri.mean(1);indices=[]
    for a,b in [(2,3),(6.9,7.4)]:
        valid=np.where((centre_local[:,1]>a)&(centre_local[:,1]<b)&(normal[:,1]<-.65))[0];indices.append(int(valid[np.argmax(area[valid])]))
    anchors=[]
    for index in indices:
        n=normal[index]/np.linalg.norm(normal[index]);patch=gun[index].mean(0)+(gun[index]-gun[index].mean(0))*.65
        anchors.append(dict(source_triangle=index,source_triangle_local=tri[index].tolist(),patch_top_relative_gun_root=patch.tolist(),normal=n.tolist(),contact_centroid_relative_gun_root=patch.mean(0).tolist(),source_area_m2=float(area[index]),pad_area_m2=float(area[index]*.65**2)))
    cradle=dict(schema='projectseele.fixed-cannon-cradle-r52.geometry-candidate.v1',production_installed=False,world_written=False,source_mesh_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),gun_candidate_sha256=hashlib.sha256((CAL/'STATION_CANDIDATE.json').read_bytes()).hexdigest(),gun_grips_changed=False,bay=c['raised_position'],closed_actor_root=[c['raised_position'][0],157.5,c['raised_position'][2]],floor_top=160,hatch_plane=174.02,stroke=16.5,contacts=anchors,clock='rise = sameGunRootY - 157.5; no independent age/state',platform_closed_bottom=163.2,platform_thickness=.3,telescopic_stages=6,sleeve_length=2.9,full_stroke_overlap=.15,aim='saddle top/normal use the same synchronized gun AIM around the same measured pivot; struts join platform to saddle underside analytically',scope='Geometry/contact and paired-sweep proposal, not native installation acceptance')
    (OUT/'CRADLE_CANDIDATE.json').write_text(json.dumps(cradle,indent=2))
    pivot=np.array(c['mesh_frame']['translation'])+rotation@(np.array(c['aim_pivot_local'])*8)
    cradle['aim_strut_contract']='Two fixed-length telescoping members per support, analytic endpoint axis from the same AIM; reject if overlap below 0.15m or total span below one member+0.15m'
    # Independent pure geometry builder, ready to be ported only after Root approval.
    def build(root_y,aim):
        s=root_y-157.5;parts={};centres=[];lengths=[];A=Rotation.from_quat(aim)
        for i,a in enumerate(anchors):
            rest=np.array(a['contact_centroid_relative_gun_root']);p=pivot+A.apply(rest-pivot);n=A.apply(np.array(a['normal']));xz=rest[[0,2]];centres.append(xz);world_p=p+np.array([0,root_y,0]);patch=pivot+A.apply(np.array(a['patch_top_relative_gun_root'])-pivot)+np.array([0,root_y,0])
            parts[f'saddle_{i}']=prism(patch,n,.12)
            parts[f'floor_plate_{i}']=box([xz[0]-1.5,160,xz[1]-1.5],[xz[0]+1.5,160.3,xz[1]+1.5])
            parts[f'outer_cylinder_{i}']=beam([xz[0],160.3,xz[1]],[xz[0],163.2,xz[1]],1.25,16,1.19)
            for k in range(1,7):
                r=1.25-k*.1;y=160.3+s*k/6;parts[f'sleeve_{i}_{k}']=beam([xz[0],y,xz[1]],[xz[0],y+2.9,xz[1]],r,16,r-.055)
            parts[f'crosshead_{i}']=box([xz[0]-2.0,163.2+s,xz[1]-2.0],[xz[0]+2.0,163.5+s,xz[1]+2.0])
            base=np.array([xz[0],163.75+s,xz[1]]);end=world_p+n*.37
            rest_length=np.linalg.norm(rest+np.array(a['normal'])*.37+np.array([0,157.5,0])-np.array([xz[0],163.75,xz[1]]));member=rest_length*.8
            span=np.linalg.norm(end-base);axis=(end-base)/span;overlap=2*member-span;admitted=overlap>=.15 and span>=member+.15
            lengths.append(dict(support=i,actual_span=float(span),fixed_member_length=float(member),overlap=float(overlap),mechanism_range_admitted=bool(admitted)))
            parts[f'aim_outer_tube_{i}']=beam(base,base+axis*member,.28,12,.23)
            parts[f'aim_inner_rod_{i}']=beam(end-axis*member,end,.2,12)
            parts[f'upper_ball_joint_{i}']=sphere(end,.25);parts[f'lower_ball_joint_{i}']=sphere(base,.25)
        delta=centres[1]-centres[0];cross=np.array([-delta[1],delta[0]])/np.linalg.norm(delta)
        for side in [-1,1]:
            a=centres[0]+cross*(1.7*side);b=centres[1]+cross*(1.7*side)
            parts[f'platform_rail_{side}']=beam([a[0],161.0+s,a[1]],[b[0],161.0+s,b[1]],.2,8)
            for index,p in enumerate([a,b]):parts[f'rail_hanger_{side}_{index}']=beam([p[0],161.0+s,p[1]],[p[0],163.2+s,p[1]],.12,8)
        # World-relative bay Y for comparison/render, common XYZ physical frame.
        return {name:t-np.array([0,174,0]) for name,t in parts.items()},lengths
    aim_rows=[]
    for state,root_y,aim in [('closed',157.5,[0,0,0,1]),('raised',174.,[0,0,0,1])]+[(f'aim_{axis}_{degrees}',174.,Rotation.from_euler(axis,degrees,degrees=True).as_quat().tolist()) for axis in ['x','y','z'] for degrees in [-2,2]]:
        parts,lengths=build(root_y,aim);write_cloud(OUT/f'cradle_{state}.bin.gz',parts)
        all_points=np.concatenate(list(parts.values())).reshape(-1,3);cradle[state+'_bounds_relative_bay']=[all_points.min(0).tolist(),all_points.max(0).tolist()]
        cradle[state+'_pieces']=len(parts)
        aim_rows.append(dict(state=state,actor_root_y=root_y,aim_xyzw=aim,struts=lengths))
    cradle['aim_geometry_samples']=aim_rows
    (OUT/'CRADLE_CANDIDATE.json').write_text(json.dumps(cradle,indent=2))
    print(json.dumps(cradle,indent=2))
if __name__=='__main__':main()
