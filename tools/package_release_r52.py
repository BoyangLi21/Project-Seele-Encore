"""Package only Root's explicitly accepted R52 selection, then read every delivered byte."""
from pathlib import Path,PurePosixPath
import argparse,copy,gzip,hashlib,json,msvcrt,os,re,shutil,uuid,zipfile
from release_r45_contract import class_protocol
from r52_spatial_plan import BASE

ROOT=Path(__file__).resolve().parents[1]
WORLD=BASE/'WORLD_R52'
BASELINES={side:Path('D:/eva/delivery')/('Project_SEELE_Encore_R51_20261009_'+suffix+'.zip')
           for side,suffix in [('server','Server'),('client','Client_PCL')]}
MOD='mods/projectseele-0.1.0-all.jar'
REQUIRED_ACCEPTANCE={'source_build','ordinary_motion','finisher','hangar_departure_return','emergency_ejection_recovery',
    'multi_air_transport','yashima','marine','surface_angels','city_motion','headquarters_lifts_doors','railway',
    'map_visual_review','performance','navigation','client_server_same_payload'}
DEFERRED_BY_USER={'yashima','marine'}
DELIVERY_CHECKS={'source_build','client_server_same_payload'}
ROOT_REVIEW_CHECKS={'map_visual_review'}
SCOPE124_ACCEPTANCE={'source_build','launch_three_destinations','hangar_departure_return','hangar_prepare_cancel_recovery','multi_air_transport','cold_restart_identity_restore','required_coordinate_cleanup','required_migration_visual_review','map_visual_review','performance','client_server_same_payload','underground_full_width','pyramid_all_floor_rings_two_lifts','complete_obsolete_retirement','direct_hq_surface_railway','fast_transport_actual','navigation'}

def offline_manual(report):
    return (report.get('release_type')=='user_acceptance_build'
            and report.get('manual_acceptance_authorized') is True
            and report.get('all_gameplay_visual_performance_manual_authorized') is True
            and report.get('additional_native_validation_prohibited') is True
            and report.get('verification_scope')=='OFFLINE_SOURCE_WORLD_MANUAL_PLAYTEST')



CODE_QUALIFICATION='CODE_REVIEWED_RUNTIME_UNVERIFIED'
def code_reviewed(report):
    return report.get('release_type')=='code_reviewed_runtime_unverified'

def validate_code_qualification(report):
    need(report.get('qualification')==CODE_QUALIFICATION and report.get('private_delivery')is True
         and report.get('manual_acceptance_required')is True and report.get('native_verified')is False,
         'Explicit private code-reviewed/runtime-unverified label required')
    need(report.get('known_implementation_blockers')==[] and report.get('code_review_complete')is True,
         'Known source defects must be resolved and Root code review complete')
    def bound(row):
        p=Path(row['path']).resolve();need(p.is_file()and sha(p)==row['sha256'],'Qualification evidence bytes changed');return json.loads(p.read_text('utf-8-sig'))
    auth=bound(report['code_review_authorization']);review=bound(report['code_review_receipt'])
    need(auth.get('schema')=='projectseele.r53.explicit-private-code-review-authorization.v1'
         and auth.get('draft')is not True and auth.get('user_authorized')is True and auth.get('private_two_packages_authorized')is True
         and auth.get('further_stress_validation_cancelled')is True and auth.get('user_request')
         and auth.get('qualification')==CODE_QUALIFICATION and auth.get('feature_scope')=='124'
         and Path(auth['world']).resolve()==Path(report['world']).resolve(), 'Latest explicit user scope required')
    need(review.get('schema')=='projectseele.r53.final-code-review.v1' and review.get('draft')is not True and review.get('code_review_complete')is True
         and review.get('known_implementation_blockers')==[] and review.get('native_verified')is False
         and review.get('build_receipt')==report['code_review_build_receipt']
         and review.get('jar_sha256')==report['jar_sha256'],'Final code review must bind this exact build')
    need(review.get('review_evidence'),'Concrete Root code-review evidence required')
    for row in review['review_evidence']:
        p=Path(row['path']);need(p.is_file()and sha(p)==row['sha256'],'Code-review proof bytes changed')
    build=bound(report['code_review_build_receipt'])
    need(build['build_exit']==0 and build['changed_during_build']==[] and build['sha256']==report['jar_sha256'],
         'Actual successful final build required')
    need(set(report['checks'])==SCOPE124_ACCEPTANCE,'Exact17 checks retained in code qualification')
    for name,check in report['checks'].items():
        need(check.get('status')=='RUNTIME_UNVERIFIED' and check.get('runtime_verified')is False
             and check.get('evidence'),'Runtime PASS cannot be imported into code qualification: '+name)
        for row in check['evidence']:
            p=Path(row['path']);need(p.is_file()and sha(p)==row['sha256'],'Code-review evidence changed')
    return report


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):
    with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def safe(name):
    p=PurePosixPath(name)
    need(name and not p.is_absolute()and ':'not in name and '\\'not in name
         and all(part not in ('','.','..')for part in name.split('/')),'Unsafe archive member: '+name)
    return name


def equal(a,b):
    while True:
        aa=a.read(1024*1024);bb=b.read(1024*1024)
        if aa!=bb:return False
        if not aa:return True


def selected_file(row,allowed_root=None):
    base=Path(allowed_root).resolve() if allowed_root is not None else ROOT.resolve()
    p=Path(row['path']).resolve();need(p.is_relative_to(base)and p.is_file(),'Selected release input must stay within its explicitly selected source root')
    need(sha(p)==row['sha256'],'Changed selected release file: '+str(p));return p


def validate_acceptance(report):
    """The user may own playtesting; known unfinished implementation cannot pass."""
    need(report.get('release_ready')is True,'R52 has unfinished implementation or delivery checks')
    scope=str(report.get('feature_scope','full'));need(scope in ('full','124'),'Unknown release feature scope')
    required=SCOPE124_ACCEPTANCE if scope=='124' else REQUIRED_ACCEPTANCE
    need(required<=set(report['checks']),'Final acceptance coverage missing')
    if scope=='124':
        need(report.get('deferred_scope')==['3_yashima_combat','6_unrelated_global_configuration'], 'Current scope must include the authorized pyramid, underground and transport work')
        need(report.get('known_implementation_blockers')==[], 'Known124 implementation blockers must be fixed before packaging')
    if code_reviewed(report):
        need(scope=='124','Explicit current124 code qualification required');validate_code_qualification(report);return
    manual=report.get('release_type')=='user_acceptance_build'
    if manual:
        need(report.get('manual_acceptance_authorized')is True,'Explicit user playtest delegation required')
        need(report.get('known_implementation_blockers')==[],'Known implementation blockers must be fixed before packaging')
    for name in required:
        check=report['checks'][name];status=check['status']
        need(check.get('evidence'),'Implementation/delivery evidence missing: '+name)
        if status=='PASS':
            if scope=='124':
                need(check.get('current_round') is True,'Historical evidence cannot qualify current124 work: '+name)
                need(check.get('world')==report.get('world') and check.get('jar_sha256')==report.get('jar_sha256'),'Current124 evidence refers to another World/Jar: '+name)
            continue
        if scope=='124':raise ValueError('Current124 native/visual/delivery acceptance incomplete: '+name)
        if scope=='full' and manual and name in DEFERRED_BY_USER and status=='DEFERRED':
            need(check.get('production_start_disabled')is True,'Deferred campaign must not start as a finished operation: '+name)
            continue
        if manual and name not in DELIVERY_CHECKS and (name not in (ROOT_REVIEW_CHECKS | ({'required_migration_visual_review'} if scope=='124' else set())) or offline_manual(report)) and status=='USER_TEST_PENDING':
            need(check.get('implemented')is True and (check.get('known_implementation_failures')==[] or offline_manual(report)),
                 'Unfinished implementation cannot be relabelled as user testing: '+name)
            continue
        raise ValueError(('Root current-round native art review incomplete: ' if name in ROOT_REVIEW_CHECKS else 'Acceptance incomplete: ')+name)


def current_world_metadata_pins(world=None,scope='full',authority=None):
    if scope=='124':
        from release_scope124_r53 import world_metadata
        need(authority is not None and Path(authority['world']).resolve()==Path(world).resolve(), 'Explicit current World authority required')
        return world_metadata(authority)
    need(scope=='full','Unknown metadata scope')
    return legacy_world_metadata_pins(world)

def legacy_world_metadata_pins(world=None):
    """Current W is the only payload authority; no migration/rebind is executed.

    Receipt node counts are read, not hardcoded to the withdrawn115511 graph.
    The post-art export is intentionally explicit; older export cannot qualify.
    """
    import nbtlib
    WORLD=Path(world) if world is not None else globals()['WORLD']
    base=WORLD.parent
    nav_receipt=base/'navigation_rebuild/export_after_art_20261012/APPLIED.json'
    travel_receipt=base/'travel_binding/after_art_20261012/APPLIED.json'
    nav=json.loads(nav_receipt.read_text('utf8'));travel=json.loads(travel_receipt.read_text('utf8'))
    need(nav.get('world_written')is True and nav.get('nearest_lift_unresolved')==0,'Current post-art navigation receipt required')
    graph_path=WORLD/'nerv_routes_r24.json.gz';nearest_path=WORLD/'nearest_lift_paths_r44.json.gz'
    for name in ('nerv_routes_r24.json.gz','nearest_lift_paths_r44.json.gz'):
        need(sha(WORLD/name)==nav['files'][name]==sha(nav_receipt.parent/name),'Current live navigation differs from actual post-art export: '+name)
    graph=json.loads(gzip.decompress(graph_path.read_bytes()));nearest=json.loads(gzip.decompress(nearest_path.read_bytes()))
    need(graph.get('r52_navigation')is True and len(graph['nodes'])==len(nearest['nodes'])==nav['nodes']
         and nearest['graph_sha256']==sha(graph_path),'Current graph/nearest-lift identity or node coverage differs')
    travel_path=WORLD/'r52/travel.json';arrivals=json.loads(travel_path.read_text('utf8'))
    need(Path(travel['file']).resolve()==travel_path.resolve() and travel['sha256']==sha(travel_path)
         and len(arrivals['destinations'])==travel['destinations'] and arrivals['measured']is True and not arrivals['issues'],
         'Current actual post-art TP arrival table differs')
    translations={}
    for name in ('r47_seele_conference.json','r48_seele_lighting.json'):
        row=json.loads((WORLD/name).read_text('utf8'));need(row.get('r52_root_translation')==[0,-93,0],'Current already-translated facility frame missing: '+name)
        translations[name]=row['r52_root_translation']
    chamber_rel='dimensions/projectseele/geofront/data/projectseele_dead_sea_chamber_r45.dat'
    chamber=nbtlib.load(WORLD/chamber_rel)['data']
    need(int(chamber.get('FrameOffsetYR52',0))==-93 and len(chamber['Images'])==10 and len(chamber['Readers'])==2,'Current ten-image/two-reader highest chamber frame missing')
    need(any(str(i.get('NBT',{}).get('Artwork',''))=='tree_ink' for i in chamber['Images']), 'Highest chamber saved closed image would restore the old paper tree')
    from query_blocks import iter_block_entities,read_box
    from facility_frame_nbt_r52 import unpack_position
    from regional_voxels import canonical_state
    if str(chamber['Mode'])=='CLOSED':
        for image in chamber['Images']:
            position=unpack_position(image['Pos']);state=image['State'];props=state.get('Properties',{})
            expected=canonical_state(str(state['Name'])+('['+','.join(str(k)+'='+str(v) for k,v in props.items())+']' if props else''))
            need(read_box(WORLD,'projectseele:geofront',position,position)[position]==expected,'Current highest-room closed state image differs')
            tags=dict(iter_block_entities(WORLD,'projectseele:geofront',position,position))
            if 'NBT' in image:
                actual=copy.deepcopy(tags.get(position,nbtlib.Compound()));saved=copy.deepcopy(image['NBT'])
                for row in (actual,saved):
                    if int(row.get('keepPacked',0))==0:row.pop('keepPacked',None)
                need(actual==saved,'Current highest-room full NBT closed image differs')
            else:need(not tags,'Unexpected current highest-room image block entity')
    art=[]
    for position,face in [((30,-422,327),'up'),((30,-409,327),'down'),((30,-415,339),None)]:
        actual=dict(iter_block_entities(WORLD,'projectseele:geofront',position,position)).get(position)
        need(actual is not None and str(actual.get('Artwork',''))=='tree_ink' and int(actual.get('Tint',0))==int('ff996080',16)-(1<<32), 'Current actual highest-room ink artwork missing: '+str(position))
        if face:need(str(actual.get('SurfaceFacing',''))==face,'Current actual floor/ceiling artwork facing differs')
        art.append({'position':list(position),'surface_facing':str(actual.get('SurfaceFacing','legacy')),'artwork':str(actual['Artwork'])})
    # This region contains the actual three artworks. Hash the live region,
    # rather than copying a pre-art section or old QA snapshot into delivery.
    art_region='dimensions/projectseele/geofront/region/r.0.0.mca'
    names=['nerv_routes_r24.json.gz','nearest_lift_paths_r44.json.gz','r52/travel.json',
           'r47_seele_conference.json','r48_seele_lighting.json',chamber_rel,art_region]
    return {'source':'CURRENT_ROOT_WORLD_ONLY_NO_RETRANSLATION','world':str(WORLD.resolve()),
            'files':{name:sha(WORLD/name) for name in names},'navigation_nodes':nav['nodes'],'travel_destinations':travel['destinations'],
            'navigation_receipt':{'path':str(nav_receipt),'sha256':sha(nav_receipt)},'travel_receipt':{'path':str(travel_receipt),'sha256':sha(travel_receipt)},
            'already_translated_frames':translations,'highest_chamber_frame_y':-93,'highest_chamber_closed_images':10,
            'highest_chamber_readers':2,'actual_ink_artworks':art,'native_visual_validation':'NOT_PERFORMED_BY_METADATA_AUDIT'}


def selection(path):
    d=json.loads(path.read_text('utf8'));need(d['schema']=='projectseele.r52.root-release-selection.v1','Explicit R52 Root selection required')
    scope=str(d.get('feature_scope','full'));context=d.get('release_context')
    if scope=='124':
        from release_scope124_r53 import validate_context
        validate_context(context);need(d.get('root_world_authority')==context['root_world_authority'],'Release current-world authority differs')
    else:need(scope=='full' and context is None,'Unknown or mixed release context')
    world=Path(context['root_world_authority']['world']) if context else WORLD
    jar=selected_file(d['jar']);runtime={safe(name):selected_file(row,context['runtime'] if context else None)for name,row in d['runtime'].items()}
    if context:need(all(path==Path(context['runtime']).resolve()/name for name,path in runtime.items()),'Runtime members must match the exact explicitly selected runtime directory')
    need(all('/'not in name for name in runtime),'Runtime binding must use exact original filenames')
    contract=json.loads(runtime['combat_bundle_r44.json'].read_text('utf-8-sig'))
    for name,digest in contract['files'].items():need(name in runtime and sha(runtime[name])==digest,'Actual runtime bundle member differs: '+name)
    with zipfile.ZipFile(jar)as z:
        need(len(z.namelist())==len(set(z.namelist())),'Duplicate final JAR members')
        need(class_protocol(z.read('com/projectseele/network/SeeleNetwork.class'))==str(d['protocol']),'Selected final protocol differs')
        for name,digest in d['required_jar_assets'].items():need(hashlib.sha256(z.read(name)).hexdigest()==digest,'Final selected source asset differs: '+name)
    acceptance=selected_file(d['acceptance']);report=json.loads(acceptance.read_text('utf8'))
    validate_acceptance(report)
    need(str(report.get('feature_scope','full'))==scope,'Selection and actual acceptance scope differ')
    need(d.get('release_type','accepted_release')==report.get('release_type','accepted_release'),
         'Package label must preserve the actual manual/accepted release status')
    need(report['jar_sha256']==d['jar']['sha256']and Path(report['world']).resolve()==world.resolve(),'Acceptance refers to another JAR/world')
    if code_reviewed(report):
        need(d.get('qualification')==report['qualification'] and d.get('private_delivery')is True and d.get('manual_acceptance_required')is True,'Private manual acceptance qualification cannot be erased')
    evidence=d.get('selection_evidence',{})
    offline=offline_manual(report) or code_reviewed(report)
    need(scope!='124' or not offline or code_reviewed(report),'Current124 offline qualification must have explicit code-review scope')
    expected={'build_receipt','source_before','offline_world_inputs','baseline_inputs'} if offline else {'build_receipt','source_before','native_inputs','native_result','baseline_inputs'}
    need(set(evidence)==expected,'Exact final build/world/baseline selection evidence required')
    for name,row in evidence.items():
        p=Path(row['path']);need(p.is_file() and sha(p)==row['sha256'],'Final selection evidence changed: '+name)
    from build_immutable_r52_candidate import snapshot,frozen_build_class_pins
    need(snapshot()==json.loads(Path(evidence['source_before']['path']).read_text('utf-8-sig')),'Production inputs changed after final source selection')
    frozen_build_class_pins(evidence['build_receipt']['path'],jar)
    # Recheck the exact successful Root install/cold binding at package time,
    # including all formal external mods. A prepared/failed C10 receipt cannot
    # qualify a newer selected Jar just because an acceptance label says PASS.
    from prepare_r52_release_selection import native_inputs,offline_world_inputs
    actual=offline_world_inputs(Path(evidence['offline_world_inputs']['path']),jar,d['jar']['sha256'],context=context) if offline else native_inputs(Path(evidence['native_inputs']['path']).parent,jar,d['jar']['sha256'],context=context)
    need(actual=={n:sha(p) for n,p in runtime.items()},'Package verified portable runtime differs')
    need(d.get('world_metadata_pins')==current_world_metadata_pins(world,scope,context['root_world_authority'] if context else None),'Selected World navigation/art/saved metadata changed; never copy an old export or rerun translation')
    if scope=='124':
        from release_scope124_r53 import validate_current_bindings
        validate_current_bindings(report,context,evidence['build_receipt']['path'],None if code_reviewed(report) else Path(evidence['native_inputs']['path']).parent,d['world_metadata_pins'])
    return d,jar,runtime


def world_files(world=None,scope='full',authority=None):
    WORLD=Path(world) if world is not None else globals()['WORLD']
    if scope=='124':
        from root_bundle_authority_r53 import validate_record
        validate_record(authority);need(WORLD.resolve()==Path(authority['world']).resolve(),'Explicit current construction World differs')
    else:need(scope=='full' and WORLD.resolve()==Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/WORLD_R52').resolve(),'Wrong legacy full-scope construction world')
    files={}
    for p in WORLD.rglob('*'):
        need(not p.is_symlink()and not p.is_junction(),'World links must not select another save: '+str(p))
        if not p.is_file():continue
        name=p.relative_to(WORLD).as_posix()
        # Dot-prefixed Project SEELE ownership/freeze markers are live data.
        # Dropping them would reactivate retired generators in the delivered world.
        if name=='session.lock' or any(part in {'.git','.idea','__pycache__'}for part in p.relative_to(WORLD).parts):continue
        need(not name.endswith(('.tmp','.part')),'World contains unfinished write: '+name)
        files[safe(name)]=p
    required={'level.dat','ROOT_ASSEMBLY_BUNDLE.json','personnel_lifts_r52.json'} if scope=='124' else {'level.dat','r52/travel.json','surface_angel_assault_r52.json'}
    need(required<=files.keys(),'Actual selected-scope World metadata absent')
    return files


def generated(side,old,config):
    prefix='overrides/'if side=='client'else'';changes={}
    if side=='client':
        manifest=json.loads(old.read('manifest.json'));need(manifest['manifestVersion']==1 and manifest['overrides']=='overrides','Keep actual PCL-compatible CurseForge layout')
        manifest['name']='EVANGELION:Encore R52';manifest['version']='R52-'+config['date']+'-PCL'
        changes['manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        setup=old.read('overrides/PCL/Setup.ini')
        if b'VersionArgumentTitle:' not in setup:
            need(hashlib.sha256(setup).hexdigest()=='3e36b70b59f12d9829c7809eec50c1c07c26297466a434dc5cf7b1ddfc538375', 'Unknown original PCL settings without a title')
            setup+=b'VersionArgumentTitle:EVANGELION:Encore R52\r\n'
        changes['overrides/PCL/Setup.ini']=re.sub(rb'(?m)^VersionArgumentTitle:[^\r\n]*',b'VersionArgumentTitle:EVANGELION:Encore R52',setup)
    else:
        props=old.read('server.properties');need(len(re.findall(rb'(?m)^level-name=',props))==1 and len(re.findall(rb'(?m)^motd=',props))==1,'Original server properties differ')
        props=re.sub(rb'(?m)^level-name=[^\r\n]*',b'level-name=SEELE_R52_WORLD',props)
        rows=props.splitlines(keepends=True)
        for i,line in enumerate(rows):
            if line.startswith(b'motd='):
                if config.get('feature_scope')=='124':
                    need(re.search(rb'EVANGELION:Encore R[0-9]+',line) is not None,'Pinned formal baseline NERV MOTD differs')
                    rows[i]=re.sub(rb'EVANGELION:Encore R[0-9]+',b'EVANGELION:Encore R52',line)
                else:
                    need(b'EVANGELION:Encore R51'in line,'Original NERV MOTD differs');rows[i]=line.replace(b'EVANGELION:Encore R51',b'EVANGELION:Encore R52')
        changes['server.properties']=b''.join(rows)
    if code_reviewed(config):
        label_key='overrides/PCL/Setup.ini' if side=='client' else 'server.properties'
        changes[label_key]=changes[label_key].replace(b'EVANGELION:Encore R52',b'EVANGELION:Encore R52 [Manual Acceptance - Runtime Unverified]')
    for name,row in config['documents'].items():changes[prefix+safe(name)]=selected_file(row)
    changes[prefix+'R52_BATCH.json']=(json.dumps(dict(release='R52',date=config['date'],protocol=config['protocol'],kind=side,
        jar_sha256=config['jar']['sha256'],acceptance_sha256=config['acceptance']['sha256'],world='SEELE_R52_WORLD'if side=='server' or config.get('feature_scope')=='124' else None,feature_scope=config.get('feature_scope','full'),
        release_type=config.get('release_type','accepted_release'),qualification=config.get('qualification'),private_delivery=config.get('private_delivery',False),manual_acceptance_required=config.get('manual_acceptance_required',False),
        source='R51 original R50 world plus Root measured R52 construction; no QA progress imported'),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    return changes


def world_payload(files,side,scope):
    need(side in ('server','client') and scope in ('full','124'),'Explicit package side/scope required')
    if side=='client' and scope=='full':return {}
    prefix='SEELE_R52_WORLD/' if side=='server' else 'overrides/saves/SEELE_R52_WORLD/'
    return {prefix+safe(name):path for name,path in files.items()}


def execute(config,jar,runtime,delivery,out):
    need(delivery.resolve()in{(ROOT/'delivery').resolve(),Path('D:/eva/delivery').resolve()},'Use the named delivery folder')
    context=config.get('release_context');scope=str(config.get('feature_scope','full'));world=Path(context['root_world_authority']['world']) if context else WORLD
    baselines={k:Path(v['path']) for k,v in context['baseline_packages'].items()} if context else BASELINES
    lock=(world/'session.lock').open('r+b');msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        need(config.get('world_metadata_pins')==current_world_metadata_pins(world,scope,context['root_world_authority'] if context else None),'World metadata changed after release selection')
        files=world_files(world,scope,context['root_world_authority'] if context else None);world_hashes={name:sha(p)for name,p in files.items()};results=[];delivery.mkdir(parents=True,exist_ok=True)
        for side,suffix in [('server','Server'),('client','Client_PCL')]:
            label='CodeReviewed_ManualAcceptance' if code_reviewed(config) else 'R52';target=delivery/f"Project_SEELE_Encore_{label}_{config['date']}_{suffix}.zip";need(not target.exists(),'Preserve an existing delivered package')
            temp=target.with_suffix('.zip.part-'+uuid.uuid4().hex);prefix='overrides/'if side=='client'else''
            with zipfile.ZipFile(baselines[side])as old:
                need(len(old.namelist())==len(set(old.namelist())),'Baseline duplicates')
                changes=generated(side,old,config);changes[prefix+MOD]=jar
                changes.update({prefix+'projectseele-local-maps/'+name:p for name,p in runtime.items()})
                changes.update(world_payload(files,side,scope))
                retired={n for n in old.namelist()if n.startswith(('SEELE_R50_WORLD/','SEELE_R51_WORLD/'))or PurePosixPath(n).name in {'R51_BATCH.json','README_R51.zh.md','NONMAP_STATUS_R51.md'}}
                if scope=='124':
                    retired.update(n for n in old.namelist() if re.match(r'^(?:overrides/saves/)?SEELE_R[0-9]+_WORLD/',n) or n.startswith(prefix+'projectseele-local-maps/'))
                retained=set(old.namelist())-retired-set(changes)
                need(not any(n.startswith('overrides/saves/')for n in retained),'Client must not inherit an unrelated test save')
                with zipfile.ZipFile(temp,'x',allowZip64=True)as archive:
                    for info in old.infolist():
                        safe(info.filename.rstrip('/'))
                        if info.filename not in retained:continue
                        with old.open(info)as source,archive.open(copy.copy(info),'w',force_zip64=True)as dest:shutil.copyfileobj(source,dest,1024*1024)
                    for name,value in changes.items():
                        safe(name)
                        if isinstance(value,Path):archive.write(value,name,compress_type=zipfile.ZIP_STORED if value.suffix in {'.jar','.mca','.gz'}else zipfile.ZIP_DEFLATED)
                        else:archive.writestr(name,value,compress_type=zipfile.ZIP_DEFLATED)
                with zipfile.ZipFile(temp)as actual:
                    need(len(actual.namelist())==len(set(actual.namelist()))and set(actual.namelist())==retained|set(changes),'Delivered ZIP inventory differs')
                    for name in retained:
                        with old.open(name)as a,actual.open(name)as b:need(equal(a,b),'Unexpected baseline change: '+name)
                    for name,value in changes.items():
                        if isinstance(value,Path):
                            with value.open('rb')as a,actual.open(name)as b:need(equal(a,b),'Delivered selected payload differs: '+name)
                        else:need(actual.read(name)==value,'Delivered generated payload differs: '+name)
                need(sha(jar)==config['jar']['sha256'],'Final JAR changed during packaging')
                os.replace(temp,target);results.append(dict(side=side,path=str(target),sha256=sha(target),bytes=target.stat().st_size,all_members_byte_readback=True,unchanged_baseline_members=len(retained)))
        need({name:sha(p)for name,p in files.items()}==world_hashes,'World changed during final packaging')
        (out/'EXECUTION_RECEIPT_R52.json').write_text(json.dumps(dict(archives=results,world_files=world_hashes,world_written=False,
            acceptance_record=config['acceptance'],native_acceptance=None if code_reviewed(config) else config['acceptance'],qualification=config.get('qualification'),native_verified=False if code_reviewed(config) else None,client_server_same_jar=True,client_server_same_world=scope=='124',feature_scope=scope),ensure_ascii=False,indent=2),'utf8')
        print(json.dumps(results,ensure_ascii=False))
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--selection',type=Path,required=True);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--delivery',type=Path,default=Path('D:/eva/delivery'));args=parser.parse_args()
    config,jar,runtime=selection(args.selection);out=ROOT/'artifacts/r52_final_packages';out.mkdir(exist_ok=True)
    context=config.get('release_context');world=Path(context['root_world_authority']['world']) if context else WORLD
    baselines={k:Path(v['path']) for k,v in context['baseline_packages'].items()} if context else BASELINES
    for side,path in baselines.items():need(sha(path)==config['baseline_sha256'][side],'Selected delivered dependency baseline differs')
    need(re.fullmatch(r'\d{8}',config['date'])is not None,'Explicit release date required')
    (out/'PACK_PLAN_R52.json').write_text(json.dumps(dict(selection=str(args.selection.resolve()),world=str(world),jar=str(jar),
        runtime_files=len(runtime),execute=args.execute,source_world_written=False),indent=2),'utf8')
    if args.execute:execute(config,jar,runtime,args.delivery,out)
    else:print('R52 selection verified; packaging not executed')


if __name__=='__main__':main()
