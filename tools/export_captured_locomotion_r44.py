"""Export exact authored segments to the existing shared body runtime convention.

No default installation. Each file is bound to one independently authored rig.
Captured stage translation is retained in provenance, removed once from pose.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from scipy.spatial import ConvexHull

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--rig',type=int,required=True);ap.add_argument('--body-profile',type=Path,required=True);ap.add_argument('--supplemental',action='store_true');args=ap.parse_args()
    out=args.out.resolve();fixture=json.loads((out/'fixture.json').read_text('utf8'));export=json.loads((out/'paired_runtime_pose_candidate.json').read_text('utf8'))
    if len(fixture['actors'])!=1:raise ValueError('One separately authored rig required')
    actor=fixture['actors'][0];role=export['roles'][actor['name']];records=json.loads((out/'contact_pass_receipt.json').read_text('utf8'))['records'];segments=fixture['source_motion_card']['segments'];clips={};mapping={}
    body=json.loads(args.body_profile.read_text('utf8'));runtime_rig=body['rigs'][str(args.rig)];names=[b['name']for b in runtime_rig]
    author_rig={b['name']:b for b in role['rig_contract_r44']}
    for bone in runtime_rig:
        if author_rig.get(bone['name'])!=bone:raise ValueError('Authored bone differs from actual body owner: '+bone['name'])
    omitted=set(role['bones'])-set(names)
    if omitted-{'r37_lining','r37_red_upper','r37_jaw','r37_red_lower'}:raise ValueError('Unknown author-only bones: '+str(omitted))
    indices=[role['bones'].index(n)for n in names]
    runtime_frames=[dict(frame,rotation_wxyz=[frame['rotation_wxyz'][i]for i in indices],
                         bone_position_xyz={n:v for n,v in frame['bone_position_xyz'].items()if n in names})for frame in role['frames']]
    axes=np.array([[1.,0,0],[0,0,-1],[0,1,0]]);to_model=np.eye(4);to_model[:3,:3]=axes.T*16/5
    bones={b['name']:b for b in actor['bones']};baked=json.loads((out/'baked_world_matrices.json').read_text('utf8'));boot_vertices={};boot_body={}
    for side in ('l','r'):
        boot=np.asarray(actor['toes'][side]['vertices']);bone=bones['foot_'+side];unbake=np.linalg.inv(np.asarray(bone['neutral_model']))@to_model
        points=boot@unbake[:3,:3].T+unbake[:3,3];boot_body[side]=points/16
        unique=np.unique(points/16,axis=0);hull=unique[ConvexHull(unique).vertices]
        boot_vertices[side]=hull.tolist()
    for i,frame in enumerate(runtime_frames):
        frame['boot_contacts_body']={}
        for side in ('l','r'):
            matrix=np.asarray(baked[i]['actors'][actor['name']]['deform']['foot_'+side]);vertices=np.asarray(actor['toes'][side]['vertices']);actual=vertices@matrix[:3,:3].T+matrix[:3,3]
            index=int(np.argmin(actual[:,2]));point=boot_body[side][index]
            stance=float(records[i]['source_sole_contact_weights'][side])
            if not records[i]['source_horizontal_foot_plants'][side]:stance=0.
            frame['boot_contacts_body'][side]=dict(point=point.tolist(),stance_weight=stance,actual_authored_minimum_world_z=float(actual[index,2]),actual_boot_vertex=index)
    for segment in segments:
        selected=[r['frame']-1 for r in records if r['raw_frame'] is not None and segment['candidate_frames'][0]<=r['raw_frame']<=segment['candidate_frames'][1]]
        if not selected:raise ValueError('Missing original source segment '+segment['label'])
        frames=[runtime_frames[i] for i in selected]
        travel=float(np.linalg.norm(np.asarray(frames[-1]['stage_root_blocks'])[:2]-np.asarray(frames[0]['stage_root_blocks'])[:2]))
        clip=dict(duration_seconds=max(1/30,(len(frames)-1)/30),frames=frames,cycle_travel_world_blocks=travel,
                  source_segment=segment,author_frame_range=[selected[0]+1,selected[-1]+1])
        clips[segment['label']]=clip;mapping[segment['label']]=[selected[0]+1,selected[-1]+1]
    for target,source,index in [('idle','stand_to_walk',0),('crouch_idle','crouch',-1)]:
        if args.supplemental and source not in clips:continue
        clips[target]=dict(duration_seconds=1.,frames=[clips[source]['frames'][index]],cycle_travel_world_blocks=0.,source_endpoint=dict(clip=source,index=index))
    profile=dict(schema='projectseele.captured-locomotion-supplement.r44'if args.supplemental else'projectseele.captured-locomotion.r44',rig_key=args.rig,bones=names,rig_contract_r44=runtime_rig,clips=clips,
                 root_authority='entity-world-pose; captured-stage-travel-removed-once',fps=30,
                 contact_units='body-model-blocks-before-render-scale',render_scale=5.,boot_vertices_body=boot_vertices,
                 source_motion_card=fixture['source_motion_card'],saved_author_scene_sha256=hashlib.sha256((out/'rokoko_continuous_legs_r44.blend').read_bytes()).hexdigest(),
                 quality='UNAPPROVED explicit runtime candidate; actual native geometry, terrain, all weapon variants and art review remain required',
                 current_scope=['Actual captured walk/run cadence','stand/walk/run/brake transitions','crouch/to-prone/prone/crawl/rise transitions','authored physical contact channels'],
                 missing=['captured crouch walking take','reverse/turning locomotion source takes','all-weapon grip authoring','native server-displacement/plant adaptation verification','native acceptance'])
    if args.supplemental:
        profile['current_scope']=['Actual separately captured supplemental clips: '+', '.join(clips),'Own captured neutral and actual per-rig physical contact authoring']
        profile['missing']=['Integration into a complete separately authored rig profile','Server-owned state selection and native transitions','Full normal-speed/native/art review']
    path=out/(f'eva_locomotion_supplement_r44_{args.rig}.json'if args.supplemental else f'eva_locomotion_capture_r44_{args.rig}.json');path.write_text(json.dumps(profile,separators=(',',':')),'utf8')
    loaded=json.loads(path.read_text('utf8'));assert loaded['rig_contract_r44']==runtime_rig
    for label,clip in loaded['clips'].items():
        if len(clip['frames'][0]['rotation_wxyz'])!=len(names):raise ValueError(label)
    report=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rig=args.rig,clip_frames={n:len(c['frames'])for n,c in clips.items()},
                original_authored_ranges=mapping,cycle_seconds={n:clips[n]['duration_seconds']for n in ('walk','run','crouch_walk')if n in clips},stage_translation_used_as_pose=False,
                actual_body_profile_sha256=hashlib.sha256(args.body_profile.read_bytes()).hexdigest(),body_bones=len(names),
                omitted_author_only_head_auxiliaries=sorted(omitted),
                contact_units=profile['contact_units'],render_scale=profile['render_scale'],boot_hull_vertices={side:len(points)for side,points in boot_vertices.items()},
                root_authority=profile['root_authority'],quality=profile['quality'],missing=profile['missing'])
    (out/'captured_runtime_export_receipt.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
