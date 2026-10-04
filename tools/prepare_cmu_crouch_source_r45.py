"""Prepare a measured CMU crouch take for the existing local Rokoko pipeline.

Preserve the complete source hierarchy/FK and timings. CMU's documented ASF
unit conversion is applied once; calibration uses this same captured actor.
No generated pose, EVA resource, world or installation is changed here.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
from bvh_motion_r12 import load_bvh


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def canonical(data):
    names={'root':'Hips','lowerback':'Spine','upperback':'Spine1',
           'thorax':'ChestExtra','lowerneck':'Neck','upperneck':'NeckExtra',
           'head':'Head','head_End':'Head_End'}
    for s,w in [('l','Left'),('r','Right')]:
        for old,new in [('hipjoint','HipSocket'),('femur','UpLeg'),('tibia','Leg'),
                        ('foot','Foot'),('toes','ToeBase'),('toes_End','ToeBase_End'),
                        ('clavicle','Shoulder'),('humerus','Arm'),('radius','ForeArm'),
                        ('wrist','ForeArmTwist'),('hand','Hand'),('fingers','FingerBase'),
                        ('fingers_End','Hand_End'),('thumb','Thumb'),('thumb_End','Thumb_End')]:
            names[s+old]=w+new
    d=dict(data);d['names']=[names[n]for n in data['names']]
    assert len(set(d['names']))==len(d['names'])
    scale_cm=2.54/.45
    d['positions']=data['positions']*scale_cm;d['offsets']=data['offsets']*scale_cm
    # BVH frame-time serialization rounds 1/120. Preserve nominal recorded
    # 120Hz, documented by the original CMU subject page and conversion args.
    assert abs(data['fps']-120)<.01
    d['fps']=120.
    return d,names


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--fixture',type=Path,required=True)
    p.add_argument('--neutral-bvh',type=Path,required=True,
                   help='Same-ASF zero-DOF calibration converted by the pinned AMC converter; not a guessed standing frame')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();assert not a.out.exists()
    faq=(a.source/'CMU_FAQ_LICENSE.html').read_text('utf8')
    assert 'without permission' in faq and '0.056444' in faq
    take=a.source/'136_09.bvh';standing=a.neutral_bvh
    data,aliases=canonical(load_bvh(take));neutral,_=canonical(load_bvh(standing))
    assert data['names']==neutral['names'] and np.array_equal(data['offsets'],neutral['offsets'])
    ns=data['names'];hip=ns.index('Hips');points=data['positions'];quats=data['rotations']
    neutral_points=neutral['positions'][0]
    calibration_knees={}
    for word in ('Left','Right'):
        u=neutral_points[ns.index(word+'Leg')]-neutral_points[ns.index(word+'UpLeg')]
        v=neutral_points[ns.index(word+'Foot')]-neutral_points[ns.index(word+'Leg')]
        angle=float(np.degrees(np.arccos(np.clip(u@v/(np.linalg.norm(u)*np.linalg.norm(v)),-1,1))))
        assert angle<.05,('Calibration subtracts real crouch flexion',word,angle)
        calibration_knees[word]=angle
    root=R.from_quat(quats[:,hip]);relative=np.stack([root.inv().apply(points[:,i]-points[:,hip])for i in range(len(ns))],axis=1)
    local=np.empty_like(quats)
    for i,parent in enumerate(data['parents']):
        local[:,i]=quats[:,i]if parent<0 else(R.from_quat(quats[:,parent]).inv()*R.from_quat(quats[:,i])).as_quat()
    relevant=[ns.index(n)for n in ['Spine1','LeftUpLeg','LeftLeg','LeftFoot','RightUpLeg','RightLeg','RightFoot']]
    candidates=[]
    for interval in range(100,265,4):
        for first in range(140,min(1000,len(points)-interval),4):
            last=first+interval
            path=points[first:last+1,hip][:,[0,2]]*.01
            travel=float(np.linalg.norm(path[-1]-path[0]));distance=float(np.linalg.norm(np.diff(path,axis=0),axis=1).sum())
            if travel<.35 or travel/max(distance,1e-9)<.98:continue
            angular=2*np.arccos(np.clip(np.abs((local[first,relevant]*local[last,relevant]).sum(1)),0,1))
            position=np.linalg.norm(relative[first,relevant]-relative[last,relevant],axis=1)*.01
            score=float(np.mean(angular**2)+10*np.mean(position**2))
            candidates.append({'first':first,'last':last,'score':score,'travel_m':travel,
                               'straightness':travel/distance,'max_joint_seam_degrees':float(np.degrees(angular).max()),
                               'max_relative_seam_m':float(position.max())})
    assert candidates
    candidates.sort(key=lambda row:row['score']);selected=candidates[0]
    count=(selected['last']-selected['first'])//4+1
    a.out.mkdir(parents=True);(a.out/'source').mkdir()
    for name,d in [('crouch_walk',data),('calibration_stand',neutral)]:
        if name=='calibration_stand':d=dict(d,positions=d['positions'][:1],rotations=d['rotations'][:1])
        np.savez_compressed(a.out/'source'/f'{name}.npz',**{k:d[k]for k in ('names','parents','positions','rotations','fps','offsets')})
    duration=(selected['last']-selected['first'])/120
    segment={'label':'crouch_walk','source_file':str(take.resolve()),'source_sha256':sha(take),
             'source_frame_range':[selected['first'],selected['last']],'source_fps':120.,
             'original_window_seconds':duration,'candidate_frames':[1,count],
             'candidate_seconds':duration,'candidate_pose_interval_seconds':duration,
             'source_time_preserved':True,'source_semantics':'CMU subject136 trial09 Walk Crouched; source is a stylized-walk capture, not asserted military or TV choreography',
             'source_url':'https://mocap.cs.cmu.edu/search.php?subjectnumber=136',
             'source_license':'CMU motion data may be copied, modified or redistributed without permission; attribution retained'}
    card={'schema':'projectseele.continuous-leg-source.r44','fps':30,'frames':count,
          'segments':[segment],'source_kind':'Original CMU subject136 crouched walk',
          'source_aliases':aliases,'source_unit_to_cm':2.54/.45,
          'unit_authority':'https://mocap.cs.cmu.edu/faqs.php',
          'calibration':'Same subject136 ASF zero-DOF reference converted by the pinned original converter; explicitly a bind reference, not a captured standing action',
          'source_timing_preserved':True,'quality':'Source candidate only; not retargeted, not native or art accepted'}
    fixture=json.loads(a.fixture.read_text('utf8'))
    fixture.update(source_motion_card=card,duration=count/30,quality=card['quality'])
    (a.out/'source_card.json').write_text(json.dumps(card,indent=2),'utf8')
    (a.out/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8')
    (a.out/'receipt.json').write_text(json.dumps({'inputs':{str(q):sha(q)for q in (take,standing,a.source/'136.asf',a.source/'CMU_FAQ_LICENSE.html',a.fixture)},
        'selected':selected,'first20':candidates[:20],'alias_only_no_hierarchy_change':True,
        'calibration_frame':0,'calibration_knee_flexion_degrees':calibration_knees,
        'source_units_to_cm':2.54/.45,'world_write':False,'installed':False},indent=2),'utf8')
    print(json.dumps({'selected':selected,'frames':count,'duration':duration,'source_only':True}))


if __name__=='__main__':main()
