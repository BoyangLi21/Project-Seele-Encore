"""Close standing strikes in one root frame instead of accumulating planted drift.

Preserves source performance and attack timing/damage. These grounded punches
keep entity translation zero; their captured weight shift stays in the body.
The support solution uses the same fixed forefoot and anatomical hinge frames.
"""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_combat_r35 import Actor
from study_combat_performance_r36 import decode
from rebuild_stance_hinges_r41 import reconstruct,reachable_root
from author_combat_performance_r36 import mix,ease

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--rig',type=int,choices=range(3),required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);data=json.loads(a.source.read_text());actor=Actor(a.rig);guard_clip=data['clips']['r32_guard'];guard=decode(actor,data,guard_clip['frames'][len(guard_clip['frames'])//2])
    # Reconstruct the captured world pose before removing its entity travel.
    gtravel=np.asarray(guard_clip.get('trajectory_m',[[0,0,0]]*len(guard_clip['frames']))[len(guard_clip['frames'])//2])
    guard.setp('root',guard.p['root']+gtravel*[-112,112,112])
    offsets={s:np.asarray(data['support_toes'][s])*16 for s in ['l','r']}
    orientations={s:R.from_matrix(guard.matrix('foot_'+s)[:3,:3])for s in ['l','r']}
    anchors={s:guard.point('foot_'+s)+orientations[s].apply(offsets[s])for s in ['l','r']}
    for s in anchors:anchors[s][1]=0
    reports=[]
    for name in ['guard','jab','cross','hook','heavy']:
        clip=data['clips']['r32_'+name];old=copy.deepcopy(clip);frames=[];poses=[];previous={s:guard.q['leg_'+s]for s in ['l','r']}
        errors=[]
        for i,f in enumerate(old['frames']):
            t=i/(len(old['frames'])-1);pose=decode(actor,data,f);travel=np.asarray(old.get('trajectory_m',[[0,0,0]]*len(old['frames']))[i])
            pose.setp('root',pose.p['root']+travel*[-112,112,112])
            if name!='guard':
                # Follow-through and recovery occupy the complete post-contact
                # interval, instead of snapping to guard in the last17 percent.
                recovery=ease((t-.58)/.42);entry=ease(t/.16)
                pose=mix(copy.deepcopy(guard),pose,entry*(1-recovery))
            else:pose=mix(copy.deepcopy(guard),pose,ease(t/.15)*(1-ease((t-.85)/.15)))
            goals={};qs={}
            for s in ['l','r']:
                q=R.from_matrix(pose.matrix('foot_'+s)[:3,:3]);qs[s]=q
                sole=-q.apply(actor.feet[s])[:,1].min();target=anchors[s]-q.apply(offsets[s]);target[1]=sole;goals[s]=target
            reachable_root(actor,pose,goals)
            for s in ['l','r']:
                errors.append(reconstruct(actor,pose,s,goals[s],qs[s],previous[s]));previous[s]=pose.q['leg_'+s]
            frames.append(actor.rig.encode(pose,(True,True),data['bones']));poses.append(pose)
        clip.update(frames=frames,trajectory_m=[[0,0,0]for _ in frames],step_contacts=[[True,True]for _ in frames],
                    root_authority_r45='stationary-entity; captured weight shift in body; cyclic guard support',stance_locked=True)
        reports.append(dict(clip=name,old_end_entity_displacement_blocks=(np.asarray(old.get('trajectory_m',[[0,0,0]])[-1])*35).tolist(),
                            new_end_entity_displacement_blocks=[0,0,0],maximum_export_ankle_error_blocks=max(errors)*5/16,
                            endpoint_root_distance_blocks=float(np.linalg.norm(poses[-1].p['root']-poses[0].p['root'])*5/16)))
    data['r45_root_authority']=dict(source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),reports=reports,
        source_record='R43 captured body performance; corrected incompatible planted support/entity travel and recovery contract',native=False,art_approved=False)
    out=a.out/a.source.name;out.write_text(json.dumps(data,separators=(',',':')),'utf8');(a.out/'authoring.json').write_text(json.dumps(data['r45_root_authority'],indent=2),'utf8');print(json.dumps(reports,indent=2))

if __name__=='__main__':main()
