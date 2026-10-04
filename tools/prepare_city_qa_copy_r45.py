"""Freeze/exactly copy one cold disabled City96 candidate to the NEW physical v2 QA save.

Default prepare/readback never writes a world. Only --execute-root --action copy
copies into an absent normal directory; no delete, rename, junction or overwrite.
Historical migration bytes/code remain separate from the new runtime admission.
"""
from pathlib import Path
from contextlib import contextmanager
import argparse, copy, hashlib, json, os, shutil, sys
import nbtlib
import prepare_city_atomic_binding_r45 as old

ROOT=old.ROOT;ART=old.ART
QA=ART/'native_candidate_session_v2/gameDir/saves/SEELE_FIELD_R45_REVIEW'
OUT=ART/'city_atomic_integration_r45/qa_copy_revision_v1'
OLD_BINDING=ART/'city_atomic_integration_r45/native_first96_v1/native_binding.json'
HELPER='src/main/java/com/projectseele/world/CityAtomicCandidateBindingR45.java'
DATA='dimensions/projectseele/geofront/data/'

def physical(path):return Path(path).resolve(strict=True)
def check_ref(row):assert old.sha(row['path'])==row['sha256'],'Frozen input changed: '+row['path']
def reparse(path):return bool(Path(path).lstat().st_file_attributes & 0x400) if os.name=='nt' else Path(path).is_symlink()
def locked_sha(handle):
    position=handle.tell();digest=hashlib.sha256()
    try:
        handle.seek(0)
        for part in iter(lambda:handle.read(4*1024*1024),b''):digest.update(part)
        return digest.hexdigest()
    finally:handle.seek(position)

def copy_locked_file(handle,dest,expected):
    assert locked_sha(handle)==expected;position=handle.tell()
    try:
        handle.seek(0)
        with dest.open('xb') as dst:shutil.copyfileobj(handle,dst,4*1024*1024);dst.flush();os.fsync(dst.fileno())
    finally:handle.seek(position)
    assert locked_sha(handle)==expected and old.sha(dest)==expected

def inventory(world,lock_handle=None):
    result={}
    for p in world.rglob('*'):
        assert not reparse(p),'No links/reparse entries inside a physical whole copy: '+str(p)
        if p.is_file():
            relative=p.relative_to(world).as_posix()
            result[relative]=locked_sha(lock_handle) if relative=='session.lock' and lock_handle is not None else old.sha(p)
    return result

def state(binding):
    for name in ('composition_receipt','binding_plan','metadata_wal','root_static_proof'):check_ref(binding[name])
    plan=old.read(binding['binding_plan']['path']);world=physical(binding['world']);assert world==physical(plan['world'])
    manifest=old.read(plan['metadata_manifest']['path']);check_ref(plan['metadata_manifest']);check_ref(plan['static_manifest'])
    bundle=Path(plan['metadata_bundle']);wal=old.read(bundle/'metadata_wal.json');assert wal['phase']=='CANDIDATE_DISABLED' and len(wal['entries'])==807
    assert manifest['archive_objects']==96 and manifest['full_be']==1471 and len(manifest['operations'])==807
    # Historical migration source epochs are proven by their immutable original frozen copies.
    # A new runtime helper does not rewrite or invalidate what was actually used to migrate.
    for row in manifest['source_epoch']:assert old.sha(bundle/row['frozen_copy'])==row['sha256']
    for row in manifest['operations']:
        assert old.sha(bundle/row['source'])==row['after_sha256'] and old.sha(world/row['target'])==row['after_sha256']
    for row in manifest['immutable_baseline']:assert old.sha(world/row['target'])==row['sha256']
    run=old.read(Path(plan['journal'])/'run.json');assert run['phase']=='COMPLETE' and run['all_exact_final_actual_voxels_and_nbt_readback'] and run['final_exact_cells']==2859160
    for row in run['regions']:
        assert old.sha(row['before_backup'])==row['before_sha256'] and old.sha(row['current_region'])==row['after_sha256']
    marker=nbtlib.load(world/manifest['marker_target'])['data']
    assert str(marker['Stage'])=='CANDIDATE_DISABLED' and not bool(marker['RuntimeEnabled']) and not bool(marker['NativeStructurePassed'])
    assert bool(marker['ExactStaticMigrationPassed']) and bool(marker['ExactCargoMigrationPassed'])
    assert str(marker['WorldUUID'])==binding['world_id']
    level=nbtlib.load(world/'level.dat')['Data'];assert int(level['WorldGenSettings']['seed'])==binding['world_seed']
    assert str(nbtlib.load(world/(DATA+'projectseele_tokyo3_building_world_id_r44.dat'))['data']['WorldUUID'])==binding['world_id']
    files=inventory(world);assert 'session.lock' in files
    assert {k:v for k,v in files.items() if k!='session.lock'}=={r['relative']:r['sha256'] for r in binding['world_files']},'Source candidate progress/files drifted after failed launch'
    return plan,world,files

def runtime_revision():
    revision=old.read(OUT/'runtime_admission_revision.json');check_ref(revision['source_after']);assert old.sha(ROOT/HELPER)==revision['source_after']['sha256']
    return revision

def prepare(out):
    binding=old.read(OLD_BINDING);plan,source,files=state(binding);revision=runtime_revision()
    assert not out.exists() and out.parent==OUT;out.mkdir()
    runtime_sources=[]
    for row in old.read(plan['metadata_manifest']['path'])['source_epoch']:
        if not row['repository_path'].endswith('.java'):continue
        path=ROOT/row['repository_path'];digest=old.sha(path)
        if row['repository_path']==HELPER:assert row['sha256']==revision['source_before']['sha256'] and digest==revision['source_after']['sha256']
        else:assert digest==row['sha256'],'Geometry/motion epoch changed outside runtime admission: '+str(path)
        runtime_sources.append(dict(path=str(path),sha256=digest))
    copy_plan=dict(schema='projectseele.city-r45-qa-copy-plan.v1',source_world=str(source),target_world=str(QA.absolute()),role='QA_ONLY',
        source_binding=old.ref(OLD_BINDING),historical_binding_plan=binding['binding_plan'],composition_receipt=binding['composition_receipt'],metadata_wal=binding['metadata_wal'],
        static_proof=binding['root_static_proof'],migration_manifest=plan['metadata_manifest'],static_manifest=plan['static_manifest'],runtime_revision=old.ref(OUT/'runtime_admission_revision.json'),
        world_id=binding['world_id'],world_seed=binding['world_seed'],files=[dict(relative=k,sha256=v) for k,v in sorted(files.items())],source_written=False,
        runtime_sources=runtime_sources,source_after_copy_must_equal_before=True,target_must_be_absent_normal_physical_directory=True,
        preserves_all_files_including_lock=True,existing_v1_session_must_remain_untouched=True,no_QA_progress_for_formal_delivery=True,
        copy_io_revision=old.ref(OUT/'copy_io_fix_v2/revision.json'))
    old.write(out/'copy_plan.json',copy_plan);old.write(out/'source_readback.json',dict(schema='projectseele.city-r45-cold-source-readback.v1',copy_plan=old.ref(out/'copy_plan.json'),files=len(files),world_id=binding['world_id'],seed=binding['world_seed'],full807_after=True,full2859160_after=True,source_original_progress_equal_first_lease=True,MC_started=False,world_written=False,cold_lock_not_claimed=True))
    template=dict(schema='projectseele.city-r45-qa-runtime-compiled-proof.v1',passed=False,source_epoch=runtime_sources,classes=[],compile_log=None)
    old.write(out/'runtime_compiled_proof_TEMPLATE.json',template);print('Prepared exact physical QA-copy plan; no world copied:',out/'copy_plan.json')

def plan_read(path):
    plan=old.read(path);assert plan['schema']=='projectseele.city-r45-qa-copy-plan.v1' and Path(plan['target_world']).absolute()==QA.absolute()
    for key in ('source_binding','historical_binding_plan','composition_receipt','metadata_wal','static_proof','migration_manifest','static_manifest','runtime_revision'):check_ref(plan[key])
    assert plan.get('copy_io_revision'),'Superseded read/copy implementation needs a newly named plan, never rewrite old evidence'
    check_ref(plan['copy_io_revision']);io_revision=old.read(plan['copy_io_revision']['path']);check_ref(io_revision['source_after'])
    assert old.sha(Path(__file__))==io_revision['source_after']['sha256'],'Whole-copy IO source epoch changed'
    runtime_revision();binding=old.read(plan['source_binding']['path']);_,source,files=state(binding)
    assert str(source)==plan['source_world'] and files=={r['relative']:r['sha256'] for r in plan['files']}
    return plan,source,files

@contextmanager
def cold_source(world):
    from release_combat_r36 import guard
    guard()
    import msvcrt
    with (world/'session.lock').open('r+b') as handle:
        handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        try:guard();yield handle
        finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)

def copy_root(plan_file,execute):
    assert execute,'Whole physical copy requires the explicit Root writer';plan,source,files=plan_read(plan_file);target=QA.absolute()
    assert not os.path.lexists(target),'Never replace an existing target, link or partial copy; preserve evidence'
    assert not target.parent.exists() or not reparse(target.parent),'Target saves parent must be a normal directory'
    receipt_path=plan_file.parent/'copy_receipt.json';assert not receipt_path.exists()
    with cold_source(source) as lock_handle:
        assert inventory(source,lock_handle)==files;target.parent.mkdir(parents=True,exist_ok=True);assert not os.path.lexists(target);target.mkdir()
        actual_target=target.resolve(strict=True);assert actual_target==target,'No symlink/junction root QA copy'
        receipt=dict(schema='projectseele.city-r45-qa-copy-receipt.v1',copy_plan=old.ref(plan_file),source_binding=plan['source_binding'],source_world=str(source),target_world=str(actual_target),
            role='QA_ONLY',world_id=plan['world_id'],world_seed=plan['world_seed'],source_written=False,copy_complete=False,files=[],original_failure_preserved=True)
        from install_city_rigid_metadata_r45 import atomic_json
        atomic_json(receipt_path,receipt)
        try:
            # No level metadata is published until the complete disabled city owner/data are present.
            order=sorted(files,key=lambda k:(k in ('level.dat','level.dat_old'),k))
            for relative in order:
                before=source/relative;dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True)
                assert not reparse(before)
                if relative=='session.lock':
                    copy_locked_file(lock_handle,dest,files[relative])
                else:
                    assert old.sha(before)==files[relative]
                    with before.open('rb') as src,dest.open('xb') as dst:shutil.copyfileobj(src,dst,4*1024*1024);dst.flush();os.fsync(dst.fileno())
                    assert old.sha(before)==files[relative]
                assert old.sha(dest)==files[relative]
                receipt['files'].append(dict(relative=relative,source_sha256=files[relative],target_sha256=old.sha(dest)))
            assert inventory(source,lock_handle)==files and inventory(target)==files
            assert int(nbtlib.load(target/'level.dat')['Data']['WorldGenSettings']['seed'])==plan['world_seed']
            assert str(nbtlib.load(target/(DATA+'projectseele_tokyo3_building_world_id_r44.dat'))['data']['WorldUUID'])==plan['world_id']
            receipt['copy_complete']=True;atomic_json(receipt_path,receipt);print('Exact complete QA_ONLY physical copy:',target)
        except BaseException as failure:
            receipt['failure']=repr(failure);atomic_json(receipt_path,receipt);raise

def ready(plan_file,out,compiled_file):
    plan,source,files=plan_read(plan_file);receipt_file=plan_file.parent/'copy_receipt.json';receipt=old.read(receipt_file);check_ref(receipt['copy_plan'])
    assert receipt['copy_complete'] and not receipt['source_written'] and receipt['role']=='QA_ONLY'
    target=physical(receipt['target_world']);assert target==QA.absolute() and not reparse(target)
    assert inventory(target)==files and inventory(source)==files
    expected={r['relative']:(r['source_sha256'],r['target_sha256']) for r in receipt['files']}
    assert len(expected)==len(receipt['files']) and expected=={k:(v,v) for k,v in files.items()}
    compiled=old.read(compiled_file);assert compiled['schema']=='projectseele.city-r45-qa-runtime-compiled-proof.v1' and compiled['passed'] is True
    assert {r['path']:r['sha256'] for r in compiled['source_epoch']}=={r['path']:r['sha256'] for r in plan['runtime_sources']}
    required={'CityAtomicCandidateBindingR45','CityCreateDistrictR45','CityRigidQualityR45','CityRigidTopologyR45','CityCreateCargoR45','CityRigidGenerationR45'}
    assert required<={Path(r['path']).stem for r in compiled['classes']}
    for row in [*compiled['source_epoch'],*compiled['classes']]:check_ref(row)
    assert not out.exists() and out.parent==OUT;out.mkdir()
    old_binding=old.read(plan['source_binding']['path']);lease=copy.deepcopy(old_binding);lease.update(schema='projectseele.city-atomic-native-binding-r45.v2',world=str(target),qa_copy=True,role='QA_ONLY',copy_receipt=old.ref(receipt_file),
        runtime_revision=plan['runtime_revision'],runtime_compiled_proof=old.ref(compiled_file),historical_source_binding=plan['source_binding'],source_epoch=[*plan['runtime_sources'],old.ref(ROOT/'tools/prepare_city_qa_copy_r45.py'),old.ref(compiled_file),*compiled['classes']],
        world_files=[dict(relative=k,sha256=v) for k,v in sorted(files.items()) if k!='session.lock'])
    old.write(out/'native_binding.json',lease)
    for kind in ('control','quality'):
        original=OLD_BINDING.parent/f'restore_all96.{kind}.json';job=old.read(original);job.update(world=str(target),candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=old.sha(out/'native_binding.json'))
        if kind=='quality':job['output']=str(out/'restore_all96_result')
        old.write(out/f'restore_all96.{kind}.json',job)
    print('Prepared explicit whole-copy QA lease; no MC started:',out)

def historical_rollback(plan_file,action,execute,proof):
    assert execute and action in ('rollback-source-static','rollback-source-metadata')
    revision=runtime_revision();original_check=old.check_plan
    def history_check(path):
        p=old.read(path);assert p['schema']=='projectseele.city-atomic-binding-plan-r45.v1'
        for row in [p['composition_receipt'],p['catalog'],p['baseline'],p['metadata_manifest'],p['static_manifest']]:check_ref(row)
        manifest=old.read(p['metadata_manifest']['path']);bundle=Path(p['metadata_bundle'])
        for row in manifest['source_epoch']:assert old.sha(bundle/row['frozen_copy'])==row['sha256']
        for row in p['source_epoch']:
            if Path(row['path'])==ROOT/HELPER:assert row['sha256']==revision['source_before']['sha256'] and old.sha(row['path'])==revision['source_after']['sha256']
            else:check_ref(row)
        world=old.candidate(Path(p['world']));assert str(world)==old.read(OLD_BINDING)['world']
        return p,world
    import stage_city_atomic_candidate_r45 as stage
    old.check_plan=history_check
    try:stage.rollback(plan_file,'rollback-static' if action.endswith('static') else 'rollback-metadata',True,proof)
    finally:old.check_plan=original_check

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--action',choices=('prepare','readback','copy','ready','rollback-source-static','rollback-source-metadata'),default='prepare');ap.add_argument('--plan',type=Path);ap.add_argument('--out',type=Path);ap.add_argument('--compiled-proof',type=Path);ap.add_argument('--execute-root',action='store_true');ap.add_argument('--root-proof',type=Path);a=ap.parse_args()
    if a.action=='prepare':assert a.out;prepare(a.out.resolve())
    elif a.action=='readback':
        assert a.plan;p,s,f=plan_read(a.plan.resolve())
        with cold_source(s) as lock_handle:assert inventory(s,lock_handle)==f
        print(json.dumps(dict(cold_readback=True,world_written=False,files=len(f),source_original_progress_and807_equal=True)))
    elif a.action=='copy':assert a.plan;copy_root(a.plan.resolve(),a.execute_root)
    elif a.action=='ready':assert a.plan and a.out and a.compiled_proof;ready(a.plan.resolve(),a.out.resolve(),a.compiled_proof.resolve())
    else:assert a.plan;historical_rollback(a.plan.resolve(),a.action,a.execute_root,a.root_proof)

if __name__=='__main__':main()
