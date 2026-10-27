"""R54 current-source server and lean PCL packaging; default is inventory only.

Never reads an old archive world or promotes a ready tree. --pack holds the
actual save lock and requires its completed ordinary Save and Quit. No SHA.
"""
from pathlib import Path
from collections import defaultdict
from contextlib import nullcontext
import argparse,gzip,io,json,os,re,sys,zipfile
sys.path.append(str(Path(__file__).resolve().parents[1]/'.Codex/map-deps'))
import nbtlib
from prepare_r53_ready_sync import CLIENT_TREES,dimensions
from install_r53_carrier_trays import stopped_world
from repair_r53_geofront_dry_weather import patch as repair_dry_weather

ROOT=Path(__file__).resolve().parents[1]
ACTUAL_WORLD=Path('F:/eva/artifacts/r53_repair_20261015/client/saves/HOTFIX_20261025')
SHADER='SEELE_Local_Cavern_R53_Review_20261026.zip'
DH_SERVER_MOD='mods/DistantHorizons-2.3.4-b-1.20.1-fabric-forge.jar'
PACK_NAME='EVANGELION_Encore_R54'
SERVER_WORLD='SEELE_R53_WORLD'
MOTD='§b§lEVANGELION:Encore R54 近三测 §r\n§6NERV！ §8| §aEVA！§8| §fSEELE!'
PCL_SOURCE='https://github.com/Meloong-Git/PCL/blob/main/Plain%20Craft%20Launcher%202/Modules/Minecraft/ModModpack.vb'
PRUNE={'.codex','logs','crash-reports','debug','screenshots','pose-captures','backups','backup','tests','test','__pycache__','.git','distanthorizons','distant_horizons_server_data'}
SUFFIXES=('.bak','.old','.backup','.log','.tmp','.pyc')

def validate_normal_save_log(text):
    started=max(text.rfind('Starting integrated minecraft server'),
                text.rfind('Starting minecraft server version'))
    recent=text[max(0,started):]
    # A crashed integrated server also saves its dimensions during teardown.
    # Only the latest session matters; a later clean restart can recover normally.
    fatal=('Encountered an unexpected exception','Exception in server tick loop',
           'This crash report has been saved to:','Preparing crash report with UUID',
           'A single server tick took')
    if any(marker in recent for marker in fatal):
        raise RuntimeError('Latest server session explicitly crashed; restart normally and Save and Quit before packaging')
    if text.rfind('All dimensions are saved') < max(0,started):
        raise RuntimeError('Latest session has no completed normal Save and Quit')

def require_normal_save(client, save_log=None):
    validate_normal_save_log((save_log or client/'logs/latest.log').read_text('utf8',errors='replace'))

def excluded(parts):
    return any(p.lower() in PRUNE or p.lower().startswith(('hs_err_pid','replay_pid')) or p.lower().endswith(SUFFIXES) for p in parts)

def files(root,world=False):
    if not root.exists():return
    for parent,dirs,names in os.walk(root,followlinks=False):
        parent=Path(parent)
        for name in dirs:
            if (parent/name).is_symlink():raise ValueError('Unexpected linked input: '+str(parent/name))
        dirs[:]=sorted(n for n in dirs if not excluded((n,)))
        for n in sorted(names):
            p=parent/n
            if p.is_symlink():raise ValueError('Unexpected linked input: '+str(p))
            if n=='session.lock' or excluded((n,)) or n.startswith(('DistantHorizons.sqlite','Distant_Horizons.sqlite')):continue
            yield p

def jsonbytes(v):return (json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8')

def shader_payload(path):
    # Older local recipes omitted this dimension-specific weather adapter.
    # Already reviewed current packs remain the original file input.
    member='shaders/lib/uniforms.glsl'
    with zipfile.ZipFile(path) as source:
        original=source.read(member)
        repaired=repair_dry_weather(original.decode('utf8')).encode('utf8')
        if repaired==original:return path
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as target:
            for entry in source.infolist():
                target.writestr(entry,repaired if entry.filename==member else source.read(entry))
            target.comment=source.comment
    return output.getvalue()

def server_dh_config(text):
    # Remote city motion must update LODs outside vanilla chunk tracking.
    # Keep this service bounded and do not generate distant world terrain.
    settings={'numberOfThreads':'2','threadRunTimeRatio':'"0.5"',
              'enableDistantGeneration':'false','distantGeneratorMode':'"PRE_EXISTING_ONLY"',
              'enableRealTimeUpdates':'true','realTimeUpdateDistanceRadiusInChunks':'256',
              'synchronizeOnLoad':'true','sendLevelKeys':'true','levelKeyPrefix':'""'}
    for key,value in settings.items():
        text=re.sub(r'(?m)^(\s*'+re.escape(key)+r'\s*=\s*)[^\r\n]*',lambda m:m[1]+value,text)
    return text.encode('utf8')

def property_value(value):
    return ''.join(r'\n' if c=='\n' else r'\\' if c=='\\' else r'\:' if c==':' else '\\u%04X'%ord(c) if ord(c)>126 or ord(c)<32 else c for c in value)

def dh_identifier(client,world):
    display=str(nbtlib.load(world/'level.dat')['Data']['LevelName'])
    aliases={world.name,display};patterns=[re.compile(r'DhClientServerLevel\{'+re.escape(name)+r'_([0-9a-v]{13})@') for name in aliases]
    logs=[client/'logs/latest.log']+sorted((client/'logs').glob('*.log.gz'),key=lambda p:p.stat().st_mtime,reverse=True)
    for p in logs:
        if not p.exists():continue
        body=gzip.open(p,'rt',encoding='utf8',errors='replace').read() if p.suffix=='.gz' else p.read_text('utf8',errors='replace')
        found={m for pat in patterns for m in pat.findall(body)}
        if len(found)>1:raise ValueError('Ambiguous DH key for this actual save in '+str(p))
        if found:return found.pop(),dict(log=str(p),world_folder=world.name,level_display_name=display)
    raise ValueError('No logged DH identifier for actual folder/display name; do not substitute an old archive key')

def offline_caches(world,seed,pack):
    result={};source={};details=[]
    for dim in dimensions(world):
        db=dim/'data/DistantHorizons.sqlite'
        if not db.exists():continue
        rel=dim.relative_to(world).as_posix()
        name='minecraft:overworld' if rel=='.' else 'minecraft:the_nether' if rel=='DIM-1' else 'minecraft:the_end' if rel=='DIM1' else ':'.join(Path(rel).parts[1:])
        wal=Path(str(db)+'-wal');live=wal.exists() and wal.stat().st_size>0
        if pack and live:raise RuntimeError('DH database has uncheckpointed WAL after shutdown: '+str(db))
        folder=(seed+'@'+name).replace(':','@@')
        result['Distant_Horizons_server_data/SEELE/'+folder+'/DistantHorizons.sqlite']=db
        source[db.relative_to(world).as_posix()]=db
        details.append(dict(dimension=name,source=str(db),bytes=db.stat().st_size,live_wal=live,scope='Entire current DB, no geographic filtering; includes current cached UN region in GeoFront'))
    assert {'data/DistantHorizons.sqlite','dimensions/projectseele/geofront/data/DistantHorizons.sqlite'}<=set(source),'Current overworld and GeoFront caches required'
    return result,source,details

def build_inputs(a):
    client=a.base.resolve()/'client';world=a.world.resolve();assert world==ACTUAL_WORLD.resolve(),'Explicit actual HOTFIX save required'
    assert (world/'level.dat').is_file() and (client/'mods/projectseele-0.1.0-all.jar').is_file()
    seed,provenance=dh_identifier(client,world);lod,world_lod,lod_details=offline_caches(world,seed,a.pack)
    current={p.relative_to(client).as_posix():p for tree in CLIENT_TREES for p in files(client/tree)}
    excluded_inputs=[]
    for name,path in list(current.items()):
        reason=('inactive_shader_or_photography_variant' if name.startswith('shaderpacks/') and Path(name).name not in {SHADER,SHADER+'.txt'}
                else 'obsolete_private_shader_install_receipt' if name=='config/projectseele-private-visuals-r46.json'
                else None)
        if reason:
            excluded_inputs.append(dict(path=name,bytes=path.stat().st_size,category=reason));del current[name]
    manifest_name='projectseele-local-maps/combat_bundle_r44.json'
    runtime_manifest=json.loads(current[manifest_name].read_text('utf8'))
    # Keep the actual bundle and its declared files together. The small legacy
    # authoring reports and SVG are still indexed, so do not rewrite the index
    # merely to save 288 KB. No runtime identity or asset bytes are changed.
    missing_runtime=[n for n in runtime_manifest['files'] if 'projectseele-local-maps/'+n not in current]
    assert not missing_runtime,('A declared runtime resource is absent from the package',missing_runtime)
    assert 'shaderpacks/'+SHADER in current
    current['shaderpacks/'+SHADER]=shader_payload(current['shaderpacks/'+SHADER])
    shader_config=(client/'config/oculus.properties').read_text('utf8');assert 'shaderPack='+SHADER in shader_config,'Actual client must select the delivered current shader'
    if (client/'options.txt').is_file():current['options.txt']=client/'options.txt'
    options=(client/'options.txt').read_text('utf8')
    selected_packs=json.loads(next(line.split(':',1)[1] for line in options.splitlines() if line.startswith('resourcePacks:')))
    required_packs=['resourcepacks/'+n.removeprefix('file/') for n in selected_packs if n.startswith('file/')]
    assert all(n in current for n in required_packs),('Enabled resource pack missing',required_packs)
    for n in ('COMPLEMENTARY_CREDITS.txt',):
        if (client/n).is_file():current[n]=client/n
    world_files={p.relative_to(world).as_posix():p for p in files(world,True)};world_files.update(world_lod)
    assert any(n.startswith('dimensions/projectseele/geofront/data/city_rigid_generation_r45/') for n in world_files)
    template=a.delivery/'Project_SEELE_Encore_R53_20261025_Server.zip'
    client_template=a.delivery/'Project_SEELE_Encore_R53_20261025_Client_PCL.zip'
    with zipfile.ZipFile(template) as z:
        server_mods={n for n in z.namelist() if n.startswith('mods/') and n.endswith('.jar')}
        server_mods.add(DH_SERVER_MOD)
        bootstrap={n for n in z.namelist() if not n.endswith('/') and (n.startswith('libraries/') or n in {'Start-Server.bat','start-server.sh','user_jvm_args.txt','eula.txt'})}
        missing=server_mods-set(current);assert not missing,('Established server mod missing from current actual client',missing)
        props=z.read('server.properties').decode('utf8')
        props='\n'.join('level-name='+SERVER_WORLD if l.startswith('level-name=') else 'motd='+property_value(MOTD) if l.startswith('motd=') else l for l in props.splitlines())+'\n'
        server={n:p for n,p in current.items() if n.startswith(('projectseele-local-maps/','config/','defaultconfigs/','licenses/')) or n in server_mods}
        server['config/DistantHorizons.toml']=server_dh_config(current['config/DistantHorizons.toml'].read_text('utf8'))
        server.update({SERVER_WORLD+'/'+n:p for n,p in world_files.items()})
        server.update({'server.properties':props.encode('ascii'),'server-icon.png':a.icon})
        old_server={i.filename:(i.file_size,i.compress_size) for i in z.infolist()}
    with zipfile.ZipFile(client_template) as z:
        manifest=json.loads(z.read('manifest.json'));assert not manifest.get('files')
        old_client={i.filename:(i.file_size,i.compress_size) for i in z.infolist()}
    manifest.update(name=PACK_NAME,version='R54-'+a.date+('-'+a.revision if a.revision else ''))
    pcl={'overrides/'+n:p for n,p in (current|lod).items()};pcl['manifest.json']=jsonbytes(manifest)
    batch=dict(version='R54',date=a.date,revision=a.revision,build=a.build,actual_save=str(world),client_contains_save=False,installed_scope='Current actual installed R54 work; new Hakone lake/roads deferred to next round',acceptance='Packaging does not certify gameplay/art; see R54 requirements log and final root verification')
    for payload,prefix in ((server,''),(pcl,'overrides/')):
        payload[prefix+'R54_BATCH.json']=jsonbytes(batch)
        payload[prefix+'R54_QUICKSTART.zh.md']=ROOT/'docs/R54_FRIENDS_QUICKSTART.zh.md'
        payload[prefix+'R54_REQUIREMENTS_LOG.zh.md']=ROOT/'docs/R54_REQUIREMENTS_LOG.zh.md'
    for payload in (server,pcl):
        for n,p in payload.items():
            if isinstance(p,Path):assert p.is_file(),p
    return dict(client=client,world=world,template=template,bootstrap=bootstrap,server=server,pcl=pcl,server_mods=server_mods,world_files=world_files,lod=lod_details,dh_provenance=provenance,old_server=old_server,old_client=old_client,
                excluded_inputs=excluded_inputs,selected_resourcepacks=required_packs,
                runtime_index_scope='Actual bundle index and every indexed file retained byte-for-byte, including 288102 bytes of indexed authoring samples/SVG; no index rewrite or asset hashing')

def sizes(payload,old):
    totals=defaultdict(lambda:dict(files=0,raw_bytes=0,estimated_zip_bytes=0))
    for n,p in payload.items():
        count=p.stat().st_size if isinstance(p,Path) else len(p);parts=n.removeprefix('overrides/').split('/');group=parts[0]
        if group==SERVER_WORLD:group='world/DH' if n.endswith('DistantHorizons.sqlite') else 'world/terrain_and_progress'
        row=totals[group];row['files']+=1;row['raw_bytes']+=count
        previous=old.get(n);ratio=(previous[1]/max(1,previous[0])) if previous else (.96 if n.endswith(('.jar','.zip','.png','.ogg','.bin','.gz','.mca')) else .35)
        row['estimated_zip_bytes']+=round(count*ratio)
    return dict(totals)

def package(target,payload,template=None,bootstrap=()):
    assert not target.exists(),'R54 output already exists; retain it and choose an explicit different delivery date/path'
    temp=target.with_suffix('.zip.partial');assert not temp.exists()
    before={n:(p.stat().st_size,p.stat().st_mtime_ns) for n,p in payload.items() if isinstance(p,Path)}
    with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as out:
        if template:
            with zipfile.ZipFile(template) as old:
                for n in sorted(bootstrap):out.writestr(n,old.read(n),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        for n,p in sorted(payload.items()):
            if isinstance(p,Path):out.write(p,n,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
            else:out.writestr(n,p)
    assert all((p.stat().st_size,p.stat().st_mtime_ns)==before[n] for n,p in payload.items() if isinstance(p,Path)),'Input changed during packaging'
    with zipfile.ZipFile(temp) as z:
        names=z.namelist();assert len(names)==len(set(names)) and set(names)==set(payload)|set(bootstrap)
        assert z.testzip() is None,'Archive CRC readback failed'
        critical={'manifest.json','server.properties','server-icon.png','R54_BATCH.json','overrides/R54_BATCH.json',SERVER_WORLD+'/level.dat','mods/projectseele-0.1.0-all.jar','overrides/mods/projectseele-0.1.0-all.jar'}
        for n in critical&set(payload):
            p=payload[n];assert z.read(n)==(p.read_bytes() if isinstance(p,Path) else p),('Critical archive content mismatch',n)
        if 'manifest.json' in names:
            m=json.loads(z.read('manifest.json'));assert m['name']==PACK_NAME and not re.search(r'[<>:"/\\|?*]',m['name'])
            assert not any(n.startswith(('overrides/saves/','overrides/libraries/','overrides/assets/','overrides/PCL/')) for n in names)
    temp.replace(target)
    return dict(file=str(target),bytes=target.stat().st_size,entries=len(names),actual_zip_inventory_and_crc_readback=True,critical_content_readback=True)

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--world',type=Path,required=True);p.add_argument('--delivery',type=Path,required=True);p.add_argument('--date',required=True);p.add_argument('--build',type=int,required=True);p.add_argument('--icon',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--pack',action='store_true');p.add_argument('--save-log',type=Path,help='Actual dedicated-server shutdown log when this save ran outside the client');p.add_argument('--revision',default='',help='Optional same-day revision; preserves earlier delivery ZIPs');a=p.parse_args()
    assert re.fullmatch(r'\d{8}',a.date) and a.build>0
    assert not a.revision or re.fullmatch(r'[A-Za-z0-9_-]+',a.revision)
    label=a.date+('_'+a.revision if a.revision else '')
    with stopped_world(a.world) if a.pack else nullcontext():
        if a.pack:require_normal_save(a.base/'client',a.save_log)
        d=build_inputs(a);groups={side:sizes(d[key],d[old]) for side,key,old in [('Server','server','old_server'),('Client_PCL','pcl','old_client')]}
        bootstrap_raw=sum(d['old_server'][n][0] for n in d['bootstrap']);bootstrap_zip=sum(d['old_server'][n][1] for n in d['bootstrap'])
        groups['Server']['server_bootstrap_libraries']=dict(files=len(d['bootstrap']),raw_bytes=bootstrap_raw,estimated_zip_bytes=bootstrap_zip)
        report=dict(version='R54',pack_written=False,actual_world=str(d['world']),manifest_name=PACK_NAME,manifest_version='R54-'+a.date+('-'+a.revision if a.revision else ''),pcl_naming_source=PCL_SOURCE,pcl_naming_rule='InstallPackCurseForge uses manifest name, validates folder name, prompts only when invalid or conflicting',world_source='Only current explicit actual save; old templates contribute bootstrap libraries/launchers and manifest format, never world data',server_world_directory=SERVER_WORLD,server_mods=sorted(d['server_mods']),motd=MOTD,shader=SHADER,dh=d['lod'],dh_identifier_source=d['dh_provenance'],size_estimate=groups,estimate_note='Raw sizes are actual current files; ZIP estimate uses prior same-entry compression ratios and fallback assumptions, not a size guarantee',new_hakone_lake_and_roads='Deferred to next round; no candidate is installed by packaging',acceptance='Final native gameplay/art status is recorded separately by root; no pass inferred from package preparation')
        report.update(excluded_client_inputs=d['excluded_inputs'],excluded_client_input_bytes=sum(r['bytes'] for r in d['excluded_inputs']),
                      retained_selected_resourcepacks=d['selected_resourcepacks'],runtime_index_scope=d['runtime_index_scope'],
                      compression='ZIP DEFLATE method 8, level 9; no model/texture/terrain reduction',
                      excluded_by_tree_policy=['saves','logs','screenshots','backups','tests','PCL','Java','assets','libraries'],
                      required_license_source_retained=['Starlight-1cda73c-source.zip','Starlight-LGPL-3.0.txt','Starlight-NOTICE.txt'])
        a.plan.parent.mkdir(parents=True,exist_ok=True);a.plan.write_bytes(jsonbytes(report))
        if a.pack:
            results=[]
            for side,key in [('Server','server'),('Client_PCL','pcl')]:
                target=a.delivery/f'Project_SEELE_Encore_R54_{label}_{side}.zip'
                results.append(package(target,d[key],d['template'] if side=='Server' else None,d['bootstrap'] if side=='Server' else ()))
            report.update(pack_written=True,packages=results,revision=a.revision);a.plan.write_bytes(jsonbytes(report));(a.delivery/f'R54_{label}_DELIVERY_RECEIPT.json').write_bytes(jsonbytes(report))
        print(json.dumps(dict(plan=str(a.plan),pack_written=a.pack,bytes={side:{'raw':sum(r['raw_bytes'] for r in rows.values()),'estimated_zip':sum(r['estimated_zip_bytes'] for r in rows.values())} for side,rows in groups.items()},packages=report.get('packages',[])),ensure_ascii=False))
if __name__=='__main__':main()
