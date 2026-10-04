"""Reuse facility DEV/copy method for actual composedv5; Root-only copy, no JVM."""
from pathlib import Path
import argparse,copy,hashlib,json,shutil,sys
sys.dont_write_bytecode=True
import nbtlib
import prepare_facility_source_session_r45 as old
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45';PREP=ART/'pyramid_components_sol_v1/v5_native_entry_preparation_v1';WORLD=ART/'composition_candidates/R45_source_candidate_20261004_v5_01/world';BASELINE=PREP/'actual_v5_source_baseline.json'
SESSION=ART/'native_facility_session_v1';TARGET=SESSION/'gameDir/saves/SEELE_FIELD_R45_REVIEW'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def source():
    b=read(BASELINE);files={r['relative']:r['sha256']for r in b['files']};assert len(files)==1736 and old.inv(WORLD)==files
    total=sum((WORLD/p).stat().st_size for p in files);assert total==520538757==b['total_bytes']
    b.update(world_id=str(nbtlib.load(WORLD/'dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID']),world_seed=int(nbtlib.load(WORLD/'level.dat')['Data']['WorldGenSettings']['seed']))
    assert b['world_id']=='50ba377e-9053-5dfa-93be-9601e623037c'and b['world_seed']==-3816295015381828007
    return b,files,total
def external(p):
    p=p.resolve();assert not p.exists()and p.is_relative_to(SESSION)and not p.is_relative_to(TARGET)and'saves'not in{v.lower()for v in p.parts};return p
def plan(out):
    out=external(out);b,files,total=source();topology=next(p for p in files if p.startswith('dimensions/projectseele/geofront/data/projectseele_city_rigid_topology_r45_'))
    city=nbtlib.load(WORLD/topology)['data'];assert str(city['Stage'])=='CANDIDATE_DISABLED'and not int(city['RuntimeEnabled'])and not int(city['NativeStructurePassed'])and not any('projectseele_city_rigid_control_r45_'in p for p in files)
    out.mkdir();write(out/'copy_plan.json',dict(schema='projectseele.facility-source-copy-plan-r45.v1',source_world=str(WORLD),target_world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],source_baseline=ref(BASELINE),files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())],file_count=1736,total_bytes=total,actual_city_prestate=dict(topology_relative=topology,actual_topology_stage='CANDIDATE_DISABLED',runtime_enabled=False,native_structure_passed=False,runtime_control_absent=True),role='COMPOSED_V5_FACILITY_COMPONENTS_ONLY',copy_root_must_require_target_absent=True,world_copied=False,source_written=False,parent_composition=b['parent_actual_composition'],parent_readback=b['parent_actual_readback']))
    print('Prepared v5 full1736 copy plan only. Root must archive earlierQA first; no world created.',flush=True)
def copy_root(plan_file,execute):
    assert execute,'Root explicit --execute-root only';p=read(plan_file);assert Path(p['source_world']).resolve()==WORLD.resolve()and p['source_baseline']==ref(BASELINE)
    old.WORLD=WORLD;old.BASELINE=BASELINE;old.source=source
    old.copy_root(plan_file,True)
def bind(args):
    out=external(args.out);b,files,total=source();plan_data=read(args.plan);copied=read(args.plan.parent/'copy_receipt.json')
    assert copied['copy_complete']and not copied['source_written']and Path(copied['target_world']).resolve()==TARGET.resolve()and{r['relative']:r['sha256']for r in copied['files']}==files==old.inv(TARGET)
    required=['world/FacilitySourceAdmissionR45','visual/LiftPassengerR20Review','client/visual/NervSecurityLifecycleR45','client/visual/RegionalStationPhoto','world/NervOperationsConsole','client/visual/FacilityComponentReviewR45']
    assert 'BUILD SUCCESSFUL'in args.compile_log.read_text('utf8',errors='replace')
    for rel in required:
        p=ROOT/f'src/main/java/com/projectseele/{rel}.java';c=ROOT/f'build/classes/java/main/com/projectseele/{rel}.class';assert p.is_file()and c.is_file()and c.stat().st_mtime>=p.stat().st_mtime,'Actual Root source/compile required before binding'
    out.mkdir();epoch=out/'runtime_epoch';epoch.mkdir()
    for label,path in [('classes',ROOT/'build/classes/java/main'),('resources',ROOT/'build/resources/main')]:
        before=old.inv(path);shutil.copytree(path,epoch/label);assert before==old.inv(path)==old.inv(epoch/label)
    spec=read(SESSION/'prepared/launch_base.UNBOUND.json');project=[s.split('%%',1)[1]for s in spec['environment']['MOD_CLASSES'].split(';')if s.startswith('projectseele%%')]
    replace={str(Path(p).resolve()):str(epoch/('classes'if(Path(p)/'com/projectseele/ProjectSeele.class').exists()else'resources'))for p in project}
    spec['environment']['MOD_CLASSES']='projectseele%%'+str(epoch/'resources')+';projectseele%%'+str(epoch/'classes')
    for i,a in enumerate(spec['command']):
        if a in('-cp','-classpath','-p','--module-path'):spec['command'][i+1]=';'.join(replace.get(str(Path(x).resolve()),x)for x in spec['command'][i+1].split(';'))
    deps=read(SESSION/'prepared/DEV_dependency_and_aux_receipt.json')
    epochs=[ref(ROOT/f'src/main/java/com/projectseele/{r}.java')for r in required]+[ref(args.compile_log),ref(PREP/'real_player_cases165.UNBOUND.json'),ref(PREP/'BE9_and_replacements8.UNBOUND.json')]
    epochs+=[ref(p)for p in sorted(epoch.rglob('*'))if p.is_file()]+[dict(path=r['target'],sha256=r['sha256'])for r in deps['dependency_files']]+[ref(SESSION/'prepared/DEV_dependency_and_aux_receipt.json')]
    classes=[dict(resource='/com/projectseele/'+p.relative_to(epoch/'classes/com/projectseele').as_posix(),sha256=sha(p))for p in sorted((epoch/'classes/com/projectseele').rglob('*.class'))if any(p.stem==Path(r).name or p.stem.startswith(Path(r).name+'$')for r in required)]
    binding=dict(schema='projectseele.facility-source-native-binding-r45.v1',test_class='FACILITY_SOURCE_UNPLACED',facility_only=True,world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],city_native_structure_pass=False,active_scopes=['COMPONENT_WALK','COMPONENT_BE'],source_baseline=ref(BASELINE),copy_receipt=ref(args.plan.parent/'copy_receipt.json'),composed_source_v5=dict(composition=b['parent_actual_composition'],actual_readback=b['parent_actual_readback'],original_baseline=ref(ART/'city_atomic_integration_r45/qa_copy_revision_v1/copy_plan_v2/copy_plan.json'),catalog=ref(ART/'pyramid_components_sol_v1/v5_combined_entry_v2/catalog.json')),source_epoch=epochs,runtime_classes=classes,world_files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())if k!='session.lock'],city_source_prestate=plan_data['actual_city_prestate'],fixed_city_files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())if k.startswith('dimensions/projectseele/geofront/data/')and'city'in k.lower()],preworld_receipt_output=str(out/'preworld_admission.json'),source_bytes=total,other_model_private_operator_or_production_activation=False)
    write(out/'native_binding.json',binding);digest=sha(out/'native_binding.json')
    job=dict(schema='projectseele.v5-components-native-job.v1',bound=True,world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=digest,facility_source_test=True,facility_scope='COMPONENT_WALK',walk_inputs=ref(PREP/'real_player_cases165.UNBOUND.json'),BE_inputs=ref(PREP/'BE9_and_replacements8.UNBOUND.json'),output=str(out/'components165_BE17.native.json'))
    write(out/'components.bound.json',job)
    props=[f'-Dprojectseele.nativeFacilityBindingR45={out/"native_binding.json"}',f'-Dprojectseele.nativeFacilityBindingR45SHA256={digest}',f'-Dprojectseele.nativeFacilityAdmissionR45={out/"preworld_admission.json"}', '-Dprojectseele.r45FacilityComponentsReview=true',f'-Dprojectseele.r45FacilityComponentsJob={out/"components.bound.json"}',f'-Dprojectseele.r45FacilityComponentsJobSHA256={sha(out/"components.bound.json")}', '-Dprojectseele.r45BeValidityReview=true','-Dprojectseele.r45BeValidityExportOnStart=true',f'-Dprojectseele.r45BeValidityOutput={out/"be_registry_actual.json"}']
    # The base contains only normal DEV settings; no old lease/City/model job.
    assert not any(a.startswith(('-Dprojectseele.r45City','-Dprojectseele.nativeCandidateBinding'))for a in spec['command'])
    spec['command'][1:1]=props;write(out/'launch.json',spec);write(out/'prepared.json',dict(bound=True,source_v5_full_epoch=True,world_written=False,Java_MC_started=False,first_session_only=True,relog_source_admission_not_yet_implemented=True,legacy90_is_not_new165_pass=True))
    print('Prepared fresh v5 launch only; does not start JVM. Do not reuse binding after execution.',flush=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['plan-copy','copy','bind']);p.add_argument('--out',type=Path);p.add_argument('--plan',type=Path);p.add_argument('--execute-root',action='store_true');p.add_argument('--compile-log',type=Path);args=p.parse_args()
    if args.mode=='plan-copy':assert args.out;plan(args.out)
    elif args.mode=='copy':assert args.plan;copy_root(args.plan.resolve(),args.execute_root)
    else:assert args.plan and args.out and args.compile_log;bind(args)
if __name__=='__main__':main()
