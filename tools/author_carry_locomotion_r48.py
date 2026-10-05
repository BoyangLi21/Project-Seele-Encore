"""Rebind recorded ACCAD arm travel to each current rig; retain the delivered lower body."""
from pathlib import Path
import copy,json
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy
import author_locomotion_r43 as capture

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r48'
RUNTIME=BASE/'runtime/projectseele-local-maps'
OUT=BASE/'carry_locomotion';OUT.mkdir(parents=True,exist_ok=True)
BODY=RUNTIME/'eva_body_r44.json'

def main():
    baseline=OUT/'before_eva_body_r44.json'
    if not baseline.exists():baseline.write_bytes(BODY.read_bytes())
    data=json.loads(baseline.read_text());common.BODY=data;common.NAMES=data['motion']['bones']
    capture.OUT=OUT;(OUT/'source').mkdir(exist_ok=True)
    sources={role:capture.human(capture.SOURCE/file)for role,(file,start,end)in capture.CLIPS.items()}
    rows=[]
    for key in range(3):
        actor=Actor(key);doc=data['stance_clips_by_rig'][str(key)];names=list(actor.rig.rig)
        doc['bones']=names
        for role in ('idle','walk','run'):
            old=data['motion']['clips'][role];old_names=data['motion']['bones'];frames=old['frames'];count=len(frames)
            file,start,end=capture.CLIPS[role];retarget=AnatomicalRetarget(sources[role]);source_poses=[];originals=[]
            for i,f in enumerate(np.linspace(start+1,end+1,count)):
                p,delta,_=retarget.pose(float(f),support='air');p=anatomy(actor,p,closure=.1)
                source_poses.append(p);originals.append(actor.rig.decode(frames[i],old_names))
            # Match the recorded arm's counter-swing to the delivered leg cycle.
            # No gait phase, stride, foot source or server motion is changed.
            shift=0
            if role!='idle':
                n=count-1;a=np.array([p.point('foot_l')[2]for p in originals[:-1]]);b=np.array([p.point('foot_l')[2]for p in source_poses[:-1]])
                a-=a.mean();b-=b.mean();shift=max(range(n),key=lambda s:float(a@np.roll(b,-s)))
            exported=[]
            for i,p in enumerate(originals):
                s=source_poses[(i+shift)%(count-1)]if role!='idle'else source_poses[i]
                for side in ('l','r'):
                    for prefix in ('clavicle_','arm_','forearm_','wrist_','hand_'):
                        bone=prefix+side
                        if bone in s.q and bone in p.q:p.setq(bone,s.q[bone]);p.setp(bone,s.p[bone])
                record=actor.rig.encode(p,contacts=(False,False),bone_names=names)
                exported.append(record)
            if role!='idle':exported[-1]=copy.deepcopy(exported[0])
            doc['clips'][role]=dict(duration_seconds=old['duration_seconds'],loop=True,frames=exported,
                                   source_file=file,source_frames=[start,end],r48_upper_body_only=True)
            rows.append(dict(rig=key,role=role,source_file=file,source_frames=[start,end],phase_shift=shift,
                             source='ACCAD / Ohio State University Open Motion Project',source_kind='recorded human motion',
                             legs_stride_clock_unchanged=True,native_verified=False))
    data['r48_carry_provenance']=rows
    BODY.write_text(json.dumps(data,separators=(',',':')),'utf8')
    (OUT/'REPORT.json').write_text(json.dumps(rows,indent=2),'utf8');print([(r['rig'],r['role'],r['phase_shift'])for r in rows])

if __name__=='__main__':main()
