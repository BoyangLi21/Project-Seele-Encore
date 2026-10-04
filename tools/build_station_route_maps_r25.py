"""All-stop diagrams before station approaches, sourced from the actual MTR routes."""
from pathlib import Path
from collections import defaultdict
import argparse,copy,json,math
import nbtlib
import regional_voxels as v
from query_blocks import read_box,iter_block_entities,AIR
from station_sign_readers_r44 import reader_visibility
from station_island_bridge_maps_r45 import island_bridge_map_rows
from station_route_contract_r44 import RouteDiagrams
from complete_station_platform_service_r45 import platform_service_rows, refresh_existing_route_maps_rows, airport_service_rows

ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R25_REVIEW';OUT=ROOT/'artifacts/facility_r25/station_maps'
NORMAL={'north':(0,-1),'south':(0,1),'west':(-1,0),'east':(1,0)}
def main(apply=False,native_path=None):
 OUT.mkdir(parents=True,exist_ok=True);v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
 native_path=Path(native_path) if native_path is not None else ROOT/'artifacts/rebuild_r45/transport_controls_agent/current_native_snapshot.json';native=json.loads(native_path.read_text(encoding='utf8'))
 platforms={q['id']:q for q in native['platforms']};routes=[q for q in native['routes'] if q['transportMode']=='TRAIN']
 def center(platform):return tuple((platform['position1'][k]+platform['position2'][k])/2 for k in ('x','y','z'))
 def station(pid):
  c=center(platforms[pid]);matches=[]
  for s in native['stations']:
   if all(min(s['position1'][k],s['position2'][k])<=q<=max(s['position1'][k],s['position2'][k]) for k,q in zip(('x','y','z'),c)):
    volume=math.prod(abs(s['position1'][k]-s['position2'][k])+1 for k in ('x','y','z'));matches.append((volume,s['name']))
  assert matches,('No native station',pid,c)
  return min(matches)[1].split('|')[0]
 names={pid:station(pid) for r in routes for pid in dict.fromkeys(q['platformId'] for q in r['routePlatformData'])}
 lines=defaultdict(set)
 for r in routes:
  for q in r['routePlatformData']:lines[names[q['platformId']]].add(r['routeNumber'])
 diagrams=RouteDiagrams(native_path,ROOT/'artifacts/repair_r43/facility_catalogue/catalogue.json')
 def diagram(pid,face,preferred_line=''):
  d=diagrams.diagram(pid,face,preferred_line)
  return d['line'],d['station'],d['rows']
 specs=[];surface=json.loads((ROOT/'artifacts/access_r22/transit/civil/station_contract.json').read_text(encoding='utf8'))['stations']
 for r in surface:
  specs.append(dict(center=r['center'],feet=r['ground']+1,horizontal=r['horizontal'],half=r['half'],platform_ids=r['platform_ids'],level='进站层'))
 # Underground platforms have their own fixed passenger approaches. Two
 # adjoining headquarters tracks share one concourse but keep direction IDs.
 for route in routes:
  if not route['routeNumber'].startswith('U'):continue
  for pid in dict.fromkeys(q['platformId'] for q in route['routePlatformData']):
   platform=platforms[pid];c=center(platform);horizontal=platform['position1']['x']!=platform['position2']['x'];half=int(abs(platform['position1']['x' if horizontal else 'z']-platform['position2']['x' if horizontal else 'z'])/2)
   specs.append(dict(center=list(map(int,c)),feet=int(c[1])+1,horizontal=horizontal,half=half,platform_ids=[pid],level='站厅'))
 refresh_rows,refresh_audit,refresh_held=refresh_existing_route_maps_rows(WORLD,surface,diagrams,json.loads((ROOT/'artifacts/repair_r43/facility_catalogue/catalogue.json').read_text(encoding='utf8')))
 if refresh_held:raise RuntimeError(('Retained map identity/type unresolved',refresh_held))
 refreshed={tuple(row['pos']):nbtlib.parse_nbt(row['after_nbt']) for row in refresh_rows}
 for row in refresh_rows:
  p.update_block_entity(tuple(row['pos']),row['before'],nbtlib.parse_nbt(row['before_nbt']),nbtlib.parse_nbt(row['after_nbt']),row['owner'])
 installed=[];held=[];occupied=set();walks=[]
 shapes=json.loads((WORLD/'native_collision_shapes.json').read_text(encoding='utf8'))
 def support(state):
  boxes=[] if state.split('[')[0] in AIR else shapes.get(state)
  if boxes is None:return False
  return any(b[0]<=.3 and b[3]>=.7 and b[2]<=.3 and b[5]>=.7 and b[4]>=.9 for b in boxes) and not any(k in state for k in ('water','lcl','fence','wall[','bars','sign','escalator_side'))
 for r in specs:
  x,rail_y,z=r['center'];feet=r['feet'];h=r['half'];horizontal=r['horizontal'];dx,dz=(h+3,23) if horizontal else (23,h+3)
  lo=(x-dx,feet-2,z-dz);hi=(x+dx,feet+7,z+dz);cells=read_box(WORLD,v.DIM,lo,hi);tags=dict(iter_block_entities(WORLD,v.DIM,lo,hi));tags.update({q:t for q,t in refreshed.items() if q in tags})
  def at(u,y,w):return (x+u,y,z+w) if horizontal else (x+w,y,z+u)
  def state(q):return cells.get(q,'UNKNOWN')
  for side in (-1,1):
   axis='z' if horizontal else 'x';origin=z if horizontal else x;pid=min(r['platform_ids'],key=lambda p:-side*((platforms[p]['position1'][axis]+platforms[p]['position2'][axis])/2-origin))
   facing=('south' if side<0 else 'north') if horizontal else ('east' if side<0 else 'west');nx,nz=NORMAL[facing];line,label,rows=diagram(pid,facing)
   existing=[q for q,tag in tags.items() if int(tag.get('NativePlatformId',-1))==pid and tag.get('MapRows') and 'facing='+facing in state(q)]
   if existing:
    if any([str(t) for t in tags[q]['MapRows']]!=diagrams.diagram(pid,facing,str(tags[q].get('Route','')))['rows'] for q in existing):
     raise RuntimeError(('Existing native diagram requires exact NBT refresh',pid,existing))
    continue
   choice=None
   # Place at the incoming stair/entrance, outside the two-block belts. All
   # three physical panel cells, backing and standing room are measured.
   for mount in ('wall','stand'):
    for u in list(range(-h+5,-h+25,3))+list(range(-15,16,5)):
     if choice:break
     for wabs in ((16,14,12,10,18,20) if mount=='wall' else (12,14,16,18)):
      q=at(u,feet+1,side*wabs);front=[(q[0]+(d if nz else 0),q[1]+dy,q[2]+(d if nx else 0)) for d in (-1,0,1) for dy in (0,1)]
      if any(pos in occupied or pos in tags or state(pos).split('[')[0] not in AIR|{'minecraft:light'} for pos in front):continue
      reader=(q[0]+nx*2,feet,q[2]+nz*2)
      if not support(state((reader[0],feet-1,reader[2]))) or any(state((reader[0],feet+k,reader[2])).split('[')[0] not in AIR|{'minecraft:light'} for k in (0,1)):continue
      approach=[(q[0]+nx*d,feet,q[2]+nz*d) for d in (1,2,3,4)]
      if any(not support(state((X,Y-1,Z))) or any((X,Y+k,Z) in occupied or state((X,Y+k,Z)).split('[')[0] not in AIR|{'minecraft:light'} for k in (0,1)) for X,Y,Z in approach):continue
      if mount=='wall':
       back=[(X-nx,Y,Z-nz) for X,Y,Z in front]
       if not all(support(state(pos)) for pos in back):continue
       rods=[]
      else:
       rods=[(q[0]+(d if nz else 0),feet+dy,q[2]+(d if nx else 0)) for d in (-1,1) for dy in (0,1)]
       if any(state(pos).split('[')[0] not in AIR|{'minecraft:light'} or not support(state((pos[0],feet-1,pos[2]))) for pos in rods):continue
       if any('escalator' in state((pos[0],feet-1,pos[2])) for pos in rods):continue
      optical=reader_visibility(state,lambda s: [] if s.split('[')[0] in AIR else shapes.get(s),q,facing,reader,direction=True,route_map=True)
      if not optical['clear']:continue
      choice=(q,front,rods,reader,mount);break
    if choice:break
   if not choice:held.append(dict(station=label,line=line,side=side,centre=r['center'],feet=feet));continue
   q,front,rods,reader,mount=choice;occupied.update(front+rods)
   block=f'projectseele:station_departure_board[facing={facing},wayfinding=true]';p.match((*q,*q),state(q),block,'r25/native_route_diagram_before_boarding')
   for pos in rods:p.match((*pos,*pos),state(pos),'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]','r25/floor_anchored_route_map')
   tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Wayfinding':nbtlib.Byte(1),'Station':nbtlib.String(label+' · '+r['level']),'Route':nbtlib.String(line+'  全线站序 / 下一站'),'PlatformCentre':nbtlib.Long(0),'NativePlatformId':nbtlib.Long(pid),'MapRows':nbtlib.List[nbtlib.String]([nbtlib.String(t) for t in rows])})
   p.block_entities[q]=tag
   installed.append(dict(station=label,line=line,platform=pid,position=q,facing=facing,mount=mount,rows=rows,reader=reader,supports=rods))
   start=[q[0]+nx*4+.5,feet,q[2]+nz*4+.5];end=[reader[0]+.5,feet,reader[2]+.5]
   walks.append(dict(id='r25/station_map/'+str(pid)+'/'+str(side),start=start,end=end,path=[start,end],readingBoard=list(q)))
 service_rows,service_maps,service_held=platform_service_rows(WORLD,surface,diagrams,reserved=occupied)
 airport_rows,airport_maps,airport_held=airport_service_rows(WORLD,diagrams)
 service_rows.extend(airport_rows)
 service_held.extend(airport_held)
 for m in airport_maps:
  d=m['actual_diagram'];service_maps.append(dict(m,station=d['station'],line=d['line'],platform=d['platform'],complete_attachment=[b['pos'] for b in m['backing']]))
 island_rows,island_maps,island_held=island_bridge_map_rows(WORLD,surface,diagrams)
 service_rows.extend(island_rows);service_held.extend(island_held)
 for m in island_maps:
  d=m['actual_diagram'];service_maps.append(dict(m,line=d['line'],complete_attachment=m['load_path']['full_attachment'],complete_hanger=m['load_path']['full_frame']))
 for row in service_rows:
  q=tuple(row['pos']);p.match((*q,*q),row['before'],row['after'],row['owner'])
  if row['after_nbt'] is not None:p.block_entities[q]=nbtlib.parse_nbt(row['after_nbt'])
 for board in service_maps:
  installed.append(dict(station=board['station'],line=board['actual_diagram']['line'],platform=board['platform'],position=board['anchor'],facing=board['actual_diagram']['physical_face'],mount='retained_whole_outer_frame',rows=board['actual_diagram']['rows'],reader=board['reader'],supports=board['complete_attachment']))
  q=board['anchor'];path=board['reader_approach']
  walks.append(dict(id='r45/platform_route_map/'+str(board['platform'])+'/'+','.join(map(str,q)),start=path[0],end=path[-1],path=path,readingBoard=list(q)))
 held.extend(service_held)
 p.meta.update(retained_map_text=refresh_audit,boards=installed,held=held,active_train_routes=[r['routeNumber'] for r in routes],native_station_labels=names,walk_nodes=walks)
 p.save_plan('all_stop_station_maps')
 if apply:p.apply('all_stop_station_maps')
 (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Station diagrams',len(installed),'held',held)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--native-snapshot',type=Path);args=ap.parse_args();main(args.apply,args.native_snapshot)
