"""Exact delta from the installed compact household; all room tops close."""
from pathlib import Path
import argparse,json,gzip,shutil,math
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from regional_voxels import canonical_state
from tv_apartment_finish_r44 import author
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
def main():
 p=argparse.ArgumentParser();p.add_argument('installed',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
 d=json.loads((a.installed/'new_district.json').read_text('utf8'));b=d['buildings'][0];x,z,X,Z=b['bounds'];f=b['floor']+10;w=MeasuredWorld(WORLD);w.box((x-1,f-1,z-1),(X+3,f+5,Z+3));w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x-1,f-1,z-1),(X+3,f+5,Z+3),selected_chunks=set(w.selected)));target={};held=[]
 base_cases=json.loads((a.installed/'native_cases.json').read_text('utf8'));protected=set()
 for c in base_cases:
  if '/stairs' not in c['id'] and '/roof' not in c['id']:continue
  for start,end in zip(c['path'],c['path'][1:]):
   steps=max(1,math.ceil(math.dist(start,end)*5))
   for i in range(steps+1):
    p=[start[k]+(end[k]-start[k])*i/steps for k in range(3)]
    for xx in range(math.floor(p[0]-.31),math.floor(p[0]+.31)+1):
     for zz in range(math.floor(p[2]-.31),math.floor(p[2]+.31)+1):
      for yy in range(math.floor(p[1]),math.ceil(p[1]+1.9)):protected.add((xx,yy,zz))
 def state(q):return target[q]['after'] if q in target else w.block(q)
 def put(q,s,owner,reason):
  q=tuple(q);old=w.block(q);tag=tags[q].snbt() if q in tags else None;s=canonical_state(s)
  if old is None or q in tags:held.append(dict(pos=q,state=old,reason='Existing full block entity is protected; finish cannot overwrite it'));return
  if old==s:target.pop(q,None)
  else:target[q]=dict(pos=q,before=old,after=s,before_nbt=tag,after_nbt=None,owner=owner,reason=reason)
 component=author(b,state,put,protected);a.output.mkdir(parents=True)
 for name,inverse in [('forward',False),('inverse',True)]:
  with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as out:
   for q in sorted(target):
    r=dict(target[q])
    if inverse:r['before'],r['after']=r['after'],r['before'];r['before_nbt'],r['after_nbt']=r.get('after_nbt'),r.get('before_nbt')
    out.write(json.dumps(r,ensure_ascii=False)+'\n')
 for name in ['new_district.json','road_authority.json','ecology_reservations.json','architecture_components.json','native_cases.json']:shutil.copy2(a.installed/name,a.output/name)
 (a.output/'tv_landmark_components.json').write_text(json.dumps(dict(components=[dict(building=b['id'],**component)],world_written=False),indent=2),'utf8')
 (a.output/'audit.json').write_text(json.dumps(dict(new_buildings=1,new_floor_planes=5,changed_cells=len(target),held=held,rail_conflicts=[],ready=False,native_passed=False,visual_passed=False,world_written=False),indent=2),'utf8')
 (a.output/'delta_provenance.json').write_text(json.dumps(dict(installed=str(a.installed.resolve()),actual_current_world_only=True,whole_city_reapply_allowed=False,all_existing_fullNBT_untouched=True,original_actor_identities_untouched=True,world_written=False),indent=2),'utf8')
 (a.output/'whole_partition_finish.json').write_text(json.dumps(dict(producer=str(Path(__file__).resolve()),component=component,held=held,native_furniture_shape_source=str((ROOT/'artifacts/rebuild_r44/city_expansion/another_furniture_home_native_v1').resolve()),world_written=False),indent=2),'utf8');print('Complete current household finish',len(target),'cells','held',len(held))
if __name__=='__main__':main()
