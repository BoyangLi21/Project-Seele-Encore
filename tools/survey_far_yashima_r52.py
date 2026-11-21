"""Bounded actual surface survey for the Root far-mountain selection."""
import sys,json,math,zlib,gzip
from collections import Counter
import numpy as np
from r52_spatial_plan import BASE
from transplant_s22_authority import read_region
from scan_all_surface_heightmaps_r50 import Metadata
from inspect_map_assets import decode_modern_section,palette_state

out=BASE/'far_yashima';out.mkdir(exist_ok=True);lo=(-1712,-1888);hi=(-945,-1121)
shape=(hi[1]-lo[1]+1,hi[0]-lo[0]+1);height=np.full(shape,-32768,np.int16);authored=np.zeros(shape,bool);status=np.zeros((48,48),np.uint8);missing=[];count=Counter()
for rx in range(lo[0]//512,hi[0]//512+1):
 for rz in range(lo[1]//512,hi[1]//512+1):
  path=BASE/f'WORLD_R52/dimensions/projectseele/geofront/region/r.{rx}.{rz}.mca'
  blobs=read_region(path)[1]if path.exists()and path.stat().st_size else[None]*1024
  for cx in range(max(lo[0]//16,rx*32),min(hi[0]//16,rx*32+31)+1):
   for cz in range(max(lo[1]//16,rz*32),min(hi[1]//16,rz*32+31)+1):
    slot=(cx&31)+(cz&31)*32;b=blobs[slot]
    if b is None:missing.append([cx,cz]);continue
    raw=zlib.decompress(b[5:])if b[4]==2 else gzip.decompress(b[5:])if b[4]==1 else b[5:]
    meta=Metadata(raw);data,_=meta.read()
    if data.get('Status','').removeprefix('minecraft:')!='full':missing.append([cx,cz]);continue
    h=np.full((16,16),-32768,np.int16);construction=np.zeros((16,16),bool)
    for s in meta.sections():
     sy=int(s['Y'])
     if sy<0:continue
     pal,values=decode_modern_section(s)
     if not pal:continue
     names=[palette_state(p)for p in pal];a=np.array(values,np.uint16).reshape(16,16,16)
     soils=np.array([v.split('[')[0]in('minecraft:grass_block','minecraft:dirt','minecraft:stone','minecraft:gravel','minecraft:sand','minecraft:sandstone','minecraft:clay')for v in names]);hit=soils[a]
     yy=sy*16+np.arange(16)[:,None,None];h=np.maximum(h,np.max(np.where(hit,yy,-32768),axis=0))
     built=np.array([not v.startswith('minecraft:')or any(t in v for t in('concrete','bricks','planks','glass','rail','cobblestone','barrier','iron_block'))for v in names]);construction|=built[a].any(0)
    zz,xx=cz*16-lo[1],cx*16-lo[0];height[zz:zz+16,xx:xx+16]=h;authored[zz:zz+16,xx:xx+16]=construction;status[zz//16,xx//16]=1;count['full']+=1
np.savez_compressed(out/'FAR_SURFACE.npz',height=height,authored=authored,status=status,origin=lo)
report=dict(world_written=False,bounds=[lo,hi],full=count['full'],missing_chunks=missing,authored_columns=int(authored.sum()),height_range=[int(height[height>0].min()),int(height.max())]if (height>0).any()else None)
(out/'SURVEY.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items()if k!='missing_chunks'}),len(missing),flush=True)
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
fig,ax=plt.subplots(figsize=(9,8));ax.imshow(np.ma.masked_less(height,0),origin='lower',extent=[lo[0],hi[0]+1,lo[1],hi[1]+1],cmap='terrain',vmin=50,vmax=max(160,int(height.max())))
z,x=np.where(authored);ax.scatter(x+lo[0],z+lo[1],s=.3,c='red');ax.grid(alpha=.3);ax.set_title('Actual far-site soil height; red = existing construction');fig.savefig(out/'FAR_SURFACE.png',dpi=150);plt.close(fig)
