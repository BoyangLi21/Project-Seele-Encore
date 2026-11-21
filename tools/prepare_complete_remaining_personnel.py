"""Finite Root-review candidates for retained compact lift and missing HQ rings.
Never writes WORLD, executes legacy main(), or installs readiness metadata.
"""
from pathlib import Path
import argparse,collections,gzip,json
import nbtlib,numpy as np
from query_blocks import read_box,iter_block_entities,AIR
from prepare_complete_main_lift_civil import STRUCT,FLOOR,WALL,points,need,save,sha

ROOT=Path(__file__).resolve().parents[1]
DIM='projectseele:geofront'

class ReadPlan:
 def __init__(self,world):self.world=world;self.before={};self.tags={};self.after={};self.owners={};self.holds=[]
 def read(self,lo,hi):self.before.update(read_box(self.world,DIM,lo,hi));self.tags.update(iter_block_entities(self.world,DIM,lo,hi))
 def old(self,p):
  p=tuple(p)
  if p not in self.before:self.read(p,p)
  need(p in self.before,'Missing measured cell '+str(p));return self.before[p]
 def put(self,p,s,owner):p=tuple(p);self.old(p);self.after[p]=s;self.owners[p]=owner
 def final(self,p):return self.after.get(tuple(p),self.old(p))
 def export(self,out):
  rows=[dict(pos=p,before=self.old(p),after=s,owner=self.owners[p])for p,s in sorted(self.after.items())if s!=self.old(p)]
  save(out/'BLOCK_PATCH.json.gz',dict(world_written=False,cells=rows,inverse=[dict(pos=r['pos'],before=r['after'],after=r['before'])for r in rows]))
  save(out/'FULL_COMPOSED_STATES.json.gz',[dict(pos=p,before=self.old(p),after=s,owner=self.owners[p])for p,s in sorted(self.after.items())])
  save(out/'HOLDS.json',self.holds);return rows

def compact(world,out,metadata):
 c=ReadPlan(world);lo=(88,-470,-85);hi=(114,-310,-15);c.read(lo,hi)
 frozen=ROOT/'.Codex/map_complete_20261013/coordinate_lift_audit/whole_routes_v1/final_evidence/frozen_lab_evidence'
 baseline=read_box(frozen,DIM,lo,hi)
 # Exact old authored component bounds from retire_old_observation_r52 are
 # reviewed here against the real current world. We never invoke that main.
 regions=[('vacated_original_upper_gallery',(88,-371,-84),(113,-363,-16)),
          ('vacated_original_middle_gallery',(95,-398,-84),(114,-388,-42)),
          ('vacated_original_upper_shaft',(89,-436,-56),(99,-363,-48))]
 for x in(89,112):
  for z in(-82,-18):regions.append(('vacated_gallery_support',(x,-467,z),(x,-372,z)))
 owned=set();protected=set(points((88,-470,-54),(89,-310,-18)))
 for owner,a,b in regions:
  for p in points(a,b):
   if p in protected:continue
   before=c.old(p)
   if before!=baseline.get(p)and before not in AIR|{'minecraft:stone','minecraft:grass_block[snowy=false]'}:
    c.holds.append(dict(kind='changed_foreign_cell_in_old_component',pos=p,before=before,frozen=baseline.get(p)))
   target='minecraft:air'if p[1]>-467 else'minecraft:grass_block[snowy=false]'if p[1]==-467 else'minecraft:stone'
   c.put(p,target,owner);owned.add(p)
 native=json.loads((metadata/'NATIVE_BE_PATCH.json').read_text('utf8'))['operations']
 cars=json.loads((metadata/'ORIGINAL_CARS.json').read_text('utf8'))['cars'];need(len(cars)==1,'One original compact car required');car=cars[0]
 need(car['parked_before']==-394 and car['parked_after']==-442,'Exact original compact-car move required')
 old_be={tuple(r['source']):r for r in native};new_be={tuple(r['target']):r for r in native if r['target']is not None}
 for r in native:
  p=tuple(r['source']);t=c.tags.get(p)
  need(t is not None and t.snbt()==r['before_nbt'],'Native original compact before changed '+str(p))
 for row in car['cells']:
  p,q=tuple(row['source']),tuple(row['target']);need(c.old(p)==row['state'],'Original car cell differs')
  need(p in owned,'Original car source outside explicitly retired shaft')
  if q in c.tags and q not in old_be:c.holds.append(dict(kind='foreign_BE_at_original_car_target',pos=q,nbt=c.tags[q].snbt()))
  if c.old(q)not in AIR|{'minecraft:light_gray_stained_glass','minecraft:gray_stained_glass'}:
   c.holds.append(dict(kind='occupied_original_car_target',pos=q,state=c.old(q)))
  c.put(q,row['state'],'move_original_compact_150_cell_car_once')
 # Fixed top cap stays above the complete original car (+4), leaving the
 # intervening air cell. The original surface-well edge at x88/89 is retained.
 for p in points((90,-436,-56),(99,-436,-48)):c.put(p,STRUCT,'retained_two_stop_shaft_top_cap')
 hardware=json.loads((metadata/'CIVIL_DEVICE_INTERFACE.json').read_text('utf8'))
 for floor in hardware['retired_landing_hardware']:
  for row in floor['hardware']:
   p=tuple(row['position']);need(c.old(p)==row['state'],'Retired native hardware changed')
   if p in protected:continue
   if row['state']not in AIR:c.put(p,'minecraft:air','retired_exact_call_or_leaf');owned.add(p)
 # Current car was parked closed; keep that complete native cabin state.
 # The landing is allowed to be open because the original car is now present.
 for row in hardware['interfaces'][0]['landing_open_state']:
  p=tuple(row['position']);need(c.old(p)==row['before'],'Station landing before changed');c.put(p,row['after'],'station_landing_with_original_car')
 for p,t in c.tags.items():
  if c.after.get(p,c.old(p))!=c.old(p)and p not in old_be:
   c.holds.append(dict(kind='other_BE_in_retirement_mask',pos=p,nbt=t.snbt()))
 # No broad native source mutation; the two retained controllers and all
 # lower laboratory/metro circulation are unchanged except station label.
 be=[]
 for p in sorted(set(old_be)|set(new_be)):
  before=c.tags.get(p);after=None
  if p in new_be:after=nbtlib.parse_nbt(new_be[p]['after_nbt'])
  elif p not in old_be:after=before
  be.append(dict(pos=p,before_nbt=None if before is None else before.snbt(),after_nbt=None if after is None else after.snbt(),state=c.final(p)))
 failures=[];target_car={tuple(r['target'])for r in car['cells']}
 shapes=json.loads((world/'native_collision_shapes.json').read_text('utf8'))
 def boxes(s):
  if s in AIR:return[]
  if s not in shapes:return None
  return shapes[s]
 for p in points((91,-469,-54),(95,-437,-50)):
  if p in target_car:continue
  b=boxes(c.final(p))
  if b is None or b:failures.append(dict(kind='remaining_native_car_sweep_obstruction',pos=p,state=c.final(p)))
 for p in protected:
  if p in c.after and c.final(p)!=c.old(p):failures.append(dict(kind='original_surface_well_edge_changed',pos=p))
 for row in car['cells']:
  if c.final(row['target'])!=row['state']:failures.append(dict(kind='car_copy_mismatch',pos=row['target']))
 for key in('96;-52',):
  caps=nbtlib.load(world/'dimensions/projectseele/geofront/data/capabilities.dat')['data']['movingelevators:elevator_groups']
  group=json.loads((metadata/'NATIVE_GROUP_PATCH.json').read_text('utf8'))['operations'][0]
  need(caps[key].snbt()==group['before_snbt'],'Compact current capability differs')
 rows=c.export(out)
 save(out/'BLOCK_ENTITY_FINAL.json',dict(rows=be,world_written=False))
 save(out/'OWNERSHIP.json',dict(retired_components=[dict(id=n,box=[a,b])for n,a,b in regions],retained_original_well_edge=[[88,-470,-54],[89,-310,-18]],
  source_car_box=car['source_box'],target_car_box=car['target_box'],original_station_tracks_and_data_untouched=True,lower_lab_connection_untouched=True))
 save(out/'STATIC_VALIDATION.json',dict(failures=failures,original_car_voxels=150,source_car_duplicated=False,native_game_verified=False,
  limitations=['Closed original car leaves require real call/open/board operation after the final directory is installed']))
 save(out/'REPORT.json',dict(world=str(world),world_written=False,ready=False,changed_cells=len(rows),composed_cells=len(c.after),
  old_floors=[-468,-442,-394,-370],final_floors=[-468,-442],native_be_endpoints=len(be),holds=len(c.holds),static_failures=len(failures),
  original_car_move=[-394,-442],car_dimensions=[5,6,5],metadata_candidate=str(metadata),source_script_sha256=sha(Path(__file__).read_bytes())))
 print(json.dumps(dict(kind='compact',changed=len(rows),holds=len(c.holds),failures=len(failures),world_written=False)))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--metadata',type=Path,required=True);args=p.parse_args()
 out=args.out.resolve();need(out.is_relative_to((ROOT/'.Codex').resolve())and not out.exists(),'Fresh .Codex output required');out.mkdir(parents=True);compact(args.world.resolve(),out,args.metadata.resolve())

if __name__=='__main__':main()
