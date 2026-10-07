"""Paired skeletal enclosure on the original rigs, without the rejected mantle morph.

Keep source topology and texture coordinates. Root motion, modest spine bend,
actual limb hinges and guarded arm planes replace the whole-body cloth cache.
This is editable original game choreography referenced to TV episode 02.
"""
from pathlib import Path
import argparse
import copy
import json
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from calibrated_arm_r49 import solve, axial_twist
import author_first_battle_r10 as b
from preview_first_battle_r12 import angel_pose
from author_combat_bundle_r44 import maintain_joint_centres
from bake_envelopment_candidate_r40 import write_hero


def ease(t):
    t=float(np.clip(t,0,1));return float(np.clip(t*t*t*(10+t*(-15+6*t)),0,1))


def mix_pose(first,second,t,names):
    result=copy.deepcopy(first)
    for n in names:
        result.setq(n,Slerp([0,1],R.concatenate([first.q[n],second.q[n]]))(t))
        result.setp(n,first.p[n]*(1-t)+second.p[n]*t)
    return result


def mix_hero(first,second,t,names,actor):
    result=mix_pose(first,second,t,names)
    for s,sign in (('l',-1),('r',1)):
        upper='arm_'+s
        axis=actor.elbows[s]-actor.P[upper];axis/=np.linalg.norm(axis)
        def split(q):
            angle=axial_twist(q,axis);twist=R.from_rotvec(axis*angle)
            return q*twist.inv(),angle
        a,ta=split(first.q[upper]);b_,tb=split(second.q[upper])
        # Swing and roll are different degrees of freedom. A raw quaternion
        # interpolation can cross a reversed shoulder between legal endpoints.
        # Blend them separately while the hand is not attached to a target.
        q=Slerp([0,1],R.concatenate([a,b_]))(t)*R.from_rotvec(axis*(ta*(1-t)+tb*t))
        result.setq(upper,q)
        lower='forearm_'+s;delta=actor.elbows[s]-actor.P[lower]
        result.setp(lower,delta-result.q[lower].apply(delta))
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True)
    ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    original=json.loads(args.source.read_text(encoding='utf-8'));result=copy.deepcopy(original)
    common.BODY=json.loads((args.runtime/'eva_body_r44.json').read_text(encoding='utf-8'));common.NAMES=common.BODY['motion']['bones']
    actor=Actor(1);names=original['eva']['bones'];rig=b.ANGEL
    idle_doc=common.BODY['stance_clips_by_rig']['1'];idle=actor.rig.decode(idle_doc['clips']['idle']['frames'][0],idle_doc['bones'])
    flat=rig.pose();flat.setq('root',R.from_euler('x',90,degrees=True))
    for s in ('l','r'):flat.setq('forearm_'+s,R.from_euler('x',-88,degrees=True))
    flat.ground()
    core_wanted=np.asarray(original['angel']['core_blocks'][440]);core_local=flat.point('torso_upper',rig.core)*b.UNIT
    flat_root=np.array([core_wanted[0]-core_local[0],0,core_wanted[2]-core_local[2]])
    stats=[]
    landing_from=None;fall_from=None;fall_root=None
    for i in range(691):
        hero_root=np.asarray(original['eva']['root_blocks'][i])
        if i>558:hero_root=np.asarray(original['eva']['root_blocks'][558])
        pose=actor.rig.decode(original['eva']['frames'][i],names)
        old_pose=copy.deepcopy(pose)
        if i==332:landing_from=copy.deepcopy(previous_hero)
        ar=np.asarray(original['angel']['root_blocks'][i]);angel=angel_pose(original['angel']['frames'][i],original['angel']['bones'])
        if i>=273:
            if i==273:fall_from=copy.deepcopy(previous_angel);fall_root=previous_angel_root.copy()
            u=ease((i-273)/59)
            angel=mix_pose(fall_from,flat,u,rig.names);ar=fall_root*(1-u)+flat_root*u
            if i>=332:angel=copy.deepcopy(flat);ar=flat_root.copy()
            if i>450:
                u=ease((i-450)/85)
                hug=rig.pose();hug.setq('torso_lower',R.from_euler('x',-12,degrees=True))
                hug.setq('torso_upper',R.from_euler('x',5,degrees=True));hug.setq('head',R.from_euler('x',-12,degrees=True))
                for s,sign in (('l',-1),('r',1)):
                    hug.setq('leg_'+s,R.from_euler('xz',[60,sign*20],degrees=True))
                    hug.setq('shin_'+s,R.from_euler('x',-110,degrees=True))
                    hug.setq('forearm_'+s,R.from_euler('x',-15,degrees=True))
                angel=mix_pose(flat,hug,u,rig.names)
                final_root=hero_root+np.array([0,4,14])
                ar=flat_root*(1-u)+final_root*u
                for s,sign in (('l',-1),('r',1)):
                    before=angel.point('hand_'+s)
                    target=(hero_root+np.array([sign*8,42,1])-ar)/b.UNIT
                    target=before*(1-u)+target*u
                    pole=angel.matrix('torso_upper')[:3,:3]@np.array([sign*.6,-.2,1])
                    r=solve(angel,rig.P,'arm_'+s,'forearm_'+s,'hand_'+s,rig.P['forearm_'+s],target,pole,[1,0,0])
                    if not r['axial_guard_passed']:raise ValueError(('Alien shoulder reverse',i,s,r))
        else:
            for s,sign in (('l',-1),('r',1)):
                target=angel.point('hand_'+s)
                pole=angel.matrix('torso_upper')[:3,:3]@np.array([sign*.5,0,1])
                r=solve(angel,rig.P,'arm_'+s,'forearm_'+s,'hand_'+s,rig.P['forearm_'+s],target,pole,[1,0,0])
                if not r['axial_guard_passed']:raise ValueError(('Early alien shoulder reverse',i,s,r))
        previous_angel=copy.deepcopy(angel);previous_angel_root=ar.copy()
        result['angel']['frames'][i]=angel.encode();result['angel']['root_blocks'][i]=ar.tolist()
        for curve,point,bone in [('core',rig.core,'torso_upper'),('eye',rig.eye,'head'),('waist',rig.waist,'torso_lower'),
                                  ('hand_l',rig.P['hand_l'],'hand_l'),('hand_r',rig.P['hand_r'],'hand_r'),
                                  ('foot_l',rig.P['foot_l'],'foot_l'),('foot_r',rig.P['foot_r'],'foot_r')]:
            if curve+'_blocks' in result['angel']:result['angel'][curve+'_blocks'][i]=(ar+angel.point(bone,point)*b.UNIT).tolist()
        if 332<=i<=450:
            cycle=((i-360)/42)%1;hit=ease(cycle/.5)if cycle<.5 else 1-ease((cycle-.5)/.5)
            authored=actor.pose(lean=-55-5*hit,drop=66,shift=0);authored.setp('root',authored.p['root']+[0,0,-52-3*hit])
            actor.solve_feet(authored,{s:actor.foot_base[s].copy()for s in ('l','r')})
            core=(np.asarray(result['angel']['core_blocks'][i])-hero_root)*b.HEROMIRROR/b.UNIT
            chamber=authored.point('arm_r')+[7,30,8]
            goals={'l':core+np.array([-25,17,7]),'r':chamber*(1-hit)+(core+[0,5,8])*hit}
            for s in ('l','r'):
                r=solve(authored,actor.P,'arm_'+s,'forearm_'+s,'hand_'+s,actor.elbows[s],goals[s],
                        authored.matrix('torso_upper')[:3,:3]@np.array([(-1 if s=='l'else 1)*.5,0,1]),[1,0,0])
                if not r['axial_guard_passed']:raise ValueError(('Core arm reverse',i,s,r))
            pose=mix_hero(landing_from,authored,ease((i-332)/24),names,actor)
        if i>450:
            brace=copy.deepcopy(idle)
            brace.setp('root',brace.p['root']+[0,-8,0])
            actor.solve_feet(brace,{s:actor.foot_base[s].copy()for s in ('l','r')})
            for s,sign in (('l',-1),('r',1)):
                goal=brace.point('arm_'+s)+np.array([sign*2,-24,-37])
                r=solve(brace,actor.P,'arm_'+s,'forearm_'+s,'hand_'+s,actor.elbows[s],goal,[sign*.1,0,1],[1,0,0])
                if not r['axial_guard_passed']:raise ValueError(('Brace arm reverse',i,s,r))
            pose=mix_hero(previous_hero,brace,ease((i-450)/40),names,actor)
            if i>558:pose=mix_hero(pose,idle,ease((i-558)/90),names,actor)
        for s in ('l','r'):
            shoulder=pose.point('arm_'+s);hand=pose.point('hand_'+s);elbow=pose.point('forearm_'+s,actor.elbows[s])
            orientation=R.from_matrix(pose.matrix('hand_'+s)[:3,:3])
            r=solve(pose,actor.P,'arm_'+s,'forearm_'+s,'hand_'+s,actor.elbows[s],hand,elbow-shoulder,[1,0,0],orientation)
            if not r['axial_guard_passed']:raise ValueError(('Inherited arm requires new blocking',i,s,r))
        if i>=332:
            landing=ease((i-332)/24)
            actor.solve_feet(pose,{s:landing_from.point('foot_'+s)*(1-landing)+actor.foot_base[s]*landing for s in ('l','r')})
        maintain_joint_centres(actor,pose)
        write_hero(original,result,i,pose)
        delta=hero_root-np.asarray(original['eva']['root_blocks'][i])
        for curve,points in result['eva'].items():
            if curve.endswith('_blocks'):points[i]=(np.asarray(points[i])+delta).tolist()
        result['eva']['frames'][i]=actor.rig.encode(pose,bone_names=names)
        previous_hero=copy.deepcopy(pose)
        if i in (210,440,450,489,505,535,558,690):
            stats.append(dict(frame=i,eva_twist={s:float(np.degrees(axial_twist(pose.q['arm_'+s],actor.elbows[s]-actor.P['arm_'+s])))for s in ('l','r')},
                              eva_head=(hero_root+pose.point('head')*b.HEROMIRROR*b.UNIT).tolist(),angel_root=ar.tolist(),
                              angel_core=result['angel']['core_blocks'][i],deformed_surface_cache=False))
    result['surface_deformation_r14']='';result.pop('r40_envelopment',None)
    result['r49_skeletal_enclosure']=dict(reference='TV episode 02: core assault, desperate bodily embrace, one final self-destruction',
            original_game_blocking=True,whole_body_mantle_morph_removed=True,
            shoulder_axial_limit_degrees=75,source_topology_and_UV_unchanged=True,native_verified=False,user_art_accepted=False)
    (args.out/'first_battle_r49_candidate.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
    (args.out/'REPORT.json').write_text(json.dumps(dict(samples=stats,native=False,art_accepted=False),indent=2),encoding='utf-8')
    print('Skeletal enclosure candidate written; no final runtime promotion')


if __name__=='__main__':main()
