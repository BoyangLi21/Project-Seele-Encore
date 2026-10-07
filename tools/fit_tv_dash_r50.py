"""Fit the TV12-guided full-body sprint to current EVA rigs and actual speed.

This preserves the supplied walk/run, replaces only the rejected anime run
candidate, and retains a separate dash clip for the actual held dash input.
"""
from pathlib import Path
import argparse,copy,json
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from author_combat_bundle_r44 import maintain_joint_centres
from hand_surface_r49 import natural_carry
from warp_locomotion_r44 import warp
from calibrated_arm_r49 import solve

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--body',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    body=json.loads(a.body.read_text('utf8'));common.BODY=body;common.NAMES=body['motion']['bones']
    baseline=json.loads((ROOT/'artifacts/rebuild_r45/motion/stability_baseline_v92/eva_body_r43.json').read_text('utf8'))
    reports=[]
    for key in range(3):
        original=json.loads((ROOT/f'artifacts/rebuild_r45/motion/tv_sprint_preserved_base_v98/eva_tv_sprint_supplement_{key}.json').read_text('utf8'))
        actor=Actor(key);doc=body['stance_clips_by_rig'][str(key)]
        oldrig={b['name']:b for b in original['rig_contract_r44']};newrig={b['name']:b for b in body['rigs'][str(key)]}
        for name in original['bones']:
            if name.startswith(('finger_','hand_')):continue
            if any(oldrig[name].get(k)!=newrig[name].get(k)for k in('parent','pivot')):raise ValueError(('Skeleton differs',key,name))
        contract=json.loads((a.assets/f'hand_rigs/unit{key:02}/hand_rig_contract.json').read_text('utf8'))
        clip=copy.deepcopy(original['clips']['tv_sprint']);frames=[]
        for index,frame in enumerate(clip['frames']):
            pose=actor.rig.decode(frame,original['bones'])
            # Keep bent elbows during the TV dash. The old supplement's
            # source forearms hang below the hips and do not match that form.
            for side,offset in(('l',0.),('r',np.pi)):
                swing=np.sin(2*np.pi*index/(len(clip['frames'])-1)+offset)
                sign=-1 if side=='l'else 1
                basis=pose.matrix('torso_upper')[:3,:3]
                goal=pose.point('arm_'+side)+basis@np.array([sign*5,-19+11*swing,-20-22*swing])
                result=solve(pose,actor.P,'arm_'+side,'forearm_'+side,'hand_'+side,actor.elbows[side],goal,basis@np.array([sign*.3,-1,.5]),[1,0,0])
                if not result['axial_guard_passed']:raise ValueError(('Sprint humerus reversed',key,index,side))
            maintain_joint_centres(actor,pose);natural_carry(pose,contract,actor.elbows,actor.P)
            frames.append(actor.rig.encode(pose,frame['foot_contact'],doc['bones']))
        clip['frames']=frames;doc['clips']['dash_run']=clip
        stride=copy.deepcopy(baseline['locomotion_contract_r43'][str(key)]['run'])
        stride.pop('forefoot_curves_r44',None);stride.pop('runtime_stride_blocks_r44',None)
        toes=json.loads((a.runtime/f'eva_gameplay_r44_{key}.json').read_text('utf8'))['support_toes']
        target_stride=[.65,.78,.90][key]*1.2/(1-.91*.6)*20*clip['duration_seconds']
        fitted,report=warp(actor,doc,'dash_run',stride['stride_blocks']/target_stride,stride,toes,1,continuous_vertical=True,proportional_swing=True)
        fitted['r50_source']='ACCAD Male2_C3_Run, TV12-guided torso/gaze, current hands, fitted ground travel'
        doc['clips']['dash_run']=fitted
        stride.update(runtime_stride_blocks_r44=target_stride,support_mask_r44=[f['foot_contact']for f in fitted['frames']],forefoot_curves_r44=fitted['forefoot_curves_r44'],forefoot_offsets_r44=toes)
        report['cadence_basis']={'reference_ground_friction':.6,'reference_sync':1.,'source_cycle_seconds':clip['duration_seconds'],'runtime_stride':target_stride,'movement_speed_changed':False,'native_measured':False}
        body['locomotion_contract_r43'][str(key)]['dash_run']=stride
        reports.append(dict(rig=key,source=str(original['reference']),frames=len(fitted['frames']),warp=report,native=False,user_accepted=False))
    (a.out/'eva_body_r50.json').write_text(json.dumps(body,separators=(',',':')),'utf8')
    (a.out/'REPORT.json').write_text(json.dumps(reports,indent=2),'utf8');print('Fitted distinct sprint for all three rigs; walk/run unchanged')

if __name__=='__main__':main()
