"""Source-backed R44 combat bundle; writes only isolated review artifacts.

The input is the actual SEELE43 private bundle, not a guessed development copy.
Recorded anatomical thigh/shoulder frames are preserved before contact IK.
Selected Phase-M knife and K1 kick performances keep their approved intentions.
"""
from pathlib import Path
import argparse, copy, hashlib, json, shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from scipy.interpolate import PchipInterpolator
import author_gameplay_motion_r32 as common
import author_combat_performance_r36 as performance
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy, plant
from author_articulation_r42 import hands
from study_combat_performance_r36 import decode
from rebuild_stance_hinges_r41 import reconstruct, reachable_root, swing
from retarget_human_r12 import axes

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'artifacts/rebuild_r44/combat/motion'
PRIVATE = ROOT/'artifacts/rebuild_r44/network_runtime/private_resources/assets/projectseele'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(data, path):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), 'utf8')


def maintain_joint_centres(actor,pose):
    # Quaternion interpolation and translation interpolation describe different
    # hinges. Rebuild the offset from the rotation that will actually be read.
    for side in ('l','r'):
        for lower,marker in [('forearm_','r30_elbow_socket_'),('shin_','r30_knee_socket_')]:
            name=lower+side
            joint=actor.P.get(marker+side)
            if joint is None:
                joint=actor.P[name]+[0,11.4,0] if lower=='shin_' else np.array([-23.489652 if side=='l' else 23.489652,123.435069,7.737214])
            delta=joint-actor.P[name];pose.setp(name,delta-pose.q[name].apply(delta))


def arm(actor, pose, side, target, orientation, authored):
    upper, lower, end = 'arm_'+side, 'forearm_'+side, 'hand_'+side
    joint = actor.elbows[side]
    u = joint-actor.P[upper]; v = actor.P[end]-joint; axis = np.array([1.,0,0])
    a = u@(v-axis*(axis@v)); b = u@np.cross(axis,v); c = (u@axis)*(v@axis)
    amplitude = np.hypot(a,b); neutral = np.arctan2(b,a)
    la, lb = np.linalg.norm(u), np.linalg.norm(v)
    direction = target-pose.point(upper)
    longest = np.sqrt(la*la+lb*lb+2*(amplitude+c))*.9999
    shortest = np.sqrt(max(0,la*la+lb*lb+2*(a*np.cos(2.85)+b*np.sin(2.85)+c)))+.0001
    length = np.clip(np.linalg.norm(direction),shortest,longest)
    angle = neutral+np.arccos(np.clip(((length*length-la*la-lb*lb)/2-c)/max(amplitude,1e-8),-1,1))
    hinge = R.from_rotvec(axis*angle)
    world = swing(authored.apply(u+hinge.apply(v)), direction)*authored
    pose.setq(upper,R.from_matrix(pose.parent(upper)[:3,:3]).inv()*world)
    pose.setq(lower,hinge)
    delta = joint-actor.P[lower]; pose.setp(lower,delta-hinge.apply(delta))
    pose.setq(end,R.from_matrix(pose.parent(end)[:3,:3]).inv()*orientation)
    return float(np.linalg.norm(pose.point(end)-target))


def palm(actor, side):
    width=actor.P['finger_index_'+side]-actor.P['finger_little_'+side]
    width/=np.linalg.norm(width)
    along=actor.P['hand_'+side]-actor.P['forearm_'+side]
    along-=width*(along@width);along/=np.linalg.norm(along)
    normal=np.cross(width,along)
    return np.column_stack((width,along,normal))


def blade(key):
    name='eva02_knife.mesh.json' if key==2 else 'progressive_knife.mesh.json'
    file=PRIVATE/'mesh'/name
    data=json.loads(file.read_text('utf8'));part=data['parts']['knife']
    vertices=(np.asarray(part['vertices']).reshape(-1,data['stride'])[:,:3]+part['pivot'])*[-1,1,1]
    grip=np.asarray(part['pivot'])*[-1,1,1]
    count=max(3,len(vertices)//200)
    ordered=np.argsort(np.linalg.norm(vertices-grip,axis=1))[-count:]
    return grip,vertices[ordered].mean(0),dict(file=name,sha256=sha(file))


def approved_snapshots(body):
    common.BODY=body;common.NAMES=body['motion']['bones']
    source=Actor(1);records={}
    root=ROOT/'src/main/resources/assets/projectseele/motion'
    for file,label,name,contact,speed in [
        ('eva_knife_attacks_phase_m_v1.json','knife_forward','eva_locked_knife_stab_twist_forward',44,1),
        ('eva_knife_attacks_phase_m_v1.json','knife_reverse','eva_short_knife_stab_twist_reverse',24,1),
        ('eva_kick_side_left_v1.json','kick','kick_side_left',48,1.5),
    ]:
        doc=json.loads((root/file).read_text('utf8'));clip=doc['clips'][name]
        snapshots=[];start=np.asarray(clip['frames'][0]['root_m'])
        for frame in clip['frames']:
            p=decode(source,doc,frame)
            travel=(np.asarray(frame['root_m'])-start).copy();travel[1]=0
            p.setp('root',[0,p.p['root'][1],0])
            snapshots.append(dict(q={n:q.as_quat().tolist() for n,q in p.q.items()},
                                  root=p.p['root'].copy(),matrices={n:p.matrix(n).copy() for n in p.q},
                                  points={n:p.point(n).copy() for n in ('hand_l','hand_r','foot_l','foot_r','leg_l','leg_r','arm_l','arm_r')},
                                  contacts=frame.get('foot_contact',[True,True]),travel=travel.tolist()))
        records[label]=dict(snapshots=snapshots,duration=clip['duration_seconds'],contact=contact/(len(snapshots)-1),speed=speed,
                            source=dict(file=file,sha256=sha(root/file),clip=name,source_id=clip.get('source_id'),sources=doc.get('sources',[])))
    # These values remain immutable when Actor switches the global target rig.
    specification=dict(P={n:p.copy() for n,p in source.P.items()},knees={s:p.copy() for s,p in source.knees.items()},
                       elbows={s:p.copy() for s,p in source.elbows.items()},height=source.height,
                       palms={s:palm(source,s) for s in ('l','r')})
    specification['blade']=blade(1)[:2]
    return records,specification


def selected(actor, label, record, reference, names):
    frames=[];errors=[];schedules=[]
    oldP=reference['P'];grip,tip,mesh=blade(actor.key)
    oldGrip,oldTip=reference['blade']
    for item in record['snapshots']:
        p=actor.rig.Pose()
        for name in p.q:
            if name in item['q']:
                p.setq(name,R.from_quat(item['q'][name]))
        p.setp('root',item['root']*actor.height/reference['height'])
        goals={};orientations={};upper_frames={}
        for side in ('l','r'):
            for family,lower,end,oldJoint,joint,axis in [
                ('leg_','shin_','foot_',reference['knees'][side],actor.knees[side],np.array([-1.,0,0])),
                ('arm_','forearm_','hand_',reference['elbows'][side],actor.elbows[side],np.array([1.,0,0])),
            ]:
                upper=family+side;lower+=side;end+=side
                oldU=oldJoint-oldP[upper];oldV=oldP[end]-oldJoint
                oldAxis=np.cross(oldU,oldV);oldAxis/=max(np.linalg.norm(oldAxis),1e-9)
                if oldAxis[0]*axis[0]<0:oldAxis=-oldAxis
                newU=joint-actor.P[upper]
                calibration=R.from_matrix(axes(oldU,oldAxis)@axes(newU,axis).T)
                authored=R.from_matrix(item['matrices'][upper][:3,:3])*calibration
                p.setq(upper,R.from_matrix(p.parent(upper)[:3,:3]).inv()*authored)
                oldLength=np.linalg.norm(oldU)+np.linalg.norm(oldV)
                newLength=np.linalg.norm(newU)+np.linalg.norm(actor.P[end]-joint)
                target=p.point(upper)+(item['points'][end]-item['points'][upper])*newLength/oldLength
                orientation=R.from_matrix(item['matrices'][end][:3,:3])
                if end.startswith('hand_'):
                    orientation=orientation*R.from_matrix(reference['palms'][side]@palm(actor,side).T)
                    errors.append(arm(actor,p,side,target,orientation,authored))
                else:
                    goals[side]=target;orientations[side]=orientation;upper_frames[side]=p.q[upper]
        reachable_root(actor,p,goals)
        for side in ('l','r'):
            errors.append(reconstruct(actor,p,side,goals[side],orientations[side],upper_frames[side]))
        # The mesh-defined grip is retargeted to this real palm, before the
        # blade orientation is solved. UN socket positions are not TV pivots.
        if label.startswith('knife_'):
            side='r';mapping=palm(actor,side)@reference['palms'][side].T
            offset=mapping@(oldGrip-oldP['hand_r'])
            desired=actor.P['hand_r']+offset
            parent=p.parent('knife')
            wanted=(p.matrix('hand_r')@np.r_[desired,1])[:3]
            local=(np.linalg.inv(parent)@np.r_[wanted,1])[:3]
            # Mesh vertices retain their own pivot, which may differ from the
            # target bone. Solve the actual rendered grip, not that marker.
            localOffset=grip-actor.P['knife']
            world=R.from_matrix(item['matrices']['knife'][:3,:3])*swing(tip-grip,oldTip-oldGrip)
            p.setq('knife',R.from_matrix(parent[:3,:3]).inv()*world)
            p.setp('knife',local-actor.P['knife']-p.q['knife'].apply(localOffset))
            hands(actor,p,.92,sides=('r',));hands(actor,p,.18,sides=('l',))
        else:
            hands(actor,p,1)
        floor=[]
        for side in ('l','r'):
            q=R.from_matrix(p.matrix('foot_'+side)[:3,:3])
            floor.append(float((q.apply(actor.feet[side])+p.point('foot_'+side))[:,1].min()))
        p.setp('root',p.p['root']+[0,-min(floor),0])
        contacts=[bool(v-min(floor)<1.1) for v in floor]
        schedules.append(contacts)
        maintain_joint_centres(actor,p)
        frames.append(actor.rig.encode(p,contacts=contacts,bone_names=names))
    lead='l' if label=='kick' else 'r'
    if label=='kick':
        sole=np.asarray(actor.feet['l']);toe=sole[sole[:,2]<=np.percentile(sole[:,2],12)]
        contactPoint=(actor.P['foot_l']+toe.mean(0))*[-1,1,1]
    else:contactPoint=tip*[-1,1,1]
    result=dict(duration_seconds=record['duration'],frames=frames,loop=False,
                leading_side=lead,contact_phase=record['contact'],trajectory_m=[x['travel'] for x in record['snapshots']],
                step_contacts=schedules,contact_bone='foot_l' if label=='kick' else 'knife',
                contact_point_model=contactPoint.tolist(),source_playback_speed=record['speed'],
                support='Approved captured body recharacterized to the target anatomical chains; no transported prior-frame shoulder',
                maximum_contact_retarget_error_model_units=max(errors),mesh=mesh if label.startswith('knife_') else None)
    return result


def grounded(actor,data,names):
    output={};reports=[]
    guardClip,guardMeta=performance.captured(actor,'StanceBoxer',False,'guard',AnatomicalRetarget,anatomy)
    temporary=dict(bones=names)
    guard=performance.sample(actor,temporary,guardClip,.5)
    anchors={'l':np.array([-actor.width,0,-actor.height*.115]),'r':np.array([actor.width,0,actor.height*.115])}
    for label,source,mirror in [('guard','StanceBoxer',False),('jab','ArmsJabBoxer',True),
                                ('cross','ArmsSinglePunch',False),('hook','ArmsSinglePunch2',True),('heavy','ArmsCloseRangePunch',False)]:
        clip,meta=(guardClip,guardMeta) if label=='guard' else performance.captured(actor,source,mirror,label,AnatomicalRetarget,anatomy)
        old=data['clips']['r32_'+label];count=len(old['frames']);poses=[];travel=[]
        curve=PchipInterpolator([0,old.get('contact_phase',.45),1],[0,clip['contact_phase'],1]) if label!='guard' else lambda t:t
        for t in np.linspace(0,1,count):
            phase=float(curve(t));p=performance.sample(actor,temporary,clip,phase)
            if label!='guard':p=performance.mix(copy.deepcopy(guard),p,performance.ease(t/.13)*(1-performance.ease((t-.83)/.17)))
            else:p=performance.mix(p,copy.deepcopy(guard),max(1-performance.ease(t/.15),performance.ease((t-.85)/.15)))
            at=phase*(len(clip['trajectory_m'])-1);i=int(at);u=at-i
            travel.append((np.asarray(clip['trajectory_m'][i])*(1-u)+np.asarray(clip['trajectory_m'][min(i+1,len(clip['trajectory_m'])-1)])*u).tolist())
            poses.append(p)
        reference={s:np.arcsin(np.clip(R.from_matrix(poses[0].matrix('foot_'+s)[:3,:3]).apply([0,0,-1])[1],-1,1)) for s in ('l','r')}
        frames=[]
        for index,p in enumerate(poses):
            plant(actor,p,anchors,np.asarray(travel[index])*[-112,112,112],reference)
            hands(actor,p,.58 if label=='guard' else 1)
            maintain_joint_centres(actor,p)
            frames.append(actor.rig.encode(p,(True,True),names))
        result=copy.deepcopy(old)
        result.update(frames=frames,trajectory_m=travel,step_contacts=[[True,True]]*len(frames),stance_locked=True,
                      support='First retarget calibration uses fixed anatomical knee axis; current source shoulder retained before sole contacts')
        output['r32_'+label]=result
        reports.append(dict(clip=label,source=meta,frames=len(frames),duration=old['duration_seconds']))
    return output,reports


def first_battle(local):
    from author_first_battle_r42 import write_hero
    import author_first_battle_r10 as battle
    source=local/'first_battle_r43.json';old=json.loads(source.read_text('utf8'));new=copy.deepcopy(old)
    actor=Actor(1);names=list(actor.rig.rig);new['eva']['bones']=names;errors=[]
    for i,frame in enumerate(old['eva']['frames']):
        p=decode(actor,old['eva'],frame)
        # The wrapping surface was baked to a synchronized paired pose. Keep
        # that interval's source; repair the shoulder planes of the pull first.
        if i<489:
            for side in ('l','r'):
                end='hand_'+side;target=p.point(end).copy();orientation=R.from_matrix(p.matrix(end)[:3,:3])
                errors.append(arm(actor,p,side,target,orientation,R.from_matrix(p.matrix('arm_'+side)[:3,:3])))
        for side in ('l','r'):
            lower='forearm_'+side;delta=actor.elbows[side]-actor.P[lower]
            p.setp(lower,delta-p.q[lower].apply(delta))
        write_hero(old,new,i,p)
        new['eva']['frames'][i]=actor.rig.encode(p,bone_names=names)
    new['r44_articulation']=dict(input_sha256=sha(source),
            changes='Anatomical elbow hinge preserving each authored shoulder frame, complete hand channels and recomputed paired spatial sockets',
            preserved='R43 direct approach, synchronized wrap surface, final blast-only cross event and shutdown endpoints',
            maximum_hand_retarget_error_model_units=max(errors),status='CANDIDATE; native pair/contact and final rendering unverified')
    compact(new,OUT/'first_battle_r44.json')
    return new['r44_articulation']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rigs',default='0,1,2,3,4');ap.add_argument('--keep-grounded',action='store_true');args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    baseline=json.loads((ROOT/'artifacts/rebuild_r44/baseline.json').read_text('utf8'))
    local=Path(baseline['instance'])/'projectseele-local-maps'
    bodyFile=local/'eva_body_r43.json';body=json.loads(bodyFile.read_text('utf8'))
    body['r44_bundle_scope']='R43 five-rig body, low stances and gait retained; attack source calibration and gameplay contact ownership revised separately'
    compact(body,OUT/'eva_body_r44.json')
    common.BODY=body;common.NAMES=body['motion']['bones'];common.OUT=OUT/'calibrated_sources';common.OUT.mkdir(exist_ok=True)
    approved,reference=approved_snapshots(body)
    reports=[]
    for key in [int(s) for s in args.rigs.split(',')]:
        source=local/f'eva_gameplay_r43_{key}.json'
        if not source.exists():source=local/f'eva_gameplay_r42_{key}.json'
        raw=json.loads(source.read_text('utf8'));data=copy.deepcopy(raw);actor=Actor(key);names=list(actor.rig.rig)
        # Re-encode all inherited clips by their actual source channel order.
        for clip in data['clips'].values():
            frames=[]
            for f in clip['frames']:
                p=decode(actor,raw,f);maintain_joint_centres(actor,p)
                frames.append(actor.rig.encode(p,f.get('foot_contact',[True,True]),names))
            clip['frames']=frames
        data['bones']=names
        groundedReport=[]
        if not args.keep_grounded:
            replacements,groundedReport=grounded(actor,data,names);data['clips'].update(replacements)
        selectedReport=[]
        for label,record in approved.items():
            clip=selected(actor,label,record,reference,names);data['clips']['r32_'+label]=clip
            data['sources'][label]=record['source'];selectedReport.append(dict(clip=label,frames=len(clip['frames']),contact=clip['contact_phase'],
                                                                            maximum_contact_retarget_error_model_units=clip['maximum_contact_retarget_error_model_units']))
        data['r44_motion_revision']=44;data['rig_contract_r44']=body['rigs'][str(key)]
        data['r44_provenance']=dict(input_sha256=sha(source),body_sha256=sha(OUT/'eva_body_r44.json'),
              grounded=groundedReport,selected=selectedReport,status='CANDIDATE; local mathematical checks do not imply native or artistic acceptance',
              inherited_scope='Low-target/berserk/jump/airborne/recovery source clips remain separate inherited behaviors for native regression')
        compact(data,OUT/f'eva_gameplay_r44_{key}.json')
        reports.append(dict(rig=key,bones=len(names),grounded=groundedReport,selected=selectedReport))
        print('Authored R44 rig',key,'channels',len(names),flush=True)
    first=first_battle(local)
    shutil.copy2(local/'sachiel_gameplay_r32.json',OUT/'sachiel_gameplay_r44.json')
    files={p.name:sha(p) for p in sorted(OUT.glob('*r44*.json')) if p.name!='combat_bundle_r44.json'}
    identity=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    manifest=dict(revision=44,bundle_id='R44-'+identity[:16],files=files,
                  synchronized_scope='body/gameplay/finisher/Sachiel gameplay only; private textures and mesh overrides are client-owned',
                  required_profiles=[0,1,2,3,4],status='ISOLATED_REVIEW_CANDIDATE')
    (OUT/'combat_bundle_r44.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (OUT.parent/'authoring_report.json').write_text(json.dumps(dict(bundle=manifest,reports=reports,first_battle=first),ensure_ascii=False,indent=2),'utf8')
    print('Matched review bundle',manifest['bundle_id'],len(files),'files',flush=True)


if __name__=='__main__':
    main()
