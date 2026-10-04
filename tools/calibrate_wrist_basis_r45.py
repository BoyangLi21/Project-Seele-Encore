"""Repair the proven hand reference error in identified captured gait clips.

Only hand rotation channels change. Joint origins, body/foot trajectories,
durations, damage and private originals are preserved. All other source
families remain explicitly unaudited until their provenance is checked.
"""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from retarget_human_r12 import axes,unit
from study_combat_performance_r36 import decode


def main():
    p=argparse.ArgumentParser();p.add_argument('--body',type=Path,required=True);p.add_argument('--hands',type=Path,required=True);p.add_argument('--rigs',default='1');p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    body=json.loads(a.body.read_text(encoding='utf8'));common.BODY=body
    assert not body.get('anatomical_hand_basis_r45'),'Refuse double calibration'
    records=[];basis={};known={'idle':'Male2_A1_Stand.bvh','walk':'Male2_B3_Walk.bvh','run':'Male2_C3_Run.bvh'}
    for key in map(int,a.rigs.split(',')):
        actor=Actor(key);file=a.hands/f'unit0{key}/hand_rig_contract.json';c=json.loads(file.read_text(encoding='utf8'));doc=body['stance_clips_by_rig'][str(key)];basis[str(key)]={};corrections={}
        for side in ['l','r']:
            h=c['hands'][side];longitudinal=np.array(h['longitudinal_bind']);across=np.array(h['digits']['index']['joints'][0]['head_bind'])-h['digits']['little']['joints'][0]['head_bind']
            old_long=unit(actor.P['finger_middle_'+side]-actor.P['hand_'+side]);old_across=actor.P['finger_index_'+side]-actor.P['finger_little_'+side]
            correction=R.from_matrix(axes(old_long,old_across)@axes(longitudinal,across).T);corrections[side]=correction
            basis[str(key)][side]=dict(longitudinal_bind=longitudinal.tolist(),across_bind=across.tolist(),source_contract_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
            samples=[]
            for name,source in known.items():
                clip=doc['clips'][name];assert clip.get('source_file')==source,(name,'unidentified source family',clip.get('source_file'))
                index=doc['bones'].index('hand_'+side)
                for number,f in enumerate(clip['frames']):
                    pose=decode(actor,doc,f);arm=pose.point('hand_'+side)-pose.point('forearm_'+side,actor.elbows[side]);arm/=np.linalg.norm(arm)
                    before=pose.matrix('hand_'+side)[:3,:3]@longitudinal
                    pose.setq('hand_'+side,pose.q['hand_'+side]*correction)
                    after=pose.matrix('hand_'+side)[:3,:3]@longitudinal
                    q=pose.q['hand_'+side].as_quat();f['rotation_wxyz'][index]=[float(q[3]),float(-q[0]),float(-q[1]),float(q[2])]
                    angle=lambda v:float(np.degrees(np.arccos(np.clip(v@arm,-1,1))))
                    samples.append(dict(clip=name,frame=number,before_wrist_bend_deg=angle(before),after_wrist_bend_deg=angle(after)))
            records.append(dict(rig=key,side=side,first_error='Retarget.hand_reference used diagonal wrist-to-MCP instead of the hand longitudinal frame',
                reference_disagreement_deg=float(np.degrees(np.arccos(np.clip(old_long@longitudinal,-1,1)))),correction_xyzw=correction.as_quat().tolist(),samples=samples))
    body['anatomical_hand_basis_r45']=basis
    body['wrist_calibration_r45']=dict(source_body_sha256=hashlib.sha256(a.body.read_bytes()).hexdigest(),
        affected_clips=list(known),rigs=a.rigs,unreviewed_families=['combat','rifle','prone','crouch','paired scenes','equipment'],native_passed=False,visual_accepted=False)
    (a.out/'eva_body_r45.json').write_text(json.dumps(body,separators=(',',':')),encoding='utf8')
    (a.out/'wrist_diagnosis.json').write_text(json.dumps(records,indent=2),encoding='utf8')
    for r in records:
        idle=[x for x in r['samples']if x['clip']=='idle']
        print(r['rig'],r['side'],'idle first',idle[0],'rest basis disagreement',r['reference_disagreement_deg'])


if __name__=='__main__':main()
