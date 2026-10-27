"""Natural shoulder relief within the existing authored Hakone ridge envelope.
The operating bench, three exits, cannon/shield route and shot corridor are
protected. Only exact existing natural soil/air changes are emitted.
"""
from pathlib import Path
import argparse,collections,gzip,json,math
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR

SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:coarse_dirt','minecraft:gravel','minecraft:andesite','minecraft:tuff','minecraft:deepslate'}
SMALL={'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:dead_bush','minecraft:dandelion','minecraft:poppy'}
DIM='projectseele:geofront'

def smooth(t):t=np.clip(t,0,1);return t*t*(3-2*t)
def point_distance(x,z,p):return np.hypot(x-p[0],z-p[2])
def line_distance(x,z,a,b):
 dx,dz=b[0]-a[0],b[2]-a[2];t=np.clip(((x-a[0])*dx+(z-a[2])*dz)/max(1e-9,dx*dx+dz*dz),0,1);return np.hypot(x-a[0]-t*dx,z-a[2]-t*dz)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--source',type=Path,required=True);a=ap.parse_args()
 original=np.load(a.source/'HEIGHTS.npz');ox,oz=map(int,original['origin']);nz,nx=original['after'].shape
 lo=(ox,144,oz);hi=(ox+nx-1,239,oz+nz-1);world=MeasuredWorld(a.world);world.box(lo,hi);world.load()
 top=np.full((nz,nx),-32768,np.int16);foreign=np.zeros((nz,nx),bool)
 for (cx,sy,cz),(palette,ids)in world.tiles.items():
  bx,bz=cx*16,cz*16;lx,lz=max(ox,bx),max(oz,bz);hx,hz=min(hi[0]+1,bx+16),min(hi[2]+1,bz+16)
  if lx>=hx or lz>=hz:continue
  arr=ids.reshape(16,16,16)[:,lz-bz:hz-bz,lx-bx:hx-bx];names=[s.split('[')[0]for s in palette]
  natural=[i for i,n in enumerate(names)if n in SOIL];other=[i for i,n in enumerate(names)if n not in SOIL|SMALL|AIR]
  ys=np.arange(sy*16,sy*16+16)[:,None,None];sl=np.s_[lz-oz:hz-oz,lx-ox:hx-ox]
  top[sl]=np.maximum(top[sl],np.where(np.isin(arr,natural),ys,-32768).max(0));foreign[sl]|=np.isin(arr,other).any(0)
 z,x=np.mgrid[oz:oz+nz,ox:ox+nx];site=json.loads((a.world/'tv_encounter_sites_r45.json').read_text('utf8'))['sites']['ramiel'];protected=np.zeros(top.shape,bool)
 for px in(-1370,-1250,-1130):protected|=np.hypot(x-px,z+1520.5)<40
 paths=list(site['eva_access_routes'].values())+[site['cover_after_supply_route']]
 original_plan=json.loads((a.source/'PLAN.json').read_text('utf8'));paths+=list(original_plan['eva_access_routes'].values())
 for path in paths:
  for aa,bb in zip(path,path[1:]):protected|=line_distance(x,z,aa,bb)<18
 for key in('hero','cover','shield_wait_port'):protected|=point_distance(x,z,site[key])<47
 shot_corridor=line_distance(x,z,site['hero'],site['angel'])<60
 protected|=(x>=-1294)&(x<=-1209)&(z>=-1444)&(z<=-1351)
 protected|=(x>=-1327)&(x<=-1285)&(z>=-1395)&(z<=-1347)
 # Preserve existing trees and every device plus a local scenery separation.
 occupied=np.argwhere(foreign)
 for iz,ix in occupied:
  protected[max(0,iz-7):min(nz,iz+8),max(0,ix-7):min(nx,ix+8)]=True
 edge=np.minimum.reduce([x-ox,ox+nx-1-x,z-oz,oz+nz-1-z]);valid=(top>=145)&(top<=215)&(edge>24)&original['active']&~protected
 relief=np.zeros(top.shape,float)
 for px,pz,rx,rz,h in[(-1468,-1432,88,112,9),(-1450,-1590,100,80,13),(-1260,-1680,145,65,15),(-1035,-1545,80,100,10),(-1080,-1268,95,70,9)]:
  r2=((x-px)/rx)**2+((z-pz)/rz)**2;relief=np.maximum(relief,h*np.maximum(0,1-r2)**1.7)
 # Distance from every immutable interface, including irregular original landscape masks.
 # Limiting added relief by this distance prevents a new vertical seam at its edge.
 distance=np.where(valid,64,0).astype(np.int16)
 for _ in range(40):
  old_distance=distance.copy()
  distance[1:]=np.minimum(distance[1:],old_distance[:-1]+1)
  distance[:-1]=np.minimum(distance[:-1],old_distance[1:]+1)
  distance[:,1:]=np.minimum(distance[:,1:],old_distance[:,:-1]+1)
  distance[:,:-1]=np.minimum(distance[:,:-1],old_distance[:,1:]+1)
 cut=np.zeros(top.shape,float)
 for px,pz,rx,rz,h in[(-1355,-1402,70,108,11),(-1190,-1295,95,75,12),(-1410,-1470,58,105,8),(-1090,-1438,85,100,9)]:
  r2=((x-px)/rx)**2+((z-pz)/rz)**2;cut=np.maximum(cut,h*np.maximum(0,1-r2)**1.7)
 relief=np.where(shot_corridor,0,relief)-cut
 limit=np.maximum(0,distance-1)*.45;relief=np.clip(relief,-limit,limit)
 minimum=np.maximum(145,original['before'])
 target=np.where(valid,np.maximum(minimum,np.minimum(220,top+np.rint(relief))),top).astype(np.int16);rows={};trees=[];outcrops=0
 def put(q,state,reason):
  q=tuple(map(int,q))
  before=world.block(q)
  if before is None or before.split('[')[0]not in SOIL|SMALL|AIR:raise ValueError(('Protected actual block',q,before))
  if before!=state:rows[q]=dict(pos=q,before=before,after=state,before_nbt=None,after_nbt=None,owner='r54/hakone_ridge',reason=reason)
 changed=np.argwhere(target!=top)
 for iz,ix in changed:
  xx,zz=ix+ox,iz+oz;old,new=int(top[iz,ix]),int(target[iz,ix])
  slope=max(abs(new-int(target[iz+dz,ix+dx]))for dx,dz in[(1,0),(-1,0),(0,1),(0,-1)])
  rocky=slope>=2 or ((xx*13+zz*7)%43<7 and new>190)
  for yy in range(max(144,min(old,new-2)),max(old,new)+1):
   state='minecraft:air'if yy>new else'minecraft:andesite'if rocky and yy>=new-1 else'minecraft:grass_block[snowy=false]'if yy==new else'minecraft:dirt'if yy>=new-2 else'minecraft:stone'
   put((xx,yy,zz),state,'Continuous low mountain-shoulder relief on measured native bearing; all exit/shot/access envelopes remain unchanged')
  if rocky:outcrops+=1
 # Irregular small broadleaf/conifer groups break the oversized circular turf edge.
 rng=np.random.default_rng(54261026)
 for zz0 in range(oz+32,oz+nz-32,19):
  for xx0 in range(ox+32,ox+nx-32,19):
   xx=xx0+int(rng.integers(-6,7));zz=zz0+int(rng.integers(-6,7));ix,iz=xx-ox,zz-oz
   if not valid[iz,ix] or shot_corridor[iz,ix] or protected[iz-4:iz+5,ix-4:ix+5].any() or rng.random()>.64:continue
   ground=int(target[iz,ix]);patch=target[iz-3:iz+4,ix-3:ix+4]
   if int(patch.max())-int(patch.min())>4 or ground>218:continue
   height=int(rng.integers(7,12));conifer=ground>192 or rng.random()<.3;wood='spruce'if conifer else'oak';need={}
   for dy in range(3,height+2):
    radius=max(1,min(3,(height+2-dy)//2))if conifer else(3 if dy<height else 2)
    for dx in range(-radius,radius+1):
     for dz in range(-radius,radius+1):
      if dx*dx+dz*dz>radius*radius+1:continue
      need[(xx+dx,ground+dy,zz+dz)]=f'minecraft:{wood}_leaves[distance=1,persistent=true,waterlogged=false]'
   for dy in range(1,height+1):need[(xx,ground+dy,zz)]=f'minecraft:{wood}_log[axis=y]'
   if any(world.block(q)not in AIR|SMALL or q in rows for q in need):continue
   for q,s in need.items():put(q,s,'Founded mixed mountain woodland outside all equipment and EVA approach envelopes')
   trees.append(dict(root=[xx,ground+1,zz],height=height,species=wood))
 a.output.mkdir(parents=True,exist_ok=True)
 for name,inv in [('forward',False),('inverse',True)]:
  with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
   for row in rows.values():
    r=row.copy()
    if inv:r['before'],r['after']=r['after'],r['before']
    f.write(json.dumps(r)+'\n')
 np.savez_compressed(a.output/'height_preview.npz',origin=[ox,oz],before=top,after=target,protected=protected)
 manifest=dict(world=str(a.world),dimension=DIM,cells=len(rows),changed_ground_columns=len(changed),rocky_surface_columns=outcrops,trees=trees,bounds=[lo,hi],source_landscape=str(a.source),native_passed=False,visual_self_review='pending',protected=['Three actual exits plus 40m radius, beyond original 30m flat ground','Every actual 13m EVA route plus 18m width each side','Cannon/shield and 60m half-width shot corridor','Every existing tree/device and below-surface tunnel','Original 24m landscape edge'],maximum_added_relief=int((target.astype(int)-top).max()),maximum_cut=int((top.astype(int)-target).max()),references=['https://www.hakone-geopark.jp/area-guide/hakone2/009kintokiyama.html','https://www.hakone.or.jp/files/AddB016_2025060916211130996.pdf'],interpretation='Scaled original mountain-shoulder interpretation of Hakone outer-rim relief; no claim of a one-to-one surveyed real map')
 (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8');print('Prepared',len(rows),'cells,',len(changed),'relief columns,',len(trees),'trees')
if __name__=='__main__':main()
