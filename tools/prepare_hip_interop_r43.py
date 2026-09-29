"""Use the existing actual-mesh Blender fixture to view the isolated basis trial."""
from pathlib import Path
import copy,json
import numpy as np
import author_first_battle_r10 as b
from author_combat_r35 import Actor
from study_combat_performance_r36 import decode

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43'

def main():
    fixture=json.loads((ART/'blender_interop/fixture.json').read_text('utf8'))
    raw=json.loads((ART/'hip_diagnosis/rig_1.json').read_text('utf8'));actor=Actor(1)
    C=np.array([[1.,0,0],[0,0,-1],[0,1,0]]);B=np.eye(4);B[:3,:3]=C@np.diag(b.HEROMIRROR)*b.UNIT;I=np.linalg.inv(B)
    actors=[]
    for label,shift in [('before',-75),('candidate',75)]:
        data=copy.deepcopy(next(a for a in fixture['actors'] if a['name']=='eva_'+label));poses=[]
        for index in (0,8,16,25,34):
            p=decode(actor,raw,raw['poses'][label][index]['frame'])
            poses.append(dict(frame=index+1,time=index/30,root=[shift,0,0],deform=[(B@p.matrix(n['name'])@I).tolist() for n in data['bones']]))
        data['poses']=poses;actors.append(data)
    out=ART/'hip_diagnosis/blender';out.mkdir(exist_ok=True)
    (out/'fixture.json').write_text(json.dumps(dict(actors=actors,scope='Isolated source-basis trial; raw capture before floor contact, timing and blends; not gameplay quality approval'),separators=(',',':')),'utf8')
    print('Prepared source calibration comparison on actual Unit01 mesh')

if __name__=='__main__':main()
