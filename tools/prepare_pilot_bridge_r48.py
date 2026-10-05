"""Exact R48 rear-bridge footprint with the Root runtime helper's full-next-state edge rules."""
from pathlib import Path
import json
from prepare_facilities_r48 import Author
from query_blocks import AIR,iter_block_entities
from measure_world_r40 import MeasuredWorld,properties
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'artifacts/rebuild_r48/construction/SEELE_R48_WORLD';OUT=ROOT/'artifacts/rebuild_r48/bridge_static'
DECK='projectseele:entry_plug_bridge_deck';GUARD='projectseele:entry_plug_bridge_guard';RAIL='projectseele:nerv_edge_rail'
DIRECTIONS={'east':(1,0),'north':(0,-1),'south':(0,1),'west':(-1,0)}
def panel(x,z):return 19<=z<=21 and abs(x)<=16 or 16<=z<=17 and 3<=abs(x)<=6 or z==18 and 2<=abs(x)<=6
def flagstate(name,flags):return name+'['+','.join(k+'='+str(flags[k]).lower()for k in DIRECTIONS)+']'
def main():
 OUT.mkdir(parents=True,exist_ok=True);a=Author(WORLD,OUT);m=MeasuredWorld(WORLD)
 for cx in(-12,30,72):m.box((cx-21,-396,-226),(cx+21,-390,-214))
 m.load();assert set(m.status.values())=={'full'};tags={}
 for cx in(-12,30,72):tags.update(iter_block_entities(WORLD,m.dimension,(cx-21,-396,-226),(cx+21,-390,-214)))
 rooms=json.loads((WORLD/'r47_pilot_restrooms.json').read_text('utf8'))['slots'];floors={};changes={};unknown=[];edge_report=[]
 def owned_room(v,q):
  x,y,z=q;door=5+42*v
  return door<=x<=door+2 and -395<=y<=-390 and -223<=z<=-217 or x==door-1 and y==-392 and z in(-219,-222)
 def sturdy(q):
  s=floors.get(q,m.block(q));name=s.split('[')[0]
  if name in AIR:return False
  if name in {DECK,'projectseele:nerv_machine_panel','projectseele:nerv_machine_edge','minecraft:smooth_stone','projectseele:nerv_structural_panel','projectseele:nerv_shaft_panel','minecraft:iron_block','minecraft:sea_lantern','projectseele:nerv_strip_light','minecraft:polished_deepslate','projectseele:nerv_floor_panel'}:return True
  unknown.append({'pos':q,'state':s,'reason':'Full next-footprint neighbouring sturdy semantics need native inspection'});return False
 for v,cx in enumerate((-12,30,72)):
  for x in range(-16,17):
   for z in range(16,25):
    q=(cx+x,-395,-240+z);old=m.block(q)
    assert old in AIR|{'projectseele:nerv_machine_panel','projectseele:nerv_machine_edge'},(q,old)
    assert q not in tags
    floors[q]=flagstate(DECK,{k:False for k in DIRECTIONS})if panel(x,z)else'minecraft:air'
 for v,cx in enumerate((-12,30,72)):
  for x in range(-19,20):
   for z in range(16,25):
    q=(cx+x,-395,-240+z);at=(q[0],q[1]+1,q[2]);old=m.block(at)
    if owned_room(v,at):continue
    if old.split('[')[0]not in AIR|{'minecraft:light',RAIL,GUARD}:continue
    if at in tags:continue
    if not sturdy(q):
     if old.startswith((RAIL+'[',GUARD+'[')):changes[at]='minecraft:air'
     continue
    flags={side:not sturdy((q[0]+dx,q[1],q[2]+dz))for side,(dx,dz)in DIRECTIONS.items()}
    if q in floors:floors[q]=flagstate(DECK,flags)
    if any(flags.values()):changes[at]=flagstate(GUARD,flags);edge_report.append({'pos':at,'flags':flags})
    elif old.startswith((RAIL+'[',GUARD+'[')):changes[at]='minecraft:air'
 assert not unknown,unknown[:10]
 desired={}
 for q,s in floors.items():a.s[q]=m.block(q);desired[q]=(s,'Full same-footprint rear crosswalk and capsule-side branches from explicit Root panel mask',None)
 for q,s in changes.items():a.s[q]=m.block(q);desired[q]=(s,'Full-next-footprint edge guard; room parts/BEs untouched; light replaced only at required edge',None)
 a.t=tags;a.emit('R48_rear_bridge_reference',desired,dict(beds=[[-12,-443,-240],[30,-443,-240],[72,-443,-240]],floor_y=-395,feet_y=-394,main_crosswalk={'X':[-16,16],'Z':[19,21]},branches={'Z16_17':'X[-6,-3]union[3,6]','Z18':'X[-6,-2]union[2,6]'},retired_central={'X':[-16,16],'Z':[22,24]},fixed_side_pockets_and_all_room_BEs_retained=True,old_capsule_wells_16_17_X_minus2_to2_retained=True,main_19_21_centres_no_new_hole=True,complete_next_edge_states=edge_report,original_room_to_goal_paths_unchanged=True,front_427_recipe_and_metadata_unchanged=True,actual_reference='User supplied codex clipboard TV bridge image; no official pixels copied',runtime_requires='Root EntryPlugBridgeLayoutR48 and same panel()/edge() logic, marker, registered deck/guard',not_native_mounted_capsule_model_or_hatch_sweep_approval=True))
 (OUT/'r48_entry_plug_bridge.json').write_text(json.dumps(dict(schema=48,installed=True,layout='rear_crosswalk_19_21_capsule_branches_16_18'),indent=2),'utf8');a.recipe()
 (OUT/'mask_contract.json').write_text(json.dumps(dict(all_next_floor=[[list(q),s]for q,s in floors.items()],all_next_guard=[[list(q),s]for q,s in changes.items()],row_before_counts=len(a.all),world_written=False,Java_Gradle_SHA_started=False),ensure_ascii=False,indent=2),'utf8');print('Source metadata427/fixed rooms/front walk, UUIDs, devices, progress untouched; candidate only')
if __name__=='__main__':main()
