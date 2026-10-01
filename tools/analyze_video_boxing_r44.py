"""Reconstruct, audit and select the published video-boxing skeleton frames."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation as R

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/video_source/boxing'


def source_rig():
    body=ET.parse(OUT/'smpl_humanoid_neutral_boxing.xml').getroot().find('worldbody/body');names=[];parents=[];offset=[]
    def visit(b,parent=-1):
        index=len(names);names.append(b.attrib['name']);parents.append(parent);offset.append([float(x)for x in b.attrib.get('pos','0 0 0').split()])
        for child in b.findall('body'):visit(child,index)
    visit(body);return names,np.asarray(parents),np.asarray(offset)


def reconstruct(file):
    names,parents,offset=source_rig();d=np.load(file,allow_pickle=False);q=d['pose_quat_global'];local=d['pose_quat'];fps=float(d['fps'])
    positions=np.zeros(q.shape[:2]+(3,));positions[:,0]=d['root_trans_offset'];global_matrices=R.from_quat(q.reshape(-1,4)).as_matrix().reshape(q.shape[:2]+(3,3))
    for i,parent in enumerate(parents):
        if parent>=0:positions[:,i]=positions[:,parent]+np.einsum('fij,j->fi',global_matrices[:,parent],offset[i])
    predicted=[]
    for i,parent in enumerate(parents):
        value=R.from_quat(local[:,i]).as_matrix()
        predicted.append(value if parent<0 else predicted[parent]@value)
    error=float(np.max(np.abs(np.stack(predicted,1)-global_matrices)))
    # Canonicalize the initial heading, preserve world motion and its timing.
    forward=np.median(global_matrices[:5,0,:,0],axis=0);yaw=np.arctan2(forward[1],forward[0]);basis=R.from_euler('z',np.pi/2-yaw).as_matrix()
    origin=positions[0,0].copy();origin[2]=0;canonical=(positions-origin)@basis.T
    rotations=np.einsum('ij,fkjl->fkil',basis,global_matrices)
    velocity=np.diff(canonical,axis=0)*fps;index={n:i for i,n in enumerate(names)}
    segments=[]
    for side in('L','R'):
        hand=index[side+'_Hand'];wrist=index[side+'_Wrist'];elbow=index[side+'_Elbow'];shoulder=index[side+'_Shoulder'];toe=index[side+'_Toe']
        extension=np.linalg.norm(canonical[:,wrist]-canonical[:,shoulder],axis=1)
        arm_length=np.linalg.norm(offset[wrist])+np.linalg.norm(offset[elbow]);ratio=extension/arm_length;speed=np.linalg.norm(velocity[:,hand],axis=1)
        peak=int(np.argmax(speed))+1
        segments.append(dict(side=side,peak_speed=float(speed[peak-1]),peak_frame=peak,extension_at_peak=float(ratio[peak]),
            extension_max=float(ratio.max()),toe_z=[float(canonical[:,toe,2].min()),float(canonical[:,toe,2].max())]))
    np.savez_compressed(OUT/(file.stem+'_fk.npz'),positions=canonical,rotations=rotations,original_positions=positions,names=np.asarray(names),parents=parents,offset=offset,fps=fps)
    return dict(name=file.stem,frames=len(q),fps=fps,local_global_rotation_max_error=error,all_finite=bool(np.isfinite(canonical).all()),beta_zero=bool(np.all(d['beta']==0)),hands=segments,
        missing='No finger joints, no contact impulses, no measured COM. XML rest body is the published neutral boxing model.',heading_rotation_rad=float(np.pi/2-yaw))


def main():
    rows=[reconstruct(p)for p in sorted(OUT.glob('data[0-7].npz'))]
    (OUT/'fk_audit.json').write_text(json.dumps(dict(schema='projectseele.video-source-fk.r44',
        rest_pose_sha256=hashlib.sha256((OUT/'smpl_humanoid_neutral_boxing.xml').read_bytes()).hexdigest(),
        quaternion_order='xyzw, verified by provided local/global chain',skeleton_order='Depth-first published neutral SMPL MJCF body order',
        units='metres; Z up; initial heading rotated to +Y; original FK also retained',motions=rows),indent=2),'utf8')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()
