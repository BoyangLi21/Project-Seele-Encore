"""Finite current v13 one-lane/three-photo preparation; root copies/binds/launches."""
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
def source():
    b=read(BASELINE);files={r['relative']:r['sha256']for r in b['files']}
    assert len(files)==1739 and reuse.old.inv(WORLD)==files==read(WORLD.parent/'composition_tv_finish_readback.json')['full_after_inventory']
    return b,files,b['total_bytes']
def copy_root():
    reuse.old.WORLD=WORLD;reuse.old.BASELINE=BASELINE;reuse.old.source=source;reuse.old.copy_root(PLAN,True)
def bind(a):
    assert a.execute_root,'Root chooses actual compile and binding epoch';out=reuse.common.external(a.out);b,files,total=source();copied=read(PLAN.parent/'copy_receipt.json')
    assert copied['copy_complete']and{r['relative']:r['sha256']for r in copied['files']}==files==reuse.old.inv(TARGET)
    required=['world/FacilitySourceAdmissionR45','visual/LiftPassengerR20Review','client/visual/NervSecurityLifecycleR45','client/visual/RegionalStationPhoto','world/NervOperationsConsole','client/visual/CommandDoorInteractionReviewR45','world/CommandRoomSlidingDoorDirector','entity/NervSlidingDoorEntity','client/render/NervPressureDoorFinishR45','client/render/NervSlidingDoorRenderer']
    assert 'BUILD SUCCESSFUL'in a.compile_log.read_text('utf8',errors='replace')
    for name,rel in [('FacilitySourceAdmissionR45','world/FacilitySourceAdmissionR45'),('CommandDoorInteractionReviewR45','client/visual/CommandDoorInteractionReviewR45')]:
        assert sha(ROOT/f'src/main/java/com/projectseele/{rel}.java')==sha(OWN/f'root_actual202_source_epoch/{name}.java'),'Actual reviewed short source required'
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
    epochs=[ref(ROOT/f'src/main/java/com/projectseele/{r}.java')for r in required]+[ref(a.compile_log),ref(INPUTS),ref(VIEWS),ref(BASELINE),*origin.values()]+[ref(p)for p in sorted(epoch.rglob('*'))if p.is_file()]+[dict(path=r['target'],sha256=r['sha256'])for r in deps['dependency_files']]+[ref(SESSION/'prepared/DEV_dependency_and_aux_receipt.json')]
    classes=[dict(resource='/com/projectseele/'+p.relative_to(epoch/'classes/com/projectseele').as_posix(),sha256=sha(p))for p in sorted((epoch/'classes/com/projectseele').rglob('*.class'))if any(p.stem==Path(r).name or p.stem.startswith(Path(r).name+'$')for r in required)]
    topology=next(k for k in files if k.startswith('dimensions/projectseele/geofront/data/projectseele_city_rigid_topology_r45_'))
    import nbtlib
    topology_tag=nbtlib.load(WORLD/topology)['data'];assert str(topology_tag['Stage'])=='CANDIDATE_DISABLED'and not int(topology_tag['RuntimeEnabled'])and not int(topology_tag['NativeStructurePassed'])and not any('projectseele_city_rigid_control_r45_'in k for k in files)
    city=dict(topology_relative=topology,actual_topology_stage='CANDIDATE_DISABLED',runtime_enabled=False,native_structure_passed=False,runtime_control_absent=True)
    binding=dict(schema='projectseele.facility-source-native-binding-r45.v1',test_class='FACILITY_SOURCE_UNPLACED',facility_only=True,world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],city_native_structure_pass=False,active_scopes=['COMMAND17','SOURCE_PHOTOS'],source_baseline=ref(BASELINE),copy_receipt=ref(PLAN.parent/'copy_receipt.json'),composed_source_v13=origin,source_epoch=epochs,runtime_classes=classes,world_files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())if k!='session.lock'],city_source_prestate=city,fixed_city_files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())if k.startswith('dimensions/projectseele/geofront/data/')and'city'in k.lower()],photo_views=ref(VIEWS),preworld_receipt_output=str(out/'preworld_admission.json'),source_bytes=total,other_model_private_operator_or_production_activation=False)
    write(out/'native_binding.json',binding);digest=sha(out/'native_binding.json')
    job=dict(schema='projectseele.command17-native-job.v1',bound=True,world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=digest,facility_source_test=True,facility_scope='COMMAND17',inputs=ref(INPUTS),short_art_preview_v13=ref(VIEWS),output=str(out/'ID6_one_crossing_three_art_images.native.json'))
    write(out/'commands.bound.json',job)
    props=[f'-Dprojectseele.nativeFacilityBindingR45={out/"native_binding.json"}',f'-Dprojectseele.nativeFacilityBindingR45SHA256={digest}',f'-Dprojectseele.nativeFacilityAdmissionR45={out/"preworld_admission.json"}','-Dprojectseele.r45CommandDoorsReview=true',f'-Dprojectseele.r45CommandDoorsJob={out/"commands.bound.json"}',f'-Dprojectseele.r45CommandDoorsJobSHA256={sha(out/"commands.bound.json")}']
    assert not any(x.startswith(('-Dprojectseele.r45FacilityComponents','-Dprojectseele.r45NervSecurity','-Dprojectseele.r45City','-Dprojectseele.nativeCandidateBinding'))for x in spec['command'])
    spec['command'][1:1]=props;write(out/'launch.json',spec);write(out/'prepared.json',dict(bound=True,actual_one_failed_lane_only=True,three_images_requested=True,full141_executed=False,Java_started=False,world_written_by_bind=False,cabin_trip_or_natural_entry_proven=False,full_lifecycle_pass=False))
    print('Root froze actual v13 one-lane/three-photo launch only; no Java started.')
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['copy','bind']);p.add_argument('--execute-root',action='store_true');p.add_argument('--compile-log',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    assert a.execute_root,'Root-only copy/binding requested'
    if a.mode=='copy':copy_root()
    else:assert a.compile_log and a.out;bind(a)
if __name__=='__main__':main()
