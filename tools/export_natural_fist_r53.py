"""Installable palm-side fist targets; preserve the articulated open hand."""
import os,sys,json,zipfile,hashlib,argparse
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import matrices,controls

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--jar',type=Path,required=True)
parser.add_argument('--sculpt',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--previous-surface-jar',type=Path,action='append',default=[],help='Installed surface-only revisions whose held poses must remain loadable')
args=parser.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
z=zipfile.ZipFile(args.jar)
prefix='assets/projectseele/'
flip=np.array([-1.,1,1])
def asset(n):return json.loads(z.read(prefix+n))
def qm(a,b):return np.r_[a[3]*b[:3]+b[3]*a[:3]+np.cross(a[:3],b[:3]),a[3]*b[3]-a[:3]@b[:3]]
def evaluate(raw,pivot,skin,ms,hand):
    points=(raw[:,:3]+pivot)*flip/16;normals=raw[:,5:8]*flip
    names=sorted(skin['influences']);weights=np.array([skin['influences'][n]for n in names]).T
    q=[];d=[]
    for name in names:
        m=np.linalg.inv(ms[hand])@ms[name]@np.asarray(skin['inverseBindColumnMajor'][name]).reshape(4,4).T
        rotation=R.from_matrix(m[:3,:3]).as_quat();q.append(rotation);d.append(.5*qm(np.r_[m[:3,3],0],rotation))
    q=np.array(q);d=np.array(d);signed=weights*np.where(q[weights.argmax(1)]@q.T<0,-1,1)
    real=signed@q;dual=signed@d;length=np.linalg.norm(real,axis=1)[:,None];real/=length;dual/=length;dual-=real*(real*dual).sum(1)[:,None]
    xyz=real[:,:3];w=real[:,3:]
    def rotate(p):
        cross=2*np.cross(xyz,p);return p+w*cross+np.cross(xyz,cross)
    translation=2*(-dual[:,3:]*xyz+w*dual[:,:3]+np.cross(xyz,dual[:,:3]))
    return rotate(points)+translation,rotate(normals)
def smooth_normals(points):
    tri=points.reshape(-1,3,3);face=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    _,idx=np.unique(np.round(points,7),axis=0,return_inverse=True)
    totals=np.zeros((idx.max()+1,3));np.add.at(totals,idx,np.repeat(face,3,axis=0))
    n=totals[idx];return n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)

base_geo=asset('geo/eva_unit01.geo.json');base_bones={b['name']:b for b in base_geo['minecraft:geometry'][0]['bones']}
sources=asset('eva/eva_original_mesh_geometry_r52_sources.json')
predecessor=dict(sources['resources'])
written={}
for unit in range(3):
    stem=f'eva_unit0{unit}';geo=asset('geo/'+stem+'.geo.json');contract=asset(f'hand_rigs/unit0{unit}/hand_rig_contract.json')
    mesh=asset('mesh/'+stem+'_anatomical_hands_r45.mesh.json');bones={b['name']:b for b in geo['minecraft:geometry'][0]['bones']}
    for side in ('l','r'):
        hand='hand_'+side;forearm='forearm_'+side
        authored=np.load(args.sculpt/f'natural_fist_{side}.npz')
        part=mesh['parts'][hand];skin=mesh['jointSkins'][hand];raw=np.array(part['vertices']).reshape(-1,8)
        if len(raw)!=40656:raise ValueError('Unexpected hand source topology')
        skin_count=int(authored['skin_vertex_count']);plate_count=int(authored['plate_vertex_count']);cuff_count=int(authored['cuff_vertex_count'])
        if len(authored['plate_rest'])!=plate_count or len(authored['bridge_rest'])!=cuff_count or len(authored['target'])!=skin_count+plate_count+cuff_count:
            raise ValueError('Authored hand surface counts differ')
        pivot=np.array(part['pivot']);wrist=pivot*flip/16;base_wrist=np.array(base_bones[hand]['pivot'])*flip/16
        shift=wrist-base_wrist
        plate=authored['plate_rest']+shift
        old_plate=(raw[skin_count:,:3]+pivot)*flip/16
        source_uv=raw[skin_count:,3:5].copy()
        plate_raw=np.zeros((plate_count,8));plate_raw[:,:3]=plate*flip*16-pivot
        # Keep the original tiny colour swatch, but give every surface a
        # continuous chart. Nearest-vertex UVs collapse most triangle tangents
        # even when every vertex samples the same diffuse/normal-map texel.
        uv_min=source_uv.min(0);uv_span=source_uv.max(0)-uv_min
        if np.any(uv_span<=0):raise ValueError('Dorsal source colour swatch has no UV extent')
        plate_raw[:,3:5]=uv_min+authored['plate_uv']*uv_span
        uv=plate_raw[:,3:5].astype(np.float32).reshape(-1,3,2)
        u=uv[:,1]-uv[:,0];v=uv[:,2]-uv[:,0];det=u[:,0]*v[:,1]-u[:,1]*v[:,0]
        if np.any(np.abs(det)<=1e-18):raise ValueError('Dorsal shell has a degenerate float32 UV triangle')
        plate_raw[:,5:8]=smooth_normals(plate)*flip
        raw=np.vstack([raw[:skin_count],plate_raw])
        for bone,weights in skin['influences'].items():
            skin['influences'][bone]=weights[:skin_count]+[1. if bone==hand else 0.]*plate_count
        bridge=authored['bridge_rest']+shift;far=authored['bridge_forearm_weights']
        rest=(raw[:,:3]+pivot)*flip/16;nearest=cKDTree(rest).query(bridge)[1]
        bridge_raw=np.zeros((len(bridge),8));bridge_raw[:,:3]=bridge*flip*16-pivot
        bridge_raw[:,3:5]=raw[nearest,3:5];bridge_raw[:,5:8]=smooth_normals(bridge)*flip
        old_count=len(raw);raw=np.vstack([raw,bridge_raw]);part['vertices']=raw.reshape(-1).tolist()
        part['handSurfaceLayoutR53']={'skin_vertex_count':skin_count,'plate_vertex_count':plate_count,'cuff_vertex_count':cuff_count}
        for bone,values in skin['influences'].items():
            weights=np.array(values);skin['influences'][bone]=np.r_[weights,weights[nearest]*(1-far)].tolist()
        skin['influences'][forearm]=np.r_[np.zeros(old_count),far].tolist()
        bind=matrices(geo,contract,side)
        skin['inverseBindColumnMajor'][forearm]=np.linalg.inv(bind[forearm]).T.reshape(-1).tolist()
        ms=matrices(geo,contract,side,controls(contract,'fist',side))
        current,normals=evaluate(raw,pivot,skin,ms,hand)
        target=authored['target'].copy()+shift
        # The far cuff belongs to the forearm at every pose, including release.
        target[old_count:][far>0]=current[old_count:][far>0]
        delta=(target-current)*flip*16
        target_normals=np.vstack([smooth_normals(target[:skin_count]),smooth_normals(target[skin_count:old_count]),smooth_normals(target[old_count:])])
        if np.median(np.sum(target_normals*normals,axis=1))<0:target_normals=-target_normals
        normal_delta=(target_normals-normals)*flip
        normal_delta[old_count:][far>0]=0
        limit=float(np.ceil(np.max(np.abs(delta))*10)/10+.1)
        if limit>8:raise ValueError(('Corrective exceeds anatomical asset limit',limit))
        targets={}
        for digit in contract['hands'][side]['digits'].values():
            for joint in digit['joints']:
                name=joint['name'];targets[name]=R.from_matrix(ms[bones[name]['parent']][:3,:3].T@ms[name][:3,:3]).as_quat().tolist()
        selected=np.flatnonzero((np.linalg.norm(delta,axis=1)+np.linalg.norm(normal_delta,axis=1))>1e-8)
        rows=np.c_[selected,delta[selected],normal_delta[selected]]
        skin['contactCorrectiveR45']={
            'activation_degrees':30,'position_limit_model':limit,
            'local_quaternion_xyzw':targets,'vertex_index_position_normal_delta':np.round(rows,8).tolist(),
            'source':'CC0 MakeHuman continuous fist; complete palm rotated about wrist; forearm-owned cuff rim. Open and weapon calibration retained.'}
        leakage=[]
        for pose in contract['pose_controls']:
            try:other=matrices(geo,contract,side,controls(contract,pose,side))
            except(KeyError,IndexError,TypeError):continue
            distance=max(2*np.arccos(np.clip(abs(R.from_matrix(other[bones[n]['parent']][:3,:3].T@other[n][:3,:3]).as_quat()@q),0,1))for n,q in targets.items())
            if distance<np.radians(30)-1e-5:leakage.append(pose)
        print(unit,side,'full-fist deformation',round(float(np.max(np.abs(delta))),3),'active controls',leakage)
        if any('rifle' in n or 'knife' in n or 'cannon' in n for n in leakage):raise ValueError('Weapon corrective overlap')
    relative='mesh/'+stem+'_anatomical_hands_r45.mesh.json';destination=out/(stem+'_anatomical_hands_r45.mesh.json')
    data=json.dumps(mesh,separators=(',',':')).encode();destination.write_bytes(data);written[prefix+relative]=str(destination)
    # Required runtime asset binding, not a comparison or validation receipt.
    def update(obj):
        if isinstance(obj,dict):
            for key,value in obj.items():
                if key==relative and isinstance(value,str):obj[key]=hashlib.sha256(data).hexdigest()
                else:update(value)
        elif isinstance(obj,list):
            for value in obj:update(value)
    update(sources)
sources['held_hand_surface_predecessors']=[predecessor]
for previous_jar in args.previous_surface_jar:
    with zipfile.ZipFile(previous_jar)as previous:
        selection=json.loads(previous.read(prefix+'eva/eva_original_mesh_geometry_r52_sources.json'))
    for candidate in [selection['resources'],*selection.get('held_hand_surface_predecessors',[])]:
        if candidate.keys()!=predecessor.keys() or any(candidate[k]!=v for k,v in predecessor.items() if '_anatomical_hands_r45.mesh.json' not in k):
            raise ValueError('Held surface migration cannot change a body, skeleton or hand contract')
        if candidate not in sources['held_hand_surface_predecessors']:sources['held_hand_surface_predecessors'].append(candidate)
manifest_path=out/'eva_original_mesh_geometry_r52_sources.json';manifest_path.write_text(json.dumps(sources,indent=2),'utf8')
written[prefix+'eva/eva_original_mesh_geometry_r52_sources.json']=str(manifest_path)
(out/'asset-entries.json').write_text(json.dumps(written,indent=2),'utf8')
print('Exported 3 articulated fist assets and their runtime source binding; hand contracts unchanged.')
