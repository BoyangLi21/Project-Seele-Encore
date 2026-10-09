"""R51 non-map delivery from the two immutable delivered R50 ZIPs.

Default prepares a plan only. Root selects the final non-map JAR/resources and
alone invokes --execute. No construction/QA world or installed PCL is read.
"""
from pathlib import Path, PurePosixPath
import argparse, copy, hashlib, io, json, os, re, shutil, struct, subprocess, uuid, zipfile
from release_r45_contract import class_protocol

ROOT=Path(__file__).resolve().parents[1]
BASE_COMMIT='de1dc4824c28de90f216205f5b596478839de7cf'
BASE_JAR_SHA='0e5d4f4afba826a06cbb142870391fa6e841b828693c1e20b2786841a94e711d'
WORLD='SEELE_R50_WORLD'; RELEASE='R51'; DATE='20261009'
BATCH=f'Project_SEELE_Encore_{RELEASE}_{DATE}'; INSTANCE=f'Project_SEELE_Encore_{RELEASE}_PCL_{DATE}'
BASELINES={
    'server':(Path('D:/eva/delivery/Project_SEELE_Encore_R50_20261006_Server.zip'),813287065,3240),
    'client':(Path('D:/eva/delivery/Project_SEELE_Encore_R50_20261006_Client_PCL.zip'),573651291,89)}
OUT=ROOT/'artifacts/r51-nonmap-two-pack'; TEMPLATES=ROOT/'tools/templates/r51-nonmap'
NONMAP_PAYLOAD_ROOT=Path('D:/eva/artifacts/r51_nonmap_release')
MOD='mods/projectseele-0.1.0-all.jar'
NONMAP_RUNTIME={
    'angel_grip_r31.json','articulated_bodies_r35.json','combat_bundle_r44.json','eva_body_r44.json',
    'eva_combat_capture_r31.json','eva_combat_capture_r31_un00.json','eva_combat_capture_r31_un01.json',
    'eva_dorsal_r30.json','eva_recovery_r31.json','first_battle_r44.json','sachiel_gameplay_r32.json','sachiel_wrap_r14.bin',
    *('eva_gameplay_r44_'+str(v)+'.json'for v in range(5)),
    *('handling_authoring_'+str(v)+'.json'for v in range(3))}
FIXED_MAP_ASSETS={
    'assets/projectseele/mesh/tv_facilities_r16.json','assets/projectseele/mesh/tv_shoulder_shells_r44.json',
    'assets/projectseele/mesh/tripo_carrier_r48.json','assets/projectseele/mesh/tripo_gripper_r48.json'}
FORBIDDEN_CLASSES=('NervFacilityLayoutR51','NervFacilityPresentationR51','ClientboundFacilityFrameR51',
                   'FacilityFrameCacheR51','SeatRetractionR52')

def need(ok,message):
    if not ok:raise ValueError(message)
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')
def sha(data):return hashlib.sha256(data).hexdigest()
def member(name):
    need(isinstance(name,str)and name and '\\'not in name and ':'not in name
         and not name.startswith('/')and all(p not in ('','..','.')for p in name.split('/')),'Unsafe exact ZIP member: '+str(name))
    return name
def prefix(side):return 'overrides/'if side=='client'else''
def local(path,allow_payload=False):
    value=Path(path);value=value if value.is_absolute()else ROOT/value;need(not value.is_symlink(),'Selected file may not be a symlink');value=value.resolve()
    allowed=value.is_relative_to(ROOT.resolve())or allow_payload and value.is_relative_to(NONMAP_PAYLOAD_ROOT.resolve())
    need(allowed and value.is_file(),'Selected file is outside the clean worktree/reviewed non-map payload root: '+str(value))
    return value
def protocol():
    text=(ROOT/'src/main/java/com/projectseele/network/SeeleNetwork.java').read_text('utf8')
    match=re.search(r'PROTOCOL_VERSION\s*=\s*"([0-9]+)"',text);need(match is not None,'Missing source protocol')
    need(match.group(1)!='63','Migrated-facility protocol63 is excluded from this R50 non-map backport')
    return match.group(1)
def open_baseline(side):
    path,size,count=BASELINES[side]
    need(path.is_file()and not path.is_symlink()and path.stat().st_size==size,'Delivered R50 ZIP identity differs: '+str(path))
    archive=zipfile.ZipFile(path);names=archive.namelist()
    need(len(names)==count and len(set(names))==len(names),'Delivered ZIP count/duplicate member mismatch')
    for name in names:member(name)
    need(all(not i.is_dir()for i in archive.infolist()),'Unexpected directory entries in delivered baseline')
    return archive
def baseline_jar():
    with open_baseline('server')as archive:raw=archive.read(MOD)
    need(sha(raw)==BASE_JAR_SHA,'Delivered R50 mod differs from its actual build23 identity')
    result=zipfile.ZipFile(io.BytesIO(raw))
    need(class_protocol(result.read('com/projectseele/network/SeeleNetwork.class'))=='60','Delivered R50 wire differs')
    return result
def resource_allowed(name):
    member(name)
    need(name.startswith(('assets/','data/','META-INF/licenses/')),'JAR whitelist may contain only exact non-code resources')
    need(name not in FIXED_MAP_ASSETS and not name.endswith(('.nbt','.mcstructure','.mca','.dat'))
         and '/worldgen/'not in name and '/structures/'not in name and 'facility_carrier_r51'not in name,
         'Map/structure/fixed-machinery resource cannot be a non-map override: '+name)
def stream_equal(a,b):
    while True:
        x=a.read(1024*1024);y=b.read(1024*1024)
        if x!=y:return False
        if not x:return True
def selection(path,execute=False):
    if path is None:
        need(not execute,'Root must select --selection before executing')
        return None,{},{}
    selected=json.loads(local(path).read_text('utf8'))
    need(selected.get('schema')=='projectseele.r51.nonmap-root-selection.v1'
         and selected.get('baseline_commit')==BASE_COMMIT,'Non-map selection provenance differs')
    need(selected.get('maps_and_new_battles_cancelled')is True,'New maps/battles must remain excluded')
    if not selected.get('root_selected_final_nonmap_jar'):
        need(not execute,'Final non-map JAR has not been selected by Root')
        return selected,{},{}
    external=False
    if selected.get('resource_selection_receipt'):
        receipt=local(selected['resource_selection_receipt'],True)
        need(receipt==NONMAP_PAYLOAD_ROOT.resolve()/'RESOURCE_SELECTION.json','Only the reviewed non-map selection receipt may authorize external payloads')
        proof=json.loads(receipt.read_text('utf8'))
        need(proof.get('world_source_unchanged')is True and proof.get('new_map_assets')==0 and proof.get('new_yashima_or_marine_assets')==0,
             'Non-map resource selection includes a cancelled map/battle extension')
        external=True
    jar=local(selected['jar']['path'],external);need(sha(jar.read_bytes())==selected['jar']['sha256'],'Selected JAR changed after Root selection')
    expected={}
    for row in selected.get('jar_resource_allowlist',[]):
        name=row['member'];resource_allowed(name);need(name not in expected,'Duplicate JAR whitelist member');expected[name]=row['sha256']
    with baseline_jar()as old,zipfile.ZipFile(jar)as new:
        names=set(new.namelist());need(len(names)==len(new.namelist()),'Duplicate JAR members')
        need(class_protocol(new.read('com/projectseele/network/SeeleNetwork.class'))==protocol(),'Final JAR/source protocol mismatch')
        need(struct.unpack('>H',new.read('com/projectseele/ProjectSeele.class')[6:8])[0]==61,'Final JAR is not Java17')
        for name in names:
            if name.endswith('.class'):
                need(not any(marker in name for marker in FORBIDDEN_CLASSES),'Migrated facility class in non-map JAR: '+name)
        old_resources={n for n in old.namelist()if n.startswith(('assets/','data/','META-INF/licenses/'))}
        new_resources={n for n in names if n.startswith(('assets/','data/','META-INF/licenses/'))}
        need(old_resources<=new_resources,'Original R50 resource removed')
        changed=set()
        for name in old_resources|new_resources:
            equal=name in old_resources and name in new_resources and old.getinfo(name).file_size==new.getinfo(name).file_size
            if equal:
                with old.open(name)as a,new.open(name)as b:equal=stream_equal(a,b)
            if not equal:changed.add(name)
        need(changed==set(expected),'JAR resource differences must exactly match Root non-map whitelist: '+str(sorted(changed^set(expected))))
        for name,digest in expected.items():need(sha(new.read(name))==digest,'Selected JAR resource digest differs: '+name)
    overrides={}
    for row in selected.get('archive_resource_overrides',[]):
        name=member(row['member']);relative=PurePosixPath(name)
        need(relative.parts[0]=='projectseele-local-maps'and len(relative.parts)==2 and relative.name in NONMAP_RUNTIME,
             'World/nav/config/map runtime overrides are forbidden: '+name)
        source=local(row['source'],external);need(sha(source.read_bytes())==row['sha256'],'Selected non-map runtime resource changed')
        for side in ['server','client']:
            need(side+'/'+name not in overrides,'Duplicate archive override')
            with open_baseline(side)as old:need(prefix(side)+name in old.namelist(),'Override cannot introduce a new map/runtime path')
            overrides[side+'/'+name]=source
    if overrides:
        with open_baseline('server')as old:
            name='projectseele-local-maps/combat_bundle_r44.json';previous=json.loads(old.read(name))
            value=overrides.get('server/'+name);bundle=json.loads(value.read_text('utf-8-sig')if value else old.read(name))
            need(bundle.get('revision')==44 and set(bundle.get('files',{}))==set(previous['files']),
                 'Non-map runtime must preserve the original complete binding member set')
            for item,digest in bundle['files'].items():
                runtime_name='projectseele-local-maps/'+member(item);source=overrides.get('server/'+runtime_name)
                payload=source.read_bytes()if source else old.read(runtime_name)
                need(sha(payload)==digest,'Combat bundle does not bind actual selected resource: '+item)
    return selected,overrides,{'server/'+MOD:jar,'client/'+MOD:jar}
def motd(raw):
    rows=raw.splitlines(keepends=True);count=0
    for i,row in enumerate(rows):
        if row.startswith(b'motd='):
            need(b'EVANGELION:Encore R50'in row,'Original R50 MOTD is missing');rows[i]=row.replace(b'EVANGELION:Encore R50',b'EVANGELION:Encore R51');count+=1
    need(count==1,'Exactly one original MOTD line required');return b''.join(rows)
def pcl_title(raw):
    need(b'VersionArgumentTitle:'not in raw,'Unexpected baseline title setting')
    return raw+b'VersionArgumentTitle:EVANGELION:Encore R51\r\n'
def generated(side,old,selected):
    base=prefix(side);result={}
    if side=='client':
        original=json.loads(old.read('manifest.json'));manifest=dict(original);manifest['name']=INSTANCE;manifest['version']='R51-20261009-PCL1'
        result['manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        result[base+'PCL/Setup.ini']=pcl_title(old.read(base+'PCL/Setup.ini'))
    else:result['server.properties']=motd(old.read('server.properties'))
    for name in ['README_R51.zh.md','NONMAP_STATUS_R51.md']:result[base+name]=(TEMPLATES/name).read_bytes()
    result[base+'R51_BATCH.json']=(json.dumps(dict(batch=BATCH,release=RELEASE,protocol=protocol(),kind=side,
        baseline_commit=BASE_COMMIT,baseline_zip=str(BASELINES[side][0]),world_prefix_unchanged=WORLD,
        all_original_world_map_config_nav_and_traffic_bytes_preserved=True,selected_nonmap_jar=selected.get('jar')if selected else None,
        nonmap_changes=selected.get('nonmap_changes',[])if selected else [],native_results=selected.get('native_results',[])if selected else [],
        new_map_and_new_battle_extensions_included=False),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    return result
def plan(args):
    selected,overrides,jars=selection(args.selection,args.execute)
    stats={}
    for side in ['server','client']:
        with open_baseline(side)as old:
            base=prefix(side);names=old.namelist();stats[side]=dict(path=str(BASELINES[side][0]),members=len(names),
                world_members=sum(n.startswith(WORLD+'/')for n in names),mods=sum(n.startswith(base+'mods/')for n in names),
                runtime_members=sum(n.startswith(base+'projectseele-local-maps/')for n in names),config_members=sum(n.startswith(base+'config/')for n in names))
            need(sha(old.read(base+MOD))==BASE_JAR_SHA,'Delivered original JAR differs on '+side)
            need(stats[side]['world_members']==(3066 if side=='server'else 0),'Original world inventory differs')
            if side=='client':need(not any(n.startswith('overrides/saves/')for n in names),'Delivered Client may not contain a QA/world')
    value=dict(schema='projectseele.r51.nonmap-two-pack-plan.v1',release=RELEASE,date=DATE,baseline_commit=BASE_COMMIT,
        baselines=stats,baseline_mod_sha256=BASE_JAR_SHA,baseline_protocol=60,selected_source_protocol=protocol(),
        final_nonmap_jar_selected=bool(jars),explicit_nonmap_archive_overrides=sorted(overrides),
        world_source='Original delivered Server ZIP only, no filesystem world source',world_prefix_unchanged=WORLD,
        client_format='Original CurseForge manifestVersion1 + overrides; only name/version change',
        outputs=[str(args.delivery/(BATCH+'_Server.zip')),str(args.delivery/(BATCH+'_Client_PCL.zip'))],
        prepared_only=not args.execute,ZIP_created=False,world_extracted=False,QA_read=False,world_written=False)
    write(args.out/'PACK_PLAN_R51.json',value);return selected,overrides,jars,value
def verify_archive(side,path,old,changes):
    with zipfile.ZipFile(path)as actual:
        need(set(actual.namelist())==set(old.namelist())|set(changes),'Final ZIP member inventory differs')
        need(len(actual.namelist())==len(set(actual.namelist())),'Final ZIP has duplicate entries')
        kept=world=0
        for name in actual.namelist():
            if name in changes:
                value=changes[name]
                if isinstance(value,Path):
                    with value.open('rb')as a,actual.open(name)as b:need(stream_equal(a,b),'Changed payload differs: '+name)
                else:need(actual.read(name)==value,'Generated payload differs: '+name)
            else:
                with old.open(name)as a,actual.open(name)as b:need(stream_equal(a,b),'Original R50 bytes changed: '+name)
                kept+=1;world+=name.startswith(WORLD+'/')
        return dict(side=side,path=str(path),original_members_byte_readback=kept,original_world_members_byte_readback=world,
                    actual_archive_readback=True,world_extracted=False)
def execute(args,selected,overrides,jars):
    need(selected and jars,'Root final selection is required')
    need(selected.get('nonmap_changes')and selected.get('native_results')is not None,'Root must describe actual non-map changes and native evidence limits')
    results=[];args.delivery.mkdir(parents=True,exist_ok=True)
    for side,suffix in [('server','Server'),('client','Client_PCL')]:
        target=args.delivery/(BATCH+'_'+suffix+'.zip');need(not target.exists(),'Preserve existing delivery: '+str(target))
        temporary=target.with_suffix('.zip.part-'+uuid.uuid4().hex)
        with open_baseline(side)as old:
            changes=generated(side,old,selected)
            changes.update({prefix(side)+key.split('/',1)[1]:p for key,p in (overrides|jars).items()if key.startswith(side+'/')})
            with zipfile.ZipFile(temporary,'x',allowZip64=True)as new:
                for info in old.infolist():
                    if info.filename in changes:continue
                    with old.open(info)as source,new.open(copy.copy(info),'w',force_zip64=True)as dest:shutil.copyfileobj(source,dest,1024*1024)
                for name,value in changes.items():
                    if isinstance(value,Path):new.write(value,name,compress_type=zipfile.ZIP_STORED)
                    else:new.writestr(name,value,compress_type=zipfile.ZIP_DEFLATED)
            results.append(verify_archive(side,temporary,old,changes))
            need(sha(local(selected['jar']['path'],True).read_bytes())==selected['jar']['sha256'],'Root JAR changed during packaging')
            for row in selected.get('archive_resource_overrides',[]):need(sha(local(row['source'],True).read_bytes())==row['sha256'],'Root runtime changed during packaging')
            os.replace(temporary,target);results[-1]['path']=str(target)
    write(args.out/'EXECUTION_RECEIPT_R51.json',dict(batch=BATCH,archives=results,all_original_world_bytes_preserved=True,
        native_verified=bool(selected.get('native_test_completed',False)),native_evidence=selected.get('native_results',[]),
        PCL_import_or_server_launch_executed=False,world_extracted=False,QA_read=False,world_written=False))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--selection',type=Path);ap.add_argument('--out',type=Path,default=OUT)
    ap.add_argument('--delivery',type=Path,default=ROOT/'delivery');ap.add_argument('--execute',action='store_true');args=ap.parse_args()
    need(args.out.resolve().is_relative_to(ROOT.resolve()),'Preparation output must stay in the clean non-map worktree')
    need(args.delivery.resolve()in{(ROOT/'delivery').resolve(),Path('D:/eva/delivery').resolve()},'Use the explicit delivery directory, never a world/QA directory')
    need(subprocess.run(['git','merge-base','--is-ancestor',BASE_COMMIT,'HEAD'],cwd=ROOT).returncode==0,'Clean R50 provenance missing')
    selected,overrides,jars,value=plan(args)
    if args.execute:execute(args,selected,overrides,jars)
    print(json.dumps(dict(plan=str(args.out/'PACK_PLAN_R51.json'),final_jar_selected=bool(jars),executed=args.execute,world_written=False)))
if __name__=='__main__':main()
