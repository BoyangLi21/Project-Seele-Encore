"""Six private R44 interim archives, inherited R43 runtime layout.

Root runs stage -> production check -> seal. No downloads, build or installation.
Existing stages/archives are never deleted or overwritten.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, os, re, shutil, tempfile, zipfile
import build_server_ready_pack as base
from package_release_r39 import write, data, read, jar
from release_combat_r36 import guard

ROOT = base.ROOT
ART = ROOT / 'artifacts/rebuild_r44'
OUT = ROOT / 'artifacts/server-ready-r44-stage'
STAGE = OUT / 'stage'
WORLD = 'SEELE_R44_STAGE_WORLD'
COMPOSED = ART / 'world_composition/ready' / WORLD
PRIOR = ROOT / 'artifacts/server-ready-r43-stage/stage'
SHADER = ART / 'atmosphere/geofront_shader_v3/ComplementaryUnbound_r5.3_SEELE_R44_GeoFrontCandidate_v3.zip'
DOCS = ('MANUAL_ACCEPTANCE_R44_STAGE.md', 'R44_STAGE_NEXT_ROUND.md')
KINDS = {'Client':'client', 'Client_Plain':'client_plain', 'Server':'server', 'World':'world', 'Textures':'textures', 'Shaders':'shaders'}
JUNK = {'logs','crash-reports','screenshots','Review','review','accounts.json','launcher_accounts.json',
        'launcher_profiles.json','usercache.json','usernamecache.json','gendo_player.png','session.lock'}
VISUAL_CONFIG = ('oculus','iris','shader','rubidium')

def forbidden(relative):
    parts = Path(relative).parts
    return any(p in JUNK for p in parts) or any('QA' in p.upper() or 'SEELE_FIELD_R44_REVIEW' in p for p in parts)

def copy_filtered(source, destination, *, plain=False, mods=False, config=False):
    assert source.is_dir(), source
    for p in sorted(source.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(source)
        if forbidden(rel) or p.suffix.lower() == '.log' or p.name.endswith('.lock'):
            continue
        if mods and (p.name.startswith('projectseele-') or plain and 'oculus' in p.name.lower()):
            continue
        if config and plain and any(t in p.name.lower() for t in VISUAL_CONFIG):
            continue
        if 'projectseele-local-maps' in source.as_posix() and (p.name.endswith(('_review.json','worldtour.json')) or p.name == 'manifest.json'):
            continue
        base.copy_file(p, destination / rel)

def review_flags():
    # Opt-in Boolean flags default false when absent. Never set path-valued
    # capturedLocomotionDirectory or private review drivers on launch.
    found = set()
    for p in (ROOT / 'src/main/java').rglob('*.java'):
        flags = re.findall(r'Boolean\.getBoolean\("(projectseele\.[A-Za-z0-9_]+)"\)',p.read_text(encoding='utf8'))
        found.update(q for q in flags if re.search(r'r44|review|witness|captur|preview|probe|smoke|fixture|author|test',q,re.I))
    found.update(('projectseele.r44TvCageReview','projectseele.r44TvPersonnelPlatformsReview',
                  'projectseele.r44NativeCraneMeshWitness','projectseele.r44CoordinationReview',
                  'projectseele.r44CapturedSupportOwnership','projectseele.r44RigidMachineryGpu'))
    return sorted(found)

def files_hash(root):
    return {p.relative_to(root).as_posix():base.sha256(p) for p in sorted(root.rglob('*'))
            if p.is_file() and not forbidden(p.relative_to(root)) and not p.name.endswith('.lock') and p.suffix.lower() != '.log'}

def atomic_new_json(path, value):
    assert not path.exists(), ('Completion marker already exists',path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=path.parent,prefix=path.name+'.partial-',delete=False) as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
        f.flush();os.fsync(f.fileno())
        temporary=Path(f.name)
    os.rename(temporary,path)

def ready_composition():
    marker = ART / 'world_composition/composed.json'
    assert marker.is_file(), 'Composition completion marker missing; do not package a directory being written'
    composed = read(marker)
    assert Path(composed['destination']).resolve() == COMPOSED.resolve()
    assert composed['source_progress_preserved'] and composed['new_story_enabled'] is False
    assert composed.get('npc_static_migration_pending') is False, 'Root must finish NPC field migration and atomically finalize composed.json'
    assert composed.get('city_archive_destination_verified') is True, 'Final city archive destination verification missing'
    assert (COMPOSED / 'level.dat').is_file()
    assert not (COMPOSED / 'city_coordination_r44.json').exists(), 'Unfinished story must stay unavailable'
    assert not (COMPOSED / 'r44_tv_personnel_platforms.json').exists(), '427/draft12 feature is not installed'
    import nbtlib
    from verify_main_r20 import entities
    expected = read(ART / 'hangar_machinery/GUARD_FLAGS_CLOSEOUT_R44_MANUAL/manifest.json')
    npc = entities(COMPOSED)[tuple(expected['uuid'])]
    assert npc.snbt() == nbtlib.parse_nbt(expected['after_snbt']).snbt(), 'Guard complete SOURCE-grounded after NBT not installed'
    assert base.sha256(COMPOSED / expected['registry_file']) == expected['registry_sha256']
    assert read(COMPOSED / expected['roster_file']) == expected['roster_after']
    gate = read(ART / 'hangar_machinery/DERIVED_CONFIG_WHITELIST_R44_MANUAL/whitelist.json')['required_copy_exact_qa_static'][0]
    assert base.sha256(COMPOSED / gate['name']) == gate['source_sha256']
    return composed

def install_docs(folder, kind):
    for name in DOCS:
        base.copy_file(ROOT / 'docs' / name, folder / name)
    if kind in ('client','client_plain','server'):
        base.copy_file(ROOT / 'docs' / DOCS[0],folder / ('README_' + kind.upper() + '_CN.txt'))

def set_options(client, plain, texture):
    options = {line.partition(':')[0]:line.partition(':')[2] for line in (PRIOR / 'client/options.txt').read_text(encoding='utf-8-sig').splitlines() if ':' in line}
    packs = ['vanilla','mod_resources'] + ([] if plain else ['file/' + texture])
    options.update(resourcePacks=json.dumps(packs),incompatibleResourcePacks=json.dumps([] if plain else ['file/' + texture]),lang='zh_cn')
    write(client / 'options.txt',''.join(k + ':' + v + '\n' for k,v in options.items()))
    write(client / 'PCL/Setup.ini','VersionArgumentIndieV2:True\n')

def verify_embedded_model(built):
    assets = ROOT / 'run/resourcepacks/eva_real_model/assets'
    with zipfile.ZipFile(built) as z:
        assert z.testzip() is None
        assert b'\x01\x00\x0249' in z.read('com/projectseele/network/SeeleNetwork.class'), 'Build is not protocol49'
        for p in assets.rglob('*'):
            if p.is_file():
                name = 'assets/' + p.relative_to(assets).as_posix()
                assert hashlib.sha256(z.read(name)).hexdigest() == base.sha256(p), name

def stage():
    guard()
    assert not STAGE.exists() and not (OUT / 'batch.json').exists(), 'Existing R44 stage preserved; use a new output revision after review'
    composed = ready_composition()
    for name in DOCS:
        assert (ROOT / 'docs' / name).is_file(), name
    baseline = read(ROOT / 'artifacts/facility_r31/baseline.json')
    for name,digest in baseline['original_user_files'].items():
        assert base.sha256(ROOT / name) == digest, ('Protected owner file changed',name)
    shader_proof = read(SHADER.parent / 'manifest.json')
    assert base.sha256(SHADER) == shader_proof['target_sha256']
    at_native_path=ART/'closeout_r44/at_visual_review.json'
    at_native=read(at_native_path)
    assert at_native['protocol']==49 and at_native['shader']==SHADER.name and at_native['native_ticks']>0
    texture_spec = read(ROOT / 'tools/realistic_pack_r25.json')
    texture = PRIOR / 'client/resourcepacks' / texture_spec['filename']
    assert hashlib.sha512(texture.read_bytes()).hexdigest() == texture_spec['sha512']
    OUT.mkdir(parents=True,exist_ok=True)
    base.validate_private_eva_mesh_contracts()
    runtime = OUT / 'private_runtime'
    assert not runtime.exists(), 'Do not overwrite a prior private runtime'
    base.copy_runtime_mods(runtime)
    assert len(list(runtime.glob('projectseele-*.jar'))) == 1
    built = next(runtime.glob('projectseele-*.jar'))
    verify_embedded_model(built)
    flags = review_flags()
    inherited = read(PRIOR / 'client/projectseele-local-maps/revision_r43_stage.json')
    for kind in ('client','client_plain','server'):
        folder = STAGE / kind
        prior = PRIOR / ('server' if kind == 'server' else 'client')
        plain = kind == 'client_plain'
        copy_filtered(prior / 'mods',folder / 'mods',plain=plain,mods=True)
        copy_filtered(prior / 'config',folder / 'config',plain=plain,config=True)
        copy_filtered(prior / 'projectseele-local-maps',folder / 'projectseele-local-maps')
        copy_filtered(prior / 'third_party_sources',folder / 'third_party_sources')
        for p in runtime.glob('*.jar'):
            base.copy_file(p,folder / 'mods' / p.name)
        for name,digest in inherited['runtime_sha256'].items():
            assert base.sha256(folder / 'projectseele-local-maps' / name) == digest, name
        for name in ('PRIVATE_USE_ONLY.txt','第一幕流程.md','素材来源.md'):
            if (prior / name).is_file():
                base.copy_file(prior / name,folder / name)
        data(folder / 'projectseele-local-maps/revision_r44_stage.json',dict(revision='R44-stage',protocol=49,
            runtime_sha256=inherited['runtime_sha256'],profiles_policy='Inherited R43 deployed actions; no private R44 captured directory',global_complete=False,manual_acceptance='PENDING'))
        data(folder / 'R44_STAGE_DEFAULTS.json',dict(false_system_flags={q:False for q in flags},private_review_driver_or_capture_directory=None,
            story_config_included=False,personnel_427_or_draft12_installed=False,shader_enabled=False))
        install_docs(folder,kind)
        if kind != 'server':
            set_options(folder,plain,texture.name)
    client = STAGE / 'client'
    base.copy_file(texture,client / 'resourcepacks' / texture.name)
    base.copy_file(texture,STAGE / 'textures/resourcepacks' / texture.name)
    for folder in (client,STAGE / 'shaders'):
        base.copy_file(SHADER,folder / 'shaderpacks' / SHADER.name)
        base.copy_file(SHADER.with_name(SHADER.name + '.txt'),folder / 'shaderpacks' / (SHADER.name + '.txt'))
        write(folder / 'config/oculus.properties','enableShaders=false\nshaderPack=' + SHADER.name + '\n')
        write(folder / 'Enable-Visuals.ps1',"$ErrorActionPreference = 'Stop'\n$pack = '" + SHADER.name + "'\n$installed = Join-Path $PSScriptRoot ('shaderpacks\\' + $pack)\nif (-not (Test-Path -LiteralPath $installed)) { throw 'Pinned R44 shader missing' }\n$cfg = Join-Path $PSScriptRoot 'config\\oculus.properties'\n[IO.Directory]::CreateDirectory((Split-Path -Parent $cfg)) | Out-Null\n[IO.File]::WriteAllText($cfg, \"enableShaders=true`nshaderPack=$pack`n\", [Text.UTF8Encoding]::new($false))\nWrite-Host 'R44 installed shader enabled; no downloads.'\n")
        write(folder / 'Enable-Visuals.bat','@echo off\r\ncd /d "%~dp0"\r\npowershell -NoProfile -ExecutionPolicy Bypass -File Enable-Visuals.ps1\r\npause\r\n')
    server = STAGE / 'server'
    copy_filtered(PRIOR / 'server/libraries',server / 'libraries')
    props = re.sub(r'^level-name=.*$', 'level-name=' + WORLD,(PRIOR / 'server/server.properties').read_text(encoding='utf-8-sig'),flags=re.M)
    props = re.sub(r'^motd=.*$', 'motd=Project SEELE: Encore R44 Stage',props,flags=re.M)
    write(server / 'server.properties',props)
    write(server / 'eula.txt','# Review Minecraft EULA before setting true.\neula=false\n')
    prior_args = (PRIOR / 'server/user_jvm_args.txt').read_text(encoding='utf-8-sig').splitlines()
    write(server / 'user_jvm_args.txt','\n'.join(x for x in prior_args if '-Dprojectseele.' not in x) + '\n' + ''.join('-D' + q + '=false\n' for q in flags))
    for name in ('Start-Server.bat','start-server.sh'):
        write(server / name,(PRIOR / 'server' / name).read_text(encoding='utf-8-sig').replace('SEELE_R43_STAGE_WORLD',WORLD))
    world_hashes = files_hash(COMPOSED)
    copy_filtered(COMPOSED,STAGE / 'world')
    copy_filtered(STAGE / 'world',server / WORLD)
    assert files_hash(STAGE / 'world') == world_hashes == files_hash(server / WORLD), 'Packaged world differs from completed composition'
    batch = dict(display_name='Project SEELE: Encore',revision='R44-stage',protocol=49,world=WORLD,instance='Project SEELE R44 Stage',
        created=datetime.datetime.now().astimezone().isoformat(),mod_sha256=base.sha256(built),runtime_profiles=inherited['runtime_sha256'],
        shader=dict(filename=SHADER.name,sha256=base.sha256(SHADER),enabled=False,native_compilation=True,visual_acceptance='PENDING',
            native_evidence=dict(source=str(at_native_path),sha256=base.sha256(at_native_path),native_ticks=at_native['native_ticks'],scope=at_native['scope'],global_lighting_or_art_passed=False)),
        texture=dict(filename=texture.name,sha256=base.sha256(texture)),owner_progress_from=composed['source'],composition=composed,
        global_complete=False,manual_acceptance='PENDING',user_acceptance='PENDING',new_story_enabled=False,false_system_flags=flags,
        navigation_sha256=base.sha256(STAGE / 'world/nerv_routes_r24.json.gz'),world_file_count=len(world_hashes),
        world_manifest_sha256=hashlib.sha256(json.dumps(world_hashes,sort_keys=True).encode()).hexdigest(),
        verification=dict(archive_integrity='PENDING',native_runtime='PENDING',art='PENDING',two_real_clients=False))
    for kind in KINDS.values():
        folder=STAGE / kind
        install_docs(folder,kind)
        data(folder / 'R44_STAGE_BATCH.json',batch)
    assert all(base.sha256(jar(STAGE / k)) == batch['mod_sha256'] for k in ('client','client_plain','server'))
    data(OUT / 'world_files.json',world_hashes)
    data(OUT / 'batch.json',batch)
    verify_stage(require_complete=False)
    atomic_new_json(OUT/'stage_complete.json',dict(batch_sha256=base.sha256(OUT/'batch.json'),mod_sha256=batch['mod_sha256'],
        composed_marker_sha256=base.sha256(ART/'world_composition/composed.json'),created=datetime.datetime.now().astimezone().isoformat()))
    print('R44 six stages ready; production check and seal remain',flush=True)

def verify_stage(require_complete=True):
    batch=read(OUT / 'batch.json')
    if require_complete:
        complete=read(OUT/'stage_complete.json')
        assert complete['batch_sha256']==base.sha256(OUT/'batch.json') and complete['mod_sha256']==batch['mod_sha256'], 'Staging completion marker is stale'
        assert complete['composed_marker_sha256']==base.sha256(ART/'world_composition/composed.json'), 'World composition marker changed after staging'
    assert batch['protocol']==49 and batch['global_complete'] is False and batch['manual_acceptance']=='PENDING'
    plain=STAGE / 'client_plain'
    assert not (plain/'resourcepacks').exists() and not (plain/'shaderpacks').exists()
    assert not list(plain.glob('Enable-Visuals.*')) and not list((plain/'mods').glob('*oculus*'))
    assert not any(any(s in p.name.lower() for s in VISUAL_CONFIG) for p in (plain/'config').rglob('*') if p.is_file())
    options=(plain/'options.txt').read_text(encoding='utf8')
    assert json.loads(next(x.split(':',1)[1] for x in options.splitlines() if x.startswith('resourcePacks:')))==['vanilla','mod_resources']
    assert sorted(p.name for p in (STAGE/'client/shaderpacks').glob('*.zip'))==[SHADER.name]
    assert 'enableShaders=false' in (STAGE/'client/config/oculus.properties').read_text()
    assert all(base.sha256(jar(STAGE/k))==batch['mod_sha256'] for k in ('client','client_plain','server'))
    expected=read(OUT/'world_files.json')
    # Batch/docs added after world source identity comparison are release metadata.
    for root in (STAGE/'world',STAGE/'server'/WORLD):
        assert all(base.sha256(root/name)==digest for name,digest in expected.items())
    for kind in KINDS.values():
        for p in (STAGE/kind).rglob('*'):
            if p.is_file():
                assert not forbidden(p.relative_to(STAGE/kind)), p
        for name in DOCS:
            assert base.sha256(STAGE/kind/name)==base.sha256(ROOT/'docs'/name)
    return batch

def recover():
    """Preserve an interrupted staging attempt before starting a fresh stage."""
    guard()
    assert not any((OUT/name).exists() for name in ('stage_complete.json','RELEASE.json','production_check.json')), 'Completed or checked batch cannot be recovered as interrupted'
    assert not list(OUT.glob('Project_SEELE_R44_Stage_*.zip')), 'Existing archives preserved; do not restage a sealing batch'
    partial=[OUT/name for name in ('stage','private_runtime','batch.json','world_files.json') if (OUT/name).exists()]
    assert partial, 'No interrupted staging artifacts'
    archive=OUT/'recovery'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    assert archive.resolve().is_relative_to(OUT.resolve()) and not archive.exists()
    archive.mkdir(parents=True)
    moves=[]
    for source in partial:
        destination=archive/source.name
        assert source.resolve().is_relative_to(OUT.resolve()) and destination.resolve().is_relative_to(OUT.resolve())
        assert not destination.exists()
        shutil.move(str(source),str(destination))
        moves.append(dict(source=str(source),preserved=str(destination)))
    data(archive/'recovery.json',dict(status='INTERRUPTED_STAGE_PRESERVED_NOT_DELETED',moves=moves))
    print('Preserved incomplete stage in '+str(archive)+'; rerun stage',flush=True)

def seal(compression_level=1):
    guard()
    batch=verify_stage()
    proof=read(OUT/'production_check.json')
    assert proof['passed'] and proof['mod_sha256']==batch['mod_sha256'], 'Actual current production-check evidence required'
    assert not (OUT/'RELEASE.json').exists(), 'Completed release preserved'
    for label in KINDS:
        assert not (OUT / ('Project_SEELE_R44_Stage_' + label + '.zip')).exists(), 'Existing ZIP preserved'
    rows=[]
    for label,kind in KINDS.items():
        folder=STAGE/kind
        base.write_manifest(folder,'r44-stage-'+kind)
        target=OUT / ('Project_SEELE_R44_Stage_' + label + '.zip')
        expected={}
        def add(z,p,name):
            assert name not in expected, ('Duplicate archive member',name)
            z.write(p,name)
            expected[name]=base.sha256(p)
        with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=compression_level,allowZip64=True) as z:
            client=kind in ('client','client_plain')
            prefix='overrides/' if client else ''
            for p in sorted(folder.rglob('*')):
                if p.is_file():
                    add(z,p,prefix+p.relative_to(folder).as_posix())
            if client:
                for p in sorted((STAGE/'world').rglob('*')):
                    if p.is_file():
                        add(z,p,'overrides/saves/'+WORLD+'/'+p.relative_to(STAGE/'world').as_posix())
                manifest=dict(minecraft=dict(version='1.20.1',modLoaders=[dict(id='forge-47.4.10',primary=True)]),manifestType='minecraftModpack',manifestVersion=1,
                    name='Project SEELE R44 Stage',version='R44-stage',author='Project SEELE: Encore',files=[],overrides='overrides')
                payload=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf8')
                z.writestr('manifest.json',payload)
                expected['manifest.json']=hashlib.sha256(payload).hexdigest()
        with zipfile.ZipFile(target) as z:
            assert z.testzip() is None, 'ZIP CRC failure'
            assert set(z.namelist())==set(expected)
            for name,digest in expected.items():
                h=hashlib.sha256()
                with z.open(name) as f:
                    for chunk in iter(lambda:f.read(1024*1024),b''):
                        h.update(chunk)
                assert h.hexdigest()==digest, ('Archive SHA readback mismatch',name)
            if kind in ('client','client_plain','server'):
                prefix='overrides/' if kind.startswith('client') else ''
                assert hashlib.sha256(z.read(prefix+'mods/'+jar(folder).name)).hexdigest()==batch['mod_sha256']
                world_entry=prefix+'saves/'+WORLD+'/level.dat' if kind.startswith('client') else WORLD+'/level.dat'
                assert world_entry in z.namelist()
        rows.append(dict(file=target.name,bytes=target.stat().st_size,sha256=base.sha256(target),crc_verified=True,member_sha256_verified=len(expected)))
        print(label+' CRC/SHA archive readback verified',flush=True)
    release=dict(**batch,files=rows,server_validation=proof,archive_integrity='CRC_AND_MEMBER_SHA256_VERIFIED',scope='Private interim handoff; global and manual acceptance unfinished')
    data(OUT/'RELEASE.json',release)
    write(OUT/'SHA256SUMS.txt',''.join(r['sha256']+'  '+r['file']+'\n' for r in rows))
    for name in DOCS:
        base.copy_file(ROOT/'docs'/name,OUT/name)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('stage','verify','seal','recover'))
    p.add_argument('--compression-level',type=int,choices=range(10),default=1)
    args=p.parse_args()
    if args.action=='stage': stage()
    elif args.action=='recover': recover()
    elif args.action=='verify': print(json.dumps(verify_stage(),ensure_ascii=False,indent=2))
    else: seal(args.compression_level)
