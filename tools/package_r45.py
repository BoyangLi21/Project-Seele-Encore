"""R45 release phases. Default plan; never builds Java, downloads or edits sources."""
from __future__ import annotations
from pathlib import Path
import argparse, datetime, hashlib, json, os, re, shutil, sys, uuid, zipfile
from release_r45_contract import *
ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'tools/release_r45_manifest.template.json'

def new_json(path,value):
 path=Path(path)
 if path.exists():raise ContractError('Existing receipt preserved: '+str(path))
 path.parent.mkdir(parents=True,exist_ok=True)
 temporary=path.with_name(path.name+'.partial-'+uuid.uuid4().hex)
 with temporary.open('x',encoding='utf-8') as f:
  json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
 if path.exists():raise ContractError('Concurrent receipt preserved')
 os.rename(temporary,path)

def copy_exact(source,destination,digest):
 source,destination=Path(source),Path(destination)
 if sha(source)!=digest:raise ContractError('Source changed before copy: '+str(source))
 destination.parent.mkdir(parents=True,exist_ok=True)
 with source.open('rb') as a,destination.open('xb') as b:shutil.copyfileobj(a,b,1048576)
 if sha(destination)!=digest:raise ContractError('Copied bytes differ: '+str(destination))

def own_user_files(repo):
 p=Path(repo)/'artifacts/rebuild_r45/baseline.json'
 if not p.is_file():raise ContractError('R45 original15 baseline missing')
 names=read_json(p)['original_user_files']
 if len(names)!=15:raise ContractError('Original15 protection list invalid')
 return {n:sha(Path(repo)/n) for n in names}

def reviews_public(groups):
 # Internal source paths and QA receipt locations stay in the build record.
 return {g:[{'id':r.get('id'),'status':r.get('status'),'evidence_sha256':r.get('evidence_sha256')} for r in rows] for g,rows in groups.items()}

def candidate_public_status(manifest,stage):
 policy=native_check_policy(manifest)
 return {'schema':'projectseele.r45.candidate-public.v1','state':'INSTALLATION_CANDIDATE_NOT_RELEASE_ACCEPTED',
  'delivery_scope':policy['scope'],'deferred_native_checks':manifest.get('deferred_native_checks',[]),'stage_digest':stage['stage_digest'],
  'reviews':reviews_public(manifest['reviews']),'checks':{k:'DEFERRED' if k in policy['deferred'] else 'UNVERIFIED' for k in sorted(policy['all'])},
  'native_executed':False,'user_acceptance':False,'release_accepted':False,'not_for_complete_story_claim':True}

class Pipeline:
 def __init__(self,repo,manifest_path):
  self.repo=Path(repo).resolve();self.path=Path(manifest_path).resolve();self.m=read_json(self.path)
  self.output=output_path(self.repo,self.m.get('output_directory')) if self.m.get('output_directory') else None
 def plan(self):
  v=Validator(self.repo,self.m);result=v.validate()
  if not (self.repo/'artifacts/rebuild_r45/baseline.json').is_file():result['issues'].append({'code':'ORIGINAL15_BASELINE','message':'Protected user-work list missing'})
  result['can_freeze']=not result['issues'];return result,v
 def freeze(self):
  result,v=self.plan()
  if result['issues']:raise ContractError(json.dumps(result,ensure_ascii=False))
  review=receipt(self.m.get('source_review_receipt'),'root reviewed source')
  if review.get('root_reviewed') is not True or review.get('input_digest')!=result['input_digest']:raise ContractError('Root source review does not bind these exact inputs')
  before=own_user_files(self.repo)
  v.inputs.append({'source':str(Path(self.m['source_review_receipt']['source']).resolve()),'sha256':self.m['source_review_receipt']['sha256'],'target':'inputs/receipts/root_source_review.json'})
  if self.output.exists():raise ContractError('Existing output preserved; choose a new epoch output')
  self.output.mkdir();folder=self.output/'frozen';folder.mkdir();copied={};index=[]
  for row in v.inputs:
   h=row['sha256'];dest=folder/'blobs'/h
   if h not in copied:copy_exact(row['source'],dest,h);copied[h]=True
   index.append({'target':row['target'],'sha256':h,'blob':'frozen/blobs/'+h,'source':row['source']})
  if own_user_files(self.repo)!=before:raise ContractError('Original15 changed during freeze; never restore or overwrite')
  new_json(folder/'manifest.json',self.m)
  frozen={'schema':'projectseele.r45.frozen.v1','input_digest':result['input_digest'],'manifest_sha256':sha(folder/'manifest.json'),
   'inputs':index,'original_user_files':before,'source_review_sha256':self.m['source_review_receipt']['sha256'],
   'state':'SOURCE_FROZEN_NOT_STAGED_NOT_NATIVE_NOT_RELEASED','native_executed':False,'released':False}
  new_json(self.output/'FROZEN.json',frozen);return frozen
 def frozen(self,live=True):
  if self.output is None:raise ContractError('No explicit output_directory')
  f=read_json(self.output/'FROZEN.json')
  stored=self.output/'frozen/manifest.json'
  if sha(stored)!=f['manifest_sha256'] or input_digest(read_json(stored))!=f['input_digest'] or input_digest(self.m)!=f['input_digest']:raise ContractError('Frozen manifest binding changed')
  if own_user_files(self.repo)!=f['original_user_files']:raise ContractError('Original15 changed after freeze; preserve and request a new reviewed epoch')
  checked=set()
  for row in f['inputs']:
   relative(row['blob']);p=self.output/row['blob']
   if row['blob'] not in checked:
    if sha(p)!=row['sha256']:raise ContractError('Frozen input changed')
    checked.add(row['blob'])
  if live:
   sources={row['source']:row['sha256'] for row in f['inputs']}
   for name,digest in sources.items():
    if not Path(name).is_file() or sha(name)!=digest:raise ContractError('Reviewed live source changed; freeze a new epoch: '+name)
  return f
 def stage(self):
  f=self.frozen();stage=self.output/'stage'
  if stage.exists():raise ContractError('Existing stage preserved; no recover/delete/overwrite mode')
  stage.mkdir()
  for kind in KINDS.values():(stage/kind).mkdir()
  seen=set()
  for row in f['inputs']:
   target=row['target']
   if target.startswith('inputs/'):continue
   relative(target)
   if target.lower() in seen:continue
   seen.add(target.lower());copy_exact(self.output/row['blob'],stage/target,row['sha256'])
  def text(kind,name,value):
   relative(name);portable_text(value.encode(),name)
   p=stage/kind/name;p.parent.mkdir(parents=True,exist_ok=True)
   with p.open('x',encoding='utf-8',newline='') as out:out.write(value)
  for kind in ('client','client_plain'):
   plain=kind=='client_plain'
   texture_names=[r['destination'].removeprefix('resourcepacks/') for r in self.m['textures']['files'] if r['destination'].startswith('resourcepacks/') and r['destination'].endswith('.zip')]
   settings=dict(self.m.get('client_options',{}))
   if any(':' in str(k) or '\n' in str(k)+str(v) for k,v in settings.items()):raise ContractError('Malformed client options')
   settings.update(resourcePacks=json.dumps(['vanilla','mod_resources']+([] if plain else ['file/'+n for n in texture_names])),incompatibleResourcePacks='[]',lang='zh_cn')
   text(kind,'options.txt',''.join(str(k)+':'+str(v)+'\n' for k,v in sorted(settings.items())))
   text(kind,'PCL/Setup.ini','VersionArgumentIndieV2:True\n')
  text('server','user_jvm_args.txt','\n'.join(check_memory(self.m['server_jvm_args']))+'\n')
  for kind in ('client','shaders'):
   text(kind,'config/oculus.properties','enableShaders=false\nshaderPack=ComplementaryUnbound_r5.3.zip\n')
   text(kind,'COMPLEMENTARY_CREDITS.txt',self.m['shaders']['credits_text']+'\n')
  # Generated payload metadata contains hashes and typed review states, never internal source paths.
  batch={'schema':'projectseele.r45.batch.v1','batch_id':self.m['batch_id'],'protocol':PROTOCOL,'minecraft':'1.20.1','forge':'47.4.10',
   'input_digest':f['input_digest'],'delivery_scope':self.m['delivery_scope'],'deferred_native_checks':self.m.get('deferred_native_checks',[]),'project_mod_sha256':self.m['build']['project_jar']['sha256'],
   'world_uuid':self.m['world']['world_uuid'],'world_seed':self.m['world']['seed'],'world_name':self.m['world']['world_name'],
   'reviews':reviews_public(self.m['reviews']),'state':'STAGED_CANDIDATE_NOT_NATIVE_NOT_RELEASED','native_executed':False,'released':False,
   'shader_enabled_by_default':False,'shader_local_personal_adaptation_only':True}
  for kind in KINDS.values():new_json(stage/kind/'R45_BATCH.json',batch)
  hashes={p.relative_to(stage).as_posix():sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}
  complete={'schema':'projectseele.r45.stage.v1','state':'STAGED_REQUIRES_ACTUAL_ROOT_ACCEPTANCE','input_digest':f['input_digest'],
   'frozen_receipt_sha256':sha(self.output/'FROZEN.json'),'files':hashes,'stage_digest':payload_hash(hashes),'native_executed':False,'released':False}
  self.check_stage(complete,stage)
  new_json(self.output/'STAGE_COMPLETE.json',complete);return complete
 def check_stage(self,complete=None,stage=None):
  f=self.frozen();stage=stage or self.output/'stage';c=complete or read_json(self.output/'STAGE_COMPLETE.json')
  if c['input_digest']!=f['input_digest'] or payload_hash(c['files'])!=c['stage_digest']:raise ContractError('Stage receipt not bound to frozen input')
  actual={p.relative_to(stage).as_posix():sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}
  if actual!=c['files']:raise ContractError('Stage payload changed/unlisted; native testing must use a new installed stage copy')
  for rel in actual:
   p=stage/rel
   if p.suffix.lower() in TEXT_SUFFIXES:
    world_prefix='server/'+self.m['world']['world_name']+'/'
    if rel.startswith('world/'):portable_world_text(p.read_bytes(),rel,self.m['world'],rel.removeprefix('world/'))
    elif rel.startswith(world_prefix):portable_world_text(p.read_bytes(),rel,self.m['world'],rel.removeprefix(world_prefix))
    else:portable_text(p.read_bytes(),rel)
  project=self.m['build']['project_jar'];world=self.m['world'];wname=world['world_name']
  for kind in ('client','client_plain','server'):
   names={p.name for p in (stage/kind/'mods').glob('*.jar')}
   expected=set(COMMON)|{Path(project['source']).name}
   if kind!='server':expected|=set(CLIENT)
   if kind=='client':expected|=set(FULL)
   if names!=expected:raise ContractError('Stage unknown/missing mod: '+kind)
   if sha(stage/kind/'mods'/Path(project['source']).name)!=project['sha256'] or sha(stage/kind/'mods/create-1.20.1-6.0.8.jar')!=CREATE_SHA:raise ContractError('Production jars changed')
   for row in self.m['runtime_files']:
    if sha(stage/kind/row['destination'])!=row['sha256']:raise ContractError('Required runtime resource mismatch')
  plain=stage/'client_plain'
  if (plain/'resourcepacks').exists() or (plain/'shaderpacks').exists() or list(plain.glob('Install-LocalPrivateVisuals*')):raise ContractError('Plain contains optional visual payload')
  check_memory((stage/'server/user_jvm_args.txt').read_text('utf-8').splitlines())
  properties=(stage/'server/server.properties').read_text('utf-8-sig')
  if not re.search(r'^level-name='+re.escape(wname)+r'\s*$',properties,re.M):raise ContractError('Server world name not bound')
  for row in world['files']:
   for base in (stage/'world',stage/'server'/wname):
    if sha(base/relative(row['relative']))!=row['sha256']:raise ContractError('Complete world bytes were not preserved')
  for kind in ('client','shaders'):
   if [p.name for p in (stage/kind/'shaderpacks').glob('*.zip')]!=['ComplementaryUnbound_r5.3.zip']:raise ContractError('Prebuilt modified shader forbidden')
   if sha(stage/kind/'shaderpacks/ComplementaryUnbound_r5.3.zip')!=SHADER_SHA:raise ContractError('Original shader bytes changed')
  return c
 def acceptance(self,path):
  c=self.check_stage();a=read_json(path)
  if a.get('schema')!='projectseele.r45.stage-acceptance.v1' or a.get('native_executed') is not True or a.get('stage_digest')!=c['stage_digest']:raise ContractError('Actual acceptance must bind exact staged payload')
  if a.get('tested_origin')!='INSTALLED_STAGE_COPY' or a.get('tested_payload_digest')!=c['stage_digest']:raise ContractError('Acceptance must use a real installation copy made from this stage')
  if a.get('project_mod_sha256')!=self.m['build']['project_jar']['sha256'] or a.get('protocol')!=PROTOCOL:raise ContractError('Acceptance jar/protocol differs')
  if a.get('synthetic_fixture') is True or a.get('scope')!='ACTUAL_NATIVE_STAGE_INSTALL':raise ContractError('Synthetic/state-only scope cannot qualify actual native stage acceptance')
  if a.get('fake_player_used') is not False:raise ContractError('FakePlayer cannot substitute real clients')
  ids=a.get('real_client_uuids',[])
  if len(ids)!=2 or len(set(ids))!=2:raise ContractError('Two distinct real client UUIDs required')
  for value in ids:uuid.UUID(value)
  if a.get('server_jvm_args')!=['-Xms2G','-Xmx20G']:raise ContractError('Actual 20G server measurement missing')
  checks=a.get('checks',{})
  policy=native_check_policy(self.m)
  if a.get('delivery_scope')!=policy['scope']:raise ContractError('Actual acceptance delivery scope differs')
  if set(checks)!=policy['all'] or any(checks.get(k)!='PASS' for k in policy['required']) or any(checks.get(k)!='DEFERRED' for k in policy['deferred']):raise ContractError('Required actual native checks unresolved/failed, or deferred campaign falsely counted passed')
  for key in ('ACTION_TV_ART','REALISTIC_TEXTURES'):
   if (a.get('user_acceptance') or {}).get(key) is not True:raise ContractError('User visual acceptance missing: '+key)
  if set(a.get('reviews',{}))!=set(REVIEW_GROUPS):raise ContractError('Acceptance must preserve six separate review groups')
  for group,rows in a['reviews'].items():
   if not isinstance(rows,list) or len({row.get('id') for row in rows if isinstance(row,dict)})!=len(rows) or any(not isinstance(row,dict) or row.get('status') not in REVIEW_STATES for row in rows):raise ContractError('Malformed actual review state: '+group)
  measured={row.get('id'):row.get('status') for row in a['reviews']['measured']}
  users={row.get('id'):row.get('status') for row in a['reviews']['user']}
  deferred={row.get('id'):row for row in a['reviews']['unverified'] if row.get('status')=='DEFERRED'}
  if set(deferred)!=policy['deferred'] or any(not deferred[k].get('reason') or deferred[k].get('user_deferred') is not True or measured.get(k)=='PASS' for k in policy['deferred']):raise ContractError('Explicit deferred scope must remain visible and cannot be counted measured PASS')
  if any(measured.get(key)!='PASS' for key in policy['required']) or any(users.get(key)!='PASS' for key in ('ACTION_TV_ART','REALISTIC_TEXTURES')):raise ContractError('Actual measured/user groups do not match retained checks')
  evidence=a.get('evidence')
  if not isinstance(evidence,list) or not evidence:raise ContractError('Actual immutable evidence files required')
  for row in evidence:
   if not Path(row['source']).is_file() or sha(row['source'])!=row['sha256']:raise ContractError('Actual acceptance evidence missing/changed')
  return a,c
 def record_acceptance(self,path):
  a,c=self.acceptance(path)
  proof={'schema':'projectseele.r45.accepted.v1','stage_digest':c['stage_digest'],'source_receipt_sha256':sha(path),
   'source_receipt':str(Path(path).resolve()),'reviews':a['reviews'],'native_executed':True,'released':False}
  new_json(self.output/'ACCEPTED.json',proof);return proof
 def seal(self,candidate=False):
  if candidate:
   c=self.check_stage();a=None
  else:
   accepted=read_json(self.output/'ACCEPTED.json')
   p=Path(accepted['source_receipt'])
   if sha(p)!=accepted['source_receipt_sha256']:raise ContractError('Actual acceptance receipt changed')
   a,c=self.acceptance(p)
   if accepted['stage_digest']!=c['stage_digest']:raise ContractError('Accepted stage changed')
  receipt_name='CANDIDATE_RELEASE.json' if candidate else 'RELEASE.json'
  if (self.output/receipt_name).exists():raise ContractError('Existing archive receipt preserved')
  destinations=[self.output/(self.m['batch_id']+('_CANDIDATE' if candidate else '')+'_'+label+'.zip') for label in KINDS]
  if any(p.exists() for p in destinations):raise ContractError('Existing ZIP preserved; no overwrite')
  stage=self.output/'stage';wname=self.m['world']['world_name'];archives=[]
  # The original staged bytes stay immutable; final acceptance metadata is added in archives.
  public_acceptance=candidate_public_status(self.m,c) if candidate else {'schema':'projectseele.r45.acceptance-public.v1','stage_digest':c['stage_digest'],
   'delivery_scope':a['delivery_scope'],'deferred_native_checks':self.m.get('deferred_native_checks',[]),'reviews':reviews_public(a['reviews']),'checks':a['checks'],'native_executed':True,'user_acceptance':a['user_acceptance'],
   'evidence_sha256':[row['sha256'] for row in a['evidence']]}
  status_name='R45_CANDIDATE_STATUS.json' if candidate else 'R45_ACCEPTANCE.json'
  for (label,kind),target in zip(KINDS.items(),destinations):
   expected={};client=kind in ('client','client_plain')
   with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
    def add(source,name):
     relative(name)
     if name.lower() in {s.lower() for s in expected}:raise ContractError('Duplicate ZIP member')
     z.write(source,name);expected[name]=sha(source)
    prefix='overrides/' if client else ''
    for file in sorted((stage/kind).rglob('*')):
     if file.is_file():add(file,prefix+file.relative_to(stage/kind).as_posix())
    if client:
     for file in sorted((stage/'world').rglob('*')):
      if file.is_file():add(file,'overrides/saves/'+wname+'/'+file.relative_to(stage/'world').as_posix())
     manifest={'minecraft':{'version':'1.20.1','modLoaders':[{'id':'forge-47.4.10','primary':True}]},'manifestType':'minecraftModpack','manifestVersion':1,
       'name':self.m['batch_id']+('_Plain' if kind=='client_plain' else ''),'version':self.m['batch_id'],'author':'Project SEELE: Encore','files':[],'overrides':'overrides'}
     data=json.dumps(manifest,ensure_ascii=False,indent=2).encode();z.writestr('manifest.json',data);expected['manifest.json']=hashlib.sha256(data).hexdigest()
    data=json.dumps(public_acceptance,ensure_ascii=False,indent=2).encode();z.writestr(prefix+status_name,data);expected[prefix+status_name]=hashlib.sha256(data).hexdigest()
   with zipfile.ZipFile(target) as z:
    if z.testzip() is not None or set(z.namelist())!=set(expected):raise ContractError('Archive CRC/member set mismatch')
    for name,digest in expected.items():
     h=hashlib.sha256()
     with z.open(name) as stream:
      for b in iter(lambda:stream.read(1048576),b''):h.update(b)
     if h.hexdigest()!=digest:raise ContractError('ZIP member SHA readback differs')
   archives.append({'filename':target.name,'sha256':sha(target),'bytes':target.stat().st_size,'crc_verified':True,'member_sha_verified':len(expected)})
  result={'schema':'projectseele.r45.release.v1','batch_id':self.m['batch_id'],'protocol':PROTOCOL,'stage_digest':c['stage_digest'],
   'accepted_receipt_sha256':None if candidate else sha(self.output/'ACCEPTED.json'),'archives':archives,'reviews':public_acceptance['reviews'],
   'state':'INSTALLATION_CANDIDATE_NOT_RELEASE_ACCEPTED' if candidate else 'ACTUAL_RELEASE_ACCEPTED',
   'native_executed':not candidate,'release_accepted':not candidate,'sealed_six_archives':True,'uploaded_or_pushed':False}
  new_json(self.output/receipt_name,result);return result

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',nargs='?',default='plan',choices=('plan','freeze','stage','verify','candidate','accept','seal'))
 ap.add_argument('--manifest',type=Path,default=DEFAULT);ap.add_argument('--acceptance',type=Path);ap.add_argument('--report',type=Path)
 args=ap.parse_args()
 try:
  pipeline=Pipeline(ROOT,args.manifest)
  if args.action=='plan':result,_=pipeline.plan()
  elif args.action=='freeze':result=pipeline.freeze()
  elif args.action=='stage':result=pipeline.stage()
  elif args.action=='verify':result=pipeline.check_stage()
  elif args.action=='candidate':result=pipeline.seal(candidate=True)
  elif args.action=='accept':
   if not args.acceptance:raise ContractError('--acceptance actual root receipt required')
   result=pipeline.record_acceptance(args.acceptance)
  else:result=pipeline.seal()
  if args.report:
   if not args.report.resolve().is_relative_to(ROOT/'artifacts/rebuild_r45/release_pipeline_sol_v13'):raise ContractError('Plan report must stay in the owned release_pipeline_sol_v13 directory, outside all worlds')
   new_json(args.report,result)
  print(json.dumps(result,ensure_ascii=False,indent=2));return 2 if result.get('issues') else 0
 except (ValueError,OSError,KeyError,zipfile.BadZipFile) as e:
  print(json.dumps({'action':args.action,'blocked':True,'error':str(e),'success':False},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
