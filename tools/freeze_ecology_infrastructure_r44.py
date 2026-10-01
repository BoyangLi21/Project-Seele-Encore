"""New immutable input epoch with 3D road-clearance protection; never starts Java."""
from pathlib import Path
import argparse,hashlib,json

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('reservations',type=Path);p.add_argument('output',type=Path);p.add_argument('--installed-prefix',type=Path);p.add_argument('--provider-plan',type=Path);a=p.parse_args()
    assert not a.output.exists(),'Keep earlier inputs and markers untouched'
    original=json.loads(a.manifest.read_text('utf8'));volumes=[r['bounds'] for r in json.loads(a.reservations.read_text('utf8'))['reservations']]
    assert len(volumes)>=391 and all(len(r)==6 and r[0]<=r[3] and r[1]<=r[4] and r[2]<=r[5] for r in volumes)
    prefix=json.loads(a.installed_prefix.read_text('utf8')) if a.installed_prefix else None
    excluded={tuple(r) for r in prefix['installed_origin_keys']} if prefix else set();removed=set()
    a.output.mkdir(parents=True);jobs=[];epochs=[];origins=0
    for i,name in enumerate(original['jobs']):
        source=Path(name);job=json.loads(source.read_text('utf8'));assert job['read_only']
        if original.get('input_epochs'):assert sha(source)==original['input_epochs'][i]['sha256']
        before_origins=list(job['chunks']);job['chunks']=[q for q in before_origins if (q['x'],q['z'],q['layer']) not in excluded]
        removed.update((q['x'],q['z'],q['layer']) for q in before_origins if (q['x'],q['z'],q['layer']) in excluded)
        if not job['chunks']:continue
        job['protected_volumes']=volumes;job['protected_infrastructure_source']=str(a.reservations.resolve());job['protected_infrastructure_sha256']=sha(a.reservations);job['require_staging_controls']=True
        target=a.output/f'batch_{i:04d}.json';target.write_text(json.dumps(job,ensure_ascii=False),'utf8');jobs.append(str(target.resolve()));origins+=len(job['chunks'])
        epochs.append(dict(job=str(target.resolve()),sha256=sha(target),source=str(source.resolve()),source_sha256=sha(source),origins=len(job['chunks']),available_chunks=len(job['available_chunks'])))
    assert removed==excluded and origins+len(excluded)==original['selected_origins']
    manifest=dict(original,jobs=jobs,input_epochs=epochs,source_manifest=str(a.manifest.resolve()),source_manifest_sha256=sha(a.manifest),protected_infrastructure_volumes=len(volumes),world_written=False,require_staging_controls=True)
    manifest['selected_origins']=origins
    if prefix:manifest['installed_prefix_provenance']=dict(path=str(a.installed_prefix.resolve()),sha256=sha(a.installed_prefix),origins=len(excluded))
    target=a.output/'manifest.json';target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    contract=json.loads(a.manifest.with_name('execution_contract.json').read_text('utf8'));contract.update(input=str(target.resolve()),input_sha256=sha(target),protected_infrastructure=str(a.reservations.resolve()),protected_infrastructure_sha256=sha(a.reservations))
    contract['selected_origins']=origins;contract['batches']=len(jobs)
    if prefix:contract['installed_prefix_provenance']=manifest['installed_prefix_provenance'];contract['total_origins_with_prior_prefix']=origins+len(excluded)
    origin_counts={}
    for name in jobs:
        for q in json.loads(Path(name).read_text('utf8'))['chunks']:
            for key in (q['layer'],q['layer']+'/'+q['biome']):origin_counts[key]=origin_counts.get(key,0)+1
    contract['origin_counts']=origin_counts
    for r in contract['source_epochs']:
        r['sha256']=sha(Path(r['path']))
    extra=[ROOT/'src/main/java/com/projectseele/world'/f'{n}.java' for n in ('NativeGeofrontVegetationR44','NativeEcologyFeatureProtectionR44','NativeEcologyFeatureControlsR44','GeoFrontBoundedChunkGenerator','EcologyFutureGenerationR44')]
    extra.extend([ROOT/'src/main/java/com/projectseele/mixin/EcologyPlacedFeatureR44Mixin.java',ROOT/'src/main/resources/projectseele.mixins.json',
        ROOT/'src/main/resources/data/projectseele/dimension/geofront.json',ROOT/'src/main/resources/data/projectseele/dimension_type/geofront.json'])
    existing={r['path'] for r in contract['source_epochs']}
    contract['source_epochs'].extend(dict(path=str(p),sha256=sha(p)) for p in extra if str(p) not in existing)
    extra_current=list(ROOT.glob('src/main/java/com/projectseele/mixin/*.java'))
    extra_current.extend(ROOT/'src/main/java/com/projectseele/registry'/name for name in ['ModBlocks.java','ModItems.java'])
    existing={str(Path(r['path']).resolve()) for r in contract['source_epochs']}
    contract['source_epochs'].extend(dict(path=str(p.resolve()),sha256=sha(p)) for p in extra_current if str(p.resolve()) not in existing)
    world=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
    provider_paths=[ROOT/'src/main/resources/data/projectseele/dimension/geofront.json',world/'datapacks/tv_world_preview/data/projectseele/dimension/geofront.json',
        ROOT/'src/main/resources/data/projectseele/dimension_type/geofront.json',world/'datapacks/tv_world_preview/data/projectseele/dimension_type/geofront.json']
    pending=None;expected_provider={}
    if a.provider_plan:
        pending=json.loads(a.provider_plan.read_text('utf8'));assert pending['protection_sha256']==sha(a.reservations)
        for row in pending['forward']:
            provider_target=Path(row['target']);candidate=Path(row['bytes_from']);assert sha(provider_target)==row['expected_sha256'],'Actual provider changed since preparing its exact candidate'
            assert json.loads(candidate.read_text('utf8'))['generator']['biome_source']['protected_volumes']==volumes
            expected_provider[str(provider_target.resolve())]=sha(candidate)
    else:
        for path in provider_paths[:2]:assert json.loads(path.read_text('utf8'))['generator']['biome_source']['protected_volumes']==volumes,'Install the same exact future provider protection before freezing'
    for path in provider_paths[2:]:assert 'fixed_time' not in json.loads(path.read_text('utf8')),'The restored native day/night provider epoch is missing'
    contract['provider_epochs']=[dict(path=str(path),sha256=expected_provider.get(str(path.resolve()),sha(path)),expected_after_root_install=bool(pending and path in provider_paths[:2])) for path in provider_paths]
    for row in contract['source_epochs']:
        if str(Path(row['path']).resolve()) in expected_provider:row['sha256']=expected_provider[str(Path(row['path']).resolve())];row['expected_after_root_install']=True
    contract['command']=f'python -X utf8 tools/run_headless_r44.py ecology "{target.resolve()}" --timeout 21600'
    contract['complete_marker']=str(target.resolve())+'.complete.json';contract['failed_marker']=str(target.resolve())+'.failed.json'
    contract['protection_semantics']='Exact 3D road/device clearance, not an XY biome reservation. Plants below the elevated valley viaduct remain eligible. A complete feature touching the protected volume rolls back as one feature.'
    if pending:
        contract['provider_root_install_pending']=True;contract['runnable_before_root_preflight']=False
        contract['provider_plan']=str(a.provider_plan.resolve());contract['provider_plan_sha256']=sha(a.provider_plan)
        contract['command_after_root_preflight']=contract.pop('command')
        contract.setdefault('requirements_before_native_author',[]).insert(0,'Root applies the two exact protected provider candidates, performs a cold source/resource build and runs preflight_ecology_execution_r44.py. Never dispatch this manifest while source/provider/input epochs differ. Input protection is frozen; Root alone authorizes native execution after its actual compiled epoch settles.')
    (a.output/'execution_contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(manifest=str(target.resolve()),batches=len(jobs),origins=origins,protected_volumes=len(volumes),world_written=False)),flush=True)

if __name__=='__main__':main()
