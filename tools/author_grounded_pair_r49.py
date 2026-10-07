"""Original paired blocking with ground support and an actual rise/charge.

No inherited shoulder pose, root snap, cloth cache or mid-sequence explosion.
TV episode 02 supplies the sequence; the side attack and short closing steps
are game choreography, not claimed as an exact tracing of the film.
"""
from pathlib import Path
import argparse,copy,json
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
import author_first_battle_r10 as b
from anatomical_hinge_r35 import solve as hinge
from calibrated_arm_r49 import solve
from author_combat_bundle_r44 import maintain_joint_centres
from bake_envelopment_candidate_r40 import write_hero
from hand_surface_r49 import natural_carry


def ease(t):
    t=float(np.clip(t,0,1));return t*t*t*(10+t*(-15+6*t))


def curve(t,keys):
    for (ta,a),(tb,bb)in zip(keys,keys[1:]):
        if t<=tb:return np.asarray(a,float)*(1-ease((t-ta)/(tb-ta)))+np.asarray(bb,float)*ease((t-ta)/(tb-ta))
    return np.asarray(keys[-1][1],float)


def mix(a,bb,t,names):
    out=copy.deepcopy(a)
    for n in names:
        out.setq(n,Slerp([0,1],R.concatenate([a.q[n],bb.q[n]]))(t));out.setp(n,a.p[n]*(1-t)+bb.p[n]*t)
    return out


def support(actor,p,yaw=0,lift=None,world_goals=None):
    rotation=R.from_euler('y',yaw,degrees=True);goals={s:rotation.apply(actor.foot_base[s])for s in('l','r')}
    if world_goals is not None:goals=world_goals
    for s,v in(lift or{}).items():goals[s]+=rotation.apply(v)
    for _ in range(8):
        for s in('l','r'):
            reach=np.linalg.norm(actor.knees[s]-actor.P['leg_'+s])+np.linalg.norm(actor.P['foot_'+s]-actor.knees[s])
            delta=p.point('leg_'+s)-goals[s];length=np.linalg.norm(delta)
            if length>reach*.991:p.setp('root',p.p['root']-delta*(1-reach*.991/length))
    for s in('l','r'):
        hinge(p,actor.P,'leg_'+s,'shin_'+s,'foot_'+s,actor.knees[s],goals[s],rotation.apply([0,0,-1]),[-1,0,0],rotation)


def hero_root(t):
    return curve(t,[(0,[0,0,0]),(3,[0,0,0]),(5.1,[0,0,14]),(8.5,[0,0,14]),(11.05,[-21,0,103]),(15.2,[-21,0,103]),(17,[-36,0,103]),(23,[-36,0,103])])


def hero_yaw(t):
    return 90*ease((t-8.5)/2.55)


def moving_feet(actor,root,t,start,end,yaw_at,root_at,mirror):
    # Foot contacts are points in the shared WORLD track, not body-local
    # constants travelling with the actor. A planted foot holds still while
    # the other advances; turning follows its next contact orientation.
    period=.6;goals={}
    for s,offset in(('l',0),('r',.5)):
        cycles=(t-start)/period+offset;cycle=np.floor(cycles);phase=cycles-cycle
        raw_before=start+(cycle-offset)*period
        before=np.clip(raw_before,start,end);after=np.clip(raw_before+period,start,end)
        def point(at):return root_at(at)+R.from_euler('y',yaw_at(at),degrees=True).apply(actor.foot_base[s])*mirror*b.UNIT
        first,last=point(before),point(after)
        weight=ease((phase-.5)/.5);world=first*(1-weight)+last*weight
        if phase>.5:world[1]+=3*np.sin(np.pi*(phase-.5)*2)
        goals[s]=(world-root)*mirror/b.UNIT
    return goals


def arm(actor,p,side,target,yaw=0):
    sign=-1 if side=='l'else 1
    pole=R.from_euler('y',yaw,degrees=True).apply([sign*.35,-1,.2])
    result=solve(p,actor.P,'arm_'+side,'forearm_'+side,'hand_'+side,actor.elbows[side],target,pole,[1,0,0])
    if not result['axial_guard_passed']:raise ValueError(('Reblock arm target',actor.key,side,result))
    p.setq('hand_'+side,R.identity())
    result['requested_end_error']=float(np.linalg.norm(p.point('hand_'+side)-target))
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--assets',type=Path,required=True)
    ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    original=json.loads(a.source.read_text(encoding='utf-8'));out=copy.deepcopy(original)
    common.BODY=json.loads((a.runtime/'eva_body_r44.json').read_text(encoding='utf-8'));common.NAMES=common.BODY['motion']['bones']
    hero=Actor(1);alien=Actor('sachiel');rig=b.ANGEL;names=original['eva']['bones']
    contract=json.loads((a.assets/'hand_rigs/unit01/hand_rig_contract.json').read_text(encoding='utf-8'))
    idle_doc=common.BODY['stance_clips_by_rig']['1'];idle=hero.rig.decode(idle_doc['clips']['idle']['frames'][0],idle_doc['bones'])
    flat=alien.pose(lean=0,drop=0)
    # The Angel bind pose is not an arms-at-side resting pose. Solve its
    # actual shoulder/elbow chain before rotating the complete body supine.
    for s,sign in(('l',-1),('r',1)):
        arm(alien,flat,s,flat.point('arm_'+s)+np.array([sign*50,-35,-12]))
    flat.setq('root',R.from_euler('x',90,degrees=True))
    flat.ground();flat_root=np.array([0.,0,55.])
    stand_at=flat_root+(flat.point('foot_l')+flat.point('foot_r'))*.5*b.UNIT;stand_at[1]=0
    # Build the choreography at 60Hz. Curves and skeleton share this clock;
    # the game's 20Hz damage/mission simulation remains unchanged.
    fps=60;count=1381
    for role in('eva','angel'):
        for k,v in out[role].items():
            if isinstance(v,list)and len(v)==691:out[role][k]=[None]*count
    for k,v in out['camera'].items():
        if isinstance(v,list)and len(v)==691:out['camera'][k]=[None]*count
    out['camera']['cuts']=[];out['fps']=fps;out['reference_seconds_r42']=[i/fps for i in range(count)]
    stats=[];temp_out=copy.deepcopy(original);last_phase=-1
    for i in range(count):
        t=i/fps;old_index=min(690,round(t*30))
        hr=hero_root(t)
        ar=flat_root.copy();enemy=rig.pose()
        if t<8.5:
            enemy=alien.pose(lean=5,drop=5);support(alien,enemy)
            for s,sign in(('l',-1),('r',1)):
                goal=enemy.point('arm_'+s)+np.array([sign*6,-24,-32])
                if t>=5.1:goal=(np.array([sign*16,38,31])-ar)/b.UNIT
                arm(alien,enemy,s,goal)
        elif t<11.05:
            if 'fallen_from'not in locals():fallen_from=copy.deepcopy(last_enemy)
            enemy=mix(fallen_from,flat,ease((t-8.5)/2.55),rig.names)
            enemy.ground()
        elif t<15.2:enemy=copy.deepcopy(flat)
        elif t<16.6:
            u=ease((t-15.2)/1.4);yaw=90*u
            risen=alien.pose(lean=8,drop=4);risen.setq('root',R.from_euler('y',90,degrees=True));support(alien,risen,90)
            for s,sign in(('l',-1),('r',1)):arm(alien,risen,s,risen.point('arm_'+s)+R.from_euler('y',90,degrees=True).apply([sign*5,-33,-14]),90)
            # Fold the knees and bring the pelvis above the feet before
            # extending the hips; a rigid horizontal-to-vertical roll is not
            # a rise. This intermediate carries weight on the feet and hand.
            crouched=alien.pose(lean=30,drop=57);crouched.setq('root',R.from_euler('y',90,degrees=True));support(alien,crouched,90)
            for s,sign in(('l',-1),('r',1)):
                hand=crouched.point('arm_'+s)+R.from_euler('y',90,degrees=True).apply([sign*5,-45,-13])
                hand[1]=max(5,hand[1]);arm(alien,crouched,s,hand,90)
            enemy=mix(flat,crouched,ease((t-15.2)/.65),rig.names)if t<15.85 else mix(crouched,risen,ease((t-15.85)/.75),rig.names)
            enemy.ground()
            feet=(enemy.point('foot_l')+enemy.point('foot_r'))*.5*b.UNIT
            ar=stand_at-feet;ar[1]=0
        else:
            u=ease((t-16.6)/1.5);enemy=alien.pose(lean=8+8*u,drop=4+15*u);enemy.setq('root',R.from_euler('y',90,degrees=True))
            foot_lift={}
            if t<18.1:
                step=(t-16.6)/1.5*2;side='l'if int(step)%2==0 else'r';foot_lift[side]=[0,7*np.sin(np.pi*(step%1)),0]
            support(alien,enemy,90,foot_lift)
            ar=curve(t,[(16.6,stand_at),(18.1,[-10,0,103]),(23,[-10,0,103])])
            for s,sign in(('l',-1),('r',1)):
                shoulder=enemy.point('arm_'+s)
                reach=shoulder+R.from_euler('y',90,degrees=True).apply([sign*5,-20,-28])
                # Standing feet support the lunge; only the arms close around
                # the upper EVA body. No levitating actor attachment is used.
                target=(hr+np.array([0,39,sign*10])-ar)/b.UNIT
                target=reach*(1-u)+target*u
                arm(alien,enemy,s,target,90)
        if t<8.5:
            p=hero.pose(lean=-10,drop=7);support(hero,p)
            for s,sign in(('l',-1),('r',1)):
                goal=p.point('arm_'+s)+np.array([sign*3,-28,-24])
                if 3<t<5.1:goal=p.point('arm_'+s)+np.array([sign*2,-8,-45])
                if t>=5.1:goal=(np.array([sign*16,38,31])-hr)*b.HEROMIRROR/b.UNIT
                arm(hero,p,s,goal)
        elif t<11.05:
            # A low advancing step around the opponent's flank replaces the
            # rejected torso fold and airborne knees through its abdomen.
            u=ease((t-8.5)/2.55);p=hero.pose(lean=-14,drop=8);p.setq('root',R.from_euler('y',90*u,degrees=True));support(hero,p,90*u)
            for s,sign in(('l',-1),('r',1)):arm(hero,p,s,p.point('arm_'+s)+R.from_euler('y',90*u,degrees=True).apply([sign*3,-20,-28]),90*u)
        elif t<15.2:
            strike=(t-11.05)/.72;phase=strike%1;hit=np.sin(np.pi*phase)**2
            p=hero.pose(lean=-42-4*hit,drop=50);p.setq('root',R.from_euler('y',90,degrees=True));support(hero,p,90)
            core=(ar+enemy.point('torso_upper',rig.core)*b.UNIT-hr)*b.HEROMIRROR/b.UNIT
            front=R.from_euler('y',90,degrees=True)
            for s in('l','r'):
                chamber=p.point('arm_'+s)+front.apply([(-5 if s=='l'else 5),-16,-26])
                goal=core+np.array([0,10,(-17 if s=='l'else 0)])
                if s=='r':goal=chamber*(1-hit)+goal*hit
                contact=arm(hero,p,s,goal,90)
                if s=='r'and hit>.98 and contact['requested_end_error']>5:
                    raise ValueError(('Core contact exceeds actual arm reach',t,contact))
        else:
            u=ease((t-15.2)/1.4);p=hero.pose(lean=-42*(1-u)+8*u,drop=50*(1-u)+10*u);p.setq('root',R.from_euler('y',90,degrees=True));support(hero,p,90)
            for s,sign in(('l',-1),('r',1)):arm(hero,p,s,p.point('arm_'+s)+R.from_euler('y',90,degrees=True).apply([sign*2,-22,-28]),90)
        for start,end in((3,5.1),(8.5,11.05),(15.2,17)):
            if start<=t<end:
                goals=moving_feet(hero,hr,t,start,end,hero_yaw,hero_root,b.HEROMIRROR)
                support(hero,p,hero_yaw(t),world_goals=goals)
        phase=sum(t>=v for v in(3,5.1,8.5,11.05,15.2,16.6,18.6))
        if phase!=last_phase:
            phase_at=t;phase_hero=copy.deepcopy(last_hero)if i else copy.deepcopy(p)
            phase_enemy=copy.deepcopy(last_enemy)if i else copy.deepcopy(enemy);last_phase=phase
        transition=ease((t-phase_at)/.35)
        p=mix(phase_hero,p,transition,names);enemy=mix(phase_enemy,enemy,transition,rig.names)
        if t>18.6:p=mix(p,idle,ease((t-18.6)/3),names)
        maintain_joint_centres(hero,p)
        if t>21.6:natural_carry(p,contract,hero.elbows,hero.P)
        # Recompute sockets/eyes from the actual authored body. Original
        # marker bind locations are kept, never the rejected world positions.
        write_hero(original,temp_out,old_index,p)
        for k in out['eva']:
            if k.endswith('_blocks'):
                out['eva'][k][i]=(np.asarray(temp_out['eva'][k][old_index])-np.asarray(original['eva']['root_blocks'][old_index])+hr).tolist()
        out['eva']['root_blocks'][i]=hr.tolist();out['eva']['frames'][i]=hero.rig.encode(p,bone_names=names)
        out['angel']['frames'][i]=enemy.encode();out['angel']['root_blocks'][i]=ar.tolist()
        for channel,bone,point in [('core','torso_upper',rig.core),('eye','head',rig.eye),('waist','torso_lower',rig.waist),('hand_l','hand_l',rig.P['hand_l']),('hand_r','hand_r',rig.P['hand_r']),('foot_l','foot_l',rig.P['foot_l']),('foot_r','foot_r',rig.P['foot_r'])]:
            if channel+'_blocks'in out['angel']:out['angel'][channel+'_blocks'][i]=(ar+enemy.point(bone,point)*b.UNIT).tolist()
        focus=(hr+p.point('torso_upper')*b.HEROMIRROR*b.UNIT+ar+enemy.point('torso_upper',rig.core)*b.UNIT)/2
        offset=curve(t,[(0,[-75,25,-85]),(8.5,[-85,25,-65]),(11.05,[-60,20,-65]),(15.2,[-60,20,-65]),(18.6,[-70,25,-75]),(23,[-70,25,-75])])
        out['camera']['target'][i]=focus.tolist();out['camera']['position'][i]=(focus+offset).tolist();out['camera']['fov'][i]=65
        last_enemy=copy.deepcopy(enemy);last_hero=copy.deepcopy(p)
        if i%60==0:stats.append(dict(second=t,eva_root=hr.tolist(),angel_root=ar.tolist(),angel_lowest_y=float(enemy.skin()[:,1].min()*b.UNIT+ar[1])))
    out['surface_deformation_r14']='';out.pop('r40_envelopment',None);out.pop('r49_skeletal_enclosure',None)
    out['landing_tick']=221;out['r49_grounded_pair']=dict(sample_fps=60,original_game_choreography=True,reference='TV episode 02',
        stages=['roar','AT pressure','wrist catch','fall and flank','supported core assault','grounded rise','two closing steps','standing embrace','one final explosion','shutdown'],
        native_verified=False,user_accepted=False)
    (a.out/'first_battle_r49_candidate.json').write_text(json.dumps(out,separators=(',',':')),encoding='utf-8')
    (a.out/'REPORT.json').write_text(json.dumps(dict(samples=stats,native=False,user_accepted=False),indent=2),encoding='utf-8')
    print('60Hz grounded pair candidate written; no publication')


if __name__=='__main__':main()
