"""R50 world restoration with the final non-map code and motion payload.

No installed game or construction world is read or written. All release members
are derived from the two delivered R50 archives and explicitly selected fixes.
"""
from pathlib import Path
import argparse,copy,hashlib,io,json,os,re,zipfile

ROOT=Path(__file__).resolve().parents[1]
DELIVERY=Path('D:/eva/delivery')
OUT=ROOT/'artifacts/r52_map_rollback_delivery'
WORLD='SEELE_R50_WORLD/'
MOD='mods/projectseele-0.1.0-all.jar'
BATCH='Project_SEELE_Encore_R52_Rollback_20261012'
RUNTIME={
 'angel_grip_r31.json','articulated_bodies_r35.json','combat_bundle_r44.json','eva_body_r44.json',
 'eva_combat_capture_r31.json','eva_combat_capture_r31_un00.json','eva_combat_capture_r31_un01.json',
 'eva_dorsal_r30.json','eva_recovery_r31.json','first_battle_r44.json','sachiel_gameplay_r32.json','sachiel_wrap_r14.bin',
 *('eva_gameplay_r44_'+str(v)+'.json'for v in range(5)),
 *('handling_authoring_'+str(v)+'.json'for v in range(3))}
RESTORE_ASSETS={
 'assets/projectseele/mesh/tv_facilities_r16.json','assets/projectseele/mesh/tv_shoulder_shells_r44.json',
 'assets/projectseele/mesh/tripo_carrier_r48.json','assets/projectseele/mesh/tripo_gripper_r48.json',
 'data/projectseele/dimension_type/geofront.json'}
REMOVE_ASSETS={
 'assets/projectseele/facility/r52_upright_guideway_paths.json',
 'assets/projectseele/mesh/upright_outer_captured_r52.json',
 'assets/projectseele/mesh/legacy_floor_recesses_r52.json'}

def digest(data):return hashlib.sha256(data).hexdigest()
def sha(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
def equal(a,b):
 while True:
  x=a.read(1024*1024);y=b.read(1024*1024)
  if x!=y:return False
  if not x:return True

README='''# R52 地图回退修复版

本包使用原始 R50 世界，恢复金字塔下沉之前的总部、办公室、湖泊、机库、铁路、插入栓与发射设施。没有导入 R52 施工世界。地图游戏数据逐文件与原始 R50 压缩包比对；只清理旧说明、诊断文本及临时锁文件。

客户端：将本批 Client_PCL.zip 拖入 PCL，作为新实例安装。客户端和服务器必须一起更换。
服务器：先正常停服，解压到新目录，使用随包 SEELE_R50_WORLD。server.properties 已设 level-name=SEELE_R50_WORLD；面板若另外指定世界名，也要使用此名称。不要把旧 R52 世界文件混入该目录。原服务器另留备份。
Windows 使用 Start-Server.bat；Linux 使用 start-server.sh 或现有 Forge 47.4.10 / Java 17 启动方式。外部模组、服务器参数和光影配置沿用 R50。

保留最新走跑和动作衔接、持剑、处决数据、手部模型修复、运输机模型及兼容旧设施的运输/回收修复、碰撞和渲染改进、暴走供电、昼天使死亡处理等非地图更新。未重新选用用户撤回的两份 FBX。
新地图专属的串联发射井、多出口联动和新机场不在本包启用，相关实现与施工记录保留为代办。

修复回退不完整的问题：新地图自动安装/恢复、额外设施区块票及启动时机械资源预加载全部停用；原插入栓不再进入新地图权限分支。世界高度和 /seele tp 命令恢复原版。不是通过关闭 watchdog 或放宽碰撞检查掩盖问题。

常用命令：/seele tp hanger（旧机库）、/seele tp command（指挥室）、/seele tp station（总部站）、/seele tp dogma（莉莉丝层）、/seele tp misato、/seele tp school。
坐标：指挥室 28.5 -406 269.5；总部站 30.5 -466 451.5；终极教条前厅 31.5 -566 280.5；机库观察廊 90.5 -367 -221.5。

本次完成源码编译、回退入口检查和压缩包逐成员校验。未再启动游戏，实际登机、发射与游玩由用户验收。不声明服务器性能实测通过。
'''
TODO='''# 地图改造代办（本包未启用）

- 金字塔下沉及只让一个角入水的人工湖；天然湖分开。
- 新机库、位于其正下方的莉莉丝层和共同电梯。
- 三个串联大井、九条内部井道及地表/地下/箱根出口。
- 仅总部站下潜的铁路衔接，旧机库处理、旧残留与道路整理。
- 与新地图绑定的运输井、机场、多机跨层运输及狙击平台。
- 屋岛与港口完整战役、新装甲井及相关地图设施。

当前回退包保持原 R50 地图。以后先确认空间方案，不再次自行改造顶层办公室。
已做代码、地图及资源不删除；它们保留在工作区和先前 R52 施工记录中，未混入本包的世界。
'''

def main():
 global OUT,BATCH,README
 parser=argparse.ArgumentParser();parser.add_argument('--legacy-hangar-fixes',action='store_true')
 parser.add_argument('--candidate',type=int,default=22);parser.add_argument('--batch');parser.add_argument('--output-dir',type=Path)
 args=parser.parse_args()
 overlay={}
 if args.legacy_hangar_fixes:
  OUT=ROOT/'artifacts/r52_nonmap_unified_20261013_delivery';BATCH='Project_SEELE_Encore_R52_NonMapUnified_20261013'
  proof=json.loads((ROOT/'.Codex/r52_legacy_hangar_fix/MAP_PATCH_RECEIPT.json').read_text('utf8'))
  allowed={'dimensions/projectseele/geofront/region/r.-1.-1.mca','dimensions/projectseele/geofront/region/r.0.-1.mca','r48_underground_sortie.json','r48_entry_plug_bridge.json'}
  assert set(proof['files'])==allowed and proof['changed_cells']==6063
  for n,h in proof['files'].items():
   f=Path(proof['world_overlay'])/n;assert sha(f)==h;overlay[WORLD+n]=f.read_bytes()
  README=README.replace('# R52 地图回退修复版','# R52 地图回退·旧机库修复版')
  README=README.replace('地图游戏数据逐文件与原始 R50 压缩包比对；只清理旧说明、诊断文本及临时锁文件。','保留 R50 布局，仅改两个区域文件及两份旧机库布局记录：三门归位、清除旧门外 6045 格失配隐形碰撞、移除两侧楼梯 18 格栏杆。其他地图数据逐文件与原始 R50 包比对。')
  README+='''
## 本次旧机库必要修复

- 三扇地下后门回到原来三米厚的墙体内，采用互不相交的薄轨道；门洞原有关闭碰撞仍保留。清除原先漂在门洞外的隐形阻挡。
- 三台插入栓的两侧楼梯去掉栏杆，桥梁撤收生成逻辑同步修改；外围通道护栏保留。
- 原地下机场、原运输机 UUID 和三个旧机库接应台保留。电话运输部门会按机体所在地选择地下回收。机体需要地下出动后，在已登记的开阔接载区停稳；接应台上的机体直接进入回库流程。
- 地下机场入口：/seele tp geofront_airport，坐标 -353.5 -475 -299.5。没有搬迁或另建机场。无任务时停止对机场周边持续申请区块加载。

本次已做代码编译、真实门网格范围、旧碰撞与楼梯方块、原飞机身份和航线数据检查；完整接载/回库仍由用户游戏验收。
'''
 if args.batch:
  assert re.fullmatch(r'[A-Za-z0-9_]+',args.batch);BATCH=args.batch
 if args.output_dir:
  OUT=(ROOT/args.output_dir).resolve();assert OUT.is_relative_to(ROOT/'artifacts')
 README+='''
## 作战与桥侧修复

前两使徒在本回退包中恢复原地图的启动、目标区、战斗循环与重玩路径；新地图远端路线不再接管。插入栓桥侧使用方块图集纹理并按原三机库显示零号机橙、初号机紫、二号机红，兼容 R50 方块缺少 unit 属性。未修改作战进度或数值平衡。
'''
 OUT.mkdir(parents=True,exist_ok=True)
 candidate=args.candidate
 receipt=json.loads((ROOT/f'artifacts/r52_unified_candidate{candidate}/BUILD_RECEIPT.json').read_text('utf8'))
 assert receipt['build_exit']==0 and not receipt['changed_during_build']
 compiled=Path(receipt['jar']);assert sha(compiled)==receipt['sha256']
 baseline=DELIVERY/'Project_SEELE_Encore_R50_20261006_Server.zip'
 with zipfile.ZipFile(baseline)as base:
  original=zipfile.ZipFile(io.BytesIO(base.read(MOD)))
  with zipfile.ZipFile(compiled)as built:
   assert REMOVE_ASSETS<=set(built.namelist())
   selected=OUT/'projectseele-0.1.0-all.jar'
   assert not selected.exists()
   removed_bytes=sum(built.getinfo(n).file_size for n in REMOVE_ASSETS)
   with zipfile.ZipFile(selected,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as out:
    for item in built.infolist():
     n=item.filename
     if n in REMOVE_ASSETS:continue
     out.writestr(copy.copy(item),original.read(n)if n in RESTORE_ASSETS else built.read(n))
   with zipfile.ZipFile(selected)as final:
    assert set(final.namelist())==set(built.namelist())-REMOVE_ASSETS
    for n in final.namelist():
     assert final.read(n)==(original.read(n)if n in RESTORE_ASSETS else built.read(n)),n
    assert b'mapRebuildEnabledR52'in final.read('com/projectseele/world/NervRouteRuntimeR52.class')
    assert b'R50 map release: migrated-map installation is disabled'in final.read('com/projectseele/world/NervRootAssemblyInstallationR52.class')
    assert json.loads(final.read('data/projectseele/dimension_type/geofront.json'))['min_y']==-672
    model='assets/projectseele/models/block/entry_plug_bridge_fascia.json'
    assert final.read(model)==(ROOT/'src/main/resources'/model).read_bytes()
    fascia=json.loads(final.read(model))
    assert fascia['textures']['hazard']=='projectseele:block/nerv_machine_hazard'
    assert all(f['tintindex']==0 for f in fascia['elements'][0]['faces'].values())
    assert final.testzip()is None
  original.close()
 jar_sha=sha(selected)
 selection=dict(compiled_jar_sha256=receipt['sha256'],final_jar_sha256=jar_sha,
  compiled_classes_unchanged=True,map_assets_restored_from_actual_R50=sorted(RESTORE_ASSETS),
  disabled_map_assets_removed=sorted(REMOVE_ASSETS),uncompressed_map_asset_bytes_removed=removed_bytes,
  runtime_map_rebuild_enabled=False,world_source=str(baseline),world_source_sha256=sha(baseline),no_game_started=True,
  legacy_hangar_fixes=args.legacy_hangar_fixes,reviewed_world_overlay_sha256={n:digest(v)for n,v in overlay.items()})
 write(OUT/'SELECTION.json',selection)
 results=[]
 with zipfile.ZipFile(DELIVERY/'Project_SEELE_Encore_R52_20261012_Server.zip')as latest:
  runtime={n:latest.read('projectseele-local-maps/'+n)for n in RUNTIME}
 for side in ('Server','Client_PCL'):
  pref=''if side=='Server'else'overrides/'
  source=DELIVERY/f'Project_SEELE_Encore_R50_20261006_{side}.zip'
  target=DELIVERY/f'{BATCH}_{side}.zip';temp=target.with_suffix('.zip.part')
  assert not target.exists()and not temp.exists()
  retained={};changes={pref+MOD:selected.read_bytes()};removed=[]
  if side=='Server':changes.update(overlay)
  for n,data in runtime.items():changes[pref+'projectseele-local-maps/'+n]=data
  changes[pref+'README_R52_MAP_ROLLBACK.zh.md']=README.encode('utf8')
  changes[pref+'MAP_TODO.zh.md']=TODO.encode('utf8')
  changes[pref+'R52_ROLLBACK_BATCH.json']=json.dumps(selection,ensure_ascii=False,indent=2).encode('utf8')
  with zipfile.ZipFile(source)as base:
   names=set(base.namelist())
   launch_args='\n'.join(base.read(n).decode('utf8')for n in names if n.endswith(('/win_args.txt','/unix_args.txt')))
   if side=='Client_PCL':
    manifest=json.loads(base.read('manifest.json'));manifest.update(name=BATCH+'_PCL',version=BATCH)
    changes['manifest.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf8')
    changes[pref+'PCL/Setup.ini']=base.read(pref+'PCL/Setup.ini').replace(b'Initialize-R50-Visuals.ps1',b'Initialize-Visuals.ps1')
    changes[pref+'Initialize-Visuals.ps1']=base.read(pref+'Initialize-R50-Visuals.ps1')
   else:
    prop=base.read('server.properties').decode('utf8').replace('Encore R50','Encore R52 Rollback')
    assert 'level-name=SEELE_R50_WORLD' in prop
    changes['server.properties']=prop.encode('utf8')
   with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True)as out:
    for item in base.infolist():
     n=item.filename;local=n.removeprefix(pref)
     old_note=('/'not in local and (local.endswith('.md')or re.fullmatch(r'R\d+_BATCH\.json',local)))
     world_note=n.startswith(WORLD)and('/'not in n[len(WORLD):])and(n.endswith('.md')or(n.endswith('.txt')and not n.endswith('/xaeromap.txt'))or n.endswith('/session.lock'))
     unused_cache=(local.startswith('libraries/')and(local.endswith('.cache')or local.endswith(('-unpacked.jar','-slim.jar')))and local not in launch_args)
     old_init=local=='Initialize-R50-Visuals.ps1'
     if old_note or world_note or unused_cache or old_init:
      removed.append(n);continue
     if n in changes:continue
     data=base.read(n);out.writestr(copy.copy(item),data);retained[n]=digest(data)
    for n,data in changes.items():out.writestr(n,data,compress_type=zipfile.ZIP_STORED if n.endswith('.jar')else zipfile.ZIP_DEFLATED)
   with zipfile.ZipFile(temp)as final:
    assert len(final.namelist())==len(set(final.namelist()))
    assert set(final.namelist())==set(retained)|set(changes)
    for n,h in retained.items():assert digest(final.read(n))==h,n
    for n,data in changes.items():assert final.read(n)==data,n
    assert digest(final.read(pref+MOD))==jar_sha
    assert not any('/r52/'in n or 'ROOT_ASSEMBLY'in n or 'ROOT_MECHANICAL'in n for n in final.namelist())
    if side=='Server':
     expected={n for n in names if n.startswith(WORLD)}-set(removed)
     assert {n for n in final.namelist()if n.startswith(WORLD)}==expected
     for n in expected:
      if n in overlay:assert final.read(n)==overlay[n],n
      else:
       with base.open(n)as a,final.open(n)as b:assert equal(a,b),n
    assert final.testzip()is None
   os.replace(temp,target)
   results.append(dict(side=side,path=str(target),bytes=target.stat().st_size,sha256=sha(target),
    all_member_bytes_verified=True,original_R50_world_files_preserved=sum(n.startswith(WORLD)for n in retained),
    removed_unused_members=removed,nonmap_runtime_files_preserved=len(runtime),retained_members=len(retained)))
   print(json.dumps(results[-1],ensure_ascii=False),flush=True)
 write(OUT/'EXECUTION_RECEIPT.json',dict(archives=results,client_server_same_jar_sha256=jar_sha,
  original_world_game_data_unchanged=not args.legacy_hangar_fixes,reviewed_legacy_hangar_overlay=list(overlay),
  all_other_original_world_files_unchanged=True,source_world_written=False,game_started=False,subagents_used=False))
 print('R52 R50-map rollback package complete',flush=True)

if __name__=='__main__':main()
