"""Airport civil works and physical boarding connections for the native F2 line."""
import copy,json,math
from pathlib import Path
import nbtlib
import regional_voxels as v
from regional_architecture import box_room,bench
from build_station_boards_r19 import packed
ROOT=v.ROOT;OUT=ROOT/'artifacts/world_repair_r21/airport';WORLD=ROOT/'run/saves/SEELE_R21_REVIEW'
FLOOR='projectseele:nerv_floor_panel';WALL='projectseele:nerv_wall_panel';STRUCT='projectseele:nerv_structural_panel';LIGHT='projectseele:nerv_strip_light';AIR='minecraft:air'
def main(apply=False):
 v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();o='r21/nerv_airport';walks=[]
 def b(box,state):p.fill(*box,state,o,'owned')
 def room(x,z,X,Z,f,h):
  b((x,f-1,z,X,f+h,Z),STRUCT);b((x+1,f+1,z+1,X-1,f+h-1,Z-1),AIR);b((x+1,f,z+1,X-1,f,Z-1),FLOOR)
  for a in range(x+6,X-4,12):b((a,f+2,z,a+7,f+h-2,z),'projectseele:clear_glass');b((a,f+h,z+3,a+3,f+h,Z-3),LIGHT)
 def path(name,pts):
  walks.extend([dict(id='r21/airport/'+name,path=pts),dict(id='r21/airport/'+name+'/return',path=list(reversed(pts)))])
 # Airport datum is surveyed terrain height plus compacted formation. The
 # aircraft envelope is cleared before buildings, never after furnishing.
 p.grade(350,-177,1350,86,72,o+'/terrain',18)
 b((350,63,-177,1350,70,86),'minecraft:stone');b((350,71,-177,1350,72,86),'minecraft:gray_concrete');b((350,73,-177,1350,123,86),AIR)
 for z in (-145,-95):
  b((710,72,z-17,1350,72,z+17),'minecraft:black_concrete')
  for x in range(724,1340,28):b((x,72,z-1,x+11,72,z+1),'minecraft:white_concrete')
  for zz in (z-16,z+16):b((710,72,zz,1350,72,zz),'minecraft:white_concrete')
  for x in range(720,1351,24):
   for zz in (z-20,z+20):b((x,72,zz,x,72,zz),'minecraft:sea_lantern')
  for x in (728,1316):
   for zz in range(z-12,z+13,4):b((x,72,zz,x+9,72,zz+1),'minecraft:white_concrete')
 # Public terminal is outside every aircraft wing sweep.
 room(364,38,478,82,72,11)
 for x in (385,398,440):b((x,73,38,x+5,78,38),AIR)
 b((385,78,38,390,78,38),STRUCT)
 for x in range(378,466,14):
  p.put(x,73,71,'projectseele:station_seat[facing=north]',o);p.put(x+2,73,71,'projectseele:station_seat[facing=north]',o)
 for x in range(371,403,3):p.put(x,73,47,'projectseele:nerv_workstation[facing=south]',o)
 room(488,41,507,60,72,32)
 b((489,99,42,506,104,59),'projectseele:clear_glass');b((488,105,41,507,106,60),STRUCT)
 # A simple maintenance ladder occupies a continuous vertical shaft.
 b((490,73,43,490,100,43),'minecraft:ladder[facing=south]')
 b((490,73,42,490,100,42),STRUCT);b((489,73,41,492,76,41),AIR)
 for x,z in [(545,47),(645,47)]:
  room(x-38,z-20,x+38,z+35,72,23);b((x-31,73,z-20,x+31,92,z-20),AIR)
  for xx in (x-35,x+35):b((xx,73,z-21,xx,91,z-21),'projectseele:nerv_machine_hazard')
 # Connected, sheltered passenger gallery ends before the retracting stair.
 room(434,17,670,29,72,7)
 b((437,73,27,445,78,38),AIR);b((437,72,27,445,72,38),FLOOR);b((436,73,28,436,79,38),WALL);b((446,73,28,446,79,38),WALL);b((436,79,28,446,79,38),STRUCT)
 b((663,73,17,668,77,17),AIR)
 for x in (511,611):p.sign(x,75,28,['NERV','← 航空整备库','机务检修',''],o)
 # The existing A320 native doorway measured in R20 is translated/rotated
 # without changing cabin scale, seat layout or flight physics.
 old=json.loads((WORLD/'regional_boarding_gates.json').read_text(encoding='utf8'));base=next(g for g in old['gates'] if g['id']=='bay');gates=[]
 for name,head,rotate in [('nerv_airport',[670.5,72,-9.5],False),('un_airport',[6720.5,74,-6109.5],True)]:
  g=copy.deepcopy(base);g['id']=name;g['head']=head
  def transform(q):
   dx,dy,dz=[q[i]-base['head'][i] for i in range(3)]
   if not rotate:dz=-dz
   return [head[0]+(dz if rotate else dx),head[1]+dy,head[2]+(-dx if rotate else dz)]
  for k in ('entry','landing','door'):g[k]=transform(base[k])
  g['stairs']=[]
  for x,y,z,state in base['stairs']:
   # Transform cell centres, preserving inclusive block coordinates.
   q=transform([x+.5,y,z+.5]);pos=[math.floor(q[0]),round(q[1]),math.floor(q[2])]
   if rotate:
    for a,c in [('north','WEST'),('east','NORTH'),('south','EAST'),('west','SOUTH')]:state=state.replace('facing='+a,'facing='+c)
    state=state.lower()
   else:state=state.replace('facing=south','facing=NORTH').replace('facing=north','facing=south').replace('facing=NORTH','facing=north')
   g['stairs'].append([*pos,state]);b((*pos,*pos),AIR)
  g['direction']='east' if rotate else 'north';g['survey_source']='Rigid transform / opposite symmetric R20 native A320 door; R21 live boarding required';g.pop('native_door',None);gates.append(g)
 # Use the aircraft's south doorway at NERV. Passengers never cross the
 # arrival taxiway or step over a runway to reach a north-side stair.
 entry=gates[0]['entry'];bx=math.floor(entry[0]);bz=math.floor(entry[2])
 b((bx-2,72,bz,bx+2,72,23),FLOOR);b((bx-1,73,bz,bx+1,77,23),AIR)
 b((bx-1,73,17,bx+1,77,17),AIR)
 # UN uses the present aviation terminal and parallel taxiway. Add a separate
 # inbound strip east of the original runway, with two taxi bends to its gate.
 b((6812,70,-6660,6852,73,-6000),'minecraft:stone');b((6812,74,-6660,6852,74,-6000),'minecraft:black_concrete');b((6812,75,-6660,6852,98,-6000),AIR)
 for z in range(-6640,-6010,28):b((6831,74,z,6833,74,z+11),'minecraft:white_concrete')
 samples=json.loads((OUT/'native/track_samples.json').read_text(encoding='utf8'))
 for r in samples:
  if r['kind'] in ('platform','siding') or r['mode']!='AIRPLANE':continue
  for i,(xx,yy,zz) in enumerate(r['points']):
   if yy>75 or r['kind']=='runway':continue
   x,y,z=math.floor(xx),round(yy),math.floor(zz)
   b((x-8,y-2,z-8,x+8,y-1,z+8),'minecraft:stone')
   runway='roll' in r['id'];b((x-8,y,z-8,x+8,y,z+8),'minecraft:black_concrete' if runway else 'minecraft:gray_concrete')
   b((x-17,y+1,z-17,x+17,y+15,z+17),AIR)
   if runway:
    if i%28<12:b((x,y,z,x,y,z),'minecraft:white_concrete')
   elif i%3==0:b((x,y,z,x,y,z),'minecraft:yellow_concrete')
 # Native swept envelopes above deliberately precede these terminal paths.
 unentry=gates[1]['entry'];ux=math.floor(unentry[0]);uz=math.floor(unentry[2])
 b((6670,74,-6048,ux,74,-6044),FLOOR);b((ux-2,74,uz,ux+2,74,-6044),FLOOR)
 for x in (ux-3,ux+3):b((x,75,uz-2,x,75,-6044),'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]')
 b((ux-2,75,uz-2,ux+2,79,uz+2),AIR)
 for x in (ux-3,ux+3):b((x,75,-6086,x,75,-6074),AIR)
 b((ux-3,75,-6049,ux-3,76,-6043),AIR)
 for gate in gates:
  for x,y,z,_ in gate['stairs']:b((x,y,z,x,y,z),AIR)
 # Flush terminal boundaries and real departure display at both airports.
 for name,at,support,head,facing in [('NERV 航空基地',(381,76,36),(381,76,37),(650,72,-10),'north'),('联合国总部机场',(6683,78,-6041),(6683,78,-6040),(6720,74,-6090),'north')]:
  b((*support,*support),STRUCT);p.put(*at,f'projectseele:station_departure_board[facing={facing}]',o,'owned')
  p.block_entities[at]=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(at[0]),'y':nbtlib.Int(at[1]),'z':nbtlib.Int(at[2]),'PlatformCentre':nbtlib.Long(packed(head)),'Station':nbtlib.String(name),'Route':nbtlib.String('F2')})
 p.sign(385,78,37,['NERV 航空基地','联合国总部 F2','高速运输 每分钟一班','由北侧连廊登机'],o)
 path('nerv_terminal_boarding',[[441.5,73,42.5],[441.5,73,23.5],[entry[0],73,23.5],entry])
 path('un_terminal_boarding',[[6674.5,75,-6046.5],[ux+.5,75,-6046.5],[ux+.5,75,uz+.5]])
 vehicles=[dict(key='r21/nerv/transport'+str(i),id='superbwarfare:ac_130h',position=[x+.5,73,60.5],yaw=180) for i,x in enumerate([545,645])]+[dict(key='r21/nerv/fighter'+str(i),id='superbwarfare:j_16',position=[x+.5,73,43.5],yaw=180) for i,x in enumerate([746,806])]
 p.meta.update(walk_nodes=walks,boarding=gates,vehicles=vehicles,datum=72)
 (OUT/'boarding_gates.json').write_text(json.dumps(gates,ensure_ascii=False,indent=2),encoding='utf8');(OUT/'vehicles.json').write_text(json.dumps(vehicles,indent=2),encoding='utf8')
 p.apply('nerv_un_airports') if apply else p.save_plan('nerv_un_airports')
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
