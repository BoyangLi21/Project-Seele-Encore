"""Check production hull-plane volume queries against an independent LP oracle."""
from pathlib import Path
import json
import numpy as np
from scipy.optimize import linprog
from scipy.spatial.transform import Rotation as R

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/combat'


def project(point,planes,passes=64):
    p=point.astype(np.float32).copy()
    for _ in range(passes):
        moved=0
        for n in planes:
            norm=float(n[:3]@n[:3]);outside=float(n[:3]@p+n[3]);old=p.copy()
            if norm>1e-12 and outside>0:p-=n[:3]*(outside/norm)
            moved=max(moved,float(np.sum((p-old)**2)))
        if moved<1e-12:break
    return p


def main():
    baseline=json.loads((ROOT/'artifacts/rebuild_r44/baseline.json').read_text());file=Path(baseline['instance'])/'projectseele-local-maps/articulated_bodies_r35.json'
    definitions=json.loads(file.read_text())['models'];rng=np.random.default_rng(44);cases=[];errors=[]
    for key,definition in definitions.items():
        hulls=[h for body in definition['bodies'] for h in body.get('hull_planes',[])]
        for index in range(20):
            hull=np.asarray(hulls[int(rng.integers(len(hulls)))],np.float32)
            centre=project(rng.uniform(-2,2,3),hull,128);rotation=R.random(random_state=rng).as_matrix();position=rng.uniform(-10,10,3)
            world=np.eye(4);world[:3,:3]=rotation*25;world[:3,3]=position
            worldCentre=(world@np.r_[centre,1])[:3];boxCentre=worldCentre+rng.uniform(-1,1,3)*(1 if index%2 else 20)
            half=rng.uniform(.1,3,3);planes=[]
            for axis in range(3):
                for sign in (-1,1):
                    n=np.zeros(4);n[axis]=sign;n[3]=-sign*boxCentre[axis]-half[axis]
                    q=world.T@n;q/=np.linalg.norm(q[:3]);planes.append(q)
            both=np.concatenate((hull,np.asarray(planes)),axis=0).astype(np.float32)
            start=(np.linalg.inv(world)@np.r_[boxCentre,1])[:3]
            candidate=project(start,both);accepted=bool(np.max(both[:,:3]@candidate+both[:,3])<=2e-5)
            oracle=linprog([0,0,0],A_ub=both[:,:3],b_ub=-both[:,3],bounds=[(None,None)]*3,method='highs')
            row=dict(profile=key,case=index,planes=len(both),runtime_algorithm=accepted,independent_oracle=bool(oracle.success))
            cases.append(row)
            if accepted!=bool(oracle.success):errors.append(row)
    result=dict(pass_=not errors,cases=len(cases),errors=errors,
                scope='Actual private articulated hull planes, rotated/transformed volumes, float32 projection checked against independent linear feasibility; native explosion/ray/field behavior separate',
                rows=cases)
    (ART/'hull_query_math.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(dict(pass_=not errors,cases=len(cases),errors=errors)),flush=True)
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
