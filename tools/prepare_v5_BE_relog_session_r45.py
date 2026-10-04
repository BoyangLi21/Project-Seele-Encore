"""Same thirdQA BE-only cold capture/launch; never writes/copies worlds or starts Java."""
from pathlib import Path
import argparse,copy,json,msvcrt,shutil,sys
sys.dont_write_bytecode=True
import prepare_v5_facility_session_r45 as v5
import prepare_facility_source_session_r45 as old
ROOT=v5.ROOT;ART=v5.ART;SESSION=v5.SESSION;TARGET=v5.TARGET;CANDIDATES=ART/'pyramid_components_sol_v1/v5_BE_only_relog_v1'
def read(p):return v5.read(p)
def ref(p):return v5.ref(p)
def sha(p):return v5.sha(p)
def write(p,v):v5.write(p,v)
def capture(a):
    assert a.root_exit_code==0 and a.root_session=='74922','Root actual third-session normal process exit required'
    first=a.first_run.resolve();assert first==SESSION/'native_components_v5_third_v1';out=v5.external(a.out)
    native=first/'components165_BE17.native.json';result=read(native);job=read(first/'components.bound.json');binding=read(first/'native_binding.json');admission=read(first/'preworld_admission.json')
    expected={r['id']for r in read(job['walk_inputs']['path'])['cases']};actual=result['walk_cases']
    assert len(expected)==len(actual)==165 and{r['id']for r in actual}==expected and all(r['passed']for r in actual)
    assert result['actual_actor_restored']and admission['passed']and admission['binding_sha256']==sha(first/'native_binding.json')==job['candidate_binding_sha256']and Path(job['world']).resolve()==TARGET.resolve()
    # BE has a preserved real failure; it is not a prerequisite to rechecking BE.
    assert result['BE_complete']==9 and not result['fresh_session_pass']
    with(TARGET/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:files=old.inv(TARGET,lock);assert old.inv(TARGET,lock)==files
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    v5.source();out.mkdir();normal=out/'normal_process_exit.json'
    write(normal,dict(schema='projectseele.root-v5-partial-scope-normal-exit.v1',process_exit=a.root_exit_code,forced_termination=False,walk_scope_pass=True,BE_scope_pass=False,root_actual_session=a.root_session,world=str(TARGET),walk_receipt_sha256=sha(native),root_fact='Root tools.write_stdin74922 returned exit_code0; not inferred from a log substring.',launcher_log=ref(first/'launcher.log')))
    write(out/'postrun_cold_snapshot.json',dict(schema='projectseele.v5-BE-postrun-cold-epoch.v1',world=str(TARGET),files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())],source_v5_written=False,world_written_by_capture=False,walk_receipt=ref(native),normal_process_exit=ref(normal),walk_binding=ref(first/'native_binding.json'),walk_job=ref(first/'components.bound.json'),walk165_actual_pass=True,BE9_of17_only=True,restoration_actual_pass=True,relog_not_yet_run=True))
    write(out/'BE_reload_parent.json',dict(cold_snapshot=ref(out/'postrun_cold_snapshot.json'),walk_binding=ref(first/'native_binding.json'),walk_job=ref(first/'components.bound.json'),walk_receipt=ref(native),normal_process_exit=ref(normal)))
    print('Captured SAME thirdQA postrun; walk165 inherited, BE9 partial, no world/Java writes.',flush=True)
def bind(a):
    parent=read(a.parent);snapshot=read(parent['cold_snapshot']['path']);files={r['relative']:r['sha256']for r in snapshot['files']};out=v5.external(a.out)
    assert Path(snapshot['world']).resolve()==TARGET.resolve()and old.inv(TARGET)==files
    for r in parent.values():assert sha(r['path'])==r['sha256']
    first=Path(parent['walk_binding']['path']).parent;original=read(first/'native_binding.json');assert read(parent['walk_receipt']['path'])['walk_complete']==165
    assert 'BUILD SUCCESSFUL'in a.compile_log.read_text('utf8',errors='replace')
    # Root v152 adds a strict sign-message ListTag element-type check. Keep
    # both full reviewed sources sealed separately from the old candidate.
    addendum=CANDIDATES/'root_v152_sign_listtype_addendum_v1/root_actual_two_source_epoch.json'
    source_epoch=read(addendum)if addendum.exists()else None
    if source_epoch is not None:
        assert source_epoch['root_authorized']and sha(source_epoch['root_actual_compile_log']['path'])==source_epoch['root_actual_compile_log']['sha256']
    # Actual complete AFTER bytes, never a contains-string assertion.
    for name,relative in [('FacilitySourceAdmissionR45','world/FacilitySourceAdmissionR45'),('FacilityComponentReviewR45','client/visual/FacilityComponentReviewR45')]:
        actual=ROOT/f'src/main/java/com/projectseele/{relative}.java';expected=CANDIDATES/(name+'.candidate.txt')
        if source_epoch is not None:
            record=next(r for r in source_epoch['sources']if r['name']==name);frozen=record['expected_frozen_source'];expected=Path(frozen['path'])
            assert Path(record['actual_source']).resolve()==actual.resolve()and sha(expected)==frozen['sha256']
        assert sha(actual)==sha(expected),'Root must apply exact reviewed BE-only source patch before binding'
    required=['world/FacilitySourceAdmissionR45','visual/LiftPassengerR20Review','client/visual/NervSecurityLifecycleR45','client/visual/RegionalStationPhoto','world/NervOperationsConsole','client/visual/FacilityComponentReviewR45']
    for r in required:
        p=ROOT/f'src/main/java/com/projectseele/{r}.java';c=ROOT/f'build/classes/java/main/com/projectseele/{r}.class';assert c.is_file()and c.stat().st_mtime>=p.stat().st_mtime
    out.mkdir();epoch=out/'runtime_epoch';epoch.mkdir()
    for label,p in [('classes',ROOT/'build/classes/java/main'),('resources',ROOT/'build/resources/main')]:
        before=old.inv(p);shutil.copytree(p,epoch/label);assert before==old.inv(p)==old.inv(epoch/label)
    spec=read(SESSION/'prepared/launch_base.UNBOUND.json');project=[s.split('%%',1)[1]for s in spec['environment']['MOD_CLASSES'].split(';')if s.startswith('projectseele%%')];replace={str(Path(p).resolve()):str(epoch/('classes'if(Path(p)/'com/projectseele/ProjectSeele.class').exists()else'resources'))for p in project};spec['environment']['MOD_CLASSES']='projectseele%%'+str(epoch/'resources')+';projectseele%%'+str(epoch/'classes')
    for i,val in enumerate(spec['command']):
        if val in('-cp','-classpath','-p','--module-path'):spec['command'][i+1]=';'.join(replace.get(str(Path(x).resolve()),x)for x in spec['command'][i+1].split(';'))
    deps=read(SESSION/'prepared/DEV_dependency_and_aux_receipt.json');epochs=[ref(ROOT/f'src/main/java/com/projectseele/{r}.java')for r in required]+[ref(a.compile_log)]+[ref(p)for p in sorted(epoch.rglob('*'))if p.is_file()]+[dict(path=r['target'],sha256=r['sha256'])for r in deps['dependency_files']]+list(parent.values())+[ref(SESSION/'prepared/DEV_dependency_and_aux_receipt.json')]
    if source_epoch is not None:epochs+=[ref(addendum)]+[r['expected_frozen_source']for r in source_epoch['sources']]
    classes=[dict(resource='/com/projectseele/'+p.relative_to(epoch/'classes/com/projectseele').as_posix(),sha256=sha(p))for p in sorted((epoch/'classes/com/projectseele').rglob('*.class'))if any(p.stem==Path(r).name or p.stem.startswith(Path(r).name+'$')for r in required)]
    binding=copy.deepcopy(original);binding.update(postrun_BE_recheck=parent,active_scopes=['COMPONENT_BE'],source_epoch=epochs,runtime_classes=classes,world_files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())if k!='session.lock'],preworld_receipt_output=str(out/'preworld_admission.json'))
    write(out/'native_binding.json',binding);digest=sha(out/'native_binding.json');job=read(parent['walk_job']['path']);job.update(candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=digest,facility_scope='COMPONENT_BE',BE_only_recheck=True,postrun_BE_recheck=parent,walk_inheritance=dict(receipt=parent['walk_receipt'],actual_cases=165,executed_this_run=0),output=str(out/'BE17.relog.native.json'))
    write(out/'components.bound.json',job);props=[f'-Dprojectseele.nativeFacilityBindingR45={out/"native_binding.json"}',f'-Dprojectseele.nativeFacilityBindingR45SHA256={digest}',f'-Dprojectseele.nativeFacilityAdmissionR45={out/"preworld_admission.json"}', '-Dprojectseele.r45FacilityComponentsReview=true',f'-Dprojectseele.r45FacilityComponentsJob={out/"components.bound.json"}',f'-Dprojectseele.r45FacilityComponentsJobSHA256={sha(out/"components.bound.json")}', '-Dprojectseele.r45BeValidityReview=true','-Dprojectseele.r45BeValidityExportOnStart=true',f'-Dprojectseele.r45BeValidityOutput={out/"be_registry_actual.json"}']
    spec['command'][1:1]=props;write(out/'launch.json',spec);write(out/'prepared.json',dict(bound=True,source_and_QA_world_written=False,QA_world_copied=False,Java_MC_started=False,walk_execute0_inherit165=True,BE_execute17=True,BE_parent9_not_fake17=True,relog_actual_pass=False))
    print('Prepared BE-only SAMEQA relog launch; walk0/inherit165; no MC/world writes.',flush=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['capture','bind']);p.add_argument('--first-run',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--root-exit-code',type=int);p.add_argument('--root-session');p.add_argument('--parent',type=Path);p.add_argument('--compile-log',type=Path);a=p.parse_args()
    if a.mode=='capture':assert a.first_run;capture(a)
    else:assert a.parent and a.compile_log;bind(a)
if __name__=='__main__':main()
