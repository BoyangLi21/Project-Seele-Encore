"""Read-only current-world authority for the explicitly selected 1/2/4 release."""
from pathlib import Path, PurePosixPath
import gzip,hashlib,json,re,copy,zipfile
from root_bundle_authority_r53 import validate_record,original_identities

def need(value,message):
    if not value:raise ValueError(message)

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def read(path):return json.loads(Path(path).read_text('utf-8-sig'))

def safe(name):
    p=PurePosixPath(name)
    need(name and not p.is_absolute() and ':' not in name and '\\' not in name and all(part not in ('','.','..') for part in name.split('/')),'Unsafe selected world metadata path: '+name)
    return name

def pinned_file(path,digest):
    path=Path(path).resolve()
    need(re.fullmatch(r'[0-9a-f]{64}',digest or '') and sha(path)==digest,'Explicit release input SHA differs: '+str(path))
    return path

def context(authority,runtime,identity_file,identity_sha256,baseline_inputs,baseline_inputs_sha256):
    validate_record(authority);world=Path(authority['world'])
    identities=original_identities(identity_file,identity_sha256,world)
    baseline_file=pinned_file(baseline_inputs,baseline_inputs_sha256);packages=read(baseline_file)
    need(set(packages)=={'server','client'},'Exact selected server/client dependency baseline set required')
    for side,row in packages.items():
        source=pinned_file(row['path'],row['sha256'])
        need(source.stat().st_size==row['bytes'],'Selected dependency archive size differs: '+side)
    runtime=Path(runtime).resolve();need(runtime.is_dir() and (runtime/'combat_bundle_r44.json').is_file(),'Actual portable runtime directory required')
    return dict(feature_scope='124',root_world_authority=authority,runtime=runtime.as_posix(),
        original_identities={'path':Path(identity_file).resolve().as_posix(),'sha256':identity_sha256,'count':len(identities)},
        baseline_inputs={'path':baseline_file.as_posix(),'sha256':baseline_inputs_sha256},
        baseline_packages=packages)

def validate_context(record):
    actual=context(record['root_world_authority'],record['runtime'],record['original_identities']['path'],record['original_identities']['sha256'],record['baseline_inputs']['path'],record['baseline_inputs']['sha256'])
    need(actual==record,'Selected release context changed')
    return actual

NAVIGATION_FILES=('nerv_routes_r24.json.gz','nearest_lift_paths_r44.json.gz')
SOURCE_REPORTS={'CURRENT_GUIDEWAY_REPORT.json','CURRENT_SOURCE_ENVELOPES.json',
    'CURRENT_PHYSICAL_READBACK.json','CURRENT_CLOSED_GATE_READBACK.json'}
R57_DELTA_MANIFEST_SHA='a1e6bb7ade3964655f32b140f7cfec0eb89e8b0bad80e8ada86979a665d5d2d9'
R58_DELTA_MANIFEST_SHA='4bbc43a7931395f79a4f5547fb2a84f6330877930efef20a24df0b0d43a61621'
R59_DELTA_MANIFEST_SHA='aed4f38a3cd8920fdf3434b6d72f27768f7d865a7ae075e4709df07bc842fcf5'
R60_DELTA_MANIFEST_SHA='46914e143b05f05af04f35d99730409622ac0ef19dc8ecba421309b1d3ab2e3b'

def reviewed_r57_delta():
    """One reviewed build, with exact old/new bytes; this is not a class-name allowlist."""
    path=Path(__file__).resolve().parent/'data/r57_accepted_authority_exact_delta.json'
    return read(pinned_file(path,R57_DELTA_MANIFEST_SHA))

def reviewed_r58_delta():
    path=Path(__file__).resolve().parent/'data/r58_accepted_authority_exact_delta.json'
    return read(pinned_file(path,R58_DELTA_MANIFEST_SHA))

def reviewed_r59_delta():
    path=Path(__file__).resolve().parent/'data/r59_accepted_authority_exact_delta.json'
    return read(pinned_file(path,R59_DELTA_MANIFEST_SHA))

def reviewed_r60_delta():
    path=Path(__file__).resolve().parent/'data/r60_accepted_authority_exact_delta.json'
    return read(pinned_file(path,R60_DELTA_MANIFEST_SHA))

def reviewed_r57_evidence(d,pins,version=57):
    need(d.get('reviewed_change_evidence')==pins['reviewed_change_evidence'],'R57 reviewed evidence selection differs')
    for row in d['reviewed_change_evidence'].values():reference(row)
    proof=read(reference(d[f'current{version}_source_equivalence']))
    need(proof['current_build_receipt']==d['current_build_receipt'] and proof['source_reports_equal'] is True
         and proof['world_written'] is False and proof[f'native{version}_pass_imported'] is False,
         'Fresh R57 source equivalence is not bound to this build')
    need(set(proof['fresh_source_reports'])=={'CURRENT_GUIDEWAY_REPORT.json','CURRENT_LEGACY_LEAD_REPORT.json',
         'CURRENT_SOURCE_ENVELOPES.json','CURRENT_SPACE_DIRECTORY.json','CURRENT_AIR_SPACE_MERGE.json'}
         and set(proof['previous_source_reports'])==set(proof['fresh_source_reports']),
         'Complete fresh R57 Source output set required')
    for name,row in proof['fresh_source_reports'].items():
        fresh=reference(row);previous=reference(proof['previous_source_reports'][name])
        need(read(fresh)==read(previous),'Fresh R57 geometry output values differ: '+name)
    need(proof['measurement_source_pipeline']==d['measurement_source_pipeline'],'R57 measurement association changed')
    measured=read(reference(d['measurement_source_pipeline']))
    need(measured['source_inputs']['selected_jar']['sha256']==pins['measurement56_jar_sha256'],
         'R57 physical association does not use the actual56 measurement Source')
    for name in SOURCE_REPORTS:
        need(measured['reports'][name]==sha(reference(d['current_reports'][name])),
             'Actual stopped-world measurement bytes changed: '+name)
    before=read(reference(pins['reviewed_change_evidence']['collision_checks']))
    after=read(reference(proof[f'current{version}_compiled_collision_checks']))
    timing=('elapsed_seconds','near1000_baseline_ms','near1000_cached_ms') if version in (58,59,60) else ('elapsed_seconds',)
    for key in timing:before.pop(key);after.pop(key)
    need(before==after,'Actual57 compiled collision lists/control-domain checks differ')
    visual=read(reference(proof[f'current{version}_compiled_visual_checks']))
    need(visual==dict(actual_jar_sha256=pins[f'current{version}_jar_sha256'],actual_mesh_tag='triangle-mesh-15998-p49-c657602b',
         production_contract_source_compiled=True,actual_production_mesh_part_lookup=True,hash_combinations=192,
         positive_checks=2,negative_checks=213,world_or_game_started=False,native_gameplay_pass_claimed=False),
         'Actual57 compiled exact visual contract positive/negative checks differ')
    if version==60:
        manual=read(reference(proof['current60_compiled_manual_npc_checks']))
        need(manual==dict(actual59_original_units=3,positive_checks=9,negative_checks=72,cold_persistent_job_roundtrips=3,
             new_manual_admission_offline_denied=True,nonempty_mission_manual_branch_denied=True,world_or_game_started=False,
             source_geometry_remeasured=False,native60_functional_pass=False),'Actual60 manual NPC/cold progress policy checks differ')
        render=read(reference(proof['current60_compiled_render_cpu_checks']))
        need(render==read(reference(pins['reviewed_change_evidence']['render_cpu_checks'])),
             'Actual60 source clip/rope cached vertices or protected passes differ')
        need(proof.get('functional_policy_change')==pins['functional_policy_change']
             and proof.get('native60_functional_pass') is False,'Manual NPC source change cannot import a functional PASS')
    return proof

def reference(row):
    need(isinstance(row,dict) and {'path','sha256'}<=row.keys(),'Explicit evidence path/SHA required')
    return pinned_file(row['path'],row['sha256'])

def saved_runtime_authority(world):
    import nbtlib
    path=Path(world)/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat'
    before=sha(path);tag=nbtlib.load(path)['data'];need(before==sha(path),'Runtime save changed while reading its accepted authority')
    return dict(path=str(path.resolve()),sha256=before,claimed=bool(int(tag['Claimed'])),epoch=int(tag['Epoch']),
        directory_fingerprint=str(tag['DirectoryFingerprint']),bundle_relative=str(tag['InstallationBundle']),
        bundle_sha256=str(tag['InstallationBundleSHA']),guide_sha256=str(tag.get('UprightGuideSourceSHA','')),
        fault=str(tag.get('Fault','')),jobs=len(tag.get('Jobs',[])),pending_installation='PendingInstallation' in tag)

def compatible_accepted_authority(row,world,build_receipt):
    """Only exact reviewed R56..R60 cases retain actually accepted R55 bytes."""
    file=reference(row);d=read(file)
    if d.get('case')=='r63-original-rig-nonphysical-scope-preserve-epoch53-and-progress':
        from prepare_r63_source_only_compatibility import validate as validate_r63
        return validate_r63(row,world,build_receipt)
    if d.get('case')=='r62-reviewed-publisher-deadband-preserve-epoch53-and-insert42':
        from accepted_authority_r62 import validate as validate_r62
        return validate_r62(row,world,build_receipt)
    if d.get('case')=='r61-reviewed-motor-fit-preserve-epoch53-and-two-jobs':
        from accepted_authority_r61 import validate as validate_r61
        return validate_r61(row,world,build_receipt)
    r57=d.get('case')=='r57-reviewed-query-cache-and-uv-preserve-epoch53'
    r58=d.get('case')=='r58-reviewed-plant-pose-cache-preserve-epoch53'
    r59=d.get('case')=='r59-restored-original-sounds-preserve-epoch53'
    r60=d.get('case')=='r60-reviewed-manual-npc-and-render-preserve-epoch53'
    reviewed=r57 or r58 or r59 or r60;version=60 if r60 else 59 if r59 else 58 if r58 else 57
    need(d.get('schema')=='projectseele.r53.compatible-accepted-authority.v1'
         and (reviewed or d.get('case')=='r56-sbw-loaded-los-preserve-epoch53'),
         'Unknown accepted-authority compatibility case')
    pins=reviewed_r60_delta() if r60 else reviewed_r59_delta() if r59 else reviewed_r58_delta() if r58 else reviewed_r57_delta() if r57 else None
    need(Path(d['world']).resolve()==Path(world).resolve(),'Compatibility refers to another actual World')
    accepted=reference(d['accepted_bundle']);current=reference(d['current_candidate_bundle'])
    old_build_path=reference(d['accepted_build_receipt']);new_build_path=reference(d['current_build_receipt'])
    need(new_build_path==Path(build_receipt).resolve(),'Compatible source build is not the current release build')
    old_build,new_build=read(old_build_path),read(new_build_path)
    old_jar=pinned_file(old_build['jar'],old_build['sha256']);new_jar=pinned_file(new_build['jar'],new_build['sha256'])
    addon='com/projectseele/mixin/SbwDefenseLoadedLosR56Mixin.class'
    old_source=read(old_build_path.parent/'SOURCE_BEFORE.json');new_source=read(new_build_path.parent/'SOURCE_BEFORE.json')
    need(set(new_source)-set(old_source)=={'src/main/java/com/projectseele/mixin/SbwDefenseLoadedLosR56Mixin.java'} and not set(old_source)-set(new_source),
         'Compatible source snapshot added or removed another source')
    changed_source={k for k in old_source if old_source[k]!=new_source[k]}
    need(changed_source==({'src/main/resources/projectseele.mixins.json'}|set(pins['source_delta']) if reviewed else {'src/main/resources/projectseele.mixins.json'}),
         'Compatible source snapshot changed an unreviewed production source')
    if reviewed:
        need(old_build['sha256']==pins['accepted55_jar_sha256'] and new_build['sha256']==pins[f'current{version}_jar_sha256'],
             'R57 compatibility is bound to another actual Jar')
        need(all(old_source[k]==v['before_sha256'] and new_source[k]==v['after_sha256'] for k,v in pins['source_delta'].items()),
             'Reviewed R57 source bytes differ')
        reviewed_r57_evidence(d,pins,version)
    need(new_source['src/main/java/com/projectseele/mixin/SbwDefenseLoadedLosR56Mixin.java']=='4dbaf8c4bca7b1747131e351d0b8cb8d5a5191db83947dba3cc5105fb735579b'
         and new_source['src/main/resources/projectseele.mixins.json']=='fc56eec480ef32b4b6030cfba3fa3a59f0deabcd836c71a6d10e659c12ac6eac',
         'Only the specifically approved loaded-LOS source/registration bytes may use this association')
    for build in (old_build,new_build):
        named=Path(build['named_class_manifest']);need(sha(named)==build['named_class_manifest_sha256'],'Named production manifest changed')
    old_named,new_named=read(old_build['named_class_manifest']),read(new_build['named_class_manifest'])
    if reviewed:
        need(set(new_named)-set(old_named)==set(pins['named_added']) and not set(old_named)-set(new_named)
             and {k for k in old_named if old_named[k]!=new_named[k]}==set(pins['named_delta'])
             and all(old_named[k]==v['before_sha256'] and new_named[k]==v['after_sha256'] for k,v in pins['named_delta'].items())
             and all(new_named[k]==v for k,v in pins['named_added'].items()),'Unreviewed R57 named production class bytes')
    else:
        need(set(new_named)-set(old_named)=={addon} and not set(old_named)-set(new_named)
             and all(new_named[k]==v for k,v in old_named.items()),'An existing named production class changed')
    need(all(sha(Path(new_build['named_class_directory'])/k)==v for k,v in new_named.items()),'Current named production bytes differ')
    with zipfile.ZipFile(old_jar)as a,zipfile.ZipFile(new_jar)as b:
        need(len(a.namelist())==len(set(a.namelist())) and len(b.namelist())==len(set(b.namelist())),'Ambiguous compatible Jar entries')
        old={n:hashlib.sha256(a.read(n)).hexdigest()for n in a.namelist()};new={n:hashlib.sha256(b.read(n)).hexdigest()for n in b.namelist()}
        need(set(new)-set(old)==(set(pins['jar_added']) if reviewed else {addon}) and not set(old)-set(new),'Compatible Jar added or removed another entry')
        need(new[addon]=='7d32fc5b29f07b9f44c6a1b946bca1acdbe97a01e04d1a6984295f4de3e2c259',
             'Compatible Jar contains another loaded-LOS compiled implementation')
        need({k for k in old if old[k]!=new[k]}==({'META-INF/MANIFEST.MF','projectseele.mixins.json'}|set(pins['jar_delta']) if reviewed else {'META-INF/MANIFEST.MF','projectseele.mixins.json'}),'An unreviewed Jar class or resource changed')
        if reviewed:
            need(all(old[k]==v['before_sha256'] and new[k]==v['after_sha256'] for k,v in pins['jar_delta'].items())
                 and all(new[k]==v for k,v in pins['jar_added'].items()),'Reviewed R57 actual compiled Jar bytes differ')
        if r59 or r60:
            from build_immutable_r52_candidate import source_sounds_catalog_pin
            catalog=source_sounds_catalog_pin(new_source['src/main/resources/assets/projectseele/sounds.json'])
            need(new_build.get('source_sounds_catalog')==catalog==pins['source_sounds_catalog'],
                 'Exact reviewed R59 original90 sound definitions differ')
            need(new['assets/projectseele/sounds.json']==catalog['source_sha256'],'Actual R59 Jar sound catalog differs')
        if r60:
            from build_immutable_r52_candidate import source_launch_subtitle_pins
            subtitles=source_launch_subtitle_pins({key:new_source['src/main/resources/'+key]
                 for key in pins['source_launch_subtitles']['files']})
            need(new_build.get('source_launch_subtitles')==pins['source_launch_subtitles']
                 and subtitles==pins['source_launch_subtitles']['files']
                 and pins['source_launch_subtitles'].get('exact_source_readbacks') is True
                 and all(new[key]==v['source_sha256'] for key,v in subtitles.items()),
                 'Exact reviewed R60 original locale keys/actual Jar readbacks differ')
        old_mix,new_mix=json.loads(a.read('projectseele.mixins.json')),json.loads(b.read('projectseele.mixins.json'))
        need(new_mix['mixins'].count('SbwDefenseLoadedLosR56Mixin')==1,'Exact approved LOS Mixin registration required')
        cleaned=copy.deepcopy(new_mix);cleaned['mixins'].remove('SbwDefenseLoadedLosR56Mixin');need(cleaned==old_mix,'Other Mixin registration changed')
        manifest=lambda z:dict(line.split(': ',1)for line in z.read('META-INF/MANIFEST.MF').decode('utf8').splitlines()if ': 'in line)
        ma,mb=manifest(a),manifest(b);ma.pop('Implementation-Timestamp',None);mb.pop('Implementation-Timestamp',None)
        need(ma==mb,'Compatible Jar manifest changed beyond the build timestamp')
    def same_without(name,removed):
        a,b=read(accepted.parent/name),read(current.parent/name)
        for key in removed:a.pop(key,None);b.pop(key,None)
        need(a==b,'Actual runtime definitions changed: '+name)
    same_without('ROOT_RUNTIME_DIRECTORY.json',['installation_receipt_sha256'])
    same_without('ROOT_MECHANICAL_OWNER.json',['commissioning_receipt_sha256','directory_fingerprint'])
    same_without('ROOT_AIR_TRANSPORT.json',['directory_fingerprint']);same_without('personnel_lifts_r52.json',['directory_fingerprint'])
    need(sha(accepted.parent/'UPRIGHT_GUIDEWAY_SOURCE.json')==sha(current.parent/'UPRIGHT_GUIDEWAY_SOURCE.json'),'Accepted guide geometry bytes differ')
    for folder in (accepted.parent,current.parent):
        owner=read(folder/'ROOT_MECHANICAL_OWNER.json')
        def walk(value):
            if isinstance(value,dict):
                if 'cells_file'in value:need(sha(folder/safe(value['cells_file']))==value['sha256'],'Exact accepted component table changed')
                for child in value.values():walk(child)
            elif isinstance(value,list):
                for child in value:walk(child)
        walk(owner)
    old_pipeline=read(reference(d['accepted_pipeline']));new_pipeline=read(reference(d['current_pipeline']))
    need(reference(old_pipeline['bundle'])==accepted and reference(new_pipeline['bundle'])==current,
         'Compatibility bundles are not the actual selected pipeline outputs')
    copied=reference(d['exact_accepted_bundle_copy']);need(sha(copied)==sha(accepted),'Copied accepted authority bytes differ')
    for name in ('CURRENT_GUIDEWAY_REPORT.json','CURRENT_SOURCE_ENVELOPES.json','CURRENT_CLOSED_GATE_READBACK.json'):
        need(old_pipeline['reports'][name]==new_pipeline['reports'][name], 'Current actual geometry/readback report changed: '+name)
        current_report=reference(d['current_reports'][name]);need(sha(current_report)==new_pipeline['reports'][name],'Current report source differs')
    old_physical=read(reference(d['accepted_physical_receipt']));new_physical=read(reference(d['current_physical_receipt']))
    old_physical.pop('evidence');new_physical.pop('evidence');need(old_physical==new_physical and new_physical['verified']is True,'Current physical definitions differ')
    ab=read(accepted);need(ab['epoch']==53 and ab['directory_fingerprint']==d['accepted_authority']['directory_fingerprint'] and sha(accepted)==d['accepted_authority']['bundle_sha256'],
                          'Accepted bundle bytes/epoch/fingerprint changed')
    for name in ('directory','mechanical_owner','upright_guideway','personnel_lifts','air_transport'):
        bound=ab[name];relative=safe(bound['file'])
        need(sha(accepted.parent/relative)==bound['sha256']==sha(current.parent/relative),
             'Exact accepted definition bytes differ: '+name)
    need(sha(reference(d['accepted_physical_receipt']))==read(accepted.parent/ab['directory']['file'])['installation_receipt_sha256']
         and sha(reference(d['accepted_physical_receipt']))==read(accepted.parent/ab['mechanical_owner']['file'])['commissioning_receipt_sha256'],
         'Original accepted receipt does not exactly bind its accepted definitions')
    need(Path(d['accepted_authority']['bundle_relative']).name==accepted.name,'Accepted relative bundle filename changed')
    state=saved_runtime_authority(world)
    need(state['claimed']and not state['fault']and state['epoch']==53 and all(state[k]==d['accepted_authority'][k]for k in ('directory_fingerprint','bundle_relative','bundle_sha256','guide_sha256')),
         'Actual persisted four-part accepted authority differs; no reset is permitted')
    need(d['initial_saved_runtime']['jobs']==0 and not d['initial_saved_runtime']['pending_installation'] and d['initial_saved_runtime']['sha256']==d['saved_data_unchanged_during_preparation_sha256'],
         'Initial compatibility preparation was not the actual unchanged zero-job authority')
    return d

def navigation_pins(world):
    """Bind the actual graph and nearest-lift cache, without claiming native QA."""
    world=Path(world).resolve();pins={name:sha(world/name) for name in NAVIGATION_FILES}
    graph=json.loads(gzip.decompress((world/NAVIGATION_FILES[0]).read_bytes()))
    nearest=json.loads(gzip.decompress((world/NAVIGATION_FILES[1]).read_bytes()))
    need(graph.get('r53_navigation') is True and graph.get('r52_navigation') is True,
        'Current R53 personnel graph required')
    need(graph.get('nodes') and len(graph['nodes'])==len(nearest.get('nodes',[])),
        'Current graph/nearest-lift node coverage differs')
    need(nearest.get('graph_sha256')==pins[NAVIGATION_FILES[0]],
        'Nearest-lift table refers to another graph')
    return pins

def validate_current_bindings(report,context,build_receipt,native_install_dir,metadata):
    """Verify current source, navigation and native evidence before either ZIP."""
    validate_context(context);world=Path(context['root_world_authority']['world']).resolve()
    bindings=report.get('bindings',{})
    need(bindings.get('schema')=='projectseele.r53.current-release-bindings.v1',
        'Current source/navigation/native release bindings required')
    fingerprint=metadata['directory_fingerprint']
    need(report.get('directory_fingerprint')==fingerprint,'Acceptance directory fingerprint differs')
    build_path=Path(build_receipt).resolve();build=read(build_path)
    pipeline_path=reference(bindings['source_pipeline']);pipeline=read(pipeline_path)
    need(Path(pipeline['world']).resolve()==world,'Source pipeline refers to another World')
    for key,path,digest in [('selected_jar',Path(build['jar']).resolve(),report['jar_sha256']),
                          ('selected_build_receipt',build_path,sha(build_path))]:
        row=pipeline['source_inputs'][key]
        need(reference(row)==path and row['sha256']==digest,'Current source pipeline build differs: '+key)
    compatibility=compatible_accepted_authority(pipeline['compatible_accepted_authority'],world,build_path) if 'compatible_accepted_authority'in pipeline else None
    if compatibility:
        need(reference(pipeline['original_current_pipeline'])==reference(compatibility['current_pipeline'])
             and reference(pipeline['bundle'])==reference(compatibility['exact_accepted_bundle_copy'])
             and pipeline['source_inputs']==read(reference(compatibility['current_pipeline']))['source_inputs'],
             'Compatible pipeline changed current source inputs or exact accepted definitions')
    rows=bindings.get('source_reports',{})
    need(SOURCE_REPORTS<=rows.keys(),'Current source report coverage missing')
    for name,row in rows.items():
        path=reference(row)
        need(path==pipeline_path.parent/safe(name) and pipeline['reports'].get(name)==row['sha256'],
            'Report was not produced by the selected current pipeline: '+name)
    guide=read(reference(rows['CURRENT_GUIDEWAY_REPORT.json']))
    expected_guide_fp=compatibility['source_geometry_directory_fingerprint'] if compatibility else fingerprint
    need(guide['directory_fingerprint']==expected_guide_fp and guide.get('production_parser_valid') is True,
        'Current production guide report fingerprint differs')
    installed=read(world/'ROOT_ASSEMBLY_BUNDLE.json')
    for key in ('directory','mechanical_owner','air_transport','personnel_lifts','upright_guideway'):
        candidate=read(reference(pipeline['bundle']))[key]
        need(candidate==installed[key],'Current installed component differs from source pipeline: '+key)
    nav=bindings.get('navigation',{});pins=navigation_pins(world)
    need(nav.get('files')==pins,'Acceptance navigation differs from actual current World')
    nav_receipt=read(reference(nav['receipt']))
    need(Path(nav_receipt.get('world','')).resolve()==world and nav_receipt.get('current_round') is True
         and nav_receipt.get('installed') is True and nav_receipt.get('files')==pins
         and nav_receipt.get('jar_sha256')==report['jar_sha256']
         and nav_receipt.get('directory_fingerprint')==fingerprint,
         'Exact current navigation installation/test binding required')
    from package_release_r52 import code_reviewed
    if code_reviewed(report):
        walking='r53_personnel_walking_graph.json.gz';need(bindings.get('walking_navigation',{}).get('sha256')==sha(world/walking),'Current walking graph bytes differ')
        need(bindings.get('native_installation')=={'status':'RUNTIME_UNVERIFIED'},'Code qualification cannot import native installation PASS')
        return bindings
    native=bindings.get('native_installation',{});folder=Path(native_install_dir).resolve()
    for key,name in [('inputs','INPUTS.json'),('result','RESULT.json')]:
        need(reference(native[key])==folder/name,'Acceptance refers to another native '+key)
    inputs=read(folder/'INPUTS.json')
    need(all(inputs['world_metadata_sha256'].get(name)==digest for name,digest in pins.items()),
         'Current native installation did not bind the tested navigation bytes')
    for name,check in report['checks'].items():
        if check['status']!='PASS':continue
        need(check.get('directory_fingerprint')==fingerprint and check.get('navigation_sha256')==pins,
             'Current acceptance check did not bind directory/navigation: '+name)
        evidence=check.get('evidence')
        need(isinstance(evidence,list) and evidence,'Pinned current evidence list required: '+name)
        for row in evidence:reference(row)
    return bindings

def world_metadata(authority):
    """Pin live 124 declarations and preserved metadata without certifying 3/5/6."""
    from prepare_r52_runtime_deployment_candidate import declared_controller_inputs,reference,exact_authority
    validate_record(authority);world=Path(authority['world']);bundle_path=world/'ROOT_ASSEMBLY_BUNDLE.json'
    bundle,controllers=declared_controller_inputs(bundle_path)
    need(bundle.get('status')=='installed' and bundle.get('epoch')==authority['epoch'],'Actual installed current-epoch assembly declaration required')
    need('fixed_cannon' not in bundle,'Scope124 must not install a deferred cannon')
    fingerprint=bundle['directory_fingerprint'];need(re.fullmatch(r'[0-9a-f]{64}',fingerprint or '') and fingerprint!='0'*64,'Actual final directory fingerprint required')
    required={'directory','mechanical_owner','air_transport','personnel_lifts','upright_guideway'}
    need(required<=bundle.keys(),'Actual launch/hangar/air/personnel components required')
    files={'ROOT_ASSEMBLY_BUNDLE.json':sha(bundle_path)};documents={}
    def visit(value,parent):
        if isinstance(value,dict):
            for key in ('file','cells_file'):
                if key in value and 'sha256' in value:
                    _,path=reference(parent,value,key);need(path.is_relative_to(world),'Declared metadata escaped actual World')
                    files[path.relative_to(world).as_posix()]=sha(path)
            for child in value.values():visit(child,parent)
        elif isinstance(value,list):
            for child in value:visit(child,parent)
    for name in required:
        _,path=reference(world,bundle[name],'file');document=read(path);documents[name]=document
        exact_authority(document,bundle['epoch'],fingerprint,name);files[path.relative_to(world).as_posix()]=sha(path);visit(document,path.parent)
    validate_record(authority,documents['directory'])
    for name in ('directory','mechanical_owner','air_transport'):need(documents[name].get('status')=='installed','Actual installed component required: '+name)
    need(documents['personnel_lifts'].get('ready') is True,'Actual ready personnel lift declaration required')
    # Existing navigation, artwork and saved progress remain byte-pinned, but
    # their historical reviews cannot qualify this round's limited scope.
    preserved={}
    for path in sorted(world.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(world);name=relative.as_posix()
        if path.suffix=='.json' or name.endswith('.json.gz') or path.suffix=='.dat' and ('data' in relative.parts or name=='level.dat'):
            need(not path.is_symlink() and not path.is_junction(),'World metadata cannot redirect to another source')
            preserved[safe(name)]=sha(path)
    return dict(source='CURRENT_DECLARED_ROOT_WORLD_ONLY',feature_scope='124',world=world.as_posix(),
        root_world_authority=authority,directory_fingerprint=fingerprint,files=files,
        navigation_sha256=navigation_pins(world),
        preserved_metadata_sha256=preserved,expected_controllers=controllers,expected_controller_count=len(controllers),
        deferred_scope=['3_yashima_combat','6_unrelated_global_configuration'],
        validation='BYTE_BINDING_ONLY_NATIVE_AND_VISUAL_ACCEPTANCE_REQUIRED_SEPARATELY')
