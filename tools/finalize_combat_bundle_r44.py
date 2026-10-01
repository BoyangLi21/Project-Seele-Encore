"""Freeze actual joint offsets and sole metadata, then sign the read-back bundle."""
from pathlib import Path
import hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
from validate_combat_bundle_r44 import Pose

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat/motion'


def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def main():
    body=json.loads((OUT/'eva_body_r44.json').read_text('utf8'));report=[]
    for key in range(5):
        file=OUT/f'eva_gameplay_r44_{key}.json';data=json.loads(file.read_text('utf8'));rig=body['rigs'][str(key)]
        pivots={b['name']:np.asarray(b['pivot'],float)*[-1,1,1] for b in rig};maximum=0;count=0
        support=body.get('rig_support',{}).get(str(key),body['support'])
        for label,clip in data['clips'].items():
            for frame in clip['frames']:
                for side in ('l','r'):
                    for family,marker in [('forearm_','r30_elbow_socket_'),('shin_','r30_knee_socket_')]:
                        name=family+side;values=frame['rotation_wxyz'][data['bones'].index(name)];w,x,y,z=values;q=R.from_quat([-x,-y,z,w])
                        joint=pivots.get(marker+side)
                        if joint is None:joint=pivots[name]+[0,11.4,0] if family=='shin_' else np.array([-23.489652 if side=='l' else 23.489652,123.435069,7.737214])
                        delta=joint-pivots[name];wanted=(delta-q.apply(delta))*[-1,1,1]
                        old=np.asarray(frame.get('bone_position_xyz',{}).get(name,[0,0,0]))
                        maximum=max(maximum,float(np.linalg.norm(old-wanted)));count+=1
                        frame.setdefault('bone_position_xyz',{})[name]=wanted.round(7).tolist()
            if label in ('r32_knife_forward','r32_knife_reverse','r32_kick'):
                contacts=[]
                for frame in clip['frames']:
                    pose=Pose(rig,data['bones'],frame);heights=[]
                    for side in ('l','r'):
                        points=np.asarray(support['foot_'+side]);m=pose.matrix('foot_'+side)
                        heights.append(float((points@m[1,:3]+m[1,3]).min()))
                    sample=[bool(height-min(heights)<1.1) for height in heights]
                    frame['foot_contact']=sample;contacts.append(sample)
                clip['step_contacts']=contacts
                if label=='r32_kick':
                    foot=np.asarray(support['foot_l']);toe=foot[foot[:,2]<=np.percentile(foot[:,2],12)]
                    clip['contact_point_model']=(toe.mean(0)*[-1,1,1]).tolist()
        data['r44_joint_contract']=dict(method='Each offset is centre - rotation(centre - pivot); never interpolate an independent offset',
                                       maximum_previous_offset_correction_model_units=maximum,channels_recomputed=count)
        file.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),'utf8');report.append(dict(rig=key,maximum_offset_correction_model_units=maximum))
    files={p.name:sha(p) for p in sorted(OUT.glob('*r44*.json')) if p.name!='combat_bundle_r44.json'}
    identity=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    manifest=json.loads((OUT/'combat_bundle_r44.json').read_text('utf8'));manifest.update(bundle_id='R44-'+identity[:16],files=files)
    (OUT/'combat_bundle_r44.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (OUT.parent/'joint_offset_repair.json').write_text(json.dumps(dict(bundle=manifest['bundle_id'],repairs=report),indent=2),'utf8')
    print(json.dumps(dict(bundle=manifest['bundle_id'],repairs=report)))


if __name__=='__main__':main()
