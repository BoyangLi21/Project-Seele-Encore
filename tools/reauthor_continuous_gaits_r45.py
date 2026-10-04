"""Reauthor only the three NERV walk/run clips from identified raw capture.

Preserve the current non-gait body, corrected wrist basis, contact timing and
captured upper body. No UN clip, mesh, damage or movement speed is modified.
"""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from warp_locomotion_r44 import warp
from study_combat_performance_r36 import decode


def main():
    p=argparse.ArgumentParser();p.add_argument('--body',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--profiles',type=Path,required=True);p.add_argument('--wrists',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--walk-clearance-fraction',type=float);p.add_argument('--walk-only',action='store_true')
    p.add_argument('--proportional-swing',action='store_true');a=p.parse_args()
    assert not(a.proportional_swing and a.walk_clearance_fraction is not None),'Compare captured swing scaling and authored cap as separate candidates'
    a.out.mkdir(parents=True,exist_ok=False);body=json.loads(a.body.read_text());reference=json.loads(a.reference.read_text());common.BODY=body
    assert not reference.get('wrist_calibration_r45'),'Reference must be the unmodified captured hand basis'
    wrists={(r['rig'],r['side']):R.from_quat(r['correction_xyzw'])for r in json.loads(a.wrists.read_text())}
    reports=[]
    for key in [0,1,2]:
        actor=Actor(key);target=body['stance_clips_by_rig'][str(key)];source=reference['stance_clips_by_rig'][str(key)]
        assert target['bones']==source['bones'],'Do not mix target bone orders'
        profile=next(a.profiles/f'eva_gameplay_r{rev}_{key}.json'for rev in [44,43,42,32]if(a.profiles/f'eva_gameplay_r{rev}_{key}.json').is_file());toes=json.loads(profile.read_text())['support_toes']
        for label,expected,stride in [('walk','Male2_B3_Walk.bvh',33.3),('run','Male2_C3_Run.bvh',40.5)]:
            if a.walk_only and label!='walk':continue
            assert source['clips'][label].get('source_file')==expected
            assert 'r44_stride_warp'not in source['clips'][label],'Refuse double-warped source'
            contract=copy.deepcopy(reference['locomotion_contract_r43'][str(key)][label])
            candidate,report=warp(actor,source,label,contract['stride_blocks']/stride,contract,toes,4,continuous_vertical=True,
                                  walk_clearance_fraction=a.walk_clearance_fraction if label=='walk'else None,proportional_swing=a.proportional_swing)
            for frame in candidate['frames']:
                pose=decode(actor,source,frame)
                for side in ['l','r']:
                    name='hand_'+side;index=source['bones'].index(name);q=(pose.q[name]*wrists[key,side]).as_quat()
                    frame['rotation_wxyz'][index]=[float(q[3]),float(-q[0]),float(-q[1]),float(q[2])]
            target['clips'][label]=candidate
            contract=body['locomotion_contract_r43'][str(key)][label]
            contract.update(runtime_stride_blocks_r44=stride,support_mask_r44=[f['foot_contact']for f in candidate['frames']],forefoot_curves_r44=candidate['forefoot_curves_r44'],forefoot_offsets_r44=toes)
            rotations=np.asarray([f['rotation_wxyz']for f in candidate['frames']]);indices=[source['bones'].index('shin_'+s)for s in ['l','r']]
            peaks={}
            for i in indices:
                q=rotations[:,i];q/=np.linalg.norm(q,axis=1)[:,None];angles=2*np.degrees(np.arccos(np.clip(abs((q[8:]*q[:-8]).sum(1)),0,1)));peaks[source['bones'][i]]=float(angles.max())
            reports.append(dict(rig=key,clip=label,knee_eight_sample_peak=peaks,**report));print(key,label,peaks,flush=True)
    body['continuous_gait_r45']=dict(source_body_sha256=hashlib.sha256(a.body.read_bytes()).hexdigest(),reference_sha256=hashlib.sha256(a.reference.read_bytes()).hexdigest(),rigs=[0,1,2],changed_clips=['walk']if a.walk_only else['walk','run'],walk_clearance_fraction=a.walk_clearance_fraction,visual_accepted=False,native_passed=False)
    (a.out/'eva_body_r45.json').write_text(json.dumps(body,separators=(',',':')),encoding='utf8');(a.out/'report.json').write_text(json.dumps(reports,indent=2),encoding='utf8')


if __name__=='__main__':main()
