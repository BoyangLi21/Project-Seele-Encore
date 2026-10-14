"""Build one frozen source candidate and verify the actual archived resources."""
import argparse,gzip,hashlib,json,os,shutil,subprocess,time,zipfile
from pathlib import Path
from release_r45_contract import class_protocol

ROOT=Path(__file__).resolve().parents[1]
BASE=Path('D:/eva/artifacts/r51_nonmap_release/selected_assets')
REVIEW=ROOT/'artifacts/r52_hand_uv_material_repair/overlay'
NONMAP_RELEASE=False


def sha(path):
    with path.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()


def snapshot():
    paths=list((ROOT/'src').rglob('*'))+[ROOT/n for n in('build.gradle','settings.gradle','gradle.properties')]
    return {p.relative_to(ROOT).as_posix():sha(p)for p in paths if p.is_file()}


DELIVERY_CLASSES=('com/projectseele/world/StationDepartureBoardBlockEntity.class',
                  'com/projectseele/client/render/StationDepartureBoardRenderer.class',
                  'com/projectseele/network/SeeleNetwork.class',
                  'com/projectseele/world/NervUprightGuidewayR52.class',
                  'com/projectseele/world/NervOuterCarrierGuideR52.class',
                  'com/projectseele/world/NervRootAssemblyInstallationR52.class',
                  'com/projectseele/world/WallArtworkBlockEntity.class',
                  'com/projectseele/client/render/WallArtworkRenderer.class',
                  'com/projectseele/client/TreeOfLifeWallClient.class',
                  'com/projectseele/client/render/NervUprightGuideRendererR52.class',
                  'com/projectseele/network/ClientboundFacilityFrameR52.class',
                  'com/projectseele/world/NervWetFloorSealR52.class',
                  'com/projectseele/world/NervHangarGateGeometryR52.class',
                  'com/projectseele/world/NervHangarGateGeometryR52$Spec.class',
                  'com/projectseele/world/NervHangarGateGeometryR52$BottomSeal.class',
                  'com/projectseele/entity/NervHangarDoorEntity.class',
                  'com/projectseele/world/NervAssemblyOwnerR52.class',
                  'com/projectseele/world/NervLegacyCarrierRideR52.class',
                  'com/projectseele/entity/NervSiloDoorEntity.class',
                  'com/projectseele/world/NervPlantMotionR52.class',
                  'com/projectseele/world/EvaOriginalMeshGeometryR52.class',
                  'com/projectseele/world/FullAssemblyGeometryR52.class',
                  'com/projectseele/world/NervSourcePreparationR52.class',
                  'com/projectseele/world/NervCraneGeometryR52.class',
                  'com/projectseele/world/NervMappedPlugMechanicsR52.class',
                  'com/projectseele/entity/EvaMechanicalFrameR52.class',
                  'com/projectseele/client/render/EvaHeadClearance.class',
                  'com/projectseele/entity/EvaObstacleCollision.class',
                  'com/projectseele/entity/EvaUnit01Entity.class',
                  'com/projectseele/entity/EvaPrototypeEntity.class',
                  'com/projectseele/entity/EvaSprintR50.class',
                  'com/projectseele/entity/EvaMechanicalFrameR52$BeforeServerLoadSubscriberR52.class',
                  'com/projectseele/world/DeadSeaChamberSavedDataR45.class',
                  'com/projectseele/GameEvents.class',
                  'com/projectseele/world/S20LiftDirectoryR52.class',
                  'com/projectseele/world/S20LiftDirectoryR52$State.class',
                  'com/projectseele/world/NervRouteRuntimeR52.class',
                  'com/projectseele/world/NervRouteDirectoryR52.class',
                  'com/projectseele/world/NervRouteRuntimeStateR52.class',
                  'com/projectseele/world/NervLaunchPhasesR53.class',
                  'com/projectseele/world/NervBankHeadTransferR53.class',
                  'com/projectseele/world/NervOriginalCarrierR52.class',
                  'com/projectseele/world/NervLegacyServiceBypassR52.class',
                  'com/projectseele/world/NervLegacyCompactLevelR52.class',
                  'com/projectseele/world/NervLegacyDeepFrameR53.class',
                  'com/projectseele/world/NervLaunchFeedbackR53.class',
                  'com/projectseele/world/NervSiloHatchGeometryR52.class',
                  'com/projectseele/world/NervConvexReliefR53.class',
                  'com/projectseele/entity/SiloHatchMechanism.class',
                  'com/projectseele/entity/SiloHatchMechanism$Spec.class',
                  'com/projectseele/world/GeoFrontHeightR52.class',
                  'com/projectseele/world/GeoFrontBoundedChunkGenerator.class',
                  'com/projectseele/world/SurfaceAngelPlanR52.class',
                  'com/projectseele/world/NervBallisticHandoffR52.class',
                  'com/projectseele/world/NervBallisticHandoffR52$Profile.class')
SOURCE_ASSETS=('assets/projectseele/mesh/upright_outer_captured_r52.json',
               'assets/projectseele/facility/r52_upright_guideway_paths.json',
               'assets/projectseele/mesh/legacy_floor_recesses_r52.json',
               'assets/projectseele/mesh/legacy_service_bypass_r52.json',
               'assets/projectseele/mesh/legacy_compact_level_r52.json',
               'assets/projectseele/mesh/legacy_deep_frame_r53.json',
               'assets/projectseele/mesh/outer_head_transfer_r53.json',
               'assets/projectseele/mesh/cage_lower_telescopes_r52.json')

def delivery_class_pins(archive):
    actual={n:archive.read(n) for n in DELIVERY_CLASSES}
    assert class_protocol(actual[DELIVERY_CLASSES[2]])=='70','Actual protocol70 required'
    assert b'RoomPlaqueR52' in actual[DELIVERY_CLASSES[0]] and b'roomPlaqueR52' in actual[DELIVERY_CLASSES[0]],'Actual board NBT/getter missing'
    assert b'roomPlaqueR52' in actual[DELIVERY_CLASSES[1]],'Actual renderer plaque branch missing'
    assert b'projectseele.r52.upright-captured-paths.v1' in actual[DELIVERY_CLASSES[3]],'Actual guideway parser missing'
    if not NONMAP_RELEASE:
        model=hashlib.sha256(archive.read(SOURCE_ASSETS[0])).hexdigest()
        assert model.encode() in actual[DELIVERY_CLASSES[4]],'Actual guide model/class constant differs'
    assert b'upright_guideway' in actual[DELIVERY_CLASSES[5]] and b'NervUprightGuidewayR52' in actual[DELIVERY_CLASSES[5]],'Actual installation entry omits guideway source'
    assert b'SurfaceFacing' in actual[DELIVERY_CLASSES[6]] and b'Tint' in actual[DELIVERY_CLASSES[6]],'Actual six-face artwork NBT missing'
    assert b'surfaceBasisR52' in actual[DELIVERY_CLASSES[7]] and b'tree_ink' in actual[DELIVERY_CLASSES[7]],'Actual six-face ink renderer missing'
    assert b'tree_ink' in actual[DELIVERY_CLASSES[8]] and b'treeInkPixelR52' in actual[DELIVERY_CLASSES[8]],'Actual local derived ink texture loader missing'
    assert b'readinessForBoundsR52' in actual[DELIVERY_CLASSES[9]] and b'last_draw_frame' in actual[DELIVERY_CLASSES[9]],'Actual static guide GPU readiness renderer missing'
    assert b'uprightGuideSourceSHA' in actual[DELIVERY_CLASSES[10]],'Actual source-carrying facility packet missing'
    assert b'NervWetFloorSealR52' in actual[DELIVERY_CLASSES[12]],'Actual gate factory must include the visible wet-floor seal'
    assert b'FloorSeal' in actual[DELIVERY_CLASSES[15]] and b'readFloorSealR52' in actual[DELIVERY_CLASSES[15]],'Actual floor seal cold-load codec missing'
    floor_sha=hashlib.sha256(archive.read(SOURCE_ASSETS[2])).hexdigest()
    assert b'mesh/legacy_floor_recesses_r52.json' in actual[DELIVERY_CLASSES[17]] and floor_sha.encode() in actual[DELIVERY_CLASSES[17]],'Actual shared legacy floor overlay and checked class constant differ'
    assert b'openClasspathResourceR52' in actual[DELIVERY_CLASSES[20]] and b'selectedUnionPathR52' in actual[DELIVERY_CLASSES[20]],'Actual selected Forge Union resource stream missing'
    assert b'selectedClasspathProviderR52' in actual[DELIVERY_CLASSES[21]] and b'checkedClasspath' in actual[DELIVERY_CLASSES[21]],'Actual strictly checked provider cache missing'
    assert b'ThreadPoolExecutor' in actual[DELIVERY_CLASSES[22]] and b'getNow' in actual[DELIVERY_CLASSES[22]],'Actual bounded nonblocking source preparation missing'
    assert b'classpathReadyR52' in actual[DELIVERY_CLASSES[23]],'Actual crane source readiness/cache missing'
    assert b'selectedClasspathProviderR52' in actual[DELIVERY_CLASSES[24]],'Actual mapped plug selected source reuse missing'
    nested=actual['com/projectseele/entity/EvaMechanicalFrameR52$BeforeServerLoadSubscriberR52.class']
    assert b'ServerAboutToStartEvent' in nested and b'prepareBeforeServerLoadR52' in nested and b'forName' in nested and b'EvaUnit01Entity' in nested,'Actual nested cold source prewarm/parent class-init entry missing'
    return {n:hashlib.sha256(data).hexdigest() for n,data in actual.items()}

def source_asset_pins():
    selected=('assets/projectseele/eva/ordinary_standing_support_hulls_r52.json',
              'assets/projectseele/eva/prone_leg_support_hulls_r52.json') if NONMAP_RELEASE else SOURCE_ASSETS
    return {n:sha(ROOT/'src/main/resources'/n) for n in selected}


SOUND_CATALOG='assets/projectseele/sounds.json'
REVIEWED_SOUND_CATALOG_SHA='8872f82650ad766cf5bb51f94c5dc5b99d70aee5655372f65845d2c14c2f4016'
REVIEWED_LAUNCH_SOUND_DEFINITIONS={
    'launch_electric_burst_r53':{'subtitle':'subtitles.projectseele.launch_electric_burst_r53',
        'sounds':[{'name':'projectseele:launch_electric_burst_r53','stream':False}]},
    'launch_rail_friction_r53':{'subtitle':'subtitles.projectseele.launch_rail_friction_r53',
        'sounds':[{'name':'projectseele:launch_rail_friction_r53_'+str(i),'stream':False} for i in range(3)]}}


def source_sounds_catalog_pin(frozen_source_sha256):
    """Only the reviewed catalog adds the two original launch sound definitions."""
    source=ROOT/'src/main/resources'/SOUND_CATALOG;baseline=BASE/SOUND_CATALOG
    frozen=json.loads((BASE/'ASSET_FROZEN.json').read_text('utf8'))['files']
    assert frozen_source_sha256==REVIEWED_SOUND_CATALOG_SHA and sha(source)==frozen_source_sha256, 'Frozen reviewed Source sound catalog changed'
    assert sha(baseline)==frozen[SOUND_CATALOG], 'Original frozen sound catalog changed'
    original=json.loads(baseline.read_text('utf-8-sig'));current=json.loads(source.read_text('utf-8-sig'))
    assert len(original)==88 and len(current)==90 and set(current)==set(original)|set(REVIEWED_LAUNCH_SOUND_DEFINITIONS), 'Only the exact two new launch events may extend the original88 sound catalog'
    assert all(current[name]==definition for name,definition in original.items()), 'An original sound definition changed'
    assert {name:current[name] for name in REVIEWED_LAUNCH_SOUND_DEFINITIONS}==REVIEWED_LAUNCH_SOUND_DEFINITIONS, 'Reviewed original launch sound definitions changed'
    return dict(path=str(source.resolve()),source_sha256=frozen_source_sha256,baseline_sha256=frozen[SOUND_CATALOG],
                original_definitions_unchanged=88,source_definitions=90,exact_added_definitions=REVIEWED_LAUNCH_SOUND_DEFINITIONS)


REVIEWED_LAUNCH_SUBTITLES={
    'assets/projectseele/lang/en_us.json':dict(
        sha256='91855638c578e79569b31816a1174113c9f84be0efe264274fe76effb50723a4',original_count=324,
        added={'subtitles.projectseele.launch_electric_burst_r53':'Launch rails discharge',
               'subtitles.projectseele.launch_rail_friction_r53':'Launch rails spark and scrape'}),
    'assets/projectseele/lang/zh_cn.json':dict(
        sha256='0cd4e92c8d3169523546ab474c8dcc81111fe7d5cf9e2047e650788842dd891f',original_count=326,
        added={'subtitles.projectseele.launch_electric_burst_r53':'\u53d1\u5c04\u8f68\u9053\uff1a\u7535\u6d41\u7206\u53d1',
               'subtitles.projectseele.launch_rail_friction_r53':'\u53d1\u5c04\u8f68\u9053\uff1a\u9ad8\u901f\u6469\u64e6'})}


def source_launch_subtitle_pins(frozen_source_sha256):
    """Hard-pin only the reviewed two locale additions; keep every old value."""
    assert set(frozen_source_sha256)==set(REVIEWED_LAUNCH_SUBTITLES), 'Exact two frozen locale files required'
    frozen=json.loads((BASE/'ASSET_FROZEN.json').read_text('utf8'))['files'];files={}
    for name,reviewed in REVIEWED_LAUNCH_SUBTITLES.items():
        source=ROOT/'src/main/resources'/name;baseline=BASE/name
        assert frozen_source_sha256[name]==reviewed['sha256'] and sha(source)==reviewed['sha256'], 'Frozen reviewed Source locale changed: '+name
        assert sha(baseline)==frozen[name], 'Original frozen locale changed: '+name
        original=json.loads(baseline.read_text('utf-8-sig'));current=json.loads(source.read_text('utf-8-sig'))
        assert len(original)==reviewed['original_count'] and len(current)==len(original)+2, 'Reviewed locale key counts changed: '+name
        assert set(current)==set(original)|set(reviewed['added']), 'Only exact two launch subtitle keys may be added: '+name
        assert all(current[key]==value for key,value in original.items()), 'An original locale value changed: '+name
        assert {key:current[key] for key in reviewed['added']}==reviewed['added'], 'Reviewed launch subtitle value changed: '+name
        files[name]=dict(path=str(source.resolve()),source_sha256=reviewed['sha256'],baseline_sha256=frozen[name],
                        original_definitions_unchanged=len(original),source_definitions=len(current),exact_added_definitions=reviewed['added'])
    return files


MECHANICAL_CRANE_PROC_R61='assets/projectseele/eva/actual_crane_procedural_triangles_r52.json.gz'
MECHANICAL_CRANE_GZIP_R61='a12a1f1b47ddf852a8a6e5165def8739c6a1698a4c672ad55fa7d7b30985258b'
MECHANICAL_CRANE_JSON_R61='6e2f2aba5d3f70ebd418ad0606394a86c9b21bf049eb65bd9425d124de25f8aa'
MECHANICAL_CRANE_ORIGINAL_GZIP_R63='366cbc5d927d4b6655d32deb40169313390725a44d61700321096d4d559f6ca2'
MECHANICAL_CRANE_ORIGINAL_JSON_R63='3411018955aec9b8827dcfcc217275fffd3edbe8880d448500f06beefd216064'


def source_mechanical_crane_pin_r61(frozen_source_sha256):
    # Only exact reviewed61 or Root-reviewed original63 restoration; no hash wildcard.
    source=ROOT/'src/main/resources'/MECHANICAL_CRANE_PROC_R61
    versions={MECHANICAL_CRANE_GZIP_R61:MECHANICAL_CRANE_JSON_R61,
              MECHANICAL_CRANE_ORIGINAL_GZIP_R63:MECHANICAL_CRANE_ORIGINAL_JSON_R63}
    assert frozen_source_sha256 in versions and sha(source)==frozen_source_sha256, 'Exact reviewed crane Source gzip changed'
    raw=gzip.decompress(source.read_bytes());raw_sha=hashlib.sha256(raw).hexdigest()
    assert raw_sha==versions[frozen_source_sha256], 'Exact reviewed crane uncompressed Source changed'
    doc=json.loads(raw);assert doc['schema']=='projectseele.r52.actual-crane-procedural-triangles.v1'
    assert set(doc['parts'])=={'top','yoke','sheave','wheel','links','rope'} and sum(len(a)//9 for a in doc['parts'].values())==28044, 'Complete actual six-part procedural Source required'
    row=dict(member=MECHANICAL_CRANE_PROC_R61,source_path=str(source.resolve()),source_gzip_sha256=frozen_source_sha256,
             source_json_sha256=raw_sha,source_geometry_delta=True,model_scope='Only reviewed top motors and first hose; all other parts/anchors unchanged')
    if frozen_source_sha256==MECHANICAL_CRANE_ORIGINAL_GZIP_R63:
        row.update(original_restore=True,all_geometry_equal=False,
                   model_scope='Root-reviewed original_restore: undo motor +.57m/first-hose geometry; restore exact original procedural source, not all-geometry equivalence')
    return row

def frozen_build_class_pins(receipt_path,jar):
    receipt_path=Path(receipt_path).resolve();jar=Path(jar).resolve();report=json.loads(receipt_path.read_text('utf-8-sig'))
    source=json.loads((receipt_path.parent/'SOURCE_BEFORE.json').read_text('utf-8-sig'))
    assert report['build_exit']==0 and report['changed_during_build']==[] and report['source_files']==len(source) and snapshot()==source,'Final successful unchanged source build required'
    assert Path(report['jar']).resolve()==jar and jar.parent==receipt_path.parent and sha(jar)==report['sha256'] and jar.stat().st_size==report['bytes'],'Same exact final built Jar required'
    with zipfile.ZipFile(jar) as archive:
        pins=delivery_class_pins(archive);assets=source_asset_pins()
        assert report['protocol']=='70' and pins==report['required_delivery_classes'] and assets==report['required_source_assets'],'Final compiled delivery class/source pins differ'
        for n,h in assets.items():assert hashlib.sha256(archive.read(n)).hexdigest()==h,'Actual guideway asset differs: '+n
        if 'source_mechanical_crane_r61' in report:
            crane=source_mechanical_crane_pin_r61(source['src/main/resources/'+MECHANICAL_CRANE_PROC_R61])
            actual=archive.read(MECHANICAL_CRANE_PROC_R61)
            readbacks=dict(gzip_sha256=hashlib.sha256(actual).hexdigest(),json_sha256=hashlib.sha256(gzip.decompress(actual)).hexdigest())
            assert report['source_mechanical_crane_r61']==dict(source=crane,actual_jar_readbacks=readbacks,exact_source_readbacks=True), 'Frozen mechanical61 readback row changed'
            assert readbacks==dict(gzip_sha256=crane['source_gzip_sha256'],json_sha256=crane['source_json_sha256']), 'Frozen mechanical61 actual Jar bytes differ'
    return pins


def target_changed_java(out,before,previous_path,compile_state_path):
    """Compile the actual repair delta, then retain only untouched cached bytes."""
    previous_path=Path(previous_path).resolve();compile_state_path=Path(compile_state_path).resolve()
    assert previous_path.is_relative_to(ROOT/'artifacts') and previous_path.name=='BUILD_RECEIPT.json'
    previous=json.loads(previous_path.read_text('utf-8-sig'))
    old=json.loads((previous_path.parent/'SOURCE_BEFORE.json').read_text('utf-8-sig'))
    assert previous['build_exit']==0 and not previous['changed_during_build']
    assert set(before)==set(old),'Incremental repair cannot add/remove build inputs'
    changed=sorted(n for n in before if before[n]!=old[n])
    allowed_resource_repairs={'src/main/resources/data/projectseele/dimension_type/geofront.json','src/main/resources/assets/projectseele/models/block/entry_plug_bridge_fascia.json'}
    resource_changes=[n for n in changed if n in allowed_resource_repairs]
    changed=[n for n in changed if n not in allowed_resource_repairs]
    assert changed and all(n.startswith('src/main/java/') and n.endswith('.java') for n in changed),'Only explicit production Java and selected rollback resources allowed'
    assert sha(Path(previous['jar']))==previous['sha256']
    assert sha(ROOT/'build/libs/projectseele-0.1.0-all.jar')==previous['sha256'],'Actual prior full-build cache Jar differs'
    state=json.loads(compile_state_path.read_text('utf-8-sig'))
    base=Path(state['destination']).resolve();assert base==(ROOT/'build/classes/java/main').resolve()
    assert str(state['sourceCompatibility'])==str(state['targetCompatibility'])=='17'
    assert state['compilerArgs']==[],'Repair sources require reviewing nonempty compile processor options'
    prefixes=[n.removeprefix('src/main/java/').removesuffix('.java') for n in changed]
    def belongs(name):return any(name==p+'.class' or name.startswith(p+'$') for p in prefixes)
    cached={p.relative_to(base).as_posix():sha(p) for p in base.rglob('*.class')}
    assert all(p+'.class' in cached for p in prefixes)
    temp=out/'target_classes';temp.mkdir();empty=out/'empty_sourcepath';empty.mkdir()
    cp=[str(base)]+state['classpath'];assert all(Path(p).exists() for p in cp)
    values=['-encoding','UTF-8','-proc:none','-implicit:none','-source','17','-target','17','-g',
            '-sourcepath',str(empty),'-classpath',';'.join(cp),'-d',str(temp)]+[str(ROOT/n) for n in changed]
    for n in changed:assert '@Mixin' not in (ROOT/n).read_text('utf8'),'Target mode does not regenerate mixin metadata'
    argument=out/'TARGET_JAVAC.args';argument.write_text('\n'.join('"'+v.replace('\\','/').replace('"','\\"')+'"' for v in values)+'\n','utf8')
    javac=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/javac.exe')
    with(out/'target_javac.log').open('wb') as log:
        result=subprocess.run([str(javac),'-J-Xmx512m','@'+str(argument)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000 if os.name=='nt' else 0)
    assert result.returncode==0,(out/'target_javac.log').read_text('utf8',errors='replace')[-4000:]
    emitted={p.relative_to(temp).as_posix():sha(p) for p in temp.rglob('*.class')}
    assert all(p+'.class' in emitted for p in prefixes) and all(belongs(n) for n in emitted),'Unexpected implicit compilation output'
    assert snapshot()==before,'Source changed during targeted repair compilation'
    backup=out/'previous_target_classes';backup.mkdir()
    removed=[]
    for n in cached:
        if belongs(n):
            target=(base/n).resolve();assert target.is_relative_to(base)
            copy=backup/n;copy.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,copy);target.unlink();removed.append(n)
    for n in emitted:
        target=base/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(temp/n,target);assert sha(target)==emitted[n]
    assert all(sha(base/n)==h for n,h in cached.items() if not belongs(n)),'Untouched class cache changed'
    evidence=dict(mode='FRESH_TARGET_JAVAC_PLUS_COMPLETE_ASSEMBLE_JARJAR_REOBF',previous_build_context=str(previous_path),
        previous_build_receipt_sha256=sha(previous_path),compile_state=str(compile_state_path),compile_state_sha256=sha(compile_state_path),
        changed_production_sources={n:before[n] for n in changed},changed_resource_sources={n:before[n] for n in resource_changes},unchanged_source_count=len(before)-len(changed)-len(resource_changes),
        unchanged_sources_match_previous_sha256=True,target_javac_exit=0,old_top_and_inner_classes_removed=removed,
        emitted_named_classes=emitted,reused_named_classes={n:h for n,h in cached.items() if not belongs(n)},
        old_receipt_relabelled=False,old_jar_patched=False,new_full_reobfuscation_required=True)
    (out/'INCREMENTAL_COMPILATION_RECEIPT.json').write_text(json.dumps(evidence,indent=2),'utf8')
    return evidence


def main():
    global NONMAP_RELEASE
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=int,required=True)
    ap.add_argument('--nonmap-release',action='store_true',help='Verify active R50 support assets; deferred generated map triangles are not required')
    ap.add_argument('--incremental-from',type=Path);ap.add_argument('--compile-state',type=Path);a=ap.parse_args()
    NONMAP_RELEASE=a.nonmap_release
    if NONMAP_RELEASE:
        assert 'mapRebuildEnabledR52(){return false;}' in (ROOT/'src/main/java/com/projectseele/world/NervRouteRuntimeR52.java').read_text('utf8')
    assert bool(a.incremental_from)==bool(a.compile_state),'Both actual prior build and exported Gradle compile state required'
    out=ROOT/f'artifacts/r52_unified_candidate{a.candidate}';assert not out.exists();out.mkdir()
    before=snapshot();(out/'SOURCE_BEFORE.json').write_text(json.dumps(before,indent=2),'utf8')
    env=dict(os.environ);env['JAVA_HOME']='C:/Users/liboy/jdks/jdk-17.0.19+10'
    incremental=target_changed_java(out,before,a.incremental_from,a.compile_state) if a.incremental_from else None
    args=['cmd.exe','/d','/c',str(ROOT/'gradlew.bat'),'--offline','-Dfile.encoding=UTF-8',
          '-Pr47FinalAssets='+str(BASE),'-Pr52ReviewedAssets='+str(REVIEW)]
    # assemble also builds an unused plain Jar. The selected delivery is the
    # complete jarJar output with its own reobfJarJar finalizer and manifest.
    args+=['assemble','-x','compileJava','-x','jar','-x','reobfJar'] if incremental else ['build']
    started=time.monotonic()
    with(out/'build.log').open('wb')as log:r=subprocess.run(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    after=snapshot();changed=[p for p in before.keys()|after.keys()if before.get(p)!=after.get(p)]
    report=dict(build_exit=r.returncode,elapsed_seconds=time.monotonic()-started,source_files=len(before),nonmap_release=NONMAP_RELEASE,
                changed_during_build=changed,native_verified=False,mechanical_full_chain_ready=False)
    if incremental:
        base=ROOT/'build/classes/java/main'
        assert all(sha(base/n)==h for n,h in incremental['reused_named_classes'].items()),'Untouched compiled cache changed during assemble'
        assert all(sha(base/n)==h for n,h in incremental['emitted_named_classes'].items()),'New repair class changed during assemble'
        report.update(gradle_task='assemble -x compileJava -x jar -x reobfJar; complete selected jarJar/reobfJarJar finalizer retained',
            non_delivered_plain_jar_task_skipped=True,
            compilation_mode=incremental['mode'],incremental_compilation_receipt=str(out/'INCREMENTAL_COMPILATION_RECEIPT.json'),
            incremental_compilation_receipt_sha256=sha(out/'INCREMENTAL_COMPILATION_RECEIPT.json'),
            full_check_suite_rerun=False,repair_regression_and_native_still_required=True)
    (out/'BUILD_RECEIPT.json').write_text(json.dumps(report,indent=2),'utf8')
    assert r.returncode==0,(out/'build.log').read_text('utf8',errors='replace')[-5000:]
    assert not changed,changed
    expected={n:sha(BASE/n)for n in json.loads((BASE/'ASSET_FROZEN.json').read_text('utf8'))['files']if n.startswith(('assets/','META-INF/licenses/'))}
    assert len(expected)==803 and SOUND_CATALOG in expected, 'Exact original803 asset inventory required'
    sounds=source_sounds_catalog_pin(before['src/main/resources/'+SOUND_CATALOG])
    subtitles=source_launch_subtitle_pins({n:before['src/main/resources/'+n] for n in REVIEWED_LAUNCH_SUBTITLES})
    crane_r61=source_mechanical_crane_pin_r61(before['src/main/resources/'+MECHANICAL_CRANE_PROC_R61])
    for row in json.loads((REVIEW.parent/'FINAL_OVERLAY_RECEIPT.json').read_text('utf8'))['files']:
        assert sha(REVIEW/row['path'])==row['sha256'];expected[row['path']]=row['sha256']
    model='assets/projectseele/models/block/entry_plug_bridge_fascia.json';expected[model]=sha(ROOT/'src/main/resources'/model)
    expected[SOUND_CATALOG]=sounds['source_sha256'];assert len(expected)==803, 'Sound catalog must replace exactly one existing asset entry'
    for name,row in subtitles.items():
        assert name in expected, 'Original locale inventory missing: '+name
        expected[name]=row['source_sha256']
    assert len(expected)==803, 'Sound and two locales must replace exactly three existing asset entries'
    jar=out/'projectseele-0.1.0-all.jar';shutil.copyfile(ROOT/'build/libs'/jar.name,jar)
    with zipfile.ZipFile(jar)as z:
        assert len(z.namelist())==len(set(z.namelist()))
        for n,d in expected.items():assert hashlib.sha256(z.read(n)).hexdigest()==d,n
        subtitle_readbacks={n:hashlib.sha256(z.read(n)).hexdigest() for n in subtitles}
        assert subtitle_readbacks=={n:row['source_sha256'] for n,row in subtitles.items()}, 'Actual Jar locale readbacks differ from frozen Source'
        protocol=class_protocol(z.read('com/projectseele/network/SeeleNetwork.class'));class_pins=delivery_class_pins(z);source_pins=source_asset_pins()
        for n,h in source_pins.items():assert hashlib.sha256(z.read(n)).hexdigest()==h,n
        crane_gzip=z.read(MECHANICAL_CRANE_PROC_R61);crane_readbacks=dict(gzip_sha256=hashlib.sha256(crane_gzip).hexdigest(),json_sha256=hashlib.sha256(gzip.decompress(crane_gzip)).hexdigest())
        assert crane_readbacks==dict(gzip_sha256=crane_r61['source_gzip_sha256'],json_sha256=crane_r61['source_json_sha256']), 'Actual61 Jar mechanical Source readback differs'
        for n in('BoundedNativeCollisionGroupsR52','NervStaticSpatialIndexR52'):assert f'com/projectseele/world/{n}.class'in z.namelist()
    named=ROOT/'build/classes/java/main'
    named_pins={p.relative_to(named).as_posix():sha(p) for p in named.rglob('*.class')}
    assert named_pins and all(n in named_pins for n in DELIVERY_CLASSES),'Same build named production classes required for offline source reports'
    named_file=out/'NAMED_PRODUCTION_CLASSES.json';named_file.write_text(json.dumps(named_pins,indent=2)+'\n','utf8')
    report.update(jar=str(jar),sha256=sha(jar),bytes=jar.stat().st_size,protocol=protocol,asset_readbacks=len(expected),required_delivery_classes=class_pins,required_source_assets=source_pins,source_asset_readbacks=len(source_pins),source_sounds_catalog=sounds,named_class_directory=str(named.resolve()),named_class_manifest=str(named_file.resolve()),named_class_manifest_sha256=sha(named_file))
    report['source_launch_subtitles']=dict(files=subtitles,actual_jar_readbacks=subtitle_readbacks,exact_source_readbacks=True)
    report['source_mechanical_crane_r61']=dict(source=crane_r61,actual_jar_readbacks=crane_readbacks,exact_source_readbacks=True)
    (out/'BUILD_RECEIPT.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
