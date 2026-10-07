"""Prepare R50 Server + direct PCL Client plans. Root alone may execute/resume.

No Java, Gradle, remote downloads, world reset, SHA suite, or installed PCL mutation.
"""
from pathlib import Path
import re
import argparse, io, json, os, shutil, struct, uuid, zipfile
from prepare_r47_two_pack import cold_world, clean_launch, need

ROOT=Path(__file__).resolve().parents[1]
R50=ROOT/'artifacts/rebuild_r50'
INPUT_ROOT=ROOT/'artifacts/rebuild_r49'
BASE=ROOT/'artifacts/server-ready-r48-two-pack/stage'
OUT=ROOT/'artifacts/server-ready-r50-two-pack'
STAGE=OUT/'stage'
TEMPLATES=ROOT/'tools/templates/r50'
BATCH='Project_SEELE_Encore_R50_20261006'
INSTANCE='Project_SEELE_Encore_R50_PCL_20261006'
WORLD='SEELE_R50_WORLD'
def current_protocol():
    wire=(ROOT/'src/main/java/com/projectseele/network/SeeleNetwork.java').read_text('utf8')
    match=re.search(r'PROTOCOL_VERSION\s*=\s*"([0-9]+)"',wire)
    if match is None:raise RuntimeError('Current wire protocol must be a literal numeric version')
    return match.group(1)
PROTOCOL=current_protocol()
DOCUMENTS=('README_R50.zh.md','MANUAL_R50.zh.md','NEXT_ROUND_R50.zh.md','FINAL_STATUS_R50.md',
           'YASHIMA_NEXT_ROUND_R50.zh.md')
EXCLUDED_DIRS={'logs','screenshots','crash-reports','debug','reports','native_qa'}
OWNED_RESOURCE_PATHS=[
    'assets/projectseele/sounds.json','data/projectseele/nerv_dialogue/profiles.json',
    'assets/projectseele/lang/zh_cn.json','assets/projectseele/lang/en_us.json',
    'META-INF/licenses/audio-recordings-r48.txt',
]+['assets/projectseele/sounds/'+name+'.ogg'for name in (
    'r48_hydraulic_charge_recorded','r48_catapult_release_recorded','r48_catapult_acceleration_recorded',
    'r48_surface_door_slide_recorded','r48_surface_door_slide_heavy_recorded','r48_surface_door_endstop_recorded')]
ROOT_RESOURCE_PATHS=[
    'assets/projectseele/mesh/seele_desk_r48.mesh.json',
    'assets/projectseele/mesh/tripo_gripper_r48.json','assets/projectseele/mesh/tripo_carrier_r48.json',
    'assets/projectseele/textures/entity/tripo_gripper_r48.png','assets/projectseele/textures/entity/tripo_carrier_r48.png',
    'assets/projectseele/textures/entity/tripo_charger_r48.png',
]+['assets/projectseele/mesh/eva_charger_unit'+unit+'_r48.mesh.json'for unit in ('00','01','02')]
ROOT_RESOURCE_PATHS += ['assets/projectseele/'+folder+'/'+name+'.json'for folder,names in (
    ('blockstates',('entry_plug_bridge_deck','entry_plug_bridge_guard')),
    ('models/block',('entry_plug_bridge_deck','entry_plug_bridge_fascia','entry_plug_bridge_rail_beam','entry_plug_bridge_rail_post')),
    ('models/item',('entry_plug_bridge_deck','entry_plug_bridge_guard')))for name in names]

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if path.is_file()and path.read_text('utf8')==text:return
    temporary=path.with_name(path.name+'.write-'+uuid.uuid4().hex)
    temporary.write_text(text,'utf8');os.replace(temporary,path)

def read(path):return json.loads(path.read_text('utf8'))
def safe_source(path):
    need(not path.is_symlink(),'Symlink source needs Root review: '+str(path))
    need(path.is_file(),'Missing selected source: '+str(path))
    return dict(path=str(path.resolve()),bytes=path.stat().st_size,mtime_ns=path.stat().st_mtime_ns)
def relative(name):
    need('\\'not in name and not name.startswith('/')and':'not in name and'..'not in Path(name).parts,'Unsafe member: '+name)
    return Path(name)
def files(folder):
    need(folder.is_dir(),'Selected folder absent: '+str(folder))
    for path in sorted(folder.rglob('*')):
        need(not path.is_symlink(),'Symlink folder/member needs review: '+str(path))
        if path.is_file():yield path

def manifest():
    return dict(minecraft=dict(version='1.20.1',modLoaders=[dict(id='forge-47.4.10',primary=True)]),
                manifestType='minecraftModpack',manifestVersion=1,name=INSTANCE,version='R50-20261006-PCL1',
                author='Boyang Li',files=[],overrides='overrides')

def airport_actor(region,identifier):
    from transplant_s22_authority import read_region,parse_chunk
    from prepare_yashima_supply_entities_r50 import canonical_uuid
    _,chunks=read_region(region)
    matches=[entity for chunk in chunks if chunk is not None
             for entity in parse_chunk(chunk).get('Entities',[]) if canonical_uuid(entity)==identifier]
    need(len(matches)==1,'Required original underground aircraft is missing or duplicated in its recorded region')
    actor=matches[0]
    need(str(actor.get('id',''))=='projectseele:un_transport' and bool(actor.get('NervAircraft',0)),
         'Required underground actor is not the commissioned NERV aircraft')
    return actor

def required_airport(args):
    audit=read(args.docs/'DELIVERY_CONTENT_AUDIT_R50.json')
    need(audit.get('source_world')==str(args.world.resolve()),'Airport member audit does not bind the selected construction world')
    receipt_name='r50_underground_aircraft_receipt.json'
    receipt=read(args.world/receipt_name)
    identifier=str(uuid.UUID(receipt['aircraft_uuid']))
    need(receipt.get('new_entities')==1 and receipt.get('original_full_entity_NBT_preserved') is True,
         'The unique underground aircraft lacks its real one-entity installation receipt')
    members={WORLD+'/'+receipt_name:args.world/receipt_name};metadata={}
    for name in ('r50_underground_airport.json','nerv_underground_transport_r50.json'):
        document=read(args.world/name)
        need(document.get('schema')==50 and document.get('installed') is True
             and document.get('dimension')=='projectseele:geofront' and document.get('aircraft_uuid')==identifier,
             'Actual installed underground airport/transport metadata missing or mismatched: '+name)
        member=WORLD+'/'+name;members[member]=args.world/name;metadata[member]=document
    rows=audit['source_files'];paths=[row['relative_world_member'] for row in rows]
    need(len(paths)==263 and len(set(paths))==263,'Airport audit must declare all263distinct complete generation sources')
    for row in rows:
        name=row['relative_world_member']
        rel=relative(name)
        need(rel.parts[:6]==('dimensions','projectseele','geofront','data','city_rigid_generation_r45','chunks')
             and rel.suffix=='.dat','Unexpected airport complete source member: '+name)
        need((args.world/rel).is_file(),'Required airport complete source omitted: '+name)
        need((args.world/rel).stat().st_size==row['receipt_after_bytes']>0,
             'Required airport complete source changed after its actual installation audit: '+name)
        members[WORLD+'/'+rel.as_posix()]=args.world/rel
    region=relative(audit['new_aircraft']['relative_world_member'])
    need(any(row.get('relative_target')==region.as_posix() for row in receipt['region_operations']),
         'Required actor region is not the actual installation-receipt member')
    need(region.parts[:4]==('dimensions','projectseele','geofront','entities') and region.suffix=='.mca',
         'Unexpected underground actor region member')
    members[WORLD+'/'+region.as_posix()]=args.world/region
    for member,source in members.items():
        rel=source.relative_to(args.world)
        need(source.is_file() and source.name!='session.lock' and not any(part in EXCLUDED_DIRS for part in rel.parts),
             'Required airport member absent or excluded: '+member)
    return dict(members=members,metadata=metadata,actor_member=WORLD+'/'+region.as_posix(),
                actor_uuid=identifier,actor=airport_actor(args.world/region,identifier),complete_sources=263)

def prepare(args):
    global PROTOCOL
    PROTOCOL=current_protocol()
    need(args.input_root.resolve() in {(ROOT/'artifacts/rebuild_r49').resolve(),R50.resolve()},'Untrusted input root')
    need(args.source_world_name in {'SEELE_R49_WORLD','SEELE_R50_WORLD'},'QA/session source names forbidden')
    need(args.world.resolve()==(args.input_root/'construction'/args.source_world_name).resolve(),'Only the single construction source is allowed')
    need(args.assets.resolve()==(args.input_root/'assets').resolve() and args.runtime.resolve()==(args.input_root/'runtime').resolve(),'QA/alternate assets and runtime are not the selected root')
    need((BASE/'server/libraries/net/minecraftforge/forge/1.20.1-47.4.10/win_args.txt').is_file(),'R48 Forge Windows runtime missing')
    need((BASE/'server/libraries/net/minecraftforge/forge/1.20.1-47.4.10/unix_args.txt').is_file(),'R48 Forge Linux runtime missing')
    recipe=read(args.shader_recipe or BASE/'client/private_shader_recipe_v12.json')
    need(recipe['scope']=='LOCAL_PERSONAL_ONLY_NOT_PREBUILT_SHADER_DISTRIBUTION','Original local shader recipe required')
    need(recipe['input_filename']=='ComplementaryUnbound_r5.3.zip','Pinned shader input differs')
    recipe['output_filename']='SEELE_Local_Cavern_R50_Private_v1.zip'
    write(OUT/'prepared/private_shader_recipe_v12.json',recipe)
    write(OUT/'prepared/manifest.json',manifest())
    inherited_properties=(BASE/'server/server.properties').read_text('ascii')
    properties=[]
    for line in inherited_properties.splitlines():
        if line.startswith('level-name='):line='level-name='+WORLD
        elif line.startswith('motd='):line=line.replace('EVANGELION:Encore R48','EVANGELION:Encore R50')
        properties.append(line)
    (OUT/'prepared/server.properties.candidate').write_text('\n'.join(properties)+'\n','ascii')
    options=(BASE/'client/options.txt').read_text('utf8').splitlines()
    keys={'version':'3465','key_iris.keybind.shaderPackSelection':'key.keyboard.f8',
          'key_key.projectseele.command_radio':'key.keyboard.o'}
    options=[line for line in options if line.partition(':')[0]not in keys]
    options += [key+':'+value for key,value in keys.items()]
    (OUT/'prepared/client_options.txt').write_text('\n'.join(options)+'\n','utf8')
    deps={side:[p.name for p in sorted((BASE/side/'mods').glob('*.jar'))if not p.name.lower().startswith('projectseele-')]for side in ('server','client')}
    need(set(deps['server']).issubset(set(deps['client'])),'A required server dependency is absent from the client payload')
    need(len(deps['client'])==20,'R48 client must provide twenty dependency mods plus the final R50 mod')
    plan=dict(schema='projectseele.r50.two-pack-plan.v1',batch=BATCH,protocol=PROTOCOL,prepared_only=not(args.execute or args.finish_staged),
              outputs=[str(args.delivery/(BATCH+'_Server.zip')),str(args.delivery/(BATCH+'_Client_PCL.zip'))],
              dependencies_base=str(BASE),dependencies=deps,bundled_client_mods=21,remote_mod_list=[],
              jar=str(args.jar.resolve()),selected_overlay=str(args.assets.resolve()),runtime=str(args.runtime.resolve()),world=str(args.world.resolve()),world_name=WORLD,
              icon=str(args.icon.resolve()),docs=str(args.docs.resolve()),pcl_instance=INSTANCE,
              client_format='CurseForge manifest v1: root manifest.json + overrides/',minecraft='1.20.1',forge='47.4.10',java='17',server_max_heap='20G',
              shader_output=recipe['output_filename'],shader_enabled_by_default=False,
              world_progress='Root selected the same single R49 construction source for final R50 distribution; no remote-progress merge claimed',
              world_copy='none: server archive reads the unique construction source directly',
              SHA_tests=False,Java_started=False,Gradle_started=False,world_copied=False,ZIP_created=False)
    from r50_selected_payload import inherited_texture_overrides
    plan['inherited_effective_project_textures']=inherited_texture_overrides(BASE/'client')
    plan.update(trusted_input_root=str(args.input_root.resolve()),source_world_name=args.source_world_name,world_authority_receipt=str(args.world_authority_receipt.resolve()),world_copy='none: stream the unique cold construction source directly into the server archive',world_copy_count=0)
    write(OUT/'PACK_PLAN_R50.json',plan)
    return plan

def validate_inputs(args):
    need(PROTOCOL==current_protocol(),'Source wire protocol changed during preparation')
    need(args.world_closed,'Root must explicitly attest --world-closed after ending the native session')
    trusted={ (ROOT/'artifacts/rebuild_r49').resolve(), (ROOT/'artifacts/rebuild_r50').resolve() }
    need(args.input_root.resolve() in trusted,'Input root is not a registered trusted construction root')
    for name,path in [('jar',args.jar),('assets',args.assets),('runtime',args.runtime),('world',args.world),('icon',args.icon)]:
        need(path.resolve().is_relative_to(args.input_root.resolve()),name+' must come from the explicitly selected trusted input root')
    need(args.source_world_name in {'SEELE_R49_WORLD','SEELE_R50_WORLD'},'QA/session/review source world names are forbidden')
    need(args.world.resolve()==(args.input_root/'construction'/args.source_world_name).resolve(),'Only the single trusted construction world is a delivery source')
    need((args.world/'level.dat').is_file(),'Selected complete cold construction world missing')
    authority=read(args.world_authority_receipt)
    need(authority.get('source_world')==str(args.world.resolve()) and authority.get('source_kind')=='single_construction_from_delivered_progress'
         and authority.get('protected_progress_preserved') is True and authority.get('qa_imported') is False
         and authority.get('no_player_or_entity_reset') is True,'Root actual progress/world authority receipt is missing or does not bind this source')
    cold_world(args.world)
    required_airport(args)
    for doc in DOCUMENTS:
        text=(args.docs/doc).read_text('utf8')
        need('ROOT_R50_FINAL_RESULTS_PENDING'not in text and'ROOT_R50_FINAL_PATHS_PENDING'not in text and 'ROOT_R50_TASK_40_PENDING'not in text,'Root final documentation still pending: '+doc)
    from release_r45_contract import class_protocol, runtime_owner_config
    from r50_selected_payload import validate_selected_payload,validate_identity_coverage
    validate_identity_coverage(args.assets,args.runtime)
    validate_selected_payload(args.jar,args.assets)
    with zipfile.ZipFile(args.jar)as jar:
        need(struct.unpack('>H',jar.read('com/projectseele/ProjectSeele.class')[6:8])[0]==61,'Final production classes must target Java17')
        need(class_protocol(jar.read('com/projectseele/network/SeeleNetwork.class'))==PROTOCOL,'Final R50 jar differs from the selected source wire protocol '+PROTOCOL)
        for name in ['META-INF/mods.toml','projectseele.mixins.json','com/projectseele/world/StaffOperationsR48.class',
                     'com/projectseele/world/ArmedSortieSavedDataR48.class','com/projectseele/world/UndergroundSortieR48.class']:
            need(name in jar.namelist(),'Final jar omits current entry: '+name)
        need('${'not in jar.read('META-INF/mods.toml').decode('utf-8-sig'),'Final registration template unresolved')
        # Byte equality is limited to the owned small sound/prose/license payload.
        # Root's model/texture contents and frozen contract are never modified here.
        for name in OWNED_RESOURCE_PATHS:
            need(name in jar.namelist()and(args.assets/name).is_file(),'Selected non-model resource missing: '+name)
            need(jar.read(name)==(args.assets/name).read_bytes(),'Final jar has an older sound/dialogue/lang/license overlay: '+name)
        for name in ROOT_RESOURCE_PATHS:
            need(name in jar.namelist()and(args.assets/name).is_file(),'Root selected model/bridge resource omitted: '+name)
            need(jar.getinfo(name).file_size==(args.assets/name).stat().st_size,'Root selected resource size differs: '+name)
    runtime_owner_config((args.runtime/'config/projectseele-runtime-r45.properties').read_bytes())
    data=args.icon.read_bytes()
    need(data[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',data[16:24])==(64,64),'Root NERV icon must be a64x64 PNG')

def selected(args,plan):
    sources={};generated={}
    def add(side,name,source):sources[side+'/'+name]=source
    def tree(side,prefix,source):
        for p in files(source):add(side,prefix+p.relative_to(source).as_posix(),p)
    for side in ('server','client'):
        for dep in plan['dependencies'][side]:add(side,'mods/'+dep,BASE/side/'mods'/dep)
        add(side,'mods/projectseele-0.1.0-all.jar',args.jar)
        tree(side,'config/',BASE/side/'config')
        if side=='client':tree(side,'config/',BASE/'server/config')
        for folder in ('config','projectseele-local-maps'):tree(side,folder+'/',args.runtime/folder)
        for doc in DOCUMENTS:add(side,doc,args.docs/doc)
        generated[side+'/R50_BATCH.json']=json.dumps(dict(batch=BATCH,protocol=PROTOCOL,minecraft='1.20.1',forge='47.4.10',java='17',
                                                          kind=side,pcl_instance=INSTANCE,source_world=str(args.world.resolve()),
                                                          remote_progress_merge_not_claimed=True),indent=2)+'\n'
    tree('server','libraries/',BASE/'server/libraries')
    for name in ('Start-Server.bat','start-server.sh','user_jvm_args.txt'):
        generated['server/'+name]=clean_launch((BASE/'server'/name).read_text('utf8'))
        for word in generated['server/'+name].split():
            if word.startswith('-Dprojectseele.combatBundleDirectory='):
                need(word=='-Dprojectseele.combatBundleDirectory=projectseele-local-maps','Production combat bundle override must use the selected relative local-maps root')
    need('-Xmx20G'in generated['server/user_jvm_args.txt'],'Server maximum heap must remain20G')
    generated['server/eula.txt']='eula=false\n'
    props=(args.server_properties or OUT/'prepared/server.properties.candidate').read_text('ascii').splitlines()
    props=[('level-name='+WORLD)if p.startswith('level-name=')else p for p in props]
    need(any(p.startswith('motd=')and'EVANGELION:Encore R50'in p for p in props),'R50 branded MOTD missing')
    generated['server/server.properties']='\n'.join(props)+'\n'
    add('server','server-icon.png',args.icon)
    for p in files(args.world):
        rel=p.relative_to(args.world)
        if p.name=='session.lock'or any(part in EXCLUDED_DIRS for part in rel.parts)or p.name.startswith('inbox')or p.name.endswith('.ack.jsonl'):continue
        add('server',WORLD+'/'+rel.as_posix(),p)
    tree('client','resourcepacks/',BASE/'client/resourcepacks')
    add('client','shaderpacks/ComplementaryUnbound_r5.3.zip',BASE/'client/shaderpacks/ComplementaryUnbound_r5.3.zip')
    add('client','options.txt',OUT/'prepared/client_options.txt')
    for name in ('COMPLEMENTARY_CREDITS.txt','Install-LocalPrivateVisuals.v12.ps1'):add('client',name,BASE/'client'/name)
    add('client','private_shader_recipe_v12.json',OUT/'prepared/private_shader_recipe_v12.json')
    add('client','Initialize-R50-Visuals.ps1',TEMPLATES/'Initialize-R50-Visuals.ps1')
    add('client','PCL/Setup.ini',TEMPLATES/'PCL/Setup.ini')
    generated['client/config/oculus.properties']='enableShaders=false\nshaderPack=SEELE_Local_Cavern_R50_Private_v1.zip\n'
    for key in generated:sources.pop(key,None)
    for key in sources|generated:
        relative(key);need(not any(part in EXCLUDED_DIRS for part in Path(key).parts),'Diagnostic path leaked: '+key)
    return sources,generated

def stage(args,sources,generated,state):
    changed=0;world_new=0
    for key,source in sources.items():
        spec=safe_source(source)
        if key.startswith('server/'+WORLD+'/'):
            state.setdefault('world_inputs',{})[key]=spec
            continue
        target=STAGE/relative(key);prior=state['files'].get(key)
        if target.is_file()and prior==spec and(target.stat().st_size,target.stat().st_mtime_ns)==(spec['bytes'],spec['mtime_ns']):continue
        if target.exists():
            need(args.refresh_payload and not key.startswith('server/'+WORLD+'/')and prior is not None,
                 'Existing staged member preserved; use --refresh-payload only for owned non-world updates: '+key)
        target.parent.mkdir(parents=True,exist_ok=True)
        with (OUT/'copy_journal.jsonl').open('a',encoding='utf8')as journal:
            journal.write(json.dumps(dict(key=key,source=spec),ensure_ascii=False)+'\n');journal.flush()
        state['files'][key]=spec
        work=OUT/'copy_work'/uuid.uuid4().hex;work.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,work)
        need(safe_source(source)==spec and(work.stat().st_size,work.stat().st_mtime_ns)==(spec['bytes'],spec['mtime_ns']),'Source changed during copy: '+key)
        os.replace(work,target);changed+=1
        if key.startswith('server/'+WORLD+'/'):world_new+=1
        if changed%128==0:write(OUT/'execution_state.json',state)
    for key,text in generated.items():
        target=STAGE/relative(key);data=text.encode('utf8')
        if target.is_file()and target.read_bytes()==data:
            state['generated'][key]=len(data);continue
        need(not target.exists()or key in state['generated'],'Unowned existing staged generated member: '+key)
        target.parent.mkdir(parents=True,exist_ok=True);work=OUT/'copy_work'/uuid.uuid4().hex;work.parent.mkdir(parents=True,exist_ok=True)
        work.write_bytes(data);os.replace(work,target);state['generated'][key]=len(data)
    state['world_newly_copied_this_run']=world_new
    write(OUT/'execution_state.json',state)

def archive_readback(path,side,entries,payload_sources=None,airport=None):
    with zipfile.ZipFile(path)as z:
        actual={row.filename:row.file_size for row in z.infolist()if not row.is_dir()}
        need(actual==entries,'Actual archive member names/sizes differ: '+str(path))
        if payload_sources:
            from r50_selected_payload import equal_streams
            for name,source in payload_sources.items():
                member='overrides/'+name if side=='client'else name
                with z.open(member)as stored,source.open('rb')as selected:
                    need(equal_streams(stored,selected),'Actual archive selected Jar/runtime bytes differ: '+member)
        if side=='client':
            need(json.loads(z.read('manifest.json'))==manifest(),'Actual PCL manifest differs')
            need(b'{version_indie}Initialize-R50-Visuals.ps1'in z.read('overrides/PCL/Setup.ini'),'PCL launch macro missing')
            need(len([name for name in actual if name.startswith('overrides/mods/')and name.endswith('.jar')])==21,'Actual PCL archive must contain21 mods')
        else:
            need(z.read('eula.txt').strip()==b'eula=false','Actual archive accepted EULA unexpectedly')
            need(b'-Xmx20G'in z.read('user_jvm_args.txt'),'Actual archive maximum heap differs')
            need(b'EVANGELION:Encore R50'in z.read('server.properties'),'Actual archive MOTD differs')
            need(airport is not None,'Required airport readback contract missing for Server')
            from r50_selected_payload import equal_streams
            for member,source in airport['members'].items():
                need(member in actual,'Final Server archive omits required airport member: '+member)
                with z.open(member)as stored,source.open('rb')as selected:
                    need(equal_streams(stored,selected),'Final Server airport member bytes differ: '+member)
            for member,expected in airport['metadata'].items():
                need(json.loads(z.read(member))==expected,'Final Server installed airport metadata differs: '+member)
            # Adapt a ZIP member to the existing region codec; no temporary
            # extraction, second MCA decoder or NBT parser is introduced.
            from types import SimpleNamespace
            member=airport['actor_member'];data=z.read(member)
            region=SimpleNamespace(name=member,read_bytes=lambda:data)
            need(airport_actor(region,airport['actor_uuid'])==airport['actor'],
                 'Final Server original underground aircraft full typed NBT differs')

def finish(args,plan,sources,generated,state):
    airport=required_airport(args)
    need(all('server/'+member in sources for member in airport['members']),
         'Server selection omitted a required installed airport/complete-source/actor member')
    keys=set(sources)|set(generated)
    for key,source in sources.items():
        if key.startswith('server/'+WORLD+'/'):
            need(state.get('world_inputs',{}).get(key)==safe_source(source),'Cold source world changed after inventory: '+key)
            continue
        need(state['files'].get(key)==safe_source(source),'Staged source differs; resume --execute or choose a new batch: '+key)
        target=STAGE/relative(key);need(target.is_file()and target.stat().st_size==source.stat().st_size,'Incomplete staged member: '+key)
    for key,text in generated.items():need((STAGE/relative(key)).read_bytes()==text.encode('utf8'),'Generated staged entry differs: '+key)
    from r50_selected_payload import equal_files
    need(PROTOCOL==current_protocol(),'Source protocol changed before finalization')
    payload={'mods/projectseele-0.1.0-all.jar':args.jar}
    progress={key[len('server/'):]:source for key,source in sources.items() if key.startswith('server/'+WORLD+'/') and source.suffix in ('.dat','.json') and source.stat().st_size<=8*1024*1024}
    for folder in('config','projectseele-local-maps'):
        for source in files(args.runtime/folder):payload[folder+'/'+source.relative_to(args.runtime/folder).as_posix()]=source
    for side in('server','client'):
        for name,source in payload.items():need(equal_files(STAGE/side/name,source),'Staged selected Jar/runtime bytes differ: '+side+'/'+name)
    args.delivery.mkdir(parents=True,exist_ok=True)
    for side,filename in zip(('server','client'),plan['outputs']):
        output=Path(filename)
        names={};entries={}
        for key in sorted(keys):
            if not key.startswith(side+'/'):continue
            name=key[len(side)+1:];member='overrides/'+name if side=='client'else name
            names[member]=sources[key] if key.startswith('server/'+WORLD+'/') else STAGE/relative(key);entries[member]=names[member].stat().st_size
        if side=='client':entries['manifest.json']=len((json.dumps(manifest(),ensure_ascii=False,indent=2)+'\n').encode('utf8'))
        if output.exists():
            need(state['archives'].get(side,{}).get('path')==str(output),'Existing final archive preserved: '+str(output))
            archive_readback(output,side,entries,payload|progress if side=='server'else payload,airport if side=='server'else None);continue
        part=output.with_name(output.name+'.part-'+uuid.uuid4().hex)
        with zipfile.ZipFile(part,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True)as z:
            if side=='client':z.writestr('manifest.json',json.dumps(manifest(),ensure_ascii=False,indent=2)+'\n')
            for name,path in names.items():z.write(path,name,compress_type=zipfile.ZIP_STORED if path.suffix.lower()in('.jar','.zip','.ogg','.png')else zipfile.ZIP_DEFLATED)
        for key,source in sources.items():
            if key.startswith('server/'+WORLD+'/'):need(state.get('world_inputs',{}).get(key)==safe_source(source),'Cold world changed while archiving: '+key)
        cold_world(args.world)
        archive_readback(part,side,entries,payload|progress if side=='server'else payload,airport if side=='server'else None)
        state['archives'][side]=dict(path=str(output),partial=str(part),entries=len(entries),actual_archive_readback=True)
        write(OUT/'execution_state.json',state)
        need(not output.exists(),'Final archive appeared during creation; preserved: '+str(output));os.replace(part,output)
    write(OUT/'EXECUTION_RECEIPT_R50.json',dict(batch=BATCH,protocol=PROTOCOL,archives=state['archives'],
          world_copied_files=0,world_streamed_files=len(state.get('world_inputs',{})),
          world_newly_copied_this_run=state.get('world_newly_copied_this_run',0),
          source_world=str(args.world.resolve()),current_remote_progress_merge_not_claimed=True,selected_small_progress_files_readback=len(progress),
          required_airport_members_readback=len(airport['members']),airport_complete_sources_readback=airport['complete_sources'],
          airport_actor_uuid=airport['actor_uuid'],airport_actor_full_typed_NBT_readback=True,
          actual_archive_readback=True,PCL_GUI_import_not_executed=True,SHA_tests=False,Java_started=False,Gradle_started=False))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    mode=ap.add_mutually_exclusive_group();mode.add_argument('--execute',action='store_true');mode.add_argument('--finish-staged',action='store_true')
    ap.add_argument('--world-closed',action='store_true');ap.add_argument('--refresh-payload',action='store_true')
    ap.add_argument('--input-root',type=Path,default=INPUT_ROOT);ap.add_argument('--source-world-name',default='SEELE_R49_WORLD')
    ap.add_argument('--world-authority-receipt',type=Path,default=R50/'final_docs/WORLD_AUTHORITY_R50.json')
    ap.add_argument('--jar',type=Path)
    ap.add_argument('--assets',type=Path)
    ap.add_argument('--runtime',type=Path);ap.add_argument('--world',type=Path)
    ap.add_argument('--icon',type=Path);ap.add_argument('--docs',type=Path,default=R50/'final_docs')
    ap.add_argument('--server-properties',type=Path);ap.add_argument('--shader-recipe',type=Path);ap.add_argument('--delivery',type=Path,default=ROOT/'delivery')
    args=ap.parse_args()
    for name,child in [('jar','release_inputs/projectseele-0.1.0-all.jar'),('assets','assets'),('runtime','runtime'),('world','construction/'+args.source_world_name),('icon','release_inputs/server-icon.png')]:
        if getattr(args,name) is None:setattr(args,name,args.input_root/child)
    plan=prepare(args)
    if not(args.execute or args.finish_staged):print('Prepared only: no stage/world copy, archive, SHA, Java, or installed PCL changes.');return
    validate_inputs(args)
    need(not any(p.is_symlink()for p in (OUT,STAGE,args.delivery)if p.exists()),'Output roots require explicit symlink review')
    state_file=OUT/'execution_state.json'
    if state_file.exists():state=read(state_file);need(state['batch']==BATCH and state['world']==str(args.world.resolve()),'Foreign stage/session preserved')
    else:
        need(not STAGE.exists()or not any(STAGE.iterdir()),'Existing unowned R50 stage preserved')
        state=dict(batch=BATCH,world=str(args.world.resolve()),files={},generated={},world_inputs={},archives={})
        write(state_file,state)
    journal=OUT/'copy_journal.jsonl'
    if journal.is_file():
        journal_lines=journal.read_text('utf8').splitlines(keepends=True)
        if journal_lines and not journal_lines[-1].endswith('\n'):
            tail=journal_lines.pop()
            preserved=OUT/('copy_journal.incomplete-'+uuid.uuid4().hex+'.txt')
            preserved.write_text(tail,'utf8')
            complete=journal.with_name('copy_journal.complete-'+uuid.uuid4().hex+'.jsonl')
            complete.write_text(''.join(journal_lines),'utf8');os.replace(complete,journal)
        for index,line in enumerate(journal_lines):
            entry=json.loads(line);relative(entry['key']);state['files'][entry['key']]=entry['source']
    sources,generated=selected(args,plan)
    if args.execute:
        need(not state['archives']or not args.refresh_payload,'Cannot refresh a finalized package; choose a new batch')
        stage(args,sources,generated,state)
    else:state['world_newly_copied_this_run']=0
    finish(args,plan,sources,generated,state)
    print('R50 Server + Client_PCL finalized; installed PCL, R49, R48 and earlier scripts/packages are preserved; no second full world stage was created.')

if __name__=='__main__':main()
