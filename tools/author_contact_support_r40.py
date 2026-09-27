"""Rebuild the support of existing normal punches, retaining their trunk/arms.

This is an isolated contact-retarget candidate, never an installation command.
Original capture, timings, damage and branch windows stay independently saved.
"""
from pathlib import Path
import copy,json,hashlib,argparse
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_combat_r35 import Actor
from study_combat_performance_r36 import decode
from anatomical_hinge_r35 import solve

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/world_combat_r40/contact_candidate'


def generate(key,out,natural=False):
    out.mkdir(parents=True,exist_ok=True)
    name='sachiel_gameplay_r32.json' if key=='sachiel' else f'eva_gameplay_r32_{key}.json'
    path=ROOT/'run/projectseele-local-maps'/name
    baseline=out/('baseline_'+name)
    raw=baseline.read_bytes() if baseline.exists() else path.read_bytes();source=json.loads(raw);candidate=copy.deepcopy(source)
    if source.get('contact_revision')==40:raise ValueError('Use the preserved pre-R40 profile as authoring input')
    if not baseline.exists():baseline.write_bytes(raw)
    actor=Actor(key);summary=[]
    anchors={'l':np.array([-actor.width,0,-actor.height*.115]),
             'r':np.array([actor.width,0,actor.height*.115])}
    for label in ('guard','jab','cross','hook','heavy'):
        clip=copy.deepcopy(source['clips']['r32_'+label])
        if natural and label!='guard':
            from scipy.interpolate import PchipInterpolator
            import author_combat_performance_r36 as performance
            info=source['sources'][label]
            original,_=performance.captured(actor,Path(info['source']).stem,info.get('mirrored',False),label)
            curve=PchipInterpolator([0,clip['contact_phase'],1],[0,original['contact_phase'],1])
            poses=[];travel=[];poles={}
            for phase in curve(np.linspace(0,1,len(clip['frames']))):
                pose=performance.sample(actor,source,original,float(phase))
                poses.append(performance.anatomy(actor,pose,poles=poles))
                location=phase*(len(original['trajectory_m'])-1);i=int(location);t=location-i
                travel.append((np.array(original['trajectory_m'][i])*(1-t)+np.array(original['trajectory_m'][min(i+1,len(original['trajectory_m'])-1)])*t).tolist())
            clip['trajectory_m']=travel
        else:poses=[decode(actor,source,frame) for frame in clip['frames']]
        reference={s:np.arcsin(np.clip(R.from_matrix(poses[0].matrix('foot_'+s)[:3,:3]).apply([0,0,-1])[1],-1,1)) for s in ('l','r')}
        output=[];max_error=0.;max_root_shift=0.
        for index,pose in enumerate(poses):
            before=np.array(pose.p['root'])
            trajectory=np.array(clip.get('trajectory_m',[[0,0,0]]*len(poses))[index])*[-112,112,112]
            goals={};orientations={}
            for side in ('l','r'):
                original=R.from_matrix(pose.matrix('foot_'+side)[:3,:3])
                pitch=np.arcsin(np.clip(original.apply([0,0,-1])[1],-1,1))-reference[side]
                # Toe-out is the common starting stance. Keep captured heel
                # articulation in the supported range, without an airborne roll.
                orientation=R.from_euler('y',np.deg2rad(10 if side=='l' else -10))*R.from_euler('x',np.clip(pitch,-.4,.4))
                floor=-orientation.apply(actor.feet[side])[:,1].min()
                target=anchors[side]-trajectory
                target[1]=floor
                goals[side]=target;orientations[side]=orientation
            # A captured pelvis may exceed the differently proportioned rig's
            # reach. Move the pelvis minimally into both reachable volumes.
            for _ in range(16):
                for side in ('l','r'):
                    hip=pose.point('leg_'+side);joint=actor.knees[side]
                    reach=(np.linalg.norm(joint-actor.P['leg_'+side])+np.linalg.norm(actor.P['foot_'+side]-joint))*.985
                    delta=hip-goals[side];distance=np.linalg.norm(delta)
                    if distance>reach:pose.setp('root',pose.p['root']-delta*(1-reach/distance))
            for side in ('l','r'):
                pole=orientations[side].apply([0,0,-1]);pole[1]=0
                solve(pose,actor.P,'leg_'+side,'shin_'+side,'foot_'+side,actor.knees[side],goals[side],pole,[-1,0,0],orientations[side])
                max_error=max(max_error,float(np.linalg.norm(pose.point('foot_'+side)-goals[side])))
            max_root_shift=max(max_root_shift,float(np.linalg.norm(pose.p['root']-before)))
            frame=pose.encode() if actor.angel else actor.rig.encode(pose,(True,True),source['bones'])
            frame['foot_contact']=[True,True];output.append(frame)
        c=candidate['clips']['r32_'+label]
        c.update(frames=output,trajectory_m=clip['trajectory_m'],step_contacts=[[True,True]]*len(output),support='captured_trunk_with_persistent_floor_contacts',stance_locked=True)
        summary.append(dict(clip=label,frames=len(output),max_foot_target_error_model_units=max_error,max_root_correction_model_units=max_root_shift,
                            temporal_parameters_changed=False,original_capture_recovery_retained=natural,
                            upper_body_rotation_channels_changed_from_baseline=natural and label!='guard'))
    candidate['contact_revision']=40
    candidate['contact_provenance']={'source_sha256':hashlib.sha256(raw).hexdigest(),
        'reason':'Native source toes remain grounded while old adapted jab lifts one sole by 17.92 model units; support derived from the adapted mesh had incorrectly become an airborne contact schedule.',
        'method':'Common two-foot stance, source torso and arm performance, captured heel articulation, explicit anatomical hinge and minimal pelvis reach correction',
        'scope':str(key)+' normal guard/jab/cross/hook/heavy only; candidate for review'}
    candidate['natural_recovery']=natural
    (out/name).write_text(json.dumps(candidate,separators=(',',':')))
    (out/('summary_'+str(key)+'.json')).write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--rigs',default='1');parser.add_argument('--out',type=Path,default=OUT);parser.add_argument('--natural-recovery',action='store_true');args=parser.parse_args()
    for value in args.rigs.split(','):generate(value if value=='sachiel' else int(value),args.out,args.natural_recovery)
