"""New anatomical hand chains on the original EVA artist surfaces.

Rest flex is calibrated from the source shape. Anatomical zero is not assumed
to equal the authored relaxed hand. No boxes, convex hulls or voxel replacement.
"""
from pathlib import Path
import argparse,collections,copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
import make_tiger_unit01_pack as tiger
from recover_original_eva_hands_r45 import SOURCES

ROOT=Path(__file__).resolve().parents[1]
def unit(v):return np.asarray(v)/max(np.linalg.norm(v),1e-12)
def smooth(t):
    t=np.clip(t,0,1);return t*t*t*(10+t*(-15+6*t))
def model_matrix(bones,name,cache):
    if name in cache:return cache[name].copy()
    b=bones[name];p=np.asarray(b['pivot'])*[-1,1,1]/16;xyz=np.radians(np.asarray(b.get('rotation',[0,0,0]))*[-1,-1,1]);rot=R.from_euler('xyz',xyz).as_matrix();m=np.eye(4);m[:3,:3]=rot;m[:3,3]=p-rot@p
    if b.get('parent'):m=model_matrix(bones,b['parent'],cache)@m
    cache[name]=m;return m.copy()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rig',type=int,choices=range(3),required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    src=ROOT/SOURCES[a.rig];v,uv,ns,tris=tiger.parse_obj(src.read_text());tiger.CLEAN_GRIP_FINGERS=False;face_bones,pivots,_=tiger.discover_finger_rig(v,tris);owners=tiger.complete_face_owners(v,tris,face_bones)
    roots,frames,palms=tiger.fingerfix.recover_finger_frames(v,tris,face_bones,owners,pivots,tiger.FINGER_ORDER,tiger.FINGER_ROOT_EMBED)
    geo_path=ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/geo/eva_unit0{a.rig}.geo.json';geo=json.loads(geo_path.read_text());bone_list=geo['minecraft:geometry'][0]['bones'];bones={b['name']:b for b in bone_list};cache={}
    minimum=min(x[1]for x in v);scale=192/(max(x[1]for x in v)-minimum);to_native=lambda x:(np.asarray(x)-[0,minimum,0])*[-1,1,-1]*scale/16
    def group(n):
        if n.startswith('finger_'):return n.split('_')[1]
        return 'forearm'if n.startswith('forearm_')else'palm'
    adjacency=collections.defaultdict(set)
    for i,face in enumerate(tris):
        for ref in face:adjacency[tuple(np.round(v[ref[0]],6))].add(group(owners[i]))
    result=dict(schema='projectseele.anatomical-hands.r45.v1',rig=a.rig,source=str(src),source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),reference='User hand_rig17-joint example: independent phalanges, thumb opposition, local limits; EVA source determines shape/proportions',hands={},new_bones=[])
    exported=dict(format_version=1,model_height=192,stride=8,source='Original EVA source surfaces with newly measured anatomical controls',parts={},jointSkins={},r37_mouth={'preserve_auto_joint_seams':True})
    for side in ['l','r']:
        hand='hand_'+side;chains={};palm_normal=unit(np.asarray(palms[side]['normal_runtime']))
        forearm=to_native(tiger.SOURCE_PIVOTS[hand])-to_native(tiger.SOURCE_PIVOTS['forearm_'+side]);longitudinal=unit(forearm-palm_normal*(forearm@palm_normal));neutral_x=unit(np.cross(palm_normal,longitudinal));neutral_z=unit(np.cross(neutral_x,longitudinal));neutral_world=np.column_stack([neutral_x,longitudinal,neutral_z])
        hand_data=dict(parent=hand,palmar_normal_bind=palm_normal.tolist(),longitudinal_bind=longitudinal.tolist(),digits={})
        for digit in ['index','middle','ring','little','thumb']:
            fr=frames['finger_'+digit+'_'+side];p0=to_native(fr['mcp_source']);tangent=unit(np.asarray(fr['bind_tangent_runtime']));indices=[i for i in range(len(tris))if group(owners[i])==digit and owners[i].endswith('_'+side)]
            points=np.unique(np.array([to_native(v[ref[0]])for i in indices for ref in tris[i]]),axis=0);along=(points-p0)@tangent;length=float(np.quantile(along,.995));assert length>.02
            fractions=[0,.48,.77,1.]if digit!='thumb'else[0,.45,.76,1.];joints=[p0]
            # Measured cross-section centroids retain the artist's curved axes.
            for f in fractions[1:]:
                distance=length*f;width=length*.18;weights=np.exp(-((along-distance)/width)**2);centre=(points*weights[:,None]).sum(0)/weights.sum();radial=centre-p0-tangent*((centre-p0)@tangent);joints.append(p0+tangent*distance+radial)
            if digit=='thumb':
                # The visible welded seam is MCP, not the carpometacarpal
                # joint. Put CMC inside the palm, retaining two visible
                # phalanges instead of compressing three into the old thumb.
                palm_centre=to_native(palms[side]['center_source'])
                cmc=palm_centre*.55+p0*.45+np.array([0,.025,0])
                distance=length*.55;weights=np.exp(-((along-distance)/(length*.18))**2);centre=(points*weights[:,None]).sum(0)/weights.sum();radial=centre-p0-tangent*((centre-p0)@tangent)
                joints=[cmc,p0,p0+tangent*distance+radial,joints[3]]
            names=[];binds=[];biases=[];lengths=[];parent=hand;previous_y=None;previous_x=None
            for j in range(3):
                y=unit(joints[j+1]-joints[j]);normal=unit(palm_normal-y*(palm_normal@y));x=unit(np.cross(normal,y));z=unit(np.cross(x,y));world_rotation=np.column_stack([x,y,z]);assert np.linalg.det(world_rotation)>.9999
                if digit=='thumb':bias=0.
                elif j==0:bias=float(np.degrees(np.arcsin(np.clip(y@palm_normal,-1,1))))
                else:bias=float(-np.degrees(np.arctan2(previous_x@np.cross(previous_y,y),np.clip(previous_y@y,-1,1))))
                name=f'r45_hand_{side}_{digit}_{j+1}';bm=model_matrix(bones,parent,cache);joint_native=(np.linalg.inv(bm)@np.r_[joints[j],1])[:3];local_rotation=bm[:3,:3].T@world_rotation;euler=R.from_matrix(local_rotation).as_euler('xyz',degrees=True)*[-1,-1,1]
                spec=dict(name=name,parent=parent,pivot=(joint_native*[-1,1,1]*16).tolist(),rotation=euler.tolist());bone_list.append(spec);bones[name]=spec;bind=model_matrix(bones,name,cache)
                assert np.linalg.norm((bind@np.r_[joint_native,1])[:3]-joints[j])<1e-7
                limits=[[-20,90],[-15,15],[-25,25]]if j==0 else[[-5 if j==1 else -10,110 if j==1 else 90],[0,0],[0,0]]
                if digit=='thumb':limits=[[-30,65],[-45,45],[-60,45]]if j==0 else[[-10,80 if j==1 else 85],[0,0],[-10,10]if j==1 else[0,0]]
                neutral_local=local_rotation if digit=='thumb'else (bm[:3,:3].T@neutral_world if j==0 else np.eye(3))
                record=dict(name=name,index=j,head_bind=joints[j].tolist(),tip_bind=joints[j+1].tolist(),length=float(np.linalg.norm(joints[j+1]-joints[j])),rest_flex_degrees=bias,angle_reference='authored thumb rest'if digit=='thumb'else'complete anatomical neutral frame; flex AND transverse bias calibrated',anatomical_limits_degrees=limits,local_bind_quaternion_xyzw=R.from_matrix(local_rotation).as_quat().tolist(),neutral_local_quaternion_xyzw=R.from_matrix(neutral_local).as_quat().tolist(),inverse_bind_column_major=np.linalg.inv(bind).T.reshape(-1).tolist())
                binds.append(record);names.append(name);biases.append(bias);lengths.append(record['length']);parent=name;previous_x=x;previous_y=y;result['new_bones'].append(spec)
            chains[digit]=dict(joints=np.asarray(joints),names=names,length=length,tangent=tangent,root=p0,bias=biases)
            hand_data['digits'][digit]=dict(joints=binds,source_rest='Author relaxed shape; controller delta X = rest_flex - anatomical_flex',source_faces=indices)
        palette=[hand,'forearm_'+side]+[n for d in chains.values()for n in d['names']];bone_index={n:i for i,n in enumerate(palette)}
        def point_weights(point,masses):
            w=np.zeros(len(palette));w[0]=masses.get('palm',0);w[1]=masses.get('forearm',0)
            for digit,c in chains.items():
                mass=masses.get(digit,0)
                if mass<=0:continue
                distances=[np.linalg.norm(point-q)for q in c['joints']];segment=int(np.argmin([np.linalg.norm(point-(q+r)*.5)for q,r in zip(c['joints'],c['joints'][1:])]))
                w[bone_index[c['names'][segment]]]+=mass
                # Narrow continuous bands at joints; phalanx armour stays rigid.
                for joint_index in [1,2]:
                    q=c['joints'][joint_index];axis=unit(c['joints'][joint_index+1]-c['joints'][joint_index-1]);d=(point-q)@axis;width=c['length']*.095
                    if abs(d)<width and segment in [joint_index-1,joint_index]:
                        w[bone_index[c['names'][segment]]]-=mass;alpha=float(smooth((d/width+1)*.5));w[bone_index[c['names'][joint_index-1]]]+=mass*(1-alpha);w[bone_index[c['names'][joint_index]]]+=mass*alpha;break
            w=np.maximum(w,0);return w/w.sum()
        selected=[i for i in range(len(tris))if owners[i]==hand or owners[i].startswith('finger_')and owners[i].endswith('_'+side)];packed=[];weights=[];area=0.;after_area=0.
        for i in selected:
            refs=tris[i];xyz=np.asarray([to_native(v[r[0]])for r in refs]);tex=np.asarray([uv[r[1]]if r[1]>=0 else[0,0]for r in refs]);normal=np.asarray([ns[r[2]]if r[2]>=0 else tiger.face_normal([v[x[0]]for x in refs])for r in refs])*[-1,1,-1]
            masses=[]
            groups=['palm','forearm','index','middle','ring','little','thumb']
            for ref in refs:
                touched=adjacency[tuple(np.round(v[ref[0]],6))];valid=[g for g in touched if g in groups];masses.append([1/len(valid)if g in valid else 0 for g in groups])
            pieces=[(xyz,tex,normal,np.asarray(masses))]
            for _ in range(2):
                more=[]
                for arrays in pieces:
                    mids=[(x+np.roll(x,-1,axis=0))*.5 for x in arrays]
                    for ids in [(0,3,5),(3,1,4),(5,4,2),(3,4,5)]:more.append(tuple(np.concatenate([x,m])[list(ids)]for x,m in zip(arrays,mids)))
                pieces=more
            area+=np.linalg.norm(np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0]))*.5
            for ps,ts,normal,ms in pieces:
                after_area+=np.linalg.norm(np.cross(ps[1]-ps[0],ps[2]-ps[0]))*.5
                for pos,t,n,mg in zip(ps,ts,normal,ms):
                    w=point_weights(pos,dict(zip(groups,mg)));weights.append(w);point=pos*[-1,1,1]*16-np.asarray(bones[hand]['pivot']);n=unit(n)*[-1,1,1];packed.extend([*point,t[0]*.5,1-t[1],*n])
        assert abs(area-after_area)<1e-8
        weights=np.asarray(weights);exported['parts'][hand]=dict(pivot=bones[hand]['pivot'],vertices=np.round(packed,7).tolist());exported['jointSkins'][hand]=dict(influences={n:np.round(weights[:,i],7).tolist()for i,n in enumerate(palette)},inverseBindColumnMajor={n:np.linalg.inv(model_matrix(bones,n,cache)).T.reshape(-1).tolist()for n in palette})
        hand_data.update(original_faces=len(selected),triangles=len(packed)//24,original_surface_area=area,exported_surface_area=after_area);result['hands'][side]=hand_data
    result['pose_controls']={
        'relaxed':{'fingers':[12,18,8],'thumb':[[2,5,12],[8,0,0],[6,0,0]]},
        'open':{'fingers':[0,0,0],'thumb':[[0,0,18],[0,0,0],[0,0,0]]},
        'spread':{'fingers':[0,0,0],'splay':{'index':-12,'middle':-3,'ring':7,'little':17},'thumb':[[0,0,30],[0,0,0],[0,0,0]]},
        'fist':{'fingers':[85,100,65],'thumb':[[25,25,-25],[45,0,0],[45,0,0]]},
        'grab':{'fingers':[38,50,28],'thumb':[[15,10,-15],[25,0,0],[20,0,0]]},
        'rifle_right':{'fingers':[67,82,48],'index':[12,24,8],'thumb':[[25,25,-20],[42,0,0],[30,0,0]]},
        'rifle_left':{'fingers':[48,63,32],'thumb':[[18,15,-15],[30,0,0],[24,0,0]]},
        'knife':{'fingers':[74,92,58],'thumb':[[28,25,-25],[45,0,0],[38,0,0]]},
        'support':{'fingers':[0,0,4],'splay':{'index':-6,'middle':-2,'ring':4,'little':10},'thumb':[[0,0,25],[4,0,0],[0,0,0]]}}
    result['angle_convention']='Desired local rotation=neutral_local*Rz(side*splay)*Ry(side*twist)*Rx(-flexion). Mesh inverse-bind still refers to artist rest. Neutral corrects complete3D rest orientation, not just scalar flex.'
    name=f'eva_unit0{a.rig}';(a.out/(name+'.geo.json')).write_text(json.dumps(geo,indent=2),'utf8');(a.out/(name+'_anatomical_hands_r45.mesh.json')).write_text(json.dumps(exported,separators=(',',':')),'utf8');(a.out/'hand_rig_contract.json').write_text(json.dumps(result,indent=2),'utf8')
    print('New independent anatomical chains',a.rig,'bones',len(result['new_bones']),'original surfaces preserved')
    print({side:{d:[round(j['rest_flex_degrees'],2)for j in x['joints']]for d,x in h['digits'].items()}for side,h in result['hands'].items()})

if __name__=='__main__':main()
