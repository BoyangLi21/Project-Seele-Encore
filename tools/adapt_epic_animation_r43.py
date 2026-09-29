"""Read the real Epic Fight MAT export back into SEELE's pose coordinates.

Trial only: object-level travel is an explicit separate curve. No game asset
promotion and no claim that Epic Fight's combat engine is installed.
"""
from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_first_battle_r10 as battle

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43'

def main():
    fixture=json.loads((ART/'blender_interop/fixture.json').read_text('utf8'));reports=[]
    for actor in fixture['actors']:
        if 'candidate' not in actor['name']:continue
        source=ART/'tool_trials'/(actor['name']+'_epic.json');raw=json.loads(source.read_text('utf8'));rest={};parents={}
        def hierarchy(node,parent=None):
            n=node['name'];parents[n]=parent;m=np.asarray(node['transform']).reshape(4,4)
            rest[n]=m if parent is None else rest[parent]@m
            for child in node.get('children',[]):hierarchy(child,n)
        for node in raw['armature']['hierarchy']:hierarchy(node)
        channels={a['name']:a for a in raw['animation']};names=list(rest);inverse={n:np.linalg.inv(m) for n,m in rest.items()}
        C=np.array([[1.,0,0],[0,0,-1],[0,1,0]]);B=np.eye(4);B[:3,:3]=C@np.diag(battle.HEROMIRROR if actor['name'].startswith('eva') else [1,1,1])*battle.UNIT;I=np.linalg.inv(B)
        samples=[]
        for expected in actor['poses']:
            frame=expected['frame'];posed={};deform={};errors=[]
            for n in names:
                channel=channels[n];assert abs(channel['time'][frame-1]-frame/raw['fps'])<.0001
                local=np.asarray(channel['transform'][frame-1]).reshape(4,4);parent=parents[n]
                posed[n]=local if parent is None else posed[parent]@local;deform[n]=posed[n]@inverse[n]
            for bone,wanted in zip(actor['bones'],expected['deform']):errors.append(float(abs(deform[bone['name']]-wanted).max()))
            # Parent-relative deformation around the original SEELE pivots.
            model={n:I@m@B for n,m in deform.items()};q=[];position={}
            pivots={b['name']:I[:3,:3]@np.asarray(b['head']) for b in actor['bones']}
            for n in [b['name'] for b in actor['bones']]:
                parent=parents[n];local=model[n] if parent is None else np.linalg.inv(model[parent])@model[n]
                rotation=R.from_matrix(local[:3,:3]);x,y,z,w=rotation.as_quat();q.append([w,-x,-y,z])
                p=local[:3,3]-pivots[n]+rotation.apply(pivots[n]);position[n]=(p*[-1,1,1]).tolist()
            samples.append(dict(frame=frame-1,time=(frame-1)/raw['fps'],rotation_wxyz=q,bone_position_xyz=position,
                object_root_blocks=(C.T@(np.asarray(expected['root'])-[75,0,0])).tolist(),matrix_error_blocks=max(errors)))
        passed=max(p['matrix_error_blocks'] for p in samples)<.002
        out=ART/'tool_trials'/(actor['name']+'_seele_samples.json')
        out.write_text(json.dumps(dict(bones=[b['name'] for b in actor['bones']],frames=samples,
            root_source='Explicit armature-object curve in fixture; exporter omits it',scope=actor['weighting_scope'],passed=passed),separators=(',',':')),'utf8')
        reports.append(dict(actor=actor['name'],samples=len(samples),maximum_matrix_error=max(p['matrix_error_blocks'] for p in samples),passed=passed))
    (ART/'tool_trials/epic_readback_r43.json').write_text(json.dumps(reports,indent=2),'utf8');print(json.dumps(reports));assert all(p['passed'] for p in reports)

if __name__=='__main__':main()
