"""Wrap the unchanged R47 client payload in PCL's CurseForge import format."""
from pathlib import Path
import argparse,json,zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE_URL='https://github.com/Meloong-Git/PCL/blob/main/Plain%20Craft%20Launcher%202/Modules/Minecraft/ModModpack.vb'
MACRO_URL='https://github.com/Meloong-Git/PCL/wiki/%E6%9B%BF%E6%8D%A2%E6%A0%87%E8%AE%B0'
NAME='Project_SEELE_Encore_R47_PCL_20261005'
GUIDE='''# R47 PCL 导入版

把此 ZIP 直接拖入 PCL 主窗口，或在下载页使用“安装整合包”。确认新版本名称后等待安装，选择 Java 17 启动。

Minecraft 1.20.1、Forge 47.4.10。全部模组、材质和配置都随包提供，不需要从 CurseForge 重新下载模组；PCL 只在基础游戏或 Forge 文件缺失时补充下载。

首次启动会在本实例内生成 R47 个人光影适配，完成后后续启动直接跳过。默认关闭光影；需要时在游戏“视频设置→光影”中选择 SEELE_Local_Cavern_R47_Private_v1.zip。若关闭了 PCL 的启动前命令，可在实例目录运行 Initialize-R47-Visuals.ps1 一次。初始化失败详情保存在 R47-Visual-Initialization-Error.txt。

这个客户端和先前 R47 服务器包使用同一模组版本。服务器包无需更换；客户端不重复包含整个世界，单人游玩可把同批服务器包里的 SEELE_R47_WORLD 复制到此实例的 saves。

旧 Client.zip 是手动实例文件包；本 Client_PCL.zip 才是可拖入导入的整合包。无需使用 Install-R47-From-Local-R46.ps1，也不要求保留 R46 实例。
'''

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--source',type=Path,default=ROOT/'delivery/Project_SEELE_Encore_R47_20261005_Client.zip')
 parser.add_argument('--output',type=Path,default=ROOT/'delivery/Project_SEELE_Encore_R47_20261005_Client_PCL.zip')
 args=parser.parse_args()
 if args.output.exists()or Path(str(args.output)+'.part').exists():raise ValueError('Existing output is preserved; choose another file')
 manifest=dict(minecraft=dict(version='1.20.1',modLoaders=[dict(id='forge-47.4.10',primary=True)]),manifestType='minecraftModpack',manifestVersion=1,name=NAME,version='R47-20261005-PCL1',author='Boyang Li',files=[],overrides='overrides')
 setup='\r\n'.join(['VersionArgumentIndie:1','VersionArgumentIndieV2:True','IsStar:False',
  'VersionAdvanceRun:powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{version_indie}Initialize-R47-Visuals.ps1"',
  'VersionAdvanceRunWait:True',''])
 wrapper=(ROOT/'tools/templates/r47/Initialize-R47-Visuals.ps1').read_bytes()
 partial=Path(str(args.output)+'.part');copied=[]
 with zipfile.ZipFile(args.source)as source,zipfile.ZipFile(partial,'x',allowZip64=True)as output:
  output.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
  output.writestr('PCL_IMPORT_R47.zh.md',GUIDE)
  for entry in source.infolist():
   name=entry.filename
   if entry.is_dir()or name.startswith('profile_templates/')or name in {'PCL/Setup.ini','Install-R47-From-Local-R46.ps1'}:continue
   if name.startswith('/')or '..'in Path(name).parts:raise ValueError('Unsafe source member '+name)
   data=source.read(name)
   if name=='README_R47.zh.md':
    data=(GUIDE+'\n详见随包 MANUAL_R47.zh.md 与 NEXT_ROUND_R47.zh.md。\n').encode('utf8')
   elif name=='MANUAL_R47.zh.md':
    data=(GUIDE+'\n---\n以下保留原 R47 更新与验收记录；其中旧 Client.zip 的手动安装步骤仅适用于旧实例文件包。\n\n'+data.decode('utf8')).encode('utf8')
   output.writestr('overrides/'+name,data,compress_type=entry.compress_type)
   copied.append(name)
  output.writestr('overrides/PCL/Setup.ini',setup)
  output.writestr('overrides/Initialize-R47-Visuals.ps1',wrapper)
  output.writestr('overrides/PCL_IMPORT_R47.zh.md',GUIDE)
 partial.replace(args.output)
 # Read the real new archive's import declaration and critical unchanged payload.
 with zipfile.ZipFile(args.output)as output,zipfile.ZipFile(args.source)as source:
  parsed=json.loads(output.read('manifest.json'));assert parsed==manifest
  assert not parsed['files']and parsed['overrides']=='overrides'
  for name in copied:
   if name in {'README_R47.zh.md','MANUAL_R47.zh.md'}:continue
   a=source.getinfo(name);b=output.getinfo('overrides/'+name)
   assert(a.CRC,a.file_size)==(b.CRC,b.file_size),name
  mods=[n for n in copied if n.startswith('mods/')and n.endswith('.jar')]
  assert 'mods/projectseele-0.1.0-all.jar'in mods
  assert b'{version_indie}Initialize-R47-Visuals.ps1'in output.read('overrides/PCL/Setup.ini')
 receipt=dict(output=str(args.output),bytes=args.output.stat().st_size,format='CurseForge manifest v1 consumed by PCL',bundled_mods=len(mods),remote_mod_downloads=0,minecraft='1.20.1',forge='47.4.10',game_jar_unchanged=True,server_unchanged=True,world_unchanged=True,source_importer=SOURCE_URL,source_macro_documentation=MACRO_URL,actual_archive_readback=True,PCL_GUI_import_not_executed=True,SHA_tests=False)
 folder=ROOT/'artifacts/rebuild_r47/pcl_import_fix';folder.mkdir(parents=True,exist_ok=True)
 (folder/'readback.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
 print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
