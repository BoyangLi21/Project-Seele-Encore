"""Measure the revised actual 60Hz skin/support/FK window without inferring artistic acceptance."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from r52_motion_core import selected, read, UNIT, MIRROR
from bake_finisher_r52 import sole_point


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('body','assets','angel-rig','clip','out'):parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();_,hero,angel=selected(args.body,args.assets,args.angel_rig);raw=args.clip.read_bytes();clip=json.loads(raw);clip_sha=hashlib.sha256(raw).hexdigest()
    report={};all_rows=[]
    for role,rig in [('eva',hero),('angel',angel)]:
        floor=(float('inf'),None);plant=(0,None);joint=(0,None);failures=[];run=[]
        for index in range(720,1177):
            pose=rig.decode(clip[role]['frames'][index],clip[role]['bones']);root=np.asarray(clip[role]['root_blocks'][index]);time=index/60
            if role=='eva' or time<18.6:
                points=pose.surface()*(MIRROR if role=='eva' else 1)*UNIT+root
                minimum=float(points[:,1].min())
                if minimum<floor[0]:floor=(minimum,index)
                if minimum<-.02:failures.append({'frame':index,'kind':'actual_skin_below_ground','minimum':minimum})
            soles={}
            for side,column in [('l',0),('r',1)]:
                sole=sole_point(pose,root,side);soles[side]=sole.tolist()
                if (role=='eva' or time<18.6) and clip[role]['frames'][index]['foot_contact'][column]:
                    error=max(0,-float(sole[1])-.002,float(sole[1])-.08)
                    if error>plant[0]:plant=(error,index)
                    if error>.03:failures.append({'frame':index,'side':side,'kind':'planted_actual_sole_gap','sole_y':float(sole[1])})
                for upper,lower,centre in [('leg_'+side,'shin_'+side,rig.knees[side]),('arm_'+side,'forearm_'+side,rig.elbows[side])]:
                    error=float(np.linalg.norm(pose.point(upper,centre)-pose.point(lower,centre))*UNIT)
                    if error>joint[0]:joint=(error,index)
                    if error>.001:failures.append({'frame':index,'kind':'separated_joint','lower':lower,'error':error})
            run.append({'frame':index,'seconds':time,'actual_soles':soles,'contacts':clip[role]['frames'][index]['foot_contact']})
            if index%120==0:print('audited full body',role,index,flush=True)
        speeds=[]
        for index in range(720,1178):
            before=np.asarray(clip[role]['frames'][index-1]['rotation_wxyz']);after=np.asarray(clip[role]['frames'][index]['rotation_wxyz'])
            before/=np.linalg.norm(before,axis=1,keepdims=True);after/=np.linalg.norm(after,axis=1,keepdims=True)
            dot=np.clip(abs(np.sum(before*after,axis=1)),0,1)
            values=np.degrees(2*np.arccos(dot))*60
            bone=int(np.argmax(values));speeds.append({'frame':index,'bone':clip[role]['bones'][bone],'degrees_per_second':float(values[bone])})
        planted=[]
        for side,column in [('l',0),('r',1)]:
            segment=[]
            for row in run+[{'frame':1177,'contacts':[False,False]}]:
                if row['contacts'][column] and (role=='eva' or row['seconds']<18.6):segment.append(row)
                elif segment:
                    points=np.asarray([row['actual_soles'][side] for row in segment])[:,[0,2]]
                    planted.append({'side':side,'frames':[segment[0]['frame'],segment[-1]['frame']],'material_sole_xz_span_metres':float(np.linalg.norm(np.ptp(points,axis=0)))})
                    segment=[]
        report[role]={'minimum_actual_full_skin_y':floor,'max_planted_sole_error_outside_ground_range':plant,'allowed_planted_range_metres':[-.002,.08],'max_elbow_knee_fk_error_metres':joint,'max_local_joint_velocity':max(speeds,key=lambda row:row['degrees_per_second']),'planted_segments':planted,'failures':failures}
        all_rows.append({'actor':role,'samples':run})
    assert hashlib.sha256(args.clip.read_bytes()).hexdigest()==clip_sha, 'Candidate changed during the exact support audit'
    args.out.write_text(json.dumps({'clip_sha256':clip_sha,'fps':60,'frames':[720,1176],'actors':report,'samples':all_rows,'limits':'Actual support/FK measurements only. Paired triangle clearance, continuous native movement/weight and artistic acceptance remain separate.','native_verified':False,'user_accepted':False},indent=2),'utf8')
    print(json.dumps({role:{key:value for key,value in item.items() if key!='failures'}|{'failure_count':len(item['failures'])} for role,item in report.items()},indent=2),flush=True)


if __name__=='__main__':main()
