"""Finite restored v13 ID6 sameQA precheck/bind. No world copy/write or JVM."""
from pathlib import Path
import argparse,json,shutil,sys
sys.dont_write_bytecode=True
import prepare_command17_facility_session_r45 as reuse

ROOT=reuse.ROOT;ART=reuse.ART;SESSION=reuse.SESSION;TARGET=reuse.TARGET
OWN=ART/'lifts_doors_lifecycle_sol_v2/command17_short_art_source_v13_v1'
WORLD=ART/'composition_candidates/R45_source_candidate_20261004_tv_finish_v13_01/world'
BASELINE=OWN/'source_v13_full_baseline.json';PLAN=OWN/'copy_plan.UNUSED.json'
INPUTS=OWN/'full141_actual_source_v13.UNBOUND.json';VIEWS=OWN/'short_art_views.consumer_v2.UNBOUND.json'
read=reuse.read;write=reuse.write;sha=reuse.sha;ref=reuse.ref
DIAG=ART/'lifts_doors_lifecycle_sol_v2/command17_first_contact_postrun_job_v2'
COLD=ART/'lifts_doors_lifecycle_sol_v2/command17_first_contact_postrun_job_v1/postrun_inventory_and_firstcontact_job.UNBOUND.json'
def source():
    b=read(BASELINE);files={r['relative']:r['sha256']for r in b['files']}
    assert len(files)==1739 and reuse.old.inv(WORLD)==files==read(WORLD.parent/'composition_tv_finish_readback.json')['full_after_inventory']
    return b,files,b['total_bytes']
def cold():
    b,source_files,total=source();snapshot=read(COLD)
    assert snapshot['schema']=='projectseele.ID6-restored-postrun-first-contact.v1' and Path(snapshot['world']).resolve()==TARGET.resolve()
    assert snapshot['file_count']==1739 and snapshot['parent_root_actual_exit0'] and snapshot['parent_restored']
    expected={r['relative']:r['sha256']for r in snapshot['files']};assert len(expected)==1739 and reuse.old.inv(TARGET)==expected,'Actual cold QA changed; no bind'
    parents={k:snapshot[k]for k in ('parent_binding','parent_admission','parent_result')}
    parents['parent_job']=ref(Path(parents['parent_binding']['path']).with_name('commands.bound.json'))
    for row in parents.values():assert sha(Path(row['path']))==row['sha256'],'Actual parent receipt changed'
    old=read(Path(parents['parent_binding']['path']));result=read(Path(parents['parent_result']['path']));admission=read(Path(parents['parent_admission']['path']));job=read(Path(parents['parent_job']['path']))
    assert result['actual_actor_restored'] and result['original_snapshot_captured'] and result['required_cases']==1 and result['completed_cases']==0
    assert result['first_failure']['current_input']['id']=='cross/6/lane1/from-1' and result['first_failure']['phase']=='WALK'
    assert admission['passed'] and admission['binding_sha256']==parents['parent_binding']['sha256']==job['candidate_binding_sha256']
    assert Path(job['world']).resolve()==TARGET.resolve() and 'postrun_ID6_first_contact'not in old
    assert job['inputs']==ref(INPUTS) and job['short_art_preview_v13']==ref(VIEWS)
    assert {r['relative']:r['sha256']for r in read(PLAN.parent/'copy_receipt.json')['files']}==source_files
    assert all(expected[r['relative']]==source_files[r['relative']]==r['sha256'] for r in old['fixed_city_files'])
    return b,expected,total,dict(cold_snapshot=ref(COLD),**parents),source_files

def precheck(a):
    b,actual,total,parent,source_files=cold()
    receipt=dict(schema='projectseele.ID6-sameQA-readonly-precheck.v1',world=str(TARGET),source_v13_diagnostic_only=True,formal_v14_world_written=False,files1739_exact=True,fixed_city_bytes_unchanged=True,parent=parent,root_confirmed_parent_exec75103_exit0=True,parent_functional_pass=False,parent_strict_restoration_pass=True,changed_since_original_v13_copy=[k for k,v in actual.items()if source_files[k]!=v],new_world_copy_or_world_write=False,Java_started=False,first_contact_scope={'case':'cross/6/lane1/from-1','gameTicks_limit_after_staging_ready':160,'photos':0,'full141':False,'stop_first_assigned_shape_clip':True})
    if a.out:assert not a.out.exists();write(a.out,receipt)
    print('Read-only precheck: exact1739 restored QA; original City bytes unchanged; parent failure retained.',flush=True)
def bind(a):
    assert a.execute_root,'Root chooses actual compile and binding epoch';out=reuse.common.external(a.out);b,files,total,parent,source_files=cold()
    copied=read(PLAN.parent/'copy_receipt.json');assert copied['copy_complete']and not copied['source_written']
    required=['world/FacilitySourceAdmissionR45','visual/LiftPassengerR20Review','client/visual/NervSecurityLifecycleR45','client/visual/RegionalStationPhoto','world/NervOperationsConsole','client/visual/CommandDoorInteractionReviewR45','world/CommandRoomSlidingDoorDirector','entity/NervSlidingDoorEntity','client/render/NervPressureDoorFinishR45','client/render/NervSlidingDoorRenderer']
    assert 'BUILD SUCCESSFUL'in a.compile_log.read_text('utf8',errors='replace')
    for name,rel in [('FacilitySourceAdmissionR45','world/FacilitySourceAdmissionR45'),('CommandDoorInteractionReviewR45','client/visual/CommandDoorInteractionReviewR45')]:
        expected=DIAG/f'{name}.java.candidate.txt'
        if name=='CommandDoorInteractionReviewR45':expected=ART/'lifts_doors_lifecycle_sol_v2/command17_first_contact_material_capture_v1/CommandDoorInteractionReviewR45.candidate.txt'
        assert (ROOT/f'src/main/java/com/projectseele/{rel}.java').read_text('utf8')==expected.read_text('utf8'),'Entire reviewed postrun/material-capture source required; not a string presence check'
    for rel in required:
        p=ROOT/f'src/main/java/com/projectseele/{rel}.java';c=ROOT/f'build/classes/java/main/com/projectseele/{rel}.class';assert c.is_file()and c.stat().st_mtime>=p.stat().st_mtime
    out.mkdir();epoch=out/'runtime_epoch';epoch.mkdir()
    for label,p in [('classes',ROOT/'build/classes/java/main'),('resources',ROOT/'build/resources/main')]:
        before=reuse.old.inv(p);shutil.copytree(p,epoch/label);assert reuse.old.inv(p)==reuse.old.inv(epoch/label)==before
    spec=read(SESSION/'prepared/launch_base.UNBOUND.json');project=[s.split('%%',1)[1]for s in spec['environment']['MOD_CLASSES'].split(';')if s.startswith('projectseele%%')];replace={str(Path(p).resolve()):str(epoch/('classes'if(Path(p)/'com/projectseele/ProjectSeele.class').exists()else'resources'))for p in project}
    spec['environment']['MOD_CLASSES']='projectseele%%'+str(epoch/'resources')+';projectseele%%'+str(epoch/'classes')
    for i,v in enumerate(spec['command']):
        if v in('-cp','-classpath','-p','--module-path'):spec['command'][i+1]=';'.join(replace.get(str(Path(x).resolve()),x)for x in spec['command'][i+1].split(';'))
        elif v.startswith('-DlegacyClassPath.file='):
            original=Path(v.split('=',1)[1]);new=epoch/'legacy_minecraftClasspath.txt';new.write_bytes(('\n'.join(';'.join(replace.get(str(Path(x).resolve()),x)for x in line.split(';'))for line in original.read_text('utf8').splitlines())+'\n').encode());spec['command'][i]='-DlegacyClassPath.file='+str(new)
    deps=read(SESSION/'prepared/DEV_dependency_and_aux_receipt.json')
    origin=dict(actual_readback=ref(WORLD.parent/'composition_tv_finish_readback.json'),parent_readback=ref(ART/'composition_candidates/R45_source_candidate_20261004_v12_01/composition_city_navigation_readback.json'),composition_receipt=ref(WORLD.parent/'composition.json'))
    epochs=[ref(ROOT/f'src/main/java/com/projectseele/{r}.java')for r in required]+[ref(a.compile_log),ref(INPUTS),ref(VIEWS),ref(BASELINE),*origin.values(),*parent.values()]+[ref(p)for p in sorted(epoch.rglob('*'))if p.is_file()]+[dict(path=r['target'],sha256=r['sha256'])for r in deps['dependency_files']]+[ref(SESSION/'prepared/DEV_dependency_and_aux_receipt.json')]
    classes=[dict(resource='/com/projectseele/'+p.relative_to(epoch/'classes/com/projectseele').as_posix(),sha256=sha(p))for p in sorted((epoch/'classes/com/projectseele').rglob('*.class'))if any(p.stem==Path(r).name or p.stem.startswith(Path(r).name+'$')for r in required)]
    topology=next(k for k in files if k.startswith('dimensions/projectseele/geofront/data/projectseele_city_rigid_topology_r45_'))
    import nbtlib
    topology_tag=nbtlib.load(WORLD/topology)['data'];assert str(topology_tag['Stage'])=='CANDIDATE_DISABLED'and not int(topology_tag['RuntimeEnabled'])and not int(topology_tag['NativeStructurePassed'])and not any('projectseele_city_rigid_control_r45_'in k for k in files)
    city=dict(topology_relative=topology,actual_topology_stage='CANDIDATE_DISABLED',runtime_enabled=False,native_structure_passed=False,runtime_control_absent=True)
    binding=dict(schema='projectseele.facility-source-native-binding-r45.v1',test_class='FACILITY_SOURCE_UNPLACED',facility_only=True,world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],city_native_structure_pass=False,active_scopes=['COMMAND17'],source_baseline=ref(BASELINE),copy_receipt=ref(PLAN.parent/'copy_receipt.json'),composed_source_v13=origin,postrun_ID6_first_contact=parent,source_epoch=epochs,runtime_classes=classes,world_files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())if k!='session.lock'],city_source_prestate=city,fixed_city_files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())if k.startswith('dimensions/projectseele/geofront/data/')and'city'in k.lower()],photo_views=ref(VIEWS),preworld_receipt_output=str(out/'preworld_admission.json'),source_bytes=total,other_model_private_operator_or_production_activation=False)
    write(out/'native_binding.json',binding);digest=sha(out/'native_binding.json')
    job=dict(schema='projectseele.command17-native-job.v1',bound=True,world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=digest,facility_source_test=True,facility_scope='COMMAND17',inputs=ref(INPUTS),short_art_preview_v13=ref(VIEWS),first_contact_diagnostic=True,output=str(out/'ID6_first_contact_160tick.native.json'))
    write(out/'commands.bound.json',job)
    props=[f'-Dprojectseele.nativeFacilityBindingR45={out/"native_binding.json"}',f'-Dprojectseele.nativeFacilityBindingR45SHA256={digest}',f'-Dprojectseele.nativeFacilityAdmissionR45={out/"preworld_admission.json"}','-Dprojectseele.r45CommandDoorsReview=true',f'-Dprojectseele.r45CommandDoorsJob={out/"commands.bound.json"}',f'-Dprojectseele.r45CommandDoorsJobSHA256={sha(out/"commands.bound.json")}']
    assert not any(x.startswith(('-Dprojectseele.r45FacilityComponents','-Dprojectseele.r45NervSecurity','-Dprojectseele.r45City','-Dprojectseele.nativeCandidateBinding'))for x in spec['command'])
    spec['command'][1:1]=props;write(out/'launch.json',spec);write(out/'prepared.json',dict(bound=True,actual_one_failed_lane_only=True,same_restored_postrun_QA=True,photos_requested=0,actual_server_gameTicks_limit160=True,stop_first_assigned_shape_clip=True,full141_executed=False,Java_started=False,world_written_by_bind=False,cabin_trip_or_natural_entry_proven=False,full_lifecycle_pass=False))
    print('Root froze restored sameQA ID6 first-contact160tick launch only; no Java/world write.',flush=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['precheck','bind']);p.add_argument('--execute-root',action='store_true');p.add_argument('--compile-log',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    if a.mode=='precheck':precheck(a)
    else:assert a.execute_root and a.compile_log and a.out;bind(a)
if __name__=='__main__':main()
