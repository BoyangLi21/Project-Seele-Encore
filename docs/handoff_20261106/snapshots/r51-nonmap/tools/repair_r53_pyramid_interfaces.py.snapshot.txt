"""Repair measured new-lobby intersections, inherited bridge access and labels.

New lobby walls are checked against their recorded pre-installation states.
Actual native elevator blocks and MTR moving walks are never cleared here.
"""
from pathlib import Path
import argparse,copy,gzip,json,math
import nbtlib
import regional_voxels as vox
from query_blocks import read_box,iter_block_entities

DIM='projectseele:geofront'
def inside_pyramid(at):
 x,y,z=at;y+=93
 if not -466<=y<=-294:return False
 r=math.floor(120*(1-(y+466)/172)+.5)
 return abs(x-30)<=r and abs(z-327)<=r

def run(base,world):
 vox.WORLD=world;vox.DIM=DIM;vox.OUT=base/'oct16-interface-repair'/world.name
 p=vox.Painter(vertical_bounds=(-1440,320));measured={};tags={};desired={};newtags={};why={}
 def read(lo,hi):
  measured.update(read_box(world,DIM,lo,hi));tags.update(iter_block_entities(world,DIM,lo,hi))
 def setcell(at,state,reason,tag=None):
  at=tuple(at);assert at in measured,at
  desired[at]=state;why[at]=reason;newtags[at]=tag
 proposals=json.loads(gzip.decompress((base/'personnel-access-proposal/EXACT_BLOCK_PROPOSAL.json.gz').read_bytes()))
 bypos={tuple(r['pos']):r for r in proposals}
 read((-50,-559,247),(96,-450,380))
 exterior=0;crossings=0
 for row in proposals:
  at=tuple(row['pos'])
  if at not in measured or not row['owner'].startswith(('r25-east-command-gallery/','s20-command-rear-x12-z253-v4/')):continue
  if -559<=at[1]<=-392 and not inside_pyramid(at) and measured[at]==row['after']:
   if row['before_nbt'] is not None:continue
   setcell(at,row['before'],'remove_new_lobby_projection_outside_original_pyramid');exterior+=1
 # These are the named old corridors crossing the new lobby's west wall.
 for y in (-554,-541,-527,-513,-499,-485,-471,-457):
  for yy in range(y,y+3):
   for z in range(371,375):
    at=54,yy,z;row=bypos.get(at)
    if row is not None and row['before']=='minecraft:air' and measured[at]==row['after'] and 'rear_public_lobby' in row['owner']:
     setcell(at,'minecraft:air','restore_original_cross_corridor_full_port');crossings+=1
 # Restore the complete original five-wide walking band at the lower T junction.
 for x in range(87,92):
  for y in range(-554,-550):
   for z in range(358,392):
    at=x,y,z;row=bypos.get(at)
    if row is not None and row['before']=='minecraft:air' and measured[at]==row['after'] and 'rear_public_lobby' in row['owner']:
     setcell(at,'minecraft:air','lower_ring_and_lobby_union_full_width');crossings+=1
 for old,new in (((87,-552,370),(86,-552,365)),((87,-552,372),(86,-552,378))):
  assert str(tags[old]['id'])=='projectseele:station_departure_board'
  assert new not in tags
  tag=copy.deepcopy(tags[old])
  for name,n in zip(('x','y','z'),new):tag[name]=nbtlib.Int(n)
  setcell(old,'minecraft:air','remove_overlapping_board_from_walking_band')
  setcell(new,measured[old],'separate_existing_boards_on_corridor_wall',tag)
 # A retained research bridge now needs its own ground entry after the old
 # HQ branch was removed. The actual two floor heights are -466 and -460.
 read((191,-468,401),(201,-455,412))
 for x in range(193,200):
  assert measured[x,-467,403]=='minecraft:deepslate_bricks'
  assert measured[x,-461,410]=='minecraft:smooth_stone'
 for z in range(403,409):
  step_y=-466+(z-403)
  for x in range(193,200):
   for y in range(-467,step_y):
    setcell((x,y,z),'projectseele:nerv_structural_panel','grounded_research_bridge_entry_foundation')
   setcell((x,step_y,z),'minecraft:smooth_quartz_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]','ground_to_retained_research_bridge')
   for y in range(step_y+1,step_y+4):
    assert measured[x,y,z]=='minecraft:air',(x,y,z,measured[x,y,z])
  for x in (192,200):
   for y in range(-467,step_y+1):setcell((x,y,z),'projectseele:nerv_structural_panel','research_stair_grounded_edge')
   setcell((x,step_y+1,z),'projectseele:clear_glass','research_stair_continuous_parapet')
 for x in range(193,200):setcell((x,-461,409),'projectseele:nerv_floor_panel','research_bridge_final_level_landing')
 # Label the exact existing console keys without changing their positions.
 read((23,-502,285),(33,-497,287))
 for variant,name in enumerate(('零号机','初号机','二号机')):
  z=287-variant
  for x,y,facing,lines in ((32,-498,'west',(name,'上：箱根','中：第三新东京','下：GeoFront')),(24,-499,'east',(name,'上键：取消出动','下键：回收','原机原路返回'))):
   at=x,y,z;back=(33 if x==32 else 23),y,z
   assert measured[at]=='minecraft:air' and at not in tags
   if measured[back]=='minecraft:air':setcell(back,'projectseele:nerv_machine_panel','existing_console_label_backing')
   front=nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':s},ensure_ascii=False))for s in lines]),'color':nbtlib.String('white'),'has_glowing_text':nbtlib.Byte(1)})
   tag=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(x),'y':nbtlib.Int(y),'z':nbtlib.Int(z),'front_text':front,'back_text':copy.deepcopy(front),'is_waxed':nbtlib.Byte(1)})
   setcell(at,f'minecraft:dark_oak_wall_sign[facing={facing},waterlogged=false]','actual_unit_and_operation_console_labels',tag)
 rows=[]
 for at,state in desired.items():
  before=measured[at];before_tag=tags.get(at);after_tag=newtags[at]
  if before==state and (before_tag.snbt()if before_tag is not None else None)==(after_tag.snbt()if after_tag is not None else None):continue
  p.exact((*at,*at),before,state,why[at])
  if after_tag is not None:p.block_entities[at]=after_tag
  rows.append(dict(pos=at,before=before,after=state,reason=why[at],before_nbt=None if before_tag is None else before_tag.snbt(),after_nbt=None if after_tag is None else after_tag.snbt()))
 p.meta.update(new_lobby_exterior_projection_cells=exterior,reopened_original_corridor_cells=crossings,boards_relocated=2,console_labels=6,research_original_floor_tops=[-466,-460])
 p.apply('pyramid_full_width_interfaces_and_console_labels')
 (vox.OUT/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode('utf8'),mtime=0))
 for lo,hi in (((-50,-559,247),(96,-450,380)),((191,-468,401),(201,-455,412)),((23,-502,285),(33,-497,287))):
  actual=read_box(world,DIM,lo,hi);actual_tags=dict(iter_block_entities(world,DIM,lo,hi))
  for row in rows:
   at=tuple(row['pos'])
   if at not in actual:continue
   assert actual[at]==row['after'],at
   expected=newtags[at];observed=actual_tags.get(at)
   assert (expected.snbt()if expected is not None else None)==(observed.snbt()if observed is not None else None),at
 print(json.dumps(dict(changed=len(rows),exterior=exterior,crossings=crossings,boards_relocated=2,console_labels=6,readback=True)))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--world',type=Path,required=True);a=p.parse_args();run(a.base,a.world)
