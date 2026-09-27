"""Five complete R40 archives from the preserved world and adopted runtime."""
from pathlib import Path
import argparse,datetime,json,hashlib,shutil,subprocess,zipfile,msvcrt
import build_server_ready_pack as base
from package_release_r39 import write,data,read,jar
from fetch_facility_doors_r40 import ensure as doors

ROOT=base.ROOT;OUT=ROOT/'artifacts/server-ready-r40';STAGE=OUT/'stage';WORLD='SEELE_R31_WORLD'
COMPOSED=ROOT/'artifacts/world_combat_r40/world_composition/ready'/WORLD


def stage():
    from release_combat_r36 import guard
    guard();assert not STAGE.exists(),'Do not replace an existing release batch'
    marker=read(ROOT/'run/projectseele-local-maps/revision_r40.json')
    for name,digest in marker['runtime_sha256'].items():assert base.sha256(ROOT/'run/projectseele-local-maps'/name)==digest,name
    baseline=read(ROOT/'artifacts/facility_r31/baseline.json')
    for name,digest in baseline['original_user_files'].items():assert base.sha256(ROOT/name)==digest,name
    composition=read(ROOT/'artifacts/world_combat_r40/world_composition/composed.json');assert Path(composition['destination'])==COMPOSED
    base.WORLD_NAME=WORLD;base.validate_private_eva_mesh_contracts()
    guide=(ROOT/'docs/MANUAL_ACCEPTANCE_R40.md').read_text('utf8')
    server,client,world,textures,shaders=(STAGE/n for n in ('server','client','world','textures','shaders'))
    base.build_server(server,guide,revision='R40');base.build_client(client,guide,revision='R40',city_shaders=True)
    for folder in (server,client):base.copy_file(doors(),folder/'mods'/doors().name)
    with (COMPOSED/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        base.copy_tree(COMPOSED,world,ignore_world_locks=True,extra_ignore_patterns=('DistantHorizons.sqlite','DistantHorizons.sqlite-shm','DistantHorizons.sqlite-wal','lod_cache_r17.json'))
    shader=read(ROOT/'run/projectseele-local-maps/revision_r39.json')['shader'];texture=read(ROOT/'tools/realistic_pack_r25.json')
    for folder,kind,spec in ((textures,'resourcepacks',texture),(shaders,'shaderpacks',shader)):
        source=ROOT/'run'/kind/spec['filename']
        if 'sha512' in spec:assert hashlib.sha512(source.read_bytes()).hexdigest()==spec['sha512']
        else:assert base.sha256(source)==spec['sha256']
        for target in (folder,client):base.copy_file(source,target/kind/source.name)
        if kind=='shaderpacks':
            for target in (folder,client):
                base.copy_file(source.with_name(source.name+'.txt'),target/kind/(source.name+'.txt'))
                write(target/'config/oculus.properties','enableShaders=true\nshaderPack='+source.name+'\n')
        write(folder/'安装说明.txt','合并到对应版本的独立游戏目录。客户端 ZIP 已内置同一份资源，此包用于独立备份或更新。\n')
    for folder in (server,client):
        for source,name in [(ROOT/'docs/MANUAL_ACCEPTANCE_R40.md','R40安装与验收.md'),(ROOT/'docs/FIRST_ACT_R31_CN.md','第一幕流程.md'),(ROOT/'docs/ASSETS.md','素材来源.md')]:base.copy_file(source,folder/name)
        local=folder/'projectseele-local-maps'
        for p in list(local.glob('*worldtour.json'))+list(local.glob('*_review.json')):p.unlink()
        for name in ['jbullet-1.0.3-sources.jar','stack-alloc-sources.jar','vecmath-sources.jar']:base.copy_file(ROOT/'artifacts/combat_rebuild_r35/jbullet'/name,folder/'third_party_sources'/name)
    base.copy_tree(ROOT/'.Codex/server-pack-cache/runtime-r25/libraries',server/'libraries')
    write(server/'eula.txt','# Review https://aka.ms/MinecraftEULA before setting true.\neula=false\n')
    write(server/'Start-Server.bat','@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\nif not exist "'+WORLD+'\\level.dat" (echo Import World ZIP into '+WORLD+' first. & pause & exit /b 1)\r\nset "SEELE_JAVA=java"\r\nif defined JAVA_HOME set "SEELE_JAVA=%JAVA_HOME%\\bin\\java.exe"\r\n"%SEELE_JAVA%" @user_jvm_args.txt @libraries/net/minecraftforge/forge/1.20.1-47.4.10/win_args.txt nogui\r\npause\r\n')
    write(server/'start-server.sh','#!/usr/bin/env sh\ncd "$(dirname "$0")" || exit 1\nexec "${JAVA_HOME:+$JAVA_HOME/bin/}java" @user_jvm_args.txt @libraries/net/minecraftforge/forge/1.20.1-47.4.10/unix_args.txt nogui\n')
    write(client/'Enable-Visuals.ps1',"$ErrorActionPreference = 'Stop'\n$cfg = Join-Path $PSScriptRoot 'config\\oculus.properties'\n[IO.File]::WriteAllText($cfg, \"enableShaders=true`nshaderPack="+shader['filename']+"`n\", [Text.UTF8Encoding]::new($false))\nWrite-Host 'R40 pinned shader enabled; no downloads.'\n")
    write(client/'Enable-Visuals.bat','@echo off\r\ncd /d "%~dp0"\r\npowershell -NoProfile -ExecutionPolicy Bypass -File Enable-Visuals.ps1\r\npause\r\n')
    opts={line.partition(':')[0]:line.partition(':')[2] for line in (client/'options.txt').read_text().splitlines() if ':' in line}
    opts.update(lang='zh_cn',renderDistance='16',simulationDistance='8',gamma='1.0',resourcePacks=json.dumps(['vanilla','mod_resources','file/'+texture['filename'],'file/eva_real_model']),incompatibleResourcePacks=json.dumps(['file/'+texture['filename']]))
    write(client/'options.txt',''.join(k+':'+v+'\n' for k,v in opts.items()));write(client/'PCL/Setup.ini','VersionArgumentIndieV2:True\n')
    batch=dict(revision='R40',protocol=44,created=datetime.datetime.now().astimezone().isoformat(),world=WORLD,
               mod_sha256=base.sha256(jar(server)),runtime=marker,shader=shader,texture=texture['filename'],world_original_progress=True,
               changed_blocks=composition['changed_cells'],native_routes=composition['native_routes'])
    assert batch['mod_sha256']==base.sha256(jar(client))
    for folder in (server,client,world,textures,shaders):data(folder/'R40_BATCH.json',batch)
    data(OUT/'batch.json',batch);print('Five R40 stages ready',flush=True)


def seal():
    from release_combat_r36 import guard
    guard();proof=read(OUT/'production_check.json');assert proof['passed']
    acceptance=read(ROOT/'artifacts/world_combat_r40/native_acceptance.json');assert acceptance['passed']
    batch=read(OUT/'batch.json');assert proof['mod_sha256']==batch['mod_sha256']
    batch['source_head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();rows=[]
    for kind in ('Client','Server','World','Shaders','Textures'):
        folder=STAGE/kind.lower();data(folder/'R40_BATCH.json',batch)
        if kind!='World':base.write_manifest(folder,'r40-'+kind.lower())
        target=OUT/f'Project_SEELE_R40_{kind}.zip';assert not target.exists()
        with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            prefix='overrides/' if kind=='Client' else ''
            for p in sorted(folder.rglob('*')):
                if p.is_file():z.write(p,prefix+p.relative_to(folder).as_posix())
            if kind=='Client':
                z.writestr('manifest.json',json.dumps(dict(minecraft=dict(version='1.20.1',modLoaders=[dict(id='forge-47.4.10',primary=True)]),manifestType='minecraftModpack',manifestVersion=1,name='Project SEELE R40',version='R40',author='Project SEELE',files=[],overrides='overrides'),ensure_ascii=False,indent=2))
                for p in sorted((STAGE/'world').rglob('*')):
                    if p.is_file():z.write(p,'overrides/saves/'+WORLD+'/'+p.relative_to(STAGE/'world').as_posix())
                z.writestr('先读我.txt','将本 ZIP 拖入 PCL 安装新实例。模组、模型、存档、材质、光影全部内置；仅可能补下载缺失的 Minecraft/Forge 基础运行库。Java 17，建议 6–8 GB 内存。\n')
        with zipfile.ZipFile(target) as z:assert z.testzip() is None
        rows.append(dict(file=target.name,bytes=target.stat().st_size,sha256=base.sha256(target)));print(kind+' ZIP ready',flush=True)
    data(OUT/'RELEASE.json',dict(**batch,files=rows,native=acceptance,server_validation=proof,visual_acceptance='User manual acceptance; technical checks do not establish aesthetic perfection'))
    write(OUT/'SHA256SUMS.txt',''.join(r['sha256']+'  '+r['file']+'\n' for r in rows));base.copy_file(ROOT/'docs/MANUAL_ACCEPTANCE_R40.md',OUT/'安装与验收.md')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','seal']);args=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    stage() if args.action=='stage' else seal()
