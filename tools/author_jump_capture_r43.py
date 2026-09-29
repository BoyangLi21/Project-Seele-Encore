"""Retarget one recorded leap continuously through preparation and landing.

The MC controller remains the vertical motion owner. Extract the recorded
ballistic pelvis travel instead of adding a second jump to the rendered root.
The source has no finger capture; hand closure is explicitly authored.
"""
from pathlib import Path
import copy,json,hashlib
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_locomotion_r43 import human,SOURCE
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy
from author_combat_performance_r36 import mix,ease
from author_gameplay_motion_r32 import rotate_stage
from study_combat_performance_r36 import decode
from author_articulation_r42 import hands

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';OUT=ART/'jump_capture'
SOURCE_FILE=SOURCE/'Male2_B18_WalkToLeapToWalk.bvh'
PREP,TAKEOFF,APEX,LAND,RECOVER=64,72,81,93,107

def main():
    OUT.mkdir(exist_ok=True);bodyfile=ART/'locomotion/eva_body_r43.json';body=json.loads(bodyfile.read_text('utf8'));reports=[]
    for rig in range(5):
        actor=Actor(rig);h=human(SOURCE_FILE);rt=AnatomicalRetarget(h)
        file=ART/'grounded_capture'/f'eva_gameplay_r42_{rig}.json';data=json.loads(file.read_text('utf8'))
        stance=body['stance_clips_by_rig'][str(rig)];idle=decode(actor,stance,stance['clips']['idle']['frames'][0])
        a,_=h.sample(TAKEOFF+1);b,_=h.sample(LAND+1);travel=b['hip']-a['hip'];travel[1]=0
        turn=R.from_euler('y',np.arctan2(travel[0],-travel[2]))
        source_hip=lambda p:(p['hip_l'][1]+p['hip_r'][1])*.5
        hip0,hip1=source_hip(a),source_hip(b)
        def captured(frame):
            p,delta,_=rt.pose(frame+1,support='air');anatomy(actor,p,closure=.24)
            # ACCAD's single hand end marker cannot define a stable palm roll.
            # Retain this rig's measured relaxed wrist frame; the recorded
            # shoulder and elbow still carry the complete arm gesture.
            for side in ('l','r'):
                for stem in ('wrist_','hand_'):
                    n=stem+side;p.setq(n,idle.q[n]);p.setp(n,idle.p[n])
            rotate_stage(p,actor.rig,turn)
            if TAKEOFF<=frame<=LAND:
                src,_=h.sample(frame+1);base=hip0+(hip1-hip0)*(frame-TAKEOFF)/(LAND-TAKEOFF)
                p.setp('root',p.p['root']+[0,-(source_hip(src)-base)*rt.leg_scale,0])
            return p
        def sole(p):
            return min(float((R.from_matrix(p.matrix('foot_'+s)[:3,:3]).apply(actor.feet[s])+p.point('foot_'+s))[:,1].min()) for s in ('l','r'))
        launch=captured(TAKEOFF);touch=captured(LAND);start_lift=-sole(launch);end_lift=-sole(touch)
        # Use the actual captured endpoint offsets for a continuous body root.
        def air(frame):
            p=captured(frame);u=(frame-TAKEOFF)/(LAND-TAKEOFF)
            p.setp('root',p.p['root']+[0,start_lift*(1-u)+end_lift*u,0]);return p
        launch=air(TAKEOFF);touch=air(LAND)
        poses={}
        poses['jump_start']=[]
        for t in np.linspace(0,1,61):
            p=captured(PREP+(TAKEOFF-PREP)*t);p.setp('root',p.p['root']+[0,-sole(p),0])
            p=mix(copy.deepcopy(idle),p,ease(t));poses['jump_start'].append(p)
        poses['jump_start'][-1]=copy.deepcopy(launch)
        poses['jump_flight']=[air(TAKEOFF+(APEX-TAKEOFF)*t*2 if t<=.5 else APEX+(LAND-APEX)*(t-.5)*2) for t in np.linspace(0,1,91)]
        poses['jump_land']=[]
        for t in np.linspace(0,1,61):
            p=captured(LAND+(RECOVER-LAND)*t);p.setp('root',p.p['root']+[0,-sole(p),0])
            p=mix(p,copy.deepcopy(idle),ease(max(0,(t-.25)/.75)));poses['jump_land'].append(p)
        poses['jump_land'][0]=copy.deepcopy(touch)
        errors=[]
        for left,right in [('jump_start','jump_flight'),('jump_flight','jump_land')]:
            x,y=poses[left][-1],poses[right][0]
            errors.append(dict(from_clip=left,to_clip=right,max_degrees=max(float(np.degrees((x.q[n].inv()*y.q[n]).magnitude())) for n in x.q),root_delta=float(np.linalg.norm(x.p['root']-y.p['root']))))
        assert all(r['max_degrees']<.001 and r['root_delta']<.001 for r in errors)
        for name,seq in poses.items():
            c=data['clips']['r32_'+name]
            c.update(frames=[actor.rig.encode(p,contacts=(name!='jump_flight',)*2,bone_names=data['bones']) for p in seq],
                loop=False,trajectory_m=[[0,0,0]]*len(seq),duration_seconds=1,takeoff_phase=1,ground_contact_phase=0,
                source_file=SOURCE_FILE.name,source_frames=[PREP,TAKEOFF] if name=='jump_start' else [TAKEOFF,APEX,LAND] if name=='jump_flight' else [LAND,RECOVER])
            if name=='jump_start':c['preparation_ticks']=6
        data['r43_jump_capture']=dict(source=str(SOURCE_FILE.relative_to(ROOT)),sha256=hashlib.sha256(SOURCE_FILE.read_bytes()).hexdigest(),
            license='CC BY 3.0',url='https://accad.osu.edu/research/motion-lab/mocap-system-and-data',
            reference='Same-actor measured standing frame, skeleton and offsets asserted; full body leap is a human movement reference, not TV animation capture',
            edits='Anatomical knees/elbows; ballistic pelvis travel extracted; continuous phase endpoints; current idle entry/recovery; rig-calibrated wrist frame and authored fingers (not hand mocap)',
            runtime='Preparation 6 ticks follows the captured 8 frames at 30 fps; buffered tap retained. Flight physics, cooldown and damage unchanged',status='CANDIDATE: native transition and visual review pending')
        (OUT/file.name).write_text(json.dumps(data,separators=(',',':')),'utf8');reports.append(dict(rig=rig,endpoints=errors))
    (OUT/'summary.json').write_text(json.dumps(reports,indent=2),'utf8');print('Five continuous captured leap candidates authored',flush=True)

if __name__=='__main__':main()
