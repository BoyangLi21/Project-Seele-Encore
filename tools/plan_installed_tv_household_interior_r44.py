"""Exact current-world full-NBT delta for the already installed household floor."""
from pathlib import Path
import argparse,json,gzip,shutil,math
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from regional_voxels import canonical_state
from compact_tv_household_r44 import author
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
def main():
 p=argparse.ArgumentParser();p.add_argument('installed',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
 d=json.loads((a.installed/'new_district.json').read_text('utf8'));b=d['buildings'][0];x,z,X,Z=b['bounds'];f=b['floor']+10;w=MeasuredWorld(WORLD);w.box((x-2,b['floor']-1,z-2),(X+4,f+5,Z+4));w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x-2,b['floor']-1,z-2),(X+4,f+5,Z+4),selected_chunks=set(w.selected)));target={};held=[]
 oldrows=[json.loads(r) for r in gzip.open(a.installed/'forward.jsonl.gz','rt',encoding='utf8')];owned={tuple(r['pos']):r for r in oldrows}
 def state(q):return target[q]['after'] if q in target else w.block(q)
 def put(q,s,owner,reason,nbt=None):
  q=tuple(map(int,q));before=w.block(q);oldtag=tags[q].snbt() if q in tags else None;s=canonical_state(s)
  if before is None or not (x<q[0]<=X and z<q[2]<Z and f<=q[1]<=f+4) and q not in owned:
   held.append(dict(pos=q,before=before,reason='Outside retained full installed component ownership'));return
  if q in tags and str(tags[q].get('id')) not in ['minecraft:bed','minecraft:sign']:
   held.append(dict(pos=q,before_nbt=oldtag,reason='Unknown existing full block entity is HARD'));return
  if s==before and oldtag==nbt:target.pop(q,None)
  else:target[q]=dict(pos=q,before=before,after=s,before_nbt=oldtag,after_nbt=nbt,owner=owner,reason=reason)
 def bed(xx,yy,zz,owner):
  for dz,part in [(0,'foot'),(-1,'head')]:
   q=(xx,yy,zz+dz);tag=tags[q].snbt() if q in tags and str(tags[q].get('id'))=='minecraft:bed' else nbtlib.Compound({'id':nbtlib.String('minecraft:bed'),'x':nbtlib.Int(xx),'y':nbtlib.Int(yy),'z':nbtlib.Int(zz+dz)}).snbt()
   put(q,f'minecraft:white_bed[facing=north,occupied=false,part={part}]',owner,'Complete real household/neighbour bed pair; unchanged original full bed NBT preserved or explicitly retired with exact inverse',tag)
 def storage(q,owner):
  tag=nbtlib.Compound({'id':nbtlib.String('minecraft:chest'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Items':nbtlib.List[nbtlib.Compound]([])}).snbt()
  put(q,'minecraft:chest[facing=east,type=single,waterlogged=false]',owner,'Actual manually usable shoe/umbrella storage cabinet beside the genkan, clear of its full doorway route',tag)
 c=author(b,state,put,bed,storage);d['rooms']=[r for r in d['rooms'] if '/floor3/' not in r['id']]+c['rooms']
 # Address semantics only: same exact exterior sign and all remaining native
 # properties are retained; a residence has no public opening-hours label.
 for q,tag in tags.items():
  if str(tag.get('id'))!='minecraft:sign' or q not in owned:continue
  copy=nbtlib.parse_nbt(tag.snbt())
  for face in ['front_text','back_text']:
   if face in copy:copy[face]['messages']=nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':s},ensure_ascii=False)) for s in ['コンフォート17','住戸・共用玄関','','']])
  put(q,w.block(q),b['id'],'Retain actual residential exterior plaque with full NBT; retire inappropriate public opening-hours text only',copy.snbt())
 a.output.mkdir(parents=True);rows=[target[q] for q in sorted(target)]
 for name,inverse in [('forward',False),('inverse',True)]:
  with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as out:
   for row in rows:
    r=dict(row)
    if inverse:r['before'],r['after']=row['after'],row['before'];r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
    out.write(json.dumps(r,ensure_ascii=False)+'\n')
 for name in ['road_authority.json','ecology_reservations.json','architecture_components.json']:shutil.copy2(a.installed/name,a.output/name)
 (a.output/'new_district.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8');before_cases=json.loads((a.installed/'native_cases.json').read_text('utf8'));retired=[r for r in before_cases if '/floor3/' in r['id']];cases=[r for r in before_cases if '/floor3/' not in r['id']]+c['cases'];(a.output/'native_cases.json').write_text(json.dumps(cases,indent=2),'utf8')
 (a.output/'tv_landmark_components.json').write_text(json.dumps(dict(components=[dict(building=b['id'],**c)],world_written=False),indent=2),'utf8')
 (a.output/'case_geometry_revisions.json').write_text(json.dumps(dict(retired_before=retired,full_room_and_public_floor_goals_reauthored=True,common_stair_routes_unchanged=True,world_written=False),indent=2),'utf8')
 (a.output/'delta_provenance.json').write_text(json.dumps(dict(installed=str(a.installed.resolve()),actual_current_world_only=True,whole_city_reapply_allowed=False,world_written=False),indent=2),'utf8')
 (a.output/'audit.json').write_text(json.dumps(dict(new_buildings=1,new_floor_planes=5,changed_cells=len(rows),held=held,rail_conflicts=[],ready=False,native_passed=False,visual_passed=False,world_written=False),indent=2),'utf8')
 (a.output/'scale_and_room_quality.json').write_text(json.dumps(dict(previous_living_square_metres=63,previous_bedrooms_square_metres=[25,30,24],previous_clear_ceiling=4,new_clear_ceiling=2.5,storey_pitch_unchanged=5,new_room_areas=[dict(room=r['id'].split('/')[-1],area=(r['bounds'][3]-r['bounds'][0]+1)*(r['bounds'][5]-r['bounds'][2]+1)) for r in c['rooms']],reference_pixel_relation='Actually viewed diagram body roughly626x534 pixels; current14x22 elongation is retired. Door/tatami/furniture metre assignments remain inference; fan80m2 is not official.',actual_entity_identities_moved=0,old_fullNBT_explicit_inverse=True,world_written=False),indent=2),'utf8')
 print('Actual installed household interior delta',len(rows),'cells','held',len(held),'fullNBT before',sum(r['before_nbt'] is not None for r in rows),'new/retained',sum(r['after_nbt'] is not None for r in rows))
if __name__=='__main__':main()
