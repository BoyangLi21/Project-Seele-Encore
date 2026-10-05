"""Passenger details and native MTR platform gates, outside all access cores."""
from pathlib import Path
import argparse,json,math,nbtlib,numpy as np
import regional_voxels as v,scan_regional_completion as scan,plan_factory_r20 as f
from query_blocks import iter_block_entities
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R22_REVIEW';OUT=ROOT/'artifacts/facility_r23/station_details'
def main(apply=False):
 OUT.mkdir(parents=True,exist_ok=True);v.WORLD=scan.WORLD=WORLD;v.OUT=OUT;p=v.Painter();records=json.loads((ROOT/'artifacts/access_r22/transit/civil/station_contract.json').read_text(encoding='utf8'))['stations'];native=json.loads((WORLD/'native_transit_r22.json').read_text());report=[];total=0
 for r in records:
  x,y,z=r['center'];h=r['half'];g=r['ground'];horizontal=r['horizontal'];dx,dz=(h+2,19) if horizontal else (19,h+2);f.LO=(x-dx,g-3,z-dz);f.HI=(x+dx,y+14,z+dz);s=f.Scene();owner='r23/japanese_station/'+str(r['platform_ids'][0]);boards=[];gates=[]
  for link in json.loads((ROOT/'artifacts/access_r22/transit/civil/station_contract.json').read_text(encoding='utf8'))['transfer_links']:
   if link['id'].endswith('/return'):continue
   axis_x=abs(link['path'][0][0]-link['path'][-1][0])>abs(link['path'][0][2]-link['path'][-1][2])
   for point in link['path']:
    xx,yy,zz=map(math.floor,point);box=(xx-(0 if axis_x else 4),yy-3,zz-(4 if axis_x else 0),xx+(0 if axis_x else 4),yy+4,zz+(4 if axis_x else 0));a=tuple(max(box[i],f.LO[i]) for i in range(3));b=tuple(min(box[i+3],f.HI[i]) for i in range(3))
    if all(a[i]<=b[i] for i in range(3)):s.protect((*a,*b))
  def at(u,Y,w):return (x+u,Y,z+w) if horizontal else (x+w,Y,z+u)
  def fill(u,Y,w,U,YY,W,state):
   a=at(u,Y,w);b=at(U,YY,W);s.fill((*np.minimum(a,b),*np.maximum(a,b)),state)
  def plaque(u,Y,w,face,rows):
   q=at(u,Y,w)
   if s.protected[q[1]-f.LO[1],q[2]-f.LO[2],q[0]-f.LO[0]]:return
   fill(u,Y,w,u,Y,w,f'projectseele:nerv_direction_panel[facing={face},wayfinding=true]')
   tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Wayfinding':nbtlib.Byte(1),'Station':nbtlib.String(r['station']),'Route':nbtlib.String(r['line']+' · 站内导向'),'PlatformCentre':nbtlib.Long(0)})
   for i,t in enumerate(rows):tag['Row'+str(i)]=nbtlib.String(t)
   p.block_entities[q]=tag;boards.append(dict(position=q,rows=rows))
  platforms=[q for q in native['platforms'] if q['id'] in r['platform_ids']];edge=int(round(max(abs(((q['position1']['z']+q['position2']['z'])/2-z) if horizontal else ((q['position1']['x']+q['position2']['x'])/2-x)) for q in platforms)))+2
  train_length=122 if r['line']=='R1' else 82
  for side in (-1,1):
   face=('south' if side<0 else 'north') if horizontal else ('east' if side<0 else 'west')
   # Glass waiting room, clearly outside the continuous boarding aisle.
   fill(-12,y-2,side*13,12,y-1,side*17,f.STRUCT)
   fill(-12,y,side*13,12,y,side*17,f.FLOOR)
   fill(-12,y+1,side*13,12,y+4,side*17,'projectseele:clear_glass');fill(-11,y+1,side*14,11,y+4,side*16,'minecraft:air')
   fill(-12,y+5,side*13,12,y+5,side*17,'minecraft:light_gray_concrete')
   fill(-2,y+1,side*13,2,y+3,side*13,'minecraft:air')
   for u in (-9,-8,-7,-6,5,6,7,8):fill(u,y+1,side*16,u,y+1,side*16,f'projectseele:station_seat[facing={face}]')
   for u in (-8,7):fill(u,y+5,side*14,u+3,y+5,side*15,'projectseele:nerv_strip_light')
   # Line colour is a narrow wall band and column marker, not a bright floor.
   colour='green' if r['line']=='R1' else 'orange'
   fill(-h+1,y+3,side*17,h-1,y+3,side*17,f'minecraft:{colour}_concrete')
   # The old west/end offset (-h+4) put the complete service cabinet beyond
   # the public landing on every elevated platform. Its plaque had no real
   # reading approach; a collision-free cabinet roof was not passenger floor.
   # Keep the commissioned inner service bay; R44 retires the whole former
   # cabinet/plaque component with exact old states, never just its label.
   for u in (h-23,):
    fill(u,y+1,side*15,u+3,y+1,side*16,'projectseele:nerv_storage_panel')
    plaque(u+1,y+3,side*16,face,['消防设备','请勿遮挡','紧急情况联系站务'])
   # Floor arrows/tactile routes lead to the stair, not through the stairwell.
   fill(-h+2,y,side*8,h-3,y,side*8,'projectseele:station_tactile_path')
   plaque(0,y+3,side*16,face,['候车室 / 优先席','请先下后上','乘车方向见站台信息牌'])
   # Continuous native half-height screen gates. Eidan 9000 has 5 m door
   # spacing; complete left/right pairs and upper/lower halves are authored.
   low=-int(train_length/2)+3;high=int(train_length/2)-3;door_positions={}
   for u in range(low,high,5):door_positions[u]=0;door_positions[u+1]=1
   for u in range(-h+1,h):
    door=u in door_positions;part=door_positions.get(u,(u-low)%2)
    # Facing north/east has increasing lateral coordinate on its right.
    increasing_right=face in ('north','east');part=part if increasing_right else 1-part
    for half,Y in [('lower',y+1),('upper',y+2)]:
     props=f'facing={face},half={half},side={"left" if part==0 else "right"}'
     state='mtr:apg_door[end=false,'+props+',unlocked=true]' if door else 'mtr:apg_glass['+props+']'
     fill(u,Y,side*edge,u,Y,side*edge,state)
     if door:
      q=at(u,Y,side*edge);p.block_entities[q]=nbtlib.Compound({'id':nbtlib.String('mtr:apg_door'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2])})
    if door and door_positions[u]==0:gates.append(dict(position=at(u,y+1,side*edge),facing=face))
   # Lower concourse furniture occupies only the wall side of the pedestrian
   # hall, clear of its paired flat travelators and all transfer doorways.
   for u in (-20,18):
    for k in range(4):fill(u+k,g+1,side*15,u+k,g+1,side*15,f'projectseele:station_seat[facing={face}]')
    fill(u-2,g+1,side*16,u-2,g+2,side*16,'projectseele:nerv_storage_panel')
  total+=s.delta(p,owner);report.append(dict(station=r['station'],line=r['line'],boards=boards,gates=gates,waiting_rooms=2))
 p.meta.update(stations=report,changed_cells=total,reference=['https://www.jreast.co.jp/company/csr/safe-cx/safety-efforts/platform/','https://www.jreast.co.jp/press/2022/hachioji/20221216_hc001.pdf'])
 p.save_plan('waiting_rooms_native_gates_and_guidance')
 if apply:p.apply('waiting_rooms_native_gates_and_guidance')
 (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Station detail groups',len(report),'changed',total,'gate pairs',sum(len(r['gates']) for r in report))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
