"""Reuse facility DEV/copy path for actual v11 COMMAND17; no JVM launch."""
from pathlib import Path
import argparse,copy,json,shutil,sys
sys.dont_write_bytecode=True
import nbtlib
import prepare_v5_facility_session_r45 as common
import prepare_facility_source_session_r45 as old

ROOT=common.ROOT;ART=common.ART;SESSION=common.SESSION;TARGET=common.TARGET
OWN=ART/'lifts_doors_lifecycle_sol_v2/command17_native_v11_v4'
WORLD=ART/'composition_candidates/R45_source_candidate_20261004_v11_01/world'
BASELINE=OWN/'actual_v11_source_baseline.json';INPUTS=OWN/'command17_cases141.UNBOUND.json'
WAL=ART/'city_transport_xhigh_r45/arrival_stair_and_command_inputs_combined_v11_v1/root_install_v11_01'
read=common.read;write=common.write;sha=common.sha;ref=common.ref
def source():
    b=read(BASELINE);files={r['relative']:r['sha256']for r in b['files']};assert len(files)==1736 and old.inv(WORLD)==files
    actual=read(WORLD.parent/'composition_v11_readback.json');assert actual['phase']=='COMPLETE'and files==actual['full_after_inventory']
    total=sum((WORLD/p).stat().st_size for p in files);assert total==b['total_bytes']
    b.update(world_id=str(nbtlib.load(WORLD/'dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID']),world_seed=int(nbtlib.load(WORLD/'level.dat')['Data']['WorldGenSettings']['seed']))
    assert b['world_id']=='50ba377e-9053-5dfa-93be-9601e623037c'and b['world_seed']==-3816295015381828007
    return b,files,total
def plan(out):
    out=common.external(out);b,files,total=source();topology=next(k for k in files if k.startswith('dimensions/projectseele/geofront/data/projectseele_city_rigid_topology_r45_'))
    tag=nbtlib.load(WORLD/topology)['data'];assert str(tag['Stage'])=='CANDIDATE_DISABLED'and not int(tag['RuntimeEnabled'])and not int(tag['NativeStructurePassed'])and not any('projectseele_city_rigid_control_r45_'in k for k in files)
    out.mkdir();write(out/'copy_plan.json',dict(schema='projectseele.facility-source-copy-plan-r45.v1',source_world=str(WORLD),target_world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],source_baseline=ref(BASELINE),files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())],file_count=1736,total_bytes=total,actual_city_prestate=dict(topology_relative=topology,actual_topology_stage='CANDIDATE_DISABLED',runtime_enabled=False,native_structure_passed=False,runtime_control_absent=True),role='CURRENT_V11_COMMAND17_ONLY_NOT_DELIVERY',copy_root_must_require_target_absent=True,world_copied=False,source_written=False))
    print('Prepared exact actualv11 copy plan only; no world created/copied.',flush=True)
def copy_root(p,execute):
    assert execute,'Root explicit --execute-root only';data=read(p);assert Path(data['source_world']).resolve()==WORLD.resolve()and data['source_baseline']==ref(BASELINE)
    old.WORLD=WORLD;old.BASELINE=BASELINE;old.source=source;old.copy_root(p,True)
def bind(a):
    out=common.external(a.out);b,files,total=source();plan_data=read(a.plan);copied=read(a.plan.parent/'copy_receipt.json')
    assert copied['copy_complete']and not copied['source_written']and{r['relative']:r['sha256']for r in copied['files']}==files==old.inv(TARGET)
    required=['world/FacilitySourceAdmissionR45','visual/LiftPassengerR20Review','client/visual/NervSecurityLifecycleR45','client/visual/RegionalStationPhoto','world/NervOperationsConsole','client/visual/CommandDoorInteractionReviewR45','world/CommandRoomSlidingDoorDirector','entity/NervSlidingDoorEntity']
    assert 'BUILD SUCCESSFUL'in a.compile_log.read_text('utf8',errors='replace')
    for name,rel in [('FacilitySourceAdmissionR45','world/FacilitySourceAdmissionR45'),('CommandDoorInteractionReviewR45','client/visual/CommandDoorInteractionReviewR45')]:
        expected=OWN/(name+('.java.candidate.txt'if name.startswith('Command')else'.candidate.txt'))
        startup=ART/'lifts_doors_lifecycle_sol_v2/command17_startup_ready_fix_v1/CommandDoorInteractionReviewR45.candidate.txt'
        if name=='CommandDoorInteractionReviewR45'and startup.exists():expected=startup
        pair=ART/'lifts_doors_lifecycle_sol_v2/command17_native_pair_and_endpoint_fix_v2/CommandDoorInteractionReviewR45.candidate.txt'
        if name=='CommandDoorInteractionReviewR45'and pair.exists():expected=pair
        assert sha(ROOT/f'src/main/java/com/projectseele/{rel}.java')==sha(expected),'Root exact reviewed current source/compile required'
    for rel in required:
        p=ROOT/f'src/main/java/com/projectseele/{rel}.java';c=ROOT/f'build/classes/java/main/com/projectseele/{rel}.class';assert c.is_file()and c.stat().st_mtime>=p.stat().st_mtime
    out.mkdir();epoch=out/'runtime_epoch';epoch.mkdir()
    for label,p in [('classes',ROOT/'build/classes/java/main'),('resources',ROOT/'build/resources/main')]:
        before=old.inv(p);shutil.copytree(p,epoch/label);assert old.inv(p)==old.inv(epoch/label)==before
    spec=read(SESSION/'prepared/launch_base.UNBOUND.json');project=[s.split('%%',1)[1]for s in spec['environment']['MOD_CLASSES'].split(';')if s.startswith('projectseele%%')];replace={str(Path(p).resolve()):str(epoch/('classes'if(Path(p)/'com/projectseele/ProjectSeele.class').exists()else'resources'))for p in project}
    spec['environment']['MOD_CLASSES']='projectseele%%'+str(epoch/'resources')+';projectseele%%'+str(epoch/'classes')
    for i,v in enumerate(spec['command']):
        if v in('-cp','-classpath','-p','--module-path'):spec['command'][i+1]=';'.join(replace.get(str(Path(x).resolve()),x)for x in spec['command'][i+1].split(';'))
        elif v.startswith('-DlegacyClassPath.file='):
            original=Path(v.split('=',1)[1]);new=epoch/'legacy_minecraftClasspath.txt';lines=[';'.join(replace.get(str(Path(x).resolve()),x)for x in line.split(';'))for line in original.read_text('utf8').splitlines()]
            new.write_bytes(('\n'.join(lines)+'\n').encode('utf8'));spec['command'][i]='-DlegacyClassPath.file='+str(new)
    deps=read(SESSION/'prepared/DEV_dependency_and_aux_receipt.json')
    origin=dict(actual_readback=ref(WORLD.parent/'composition_v11_readback.json'),parent_readback=ref(ART/'composition_candidates/R45_source_candidate_20261004_v10_01/composition_v10_readback.json'),static_WAL=ref(WAL/'run.json'),metadata_WAL=ref(WAL/'command_inputs_metadata_WAL.json'))
    epochs=[ref(ROOT/f'src/main/java/com/projectseele/{r}.java')for r in required]+[ref(a.compile_log),ref(INPUTS),ref(BASELINE),*origin.values()]+[ref(p)for p in sorted(epoch.rglob('*'))if p.is_file()]+[dict(path=r['target'],sha256=r['sha256'])for r in deps['dependency_files']]+[ref(SESSION/'prepared/DEV_dependency_and_aux_receipt.json')]
    classes=[dict(resource='/com/projectseele/'+p.relative_to(epoch/'classes/com/projectseele').as_posix(),sha256=sha(p))for p in sorted((epoch/'classes/com/projectseele').rglob('*.class'))if any(p.stem==Path(r).name or p.stem.startswith(Path(r).name+'$')for r in required)]
    binding=dict(schema='projectseele.facility-source-native-binding-r45.v1',test_class='FACILITY_SOURCE_UNPLACED',facility_only=True,world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],city_native_structure_pass=False,active_scopes=['COMMAND17'],source_baseline=ref(BASELINE),copy_receipt=ref(a.plan.parent/'copy_receipt.json'),composed_source_v11=origin,source_epoch=epochs,runtime_classes=classes,world_files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())if k!='session.lock'],city_source_prestate=plan_data['actual_city_prestate'],fixed_city_files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())if k.startswith('dimensions/projectseele/geofront/data/')and'city'in k.lower()],preworld_receipt_output=str(out/'preworld_admission.json'),source_bytes=total,other_model_private_operator_or_production_activation=False)
    write(out/'native_binding.json',binding);digest=sha(out/'native_binding.json');job=dict(schema='projectseele.command17-native-job.v1',bound=True,world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=digest,facility_source_test=True,facility_scope='COMMAND17',inputs=ref(INPUTS),output=str(out/'COMMAND17_39inputs_102crossings.native.json'))
    write(out/'commands.bound.json',job)
    props=[f'-Dprojectseele.nativeFacilityBindingR45={out/"native_binding.json"}',f'-Dprojectseele.nativeFacilityBindingR45SHA256={digest}',f'-Dprojectseele.nativeFacilityAdmissionR45={out/"preworld_admission.json"}','-Dprojectseele.r45CommandDoorsReview=true',f'-Dprojectseele.r45CommandDoorsJob={out/"commands.bound.json"}',f'-Dprojectseele.r45CommandDoorsJobSHA256={sha(out/"commands.bound.json")}']
    assert not any(x.startswith(('-Dprojectseele.r45FacilityComponents','-Dprojectseele.r45NervSecurity','-Dprojectseele.r45City','-Dprojectseele.nativeCandidateBinding'))for x in spec['command'])
    spec['command'][1:1]=props;write(out/'launch.json',spec);write(out/'prepared.json',dict(bound=True,actual39inputs51bidirectional102=True,walk165_or_BE17_executed=False,source_world_or_QA_copied_written_by_bind=False,Java_MC_started=False,full_lifecycle_pass=False))
    print('Prepared only current COMMAND17 launch; no world/Java writes.',flush=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['plan-copy','copy','bind']);p.add_argument('--out',type=Path);p.add_argument('--plan',type=Path);p.add_argument('--execute-root',action='store_true');p.add_argument('--compile-log',type=Path);a=p.parse_args()
    if a.mode=='plan-copy':assert a.out;plan(a.out)
    elif a.mode=='copy':assert a.plan;copy_root(a.plan.resolve(),a.execute_root)
    else:assert a.plan and a.out and a.compile_log;bind(a)
if __name__=='__main__':main()
