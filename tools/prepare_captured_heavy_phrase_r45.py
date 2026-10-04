"""Private full windup/contact/recovery from the existing CC-BY G1 M_Move11 capture."""
from pathlib import Path
import argparse,copy,hashlib,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from bvh_motion_r12 import load_bvh,save_npz
from retarget_human_r12 import Human
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_combat_r35 import Actor
from author_grounded_capture_r43 import anatomy
from rebuild_stance_hinges_r41 import reconstruct,reachable_root
import author_gameplay_motion_r32 as common

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--start',type=int,default=600);ap.add_argument('--end',type=int,default=765);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    incomplete=a.out/'AUTHORING_INCOMPLETE.json';incomplete.write_text('{"status":"Do not install: complete three-rig authoring has not finished"}')
    src=ROOT/'artifacts/motion_research/free_mocap_sources/g1_moves/M_Move11/M_Move11.bvh'
    m=load_bvh(src);assert 0<=a.start<a.end<len(m['positions'])
    aliases={'Head_End':'Head','LeftFingerBase':'LeftHandMiddle1','RightFingerBase':'RightHandMiddle1',
             'LThumb':'LeftHandThumb1','RThumb':'RightHandThumb1','LeftToeBase_End':'LeftToeBase','RightToeBase_End':'RightToeBase'}
    for alias,target in aliases.items():
        i=m['names'].index(target);m['names'].append(alias);m['parents']=np.r_[m['parents'],i];m['offsets']=np.r_[m['offsets'],[[0,0,0]]]
        m['positions']=np.concatenate([m['positions'],m['positions'][:,i:i+1,:]],axis=1);m['rotations']=np.concatenate([m['rotations'],m['rotations'][:,i:i+1,:]],axis=1)
    rest=np.zeros_like(m['positions'][0]);rest[0]=m['positions'][a.start,0]
    for i,parent in enumerate(m['parents']):
        if parent>=0:rest[i]=rest[parent]+m['offsets'][i]
    m['positions']=np.r_[rest[None],m['positions'][a.start:a.end+1]]
    m['rotations']=np.r_[np.tile([0,0,0,1.],(1,len(rest),1)),m['rotations'][a.start:a.end+1]]
    calibrated=a.out/'captured_source_window.npz';save_npz(calibrated,m);h=Human(calibrated);h.reference_frame=0
    ref=m['positions'][0];across=ref[h.index[h.map['shoulder_l']]]-ref[h.index[h.map['shoulder_r']]];forward=np.cross(across,[0,1,0]);forward/=np.linalg.norm(forward)
    h.basis=R.from_euler('y',np.arctan2(forward[0],-forward[2]));h.reference=ref[h.index['Hips']].copy();h.reference[1]=0
    base=ROOT/'artifacts/rebuild_r45/motion/selected_three_stage_clock_v145'
    for p in [*base.glob('eva_gameplay*.json'),base/'sachiel_gameplay_r32.json']:shutil.copy2(p,a.out/p.name)
    source_contacts=np.load(ROOT/'artifacts/motion_research/eva_mocap_combat_phase_s/source/M_Move11.npz')['foot_contact'][a.start:a.end+1]
    report=[]
    for rig in [0,1,2]:
        actor=Actor(rig);retarget=AnatomicalRetarget(h);poses=[];travel=[]
        for frame in range(1,h.frames):
            pose,delta,_=retarget.pose(frame,support='air');poses.append(anatomy(actor,pose));travel.append(delta)
        palms={s:np.array([p.point('hand_'+s)-(p.point('leg_l')+p.point('leg_r'))*.5 for p in poses])for s in ['l','r']}
        # This selected phrase is the inspected right overhand. The left
        # recovery hand drops faster near the beginning; that is not a hit.
        lead='r';peak=int(np.argmax(palms[lead][:,1]));velocity=-np.gradient(palms[lead][:,1])
        contact=peak+int(np.argmax(velocity[peak:]));assert peak<contact<len(poses)-1
        aim=palms[lead][contact];turn=R.from_euler('y',np.arctan2(aim[0],-aim[2]));track=turn.apply(np.array(travel)-travel[0]);track[:,1]=0
        profile=json.loads((a.out/f'eva_gameplay_r42_{rig}.json').read_text());frames=[];soles=[]
        for i,p in enumerate(poses):
            common.rotate_stage(p,actor.rig,turn)
            goals={};orientations={}
            for k,s in enumerate(['l','r']):
                q=R.from_matrix(p.matrix('foot_'+s)[:3,:3]);goal=p.point('foot_'+s).copy();low=float((q.apply(actor.feet[s])+goal)[:,1].min())
                if source_contacts[i,k]or low<0:goal[1]-=low
                goals[s]=goal;orientations[s]=q
            reachable_root(actor,p,goals)
            for s in ['l','r']:reconstruct(actor,p,s,goals[s],orientations[s],p.q['leg_'+s])
            frames.append(actor.rig.encode(p,tuple(source_contacts[i]),profile['bones']))
            soles.append([float((orientations[s].apply(actor.feet[s])+p.point('foot_'+s))[:,1].min())*5/16 for s in ['l','r']])
        clip=copy.deepcopy(profile['clips']['r32_heavy']);seconds=(a.end-a.start)/m['fps']
        clip.update(frames=frames,trajectory_m=(track*[-1,1,1]/112).tolist(),duration_seconds=seconds,source_duration_seconds=seconds,source_timing_r45=True,
                    contact_phase=contact/(len(frames)-1),leading_side=lead,stance_locked=False,step_contacts=source_contacts.tolist(),support='captured_per_frame_support_no_fixed_dual_anchor')
        profile['clips']['r32_heavy']=clip;profile['sources']['heavy']=dict(source=str(src.relative_to(ROOT)),sha256=hashlib.sha256(src.read_bytes()).hexdigest(),frames_zero_based=[a.start,a.end],license='CC BY 4.0',url='https://huggingface.co/datasets/exptech/g1-moves',private_comparison=True)
        (a.out/f'eva_gameplay_r42_{rig}.json').write_text(json.dumps(profile,separators=(',',':')))
        report.append(dict(rig=rig,frames=len(frames),leading_side=lead,source_windup_peak_frame=a.start+peak,source_contact_frame=a.start+contact,source_duration_seconds=seconds,old_duration_seconds=1.55,existing_speed_multiplier=1.5,
                           damage_and_cooldown_unchanged=True,sole_minimum_blocks=np.min(soles,axis=0).tolist(),foot_contact_counts=source_contacts.sum(0).tolist()))
    (a.out/'provenance.json').write_text(json.dumps(dict(reports=report,aliases=aliases,alias_scope='Existing captured landmarks copied for the older adapter; no invented finger/end-point motion; neutral calibration frame is excluded.',promoted=False,native=False,art_accepted=False),indent=2));incomplete.unlink();print(json.dumps(report))

if __name__=='__main__':main()
