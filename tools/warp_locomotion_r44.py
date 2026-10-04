"""Stride/stance warping with cyclic foot locks and anatomical two-bone IK.

Keeps the captured pelvis, chest, arm performance and foot roll. A source
support episode owns one world-space sole patch; only swing residual travel
is scaled. This is a new isolated bundle, not a write to a running candidate.
"""
from pathlib import Path
import argparse,copy,hashlib,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from study_combat_performance_r36 import decode
from rebuild_stance_hinges_r41 import reconstruct,reachable_root
from author_combat_bundle_r44 import maintain_joint_centres
from check_locomotion_warp_r44 import frame_between

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/combat'


def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def episodes(mask):
    count=len(mask);entries=[i for i in range(count) if mask[i] and not mask[(i-1)%count]]
    if not entries:
        if mask.all():raise ValueError('A moving cyclic foot cannot stay supported for the entire loop')
        return []
    result=[]
    for start in entries:
        end=start
        while mask[end%count] and end-start<count:end+=1
        result.append((start,end-1))
    return result


def targets(points,mask,source_stride,target_stride,continuous_vertical=False,proportional_swing=False):
    count=len(points);result=np.empty_like(points);known=np.zeros(count,bool);components=episodes(mask)
    for start,end in components:
        ids=np.arange(start,end+1);idx=ids%count;phase=ids/count
        # Bedrock's local forward is -Z. Entity +Z travel is subtracted when
        # measuring the sole patch's world position in this model frame.
        anchor=np.mean(points[idx]-np.column_stack((np.zeros(len(ids)),np.zeros(len(ids)),phase*source_stride)),axis=0)
        anchor[2]*=target_stride/source_stride;anchor[1]=0
        result[idx]=anchor+np.column_stack((np.zeros(len(ids)),np.zeros(len(ids)),phase*target_stride));known[idx]=True
    if not components:raise ValueError('No source support episode')
    # The source's swing shape is retained relative to its endpoint chord.
    # This lets both contact velocities remain exactly the new stride slope.
    boundaries=[i for i in range(count) if not known[i] and known[(i-1)%count]]
    for start in boundaries:
        end=start
        while not known[end%count] and end-start<count:end+=1
        first=(start-1)%count;last=end%count;span=end-(start-1)
        for i in range(start,end):
            u=(i-(start-1))/span;idx=i%count
            old_chord=points[first]*(1-u)+points[last]*u
            new_chord=result[first]*(1-u)+result[last]*u
            residual=points[idx]-old_chord
            residual[[0,2]]*=target_stride/source_stride
            if proportional_swing:residual[1]*=target_stride/source_stride
            result[idx]=new_chord+residual
            if continuous_vertical:result[idx,1]=max(0.,result[idx,1])
            else:result[idx,1]=points[idx,1]
    return result,components


def warp(actor,document,label,gain,contract,toes,density,continuous_vertical=False,walk_clearance_fraction=None,proportional_swing=False):
    names=document['bones'];source=copy.deepcopy(document['clips'][label]);original=source['frames'];frames=[]
    for i in range((len(original)-1)*density):
        a=i//density;w=(i%density)/density
        f=frame_between(original[a],original[a+1],w)
        f['foot_contact']=(np.asarray(original[a]['foot_contact'],bool)&np.asarray(original[a+1]['foot_contact'],bool)).tolist()
        frames.append(f)
    poses=[decode(actor,document,f) for f in frames]
    for p in poses:maintain_joint_centres(actor,p)
    count=len(poses);vertices=common.BODY.get('rig_support',{}).get(str(actor.key),common.BODY['support'])
    points={};offsets={};orientations={};masks={};wanted={};support=[];floor_toe={}
    source_stride=float(contract['stride_blocks']);target_stride=source_stride/gain
    contact_changes=[]
    measured_clearance={};forward_velocity={}
    for side,index in [('l',0),('r',1)]:
        name='foot_'+side;patches=[];rotated=[];qs=[];heights=[];toe=np.asarray(toes[side])*16
        for p in poses:
            orientation=R.from_matrix(p.matrix(name)[:3,:3]);surface=orientation.apply(np.asarray(vertices[name])-actor.P[name])
            # A changing set of lowest mesh vertices has a discontinuous
            # centroid at a heel/toe roll. Use the measured forefoot marker,
            # exactly as the existing runtime support solver does.
            patch=orientation.apply(toe);heights.append(float(patch[1]-surface[:,1].min()))
            patches.append(p.point(name)+patch);rotated.append(patch);qs.append(orientation)
        points[side]=np.asarray(patches);offsets[side]=np.asarray(rotated);orientations[side]=qs
        masks[side]=np.asarray([bool(f['foot_contact'][index]) for f in frames])
        floor_toe[side]=heights
        measured_clearance[side]=points[side][:,1]-heights
        forward_velocity[side]=(np.roll(points[side][:,2],-1)-np.roll(points[side][:,2],1))*count/2
        if continuous_vertical:
            before=masks[side].copy()
            # A foot still sweeping forwards relative to the pelvis cannot
            # own a planted world patch merely because it is low. The old
            # height-only labels latched that foot before heel strike.
            masks[side]&=forward_velocity[side]>source_stride/(5/16)*.05
            contact_changes.append(dict(side=side,released_false_plants=np.flatnonzero(before&~masks[side]).tolist()))
    if continuous_vertical and label=='walk':
        for i in range(count):
            if masks['l'][i]or masks['r'][i]:continue
            supportable=[s for s in ['l','r']if measured_clearance[s][i]<actor.height*.006 and forward_velocity[s][i]>0]
            if supportable:masks[min(supportable,key=lambda s:measured_clearance[s][i])][i]=True
    clearance_revision=[]
    for side in ['l','r']:
        measured=points[side].copy()
        # The marker sits above the sole during a heel/toe roll. Work in
        # ground clearance, then restore that geometric offset for EVERY
        # frame. Mixing absolute swing Y with planted sole Y created a jump.
        if continuous_vertical:measured[:,1]-=floor_toe[side]
        # When shortening a captured step, preserve its 3D swing proportions.
        # Scaling only horizontal residuals retained the tall source arc over
        # a much shorter step and changed the gait into a marching silhouette.
        desired,components=targets(measured,masks[side],source_stride/(5/16),target_stride/(5/16),continuous_vertical,proportional_swing)
        if walk_clearance_fraction is not None:
            assert label=='walk' and continuous_vertical and .005<=walk_clearance_fraction<=.06
            # Retarget the swing sole path, then solve the rigid leg chain.
            # The inherited long-boot capture clears over 10% of body height:
            # compressing stride alone retained that marching/high-step arc.
            # Preserve contact episodes and horizontal ground anchors; only
            # ordinary walk receives this authored clearance envelope.
            peak=float(max(0,desired[:,1].max()));limit=actor.height*walk_clearance_fraction
            scale=min(1.,limit/max(peak,1e-9));desired[:,1]*=scale
            clearance_revision.append(dict(side=side,source_peak_model=peak,target_peak_model=float(desired[:,1].max()),fraction_of_rig_height=walk_clearance_fraction,scale=scale))
        wanted[side]=desired;support.append(dict(side=side,episodes=components))
    exported=[];actual={s:[] for s in ('l','r')};joint_error=0;root_change=0
    for i,p in enumerate(poses):
        original_root=p.p['root'].copy();goals={}
        for side in ('l','r'):
            desired=wanted[side][i].copy()
            if continuous_vertical:desired[1]+=floor_toe[side][i]
            elif masks[side][i]:desired[1]=floor_toe[side][i]
            goals[side]=desired-offsets[side][i]
        reachable_root(actor,p,goals)
        for side in ('l','r'):
            joint_error=max(joint_error,reconstruct(actor,p,side,goals[side],orientations[side][i],p.q['leg_'+side]))
        maintain_joint_centres(actor,p)
        root_change=max(root_change,float(np.linalg.norm(p.p['root']-original_root)))
        for side in ('l','r'):
            matrix=p.matrix('foot_'+side);toe=actor.P['foot_'+side]+np.asarray(toes[side])*16
            patch=(matrix@np.r_[toe,1])[:3];actual[side].append(patch)
        exported.append(actor.rig.encode(p,tuple(masks[s][i] for s in ('l','r')),names))
    exported.append(copy.deepcopy(exported[0]));metrics=[]
    for side in ('l','r'):
        speed=[];a=np.asarray(actual[side]);valid=masks[side]&np.roll(masks[side],-1)
        for i in range(count):
            if not valid[i]:continue
            next=(i+1)%count;delta=a[next]-a[i];delta[2]-=target_stride/(5/16)/count
            speed.append(np.linalg.norm(delta[[0,2]])*5/16*count)
        metrics.append(dict(side=side,support_world_rms_speed_blocks_per_cycle=float(np.sqrt(np.mean(np.square(speed)))),
                            support_world_max_speed_blocks_per_cycle=float(max(speed))))
    result=copy.deepcopy(source);result['frames']=exported
    result['r44_stride_warp']=dict(source_stride_blocks=source_stride,runtime_stride_blocks=target_stride,cycle_gain=gain,
        source='Same ACCAD calibrated whole-body performance; support locks plus scaled swing residuals and anatomical IK',
        root_correction_max_model_units=root_change,ankle_target_error_max_model_units=joint_error,support=support,metrics=metrics,
        source_frames=len(original),runtime_frames=len(exported),constraint_resolve_density=density,
        continuous_sole_clearance_r45=continuous_vertical,contact_direction_audit_r45=contact_changes)
    if clearance_revision:result['r44_stride_warp']['walk_swing_clearance_r45']=clearance_revision
    if proportional_swing:result['r44_stride_warp']['source_3d_swing_proportion_preserved_r45']=True
    result['forefoot_curves_r44']={side:(np.vstack((actual[side],actual[side][0]))/16).tolist() for side in ('l','r')}
    result['forefoot_offsets_r44']=toes
    return result,result['r44_stride_warp']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ART/'motion');ap.add_argument('--output',type=Path,default=ART/'locomotion_warp/motion')
    ap.add_argument('--walk-gain',type=float,default=1.35);ap.add_argument('--run-gain',type=float,default=1.55)
    ap.add_argument('--density',type=int,default=4);args=ap.parse_args()
    if args.source.resolve()==args.output.resolve():raise ValueError('Do not mutate a running/reference bundle')
    args.output.mkdir(parents=True,exist_ok=True);manifest=json.loads((args.source/'combat_bundle_r44.json').read_text('utf8'))
    for name in manifest['files']:shutil.copy2(args.source/name,args.output/name)
    file=args.source/'eva_body_r44.json';body=json.loads(file.read_text('utf8'));common.BODY=body;reports=[]
    for key in range(5):
        actor=Actor(key);document=body['stance_clips_by_rig'][str(key)]
        toes=json.loads((args.source/f'eva_gameplay_r44_{key}.json').read_text('utf8'))['support_toes']
        for label,gain in [('walk',args.walk_gain),('run',args.run_gain)]:
            contract=body['locomotion_contract_r43'][str(key)][label]
            candidate,report=warp(actor,document,label,gain,contract,toes,args.density);document['clips'][label]=candidate
            contract['runtime_stride_blocks_r44']=report['runtime_stride_blocks'];contract['support_mask_r44']=[f['foot_contact'] for f in candidate['frames']]
            contract['forefoot_curves_r44']=candidate['forefoot_curves_r44'];contract['forefoot_offsets_r44']=toes
            reports.append(dict(rig=key,clip=label,**report));print('Warped support',key,label,'stride',round(report['runtime_stride_blocks'],3),flush=True)
    body['r44_locomotion_warp']=dict(reference_body_sha256=sha(file),method='One cyclic world-space sole patch per source support episode; source foot roll, trunk and arms retained; two-bone IK with current thigh plane and recomputed offsets',
        walk_gain=args.walk_gain,run_gain=args.run_gain,status='CANDIDATE: flat-ground support math checked, native transition/slope/visual review still required')
    target=args.output/'eva_body_r44.json';target.write_text(json.dumps(body,ensure_ascii=False,separators=(',',':')),'utf8')
    files={name:sha(args.output/name) for name in manifest['files']};identity=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    manifest.update(files=files,bundle_id='R44-'+identity[:16]);(args.output/'combat_bundle_r44.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (args.output.parent/'support_warp_report.json').write_text(json.dumps(dict(bundle=manifest['bundle_id'],reference_bundle=json.loads((args.source/'combat_bundle_r44.json').read_text())['bundle_id'],reports=reports),indent=2),'utf8')
    print('Isolated warped bundle',manifest['bundle_id'],flush=True)


if __name__=='__main__':main()
