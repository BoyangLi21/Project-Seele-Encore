"""Author complete hand bases and non-looping airborne poses against the five real rigs.

Private candidate only. Reference clips are never embedded in the runtime assets.
"""
from pathlib import Path
import argparse, copy, hashlib, json
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
from author_combat_r35 import Actor
from study_combat_performance_r36 import decode
from rebuild_stance_hinges_r41 import reconstruct, reachable_root, deltas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/rebuild_r42/motion'
THUMB = {'l': (-59.326567, -140.163194, -6.397107), 'r': (-59.107334, 140.223847, 6.348767)}


def unit(v):
    return v / max(np.linalg.norm(v), 1e-10)


def palm_basis(actor,side):
    width=unit(actor.P['finger_index_'+side]-actor.P['finger_little_'+side])
    along=actor.P['hand_'+side]-actor.P['forearm_'+side]
    along=unit(along-width*(along@width));palmar=unit(np.cross(width,along))
    bind=R.from_euler('xyz',np.array(actor.rig.rig['finger_middle_axis_'+side]['rotation'])*[-1,-1,1],degrees=True)
    if palmar@bind.apply([1,0,0])<0:palmar=-palmar
    return along,palmar


def hands(actor, pose, closure=.1, support=0, sides=('l','r')):
    """The adapter zero is not an open hand on the recovered TV geometry."""
    for side in sides:
        along,palmar=palm_basis(actor,side)
        calibrated=R.from_matrix(np.column_stack((palmar,-along,np.cross(palmar,-along))))
        for digit in ('index', 'middle', 'ring', 'little', 'thumb'):
            stem = 'finger_' + digit
            axis = stem + '_axis_' + side
            if axis in actor.P:
                b = actor.rig.rig[axis]
                bind = R.from_euler('xyz', np.array(b.get('rotation', [0, 0, 0])) * [-1, -1, 1], degrees=True)
                if digit != 'thumb':
                    bind=calibrated
                else:
                    bind = bind * R.from_euler('z', (1 if side == 'r' else -1) * 65 * closure, degrees=True)
                pose.setq(axis, bind); pose.setp(axis, [0, 0, 0])
            curl = np.array([6, 12, 0]) * (1-closure) + np.array([28, 42, 0]) * closure if digit == 'thumb' else np.array([10, 14, 7]) * (1-closure) + np.array([72, 88, 52]) * closure
            for joint, suffix in enumerate(('', '_tip', '_distal')):
                name = stem + suffix + '_' + side
                if name not in actor.P:
                    continue
                q = R.from_euler('z', curl[joint] * (1-support), degrees=True)
                if digit == 'thumb' and axis not in actor.P:
                    q = R.identity()
                    if joint == 0:
                        root = actor.P[name]; middle = actor.P['finger_middle_' + side]
                        tangent = unit(actor.P[stem + '_tip_' + side] - root)
                        normal = palmar
                        radial = root - middle; radial = unit(radial - along*(radial@along) - normal*(radial@normal))
                        from rebuild_stance_hinges_r41 import swing
                        opened = swing(tangent, unit(along + radial))
                        target=actor.P['finger_index_'+side]+palmar*1.6+along*1.4
                        opposed=swing(tangent,unit(target-root))
                        q = Slerp([0,1], R.concatenate([opened, opposed]))([closure*(1-support)])[0]
                pose.setq(name, q); pose.setp(name, [0, 0, 0])


def corrected_source(actor, data, clip):
    """Continuous anatomical knees, preserving captured foot trajectories."""
    poses=[]; previous={s:R.identity() for s in ('l','r')}
    for f in clip['frames']:
        p=decode(actor,data,f)
        targets={s:p.point('foot_'+s).copy() for s in ('l','r')}
        orientations={s:R.from_matrix(p.matrix('foot_'+s)[:3,:3]) for s in ('l','r')}
        reachable_root(actor,p,targets)
        for s in ('l','r'):
            reconstruct(actor,p,s,targets[s],orientations[s],previous[s]); previous[s]=p.q['leg_'+s]
        poses.append(p)
    return poses


def continuous_arms(actor,data,clip):
    """Elbow hinge with transported shoulder frame; retain real hand trajectories."""
    from rebuild_stance_hinges_r41 import swing
    poses=[];previous={s:decode(actor,data,clip['frames'][0]).q['arm_'+s] for s in ('l','r')}
    for frame in clip['frames']:
        p=decode(actor,data,frame)
        for side in ('l','r'):
            upper='arm_'+side;lower='forearm_'+side;end='hand_'+side;joint=actor.elbows[side]
            target=p.point(end).copy();orientation=R.from_matrix(p.matrix(end)[:3,:3]);p.setq(upper,previous[side])
            axis=np.array([1.,0,0]);u=joint-actor.P[upper];v=actor.P[end]-joint
            a=u@(v-axis*(axis@v));bval=u@np.cross(axis,v);c=(u@axis)*(v@axis);amp=np.hypot(a,bval);neutral=np.arctan2(bval,a)
            la=np.linalg.norm(u);lb=np.linalg.norm(v);direction=target-p.point(upper)
            length=np.clip(np.linalg.norm(direction),np.sqrt(max(0,la*la+lb*lb+2*(a*np.cos(2.85)+bval*np.sin(2.85)+c)))+.0001,np.sqrt(la*la+lb*lb+2*(amp+c))*.99999)
            angle=neutral+np.arccos(np.clip(((length*length-la*la-lb*lb)/2-c)/max(amp,1e-8),-1,1));hinge=R.from_rotvec(axis*angle)
            authored=R.from_matrix(p.matrix(upper)[:3,:3]);world=swing(authored.apply(u+hinge.apply(v)),direction)*authored
            p.setq(upper,R.from_matrix(p.parent(upper)[:3,:3]).inv()*world);p.setq(lower,hinge)
            offset=joint-actor.P[lower];p.setp(lower,offset-hinge.apply(offset))
            p.setq(end,R.from_matrix(p.parent(end)[:3,:3]).inv()*orientation);previous[side]=p.q[upper]
        poses.append(p)
    return poses


def committed_lead_arm(actor,poses,clip):
    """A strike extends, follows through and returns; no post-contact elbow snap."""
    side=clip['leading_side'];contact=float(clip['contact_phase']);count=len(poses)
    def at(t):return poses[round(t*(count-1))]
    start=at(0);anticipation=at(max(.12,contact-.23));impact=at(contact);finish=at(1)
    follow=copy.deepcopy(impact)
    follow.setq('forearm_'+side,impact.q['forearm_'+side]*R.from_euler('x',12,degrees=True))
    follow.setq('arm_'+side,impact.q['arm_'+side]*R.from_euler('y',(-1 if side=='l' else 1)*6,degrees=True))
    times=np.array([0,max(.12,contact-.23),contact,min(contact+.12,.75),.9,1.])
    keyposes=[start,anticipation,impact,follow,finish,finish]
    for name in ('arm_'+side,'forearm_'+side,'wrist_'+side,'hand_'+side):
        curve=Slerp(times,R.concatenate([p.q[name] for p in keyposes]))
        for i,p in enumerate(poses):
            t=i/(count-1);span=min(len(times)-2,max(0,np.searchsorted(times,t,side='right')-1));u=(t-times[span])/(times[span+1]-times[span]);u=u*u*u*(10-15*u+6*u*u)
            p.setq(name,curve([times[span]+u*(times[span+1]-times[span])])[0])
    for p in poses:
        q=p.q['forearm_'+side];offset=actor.elbows[side]-actor.P['forearm_'+side];p.setp('forearm_'+side,offset-q.apply(offset))


def flight_pose(actor, template, t):
    p=copy.deepcopy(template)
    # One compression and one extension, not a cyclic midair stepping motion.
    peak=np.sin(np.pi*t)**1.25
    asym=np.sin(np.pi*t)*5
    p.setq('root',R.from_euler('x',-8*peak,degrees=True))
    p.setq('torso_lower',R.from_euler('x',-6*peak,degrees=True))
    p.setq('torso_upper',R.from_euler('x',-10*peak,degrees=True))
    p.setq('head',R.from_euler('x',12*peak,degrees=True))
    for side,sign in (('l',-1),('r',1)):
        p.setq('leg_'+side,R.from_euler('xyz',[10+58*peak+sign*asym,0,sign*3],degrees=True))
        hinge=R.from_euler('x',-(18+105*peak),degrees=True)
        p.setq('shin_'+side,hinge)
        offset=actor.knees[side]-actor.P['shin_'+side]
        p.setp('shin_'+side,offset-hinge.apply(offset))
        p.setq('ankle_'+side,R.identity())
        parent=R.from_matrix(p.parent('foot_'+side)[:3,:3])
        p.setq('foot_'+side,parent.inv()*R.from_euler('x',-22*peak,degrees=True))
        p.setq('arm_'+side,R.from_euler('xyz',[20+24*peak,0,sign*(12+8*peak)],degrees=True))
        p.setq('forearm_'+side,R.from_euler('x',58+20*peak,degrees=True))
    # Airborne root follows physics. Rotation about the high root marker must
    # not manufacture another translation of the entire pelvis.
    pelvis=(p.point('leg_l')+p.point('leg_r'))*.5
    rest=(actor.P['leg_l']+actor.P['leg_r'])*.5
    p.setp('root',p.p['root']+rest-pelvis)
    hands(actor,p,.18)
    return p


def author():
    OUT.mkdir(parents=True,exist_ok=True); report=[]
    body_source=ROOT/'run/projectseele-local-maps/eva_body_r41.json'
    body=json.loads(body_source.read_text('utf8'))
    for key in range(5):
        actor=Actor(key); source=ROOT/f'run/projectseele-local-maps/eva_gameplay_r32_{key}.json'
        data=json.loads(source.read_text('utf8')); baseline=OUT/f'baseline_eva_gameplay_r32_{key}.json'
        if not baseline.exists():baseline.write_bytes(source.read_bytes())
        # Fix all inherited hand channels, including guard and ordinary motion.
        for name,c in data['clips'].items():
            closure=.16 if name.startswith('r32_jump') else .58 if name in ('r32_guard','r32_advance','r32_retreat','r32_left','r32_right') else .55 if name.startswith('r32_berserk') else 1
            hand=actor.rig.Pose(); hands(actor,hand,closure)
            for f in c['frames']:
                for n,q in hand.q.items():
                    if not n.startswith('finger_'):continue
                    i=data['bones'].index(n);x,y,z,w=q.as_quat();f['rotation_wxyz'][i]=[w,-x,-y,z]
                    f.setdefault('bone_position_xyz',{})[n]=[0,0,0]
        for name in ('jump_start','jump_land','air_strike','air_kick'):
            c=data['clips']['r32_'+name]; before=deltas(c['frames'],data['bones'])
            poses=corrected_source(actor,data,c)
            c['frames']=[actor.rig.encode(p,contacts=tuple(f.get('foot_contact',[False,False])),bone_names=data['bones']) for p,f in zip(poses,c['frames'])]
            report.append(dict(rig=key,clip=name,before=before,after=deltas(c['frames'],data['bones'])))
        for name,c in data['clips'].items():
            if name.startswith('r32_jump'):continue
            poses=continuous_arms(actor,data,c)
            if name in ('r32_jab','r32_cross','r32_hook','r32_low_jab','r32_low_cross','r32_low_hook'):committed_lead_arm(actor,poses,c)
            c['frames']=[actor.rig.encode(p,contacts=tuple(f.get('foot_contact',[False,False])),bone_names=data['bones']) for p,f in zip(poses,c['frames'])]
        # The exported source had a 36-degree change in the first three frames
        # of takeoff. Author compression/extension on the actual bearing feet.
        stance=body['stance_clips_by_rig'][str(key)]
        standing=decode(actor,stance,stance['clips']['unarmed_stance']['frames'][0])
        feet={s:standing.point('foot_'+s).copy() for s in ('l','r')}
        orientations={s:R.from_matrix(standing.matrix('foot_'+s)[:3,:3]) for s in ('l','r')}
        start=[];land=[]
        for t in np.linspace(0,1,61):
            compression=np.sin(np.pi*t)**2
            for destination,depth in ((start,.045*actor.height*compression),(land,.065*actor.height*np.sin(np.pi*t)**2)):
                p=copy.deepcopy(standing);p.setp('root',p.p['root']+[0,-depth,0])
                p.setq('torso_lower',p.q['torso_lower']*R.from_euler('x',-8*compression,degrees=True))
                p.setq('torso_upper',p.q['torso_upper']*R.from_euler('x',-12*compression,degrees=True))
                for s in ('l','r'):
                    reconstruct(actor,p,s,feet[s],orientations[s],standing.q['leg_'+s])
                hands(actor,p,.16);destination.append(actor.rig.encode(p,contacts=(True,True),bone_names=data['bones']))
        for name,frames in (('jump_start',start),('jump_land',land)):
            c=data['clips']['r32_'+name];c.update(frames=frames,trajectory_m=[[0,0,0]]*len(frames),duration_seconds=1,loop=False,takeoff_phase=1,ground_contact_phase=0)
        template=actor.rig.Pose(); frames=[actor.rig.encode(flight_pose(actor,template,t),contacts=(False,False),bone_names=data['bones']) for t in np.linspace(0,1,91)]
        c=copy.deepcopy(data['clips']['r32_jump_loop']);c.update(frames=frames,loop=False,trajectory_m=[[0,0,0]]*91,duration_seconds=1.5)
        data['clips']['r32_jump_flight']=c
        data['hand_pose_revision']=3;data['airborne_revision']=42
        data.setdefault('sources',{})['r42_articulation']={'source':'Original anatomical hand closure and single-cycle airborne performance; TV 02 reference only','license':'MIT'}
        target=OUT/f'eva_gameplay_r42_{key}.json';target.write_text(json.dumps(data,separators=(',',':')),'utf8')
        from rebuild_stance_hinges_r41 import hand_frame
        for name in ('unarmed_stance','prone_crawl'):
            c=stance['clips'][name];poses=[decode(actor,stance,f) for f in c['frames']]
            for side in ('l','r'):
                along,palmar=palm_basis(actor,side)
                goal=R.from_matrix(hand_frame([0,0,-1],[0,1,0])@hand_frame(along,-palmar).T)
                origin=R.from_matrix(poses[60 if name=='unarmed_stance' else 0].matrix('hand_'+side)[:3,:3])
                curve=Slerp([0,1],R.concatenate([origin,goal]))
                for i,p in enumerate(poses):
                    if name=='unarmed_stance' and i<=60:continue
                    t=np.clip((i-60)/60,0,1) if name=='unarmed_stance' else 1
                    t=t*t*t*(10-15*t+6*t*t)
                    world=curve([t])[0];p.setq('hand_'+side,R.from_matrix(p.parent('hand_'+side)[:3,:3]).inv()*world)
            c['frames']=[actor.rig.encode(p,contacts=tuple(f.get('foot_contact',[True,True])),bone_names=stance['bones']) for p,f in zip(poses,c['frames'])]
        print('Candidate',key,flush=True)
    body['articulation_revision_r42']=dict(source_sha256=hashlib.sha256(body_source.read_bytes()).hexdigest(),method='Measured palm frame; supporting wrist calibrated to that same frame; lower body retained')
    (OUT/'eva_body_r42.json').write_text(json.dumps(body,separators=(',',':')),'utf8')
    (OUT/'articulation_report.json').write_text(json.dumps(report,indent=2),'utf8')


def hand_studies():
    import review_tv_combat_r34 as mesh_tools
    import combat_hand_pose_r36 as old
    target=OUT/'hand_study';target.mkdir(parents=True,exist_ok=True);manifest=[]
    for key in (1,3):
        actor=Actor(key);model=['eva_unit00','eva_unit01','eva_unit02','eva_prototype','eva_un01'][key]
        for label,closure in (('relaxed',.0),('fist',1)):
            for version in ('before','candidate'):
                p=actor.rig.Pose()
                if version=='before':old.apply(p,actor.rig.rig,closure)
                else:hands(actor,p,closure)
                v,uv=mesh_tools.mesh(actor,p,model);file=f'{model}_{label}_{version}'
                np.savez_compressed(target/(file+'.npz'),vertices=v*5/16,uv=uv)
                at=(p.point('finger_middle_r')+np.array([0,-2,0]))*5/16
                manifest.append(dict(file=file,model=model,camera_target=(at[[0,2,1]]*[1,-1,1]).tolist(),camera_offset=[-14,24,5],scale=6.5))
    (target/'manifest.json').write_text(json.dumps(manifest),'utf8')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--hand-studies',action='store_true');args=ap.parse_args()
    hand_studies() if args.hand_studies else author()
