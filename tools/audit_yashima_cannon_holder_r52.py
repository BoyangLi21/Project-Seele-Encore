"""Read-only exact production convex-body/AABB admission audit; no world writes or native pass claim."""
from pathlib import Path
import json,itertools
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.Codex/r52_operations/calibration'
def main():
    candidate=json.loads((OUT/'STATION_CANDIDATE.json').read_text())
    matrices=json.loads((OUT/'fitted/actual_fitted_bone_matrices.json').read_text())
    physical=json.loads(Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game/projectseele-local-maps/articulated_bodies_r35.json').read_text())['models']['1']
    yaw=np.radians(candidate['prone_yaw']);forward=np.array([-np.sin(yaw),0,np.cos(yaw)]);right=np.cross(forward,[0,1,0])
    body=np.eye(4);body[:3,:3]=np.column_stack((right,[0,1,0],-forward))*25;body[:3,3]=candidate['prone_position']
    frame=candidate['mesh_frame'];gun=np.eye(4);gun[:3,:3]=Rotation.from_quat(frame['quaternion_xyzw']).as_matrix()*frame['scale'];gun[:3,3]=np.array(candidate['raised_position'])+frame['translation']
    corners=np.array(list(itertools.product(*zip(*candidate['bounds_local']))));points=np.c_[corners,np.ones(8)]@gun.T
    lo,hi=points[:,:3].min(0)+.001,points[:,:3].max(0)-.001
    local_lo,local_hi=np.array(candidate['bounds_local'])
    faces=np.array([[1,0,0,-local_hi[0]],[-1,0,0,local_lo[0]],[0,1,0,-local_hi[1]],[0,-1,0,local_lo[1]],[0,0,1,-local_hi[2]], [0,0,-1,local_lo[2]]])@np.linalg.inv(gun)
    blocked=[]
    for row in physical['bodies']:
        name=row['name']
        if name in ['hand_l','hand_r','wrist_l','wrist_r']:continue
        matrix=np.array(matrices[name]).reshape(4,4,order='F');matrix[:3,3]*=.2
        world=body@matrix@np.array(row['bind']).reshape(4,4)
        localbox=faces@world
        for planes in row.get('hull_planes',[]):
            both=np.r_[np.asarray(planes),localbox]
            result=linprog(np.zeros(3),A_ub=both[:,:3],b_ub=-both[:,3],bounds=[(None,None)]*3,method='highs')
            if result.success:blocked.append(name);break
    report=dict(scope='Same original cannon AABB and actual production posed convex hulls; read-only model admission audit, not native station acceptance',
        gun_bounds_world=[lo.tolist(),hi.tolist()],non_grip_body_intersections=blocked,clear=not blocked)
    (OUT/'HOLDER_COLLISION_AUDIT.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report))
if __name__=='__main__':main()
