"""Build one frozen source candidate and verify the actual archived resources."""
import argparse,hashlib,json,os,shutil,subprocess,time,zipfile
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
                  'com/projectseele/world/S20LiftDirectoryR52$State.class')
SOURCE_ASSETS=('assets/projectseele/mesh/upright_outer_captured_r52.json',
               'assets/projectseele/facility/r52_upright_guideway_paths.json',
               'assets/projectseele/mesh/legacy_floor_recesses_r52.json')

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

def frozen_build_class_pins(receipt_path,jar):
    receipt_path=Path(receipt_path).resolve();jar=Path(jar).resolve();report=json.loads(receipt_path.read_text('utf-8-sig'))
    source=json.loads((receipt_path.parent/'SOURCE_BEFORE.json').read_text('utf-8-sig'))
    assert report['build_exit']==0 and report['changed_during_build']==[] and report['source_files']==len(source) and snapshot()==source,'Final successful unchanged source build required'
    assert Path(report['jar']).resolve()==jar and jar.parent==receipt_path.parent and sha(jar)==report['sha256'] and jar.stat().st_size==report['bytes'],'Same exact final built Jar required'
    with zipfile.ZipFile(jar) as archive:
        pins=delivery_class_pins(archive);assets=source_asset_pins()
        assert report['protocol']=='70' and pins==report['required_delivery_classes'] and assets==report['required_source_assets'],'Final compiled delivery class/source pins differ'
        for n,h in assets.items():assert hashlib.sha256(archive.read(n)).hexdigest()==h,'Actual guideway asset differs: '+n
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
    for row in json.loads((REVIEW.parent/'FINAL_OVERLAY_RECEIPT.json').read_text('utf8'))['files']:
        assert sha(REVIEW/row['path'])==row['sha256'];expected[row['path']]=row['sha256']
    model='assets/projectseele/models/block/entry_plug_bridge_fascia.json';expected[model]=sha(ROOT/'src/main/resources'/model)
    jar=out/'projectseele-0.1.0-all.jar';shutil.copyfile(ROOT/'build/libs'/jar.name,jar)
    with zipfile.ZipFile(jar)as z:
        assert len(z.namelist())==len(set(z.namelist()))
        for n,d in expected.items():assert hashlib.sha256(z.read(n)).hexdigest()==d,n
        protocol=class_protocol(z.read('com/projectseele/network/SeeleNetwork.class'));class_pins=delivery_class_pins(z);source_pins=source_asset_pins()
        for n,h in source_pins.items():assert hashlib.sha256(z.read(n)).hexdigest()==h,n
        for n in('BoundedNativeCollisionGroupsR52','NervStaticSpatialIndexR52'):assert f'com/projectseele/world/{n}.class'in z.namelist()
    report.update(jar=str(jar),sha256=sha(jar),bytes=jar.stat().st_size,protocol=protocol,asset_readbacks=len(expected),required_delivery_classes=class_pins,required_source_assets=source_pins,source_asset_readbacks=len(source_pins))
    (out/'BUILD_RECEIPT.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
