"""Export exact profile FK onto the already measured diagnostic body mesh."""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_captured_arm_support_r45 import Pose

p=argparse.ArgumentParser()
for k in ('body','sprint','fixture','out'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();assert not a.out.exists();a.out.mkdir(parents=True)
body=json.loads(a.body.read_text('utf8'));sprint=json.loads(a.sprint.read_text('utf8'))
fixture=json.loads(a.fixture.read_text('utf8'));actor=fixture['actors'][0];assert str(actor['key'])=='1'
profile=body['stance_clips_by_rig']['1'];doc={'bones':profile['bones'],'rig_contract_r44':body['rigs']['1']}
assert sprint['bones']==doc['bones'] and sprint['rig_contract_r44']==doc['rig_contract_r44']
convert=np.eye(4);convert[:3,:3]=np.array([[1,0,0],[0,0,-1],[0,1,0]])*5;inverse=np.linalg.inv(convert)
neutral={}
for b in actor['bones']:
    n=np.array(b['neutral_model'],dtype=float);n[:3,3]/=16;neutral[b['name']]=n
zero={'root_m':[0,0,0],'bone_position_xyz':{},'rotation_wxyz':[]}
rig={b['name']:b for b in doc['rig_contract_r44']}
for n in doc['bones']:
    angles=np.array(rig[n].get('rotation',[0,0,0]))*[-1,-1,1]
    x,y,z,w=R.from_euler('xyz',angles,degrees=True).as_quat();zero['rotation_wxyz'].append([w,-x,-y,z])
bind=Pose(doc,zero);errors={n:float(np.max(np.abs(bind.matrix(n)-neutral[n])))for n in doc['bones'] if n in neutral}
assert max(errors.values())<1e-4,('Saved fixture does not match actual profile bind matrices',sorted(errors.items(),key=lambda r:-r[1])[:3])
parents={b['name']:b.get('parent')for b in actor['bones']};roles={}
for role,clip in [('baseline',profile['clips']['run']),('tv_sprint',sprint['clips']['tv_sprint'])]:
    frames=[]
    for f in clip['frames']:
        pose=Pose(doc,f);cache={}
        def matrix(n):
            if n in cache:return cache[n]
            if n in pose.rig:m=pose.matrix(n)
            elif parents[n]:m=matrix(parents[n])@np.linalg.inv(neutral[parents[n]])@neutral[n]
            else:m=neutral[n]
            cache[n]=m;return m
        frames.append({n:(convert@matrix(n)@np.linalg.inv(neutral[n])@inverse).tolist()for n in neutral})
    roles[role]={'duration_seconds':clip['duration_seconds'],'frames':frames}
(a.out/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8')
(a.out/'poses.json').write_text(json.dumps(roles,separators=(',',':')),'utf8')
(a.out/'source_receipt.json').write_text(json.dumps({'inputs':{str(q):hashlib.sha256(q.read_bytes()).hexdigest()for q in (a.body,a.sprint,a.fixture)},
    'neutral_matrix_max_error':max(errors.values()),'scope':'Offline profile FK on saved body mesh; legacy fixture hands and seam skin are not the current native hand submission',
    'native':False,'visual_accepted':False},indent=2),'utf8')
print('Prepared matched offline baseline/sprint comparison',max(errors.values()))
