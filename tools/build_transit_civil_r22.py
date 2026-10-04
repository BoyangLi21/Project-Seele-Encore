"""Civil works follow the evaluated two-line railway, including real MTR stairs."""
from pathlib import Path
import argparse,json,math
from collections import defaultdict
import numpy as np,nbtlib
import regional_voxels as v
from query_blocks import chunk_statuses,iter_block_entities
from measure_world_r40 import MeasuredWorld
from build_transit_civil_r20 import grouped
from build_station_boards_r19 import packed
ROOT=v.ROOT;OUT=ROOT/'artifacts/access_r22/transit/civil';REVIEW=ROOT/'run/saves/SEELE_R22_REVIEW'
AIR='minecraft:air';FLOOR='minecraft:smooth_stone';DECK='minecraft:light_gray_concrete';EDGE='projectseele:nerv_machine_edge';GLASS='projectseele:clear_glass';LIGHT='projectseele:nerv_strip_light'
def xyz(p):return tuple(p[k] for k in ('x','y','z'))
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def ff(p,box,state,owner):p.fill(*map(int,box),state,owner,'owned')

def transfer(p,name,start,direction,low,high,length):
 dx,dz=direction;face={(-1,0):'west',(1,0):'east',(0,-1):'north',(0,1):'south'}[direction];owner='r22/transfer/'+name;points=[]
 def at(n,y,w):return (start[0]+dx*n+(w if dz else 0),y,start[1]+dz*n+(w if dx else 0))
 for n in range(length+1):
  y=low+max(0,min(high-low,n-1));points.append([q+.5 if i!=1 else q for i,q in enumerate(at(n,y+1,0))])
  for w in range(-4,5):
   a=at(n,min(low,y)-1,w);b=at(n,high+5,w);ff(p,(*a,*b),AIR,owner)
   for h,state in [(-2,EDGE),(-1,DECK),(0,FLOOR)]:q=at(n,y+h,w);ff(p,(*q,*q),state,owner)
   q=at(n,y+5,w);ff(p,(*q,*q),LIGHT if w==0 and n%8==0 else DECK,owner)
   if abs(w)==4:
    for h in range(1,5):q=at(n,y+h,w);ff(p,(*q,*q),EDGE if h==1 else GLASS,owner)
  if 2<=n<=high-low+1:
   for w in (-1,0,1):q=at(n,y,w);ff(p,(*q,*q),f'minecraft:smooth_quartz_stairs[facing={face},half=bottom,shape=straight,waterlogged=false]',owner)
  orient='landing_bottom' if n==0 else 'transition_bottom' if n==1 else 'slope' if n<=high-low else 'transition_top' if n==high-low+1 else 'landing_top' if n==high-low+2 else 'flat'
  for w0,forward in [(-3,True),(2,False)]:
   for lane in (0,1):
    side='left' if (lane==0)==(face in ('east','north')) else 'right'
    for h,block in [(0,'escalator_step'),(1,'escalator_side')]:
     state=f'mtr:{block}[facing={face},orientation={orient},side={side}'+(f',direction={str(forward).lower()},status=true]' if h==0 else ']');q=at(n,y+h,w0+lane);ff(p,(*q,*q),state,owner)
 return dict(id=owner,path=points)

class Station:
 def __init__(self,p,name,line,platforms,ground):
  self.p=p;self.name=name;self.line=line;self.platforms=platforms;self.ground=ground;self.owner='r22/station/'+str(platforms[0]['id']);self.walks=[];self.boards=[];self.belts=[]
  centres=[[(q['position1'][k]+q['position2'][k])/2 for k in ('x','y','z')] for q in platforms];self.cx,self.y,self.cz=map(lambda n:int(round(n)),np.mean(centres,axis=0));q=platforms[0];self.horizontal=q['position1']['z']==q['position2']['z'];self.half=max(int(abs(q['position1']['x']-q['position2']['x'])+abs(q['position1']['z']-q['position2']['z']))//2 for q in platforms)+10
 def at(self,u,y,w):return (self.cx+u,y,self.cz+w) if self.horizontal else (self.cx+w,y,self.cz+u)
 def fill(self,u,y,w,U,Y,W,state):
  a=self.at(u,y,w);b=self.at(U,Y,W);ff(self.p,(*np.minimum(a,b),*np.maximum(a,b)),state,self.owner)
 def path(self,label,points):
  pts=[[x+.5,y,z+.5] for x,y,z in points]
  self.walks.extend([dict(id=self.owner+'/'+label,path=pts),dict(id=self.owner+'/'+label+'/return',path=list(reversed(pts)))])
 def belt(self,u,f,w,length,direction=True,rise=0):
  facing='east' if self.horizontal else 'south';states=[]
  if rise:
   states=[(0,f,'landing_bottom'),(1,f,'transition_bottom')]+[(i,f+i-1,'slope') for i in range(2,rise+1)]+[(rise+1,f+rise,'transition_top'),(rise+2,f+rise,'landing_top')]
  else:states=[(i,f,'landing_bottom' if i==0 else 'landing_top' if i==length-1 else 'flat') for i in range(length)]
  for i,y,orient in states:
   for lane in (0,1):
    side=('left' if lane==0 else 'right') if self.horizontal else ('right' if lane==0 else 'left')
    self.fill(u+i,y-1,w+lane,u+i,y-1,w+lane,DECK)
    self.fill(u+i,y+1,w+lane,u+i,y+4,w+lane,AIR)
    self.fill(u+i,y,w+lane,u+i,y,w+lane,f'mtr:escalator_step[direction={str(direction).lower()},facing={facing},orientation={orient},side={side},status=true]')
    self.fill(u+i,y+1,w+lane,u+i,y+1,w+lane,f'mtr:escalator_side[facing={facing},orientation={orient},side={side}]')
  self.belts.append(dict(start=self.at(u,f,w),length=len(states),rise=rise,direction=direction,axis='x' if self.horizontal else 'z'))
 def board(self,u,y,w,face,platform):
  at=self.at(u,y,w);backw=w+(1 if w>0 else -1)
  self.fill(u-1,y,backw,u+1,y+1,backw,EDGE)
  self.p.put(*at,f'projectseele:station_departure_board[facing={face},wayfinding=false]',self.owner,'owned')
  centre=tuple((platform['position1'][k]+platform['position2'][k])//2 for k in ('x','y','z'))
  self.p.block_entities[at]=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(at[0]),'y':nbtlib.Int(at[1]),'z':nbtlib.Int(at[2]),'PlatformCentre':nbtlib.Long(packed(centre)),'Station':nbtlib.String(self.name),'Route':nbtlib.String(self.line),'Row0':nbtlib.String('正在读取实时班次'),'Wayfinding':nbtlib.Byte(0)})
  self.p.block_entities[at]['NativePlatformId']=nbtlib.Long(platform['id'])
  self.boards.append(dict(position=at,platform=centre,platform_id=platform['id'],station=self.name,line=self.line))
 def build(self):
  h,y,g=self.half,self.y,self.ground
  self.fill(-h,g+1,-15,h,y+13,15,AIR);self.fill(-h,g-2,-15,h,g-1,15,DECK);self.fill(-h,g,-15,h,g,15,FLOOR)
  self.fill(-h,y-2,-15,h,y-1,15,DECK);self.fill(-h,y,-15,h,y,15,FLOOR)
  for side in (-1,1):
   self.fill(-h,y+1,side*15,h,y+1,side*15,EDGE);self.fill(-h,y+2,side*15,h,y+3,side*15,GLASS)
   self.fill(-h,y+10,side*15,h,y+10,side*15,EDGE)
   for u in range(-h+2,h,16):self.fill(u,g+1,side*15,u,y+10,side*15,DECK)
  self.fill(-h,y+11,-15,h,y+11,-2,DECK);self.fill(-h,y+11,2,h,y+11,15,DECK);self.fill(-h,y+12,-2,h,y+12,2,GLASS)
  for u in range(-h+7,h-3,12):
   for side in (-1,1):self.fill(u,y+10,side*9,u+3,y+10,side*9,LIGHT)
  for q in self.platforms:
   centre=[(q['position1'][k]+q['position2'][k])/2 for k in ('x','y','z')];offset=round(centre[2]-self.cz if self.horizontal else centre[0]-self.cx)
   self.fill(-h,y,offset-1,h,y+6,offset+1,AIR);self.fill(-h,y-1,offset-1,h,y-1,offset+1,'minecraft:gravel')
   for sign in (-1,1):
    edge=offset+sign*2;face=('south' if sign<0 else 'north') if self.horizontal else ('east' if sign<0 else 'west')
    self.fill(-h+6,y,edge,h-6,y,edge,f'mtr:platform[door_type=none,facing={face},side=0]');self.fill(-h+6,y,offset+sign*3,h-6,y,offset+sign*3,'projectseele:station_tactile_warning')
  # Two paired stairs at each end-side platform; the middle path stays walkable.
  rise=y-g;u0=-h+5
  for sign in (-1,1):
   w0=-13 if sign<0 else 7;w1=-8 if sign<0 else 12;wm=-10 if sign<0 else 10
   self.fill(u0-1,g+1,min(w0,w1),u0+rise+4,y+6,max(w0,w1)+1,AIR)
   self.belt(u0,g,w0,0,True,rise);self.belt(u0,g,w1,0,False,rise)
   for i in range(rise):
    self.fill(u0+i+1,g,wm,u0+i+1,g+i,wm,DECK)
    facing='east' if self.horizontal else 'south';self.fill(u0+i+1,g+i+1,wm,u0+i+1,g+i+1,wm,f'minecraft:smooth_quartz_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]')
   self.fill(u0+rise+1,y,min(w0,w1),u0+rise+5,y,max(w0,w1)+1,FLOOR)
   # Reapply the short top transitions after the landing floor.
   for w,d in [(w0,True),(w1,False)]:self.belt(u0,g,w,0,d,rise)
   self.path('stair_'+str(sign),[self.at(u0-1,g+1,wm),self.at(u0+1,g+1,wm),self.at(u0+rise+2,y+1,wm),self.at(u0+rise+6,y+1,wm)])
   self.path('ground_access_'+str(sign),[self.at(u0-2,g+1,sign*16),self.at(u0-2,g+1,wm),self.at(u0-1,g+1,wm)])
   beltstart=u0+rise+9;beltend=h-19
   if beltend-beltstart>=12:self.belt(beltstart,y,w0,beltend-beltstart,sign>0)
   self.path('platform_'+str(sign),[self.at(u0+rise+6,y+1,wm),self.at(h-5,y+1,wm)])
   face=('south' if sign<0 else 'north') if self.horizontal else ('east' if sign<0 else 'west')
   q=min(self.platforms,key=lambda q:abs(((q['position1']['z']+q['position2']['z'])/2-self.cz if self.horizontal else (q['position1']['x']+q['position2']['x'])/2-self.cx)-sign*4))
   self.board(h-10,y+4,sign*14,face,q)
   for u in range(h-27,h-20):self.p.put(*self.at(u,y+1,sign*13),f'projectseele:station_seat[facing={face}]',self.owner,'owned')
  # A seven-metre-clear footbridge, with stairs at both platforms, crosses over
  # the trains. No path is advertised across an unprotected track trench.
  u0=h-15
  self.fill(u0+7,y+7,-14,u0+10,y+7,14,FLOOR)
  for u in (u0+6,u0+11):self.fill(u,y+8,-14,u,y+9,14,GLASS)
  for side in (-1,1):
   w=side*10
   for i in range(7):
    self.fill(u0+i,y+1,w-1,u0+i,y+10,w+1,AIR);self.fill(u0+i,y,w-1,u0+i,y+i,w+1,DECK)
    self.fill(u0+i,y+i+1,w-1,u0+i,y+i+1,w+1,f'minecraft:smooth_quartz_stairs[facing={"east" if self.horizontal else "south"},half=bottom,shape=straight,waterlogged=false]')
   self.path('footbridge_stair_'+str(side),[self.at(u0-1,y+1,w),self.at(u0+8,y+8,w)])
  self.path('footbridge',[self.at(u0+8,y+8,-10),self.at(u0+8,y+8,10)])
  return dict(station=self.name,line=self.line,center=[self.cx,y,self.cz],ground=g,half=h,horizontal=self.horizontal,platform_ids=[p['id'] for p in self.platforms],walks=self.walks,boards=self.boards,belts=self.belts)

def main(apply=False,built='built4'):
 OUT.mkdir(parents=True,exist_ok=True);v.WORLD=REVIEW;v.OUT=OUT;p=v.Painter()
 before=load(OUT.parent.parent/'native_before.json');native=load(OUT.parent/built/'native_commission.json');old=load(ROOT/'artifacts/world_rebuild_r20/transit/civil/viaduct_stations_and_streets/places.json');assert native['passed']
 for name,box in [('pyramid',(-194,-672,-4,254,70,444)),('surface_cages',(-65,32,-175,195,90,20)),('gateway_lift',(-370,-490,739,-350,155,760))]:p.protect(box,name)
 plots=load(ROOT/'artifacts/world_quality_r02/surface_layout.json')['kept_plots']
 for b in plots:
  x,X,z,Z=b['bounds'];p.protect((x,b['floor'],z,X,b['floor']+b.get('storeys',1)*5+6,Z),b['id'])
 # Remove measured superseded elevated rail formations, never ground streets.
 columns={}
 for r in before['curves']:
  if r['mode']!='TRAIN' or r['points'][0][1]<0:continue
  for xx,yy,zz in r['points']:
   x,y,z=math.floor(xx),math.floor(yy),math.floor(zz)
   for dx in range(-3,4):
    for dz in range(-3,4):columns[x+dx,z+dz]=min(y,columns.get((x+dx,z+dz),y))
 for x,X,z,y in grouped(columns):
  for state in (DECK,'minecraft:gravel',FLOOR,EDGE,GLASS,'minecraft:light_gray_stained_glass'):
   p.match((x,y-3,z,X,y+6,z),state,AIR,'r22/retired_elevated_alignment')
 # Old piers and superseded station roofs must not survive as floating relics.
 terrain=np.load(ROOT/'artifacts/world_quality_r02/terrain_target.npz');ox,oz=map(int,terrain['origin']);height=terrain['height']
 def ground(x,z):return int(height[z-oz,x-ox]) if 0<=z-oz<height.shape[0] and 0<=x-ox<height.shape[1] else 70
 for x,y,z in old['piers']:
  g=ground(x,z);p.match((x-1,g+1,z-1,x+1,y-4,z+1),DECK,AIR,'r22/retired_viaduct_pier')
 for st in old['stations']:
  if st['center'][1]<0:continue
  x,y,z=st['center'];h=st['half'];dx,dz=(h,15) if st['horizontal'] else (15,h)
  ff(p,(x-dx,st['ground']+1,z-dz,x+dx,y+14,z+dz),AIR,'r22/superseded_station_volume')
 # Group the current platforms into through stations using their native route
 # membership and the surveyed station footprints, not an old two-stop list.
 groups=defaultdict(list);source={}
 for route in native['routes']:
  if route['routeNumber'] not in ('R1','S1'):continue
  for pid in dict.fromkeys(q['platformId'] for q in route['routePlatformData']):
   q=next(p for p in native['platforms'] if p['id']==pid);mid=np.mean([xyz(q['position1']),xyz(q['position2'])],axis=0)
   st=min((x for x in old['stations'] if x['center'][1]>0),key=lambda x:sum((x['center'][k]-mid[k])**2 for k in (0,2)))
   key=route['routeNumber'],st['station'];groups[key].append(q);source[key]=st
 records=[]
 for key,platforms in groups.items():records.append(Station(p,key[1],key[0],platforms,source[key]['ground']).build())
 # Lay one union of track clearance after station construction so crossing
 # curves cannot refill one another. Station lip blocks sit outside this core.
 decks=defaultdict(set);cores=defaultdict(set);supports=[]
 for r in native['curves']:
  if r['mode']!='TRAIN' or r['points'][0][1]<0:continue
  for i,(xx,yy,zz) in enumerate(r['points']):
   x,y,z=math.floor(xx),math.floor(yy),math.floor(zz)
   for dx in range(-3,4):
    for dz in range(-3,4):decks[x+dx,z+dz].add(y)
   for dx in range(-1,2):
    for dz in range(-1,2):cores[x+dx,z+dz].add(y)
   if r['kind']=='rail' and i%48==0:supports.append((x,y,z))
 for (x,z),ys in decks.items():
  for y in ys:ff(p,(x,y-3,z,x,y-1,z),DECK,'r22/evaluated_viaduct_deck')
 road=np.load(ROOT/'artifacts/world_rebuild_r20/transit/civil/road_contract.npz');rx,rz=map(int,road['origin']);piers=[];relocated_piers=[]
 road_mask=road['mask']
 # Original positive road operations include later R07/R10/UN expansion widths.
 expansion=load(ROOT/'artifacts/rebuild_r44/surface_network/road_authority_additions.json')
 authored_paving={tuple(row['pos'])for row in expansion['columns']}
 def road_footprint(x,z):
  for X in range(x-3,x+4):
   for Z in range(z-3,z+4):
    if (X,Z)in authored_paving:return True
    if 0<=Z-rz<road_mask.shape[0]and 0<=X-rx<road_mask.shape[1]and road_mask[Z-rz,X-rx]:return True
  return False
 # Verify all nine actual foundation columns, not an old centre-height sample.
 pier_world=MeasuredWorld(REVIEW)
 for sx,sy,sz in supports:pier_world.box((sx-11,31,sz-11),(sx+11,sy-3,sz+11))
 pier_world.load()
 shapes={v.canonical_state(state):boxes for state,boxes in load(REVIEW/'native_collision_shapes.json').items()}
 selected=set(pier_world.selected)
 tag_lo=(min(x for x,z in selected)*16,31,min(z for x,z in selected)*16)
 tag_hi=(max(x for x,z in selected)*16+15,max(y for x,y,z in supports)-3,max(z for x,z in selected)*16+15)
 pier_tags=dict(iter_block_entities(REVIEW,v.DIM,tag_lo,tag_hi,selected_chunks=selected))
 natural={'minecraft:grass_block','minecraft:dirt','minecraft:stone','minecraft:gravel','minecraft:deepslate','minecraft:sandstone','minecraft:clay'}
 blank={'minecraft:air','minecraft:cave_air','minecraft:void_air'}
 planned_device_boxes=[op.box for op in p.ops if op.state not in {AIR,DECK}and op.state.partition('[')[0]not in natural]
 def actual_full_soil(X,Y,Z):
  state=pier_world.get(X,Y,Z)
  return state is not None and state.partition('[')[0]in natural and shapes.get(state)==[[0,0,0,1,1,1]]
 def foundation_columns(X,y,Z):
  result=[]
  for xx in range(X-1,X+2):
   for zz in range(Z-1,Z+2):
    actual=[yy for yy in range(34,y-3)if actual_full_soil(xx,yy,zz)]
    if not actual:return None
    datum=max(actual);base=datum-2;top=y-4
    if not actual_full_soil(xx,base-1,zz):return None
    for yy in range(base,top+1):
     state=pier_world.get(xx,yy,zz)
     if (xx,yy,zz)in pier_tags or (xx,yy,zz)in p.block_entities:return None
     if state not in blank and (state is None or state.partition('[')[0]not in natural):return None
    for protected in p.keep_boxes:
     a,b,c,A,B,C=protected['box']
     if protected['modes']and 'owned'not in protected['modes']:continue
     if a<=xx<=A and c<=zz<=C and base<=B and top>=b:return None
    if any(a<=xx<=A and c<=zz<=C and base<=B and top>=b for a,b,c,A,B,C in planned_device_boxes):return None
    result.append(dict(x=xx,z=zz,actual_ground=datum,base=base,top=top,bearing=(xx,base-1,zz)))
  return result
 def pier_site(x,y,z):
  offsets=sorted(((dx,dz)for dx in range(-10,11)for dz in range(-10,11)),key=lambda q:(q[0]*q[0]+q[1]*q[1],q))
  for dx,dz in offsets:
   X,Z=x+dx,z+dz
   if road_footprint(X,Z):continue
   if any(y not in decks.get((X+a,Z+b),set())for a in(-1,0,1)for b in(-1,0,1)):continue
   if any(abs(X-q[0])<15 and abs(Z-q[2])<15 for q in piers):continue
   if any(abs(X-r['center'][0])<r['half']+8 and abs(Z-r['center'][2])<r['half']+8 for r in records):continue
   if foundation_columns(X,y,Z)is not None:return X,Z
  raise RuntimeError(('No complete supported off-road pier site; structural review required',x,y,z))
 for x,y,z in supports:
  if any(abs(x-q[0])<15 and abs(z-q[2])<15 for q in piers):continue
  if road_footprint(x,z):
   original=x,y,z;x,z=pier_site(x,y,z);relocated_piers.append(dict(before=original,after=(x,y,z)))
  if any(abs(x-r['center'][0])<r['half']+8 and abs(z-r['center'][2])<r['half']+8 for r in records):continue
  foundations=foundation_columns(x,y,z)
  if foundations is None:raise RuntimeError(('Complete nine-column pier foundation or device keepout failed',x,y,z))
  for column in foundations:ff(p,(column['x'],column['base'],column['z'],column['x'],column['top'],column['z']),DECK,'r22/viaduct_pier')
  piers.append((x,y,z))
 for (x,z),ys in cores.items():
  for y in ys:ff(p,(x,y,z,x,y+6,z),AIR,'r22/train_body_clearance');ff(p,(x,y-1,z,x,y-1,z),'minecraft:gravel','r22/ballast')
 links=[transfer(p,'hakone_direct',(-1480,666),(0,-1),118,130,20),transfer(p,'bay_direct',(350,300),(-1,0),94,106,22)]
 links += [dict(id=x['id']+'/return',path=list(reversed(x['path']))) for x in links[:]]
 p.meta.update(stations=records,piers=piers,relocated_piers=relocated_piers,walk_nodes=[w for r in records for w in r['walks']]+links,boards=[b for r in records for b in r['boards']],belts=[b for r in records for b in r['belts']],surface_routes=2,transfer_links=links)
 p.save_plan('two_line_stations_and_viaducts')
 if apply:
  missing=[list(q) for q,status in chunk_statuses(REVIEW,v.DIM,p.by_chunk).items() if status!='full']
  (REVIEW/'r22_generate_chunks.json').write_text(json.dumps(missing))
  if missing:raise RuntimeError(f'Native generation is required for {len(missing)} chunks before any further civil writes')
  p.apply('two_line_stations_and_viaducts')
 (OUT/'station_contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('R22 physical station groups',len(records),'piers',len(piers),'ops',len(p.ops))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--built',default='built4');a=ap.parse_args();main(a.apply,a.built)
