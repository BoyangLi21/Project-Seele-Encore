"""Retire measured old roads, recess the lift head and place the weapon well."""
from pathlib import Path
import copy,json,math,msvcrt,shutil
import nbtlib,numpy as np
import regional_voxels as v
import scan_regional_completion as scan
from query_blocks import iter_block_entities,AIR,read_box
from transplant_s22_authority import read_region,parse_chunk,build_region,chunk_blob
from apply_s20_approved_semantic_repairs import atomic_replace
ROOT=v.ROOT;OUT=ROOT/'artifacts/world_repair_r21/surface';WORLD=ROOT/'run/saves/SEELE_R21_REVIEW'
FLOOR='projectseele:nerv_floor_panel';WALL='projectseele:nerv_wall_panel';STRUCT='projectseele:nerv_structural_panel';EMPTY='minecraft:air'
def main():
 OUT.mkdir(parents=True,exist_ok=True);v.WORLD=WORLD;scan.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
 def b(box,state,owner='r21/recessed_public_lift'):p.fill(*box,state,owner,'owned')
 # The complete native city has physically sunk. Only unchanged residual
 # road bands are retired; future movable building cells are not guessed.
 base=json.loads((OUT.parent/'baseline.json').read_text());cold=Path(base['backup'])/'world';lo=(-194,92,16);hi=(199,112,34)
 current=read_box(WORLD,v.DIM,lo,hi);before=read_box(cold,v.DIM,lo,hi);retired=0
 for q,state in current.items():
  if state.split('[')[0] in AIR|{'minecraft:light'} or state!=before[q]:continue
  p.match((*q,*q),state,EMPTY,'r21/retire_old_city_skyroad');retired+=1
 # Top native stop lowers six metres; existing car and lower stop remain.
 cp=WORLD/'dimensions/projectseele/geofront/data/capabilities.dat';caps=nbtlib.load(cp);group=caps['data']['movingelevators:elevator_groups']['130;269']['group'];assert not int(group['isMoving'])
 assert list(map(int,group['floors']))==[-442,81]
 oldbe=dict(iter_block_entities(WORLD,v.DIM,(112,73,265),(139,90,282)))
 controller=copy.deepcopy(oldbe[(130,81,269)]);controller['y']=nbtlib.Int(75)
 b((112,81,265,139,90,282),EMPTY)
 b((112,72,265,139,74,282),STRUCT)
 b((112,75,265,139,80,282),STRUCT);b((113,75,266,138,79,281),EMPTY);b((113,74,266,138,74,281),FLOOR)
 # Roof and pavement are already flush at Y=80, with a retained native well.
 b((127,70,270,133,79,276),EMPTY)
 for x in (126,134):b((x,75,269,x,79,277),WALL)
 for z in (269,277):b((127,75,z,133,79,z),WALL)
 b((125,75,271,126,78,275),EMPTY)
 state=read_box(WORLD,v.DIM,(130,81,269),(130,81,269))[(130,81,269)];p.put(130,75,269,state,'r21/lift_controller_move','owned');p.block_entities[130,75,269]=controller
 # Seven-wide stair from street to the underground lift vestibule.
 for x in range(111,120):
  floor=80 if x<=112 else max(74,80-(x-112))
  b((x,73,270,x,floor-1,278),STRUCT);b((x,floor+1,271,x,86,277),EMPTY)
  b((x,floor,271,x,floor,277),'minecraft:smooth_quartz_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]' if 113<=x<=118 else FLOOR)
  for z in (270,278):b((x,floor,z,x,max(80,floor+2),z),WALL)
 b((119,75,271,124,79,277),EMPTY);b((119,74,271,124,74,277),FLOOR)
 # Solid safety curb around the open stair. Its surveyed above-grade portion
 # joins the city emergency cover manifest below.
 for z in (270,278):b((111,81,z,119,81,z),'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]')
 b((119,81,270,119,81,278),'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]')
 p.sign(124,77,266,['第三新东京','地下公共电梯','NERV 总部 / 机库','警戒时地表入口封闭'],'r21/lift_sign',facing='south')
 # The decommissioned weapon opening has a real continuous pavement cap.
 b((21,68,288,38,79,305),'minecraft:stone','r21/retired_weapon_well');b((21,80,288,38,80,305),'minecraft:black_concrete','r21/retired_weapon_well')
 # A new reinforced armament vault is beside the actual surface launch group.
 b((109,35,-47,131,79,-25),STRUCT,'r21/weapon_vault')
 b((116,37,-44,124,79,-28),EMPTY,'r21/weapon_vault')
 b((109,80,-47,131,80,-25),FLOOR,'r21/weapon_vault')
 b((115,80,-45,125,80,-27),'minecraft:barrier','r21/weapon_vault')
 for x in (109,131):b((x,80,-47,x,80,-25),'projectseele:nerv_machine_hazard','r21/weapon_vault')
 for x in (-12,30,72):
  b((x-5,77,-82,x+5,80,-68),FLOOR,'r21/launch_power_pads');p.put(x,81,-75,'projectseele:umbilical_pylon','r21/launch_power_pads','owned')
 # Mechanical warning panels are actual networked blocks at both endpoints.
 for cx in (-12,30,72):
  for x,y,z in [(cx-17,-379,-221),(cx+17,-379,-221),(cx-17,-356,-53),(cx+17,-356,-53)]:
   b((x,y-1,z,x,y-1,z),STRUCT,'r21/alarm_mount');p.put(x,y,z,'projectseele:nerv_warning_beacon[lit=false]','r21/alarm_mount','owned')
 p.meta.update(retired_road_cells=retired,new_weapon_station=[120.5,80,-35.5],public_lift_upper_walk=75,old_weapon_well_closed=True)
 p.apply('surface_services_and_old_roads')
 # Only the public group's upper binding changes; captured cabin data remains.
 shutil.copy2(cp,OUT/'capabilities_before.dat');group['floors']=nbtlib.IntArray([-442,75]);group['floorData'][1]['name']=nbtlib.String('第三新东京 · 浅层前厅');caps.save(cp)
 # Preserve the original armament entity identity while moving its saved chunk.
 folder=WORLD/'dimensions/projectseele/geofront/entities';regions={};moved=[];cargo=None
 for f in folder.glob('r.*.mca'):
  if f.stat().st_size<8192:continue
  stamps,blobs=read_region(f);dirty=False
  for slot,blob in enumerate(blobs):
   if not blob:continue
   root=parse_chunk(blob);keep=[]
   for e in root.get('Entities',[]):
    if str(e.get('id'))=='projectseele:nerv_armament_station':
     if cargo is not None:raise RuntimeError('Multiple armament stations need classification')
     cargo=copy.deepcopy(e);moved.append(dict(uuid=list(map(int,e['UUID'])),before=list(map(float,e['Pos']))));continue
    keep.append(e)
   if len(keep)!=len(root.get('Entities',[])):root['Entities']=nbtlib.List[nbtlib.Compound](keep);blobs[slot]=chunk_blob(root);dirty=True
  if dirty:regions[f]=(stamps,blobs)
 assert cargo is not None
 cargo['Pos']=nbtlib.List[nbtlib.Double]([120.5,80,-35.5]);cargo['StationState']=nbtlib.Int(0);cargo['LiftProgress']=nbtlib.Float(0);cargo['HatchProgress']=nbtlib.Float(0);cargo['DoorProgress']=nbtlib.Float(0);cargo['PhaseTicks']=nbtlib.Int(0);cargo['DeployQueued']=nbtlib.Byte(0)
 cx,cz=7,-3;dest=folder/'r.0.-1.mca';slot=(cz%32)*32+cx%32
 if dest not in regions:regions[dest]=read_region(dest)
 stamps,blobs=regions[dest]
 root=parse_chunk(blobs[slot]) if blobs[slot] else nbtlib.File({'DataVersion':nbtlib.Int(3465),'Position':nbtlib.IntArray([cx,cz]),'Entities':nbtlib.List[nbtlib.Compound]()})
 root['Entities'].append(cargo);blobs[slot]=chunk_blob(root)
 for path,(stamps,blobs) in regions.items():shutil.copy2(path,OUT/('entities_before_'+path.name));atomic_replace(path,build_region(stamps,blobs))
 (OUT/'runtime_changes.json').write_text(json.dumps(dict(armament=moved,new_position=[120.5,80,-35.5],lift_floors=[-442,75]),indent=2))
 # Temporary empty descriptor activates the recessed upper stop on next load.
 (WORLD/'battlefield_r21.json').write_text(json.dumps(dict(bounds=[-144,41,207,392],cells=[])))
 print('Surface services ready; retained armament UUID, shallow native stop, removed road',retired)
if __name__=='__main__':main()
