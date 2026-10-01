"""Read and sample the encoded warped body at fractional runtime phases."""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
from validate_combat_bundle_r44 import Pose
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from rebuild_stance_hinges_r41 import reconstruct

ROOT=Path(__file__).resolve().parents[1]


def frame_between(a,b,weight):
    qa=np.asarray(a['rotation_wxyz']);qb=np.asarray(b['rotation_wxyz']);xyzw=lambda q:np.column_stack((q[:,1:4]*[-1,-1,1],q[:,0]))
    x,y=xyzw(qa),xyzw(qb);dot=(x*y).sum(1);y*=np.where(dot<0,-1,1)[:,None]
    theta=np.arccos(np.clip(abs(dot),0,1));sine=np.sin(theta)
    first=np.divide(np.sin((1-weight)*theta),sine,out=np.full_like(sine,1-weight),where=sine>1e-8)
    second=np.divide(np.sin(weight*theta),sine,out=np.full_like(sine,weight),where=sine>1e-8)
    q=x*first[:,None]+y*second[:,None];q/=np.linalg.norm(q,axis=1,keepdims=True)
    q=np.column_stack((q[:,3],q[:,:3]*[-1,-1,1]))
    positions={name:(np.asarray(a.get('bone_position_xyz',{}).get(name,[0,0,0]))*(1-weight)+np.asarray(b.get('bone_position_xyz',{}).get(name,[0,0,0]))*weight).tolist()
               for name in set(a.get('bone_position_xyz',{}))|set(b.get('bone_position_xyz',{}))}
    return dict(rotation_wxyz=q.tolist(),root_m=(np.asarray(a['root_m'])*(1-weight)+np.asarray(b['root_m'])*weight).tolist(),bone_position_xyz=positions)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bundle',type=Path,default=ROOT/'artifacts/rebuild_r44/combat/locomotion_warp/motion');args=ap.parse_args()
    body=json.loads((args.bundle/'eva_body_r44.json').read_text('utf8'));common.BODY=body;reports=[];errors=[]
    for key in range(5):
        rig=body['rigs'][str(key)];source=body['stance_clips_by_rig'][str(key)];vertices=body.get('rig_support',{}).get(str(key),body['support'])
        toes=json.loads((args.bundle/f'eva_gameplay_r44_{key}.json').read_text('utf8'))['support_toes']
        actor=Actor(key)
        for label in ('walk','run'):
            clip=source['clips'][label];frames=clip['frames'];count=len(frames)-1
            stride=body['locomotion_contract_r43'][str(key)][label]['runtime_stride_blocks_r44'];points=[];support=[];worstJoint=0
            for at in np.linspace(0,count,count*4+1):
                a=min(int(at),count);b=min(a+1,count);w=at-a
                frame=frame_between(frames[a],frames[b],w);pose=Pose(rig,source['bones'],frame)
                # Match EvaBodyPose.preserveJointCentres after interpolation.
                for side in ('l','r'):
                    name='shin_'+side;joint=pose.P.get('r30_knee_socket_'+side,pose.P[name]+[0,11.4,0]);delta=joint-pose.P[name]
                    pose.p[name]=delta-pose.q[name].apply(delta)
                pose.cache.clear();feet=[]
                if 'forefoot_curves_r44' in clip:
                    # The new runtime solves the interpolated end-effector
                    # curve after quaternion blending and terrain adjustment.
                    goals=clip['forefoot_curves_r44']
                    runtime=actor.rig.Pose()
                    for name in runtime.q:runtime.setq(name,pose.q[name]);runtime.setp(name,pose.p[name])
                    for side in ('l','r'):
                        foot='foot_'+side;offset=np.asarray(toes[side])*16;matrix=runtime.matrix(foot);orientation=R.from_matrix(matrix[:3,:3])
                        current=runtime.point(foot,actor.P[foot]+offset)
                        target=(np.asarray(goals[side][a])*(1-w)+np.asarray(goals[side][b])*w)*16;target[1]=current[1]
                        target-=orientation.apply(offset)
                        reconstruct(actor,runtime,side,target,orientation,runtime.q['leg_'+side])
                    pose.q.update(runtime.q);pose.p.update(runtime.p);pose.cache.clear()
                for side in ('l','r'):
                    matrix=pose.matrix('foot_'+side);point=pose.P['foot_'+side]+np.asarray(toes[side])*16
                    patch=(matrix@np.r_[point,1])[:3]*5/16
                    patch[2]-=at/count*stride;feet.append(patch)
                    joint=pose.P.get('r30_knee_socket_'+side,pose.P['shin_'+side]+[0,11.4,0])
                    worstJoint=max(worstJoint,float(np.linalg.norm(pose.point('leg_'+side,joint)-pose.point('shin_'+side,joint))))
                points.append(feet);support.append(np.asarray(frames[a]['foot_contact'],bool)&np.asarray(frames[b]['foot_contact'],bool))
            points=np.asarray(points);support=np.asarray(support,bool);valid=support[:-1]&support[1:]
            velocity=np.linalg.norm(np.diff(points[:,:,[0,2]],axis=0),axis=2)*count*4
            values=velocity[valid]
            row=dict(rig=key,clip=label,runtime_stride_blocks=stride,subsamples=len(points),
                     encoded_support_world_rms_blocks_per_cycle=float(np.sqrt(np.mean(values**2))),
                     encoded_support_world_max_blocks_per_cycle=float(values.max()),joint_gap_model_units=worstJoint)
            if row['encoded_support_world_rms_blocks_per_cycle']>1.0 or worstJoint>1e-3:errors.append(row)
            reports.append(row)
    result=dict(pass_=not errors,errors=errors,measurements=reports,
        scope='Read-back at quarter-frame phases through quaternion interpolation and runtime hinge-offset reconstruction; horizontal world support measured at the same forefoot marker as runtime, with source heel/toe roll retained',
        unverified=['Terrain/turning and walk-run mixture', 'Final GPU skinning', 'Network interpolation and perceptual cadence'])
    (args.bundle.parent/'encoded_support_check.json').write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps(result),flush=True)
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
