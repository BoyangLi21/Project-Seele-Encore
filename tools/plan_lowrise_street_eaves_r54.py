"""Complete existing low-rise shop/inn eaves without replacing their authored bodies."""
from pathlib import Path
import argparse,gzip,json,collections
from query_blocks import read_box,iter_block_entities,AIR
WALL={'minecraft:light_gray_concrete','minecraft:white_concrete','minecraft:smooth_sandstone','minecraft:gray_concrete','minecraft:smooth_stone','minecraft:white_terracotta','minecraft:light_gray_terracotta'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--district',type=Path,action='append',required=True);a=ap.parse_args();rows={};done=[];held=[]
 for file in a.district:
  for b in json.loads(file.read_text('utf8'))['buildings']:
   if b['kind']not in{'local_shop','coffee_house','small_inn','shophouse','book_office'}or b['storeys']>3:continue
   x,z,X,Z=b['bounds'];f=b['floor'];door=tuple(b['door']);face=b.get('facing','south');normal={'south':(0,1),'north':(0,-1),'east':(1,0),'west':(-1,0)}[face];nx,nz=normal
   lo=(x-1,f,z-1);hi=(X+1,f+6,Z+1);cells=read_box(a.world,'projectseele:geofront',lo,hi);bes=dict(iter_block_entities(a.world,'projectseele:geofront',lo,hi))
   if '_door'not in cells.get(door,''):held.append(dict(id=b['id'],reason='Registered current door differs; preserve changed body'));continue
   owner='r54/eaves/'+b['id'];count=len(rows)
   def put(q,s,reason):
    before=cells.get(q)
    if before is None or q in bes or before.split('[')[0]not in WALL|AIR:return
    if before!=s:rows[q]=dict(pos=q,before=before,after=s,before_nbt=None,after_nbt=None,owner=owner,reason=reason)
   axis=range(x+1,X)if nz else range(z+1,Z)
   def point(u,y,out=0):return(u,y,(Z if nz>0 else z)+nz*out)if nz else((X if nx>0 else x)+nx*out,y,u)
   for u in axis:
    fascia=point(u,f+3)
    if cells.get(fascia)in WALL:put(fascia,'minecraft:dark_oak_planks','Ground-floor timber shop/inn fascia below retained upper-storey plaster, with original signage and glazing')
    attach=point(u,f+4);eave=point(u,f+4,1)
    if cells.get(attach)in WALL and cells.get(eave)in AIR:
     opposite={'south':'north','north':'south','east':'west','west':'east'}[face]
     put(eave,f'minecraft:dark_oak_stairs[facing={opposite},half=bottom,shape=straight,waterlogged=false]','One-metre attached sloping timber eave above existing entrance headroom; no sidewalk support post')
   if len(rows)>count:done.append(dict(id=b['id'],kind=b['kind'],cells=len(rows)-count,door=list(door),facing=face))
 a.output.mkdir(parents=True,exist_ok=True)
 for name,inv in [('forward',False),('inverse',True)]:
  with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
   for row in rows.values():
    r=row.copy()
    if inv:r['before'],r['after']=r['after'],r['before']
    f.write(json.dumps(r)+'\n')
 m=dict(world=str(a.world),dimension='projectseele:geofront',cells=len(rows),buildings=done,held=held,native_passed=False,visual_self_review='pending',scope='Existing named low-rise shop and inn facade/eave only; actual doors, signage full NBT, glazing, rooms, roofs and public paths retained')
 (a.output/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf8');print('Prepared',len(rows),'cells',len(done),'shops/inns;',len(held),'changed sites retained')
if __name__=='__main__':main()
