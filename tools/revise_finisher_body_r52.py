"""Revise the failed native rise/approach performance using actual planted feet and run carry."""
from pathlib import Path
import argparse, copy, hashlib, json
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
from r52_motion_core import selected, read, UNIT, MIRROR, ease, mix, hand_controls
from author_finisher_r52 import stance, world, hand_world, foot_solve
from bake_finisher_r52 import anchors, sole_point
from anatomical_hinge_r35 import solve as hinge
from calibrated_arm_r49 import axial_twist


def rotation_mix(first, last, weight):
    return Slerp([0, 1], R.concatenate([first, last]))(float(np.clip(weight, 0, 1)))


def hermite(times, values, slopes, t):
    if t <= times[0]: return values[0]
    if t >= times[-1]: return values[-1]
    for i in range(len(times)-1):
        if t <= times[i+1]:
            duration=times[i+1]-times[i];u=(t-times[i])/duration
            return (2*u**3-3*u**2+1)*values[i]+(u**3-2*u**2+u)*duration*slopes[i]+(-2*u**3+3*u**2)*values[i+1]+(u**3-u**2)*duration*slopes[i+1]


def stepped(first, last, side, t, start, end, lift):
    u=float(np.clip((t-start)/(end-start),0,1));w=ease(u)
    point=first[side]*(1-w)+last[side]*w
    height=lift*np.sin(np.pi*u)**2
    return point, .05+height, bool(u <= 0 or u >= 1)


def ground_feet(pose, root, goals, heights, yaw,foot_yaws=None,sole_goals=None,preserve_root=False):
    rig=pose.rig;mirror=1 if rig.angel else MIRROR
    local={side:(goals[side]-root)*mirror/UNIT for side in ('l','r')}
    original_root=pose.p['root'].copy()
    foot_solve(rig,pose,local,yaw,sole_heights={s:(heights[s]-root[1])/UNIT for s in ('l','r')})
    if preserve_root:pose.setp('root',original_root)
    # Solve the actual deformed sole, never move the global entity root to
    # conceal a raised foot. This also includes the Angel's shin/foot weights.
    for _ in range(6):
        for side in ('l','r'):
            actual=sole_point(pose,root,side);correction=np.array([0,heights[side]-actual[1],0])
            if sole_goals is not None:correction[[0,2]]=np.asarray(sole_goals[side])[[0,2]]-actual[[0,2]]
            local[side]=local[side]+correction/UNIT
            hinge(pose,rig.P,'leg_'+side,'shin_'+side,'foot_'+side,rig.knees[side],local[side],
                  pose.q['root'].apply([0,0,-1]),[-1,0,0],R.from_euler('y',(foot_yaws or {}).get(side,yaw),degrees=True))


def run_carry(pose, idle, running, amount):
    # Both human carry clips come from the restored pre-FBX R48 source. Their
    # torso counter-rotation drives the mass of the rush; feet retain the
    # separately authored actual world contacts and anatomical leg lengths.
    for name, strength in [('torso_lower',.35),('torso_upper',.45),('neck',.2),('head',.2)]:
        if name in pose.q and name in idle.q and name in running.q:
            delta=idle.q[name].inv()*running.q[name]
            pose.setq(name,pose.q[name]*rotation_mix(R.identity(),delta,amount*strength))


def preserve_hinges(pose):
    for side in ('l','r'):
        for family,joint in [('forearm_',pose.rig.elbows[side]),('shin_',pose.rig.knees[side])]:
            name=family+side;delta=joint-pose.rig.P[name]
            pose.setp(name,delta-pose.q[name].apply(delta))


def continuous_arms(rig,pose,root,goals,yaw,previous):
    normals={};directions={}
    for side in ('l','r'):
        origin=previous.point('arm_'+side)
        direction=previous.point('hand_'+side)-origin;direction/=max(np.linalg.norm(direction),1e-8)
        elbow=previous.point('arm_'+side,rig.elbows[side])-origin
        normal=np.cross(direction,elbow);normal/=max(np.linalg.norm(normal),1e-8)
        normals[side]=normal;directions[side]=direction
        for prefix in ('arm_','forearm_','hand_'):
            name=prefix+side;pose.setq(name,previous.q[name])
    pose.r52_elbow_normals=normals;pose.r52_elbow_directions=directions
    hand_world(rig,pose,root,goals,yaw,stable=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('body','assets','angel-rig','source','out'):parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    body,hero,angel=selected(args.body,args.assets,args.angel_rig);old=read(args.source);out=copy.deepcopy(old)
    def original(role,seconds):
        index=round(seconds*60);rig=hero if role=='eva' else angel
        return rig.decode(old[role]['frames'][index],old[role]['bones']),np.asarray(old[role]['root_blocks'][index])
    h0,hr0=original('eva',12);a0,ar0=original('angel',12)
    a13,ar13=original('angel',13);a14,ar14=original('angel',14)
    old_hug_h,hr_end=original('eva',18.25);old_hug_a,ar_end=original('angel',18.25)
    hstand=stance(hero,yaw=90,drop=7,lean=-3);hr_stand=np.array([-42.,0,60])
    hand_world(hero,hstand,hr_stand,{'l':hr_stand+[7,36,-8],'r':hr_stand+[7,36,8]},90)
    hand_controls(hstand,'relaxed','relaxed')
    astand=stance(angel,yaw=90,drop=4,lean=-3,width=24);ar_stand=np.array([0.,0,60])
    hand_world(angel,astand,ar_stand,{'l':ar_stand+[-9,35,10],'r':ar_stand+[-9,35,-10]},90)
    hbrace=stance(hero,yaw=90,drop=4,lean=4)
    hand_world(hero,hbrace,hr_end,{'l':hr_end+[4,40,-12],'r':hr_end+[4,40,12]},90)
    hand_controls(hbrace,'grab','grab')
    afinal=stance(angel,yaw=90,drop=7,lean=-6,width=48)
    hand_world(angel,afinal,ar_end,{'l':[-36,34,70],'r':[-36,34,50]},90)
    for side in ('l','r'):
        desired=R.from_euler('y',0 if side=='l' else 180,degrees=True)*R.from_euler('x',-45,degrees=True)
        afinal.setq('hand_'+side,R.from_matrix(afinal.parent('hand_'+side)[:3,:3]).inv()*desired)
    def feet(pose,root):return {s:world(pose,root,'foot_'+s) for s in ('l','r')}
    hf0,hfs,hfe=feet(h0,hr0),feet(hstand,hr_stand),feet(hbrace,hr_end)
    af0,af13,af14,afs,afe=feet(a0,ar0),feet(a13,ar13),feet(a14,ar14),feet(astand,ar_stand),feet(afinal,ar_end)
    def soles(pose,root):return {s:sole_point(pose,root,s) for s in ('l','r')}
    as0,as13,as14,ass,ase=soles(a0,ar0),soles(a13,ar13),soles(a14,ar14),soles(astand,ar_stand),soles(afinal,ar_end)
    stance_source=body['stance_clips_by_rig']['1'];idle=hero.decode(stance_source['clips']['idle']['frames'][0],stance_source['bones'])
    run_frames=stance_source['clips']['run']['frames'];baseline=anchors(old,hero);rows=[];previous={'eva':h0,'angel':a0}
    for index in range(720,1117):
        t=index/60
        if t<13.3:
            u=ease((t-12)/1.3);h=mix(h0,hstand,ease((t-12)/1.1));hr=hr0*(1-u)+hr_stand*u
            hg,hh,hc={},{},[]
            for side,start,end in [('r',12.35,12.77),('l',12.82,13.24)]:
                hg[side],hh[side],contact=stepped(hf0,hfs,side,t,start,end,.9);hc.append(contact)
            hc=[hc[1],hc[0]]
        elif t<16.1:
            h=copy.deepcopy(hstand);hr=hr_stand.copy();hg=copy.deepcopy(hfs);hh={'l':.05,'r':.05};hc=[True,True]
            reaction=np.sin(np.pi*np.clip((t-14.65)/1.45,0,1))**2
            h.setq('torso_upper',h.q['torso_upper']*R.from_euler('xyz',[-4*reaction,6*reaction,0],degrees=True))
            h.setq('head',h.q['head']*R.from_euler('y',-5*reaction,degrees=True))
            readiness=ease((t-15.1)/.9)
            for side in ('l','r'):
                for prefix in ('arm_','forearm_','hand_'):
                    name=prefix+side;h.setq(name,rotation_mix(hstand.q[name],hbrace.q[name],readiness))
        else:
            u=ease((t-16.1)/.75);h=mix(hstand,hbrace,u);hr=hr_stand*(1-u)+hr_end*u
            hg,hh,hc={},{},[]
            for side,start,end in [('l',16.1,16.43),('r',16.5,16.83)]:
                hg[side],hh[side],contact=stepped(hfs,hfe,side,t,start,end,.85);hc.append(contact)
        if t<14:
            a,ar=original('angel',t)
            ag,ah,ac,asp={},{},[],{}
            first,last,first_soles,last_soles=(af0,af13,as0,as13) if t<13.2 else (af13,af14,as13,as14)
            schedule=[('r',12.05,12.33),('l',12.35,12.7)] if t<13.2 else [('r',13.2,13.55),('l',13.6,13.95)]
            for side,start,end in schedule:
                ag[side],ah[side],contact=stepped(first,last,side,t,start,end,.8);ac.append(contact)
                asp[side]=first_soles[side]*(1-ease((t-start)/(end-start)))+last_soles[side]*ease((t-start)/(end-start))
            ac=[ac[1],ac[0]]
        elif t<14.65:
            u=ease((t-14)/.65);a=mix(a14,astand,u);ar=ar14*(1-u)+ar_stand*u
            ag,ah,ac,asp={},{},[],{}
            for side,start,end in [('r',14.0,14.28),('l',14.32,14.60)]:
                ag[side],ah[side],contact=stepped(af14,afs,side,t,start,end,.65);ac.append(contact)
                asp[side]=as14[side]*(1-ease((t-start)/(end-start)))+ass[side]*ease((t-start)/(end-start))
            ac=[ac[1],ac[0]]
        elif t<15.75:
            a=copy.deepcopy(astand);ar=ar_stand.copy();ag=copy.deepcopy(afs);ah={'l':.05,'r':.05};ac=[True,True];asp=copy.deepcopy(ass)
            response=np.sin(np.pi*np.clip((t-14.75)/1.0,0,1))**2
            a.setq('torso_upper',a.q['torso_upper']*R.from_euler('xyz',[-5*response,-4*response,0],degrees=True))
            a.setq('neck',a.q['neck']*R.from_euler('x',-7*response,degrees=True))
            a.setq('head',a.q['head']*R.from_euler('x',4*response,degrees=True))
        else:
            x=hermite([15.75,16.1,16.65,17.15],[0,-4,-15.5,-19],[0,-20,-20,0],t)
            ar=np.array([x,0,60.]);running=ease((t-15.75)/.25)*(1-ease((t-16.65)/.5))
            lean=-3-12*running;drop=4+4*running+3*ease((t-16.7)/.5)
            a=stance(angel,yaw=90,drop=drop,lean=lean,width=24+24*ease((t-16.1)/.8))
            phase=((t-15.75)/.8)%1;template=hero.decode(run_frames[min(len(run_frames)-1,round(phase*(len(run_frames)-1)))],stance_source['bones'])
            run_carry(a,idle,template,running)
            arm_ready=ease((t-15.75)/.25)
            goals={s:ar+[-9*(1-arm_ready)+(-12+(1 if s=='l' else -1)*4*np.sin(phase*2*np.pi)*running)*arm_ready,35+2*np.cos(phase*2*np.pi)*running*arm_ready,(1 if s=='l' else -1)*(10+8*arm_ready)] for s in ('l','r')}
            ag,ah,ac,asp={},{},[],{}
            for side,start,end in [('r',15.85,16.35),('l',16.37,16.92)]:
                ag[side],ah[side],contact=stepped(afs,afe,side,t,start,end,1.65);ac.append(contact)
                asp[side]=ass[side]*(1-ease((t-start)/(end-start)))+ase[side]*ease((t-start)/(end-start))
            ac=[ac[1],ac[0]]
            if t>=17.15:
                closing=ease((t-17.15)/.75);a=mix(a,afinal,closing)
                # Move around the outside of the real shoulder before
                # closing inward. Interpolating the endpoint arm rotations
                # swept the long claws through the bracing 34-joint hands.
                around=ease((t-17.15)/.4);inward=ease((t-17.55)/.35)
                goals={s:np.array([-31-5*around,35-around,60+(1 if s=='l' else -1)*(18-8*inward)]) for s in ('l','r')}
            continuous_arms(angel,a,ar,goals,90,previous['angel'])
            for side in ('l','r'):
                desired=R.from_euler('y',0 if side=='l' else 180,degrees=True)*R.from_euler('x',-45,degrees=True)
                initial=R.from_matrix(astand.matrix('hand_'+side)[:3,:3])
                a.setq('hand_'+side,R.from_matrix(a.parent('hand_'+side)[:3,:3]).inv()*rotation_mix(initial,desired,arm_ready))
        if t>=17.15:
            u=ease((t-17.15)/.75);h=mix(h,hbrace,u)
        # The actual forehead horn and rear helmet otherwise cross the
        # approaching cowl/spikes. A small anticipatory head turn clears
        # them before the bodies meet, without shortening the source mesh.
        head_clearance=ease((t-16.15)/.5)
        if head_clearance>0:h.setq('head',h.q['head']*R.from_euler('xy',[16*head_clearance,10*head_clearance],degrees=True))
        ground_feet(h,hr,hg,hh,90)
        if t>=13.3:
            readiness=ease((t-15.1)/.9)
            goals={s:hr+np.array([7-3*readiness,36+4*readiness,(1 if s=='r' else -1)*(8+4*readiness)]) for s in ('l','r')}
            continuous_arms(hero,h,hr,goals,90,previous['eva'])
        root_right=a.q['root'].apply([1,0,0]);body_yaw=float(np.degrees(np.arctan2(-root_right[2],root_right[0])))
        foot_yaws={side:90*ease((t-start)/(end-start)) for side,start,end in [('r',14.0,14.28),('l',14.32,14.60)]} if 14<=t<14.65 else None
        ground_feet(a,ar,ag,ah,body_yaw,foot_yaws,asp,preserve_root=t<14)
        # Complete all hand channels from the authored source, never leave a
        # late default hand writer to close an otherwise unkeyed hand.
        if t>=13.3:
            open_hand=copy.deepcopy(h);closed_hand=copy.deepcopy(h)
            hand_controls(open_hand,'relaxed','relaxed');hand_controls(closed_hand,'grab','grab')
            closure=ease((t-17.1)/.65)
            for name in h.q:
                if name.startswith('r45_hand_'):h.setq(name,rotation_mix(open_hand.q[name],closed_hand.q[name],closure))
        preserve_hinges(h);preserve_hinges(a)
        previous={'eva':h,'angel':a}
        item={'eva':h,'angel':a,'hr':hr,'ar':ar}
        for role,root_key,pose,root,contacts in [('eva','hr',h,hr,hc),('angel','ar',a,ar,ac)]:
            out[role]['frames'][index]=pose.encode(out[role]['bones'],contacts);out[role]['root_blocks'][index]=root.tolist()
            for side in ('l','r'):
                out[role]['hand_'+side+'_blocks'][index]=world(pose,root,'hand_'+side).tolist()
                out[role]['foot_'+side+'_blocks'][index]=sole_point(pose,root,side).tolist()
            if role=='eva':
                for channel,(bone,point) in baseline.items():out[role][channel][index]=world(pose,root,bone,point).tolist()
            else:
                for channel,bone,point in [('eye_blocks','head',angel.eye),('core_blocks','torso_upper',angel.core),('waist_blocks','torso_lower',angel.waist)]:out[role][channel][index]=world(pose,root,bone,point).tolist()
        if index%6==0:
            rows.append({'frame':index,'seconds':t,'roots':{'eva':hr.tolist(),'angel':ar.tolist()},'contacts':{'eva':hc,'angel':ac},'actual_soles':{role:{s:sole_point(item[role],item['hr' if role=='eva' else 'ar'],s).tolist() for s in ('l','r')} for role in ('eva','angel')}})
        if index%120==0:print('revised action frame',index,flush=True)
    # Blend a real settled end pose into the already frozen blast recovery;
    # never restore the old backward-leaning embrace in one render frame.
    last_h=h;last_a=a
    for index in range(1117,1177):
        u=ease((index-1116)/60)
        for role,rig,first in [('eva',hero,last_h),('angel',angel,last_a)]:
            target=rig.decode(old[role]['frames'][index],old[role]['bones']);pose=mix(first,target,u)
            if role=='eva':ground_feet(pose,np.asarray(out[role]['root_blocks'][index]),copy.deepcopy(hfe),{'l':.05,'r':.05},90)
            preserve_hinges(pose)
            out[role]['frames'][index]=pose.encode(out[role]['bones'],[True,True])
            root=np.asarray(out[role]['root_blocks'][index])
            for side in ('l','r'):
                out[role]['hand_'+side+'_blocks'][index]=world(pose,root,'hand_'+side).tolist();out[role]['foot_'+side+'_blocks'][index]=sole_point(pose,root,side).tolist()
            if role=='eva':
                for channel,(bone,point) in baseline.items():out[role][channel][index]=world(pose,root,bone,point).tolist()
            else:
                for channel,bone,point in [('eye_blocks','head',angel.eye),('core_blocks','torso_upper',angel.core),('waist_blocks','torso_lower',angel.waist)]:out[role][channel][index]=world(pose,root,bone,point).tolist()
    # Keep the controlled wrist location and the complete punch performance;
    # turn only the actual long left claws out of the near head/chest space.
    # The palm support has its original real orientation back before 13 s.
    for index in range(342,759):
        t=index/60;weight=ease((t-5.7)/.8)*(1-ease((t-12.05)/.6))
        pose=angel.decode(out['angel']['frames'][index],out['angel']['bones']);root=np.asarray(out['angel']['root_blocks'][index])
        orientation=R.from_matrix(pose.matrix('hand_l')[:3,:3]);clear=R.from_euler('y',-90,degrees=True)*R.from_euler('x',45,degrees=True)
        # The delivered skin blends the elbow spike with a small hand weight.
        # Lift that real arm arc by 0.2 degrees, clearing its floor and the
        # near knee while leaving the entity root and limb lengths unchanged.
        lift=.2*weight+.3*np.sin(np.pi*np.clip((t-5.7)/.8,0,1))**2
        arm=R.from_matrix(pose.matrix('arm_l')[:3,:3]);pose.setq('arm_l',R.from_matrix(pose.parent('arm_l')[:3,:3]).inv()*R.from_euler('x',lift,degrees=True)*arm)
        pose.setq('hand_l',R.from_matrix(pose.parent('hand_l')[:3,:3]).inv()*rotation_mix(orientation,clear,weight))
        out['angel']['frames'][index]=pose.encode(out['angel']['bones'],out['angel']['frames'][index]['foot_contact'])
        out['angel']['hand_l_blocks'][index]=world(pose,root,'hand_l').tolist()
    for index in range(426,798):
        t=index/60;weight=ease((t-7.1)/.5)*(1-ease((t-12)/1.3))
        pose=hero.decode(out['eva']['frames'][index],out['eva']['bones']);root=np.asarray(out['eva']['root_blocks'][index])
        pose.setq('neck',pose.q['neck']*R.from_euler('x',10*weight,degrees=True))
        pose.setq('head',pose.q['head']*R.from_euler('xy',[15*weight,20*weight],degrees=True))
        out['eva']['frames'][index]=pose.encode(out['eva']['bones'],out['eva']['frames'][index]['foot_contact'])
        for channel,(bone,point) in baseline.items():out['eva'][channel][index]=world(pose,root,bone,point).tolist()
    out['r52_finisher_rebuild']['body_revision']='Native3 rejected long suspended knee: two actual retreat feet/reaction, two rush steps, deceleration, waist-level wrap outside bracing shoulders; controlled left claws clear the actual near head/chest; restored pre-FBX human run carry'
    out['r52_finisher_rebuild']['body_changed_frames']=[342,1176]
    out['r52_finisher_rebuild']['native_verified']=False
    target=args.out/'first_battle_r52_body2.json';target.write_text(json.dumps(out,separators=(',',':')),'utf8')
    report={'source_sha256':hashlib.sha256(args.source.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'body_source_sha256':hashlib.sha256(args.body.read_bytes()).hexdigest(),'changed_frames':[342,1176],'eva_double_support_window':[13.3,16.1],'angel_double_support_window':[14.65,15.75],'angel_rush_root_knots':[[15.75,0,0],[16.1,-4,-20],[16.65,-15.5,-20],[17.15,-19,0]],'angel_two_steps':[['r',15.85,16.35],['l',16.37,16.92]],'both_planted_before_close':16.92,'close_interval':[17.15,17.9],'samples':rows,'native_verified':False,'user_accepted':False}
    (args.out/'BODY2_REVISION_REPORT.json').write_text(json.dumps(report,indent=2),'utf8')
    print('New body candidate',target,flush=True)


if __name__=='__main__':main()
