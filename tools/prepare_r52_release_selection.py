"""Prepare Root's exact package selection after final build/install/acceptance.

Writes one repository-local JSON only. Never builds, installs, starts a server,
packages files, or changes the supplied acceptance report.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import zipfile

from build_immutable_r52_candidate import BASE, REVIEW, ROOT, snapshot, frozen_build_class_pins, source_asset_pins,source_sounds_catalog_pin,SOUND_CATALOG,source_launch_subtitle_pins,source_mechanical_crane_pin_r61,MECHANICAL_CRANE_PROC_R61
from package_release_r52 import BASELINES, WORLD, need, safe, validate_acceptance,current_world_metadata_pins,offline_manual,code_reviewed
from release_r45_contract import class_protocol
from root_bundle_authority_r53 import arguments as authority_arguments, validate as world_authority, original_identities
from release_scope124_r53 import context as release_context, validate_context
from prepare_r52_runtime_deployment_candidate import declared_controller_inputs,reference,expected_controllers

RUNTIME = ROOT / 'artifacts/r52_runtime_candidate/projectseele-local-maps'
BASELINE_INPUTS = ROOT / 'artifacts/r52_delivery_preparation/BASELINE_PACKAGE_INPUTS.json'
DOCUMENTS = ('README_R52.zh.md', 'R52_RELEASE_NOTES.zh.md', 'R52_USER_ACCEPTANCE.zh.md')
BRIDGE = 'assets/projectseele/models/block/entry_plug_bridge_fascia.json'


def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def repo_file(path):
    path = Path(path).resolve()
    need(path.is_relative_to(ROOT.resolve()) and path.is_file(),
         'Current repository file required: ' + str(path))
    return path


def selected(path):
    path = repo_file(path)
    return {'path': str(path), 'sha256': sha(path)}


def tree_hashes(folder):
    return {safe(p.relative_to(folder).as_posix()): sha(p)
            for p in sorted(folder.rglob('*')) if p.is_file()}


def jar_assets(build):
    """The same base + reviewed UV + source bridge selection as the build tool."""
    frozen = read(BASE / 'ASSET_FROZEN.json')['files']
    expected = {safe(n): digest for n, digest in frozen.items()
                if n.startswith(('assets/', 'META-INF/licenses/'))}
    need(len(expected) == 803, 'Explicit R51 base803 assets required')
    for name, digest in expected.items():
        need(sha(BASE / name) == digest, 'Frozen base asset changed: ' + name)
    reviewed = read(REVIEW.parent / 'FINAL_OVERLAY_RECEIPT.json')
    need(reviewed['schema'] == 'projectseele.r52.reviewed-assets-overlay.v1'
         and reviewed['expected_member_count'] == 4 and len(reviewed['files']) == 4,
         'Complete reviewed four-member UV overlay required')
    seen = set()
    for row in reviewed['files']:
        name = safe(row['path'])
        need(name.startswith('assets/projectseele/mesh/') and name not in seen
             and expected.get(name) == row['baseline_sha256'],
             'Reviewed asset does not match the frozen base: ' + name)
        need(sha(REVIEW / name) == row['sha256'], 'Reviewed UV asset changed: ' + name)
        seen.add(name)
        expected[name] = row['sha256']
    expected[BRIDGE] = sha(ROOT / 'src/main/resources' / BRIDGE)
    if 'source_sounds_catalog' in build:
        sounds=source_sounds_catalog_pin(build['source_sounds_catalog']['source_sha256'])
        need(sounds==build['source_sounds_catalog'],'Frozen Source sound catalog receipt differs')
        need(SOUND_CATALOG in expected,'Original sound catalog entry must exist')
        expected[SOUND_CATALOG]=sounds['source_sha256']
    if 'source_launch_subtitles' in build:
        declaration=build['source_launch_subtitles']
        subtitles=source_launch_subtitle_pins({n:row['source_sha256'] for n,row in declaration['files'].items()})
        need(subtitles==declaration['files'] and declaration.get('exact_source_readbacks') is True,
             'Frozen Source launch subtitle receipt differs')
        need(declaration['actual_jar_readbacks']=={n:row['source_sha256'] for n,row in subtitles.items()},
             'Build locale readbacks did not match exact frozen Source')
        for name,row in subtitles.items():
            need(name in expected,'Original locale inventory entry absent: '+name)
            expected[name]=row['source_sha256']
    need(len(expected) == build['asset_readbacks'] == 803,
         'Final build asset readback count differs from exact base/UV/bridge selection')
    expected.update(source_asset_pins())
    need(build['required_source_assets']==source_asset_pins(), 'Exact built upright model/path and independent Legacy floor-overlay asset pins required')
    if 'source_mechanical_crane_r61' in build:
        row=build['source_mechanical_crane_r61']
        mechanical=source_mechanical_crane_pin_r61(row['source']['source_gzip_sha256'])
        need(row['source']==mechanical and row.get('exact_source_readbacks') is True,
             'Exact reviewed61 mechanical Source row differs')
        need(row['actual_jar_readbacks']==dict(gzip_sha256=mechanical['source_gzip_sha256'],json_sha256=mechanical['source_json_sha256']),
             'Actual61 procedural gzip/raw Jar readback row differs')
        need(MECHANICAL_CRANE_PROC_R61 not in expected, 'Reviewed crane Source must be one additional exact readback, never replace803 overlay or original8 source assets')
        expected[MECHANICAL_CRANE_PROC_R61]=mechanical['source_gzip_sha256']
    return expected


def native_inputs(directory, jar, jar_sha256, context=None):
    world = Path(context['root_world_authority']['world']) if context else WORLD
    runtime_root = Path(context['runtime']) if context else RUNTIME
    baseline_path = Path(context['original_identities']['path']) if context else ROOT/'artifacts/r52_delivery_preparation/ORIGINAL_WORLD_IDENTITIES_BEFORE_INSTALL.json'
    if context: validate_context(context)
    inputs = read(directory / 'INPUTS.json')
    result = read(directory / 'RESULT.json')
    for key in ('installation_accepted', 'native_restart_passed',
                'actual_controller_uuid_and_sources_retained', 'geofront_original_identities_retained',
                'normal_stop_complete'):
        need(result.get(key) is True, 'Minimal actual install/restart did not pass: ' + key)
    need(not result.get('failure') and not result.get('live_pid_needs_root_attention')
         and result.get('pid') is None, 'Native installation is failed or still running')
    need(inputs.get('prepared_only') is False and inputs.get('no_world_copy_or_qa_import') is True,
         'Prepared-only or copied QA inputs cannot qualify a release')
    observer_path=Path(inputs['observer_receipt']).resolve() if context else ROOT/'.codex/r52_continuous_delivery_tools/OBSERVER_COMPILE_RECEIPT.json'
    observer=read(observer_path)
    need(sha(observer_path)==inputs['observer_receipt_sha256'] and observer['compile_passed'] is True
         and observer['agent_sha256']==inputs['agent_sha256']==sha(observer_path.parent/'r52_lifecycle_readonly_agent.jar')
         and observer['source_sha256']==inputs['observer_source_sha256']
         and all(sha(ROOT/name)==digest for name,digest in observer['source_sha256'].items()),
         'Actual native observer does not match current exact controller/source checks')
    need(Path(inputs['world']).resolve() == Path(result['world']).resolve() == world.resolve(),
         'Native receipts must refer to the explicitly selected Root World')
    need(sha(inputs['build_receipt'])==inputs['build_receipt_sha256'] and frozen_build_class_pins(inputs['build_receipt'],jar)==inputs['compiled_delivery_class_sha256'], 'Native actual final build/class pins differ')
    need(Path(inputs['jar']).resolve() == jar and inputs['jar_sha256'] == jar_sha256,
         'Native installation used another immutable JAR')
    for name, digest in inputs['world_metadata_sha256'].items():
        need(sha(world / safe(name)) == digest,
             'Installed Root metadata changed after native readback: ' + name)
    deployment=read(inputs['deployment'])
    need(sha(inputs['deployment'])==inputs['deployment_sha256'], 'Actual native deployment input changed')
    bundle_row=next(r for r in deployment['files'] if r['world_relative']=='ROOT_ASSEMBLY_BUNDLE.json')
    need(sha(bundle_row['candidate'])==bundle_row['sha256']==deployment['bundle_sha256'], 'Observed actual bundle binding changed')
    _,declared=declared_controller_inputs(bundle_row['candidate']);expected={row['uuid']:row['role'] for row in declared}
    need(inputs['expected_controllers']==expected and result['expected_controllers']==expected
         and inputs['expected_controller_count']==result['expected_controller_count']==len(expected)
         and deployment['expected_controllers']==declared, 'Actual restart UUID/roles differ from selected owner manifest')
    need(sha(baseline_path)==inputs['original_identity_baseline_sha256']
         and inputs['geofront_original_identities']==read(baseline_path)['managed_geofront'],
         'Original exact pre-install identity baseline differs')
    state_rows = result['complete_door_and_cannon_state_matches']
    compared = {row['uuid']: row['role'] for row in state_rows}
    need(len(compared) == len(state_rows) and compared ==
         {identity: role for identity, role in expected.items()
          if role in ('silo_gate', 'hangar_gate', 'fixed_cannon')},
         'Native door/cannon restart state readback does not cover its exact identities')
    host = (directory / 'host').resolve()
    need(Path(inputs['workingDirectory']).resolve() == host,
         'Actual installation host differs from the observed host')
    host_jar = host / 'mods/projectseele-0.1.0-all.jar'
    need(sha(host_jar) == jar_sha256 and
         inputs['initial_host_sha256'].get('mods/projectseele-0.1.0-all.jar') == jar_sha256,
         'Actual native host JAR differs from its initial/final build binding')
    if context:
        need(inputs.get('root_world_authority')==context['root_world_authority'], 'Native installation lacks the exact current Root authority')
        need(inputs['original_identity_baseline_sha256']==context['original_identities']['sha256'], 'Native original-identity authority differs')
    validate_native_baseline_members(inputs,host,context)
    pins = inputs['runtime_sha256']
    need(all('/' not in safe(name) for name in pins), 'Portable runtime must use flat original filenames')
    actual = tree_hashes(runtime_root)
    need(actual == pins == tree_hashes(host / 'projectseele-local-maps'),
         'Selected, observed native, and actual host runtime differ')
    for name, digest in pins.items():
        need(inputs['initial_host_sha256'].get('projectseele-local-maps/' + name) == digest,
             'Native initial runtime binding differs: ' + name)
    contract = read(runtime_root / 'combat_bundle_r44.json')
    need(set(actual) == set(contract['files']) | {'combat_bundle_r44.json'},
         'Runtime must contain exactly the selected combat contract and its members')
    for name, digest in contract['files'].items():
        need(actual.get(name) == digest, 'Actual portable combat contract differs: ' + name)
    return actual


def validate_native_baseline_members(inputs,host,context=None):
    """The real restart must use the same complete formal server dependencies
    that packaging retains. Forge may normalise config after startup; validate
    its exact staged config plus the still-live immutable external JARs.
    """
    server_baseline=Path(context['baseline_packages']['server']['path']) if context else BASELINES['server']
    need(Path(inputs.get('full_delivered_dependency_source','')).resolve()==server_baseline.resolve(),
         'Actual native host must use the full formal R51 server dependency source')
    staged=inputs.get('full_delivered_host_members',{});expected={}
    with zipfile.ZipFile(server_baseline) as archive:
        need(len(archive.namelist())==len(set(archive.namelist())),'Formal server baseline has duplicate members')
        for info in archive.infolist():
            name=safe(info.filename) if not info.is_dir() else None
            if name is None or not name.startswith(('mods/','config/','defaultconfigs/')) or name.startswith('mods/projectseele-'):continue
            with archive.open(info) as stream:expected[name]=hashlib.file_digest(stream,'sha256').hexdigest()
    need(staged==expected and all(inputs['initial_host_sha256'].get(n)==h for n,h in expected.items()),
         'Actual native full external mods/config/defaultconfigs differ from the formal baseline')
    external={n:h for n,h in expected.items() if n.startswith('mods/') and n.endswith('.jar')}
    need(set('mods/'+p.name for p in (host/'mods').glob('*.jar'))==set(external)|{'mods/projectseele-0.1.0-all.jar'},
         'Actual native host external mod inventory differs from the full formal baseline')
    need(all(sha(host/n)==h for n,h in external.items()),'Actual native external mod binary changed')


TRANSIENT4_LIFECYCLE_PROOF=ROOT/'.Codex/map_complete_20261013/delivery_finish/transient_lifecycle4/EXACT4_TRANSIENT_LIFECYCLE_REVIEW.json'
TRANSIENT4_LIFECYCLE_SHA='e5af04d57c3da96757961dabd73721ec57e0300ecfca18a93da934de16f95a21'
TRANSIENT4_TYPES={
 '6fc64974-f099-4c11-a95c-1dcc4d023c07':'minecraft:experience_orb',
 '5ea32ce3-d39e-4896-b554-dba9690c01ad':'minecraft:experience_orb',
 '6e0ee84a-8042-4d55-b19d-6b6abe5ffa9f':'minecraft:experience_orb',
 '24436972-040e-4c51-aea7-66b3702f8b2b':'minecraft:item'}
def original_identity_lifecycle4(original,current,context):
    missing=set(original)-set(current)
    if not missing:
        need(all(current.get(k)==v for k,v in original.items()),'Original identity type/dimension changed')
        return dict(original_count=len(original),retained_count=len(original),disposable_missing=[])
    need(context is not None and context['original_identities']['sha256']=='4365d99010d59cc45df32ecccbb147cd0f213292b07b7d27c2a68fabd828bf66'
         and len(original)==678 and missing==set(TRANSIENT4_TYPES),'Only Root-reviewed exact4 disposable UUID delta allowed')
    need(sha(TRANSIENT4_LIFECYCLE_PROOF)==TRANSIENT4_LIFECYCLE_SHA,'Exact disposable lifecycle evidence changed')
    proof=read(TRANSIENT4_LIFECYCLE_PROOF)
    need(proof['original_game_time']==4224671 and proof['current_game_time']==4337383 and proof['global_time_delta_ticks']==112712
         and proof['only_reviewed_missing_uuids']==sorted(TRANSIENT4_TYPES) and proof['exact_removal_cause_proven']is False,
         'Known lifecycle evidence must retain cause uncertainty')
    for row in proof['entities']:
        u=row['uuid'];need(u in TRANSIENT4_TYPES and original[u]=={'type':TRANSIENT4_TYPES[u],'dimension':'dimensions/projectseele/geofront'}
            and row['type']==TRANSIENT4_TYPES[u] and row['baseline_age_ticks']==1643 and row['lifespan_ticks']==6000
            and row['invulnerable']==0 and row['can_update']==1 and row['elapsed_global_time_sufficient']is True,
            'Unreviewed disposable entity/NBT delta')
    retained={k:v for k,v in original.items()if k not in TRANSIENT4_TYPES}
    need(len(retained)==674 and all(current.get(k)==v for k,v in retained.items()),'All other674 UUID/type/dimension must remain exact')
    return dict(original_count=678,retained_count=674,disposable_missing=sorted(TRANSIENT4_TYPES),lifecycle_evidence={'path':str(TRANSIENT4_LIFECYCLE_PROOF.resolve()),'sha256':TRANSIENT4_LIFECYCLE_SHA},exact_removal_cause_proven=False)


def offline_world_inputs(receipt_path,jar,jar_sha256,create=False,context=None):
    """Explicit final user delegation: current identity/bytes, never native PASS."""
    from run_r52_minimal_install_restart import entity_index
    if context: validate_context(context)
    world=Path(context['root_world_authority']['world']) if context else WORLD
    runtime_root=Path(context['runtime']) if context else RUNTIME
    baseline_path=Path(context['original_identities']['path']) if context else ROOT/'artifacts/r52_delivery_preparation/ORIGINAL_WORLD_IDENTITIES_BEFORE_INSTALL.json'
    original=read(baseline_path)['managed_geofront'];current=entity_index(world)
    need(original and (context is not None or len(original)==680),'Current original identity baseline required')
    lifecycle=original_identity_lifecycle4(original,current,context)
    bundle_path=world/'ROOT_ASSEMBLY_BUNDLE.json';bundle=read(bundle_path);documents={};metadata={'ROOT_ASSEMBLY_BUNDLE.json':sha(bundle_path)}
    for key,row in bundle.items():
        if isinstance(row,dict) and 'file' in row and 'sha256' in row:
            _,path=reference(world,row,'file');metadata[path.relative_to(world).as_posix()]=sha(path)
            if key in ('directory','mechanical_owner','fixed_cannon'):documents[key]=read(path)
    need({'directory','mechanical_owner'}<=documents.keys() and (context is not None or 'fixed_cannon' in documents),'Actual complete current owner/directory and explicitly selected optional cannon references required')
    if context: need('fixed_cannon' not in documents,'Scope124 must not install a deferred cannon')
    declared=expected_controllers(bundle,documents['mechanical_owner'],documents['directory'],documents.get('fixed_cannon'))
    expected={r['uuid']:r['role'] for r in declared};need(len(expected)==len(declared) and (context is not None or len(expected)==52),'Exact final declared controller roles required')
    types={'original_carrier':'projectseele:nerv_carrier_platform','original_gantry':'projectseele:nerv_carrier_platform','original_crane':'projectseele:nerv_carrier_platform','silo_gate':'projectseele:nerv_silo_door','hangar_gate':'projectseele:nerv_hangar_door','fixed_cannon':'projectseele:yashima_cannon_r52'}
    need(all(current.get(k)=={'type':types[role],'dimension':'dimensions/projectseele/geofront'} for k,role in expected.items()),'Current exact declared persisted UUID/type/dimension differs')
    runtime=tree_hashes(runtime_root);contract=read(runtime_root/'combat_bundle_r44.json')
    need(set(runtime)==set(contract['files'])|{'combat_bundle_r44.json'} and all(runtime.get(k)==v for k,v in contract['files'].items()),'Actual selected runtime differs from its full contract')
    owner=documents['mechanical_owner'];guide=bundle['upright_guideway'];model='assets/projectseele/mesh/upright_outer_captured_r52.json'
    with zipfile.ZipFile(jar) as z:model_sha=hashlib.sha256(z.read(model)).hexdigest()
    need(owner['ground_guides']['mode']=='continuous_upright' and owner['ground_guides']['source_sha256']==model_sha and owner['ground_guides']['paths_sha256']==guide['sha256'],'Actual current guide model/path byte binding differs')
    regions={p.relative_to(world).as_posix():sha(p) for p in sorted(world.rglob('entities/r.*.mca'))}
    data={'schema':'projectseele.r52.offline-world-identity-byte-baseline.v1','world':str(world.resolve()),'jar_sha256':jar_sha256,'original_identity_baseline_sha256':sha(baseline_path),'original_identities_retained':True,'original_identity_count':len(original),'expected_controllers':expected,'expected_controller_count':len(expected),'actual_identity_type_dimension':{k:current[k] for k in expected},'actual_entity_count':len(current),'entity_region_sha256':regions,'current_root_metadata_sha256':metadata,'directory_fingerprint':bundle['directory_fingerprint'],'guide_model_sha256':model_sha,'guide_paths_sha256':guide['sha256'],'runtime_sha256':runtime,'native_installation_passed':False,'native_save_cold_passed':False,'map_visual_passed':False,'performance_passed':False,'scope':'OFFLINE_SOURCE_WORLD_MANUAL_PLAYTEST_NO_NEW_GAME','world_written':False}
    if context: data.update(feature_scope='124',root_world_authority=context['root_world_authority'],original_identities_retained=not lifecycle['disposable_missing'],original_persistent_identities_retained=True,original_retained_count=lifecycle['retained_count'],original_identity_lifecycle_delta=lifecycle)
    else:
        data['original680_retained']=data.pop('original_identities_retained');data.pop('original_identity_count')
        data['expected52_controllers']=data.pop('expected_controllers');data.pop('expected_controller_count')
        data['actual52_identity_type_dimension']=data.pop('actual_identity_type_dimension')
    receipt_path=Path(receipt_path).resolve();need(receipt_path.is_relative_to(ROOT/'artifacts'),'Repository offline baseline required')
    if create:
        need(not receipt_path.exists(),'Preserve prior offline baseline');receipt_path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n','utf8')
    else:need(read(receipt_path)==data,'Current identity/source/runtime/metadata bytes changed after offline baseline')
    return runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope',choices=['full','124'],default='full')
    authority_arguments(parser,required=False)
    for name in ('runtime','original-identities','baseline-inputs'):parser.add_argument('--'+name,type=Path)
    for name in ('original-identities-sha256','baseline-inputs-sha256'):parser.add_argument('--'+name)
    parser.add_argument('--build-receipt', type=Path, required=True)
    parser.add_argument('--native-install-dir', type=Path)
    parser.add_argument('--offline-manual',action='store_true',help='Explicit latest user delegation; current World identities/source bytes, no native PASS')
    parser.add_argument('--code-reviewed-runtime-unverified',action='store_true',help='Explicit private manual acceptance build, exact code review; no native PASS')
    parser.add_argument('--acceptance', type=Path, required=True)
    parser.add_argument('--date', required=True, help='YYYYMMDD release date')
    parser.add_argument('--out', type=Path, help='Fresh selection JSON inside this repository artifacts')
    args = parser.parse_args()
    context=None;offline_requested=args.offline_manual or args.code_reviewed_runtime_unverified
    need(not(args.offline_manual and args.code_reviewed_runtime_unverified),'Choose one explicit qualification')
    if args.scope=='124':
        need(not args.offline_manual,'This scope124 release requires actual current-round native acceptance')
        need(all(getattr(args,name) is not None for name in ('world','baseline','root_plan','baseline_sha256','root_plan_sha256','runtime','original_identities','original_identities_sha256','baseline_inputs','baseline_inputs_sha256')), 'Scope124 requires explicit World/baseline/plan/runtime/original identities/package baseline and SHA pins')
        context=release_context(world_authority(args),args.runtime,args.original_identities,args.original_identities_sha256,args.baseline_inputs,args.baseline_inputs_sha256)
    world=Path(context['root_world_authority']['world']) if context else WORLD
    runtime_root=Path(context['runtime']) if context else RUNTIME
    baseline_inputs=Path(context['baseline_inputs']['path']) if context else BASELINE_INPUTS
    baselines={k:Path(v['path']) for k,v in context['baseline_packages'].items()} if context else BASELINES
    need(re.fullmatch(r'\d{8}', args.date) is not None, 'Explicit YYYYMMDD date required')
    datetime.datetime.strptime(args.date, '%Y%m%d')
    output = (args.out or ROOT / 'artifacts/r52_delivery_preparation' /
              ('ROOT_RELEASE_SELECTION_' + args.date + '.json')).resolve()
    need(output.is_relative_to((ROOT / 'artifacts').resolve()) and not output.exists(),
         'Fresh current-repository artifacts selection required; preserve previous selections')
    build_path = repo_file(args.build_receipt)
    need(build_path.name == 'BUILD_RECEIPT.json', 'Actual final BUILD_RECEIPT.json required')
    source_path = repo_file(build_path.parent / 'SOURCE_BEFORE.json')
    build, source = read(build_path), read(source_path)
    need(build['build_exit'] == 0 and build['changed_during_build'] == []
         and build['source_files'] == len(source), 'Frozen successful source build required')
    need(snapshot() == source, 'Current src/Gradle inputs differ from the final build snapshot')
    jar = repo_file(build['jar'])
    need(jar.parent == build_path.parent and sha(jar) == build['sha256']
         and jar.stat().st_size == build['bytes'], 'Actual immutable final JAR changed')
    frozen_build_class_pins(build_path,jar)
    assets = jar_assets(build)
    with zipfile.ZipFile(jar) as archive:
        names = archive.namelist()
        need(len(names) == len(set(names)), 'Duplicate final JAR members')
        protocol = class_protocol(archive.read('com/projectseele/network/SeeleNetwork.class'))
        need(protocol == str(build['protocol']), 'Actual final protocol differs from build receipt')
        for name, digest in assets.items():
            need(hashlib.sha256(archive.read(name)).hexdigest() == digest,
                 'Actual final JAR resource differs: ' + name)
    acceptance_path = repo_file(args.acceptance)
    acceptance = read(acceptance_path)
    need(str(acceptance.get('feature_scope','full'))==args.scope, 'Acceptance scope differs from explicit release selection')
    validate_acceptance(acceptance)
    need(args.offline_manual==offline_manual(acceptance) and args.code_reviewed_runtime_unverified==code_reviewed(acceptance),'Explicit selection mode differs from actual user authorization')
    if offline_requested:
        offline_path=output.with_suffix('.OFFLINE_WORLD_INPUTS.json')
        runtime=offline_world_inputs(offline_path,jar,build['sha256'],create=True,context=context)
        install=None
    else:
        need(args.native_install_dir is not None,'Actual native installation directory required')
        install=args.native_install_dir.resolve();runtime=native_inputs(install,jar,build['sha256'],context=context)
    need(acceptance.get('draft') is not True, 'Acceptance is still a draft')
    need(acceptance['jar_sha256'] == build['sha256']
         and Path(acceptance['world']).resolve() == world.resolve(),
         'Completed acceptance must bind the same final JAR and Root World')
    documents = {}
    for name in DOCUMENTS:
        path = repo_file(ROOT / 'docs' / name)
        content = path.read_bytes()
        text = content.decode('utf-8-sig')
        need(not re.search(r'DRAFT|待填写|待确认|待\s*Root|【[^】]*(?:填写|确认)[^】]*】', text, re.I),
             'Unfinished release document: ' + name)
        documents[name] = {'path': str(path), 'sha256': hashlib.sha256(content).hexdigest()}
    baseline = read(baseline_inputs)
    need(set(baseline) == set(baselines), 'Exact R51 server/client baseline pins required')
    baseline_hashes = {}
    for side, path in baselines.items():
        row = baseline[side]
        need(Path(row['path']).resolve() == path.resolve() and path.is_file()
             and path.stat().st_size == row['bytes']
             and re.fullmatch(r'[0-9a-f]{64}', row['sha256']) is not None,
             'Pinned R51 baseline path/size/hash differs: ' + side)
        baseline_hashes[side] = row['sha256']
    need(snapshot() == source, 'Source changed during release selection preparation')
    need(sha(jar) == build['sha256'], 'Final JAR changed during selection preparation')
    world_metadata=current_world_metadata_pins(world=world,scope=args.scope,authority=context['root_world_authority'] if context else None)
    if args.scope=='124':
        from release_scope124_r53 import validate_current_bindings
        validate_current_bindings(acceptance,context,build_path,install,world_metadata)
    evidence={'build_receipt':selected(build_path),'source_before':selected(source_path),'baseline_inputs':{'path':str(baseline_inputs),'sha256':sha(baseline_inputs)}}
    if offline_requested:evidence['offline_world_inputs']=selected(offline_path)
    else:evidence.update(native_inputs={'path':str(install/'INPUTS.json'),'sha256':sha(install/'INPUTS.json')},native_result={'path':str(install/'RESULT.json'),'sha256':sha(install/'RESULT.json')})
    config = {'schema': 'projectseele.r52.root-release-selection.v1', 'date': args.date,
              'release_type': acceptance.get('release_type', 'accepted_release'),
              'qualification': acceptance.get('qualification'), 'private_delivery':acceptance.get('private_delivery',False),
              'manual_acceptance_required':acceptance.get('manual_acceptance_required',False),
              'protocol': protocol, 'jar': {'path': str(jar), 'sha256': build['sha256']},
              'runtime': {name: {'path': str((runtime_root / name).resolve()), 'sha256': digest}
                          for name, digest in runtime.items()},
              'required_jar_assets': assets, 'documents': documents,
              'acceptance': selected(acceptance_path), 'baseline_sha256': baseline_hashes,
              'world_metadata_pins':world_metadata,
              'selection_evidence':evidence}
    if context: config.update(feature_scope='124',release_context=context,root_world_authority=context['root_world_authority'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf8', newline='\n') as stream:
        stream.write(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'selection': str(output), 'jar_sha256': build['sha256'],
                      'protocol': protocol, 'runtime_files': len(runtime),
                      'required_jar_assets': len(assets), 'packaging_executed': False}))


if __name__ == '__main__':
    main()
