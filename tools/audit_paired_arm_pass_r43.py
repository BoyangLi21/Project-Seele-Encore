"""Locate the R42 arm-pass deviation before rendering; do not infer artistic approval."""
from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_first_battle_r10 as b
from author_combat_r35 import Actor

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/repair_r43/first_battle'


def main():
    old=json.loads((ROOT/'run/projectseele-local-maps/first_battle_r42.json').read_text())
    candidate=json.loads((OUT/'first_battle_r43.json').read_text());actor=Actor(1);rows=[]
    for i in range(303):
        original=b.eva.decode(candidate['eva']['frames'][i],candidate['eva']['bones'])
        rewritten=b.eva.decode(old['eva']['frames'][i],old['eva']['bones'])
        root=np.asarray(old['eva']['root_blocks'][i])
        for side in ('l','r'):
            upper='arm_'+side;hand='hand_'+side
            elbow0=b.hero_world(original,root,upper,actor.elbows[side]);elbow1=b.hero_world(rewritten,root,upper,actor.elbows[side])
            wrist0=b.hero_world(original,root,hand);wrist1=b.hero_world(rewritten,root,hand)
            angle=(original.q[upper].inv()*rewritten.q[upper]).magnitude()*180/np.pi
            rows.append(dict(frame=i,time=i/30,side=side,shoulder_rotation_delta_degrees=float(angle),
                             elbow_displacement_blocks=float(np.linalg.norm(elbow1-elbow0)),wrist_displacement_blocks=float(np.linalg.norm(wrist1-wrist0)),
                             authored_elbow=elbow0.tolist(),r42_elbow=elbow1.tolist()))
    affected=[r for r in rows if r['elbow_displacement_blocks']>.25]
    grip=[r for r in rows if 5.1<=r['time']<=10.0]
    report=dict(scope='Same source/roots/torso/legs before 10.1s; R43 omits only the whole-scene arm normalization in this interval',
                first_deviation=affected[0] if affected else None,
                worst_grip=max(grip,key=lambda r:r['elbow_displacement_blocks']),
                worst_shoulder=max(rows,key=lambda r:r['shoulder_rotation_delta_degrees']),samples=rows,
                limitation='A large change establishes the first offline divergence, not that the earlier choreography is aesthetically acceptable; native and mesh review still required.')
    (OUT/'arm_pass_audit.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='samples'},indent=2))


if __name__=='__main__':main()
