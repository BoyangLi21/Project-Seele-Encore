"""Strict R45 input contract; no Java, download, build or world mutation."""
from __future__ import annotations
from pathlib import Path, PurePosixPath
import hashlib, io, json, re, struct, tomllib, zipfile
from release_r45_resource_closure import check_resource_closure, check_optional_texture_pack

SCHEMA='projectseele.release-r45.manifest.v1'
PROTOCOL='54'
CREATE_SHA='6fbb910c367dbce8e4fc7e5bf64b6edd4de980906ed00af8e47e4af843c0d9b0'
SHADER_SHA='66061b3c5b4843e31bc9a7562a7ac697a51bb77c73defc7071f996b783efacce'
LICENSE_SHA='1e1f730abd9c25ad4d0ba301453d37547d17102a3cfc628de794d5b08e278a20'
COMMON=frozenset('MTR-forge-4.0.5+1.20.1.jar Patchouli-1.20.1-85-FORGE.jar another-furniture-1.20.1-3.0.4.jar ars-nouveau-4.12.7.jar curios-forge-1.20.1-5.14.1.jar ferritecore-6.0.1-forge.jar geckolib-forge-1.20.1-4.8.4.jar grandpianomod-1.0.0.jar kotlinforforge-4.12.0-all.jar mcw-doors-1.1.5-mc1.20.1forge.jar modernfix-forge-5.27.83+mc1.20.1.jar movingelevators-1.4.12-forge-mc1.20.1.jar superbwarfare-0.8.9.1-hotfix-mc1.20.1-993063bed-all.jar supermartijn642configlib-1.1.8-forge-mc1.20.jar supermartijn642corelib-1.1.24-forge-mc1.20.1.jar create-1.20.1-6.0.8.jar'.split())
CLIENT=frozenset('embeddium-0.3.31+mc1.20.1.jar xaerominimap-forge-1.20.1-26.5.0.jar xaeroworldmap-forge-1.20.1-1.46.0.jar'.split())
FULL=frozenset(['oculus-mc1.20.1-1.8.0.jar'])
KINDS={'Client':'client','Client_Plain':'client_plain','Server':'server','World':'world','Textures':'textures','Shaders':'shaders'}
REVIEW_GROUPS=('functional','measured','inherited','visual_self','user','unverified')
NATIVE_CHECKS=frozenset(['NPC_ORIGINAL_EVA','MID_MISSION_REINFORCEMENT','CANCEL_NO_AUTO_LAUNCH','PHYSICAL_EQUIPMENT_CUSTODY','VICTORY_RETURN_ARCHIVE','COLD_RESTART','TWO_REAL_CLIENTS','SERVER_20G_PERFORMANCE','CITY_BIDIRECTIONAL_PERFORMANCE','FULL_PLAIN_VISUAL_RESOURCES','SCRIPT_OFFLINE_INSTALL','WORLD_IDENTITIES_AND_PROGRESS'])
DEFERRED_CAMPAIGN_CHECKS=frozenset(['NPC_ORIGINAL_EVA','MID_MISSION_REINFORCEMENT','PHYSICAL_EQUIPMENT_CUSTODY','VICTORY_RETURN_ARCHIVE'])
CORE_OPERATION_CHECKS=frozenset(['CORE_EVA_PLAYER_CONTROLS','CORE_RECOVERY_EQUIPMENT_RETURN','FIRST_PERSON_OPTICS','AT_FIELD_CONTACT','AUDIO_LIFECYCLE','REAL_AI_COMBAT'])
REVIEW_STATES=('PASS','FAIL','PENDING','UNVERIFIED','INHERITED','DEFERRED')

def native_check_policy(manifest):
 scope=manifest.get('delivery_scope')
 if scope not in ('CORE_EVA_OPERATIONS_R45','FULL_CAMPAIGN_R45'):raise ContractError('Explicit current delivery_scope required')
 rows=manifest.get('deferred_native_checks',[])
 if not isinstance(rows,list) or any(not isinstance(r,dict) or r.get('user_deferred') is not True or not r.get('reason') for r in rows):raise ContractError('Deferred checks require explicit user scope and reasons')
 ids={r.get('id') for r in rows}
 if len(ids)!=len(rows) or (ids!=DEFERRED_CAMPAIGN_CHECKS if scope=='CORE_EVA_OPERATIONS_R45' else bool(ids)):raise ContractError('Only the four explicitly postponed campaign-chain checks may be deferred in CORE scope; FULL defers none')
 return {'scope':scope,'required':(NATIVE_CHECKS|CORE_OPERATION_CHECKS)-ids,'deferred':ids,'all':NATIVE_CHECKS|CORE_OPERATION_CHECKS}

TEXT_SUFFIXES={'.json','.toml','.properties','.txt','.md','.ps1','.bat','.sh','.cfg','.ini','.xml'}
ABS_PATH=re.compile(r'\b[A-Za-z]:[\\/]|(?:"|\s)/(?:home|Users|mnt|tmp)/|"\\\\\\\\')
PRIVATE_FLAGS=re.compile(r'-Dprojectseele\.[^=\s]*(?:lease|author|review|witness|probe|fixture|capture|acceptance|plan)[^=\s]*=',re.I)
PRIVATE_KEY=re.compile(r'^(?:QA[_-]?ONLY|qa_lease|lease_id|lease_uuid|qa_plan|acceptance_plan|developerCommands)$',re.I)

class ContractError(ValueError):pass

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def payload_hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def batch_series(m):
 match=re.search(r'(?:^|_)(R4[56])(?:_|$)',str(m.get('batch_id','')))
 if not match:raise ContractError('Current batch series missing')
 return match.group(1)

def input_digest(m):return payload_hash({k:v for k,v in m.items() if k not in ('source_review_receipt','acceptance_receipts')})
def read_json(path):return json.loads(Path(path).read_text('utf-8-sig'))

def relative(value):
 if not isinstance(value,str) or not value or '\\' in value or ':' in value or value.startswith('/'):
  raise ContractError(f'Unsafe relative path: {value!r}')
 p=PurePosixPath(value)
 if any(q in ('','..','.') for q in value.split('/')):raise ContractError(f'Unsafe relative path: {value}')
 if any(q.rstrip(' .')!=q or q.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]} for q in p.parts):raise ContractError(f'Unsafe Windows path: {value}')
 return p.as_posix()

def output_path(repo,value):
 if not value or not Path(value).is_absolute():raise ContractError('output_directory must be explicit and absolute')
 p=Path(value);actual=p.resolve();root=Path(repo).resolve()/'artifacts'
 if actual.parent!=root or not re.fullmatch(r'server-ready-r4[56]-[a-zA-Z0-9_-]+',p.name):raise ContractError('Output must be a new artifacts/server-ready-r45/r46-<epoch> directory')
 for q in [p,*p.parents]:
  if q.exists() and (q.is_symlink() or getattr(q,'is_junction',lambda:False)()):raise ContractError('Output reparse point forbidden')
  if q==Path(repo):break
 return actual

def portable_text(data,label):
 text=data.decode('utf-8-sig')
 if ABS_PATH.search(text):raise ContractError(f'Development absolute path in deliverable: {label}')
 if PRIVATE_FLAGS.search(text):raise ContractError(f'QA/author/lease JVM flag in deliverable: {label}')
 if label.lower().endswith('.json'):
  obj=json.loads(text)
  def walk(x):
   if isinstance(x,dict):
    for k,v in x.items():
     if PRIVATE_KEY.match(k) and v not in (False,None,'',[],{}):raise ContractError(f'QA/lease JSON field in deliverable: {label}:{k}')
     if k=='role' and v=='QA_ONLY':raise ContractError(f'QA_ONLY deliverable: {label}')
     walk(v)
   elif isinstance(x,list):
    for v in x:walk(v)
  walk(obj)
 return text

def portable_world_text(data,label,world,relative_name):
 # Preserve original save bytes. Mask only Root-reviewed, exact-SHA historical
 # fields for this check; launch/config/resource paths never use this function.
 rows=[r for r in world.get('legacy_provenance',[]) if r.get('relative')==relative_name]
 if not rows:return portable_text(data,label)
 if len(rows)!=1:raise ContractError('Duplicate legacy provenance allowance')
 row=rows[0]
 if row.get('scope')!='HISTORICAL_PROVENANCE_NOT_RUNTIME_DEPENDENCY' or not row.get('consumer_audit') or row.get('sha256')!=hashlib.sha256(data).hexdigest():raise ContractError('Legacy provenance allowance must bind unchanged original bytes and consumer audit')
 if '/' in relative_name or Path(relative_name).suffix.lower() not in ('.json','.md'):raise ContractError('Runtime/config/nested world files cannot receive provenance exceptions')
 originals=[r for r in world.get('files',[]) if r.get('relative')==relative_name]
 if len(originals)!=1 or originals[0].get('sha256')!=row['sha256']:raise ContractError('Legacy allowance is outside the original world file manifest')
 text=data.decode('utf-8-sig')
 if relative_name.endswith('.json'):
  obj=json.loads(text);seen=set()
  if not row.get('json_fields') or row.get('text_literals'):raise ContractError('JSON provenance requires exact JSON pointers')
  for field in row['json_fields']:
   pointer=field.get('json_pointer','')
   if not pointer.startswith('/') or pointer in seen:raise ContractError('Invalid/duplicate provenance JSON pointer')
   seen.add(pointer);keys=[k.replace('~1','/').replace('~0','~') for k in pointer[1:].split('/')];parent=obj
   for key in keys[:-1]:parent=parent[int(key)] if isinstance(parent,list) else parent[key]
   key=int(keys[-1]) if isinstance(parent,list) else keys[-1];value=parent[key]
   if not isinstance(value,str) or not ABS_PATH.search(value) or hashlib.sha256(value.encode()).hexdigest()!=field.get('value_sha256'):raise ContractError('Historical path value changed or was not a path')
   parent[key]='[historical provenance retained in original save bytes]'
  text=json.dumps(obj,ensure_ascii=False)
 else:
  if row.get('json_fields') or not row.get('text_literals'):raise ContractError('Historical document requires exact literal allowances')
  for literal in row['text_literals']:
   if not isinstance(literal,str) or not ABS_PATH.search(literal) or literal not in text:raise ContractError('Historical document path literal changed')
   text=text.replace(literal,'[historical repository location]')
 return portable_text(text.encode(),label)

def runtime_owner_config(data):
 text=portable_text(data,'config/projectseele-runtime-r45.properties');values={}
 for line in text.splitlines():
  line=line.strip()
  if not line or line.startswith(('#','!')):continue
  if '=' not in line or '\\' in line:raise ContractError('Malformed/escaped runtime owner setting')
  key,value=line.split('=',1);key=key.strip();value=value.strip()
  if key in values:raise ContractError('Duplicate runtime owner setting: '+key)
  values[key]=value
 keys={'schema','weapon_handling','cannon_contact','captured_support','captured_locomotion_directory'}
 for side in ('client','server'):keys|={f'city.union.{side}.{suffix}' for suffix in ('enabled','required','create_class_sha256','proof_sha256')}
 optional={'tv_cage','personnel_platforms'}
 if not keys.issubset(values) or not set(values).issubset(keys|optional) or values['schema']!='projectseele.runtime-owners.r45.v1':raise ContractError('Incomplete/unknown runtime owner config')
 for key in optional:
  if values.get(key,'false') not in ('true','false'):raise ContractError('Invalid explicit facility Boolean: '+key)
 if values.get('tv_cage','false')!=values.get('personnel_platforms','false'):raise ContractError('TV cage and personnel platform owners must deploy together')
 for key in ('weapon_handling','cannon_contact','captured_support','city.union.client.enabled','city.union.client.required','city.union.server.enabled','city.union.server.required'):
  if values[key] not in ('true','false'):raise ContractError('Explicit runtime owner Boolean required: '+key)
 directory=values['captured_locomotion_directory']
 if directory and not relative(directory).startswith('projectseele-local-maps/'):raise ContractError('Captured owner directory must be portable inside its instance')
 if values['captured_support']=='true' and not directory:raise ContractError('Captured support owner lacks selected captured profiles')
 for side in ('client','server'):
  prefix=f'city.union.{side}.'
  if values[prefix+'enabled']=='true':raise ContractError('Published City proof is unmeasured; this candidate requires explicit disabled City profiles')
  if values[prefix+'required']!='false' or values[prefix+'proof_sha256']:raise ContractError('Disabled City profile cannot claim a required proof')
 return values

def check_memory(args):
 if not isinstance(args,list) or not all(isinstance(x,str) and '\n' not in x and '\r' not in x for x in args):raise ContractError('server_jvm_args must be a line array')
 if [x for x in args if x.startswith(('-Xms','-Xmx'))]!=['-Xms2G','-Xmx20G']:raise ContractError('Production server requires exactly -Xms2G -Xmx20G; inherited16G/smoke4G rejected')
 if '-Dfile.encoding=UTF-8' not in args:raise ContractError('Server UTF-8 argument missing')
 portable_text('\n'.join(args).encode(),'user_jvm_args.txt')
 for x in args:
  if x.startswith('@') or not (x in ('-Xms2G','-Xmx20G','-Dfile.encoding=UTF-8','-XX:+UseG1GC','-XX:+ParallelRefProcEnabled') or re.fullmatch(r'-XX:(?:MaxGCPauseMillis|G1ReservePercent|InitiatingHeapOccupancyPercent)=\d+',x) or re.fullmatch(r'-XX:G1HeapRegionSize=\d+M',x) or x.startswith('-Dprojectseele.')):raise ContractError(f'Unapproved server JVM argument: {x}')
  if x.startswith('-Dprojectseele.') and not re.fullmatch(r'-Dprojectseele\.combatBundleDirectory=projectseele-local-maps(?:/[a-zA-Z0-9_-]+)?',x):raise ContractError(f'Unapproved production property: {x}')
 return args

def class_protocol(data):
 if data[:4]!=b'\xca\xfe\xba\xbe':raise ContractError('Not a JVM class')
 count=struct.unpack_from('>H',data,8)[0];i=1;pos=10;utf={};strings={}
 widths={3:4,4:4,5:8,6:8,7:2,8:2,9:4,10:4,11:4,12:4,15:3,16:2,17:4,18:4,19:2,20:2}
 while i<count:
  tag=data[pos];pos+=1
  if tag==1:
   size=struct.unpack_from('>H',data,pos)[0];pos+=2;utf[i]=data[pos:pos+size].decode('utf-8',errors='replace');pos+=size
  elif tag in widths:
   if tag==8:strings[i]=struct.unpack_from('>H',data,pos)[0]
   pos+=widths[tag];i+=int(tag in (5,6))
  else:raise ContractError(f'Unknown class constant tag {tag}')
  i+=1
 pos+=6;interfaces=struct.unpack_from('>H',data,pos)[0];pos+=2+2*interfaces
 fields=struct.unpack_from('>H',data,pos)[0];pos+=2
 for _ in range(fields):
  flags,name,desc,attributes=struct.unpack_from('>HHHH',data,pos);pos+=8
  for _ in range(attributes):
   attr,length=struct.unpack_from('>HI',data,pos);pos+=6
   if utf.get(name)=='PROTOCOL_VERSION' and utf.get(desc)=='Ljava/lang/String;' and utf.get(attr)=='ConstantValue' and length==2 and flags&0x0018==0x0018:
    value=struct.unpack_from('>H',data,pos)[0]
    if value in strings:return utf[strings[value]]
   pos+=length
 raise ContractError('Actual static final PROTOCOL_VERSION ConstantValue missing')

def inspect_jar(path):
 result={'mods':{},'primary_mods':{},'dependencies':[],'embedded':[]}
 def scan(z,depth=0):
  if depth>4:raise ContractError('Nested jar depth exceeds contract')
  if 'META-INF/mods.toml' in z.namelist():
   t=tomllib.loads(z.read('META-INF/mods.toml').decode('utf-8'))
   for mod in t.get('mods',[]):
    version=str(mod.get('version',''))
    if version=='${file.jarVersion}':
     manifest=z.read('META-INF/MANIFEST.MF').decode('utf-8')
     version=next((s.partition(':')[2].strip() for s in manifest.splitlines() if s.startswith('Implementation-Version:')),'')
    if depth==0:result['primary_mods'][mod['modId']]=version
    old=result['mods'].get(mod['modId'])
    if old is None or version_tuple(version)>version_tuple(old):result['mods'][mod['modId']]=version
   for deps in t.get('dependencies',{}).values():result['dependencies'].extend(deps)
  if 'META-INF/jarjar/metadata.json' in z.namelist():
   rows=json.loads(z.read('META-INF/jarjar/metadata.json'))['jars']
   for row in rows:
    result['embedded'].append(row['identifier']['artifact'])
    scan(zipfile.ZipFile(io.BytesIO(z.read(row['path']))),depth+1)
 with zipfile.ZipFile(path) as z:scan(z)
 return result

def version_tuple(value):
 parts=re.match(r'^(\d+(?:\.\d+)*)',str(value))
 if not parts:raise ContractError(f'Cannot verify dependency version {value!r}')
 x=tuple(map(int,parts[1].split('.')));return x+(0,)*(6-len(x))

def range_contains(version,requirement):
 if not requirement or requirement=='*':return True
 v=version_tuple(version);r=str(requirement)
 if re.fullmatch(r'\[[^,]+\]',r):return v==version_tuple(r[1:-1])
 m=re.fullmatch(r'([\[(])([^,]*),([^\])]*)([\])])',r)
 if not m:raise ContractError(f'Unknown dependency range {r!r}')
 lo,hi=m[2].strip(),m[3].strip()
 lower=not lo or (v>=version_tuple(lo) if m[1]=='[' else v>version_tuple(lo))
 upper=not hi or (v<=version_tuple(hi) if m[4]==']' else v<version_tuple(hi))
 return lower and upper

def check_dependencies(metadata,side):
 versions={'minecraft':'1.20.1','forge':'47.4.10','kotlinforforge':'4.12.0'}
 for item in metadata:
  for name,value in item['mods'].items():
   if name not in versions or version_tuple(value)>version_tuple(versions[name]):versions[name]=value
 # Verify the pinned top-level modules; native Forge selection is a separate acceptance gate.
 for item in metadata:versions.update(item.get('primary_mods',{}))
 for item in metadata:
  for d in item['dependencies']:
   if not d.get('mandatory') or d.get('side','BOTH') not in ('BOTH',side):continue
   if d['modId'] not in versions:raise ContractError(f'Missing {side} dependency {d["modId"]}')
   if not range_contains(versions[d['modId']],d.get('versionRange','*')):raise ContractError(f'Unsatisfied {side} dependency {d["modId"]} {d.get("versionRange")}')

def protected_world_file(name):
 n=relative(name).lower()
 return n in ('level.dat','level.dat_old','uid.dat') or any(part in {'playerdata','advancements','stats','region','entities','poi','data','datapacks','serverconfig','mtr'} for part in PurePosixPath(n).parts) or any(s in n for s in ('mtr','city_coordination','tv_campaign','tv_encounter','nerv_routes','registry','roster','supply','inventory','ledger','canonical'))

def receipt(row,label):
 if not isinstance(row,dict) or not row.get('source') or not row.get('sha256'):raise ContractError(f'Missing pinned receipt: {label}')
 p=Path(row['source'])
 if not p.is_absolute() or not p.is_file() or sha(p)!=row['sha256']:raise ContractError(f'Receipt missing/changed: {label}')
 return read_json(p)

class Validator:
 def __init__(self,repo,manifest):self.repo=Path(repo).resolve();self.m=manifest;self.issues=[];self.inputs=[];self.mods={};self.resource_closure={}
 def issue(self,code,message):self.issues.append({'code':code,'message':message})
 def runcheck(self,code,fn):
  try:return fn()
  except (ValueError,KeyError,OSError,zipfile.BadZipFile,UnicodeError,struct.error,IndexError,TypeError) as e:self.issue(code,str(e));return None
 def blob(self,row,target,*,text=False,world_relative=None):
  def verify():
   if not isinstance(row,dict) or not row.get('source') or not row.get('sha256'):raise ContractError(f'Missing source/SHA256: {target}')
   path=Path(row['source']);relative(target)
   if not path.is_absolute() or not path.is_file():raise ContractError(f'Explicit input file missing: {target}')
   actual=sha(path)
   if not re.fullmatch('[a-f0-9]{64}',str(row['sha256'])) or actual!=row['sha256']:raise ContractError(f'Input SHA changed: {target}')
   if text or Path(target).suffix.lower() in TEXT_SUFFIXES:
    if world_relative is None:portable_text(path.read_bytes(),target)
    else:portable_world_text(path.read_bytes(),target,self.m['world'],world_relative)
   self.inputs.append({'source':str(path.resolve()),'sha256':actual,'target':target})
   return path
  return self.runcheck('INPUT_FILE',verify)
 def catalog(self,key,expected,kinds):
  rows=self.m.get(key)
  if not isinstance(rows,list):self.issue('MOD_LIST_MISSING',key);return
  names=[r.get('filename') for r in rows if isinstance(r,dict)]
  if len(names)!=len(rows) or len(set(names))!=len(names):self.issue('DUPLICATE_MOD',key)
  for name in sorted(expected-set(names)):self.issue('MOD_MISSING',f'{key}: {name}')
  for name in sorted(set(names)-expected,key=str):self.issue('MOD_UNKNOWN',f'{key}: {name}')
  for row in rows:
   if not isinstance(row,dict) or row.get('filename') not in expected:continue
   name=row['filename'];p=self.blob(row,f'inputs/mods/{name}')
   if p:
    meta=self.runcheck('MOD_MANIFEST',lambda:inspect_jar(p))
    if meta:
     expected_versions={
      'MTR-forge-4.0.5+1.20.1.jar':('mtr','4.0.5'),'Patchouli-1.20.1-85-FORGE.jar':('patchouli','1.20.1-85-FORGE'),
      'another-furniture-1.20.1-3.0.4.jar':('another_furniture','1.20.1-3.0.4'),'ars-nouveau-4.12.7.jar':('ars_nouveau','4.12.7'),
      'create-1.20.1-6.0.8.jar':('create','6.0.8'),'curios-forge-1.20.1-5.14.1.jar':('curios','5.14.1+1.20.1'),
      'embeddium-0.3.31+mc1.20.1.jar':('embeddium','0.3.31+mc1.20.1'),'ferritecore-6.0.1-forge.jar':('ferritecore','6.0.1'),
      'geckolib-forge-1.20.1-4.8.4.jar':('geckolib','4.8.4'),'grandpianomod-1.0.0.jar':('grandpianomod','1.0.0'),
      'kotlinforforge-4.12.0-all.jar':('kotlinforforge','4.12.0'),'mcw-doors-1.1.5-mc1.20.1forge.jar':('mcwdoors','1.1.5'),
      'modernfix-forge-5.27.83+mc1.20.1.jar':('modernfix','5.27.83+mc1.20.1'),'movingelevators-1.4.12-forge-mc1.20.1.jar':('movingelevators','1.4.12'),
      'oculus-mc1.20.1-1.8.0.jar':('oculus','1.8.0'),'superbwarfare-0.8.9.1-hotfix-mc1.20.1-993063bed-all.jar':('superbwarfare','0.8.9.1'),
      'supermartijn642configlib-1.1.8-forge-mc1.20.jar':('supermartijn642configlib','1.1.8'),
      'supermartijn642corelib-1.1.24-forge-mc1.20.1.jar':('supermartijn642corelib','1.1.24'),
      'xaerominimap-forge-1.20.1-26.5.0.jar':('xaerominimap','26.5.0'),'xaeroworldmap-forge-1.20.1-1.46.0.jar':('xaeroworldmap','1.46.0')}
     ident,version=expected_versions[name]
     if name=='kotlinforforge-4.12.0-all.jar':
      # The official all.jar is a Forge LIBRARY wrapper. The actual mod and
      # language providers live in its three declared nested JARs.
      with zipfile.ZipFile(p) as archive:wrapper=archive.read('META-INF/MANIFEST.MF').decode('utf-8')
      if meta['mods'].get(ident)!=version or not {'kfflang','kfflib','kffmod'}<=set(meta['embedded']) or not re.search(r'^FMLModType: LIBRARY\s*$',wrapper,re.M):
       self.issue('MOD_ID_VERSION',f'Actual {name} is not the complete KotlinForForge {version} library wrapper')
     elif meta['primary_mods'].get(ident)!=version:self.issue('MOD_ID_VERSION',f'Actual {name} primary module is not {ident} {version}')
     self.mods[name]=meta
    if name=='create-1.20.1-6.0.8.jar':
     if sha(p)!=CREATE_SHA:self.issue('CREATE_NOT_UNMODIFIED_UNIVERSAL','Create production SHA must be verified original6.0.8 universal')
     if meta and not {'Registrate','flywheel-forge-1.20.1','mixinextras-forge','Ponder-Forge-1.20.1'}<=set(meta['embedded']):self.issue('CREATE_JARJAR_MISSING','Original universal nested dependencies missing')
   for kind in kinds:
    if p:self.inputs.append({'source':str(p.resolve()),'sha256':row['sha256'],'target':f'{kind}/mods/{name}'})
 def validate(self):
  m=self.m
  if m.get('schema')!=SCHEMA:self.issue('SCHEMA','Explicit R45 manifest required; R44/v12 audit is not a build manifest')
  if not re.fullmatch(r'(?:R4[56]_[a-zA-Z0-9_-]+|Project_SEELE_Encore_R4[56]_[0-9]{8})',str(m.get('batch_id',''))):self.issue('BATCH_ID','Explicit R45 or Project_SEELE_Encore_R45_<date> batch_id required')
  if m.get('protocol')!=PROTOCOL:self.issue('PROTOCOL','Current protocol54 required; older client semantics refused')
  if (m.get('minecraft'),m.get('forge'),m.get('java'))!=('1.20.1','47.4.10','17'):self.issue('PLATFORM','Pinned MC/Forge/Java versions required')
  self.runcheck('OUTPUT_PATH',lambda:output_path(self.repo,m.get('output_directory')))
  self.runcheck('SERVER_MEMORY',lambda:check_memory(m.get('server_jvm_args')))
  self.runcheck('DELIVERY_SCOPE',lambda:native_check_policy(m))
  reviews=m.get('reviews',{})
  if set(reviews)!=set(REVIEW_GROUPS):self.issue('REVIEW_GROUPS','Keep functional/measured/inherited/visual_self/user/unverified separate')
  for group,rows in reviews.items():
   if not isinstance(rows,list) or any(not isinstance(x,dict) or x.get('status') not in REVIEW_STATES for x in rows):self.issue('REVIEW_STATE',group)
  build=m.get('build') or {};project=build.get('project_jar');p=self.blob(project,'inputs/projectseele-runtime.jar')
  if p:
   if not p.name.endswith('-all.jar'):self.issue('PROJECT_NOT_ALL','Production reobfuscated all.jar required')
   def project_contract():
    with zipfile.ZipFile(p) as z:
     if PROTOCOL!=class_protocol(z.read('com/projectseele/network/SeeleNetwork.class')):raise ContractError('Actual jar protocol is not54')
     nested=json.loads(z.read('META-INF/jarjar/metadata.json'))['jars']
     if not {'jbullet','stack-alloc','vecmath'}<=set(x['identifier']['artifact'] for x in nested):raise ContractError('Physics jarJar runtime missing')
     assets=build.get('embedded_assets')
     if not isinstance(assets,dict) or not assets:raise ContractError('Approved complete embedded model/control resource manifest missing')
     mandatory={f'assets/projectseele/{family}/{unit}.{suffix}' for unit in ('eva_unit00','eva_unit01','eva_unit02','eva_prototype','eva_un01') for family,suffix in [('mesh','mesh.json'),('geo','geo.json'),('animations','animation.json'),('textures/entity','png')]}
     mandatory.add('data/projectseele/nerv_dialogue/profiles.json')
     if not mandatory<=set(assets):raise ContractError('Complete original EVA model/dialogue resource set missing: '+str(sorted(mandatory-set(assets))))
     for name,digest in assets.items():
      relative(name)
      if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ContractError(f'Embedded resource changed: {name}')
     self.resource_closure=check_resource_closure(z,assets,m.get('runtime_files'))
     if re.fullmatch(r'(?:R46_[a-zA-Z0-9_-]+|Project_SEELE_Encore_R46_[0-9]{8})',str(m.get('batch_id',''))):
      from release_r46_features import check_r46_features
      recipes=[r for r in (m.get('shaders') or {}).get('adapter_files',[]) if r.get('destination')=='private_shader_recipe_v12.json']
      if len(recipes)!=1:raise ContractError('One R46 actual personal recipe required')
      check_r46_features(z,m.get('runtime_files'),recipes[0]['source'])
     for member in z.namelist():
      if member.startswith(('assets/','data/')) and Path(member).suffix.lower() in TEXT_SUFFIXES:portable_text(z.read(member),member)
     for prefix in ('assets/projectseele/mesh/','assets/projectseele/geo/','assets/projectseele/animations/','data/projectseele/nerv_dialogue/'):
      if not any(n.startswith(prefix) for n in assets):raise ContractError(f'Required resource family missing: {prefix}')
    proof=receipt(build.get('production_receipt'),'production build')
    self.inputs.append({'source':str(Path(build['production_receipt']['source']).resolve()),'sha256':build['production_receipt']['sha256'],'target':'inputs/receipts/production.json'})
    if proof.get('scope')!='ACTUAL_PRODUCTION_BUILD' or proof.get('build_executed') is not True or proof.get('production_reobfuscated') is not True or proof.get('project_mod_sha256')!=project['sha256'] or proof.get('protocol')!=PROTOCOL:raise ContractError('Actual production build receipt does not bind finaljar/protocol/reobfuscation')
   self.runcheck('PROJECT_CONTRACT',project_contract)
   for kind in ('client','client_plain','server'):self.inputs.append({'source':str(p.resolve()),'sha256':project['sha256'],'target':f'{kind}/mods/{p.name}'})
  def asset_policy():
   proof=receipt(m.get('asset_policy_receipt'),'formal gantry resource policy')
   if proof.get('gantry_track')!='draft12' or proof.get('experimental_thin_beams_included') is not False:raise ContractError('Only formal draft12 gantry resources allowed; experimental thin beams refused')
   if proof.get('project_mod_sha256')!=(project or {}).get('sha256'):raise ContractError('Gantry policy does not bind final production jar')
   hashes=proof.get('gantry_asset_sha256')
   if not isinstance(hashes,dict) or not hashes or any(build.get('embedded_assets',{}).get(name)!=digest for name,digest in hashes.items()):raise ContractError('Formal gantry hashes not covered by final embedded asset manifest')
   self.inputs.append({'source':str(Path(m['asset_policy_receipt']['source']).resolve()),'sha256':m['asset_policy_receipt']['sha256'],'target':'inputs/receipts/asset_policy.json'})
  self.runcheck('FORMAL_RESOURCE_POLICY',asset_policy)
  self.catalog('common_mods',COMMON,('client','client_plain','server'))
  self.catalog('client_mods',CLIENT,('client','client_plain'))
  self.catalog('full_client_mods',FULL,('client',))
  project_meta=self.runcheck('PROJECT_DEPENDENCIES',lambda:inspect_jar(p)) if p else None
  for side,keys in [('SERVER',COMMON),('CLIENT',COMMON|CLIENT),('CLIENT',COMMON|CLIENT|FULL)]:
   if keys<=self.mods.keys():self.runcheck('DEPENDENCY_CLOSURE',lambda s=side,k=keys:check_dependencies([self.mods[n] for n in k]+([project_meta] if project_meta else []),s))
  for key,kinds in [('runtime_files',('client','client_plain','server')),('client_files',('client','client_plain')),('server_files',('server',)),('docs_files',tuple(KINDS.values()))]:
   rows=m.get(key)
   if not isinstance(rows,list) or not rows:self.issue('PAYLOAD_LIST_MISSING',key);continue
   for row in rows:
    if not isinstance(row,dict) or not row.get('destination'):self.issue('DESTINATION_MISSING',key);continue
    dest=self.runcheck('DESTINATION',lambda r=row:relative(r['destination']))
    if not dest:continue
    if any(t in dest.lower() for t in ('oculus','iris','shader','rubidium','gendo_player','accounts.json','launcher_profiles')) or (dest.endswith('.jar') and not (key=='server_files' and dest.startswith('libraries/'))) or dest.startswith(('mods/','saves/','shaderpacks/','resourcepacks/')) or re.fullmatch(r'R4[56]_(?:BATCH|ACCEPTANCE|CANDIDATE_STATUS)\.json',dest) or dest in ('user_jvm_args.txt','manifest.json','PCL/Setup.ini','COMPLEMENTARY_CREDITS.txt','options.txt'):self.issue('PAYLOAD_CONFLICT',key+':'+dest);continue
    for kind in kinds:self.blob(row,kind+'/'+dest)
  if not any(x['target'].startswith('server/libraries/') for x in self.inputs):self.issue('FORGE_RUNTIME_MISSING','Explicit server libraries file list required')
  def forge_runtime():
   proof=receipt(m.get('forge_runtime_receipt'),'Forge production runtime')
   if proof.get('forge')!='47.4.10' or proof.get('minecraft')!='1.20.1' or proof.get('production_installed') is not True:raise ContractError('Actual Forge47.4.10 production runtime receipt required')
   files={row['target'].removeprefix('server/'):row['sha256'] for row in self.inputs if row['target'].startswith('server/libraries/')}
   if not files or proof.get('files')!=files:raise ContractError('Forge runtime libraries are missing/unknown relative to pinned installation manifest')
   self.inputs.append({'source':str(Path(m['forge_runtime_receipt']['source']).resolve()),'sha256':m['forge_runtime_receipt']['sha256'],'target':'inputs/receipts/forge_runtime.json'})
  self.runcheck('FORGE_RUNTIME_RECEIPT',forge_runtime)
  for name in ('Start-Server.bat','start-server.sh','server.properties'):
   if not any(x['target']=='server/'+name for x in self.inputs):self.issue('SERVER_ENTRY_MISSING',name)
  for row in self.inputs:
   if row['target'] in ('server/Start-Server.bat','server/start-server.sh'):
    def launch_check(r=row):
     text=Path(r['source']).read_text('utf-8-sig')
     argfile='win_args.txt' if r['target'].endswith('.bat') else 'unix_args.txt'
     if 'user_jvm_args.txt' not in text or argfile not in text or 'nogui' not in text:raise ContractError('Server launcher must use pinned user_jvm_args and Forge argfile with nogui')
     if re.search(r'-Xm[sx]|-Dprojectseele\.',text):raise ContractError('Server launcher contains hidden heap override or private property')
    self.runcheck('SERVER_LAUNCH_CHAIN',launch_check)
   if row['target'].startswith('server/libraries/') and row['target'].endswith('_args.txt'):
    def forge_args(r=row):
     text=Path(r['source']).read_text('utf-8-sig')
     if re.search(r'-Xm[sx]|-Dprojectseele\.',text):raise ContractError('Forge argfile contains hidden heap/QA override')
    self.runcheck('FORGE_ARGS',forge_args)

  world=m.get('world') or {};role=world.get('role')
  if role!='DELIVERY_SOURCE':self.issue('WORLD_ROLE','DELIVERY_SOURCE required; QA_ONLY cannot be packaged')
  source=Path(world.get('source_directory') or '.')
  source_safe=source.is_absolute() and source.is_dir() and source.resolve() not in {Path(self.repo).resolve(),(self.repo/'artifacts').resolve(),(self.repo/'run').resolve(),Path(source.anchor).resolve()} and (source/'level.dat').is_file()
  if not source_safe:self.issue('WORLD_SOURCE','Explicit reviewed world directory with level.dat required; drive/workspace/container roots refused')
  qa_source=any('native_candidate_session' in part.lower() or part.upper().endswith('_REVIEW') for part in source.parts)
  if qa_source:self.issue('WORLD_QA_PATH','Known native QA/review source cannot be relabeled delivery')
  no_global_uuid=world.get('world_uuid') is None and world.get('world_identity_kind')=='VANILLA_NO_GLOBAL_UUID'
  if not no_global_uuid and not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',str(world.get('world_uuid',''))):self.issue('WORLD_UUID','Original UUID or explicit vanilla no-global-UUID identity required')
  if not isinstance(world.get('seed'),int) or isinstance(world.get('seed'),bool):self.issue('WORLD_SEED','Original integer seed required')
  name=world.get('world_name');valid_name=isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_-]+',name) and 'REVIEW' not in name.upper() and 'QA' not in name.upper()
  if not valid_name:self.issue('WORLD_NAME','Explicit non-QA delivery world_name required')
  if world.get('writer_closed') is not True:self.issue('WORLD_WRITER','Root must close the sole source writer before freeze')
  def world_receipt():
   proof=receipt(world.get('composition_receipt'),'world composition')
   self.inputs.append({'source':str(Path(world['composition_receipt']['source']).resolve()),'sha256':world['composition_receipt']['sha256'],'target':'inputs/receipts/composition.json'})
   for key in ('source_progress_preserved','original_identities_preserved','required_components_installed'):
    if proof.get(key) is not True:raise ContractError('Composition not closed: '+key)
   if proof.get('role')!='DELIVERY_SOURCE' or Path(proof.get('world','')).resolve()!=source.resolve():raise ContractError('Composition role/source does not match delivery source')
   if proof.get('world_uuid')!=world.get('world_uuid') or proof.get('seed')!=world.get('seed'):raise ContractError('Original world UUID/seed not bound')
   if no_global_uuid and proof.get('world_identity_kind')!='VANILLA_NO_GLOBAL_UUID':raise ContractError('Vanilla no-global-UUID identity receipt does not bind selected world')
   return True
  world_approved=self.runcheck('WORLD_RECEIPT',world_receipt) is True and source_safe and not qa_source and role=='DELIVERY_SOURCE'
  rows=world.get('files');omissions=world.get('omissions',[]);listed=set()
  if not isinstance(rows,list) or not rows:self.issue('WORLD_FILE_MANIFEST','Exact world files with full NBT SHA required');rows=[]
  for row in rows:
   if not isinstance(row,dict):self.issue('WORLD_FILE','Malformed world file row');continue
   rel=self.runcheck('WORLD_PATH',lambda r=row:relative(r.get('relative')))
   if not rel:continue
   if rel.lower() in listed:self.issue('WORLD_DUPLICATE',rel)
   listed.add(rel.lower())
   if re.fullmatch(r'R4[56]_(?:BATCH|ACCEPTANCE|CANDIDATE_STATUS)\.json',rel):self.issue('WORLD_RELEASE_METADATA_CONFLICT','Prior package metadata requires explicit non-progress omission: '+rel)
   if rel.endswith('.lock') or rel=='session.lock':self.issue('WORLD_LOCK','Locks must have explicit omission receipt');continue
   p=source/rel
   if not world_approved:continue
   if not p.resolve().is_relative_to(source.resolve()):self.issue('WORLD_ESCAPE',rel);continue
   self.blob({'source':str(p),'sha256':row.get('sha256')},'world/'+rel,world_relative=rel)
   if valid_name:self.blob({'source':str(p),'sha256':row.get('sha256')},'server/'+name+'/'+rel,world_relative=rel)
  excluded=set()
  for row in omissions:
   rel=self.runcheck('WORLD_OMISSION',lambda r=row:relative(r.get('relative')))
   if not rel:continue
   if protected_world_file(rel) or not row.get('reason'):self.issue('PROTECTED_WORLD_OMISSION',rel)
   excluded.add(rel.lower())
  if listed&excluded:self.issue('WORLD_OMISSION_CONFLICT','File both included and omitted')
  if world_approved:
   def inventory():
    actual=set()
    for path in source.rglob('*'):
     if path.is_symlink() or getattr(path,'is_junction',lambda:False)():raise ContractError('World nested reparse point refused')
     if path.is_file():actual.add(path.relative_to(source).as_posix().lower())
    if actual!=listed|excluded:raise ContractError(f'World file manifest incomplete or stale: unlisted={sorted(actual-listed-excluded)[:12]} missing={sorted((listed|excluded)-actual)[:12]}')
   self.runcheck('WORLD_INVENTORY',inventory)
  if 'level.dat' not in listed:self.issue('WORLD_LEVEL','Original level.dat missing')
  textures=m.get('textures') or {}
  if textures.get('selected') is None:self.issue('TEXTURE_UNSELECTED','Realistic industrial/city texture remains unselected; fallback is not acceptance')
  def texture_license():
   proof=receipt(textures.get('license_receipt'),'texture license')
   self.inputs.append({'source':str(Path(textures['license_receipt']['source']).resolve()),'sha256':textures['license_receipt']['sha256'],'target':'inputs/receipts/texture_license.json'})
   if proof.get('redistribution_allowed') is not True or proof.get('selection_role')!='REALISTIC_INDUSTRIAL_CITY' or not proof.get('official_source'):raise ContractError('Texture redistribution/realistic selection receipt missing')
  self.runcheck('TEXTURE_LICENSE',texture_license)
  rows=textures.get('files')
  if not isinstance(rows,list) or not rows:self.issue('TEXTURE_PAYLOAD','Texture payload file list missing');rows=[]
  for row in rows:
   name=(row.get('destination') or '') if isinstance(row,dict) else ''
   if not name.startswith('resourcepacks/') or 'rotr' in name.lower() or 'faithful' in name.lower():self.issue('TEXTURE_NOT_SELECTED_REALISTIC',name);continue
   texture_source=None
   for kind in ('textures','client'):
    if isinstance(row,dict):texture_source=self.blob(row,kind+'/'+name)
   if texture_source and name.endswith('.zip'):
    def optional_texture_scope(p=texture_source):
     with zipfile.ZipFile(p) as z:check_optional_texture_pack(z,self.resource_closure.get('protected_model_control_resources',[]))
    self.runcheck('OPTIONAL_TEXTURE_CORE_SHADOW',optional_texture_scope)
  shaders=m.get('shaders') or {};stock=shaders.get('original_zip')
  p=self.blob(stock,'shaders/shaderpacks/ComplementaryUnbound_r5.3.zip')
  if p:
   if sha(p)!=SHADER_SHA:self.issue('SHADER_NOT_ORIGINAL','Only pinned unmodified r5.3 shader is permitted')
   else:
    with zipfile.ZipFile(p) as z:
     if hashlib.sha256(z.read('License.txt')).hexdigest()!=LICENSE_SHA:self.issue('SHADER_LICENSE_CHANGED','Original 1.5 license bytes changed')
   self.blob(stock,'client/shaderpacks/ComplementaryUnbound_r5.3.zip')
  rows=shaders.get('adapter_files')
  required={'Install-LocalPrivateVisuals.v12.ps1','private_shader_recipe_v12.json'}
  if not isinstance(rows,list) or {r.get('destination') for r in rows if isinstance(r,dict)}!=required:self.issue('SHADER_ADAPTER','Both offline personal adapter files required; no prebuilt variant');rows=[]
  for row in rows:
   for kind in ('shaders','client'):self.blob(row,kind+'/'+row['destination'])
  for row in rows:
   if row.get('destination')=='private_shader_recipe_v12.json':
    def recipe_check(r=row):
     if not r.get('source'):raise ContractError('Pinned personal shader recipe source missing')
     recipe=read_json(r['source'])
     if recipe.get('input_sha256')!=SHADER_SHA or recipe.get('input_license_sha256')!=LICENSE_SHA or recipe.get('scope')!='LOCAL_PERSONAL_ONLY_NOT_PREBUILT_SHADER_DISTRIBUTION':raise ContractError('Personal adapter input/license/scope is not bound to original r5.3')
     if 'Complementary' in str(recipe.get('output_filename')):raise ContractError('Local derivative name must be separate from original')
    self.runcheck('SHADER_ADAPTER_SCOPE',recipe_check)
  if shaders.get('enabled_by_default') is not False:self.issue('SHADER_DEFAULT','Default shader must be disabled')
  if not shaders.get('credits_text') or 'https://www.complementary.dev/' not in shaders.get('credits_text',''):self.issue('SHADER_CREDITS','Visible original shader credits, URL and modpack responsibility required')
  allowed_options={'renderDistance','simulationDistance','mipmapLevels','graphicsMode','particles','entityDistanceScaling','lang','fov','gamma','maxFps','fullscreen','enableVsync'}
  for key in (m.get('client_options') or {}):
   if key not in allowed_options and not key.startswith('key_') and not key.startswith('soundCategory_'):self.issue('CLIENT_OPTION_UNKNOWN',key)
  owners=[r for r in (m.get('runtime_files') or []) if isinstance(r,dict) and r.get('role')=='runtime_owners']
  if len(owners)!=1 or owners[0].get('destination')!='config/projectseele-runtime-r45.properties':self.issue('RUNTIME_OWNER_CONFIG','One identical explicit portable owner file required for Full/Plain/server')
  elif owners[0].get('source') and Path(owners[0]['source']).is_file():
   def owners_check():
    flags=runtime_owner_config(Path(owners[0]['source']).read_bytes());directory=flags['captured_locomotion_directory']
    selected={r.get('destination') for r in (m.get('runtime_files') or []) if isinstance(r,dict)}
    if directory:
     for rig in (0,1,2):
      if f'{directory}/eva_locomotion_capture_r44_{rig}.json' not in selected:raise ContractError('Selected captured owner profile missing: unit0'+str(rig))
   self.runcheck('PORTABLE_RUNTIME_OWNERS',owners_check)
  roles={r.get('role') for r in (m.get('runtime_files') or []) if isinstance(r,dict)}
  for role in {'eva_body','eva_gameplay_0','eva_gameplay_1','eva_gameplay_2','eva_gameplay_3','eva_gameplay_4','first_battle','sachiel','grip','recovery','physical_bodies'}-roles:self.issue('RUNTIME_ROLE_MISSING',role)
  seen={}
  for row in self.inputs:
   target=row['target'].lower()
   if target in seen and seen[target]!=row['sha256']:self.issue('DESTINATION_CONFLICT',row['target'])
   seen[target]=row['sha256']
  def source_review():
   review=receipt(m.get('source_review_receipt'),'root reviewed source')
   if review.get('root_reviewed') is not True or review.get('input_digest')!=input_digest(m):raise ContractError('Root reviewed-source receipt does not bind exact input_digest')
  self.runcheck('ROOT_SOURCE_REVIEW',source_review)
  return {'schema':'projectseele.release-r45.plan.v1','input_digest':input_digest(m),'issues':self.issues,'can_freeze':not self.issues,
   'input_count':len(self.inputs),'reviews':reviews,'resource_closure':self.resource_closure,'native_executed':False,'released':False}
