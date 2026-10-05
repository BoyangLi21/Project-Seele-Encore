"""Root identity generation for the selected overlay/runtime. Default plan never hashes/writes."""
from pathlib import Path
import argparse,hashlib,json,os,uuid
from r48_selected_payload import selected_resources,sound_files,REQUIRED_R48
ROOT=Path(__file__).resolve().parents[1];R48=ROOT/'artifacts/rebuild_r48'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def write(p,value):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.pending-'+uuid.uuid4().hex)
 tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8');os.replace(tmp,p)
def main():
 p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,default=R48/'assets');p.add_argument('--runtime',type=Path,default=R48/'runtime');p.add_argument('--out',type=Path,required=True);p.add_argument('--write-identities',action='store_true');a=p.parse_args()
 a.assets,a.runtime,a.out=(x.resolve()for x in(a.assets,a.runtime,a.out))
 if any(not x.is_relative_to(R48.resolve())for x in(a.assets,a.runtime,a.out)):raise ValueError('Use selected R48 artifact roots only')
 resources=selected_resources(a.assets);sounds=sound_files(a.assets);maps=a.runtime/'projectseele-local-maps';owner=a.runtime/'config/projectseele-runtime-r45.properties'
 if not owner.is_file()or not maps.is_dir():raise ValueError('Selected runtime owner/local-maps missing')
 from release_r45_contract import runtime_owner_config
 runtime_owner_config(owner.read_bytes())
 # CombatMotionResourcesR44 resolves only root-level names in the selected
 # default bundle. Its manifest must not recursively bind itself.
 inputs={f.name:f for f in sorted(maps.iterdir())if f.is_file()and f.name not in('combat_bundle_r44.json','manifest.json')}
 for name in('eva_body_r44.json','eva_gameplay_r44_0.json','eva_gameplay_r44_1.json','eva_gameplay_r44_2.json','eva_gameplay_r44_3.json','eva_gameplay_r44_4.json','first_battle_r44.json','articulated_bodies_r35.json'):
  if name not in inputs:raise ValueError('Current default runtime loader input missing: '+name)
 pending=[name for name in REQUIRED_R48 if name not in resources]
 plan={'schema':'projectseele.r48.selected-resource-identity-plan.v1','assets':str(a.assets),'runtime':str(a.runtime),'asset_entries':len(resources),'project_sound_files':len(sounds),'default_maps_files':sorted(inputs),'Root_loader_resources_pending':pending,'outputs':[str(a.assets/'ASSET_FROZEN.json'),str(maps/'combat_bundle_r44.json')],'world_written':False,'native_pass_claimed':False,'hashes_generated':False,'prepared_only':not a.write_identities}
 if not a.write_identities:print(json.dumps(plan,ensure_ascii=False,indent=2));return
 if pending:raise ValueError('Root model-loader resources must be completed before the final identity generation: '+str(pending))
 if a.out.exists():raise ValueError('Preserve earlier identity receipt; select a new --out')
 a.out.mkdir(parents=True)
 selected={n:digest(f)for n,f in resources.items()if n.startswith(('assets/','data/'))}
 recipe={'schema':'projectseele.r48.actual-selected-identity-inputs.v1','assets':str(a.assets),'runtime':str(a.runtime),'selected_resources':selected,'owner_config':{'path':str(owner),'sha256':digest(owner)},'maps':{n:digest(f)for n,f in inputs.items()},'world_source_authority':str(R48/'construction/SEELE_R48_WORLD'),'world_copied':False,'world_hashes_computed':False,'native_pass_claimed':False}
 write(a.out/'SELECTED_INPUTS.json',recipe)
 frozen={'schema':'projectseele.final-assets-frozen.r45.v1','recipe_sha256':digest(a.out/'SELECTED_INPUTS.json'),'files':selected,'source_inputs':[{'source':str(a.out/'SELECTED_INPUTS.json'),'sha256':digest(a.out/'SELECTED_INPUTS.json')}],'user_art_accepted':False,'Java_or_native_run':False,'world_written':False}
 bundle={'revision':44,'bundle_id':'R48_CURRENT_SELECTED_RUNTIME','files':recipe['maps'],'native_or_user_acceptance':False}
 for target in(a.assets/'ASSET_FROZEN.json',maps/'combat_bundle_r44.json'):
  if target.is_file():(a.out/(target.name+'.before')).write_bytes(target.read_bytes())
 write(a.assets/'ASSET_FROZEN.json',frozen);write(maps/'combat_bundle_r44.json',bundle)
 plan.update(hashes_generated=True,prepared_only=False);write(a.out/'IDENTITY_GENERATED.json',plan);print(json.dumps(plan,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
