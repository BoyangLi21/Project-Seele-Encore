"""Root-only disabled candidate stage, separated from native/art acceptance and promotion."""
from pathlib import Path
import argparse, copy, gzip, hashlib, io, json, shutil, sys
import nbtlib
import prepare_city_atomic_binding_r45 as binding
import migrate_city_atomic_candidate_r45 as migration
import install_city_rigid_metadata_r45 as metadata

ROOT=binding.ROOT
ART=binding.ART
PATCH_RECEIPT=ART/'city_atomic_integration_r45/candidate_phase_patch_receipt.json'

def prepare(base_file,out):
    base=binding.read(base_file);world=binding.candidate(Path(base['world']));patch=binding.read(PATCH_RECEIPT)
    allowed={r['path']:r['after_sha256'] for r in patch['sources']}
    for row in base['source_epoch']:
        digest=binding.sha(row['path'])
        assert digest==row['sha256'] or digest==allowed.get(row['path']),'Only the exact reviewed candidate-phase patch can rebind the original source epoch'
    assert all(binding.sha(p)==v for p,v in allowed.items()),'Apply the explicit candidate-phase Java patch before preparing its lease'
    for r in [base['composition_receipt'],base['catalog'],base['baseline'],base['metadata_manifest'],base['static_manifest']]:assert binding.sha(r['path'])==r['sha256']
    binding.files_match(world,base['composition_files']);old_bundle=Path(base['metadata_bundle']);manifest=binding.read(old_bundle/'manifest.json')
    assert not (old_bundle/'metadata_wal.json').exists() and not metadata.metadata_current_errors(world,manifest)
    assert not out.exists() and out.is_relative_to(ART) and not out.is_relative_to(ART/'source_world_backup');out.mkdir(parents=True)
    bundle=out/'metadata_bundle';bundle.mkdir()
    for name in ('payload','baseline'):shutil.copytree(old_bundle/name,bundle/name)
    (bundle/'source_epoch').mkdir();sources=list(dict.fromkeys([r['repository_path'] for r in manifest['source_epoch']]+['tools/stage_city_atomic_candidate_r45.py']))
    epoch=[]
    for i,relative in enumerate(sources):
        path=ROOT/relative;dest=bundle/'source_epoch'/f'{i}_{path.name}';shutil.copyfile(path,dest)
        epoch.append(dict(repository_path=relative,sha256=binding.sha(path),frozen_copy=dest.relative_to(bundle).as_posix()))
    manifest['source_epoch']=epoch;manifest['candidate_phase_patch']=binding.ref(PATCH_RECEIPT);binding.write(bundle/'manifest.json',manifest)
    shutil.copyfile(old_bundle/'required_root_static_proof_TEMPLATE.json',bundle/'required_root_static_proof_TEMPLATE.json')
    plan=copy.deepcopy(base);plan.update(metadata_bundle=str(bundle),metadata_manifest=binding.ref(bundle/'manifest.json'),source_epoch=[dict(path=str(ROOT/r['repository_path']),sha256=r['sha256']) for r in epoch],
        required_root_static_proof=str(bundle/'required_root_static_proof_TEMPLATE.json'),parent_plan=binding.ref(base_file),candidate_phase_patch=binding.ref(PATCH_RECEIPT),candidate_only_phase='CANDIDATE_DISABLED',native_art_pass=False)
    # The unchanged full static recipe, inverse and READY database are reused, not restaged or filtered.
    binding.write(out/'binding_plan.json',plan);print('Prepared full807 disabled-candidate bundle:',out/'binding_plan.json')

def finish(plan_file,execute):
    assert execute,'Candidate finish is an explicit Root world mutation'
    plan,world=binding.check_plan(plan_file);bundle=Path(plan['metadata_bundle']);manifest,wal=migration.known_candidate(plan,world)
    assert plan.get('candidate_only_phase')=='CANDIDATE_DISABLED' and wal and wal['phase'] in ('INSTALLING','APPLYING_METADATA','CANDIDATE_DISABLED')
    run=binding.read(Path(plan['journal'])/'run.json')
    assert run['phase']=='COMPLETE' and run['all_exact_final_actual_voxels_and_nbt_readback'] and run['final_exact_cells']==2859160
    for row in run['regions']:
        assert binding.sha(row['before_backup'])==row['before_sha256'],'Complete durable static inverse is required'
        assert binding.sha(row['current_region'])==row['after_sha256']
    codec=migration.codec_module();codec.TARGET=world
    with codec.locked_journal(plan_file.parent/'metadata_controller'),codec.locked_world():
        manifest,wal=migration.known_candidate(plan,world)
        errors,counts=metadata.actual_candidate_check(world,bundle,manifest);assert not errors,errors[:10]
        assert counts['actual_cargo_be']==1471 and counts['actual_cargo_cells']==749242
        proof=dict(schema='projectseele.city-rigid-candidate-static-readback-r45.v1',world=str(world),world_id=plan['world_id'],
            composition_receipt=plan['composition_receipt'],static_run=binding.ref(Path(plan['journal'])/'run.json'),
            exact_static_forward_applied=True,complete_static_inverse_durable=True,**counts,
            native_structure_port_bearing_passed=False,root_structure_art_review_passed=False,native_motion_passed=False,user_approved=False,production_runtime_enabled=False)
        proof_file=plan_file.parent/'candidate_static_readback.json'
        if proof_file.exists():assert binding.read(proof_file)==proof
        else:metadata.atomic_json(proof_file,proof)
        tag=nbtlib.load(bundle/manifest['installed_marker']);data=tag['data'];data['Stage']=nbtlib.String('CANDIDATE_DISABLED')
        data['NativeStructurePassed']=nbtlib.Byte(0);data['ExactCargoMigrationPassed']=nbtlib.Byte(1);data['ExactStaticMigrationPassed']=nbtlib.Byte(1);data['RuntimeEnabled']=nbtlib.Byte(0)
        data['CandidateStaticProofSHA256']=nbtlib.String(binding.sha(proof_file));stream=io.BytesIO();tag.write(stream);marker_bytes=gzip.compress(stream.getvalue(),compresslevel=1,mtime=0)
        marker_sha=hashlib.sha256(marker_bytes).hexdigest();wal.update(phase='APPLYING_METADATA',candidate_static_proof=binding.ref(proof_file),marker_after_sha256=marker_sha)
        metadata.atomic_json(bundle/'metadata_wal.json',wal)
        for row in manifest['operations']:
            target=metadata.resolve(world,row['target']);actual=metadata.sha(target);assert actual in (row['before_sha256'],row['after_sha256'])
            if actual!=row['after_sha256']:metadata.atomic_bytes(target,metadata.resolve(bundle,row['source']).read_bytes())
            assert metadata.sha(target)==row['after_sha256']
        metadata.atomic_bytes(metadata.resolve(world,manifest['marker_target']),marker_bytes)
        assert binding.sha(world/manifest['marker_target'])==marker_sha
        wal.update(phase='CANDIDATE_DISABLED',actual_native_readback=counts,world_written=True,native_structure_pass=False,native_art_pass=False,runtime_enabled=False)
        metadata.atomic_json(bundle/'metadata_wal.json',wal);print('Full807 candidate installed disabled. Native/art/user approval remain false.')

def ready(plan_file,out,compiled_file):
    plan,world=binding.check_plan(plan_file);bundle=Path(plan['metadata_bundle']);manifest,wal=migration.known_candidate(plan,world)
    assert wal and wal['phase']=='CANDIDATE_DISABLED' and not wal['native_structure_pass'] and not wal['native_art_pass'] and not wal['runtime_enabled']
    expected=dict(plan['composition_files']);run=binding.read(Path(plan['journal'])/'run.json');assert run['phase']=='COMPLETE'
    for r in run['regions']:expected[Path(r['current_region']).relative_to(world).as_posix()]=r['after_sha256']
    for r in manifest['operations']:expected[r['target']]=r['after_sha256']
    expected[manifest['marker_target']]=wal['marker_after_sha256'];binding.files_match(world,expected)
    compiled=binding.read(compiled_file);assert compiled['schema']=='projectseele.city-atomic-compiled-proof-r45.v1' and compiled['passed'] is True
    assert {r['path']:r['sha256'] for r in compiled['source_epoch']}=={r['path']:r['sha256'] for r in plan['source_epoch'] if r['path'].endswith('.java')}
    required={'CityAtomicCandidateBindingR45','CityCreateDistrictR45','CityRigidQualityR45','CityCreateCargoR45','CityRigidTopologyR45','CityRigidGenerationR45'}
    assert required<={Path(r['path']).stem for r in compiled['classes']}
    for r in compiled['classes']:assert binding.sha(r['path'])==r['sha256']
    assert not out.exists();out.mkdir(parents=True)
    lease=dict(schema='projectseele.city-atomic-native-binding-r45.v1',world=str(world),world_id=plan['world_id'],world_seed=plan['world_seed'],composition_complete=True,
        installed_disabled=True,native_candidate_only=True,native_structure_pass=False,native_art_pass=False,runtime_enabled=False,
        composition_receipt=plan['composition_receipt'],binding_plan=binding.ref(plan_file),metadata_wal=binding.ref(bundle/'metadata_wal.json'),root_static_proof=wal['candidate_static_proof'],
        source_epoch=[*plan['source_epoch'],binding.ref(compiled_file),*compiled['classes']],world_files=[dict(relative=k,sha256=v) for k,v in sorted(expected.items())])
    binding.write(out/'native_binding.json',lease);common=dict(world=str(world),world_id=plan['world_id'],world_seed=plan['world_seed'],candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=binding.sha(out/'native_binding.json'))
    c=dict(schema='projectseele.actual96-native-control-job-r45.v1',**common,enable_native_district=True,request_on_start=True,retract=False,actual_existing_structures=True,helper_replacement=False,requires_installed_native_verified_topology=False,requires_exact_disabled_candidate_lease=True,expected_source_endpoint=312)
    q=dict(schema='projectseele.actual96-native-quality-job-r45.v1',**common,mode='travel',endpoint_depth=0,witness_indices=[43,64,93],checkpoint_motion_tick=100,timeout_ticks=6000,stop_server_when_done=True,actual_existing_structures=True,helper_replacement=False,output=str(out/'restore_all96_result'))
    binding.write(out/'restore_all96.control.json',c);binding.write(out/'restore_all96.quality.json',q)
    print('Prepared opt-in native candidate lease. No native/art pass claimed:',out)

def rollback(plan_file,action,execute,proof_file):
    assert execute,'Rollback requires the explicit single Root writer'
    plan,world=binding.check_plan(plan_file);bundle=Path(plan['metadata_bundle']);manifest,wal=migration.known_candidate(plan,world)
    assert wal and wal['phase'] in ('INSTALLING','APPLYING_METADATA','CANDIDATE_DISABLED','ROLLING_BACK_METADATA')
    codec=migration.codec_module();codec.TARGET=world;journal=Path(plan['journal'])
    if action=='rollback-static':
        with codec.locked_journal(journal):
            m,run,db=codec.stage(Path(plan['static_manifest']['path']),journal,resume=True)
            try:codec.install(m,run,db,journal,rollback=True)
            finally:db.close()
        return
    assert proof_file and proof_file.resolve().is_relative_to(plan_file.parent)
    proof=binding.read(proof_file);assert proof['schema']=='projectseele.city-rigid-root-static-proof-r45.v1' and proof['world_id']==plan['world_id']
    assert proof['topology_forward_sha256']==manifest['static_forward_sha256'] and proof['topology_inverse_sha256']==manifest['static_inverse_sha256']
    assert proof.get('exact_static_inverse_applied') is True and proof.get('original_static_full_nbt_restored') is True
    run=binding.read(journal/'run.json');assert run['phase']=='ROLLED_BACK'
    for row in run['regions']:assert binding.sha(row['current_region'])==row['before_sha256']
    with codec.locked_journal(plan_file.parent/'metadata_controller'),codec.locked_world():
        manifest,wal=migration.known_candidate(plan,world);wal['phase']='ROLLING_BACK_METADATA';metadata.atomic_json(bundle/'metadata_wal.json',wal)
        for entry in reversed(wal['entries']):
            target=metadata.resolve(world,entry['target']);current=metadata.sha(target);assert current in (entry['before_sha256'],entry['after_sha256'])
            if entry['backup']:
                inverse=metadata.resolve(bundle,entry['backup']);assert binding.sha(inverse)==entry['before_sha256']
                metadata.atomic_bytes(target,inverse.read_bytes());assert metadata.sha(target)==entry['before_sha256']
            elif target.exists():
                assert current==entry['after_sha256'];target.unlink()
        marker=metadata.resolve(world,manifest['marker_target'])
        if marker.exists():
            assert metadata.sha(marker) in (binding.sha(bundle/manifest['installing_marker']),wal.get('marker_after_sha256'));marker.unlink()
        binding.files_match(world,plan['composition_files']);wal.update(phase='ROLLED_BACK',root_inverse_proof=binding.ref(proof_file));metadata.atomic_json(bundle/'metadata_wal.json',wal)
        print('Exact original composed static/fullNBT and original metadata bytes restored; UUID/depth never reset.')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--action',choices=('prepare','finish-candidate','ready','rollback-static','rollback-metadata'),required=True);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--out',type=Path);ap.add_argument('--execute-root',action='store_true');ap.add_argument('--compiled-proof',type=Path);ap.add_argument('--root-proof',type=Path);a=ap.parse_args()
    if a.out:
        assert a.out.resolve().is_relative_to(ART/'city_atomic_integration_r45'),'Use a named standalone City96 artifact output'
    if a.action=='prepare':assert a.out;prepare(a.plan.resolve(),a.out.resolve())
    elif a.action=='finish-candidate':finish(a.plan.resolve(),a.execute_root)
    elif a.action.startswith('rollback-'):rollback(a.plan.resolve(),a.action,a.execute_root,a.root_proof)
    else:assert a.out and a.compiled_proof;ready(a.plan.resolve(),a.out.resolve(),a.compiled_proof.resolve())

if __name__=='__main__':main()
