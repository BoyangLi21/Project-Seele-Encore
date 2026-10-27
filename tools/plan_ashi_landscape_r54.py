"""Author the commissioned surface Lake Ashi adaptation; never write a save.

All reads use query_blocks through MeasuredWorld. Exact old states are the
positive mask and the inverse patch. Artificial columns and all y<48 stay out.
The existing west-side New Hakone remains a fictional town, not Hakone-Yumoto.
"""
from pathlib import Path
import argparse, collections, gzip, json, math
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities

SOIL={'minecraft:'+s for s in ('stone','dirt','grass_block','coarse_dirt','gravel','sand','sandstone','clay','andesite','diorite','granite','deepslate','tuff','podzol','rooted_dirt','mud')}
PLANTS={'minecraft:'+s for s in ('grass','tall_grass','fern','large_fern','dead_bush','dandelion','poppy','sugar_cane','seagrass','tall_seagrass','kelp','kelp_plant','vine','azalea','flowering_azalea','azalea_leaves','flowering_azalea_leaves','moss_carpet')}
NATURAL=SOIL|PLANTS|AIR|{'minecraft:water'}|{'minecraft:'+t+s for t in ('oak','birch','spruce','jungle','dark_oak','acacia')for s in ('_log','_leaves')}
LO=(-1232,48,944);HI=(-496,191,1776);WATER=66

def smooth(t):
 t=np.clip(t,0,1);return t*t*(3-2*t)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 w=MeasuredWorld(a.world);w.box(LO,HI);w.load();ox,_,oz=LO;nx=HI[0]-ox+1;nz=HI[2]-oz+1
 top=np.full((nz,nx),47,np.int16);highest=top.copy();foreign=np.zeros(top.shape,bool);full=np.zeros(top.shape,bool)
 for (cx,cz),status in w.status.items():
  if status=='full':full[max(0,cz*16-oz):min(nz,cz*16+16-oz),max(0,cx*16-ox):min(nx,cx*16+16-ox)]=True
 for (cx,sy,cz),(pal,ids)in w.tiles.items():
  bx,bz=cx*16,cz*16;lx,lz=max(ox,bx),max(oz,bz);hx,hz=min(HI[0]+1,bx+16),min(HI[2]+1,bz+16)
  if lx>=hx or lz>=hz:continue
  arr=ids.reshape(16,16,16)[:,lz-bz:hz-bz,lx-bx:hx-bx];names=[s.split('[')[0]for s in pal];ys=np.arange(sy*16,sy*16+16)[:,None,None];sl=np.s_[lz-oz:hz-oz,lx-ox:hx-ox]
  top[sl]=np.maximum(top[sl],np.where(np.isin(arr,[i for i,n in enumerate(names)if n in SOIL]),ys,47).max(0))
  highest[sl]=np.maximum(highest[sl],np.where(np.isin(arr,[i for i,n in enumerate(names)if n not in AIR]),ys,47).max(0))
  foreign[sl]|=np.isin(arr,[i for i,n in enumerate(names)if n not in NATURAL]).any(0)
 # A full-column artificial-object exclusion, widened beyond the road footprint.
 protected=foreign.copy()
 for dz in range(-24,25):
  for dx in range(-24,25):
   srcz=slice(max(0,-dz),min(nz,nz-dz));srcx=slice(max(0,-dx),min(nx,nx-dx));dstz=slice(max(0,dz),min(nz,nz+dz));dstx=slice(max(0,dx),min(nx,nx+dx));protected[dstz,dstx]|=foreign[srcz,srcx]
 z,x=np.mgrid[oz:oz+nz,ox:ox+nx];t=smooth((z-1120)/600);centre=-1000+170*t+12*np.sin(z/97)
 d=np.sqrt(((x-centre)/(100+130*t))**2+((z-1420)/300)**2)+.018*np.sin(z/39)+.013*np.cos(x/31)
 lake=d<1;shore=(d>=1)&(d<1.16)
 if np.any((lake|shore)&(~full|protected)):
  bad=np.argwhere((lake|shore)&(~full|protected));print('Rejected boundary',len(bad),'bounds',bad.min(0)+[oz,ox],bad.max(0)+[oz,ox],'incomplete',int(((lake|shore)&~full).sum()),'artificial',int(((lake|shore)&protected).sum()),flush=True)
  raise RuntimeError('Whole lake/shore intersects incomplete or artificial columns; no partial lake emitted')
 target=top.copy();target[lake]=WATER-np.ceil(2+10*np.sqrt(np.maximum(0,1-d[lake]))).astype(np.int16)
 target[shore]=np.rint((WATER+1)*(1-smooth((d[shore]-1)/.16))+np.maximum(top[shore],WATER+1)*smooth((d[shore]-1)/.16)).astype(np.int16)
 active=lake|shore
 # One continuous south-ward approach, with a short east-shore turnout.
 paths=[dict(id='ashi_east_approach',points=[[-560,80,960],[-590,76,1080],[-575,72,1230],[-560,72,1500],[-610,72,1660]],halfwidth=4),dict(id='ashi_view_spur',points=[[-567,72,1380],[-690,68,1380]],halfwidth=3),dict(id='ashi_north_walk',points=[[-1120,104,1020],[-1108,104,1020],[-980,80,1020],[-980,68,1100],[-970,68,1110]],halfwidth=2)]
 JOIN={'minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone','minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:yellow_concrete','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'}
 def join(q):return (abs(q[0]+560)<=12 and 952<=q[1]<=972)or(-1128<=q[0]<=-1108 and abs(q[1]-1020)<=8)
 road={}
 for path in paths:
  for aa,bb in zip(path['points'],path['points'][1:]):
   steps=max(abs(bb[0]-aa[0]),abs(bb[2]-aa[2]))
   for i in range(steps+1):
    xx,_,zz=[round(a0+(b0-a0)*i/max(1,steps))for a0,b0 in zip(aa,bb)];yy=round((aa[1]+(bb[1]-aa[1])*i/max(1,steps))*2)/2
    for dx in range(-path['halfwidth'],path['halfwidth']+1):
     for dz in range(-path['halfwidth'],path['halfwidth']+1):
      q=(xx+dx,zz+dz);ix,iz=q[0]-ox,q[1]-oz
      if not full[iz,ix]:raise RuntimeError(('Road incomplete',q))
      if lake[iz,ix]:raise RuntimeError(('Road intersects lake',q))
      # Join the authorized existing south-ward road only on its asphalt.
      if foreign[iz,ix] and not (join(q) and w.get(q[0],80 if q[1]<1000 else 104,q[1]) in JOIN):raise RuntimeError(('Road intersects an existing object',q))
      road[q]=yy
 road_mask=np.zeros(top.shape,bool);road_height=np.zeros(top.shape,np.float32)
 for (xx,zz),yy in road.items():road_mask[zz-oz,xx-ox]=True;road_height[zz-oz,xx-ox]=yy
 distance=np.where(road_mask,0,1000).astype(np.int16);near_y=road_height.copy()
 for _ in range(64):
  for dst,src in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),(np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])]:
   candidate=distance[src]+1;take=candidate<distance[dst];near_y[dst]=np.where(take,near_y[src],near_y[dst]);distance[dst]=np.minimum(distance[dst],candidate)
 width=np.minimum(64,10+2*np.abs(near_y-top));shoulder=(distance<width)&~active&~road_mask&~protected&full
 target[shoulder]=np.rint(top[shoulder]+(near_y[shoulder]-top[shoulder])*(1-smooth(distance[shoulder]/width[shoulder]))).astype(np.int16)
 active|=shoulder
 a.output.mkdir(parents=True,exist_ok=True);counts=collections.Counter();cells=0;bounds=[list(HI),list(LO)]
 with gzip.open(a.output/'forward.jsonl.gz','wt',encoding='utf8')as fw,gzip.open(a.output/'inverse.jsonl.gz','wt',encoding='utf8')as inv:
  def emit(q,after,reason):
   nonlocal cells
   old=w.block(q)
   if old is None:raise RuntimeError(('Unread',q))
   if old==after:return
   if old.split('[')[0]not in NATURAL:raise RuntimeError(('Artificial cell',q,old))
   r=dict(pos=q,before=old,after=after,before_nbt=None,after_nbt=None,owner='r54/ashi_surface',reason=reason)
   fw.write(json.dumps(r)+'\n');r['before'],r['after']=after,old;inv.write(json.dumps(r)+'\n');cells+=1;counts[reason]+=1
   for k in range(3):bounds[0][k]=min(bounds[0][k],q[k]);bounds[1][k]=max(bounds[1][k],q[k])
  for iz,ix in np.argwhere(active):
   xx,zz=int(ix+ox),int(iz+oz)
   if (xx,zz)in road:continue
   old,new=int(top[iz,ix]),int(target[iz,ix]);high=int(highest[iz,ix]);wet=bool(lake[iz,ix])
   if not wet and old==new:continue
   for yy in range(max(48,min(old,new)-3),max(high,new,WATER if wet else new)+1):
    after='minecraft:water[level=0]'if wet and new<yy<=WATER else'minecraft:air'if yy>new else'minecraft:gravel'if wet and yy==new else'minecraft:clay'if wet and yy>=new-2 else'minecraft:grass_block[snowy=false]'if yy==new else'minecraft:dirt'if yy>=new-2 else'minecraft:stone'
    emit((xx,yy,zz),after,'Sealed lake basin and source water'if wet else'Continuous natural shore transition')
  for (xx,zz),height in sorted(road.items()):
   new=math.ceil(height);half=height!=int(height)
   ix,iz=xx-ox,zz-oz;old=int(top[iz,ix]);high=int(highest[iz,ix]);edge=any((xx+dx,zz+dz)not in road for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)])
   if foreign[iz,ix] and join((xx,zz)):continue
   for yy in range(max(48,min(old,new)-2),max(high,new+4)+1):
    surface=('minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'if edge else'minecraft:polished_blackstone_slab[type=bottom,waterlogged=false]')if half else('minecraft:light_gray_concrete'if edge else'minecraft:black_concrete')
    after='minecraft:air'if yy>new else surface if yy==new else'minecraft:stone'
    emit((xx,yy,zz),after,'Authorized continuous south-ward to east-shore road')
 np.savez_compressed(a.output/'surface_plan.npz',origin=[ox,oz],before=top,after=target,lake=lake,shore=shore,foreign=foreign)
 manifest=dict(world=str(a.world),dimension='projectseele:geofront',cells=cells,bounds=bounds,counts=dict(counts),lake_water_y=WATER,lake_columns=int(lake.sum()),positiveEditMask='exact pos set in forward.jsonl.gz',underground_untouched_below_y=48,identity_progress_files_modified=False,native_verified=False,visual_verified=False,paths=paths,adaptation='Original compressed Lake Ashi southwest of the existing city. Existing New Hakone is an invented west-side town, not geographically Hakone-Yumoto.',references=['https://www.gsi.go.jp/kihonjohochousa/kihonjohochousa40038.html','https://www.hakone.or.jp/files/AddB016_2025060916211130996.pdf','https://www.hakone-geopark.jp/global-image/units/upfiles/20016-1-20260331202209_b69cbae61d46a1.pdf'])
 (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
 (a.output/'surface_geography_r54.json').write_text(json.dumps(dict(revision=54,landmarks=[dict(id='ashi_lake',name='芦之湖（缩尺改编）',pos=[-900,67,1370]),dict(id='ashi_east_shore',name='芦之湖东岸',pos=[-617,73,1380])],paths=paths,existing_towns_not_relocated=True,geographic_one_to_one=False),ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(manifest,ensure_ascii=False))

if __name__=='__main__':main()
