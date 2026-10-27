"""Measured TV-era street facades on the existing regional building catalogue.
Only registered outer walls and attached high-level fittings; no interior, door,
road, roof access, block entity or moving-city cargo is changed.
"""
from pathlib import Path
import argparse,collections,gzip,json
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

DIM='projectseele:geofront'
WALL={'minecraft:gray_concrete','minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:smooth_sandstone'}
GLASS={'minecraft:gray_stained_glass','minecraft:light_gray_stained_glass','minecraft:black_stained_glass'}

def main():
 a=argparse.ArgumentParser();a.add_argument('--world',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--catalogue',type=Path,required=True);args=a.parse_args()
 records=json.loads(args.catalogue.read_text('utf8'))['buildings'];world=MeasuredWorld(args.world);entries=[]
 for b in records:
  if b['id'].split('/')[0]not in {'tokyo_west','tokyo_north','tokyo_south','new_hakone'}:continue
  lo,hi=b.get('actual_building_bounds',b['planned_bounds']);floor=lo[1];entries.append((b,lo,hi))
  for z in (lo[2],hi[2]):world.box((lo[0],floor,z-1),(hi[0],hi[1]+1,z+1))
  for x in (lo[0],hi[0]):world.box((x-1,floor,lo[2]),(x+1,hi[1]+1,hi[2]))
 world.load();rows={};counts=collections.Counter();done=[];held=[]
 def put(q,after,owner,reason):
  before=world.block(q)
  if before is None:raise ValueError((q,'not measured'))
  if before==after:return
  # All touched states are plain known wall/air blocks; no BE-bearing state enters this set.
  if before.split('[')[0]not in WALL|AIR:return
  rows[q]=dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,owner=owner,reason=reason)
 for b,lo,hi in entries:
  owner='r54/facade/'+b['id'];floor=lo[1];height=hi[1]-floor
  doors=b.get('public_doors',[])
  if not doors or not any('_door' in (world.block(tuple(d['pos']))or'')for d in doors):held.append({'id':b['id'],'reason':'Current registered exterior door no longer matches; preserve changed frontage'});continue
  kind=b.get('street_front',b.get('style','residential'));region=b['id'].split('/')[0]
  low_shop=height<=14 and kind in {'bookshop','coffee_house','household_store','corner_market','neighbourhood_office'}
  group='low_shop'if low_shop else'inn'if region=='new_hakone'and height<=22 else'office'if b.get('style')=='office'else'apartment'
  main={'office':'minecraft:light_gray_concrete','apartment':'minecraft:white_concrete','inn':'minecraft:light_gray_terracotta','low_shop':'minecraft:white_terracotta'}[group]
  before_count=len(rows);fittings=0
  for axis,edge,normal in [('z',lo[2],-1),('z',hi[2],1),('x',lo[0],-1),('x',hi[0],1)]:
   start,end=(lo[0],hi[0])if axis=='z'else(lo[2],hi[2]);face='north'if axis=='z'and normal<0 else'south'if axis=='z'else'west'if normal<0 else'east'
   def q(u,y,out=0):return(u,y,edge+out*normal)if axis=='z'else(edge+out*normal,y,u)
   for u in range(start,end+1):
    for y in range(floor+1,hi[1]):
     old=world.block(q(u,y));name=(old or'').split('[')[0]
     if name not in WALL:continue
     if y<=floor+2:after='minecraft:polished_andesite'
     elif y==floor+3 and group in {'inn','low_shop'}:after='minecraft:dark_oak_planks'
     else:after=main
     put(q(u,y),after,owner,'Use-specific continuous muted plaster and durable stone plinth; inn/shop timber only at ground-storey lintel; all glazing and entrances remain')
   # Small weather hoods are attached above existing upper-storey glazing.
   # None is put over a door, on the public walking level or into a neighbour.
   for u in range(start+2,end-1):
    for y in range(floor+7,hi[1]-1):
     if world.block(q(u,y)) not in GLASS or world.block(q(u,y+1)) not in WALL:continue
     outward=q(u,y+1,1)
     if world.block(outward)not in AIR:continue
     if (u-start)%8 not in (2,3,4,5):continue
     material='minecraft:stone_brick_slab[type=bottom,waterlogged=false]'if group=='inn'else'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
     put(outward,material,owner,'Attached upper-window weather hood, clear of ground-level circulation and retained window opening');fittings+=1
   # Two compact facade-mounted ventilation cabinets sit on solid upper wall bays.
   for u in (start+1,end-1):
    y=floor+7
    if y>=hi[1]-2 or world.block(q(u,y))not in WALL or world.block(q(u,y,1))not in AIR:continue
    put(q(u,y,1),'minecraft:chiseled_quartz_block',owner,'Small fixed ventilation cabinet supported by an existing solid wall bay above public headroom');fittings+=1
  changed=len(rows)-before_count
  if changed:done.append(dict(id=b['id'],cells=changed,fixtures=fittings,palette=group));counts[region]+=1
 args.output.mkdir(parents=True,exist_ok=True)
 for name,inv in [('forward',False),('inverse',True)]:
  with gzip.open(args.output/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
   for row in rows.values():
    r=row.copy()
    if inv:r['before'],r['after']=r['after'],r['before']
    f.write(json.dumps(r)+'\n')
 manifest=dict(world=str(args.world),dimension=DIM,cells=len(rows),buildings=done,regions=dict(counts),held=held,native_passed=False,visual_self_review='pending',scope='Existing outer wall materials and attached upper-floor weather hoods; no door/glass/interior/roof/terrain edit')
 (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8');print('Prepared',len(rows),'cells',len(done),'facades',dict(counts),'held',len(held))
if __name__=='__main__':main()
