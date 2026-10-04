"""Resolve measured passenger conflicts without touching native tracks or stair cores."""
from pathlib import Path
import argparse,copy,json,math,nbtlib,numpy as np
import regional_voxels as v,scan_regional_completion as scan,plan_factory_r20 as f
from query_blocks import read_box,iter_block_entities,AIR
from station_lower_support_r45 import support_ops
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R22_REVIEW';OUT=ROOT/'artifacts/facility_r23/access_finish'
def main(apply=False):
 OUT.mkdir(parents=True,exist_ok=True);v.WORLD=scan.WORLD=WORLD;v.OUT=OUT;p=v.Painter();source=json.loads((ROOT/'artifacts/access_r22/transit/civil/station_contract.json').read_text(encoding='utf8'));routes=json.loads((ROOT/'artifacts/facility_r23/validation/full_walk_cases.json').read_text(encoding='utf8'));before=ROOT/'artifacts/facility_r23/finish/station_before';reports=[];allchanges=0
 for r in source['stations']:
  x,y,z=r['center'];h=r['half'];g=r['ground'];horizontal=r['horizontal'];dx,dz=(h+4,21) if horizontal else (21,h+4);f.LO=(x-dx,g-3,z-dz);f.HI=(x+dx,y+14,z+dz);s=f.Scene();existing_BE=set(q for q,be in iter_block_entities(WORLD,v.DIM,f.LO,f.HI));moved=[];ports=set();waiting=[]
  def at(u,Y,w):return (x+u,Y,z+w) if horizontal else (x+w,Y,z+u)
  def state(q):return s.palette[s.after[q[1]-f.LO[1],q[2]-f.LO[2],q[0]-f.LO[0]]]
  def fill(u,Y,w,U,YY,W,value):
   a,b=at(u,Y,w),at(U,YY,W);s.fill((*np.minimum(a,b),*np.maximum(a,b)),value)
  for side in (-1,1):
   for u in (-20,18):
    for k in range(4):
     old,new=at(u+k,g+1,side*15),at(u+k,g+1,side*10)
     if state(old).startswith('projectseele:station_seat'):
      assert state(new).split('[')[0] in AIR;s.fill((*new,*new),state(old));s.fill((*old,*old),'minecraft:air');moved.append([old,new])
    old,new=at(u-2,g+1,side*16),at(u-2,g+1,side*11)
    for dy in (0,1):
     a,b=(old[0],old[1]+dy,old[2]),(new[0],new[1]+dy,new[2])
     if state(a).split('[')[0]=='projectseele:nerv_storage_panel':
      assert state(b).split('[')[0] in AIR;s.fill((*b,*b),state(a));s.fill((*a,*a),'minecraft:air');moved.append([a,b])
  # Existing station-to-building paths determine openings in the station
  # frame. Move the complete column, not only its bottom three blocks.
  for route in routes:
   if not route['id'].startswith('station_road/'):continue
   pts=route.get('path',[route.get('start'),route.get('end')])
   for aa,bb in zip(pts,pts[1:]):
    aa,bb=np.asarray(aa),np.asarray(bb);n=max(1,int(np.linalg.norm(bb-aa)*3))
    if min(aa[1],bb[1])>g+1.6 or max(aa[1],bb[1])<g+.5:continue
    for q in np.linspace(aa,bb,n+1):
     u=q[0]-x if horizontal else q[2]-z;w=q[2]-z if horizontal else q[0]-x
     if abs(u)<=h and abs(abs(w)-17)<.5:ports.add((int(math.floor(u)),1 if w>0 else -1))
  for u,side in ports:
   fill(u-1,g+1,side*17,u+1,y+10,side*17,'minecraft:air')
   for U in (u-3,u+3):
    fill(U,y-2,side*17,U,y+10,side*17,'minecraft:light_gray_concrete')
    for op in support_ops(at,U,side,g,y,h,s,f.LO,existing_BE):fill(*op)
   fill(u-3,y+10,side*17,u+3,y+10,side*17,'projectseele:nerv_machine_edge')
   fill(u-2,y+1,side*17,u+2,y+1,side*17,'projectseele:nerv_machine_edge');fill(u-2,y+2,side*17,u+2,y+3,side*17,'projectseele:clear_glass')
  conflicts={('新箱根中央','R1'):1,('新箱根中央','S1'):-1,('湾岸防卫区','R1'):-1,('湾岸防卫区','S1'):1}
  side=conflicts.get((r['station'],r['line']))
  if side is not None:
   a,b=at(-12,y+1,side*13),at(12,y+5,side*17);lo=tuple(map(int,np.minimum(a,b)));hi=tuple(map(int,np.maximum(a,b)));old=read_box(before,v.DIM,lo,hi)
   # Restore only dressing actually placed by this round. The protected
   # transfer tunnel remains the current, already restored one.
   protect=set()
   for link in source['transfer_links']:
    for q in link['path']:
     xx,yy,zz=map(math.floor,q);axisx=abs(link['path'][0][0]-link['path'][-1][0])>abs(link['path'][0][2]-link['path'][-1][2]);protect.update((xx+dx,Y,zz+dz) for Y in range(yy-3,yy+5) for dx in ([0] if axisx else range(-4,5)) for dz in (range(-4,5) if axisx else [0]))
   for q,value in old.items():
    if q not in protect:s.fill((*q,*q),value)
   offset=20;face=('south' if side<0 else 'north') if horizontal else ('east' if side<0 else 'west')
   fill(offset-12,y+1,side*13,offset+12,y+4,side*17,'projectseele:clear_glass');fill(offset-11,y+1,side*14,offset+11,y+4,side*16,'minecraft:air');fill(offset-12,y+5,side*13,offset+12,y+5,side*17,'minecraft:light_gray_concrete');fill(offset-2,y+1,side*13,offset+2,y+3,side*13,'minecraft:air')
   for U in (-9,-8,-7,-6,5,6,7,8):fill(offset+U,y+1,side*16,offset+U,y+1,side*16,f'projectseele:station_seat[facing={face}]')
   for U in (-8,7):fill(offset+U,y+5,side*14,offset+U+3,y+5,side*15,'projectseele:nerv_strip_light')
   waiting.append(dict(side=side,offset=offset))
  allchanges+=s.delta(p,'r23/unblocked_station_access') if np.any(s.before!=s.after) else 0;reports.append(dict(station=r['station'],line=r['line'],moved_concourse_furniture=moved,entrance_ports=sorted(ports),relocated_waiting_rooms=waiting))
 # Low defense positions need a level walk-in apron beyond the gun pad.
 military=json.loads((ROOT/'artifacts/facility_r23/readiness/contract.json').read_text(encoding='utf8'));aprons=0
 for e in military['vehicles']:
  if e['role']!='defense':continue
  x,y,z=map(math.floor,e['position']);lo=(x-2,72,z+4);hi=(x+2,78,z+8);b=read_box(WORLD,v.DIM,lo,hi)
  for q,old in b.items():
   target='minecraft:air' if q[1]>=75 else 'projectseele:nerv_floor_panel'
   if old!=target:p.match((*q,*q),old,target,'r23/defense_walk_in_apron');aprons+=1
 p.meta.update(stations=reports,station_changes=allchanges,defense_apron_changes=aprons);p.save_plan('clear_station_ports_and_defense_access')
 if apply:p.apply('clear_station_ports_and_defense_access');(WORLD/'military_readiness_r23.json').write_text(json.dumps(military,ensure_ascii=False,indent=2),encoding='utf8')
 (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Station changes',allchanges,'defense apron',aprons)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
