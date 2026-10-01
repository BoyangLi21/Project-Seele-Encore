"""Measured TV cage/launch-chamber reconstruction; cold, reversible world patches."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import regional_voxels as vox
from scan_regional_completion import volume

OUT=vox.ROOT/'artifacts/tv_facilities_r16'
GREEN='projectseele:nerv_machine_panel';BLUE='projectseele:nerv_shaft_panel';EDGE='projectseele:nerv_machine_edge';HAZARD='projectseele:nerv_machine_hazard'
FINISHES={'projectseele:nerv_structural_panel','minecraft:polished_deepslate','minecraft:deepslate_bricks','minecraft:deepslate_tiles','minecraft:polished_blackstone_bricks','minecraft:gray_concrete','minecraft:orange_concrete','minecraft:purple_concrete','minecraft:red_concrete','minecraft:orange_terracotta','minecraft:purple_terracotta','minecraft:red_terracotta','minecraft:chiseled_polished_blackstone'}

def plan():
 if (vox.WORLD/'eva_facility_r29.json').is_file() or (vox.WORLD/'.projectseele_spatial_preview_read_only.json').is_file():
  raise RuntimeError('The old partial R16 palette plan is retired in delivered/frozen facilities; use the complete measured R44 component contract')
 p=vox.Painter();written={};p.meta.update(reference='Cached animation frames: olive fabricated equipment, blue vessel/shaft surfaces, shoulder actuators, upright restraint pallet and shutters; episode/edition metadata remains unverified, not asserted from the filenames',preserved=['headquarters command layout','all original personnel paths and doors','EVA fleet and plug UUIDs','plug socket and crane kinematics','31x31 shaft clear cores'],bulkheads_y=[-332,-192,-52])
 for name in ('cages','launch'):
  src=np.load(OUT/'survey'/(name+'.npz'));a=src['blocks'];pal=src['palette'];lo=src['lo'];hi=src['hi'];ys,zs,xs=np.ogrid[lo[1]:hi[1]+1,lo[2]:hi[2]+1,lo[0]:hi[0]+1]
  if name=='cages':
   mask=(zs>=-127)&(zs<=-55)&(ys<=-355)&(xs>=-32)&(xs<=92)
  else:mask=(ys>=-442)&(ys<=78)&(zs>=-53)&(zs<=-19)
  desired={}
  for i,state in enumerate(pal):
   if state not in FINISHES:continue
   eligible=(a==i)&mask;coords=np.argwhere(eligible)
   for yy,zz,xx in coords:
    x,y,z=int(xx+lo[0]),int(yy+lo[1]),int(zz+lo[2]);target=GREEN if name=='cages' else BLUE
    if name=='cages' and y<=-442:target='projectseele:nerv_floor_panel'
    # Structural bay divisions and overhead beams keep a readable hierarchy.
    if name=='cages' and (x in (-32,-31,8,9,10,50,51,52,91,92) or y in (-437,-419,-401,-363,-362)) and y>-442:target=BLUE
    if name=='launch' and y in tuple(range(-330,78,24)):target=EDGE
    desired[x,y,z]=(str(state),target)
  # Run-length patches preserve each measured old state, including properties.
  rows={}
  for (x,y,z),states in desired.items():rows.setdefault((y,z),[]).append((x,*states))
  for (y,z),row in rows.items():
   row.sort();start=previous=row[0][0];before,after=row[0][1:]
   for x,b,n in row[1:]+[(10**9,'','')]:
    if x!=previous+1 or (b,n)!=(before,after):
     p.match((start,y,z,previous,y,z),before,after,'r16/'+name+'/plating');start=x;before,after=b,n
    previous=x
  written.update({pos:value[1] for pos,value in desired.items()})
  p.meta.setdefault('material_cells',{})[name]=len(desired)
 # Positive edit mask for guides and indexed shutter collars, all outside |dx|,|dz|<=15.
 src=np.load(OUT/'survey/launch.npz');a,pal,lo=src['blocks'],src['palette'],src['lo']
 def place(x,y,z,new,purpose):
  old=str(pal[a[y-lo[1],z-lo[2],x-lo[0]]])
  if old in ('minecraft:air','minecraft:void_air') or old in FINISHES or old=='minecraft:iron_block':
   p.match((x,y,z,x,y,z),written.get((x,y,z),old),new,'r16/launch/'+purpose);written[x,y,z]=new
 for cx in (-12,30,72):
  for y in range(-441,79):
   for dx in (-10,10):place(cx+dx,y,-20,EDGE,'continuous_rear_guides')
   for dx in (-16,16):
    for z in (-46,-26):
     if (y+440)%16<10:place(cx+dx,y,z,'projectseele:nerv_strip_light','recessed_light_banks')
  for floor in (-332,-192,-52):
   for y in range(floor-2,floor+3):
    for d in range(-16,17):
     for x,z in [(cx+d,-52),(cx+d,-20),(cx-16,-36+d),(cx+16,-36+d)]:
      place(x,y,z,EDGE if z==-20 and abs(x-cx)==10 or y in (floor-2,floor+2) else GREEN,'bulkhead_mounts')
   # All 961 moving seals must start as measured air, not overwrite a bridge or build.
   for z in range(-51,-20):
    for x in range(cx-15,cx+16):
     old=str(pal[a[floor-lo[1],z-lo[2],x-lo[0]]]);assert old in ('minecraft:air','minecraft:void_air'),('Bulkhead intersects existing block',x,floor,z,old)
 return p

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args();vox.OUT=OUT/'map';p=plan()
 if args.apply:
  # Material and mount operations can overlap. The patch engine applies only
  # the matching measured states; mounts are commissioned in a second pass.
  p.apply('tv_facilities')
  marker=vox.WORLD/'tv_facilities_r16.json'
  marker.write_text(json.dumps(dict(version=16,dimension=vox.DIM,cages=[[-12,-443,-96],[30,-443,-96],[72,-443,-96]],shafts=[[-12,-443,-36],[30,-443,-36],[72,-443,-36]],bulkheads_y=[-332,-192,-52],mechanical_assets='tv_facilities_r16.json'),indent=2),encoding='utf8')
 else:p.save_plan('tv_facilities')
 print(p.meta['material_cells'])
if __name__=='__main__':main()
