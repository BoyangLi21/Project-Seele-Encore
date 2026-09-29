"""Per-rig locomotion candidate from the original ACCAD capture, not Tiger channels.

Input cycle endpoints are measured left-foot forward extrema. Object travel,
foot contact phases and skeleton poses are exported together. No live install.
"""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
from bvh_motion_r12 import load_bvh,save_npz
from retarget_human_r12 import Human,unit
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy
from author_articulation_r42 import hands
from author_combat_performance_r36 import mix,ease
from author_gameplay_motion_r32 import rotate_stage

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/repair_r43/locomotion'
SOURCE=ROOT/'external-assets/incoming/mocap/accad-eva-seed-r01/third_party_normalized/source_extract/male2_bvh'
CLIPS={'idle':('Male2_A1_Stand.bvh',0,114),'walk':('Male2_B3_Walk.bvh',189,309),'run':('Male2_C3_Run.bvh',27,50)}

def human(file):
    data=load_bvh(file);reference=load_bvh(SOURCE/'Male2_A1_Stand.bvh')
    assert data['names']==reference['names'] and np.allclose(data['offsets'][1:],reference['offsets'][1:]),'Reference actor skeleton mismatch'
    # These BVHs store joint pre-rotations in motion channels. Summing OFFSET
    # with zero rotations produces a folded skeleton, NOT an upright T-pose.
    # Use the same measured standing frame for all three clips.
    rest=reference['positions'][0].copy()
    data['positions']=np.concatenate([rest[None],data['positions']]);data['rotations']=np.concatenate([reference['rotations'][:1],data['rotations']])
    target=OUT/'source'/(file.stem+'_calibrated.npz');target.parent.mkdir(exist_ok=True);save_npz(target,data)
    h=Human(target);h.reference_frame=0;h.reference=h.positions[0,h.index[h.map['hip']]].copy();h.reference[1]=0
    for side,word in (('l','Left'),('r','Right')):
        if h.map['finger_'+side] not in h.index:h.map['finger_'+side]=word+'Hand_End'
        if h.map.get('thumb_'+side) not in h.index:h.map.pop('thumb_'+side,None)
    across=rest[h.index[h.map['shoulder_l']]]-rest[h.index[h.map['shoulder_r']]];forward=unit(np.cross(across,[0,1,0])*[1,0,1],(0,0,-1))
    h.basis=R.from_euler('y',np.arctan2(forward[0],-forward[2]));h.floor=min(rest[h.index[h.map['ankle_'+s]],1] for s in ('l','r'))
    h.height=float(rest[h.index['Head_End'],1]-min(rest[h.index[h.map['toe_'+s]],1] for s in ('l','r')))
    return h

def contact_phases(heights):
    result={}
    for i,side in enumerate(('l','r')):
        values=heights[:,i];threshold=float(values.min()+max(.12,np.ptp(values)*.10));contact=values<=threshold
        entered=[j/(len(values)-1) for j in range(len(values)-1) if contact[j] and not contact[(j-1)%(len(values)-1)]]
        left=[j/(len(values)-1) for j in range(len(values)-1) if not contact[j] and contact[(j-1)%(len(values)-1)]]
        result[side]=dict(forward=entered or [float(np.argmin(values)/(len(values)-1))],reverse=left or [float(np.argmin(values)/(len(values)-1))])
    return result

def main(rigs):
    OUT.mkdir(exist_ok=True);bodyfile=ROOT/'run/projectseele-local-maps/eva_body_r42.json';data=json.loads(bodyfile.read_text('utf8'));report=[]
    data['locomotion_contract_r43']={}
    for key in rigs:
        actor=Actor(key);override=data['stance_clips_by_rig'][str(key)];names=override['bones'];contracts={}
        for label,(source,start,end) in CLIPS.items():
            file=SOURCE/source;h=human(file);retarget=AnatomicalRetarget(h);start_point,_=h.sample(start+1);end_point,_=h.sample(end+1)
            displacement=end_point['hip']-start_point['hip'];displacement[1]=0
            turn=R.identity() if label=='idle' else R.from_euler('y',np.arctan2(displacement[0],-displacement[2]))
            duration=(end-start)/h.fps;count=round(duration*60)+1;poses=[];travel=[]
            for frame in np.linspace(start+1,end+1,count):
                pose,delta,_=retarget.pose(frame,support='air');anatomy(actor,pose,closure=.10 if label!='run' else .3)
                rotate_stage(pose,actor.rig,turn);poses.append(pose);travel.append(turn.apply(delta))
            travel=np.asarray(travel);travel-=travel[0];travel[:,1]=0
            stride=float(np.linalg.norm(travel[-1])*5/16) if label!='idle' else 0
            # The movement controller supplies horizontal displacement. Poses
            # stay local; a final short recovery closes the chosen source cycle.
            reference=copy.deepcopy(poses[0]);frames=[];heights=[]
            for i,pose in enumerate(poses):
                t=i/(count-1)
                if t>.88:pose=mix(pose,copy.deepcopy(reference),ease((t-.88)/.12))
                floors=[]
                for side in ('l','r'):
                    q=R.from_matrix(pose.matrix('foot_'+side)[:3,:3]);floors.append(float((q.apply(actor.feet[side])+pose.point('foot_'+side))[:,1].min()))
                if min(floors)<0:
                    pose.setp('root',pose.p['root']+[0,-min(floors),0]);floors=np.asarray(floors)-min(floors)
                heights.append(np.asarray(floors)*5/16);hands(actor,pose,.10 if label!='run' else .3)
                frame=actor.rig.encode(pose,contacts=tuple(v<.35 for v in np.asarray(floors)*5/16),bone_names=names);frames.append(frame)
            frames[-1]=copy.deepcopy(frames[0]);heights[-1]=heights[0]
            override['clips'][label]=dict(duration_seconds=duration,loop=True,frames=frames,source_file=source,source_frames=[start,end])
            contracts[label]=dict(stride_blocks=stride,source_duration_seconds=duration,contacts=contact_phases(np.asarray(heights)),
                source_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),source_frames=[start,end])
            report.append(dict(rig=key,clip=label,frames=count,stride_blocks=stride,source_frames=[start,end]))
        data['locomotion_contract_r43'][str(key)]=contracts
    data['r43_locomotion_provenance']=dict(source_body_sha256=hashlib.sha256(bodyfile.read_bytes()).hexdigest(),
        source='ACCAD / The Ohio State University Open Motion Project',license='CC BY 3.0',url='https://accad.osu.edu/research/motion-lab/mocap-system-and-data',
        changes='Shared measured standing calibration (Male2_A1_Stand frame 0, never zero-channel OFFSET skeleton); per-rig anatomical knee frame; actual joint lengths; cyclic endpoint recovery; hand articulation; source travel and sole contact metadata',
        scope='CANDIDATE idle/walk/run only; complex terrain, weapon/stance transitions and source-to-native vertex chain remain unverified')
    (OUT/'eva_body_r43.json').write_text(json.dumps(data,separators=(',',':')),'utf8');(OUT/'summary.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--rigs',default='1');args=p.parse_args();main([int(s) for s in args.rigs.split(',')])
