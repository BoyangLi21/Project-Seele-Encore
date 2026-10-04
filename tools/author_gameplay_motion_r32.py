"""Author isolated calibrated gameplay motion for five EVA rigs and Sachiel.

Uses genuine Tuffles performances and Quaternius CC0 authored jumps. Never
installs a file into a running client and never modifies the owner's originals.
"""
from pathlib import Path
import copy
import hashlib
import json
import numpy as np
from scipy.spatial.transform import Rotation as R
from bvh_motion_r12 import load_bvh, save_npz
import retarget_human_r12 as rt
import author_eva_rifle_stances_r06 as surface

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'artifacts/combat_sortie_r32/gameplay_sources'
TUFFLES = ROOT/'external-assets/incoming/mocap/eva-action-source-r02/tuffles/HaleyTufflesPremadeMocapPack/BVH Converted/Combat'
BODY = json.loads((ROOT/'run/projectseele-local-maps/eva_body_r25.json').read_text())
NAMES = BODY['motion']['bones']
BASE_K = {s: rt.eva.K[s]-rt.eva.P['shin_'+s] for s in ('l','r')}
BASE_E = {s: rt.eva.E[s]-rt.eva.P['forearm_'+s] for s in ('l','r')}
SELECTION = {
    'guard': ('StanceBoxer', 'feet'),
    'jab': ('ArmsJabBoxer', 'feet'),
    'cross': ('ArmsSinglePunch', 'feet'),
    'hook': ('ArmsSimpleLariat', 'feet'),
    'heavy': ('ArmsCloseRangePunch', 'feet'),
    'shove': ('ArmsGrappleKnockdown', 'feet'),
    'stomp': ('LegsStomp', 'feet'),
    'air_strike': ('AerialSlapDownwards', 'air'),
    'air_kick': ('LegsDivekickFightingGameInspired', 'air'),
    'jump_start': ('Jump_Start', 'air'),
    'jump_loop': ('Jump_Loop', 'air'),
    'jump_land': ('Jump_Land', 'feet'),
}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def human(source,mirror=False):
    if source.startswith(('Ninja','Jump_')):
        path=OUT/(source+'.npz'); motion=dict(np.load(path)); calibration=dict(np.load(OUT/'A_TPose.npz'))
        motion['positions']=np.concatenate([calibration['positions'][:1],motion['positions']])
        motion['rotations']=np.concatenate([calibration['rotations'][:1],motion['rotations']])
    else:
        path=TUFFLES/(source+'.bvh'); motion=load_bvh(path)
        rest=np.zeros_like(motion['positions'][0]); rest[0]=motion['positions'][0,0]
        for i,parent in enumerate(motion['parents']):
            if parent>=0: rest[i]=rest[parent]+motion['offsets'][i]
        motion['positions']=np.concatenate([rest[None],motion['positions']])
        motion['rotations']=np.concatenate([np.tile([0.,0,0,1],(1,len(rest),1)),motion['rotations']])
        up=R.from_euler('x',-90,degrees=True)
        motion['positions']=up.apply(motion['positions'].reshape(-1,3)).reshape(motion['positions'].shape)
        motion['rotations']=(up*R.from_quat(motion['rotations'].reshape(-1,4))).as_quat().reshape(motion['rotations'].shape)
    if mirror:
        motion['positions'][:,:,0]*=-1
        motion['rotations'][:,:,[1,2]]*=-1
        motion['names']=[('R'+n[1:] if n.startswith('L') and len(n)>1 and n[1].isupper() else 'L'+n[1:] if n.startswith('R') and len(n)>1 and n[1].isupper() else n) for n in motion['names']]
    calibrated=OUT/(source+('_left' if mirror else '')+'_calibrated.npz');save_npz(calibrated,motion)
    h=rt.Human(calibrated);h.reference_frame=0
    p=h.positions[0];across=p[h.index[h.map['shoulder_l']]]-p[h.index[h.map['shoulder_r']]]
    forward=rt.unit(np.cross(across,rt.UP)*[1,0,1],(0,0,1));h.basis=R.from_euler('y',np.arctan2(forward[0],-forward[2]))
    h.floor=min(p[h.index[h.map['ankle_'+s]],1] for s in ('l','r'))
    h.height=float(p[h.index['Head_End'],1]-min(p[h.index[h.map['toe_'+s]],1] for s in ('l','r')))
    return h, {'source':str(path.relative_to(ROOT)), 'sha256':sha(path), 'mirrored':mirror,'calibration':'bind/reference pose prepended; excluded from exported motion'}

def configure(key):
    rig={b['name']:b for b in BODY['rigs'][str(key)]};m=rt.eva
    m.rig=rig;m.parents={n:b.get('parent') for n,b in rig.items()};m.P={n:np.asarray(b['pivot'],float)*[-1,1,1] for n,b in rig.items()}
    m.K={s:m.P.get('r30_knee_socket_'+s,m.P['shin_'+s]+BASE_K[s]) for s in ('l','r')}
    m.E={s:m.P.get('r30_elbow_socket_'+s,m.P['forearm_'+s]+BASE_E[s]) for s in ('l','r')}
    # New hand geometry declares its longitudinal frame explicitly. Clear it
    # when switching rigs so a NERV calibration cannot leak into a UN actor.
    m.anatomical_hand_basis_r45=BODY.get('anatomical_hand_basis_r45',{}).get(str(key))
    hulls={n:np.asarray(v,float) for n,v in BODY['rig_support'].get(str(key),BODY['support']).items()}
    m.feet={s:hulls['foot_'+s]-m.P['foot_'+s] for s in ('l','r')};m.idle=m.Pose()
    for n,b in rig.items():m.idle.setq(n,R.from_euler('xyz',np.asarray(b.get('rotation',[0,0,0]))*[-1,-1,1],degrees=True))
    surface.floor=lambda p,names:min((np.c_[hulls[n],np.ones(len(hulls[n]))]@p.matrix(n).T)[:,1].min() for n in names if n in hulls)

def rotate_stage(p,rig,rotation):
    p.setq('root',rotation*p.q['root']);p.setp('root',rotation.apply(p.p['root']+rig.P['root'])-rig.P['root'])

def export(h,support,label,angel=False):
    actor=rt.Retarget(h,angel,calibrated_trunk=True);rig=rt.battle.ANGEL if angel else rt.eva
    duration=(h.frames-2)/h.fps;count=round(duration*60)+1;poses=[];travel=[];metadata=[]
    floor=min(h.positions[0,h.index[h.map['toe_'+side]],1] for side in ('l','r'))
    heights=np.maximum(h.positions[1:,h.index[h.map['toe_l']],1],h.positions[1:,h.index[h.map['toe_r']],1])-floor
    airborne=np.flatnonzero(heights>.04)
    takeoff=float(airborne[0]/max(1,len(heights)-1)) if len(airborne) else 0
    touchdown=np.flatnonzero(heights<.04)
    landing=float(touchdown[0]/max(1,len(heights)-1)) if len(touchdown) else 1
    for frame in np.linspace(1,h.frames-1,count):
        frame_support='air' if label=='jump_land' and (frame-1)/max(1,h.frames-2)<landing else support
        p,delta,meta=actor.pose(float(frame),support=frame_support)
        src,_=h.sample(float(frame));head=R.from_matrix(rt.axes(src['head_end']-src['head'],src['shoulder_r']-src['shoulder_l']))*R.from_matrix(rt.axes(actor.ref['head_end']-actor.ref['head'],actor.ref['shoulder_r']-actor.ref['shoulder_l'])).inv()
        p.setq('head',R.from_matrix(p.parent('head')[:3,:3]).inv()*head)
        if not angel:
            for n,spec in rig.rig.items():
                if n.startswith('finger_'):p.setq(n,R.from_euler('xyz',np.asarray(spec.get('rotation',[0,0,0]))*[-1,-1,1],degrees=True));p.setp(n,[0,0,0])
        poses.append(p);travel.append(delta);metadata.append(meta)
    palms={s:np.array([p.point('hand_'+s)-(p.point('leg_l')+p.point('leg_r'))*.5 for p in poses]) for s in ('l','r')}
    lead=max(('l','r'),key=lambda s:float(np.ptp(palms[s][:,2])))
    contact=int(np.argmax(-palms[lead][:,2]));aim=palms[lead][contact].copy()
    if label=='air_strike' or angel and label=='heavy':
        lead=max(('l','r'),key=lambda side:float(np.max(-np.gradient(palms[side][:,1]))))
        contact=int(np.argmax(-np.gradient(palms[lead][:,1])));aim=palms[lead][contact].copy()
    if label=='air_kick':
        feet={side:np.array([p.point('foot_'+side)-(p.point('leg_l')+p.point('leg_r'))*.5 for p in poses]) for side in ('l','r')}
        lead=max(feet,key=lambda side:float(np.ptp(feet[side][:,2])));contact=int(np.argmax(-feet[lead][:,2]));aim=feet[lead][contact].copy()
    if label=='stomp':
        heights={s:np.array([p.point('foot_'+s)[1] for p in poses]) for s in ('l','r')};lead=max(heights,key=lambda s:float(np.ptp(heights[s])))
        peak=int(np.argmax(heights[lead]));contact=peak+int(np.argmin(heights[lead][peak:]));aim=np.array([0,0,-1.])
    angle=0 if label.startswith('jump_') or label=='guard' else float(np.arctan2(aim[0],-aim[2]))
    rotation=R.from_euler('y',angle);travel=rotation.apply(np.array(travel)-travel[0]);travel[:,1]=0
    if support=='air' or label in ('guard','jump_land'): travel[:]=0
    max_travel=float(np.max(np.linalg.norm(travel[:,[0,2]],axis=1)))*5/16
    stride_scale=min(1.,(11 if angel else 8)/max(.01,max_travel))
    for p in poses:rotate_stage(p,rig,rotation)
    initial={s:poses[0].point('foot_'+s) for s in ('l','r')}
    records=[];minimum=1e9
    for index,p in enumerate(poses):
        if stride_scale<.999:
            for side in ('l','r'):
                target=p.point('foot_'+side).copy();target[[0,2]]=initial[side][[0,2]]+stride_scale*(target[[0,2]]-initial[side][[0,2]])
                orientation=R.from_matrix(p.matrix('foot_'+side)[:3,:3]);pole=p.point('shin_'+side)-p.point('leg_'+side)
                rt.solve_ik(p,'leg_'+side,'shin_'+side,'foot_'+side,actor.knees[side],target,pole,orientation)
        if label.startswith('jump_') and not angel:
            # The stock game's stylised jump splays its knees. Keep its recorded
            # flexion/extension, but solve the EVA's longer legs in a sagittal
            # knee plane with a measured, narrow foot corridor.
            frame=R.from_matrix(p.matrix('root')[:3,:3])
            for side in ('l','r'):
                hip=p.point('leg_'+side);target=p.point('foot_'+side);local=frame.inv().apply(target-hip)
                length=np.linalg.norm(actor.knees[side]-rig.P['leg_'+side])+np.linalg.norm(rig.P['foot_'+side]-actor.knees[side])
                local[0]=np.clip(local[0],-.10*length,.10*length)
                target=hip+frame.apply(local);orientation=R.from_matrix(p.matrix('foot_'+side)[:3,:3])
                rt.solve_ik(p,'leg_'+side,'shin_'+side,'foot_'+side,actor.knees[side],target,frame.apply([-.08 if side=='l' else .08,0,-1]),orientation)
        if support=='air':
            hip=(p.point('leg_l')+p.point('leg_r'))*.5;wanted=(rig.P['leg_l']+rig.P['leg_r'])*.5
            p.setp('root',p.p['root']+wanted-hip)
        foot_min=min(float((p.matrix('foot_'+s)@np.r_[rig.P['foot_'+s],1])[1]) for s in ('l','r'))
        minimum=min(minimum,foot_min)
        if angel:record=p.encode();record['foot_contact']=[bool(metadata[index]['contacts'][s]) for s in ('l','r')]
        else:record=rig.encode(p,contacts=tuple(bool(metadata[index]['contacts'][s]) for s in ('l','r')),bone_names=NAMES)
        records.append(record)
    for i in range(1,len(records)):
        for j in range(len(records[i]['rotation_wxyz'])):
            if np.dot(records[i-1]['rotation_wxyz'][j],records[i]['rotation_wxyz'][j])<0:records[i]['rotation_wxyz'][j]=[-v for v in records[i]['rotation_wxyz'][j]]
    return {'duration_seconds':duration,'loop':label in ('guard','jump_loop'),'frames':records,'leading_side':lead,'contact_phase':contact/max(1,count-1),
            'trajectory_m':(travel*stride_scale*[-1,1,1]/112).round(8).tolist(),'source_stride_scale':stride_scale,'maximum_source_travel_blocks':max_travel,
            'takeoff_phase':takeoff,'ground_contact_phase':landing,'support':support,'minimum_ankle_y_blocks':minimum*5/16}

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--rig',type=int,choices=range(5));ap.add_argument('--angel',action='store_true');ap.add_argument('--only');args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    selected={k:v for k,v in SELECTION.items() if not args.angel or k in ('guard','jab','cross','hook','heavy','shove','stomp')}
    if args.angel:selected['heavy']=('SlapDownwards','feet')
    if args.only:selected={k:v for k,v in selected.items() if k in args.only.split(',')}
    humans={k:human(source,k in ('jab','hook')) for k,(source,_) in selected.items()}
    if args.angel:keys=['sachiel']
    else:keys=[args.rig] if args.rig is not None else list(range(5))
    for key in keys:
        if key!='sachiel':configure(key)
        path=OUT/('sachiel_gameplay_r32.json' if key=='sachiel' else f'eva_gameplay_r32_{key}.json')
        prior=json.loads(path.read_text()) if args.only else {}
        clips=prior.get('clips',{});provenance=prior.get('sources',{})
        for label,(_,support) in selected.items():
            h,meta=humans[label];clips['r32_'+label]=export(h,support,label,key=='sachiel');provenance[label]=meta
            print(key,label,len(clips['r32_'+label]['frames']),flush=True)
        data={'schema':2,'sample_rate':60,'bones':rt.battle.ANGEL.names if key=='sachiel' else NAMES,'rig_key':key,'clips':clips,'sources':provenance}
        if key=='sachiel':data['rig']=list(rt.battle.ANGEL.bones.values())
        path=OUT/('sachiel_gameplay_r32.json' if key=='sachiel' else f'eva_gameplay_r32_{key}.json')
        path.write_text(json.dumps(data,separators=(',',':')),encoding='utf8');print(path,flush=True)

if __name__=='__main__':main()
