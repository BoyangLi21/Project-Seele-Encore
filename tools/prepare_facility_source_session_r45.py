"""Isolated non-world DEV setup and root-only exact source copy/binding.

runtime writes auxiliary configuration/resources only. copy requires explicit
--execute-root and an absent world; never reads or copies old QA progress.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,os,shutil,sys,msvcrt,zipfile,math
from pathlib import Path
sys.dont_write_bytecode=True
import nbtlib
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha

SESSION=ROOT/'artifacts/rebuild_r45/native_facility_session_v1'
GAME=SESSION/'gameDir';TARGET=GAME/'saves/SEELE_FIELD_R45_REVIEW'
BASE=ROOT/'artifacts/rebuild_r45/city_atomic_integration_r45/qa_settled_endpoint_revision_v1/native_lazy_fold_retract_run_v1/launch.json'
ART=SESSION/'prepared';BUNDLE=ROOT/'artifacts/rebuild_r45/lifts_doors_lifecycle_sol_v2/physical25_combined_v4/bundle.json'

def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def inv(p,lock=None):
    result={}
    for f in sorted(p.rglob('*')):
        if not f.is_file():continue
        key=f.relative_to(p).as_posix()
        if key=='session.lock'and lock is not None:
            at=lock.tell();lock.seek(0);result[key]=hashlib.sha256(lock.read()).hexdigest();lock.seek(at)
        else:result[key]=sha(f)
    return result
def source():
    b=read(BASELINE);expected={r['relative']:r['sha256']for r in b['files']};assert len(expected)==1736 and inv(WORLD)==expected
    size=sum((WORLD/k).stat().st_size for k in expected);assert size==520513536;return b,expected,size

def runtime():
    assert not GAME.exists(),'Preserve earlier runtime; use a named follow-up revision, never overwrite'
    ART.mkdir(parents=True,exist_ok=False);spec=read(BASE);assert len(spec['command'])>50
    runtime=SESSION/'runtime';runtime.mkdir();deps=[];mapping={}
    def copy_file(p):
        p=Path(p).resolve();assert p.is_file();key=str(p).lower()
        if key in mapping:return mapping[key]
        digest=sha(p);dest=runtime/'deps'/digest[:16]/p.name;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():shutil.copy2(p,dest)
        assert sha(p)==digest==sha(dest);mapping[key]=str(dest);deps.append(dict(source=str(p),target=str(dest),sha256=digest,bytes=p.stat().st_size));return str(dest)
    def snapshot(p,name):
        p=Path(p).resolve();before=inv(p);dest=runtime/name;shutil.copytree(p,dest);assert inv(dest)==before==inv(p)
        return dest,dict(source=str(p),target=str(dest),files=before,sha256=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest())
    classes,classes_ref=snapshot(ROOT/'build/classes/java/main','project_classes')
    resources,resources_ref=snapshot(ROOT/'build/resources/main','project_resources')
    assert sha(resources/'assets/projectseele/mesh/tv_shoulder_shells_r44.json')==sha(ROOT/'src/main/resources/assets/projectseele/mesh/tv_shoulder_shells_r44.json')
    old_project={str(Path(e.split('%%',1)[1]).resolve()).lower()for e in spec['environment']['MOD_CLASSES'].split(';')if e.startswith('projectseele%%')}
    def classpath(value):
        result=[]
        for entry in value.split(';'):
            p=Path(entry).resolve()
            if str(p).lower()in old_project:
                if (p/'com/projectseele/ProjectSeele.class').exists():result.append(str(classes))
                else:result.append(str(resources))
            elif p.is_file():result.append(copy_file(p))
            else:assert p.is_dir();result.append(str(p))
        return ';'.join(result)
    cmd=[x for x in spec['command']if not x.startswith(('-Dprojectseele.','-XX:StartFlightRecording=','-Xlog:gc'))]
    for i,a in enumerate(cmd):
        if a in('-cp','-classpath','-p','--module-path'):cmd[i+1]=classpath(cmd[i+1])
        elif a.startswith('-DlegacyClassPath.file='):
            old=Path(a.split('=',1)[1]);lines=old.read_text('utf8').splitlines();new=runtime/'legacy_minecraftClasspath.txt'
            new.write_text('\n'.join(classpath(s)for s in lines if s)+'\n','utf8');cmd[i]='-DlegacyClassPath.file='+str(new)
        elif a.startswith(('-Dmixin.env.refMapRemappingFile=','-Dnet.minecraftforge.gradle.GradleStart.srg.srg-mcp=')):
            k,v=a.split('=',1);cmd[i]=k+'='+copy_file(v)
    cmd[cmd.index('--gameDir')+1]=str(GAME);cmd[cmd.index('--quickPlaySingleplayer')+1]=TARGET.name
    cmd[1:1]=['-Dprojectseele.nativeReviewWorld='+TARGET.name,'-Dprojectseele.strictHighDetail=true']
    spec.update(command=cmd,workingDirectory=str(GAME));spec['environment']['MOD_CLASSES']='projectseele%%'+str(resources)+';projectseele%%'+str(classes)
    # Same verified userdev setup: remapped slim Create plus independently
    # remapped ForgeGradle Flywheel/Ponder/Registrate, no raw universal duplicate.
    required=('create-1.20.1-6.0.8_mapped_official_1.20.1-slim.jar','flywheel-forge-1.20.1-1.0.5_mapped_official_1.20.1.jar','Ponder-Forge-1.20.1-1.0.91_mapped_official_1.20.1.jar','Registrate-MC1.20-1.3.3_mapped_official_1.20.1.jar')
    selected=[r for r in deps if Path(r['source']).name in required];assert {Path(r['source']).name for r in selected}==set(required)
    with zipfile.ZipFile(next(r['target']for r in selected if'create-'in Path(r['source']).name))as z:
        jarjar=json.loads(z.read('META-INF/jarjar/metadata.json'));assert all(r['identifier']['artifact']=='mixinextras-forge'for r in jarjar['jars'])
    GAME.mkdir();aux=[]
    for name in('config','shaderpacks','projectseele-local-maps'):
        src=ROOT/'run'/name;before=inv(src);dest=GAME/name;shutil.copytree(src,dest);assert before==inv(src)==inv(dest);aux.append(dict(source=str(src),target=str(dest),files=before))
    (GAME/'mods').mkdir();assert not any((ROOT/'run/mods').iterdir()),'DEV method expects no duplicate raw mod jars in gameDir'
    packroot=GAME/'resourcepacks';packroot.mkdir()
    for name in('eva_real_model','rotrblocks-v87-128x-2d.zip'):
        src=ROOT/'run/resourcepacks'/name;dest=packroot/name
        if src.is_dir():before=inv(src);shutil.copytree(src,dest);assert before==inv(src)==inv(dest);aux.append(dict(source=str(src),target=str(dest),files=before))
        else:digest=sha(src);shutil.copy2(src,dest);assert sha(src)==digest==sha(dest);aux.append(dict(source=str(src),target=str(dest),sha256=digest))
    options=(ROOT/'run/options.txt').read_bytes();(GAME/'options.txt').write_bytes(options)
    assert(ROOT/'run/options.txt').read_bytes()==options
    # Only selected normal packs; no temporary model study or old QA minimap.
    lines=options.decode('utf8').splitlines();wanted=['vanilla','mod_resources','file/rotrblocks-v87-128x-2d.zip','file/eva_real_model']
    lines=[('resourcePacks:'+json.dumps(wanted,separators=(',',':')))if l.startswith('resourcePacks:')else l for l in lines]
    (GAME/'options.txt').write_text('\n'.join(lines)+'\n','utf8')
    write(ART/'launch_base.UNBOUND.json',spec)
    write(ART/'DEV_dependency_and_aux_receipt.json',dict(base_launch=ref(BASE),dependency_files=deps,Create_complete_remapped_DEV_dependencies=selected,
        project_classes=classes_ref,project_resources=resources_ref,normal_auxiliary=aux,options_source_sha256=hashlib.sha256(options).hexdigest(),options_target_sha256=sha(GAME/'options.txt'),
        gameDir=str(GAME),world_directory_created=False,world_copied=False,old_QA_progress_or_minimap_cache_copied=False,main_run_or_PCL_changed=False,Java_Gradle_MC_started=False,
        final_freeze_must_follow_root_new_admission_bridge_compile=True))
    print('Materialized isolated non-world runtime and full verified DEV dependencies; no saves directory/world created.',flush=True)

def plan_copy(out):
    assert not out.exists() and not out.is_relative_to(WORLD);b,files,total=source();assert not TARGET.exists()
    topology=next(k for k in files if k.startswith('dimensions/projectseele/geofront/data/projectseele_city_rigid_topology_r45_'))
    tag=nbtlib.load(WORLD/topology)['data'];assert str(tag['Stage'])=='CANDIDATE_DISABLED' and not int(tag['RuntimeEnabled'])and not int(tag['NativeStructurePassed'])
    assert not any('projectseele_city_rigid_control_r45_'in k for k in files)
    out.mkdir();plan=dict(schema='projectseele.facility-source-copy-plan-r45.v1',source_world=str(WORLD),target_world=str(TARGET),world_id=b['world_id'],world_seed=b['world_seed'],source_baseline=ref(BASELINE),files=[dict(relative=k,sha256=v)for k,v in sorted(files.items())],file_count=1736,total_bytes=total,
        actual_city_prestate=dict(topology_relative=topology,actual_topology_stage=str(tag['Stage']),runtime_enabled=False,native_structure_passed=False,runtime_control_absent=True),
        role='FACILITY_SOURCE_UNPLACED_ONLY_NOT_DELIVERY_ACCEPTANCE',source_written=False,world_copied=False)
    write(out/'copy_plan.json',plan);print('Exact1736/520513536 source plan prepared; original City unplaced bytes, no world copied.',flush=True)

def copy_root(plan_file,execute):
    assert execute,'Only root --execute-root may copy a world';plan=read(plan_file);assert plan['schema']=='projectseele.facility-source-copy-plan-r45.v1' and Path(plan['target_world']).resolve()==TARGET.resolve()
    b,files,total=source();assert files=={r['relative']:r['sha256']for r in plan['files']}and not TARGET.exists();assert not(plan_file.parent/'copy_receipt.json').exists()
    with(WORLD/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            assert inv(WORLD,lock)==files;TARGET.mkdir(parents=True,exist_ok=False);copied=[]
            for relative,digest in sorted(files.items(),key=lambda r:(r[0]in('level.dat','level.dat_old'),r[0])):
                dest=TARGET/relative;dest.parent.mkdir(parents=True,exist_ok=True)
                if relative=='session.lock':
                    lock.seek(0);data=lock.read();assert hashlib.sha256(data).hexdigest()==digest;dest.write_bytes(data)
                else:
                    with(WORLD/relative).open('rb')as src,dest.open('xb')as dst:shutil.copyfileobj(src,dst,4*1024*1024)
                assert sha(dest)==digest
                if relative!='session.lock':assert sha(WORLD/relative)==digest
                copied.append(dict(relative=relative,sha256=digest))
            assert inv(WORLD,lock)==files==inv(TARGET)
            write(plan_file.parent/'copy_receipt.json',dict(schema='projectseele.facility-source-copy-receipt-r45.v1',copy_complete=True,source_written=False,source_world=str(WORLD),target_world=str(TARGET),world_id=plan['world_id'],world_seed=plan['world_seed'],files=copied,source_baseline=plan['source_baseline'],copy_plan=ref(plan_file),total_bytes=total))
            print('Root exact full source copy/readback complete; no old QA progress used.',flush=True)
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def readback_copy(plan_file):
    plan=read(plan_file);_,expected,total=source();assert Path(plan['target_world']).resolve()==TARGET.resolve() and inv(TARGET)==expected
    receipt=read(plan_file.parent/'copy_receipt.json');assert receipt['copy_complete'] and receipt['total_bytes']==total and not receipt['source_written']
    print('Exact source/physical facility target1736 files and520513536 bytes readback equal; no world bytes written.',flush=True)

def make_binding(args):
    out=args.out.resolve();assert not out.exists() and not out.is_relative_to(TARGET);base,sourcefiles,total=source()
    copyreceipt=read(args.plan.parent/'copy_receipt.json');overlay=read(args.apply_receipt);bundle=read(BUNDLE)
    assert copyreceipt['copy_complete'] and Path(copyreceipt['target_world']).resolve()==TARGET.resolve()
    assert overlay['installed'] and overlay['cells']==25 and Path(overlay['world']).resolve()==TARGET.resolve() and overlay['bundle_sha256']==sha(BUNDLE)
    assert overlay['before_files']==sourcefiles and inv(TARGET)==overlay['after_files'] and not overlay['navigation_or_model_installed']
    assert 'BUILD SUCCESSFUL'in args.compile_log.read_text('utf8',errors='replace')
    require_sources={'world/FacilitySourceAdmissionR45':'runtime_classes','visual/LiftPassengerR20Review':'LIFT90','client/visual/NervSecurityLifecycleR45':'READER5','client/visual/RegionalStationPhoto':'SOURCE_PHOTOS','world/NervOperationsConsole':'NO_CITY_REQUEST'}
    for rel in require_sources:
        src=ROOT/f'src/main/java/com/projectseele/{rel}.java';compiled=ROOT/f'build/classes/java/main/com/projectseele/{rel}.class';assert compiled.exists()and compiled.stat().st_mtime>=src.stat().st_mtime,'Root must actually compile the current admission/bridges'
    # Fresh post-compile non-world epoch, preserving the earlier snapshot.
    epoch=out/'runtime_epoch';epoch.mkdir(parents=True)
    for label,path in [('classes',ROOT/'build/classes/java/main'),('resources',ROOT/'build/resources/main')]:
        before=inv(path);shutil.copytree(path,epoch/label);assert before==inv(path)==inv(epoch/label)
    spec=read(ART/'launch_base.UNBOUND.json');oldenv=spec['environment']['MOD_CLASSES'].split(';');replace={str(Path(s.split('%%',1)[1]).resolve()):str(epoch/('classes'if'project_classes'in s else'resources'))for s in oldenv}
    spec['environment']['MOD_CLASSES']='projectseele%%'+str(epoch/'resources')+';projectseele%%'+str(epoch/'classes')
    for i,a in enumerate(spec['command']):
        if a in('-cp','-classpath'):spec['command'][i+1]=';'.join(replace.get(str(Path(x).resolve()),x)for x in spec['command'][i+1].split(';'))
    source_epoch=[ref(ROOT/'src/main/java/com/projectseele'/f'{rel}.java')for rel in require_sources]+[ref(args.compile_log),ref(BUNDLE)]
    # FML checks the entire frozen input inventory and actual loaded class
    # resources. Source text strings are not admission evidence.
    source_epoch +=[ref(p)for p in sorted(epoch.rglob('*'))if p.is_file()]
    dep=read(ART/'DEV_dependency_and_aux_receipt.json');source_epoch +=[dict(path=r['target'],sha256=r['sha256'])for r in dep['dependency_files']]
    # Forge may normalize ordinary options/config during startup. Their copy
    # receipt is a frozen preparation input; mutable game settings are not the
    # world/device identity authority.
    source_epoch +=[ref(ART/'DEV_dependency_and_aux_receipt.json')]
    runtime_classes=[dict(resource='/com/projectseele/'+str(p.relative_to(epoch/'classes/com/projectseele')).replace('\\','/'),sha256=sha(p))for p in sorted((epoch/'classes/com/projectseele').rglob('*.class'))if any(p.stem==Path(rel).name or p.stem.startswith(Path(rel).name+'$')for rel in require_sources)]
    plan=read(args.plan);city=plan['actual_city_prestate'];mode=args.scope;scope={'lifts':'LIFT90','security':'READER5','photos':'SOURCE_PHOTOS'}[mode]
    binding=dict(schema='projectseele.facility-source-native-binding-r45.v1',test_class='FACILITY_SOURCE_UNPLACED',facility_only=True,world=str(TARGET),world_id=base['world_id'],world_seed=base['world_seed'],city_native_structure_pass=False,active_scopes=[scope],
        source_baseline=ref(BASELINE),copy_receipt=ref(args.plan.parent/'copy_receipt.json'),physical_bundle=ref(BUNDLE),physical_apply_receipt=ref(args.apply_receipt),source_epoch=source_epoch,runtime_classes=runtime_classes,
        world_files=[dict(relative=k,sha256=v)for k,v in sorted(overlay['after_files'].items())if k!='session.lock'],city_source_prestate=city,
        fixed_city_files=[dict(relative=k,sha256=v)for k,v in sorted(sourcefiles.items())if k.startswith('dimensions/projectseele/geofront/data/')and'city'in k.lower()],preworld_receipt_output=str(out/'preworld_admission.json'),
        fixed_scope='Whole source City bytes remain original CANDIDATE_DISABLED/control-absent; no fake MOVE1/READY',active_scope='Only selected facility actors/devices/player movement; no City request or production model/navigation activation')
    if mode=='photos':
        controls=read(ROOT/'artifacts/rebuild_r45/lifts_doors_lifecycle_sol_v2/command_controls_v3/resolved_fixed_controls.json');views=[]
        def view(name,position,target):
            dx,dy,dz=[target[k]-position[k]for k in range(3)];dy-=1.62
            views.append(dict(file=name+'.png',position=position,yaw=math.degrees(math.atan2(-dx,dz)),pitch=-math.degrees(math.atan2(dy,math.hypot(dx,dz))),warmupTicks=220,requiredSections=[],fov=70))
        view('current_deep_14_threshold',[14.5,-566,260.5],[12.5,-565,253.5]);view('current_compact_original_car',[96.5,-393,-46.5],[93.5,-392.5,-52.5]);view('current_two_MTR_port',[99.5,-367,-207.5],[98.5,-365.5,-213.5]);view('current_observer_control_floor',[90.5,-367,-271.5],[35,-365,-278]);view('current_hangar_86_return',[86.5,-394,-267.5],[86.5,-392.5,-271.5]);view('current_105_transition',[105.5,-391,-38.5],[105.5,-389.5,-42.5])
        original=read(Path(bundle['marker']['before_path']))
        for row in controls:
            p=row['contract'][0]['operator'];door=next(d for d in original['doors']if d['id']==row['id']);q=door['lower'];view('current_command_'+str(row['id']),p,[q[0]+.5,q[1]+1,q[2]+.5])
        write(out/'current_source_photo_views.json',views);binding['photo_views']=ref(out/'current_source_photo_views.json')
    write(out/'native_binding.json',binding);digest=sha(out/'native_binding.json')
    props=[f'-Dprojectseele.nativeFacilityBindingR45={out/"native_binding.json"}',f'-Dprojectseele.nativeFacilityBindingR45SHA256={digest}',f'-Dprojectseele.nativeFacilityAdmissionR45={out/"preworld_admission.json"}',
        '-Dprojectseele.r45BeValidityReview=true',f'-Dprojectseele.r45BeValidityOutput={out/"be_registry_actual.json"}']
    write(out/'be_registry_OP_PENDING.json',dict(command='/seele review_be_validity export',required_permission=4,output=str(out/'be_registry_actual.json'),
        automatic_OP_queue_in_existing_lift_runner=False,actual_command_sent=False,actual_export_exists=False,world_chunks_read_or_loaded_by_export=False,
        registration_properties=props[-2:],root_must_send_through_existing_actual_OP_mechanism=True,native_tick_function_pass=False))
    if mode=='lifts':
        job=read(ROOT/'artifacts/rebuild_r45/lifts_doors_lifecycle_sol_v2/physical25_combined_v4/all90_physical_bundle_priority_cases.UNBOUND.json')
        job.update(bound=True,world=str(TARGET),candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=digest,facility_source_test=True,facility_scope='LIFT90');write(out/'all90_lifts.bound.json',job)
        props+=['-Dprojectseele.regionalBuild=r44-lifts',f'-Dprojectseele.r45LiftTripCases={out/"all90_lifts.bound.json"}',f'-Dprojectseele.r44LiftInterfaces={job["interfaces_file"]}',f'-Dprojectseele.r45LiftOutput={out/"lifts90.native.json"}','-Dprojectseele.r40LiftStart=0','-Dprojectseele.r41LiftEnd=90']
    elif mode=='security':
        job=read(ROOT/'artifacts/rebuild_r45/lifts_doors_lifecycle_sol_v2/security_job_v3/nerv_security_native_job.json');job.update(bound=True,world=str(TARGET),candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=digest,facility_source_test=True,facility_scope='READER5');write(out/'readers5.bound.json',job)
        props+=['-Dprojectseele.regionalBuild=r45-nerv-security','-Dprojectseele.r45NervSecurityReview=true',f'-Dprojectseele.r45NervSecurityCases={out/"readers5.bound.json"}',f'-Dprojectseele.r45NervSecurityOutput={out/"security5.native.json"}']
    else:props+=['-Dprojectseele.regionalBuild=r44-facility-photos','-Dprojectseele.photoCaptureHoldTicks=120']
    # Intentionally no TV personnel/model flags and no City job/forced request.
    spec['command'][1:1]=props;write(out/'launch.json',spec);write(out/'prepared.json',dict(bound=True,scope=scope,world_written=False,Java_Gradle_MC_started=False,source_first_session_only=True,
        single_use_admission=True,facility_not_combined_delivery_acceptance=True,other_scopes_need_new_root_source_copy_or_reviewed_named_facility_checkpoint=True,
        supplemental_COMMAND17_MTR2_all80_width_and_raw14_need_current_actual_driver_or_root_inputs=True))
    print('Fresh compiled source facility launch prepared only. Choose ONE scope; never reuse this admission/world epoch after running.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['runtime','plan-copy','copy','readback-copy','bind']);p.add_argument('--out',type=Path);p.add_argument('--plan',type=Path);p.add_argument('--execute-root',action='store_true');p.add_argument('--apply-receipt',type=Path);p.add_argument('--compile-log',type=Path);p.add_argument('--scope',choices=['lifts','security','photos']);a=p.parse_args()
    if a.mode=='runtime':runtime()
    elif a.mode=='plan-copy':assert a.out;plan_copy(a.out.resolve())
    elif a.mode=='copy':assert a.plan;copy_root(a.plan.resolve(),a.execute_root)
    elif a.mode=='readback-copy':assert a.plan;readback_copy(a.plan.resolve())
    else:assert a.plan and a.out and a.apply_receipt and a.compile_log and a.scope;make_binding(a)
