"""Join the surveyed Tokyo-3 western/eastern avenues to the existing regional street grid.
Only author exact reversible cells; no world writes or entity/traffic edits.
"""
from pathlib import Path
import argparse,gzip,json,math
from query_blocks import read_box,iter_block_entities,AIR

SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:coarse_dirt','minecraft:gravel','minecraft:andesite'}
PAVING={'minecraft:black_concrete','minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:white_concrete','minecraft:yellow_concrete','minecraft:smooth_stone','minecraft:smooth_stone_slab','projectseele:road_asphalt_slab','projectseele:road_marking_slab','minecraft:deepslate_bricks'}
DIM='projectseele:geofront'

def main():
 a=argparse.ArgumentParser();a.add_argument('--world',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
 rows={};routes=[];relocated=[]
 for name,x0,x1 in [('tokyo_west_public_port',-256,-174),('tokyo_east_harbour_port',234,280)]:
  lo=(x0,77,190);hi=(x1,90,210);b=read_box(args.world,DIM,lo,hi);bes=dict(iter_block_entities(args.world,DIM,lo,hi))
  approved_lamps=set()
  def put(q,after,reason):
   before=b.get(q)
   if before is None or q in bes or before.split('[')[0] not in SOIL|PAVING|AIR and q not in approved_lamps:raise ValueError((name,q,before,'retained component'))
   if before!=after:rows[q]=dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,owner='r54/'+name,reason=reason)
  # The west avenue joins through one existing lamp. Move the entire measured
  # fixture two metres outside the new sidewalk instead of leaving its pole in a lane.
  for (lx,ly,lz),st in list(b.items()):
   if st!='minecraft:polished_deepslate' or not 194<=lz<=206 or not 79<=ly<=82:continue
   if 'iron_bars' not in b.get((lx,ly+1,lz),''):continue
   fixture={q:v for q,v in b.items()if lx-1<=q[0]<=lx and lz==q[2] and ly<=q[1]<=ly+6 and v.split('[')[0] in {'minecraft:polished_deepslate','minecraft:iron_bars','minecraft:lantern','minecraft:polished_blackstone_slab'}}
   if len(fixture)!=9:raise ValueError(('Incomplete declared street lamp',fixture))
   dz=(192 if lz<200 else 208)-lz
   for q,v in fixture.items():
    dest=(q[0],q[1],q[2]+dz)
    if b.get(dest,'').split('[')[0] not in SOIL|AIR:raise ValueError(('Lamp destination occupied',dest,b.get(dest)))
   approved_lamps.update(fixture)
   for q,v in fixture.items():
    put(q,'minecraft:air','Relocate complete obstructing street lamp outside the new public sidewalk')
    put((q[0],q[1],q[2]+dz),v,'Original street lamp retained as one complete fixture at the founded outer verge')
   relocated.append(dict(from_base=[lx,ly,lz],to_base=[lx,ly,lz+dz],cells=9))
  route=[]
  for x in range(x0,x1+1):
   feet=82.0 if name.startswith('tokyo_west') and x<=-247 else 81.5 if name.startswith('tokyo_west') and x<=-243 else 81.0
   y=math.ceil(feet)-1;half=feet%1!=0
   for dz in range(-6,7):
    z=200+dz
    # Both end junctions retain north/south flow; zebra marks announce the city interface.
    zebra=(x in range(-240,-234) or x in range(261,267)) and abs(dz)<=3 and dz%2==0
    line=abs(dz)==4 or dz==0 and x%12<5
    surface='minecraft:smooth_stone' if abs(dz)>=5 else 'minecraft:white_concrete' if line or zebra else 'minecraft:black_concrete'
    if half:surface=('minecraft:smooth_stone_slab' if abs(dz)>=5 else 'projectseele:road_marking_slab' if line or zebra else 'projectseele:road_asphalt_slab')+'[type=bottom,waterlogged=false]'
    put((x,y,z),surface,'Two vehicle lanes and continuous two-metre pedestrian edges join the real avenue and regional street datums')
    if y>77 and b.get((x,y-1,z),'').split('[')[0] in SOIL|AIR:put((x,y-1,z),'minecraft:stone','Continuous formed road bearing; no floating deck')
    for yy in range(math.ceil(feet),math.ceil(feet)+4):
     old=rows.get((x,yy,z),{}).get('after',b.get((x,yy,z)))
     if old not in AIR:put((x,yy,z),'minecraft:air','Four metre existing public-road headroom; preserve all other equipment')
   route.append([x+.5,feet,200.5])
  routes.append(dict(id=name,path=route,width=13,carriage_width=9,sidewalk_width=2,headroom=4))
 args.output.mkdir(parents=True,exist_ok=True)
 for name,inv in [('forward',False),('inverse',True)]:
  with gzip.open(args.output/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
   for row in rows.values():
    r=row.copy()
    if inv:r['before'],r['after']=r['after'],r['before']
    f.write(json.dumps(r)+'\n')
 (args.output/'routes.json').write_text(json.dumps(routes,indent=2),encoding='utf8')
 (args.output/'manifest.json').write_text(json.dumps(dict(world=str(args.world),dimension=DIM,cells=len(rows),routes=len(routes),relocated_lamps=relocated,native_passed=False,visual_self_review='pending',protected='No city shaft, tower, block entity or rail edits; north launch district and south mountain remain intact'),indent=2),encoding='utf8')
 print('Prepared',len(rows),'cells for',len(routes),'complete avenue interfaces')
if __name__=='__main__':main()

