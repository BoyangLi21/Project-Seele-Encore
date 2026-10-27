"""Purpose-specific detail inside the 34 measured rooms; preserve doors and existing circulation."""
import argparse,json
from pathlib import Path
from collections import Counter
import numpy as np
import regional_voxels as vox
from scan_regional_completion import volume
ROOT=vox.ROOT;OUT=ROOT/'artifacts/first_battle_world_r10/world_art';AIR={'minecraft:air','minecraft:cave_air','minecraft:light[level=15,waterlogged=false]'}
ROOMS=json.loads((ROOT/'artifacts/world_motion_r04/pyramid/places.json').read_text(encoding='utf8'))['rooms']
def build():
 p=vox.Painter();lo=(-56,-436,266);hi=(114,-355,409);a,pal=volume(lo,hi);desired={};counts=Counter();owners={}
 def original(pos):x,y,z=pos;return pal[a[y-lo[1],z-lo[2],x-lo[0]]]
 def state(pos):return desired.get(pos,original(pos))
 def put(pos,new,owner,allowed=None):
  before=state(pos)
  if before==new or allowed is not None and before not in allowed:return
  desired[pos]=new;owners[pos]=owner;counts[owner]+=1
 for room in ROOMS:
  if room['id']=='r04/pyramid/435/06':continue  # R54 private ward recipe owns this interior.
  x0,x1,z0,z1=room['bounds'];f=room['floor'];kind=room['purpose'];owner=room['id']+'/r10';ex,ey,ez=room['entry'];cx=(x0+x1)//2;cz=(z0+z1)//2
  def clear_entry(x,z):return abs(x-ex)<=3 and abs(z-ez)<=4
  for z in range(z0+1,z1):
   for x in range(x0+1,x1):
    if clear_entry(x,z):continue
    for y in range(f+1,f+5):
     pos=x,y,z;s=state(pos)
     if kind=='ANALYSIS' and s=='minecraft:black_stained_glass':put(pos,'projectseele:nerv_workstation[facing=south]',owner+'/crt')
     if kind=='ARCHIVE' and s=='minecraft:bookshelf':put(pos,'projectseele:nerv_storage_panel[facing=east]',owner+'/files')
     if kind=='SUPPLIES' and s=='minecraft:iron_block':put(pos,'projectseele:nerv_storage_panel[facing=south]',owner+'/equipment')
     if kind=='MEDICAL' and s=='minecraft:flower_pot':put(pos,'projectseele:nerv_medical_panel[facing=west]',owner+'/vitals')
     if kind=='QUARTERS' and s=='minecraft:flower_pot':put(pos,'minecraft:potted_bamboo',owner+'/personal')
  # Recessed ceiling service runs and edge battens retain at least six blocks of headroom.
  for z in range(z0+3,z1-2):
   for x in (x0+2,x1-2):
    put((x,f+7,z),'minecraft:polished_blackstone_slab[type=top,waterlogged=false]',owner+'/duct',AIR)
   if (z-z0)%7==0:
    for x in range(x0+4,x1-3):put((x,f+8,z),'projectseele:nerv_strip_light' if abs(x-cx)<3 else 'minecraft:smooth_stone_slab[type=top,waterlogged=false]',owner+'/lighting',AIR)
  # Full-height storage only occupies empty perimeter bays away from every entrance.
  if kind in ('ANALYSIS','QUARTERS','MEDICAL','CAFETERIA'):
   for z in range(z0+3,z1-2,7):
    x=x0+1
    if clear_entry(x,z) or any(state((x,y,z)) not in AIR for y in range(f+1,f+4)):continue
    cabinet='nerv_server_rack' if kind=='ANALYSIS' else 'nerv_storage_panel'
    for y in range(f+1,f+(4 if kind=='ANALYSIS' else 3)):put((x,y,z),f'projectseele:{cabinet}[facing=east]',owner+'/wall_bays',AIR)
  if kind=='BRIEFING':
   for x in range(x0+4,x1-3):
    put((x,f+6,z0+1),'minecraft:polished_blackstone_slab[type=top,waterlogged=false]',owner+'/screen_frame',AIR)
   put((cx,f+7,cz),'minecraft:observer[facing=north,powered=false]',owner+'/projector',AIR)
  if kind=='CAFETERIA':
   for x in range(x0+3,min(x1-2,x0+13)):
    if clear_entry(x,z0+1):continue
    put((x,f+1,z0+1),'minecraft:smooth_quartz',owner+'/servery',AIR)
    if (x-x0)%3==0:put((x,f+2,z0+1),'minecraft:heavy_weighted_pressure_plate[power=0]',owner+'/tray',AIR)
  p.meta['rooms'].append(dict(room,detail_programme=kind+' / CRT hardware, wall bays, ceiling services, task lighting'))
 for pos,new in sorted(desired.items()):p.match((*pos,*pos),original(pos),new,owners[pos])
 p.meta['changed_cells']=len(desired);p.meta['detail_counts']=dict(counts);vox.OUT=OUT
 return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args();p=build();p.apply('pyramid_rooms') if args.apply else p.save_plan('pyramid_rooms')
