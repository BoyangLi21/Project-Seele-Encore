"""Root's bounded contact-bank correction: substantial two-face corner immersion."""
from pathlib import Path
import json,msvcrt,argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from survey_r52_original_complex import measure
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids
from extend_world_depth_r52 import acquire_world_lock
from r52_spatial_plan import BASE
import regional_voxels as vox

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');arg=ap.parse_args()
 out=BASE/'final_map_audit/actual_corner_immersion';stage='two_faces_visible_corner';assert not list((out/stage).glob('applied_*'))
 lo=(-55,-510,174);hi=(28,-464,324);before,names=measure(lo,hi)
 for s in ('minecraft:water[level=0]','minecraft:black_concrete','minecraft:stone','minecraft:air','projectseele:nerv_floor_panel'):
  if s not in names:names.append(s)
 ids={s:i for i,s in enumerate(names)};after=before.copy()
 yy,zz,xx=np.ogrid[lo[1]:hi[1]+1,lo[2]:hi[2]+1,lo[0]:hi[0]+1]
 pyramid=np.broadcast_to(np.maximum(abs(xx-30),abs(zz-327))<=np.minimum(120,np.ceil((-384-yy)*120/174))+1,before.shape)
 pyramid=pyramid.copy()|np.broadcast_to((xx>=8)&(xx<=16)&(zz>=249)&(zz<=257)&(yy>=-493)&(yy<=-470),before.shape)
 # Keep the existing forecourt support attached to dry land and the building,
 # rather than turn a retained structural member into an isolated island.
 forecourt=np.broadcast_to((xx>=8)&(zz>=249)&(zz<=265),before.shape)
 # Preserve the existing main basin. Its contact bank runs diagonally to
 # the enlarged corner recess; it no longer merely touches a corner point.
 limit=np.minimum(20,zz-216)
 basin=np.broadcast_to((xx<=limit)&(zz>=185)&(zz<=317),before.shape)&~pyramid&~forecourt
 rim=np.broadcast_to((xx>limit)&(xx<=limit+4)&(zz>=185)&(zz<=317)|(zz>317)&(zz<=321)&(xx<=20),before.shape)&~pyramid&~forecourt
 natural={'minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:coarse_dirt','minecraft:podzol','minecraft:gravel','minecraft:water','minecraft:grass','minecraft:fern','minecraft:azure_bluet'}
 authored={'minecraft:black_concrete','projectseele:nerv_floor_panel','projectseele:nerv_strip_light','minecraft:sea_lantern'}
 allowed=np.isin(before,[i for i,s in enumerate(names) if s.split('[')[0] in natural|authored])
 assert np.all(allowed[basin|rim]),{names[int(i)]:int(n)for i,n in zip(*np.unique(before[(basin|rim)&~allowed],return_counts=True))}
 depth=np.maximum(1,np.minimum(36,np.floor(np.minimum(limit-xx,317-zz)*.45)))
 floor=-473-depth
 target=np.where(yy>-473,ids['minecraft:air'],np.where(yy>floor,ids['minecraft:water[level=0]'],np.where(yy>=floor-1,ids['minecraft:black_concrete'],ids['minecraft:stone'])))
 after[basin]=np.broadcast_to(target,before.shape)[basin]
 rimtarget=np.where(yy>-468,ids['minecraft:air'],np.where(yy==-468,ids['projectseele:nerv_floor_panel'],ids['minecraft:black_concrete']))
 after[rim]=np.broadcast_to(rimtarget,before.shape)[rim]
 # Seal only basin-side cells against protected interior air, if any.
 wet=after==ids['minecraft:water[level=0]'];air=after==ids['minecraft:air'];seals=np.zeros(before.shape,bool)
 for d in ((0,0,1),(0,0,-1),(0,1,0),(0,-1,0),(-1,0,0)):
  a=tuple(slice(max(0,-v),min(n,n-v))for n,v in zip(before.shape,d));b=tuple(slice(max(0,v),min(n,n+v))for n,v in zip(before.shape,d));hit=wet[a]&air[b]
  assert not np.any(hit&~(pyramid|forecourt)[b]),'Uncontained water outside protected pyramid'
  seals[a]|=hit
 after[seals]=ids['minecraft:black_concrete'];assert np.array_equal(before[pyramid],after[pyramid])
 # These are actual water cells on BOTH adjacent faces, not a corner-point test.
 contacts=[(-34,-473,z)for z in range(266,311)]+[(x,-473,263)for x in range(-31,8)]
 assert all(after[y-lo[1],z-lo[2],x-lo[0]]==ids['minecraft:water[level=0]']for x,y,z in contacts)
 tags=dict(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi))
 for x,y,z in tags:assert before[y-lo[1],z-lo[2],x-lo[0]]==after[y-lo[1],z-lo[2],x-lo[0]],('Device',x,y,z)
 graph=np.load(BASE/'navigation_rebuild/combined/CURRENT_GRAPH.npz');nav=graph['coords'][graph['kept']]
 for x,y,z in nav:
  for h in (y-1,y,y+1):
   if lo[0]<=x<=hi[0]and lo[1]<=h<=hi[1]and lo[2]<=z<=hi[2]:assert before[h-lo[1],z-lo[2],x-lo[0]]==after[h-lo[1],z-lo[2],x-lo[0]],('Navigation',x,h,z)
 vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320));n=cuboids(p,lo,before,after,names,'R52_actual_two_face_corner_immersion');folder=p.save_plan(stage)
 fig,axes=plt.subplots(1,2,figsize=(10,8),layout='constrained')
 for ax,data,title in zip(axes,(before,after),('Rejected thin contact','Actual broad corner recess')):
  layer=data[-473-lo[1]];rgb=np.full((*layer.shape,3),(.4,.46,.34));rgb[layer==ids['minecraft:water[level=0]']]=(.08,.33,.47);rgb[pyramid[-473-lo[1]]]=(.12,.13,.14);ax.imshow(rgb,extent=[lo[0],hi[0],hi[2],lo[2]]);ax.set(title=title,xlabel='X',ylabel='Z')
 fig.savefig(folder/'CONTACT_BEFORE_AFTER.png',dpi=140);plt.close(fig)
 report=dict(world_written=False,changed_cells=n,actual_adjacent_water_cells_verified=len(contacts),north_face_wet_span_m=39,west_face_wet_span_m=45,pyramid_volume_preserved=True,forecourt_dry_connection_preserved=True,devices_preserved=len(tags),navigation_preserved=True,bank1_launch_range_untouched='All edits Z>=185; retained upper passage ends Z142',native_art_verified=False)
 if arg.apply:
  lock=acquire_world_lock()
  try:report.update(world_written=True,receipt=p.apply(stage,session_lock=lock))
  finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
 (folder/'APPLIED.json'if arg.apply else folder/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
