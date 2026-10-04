"""Root-owned whole-body attack study, with source performances and explicit support.

Private until mesh and game review; timings are not a claim of artistic quality.
TV19 cuts263B/267/274 inform forward commitment and whole-body pressure, not
frame-for-frame capture. Eyes Japan supplies a human stepping power punch.
"""
from pathlib import Path
import argparse,copy,hashlib,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from bvh_motion_r12 import load_bvh,save_npz
from retarget_human_r12 import Human
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy
import author_combat_performance_r36 as performance

ROOT=Path(__file__).resolve().parents[1]

def eyes_power(out):
    source=ROOT/'external-assets/incoming/mocap/eyes-japan-r01/selected/karate-09-punch strong-yokoyama.bvh'
    data=load_bvh(source);start,end=400,431
    aliases={'Spine':'Chest','Spine1':'Chest'}
    for side in ('Left','Right'):
        aliases.update({side+'Arm':side+'UpArm',side+'ForeArm':side+'LowArm',side+'Leg':side+'LowLeg',
                        side+'FingerBase':side+'Hand_End',side+'ToeBase':side+'Foot_End',
                        side+'ToeBase_End':side+'Foot_End',side[0]+'Thumb':side+'Hand_End'})
    for alias,target in aliases.items():
        i=data['names'].index(target);data['names'].append(alias);data['parents']=np.r_[data['parents'],i]
        data['offsets']=np.r_[data['offsets'],[[0.,0.,0.]]]
        data['positions']=np.concatenate([data['positions'],data['positions'][:,i:i+1]],axis=1)
        data['rotations']=np.concatenate([data['rotations'],data['rotations'][:,i:i+1]],axis=1)
    neutral=np.zeros_like(data['positions'][0]);neutral[0]=data['positions'][start,0]
    for i,parent in enumerate(data['parents']):
        if parent>=0:neutral[i]=neutral[parent]+data['offsets'][i]
    data['positions']=np.r_[neutral[None],data['positions'][start:end+1]]
    data['rotations']=np.r_[np.tile([0.,0.,0.,1.],(1,len(neutral),1)),data['rotations'][start:end+1]]
    path=out/'eyes_power_calibrated.npz';save_npz(path,data);human=Human(path);human.reference_frame=0
    across=neutral[human.index[human.map['shoulder_l']]]-neutral[human.index[human.map['shoulder_r']]]
    forward=np.cross(across,[0,1,0]);human.basis=R.from_euler('y',np.arctan2(forward[0],-forward[2]))
    human.reference=neutral[human.index['Hips']].copy();human.reference[1]=0
    return human,dict(source=str(source.relative_to(ROOT)),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                     frames_zero_based=[start,end],first_full_extension_frame=418,aliases=aliases,hand_markers='No measured fingers; current anatomical hand controller owns finger poses')

def support(human,count):
    times=np.linspace(1,human.frames-1,count);points=[human.sample(float(t))[0]for t in times]
    dt=(human.frames-2)/human.fps/(count-1);result=[]
    for side in ('l','r'):
        feet=[np.array([p[n+'_'+side]for p in points])for n in ('ankle','toe')]
        floor=min(float(np.percentile(v[:,1],3))for v in feet);contacts=np.zeros(count,bool)
        for v in feet:
            speed=np.linalg.norm(np.gradient(v[:,[0,2]],dt,axis=0),axis=1)
            contacts|=(v[:,1]<floor+.022*human.height)&(speed<.35*human.height)
        result.append(contacts)
    return np.column_stack(result).tolist()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--rigs',nargs='+',type=int,default=[1]);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);source_dir=a.out/'source';source_dir.mkdir();performance.common.OUT=source_dir
    (a.out/'AUTHORING_INCOMPLETE.json').write_text('{}')
    base=ROOT/'artifacts/rebuild_r45/motion/two_stage_repair_work_v181'
    for f in base.glob('*gameplay*.json'):shutil.copy2(f,a.out/f.name)
    original_human=performance.common.human;human,meta=eyes_power(source_dir);reports=[]
    for rig in a.rigs:
        actor=Actor(rig);path=a.out/f'eva_gameplay_r42_{rig}.json';data=json.loads(path.read_text())
        for label,source,mirror in [('jab','ArmsPunch1',True),('cross','ArmsCloseRangePunch',False),('heavy','eyes_power',False)]:
            performance.common.human=(lambda *args:(human,meta))if source=='eyes_power'else original_human
            try:
                clip,origin=performance.captured(actor,source,mirror,label,AnatomicalRetarget,anatomy)
                actual_human,_=performance.common.human(source,mirror)
            finally:performance.common.human=original_human
            contacts=support(actual_human,len(clip['frames']))
            if source=='eyes_power':
                clip['contact_phase']=(origin['first_full_extension_frame']-origin['frames_zero_based'][0])/(origin['frames_zero_based'][1]-origin['frames_zero_based'][0])
            for frame,contact in zip(clip['frames'],contacts):frame['foot_contact']=contact
            clip.update(stance_locked=False,step_contacts=contacts,source_timing_r45=True,
                        source_duration_seconds=clip['duration_seconds'],support='Captured heel/toe support, without permanent two-foot anchors')
            data['clips']['r32_'+label]=clip;data['sources'][label]=dict(origin,root_authored_adaptation='Complete body capture, EVA hinge reconstruction and support; not a TV motion capture')
            reports.append(dict(rig=rig,clip=label,source=origin,contact_phase=clip['contact_phase'],leading_side=clip['leading_side'],duration=clip['duration_seconds']))
        path.write_text(json.dumps(data,separators=(',',':')))
    (a.out/'provenance.json').write_text(json.dumps(dict(clips=reports,private_study=True,native_passed=False,visual_passed=False,not_a_timing_only_repair=True),indent=2))
    (a.out/'AUTHORING_INCOMPLETE.json').unlink();print(json.dumps(reports))

if __name__=='__main__':main()
