"""Original EVA palm plus clean articulated fingers in anatomical neutral.

The inherited curved finger shell is a shape reference, not reused as stretched
skin. New phalanges and covered hinges are built along the new straight axes.
"""
from pathlib import Path
import argparse,copy,json
import numpy as np
from scipy.spatial.transform import Rotation as R
from PIL import Image
import make_tiger_unit01_pack as tiger
from author_anatomical_hand_rig_r45 import model_matrix,unit

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--basis',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    c=json.loads((a.basis/'hand_rig_contract.json').read_text());key=c['rig'];name=f'eva_unit0{key}';geo=json.loads((ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/geo/{name}.geo.json').read_text());bs=geo['minecraft:geometry'][0]['bones'];bones={b['name']:b for b in bs};cache={};new_contract=copy.deepcopy(c);new_contract['new_bones']=[]
    v,uv,ns,tris=tiger.parse_obj(Path(c['source']).read_text());tiger.CLEAN_GRIP_FINGERS=False;fb,_,_=tiger.discover_finger_rig(v,tris);owners=tiger.complete_face_owners(v,tris,fb);minimum=min(p[1]for p in v);scale=192/(max(p[1]for p in v)-minimum);native=lambda p:(np.asarray(p)-[0,minimum,0])*[-1,1,-1]*scale/16
    tex=np.asarray(Image.open(ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/textures/entity/{name}.png').convert('RGBA'));light=tex[:,:tex.shape[1]//2,:3].astype(float).mean(2);light[tex[:,:tex.shape[1]//2,3]<250]=1e9;dy,dx=np.unravel_index(light.argmin(),light.shape);dark=np.array([(dx+.5)/tex.shape[1],(dy+.5)/tex.shape[0]])
    data=dict(format_version=1,model_height=192,stride=8,source='Original artist palm; new anatomical phalanges fitted to source dimensions, not voxel/hull reconstruction',parts={},jointSkins={},r37_mouth={'preserve_auto_joint_seams':True});quality=[]
    for side in ['l','r']:
        parent_hand='hand_'+side;n=unit(c['hands'][side]['palmar_normal_bind']);long=unit(c['hands'][side]['longitudinal_bind']);width=unit(np.cross(n,long));palm=[]
        def triangle(buf,points,texcoords,normals):
            if np.linalg.norm(np.cross(points[1]-points[0],points[2]-points[0]))<1e-12:return
            for xyz,t,nor in zip(points,texcoords,normals):buf.append((np.asarray(xyz),np.asarray(t),unit(nor)))
        for i,face in enumerate(tris):
            if owners[i]!=parent_hand:continue
            ps=np.asarray([native(v[r[0]])for r in face]);ts=np.asarray([[uv[r[1]][0]*.5,1-uv[r[1]][1]]for r in face]);normal=np.asarray([ns[r[2]]if r[2]>=0 else tiger.face_normal([v[x[0]]for x in face])for r in face])*[-1,1,-1];triangle(palm,ps,ts,normal)
        def emit(part,buf):
            pivot=np.asarray(bones[part]['pivot']);packed=[]
            for pos,t,nor in buf:packed.extend([*(pos*[-1,1,1]*16-pivot),*t,*(nor*[-1,1,1])])
            data['parts'][part]=dict(pivot=pivot.tolist(),vertices=np.round(packed,7).tolist());bind=model_matrix(bones,part,cache);data['jointSkins'][part]=dict(influences={part:[1.]*(len(packed)//8)},inverseBindColumnMajor={part:np.linalg.inv(bind).T.reshape(-1).tolist()})
        emit(parent_hand,palm)
        mcp_mean=np.mean([c['hands'][side]['digits'][d]['joints'][0]['head_bind']for d in ['index','middle','ring','little']],axis=0)
        for digit,d in c['hands'][side]['digits'].items():
            old=d['joints'];lengths=[j['length']for j in old]
            if digit=='thumb':
                joints=[np.array(old[0]['head_bind']),np.array(old[1]['head_bind'])];radial=joints[1]-mcp_mean;radial=unit(radial-n*(radial@n)-long*(radial@long));forward=unit(long+radial)
                joints += [joints[1]+forward*lengths[1],joints[1]+forward*(lengths[1]+lengths[2])]
            else:
                first=np.array(old[0]['head_bind']);joints=[first];
                for length in lengths:joints.append(joints[-1]+long*length)
            ids=d['source_faces'];srcpts=np.array([native(v[r[0]])for i in ids for r in tris[i]]);source_axis=unit(np.array(old[-1]['tip_bind'])-np.array(old[0]['head_bind']));cross=unit(np.cross(n,source_axis));depth=unit(np.cross(cross,source_axis));centre=srcpts.mean(0);along=(srcpts-np.array(old[0]['head_bind']))@source_axis;mid=srcpts[(along>np.quantile(along,.2))&(along<np.quantile(along,.8))]
            radii=[float((np.quantile((mid-centre)@axis,.9)-np.quantile((mid-centre)@axis,.1))*.5)for axis in [cross,depth]];total=sum(lengths);rx=float(np.clip(radii[0],total*.065,total*.12));rz=float(np.clip(radii[1],total*.065,total*.12));sample_uv=np.median([[uv[r[1]][0]*.5,1-uv[r[1]][1]]for i in ids for r in tris[i]if r[1]>=0],axis=0)
            parent=parent_hand;records=[]
            for j in range(3):
                head=joints[j];tail=joints[j+1];y=unit(tail-head);nn=unit(n-y*(n@y));x=unit(np.cross(nn,y));z=unit(np.cross(x,y));world=np.column_stack([x,y,z]);bp=model_matrix(bones,parent,cache);pivot=(np.linalg.inv(bp)@np.r_[head,1])[:3];rotation=bp[:3,:3].T@world;bone=old[j]['name'];spec=dict(name=bone,parent=parent,pivot=(pivot*[-1,1,1]*16).tolist(),rotation=(R.from_matrix(rotation).as_euler('xyz',degrees=True)*[-1,-1,1]).tolist());bs.append(spec);bones[bone]=spec;bind=model_matrix(bones,bone,cache);new_contract['new_bones'].append(spec)
                records.append(dict(old[j],head_bind=head.tolist(),tip_bind=tail.tolist(),length=float(np.linalg.norm(tail-head)),rest_flex_degrees=0.,local_bind_quaternion_xyzw=R.from_matrix(rotation).as_quat().tolist(),neutral_local_quaternion_xyzw=R.from_matrix(rotation).as_quat().tolist(),inverse_bind_column_major=np.linalg.inv(bind).T.reshape(-1).tolist(),angle_reference='New anatomical open bind; visible phalanx centre and bone axis share the same frame'))
                buf=[];length=float(np.linalg.norm(tail-head));r0=np.array([rx,rz])*(1-j*.08);r1=r0*.9;gap=min(length*.08,min(r0)*.25)
                # Twelve bevelled-oval stations: flat armour faces, softened
                # corners and a tapered distal end, with no box palm.
                rings=[];ring_count=16
                for pos,taper in [(gap,.88),(gap+min(r0)*.22,1),(length-gap-min(r0)*.22,.94),(length-gap,.80)]:
                    ratio=pos/length;rr=(r0*(1-ratio)+r1*ratio)*taper;ring=[]
                    for k in range(ring_count):
                        angle=2*np.pi*k/ring_count;xx=np.sign(np.cos(angle))*abs(np.cos(angle))**.72;zz=np.sign(np.sin(angle))*abs(np.sin(angle))**.72;ring.append(head+y*pos+x*xx*rr[0]+z*zz*rr[1])
                    rings.append(ring)
                for ring_a,ring_b in zip(rings,rings[1:]):
                    for k in range(ring_count):
                        nxt=(k+1)%ring_count;quad=[ring_a[k],ring_a[nxt],ring_b[nxt],ring_b[k]]
                        for ii in [(0,1,2),(0,2,3)]:
                            ps=np.array([quad[q]for q in ii]);normal=unit(np.cross(ps[1]-ps[0],ps[2]-ps[0]));triangle(buf,ps,[sample_uv]*3,[normal]*3)
                for ring,endnormal in [(rings[0],-y),(rings[-1],y)]:
                    centre_ring=np.mean(ring,axis=0)
                    for k in range(ring_count):triangle(buf,[centre_ring,ring[k],ring[(k+1)%ring_count]],[sample_uv]*3,[endnormal]*3)
                # Joint cover is spherical at the exact shared hinge centre.
                # Rotation cannot stretch it or uncover the mating segment.
                radius=min(r0)*.94;lat=8;lon=16;rows=[]
                for rr in range(lat+1):
                    phi=np.pi*rr/lat;rows.append([head+radius*(y*np.cos(phi)+np.sin(phi)*(x*np.cos(2*np.pi*k/lon)+z*np.sin(2*np.pi*k/lon)))for k in range(lon)])
                for aa,bb in zip(rows,rows[1:]):
                    for k in range(lon):
                        kk=(k+1)%lon;quad=[aa[k],aa[kk],bb[kk],bb[k]]
                        for ii in [(0,1,2),(0,2,3)]:ps=[quad[q]for q in ii];triangle(buf,ps,[dark]*3,[unit(q-head)for q in ps])
                emit(bone,buf);parent=bone
            new_contract['hands'][side]['digits'][digit]['joints']=records;quality.append(dict(side=side,digit=digit,lengths=lengths,radii=[rx,rz],visible_geometry_follows_bone_axis=True))
    for pose in new_contract['pose_controls'].values():pose.pop('bone_angles',None)
    new_contract.pop('thumb_opposition_solver',None);new_contract.pop('armour_segmentation',None);new_contract['construction']=dict(original_palm_preserved=True,fingers='New anatomical-neutral phalanges fitted to original source lengths, width and colours; rigid armour plus closed joint covers',dimensions=quality,visual_passed=False)
    (a.out/(name+'.geo.json')).write_text(json.dumps(geo,indent=2),'utf8');(a.out/(name+'_anatomical_hands_r45.mesh.json')).write_text(json.dumps(data,separators=(',',':')),'utf8');(a.out/'hand_rig_contract.json').write_text(json.dumps(new_contract,indent=2),'utf8');print('Built original-palm hand with straight anatomical finger meshes and30new joint controls')
if __name__=='__main__':main()
