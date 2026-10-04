"""Read-only sameQA postrun capture/binding; never copies a world or starts Java."""
from pathlib import Path
import argparse,copy,hashlib,json,msvcrt,shutil,sys
sys.dont_write_bytecode=True
import prepare_v5_facility_session_r45 as v5
import prepare_facility_source_session_r45 as old
ROOT=v5.ROOT;ART=v5.ART;SESSION=v5.SESSION;TARGET=v5.TARGET
def read(p):return v5.read(p)
def sha(p):return v5.sha(p)
def ref(p):return v5.ref(p)
def write(p,v):v5.write(p,v)
def capture(a):
    assert a.execute_root and a.root_exit_code==0,'Root actual normal-exit attestation required; do not run on a live session'
    first=a.first_run.resolve();assert first.parent==SESSION and first.name=='native_components_v5_second_v1'
    out=v5.external(a.out);native=first/'components165_BE17.native.json';result=read(native);binding=read(first/'native_binding.json');job=read(first/'components.bound.json');admission=read(first/'preworld_admission.json')
    assert result['fresh_session_pass']and result['actual_actor_restored']and result['error']==''and result['walk_complete']==165 and result['BE_complete']==17,'Actual completed FIRST165/17/restoration required'
    assert admission['passed']and admission['binding_sha256']==sha(first/'native_binding.json')==job['candidate_binding_sha256']and Path(job['world']).resolve()==TARGET.resolve()
    assert not binding.get('postrun_reload')and binding.get('composed_source_v5')
    # Only target-world lock. Other Root MCs are irrelevant to this cold copy.
    with(TARGET/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:files=old.inv(TARGET,lock);assert old.inv(TARGET,lock)==files
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    v5.source()  # immutable composed source remains the actual Root epoch
    out.mkdir();normal=out/'normal_process_exit.json'
    write(normal,dict(schema='projectseele.root-v5-normal-process-exit-attestation.v1',process_exit=a.root_exit_code,forced_termination=False,process_and_output_gate=True,root_actual_session=a.root_session,world=str(TARGET),first_job_sha256=sha(first/'components.bound.json'),first_native_result_sha256=sha(native),launcher_log=ref(first/'launcher.log'),assertion_source='Root explicit actual completed launcher exit; validated native165/17/restoration and preworld binding. Not inferred from source strings or a future run.'))
    write(out/'postrun_cold_snapshot.json',dict(schema='projectseele.v5-component-postrun-cold-epoch.v1',world=str(TARGET),files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())],source_v5_written=False,world_written_by_capture=False,first_native_result=ref(native),normal_process_exit=ref(normal),first_binding=ref(first/'native_binding.json'),first_job=ref(first/'components.bound.json'),first_admission=ref(first/'preworld_admission.json'),relog_not_yet_run=True,source_clone_is_not_relog=True))
    write(out/'reload_parent.json',dict(cold_snapshot=ref(out/'postrun_cold_snapshot.json'),first_binding=ref(first/'native_binding.json'),first_job=ref(first/'components.bound.json'),first_native_result=ref(native),normal_process_exit=ref(normal)))
    print('Captured actual sameQA postrun inventory/normal-exit parent only. No world/Java writes.',flush=True)
def bind(a):
    cold=read(a.parent);snapshot=read(cold['cold_snapshot']['path']);expected={r['relative']:r['sha256']for r in snapshot['files']};out=v5.external(a.out)
    assert Path(snapshot['world']).resolve()==TARGET.resolve()and old.inv(TARGET)==expected
    for r in cold.values():assert sha(r['path'])==r['sha256']
    first=Path(cold['first_binding']['path']).parent;original=read(first/'native_binding.json')
    assert read(cold['first_native_result']['path'])['fresh_session_pass']and read(cold['normal_process_exit']['path'])['process_and_output_gate']
    assert 'BUILD SUCCESSFUL'in a.compile_log.read_text('utf8',errors='replace')
    required=['world/FacilitySourceAdmissionR45','visual/LiftPassengerR20Review','client/visual/NervSecurityLifecycleR45','client/visual/RegionalStationPhoto','world/NervOperationsConsole','client/visual/FacilityComponentReviewR45']
    for r in required:
        p=ROOT/f'src/main/java/com/projectseele/{r}.java';c=ROOT/f'build/classes/java/main/com/projectseele/{r}.class';assert c.is_file()and c.stat().st_mtime>=p.stat().st_mtime,'Actual Root relog-source compile required'
    out.mkdir();epoch=out/'runtime_epoch';epoch.mkdir()
    for label,p in [('classes',ROOT/'build/classes/java/main'),('resources',ROOT/'build/resources/main')]:
        before=old.inv(p);shutil.copytree(p,epoch/label);assert before==old.inv(p)==old.inv(epoch/label)
    spec=read(SESSION/'prepared/launch_base.UNBOUND.json');project=[s.split('%%',1)[1]for s in spec['environment']['MOD_CLASSES'].split(';')if s.startswith('projectseele%%')]
    replace={str(Path(p).resolve()):str(epoch/('classes'if(Path(p)/'com/projectseele/ProjectSeele.class').exists()else'resources'))for p in project};spec['environment']['MOD_CLASSES']='projectseele%%'+str(epoch/'resources')+';projectseele%%'+str(epoch/'classes')
    for i,v in enumerate(spec['command']):
        if v in('-cp','-classpath','-p','--module-path'):spec['command'][i+1]=';'.join(replace.get(str(Path(x).resolve()),x)for x in spec['command'][i+1].split(';'))
    deps=read(SESSION/'prepared/DEV_dependency_and_aux_receipt.json');epochs=[ref(ROOT/f'src/main/java/com/projectseele/{r}.java')for r in required]+[ref(a.compile_log)]+[ref(p)for p in sorted(epoch.rglob('*'))if p.is_file()]+[dict(path=r['target'],sha256=r['sha256'])for r in deps['dependency_files']]+[ref(SESSION/'prepared/DEV_dependency_and_aux_receipt.json')]+list(cold.values())
    classes=[dict(resource='/com/projectseele/'+p.relative_to(epoch/'classes/com/projectseele').as_posix(),sha256=sha(p))for p in sorted((epoch/'classes/com/projectseele').rglob('*.class'))if any(p.stem==Path(r).name or p.stem.startswith(Path(r).name+'$')for r in required)]
    binding=copy.deepcopy(original);binding.update(postrun_reload=cold,source_epoch=epochs,runtime_classes=classes,world_files=[dict(relative=k,sha256=v)for k,v in sorted(expected.items())if k!='session.lock'],preworld_receipt_output=str(out/'preworld_admission.json'))
    write(out/'native_binding.json',binding);digest=sha(out/'native_binding.json');job=read(cold['first_job']['path']);job.update(candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=digest,postrun_reload=cold,output=str(out/'components165_BE17.relog.native.json'))
    write(out/'components.bound.json',job)
    props=[f'-Dprojectseele.nativeFacilityBindingR45={out/"native_binding.json"}',f'-Dprojectseele.nativeFacilityBindingR45SHA256={digest}',f'-Dprojectseele.nativeFacilityAdmissionR45={out/"preworld_admission.json"}', '-Dprojectseele.r45FacilityComponentsReview=true',f'-Dprojectseele.r45FacilityComponentsJob={out/"components.bound.json"}',f'-Dprojectseele.r45FacilityComponentsJobSHA256={sha(out/"components.bound.json")}', '-Dprojectseele.r45BeValidityReview=true','-Dprojectseele.r45BeValidityExportOnStart=true',f'-Dprojectseele.r45BeValidityOutput={out/"be_registry_actual.json"}']
    spec['command'][1:1]=props;write(out/'launch.json',spec);write(out/'prepared.json',dict(bound=True,sameQA_postrun_only=True,world_written=False,world_copied=False,Java_MC_started=False,walk165_BE17_inputs_unchanged=True,relog_actual_pass=False))
    print('Prepared sameQA postrun relog launch only. Root remains sole launcher.',flush=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['capture','bind']);p.add_argument('--first-run',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--root-exit-code',type=int);p.add_argument('--root-session');p.add_argument('--execute-root',action='store_true');p.add_argument('--parent',type=Path);p.add_argument('--compile-log',type=Path);a=p.parse_args()
    if a.mode=='capture':assert a.first_run and a.root_session;capture(a)
    else:assert a.parent and a.compile_log;bind(a)
if __name__=='__main__':main()
