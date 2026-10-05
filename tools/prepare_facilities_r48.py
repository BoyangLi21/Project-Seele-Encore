"""R48 measured facility candidates. Does not write any world or run a JVM."""
from pathlib import Path
from collections import defaultdict
import argparse,copy,gzip,json,math,sys
import nbtlib
from query_blocks import read_box,iter_block_entities,chunk_statuses,AIR
from regional_voxels import canonical_state
from apply_s20_approved_semantic_repairs import parse_state
ROOT=Path(__file__).resolve().parents[1]
DIM='projectseele:geofront'
FLOOR='projectseele:nerv_floor_panel';WALL='projectseele:nerv_wall_panel';FRAME='projectseele:nerv_structural_panel'
class Author:
 def __init__(self,world,out):self.world=world;self.out=out;self.all={};self.s={};self.t={};self.components=[]
 def read(self,lo,hi):
  selected={(x,z)for x in range(lo[0]//16,hi[0]//16+1)for z in range(lo[2]//16,hi[2]//16+1)}
  assert set(chunk_statuses(self.world,DIM,selected).values())=={'full'},('Unfinished/missing selected facility chunk',lo,hi)
  self.s.update(read_box(self.world,DIM,lo,hi));self.t.update(iter_block_entities(self.world,DIM,lo,hi))
 def emit(self,name,desired,objects):
  rows=[]
  for q,value in sorted(desired.items()):
   after,reason,newtag=value;before=self.s[q];old=self.t.get(q);after=canonical_state(after)
   if before==after and old==newtag:continue
   row=dict(pos=list(q),before=before,after=after,before_nbt=None if old is None else old.snbt(),after_nbt=None if newtag is None else newtag.snbt(),owner=name,reason=reason)
   assert q not in self.all,('Overlapping facilities',q);self.all[q]=row;rows.append(row)
  target=self.out/name;target.mkdir(parents=True,exist_ok=True)
  for fn,items in [('forward.jsonl.gz',rows),('inverse.jsonl.gz',[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt'])for r in reversed(rows)])]:
   with gzip.open(target/fn,'wt',encoding='utf8')as stream:
    for row in items:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
  (target/'positiveEditMask.json').write_text(json.dumps([r['pos']for r in rows]),'utf8')
  contract=dict(schema='projectseele.r48.facility-candidate.v1',world=str(self.world),dimension=DIM,rows=len(rows),objects=objects,complete_NBT=True,world_written=False,native_verified=False,visual_verified=False,authorization='User R48 F01-F11 S01-S02 facilities reconstruction',progress_and_entity_files_untouched=True)
  (target/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf8');self.components.append(contract);print(name,len(rows))
 def recipe(self):
  data=Path('dimensions/projectseele/geofront/data');topology=nbtlib.load(next((self.world/data).glob('projectseele_city_rigid_topology_r45_*.dat')))['data']
  generation=data/str(topology['GenerationFolder']);world_id=str(topology['WorldUUID']);sample=nbtlib.load(next((self.world/generation/'chunks').glob('*.dat')))
  out=self.out/'generation_recipe';(out/'before').mkdir(parents=True,exist_ok=True);(out/'payload').mkdir(exist_ok=True);shards=defaultdict(dict);ops=[]
  def packed(q):
   x,y,z=q;n=((x&67108863)<<38)|((z&67108863)<<12)|(y&4095);return n-(1<<64)if n>=1<<63 else n
  for q,row in self.all.items():shards[q[0]//16,q[2]//16][q]=row
  for (cx,cz),rows in sorted(shards.items()):
   relative=generation/'chunks'/f'{cx}_{cz}.dat';source=self.world/relative
   if source.exists():
    before=out/'before'/source.name;before.write_bytes(source.read_bytes());doc=copy.deepcopy(nbtlib.load(source));assert str(doc['WorldUUID'])==world_id
   else:
    before=None;doc=nbtlib.File({'Version':copy.deepcopy(sample['Version']),'WorldUUID':nbtlib.String(world_id),'InitialDepth':copy.deepcopy(sample['InitialDepth']),'Palette':nbtlib.List[nbtlib.Compound]([]),'Static':nbtlib.List[nbtlib.Compound]([]),'Ground':nbtlib.List[nbtlib.Compound]([])},gzipped=True)
   palette=doc['Palette'];ids={r.snbt():i for i,r in enumerate(palette)};existing={int(r['Pos']):r for r in doc['Static']}
   for q,row in rows.items():
    state=parse_state(row['after']);key=state.snbt()
    if key not in ids:ids[key]=len(palette);palette.append(state)
    value=nbtlib.Compound({'Pos':nbtlib.Long(packed(q)),'StateId':nbtlib.Int(ids[key])})
    if row['after_nbt']:value['NBT']=nbtlib.parse_nbt(row['after_nbt'])
    existing[packed(q)]=value
   doc['Static']=nbtlib.List[nbtlib.Compound]([existing[k]for k in sorted(existing)]);target=out/'payload'/source.name;doc.save(target,gzipped=True)
   ops.append(dict(relative_target=relative.as_posix(),before_file=None if before is None else str(before),after_file=str(target),changed_cells=len(rows),full_existing_shard_preserved=True))
  (out/'file_patch.json').write_text(json.dumps(dict(operations=ops,world_written=False,WorldUUID=world_id,changed_cells=len(self.all),runtime='CityRigidGenerationR45 static chunk source only; no tower cargo, city journey, entity or task progress rewritten'),indent=2),'utf8')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r48/facilities');args=ap.parse_args();a=Author(args.world.resolve(),args.out.resolve());a.out.mkdir(parents=True,exist_ok=True)
 a.read((8,-469,-145),(110,-461,-44));a.read((-38,-470,-290),(9,-462,-115));a.read((-32,-470,-286),(-26,-388,-275))
 d={}
 for x0 in(28,53):
  for x in range(x0,x0+4):
   for y in range(-468,-464):d[x,y,-91]=('minecraft:air','Complete four-wide control-booth to trial-island bridge door',None)
 a.emit('F01_experiment_access',d,dict(first_error='R47 experiment booth north glass wall has no south-pier doorway; full X103 east branch measured intact',pool_LCL_and_both_capsule_clearance_retained=True,ports=[[[28,-468,-91],[31,-465,-91]],[[53,-468,-91],[56,-465,-91]]],east_branch=[[100,-469,-81],[106,-464,-45]],capsule_mount_hatch_and_research_runtime_unchanged=True))
 d={}
 for y in range(-469,-463):
  for z in range(-280,-275):
   q=(-31,y,z);assert q not in a.t and a.s[q]in{FLOOR,WALL,'minecraft:air'};d[q]=('minecraft:air','Remove R47 tunnel lateral wall inside original five-wide cabin sweep',None)
 a.emit('F02_rear_lift_sweep',d,dict(first_error='prepare_experimental_lifts tunnel union lateral x=-31 overwrites own radius-two cabin cells after shaft clearance',original_cabin_floor_and_furnishing_at_y_minus395_retained=True,all_original_controller_NBT_retained=True,full_sweep=[[-31,-469,-280],[-27,-396,-276]],native_call_board_move_reload_pending=True))
 d={}
 for z in range(-260,-184):
  for x0,direction in((-36,False),(-33,True)):
   for lane in range(2):
    q=(x0+lane,-469,z);assert a.s[q].startswith(('projectseele:nerv_moving_walk',FLOOR));d[q]=(f'mtr:escalator_step[direction={str(direction).lower()},facing=north,orientation=flat,side={"left"if lane==0 else"right"},status=true]','Two complete native moving-walk lanes; central walking strip retained',None)
 a.emit('F03_west_bidirectional_walk',d,dict(first_error='R47 uses one-cell custom belts; requested native two-cell device width absent',length=76,two_cells_per_direction=True,centre_x=-34,stationary_buffers_at_both_ends=True,no_native_traffic_data_write=True))
 a.read((-378,80,609),(-350,89,633));d={}
 for x,hinge in((-364,'left'),(-363,'right')):
  for y,half in((81,'lower'),(82,'upper')):
   q=(x,y,621);assert a.s[q].startswith('mcwdoors:store_door[');d[q]=(f'projectseele:city_personnel_door[facing=south,half={half},hinge={hinge},open=false,powered=false]','Complete public double metal latch replacing unsupported store door use',None)
 for y in(81,82):d[-365,y,621]=('minecraft:smooth_sandstone','Full frame return closes unowned one-cell lateral doorway gap',None)
 a.emit('F05_complete_public_door',d,dict(door=[[-364,81,621],[-363,82,621]],preserved_facing_hinges_and_floor=True,first_error='Fixed shop has Macaw store-door pair plus unframed third aperture; native original latch failure unverified; candidate uses supported registered public manual latch',same_class_other_city_instances='City agent owns broader public entrance audit; this candidate is this entire fixed-shop door/frame only'))
 a.read((-411,80,698),(-300,95,704));d={}
 # Exact outer wall face: seal all openings, preserve the original main entrance.
 for x in range(-410,-300):
  for y in range(81,95):
   q=(x,y,700)
   if -368<=x<=-352:continue
   if q in a.t:continue
   if a.s[q]in AIR:d[q]=(WALL,'Close full existing gateway outer-wall side bypass apertures',None)
 for x in range(-368,-351):
  for y in range(81,95):
   q=(x,y,701);state='projectseele:clear_glass'if y<94 else FRAME
   if x in(-368,-364,-357,-352):state='projectseele:nerv_machine_edge'
   if x in(-361,-360)and y<=82:state='minecraft:air'
   d[q]=(state,'Complete subway checkpoint partition with native two-cell central gate',None)
 for x,block,face in((-361,'entrance','south'),(-360,'exit','north')):
  d[x,81,701]=(f'mtr:ticket_barrier_{block}_1[facing={face},open=closed]','Native subway gate body; exact NERV swipe service controls this pair',None)
 q=(-355,82,700);tag=copy.deepcopy(a.t[q]);tag['Linked']=nbtlib.Byte(0);tag['Label']=nbtlib.String('NERV · 地面入口地铁闸机');d[q]=(a.s[q],'Retain complete original reader NBT; bind finite native gate service',tag)
 a.emit('F06_secure_subway_checkpoint',d,dict(first_error='Outer wall has side apertures around narrow R47 checkpoint; original reader drives full-height lift-style leaves',native_gate_positions=[[-361,81,701],[-360,81,701]],reader=[-355,82,700],safe_egress_button=[-355,82,702],clearance=1,requires='SecureStationGateR48 plus PublicStationGatesR44 finite delegation',no_public_free_access_manifest=True))
 marker=dict(schema=48,dimension=DIM,installed=True,reader=[-355,82,700],gates=[[-361,81,701],[-360,81,701]],clearance=1)
 (a.out/'r48_secure_station_gate.json').write_text(json.dumps(marker,indent=2),'utf8')
 a.read((500,71,26),(685,80,35));d={}
 for cx in(545,645):
  # Service gallery's south wall crosses the complete original north hangar door.
  for x in range(cx-31,cx+32):
   for z in(28,29):
    for y in range(73,79):
     q=x,y,z;assert q not in a.t
     if a.s[q]in AIR|{FRAME,WALL}:d[q]=('minecraft:air','Reopen both complete original hangar fronts through later passenger gallery wall',None)
 a.emit('F07_airport_hangar_fronts',d,dict(first_error='build_nerv_airport_r21 constructs open hangar north fronts, then closes them with gallery south wall Z29',full_original_door_width=63,two_hangar_centres=[545,645],floor_72_and_overhead_structure_79_retained=True,aircraft_gear_and_boarding_routes_untouched=True))
 a.read((575,30,469),(1140,98,475));d={};native=json.loads((a.world/'native_transit_r22.json').read_text('utf8'))
 import numpy as np
 from scipy.spatial import cKDTree
 points=np.asarray([p for c in native['curves']if c['mode']=='TRAIN'for p in c['points']]);tree=cKDTree(points)
 for q,state in a.s.items():
  x,y,z=q
  if not(575<=x<=1140 and 469<=z<=475 and 89<=y<=93):continue
  if state.split('[')[0]not in{'minecraft:light_gray_concrete','minecraft:gravel','projectseele:nerv_machine_edge','projectseele:clear_glass','minecraft:light_gray_stained_glass'}or q in a.t:continue
  dist,_=tree.query(np.array(q)+.5,p=np.inf)
  if dist<7:continue
  # Retired C1 complete formation ownership, exact source strip. Current station starts beyond x1140.
  d[q]=('minecraft:air','Retire complete old C1 formation and attached source edge cells outside current native rail envelopes',None)
 old=json.loads((ROOT/'artifacts/world_rebuild_r20/transit/civil/viaduct_stations_and_streets/places.json').read_text('utf8'))
 retired_piervoxels=0
 for px,py,pz in old['piers']:
  if not(575<=px-1 and px+1<=1140 and pz==472):continue
  for x in range(px-1,px+2):
   for z in range(pz-1,pz+2):
    for y in range(30,89):
     q=(x,y,z)
     if a.s.get(q)=='minecraft:light_gray_concrete'and q not in a.t and tree.query(np.array(q)+.5,p=np.inf)[0]>=7:
      d[q]=('minecraft:air','Complete retired original C1 pier/footer member; measured old source ownership',None);retired_piervoxels+=1
 a.emit('F08_retired_C1_bridge',d,dict(first_error='Superseded C1 centre ballast/formation survives R22 retirement; current native TRAIN curves do not use reported 678/93/472',source='R20 viaduct_stations_and_streets places; R22 retired alignment authority',bounds=[[575,30,469],[1140,93,475]],retired_pier_footer_cells=retired_piervoxels,current_native_track_margin=7,live_station_and_APG_untouched=True))
 a.read((86,-447,-67),(132,-430,-16));d={}
 for z in(-44,-43):
  q=(98,-442,z);assert a.s[q].startswith('mtr:ticket_barrier_');d[q]=('minecraft:air','Complete pair of redundant lift-side free gates retired; landing and APG retained',None)
 a.emit('F09_retired_hangar_gate_pair',d,dict(first_error='Independent free public barrier pair remains beside actual lift despite no useful access boundary',full_pair=[[98,-442,-44],[98,-442,-43]],APG_and_vertical_native_elevator_untouched=True))
 before=json.loads((a.world/'r44_public_station_gates.json').read_text('utf8'));after=copy.deepcopy(before);after['gates']=[g for g in after['gates']if tuple(g['position'])not in{(98,-442,-44),(98,-442,-43)}]
 (a.out/'public_gate_metadata_patch.json').write_text(json.dumps(dict(relative_target='r44_public_station_gates.json',before=before,after=after),ensure_ascii=False,indent=2),'utf8')
 a.read((96,-490,-170),(109,-443,-166));d={}
 for x in(99,107):
  support=max(y for y in range(-490,-467)if a.s[x,y,-168].split('[')[0]in{'minecraft:stone','minecraft:dirt','minecraft:grass_block'})
  assert a.s[x,-467,-168]==FRAME
  for y in range(support+1,-467):
   q=x,y,-168;assert a.s[q]in AIR and q not in a.t;d[q]=(FRAME,'Restore original named gallery support column continuously to measured bearing soil',None)
 a.emit('F10_gallery_bearing_columns',d,dict(first_error='R47 extended gallery casting stops at-467 without reaching measured soil; same two whole source columns',columns=[99,107],z=-168,upper_columns_preserved=True,foundation_source='Measured exact original bearing soil at-479/-478; not inferred from air',no_route_or_motion_volume_filled=True))
 a.read((16,-365,300),(51,-356,316));d={};lights=[];table=[]
 for q,state in list(a.s.items()):
  x,y,z=q
  if not(16<=x<=51 and -365<=y<=-356 and 300<=z<=315):continue
  if state==WALL and(y==-356 or x in(16,51)or z in(300,315)):d[q]=('minecraft:black_concrete','Complete existing SEELE wall and ceiling finish; entrance stays open',None)
  if state.startswith('minecraft:light['):
   centre=32<=x<=36 and 307<=z<=309
   (table if centre else lights).append(list(q));d[q]=('minecraft:light[level=14,waterlogged=false]','Day lighting defaults bright; finite meeting button later controls exact light list',None)
 button=(17,-363,312);assert a.s[button]in AIR;d[button]=('minecraft:polished_blackstone_button[face=wall,facing=east,powered=false]','Actual wall-supported SEELE daily/meeting lighting button',None)
 a.emit('S01_S02_black_room_lighting',d,dict(first_error='R47 room shell remained grey and fixed low ambient light has no physical mode switch',room=[[16,-365,300],[51,-356,315]],entrance=[[26,-364,315],[30,-362,315]],reader_and_lift_NBT_unchanged=True,button=list(button),ambient=lights,table=table,default='daily bright',meeting='all ambient0; existing table lights12/14',read_card_clearance_policy_unchanged=True))
 (a.out/'r48_seele_lighting.json').write_text(json.dumps(dict(schema=48,dimension=DIM,installed=True,button=list(button),ambient=lights,table=table),indent=2),'utf8')
 a.recipe();(a.out/'manifest.json').write_text(json.dumps(dict(world=str(a.world),components=a.components,total_cells=len(a.all),world_written=False,Java_Gradle_SHA_started=False,requires_native_validation=['both experimental lifts call/board/move/reload','two capsules mount/measure/hatch/exit','native bidirectional moving walks in client','NERV employee swipe vs no-card, spectator, safe egress and occupied closure','manual pilot room door while NPC boarding; original hangar interlocks','SEELE daily/meeting persisted modes with real card-gated entry','complete source-generation cold chunk after receipt'],reference_adoptions={'station':'https://www.odakyu.jp/station/hakone_yumoto/index.html; static gate buffer and separate directions adapted to retained Minecraft hall','TV':'https://evangelion.fandom.com/wiki/SEELE; dark sound-only composition secondary reference; no claim of exact official room dimensions','original_design':'black concrete and table-only emphasis explicitly requested by user; all block geometry original'}),ensure_ascii=False,indent=2),'utf8')
if __name__=='__main__':main()
