"""Independent body3: remove the long planted hold and lead the rush with reachable hands."""
from pathlib import Path
import argparse, copy, hashlib, json
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.spatial.transform import Rotation as R
from r52_motion_core import selected, read, UNIT, MIRROR, ease, mix
from author_finisher_r52 import world
from bake_finisher_r52 import anchors, sole_point
from revise_finisher_body_r52 import ground_feet, continuous_arms, preserve_hinges, rotation_mix
from anatomical_hinge_r35 import solve as hinge


def retain_source_soles(pose,root,goals):
    """Keep the actual original foot orientation; only correct resampling error."""
    mirror=np.ones(3) if pose.rig.angel else MIRROR
    orientations={side:R.from_matrix(pose.matrix('foot_'+side)[:3,:3]) for side in ('l','r')}
    for _ in range(5):
        for side in ('l','r'):
            difference=(goals[side]-sole_point(pose,root,side))*mirror/UNIT
            point=pose.point('foot_'+side)+difference
            hinge(pose,pose.rig.P,'leg_'+side,'shin_'+side,'foot_'+side,pose.rig.knees[side],point,
                  pose.q['root'].apply([0,0,-1]),[-1,0,0],orientations[side])


def preserve_shoe_knee_swivel(pose,side,angle):
    """Finite knee clearance around the intact hip/ankle line; keep full shoe FK."""
    if abs(angle)<1e-9:return
    foot=pose.matrix('foot_'+side).copy();hip=pose.point('leg_'+side);ankle=pose.point('foot_'+side)
    axis=ankle-hip;axis/=np.linalg.norm(axis)
    upper=R.from_matrix(pose.matrix('leg_'+side)[:3,:3])
    pose.setq('leg_'+side,R.from_matrix(pose.parent('leg_'+side)[:3,:3]).inv()*R.from_rotvec(axis*np.radians(angle))*upper)
    preserve_hinges(pose)
    pose.setq('foot_'+side,R.from_matrix(pose.parent('foot_'+side)[:3,:3]).inv()*R.from_matrix(foot[:3,:3]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('body','assets','angel-rig','source','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    target=args.out/'first_battle_r52_body3.json'
    assert not target.exists(), 'Preserve every attempted clip'
    _,hero,angel=selected(args.body,args.assets,args.angel_rig)
    old=read(args.source);candidate=copy.deepcopy(old);fps=old['fps'];assert fps==60
    rigs={'eva':hero,'angel':angel}
    # Each curve samples the existing original source pose/contacts; no actor
    # scale or bone lengths are changed. Separate clocks shorten both holds.
    clocks={
        'eva':lambda t:np.interp(t,[12,13.2,14.5,15.6,17.9,18.6],[12,13.3,16.1,16.83,17.9,18.6]),
        'angel':lambda t:np.interp(t,[12,14.25,14.4,14.85,15.5,16.1,17.9,18.6],[12,14.65,15.75,16.1,16.65,17.15,17.9,18.6])}
    def source(role,time):
        frame=float(np.clip(time*fps,0,len(old[role]['frames'])-1));first=int(np.floor(frame));last=min(first+1,len(old[role]['frames'])-1);weight=frame-first;rig=rigs[role]
        p=mix(rig.decode(old[role]['frames'][first],old[role]['bones']),rig.decode(old[role]['frames'][last],old[role]['bones']),weight)
        root=np.asarray(old[role]['root_blocks'][first])*(1-weight)+np.asarray(old[role]['root_blocks'][last])*weight
        soles={side:np.asarray(old[role]['foot_'+side+'_blocks'][first])*(1-weight)+np.asarray(old[role]['foot_'+side+'_blocks'][last])*weight for side in ('l','r')}
        contacts=[bool(old[role]['frames'][first]['foot_contact'][i] and old[role]['frames'][last]['foot_contact'][i]) for i in (0,1)]
        return p,root,soles,contacts
    baseline=anchors(old,hero);previous={role:source(role,12)[0] for role in rigs};rows=[]
    _,hfinal,_,_=source('eva',18.25)
    hready=source('eva',13.3)[0];hbrace=source('eva',17.9)[0]
    for index in range(720,1117):
        t=index/fps;poses={};roots={};support={};contacts={}
        for role in rigs:
            p,root,soles,flags=source(role,float(clocks[role](t)))
            poses[role]=p;roots[role]=root;support[role]=soles;contacts[role]=flags
        h,a=poses['eva'],poses['angel'];hr,ar=roots['eva'],roots['angel']
        source_fingers={name:(q,h.p[name].copy()) for name,q in h.q.items() if name.startswith('r45_hand_')}
        if 13.2<=t<14.5:
            readiness=ease((t-13.2)/1.1)
            # Bracing mass/guard changes while the real feet remain planted.
            for name in ('torso_upper','neck','head'):
                h.setq(name,rotation_mix(hready.q[name],hbrace.q[name],readiness*.55))
        if 13.2<=t<=18.6:
            readiness=ease((t-13.2)/1.1)
            goals={side:hr+np.array([7-3*readiness,36+4*readiness,(1 if side=='r' else -1)*(8+4*readiness)]) for side in ('l','r')}
            continuous_arms(hero,h,hr,goals,90,previous['eva'])
            # The arm helper has relaxed defaults. Retain every authored
            # finger channel and the existing finite contact closure instead.
            for name,(rotation,position) in source_fingers.items():h.setq(name,rotation);h.setp(name,position)
        if 14.85<=t<=18.6:
            lead=ease((t-14.85)/.90);around=ease((t-16.1)/.75);inward=ease((t-16.85)/1.05)
            goals={}
            for side in ('l','r'):
                sign=1 if side=='l' else -1
                original=world(a,ar,'hand_'+side)
                destination=np.array([-31-5*around,35-around,60+sign*(18-8*inward)])
                wanted=original*(1-lead)+destination*lead
                origin=world(a,ar,'arm_'+side)
                reach=(np.linalg.norm(angel.elbows[side]-angel.P['arm_'+side])+np.linalg.norm(angel.P['hand_'+side]-angel.elbows[side]))*UNIT*.987
                delta=wanted-origin;distance=np.linalg.norm(delta)
                if distance>reach:wanted=origin+delta*(reach/distance)
                goals[side]=wanted
            original_orientations={side:R.from_matrix(a.matrix('hand_'+side)[:3,:3]) for side in ('l','r')}
            continuous_arms(angel,a,ar,goals,90,previous['angel'])
            for side in ('l','r'):
                desired=R.from_euler('y',0 if side=='l' else 180,degrees=True)*R.from_euler('x',-45,degrees=True)
                current=original_orientations[side]
                a.setq('hand_'+side,R.from_matrix(a.parent('hand_'+side)[:3,:3]).inv()*rotation_mix(current,desired,lead))
        for role,p,root in [('eva',h,hr),('angel',a,ar)]:
            retain_source_soles(p,root,support[role])
            if role=='eva':preserve_shoe_knee_swivel(p,'l',4*ease((t-13.25)/.25)*(1-ease((t-13.7)/.25)))
            preserve_hinges(p);candidate[role]['frames'][index]=p.encode(candidate[role]['bones'],contacts[role]);candidate[role]['root_blocks'][index]=root.tolist()
            for side in ('l','r'):
                candidate[role]['hand_'+side+'_blocks'][index]=world(p,root,'hand_'+side).tolist();candidate[role]['foot_'+side+'_blocks'][index]=sole_point(p,root,side).tolist()
            if role=='eva':
                for channel,(bone,point) in baseline.items():candidate[role][channel][index]=world(p,root,bone,point).tolist()
            else:
                for channel,bone,point in [('eye_blocks','head',angel.eye),('core_blocks','torso_upper',angel.core),('waist_blocks','torso_lower',angel.waist)]:candidate[role][channel][index]=world(p,root,bone,point).tolist()
        previous={'eva':h,'angel':a}
        if index%6==0:rows.append(dict(frame=index,seconds=t,original_source_seconds={role:float(clocks[role](t)) for role in rigs},roots={role:root.tolist() for role,root in roots.items()},contacts=contacts))
        if index%120==0:print('body3 exact frame',index,flush=True)
    # The endpoint must enter the frozen explosion without a new pose/root cut.
    for role in rigs:
        for endpoint in (720,1116):
            candidate[role]['frames'][endpoint]=copy.deepcopy(old[role]['frames'][endpoint])
            for name,value in old[role].items():
                if name!='frames' and isinstance(value,list) and len(value)==1381:candidate[role][name][endpoint]=copy.deepcopy(value[endpoint])
    candidate['r52_finisher_rebuild'].update(body_revision='Body3: shorter recovery hold, earlier actual two-foot rush, reachable hands before final torso closure; runtime death/UUID code untouched',body_changed_frames=[720,1115],native_verified=False,user_accepted=False)
    target.write_text(json.dumps(candidate,separators=(',',':')),'utf8')
    report=dict(source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),body_source_sha256=hashlib.sha256(args.body.read_bytes()).hexdigest(),changed_frames=[720,1115],frames=len(candidate['eva']['frames']),fps=fps,actor_scales_changed=False,bone_lengths_changed=False,foot_goals='Retimed same original actual soles, re-solved anatomical hinge chains',rush_window=[14.4,16.1],hand_lead_window=[14.85,15.75],closure_window=[16.1,17.9],runtime_death_tick=372,samples=rows,native_verified=False,user_accepted=False)
    (args.out/'BODY3_REVISION_REPORT.json').write_text(json.dumps(report,indent=2),'utf8')
    print(target,flush=True)


if __name__=='__main__':main()
