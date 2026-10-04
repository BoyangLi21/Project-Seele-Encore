"""Separate boarding, full-width stairs and waiting spaces in the actual stations."""
from pathlib import Path
import argparse,json,copy
import numpy as np,nbtlib
import regional_voxels as v
import scan_regional_completion as scan
import plan_factory_r20 as factory
from build_transit_civil_r22 import Station
from query_blocks import iter_block_entities
from station_lower_support_r45 import support_ops
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R22_REVIEW';OUT=ROOT/'artifacts/facility_r23/stations'
AIR='minecraft:air';FLOOR='minecraft:smooth_stone';DECK='minecraft:light_gray_concrete';EDGE='projectseele:nerv_machine_edge';GLASS='projectseele:clear_glass';LIGHT='projectseele:nerv_strip_light'

class Adapter:
 def __init__(self,scene,painter):self.scene=scene;self.block_entities=painter.block_entities
 def put(self,x,y,z,state,*args):self.scene.fill((x,y,z,x,y,z),state)
class RevisedStation(Station):
 def __init__(self,record,scene,painter,platforms):
  self.scene=scene;self.p=Adapter(scene,painter);self.cx,self.y,self.cz=record['center'];self.ground=record['ground'];self.half=record['half'];self.horizontal=record['horizontal'];self.name=record['station'];self.line=record['line'];self.platforms=platforms;self.owner='r23/station/'+str(platforms[0]['id']);self.walks=[];self.boards=[];self.belts=[]
 def fill(self,u,y,w,U,Y,W,state):
  a=self.at(u,y,w);b=self.at(U,Y,W);self.scene.fill(tuple(map(int,(*np.minimum(a,b),*np.maximum(a,b)))),state)
 def replan(self):
  h,g,y=self.half,self.ground,self.y;rise=y-g;u0=-h+5
  # The former R22 bridge usedw9..11; R23 usesw11..13. Retire its
  # complete remaining outer two slopes and preserve their later lamps.
  retired_bridge_lamps=[];old_bridge_b=h-15
  def old_state(q):return self.scene.palette[int(self.scene.after[q[1]-factory.LO[1],q[2]-factory.LO[2],q[0]-factory.LO[0]])]
  for sign in(-1,1):
   for i in range(7):
    for cross in(9,10):
     for Y in range(y+1,y+i+2):
      q=self.at(old_bridge_b+i,Y,sign*cross)
      if q in getattr(self.scene,'source_BE_positions',set()):raise RuntimeError(('Old bridge retirement meets original BE',q))
      if self.scene.protected[q[1]-factory.LO[1],q[2]-factory.LO[2],q[0]-factory.LO[0]]:raise RuntimeError(('Old bridge retirement crosses protected volume',q))
      old=old_state(q)
      expected=DECK if Y<y+i+1 else f'minecraft:smooth_quartz_stairs[facing={"east"if self.horizontal else"south"},half=bottom,shape=straight,waterlogged=false]'
      if old==expected:self.fill(old_bridge_b+i,Y,sign*cross,old_bridge_b+i,Y,sign*cross,AIR)
      elif old=='projectseele:nerv_ceiling_light[hanging=true,lit=true]':
       retired_bridge_lamps.append((q,sign*cross,old));self.fill(old_bridge_b+i,Y,sign*cross,old_bridge_b+i,Y,sign*cross,AIR)
      elif old!=AIR:raise RuntimeError(('Unclassified current object on superseded R22 bridge slope',q,old))
  edge=int(round(max(abs(((q['position1']['z']+q['position2']['z'])/2-self.cz) if self.horizontal else ((q['position1']['x']+q['position2']['x'])/2-self.cx)) for q in self.platforms)))+2
  # Retire native mechanisms inside this authored station before rebuilding
  # the complete two-block pairs. Rail geometry itself stays untouched.
  m=np.array([s.startswith(('mtr:escalator_step','mtr:escalator_side')) for s in self.scene.palette])[self.scene.after];self.scene.after[m&~self.scene.protected]=self.scene.state(AIR)
  self.fill(-h-1,g-2,-18,h+1,g-1,18,DECK);self.fill(-h-1,g,-18,h+1,g,18,FLOOR)
  for sign in (-1,1):
   lo,hi=(-17,-edge) if sign<0 else (edge,17)
   self.fill(-h,y-2,lo,h,y-1,hi,DECK);self.fill(-h,y,lo,h,y,hi,FLOOR)
   self.fill(-h,y+1,lo,h,y+4,hi,AIR)
   # Relocate the outer frame and every fixture attached to it together.
   # Retiring an old frame must not cut through the newly laid deck.
   self.fill(-h,g+1,sign*15,h,y-3,sign*15,AIR)
   self.fill(-h,y+1,sign*15,h,y+10,sign*15,AIR)
   for u in range(-h+2,h,16):
    self.fill(u,y-2,sign*17,u,y+10,sign*17,DECK)
    for op in support_ops(self.at,u,sign,g,y,h,self.scene,factory.LO,getattr(self.scene,"source_BE_positions",set())):self.fill(*op)
   self.fill(-h,y+1,sign*17,h,y+1,sign*17,EDGE);self.fill(-h,y+2,sign*17,h,y+3,sign*17,GLASS)
   self.fill(-h,y+10,sign*17,h,y+10,sign*17,EDGE);self.fill(-h,y+11,sign*17,h,y+11,sign*15,DECK)
   # Four unobstructed metres beside the platform edge, then an independent
   # paired escalator/stair core. The rail foundation ends at cross-offset 7.
   up,down,stair=(-15,-11,-13) if sign<0 else (10,14,12)
   low,high=min(up,down),max(up,down)+1
   self.fill(u0-1,g+1,low,u0+rise+5,y+6,high,AIR)
   for n in range(rise):
    self.fill(u0+n+1,g,stair,u0+n+1,g+n,stair+1,DECK)
    self.fill(u0+n+1,g+n+1,stair,u0+n+1,g+n+1,stair+1,f'minecraft:smooth_quartz_stairs[facing={"east" if self.horizontal else "south"},half=bottom,shape=straight,waterlogged=false]')
   self.fill(u0+rise+1,y,low,u0+rise+6,y,high,FLOOR)
   self.belt(u0,g,up,0,True,rise);self.belt(u0,g,down,0,False,rise)
   # Stairwell guards stay at platform height, outside the moving assembly.
   inner=-9 if sign<0 else 9
   self.fill(u0-1,y+1,inner,u0+rise,y+2,inner,GLASS)
   self.fill(u0-1,y+1,sign*16,u0+rise,y+2,sign*16,GLASS)
   self.fill(u0-2,y+1,low,u0-2,y+2,high,GLASS)
   self.path('ordinary_stair_'+str(sign),[self.at(u0-2,g+1,stair),self.at(u0,g+1,stair),self.at(u0+rise+2,y+1,stair),self.at(u0+rise+7,y+1,stair)])
   self.path('ground_entrance_'+str(sign),[self.at(u0-2,g+1,sign*18),self.at(u0-2,g+1,stair),self.at(u0-1,g+1,stair)])
   self.path('boarding_corridor_'+str(sign),[self.at(-h+2,y+1,sign*8),self.at(h-3,y+1,sign*8)])
   # Platform end barriers close the former walk-off ends, outside rail gauge.
   for end in (-h,h):self.fill(end,y+1,lo,end,y+2,hi,GLASS)
   face=('south' if sign<0 else 'north') if self.horizontal else ('east' if sign<0 else 'west')
   self.fill(-h+6,y,sign*edge,h-6,y,sign*edge,f'mtr:platform[door_type=none,facing={face},side=0]')
   target=min(self.platforms,key=lambda p:abs(((p['position1']['z']+p['position2']['z'])/2-self.cz if self.horizontal else (p['position1']['x']+p['position2']['x'])/2-self.cx)-sign*4))
   self.board(h-10,y+3,sign*16,face,target)
   for u in (-h+rise+20,0,h-29):
    if u<u0+rise+9 or u>h-22:continue
    for k in range(3):self.p.put(*self.at(u+k,y+1,sign*16),f'projectseele:station_seat[facing={face}]',self.owner,'owned')
   # Tactile warning is parallel to the train, outside the four-metre aisle.
   self.fill(-h+1,y,sign*(edge+1),h-1,y,sign*(edge+1),'projectseele:station_tactile_warning')
   # A restrained underside of beams, battens and linear lights.
   for u in range(-h+3,h-2,4):self.fill(u,y+10,sign*8,u,y+10,sign*16,'minecraft:spruce_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]')
   for u in range(-h+5,h-3,12):self.fill(u,y+10,sign*8,u+4,y+10,sign*8,LIGHT)
  # Rebuild the pedestrian overbridge above the train envelope; all four
  # perimeter edges have guarding, including the previously open two ends.
  b=h-15;self.fill(b+7,y+7,-16,b+10,y+7,16,FLOOR)
  for u in (b+6,b+11):self.fill(u,y+8,-17,u,y+9,17,GLASS)
  for w in (-17,17):self.fill(b+6,y+8,w,b+11,y+9,w,GLASS)
  for sign in (-1,1):
   w=sign*12
   for i in range(7):
    self.fill(b+i,y+1,w-1,b+i,y+10,w+1,AIR);self.fill(b+i,y,w-1,b+i,y+i,w+1,DECK)
    self.fill(b+i,y+i+1,w-1,b+i,y+i+1,w+1,f'minecraft:smooth_quartz_stairs[facing={"east" if self.horizontal else "south"},half=bottom,shape=straight,waterlogged=false]')
   self.path('overbridge_stair_'+str(sign),[self.at(b-1,y+1,w),self.at(b+8,y+8,w)])
  self.path('overbridge',[self.at(b+8,y+8,-12),self.at(b+8,y+8,12)])
  for old,cross,state in retired_bridge_lamps:
   q=self.at(b+7,y+6,cross);support=self.at(b+7,y+7,cross)
   if q in getattr(self.scene,'source_BE_positions',set())or old_state(q)!=AIR or old_state(support)!=FLOOR:raise RuntimeError(('Retained lamp has no complete actual new bridge ceiling support',old,q,support))
   for cell in(q,support):
    if self.scene.protected[cell[1]-factory.LO[1],cell[2]-factory.LO[2],cell[0]-factory.LO[0]]:raise RuntimeError(('Retained lamp transfer meets protected device',cell))
   self.fill(b+7,y+6,cross,b+7,y+6,cross,state)
  # Flat moving walks belong to the lower circulation hall, with crossing
  # landings, not beside boarding doors or stairs at the platform edge.
  for begin,end in [(-h+12,-5),(5,h-12)]:
   if end-begin<10:continue
   for w,d in [(-4,True),(3,False)]:
    self.belt(begin,g,w,end-begin,d)
    self.fill(begin,g+1,w,end-1,g+1,w+1,AIR)
   self.path('concourse_'+str(begin),[self.at(begin-2,g+1,0),self.at(end+2,g+1,0)])
  return dict(station=self.name,line=self.line,center=[self.cx,y,self.cz],ground=g,half=h,platform_outer_width=17,minimum_boarding_aisle=4,walks=self.walks,boards=self.boards,belts=self.belts)

def main(apply=False):
 OUT.mkdir(parents=True,exist_ok=True);v.WORLD=scan.WORLD=WORLD;v.OUT=OUT;p=v.Painter();source=json.loads((ROOT/'artifacts/access_r22/transit/civil/station_contract.json').read_text(encoding='utf8'));native=json.loads((WORLD/'native_transit_r22.json').read_text(encoding='utf8'));records=[];total=0
 for record in source['stations']:
  x,y,z=record['center'];h=record['half'];g=record['ground'];dx,dz=(h+2,19) if record['horizontal'] else (19,h+2);lo=(x-dx,g-3,z-dz);hi=(x+dx,y+14,z+dz);factory.LO=lo;factory.HI=hi;s=factory.Scene()
  original_tags=dict(iter_block_entities(WORLD,v.DIM,lo,hi));s.source_BE_positions=set(original_tags)
  for q,be in original_tags.items():
   if str(be['id']) not in ('projectseele:station_departure_board','minecraft:sign'):s.protect((*q,*q))
  # Preserve the installed transfer passages through both station shells.
  for route in source['transfer_links']:
   if route['id'].endswith('/return'):continue
   path=route['path'];axis_x=abs(path[0][0]-path[-1][0])>abs(path[0][2]-path[-1][2])
   for xx,yy,zz in path:
    xx,yy,zz=map(math_floor,(xx,yy,zz));box=(xx-(0 if axis_x else 4),yy-3,zz-(4 if axis_x else 0),xx+(0 if axis_x else 4),yy+4,zz+(4 if axis_x else 0));a=tuple(max(box[i],lo[i]) for i in range(3));b=tuple(min(box[i+3],hi[i]) for i in range(3))
    if all(a[i]<=b[i] for i in range(3)):s.protect((*a,*b))
  platforms=[q for q in native['platforms'] if q['id'] in record['platform_ids']];r=RevisedStation(record,s,p,platforms);records.append(r.replan());total+=s.delta(p,r.owner)
 p.meta.update(stations=records,walk_nodes=[q for r in records for q in r['walks']],boards=[q for r in records for q in r['boards']],changed_cells=total,reference='JR East platform/concourse separation, visible boarding aisles, full stairwell guarding')
 p.save_plan('separated_stairs_and_guarded_platforms')
 if apply:p.apply('separated_stairs_and_guarded_platforms')
 (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('R23 repaired station groups',len(records),'changes',total,'native routes unchanged')
def math_floor(x):return int(np.floor(x))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
