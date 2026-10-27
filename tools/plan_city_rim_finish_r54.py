"""Finish fixed street-side rims around the installed one hundred moving-city footprints.
The active cargo/ground-hatch mask, controllers and original below-surface anchors
are excluded. No city state, entities, topology or movement recipes are changed.
"""
from pathlib import Path
import argparse,json,gzip,collections
import nbtlib
from query_blocks import read_box,iter_block_entities

FLOOR={'minecraft:black_concrete','minecraft:smooth_stone','minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:polished_deepslate','minecraft:deepslate_tiles','projectseele:nerv_floor_panel','minecraft:orange_concrete','minecraft:yellow_concrete'}

def blockpos(v):
 n=int(v)&((1<<64)-1);x=n>>38;z=(n>>12)&((1<<26)-1);y=n&4095
 return(x-(1<<26)if x>=1<<25 else x,y-4096 if y>=2048 else y,z-(1<<26)if z>=1<<25 else z)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();dd=a.world/'dimensions/projectseele/geofront/data';top=nbtlib.load(next(dd.glob('projectseele_city_rigid_topology_r45_*.dat')))['data'];towers=[];moving=set()
 for n,t in enumerate(top['Towers']):
  x,y,z=blockpos(t['Centre']);f=t['Footprint'];bounds=(x+int(f['MinX']),x+int(f['MaxX']),z+int(f['MinZ']),z+int(f['MaxZ']));towers.append((n,bounds))
  x0,x1,z0,z1=bounds;moving.update((xx,zz)for xx in range(x0,x1+1)for zz in range(z0,z1+1))
 xmin=min(t[1][0]for t in towers)-1;xmax=max(t[1][1]for t in towers)+1;zmin=min(t[1][2]for t in towers)-1;zmax=max(t[1][3]for t in towers)+1
 b=read_box(a.world,'projectseele:geofront',(xmin,80,zmin),(xmax,81,zmax));bes=dict(iter_block_entities(a.world,'projectseele:geofront',(xmin,80,zmin),(xmax,81,zmax)));rows={};done=[];preserved=collections.Counter()
 for n,(x0,x1,z0,z1)in towers:
  x0-=1;x1+=1;z0-=1;z1+=1;corners=[(x0,z0),(x1,z0),(x0,z1),(x1,z1)];coords={(x,z)for x in range(x0,x1+1)for z in(z0,z1)}|{(x,z)for z in range(z0,z1+1)for x in(x0,x1)};count=len(rows)
  for x,z in coords:
   q=(x,80,z);old=b.get(q)
   if(x,z)in moving:preserved['other_moving_mask']+=1;continue
   if q in bes:preserved['original_block_entity']+=1;continue
   if old not in FLOOR:preserved['non_template_static_component']+=1;continue
   near=min(abs(x-cx)+abs(z-cz)for cx,cz in corners)
   # Full-width walking floor stays a full cube; only its material changes.
   after='projectseele:nerv_hazard_paving'if near<=3 else'projectseele:nerv_floor_panel'
   if old!=after:rows[q]=dict(pos=q,before=old,after=after,before_nbt=None,after_nbt=None,owner=f'r54/city_static_rim/{n}',reason='Fixed street-side service rim and corner hazard bands outside the exact moving city/cap footprint')
  done.append(dict(tower=n,cells=len(rows)-count,static_rim_bounds=[x0,z0,x1,z1]))
 a.out.mkdir(parents=True,exist_ok=True);forward=list(rows.values());inverse=[]
 for row in forward:
  r=row.copy();r['before'],r['after']=r['after'],r['before'];inverse.append(r)
 for name,rs in [('forward',forward),('inverse',inverse)]:
  with gzip.open(a.out/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
   for r in rs:f.write(json.dumps(r)+'\n')
 m=dict(schema='projectseele.r54.city-static-rims.v1',world=str(a.world),dimension='projectseele:geofront',static_cells=len(rows),towers=done,preserved=dict(preserved),metadata_preconditions=[],world_tables=[],world_written=False,native_passed=False,visual_self_review='pending',moving_floor_intersections=0,scope='Fixed Y80 perimeters only; exact 100 cargo/hatch masks, controllers, private templates and future motion identity remain untouched')
 for name,v in [('forwardPatch.json',forward),('inversePatch.json',inverse),('positiveEditMask.json',[r['pos']for r in forward]),('installation_manifest.json',m)]:
  (a.out/name).write_text(json.dumps(v,ensure_ascii=False,separators=(',',':')),encoding='utf8')
 print('Prepared',len(rows),'static rim cells for',len(towers),'declared moving footprints',dict(preserved))
if __name__=='__main__':main()
