"""Retarget the supplied 60Hz Manny walks without replacing EVA geometry.

The source bind and complete pelvis/chest/limb performance are retained.
The crop is a measured same-foot cycle, not an arbitrary four-second loop.
"""
from pathlib import Path
import argparse,copy,json
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
from scipy.signal import find_peaks
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from retarget_human_r12 import Human
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy
from author_combat_bundle_r44 import maintain_joint_centres
from hand_surface_r49 import natural_carry
from warp_locomotion_r44 import warp


def source_motion(path,target):
    data=np.load(path);names=list(data['names']);idx={n:i for i,n in enumerate(names)}
    mapping={'Hip':'pelvis','LowerSpine':'spine_01','Chest':'spine_05','Neck':'neck_01','Head':'head','Head_End':'head'}
    for side in('l','r'):
        for name,bone in [('Shoulder','upperarm'),('Forearm','lowerarm'),('Hand','hand'),('Thigh','thigh'),('Shin','calf'),('Foot','foot'),('Toe','ball'),('Toe_End','ball'),('Finger2','middle_03'),('Finger0','thumb_03')]:mapping[side.upper()+name]=bone+'_'+side
    convert=R.from_euler('x',-90,degrees=True)
    positions=np.concatenate([data['bind_positions'][None],data['positions']]);quats=np.concatenate([data['bind_rotations'][None],data['rotations']])
    selected=np.stack([positions[:,idx[n]]for n in mapping.values()],axis=1)
    selected_q=np.stack([quats[:,idx[n]]for n in mapping.values()],axis=1)
    selected=convert.apply(selected.reshape(-1,3)).reshape(selected.shape)
    selected_q=(convert*R.from_quat(selected_q.reshape(-1,4))).as_quat().reshape(selected_q.shape)
    # Explicit synthetic end markers provide lengths, never an extra pose.
    out_names=list(mapping)
    selected[:,out_names.index('Head_End'),1]+=.12
    for s in('L','R'):selected[:,out_names.index(s+'Toe_End'),2]-=.08
    np.savez_compressed(target,names=out_names,positions=selected,rotations=selected_q,fps=60.,source=str(path))
    h=Human(target);h.reference_frame=0
    p=selected[0];across=p[h.index['LShoulder']]-p[h.index['RShoulder']]
    forward=np.cross(across,[0,1,0]);h.basis=R.from_euler('y',np.arctan2(forward[0],-forward[2]))
    # Find two matching heel-strike extrema after the opening transient.
    centred=selected[1:]-selected[1:,h.index['Hip'],None,:]
    foot=centred[:,h.index['LFoot'],2]-centred[:,h.index['RFoot'],2]
    peaks,_=find_peaks(foot,distance=25,prominence=.12)
    if len(peaks)<2:raise ValueError('Source does not contain a complete stable same-foot cycle')
    keypoints=[h.index[n]for n in('LFoot','RFoot','LShin','RShin','LHand','RHand','Chest','Head')]
    choices=[]
    for a,b in zip(peaks,peaks[1:]):
        if a<12 or b>len(foot)-10:continue
        error=float(np.linalg.norm(centred[a,keypoints]-centred[b,keypoints],axis=1).mean())
        choices.append((error,int(a)+1,int(b)+1))
    if not choices:raise ValueError('No cycle survives the source transition margins')
    error,start,end=min(choices)
    return h,dict(first=start,last=end,seconds=(end-start)/60,endpoint_joint_error_m=error,available_strikes=peaks.tolist())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--assets',type=Path,required=True);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    body=json.loads((a.runtime/'eva_body_r44.json').read_text(encoding='utf-8'));common.BODY=body;common.NAMES=body['motion']['bones']
    sources={n:source_motion(a.source/f'{n}_rig0.npz',a.out/f'{n}_canonical.npz')for n in('walk','run')};reports=[]
    # The separately reviewed TV dash is assembled by fit_tv_dash_r50.py.
    # Do not regenerate the rejected high-knee Run_Anime candidate here.
    for key in range(3):
        actor=Actor(key);doc=body['stance_clips_by_rig'][str(key)];bone_names=doc['bones']
        contract=json.loads((a.assets/f'hand_rigs/unit{key:02}/hand_rig_contract.json').read_text(encoding='utf-8'))
        toes=json.loads((a.runtime/f'eva_gameplay_r44_{key}.json').read_text(encoding='utf-8'))['support_toes']
        for label,(human,crop)in sources.items():
            retarget=AnatomicalRetarget(human);frames=[];travel=[];feet=[]
            source_floor=float(np.quantile([min(human.sample(f)[0]['toe_'+s][1],human.sample(f)[0]['toe_end_'+s][1])for f in range(crop['first'],crop['last']+1)for s in('l','r')],.02))
            for f in range(crop['first'],crop['last']+1):
                pose,delta,info=retarget.pose(f,support='air');pose=anatomy(actor,pose,closure=.12)
                # Use source heel/toe height for support; keep the captured
                # knee bend plane, and never pin both feet for the whole loop.
                contacts=[]
                raw,_=human.sample(f)
                for s in('l','r'):
                    contact=min(raw['toe_'+s][1],raw['toe_end_'+s][1])-source_floor<.035
                    contacts.append(contact)
                maintain_joint_centres(actor,pose);natural_carry(pose,contract,actor.elbows,actor.P)
                low=min(float((R.from_matrix(pose.matrix('foot_'+s)[:3,:3]).apply(actor.feet[s])+pose.point('foot_'+s))[:,1].min())for s in('l','r'))
                if low<0:pose.setp('root',pose.p['root']+[0,-low,0])
                frames.append(actor.rig.encode(pose,tuple(contacts),bone_names));travel.append(delta)
                feet.append({s:pose.point('foot_'+s).tolist()for s in('l','r')})
            # Close the small measured residual over the final tenth, keeping
            # root travel outside the body and the original cycle duration.
            first=actor.rig.decode(frames[0],bone_names);count=len(frames)
            for i in range(max(1,count-round(count*.12)),count):
                t=(i-(count-1)*.88)/((count-1)*.12);t=float(np.clip(t,0,1));w=t*t*(3-2*t)
                pose=actor.rig.decode(frames[i],bone_names)
                for n in bone_names:
                    pose.setq(n,Slerp([0,1],R.concatenate([pose.q[n],first.q[n]]))(w));pose.setp(n,pose.p[n]*(1-w)+first.p[n]*w)
                maintain_joint_centres(actor,pose);frames[i]=actor.rig.encode(pose,frames[i]['foot_contact'],bone_names)
            stride=float(np.linalg.norm(np.asarray(travel[-1])-travel[0])*5/16)
            old=doc['clips'].get(label,doc['clips']['run']);clip=copy.deepcopy(old);clip.update(frames=frames,duration_seconds=crop['seconds'],loop=True,source_fps=60,
                r50_user_source=dict(file='行走.fbx'if label=='walk'else'跑步.fbx',crop=crop,source_geometry_installed=False))
            clip.pop('r48_upper_body_only',None);clip['source_file']='User supplied '+('行走.fbx'if label=='walk'else'跑步.fbx');clip['source_frames']=[crop['first'],crop['last']]
            doc['clips'][label]=clip
            locomotion=body.setdefault('locomotion_contract_r43',{}).setdefault(str(key),{}).setdefault(label,{})
            locomotion.update(stride_blocks=stride,runtime_stride_blocks_r44=stride,cycle_seconds=crop['seconds'],support_mask_r44=[f['foot_contact']for f in frames])
            contacts={}
            for k,s in enumerate(('l','r')):
                mask=np.asarray([f['foot_contact'][k]for f in frames],bool)
                on=np.flatnonzero(mask&~np.roll(mask,1))/(len(mask)-1)
                off=np.flatnonzero(~mask&np.roll(mask,1))/(len(mask)-1)
                contacts[s]={'forward':on.tolist(),'reverse':off.tolist()}
            locomotion['contacts']=contacts
            # Old contact paths belonged to different source feet; they cannot
            # be reused against the new motion merely because the name agrees.
            for obsolete in('forefoot_curves_r44','forefoot_offsets_r44'):locomotion.pop(obsolete,None)
            # The server advances phase by actual distance / this stride.
            # Fit each rig to its existing full-input speed and the source
            # cycle duration; a shared 42m run silently slowed Unit00 the most.
            speed=([.36,.42,.48]if label=='walk'else[.65,.78,.90])[key]
            target_stride=speed/(1-.91*.6)*20*crop['seconds']
            warped,report=warp(actor,doc,label,stride/target_stride,locomotion,toes,1,continuous_vertical=True,proportional_swing=True)
            report['source']='User supplied 60Hz FBX cycle; proportional stride/swing fit to existing movement, preserved torso and arms'
            report['cadence_basis']={'full_input_driving_speed':speed,'reference_ground_friction':.6,'reference_sync':1.,'source_cycle_seconds':crop['seconds'],'movement_speed_changed':False,'native_measured':False}
            doc['clips'][label]=warped
            locomotion.update(runtime_stride_blocks_r44=target_stride,support_mask_r44=[f['foot_contact']for f in warped['frames']],
                forefoot_curves_r44=warped['forefoot_curves_r44'],forefoot_offsets_r44=toes)
            reports.append(dict(rig=key,clip=label,frames=len(warped['frames']),seconds=crop['seconds'],source_stride_blocks=stride,runtime_stride_blocks=target_stride,source=crop,warp=report,native=False,user_accepted=False))
    body['r50_user_locomotion']=dict(full_body_source=True,sample_fps=60,geometry_unchanged=True,prevents_legacy_chest_replacement=True)
    (a.out/'eva_body_r50.json').write_text(json.dumps(body,separators=(',',':')),encoding='utf-8')
    (a.out/'REPORT.json').write_text(json.dumps(reports,indent=2),encoding='utf-8');print(json.dumps(reports,indent=2))


if __name__=='__main__':main()
