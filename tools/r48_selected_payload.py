"""Exact selected R48 Jar payload checks; no hashing, copying, launch or world writes."""
from pathlib import Path
import json,zipfile
ROOT=Path(__file__).resolve().parents[1]
TOPS=('assets','data','META-INF/licenses')
REQUIRED_R48=('assets/projectseele/eva/un_models_r48.json','assets/projectseele/motion/un_finger_poses_r48.json',
 'assets/projectseele/motion/eva_power_ports_r48.json','assets/projectseele/mesh/tripo_carrier_r48.json',
 'assets/projectseele/mesh/tripo_gripper_r48.json','assets/projectseele/mesh/seele_desk_r48.mesh.json',
 'assets/projectseele/blockstates/entry_plug_bridge_deck.json','assets/projectseele/blockstates/entry_plug_bridge_guard.json')
def equal_streams(a,b):
 while True:
  left,right=a.read(1048576),b.read(1048576)
  if left!=right:return False
  if not left:return True
def equal_files(a,b):
 with Path(a).open('rb')as left,Path(b).open('rb')as right:return equal_streams(left,right)
def selected_resources(overlay):
 overlay=Path(overlay).resolve();result={}
 for top in TOPS:
  for p in sorted((overlay/top).rglob('*')):
   if p.is_file():
    if p.is_symlink():raise ValueError('Selected resource symlink: '+str(p))
    name=p.relative_to(overlay).as_posix()
    if '..'in p.relative_to(overlay).parts:raise ValueError('Unsafe selected resource: '+name)
    result[name]=p
 if len(result)!=len({n.lower()for n in result}):raise ValueError('Case-colliding selected resources')
 if not result:raise ValueError('Empty selected R48 overlay')
 return result
def sound_files(overlay):
 path=Path(overlay)/'assets/projectseele/sounds.json';events=json.loads(path.read_text('utf-8-sig'));required=set()
 for event,row in events.items():
  for item in row.get('sounds',[]):
   name=item if isinstance(item,str)else item['name'];kind='file'if isinstance(item,str)else item.get('type','file')
   namespace,_,value=name.partition(':')
   if not value:namespace,value='projectseele',namespace
   if namespace!='projectseele':continue
   if kind=='event':
    if value not in events:raise ValueError('Selected sound refers to absent event: '+event+' -> '+value)
    continue
   target='assets/projectseele/sounds/'+value+'.ogg'
   if not(Path(overlay)/target).is_file():raise ValueError('Selected sound file missing: '+event+' -> '+target)
   required.add(target)
 return required
def validate_selected_payload(jar,overlay):
 resources=selected_resources(overlay);sounds=sound_files(overlay)
 missing=[name for name in REQUIRED_R48 if name not in resources]
 if missing:raise ValueError('Final Root R48 loader resources still pending: '+str(missing))
 with zipfile.ZipFile(jar)as z:
  names=z.namelist();seen=set(names)
  if len(names)!=len(seen):raise ValueError('Duplicate final Jar member names')
  for name,p in resources.items():
   if name not in seen or z.read(name)!=p.read_bytes():raise ValueError('Final Jar differs from selected R48 resource: '+name)
  classes=[]
  for source in (ROOT/'src/main/java/com/projectseele').rglob('*R48*.java'):
   name=source.relative_to(ROOT/'src/main/java').as_posix()[:-5]+'.class'
   if name not in seen:raise ValueError('Final Jar omits new R48 source class: '+name)
   classes.append(name)
 return {'selected_resources_exact_bytes':len(resources),'all_referenced_project_sounds_present':len(sounds),'new_R48_classes_present':len(classes),'SHA_suite_run':False,'native_or_model_acceptance_claimed':False}
def validate_identity_coverage(overlay,runtime):
 resources=selected_resources(overlay);frozen=json.loads((Path(overlay)/'ASSET_FROZEN.json').read_text('utf-8-sig'))
 expected={n for n in resources if n.startswith(('assets/','data/'))}
 if frozen.get('schema')!='projectseele.final-assets-frozen.r45.v1'or set(frozen.get('files',{}))!=expected:
  raise ValueError('ASSET_FROZEN does not cover this exact current overlay; Root must generate the final R48 identities')
 maps=Path(runtime)/'projectseele-local-maps';bundle=json.loads((maps/'combat_bundle_r44.json').read_text('utf-8-sig'))
 expected_maps={p.name for p in maps.iterdir()if p.is_file()and p.name not in('combat_bundle_r44.json','manifest.json')}
 if bundle.get('revision')!=44 or bundle.get('bundle_id')!='R48_CURRENT_SELECTED_RUNTIME'or set(bundle.get('files',{}))!=expected_maps:
  raise ValueError('Current default combat bundle identity is missing/incomplete; Root must generate the final R48 identities')
 for values in(frozen['files'],bundle['files']):
  if any(not isinstance(h,str)or len(h)!=64 or any(c not in'0123456789abcdef'for c in h)for h in values.values()):raise ValueError('Malformed formal selected-resource digest')
 return {'formal_asset_members':len(expected),'formal_default_maps_members':len(expected_maps),'coverage_checked_only':True,'hash_or_native_acceptance_claimed':False}
def inherited_texture_overrides(client):
 # These inherited R47 terrain/material packs are selected above mod_resources.
 # Only their established NERV panel texture overrides are permitted; no
 # stale model, animation, sound or runtime JSON can shadow the final Jar.
 stems=('nerv_floor_panel','nerv_hazard_paving','nerv_machine_edge','nerv_machine_hazard','nerv_machine_panel',
        'nerv_shaft_panel','nerv_structural_panel_side','nerv_structural_panel_top','nerv_wall_panel')
 allowed={'assets/projectseele/textures/block/'+name+suffix+'.png'for name in stems for suffix in('','_n','_s')}
 result=[]
 for pack in sorted((Path(client)/'resourcepacks').glob('*.zip')):
  with zipfile.ZipFile(pack)as z:
   members=sorted(n for n in z.namelist()if n.startswith('assets/projectseele/')and not n.endswith('/'))
   unexpected=set(members)-allowed
   if unexpected:raise ValueError('Inherited texture pack shadows final R48 model/sound/data: '+pack.name+' '+str(sorted(unexpected)))
   if members:result.append({'pack':pack.name,'higher_than_mod_resources':True,'selected_block_texture_overrides':members})
 return result
