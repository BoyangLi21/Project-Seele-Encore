"""Rebuild measured personnel circulation as unions, with explicit portals.

Unlike route-centre tests, the saved contract covers the entire usable section,
each exterior edge, the ceiling and paired moving-walk end landings.
"""
import json, math
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_erosion
import regional_voxels as v
import scan_regional_completion as scan
from plan_factory_r20 import Scene,FLOOR,WALL,STRUCT,EDGE,LIGHT
import plan_factory_r20 as factory
from query_blocks import iter_block_entities

ROOT=v.ROOT;OUT=ROOT/'artifacts/world_repair_r21';REVIEW=ROOT/'run/saves/SEELE_R21_REVIEW'
AIR='minecraft:air';GLASS='projectseele:clear_glass'
LO=(-42,-474,-298);HI=(207,-345,478)

class Facility(Scene):
 def __init__(self):
  self.before,self.palette=scan.volume(LO,HI);self.after=self.before.copy();self.ids={s:i for i,s in enumerate(self.palette)};self.protected=np.zeros(self.after.shape,bool);self.descriptions=[];self.contract=[];self.belts=[];self.walks=[]
 def index(self,b):
  x,y,z,X,Y,Z=map(int,b)
  assert x>=LO[0] and y>=LO[1] and z>=LO[2] and X<=HI[0] and Y<=HI[1] and Z<=HI[2],b
  return np.s_[y-LO[1]:Y-LO[1]+1,z-LO[2]:Z-LO[2]+1,x-LO[0]:X-LO[0]+1]
 def hall(self,name,rects,f,height=6,ports=()):
  x0=min(b[0] for b in rects);X=max(b[1] for b in rects);z0=min(b[2] for b in rects);Z=max(b[3] for b in rects)
  mask=np.zeros((Z-z0+1,X-x0+1),bool)
  for x,xx,z,zz in rects:mask[z-z0:zz-z0+1,x-x0:xx-x0+1]=True
  inside=binary_erosion(mask)
  for zz,xx in np.argwhere(mask):
   x,z=int(xx+x0),int(zz+z0);rim=not inside[zz,xx]
   self.fill((x,f-1,z,x,f-1,z),STRUCT);self.fill((x,f,z,x,f,z),FLOOR)
   self.fill((x,f+1,z,x,f+height-1,z),WALL if rim else AIR)
   if rim:self.fill((x,f+2,z,x,f+height-2,z),GLASS)
   self.fill((x,f+height,z,x,f+height,z),LIGHT if not rim and x%10 in (0,1) and z%12 in (0,1) else STRUCT)
  for box in ports:self.fill(box,AIR)
  self.contract.append(dict(id=name,rects=rects,floor=f,height=height,ports=ports))
 def belt(self,name,x,z,length,f,axis='z',direction=True):
  facing='north' if axis=='z' else 'east'
  for i in range(length):
   for lane,side in [(0,'left'),(1,'right')]:
    xx=x+lane if axis=='z' else x+i;zz=z+i if axis=='z' else z+lane
    self.fill((xx,f-1,zz,xx,f-1,zz),STRUCT)
    for yy,block in [(f,'escalator_step'),(f+1,'escalator_side')]:
     fields=f'facing={facing},orientation=flat,side={side}'
     if block=='escalator_step':fields=f'direction={str(direction).lower()},'+fields+',status=true'
     self.fill((xx,yy,zz,xx,yy,zz),f'mtr:{block}[{fields}]')
  self.belts.append(dict(id=name,origin=[x,f,z],length=length,axis=axis,direction=direction))
 def path(self,name,points):
  for suffix,pts in [('',points),('/return',list(reversed(points)))]:self.walks.append(dict(id='r21/'+name+suffix,path=pts))

def main(apply=False):
 factory.LO=LO;factory.HI=HI
 v.WORLD=REVIEW;scan.WORLD=REVIEW;v.OUT=OUT/'facility';s=Facility();p=v.Painter()
 # Fixed cabin capture and controllers are authoritative. Outside this exact
 # volume, abandoned rail halves and holes must no longer be protected blindly.
 sweeps=json.loads((ROOT/'artifacts/world_rebuild_r20/lifts/sweep_masks.json').read_text())
 for r in sweeps:
  a,b=r['sweep']
  if all(LO[i]<=a[i]<=b[i]<=HI[i] for i in range(3)):s.protect((*a,*b))
 for pos,tag in iter_block_entities(REVIEW,v.DIM,LO,HI):
  if 'movingelevators' in str(tag['id']):s.protect((*pos,*pos))
 # The native U2 turnback is live rail, including the space west of its
 # platform. It must never be filled by a pedestrian-foyer union.
 s.protect((93,-448,-42,119,-431,-37))
 # The north platform apron belongs to the station, including its ceiling.
 # R21's foyer union previously replaced its first twelve gate cells.
 s.protect((113,-444,-54,184,-433,-37))
 # Accepted command interior and pyramid skin are immutable.
 protected_states=np.array([q.startswith(('projectseele:nerv_pyramid_panel','projectseele:one_way_glass')) for q in s.palette])
 s.protected|=protected_states[s.before]
 s.protect((-8,-474,278,61,-390,366))
 # Explicitly retire the leftover east apron, keeping the active public lift.
 old=np.asarray(s.palette)
 for box in [(135,-449,195,164,-436,265),(114,-446,-198,164,-442,-58)]:
  sl=s.index(box);a=s.after[sl];pr=s.protected[sl]
  old_mask=np.array([q.startswith('minecraft:') and any(n in q for n in ('concrete','deepslate','blackstone','smooth_stone','iron_bars')) for q in old])[a]
  a[old_mask&~pr]=s.state(AIR)
 # Clear all old half-belts before the complete corridor cross sections.
 for box in [(96,-398,-274,108,-389,-42),(112,-444,-10,123,-441,245)]:
  sl=s.index(box);a=s.after[sl];ret=np.array([q.startswith('mtr:escalator_') for q in s.palette])[a]
  a[ret&~s.protected[sl]]=s.state(AIR)
 # Lower plant: one coherent enclosed junction, then the long north gallery.
 s.hall('factory_lower',[(102,114,-290,-43),(91,131,-48,-42)],-443,6,
        [(91,-442,-49,95,-439,-46),(128,-442,-47,131,-438,-43)])
 s.belt('factory_lower/north',104,-284,222,-443,direction=True)
 s.belt('factory_lower/south',110,-284,222,-443,direction=False)
 # Middle gallery gains full two-direction moving walks and a spacious landing.
 s.hall('factory_middle',[(95,113,-275,-43),(89,113,-49,-43),(86,113,-271,-259)],-395,7,
        [(91,-394,-49,95,-391,-46),(86,-394,-269,90,-390,-263)])
 # Complete retracted enclosed observation boundary: keep the three
 # original clear rows at Z=-46..-44 and the actual lift handoff at Z=-45.
 for x in range(90,114):
  for y in range(-396,-387):
   old=s.palette[s.before[y-LO[1],-42-LO[2],x-LO[0]]]
   if old in {FLOOR,STRUCT,WALL,GLASS}:s.fill((x,y,-42,x,y,-42),AIR)
 for x in range(90,113):
  for y in range(-394,-388):
   state=STRUCT if x in (90,96,104,112) or y==-389 else WALL if y==-394 else GLASS
   s.fill((x,y,-43,x,y,-43),state)
 s.contract[-1].update(south_end_role='Enclosed industrial observation window; no south door',enclosed_observation_boundaries=[dict(x=[90,112],z=-43,feet=-394,wall_y=[-394,-389],waist_state=WALL,glass_state=GLASS,frame_state=STRUCT,vertical_frame_x=[90,96,104,112],top_seal_y=-389,continuous_roof_y=-388,through_route=False,enclosed=True,clear_waiting_rows_z=[-46,-45,-44])])
 s.belt('factory_middle/north',98,-252,185,-395,direction=True)
 s.belt('factory_middle/south',107,-252,185,-395,direction=False)
 # The old exterior half-escalator is absorbed into the usable width above.
 # Outside supported corridors, its complete superseded rail is retired.
 # Upper observation circulation: -367 walking datum requested by the user.
 s.hall('commander_gallery',[(94,113,-287,-82),(-34,113,-226,-216),(-34,113,-287,-275)],-368,7)
 s.belt('upper_gallery/north',98,-267,167,-368,direction=True)
 s.belt('upper_gallery/south',108,-267,167,-368,direction=False)
 s.belt('observer_cross/east',-25,-225,111,-368,axis='x',direction=True)
 s.belt('observer_cross/west',-25,-218,111,-368,axis='x',direction=False)
 # Moving walks end before crossings; users must not climb over handrails.
 s.fill((96,-368,-228,111,-368,-214),FLOOR)
 s.fill((96,-367,-228,111,-362,-214),AIR)
 # Three window bays look into the three wet cages. Workstations stay clear
 # of the four-metre circulation lane and do not intersect the crane runway.
 for cx in (-12,30,72):
  for dx in (-5,-3,3,5):s.fill((cx+dx,-367,-277,cx+dx,-367,-277),'projectseele:nerv_workstation[facing=south]')
  for dx in (-4,4):s.fill((cx+dx,-367,-279,cx+dx,-367,-279),'projectseele:nerv_office_chair[facing=south]')
 # Keep the retained lower observation room and join its -369 level by two
 # actual risers, with complete headroom and enclosed sides.
 s.hall('upper_transition',[(98,110,-91,-76)],-370,8)
 for z,y in [(-85,-369),(-86,-368)]:
  s.fill((99,y,z,109,y,z),'minecraft:smooth_quartz_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
  s.fill((99,y+1,z,109,-363,z),AIR)
 s.fill((99,-368,-84,109,-363,-77),AIR);s.fill((99,-367,-90,109,-363,-87),AIR)
 s.fill((99,-368,-92,109,-368,-87),FLOOR)
 s.fill((99,-367,-92,109,-363,-87),AIR)
 # The compact lift's free east edge was outside the captured cabin. Enclose
 # its rear and sides, retain the native north/south gates and controllers.
 for f,doorz in [(-443,-48),(-395,-48),(-371,-56)]:
  for box in [(90,f,-55,90,f+6,-49),(96,f,-55,96,f+6,-49)]:
   s.fill(box,STRUCT)
  rear=-55 if doorz==-48 else -49
  s.fill((90,f,rear,96,f+6,rear),STRUCT)
  s.fill((97,f,-56,99,f,-48),FLOOR)
  s.fill((97,f-1,-56,99,f-1,-48),STRUCT)
  if f==-371:
   # Two previously uncovered cells directly beside the shaft are no longer
   # a walk-in drop, irrespective of the car's current stop.
   s.fill((96,-370,-55,96,-365,-49),STRUCT)
   s.fill((97,-370,-56,99,-370,-48),FLOOR)
 # Main pyramid-to-launch pedestrian route with genuine paired handrails.
 s.hall('pyramid_launch_link',[(112,124,-12,244),(113,155,-25,-9),(146,155,-28,-20),(89,128,240,251)],-443,7,
        [(147,-442,-28,153,-438,-24),(91,-442,248,96,-438,251),(120,-442,248,126,-438,251),(110,-442,247,114,-438,251)])
 s.belt('pyramid_launch/north',114,2,232,-443,direction=True)
 s.belt('pyramid_launch/south',121,2,232,-443,direction=False)
 # Station west edge, both terminal ends and southern apron must have a
 # continuous perimeter. Train track remains unobstructed, not a false wall.
 s.hall('launch_station_west_foyer',[(102,116,-48,-43),(108,116,-35,-25)],-443,7,
        [(113,-442,-47,116,-438,-43),(113,-442,-34,116,-438,-28)])
 # West face is fully glazed above a solid parapet; south platform opens only
 # at its real public entrance. No full-depth holes beside the dead-end rail.
 for z0,z1 in [(-55,-44),(-35,-25)]:
  s.fill((107,-444,z0,111,-443,z1),STRUCT)
  s.fill((107,-442,z0,107,-437,z1),WALL)
  s.fill((107,-440,z0,107,-438,z1),GLASS)
 # A signed, short southern route already links the pyramid to headquarters
 # station. Finish its low level envelope rather than inventing another line.
 s.hall('headquarters_station_approach',[(24,36,442,471)],-467,7,
        [(27,-466,442,33,-462,442),(27,-466,471,33,-462,471)])
 s.belt('headquarters_station/north',26,446,21,-467,direction=True)
 s.belt('headquarters_station/south',32,446,21,-467,direction=False)
 # Port clearances override every union rim; only the named port volumes.
 for box in [(99,-367,-83,110,-363,-80),(95,-367,-224,98,-363,-218),
             (95,-367,-284,98,-363,-278),(104,-442,-48,113,-438,-43),
             (110,-442,-47,116,-438,-43),(110,-442,-34,116,-438,-28),
             (113,-442,-12,123,-438,-9),(147,-442,-25,153,-438,-23)]:s.fill(box,AIR)
 for x,z in [(114,240),(124,240),(114,0),(124,0)]:s.fill((x,-468,z,x,-445,z),STRUCT)
 # Carry exact section contracts plus positive and inverse voxel deltas.
 s.path('pyramid_launch_centre',[[118.5,-442,244.5],[118.5,-442,-17.5],[150.5,-442,-17.5],[150.5,-442,-28.5]])
 s.path('factory_middle',[[104.5,-394,-45.5],[104.5,-394,-265.5],[88.5,-394,-265.5]])
 s.path('factory_lower',[[108.5,-442,-44.5],[108.5,-442,-286.5]])
 s.path('upper_risers',[[104.5,-369,-78.5],[104.5,-369,-83.5],[104.5,-367,-88.5],[104.5,-367,-281.5]])
 s.path('upper_three_cages',[[102.5,-367,-221.5],[-29.5,-367,-221.5]])
 s.path('upper_front_observers',[[102.5,-367,-281.5],[-29.5,-367,-281.5]])
 changed=s.delta(p,'r21/personnel_circulation')
 p.meta.update(walk_nodes=s.walks,contracts=s.contract,moving_walkways=s.belts,changed_cells=changed)
 target=p.apply('coherent_personnel_routes') if apply else p.save_plan('coherent_personnel_routes')
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'facility_contract.json').write_text(json.dumps(dict(world=str(REVIEW),sections=s.contract,belts=s.belts,walks=s.walks,retired_platform=[135,-449,195,164,-436,265]),ensure_ascii=False,indent=2),encoding='utf8')
 print('R21 authored',changed,'cells',len(s.belts),'moving walks',flush=True)
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
