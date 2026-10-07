"""Prepare one normal Forge client for the existing R49 QA world; --stage never starts Java."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,stat
from prepare_r50_two_pack import current_protocol
from r50_selected_payload import validate_selected_payload,validate_identity_coverage,equal_files
ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'artifacts/rebuild_r49'
OUT=ROOT/'artifacts/rebuild_r50/native_client'
GAME=INPUT/'native_qa/game'
QA=INPUT/'native_qa/worlds/SEELE_R49_QA'
WORLDS=QA.parent
BASE=ROOT/'artifacts/server-ready-r48-two-pack/stage/client'
R50_PREPARED=ROOT/'artifacts/server-ready-r50-two-pack/prepared'
TEMPLATE=ROOT/'artifacts/rebuild_r47/native_qa/client-release-source.json'
OLD='Project_SEELE_Encore_R46_20261004'
R48='Project_SEELE_Encore_R48_PCL_20261005'

def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def reparse_directory(path):
 # Windows junctions are directory reparse points, not Python symbolic links.
 return path.is_symlink() or bool(getattr(path.lstat(),'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400))

def saves_link_preflight():
 """Preserve any existing saves tree; only the parent link may point at the trusted worlds folder."""
 assert QA.is_dir() and not reparse_directory(QA),'The original QA save itself must be a real directory for Minecraft validation'
 assert (QA/'level.dat').is_file() and WORLDS.is_dir()
 saves=GAME/'saves'
 if os.path.lexists(saves):
  assert saves.is_dir() and reparse_directory(saves) and saves.resolve()==WORLDS.resolve(),(
   'Existing saves tree preserved: root must first back up the old game/saves directory and replace only that parent with a junction to native_qa/worlds; no child save junction or validation bypass is permitted')
  assert (saves/QA.name).is_dir() and not reparse_directory(saves/QA.name)
  assert (saves/QA.name).resolve()==QA.resolve(),'The normal child save must resolve to the same existing QA world'
 return saves

def ensure_saves_parent_link(saves):
 if not os.path.lexists(saves):
  assert os.name=='nt'
  def ps(value):return "'"+str(value).replace("'","''")+"'"
  subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command','New-Item -ItemType Junction -Path '+ps(saves)+' -Target '+ps(WORLDS)+' | Out-Null'],check=True)
 assert saves_link_preflight()==saves

def prepare(args):
 assert (QA/'level.dat').is_file(),'Only the already existing once-copied QA world may be used'
 receipt=json.loads((INPUT/'native_qa/COPY_ONCE.json').read_text('utf-8-sig'))
 assert Path(receipt['qa_world']).resolve()==QA.resolve() and receipt['copied_once']is True
 spec=json.loads(TEMPLATE.read_text('utf-8-sig'));original=spec['command']
 cmd=[part.replace(OLD,R48)for part in original if not part.startswith('-Dprojectseele.')]
 # Keep the established actual profile identity; never create a new login UUID.
 uid=cmd[cmd.index('--uuid')+1]
 assert any(p.stem.replace('-','')==uid.replace('-','')for p in (QA/'playerdata').glob('*.dat')),'Established template profile is absent from this QA progress'
 for flag,value in [('--gameDir',str(GAME.resolve())),('--version','Project_SEELE_Encore_R50_NATIVE'),('--quickPlaySingleplayer',QA.name)]:
  if flag in cmd:cmd[cmd.index(flag)+1]=value
  else:cmd += [flag,value]
 assert cmd[cmd.index('--launchTarget')+1]=='forgeclient' and cmd[cmd.index('--fml.forgeVersion')+1]=='47.4.10'
 cmd=[('-Dminecraft.launcher.brand=PCL'if v.startswith('-Dminecraft.launcher.brand=')else v)for v in cmd]
 cmd.insert(1,'-Dprojectseele.combatBundleDirectory=projectseele-local-maps')
 deps=[Path(cmd[0])]
 for flag in ('-cp','-p'):deps += [Path(x)for x in cmd[cmd.index(flag)+1].split(';')if x]
 for v in cmd:
  if v.startswith(('-Djava.library.path=','-Djna.tmpdir=','-Dorg.lwjgl.system.SharedLibraryExtractPath=','-Dio.netty.native.workdir=')):deps.append(Path(v.split('=',1)[1]))
 missing=[str(p)for p in deps if not p.exists()]
 assert not missing,('Launcher dependency missing',missing)
 assets=Path(cmd[cmd.index('--assetsDir')+1]);index_path=assets/'indexes'/(cmd[cmd.index('--assetIndex')+1]+'.json');assert index_path.is_file()
 index=json.loads(index_path.read_text('utf8'));objects=index.get('objects',{});missing_assets=[name for name,obj in objects.items()if not (assets/'objects'/obj['hash'][:2]/obj['hash']).is_file()];assert not missing_assets
 native=Path(next(v.split('=',1)[1]for v in cmd if v.startswith('-Djava.library.path=')))
 assert all((native/name).is_file()for name in ('lwjgl.dll','glfw.dll','lwjgl_opengl.dll','OpenAL.dll','lwjgl_stb.dll','jemalloc.dll'))
 assert not any(v.startswith('-Dprojectseele.')and v!='-Dprojectseele.combatBundleDirectory=projectseele-local-maps'for v in cmd)
 environment={k:v for k,v in spec.get('environment',{}).items()if k!='MOD_CLASSES'}
 assert not any('projectseele.'in environment.get(k,'')for k in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS'))
 spec=dict(command=cmd,workingDirectory=str(GAME.resolve()),environment=environment,prepared_only=True,
  normal_tick_rate=20,developer_or_qa_override=False,qa_world=str(QA.resolve()),no_world_copy=True,no_player_or_entity_NBT_mutation=True,
  established_profile_identity_preserved=True,protocol=current_protocol(),final_jar_and_formal_identity_pending=True,
  save_link_strategy='parent saves junction to native_qa/worlds; QA child remains a real directory',
  save_link=str(GAME/'saves'),save_link_target=str(WORLDS.resolve()),minecraft_save_validation_unchanged=True)
 write(OUT/'launch.json',spec)
 def quote(value):
  assert not any(c in value for c in '\r\n\0')
  return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'
 (OUT/'launch.args').write_text('\n'.join(quote(x)for x in cmd[1:])+'\n',encoding='utf-8')
 write(OUT/'PREPARED_ONLY.json',dict(template=str(TEMPLATE),actual_R48_PCL_runtime_inherited=True,launcher_references_checked=len(deps),missing_dependencies=[],asset_objects_checked=len(objects),missing_asset_objects=[],
   existing_QA_world=str(QA.resolve()),game=str(GAME.resolve()),preserve_identity=True,normal_tick_rate=20,normal_forgeclient=True,
   save_link_strategy='parent saves junction',save_link=str(GAME/'saves'),save_link_target=str(WORLDS.resolve()),QA_child_is_real_directory=True,minecraft_save_validation_unchanged=True,
   project_override_only='relative combatBundleDirectory (production owner)',Java_started=False,world_copied=False,world_NBT_written=False,
   final_root_stage_command='python tools/prepare_r50_native_client.py --stage --jar artifacts/rebuild_r49/release_inputs/projectseele-0.1.0-all.jar'))
 return spec

def stage(args,spec):
 jar=args.jar.resolve();assert jar.parent==(INPUT/'release_inputs').resolve() and jar.is_file()
 # Use the exact final two-pack recipe. The Java client bootstrap already
 # supports its R50 local filename; never stage a prebuilt private derivative.
 recipe_source=R50_PREPARED/'private_shader_recipe_v12.json'
 assert recipe_source.is_file(),'Run the prepare_r50_two_pack plan first; its final R50 local shader recipe is required'
 recipe=json.loads(recipe_source.read_text('utf-8-sig'))
 assert recipe.get('schema')=='projectseele.local-private-shader-adapter.v12'
 assert recipe.get('scope')=='LOCAL_PERSONAL_ONLY_NOT_PREBUILT_SHADER_DISTRIBUTION'
 assert recipe.get('input_filename')=='ComplementaryUnbound_r5.3.zip' and recipe.get('output_filename')=='SEELE_Local_Cavern_R50_Private_v1.zip'
 assert recipe.get('input_sha256')=='66061b3c5b4843e31bc9a7562a7ac697a51bb77c73defc7071f996b783efacce'
 assert recipe.get('input_license_sha256')=='1e1f730abd9c25ad4d0ba301453d37547d17102a3cfc628de794d5b08e278a20'
 credits_source=BASE/'COMPLEMENTARY_CREDITS.txt'
 assert credits_source.is_file(),'Pinned original Complementary credits must accompany the recipe'
 for source in (recipe_source,credits_source):
  target=GAME/source.name
  assert not target.exists() or equal_files(target,source),('Existing client shader recipe/credits preserved; inspect before replacing',target)
 validate_identity_coverage(INPUT/'assets',INPUT/'runtime');validate_selected_payload(jar,INPUT/'assets')
 from release_r45_contract import class_protocol
 import zipfile
 with zipfile.ZipFile(jar)as z:assert class_protocol(z.read('com/projectseele/network/SeeleNetwork.class'))==current_protocol()
 # Check before copying any mods/configs. An old per-save junction is left
 # intact for root's explicit backup; this script never moves/deletes it.
 saves=saves_link_preflight()
 dependencies=[p for p in (BASE/'mods').glob('*.jar')if not p.name.lower().startswith('projectseele-')]
 assert len(dependencies)==20
 mods=GAME/'mods';mods.mkdir(parents=True,exist_ok=True)
 allowed={p.name for p in dependencies}|{'projectseele-0.1.0-all.jar'}
 assert set(p.name for p in mods.glob('*.jar')).issubset(allowed),'Foreign extra mods preserved; inspect before staging'
 originals=list(mods.glob('projectseele-*.jar'));assert len(originals)<=1 and all(p.name=='projectseele-0.1.0-all.jar'for p in originals),'Foreign project Jar preserved'
 for source in dependencies+[jar]:
  target=mods/('projectseele-0.1.0-all.jar'if source==jar else source.name)
  if target.exists()and equal_files(target,source):continue
  if target.exists():
   backup=OUT/'stage_before'/target.relative_to(GAME);backup.parent.mkdir(parents=True,exist_ok=True)
   if backup.exists():
    assert args.replace_owned_candidate and source==jar and (OUT/'STAGED.json').is_file(),'Earlier stage backup preserved; replacing a reviewed project candidate requires the explicit flag'
    assert json.loads((OUT/'STAGED.json').read_text('utf8')).get('normal_client')is True
   else:shutil.copy2(target,backup)
  shutil.copy2(source,target)
 assert len(list(mods.glob('*.jar')))==21,'Unknown extra or missing QA client mods; preserve and inspect'
 for folder in ('config','projectseele-local-maps'):
  for source in (INPUT/'runtime'/folder).rglob('*'):
   if source.is_file():
    target=GAME/folder/source.relative_to(INPUT/'runtime'/folder);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
 for folder in ('resourcepacks','shaderpacks'):
  for source in (BASE/folder).rglob('*'):
   if source.is_file():
    target=GAME/folder/source.relative_to(BASE/folder);target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():shutil.copy2(source,target)
 for source in (recipe_source,credits_source):
  target=GAME/source.name
  if not target.exists():shutil.copy2(source,target)
 if not (GAME/'options.txt').exists():shutil.copy2(BASE/'options.txt',GAME/'options.txt')
 ensure_saves_parent_link(saves)
 spec['final_jar_and_formal_identity_pending']=False;write(OUT/'launch.json',spec)
 write(OUT/'STAGED.json',dict(normal_client=True,normal_tick_rate=20,protocol=current_protocol(),world_link=str(saves),world_target=str(WORLDS.resolve()),
  selected_world=str(saves/QA.name),selected_world_target=str(QA.resolve()),selected_world_is_real_directory=True,minecraft_save_validation_unchanged=True,
  local_shader_recipe=str(recipe_source),local_shader_output=recipe['output_filename'],private_derivative_prebuilt_or_copied=False,
  client_bootstrap='Existing LocalPrivateShaderBootstrapR46 creates and validates the declared local-only v12 derivative on first normal client setup; existing ZIP/settings and later user choices are preserved',
  world_copied=False,NBT_written=False,Java_started=False))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',action='store_true');p.add_argument('--replace-owned-candidate',action='store_true');p.add_argument('--jar',type=Path,default=INPUT/'release_inputs/projectseele-0.1.0-all.jar');a=p.parse_args()
 spec=prepare(a)
 if a.stage:stage(a,spec)
 print('Prepared normal client launch; Java not started; existing QA world not copied or edited.')
if __name__=='__main__':main()
