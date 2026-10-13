"""Constrain the approved-scope R52 blocking into one 60Hz candidate clock."""
from pathlib import Path
import argparse,copy,json,hashlib,subprocess
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
from r52_motion_core import selected,read,UNIT,MIRROR,ease,mix,hand_controls,skin
from author_finisher_r52 import keyposes,sample,world,vec,foot_solve,hand_world,palm_support,alien_palm_orientation,angel_patch,Preview
from calibrated_arm_r49 import axial_twist

def yaw(p):
    # A supine forward axis is vertical; atan2 on its tiny X/Z projection
    # alternates 0/180 with rounding. The lateral axis remains horizontal.
    right=p.q['root'].apply([1,0,0]);return float(np.degrees(np.arctan2(-right[2],right[0])))

def floor_body(p):
    rig=p.rig;dominant=rig.ids[np.arange(len(rig.ids)),np.argmax(rig.weights,axis=1)]
    mask=~np.isin(dominant,[rig.names.index(n) for n in ['arm_l','forearm_l','hand_l','arm_r','forearm_r','hand_r']])
    matrices=np.asarray([p.matrix(n) for n in rig.names]);v=skin(rig.vertices[mask],matrices,rig.ids[mask],rig.weights[mask])
    minimum=v[:,1].min()
    if minimum<0:p.setp('root',p.p['root']+[0,-minimum,0])

def feet_at(key,role,root_key,side):return world(key[role],key[root_key],'foot_'+side)

def sole_point(p,root,side):
    rig=p.rig;mir=np.ones(3) if rig.angel else MIRROR
    if rig.angel:
        mask=(np.where(rig.ids==rig.names.index('foot_'+side),rig.weights,0).sum(1)>.20)&(rig.vertices[:,1]<17)
        matrices=np.asarray([p.matrix(n) for n in rig.names]);v=skin(rig.vertices[mask],matrices,rig.ids[mask],rig.weights[mask])*UNIT+root
        rest=rig.vertices[mask]
    else:
        v=p.surface(['foot_'+side])*mir*UNIT+root;rest=rig.parts['foot_'+side]
    # Keep the same material sole vertices for X/Z. Selecting a new minimum
    # subset every frame made the derived footprint jump from heel to toe.
    support=rest[:,1]<rest[:,1].min()+.25;point=v[support].mean(0);point[1]=v[:,1].min();return point

def walking_goals(keys,role,root_key,t,start,end,first,last,period=.78):
    rig=first[role].rig;mir=np.ones(3) if rig.angel else MIRROR
    first_yaw=yaw(first[role]);last_yaw=yaw(last[role])
    local_a={s:R.from_euler('y',first_yaw,degrees=True).inv().apply((feet_at(first,role,root_key,s)-first[root_key])*mir/UNIT) for s in ('l','r')}
    local_b={s:R.from_euler('y',last_yaw,degrees=True).inv().apply((feet_at(last,role,root_key,s)-last[root_key])*mir/UNIT) for s in ('l','r')}
    goals={};contacts=[];heights={}
    for s,offset in [('l',0),('r',.5)]:
        final_anchor=start+(np.floor((end-start)/period+offset+1e-8)-offset)*period
        if t>=final_anchor-1e-8 and final_anchor<end-1e-8:
            goals[s]=feet_at(last,role,root_key,s);contacts.append(True);heights[s]=0;continue
        if t>=end:
            goals[s]=feet_at(last,role,root_key,s);contacts.append(True);heights[s]=0;continue
        cyc=(t-start)/period+offset;cycle=np.floor(cyc);phase=cyc-cycle
        before=float(np.clip(start+(cycle-offset)*period,start,end));after=float(np.clip(start+(cycle+1-offset)*period,start,end))
        def anchor(at):
            if at>=final_anchor-1e-8:return feet_at(last,role,root_key,s)
            u=ease((at-start)/(end-start))
            offset_local=local_a[s]*(1-u)+local_b[s]*u
            heading=first_yaw+((last_yaw-first_yaw+180)%360-180)*u
            return first[root_key]*(1-u)+last[root_key]*u+R.from_euler('y',heading,degrees=True).apply(offset_local)*mir*UNIT
        a,b=anchor(before),anchor(after)
        if phase<.50:goal=a.copy();contact=True;lift=0
        else:
            u=ease((phase-.5)/.5);goal=a*(1-u)+b*u;peak=3.8 if start>=15.4 else 3.6 if role=='eva' and start>=12 else 2.4;lift=peak*np.sin(np.pi*(phase-.5)*2);goal[1]+=lift;contact=False
        goals[s]=goal;contacts.append(contact);heights[s]=lift
    return goals,contacts,heights

def contact_goals(item,keys,t,role):
    root_key='ar' if role=='angel' else 'hr';p=item[role];root=item[root_key]
    schedules=[(0,3.2,keys[0],keys[1],.80),(3.2,5.5,keys[1],keys[2],.46),(5.5,7.1,keys[2],keys[3],.64),(12.6,15.4,keys[4],keys[7],.95),(15.4,17.20,keys[7],keys[8],.90)] if role=='eva' else [(14,15.4,keys[6],keys[7],.70),(15.4,18.10,keys[7],keys[8],.90)]
    for start,end,first,last,period in schedules:
        if start<=t<end:return walking_goals(keys,role,root_key,t,start,end,first,last,period)
    if role=='eva':
        k=keys[4] if 7.1<=t<12.6 else keys[8] if t>=15.4 else keys[0]
        return {s:feet_at(k,role,root_key,s) for s in ('l','r')},[True,True],{'l':0,'r':0}
    if 5.5<=t<12:return {s:feet_at(keys[2],role,root_key,s) for s in ('l','r')},[True,True],{'l':0,'r':0}
    if 12<=t<14:
        first,last=(keys[2],keys[5]) if t<13 else (keys[5],keys[6]);start,end=(12,13) if t<13 else (13,14)
        if t>=13:
            goals={};contacts=[];heights={}
            for s,step_start in [('l',13.6),('r',13.2)]:
                u=float(np.clip((t-step_start)/.4,0,1));weight=ease(u);lift=2.4*np.sin(np.pi*u)
                goals[s]=feet_at(first,role,root_key,s)*(1-weight)+feet_at(last,role,root_key,s)*weight+np.asarray([0,lift,0])
                contacts.append(u<=0 or u>=1);heights[s]=lift
            return goals,contacts,heights
        u=ease((t-13.2)/.8) if t>=13 else ease((t-start)/(end-start))
        return {s:feet_at(first,role,root_key,s)*(1-u)+feet_at(last,role,root_key,s)*u for s in ('l','r')},[True,True],{'l':0,'r':0}
    if t>=18.10:return {s:feet_at(keys[8],role,root_key,s) for s in ('l','r')},[True,True],{'l':0,'r':0}
    return {s:world(p,root,'foot_'+s) for s in ('l','r')},[t<=3.2,t<=3.2],{'l':0,'r':0}

def constrained(keys,t,previous=None):
    item=sample(keys,t);item['t']=t
    for role,root_key in [('angel','ar'),('eva','hr')]:
        p=item[role];rig=p.rig;root=item[root_key];mir=np.ones(3) if rig.angel else MIRROR
        before_hands={s:world(p,root,'hand_'+s) for s in ('l','r')}
        before_orientations={s:R.from_matrix(p.matrix('hand_'+s)[:3,:3]) for s in ('l','r')}
        before_controls={n:p.q[n] for n in p.q if n.startswith('r45_hand_')}
        goals,contacts,heights=contact_goals(item,keys,t,role)
        if 15.4<=t<18.10 and contacts[0]!=contacts[1]:
            # Move the pelvis toward the planted side while the other foot
            # swings. The foot anchors remain fixed in world space.
            support=-1 if contacts[0] else 1;shift=1.3/UNIT*max(heights.values())/3.8
            p.setp('root',p.p['root']+p.q['root'].apply([support*shift,0,0]))
        if role=='angel' and 3.2<t<5.5:
            floor_body(p)
        else:
            local={s:(goals[s]-root)*mir/UNIT for s in ('l','r')}
            foot_solve(rig,p,local,yaw(p),sole_heights={s:heights[s]/UNIT for s in ('l','r')})
            if role=='angel' and 12<=t<15.4:
                floor_body(p)
                # Preserve planted soles after correcting the solid body.
                foot_solve(rig,p,local,yaw(p),sole_heights={s:heights[s]/UNIT for s in ('l','r')})
        if role=='angel' and 12<=t<=14 and previous is not None:
            p.r52_elbow_poles={};p.r52_elbow_normals={};p.r52_elbow_directions={}
            for s in ('l','r'):
                bone='arm_'+s;old=previous[role];origin=old.point(bone);direction=old.point('hand_'+s)-origin;direction/=np.linalg.norm(direction)
                elbow=old.point(bone,rig.elbows[s])-origin;bend=elbow-direction*(elbow@direction)
                if np.linalg.norm(bend)>1e-5:
                    bend/=np.linalg.norm(bend);p.r52_elbow_poles[s]=bend;p.r52_elbow_normals[s]=np.cross(direction,bend);p.r52_elbow_directions[s]=direction
        if role=='eva' and 7.9<=t<12:
            # The contact pose is physically reachable. Preserve the authored
            # whole-arm arc between chamber/contact; solving an endpoint on
            # every frame can cross elbow-plane singularities at full reach.
            for s in ('l','r'):
                lower='forearm_'+s;delta=rig.elbows[s]-rig.P[lower]
                p.setp(lower,delta-p.q[lower].apply(delta))
            hand_controls(p,'support','fist')
        else:
            if role=='eva':
                for n,q in before_controls.items():p.setq(n,q)
                for s in ('l','r'):
                    lower='forearm_'+s;delta=rig.elbows[s]-rig.P[lower]
                    p.setp(lower,delta-p.q[lower].apply(delta))
            for s in ('l','r'):p.setq('hand_'+s,R.from_matrix(p.parent('hand_'+s)[:3,:3]).inv()*before_orientations[s])
        if role=='angel' and 13<=t<=14:
            # A real rear palm is held while the seated body is stationary.
            # After 13.2s it is free: transport the actual complete arm
            # orientations continuously, with no new endpoint IK target.
            first,last=keys[5]['angel'],keys[6]['angel'];weight=ease((t-13.2)/.8)
            extra=R.from_euler('x',-28*np.sin(np.pi*weight),degrees=True)
            for s in ('l','r'):
                for prefix in ('arm_','forearm_','hand_'):
                    bone=prefix+s;start=R.from_matrix(first.matrix(bone)[:3,:3]);finish=R.from_matrix(last.matrix(bone)[:3,:3])
                    orientation=(extra if s=='l' else R.identity())*Slerp([0,1],R.concatenate([start,finish]))(weight)
                    p.setq(bone,R.from_matrix(p.parent(bone)[:3,:3]).inv()*orientation)
                lower='forearm_'+s;delta=rig.elbows[s]-rig.P[lower]
                p.setp(lower,delta-p.q[lower].apply(delta))
        if role=='angel' and 12<=t<13:
            # Free withdrawal has no planted hand target. Author a continuous
            # whole-arm arc above the floor, ending at the real palm support.
            # This avoids an endpoint solver changing branches to clear spikes.
            first,last=keys[2]['angel'],keys[5]['angel'];weight=ease(t-12)
            bump=-25*np.sin(np.pi*float(np.clip((t-12.5)/.5,0,1)))
            for s in ('l','r'):
                extra=R.from_euler('x',bump if s=='l' else 40*np.sin(np.pi*weight),degrees=True)
                for prefix in ('arm_','forearm_','hand_'):
                    bone=prefix+s;start=R.from_matrix(first.matrix(bone)[:3,:3]);finish=R.from_matrix(last.matrix(bone)[:3,:3])
                    orientation=extra*Slerp([0,1],R.concatenate([start,finish]))(weight)
                    p.setq(bone,R.from_matrix(p.parent(bone)[:3,:3]).inv()*orientation)
        if 15.4<=t<=18.25:
            # The pair first places feet and shifts weight toward each other.
            # Forearms close only after that approach, then finish behind the
            # shoulder/rib sides. No independent wrist endpoint solve.
            first,last=keys[7][role],keys[8][role];weight=ease((t-16.8)/1.45)
            for s in ('l','r'):
                for prefix in ('arm_','forearm_','hand_'):
                    bone=prefix+s;start=R.from_matrix(first.matrix(bone)[:3,:3]);finish=R.from_matrix(last.matrix(bone)[:3,:3]);w=ease((t-16.0)/1.4) if role=='angel' and prefix=='hand_' else weight;orientation=Slerp([0,1],R.concatenate([start,finish]))(w)
                    p.setq(bone,R.from_matrix(p.parent(bone)[:3,:3]).inv()*orientation)
                lower='forearm_'+s;delta=rig.elbows[s]-rig.P[lower]
                p.setp(lower,delta-p.q[lower].apply(delta))
        item[role+'_contacts']=contacts
    return item

def anchors(source,hero):
    role=source['eva'];p=hero.decode(role['frames'][0],role['bones']);root=vec(role['root_blocks'][0]);result={}
    binding={'eye_blocks':'head','look_blocks':'head','socket_blocks':'torso_upper','socket_outward_blocks':'torso_upper','socket_up_blocks':'torso_upper','rib_tip_blocks':'hand_r','rib_side_blocks':'hand_r'}
    for channel,bone in binding.items():
        if channel in role:
            model=(vec(role[channel][0])-root)*MIRROR/UNIT;result[channel]=(bone,(np.linalg.inv(p.matrix(bone))@np.r_[model,1])[:3])
    return result

def main():
    ap=argparse.ArgumentParser()
    for key in ('body','assets','angel-rig','source','out'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--preview',action='store_true');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    body,hero,alien=selected(a.body,a.assets,a.angel_rig);source=read(a.source);out=copy.deepcopy(source);keys=keyposes(hero,alien);baseline=anchors(source,hero)
    names=list(dict.fromkeys(source['eva']['bones']+[b['name'] for b in hero.hand_contract['new_bones']]))
    out['eva']['bones']=names;count=1381
    for role in ('eva','angel'):
        for k,v in list(out[role].items()):
            if isinstance(v,list) and len(v)==count:out[role][k]=[]
    out['angel'].setdefault('foot_l_blocks',[]);out['angel'].setdefault('foot_r_blocks',[])
    for k in ('position','target','fov'):out['camera'][k]=[]
    out['camera']['cuts']=[];stats=[];motions=[];preview=Preview(a.assets,(640,480));previous={};max_speed={}
    proc=None
    if a.preview:
        proc=subprocess.Popen(['ffmpeg','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','640x480','-r','12','-i','-','-an','-c:v','libx264','-preset','fast','-crf','26','-pix_fmt','yuv420p',str(a.out/'continuous_constrained_low.mp4')],stdin=subprocess.PIPE)
    previous_item=None
    for i in range(count):
        t=i/60;item=constrained(keys,t,previous_item);previous_item=item
        for role,root_key,rig,bones in [('eva','hr',hero,names),('angel','ar',alien,out['angel']['bones'])]:
            p=item[role];root=item[root_key];frame=p.encode(bones,item[role+'_contacts'])
            if role in previous:
                for j,q in enumerate(frame['rotation_wxyz']):
                    if np.dot(q,previous[role][j])<0:frame['rotation_wxyz'][j]=[-v for v in q]
                qs=np.asarray(frame['rotation_wxyz']);old=np.asarray(previous[role]);delta=2*np.degrees(np.arccos(np.clip(np.abs((qs*old).sum(1)),0,1)))*60
                max_speed[role]=max(max_speed.get(role,0),float(delta.max()))
                if delta.max()>900:motions.append({'frame':i,'actor':role,'bone':bones[int(delta.argmax())],'speed_deg_s':float(delta.max())})
            previous[role]=copy.deepcopy(frame['rotation_wxyz']);out[role]['frames'].append(frame);out[role]['root_blocks'].append(root.tolist())
            for s in ('l','r'):
                out[role]['hand_'+s+'_blocks'].append(world(p,root,'hand_'+s).tolist())
                if 'foot_'+s+'_blocks' in out[role]:out[role]['foot_'+s+'_blocks'].append(sole_point(p,root,s).tolist())
            if role=='eva':
                for channel,(bone,point) in baseline.items():out[role][channel].append(world(p,root,bone,point).tolist())
            else:
                for channel,bone,point in [('eye_blocks','head',rig.eye),('core_blocks','torso_upper',rig.core),('waist_blocks','torso_lower',rig.waist)]:out[role][channel].append(world(p,root,bone,point).tolist())
        out['camera']['position'].append(preview.eye.tolist());out['camera']['target'].append(preview.target.tolist());out['camera']['fov'].append(41)
        if i%12==0:
            report={'frame':i,'second':t,'eva_root':item['hr'].tolist(),'angel_root':item['ar'].tolist()}
            for role,root_key in [('eva','hr'),('angel','ar')]:
                p=item[role];report[role+'_minimum_y_blocks']=float(p.surface()[:,1].min()*UNIT+item[root_key][1]);report[role+'_upper_arm_axial_degrees']={s:float(np.degrees(abs(axial_twist(p.q['arm_'+s],p.rig.elbows[s]-p.rig.P['arm_'+s])))) for s in ('l','r')}
            stats.append(report)
        if proc is not None and i%5==0:proc.stdin.write(preview.render(item,item['name']).tobytes())
        if i%120==0:print('baked frame',i,flush=True)
    if proc is not None:proc.stdin.close();proc.wait()
    for key in ['r24_camera','r42_articulation','r48_direction','r49_paired_contact','r49_grounded_pair','r51_floor_contact_correction','r40_envelopment','r49_skeletal_enclosure']:out.pop(key,None)
    cues={'19':16,'122':141,'410':259,'428':269,'28':28,'53':53,'75':60,'99':64,'160':68,'184':149,'307':208,'255':167,'283':188,'321':229,'354':354}
    before_cues=source.get('event_tick_remap_r42',{});out.update(fps=60,duration_ticks=460,landing_tick=110,surface_deformation_r14='',event_tick_remap_r42=cues,reference_seconds_r42=[i/60 for i in range(count)],reference='R52 original game choreography following TV episode 02 order: grounded fall, outside support/core strikes, palm/heel rise, planted closing steps, embrace, one death event, natural arm release')
    out['r52_finisher_rebuild']={'source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'death_tick':372,'return_tick':432,'full_skeletal_sequence':True,'mesh_or_bone_scaling':False,'withdrawn_fbx_used':False,'native_verified':False,'user_accepted':False,'event_cue_changes':{k:{'before':before_cues.get(k,int(k)),'after':v} for k,v in cues.items() if before_cues.get(k,int(k))!=v},'landing_cue_before':source.get('landing_tick'),'support_selection':'Angel posterior torso/shoulder/back/hip skin; actual 50/50 shin-foot heel vertices; palm y111..134,z-79..-55, excluding wrist spikes and curled claw tips'}
    path=a.out/'first_battle_r52_candidate.json';path.write_text(json.dumps(out,separators=(',',':')),encoding='utf-8')
    (a.out/'BAKE_REPORT.json').write_text(json.dumps({'candidate':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'max_bone_speed_deg_s':max_speed,'speed_outliers_over_900':motions,'surface_samples':stats,'native_verified':False,'user_accepted':False},indent=2),encoding='utf-8')
    print('Candidate complete',path,flush=True)
if __name__=='__main__':main()
