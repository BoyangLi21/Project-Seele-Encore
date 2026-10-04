"""Fill concrete R45 inputs after Root's real build; no Java, stage, ZIP, or world writes."""
from pathlib import Path
import argparse,hashlib,json,zipfile,uuid
import nbtlib
from release_r45_contract import COMMON,CLIENT,FULL,CREATE_SHA,PROTOCOL,sha,class_protocol,input_digest

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,o):
 p=Path(p)
 if p.exists():raise ValueError('Existing input/receipt preserved '+str(p))
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(o,ensure_ascii=False,indent=2)+'\n').encode())
def blob(p):return {'source':str(Path(p).resolve()),'sha256':sha(p)}
def payload_blob(row):
 item=dict(row);actual=blob(row['source'])
 if row.get('sha256') and row['sha256']!=actual['sha256']:raise ValueError('Selected payload bytes changed '+row['source'])
 item.update(actual);return item
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['jar','build-log','world','world-receipt','payload-selection','output']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--asset-policy',type=Path);p.add_argument('--final-assets',type=Path,required=True)
 p.add_argument('--root-reviewed',action='store_true',help='Root explicitly reviewed these selected source inputs; never grants native/user acceptance')
 p.add_argument('--world-uuid');p.add_argument('--batch',required=True);p.add_argument('--stage-output',type=Path,required=True)
 p.add_argument('--mod-root',type=Path,default=Path('C:/Users/liboy/AppData/Roaming/.minecraft/versions/Project SEELE R44 Stage/mods'))
 p.add_argument('--forge-root',type=Path,default=ROOT/'.Codex/server-pack-cache/runtime-r25')
 p.add_argument('--create',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/create-1.20.1-6.0.8.jar')
 a=p.parse_args();m=read(ROOT/'tools/release_r45_manifest.template.json');payload=read(a.payload_selection)
 if a.output.exists():raise ValueError('Choose a new manifest input file')
 with zipfile.ZipFile(a.jar) as z:
  if class_protocol(z.read('com/projectseele/network/SeeleNetwork.class'))!=PROTOCOL:raise ValueError('Actual final jar protocol differs')
  assets={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith(('assets/','data/')) and not n.endswith('/')}
 frozen_assets=read(a.final_assets/'ASSET_FROZEN.json')
 if frozen_assets.get('schema')!='projectseele.final-assets-frozen.r45.v1' or assets!=frozen_assets.get('files'):raise ValueError('Actual jar assets differ from Root exact selected asset overlay')
 log=a.build_log.read_text(encoding='utf-8-sig',errors='replace')
 if 'BUILD SUCCESSFUL' not in log or 'reobfJarJar' not in log:raise ValueError('Actual production reobfJarJar build log required')
 evidence=a.output.parent/(a.batch+'_input_receipts');evidence.mkdir(parents=True,exist_ok=False)
 production={'scope':'ACTUAL_PRODUCTION_BUILD','build_executed':True,'production_reobfuscated':True,'project_mod_sha256':sha(a.jar),'protocol':PROTOCOL,'build_log_sha256':sha(a.build_log)}
 write(evidence/'production.json',production)
 m.update(batch_id=a.batch,output_directory=str(a.stage_output.resolve()),protocol=PROTOCOL)
 m['build']={'project_jar':blob(a.jar),'production_receipt':blob(evidence/'production.json'),'embedded_assets':assets}
 for key,names in [('common_mods',COMMON),('client_mods',CLIENT),('full_client_mods',FULL)]:
  rows=[]
  for name in sorted(names):
   source=a.create if name=='create-1.20.1-6.0.8.jar' else a.mod_root/name
   if not source.is_file():raise ValueError('Exact existing production dependency missing '+str(source))
   row=blob(source);row['filename']=name;rows.append(row)
  m[key]=rows
 if sha(a.create)!=CREATE_SHA:raise ValueError('Create must be original universal, not dev slim/remapped')
 for key in ['runtime_files','client_files','server_files','docs_files']:
  m[key]=[]
  for row in payload.get(key,[]):
   m[key].append(payload_blob(row))
 libraries={}
 for source in sorted((a.forge_root/'libraries').rglob('*')):
  if source.is_file():
   destination='libraries/'+source.relative_to(a.forge_root/'libraries').as_posix();digest=sha(source);libraries[destination]=digest;m['server_files'].append({'source':str(source.resolve()),'sha256':digest,'destination':destination})
 if not libraries:raise ValueError('Actual existing Forge production libraries missing')
 write(evidence/'forge_runtime.json',{'forge':'47.4.10','minecraft':'1.20.1','production_installed':True,'files':libraries,'scope':'EXISTING_ROOT_FORGE_RUNTIME_BYTE_READBACK_NOT_SERVER_NATIVE'})
 m['forge_runtime_receipt']=blob(evidence/'forge_runtime.json')
 composition=read(a.world_receipt);inventory=composition.get('full_after_inventory')
 if not isinstance(inventory,dict) or Path(composition.get('world','')).resolve()!=a.world.resolve():raise ValueError('Actual world receipt/inventory must bind selected source')
 data=nbtlib.load(a.world/'level.dat')['Data'];seed=int(data['WorldGenSettings']['seed'])
 world_uuid=a.world_uuid
 if world_uuid:uuid.UUID(world_uuid)
 else:
  if any('uuid' in str(k).lower() for k in data) or (a.world/'uid.dat').exists():raise ValueError('Existing world UUID requires explicit original value')
 preservation=composition.get('all_actor_player_task_MTR_and_unrelated_files_byte_preserved') is True
 if not preservation or composition.get('world_written_by_root') is not True or not str(composition.get('phase','')).startswith('COMPLETE'):raise ValueError('Actual Root complete static composition and original progress preservation required')
 world_proof={'role':'DELIVERY_SOURCE','world':str(a.world.resolve()),'world_uuid':world_uuid,'world_identity_kind':'GLOBAL_UUID' if world_uuid else 'VANILLA_NO_GLOBAL_UUID','seed':seed,'source_progress_preserved':preservation,'original_identities_preserved':preservation,'required_components_installed':True,'component_scope':'Only Root selected final static composition; postponed campaign supply not installed or claimed','actual_composition_receipt_sha256':sha(a.world_receipt),'scope':'ROOT_ACTUAL_STATIC_COMPOSITION_NOT_USER_ART_OR_NATIVE'}
 write(evidence/'composition.json',world_proof)
 omitted=payload.get('world_omissions',[]);omitted_names={r['relative'] for r in omitted}
 if 'session.lock' in inventory and 'session.lock' not in omitted_names:omitted.append({'relative':'session.lock','reason':'Source process lock is not world progress; never installed'});omitted_names.add('session.lock')
 m['world']={'role':'DELIVERY_SOURCE','source_directory':str(a.world.resolve()),'world_name':payload['world_name'],'world_uuid':world_uuid,'world_identity_kind':'GLOBAL_UUID' if world_uuid else 'VANILLA_NO_GLOBAL_UUID','seed':seed,'writer_closed':True,'composition_receipt':blob(evidence/'composition.json'),'files':[{'relative':name,'sha256':digest} for name,digest in inventory.items() if name not in omitted_names],'omissions':omitted}
 m['world']['legacy_provenance']=payload.get('legacy_world_provenance',[])
 if a.asset_policy:m['asset_policy_receipt']=blob(a.asset_policy)
 else:
  policy=payload.get('asset_policy_selection',{})
  if policy.get('gantry_track')!='draft12' or policy.get('experimental_thin_beams_included') is not False:raise ValueError('Explicit Root formal asset policy selection required')
  members=policy.get('gantry_asset_members',[])
  if not members or any(n not in assets for n in members):raise ValueError('Actual selected gantry asset members missing')
  write(evidence/'asset_policy.json',{'gantry_track':'draft12','experimental_thin_beams_included':False,'project_mod_sha256':sha(a.jar),'gantry_asset_sha256':{n:assets[n] for n in members},'selected_asset_manifest_sha256':sha(a.final_assets/'ASSET_FROZEN.json'),'scope':'ROOT_SELECTED_FROZEN_ASSET_BYTES_NOT_ART_OR_NATIVE_ACCEPTANCE'})
  m['asset_policy_receipt']=blob(evidence/'asset_policy.json')
 for key in ['textures','shaders','client_options','server_jvm_args']:
  if key in payload:m[key]=payload[key]
 m['textures']['license_receipt']=payload_blob(m['textures']['license_receipt'])
 m['textures']['files']=[payload_blob(row) for row in m['textures']['files']]
 m['shaders']['original_zip']=payload_blob(m['shaders']['original_zip'])
 m['shaders']['adapter_files']=[payload_blob(row) for row in m['shaders']['adapter_files']]
 # All remaining validation belongs to user; this is a candidate build input, not acceptance.
 m['reviews']['user']=[{'id':name,'status':'UNVERIFIED','scope':'User review after installation'} for name in ['ACTION_TV_ART','REALISTIC_TEXTURES']]
 m['source_review_receipt']=None
 if a.root_reviewed:
  write(evidence/'root_source_review.json',{'root_reviewed':True,'input_digest':input_digest(m),'scope':'ROOT_EXPLICIT_SOURCE_SELECTION_REVIEW_NOT_NATIVE_OR_USER_ACCEPTANCE'})
  m['source_review_receipt']=blob(evidence/'root_source_review.json')
 write(a.output,m)
 print(json.dumps({'manifest':str(a.output.resolve()),'sha256':sha(a.output),'embedded_assets':len(assets),'world_files':len(inventory),'state':'FILLED_REQUIRES_ROOT_SOURCE_REVIEW_THEN_FREEZE_STAGE_CANDIDATE','stage_or_package_or_Java':False},indent=2))
if __name__=='__main__':main()
