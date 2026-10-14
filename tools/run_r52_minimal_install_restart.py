"""Root-controlled real install/save/cold-restart; no world copy or gameplay tour.

Default prepares an isolated small host using the existing dedicated libraries
and configuration. --run explicitly starts it against the selected actual World.
"""
from pathlib import Path
import argparse, hashlib, json, math, msvcrt, os, re, shutil, subprocess, time, uuid, zipfile
from launch_rendered_client_r17 import java_environment
from build_immutable_r52_candidate import frozen_build_class_pins
from prepare_r52_runtime_deployment_candidate import relative, reference, declared_controller_inputs
from root_bundle_authority_r53 import arguments as authority_arguments, validate as world_authority, original_identities, candidate as candidate_path
from r52_spatial_plan import BASE
WORLD=BASE/'WORLD_R52'
from wet_front_seal_manifest_r52 import sealed_front_specs

REPO=Path(__file__).resolve().parents[1]
LAUNCH=Path('D:/eva/artifacts/rebuild_r49/native_session/original_npc_01/launch.json')
SERVER=Path('D:/eva/artifacts/rebuild_r49/native_qa/game')
MTR=REPO/'artifacts/r52_hq_rail_boundary/MTR-forge-4.0.5+1.20.1.jar'
MTR_SHA='97466eb715ab02f50a7f7e23f920bf9fdd9d5e4bbb12620c06c6751324c66e9a'
SERVER_RELEASE=Path('D:/eva/delivery/Project_SEELE_Encore_R51_20261009_Server.zip')
OBSERVER=REPO/'.codex/r52_continuous_delivery_tools'
AGENT=OBSERVER/'r52_lifecycle_readonly_agent.jar'
ATTACH=OBSERVER/'observer_classes'
OBSERVER_RECEIPT=OBSERVER/'OBSERVER_COMPILE_RECEIPT.json'

def need(value, reason):
    if not value: raise ValueError(reason)
def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path): return json.loads(Path(path).read_text('utf-8-sig'))
def write(path, data): Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
def quote(arg):
    need(not any(x in arg for x in '\r\n\0'),'Unsafe Java argument')
    return '"'+arg.replace('\\','\\\\').replace('"','\\"')+'"'
def copy_file(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    try: os.link(source,target)
    except OSError: shutil.copyfile(source,target)
    need(sha(source)==sha(target),'Host byte copy differs')
def check_world_unlocked(world):
    # Use the same native byte-range lock as existing Root world tools; release before Java.
    path=world/'session.lock';need(path.is_file(),'Actual existing native World/session.lock required')
    with path.open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
def entity_index(world,empty_regions=None):
    from transplant_s22_authority import read_region,parse_chunk
    result={}
    def visit(row,dimension):
        if 'UUID' in row:
            words=[int(x)&0xffffffff for x in row['UUID']];need(len(words)==4,'Actual typed128-bit original identity required')
            identity=str(uuid.UUID(int=sum(x<<(96-32*i) for i,x in enumerate(words))))
            value={'type':str(row['id']),'dimension':dimension}
            need(identity not in result,'Duplicate serialized UUID in actual World: '+identity);result[identity]=value
        for child in row.get('Passengers',[]):visit(child,dimension)
    for file in sorted(world.rglob('entities/r.*.mca')):
        size=file.stat().st_size
        if size==0:
            if empty_regions is not None:empty_regions.append(file.relative_to(world).as_posix())
            continue
        need(size>=8192,'Nonempty truncated entity region: '+str(file))
        dimension=file.parent.parent.relative_to(world).as_posix()
        if dimension=='.':dimension='overworld'
        for blob in read_region(file)[1]:
            if blob is not None:
                root=parse_chunk(blob)
                for row in root.get('Entities',[]):visit(row,dimension)
    return result
def native_state(row):
    import nbtlib
    root=nbtlib.parse_nbt(row['actual_source_nbt'])
    role=row['role'];keys={'silo_gate':['R52DeclaredHatch'],'hangar_gate':['R52SideStack'],
        'fixed_cannon':['GunGeometryR52','GunCradleR52','GunAimR52','GunLoadedR52','GunReadyR52']}[role]
    def canonical(value):
        if hasattr(value,'items'): return {k:canonical(v) for k,v in sorted(value.items())}
        if isinstance(value,(list,tuple)) or hasattr(value,'dtype') and getattr(value,'ndim',0)>0: return [canonical(v) for v in value]
        return {'type':type(value).__name__,'value':str(value)}
    need(all(k in root for k in keys),'Actual complete persisted controller state missing')
    return {key:canonical(root[key]) for key in keys}

def validate_sealed_native_specs(rows,gates):
    """Compare selected real Spec to actual save NBT on both boots.

    Comparing two equally incomplete old NBT snapshots is not admission.
    """
    import nbtlib
    actual={r['uuid']:r for r in rows};verified=[]
    for name,seal in sealed_front_specs(gates).items():
        g=seal['gate'];row=actual.get(str(uuid.UUID(g['visual'])))
        need(row is not None and row['role']=='hangar_gate','Actual original sealed-front UUID/role missing: '+name)
        root=nbtlib.parse_nbt(row['actual_source_nbt']);stack=root.get('R52SideStack');need(isinstance(stack,nbtlib.Compound),'Actual sealed front full persisted stack missing: '+name)
        spec=stack.get('Spec');need(isinstance(spec,nbtlib.Compound) and not bool(spec.get('GeometryMissing',False)),'Actual sealed front geometry is missing/held: '+name)
        for field,expected in [('Width',g['width']),('Height',g['height'])]:need(field in spec and isinstance(spec[field],nbtlib.Float) and math.isclose(float(spec[field]),expected,rel_tol=1e-7,abs_tol=1e-6),'Actual selected front dimension differs: '+name+'/'+field)
        hs=g['hangar_stack']
        for field,expected in [('OpenTicks',hs['open_ticks']),('CloseTicks',hs['close_ticks']),('DepthDirection',hs.get('depth_direction',1))]:need(isinstance(spec.get(field),nbtlib.Int) and int(spec[field])==expected,'Actual selected front timing/direction differs: '+name+'/'+field)
        f=spec.get('FloorSeal');version=hs['floor_seal'].get('version',1);need(isinstance(f,nbtlib.Compound) and isinstance(f.get('Version'),nbtlib.Int) and int(f['Version'])==version,'Actual selected floor seal/version missing: '+name)
        if version==2:need(isinstance(f.get('RetainedBoxCount'),nbtlib.Int) and int(f['RetainedBoxCount'])==hs['floor_seal']['retained_box_count'],'Actual retained original floor mechanism changed: '+name)
        for field,key in [('DropM','drop_m'),('RetreatLocalZ','retreat_local_z_m')]:need(isinstance(f.get(field),nbtlib.Double) and float(f[field])==hs['floor_seal'][key],'Actual selected floor seal travel differs: '+name+'/'+field)
        boxes=f.get('ClosedBoxes');expected=hs['floor_seal']['closed_boxes']
        need(isinstance(boxes,nbtlib.List) and len(boxes)==len(expected),'Actual selected physical closed seal boxes missing: '+name)
        for actual_box,wanted in zip(boxes,expected):need(isinstance(actual_box,nbtlib.List) and len(actual_box)==6 and all(isinstance(v,nbtlib.Double) and float(v)==w for v,w in zip(actual_box,wanted)),'Actual selected floor seal box differs: '+name)
        verified.append({'resource':name,'uuid':row['uuid'],'closed_box_count':len(expected)})
    return verified
def main():
    global OBSERVER,AGENT,ATTACH,OBSERVER_RECEIPT
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build-receipt',type=Path,required=True);ap.add_argument('--jar',type=Path,required=True);ap.add_argument('--jar-sha256',required=True)
    ap.add_argument('--deployment',type=Path,required=True);ap.add_argument('--deployment-sha256',required=True)
    ap.add_argument('--scope',choices=['full','124'],default='full')
    authority_arguments(ap,required=False)
    ap.add_argument('--original-identities',type=Path);ap.add_argument('--original-identities-sha256')
    ap.add_argument('--server-release-sha256')
    ap.add_argument('--observer-dir',type=Path,help='Exact current standalone observer compile output')
    ap.add_argument('--runtime',type=Path,required=True)
    ap.add_argument('--server-template',type=Path,default=SERVER);ap.add_argument('--launch-template',type=Path,default=LAUNCH)
    ap.add_argument('--mtr',type=Path,default=MTR,help='Same exact MTR4.0.5 binary used by the delivered world and measured native railway')
    ap.add_argument('--server-release',type=Path,default=SERVER_RELEASE,help='Complete already-delivered mod and configuration set; never use the old reduced geometry fixture')
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--run',action='store_true')
    ap.add_argument('--heap',choices=['4G','5G','6G'],default='6G');ap.add_argument('--startup-timeout',type=int,default=300)
    ap.add_argument('--install-timeout',type=int,default=900);ap.add_argument('--retry-seconds',type=int,default=10)
    ap.add_argument('--first-boot-jfr',action='store_true',help='Root-authorized single actual first-boot 30-second profile; no heap/watchdog/admission change')
    args=ap.parse_args()
    need(args.world is not None,'Explicit actual World required')
    authority=None
    if args.scope=='124':
        need(all(getattr(args,n) is not None for n in ('baseline','root_plan','baseline_sha256','root_plan_sha256','original_identities','original_identities_sha256','server_release_sha256','observer_dir')), 'Scope124 requires explicit Root authority, original identity baseline, observer and dependency archive SHA')
        authority=world_authority(args)
        original=original_identities(args.original_identities,args.original_identities_sha256,args.world)
        baseline_path=args.original_identities.resolve()
    else:
        baseline_path=REPO/'artifacts/r52_delivery_preparation/ORIGINAL_WORLD_IDENTITIES_BEFORE_INSTALL.json'
        original=read(baseline_path)['managed_geofront']
    identity_sha=sha(baseline_path)
    if args.observer_dir:
        OBSERVER=candidate_path(args.observer_dir,args.world);AGENT=OBSERVER/'r52_lifecycle_readonly_agent.jar';ATTACH=OBSERVER/'observer_classes';OBSERVER_RECEIPT=OBSERVER/'OBSERVER_COMPILE_RECEIPT.json'
    for key in ['build_receipt','jar','deployment','world','runtime','server_template','launch_template','out']:setattr(args,key,getattr(args,key).resolve())
    if args.scope=='full':need(args.world==WORLD.resolve(),'Only the original full-scope World authority is admitted')
    candidate_path(args.out,args.world)
    need(not args.out.exists(),'Fresh isolated attempt directory required')
    need(5<=args.retry_seconds<=60 and 30<=args.install_timeout<=1800 and 30<=args.startup_timeout<=600,'Bounded install/startup intervals required')
    need(sha(args.jar)==args.jar_sha256 and sha(args.deployment)==args.deployment_sha256,'Selected immutable JAR/deployment SHA differs')
    need(args.mtr.is_file() and sha(args.mtr)==MTR_SHA,'Actual required native MTR4.0.5 source must match the delivered railway binary')
    if args.scope=='124':need(re.fullmatch(r'[0-9a-f]{64}',args.server_release_sha256) and sha(args.server_release)==args.server_release_sha256,'Explicit delivered server dependency archive SHA differs')
    else:need(args.server_release.resolve()==SERVER_RELEASE.resolve() and args.server_release.is_file(),'Actual delivered R51 server dependency set required')
    server_release_sha=sha(args.server_release)
    class_pins=frozen_build_class_pins(args.build_receipt,args.jar);build_receipt_sha=sha(args.build_receipt)
    deployment=read(args.deployment)
    need(deployment['ready'] is True and Path(deployment['world']).resolve()==args.world,'Complete selected actual-controller deployment required')
    if authority:need(deployment.get('root_world_authority')==authority and deployment.get('feature_scope')=='124','Deployment must bind the exact current scope124 authority')
    bundle_relative='ROOT_ASSEMBLY_BUNDLE.json';bundle=args.world/bundle_relative
    candidate_bundle=next(Path(r['candidate']) for r in deployment['files'] if r['world_relative']==bundle_relative)
    world_pins={r['world_relative']:r['sha256'] for r in deployment['files']}
    if args.scope=='124':
        from release_scope124_r53 import navigation_pins
        world_pins.update(navigation_pins(args.world))
    selected_bundle,declared=declared_controller_inputs(candidate_bundle);controllers={r['uuid']:r['role'] for r in declared};controller_count=len(controllers)
    _,owner_path=reference(candidate_bundle.parent,selected_bundle['mechanical_owner'],'file');selected_gates=read(owner_path)['gates']
    need(deployment['expected_controllers']==declared and deployment['expected_controller_count']==controller_count,'Deployment exact UUID/role set differs from actual owner/directory/cannon')
    need(sha(bundle)==deployment['bundle_sha256']==sha(candidate_bundle),'Actual World-root bundle differs from selected candidate')
    observer=read(OBSERVER_RECEIPT)
    need(observer['compile_passed'] is True and observer['agent_sha256']==sha(AGENT)
         and all(sha(REPO/name)==digest for name,digest in observer['source_sha256'].items())
         and all(sha(ATTACH/name)==digest for name,digest in observer['class_sha256'].items()),'Current compiled readonly lifecycle observer/source receipt required')
    agent_sha=sha(AGENT);observer_sha=sha(OBSERVER_RECEIPT);launch_sha=sha(args.launch_template)
    runtime_pins={p.relative_to(args.runtime).as_posix():sha(p) for p in args.runtime.rglob('*') if p.is_file()}
    need('combat_bundle_r44.json' in runtime_pins,'Actual final portable runtime directory required')
    def locked_inputs():
        need(sha(baseline_path)==identity_sha and sha(args.server_release)==server_release_sha,'Original identities or full dependency archive changed')
        if authority:need(world_authority(args)==authority,'Current Root declaration changed')
        need(sha(args.jar)==args.jar_sha256 and sha(args.build_receipt)==build_receipt_sha and sha(args.deployment)==args.deployment_sha256 and sha(AGENT)==agent_sha and sha(OBSERVER_RECEIPT)==observer_sha and all(sha(REPO/name)==digest for name,digest in observer['source_sha256'].items()) and sha(args.launch_template)==launch_sha,'Selected source/tool authority changed')
        for name,digest in world_pins.items():need(sha(args.world/relative(name).as_posix())==digest,'Actual World metadata changed: '+name)
        for name,digest in runtime_pins.items():need(sha(args.runtime/name)==digest,'Selected runtime changed: '+name)
    locked_inputs();check_world_unlocked(args.world)
    spec=read(args.launch_template);command=list(spec['command'])
    need(command[command.index('--launchTarget')+1]=='forgeserver','Existing dedicated Forge launch only')
    need(not spec.get('environment'),'Review environment in old template requires explicit review')
    need(not any(x.startswith('-Dprojectseele.') for x in command),'Review/resource/admission overrides in old template are not normal production')
    for key in ['--world','--universe']:
        if key in command:i=command.index(key);del command[i:i+2]
    command=[x for x in command if not x.startswith(('-Xms','-Xmx'))]
    command[1:1]=['-Xms512m','-Xmx'+args.heap,'-Dprojectseele.combatBundleDirectory=projectseele-local-maps']
    command+=['--universe',args.world.parent.as_posix(),'--world',args.world.name]
    java,env=java_environment();command[0]=(java/'bin/java.exe').as_posix();env.pop('MOD_CLASSES',None)
    need(not any('-Dprojectseele.' in env.get(k,'') for k in ['JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS']),'Inherited Java review options require explicit review')
    for item in command:
        if item.startswith('-DlibraryDirectory='):need(Path(item.split('=',1)[1]).is_dir(),'Retained dedicated library directory unavailable')
    args.out.mkdir(parents=True);host=args.out/'host';host.mkdir()
    delivered_members={}
    with zipfile.ZipFile(args.server_release) as archive:
        need(len(archive.namelist())==len(set(archive.namelist())),'Delivered dependency archive contains duplicate members')
        for item in archive.infolist():
            if item.is_dir():continue
            name=item.filename
            if not name.startswith(('mods/','config/','defaultconfigs/')):continue
            need('\\' not in name and ':' not in name and all(part not in ('','.','..') for part in name.split('/')),'Unsafe delivered host member')
            if name.startswith('mods/projectseele-'):continue
            destination=(host/name).resolve();need(destination.is_relative_to(host.resolve()),'Host member escaped selected host')
            destination.parent.mkdir(parents=True,exist_ok=True)
            digest=hashlib.sha256()
            with archive.open(item) as source,destination.open('xb') as target:
                while chunk:=source.read(1024*1024):target.write(chunk);digest.update(chunk)
            need(destination.stat().st_size==item.file_size and sha(destination)==digest.hexdigest(),'Actual delivered host member differs')
            delivered_members[name]=digest.hexdigest()
    need([n for n in delivered_members if n.startswith('mods/') and n.endswith('.jar')] and (args.scope=='124' or len([n for n in delivered_members if n.startswith('mods/') and n.endswith('.jar')])==16),'Complete selected delivered external mods required before actual World load')
    need(delivered_members.get('mods/'+MTR.name)==MTR_SHA,'Delivered actual railway binary differs')
    need(re.search(r'(?m)^eula=true\s*$',(args.server_template/'eula.txt').read_text('utf8')),'Reuse an existing Root EULA agreement; never auto-accept')
    shutil.copyfile(args.server_template/'eula.txt',host/'eula.txt')
    props=(args.server_template/'server.properties').read_text('utf-8-sig').splitlines()
    settings={'server-ip':'127.0.0.1','server-port':'0','enable-rcon':'false','enable-query':'false','level-name':args.world.name}
    props=[line for line in props if line.partition('=')[0] not in settings];props += [key+'='+value for key,value in settings.items()]
    (host/'server.properties').write_text('\n'.join(props)+'\n','utf8')
    shutil.copyfile(args.jar,host/'mods/projectseele-0.1.0-all.jar')
    shutil.copytree(args.runtime,host/'projectseele-local-maps')
    launch_args=args.out/'launch.args';launch_args.write_text('\n'.join(quote(x) for x in command[1:])+'\n','utf8')
    empty_regions=[];all_before=entity_index(args.world,empty_regions)
    # Preserve exact same-World serialized originals before any entity decode.
    # A rejected subclass constructor must never make its old NBT unrecoverable.
    entity_backups={}
    for source in sorted(args.world.rglob('entities/r.*.mca')):
        data=source.read_bytes();digest=hashlib.sha256(data).hexdigest()
        target=args.out/'entity_regions_before_boot'/source.relative_to(args.world)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        need(sha(target)==digest and sha(source)==digest,'Exact quiescent preboot entity-region backup differs')
        entity_backups[source.relative_to(args.world).as_posix()]=digest
    other_before={k:v for k,v in all_before.items() if v['dimension']!='dimensions/projectseele/geofront'}
    need(original and all(all_before.get(k)==v for k,v in original.items()),'Every actual pre-install original UUID/type/dimension must still be present')
    host_pins={p.relative_to(host).as_posix():sha(p) for p in host.rglob('*') if p.is_file()}
    prepared={'prepared_only':not args.run,'world':str(args.world),'jar':str(args.jar),'jar_sha256':args.jar_sha256,'build_receipt':str(args.build_receipt),'build_receipt_sha256':build_receipt_sha,'compiled_delivery_class_sha256':class_pins,'deployment':str(args.deployment),'deployment_sha256':args.deployment_sha256,
        'world_metadata_sha256':world_pins,'runtime_sha256':runtime_pins,'initial_host_sha256':host_pins,'agent_sha256':agent_sha,'observer_receipt_sha256':observer_sha,'observer_source_sha256':observer['source_sha256'],'launch_template_sha256':launch_sha,
        'required_mtr_source':str(args.mtr.resolve()),'required_mtr_sha256':MTR_SHA,'full_delivered_dependency_source':str(args.server_release.resolve()),'full_delivered_host_members':delivered_members,
        'geofront_original_identities':original,'original_identity_baseline_sha256':sha(baseline_path),'all_dimensions_before':all_before,'other_dimensions_before':other_before,'other_dimension_identity_count':len(other_before),
        'expected_controllers':controllers,'expected_controller_count':controller_count,'empty_entity_region_files':empty_regions,'command':command,'workingDirectory':str(host),'no_world_copy_or_qa_import':True,'native_cycles_passed':False}
    if authority:prepared.update(feature_scope='124',root_world_authority=authority,original_identity_count=len(original),full_delivered_dependency_sha256=server_release_sha,observer_receipt=OBSERVER_RECEIPT.as_posix())
    critical_before={}
    for name in ('level.dat','level.dat_old'):
        path=args.world/name
        if path.is_file():
            backup=args.out/'critical_before'/name;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,backup)
            critical_before[name]=sha(path);need(sha(backup)==critical_before[name],'Exact preboot level metadata backup differs')
    prepared['critical_preboot_metadata_sha256']=critical_before
    prepared['critical_preboot_entity_region_sha256']=entity_backups
    write(args.out/'INPUTS.json',prepared)
    if not args.run:print('Prepared Root-only real install/cold restart; no Java or World write:',args.out,flush=True);return
    result={'installation_accepted':False,'native_restart_passed':False,'native_cycles_passed':False,'gameplay_acceptance':'USER_TEST_PENDING','world':str(args.world),'pid':None}
    lease=(args.world.parent/('.root_world_install_'+hashlib.sha256(str(args.world).encode()).hexdigest()[:16]+'.lock')).open('a+b');lease.seek(0);lease.write(b'0');lease.flush();lease.seek(0);msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
    process=None
    fatal_entity_load=False
    def reject_failed_entity_decode(text):
        nonlocal fatal_entity_load
        failures=[line for line in text.splitlines() if 'Exception loading entity' in line or 'Duplicate id value for' in line]
        if failures:
            fatal_entity_load=True;result['first_fatal_entity_load']=failures[0]
            raise ValueError('Actual entity constructor/decode rejected; stop before accepting/saving incomplete originals: '+failures[0])
    def submit(text,phase):
        need(process is not None and process.poll() is None and '\n' not in text and '\r' not in text,'Live owned console required')
        with (args.out/'COMMANDS.jsonl').open('a',encoding='utf8') as log:log.write(json.dumps({'time':time.time(),'phase':phase,'command':text,'submitted_not_success':True},ensure_ascii=False)+'\n')
        process.stdin.write((text+'\n').encode('utf8'));process.stdin.flush()
    def boot(phase):
        nonlocal process
        locked_inputs();check_world_unlocked(args.world);need(sha(host/'mods/projectseele-0.1.0-all.jar')==args.jar_sha256,'Staged final JAR changed')
        snapshot=entity_index(args.world);need(all(snapshot.get(k)==v for k,v in original.items()),'A managed GeoFront original exact UUID/type/dimension disappeared')
        probe=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-CimInstance Win32_Process -Filter \"Name='java.exe'\").Count"],capture_output=True,text=True,check=True)
        need(probe.stdout.strip()=='0','Stop other Java/build/game processes before the sole heavy dedicated host')
        log_path=args.out/(phase+'.log')
        with log_path.open('xb') as log:process=subprocess.Popen([command[0],'@'+str(launch_args)],cwd=host,env=env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        result['pid']=process.pid;write(args.out/'RESULT.json',result);deadline=time.monotonic()+args.startup_timeout
        while time.monotonic()<deadline:
            text=log_path.read_text('utf8',errors='replace')
            reject_failed_entity_decode(text)
            if re.search(r'Done \(',text):
                if phase=='install' and args.first_boot_jfr:
                    profile=(args.out/'server-first30s.jfr').resolve()
                    recording=subprocess.run([str(Path(command[0]).with_name('jcmd.exe')),str(process.pid),
                        'JFR.start','name=R52FirstBoot','duration=30s','settings=profile','filename='+profile.as_posix()],
                        capture_output=True,text=True,timeout=30)
                    write(args.out/'FIRST_BOOT_JFR_COMMAND.json',{'pid':process.pid,'command':'JFR.start duration=30s settings=profile',
                        'filename':profile.as_posix(),'exit_code':recording.returncode,'stdout':recording.stdout,'stderr':recording.stderr,
                        'watchdog_changed':False,'heap_changed':False,'source_or_admission_changed':False})
                    need(recording.returncode==0,'Actual first-boot JFR could not start: '+recording.stderr)
                return log_path
            need(process.poll() is None,'Dedicated server exited before normal startup; preserve log')
            time.sleep(.5)
        raise TimeoutError('Normal server startup not ready; owned process remains available for Root inspection')
    def lifecycle(name):
        output=args.out/(name+'.json');need(not output.exists(),'Fresh actual observation required')
        checked=subprocess.run([command[0],'-Xmx256m','--add-modules','jdk.attach','-cp',str(ATTACH),'R52LifecycleReadOnlyAttach',str(process.pid),str(AGENT),str(candidate_bundle),str(output)],capture_output=True,text=True,timeout=30)
        need(checked.returncode==0,'Actual lifecycle attachment failed: '+checked.stderr[-1200:]);deadline=time.monotonic()+45
        while not output.exists() and time.monotonic()<deadline:need(process.poll() is None,'Owned server exited before actual snapshot');time.sleep(.5)
        need(output.is_file(),'Actual lifecycle server-thread snapshot absent');data=read(output)
        need('error' not in data and data.get('all_expected_original_uuid_and_source_observed') is True and data.get('persisted_same_bundle_authority') is True,'Actual declared UUID/source/persisted bundle authority failed: '+str(data.get('error',data.get('restore_hold'))))
        need(data['expected_original_controller_count']==controller_count and not data.get('restore_hold') and {r['uuid']:r['role'] for r in data['controllers']}==controllers,'Actual declared controller set differs or restoration held')
        data['selected_wet_floor_seal_specs_verified']=validate_sealed_native_specs(data['controllers'],selected_gates)
        return data
    def save_stop(phase):
        need(result['installation_accepted'],'No save/stop is issued as a substitute for an accepted installation')
        submit('save-all flush',phase);submit('stop',phase)
        try:process.wait(timeout=60)
        except subprocess.TimeoutExpired:raise TimeoutError('Normal stop incomplete; leave same process for Root, never kill/relaunch')
        need(process.returncode==0,'Normal owned dedicated server exited unsuccessfully');process.stdin.close()
        snapshot=entity_index(args.world);need(all(snapshot.get(k)==v for k,v in original.items()),'Managed GeoFront original exact persisted identity/type/dimension changed')
        need(all(k in snapshot and snapshot[k]['dimension']=='dimensions/projectseele/geofront' for k in controllers),'A declared actual GeoFront controller was not written by actual native entity storage')
        other_now={k:v for k,v in snapshot.items() if v['dimension']!='dimensions/projectseele/geofront'}
        write(args.out/(phase+'_OTHER_DIMENSIONS.json'),{'observed_before_count':len(other_before),'observed_after_count':len(other_now),
            'missing':{k:v for k,v in other_before.items() if k not in other_now},'added':{k:v for k,v in other_now.items() if k not in other_before},
            'changed':{k:{'before':v,'after':other_now[k]} for k,v in other_before.items() if k in other_now and other_now[k]!=v},
            'scope':'Other dimensions observed separately; no deletion, replacement, reset or total-count acceptance was applied.'})
        return snapshot
    try:
        log=boot('install');deadline=time.monotonic()+args.install_timeout
        success='Root physical owner and shared runtime installed; native cycles and visuals still require actual verification'
        while time.monotonic()<deadline:
            locked_inputs();before=log.stat().st_size;submitted_at=time.monotonic();submit('execute in projectseele:geofront run nerv r52 install '+bundle_relative,'install')
            # Keep exactly one command in flight. Repeating an unanswered
            # installation command makes DedicatedServer drain several heavy
            # attempts in a single tick, starving the entities being loaded.
            replied=False
            while time.monotonic()<deadline:
                need(process.poll() is None,'Actual server exited during installation')
                with log.open('rb') as stream:stream.seek(before);fresh=stream.read().decode('utf8',errors='replace')
                reject_failed_entity_decode(log.read_text('utf8',errors='replace'))
                if success in fresh and ('directory='+deployment['directory_fingerprint']) in fresh:
                    result['actual_console_commissioning_reply_accepted']=True;result['installation_accepted']=True;break
                if 'R52 Root installation held:' in fresh:
                    reason=next(line for line in reversed(fresh.splitlines()) if 'R52 Root installation held:' in line)
                    result['last_actual_install_reply']=reason
                    raise ValueError('Actual installation source/contract failure; preserve first reply: '+reason)
                if 'immutable source preparation failed:' in fresh:
                    reason=next(line for line in reversed(fresh.splitlines()) if 'immutable source preparation failed:' in line)
                    result['last_actual_install_reply']=reason
                    raise ValueError('Actual immutable source failure; retry cannot change this selected source: '+reason)
                replies=[line for line in fresh.splitlines() if '[epoch=' in line and ('directory='+deployment['directory_fingerprint']) in line]
                if replies:
                    result['last_actual_install_reply']=replies[-1];replied=True;break
                time.sleep(.5)
            if result['installation_accepted']:break
            need(replied,'The sole installation request received no actual reply before the bounded deadline; no extra commands were queued')
            pause=min(deadline-time.monotonic(),args.retry_seconds-(time.monotonic()-submitted_at))
            if pause>0:time.sleep(pause)
        need(result['installation_accepted'],'Actual installation never accepted; no save/stop/second boot or fake pass issued')
        before=lifecycle('BEFORE_SAVE');saved=save_stop('accepted_install');write(args.out/'PERSISTED_AFTER_INSTALL.json',saved)
        boot('cold_restart');deadline=time.monotonic()+args.install_timeout;after=None
        while time.monotonic()<deadline:
            try:after=lifecycle('AFTER_RESTART_'+str(int(time.monotonic())));break
            except (ValueError,TimeoutError):
                need(process.poll() is None,'Actual server exited while restoring original UUIDs');time.sleep(args.retry_seconds)
        need(after is not None,'Actual cold restoration never proved same declared controller authority')
        before_rows={r['uuid']:r for r in before['controllers']};after_rows={r['uuid']:r for r in after['controllers']}
        compared=[]
        for identity,role in controllers.items():
            if role in ['silo_gate','hangar_gate','fixed_cannon']:
                need(native_state(before_rows[identity])==native_state(after_rows[identity]),'Full persisted native controller state changed on cold restart: '+identity)
                need(before_rows[identity]['actual_position']==after_rows[identity]['actual_position'],'Actual declared controller frame changed on cold restart')
                compared.append({'uuid':identity,'role':role})
        save_stop('verified_cold_restart');locked_inputs()
        result.update({'native_restart_passed':True,'geofront_original_identities_retained':True,'other_dimension_identity_count_before':len(other_before),
            'actual_controller_uuid_and_sources_retained':True,'expected_controller_count':controller_count,'expected_controllers':controllers,'selected_wet_floor_seal_specs_retained':after['selected_wet_floor_seal_specs_verified'],'complete_door_and_cannon_state_matches':compared,'normal_stop_complete':True,'pid':None})
    except BaseException as failure:
        if result.get('installation_accepted'):
            result['console_commissioned_but_native_verification_failed']=True
            result['installation_accepted']=False
        if fatal_entity_load and process is not None and process.poll() is None:
            try:
                submit('stop','fatal_entity_decode_normal_stop');process.wait(timeout=60)
                result['fatal_entity_decode_normal_stop_complete']=process.returncode==0
            except (OSError,ValueError,subprocess.TimeoutExpired) as stop_error:
                result['fatal_entity_decode_stop_error']=repr(stop_error)
        result['failure']=repr(failure);result['live_pid_needs_root_attention']=process.pid if process is not None and process.poll() is None else None
        write(args.out/'RESULT.json',result)
        print('R52_MINIMAL_INSTALL_FAILED; preserve actual log/state; no automatic kill, reset or second launch. Live PID:',result['live_pid_needs_root_attention'],flush=True)
        raise
    finally:
        write(args.out/'RESULT.json',result);lease.seek(0);msvcrt.locking(lease.fileno(),msvcrt.LK_UNLCK,1);lease.close()
    print('R52 real accepted install + native save + cold declared UUID/state readback PASS; full play remains USER_TEST_PENDING:',args.out,flush=True)
if __name__=='__main__':main()
