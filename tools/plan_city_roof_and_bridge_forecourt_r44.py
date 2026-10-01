"""Correct an uninstalled district's roof skin and complete founded wet-edge court.

The shallow existing water remains intact below an explicit reinforced concrete
deck/beam frame. This is engineering inference, never an accidental floor hole.
"""
from pathlib import Path
import argparse,json,gzip,shutil
from collections import Counter
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from regional_voxels import canonical_state
from city_roof_r44 import compact_roof
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
def main():
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
 rows=[json.loads(s) for s in gzip.open(a.source/'forward.jsonl.gz','rt',encoding='utf8')];target={tuple(r['pos']):r for r in rows};d=json.loads((a.source/'new_district.json').read_text('utf8'));w=MeasuredWorld(WORLD)
 x0,x1,z0,z1=d['bounds'];w.box((x0-16,40,z0-16),(x1+16,220,z1+16));w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x0-16,40,z0-16),(x1+16,220,z1+16),selected_chunks=set(w.selected)));held=[];revision=[]
 def state(q):return target[q]['after'] if q in target else w.block(q)
 def put(q,s,owner,reason):
  q=tuple(q);before=w.block(q);old=state(q)
  if before is None or q in tags or (before.split('[')[0] not in AIR|{'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:grass','minecraft:tall_grass','minecraft:smooth_stone','minecraft:stone_bricks','minecraft:stone_slab'} and q not in target):held.append(dict(pos=q,state=before,reason=reason));return
  s=canonical_state(s)
  if old==s:return
  revision.append(dict(pos=q,previous_candidate=old,revised=s,reason=reason))
  if s==before:target.pop(q,None)
  else:target[q]=dict(pos=q,before=before,after=s,before_nbt=None,after_nbt=None,owner=owner,reason=reason)
 roofs=[compact_roof(b,state,put) for b in d['buildings'] if b['kind']=='compact_home']
 b=next(b for b in d['buildings'] if b['id'].endswith('/11'));x,z,X,Z=b['bounds'];f=b['floor'];owner=b['id'];missing=[];water_before=[]
 for xx in range(x-3,X+4):
  for zz in range(-705,z):
   if state((xx,f,zz)) not in AIR:continue
   missing.append((xx,zz))
   for yy in range(40,f):
    if 'minecraft:water' in (w.block((xx,yy,zz)) or ''):water_before.append(dict(pos=[xx,yy,zz],state=w.block((xx,yy,zz))))
   put((xx,f,zz),'minecraft:smooth_stone',owner,'Whole explicit wet-edge concrete forecourt deck above retained water; former accidental AIR floor retired')
 # The entire contiguous deck frame spans into the already founded dry
 # frontage and eight retained masonry returns, with two-deep concrete ribs.
 # No water level or water cell is filled. Below-water vertical piles are
 # neither fabricated nor claimed; its dry abutments carry the actual frame.
 beams=[]
 for xx in range(x-3,X+4):
  for zz in range(-705,z):
   for yy in [f-2,f-1]:
    q=(xx,yy,zz);old=state(q)
    if old in AIR:put(q,'minecraft:smooth_stone',owner,'Continuous two-metre-deep reinforced concrete forecourt beam frame joins the retained founded masonry/dry building plinth');beams.append(q)
 water_preserved=all(state(tuple(v['pos']))==v['state'] for v in water_before);assert water_preserved
 a.output.mkdir(parents=True)
 final=[target[q] for q in sorted(target)]
 for name,inverse in [('forward',False),('inverse',True)]:
  with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as out:
   for row in final:
    r=dict(row)
    if inverse:r['before'],r['after']=row['after'],row['before'];r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
    out.write(json.dumps(r,ensure_ascii=False)+'\n')
 for name in ['native_cases.json','road_authority.json','source_shape_candidates.json','architecture_components.json']:
  if (a.source/name).exists():shutil.copy2(a.source/name,a.output/name)
 (a.output/'new_district.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')
 parcels=json.loads((a.source/'parcel_components.json').read_text('utf8'));existing={tuple(c['pos']) for c in parcels['full_court_columns']}
 parcels['full_court_columns'].extend(dict(pos=q,native_feet=f+1,owner=owner,role='Whole declared wet-edge supported concrete forecourt above preserved native water') for q in missing if q not in existing)
 (a.output/'parcel_components.json').write_text(json.dumps(parcels,indent=2),'utf8')
 protect=json.loads((a.source/'ecology_reservations.json').read_text('utf8'));protect['reservations'].extend(dict(bounds=[b['bounds'][0]-1,b['roof'],b['bounds'][1]-1,b['bounds'][2]+1,b['roof']+8,b['bounds'][3]+1],owner=b['id'],role='Whole connected compact tile gable and clear eaves') for b in d['buildings'] if b['kind']=='compact_home')
 (a.output/'ecology_reservations.json').write_text(json.dumps(protect,indent=2),'utf8')
 audit=json.loads((a.source/'audit.json').read_text('utf8'));audit.update(changed_cells=len(final),held=held,world_written=False,ready=False,native_passed=False,visual_passed=False)
 (a.output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),'utf8')
 (a.output/'geometry_revision.json').write_text(json.dumps(dict(source=str(a.source.resolve()),producer=str(Path(__file__).resolve()),roofs=roofs,whole_forecourt_missing_floor_columns=len(missing),continuous_beam_cells=len(beams),retained_water_cells=len(water_before),all_retained_water_unchanged=water_preserved,deck_span_engineering_inferred=True,maximum_transverse_span_metres=11,full_source_state_revisions=revision,held=held,world_written=False,visual_passed=False),indent=2),'utf8')
 print('Connected compact roofs',len(roofs),'whole bridge court repaired',len(missing),'beamcells',len(beams),'water preserved',len(water_before),'cells',len(final),'held',len(held))
if __name__=='__main__':main()
