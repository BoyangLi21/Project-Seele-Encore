"""Prepare two R47 file packs; only Root --execute copies the cold world/builds ZIPs.

No Java, Gradle, download, SHA suite, existing-stage removal or PCL mutation.
"""
from pathlib import Path
import argparse,copy,json,os,shutil,zipfile,sys,time
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/server-ready-r46-two-pack/stage'
OUT=ROOT/'artifacts/server-ready-r47-two-pack'
STAGE=OUT/'stage';DELIVERY=ROOT/'delivery'
BATCH='Project_SEELE_Encore_R47_20261005';WORLD_NAME='SEELE_R47_WORLD'
OLD_PROFILE='Project_SEELE_Encore_R46_20261004';PROFILE=BATCH
PCL_BASE=Path(os.environ.get('APPDATA','C:/Users/liboy/AppData/Roaming'))/'.minecraft/versions'/OLD_PROFILE
TEMPLATES=ROOT/'tools/templates/r47'
PROTOCOL='55'
DOCUMENTS=('README_R47.zh.md','MANUAL_R47.zh.md','NEXT_ROUND_R47.zh.md')
EXCLUDED_DIRS={'logs','screenshots','crash-reports','debug','reports','native_qa'}
def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
def need(condition,message):
 if not condition:raise RuntimeError(message)
def safe_relative(value):
 p=Path(value);need(not p.is_absolute()and'..'not in p.parts,'Unsafe package relative path: '+value);return p
def profile_copy(value):
 if isinstance(value,dict):return {k:profile_copy(v)for k,v in value.items()}
 if isinstance(value,list):return [profile_copy(v)for v in value if not(isinstance(v,str)and v.startswith('-Dprojectseele.')and not v.startswith('-Dprojectseele.combatBundleDirectory='))]
 if isinstance(value,str):return value.replace(OLD_PROFILE,PROFILE)
 return value
def dependency_inventory():
 return {side:[p.name for p in sorted((BASE/side/'mods').glob('*.jar'))if not p.name.lower().startswith('projectseele-')]for side in ('server','client')}
def validate_jar(path):
 from release_r45_contract import class_protocol
 with zipfile.ZipFile(path)as z:
  names=set(z.namelist());need(class_protocol(z.read('com/projectseele/network/SeeleNetwork.class'))==PROTOCOL,'Final jar protocol must be55')
  required={
   'assets/projectseele/mesh/eva_unit00_anatomical_hands_r45.mesh.json',
   'assets/projectseele/mesh/eva_unit01_anatomical_hands_r45.mesh.json',
   'assets/projectseele/mesh/eva_unit02_anatomical_hands_r45.mesh.json',
   'assets/projectseele/mesh/tv_shoulder_shells_r44.json',
   'com/projectseele/world/TvPersonnelSemanticEpochR47.class',
   'com/projectseele/world/CityNativeUnionProbeR47.class',
   'com/projectseele/world/PilotRestroomsR47.class',
   'com/projectseele/world/PilotRestroomsR47$Plan.class',
   'com/projectseele/world/PilotRestroomsR47$SeatState.class',
   'com/projectseele/world/PilotRestroomServicesR47.class',
   'com/projectseele/world/PilotRestroomServicesR47$PhoneCall.class',
   'com/projectseele/world/PilotRestroomServicesR47$Alarm.class',
   'com/projectseele/world/PilotRestroomServicesR47$State.class',
   'com/projectseele/world/PilotRestroomServicesR47$UUIDGuard.class',
   'com/projectseele/world/NervRoomPartitionR47.class',
   'com/projectseele/entity/NervCommandSeatEntity.class',
   'com/projectseele/client/render/NervCommandSeatRenderer.class',
   'com/projectseele/world/SeeleConferenceAccessR47.class',
   'com/projectseele/world/SeeleConferenceAccessR47$Lease.class',
   'com/projectseele/world/SeeleConferenceAccessR47$Swipe.class',
   'com/projectseele/world/SeeleConferencePropsR47.class',
   'com/projectseele/world/SeeleConferencePropsR47$Prop.class',
   'com/projectseele/world/SeeleConferencePropsR47$State.class',
   'com/projectseele/registry/SeeleConferenceEntitiesR47.class',
   'com/projectseele/entity/SeeleMonolithEntityR47.class',
   'com/projectseele/client/render/SeeleMonolithRendererR47.class',
   'META-INF/mods.toml','projectseele.mixins.json',
   'com/projectseele/mixin/client/LclWaterResourceReloadR47Mixin.class',
   'com/projectseele/mixin/client/MovingElevatorRenderOriginR47Mixin.class'}
  assets=ROOT/'artifacts/rebuild_r47/assets'
  for top in ('assets','data','META-INF/licenses'):
   for p in (assets/top).rglob('*'):
    if p.is_file():required.add(p.relative_to(assets).as_posix())
  missing=sorted(required-names);need(not missing,'Final fatjar omitted selected resources/classes: '+str(missing[:20]))
  mods=z.read('META-INF/mods.toml').decode('utf-8-sig')
  need('${'not in mods,'Final jar registration metadata contains an unresolved source template')
  mixins=json.loads(z.read('projectseele.mixins.json').decode('utf-8-sig'))
  client_mixins=mixins.get('client',[])
  need(isinstance(client_mixins,list),'Final client mixin list is absent or malformed')
  for entry in ('client.LclWaterResourceReloadR47Mixin','client.MovingElevatorRenderOriginR47Mixin'):
   need(entry in client_mixins,'Final source client mixin omitted by an older snapshot: '+entry)
  need(b'SeelePilotLastRouteFaultR47'in z.read('com/projectseele/world/TrainingPilotDirector.class'),'Final jar lacks the native-ground-settle correction')
  pilot=z.read('com/projectseele/world/TrainingPilotDirector.class')
  for marker in (b'SeelePilotRestroomEpochR47',b'migration:original_approach_absent',b'SeelePilotReturnRejectR47',b'returnReject={'):
   need(marker in pilot,'Final jar omitted the current original-pilot migration/return diagnostic: '+marker.decode('ascii'))
  need(b'PILOT_REST_SEAT_R47'in z.read('com/projectseele/entity/NervCommandSeatEntity.class'),'Final jar omitted the persistent original-pilot chair support')
  need(b'r47-original-pilot-restrooms-v2'in z.read('com/projectseele/world/PilotRestroomsR47.class'),'Final jar retained the retired v1 pilot-room epoch')
  need(b'ownsRoomMaintenanceSpaceR47'in z.read('com/projectseele/world/EvaHangarBuilder.class'),'Final jar omitted the bounded room-maintenance protection')
  return dict(protocol=PROTOCOL,bytes=path.stat().st_size,selected_entries_checked=len(required),hash_test=False)
def plan(args):
 need((BASE/'server/libraries/net/minecraftforge/forge/1.20.1-47.4.10/win_args.txt').is_file(),'Retained R46 complete Forge runtime missing')
 need((BASE/'server/libraries/net/minecraftforge/forge/1.20.1-47.4.10/unix_args.txt').is_file(),'Retained Linux Forge argument runtime missing')
 original_profile=PCL_BASE/(OLD_PROFILE+'.json')
 profile_source=original_profile if original_profile.is_file()else TEMPLATES/(PROFILE+'.json')
 profile=profile_copy(json.loads(profile_source.read_text('utf8')));profile['id']=PROFILE
 need(profile['mainClass']=='cpw.mods.bootstraplauncher.BootstrapLauncher','Preserved actual Forge profile required')
 prepared=OUT/'prepared';write(prepared/'profile_templates'/(PROFILE+'.json'),profile)
 prepared.mkdir(parents=True,exist_ok=True);shutil.copy2(TEMPLATES/'Install-R47-From-Local-R46.ps1',prepared/'Install-R47-From-Local-R46.ps1')
 recipe_source=args.shader_recipe or BASE/'client/private_shader_recipe_v12.json'
 recipe=json.loads(recipe_source.read_text('utf8'))
 need(recipe['scope']=='LOCAL_PERSONAL_ONLY_NOT_PREBUILT_SHADER_DISTRIBUTION','Local authorized shader recipe required')
 need(recipe['input_filename']=='ComplementaryUnbound_r5.3.zip','Original shader input differs')
 recipe['output_filename']='SEELE_Local_Cavern_R47_Private_v1.zip'
 write(prepared/'private_shader_recipe_v12.json',recipe)
 result=dict(schema='projectseele.r47.two-pack-plan.v1',prepared_only=not(args.execute or args.finish_staged),
  stage_root=str(STAGE),outputs=[str(DELIVERY/(BATCH+'_Server.zip')),str(DELIVERY/(BATCH+'_Client.zip'))],
  dependencies_base=str(BASE),dependencies=dependency_inventory(),forge='47.4.10',minecraft='1.20.1',protocol=PROTOCOL,
  jar=str(args.jar.resolve()),jar_current_bytes=args.jar.stat().st_size if args.jar.is_file()else None,
  runtime=str(args.runtime.resolve()),world=str(args.world.resolve()),world_name=WORLD_NAME,
  world_copy_count=1,world_pack='server only; local client may copy the same Server world after extraction',
  world_progress='Full original .dat/.mca/playerdata/entities/MTR/mission/city progress retained; no reset/import from another QA world',
  docs=str(args.docs.resolve()),required_docs=DOCUMENTS,pcl_instance=PROFILE,pcl_profile_base=str(PCL_BASE),
  client_format='Plain instance file bundle, not advertised as direct PCL modpack import',
  source_shader=str(recipe_source.resolve()),prepared_shader_recipe=str(prepared/'private_shader_recipe_v12.json'),
  texture_files=[p.name for p in sorted((BASE/'client/resourcepacks').glob('*.zip'))],
  shader_files=['ComplementaryUnbound_r5.3.zip'],prebuilt_personal_shader_distributed=False,
  excludes=['All old project jars replaced by exactly one final fatjar','R46 docs/batch/status files','logs/screenshots/crash reports',
    'native inbox/control/ack files','private generated shader zip','old launch/debug/probe System properties','old separate world/plain/texture/shader packs'],
  java_started=False,Gradle_started=False,SHA_tests=False,world_copied=False,ZIP_created=False)
 need(len(result['texture_files'])==2,'Retained Full client must contain exactly two selected texture packs')
 write(OUT/'PACK_PLAN_R47.json',result)
 return result
def clean_launch(text):
 for word in text.split():
  if word.startswith('-Dprojectseele.')and not word.startswith('-Dprojectseele.combatBundleDirectory='):
   raise RuntimeError('QA/debug/probe property forbidden in release launch: '+word)
 return text
def cp(source,target):
 need(source.is_file(),'Missing selected source '+str(source));need(not source.is_symlink(),'Symlink source is not a frozen package member '+str(source))
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
def tree(source,target):
 need(source.is_dir(),'Missing source directory '+str(source))
 for p in sorted(source.rglob('*')):
  need(not p.is_symlink(),'Source symlink requires explicit review '+str(p))
  if p.is_file():cp(p,target/p.relative_to(source))
def cold_world(source):
 """Probe the existing session lock without rewriting any source file."""
 lock=source/'session.lock'
 if os.name=='nt'and lock.exists():
  import ctypes
  from ctypes import wintypes
  class OVERLAPPED(ctypes.Structure):
   _fields_=[('Internal',ctypes.c_size_t),('InternalHigh',ctypes.c_size_t),('Offset',wintypes.DWORD),('OffsetHigh',wintypes.DWORD),('hEvent',wintypes.HANDLE)]
  kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.CreateFileW.restype=wintypes.HANDLE
  kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
  h=kernel.CreateFileW(str(lock),0x80000000,7,None,3,0,None)
  need(h not in(None,ctypes.c_void_p(-1).value),'World session lock cannot be opened read-only')
  overlap=OVERLAPPED()
  try:
   kernel.LockFileEx.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(OVERLAPPED)]
   need(kernel.LockFileEx(h,3,0,1,0,ctypes.byref(overlap))!=0,'Selected world is still held by Minecraft; Root must finish/close it')
   kernel.UnlockFileEx.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(OVERLAPPED)]
   kernel.UnlockFileEx(h,0,1,0,ctypes.byref(overlap))
  finally:kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle(h)
def execute(args,p):
 need(args.world_closed,'Root must explicitly attest --world-closed after the actual native session')
 need(args.world.resolve().is_relative_to((ROOT/'artifacts/rebuild_r47').resolve()),'Use Root selected R47 construction/final cold world, not an unrelated save')
 need(args.world.name==WORLD_NAME,'Final R47 world directory must be SEELE_R47_WORLD')
 need((args.world/'level.dat').is_file(),'Final cold world absent')
 cold_world(args.world)
 # Validate all selected essentials before any large copy. Never delete R46,
 # PCL, delivery ZIPs, or an existing generated R47 stage.
 for doc in DOCUMENTS:
  file=args.docs/doc;need(file.is_file(),'Root final documentation still pending: '+str(file))
  text=file.read_text('utf8')
  for marker in ('Root 发布时填写','ROOT_R47_RELEASE_PATHS','FINAL_NATIVE_RESULTS_PENDING','交付草稿'):
   need(marker not in text,'Unfinished release documentation '+str(file)+': '+marker)
 from release_r45_contract import runtime_owner_config
 runtime_owner_config((args.runtime/'config/projectseele-runtime-r45.properties').read_bytes())
 runtime_files=list(args.runtime.rglob('*'));need(any(p.is_file()for p in runtime_files),'Complete R47 runtime absent')
 jar_receipt=validate_jar(args.jar)
 for side in ('server','client'):
  need(not(STAGE/side).exists()or not any((STAGE/side).iterdir()),'Existing R47 '+side+' stage preserved; do not overwrite/delete it')
 for name in p['outputs']:need(not Path(name).exists()and not Path(name+'.part').exists(),'Existing delivery/partial ZIP preserved '+name)
 need(not any(p.is_symlink()for p in (STAGE,OUT,DELIVERY)if p.exists()),'Resolved output root cannot be a symlink')
 receipts=[]
 for side in ('server','client'):
  dest=STAGE/side;dest.mkdir(parents=True,exist_ok=True)
  for dep in p['dependencies'][side]:cp(BASE/side/'mods'/dep,dest/'mods'/dep)
  cp(args.jar,dest/'mods/projectseele-0.1.0-all.jar')
  tree(BASE/side/'config',dest/'config')
  if side=='client':tree(BASE/'server/config',dest/'config')
  # R47 selected runtime/maps replaces legacy map selection rather than
  # resurrecting old high-priority clips through a recursive overlay.
  for folder in ('config','projectseele-local-maps'):tree(args.runtime/folder,dest/folder)
  for doc in DOCUMENTS:cp(args.docs/doc,dest/doc)
  if side=='server':
   tree(BASE/'server/libraries',dest/'libraries')
   for name in ('Start-Server.bat','start-server.sh','user_jvm_args.txt'):
    text=clean_launch((BASE/'server'/name).read_text('utf8'));(dest/name).write_text(text,'utf8')
   need('-Xmx20G'in(dest/'user_jvm_args.txt').read_text('utf8'),'Production server maximum heap20G missing')
   # A distribution does not accept EULA on the recipient's behalf.
   (dest/'eula.txt').write_text('eula=false\n','utf8')
   properties=(BASE/'server/server.properties').read_text('utf8').splitlines()
   properties=[('level-name='+WORLD_NAME)if line.startswith('level-name=')else('motd=Project SEELE Encore R47')if line.startswith('motd=')else line for line in properties]
   (dest/'server.properties').write_text('\n'.join(properties)+'\n','utf8')
   target=dest/WORLD_NAME;files=0;byte_count=0
   for f in sorted(args.world.rglob('*')):
    rel=f.relative_to(args.world)
    if not f.is_file()or f.name=='session.lock'or any(part in EXCLUDED_DIRS for part in rel.parts):continue
    if f.name.startswith('inbox')or f.name.endswith('.ack.jsonl'):continue
    cp(f,target/rel);files+=1;byte_count+=f.stat().st_size
   receipts.append(dict(scope='single_whole_world_copy',files=files,bytes=byte_count,source=str(args.world.resolve()),target=str(target)))
  else:
   tree(BASE/'client/resourcepacks',dest/'resourcepacks')
   cp(BASE/'client/shaderpacks/ComplementaryUnbound_r5.3.zip',dest/'shaderpacks/ComplementaryUnbound_r5.3.zip')
   for name in ('options.txt','COMPLEMENTARY_CREDITS.txt','Install-LocalPrivateVisuals.v12.ps1'):cp(BASE/'client'/name,dest/name)
   cp(OUT/'prepared/private_shader_recipe_v12.json',dest/'private_shader_recipe_v12.json')
   cp(OUT/'prepared/profile_templates'/(PROFILE+'.json'),dest/'profile_templates'/(PROFILE+'.json'))
   cp(OUT/'prepared/Install-R47-From-Local-R46.ps1',dest/'Install-R47-From-Local-R46.ps1')
   tree(BASE/'client/PCL',dest/'PCL')
   # Only a present original shader is named before local installation. The
   # installer creates/selects the R47 private derivative before PCL launch.
   (dest/'config/oculus.properties').write_text('enableShaders=false\nshaderPack=ComplementaryUnbound_r5.3.zip\n','utf8')
   # No vanilla/client jar, access token, generated shader, or personal PCL
   # logs/options are copied from the user's installed profile.
  write(dest/'R47_BATCH.json',dict(batch=BATCH,protocol=PROTOCOL,minecraft='1.20.1',forge='47.4.10',kind=side,pcl_version=PROFILE))
 write(OUT/'STAGE_READY.json',dict(batch=BATCH,jar=jar_receipt,world_copies=1,receipts=receipts))
 finish_staged(args,p,jar_receipt,receipts)

def finish_staged(args,p,jar_receipt=None,receipts=None):
 need(args.world_closed,'Root must close the selected world before finalizing its stage')
 cold_world(args.world)
 if jar_receipt is None:
  jar_receipt=validate_jar(args.jar)
  for side in ('server','client'):
   root=STAGE/side
   need(json.loads((root/'R47_BATCH.json').read_text('utf8'))['batch']==BATCH,'Foreign staged batch')
   need((root/'mods/projectseele-0.1.0-all.jar').stat().st_size==args.jar.stat().st_size,'Selected final jar differs from staged copy')
   for doc in DOCUMENTS:need((root/doc).read_bytes()==(args.docs/doc).read_bytes(),'Frozen staged document changed '+doc)
  # A failed final check may be resumed only over the same whole-world copy.
  # This checks completeness without recopying it or starting a hash suite.
  target=STAGE/'server'/WORLD_NAME;files=0;byte_count=0
  for f in args.world.rglob('*'):
   rel=f.relative_to(args.world)
   if not f.is_file()or f.name=='session.lock'or any(part in EXCLUDED_DIRS for part in rel.parts):continue
   if f.name.startswith('inbox')or f.name.endswith('.ack.jsonl'):continue
   need((target/rel).is_file()and(target/rel).stat().st_size==f.stat().st_size,'Incomplete staged world '+str(rel))
   files+=1;byte_count+=f.stat().st_size
  receipts=[dict(scope='single_whole_world_copy',files=files,bytes=byte_count,source=str(args.world.resolve()),target=str(target),resumed_without_recopy=True)]
 # Same selected source was copied to both. Enforce shared configuration
 # equality and exact common dependency names with no SHA re-read suite.
 for config in (BASE/'server/config').rglob('*'):
  if config.is_file():
   rel=config.relative_to(BASE/'server/config');need((STAGE/'server/config'/rel).read_bytes()==(STAGE/'client/config'/rel).read_bytes(),'Common config differs '+str(rel))
 for item in args.runtime.rglob('*'):
  if item.is_file():
   rel=item.relative_to(args.runtime);need((STAGE/'server'/rel).stat().st_size==(STAGE/'client'/rel).stat().st_size,'Runtime member omitted '+str(rel))
 DELIVERY.mkdir(parents=True,exist_ok=True)
 for side,filename in zip(('server','client'),p['outputs']):
  output=Path(filename);partial=Path(filename+'.part');files=[]
  with zipfile.ZipFile(partial,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True)as archive:
   for f in sorted((STAGE/side).rglob('*')):
    if not f.is_file():continue
    rel=f.relative_to(STAGE/side).as_posix();need(not any(x in EXCLUDED_DIRS for x in Path(rel).parts),'Diagnostic path leaked into release '+rel)
    archive.write(f,rel,compress_type=zipfile.ZIP_STORED if f.suffix.lower()in('.jar','.zip','.ogg','.png')else zipfile.ZIP_DEFLATED)
    files.append(dict(path=rel,bytes=f.stat().st_size))
  need(not output.exists(),'Final ZIP appeared during package creation; preserving it '+str(output))
  partial.replace(output);receipts.append(dict(scope=side,zip=str(output),zip_bytes=output.stat().st_size,files=files))
 write(OUT/'EXECUTION_RECEIPT.json',dict(batch=BATCH,protocol=PROTOCOL,jar=jar_receipt,outputs=receipts,world_copies=1,SHA_tests=False,Java_started=False,
  generated_sources_preserved=True,old_R46_and_user_PCL_untouched=True,user_native_server_acceptance_not_claimed=True))
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 mode=ap.add_mutually_exclusive_group();mode.add_argument('--execute',action='store_true');mode.add_argument('--finish-staged',action='store_true')
 ap.add_argument('--world-closed',action='store_true')
 ap.add_argument('--jar',type=Path,default=ROOT/'build/libs/projectseele-0.1.0-all.jar')
 ap.add_argument('--world',type=Path,default=ROOT/'artifacts/rebuild_r47/construction/SEELE_R47_WORLD')
 ap.add_argument('--runtime',type=Path,default=ROOT/'artifacts/rebuild_r47/runtime')
 ap.add_argument('--docs',type=Path,default=ROOT/'artifacts/rebuild_r47/final_docs')
 ap.add_argument('--shader-recipe',type=Path)
 args=ap.parse_args();p=plan(args)
 if args.execute:execute(args,p);print('Root R47 two-pack execution complete.')
 elif args.finish_staged:finish_staged(args,p);print('Root R47 two-pack stage finalized without a second world copy.')
 else:print('Prepared only: two pack plan/profile/authorized recipe. No stage payload/world copy, ZIP, SHA, Java or PCL write.')
if __name__=='__main__':main()
