"""Paired revision: complete hand ownership and a compact, fast TV-style leap.

The independently baked final Sachiel envelopment keeps its original time and
attachment frames. Both actors, camera and event cues are retimed together.
"""
from pathlib import Path
import copy,json,hashlib,math
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
from author_combat_r35 import Actor
from author_articulation_r42 import hands,flight_pose,palm_basis
import author_first_battle_r10 as b
from bake_envelopment_candidate_r40 import write_hero
from preview_first_battle_r12 import angel_pose
from rebuild_stance_hinges_r41 import reconstruct,reachable_root,swing,hand_frame

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r42/first_battle'
NEW=np.array([0,10.1,11.05,16.3,23.]);OLD=np.array([0,10.1,12.2,16.3,23.])


def pin_pose(actor,original,enemy,hero_root,enemy_root,old_time):
    p=copy.deepcopy(original);weight=1-b.smooth((old_time-15.95)/.35)
    if weight<=0:return p
    feet={s:original.point('foot_'+s).copy() for s in ('l','r')}
    foot_rotation={s:R.from_matrix(original.matrix('foot_'+s)[:3,:3]) for s in ('l','r')}
    wrists={s:R.from_matrix(original.matrix('hand_'+s)[:3,:3]) for s in ('l','r')}
    impact=sum(math.exp(-((old_time-at)/.13)**2) for at in (12.75,14.15,16.05))
    p.setq('torso_lower',p.q['torso_lower']*R.from_euler('x',-(16+5*impact)*weight,degrees=True))
    p.setq('torso_upper',p.q['torso_upper']*R.from_euler('x',-(34+4*impact)*weight,degrees=True))
    reachable_root(actor,p,feet)
    for s in ('l','r'):reconstruct(actor,p,s,feet[s],foot_rotation[s],original.q['leg_'+s])
    core=b.angel_world(enemy,enemy_root,'torso_upper',b.ANGEL.core)
    skin=enemy.skin()*b.UNIT+enemy_root
    core_mask=np.linalg.norm(b.ANGEL.vertices-b.ANGEL.core,axis=1)<13
    region=skin[core_mask]
    top=region[np.argmax(region[:,1])] if len(region) else core+np.array([0,2,0])
    contact=top+np.array([0,.12,0])
    desired=core+[-6,2,-2];ids=np.argsort(np.linalg.norm(skin-desired,axis=1))[:4]
    left=skin[ids].mean(0)+[0,.22,0]
    offset=b.curve([(12.2,[5,14,-5]),(12.75,[0,0,0]),(12.92,[0,.35,0]),
                    (13.55,[6,15,-5]),(14.15,[0,0,0]),(14.32,[0,.35,0]),
                    (15.05,[4,12,-4]),(15.35,[-1,1,-1]),(16.05,[0,0,0]),(16.3,[0,2,-2])],old_time)
    for side,goal in (('l',left),('r',contact+offset)):
        name='hand_'+side;old=b.hero_world(original,hero_root,name,actor.P['finger_middle_'+side])
        goal=old*(1-weight)+goal*weight
        along,palmar=palm_basis(actor,side)
        if side=='l':orientation=R.from_matrix(hand_frame([0,0,-1],[0,1,0])@hand_frame(along,-palmar).T)
        else:orientation=swing(wrists[side].apply(along),[0,-1,0])*wrists[side]
        orientation=b.qmix(wrists[side],orientation,weight)
        target=(goal-hero_root)*b.HEROMIRROR/b.UNIT-orientation.apply(actor.P['finger_middle_'+side]-actor.P[name])
        pole=original.point('arm_'+side,actor.elbows[side])-original.point('arm_'+side)
        actor.anatomical_ik(p,'arm_'+side,'forearm_'+side,name,actor.elbows[side],target,pole)
        p.setq(name,R.from_matrix(p.parent(name)[:3,:3]).inv()*orientation)
    head=R.from_matrix(p.matrix('head')[:3,:3]);target=(core-hero_root)*b.HEROMIRROR/b.UNIT-p.point('head')
    aimed=swing(head.apply([0,0,-1]),target)*head
    p.setq('head',R.from_matrix(p.parent('head')[:3,:3]).inv()*b.qmix(head,aimed,weight))
    return p


def sample_frames(role,at):
    old=role['frames'];frames=[]
    for f in at:
        i=int(f);j=min(i+1,len(old)-1);t=f-i
        a=old[i];c=old[j];qa=np.asarray(a['rotation_wxyz']);qb=np.asarray(c['rotation_wxyz']).copy()
        dot=(qa*qb).sum(1);qb[dot<0]*=-1;theta=np.arccos(np.clip(np.abs(dot),0,1));s=np.sin(theta)
        wa=np.divide(np.sin((1-t)*theta),s,out=np.full_like(s,1-t),where=s>1e-7)
        wb=np.divide(np.sin(t*theta),s,out=np.full_like(s,t),where=s>1e-7)
        q=qa*wa[:,None]+qb*wb[:,None];q/=np.linalg.norm(q,axis=1,keepdims=True)
        positions={n:(np.asarray(a.get('bone_position_xyz',{}).get(n,[0,0,0]))*(1-t)+np.asarray(c.get('bone_position_xyz',{}).get(n,[0,0,0]))*t).tolist()
                   for n in set(a.get('bone_position_xyz',{}))|set(c.get('bone_position_xyz',{}))}
        frames.append(dict(root_m=(np.asarray(a['root_m'])*(1-t)+np.asarray(c['root_m'])*t).tolist(),rotation_wxyz=q.tolist(),bone_position_xyz=positions))
    return frames


def main():
    OUT.mkdir(parents=True,exist_ok=True);source=ROOT/'run/projectseele-local-maps/first_battle_r24.json'
    baseline=OUT/'baseline_first_battle_r24.json'
    if not baseline.exists():baseline.write_bytes(source.read_bytes())
    original=json.loads(baseline.read_text('utf8'));data=copy.deepcopy(original);time=np.linspace(0,23,691)
    old_time=np.interp(time,NEW,OLD);at=old_time*30
    for role in ('eva','angel'):
        data[role]['frames']=sample_frames(original[role],at)
        for key,rows in original[role].items():
            if key.endswith('_blocks'):
                points=np.asarray(rows);data[role][key]=np.column_stack([np.interp(at,np.arange(691),points[:,k]) for k in range(3)]).tolist()
    for key in ('position','target'):
        points=np.asarray(original['camera'][key]);data['camera'][key]=np.column_stack([np.interp(at,np.arange(691),points[:,k]) for k in range(3)]).tolist()
    data['camera']['fov']=np.interp(at,np.arange(691),original['camera']['fov']).tolist()
    data['camera']['cuts']=sorted(set(round(np.interp(x/30,OLD,NEW)*30) for x in original['camera'].get('cuts',[])))
    actor=Actor(1);names=list(actor.rig.rig);hero=data['eva'];raw=copy.deepcopy(data)
    hero['bones']=names
    start=303;end=round(11.05*30)
    pa=b.eva.decode(raw['eva']['frames'][start],raw['eva']['bones']);pb=b.eva.decode(raw['eva']['frames'][end],raw['eva']['bones'])
    pb=pin_pose(actor,pb,angel_pose(raw['angel']['frames'][end],raw['angel']['bones']),np.array(hero['root_blocks'][end]),np.array(data['angel']['root_blocks'][end]),old_time[end])
    surface={n:(np.asarray(part['vertices']).reshape(-1,8)[:,:3]+part['pivot'])*[-1,1,1]
             for n,part in b.eva.mesh['parts'].items() if n in actor.P and n not in ('cannon','knife','lance','n2','entry_plug')}
    def hip(p,root):return .5*(b.hero_world(p,root,'leg_l')+b.hero_world(p,root,'leg_r'))
    ha=hip(pa,np.array(hero['root_blocks'][start]));hb=hip(pb,np.array(hero['root_blocks'][end]))
    for i,t in enumerate(time):
        p=b.eva.decode(raw['eva']['frames'][i],raw['eva']['bones'])
        if end<i<489:
            p=pin_pose(actor,p,angel_pose(raw['angel']['frames'][i],raw['angel']['bones']),np.array(hero['root_blocks'][i]),np.array(data['angel']['root_blocks'][i]),old_time[i])
        if start<=i<=end:
            u=(i-start)/(end-start);flight=flight_pose(actor,actor.rig.Pose(),u)
            # Compact hips and knees make one forward turnover, with shoulder
            # width readable and hands ready for the eventual chest contact.
            for side in ('l','r'):
                q=R.from_euler('x',-(18+112*np.sin(np.pi*u)**1.15),degrees=True)
                flight.setq('leg_'+side,R.from_euler('x',12+92*np.sin(np.pi*u)**1.15,degrees=True))
                flight.setq('shin_'+side,q);d=actor.knees[side]-actor.P['shin_'+side];flight.setp('shin_'+side,d-q.apply(d))
                flight.setq('arm_'+side,R.from_euler('xyz',[48+30*np.sin(np.pi*u),0,(-1 if side=='l' else 1)*15],degrees=True))
                flight.setq('forearm_'+side,R.from_euler('x',70,degrees=True))
            entry=b.smooth(u/.2);release=b.smooth((u-.70)/.30)
            for n in names:
                flight.setq(n,b.qmix(pa.q[n],flight.q[n],entry));flight.setp(n,pa.p[n]*(1-entry)+flight.p[n]*entry)
                flight.setq(n,b.qmix(flight.q[n],pb.q[n],release));flight.setp(n,flight.p[n]*(1-release)+pb.p[n]*release)
            # Rotation is authored across 29 samples, so quaternion interpolation
            # never shortcuts a 360-degree turn into a static airborne pose.
            root_base=b.qmix(pa.q['root'],pb.q['root'],u)
            flight.setq('root',R.from_euler('x',-360*u,degrees=True)*root_base)
            root=np.array(hero['root_blocks'][i]);goal=ha*(1-u)+hb*u;goal[1]+=4*22*u*(1-u)
            flight.setp('root',flight.p['root']+(goal-hip(flight,root))*b.HEROMIRROR/b.UNIT)
            minimum=min(float((v@flight.matrix(n)[1,:3]+flight.matrix(n)[1,3]).min()*b.UNIT+root[1]) for n,v in surface.items())
            if minimum<.015:flight.setp('root',flight.p['root']+[0,(.015-minimum)/b.UNIT,0])
            p=flight
        closure=.24 if t<5.1 else .68 if t<8.5 else .25 if t<11.05 else .92 if t<16.3 else .52 if t<18.6 else .08
        hands(actor,p,closure)
        if end<=i<489:
            hands(actor,p,.2,sides=('l',));hands(actor,p,.65 if old_time[i]>15.35 else 1,sides=('r',))
        # The old clip's sparse bone list omitted some thumb and adapter channels.
        # Recompute spatial sockets against the final complete pose.
        # write_hero decodes the source using its own list; the destination uses
        # the expanded list only for encoding, so retain the read-only source.
        write_hero(raw,data,i,p)
        data['eva']['frames'][i]=b.eva.encode(p,bone_names=names)
        if start<=i<=end:
            centre=hip(p,np.array(hero['root_blocks'][i]))
            data['camera']['target'][i]=(centre+[0,4,0]).tolist()
            data['camera']['position'][i]=(centre+[-66,17,-28]).tolist()
            data['camera']['fov'][i]=66
    from author_articulation_r42 import continuous_arms
    arm_source=copy.deepcopy(data)
    stable=continuous_arms(actor,dict(bones=names),dict(frames=arm_source['eva']['frames']))
    for i,p in enumerate(stable):write_hero(arm_source,data,i,p)
    # Retiming samples rotations and spatial curves independently. Restore the
    # socket's orthonormal frame after that interpolation, rather than relaxing
    # the runtime contract or skipping its legacy-to-current socket conversion.
    for i in range(691):
        origin=np.asarray(data['eva']['socket_blocks'][i]);out=np.asarray(data['eva']['socket_outward_blocks'][i])-origin
        out/=np.linalg.norm(out);up=np.asarray(data['eva']['socket_up_blocks'][i])-origin;up-=out*(up@out);up/=np.linalg.norm(up)
        data['eva']['socket_outward_blocks'][i]=(origin+2*out).tolist();data['eva']['socket_up_blocks'][i]=(origin+2*up).tolist()
    data['camera']['cuts']=sorted(set(data['camera']['cuts']+[start,end+1]))
    data['landing_tick']=round(11.05*20)
    data['event_tick_remap_r42']={str(old):round(np.interp(old/20,OLD,NEW)*20) for old in (19,122,410,428,28,53,75,99,107,160,184,307,255,283,321,354)}
    data['reference_seconds_r42']=old_time.tolist()
    data.pop('r18_scene_offsets',None)
    data['r42_articulation']={'source_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),'jump_seconds_before':2.1,'jump_seconds_after':.95,
        'reference':'TV episode 02 public excerpt 211172: compression, compact airborne turnover and immediate committed contact; no footage distributed',
        'complete_bone_channels':len(names),'retimed_shared_clock':True,'preserved_surface_interval_seconds':[16.3,18.6]}
    file=OUT/'first_battle_r42.json';file.write_text(json.dumps(data,separators=(',',':')),'utf8')
    print('Authored paired candidate',len(names),'bones',hashlib.sha256(file.read_bytes()).hexdigest())


if __name__=='__main__':main()
