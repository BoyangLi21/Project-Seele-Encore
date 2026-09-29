"""Interim acceptance batch: verified subset, preserved progress, five archives."""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,zipfile
import build_server_ready_pack as base
from package_release_r39 import write,data,read,jar
from release_combat_r36 import guard

ROOT=base.ROOT;ART=ROOT/'artifacts/repair_r43';OUT=ROOT/'artifacts/server-ready-r43-stage';STAGE=OUT/'stage';WORLD='SEELE_R43_STAGE_WORLD';COMPOSED=ART/'world_composition/ready'/WORLD
SELECTED={'eva_body_r43.json':ART/'locomotion/eva_body_r43.json','eva_gameplay_r43_1.json':ART/'grounded_capture/eva_gameplay_r42_1.json','first_battle_r43.json':ART/'first_battle/first_battle_r43.json'}

def stage():
    guard();assert not (OUT/'batch.json').exists(),'Do not overwrite a completed release stage';OUT.mkdir(exist_ok=True)
    composition=read(ART/'world_composition/composed.json');assert Path(composition['destination'])==COMPOSED
    baseline=read(ROOT/'artifacts/facility_r31/baseline.json')
    for name,digest in baseline['original_user_files'].items():assert base.sha256(ROOT/name)==digest,('Protected pre-existing work changed',name)
    # Retain the already delivered, pinned dependency/visual set; no downloads.
    prior=ROOT/'artifacts/server-ready-r42/stage'
    for kind in ('client','server','textures','shaders'):base.copy_tree(prior/kind,STAGE/kind)
    base.copy_tree(COMPOSED,STAGE/'world',ignore_world_locks=True)
    runtime=OUT/'private_runtime';base.copy_runtime_mods(runtime);candidates=list(runtime.glob('projectseele-*.jar'));assert len(candidates)==1;built=candidates[0]
    inherited=read(ROOT/'run/projectseele-local-maps/revision_r42.json')
    marker=dict(revision='R43-stage',protocol=45,scope='User-requested interim acceptance, global reconstruction unfinished',runtime_sha256=dict(inherited['runtime_sha256']),
        new_profiles={name:base.sha256(p) for name,p in SELECTED.items()},new_grounded_attack_rigs=[1],inherited_attack_rigs=[0,2,3,4],new_jump_candidate_included=False,
        candidate_art_rejected=['jump_reference','jump_capture'],pending_world_plan_included=False)
    marker['runtime_sha256'].update(marker['new_profiles'])
    for kind in ('client','server'):
        folder=STAGE/kind;old=jar(folder)
        if old.name!=built.name:
            assert old.resolve().is_relative_to(STAGE.resolve());old.unlink()
        base.copy_file(built,folder/'mods'/built.name)
        for name,source in SELECTED.items():base.copy_file(source,folder/'projectseele-local-maps'/name)
        data(folder/'projectseele-local-maps/revision_r43_stage.json',marker)
        for name,digest in marker['runtime_sha256'].items():assert base.sha256(folder/'projectseele-local-maps'/name)==digest,name
        base.copy_file(ROOT/'docs/MANUAL_ACCEPTANCE_R43_STAGE.md',folder/'R43阶段安装与验收.md')
        base.copy_file(ROOT/'docs/QUALITY_MATRIX_R43.md',folder/'R43已验证与未完成.md')
        base.copy_file(ROOT/'docs/ROOT_CAUSES_R43.md',folder/'R43根因与证据.md')
        base.copy_file(ROOT/'docs/MANUAL_ACCEPTANCE_R43_STAGE.md',folder/('README_'+kind.upper()+'_CN.txt'))
        base.copy_file(ROOT/'docs/MANUAL_ACCEPTANCE_R43_STAGE.md',folder/'R43_STAGE_TEST_GUIDE_CN.md')
        base.copy_file(ROOT/'docs/R43_STAGE_NEXT_ROUND.md',folder/'下一轮继续清单.md')
        for legacy in ('R42_TEST_GUIDE_CN.md','R42安装与验收.md','R42整改与验证.md'):
            old=folder/legacy
            if old.exists():old.unlink()
    server=STAGE/'server';props=(server/'server.properties').read_text('utf-8-sig').replace('level-name=SEELE_R42_WORLD','level-name='+WORLD);write(server/'server.properties',props)
    for name in ('Start-Server.bat','start-server.sh'):
        p=server/name;write(p,p.read_text('utf-8-sig').replace('SEELE_R42_WORLD',WORLD).replace('R42','R43 Stage'))
    for name in ('Enable-Visuals.ps1','Enable-Visuals.bat'):
        p=STAGE/'client'/name;write(p,p.read_text('utf-8-sig').replace('R42','R43 Stage'))
    nav=STAGE/'world/nerv_routes_r24.json.gz'
    batch=dict(revision='R43-stage',protocol=45,world=WORLD,created=datetime.datetime.now().astimezone().isoformat(),mod_sha256=base.sha256(built),
        runtime=marker,changed_static_cells=composition['changed_cells'],owner_progress_from=composition['source'],owner_r42_unchanged=True,
        navigation_sha256=base.sha256(nav),global_complete=False,user_acceptance='PENDING',
        verification=dict(native_platform_paths=26,native_building_stair_paths=5112,whole_world_art=False,two_real_clients=False),
        deferred=['Full global architecture and art','Jump art candidate','All rig attack quality and angel combat','Full station entrance/transfer/live boarding coverage','Remaining isolated spaces','Next playable chapter'])
    assert base.sha256(jar(STAGE/'client'))==batch['mod_sha256']==base.sha256(jar(server))
    for kind in ('client','server','world','textures','shaders'):
        folder=STAGE/kind;data(folder/'R43_STAGE_BATCH.json',batch)
        old=folder/'R42_BATCH.json'
        if old.exists():old.unlink()
    data(OUT/'batch.json',batch);base.copy_file(ROOT/'docs/MANUAL_ACCEPTANCE_R43_STAGE.md',OUT/'阶段安装与验收.md');print('R43 interim stages ready',flush=True)

def seal():
    guard();batch=read(OUT/'batch.json');proof=read(OUT/'production_check.json');assert proof['passed'] and proof['mod_sha256']==batch['mod_sha256']
    rows=[]
    for kind in ('Client','Server','World','Textures','Shaders'):
        folder=STAGE/kind.lower();base.write_manifest(folder,'r43-stage-'+kind.lower());target=OUT/f'Project_SEELE_R43_Stage_{kind}.zip';assert not target.exists()
        with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            prefix='overrides/' if kind=='Client' else ''
            for p in sorted(folder.rglob('*')):
                if p.is_file():z.write(p,prefix+p.relative_to(folder).as_posix())
            if kind=='Client':
                z.writestr('manifest.json',json.dumps(dict(minecraft=dict(version='1.20.1',modLoaders=[dict(id='forge-47.4.10',primary=True)]),manifestType='minecraftModpack',manifestVersion=1,name='Project SEELE R43 Stage',version='R43-stage',author='Project SEELE',files=[],overrides='overrides'),ensure_ascii=False,indent=2))
                for p in sorted((STAGE/'world').rglob('*')):
                    if p.is_file():z.write(p,'overrides/saves/'+WORLD+'/'+p.relative_to(STAGE/'world').as_posix())
                z.writestr('先读我.txt','本批为阶段验收包，全域重构尚未完成。拖入 PCL 安装独立实例；模组、模型、存档、材质、光影已内置。原 R42 保留。请先看 R43阶段安装与验收.md。\n')
        with zipfile.ZipFile(target) as z:assert z.testzip() is None
        rows.append(dict(file=target.name,bytes=target.stat().st_size,sha256=base.sha256(target)));print(kind,'archive verified',flush=True)
    data(OUT/'RELEASE.json',dict(**batch,files=rows,server_validation=proof,scope='Interim handoff requested by user, not global quality completion'))
    write(OUT/'SHA256SUMS.txt',''.join(r['sha256']+'  '+r['file']+'\n' for r in rows))

def install():
    guard();release=read(OUT/'RELEASE.json');assert release['server_validation']['passed']
    original=Path(read(ROOT/'artifacts/server-ready-r42/installed_local.json')['pcl']);name='Project SEELE R43 Stage';target=original.parent/name
    assert not target.exists(),'Never replace an installed instance'
    base.copy_tree(STAGE/'client',target);base.copy_tree(STAGE/'world',target/'saves'/WORLD,ignore_world_locks=True)
    meta=read(original/(original.name+'.json'));meta['id']=name;data(target/(name+'.json'),meta);base.copy_file(original/(original.name+'.jar'),target/(name+'.jar'))
    assert base.sha256(jar(target))==release['mod_sha256'];assert base.sha256(target/'saves'/WORLD/'nerv_routes_r24.json.gz')==release['navigation_sha256']
    data(OUT/'installed_local.json',dict(pcl=str(target),world=str(target/'saves'/WORLD),original_instance_retained=str(original),accounts_copied=False));print('Installed independent PCL instance:',target,flush=True)

def refresh():
    """Refresh this unaccepted batch after the requested command cleanup."""
    guard();batch=read(OUT/'batch.json');proof=read(ART/'travel_commands/result.json')
    assert proof['passed'] and len(proof['cases'])==15 and all(r.get('settled') for r in proof['cases'])
    baseline=read(ROOT/'artifacts/facility_r31/baseline.json')
    for name,digest in baseline['original_user_files'].items():assert base.sha256(ROOT/name)==digest,name
    history=ART/'stage_refresh';history.mkdir(exist_ok=True)
    for name in ('batch.json','RELEASE.json','production_check.json'):
        if (OUT/name).exists() and not (history/name).exists():base.copy_file(OUT/name,history/name)
    runtime=OUT/'private_runtime';base.copy_runtime_mods(runtime)
    built=next(runtime.glob('projectseele-*.jar'));batch['mod_sha256']=base.sha256(built)
    batch['updated']=datetime.datetime.now().astimezone().isoformat()
    batch['verification']['travel_commands']=len(proof['cases'])
    batch['verification']['production_command_tree']=proof['root_commands']
    for kind in ('client','server'):
        folder=STAGE/kind;old=jar(folder);assert old.name==built.name
        base.copy_file(built,old)
        for name in ('R43阶段安装与验收.md','R43_STAGE_TEST_GUIDE_CN.md','README_'+kind.upper()+'_CN.txt'):
            base.copy_file(ROOT/'docs/MANUAL_ACCEPTANCE_R43_STAGE.md',folder/name)
        base.copy_file(ROOT/'docs/R43_STAGE_NEXT_ROUND.md',folder/'下一轮继续清单.md')
        if (ROOT/'docs/STORAGE_CLEANUP_R43.md').exists():base.copy_file(ROOT/'docs/STORAGE_CLEANUP_R43.md',folder/'工程清理记录.md')
    for kind in ('client','server','world','textures','shaders'):data(STAGE/kind/'R43_STAGE_BATCH.json',batch)
    assert base.sha256(STAGE/'world/nerv_routes_r24.json.gz')==batch['navigation_sha256']
    data(OUT/'batch.json',batch);base.copy_file(ROOT/'docs/MANUAL_ACCEPTANCE_R43_STAGE.md',OUT/'阶段安装与验收.md')
    for kind in ('Client','Server','World','Textures','Shaders'):
        previous=OUT/f'Project_SEELE_R43_Stage_{kind}.zip'
        assert previous.resolve().parent==OUT.resolve()
        if previous.exists():previous.unlink()
    print('Refreshed runtime and guide; staged world progress unchanged',flush=True)

def update_installed():
    guard();release=read(OUT/'RELEASE.json');assert release['server_validation']['passed']
    receipt=read(OUT/'installed_local.json');target=Path(receipt['pcl'])
    assert target.name=='Project SEELE R43 Stage' and target.is_dir()
    world=target/'saves'/WORLD
    before={p.relative_to(world).as_posix():base.sha256(p) for p in world.rglob('*') if p.is_file()}
    old=jar(target);candidate=jar(STAGE/'client');prior=read(ART/'stage_refresh/batch.json')['mod_sha256']
    assert base.sha256(old) in {prior,release['mod_sha256']},'Installed runtime changed outside this stage'
    assert old.name==candidate.name;base.copy_file(candidate,old)
    for source in (STAGE/'client').iterdir():
        if source.is_file() and source.suffix.lower() in {'.md','.txt','.json'} and source.name!='options.txt':base.copy_file(source,target/source.name)
    after={p.relative_to(world).as_posix():base.sha256(p) for p in world.rglob('*') if p.is_file()}
    assert before==after,'Installed world must remain untouched'
    receipt.update(runtime_sha256=base.sha256(old),world_files_unchanged=len(before),updated=datetime.datetime.now().astimezone().isoformat())
    data(OUT/'installed_local.json',receipt);print('Updated installed R43 runtime; preserved',len(before),'world files',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','seal','install','refresh','update_installed']);args=p.parse_args();globals()[args.action]()
