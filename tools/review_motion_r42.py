"""Bounded native input review; restore the owner's shader preference afterwards."""
from pathlib import Path
import argparse,hashlib,json,re,time,subprocess,sys,shutil
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r42'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rig',type=int,choices=range(5),default=1)
    ap.add_argument('--case',choices=['gait','locomotion','stance','rifle','basic','normals','duel','awakening'],default='locomotion')
    ap.add_argument('--shaders',action='store_true');ap.add_argument('--guard-locomotion',action='store_true')
    ap.add_argument('--class-overlay',type=Path)
    ap.add_argument('--resource-overlay',type=Path)
    ap.add_argument('--shared-contact-witness',action='store_true')
    ap.add_argument('--angel-skin-witness-path',type=Path)
    ap.add_argument('--captured-locomotion-directory',type=Path)
    ap.add_argument('--captured-support-ownership',action='store_true')
    ap.add_argument('--at-field-calibration',action='store_true')
    ap.add_argument('--captured-state-witness-path',type=Path)
    ap.add_argument('--first-battle',type=Path);ap.add_argument('--output-root',type=Path,default=OUT);ap.add_argument('--gameplay-directory',type=Path);ap.add_argument('--body',type=Path)
    args=ap.parse_args()
    if args.captured_state_witness_path:
        assert args.captured_state_witness_path.is_absolute(),'Captured state witness requires an explicit absolute output path'
        assert not args.captured_state_witness_path.exists(),'Preserve prior captured state witness; choose a fresh output path'
        args.captured_state_witness_path=args.captured_state_witness_path.resolve()
        args.captured_state_witness_path.parent.mkdir(parents=True,exist_ok=True)
    if args.captured_support_ownership:assert args.captured_locomotion_directory,'Captured ownership candidate requires an explicit captured profile directory'
    if args.resource_overlay:
        assert args.resource_overlay.is_absolute(),'Resource overlay must be an explicit absolute directory'
        assert args.angel_skin_witness_path,'Mesh resource overlay requires actual parsed/emit witness verification'
    if args.angel_skin_witness_path:
        assert args.angel_skin_witness_path.is_absolute(),'Angel witness output must be an explicit absolute path'
        args.angel_skin_witness_path=args.angel_skin_witness_path.resolve()
        assert not args.angel_skin_witness_path.exists(),'Preserve prior angel witness; choose a fresh output path'
        args.angel_skin_witness_path.parent.mkdir(parents=True,exist_ok=True)
    guard();out=args.output_root
    label=f'{args.case}_{args.rig}_{"shader" if args.shaders else "clear"}'+('_guard' if args.guard_locomotion else '')
    dest=out/'native'/label/time.strftime('%Y%m%d_%H%M%S');dest.mkdir(parents=True,exist_ok=False)
    inputs=dest/'resources';inputs.mkdir();provenance=[]
    def freeze(source,target):
        source=source.resolve();shutil.copy2(source,target)
        provenance.append(dict(source=str(source),snapshot=str(target.resolve()),sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
        return target.resolve()
    for name in ('body','first_battle'):
        source=getattr(args,name)
        if source:setattr(args,name,freeze(source,inputs/source.name))
    captured_expected={}
    if args.captured_locomotion_directory:
        directory=inputs/'captured_locomotion';directory.mkdir();source=args.captured_locomotion_directory.resolve()
        for rig in range(5):
            path=source/f'eva_locomotion_capture_r44_{rig}.json'
            if not path.is_file():continue
            profile=json.loads(path.read_text('utf8'));assert profile['schema']=='projectseele.captured-locomotion.r44'and profile['rig_key']==rig,'Captured locomotion schema/rig mismatch'
            target=freeze(path,directory/path.name);captured_expected[rig]=dict(file=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        assert args.rig in captured_expected,'Captured directory has no complete selected rig profile'
        args.captured_locomotion_directory=directory.resolve()
    if args.gameplay_directory:
        directory=inputs/'gameplay';directory.mkdir()
        sources=[*args.gameplay_directory.glob('eva_gameplay_r*.json'),*args.gameplay_directory.glob('sachiel_gameplay_r*.json')]
        manifest=args.gameplay_directory/'combat_bundle_r44.json'
        if manifest.is_file():
            contract=json.loads(manifest.read_text('utf8'))
            for name,digest in contract['files'].items():
                assert hashlib.sha256((args.gameplay_directory/name).read_bytes()).hexdigest()==digest,('Candidate changed before review',name)
            sources.append(manifest)
        assert sources,'Explicit gameplay directory contains no compatible profiles'
        for source in dict.fromkeys(sources):freeze(source,directory/source.name)
        args.gameplay_directory=directory.resolve()
    (dest/'source_snapshots.json').write_text(json.dumps(provenance,indent=2),'utf8')
    spec=json.loads((ROOT/'.Codex/client-r42-motion-1.json').read_text('utf8'))
    # The bootstrap template once contained old body/gameplay review paths.
    # Appending a new -D earlier left the LAST old -D in control of the JVM.
    # Keep only launcher/classpath settings; author every review option here.
    spec['command']=[x for x in spec['command'] if not x.startswith('-Dprojectseele.')]
    if args.class_overlay:
        frozen=args.class_overlay.resolve();overlay=dest/'classes'
        classes=ROOT/'build/classes/java/main';shutil.copytree(classes,overlay)
        rows=[]
        for file in frozen.rglob('*.class'):
            target=overlay/file.relative_to(frozen);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
            rows.append(dict(file=str(file.relative_to(frozen)),sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
        assert rows,'Empty production class overlay'
        (dest/'class_overlay_manifest.json').write_text(json.dumps(rows,indent=2),'utf8')
        forms=[str(classes),classes.as_posix(),str(classes).replace('\\','\\\\')]
        def redirect(text):
            for original in forms:text=text.replace(original,overlay.resolve().as_posix())
            return text
        spec['command']=[redirect(s) for s in spec['command']]
        spec['environment']={k:redirect(v) for k,v in spec['environment'].items()}
        cp=dest/'minecraftClasspath.txt';cp.write_text(redirect((ROOT/'build/classpath/runClient_minecraftClasspath.txt').read_text('utf8')),'utf8')
        spec['command']=[f'-DlegacyClassPath.file={cp.resolve().as_posix()}' if s.startswith('-DlegacyClassPath.file=') else s for s in spec['command']]
    spec['command'][1:1]=[f'-Dprojectseele.combatVariant={args.rig}','-Dprojectseele.r40PoseLayers=true',
        '-Dprojectseele.combatVideo=true','-Dprojectseele.combatSideView=true','-Dprojectseele.combatFieldEnergy=0',
        '-Dprojectseele.regionalBuild=r31-combat','-Dprojectseele.nativeCapture=true']
    if args.gameplay_directory:spec['command'][1:1]=[f'-Dprojectseele.gameplayReviewDirectory={args.gameplay_directory.resolve().as_posix()}']
    if args.shared_contact_witness:
        spec['command'][1:1]=['-Dprojectseele.r44SharedContactWitness=true','-Dprojectseele.r44SharedContactTickGap=4','-Dprojectseele.r44SharedContactFrames=320']
    if args.angel_skin_witness_path:
        spec['command'][1:1]=[f'-Dprojectseele.r44RiggedSkinWitnessPath={args.angel_skin_witness_path.as_posix()}',
            '-Dprojectseele.r44RiggedSkinWitnessFrames=480','-Dprojectseele.r44RiggedSkinWitnessTickGap=3']
    if args.body:spec['command'][1:1]=[f'-Dprojectseele.bodyPoseReview={args.body.resolve().as_posix()}']
    if args.captured_locomotion_directory:spec['command'][1:1]=[f'-Dprojectseele.capturedLocomotionDirectory={args.captured_locomotion_directory.as_posix()}']
    if args.captured_support_ownership:spec['command'][1:1]=['-Dprojectseele.r44CapturedSupportOwnership=true']
    if args.at_field_calibration:spec['command'][1:1]=['-Dprojectseele.r44AtFieldCalibration=true']
    if args.captured_state_witness_path:spec['command'][1:1]=['-Dprojectseele.r44CapturedStateWitness=true',f'-Dprojectseele.r44CapturedStateWitnessPath={args.captured_state_witness_path.as_posix()}']
    if args.output_root!=OUT:spec['command'][1:1]=[f'-Dprojectseele.reviewArtifactRoot={args.output_root.resolve().as_posix()}/native_media']
    if args.case in ('gait','locomotion','stance','rifle'):spec['command'][1:1]=['-Dprojectseele.r41StanceContacts=true','-Dprojectseele.r41PoseOnly=true']
    if args.case=='rifle':spec['command'][1:1]=['-Dprojectseele.r41PoseWeapon=4','-Dprojectseele.r41HandCamera=true']
    if args.case in ('gait','locomotion'):spec['command'][1:1]=['-Dprojectseele.r42Locomotion=true']
    if args.case=='gait':spec['command'][1:1]=['-Dprojectseele.r43Gait=true']
    if args.guard_locomotion:
        assert args.case=='gait';spec['command'][1:1]=['-Dprojectseele.r43GuardLocomotion=true']
    if args.case=='duel':spec['command'][1:1]=['-Dprojectseele.combatExchange=true']
    if args.case=='normals':spec['command'][1:1]=['-Dprojectseele.combatNormals=true']
    if args.case=='awakening':
        spec['command'][1:1]=['-Dprojectseele.combatAwakening=true','-Dprojectseele.combatExchange=true','-Dprojectseele.r42OpticsReview=true']
        spec['command']=[x for x in spec['command'] if not x.startswith('-Dprojectseele.combatSideView=')]
        candidate=args.first_battle or OUT/'first_battle/first_battle_r42.json'
        if candidate.exists():spec['command'][1:1]=[f'-Dprojectseele.firstBattleReviewClip={candidate.resolve().as_posix()}']
    options=[x.split('=',1)[0] for x in spec['command'] if x.startswith('-Dprojectseele.')]
    assert len(options)==len(set(options)),'Duplicate review JVM properties'
    expected={}
    if args.body:expected['body']=dict(file=str(args.body.resolve()),sha256=hashlib.sha256(args.body.read_bytes()).hexdigest())
    if args.gameplay_directory:
        p=next((args.gameplay_directory/f'eva_gameplay_r{revision}_{args.rig}.json' for revision in (44,43,42,32)
                if (args.gameplay_directory/f'eva_gameplay_r{revision}_{args.rig}.json').is_file()),None)
        assert p is not None,'Missing actual runtime-selected rig profile'
        expected['gameplay']=dict(file=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    if args.first_battle:expected['first_battle']=dict(file=str(args.first_battle.resolve()),sha256=hashlib.sha256(args.first_battle.read_bytes()).hexdigest())
    if captured_expected:expected['captured_locomotion']=captured_expected
    (dest/'expected_resources.json').write_text(json.dumps(expected,indent=2),'utf8')
    resource_overlay=None
    if args.resource_overlay:
        from prepare_mesh_resource_overlay_r44 import prepare as prepare_resource_overlay
        spec,resource_overlay=prepare_resource_overlay(spec,args.resource_overlay,dest)
    from freeze_native_r44 import freeze as freeze_runtime
    spec=freeze_runtime(spec,dest)
    launch=dest/'launch.json';launch.write_text(json.dumps(spec),'utf8')
    cfg=ROOT/'run/config/oculus.properties';original=cfg.read_bytes();(dest/'original_oculus.properties').write_bytes(original)
    text=original.decode('utf8');text=text.replace('enableShaders=true','enableShaders=false') if not args.shaders else text.replace('enableShaders=false','enableShaders=true')
    began=time.time();cfg.write_text(text,'utf8');resource_activation=None
    try:
        if resource_overlay:
            from prepare_mesh_resource_overlay_r44 import activate as activate_resource_overlay
            resource_activation=activate_resource_overlay(resource_overlay,dest)
        with (dest/'native.log').open('w',encoding='utf8') as log:
            result=subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        assert result.returncode==0,('Client failed',result.returncode)
        pattern='r32_normal_*.json' if args.case=='normals' else 'r31_combat_*.json'
        report=max((ROOT/'run/saves/SEELE_FIELD_R31_REVIEW/Review').glob(pattern),key=lambda p:p.stat().st_mtime)
        assert report.stat().st_mtime>=began,'No fresh native result'
        if args.captured_state_witness_path:
            witness=args.captured_state_witness_path;assert witness.is_file()and witness.stat().st_mtime>=began,'Missing fresh captured state lifecycle witness'
            rows=[json.loads(line)for line in witness.read_text('utf8').splitlines()if line.strip()];assert rows,'Captured state witness is empty'
            record=dict(path=str(witness),sha256=hashlib.sha256(witness.read_bytes()).hexdigest(),rows=len(rows),
                kinds=sorted(set(r['kind']for r in rows)),logical_sides=sorted(set(r['logical_client']for r in rows)),
                level_identities=sorted(set(r['level_identity']for r in rows)),actor_identities=sorted(set(r['actor_identity']for r in rows if'actor_identity'in r)),
                state_identities=sorted(set(r['state_identity']for r in rows if'state_identity'in r)),
                scope='Actual bounded creation/leave/unload callbacks; missing logical side or unload event is explicitly unobserved, not inferred')
            (dest/'captured_state_witness_readback.json').write_text(json.dumps(record,indent=2),'utf8')
        if args.angel_skin_witness_path:
            witness=args.angel_skin_witness_path;assert witness.is_file()and witness.stat().st_mtime>=began,'Missing fresh angel skin witness'
            identities=[];ticks=[];frames=[];resources=set();vertices=[];branches=set()
            with witness.open(encoding='utf8')as stream:
                for line in stream:
                    row=json.loads(line)
                    if row.get('kind')=='actual-parsed-weighted-resource':
                        identities.append({k:row.get(k)for k in('resource','source_pack_id','source_bytes_sha256','loaded_renderer_class_sha256')})
                    elif row.get('kind')=='actual-weighted-emit-vertices':
                        ticks.append(row['game_time']);frames.append(row['frame']);resources.add(row['resource']);vertices.append(row['vertices']);branches.add(row['branch'])
            assert identities and ticks,'Witness has no actual parsed resource or submitted frames'
            if resource_overlay:
                loaded={row['resource']:row['source_bytes_sha256']for row in identities}
                assert all(loaded.get(resource)==digest for resource,digest in resource_overlay['expected_resource_identities'].items()),'Actual weighted resource did not select exact frozen mesh overlay'
            skin_record=dict(path=str(witness),sha256=hashlib.sha256(witness.read_bytes()).hexdigest(),mtime=witness.stat().st_mtime,
                actual_submitted_frames=len(ticks),game_time_range=[min(ticks),max(ticks)],frame_range=[min(frames),max(frames)],
                vertices_per_frame_range=[min(vertices),max(vertices)],resources=sorted(resources),branches=sorted(branches),resource_identities=identities,
                scope='Fresh exact parsed resource, actual final CPU palettes and submitted vertices; no GPU/art acceptance inferred')
            (dest/'angel_skin_witness_readback.json').write_text(json.dumps(skin_record,indent=2),'utf8')
        data=json.loads(report.read_text());(dest/'result.json').write_bytes(report.read_bytes())
        log=(dest/'native.log').read_text('utf8');actual={}
        body=re.findall(r'EVA body profile resolved: file=(.*?) sha256=([0-9a-f]{64})',log)
        gameplay=re.findall(r'EVA gameplay profile resolved: rig=(\d+) file=(.*?) sha256=([0-9a-f]{64})',log)
        if body:actual['body']=dict(file=body[-1][0],sha256=body[-1][1])
        for rig,file,digest in gameplay:
            if int(rig)==args.rig:actual['gameplay']=dict(file=file,sha256=digest)
        first=re.findall(r'First-battle loaded clip fingerprint (.*)',log)
        if first:actual['first_battle_fingerprints']=first
        resource_match=True
        for key,wanted in expected.items():
            if key=='captured_locomotion':
                resolved=re.findall(r'Combat motion resource resolved: role=captured-locomotion-(\d+) bundle=.*? file=(.*?) sha256=([0-9a-f]{64})',log)
                loaded={int(rig):dict(file=file,sha256=digest)for rig,file,digest in resolved}
                actual[key]=loaded
                for rig,profile in wanted.items():
                    assert hashlib.sha256(Path(profile['file']).read_bytes()).hexdigest()==profile['sha256'],'Captured profile changed during review'
                    resource_match &= rig in loaded and loaded[rig]['sha256']==profile['sha256']and Path(loaded[rig]['file']).resolve()==Path(profile['file']).resolve()
                continue
            assert hashlib.sha256(Path(wanted['file']).read_bytes()).hexdigest()==wanted['sha256'],'Candidate changed during review'
            if key=='first_battle':ok=any(wanted['sha256'] in value for value in first)
            else:ok=key in actual and actual[key]['sha256']==wanted['sha256'] and Path(actual[key]['file']).resolve()==Path(wanted['file']).resolve()
            resource_match &= ok
        (dest/'resolved_resources.json').write_text(json.dumps(dict(expected=expected,actual=actual,passed=resource_match),indent=2),'utf8')
        (out/'native'/('latest_'+label+'.json')).write_text(json.dumps(dict(result=str(dest/'result.json'),media=data.get('media'),passed=bool(data.get('passed') and resource_match),resource_match=resource_match),indent=2),'utf8')
        assert resource_match,'Native runtime did not select the requested candidate resources'
        print(json.dumps({k:data.get(k) for k in ('passed','error','media','cases')},ensure_ascii=False),flush=True)
        if 'stance_r41' in data:print({k:v for k,v in data['stance_r41'].items() if k not in ('events','poses','contact_cases')},flush=True)
        if not data.get('passed'):raise RuntimeError('Native review did not pass; inspect '+str(dest/'result.json'))
    finally:
        cfg.write_bytes(original)
        if resource_activation:
            from prepare_mesh_resource_overlay_r44 import deactivate as deactivate_resource_overlay
            deactivate_resource_overlay(resource_activation,dest)


if __name__=='__main__':main()
