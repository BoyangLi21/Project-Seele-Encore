"""Temporary private rig installation with exact readback and no video.

Never changes the user's PCL instance, original meshes or historical handoff.
Restores only our own exact candidate bytes, refusing to overwrite later edits.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys, time
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--case',default='normals',choices=['normals','duel','gait','stance','rifle','cannon','cannon_fire','knife','handling','shutdown','field']);p.add_argument('--pose',default='');p.add_argument('--out',type=Path,required=True);p.add_argument('--body',type=Path);p.add_argument('--gameplay-directory',type=Path);p.add_argument('--expect-fallback',action='store_true');p.add_argument('--body-surface-witness',action='store_true');p.add_argument('--held-move-turn',action='store_true');p.add_argument('--weapon-actions',action='store_true')
    p.add_argument('--contact-trace',action='store_true')
    p.add_argument('--native-stills',action='store_true')
    p.add_argument('--cannon-contact',action='store_true')
    p.add_argument('--geometric-footsteps',action='store_true')
    p.add_argument('--shutdown-entry-trace',action='store_true')
    p.add_argument('--frozen-ack-trace',action='store_true')
    p.add_argument('--shutdown-arena',type=int,nargs=2)
    p.add_argument('--pilot-view',action='store_true')
    p.add_argument('--shaders',action='store_true')
    p.add_argument('--angel-resource-overlay',type=Path,help='Optional exact private Angel asset epoch with bounded actual emitted-skin capture')
    p.add_argument('--angel-surface-witness',action='store_true',help='Capture unchanged actually submitted Angel skin without a resource replacement')
    p.add_argument('--witness-min-stance',type=float,default=0,help='Bound expensive real-body vertex capture to the relevant posture')
    p.add_argument('--captured-locomotion-directory',type=Path,help='Explicit whole captured state-machine candidate; never selected implicitly')
    p.add_argument('--captured-support-ownership',action='store_true')
    p.add_argument('--witness-review-ticks',type=int,nargs=2)
    a=p.parse_args();guard();a.candidate=a.candidate.resolve();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
    for directory in (a.candidate,a.candidate.parent):
        assert not (directory/'INVALID_PIPELINE.json').exists(),'Failed authoring output is not an admissible candidate'
        assert not (directory/'REJECTED_BY_USER.json').exists(),'User-rejected assets cannot enter native review or promotion'
    c=json.loads((a.candidate/'hand_rig_contract.json').read_text());rig=c['rig'];name=f'eva_unit0{rig}';pack=ROOT/'run/resourcepacks/eva_real_model/assets/projectseele'
    if a.case=='rifle':
        assert set(c.get('weapon_grip_frames',{}))=={'l','r'},'Rifle review requires both measured palm frames; do not silently fall back to legacy hand pivots'
        dependency=c.get('weapon_grip_source_r45',{})
        for part in (name+'.geo.json',name+'_anatomical_hands_r45.mesh.json'):
            assert dependency.get(part)==sha(a.candidate/part),'Rifle palm calibration is missing or stale after a rig/mesh rebuild'
    from validate_anatomical_asset_r45 import validate
    preflight=validate(a.candidate);(a.out/'preflight.json').write_text(json.dumps(preflight,indent=2),encoding='utf8')
    if not a.expect_fallback:assert preflight['structural_passed'],('Candidate rejected before game launch',preflight['issues'])
    targets=[(a.candidate/(name+'.geo.json'),pack/'geo'/(name+'.geo.json')),(a.candidate/(name+'_anatomical_hands_r45.mesh.json'),pack/'mesh'/(name+'_anatomical_hands_r45.mesh.json'))]
    if 'knife_attachment_r45'in c:
        knife=Path(c['knife_attachment_r45']['source_mesh'])
        if not knife.is_absolute():knife=ROOT/knife
        assert knife.is_file(),'Missing fitted knife candidate'
        targets.append((knife,pack/'mesh'/knife.name))
    if 'knife_mechanism_r45'in c:
        body=a.candidate/c['knife_mechanism_r45']['body_mesh'];assert body.is_file()
        targets.append((body,pack/'mesh'/body.name))
    original=json.loads(targets[0][1].read_text());new=json.loads(targets[0][0].read_text());old_bones={b['name']:b for b in original['minecraft:geometry'][0]['bones']};new_bones={b['name']:b for b in new['minecraft:geometry'][0]['bones']}
    assert all(new_bones[n]==b for n,b in old_bones.items()),'Candidate changes non-hand source bones'
    expected={j['name']for j in c['new_bones']}|{j['name']for j in c.get('knife_mechanism_r45',{}).get('bones',[])}
    assert set(new_bones)-set(old_bones)==expected,'Unexpected rig changes'
    manifest=[]
    for source,target in targets:
        backup=a.out/'backup'/target.name;backup.parent.mkdir(exist_ok=True)
        if target.exists():shutil.copy2(target,backup)
        manifest.append(dict(source=str(source),target=str(target),candidate_sha256=sha(source),before_sha256=sha(target)if target.exists()else None,backup=str(backup)))
    (a.out/'installation.json').write_text(json.dumps(manifest,indent=2),'utf8')
    witness=a.out/'hand_vertices.jsonl'
    command=[sys.executable,'-X','utf8',str(ROOT/'tools/review_motion_r42.py'),'--rig',str(rig),'--case',a.case,'--no-media','--anatomical-hands',str(a.candidate.parent),'--hand-witness',str(witness),'--hand-witness-stage','','--output-root',str(a.out/'native')]
    assert 0<=a.witness_min_stance<=3
    command+=['--hand-witness-min-stance',str(a.witness_min_stance)]
    if a.witness_review_ticks:command+=['--hand-witness-review-ticks',*map(str,a.witness_review_ticks)]
    if a.pose:command+=['--hand-pose',a.pose]
    if a.body_surface_witness:command+=['--body-surface-witness']
    if a.held_move_turn:command+=['--held-move-turn']
    if a.weapon_actions:command+=['--weapon-actions']
    if a.native_stills:command+=['--native-stills']
    if a.cannon_contact:command+=['--cannon-contact']
    if a.geometric_footsteps:command+=['--geometric-footsteps']
    if a.contact_trace:command+=['--contact-trace']
    if a.shutdown_entry_trace:command+=['--shutdown-entry-trace']
    if a.frozen_ack_trace:command+=['--frozen-ack-trace']
    if a.shutdown_arena:command+=['--shutdown-arena',*map(str,a.shutdown_arena)]
    if a.pilot_view:command+=['--pilot-view']
    if a.shaders:command+=['--shaders']
    if a.angel_resource_overlay:
        command+=['--resource-overlay',str(a.angel_resource_overlay.resolve()),
            '--angel-skin-witness-path',str(a.out/'angel_skin.jsonl'),
            '--angel-skin-witness-frames','32','--angel-skin-witness-gap','12']
    elif a.angel_surface_witness:
        command+=['--angel-skin-witness-path',str(a.out/'angel_skin.jsonl'),
            '--angel-skin-witness-frames','96','--angel-skin-witness-gap','6']
    if a.body:command+=['--body',str(a.body.resolve())]
    if a.gameplay_directory:command+=['--gameplay-directory',str(a.gameplay_directory.resolve())]
    if a.captured_support_ownership:assert a.captured_locomotion_directory,'Captured support ownership needs a complete explicit profile'
    if a.captured_locomotion_directory:
        captured=a.captured_locomotion_directory.resolve()
        assert not (captured/'REJECTED_BY_USER.json').exists(),'Do not replay rejected candidates'
        assert not (captured/'INVALID_PIPELINE.json').exists(),'Failed captured motion is not a review/install candidate'
        command+=['--captured-locomotion-directory',str(captured)]
    if a.captured_support_ownership:command+=['--captured-support-ownership']
    installed=[]
    try:
        for row in manifest:
            shutil.copy2(row['source'],row['target']);assert sha(Path(row['target']))==row['candidate_sha256'];installed.append(row)
        with(a.out/'runner.log').open('w',encoding='utf8')as log:r=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if r.returncode:raise RuntimeError('Native hand check failed; see '+str(a.out/'runner.log'))
        palettes=0;submitted=0;geometry=set();mesh_hashes=set();new_joints=set();original_hands=set();resources={};measured_grip_frames=0;fallback_grip_frames=0
        with witness.open(encoding='utf8')as stream:
            for line in stream:
                row=json.loads(line)
                if row['kind']=='actual_cpu_submitted_part':resources.setdefault(row['resource'],set()).add(row['loaded_resource_sha256'])
                if row['kind']=='final_named_palette':
                    palettes+=1;geometry.add(row['loaded_geometry_sha256']);new_joints.update(b['name']for b in row['bones']if b['name'].startswith('r45_hand_'))
                    if row.get('actual_owner_inputs',{}).get('weapon')==4 and 'rifle_arm_owner_trace'in row:
                        if row['rifle_arm_owner_trace']['measured_grip']:measured_grip_frames+=1
                        else:fallback_grip_frames+=1
                elif row['kind']=='actual_cpu_submitted_part'and'anatomical_hands' in row['resource']:
                    submitted+=1;mesh_hashes.add(row['loaded_resource_sha256'])
                elif row['kind']=='actual_cpu_submitted_part'and row['resource']==f'projectseele:mesh/{name}.mesh.json'and row['bone']in ['hand_l','hand_r']:
                    original_hands.add(row['bone'])
        assert geometry=={manifest[0]['candidate_sha256']},('Wrong actual geometry',geometry)
        if a.expect_fallback:
            assert not mesh_hashes and original_hands=={'hand_l','hand_r'},'Invalid replacement must retain both actual original hands'
        else:
            assert mesh_hashes=={manifest[1]['candidate_sha256']},('Wrong actual skin',mesh_hashes)
            assert len(new_joints)==len(c['new_bones']) and submitted>=2 and palettes>=1,'No full actual anatomical palette/skin'
            if a.case=='rifle':assert measured_grip_frames>0 and fallback_grip_frames==0,('Measured firearm contact was not the actual renderer owner',measured_grip_frames,fallback_grip_frames)
        prohibited=('.mp4','.jpg')if a.native_stills else('.mp4','.png','.jpg')
        assert not any(p.suffix.lower()in prohibited for p in(a.out/'native').rglob('*')),'Unexpected media output'
        for installed_resource in manifest[2:]:
            resource='projectseele:mesh/'+Path(installed_resource['target']).name
            if 'knife_cage'in resource or a.case in ('knife','handling'):
                assert resources.get(resource)=={installed_resource['candidate_sha256']},('Candidate mechanical resource not actually submitted',resource,resources.get(resource))
        report=dict(actual_palettes=palettes,actual_submitted_hand_parts=submitted,new_joint_count=len(new_joints),geometry_sha256=list(geometry),mesh_sha256=list(mesh_hashes),no_media=not a.native_stills,no_video=True,native_stills=a.native_stills,original_hand_fallback_verified=a.expect_fallback,art_accepted=False)
        report['actually_submitted_resources']={k:sorted(v)for k,v in resources.items()}
        report['measured_grip_frames']=measured_grip_frames;report['fallback_grip_frames']=fallback_grip_frames
        (a.out/'readback.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))
    finally:
        for row in reversed(installed):
            target=Path(row['target']);assert sha(target)==row['candidate_sha256'],'External changes found: candidate restoration stopped'
            if row['before_sha256'] is None:target.unlink()
            else:shutil.copy2(row['backup'],target);assert sha(target)==row['before_sha256']
        (a.out/'restored.json').write_text(json.dumps({'development_resources_restored':True,'user_installation_unchanged':True}),'utf8')

if __name__=='__main__':main()
