"""Small read-only closure check for final embedded assets and selected embedded/override hand contracts."""
from pathlib import PurePosixPath, Path
import hashlib
import json
import re
import math

class ResourceClosureError(ValueError): pass

WEAPONS={
 'progressive_knife':('knife','progressive_knife'),
 'positron_cannon':('cannon','positron_cannon'),
 'eva_pallet_smg':('cannon','eva_pallet_smg'),
 'eva_n2_device':('n2','eva_n2_device'),
 'longinus_lance':('lance','longinus_lance'),
 'eva02_knife':('knife','eva02_weapons'),
}
CORE_PREFIXES=('assets/projectseele/geo/','assets/projectseele/mesh/','assets/projectseele/animations/',
 'assets/projectseele/motion/','assets/projectseele/eva/','assets/projectseele/gameplay/','assets/projectseele/hand_rigs/',
 'assets/projectseele/textures/entity/','data/projectseele/nerv_dialogue/')

def _leaf(value,label):
 if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9_]+\.mesh\.json',value):
  raise ResourceClosureError('Portable mesh filename required for '+label+'; keep author source paths in the review receipt')
 return value

def check_resource_closure(archive,declared,runtime_files):
 """No copying or source edits. Every asset member and selected runtime reference stays hash-bound."""
 names=archive.namelist()
 if len(names)!=len(set(names)) or len(names)!=len({n.lower() for n in names}):
  raise ResourceClosureError('Duplicate/case-colliding final JAR members')
 members={n for n in names if n.startswith(('assets/','data/')) and not n.endswith('/')}
 if not isinstance(declared,dict):raise ResourceClosureError('Complete embedded resource hashes required')
 if members!=set(declared):
  raise ResourceClosureError('Final embedded resource manifest differs; unlisted='+str(sorted(members-set(declared)))[:1200]+' absent='+str(sorted(set(declared)-members))[:1200])
 required={};jsons={};hand_requirements={}
 def require(name,reason,part=None):
  if name not in members or name not in declared:raise ResourceClosureError('Required resolved resource missing: '+name+' <- '+reason)
  raw=archive.read(name)
  if hashlib.sha256(raw).hexdigest()!=declared[name]:raise ResourceClosureError('Required resolved resource hash changed: '+name)
  required.setdefault(name,[]).append(reason)
  if name.endswith('.json'):
   if name not in jsons:jsons[name]=json.loads(raw)
   if part is not None and part not in jsons[name].get('parts',{}):raise ResourceClosureError('Required mesh part missing: '+name+'#'+part+' <- '+reason)
  return jsons.get(name)
 for mesh,(part,texture) in WEAPONS.items():
  require('assets/projectseele/mesh/'+mesh+'.mesh.json','existing EVA renderer weapon',part)
  require('assets/projectseele/textures/entity/'+texture+'.png','existing EVA renderer weapon texture')
 sound=require('assets/projectseele/sounds.json','all Full/Plain cockpit and AT audio')
 for event,spec in sound.items():
  for item in spec['sounds']:
   entry={'name':item} if isinstance(item,str) else item
   if entry.get('type','file')!='file':continue
   name=entry['name'];ns,sep,path=name.partition(':');ns,path=(ns,path) if sep else ('projectseele',name)
   if ns=='projectseele':require('assets/'+ns+'/sounds/'+path+'.ogg','sound event '+event)
 profiles={};fingerprints={rig:'ABSENT' for rig in (0,1,2)}
 for row in runtime_files or []:
  destination=row.get('destination','')
  if destination.endswith('/hand_rig_contract.json'):
   path=Path(row.get('source',''))
   if not path.is_file():raise ResourceClosureError('Hand contract source missing: '+destination)
   raw=path.read_bytes()
   if hashlib.sha256(raw).hexdigest()!=row.get('sha256'):raise ResourceClosureError('Hand contract input changed: '+destination)
   value=json.loads(raw);rig=value.get('rig')
   if rig not in (0,1,2) or rig in profiles:raise ResourceClosureError('Hand contract rig absent/duplicate: '+destination)
   profiles[rig]=(value,destination,hashlib.sha256(raw).hexdigest())
 external_override=bool(profiles)
 if not external_override:
  for rig in (0,1,2):
   name=f'assets/projectseele/hand_rigs/unit0{rig}/hand_rig_contract.json'
   if name in members:
    value=require(name,'default server/client classpath hand contract')
    if value.get('rig')!=rig:raise ResourceClosureError('Embedded hand contract rig mismatch: '+name)
    profiles[rig]=(value,name,declared[name])
 for rig in (0,1,2):
  geo_name=f'assets/projectseele/geo/eva_unit0{rig}.geo.json';geo=require(geo_name,'selected original airframe rig')
  bones={b['name'] for body in geo.get('minecraft:geometry',[]) for b in body.get('bones',[])}
  hands={n for n in bones if n.startswith('r45_hand_')}
  if not hands:
   if rig in profiles:raise ResourceClosureError('Selected hand contract has no matching final embedded GeoBone rig: unit0'+str(rig))
   continue
  if rig not in profiles:raise ResourceClosureError('Selected hand GeoBones require runtime contract or default embedded contract: unit0'+str(rig)+'; explicit override never falls back per rig')
  contract,dest,contract_sha=profiles[rig]
  if contract.get('schema') not in ('projectseele.anatomical-hands.r45.v1','projectseele.anatomical-hands.r45.v2'):
   raise ResourceClosureError('Unknown selected hand contract schema: '+dest)
  expected=30 if contract['schema'].endswith('.v1') else 34
  declared_hands={b['name'] for b in contract['new_bones'] if b['name'].startswith('r45_hand_')}
  if len(hands)!=expected or hands!=declared_hands:raise ResourceClosureError('Final model/contract hand bone set differs: unit0'+str(rig))
  canonical=f'projectseele-local-maps/hands/unit0{rig}/hand_rig_contract.json' if external_override else f'assets/projectseele/hand_rigs/unit0{rig}/hand_rig_contract.json'
  if dest!=canonical:raise ResourceClosureError('Hand contract must use common Full/Plain/server selected root: '+canonical)
  require(f'assets/projectseele/mesh/eva_unit0{rig}_anatomical_hands_r45.mesh.json',dest,'hand_l')
  require(f'assets/projectseele/mesh/eva_unit0{rig}_anatomical_hands_r45.mesh.json',dest,'hand_r')
  if 'knife_attachment_r45' in contract:
   mesh=_leaf(contract['knife_attachment_r45'].get('source_mesh'),dest+':knife_attachment_r45.source_mesh')
   require('assets/projectseele/mesh/'+mesh,dest+':selected knife attachment','knife')
  if 'knife_mechanism_r45' in contract:
   mech=contract['knife_mechanism_r45'];mesh=_leaf(mech.get('body_mesh'),dest+':knife_mechanism_r45.body_mesh')
   body=require('assets/projectseele/mesh/'+mesh,dest+':selected knife mechanism')
   for bone in mech.get('bones',[]):
    if bone.get('name') not in bones:raise ResourceClosureError('Selected knife mechanism bone missing from final GEO: '+str(bone.get('name')))
   if not body.get('parts'):raise ResourceClosureError('Selected knife mechanism mesh has no actual parts: '+mesh)
  if 'sword_attachment_r45' in contract:
   sword=contract['sword_attachment_r45'];mesh=_leaf(sword.get('source_mesh'),dest+':sword_attachment_r45.source_mesh')
   expected_sha=sword.get('source_mesh_sha256')
   if rig!=2 or sword.get('mesh_part')!='lance' or sword.get('grip_side')!='r' or mesh!='eva02_longsword.mesh.json' or not isinstance(expected_sha,str) or not re.fullmatch(r'[a-f0-9]{64}',expected_sha):
    raise ResourceClosureError('Invalid independent Unit02 sword binding: '+dest)
   if sword.get('intended_variant',2)!=2:raise ResourceClosureError('Sword intended variant must be Unit02: '+dest)
   if not {'lance','hand_r'}<=bones:raise ResourceClosureError('Selected Sword actual GEO hand/socket bones missing: '+dest)
   require('assets/projectseele/mesh/'+mesh,dest+':selected independent Sword','lance')
   if declared['assets/projectseele/mesh/'+mesh]!=expected_sha:raise ResourceClosureError('Selected Sword geometry SHA differs from common hand contract: '+mesh)
   require('assets/projectseele/textures/entity/eva02_longsword.png',dest+':selected independent Sword texture')
   def vector(name,length):
    values=sword.get(name)
    if not isinstance(values,list) or len(values)!=length or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
     raise ResourceClosureError('Invalid finite Sword vector '+name+': '+dest)
    return values
   rotation=vector('rotation_xyzw',4)
   if abs(sum(v*v for v in rotation)-1)>.01:raise ResourceClosureError('Unnormalized Sword attachment: '+dest)
   vector('source_handle_centre',3);vector('target_handle_centre',3)
   base=vector('blade_base_bind',3);tip=vector('blade_tip_bind',3)
   length=math.sqrt(sum((a-b)**2 for a,b in zip(base,tip)));radius=sword.get('blade_radius_native')
   if not 1<=length<=20 or type(radius) not in (int,float) or not math.isfinite(radius) or not 0<radius<=1:
    raise ResourceClosureError('Invalid measured Sword blade segment: '+dest)
  fingerprints[rig]=contract_sha
  hand_requirements[str(rig)]={'runtime_contract':dest,'source':'EXPLICIT_PRIVATE_OVERRIDE' if external_override else 'DEFAULT_CLASSPATH','sha256':contract_sha,'bones':expected,'directory_property':'projectseele.handRigDirectoryR45=projectseele-local-maps/hands' if external_override else None}
 return {'required_resolved_resources':required,'selected_hand_contracts':hand_requirements,
  'protected_model_control_resources':sorted(n for n in members if n.startswith(CORE_PREFIXES)),
  'anatomical_hand_rigs_fingerprint':hashlib.sha256(''.join(f'{rig}:{fingerprints[rig]};' for rig in (0,1,2)).encode('utf-8')).hexdigest(),
  'complete_embedded_manifest_members':len(members),'native_or_user_acceptance':False}

def check_optional_texture_pack(archive,protected):
 """Optional visual textures cannot shadow mandatory EVA geometry/control or skin resources."""
 protected=set(protected)
 for name in archive.namelist():
  if name.endswith('/'):continue
  if name in protected or name.startswith(CORE_PREFIXES):
   raise ResourceClosureError('Optional texture pack shadows required shared Full/Plain EVA resource: '+name)
