"""Complete the named existing well facades and replace the reported apex mast."""
from pathlib import Path
from collections import deque
import argparse,gzip,json
import numpy as np
from query_blocks import read_box,iter_block_entities
import regional_voxels as vox
import survey_r52_original_complex as survey

DIM='projectseele:geofront'
LO=(-32,-379,-55);HI=(92,-310,6)

def reaches_outside(a,palette,origin,point):
 y=point[1]-origin[1];z=point[2]-origin[2];x=point[0]-origin[0]
 air=a[y]==palette.index('minecraft:air')
 if not air[z,x]:return False
 seen={(z,x)};todo=deque(seen)
 while todo:
  z,x=todo.popleft()
  if z in (0,air.shape[0]-1) or x in (0,air.shape[1]-1):return True
  for zz,xx in ((z-1,x),(z+1,x),(z,x-1),(z,x+1)):
   if (zz,xx)not in seen and 0<=zz<air.shape[0] and 0<=xx<air.shape[1] and air[zz,xx]:seen.add((zz,xx));todo.append((zz,xx))
 return False

def run(base,world):
 vox.WORLD=world;vox.DIM=DIM;vox.OUT=base/'oct16-shell-repair'/world.name
 p=vox.Painter(vertical_bounds=(-1440,320));rows=[]
 def setcell(at,old,new,why):
  if old==new:return
  p.exact((*at,*at),old,new,why);rows.append(dict(pos=at,before=old,after=new,reason=why))
 survey.WORLD=base/'WORLD';original,original_palette=survey.measure(LO,HI)
 reported=(36,-377,-20)
 assert reaches_outside(original,original_palette,LO,reported),'Frozen report must reproduce before repair'
 survey.WORLD=world;before,palette=survey.measure(LO,HI);after=before.copy()
 for name in ('projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel'):
  if name not in palette:palette.append(name)
 protected=set();owner=json.loads((world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
 for gate in owner['gates']:
  table=gate['collision_steps']
  if isinstance(table,dict):table=json.loads(gzip.decompress((world/table['cells_file']).read_bytes()))
  for step in table:
   for cell in step:protected.add(tuple(cell['position']))
 for left,right in ((-29,5),(13,47),(55,89)):
  for y in range(LO[1],HI[1]+1):
   wall='projectseele:nerv_structural_panel' if y%12==0 else 'projectseele:nerv_shaft_panel'
   perimeter={(x,z)for x in range(left,right+1)for z in (-54,5)}|{(x,z)for x in (left,right)for z in range(-54,6)}
   for x,z in perimeter:
    at=x,y,z;iy,iz,ix=y-LO[1],z-LO[2],x-LO[0];old=palette[int(before[iy,iz,ix])]
    if old!='minecraft:air' or at in protected:continue
    setcell(at,old,wall,'reported_existing_wells_upper_facade_completion');after[iy,iz,ix]=palette.index(wall)
 assert not reaches_outside(after,palette,LO,reported),'Reported upper well is still horizontally open'
 cap=read_box(world,DIM,(27,-391,324),(33,-384,330))
 allowed={'minecraft:air','minecraft:white_concrete','minecraft:red_concrete','minecraft:beacon','projectseele:nerv_pyramid_panel'}
 for at,old in cap.items():
  assert old in allowed,(at,old)
  if at[1]>-391:setcell(at,old,'minecraft:air','replace_reported_red_white_apex_mast')
  else:
   x,y,z=at
   new='projectseele:nerv_pyramid_panel' if x in (27,33)or z in (324,330) else 'projectseele:nerv_machine_panel'
   if x==30 and z==327:new='projectseele:nerv_alert_light[lit=true]'
   setcell(at,old,new,'flush_dark_metal_pyramid_cap')
 p.meta.update(reported_well=list(reported),frozen_original_report_reproduced=True,upper_facades_y=[-379,-310],apex_flat_y=-391,apex_existing_centre=[30,327])
 p.apply('old_well_upper_facades_and_flush_apex')
 for lo,hi in ((LO,HI),((27,-391,324),(33,-384,330))):
  observed=read_box(world,DIM,lo,hi)
  for row in rows:
   at=tuple(row['pos'])
   if at in observed:assert observed[at]==row['after'],at
 assert not list(iter_block_entities(world,DIM,(30,-384,327),(30,-384,327))),'Retired beacon NBT remains'
 (vox.OUT/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode('utf8'),mtime=0))
 print(json.dumps(dict(world=str(world),changed=len(rows),frozen_report_reproduced=True,reported_well_closed=True,readback=True)))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--world',type=Path,required=True);a=p.parse_args();run(a.base,a.world)
