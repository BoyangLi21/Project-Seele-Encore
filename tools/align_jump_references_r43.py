"""Make jump phases share the current rig's neutral reference, not three binds.

Keep the authored jump gesture and physics timing. Rebase each complete pose
relative to its own source endpoint; preserve anatomical hinges and bearing
feet. Output is an isolated candidate, never an installed runtime asset.
"""
from pathlib import Path
import copy,json,hashlib
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_combat_r35 import Actor
from study_combat_performance_r36 import decode
from rebuild_stance_hinges_r41 import reachable_root,reconstruct

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';OUT=ART/'jump_reference'

def gaps(a,b):
    return sorted([dict(bone=n,degrees=float(np.degrees((a.q[n].inv()*b.q[n]).magnitude()))) for n in a.q],key=lambda r:-r['degrees'])[:6]

def main():
    OUT.mkdir(exist_ok=True);bodyfile=ART/'locomotion/eva_body_r43.json';body=json.loads(bodyfile.read_text('utf8'));reports=[]
    for rig in range(5):
        actor=Actor(rig);source=ART/'grounded_capture'/f'eva_gameplay_r42_{rig}.json';data=json.loads(source.read_text('utf8'))
        stance=body['stance_clips_by_rig'][str(rig)];neutral=decode(actor,stance,stance['clips']['idle']['frames'][0]);target=copy.deepcopy(neutral)
        for name in ('jump_start','jump_flight','jump_land'):
            clip=data['clips']['r32_'+name];old=[decode(actor,data,f) for f in clip['frames']];reference=copy.deepcopy(old[0]);before=gaps(target,reference);poses=[]
            feet={s:target.point('foot_'+s).copy() for s in ('l','r')};orientations={s:R.from_matrix(target.matrix('foot_'+s)[:3,:3]) for s in ('l','r')}
            for p in old:
                for n in p.q:
                    p.setq(n,target.q[n]*reference.q[n].inv()*p.q[n]);p.setp(n,p.p[n]+target.p[n]-reference.p[n])
                # Local translations are a function of the final hinge angle,
                # not an independently interpolated animation channel.
                for side in ('l','r'):
                    for name2,joint in (('shin_'+side,actor.knees[side]),('forearm_'+side,actor.elbows[side])):
                        offset=joint-actor.P[name2];p.setp(name2,offset-p.q[name2].apply(offset))
                if name!='jump_flight':
                    reachable_root(actor,p,feet)
                    for side in ('l','r'):reconstruct(actor,p,side,feet[side],orientations[side],p.q['leg_'+side])
                poses.append(p)
            clip['frames']=[actor.rig.encode(p,contacts=(name!='jump_flight',)*2,bone_names=data['bones']) for p in poses]
            after_start=gaps(target,poses[0]);after_end=gaps(target,poses[-1])
            assert after_start[0]['degrees']<.05 and after_end[0]['degrees']<.05,(rig,name,after_start,after_end)
            reports.append(dict(rig=rig,clip=name,before_reference_gap=before,after_reference_gap=after_start,after_end_gap=after_end))
            target=copy.deepcopy(poses[-1])
        data['r43_jump_reference']=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),body_sha256=hashlib.sha256(bodyfile.read_bytes()).hexdigest(),
            method='Complete local reference delta per phase; explicit hinge position reconstruction; grounded source/landing feet; physics duration and damage unchanged',status='CANDIDATE, requires actual transition and visual review')
        (OUT/source.name).write_text(json.dumps(data,separators=(',',':')),'utf8')
    (OUT/'reference_gaps.json').write_text(json.dumps(reports,indent=2),'utf8');print('Authored five isolated jump-reference candidates',flush=True)

if __name__=='__main__':main()
