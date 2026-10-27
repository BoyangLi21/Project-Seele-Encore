"""Measured Hakone station exterior/interior detailing; never writes a world."""
import sys,json,gzip
from pathlib import Path
from collections import Counter
sys.path.append(str(Path(__file__).resolve().parents[1]/'.Codex/map-deps'))
from school_hakone_patch_r45 import Candidate
from author_hakone_station_r45 import protect_existing
from query_blocks import AIR
from plan_hakone_lighting_r54 import source_lamp_targets,WARM

WORLD=Path('F:/eva/artifacts/r53_repair_20261015/client/saves/HOTFIX_20261025')
OUT=Path('F:/eva/artifacts/r54_update_20261026/hakone_art')

def main():
 c=Candidate(WORLD,[-1558,104,617,-1402,148,695],'r54/hakone_station_art')
 meta=json.loads((WORLD/'r45_school_hakone_components.json').read_text('utf8'))['hakone']
 protect_existing(c,json.loads((WORLD/'native_transit_r28.json').read_text('utf8')),json.loads((WORLD/'quality_walk_cases.json').read_text('utf8')))
 # Preserve actual opening leaves and their full immediate swept/approach volume.
 for port in meta['ports']:
  if 'position' not in port:continue
  x,y,z=port['position']
  for X in range(x-1,x+2):
   for Z in range(z-2,z+3):
    for Y in range(y,y+3):c.hard.add((X,Y,Z))
 def put(q,state,why,allowed=None):
  old=c.measured.block(q)
  if allowed is None or old in allowed:c.put(q,state,why)
 def add(q,state,why):put(q,state,why,AIR)
 stations=[r for r in meta['components'] if r['kind']=='full_retained_operating_station_building']
 for station in stations:
  x,y,z,X,Y,Z=station['bounds'];mid=(z+Z)//2;edge=Y-4
  # Retain the measured complete pitched shell; give its stepped edges proper
  # tile nosings, raised ridge and an overhanging half-block gutter/eave profile.
  for xx in range(x,X+1):
   for zz in range(z,Z+1):
    top=edge+round(4*(1-abs(zz-mid)/15))
    if c.measured.get(xx,top,zz)!='minecraft:gray_concrete':continue
    nxt=edge+round(4*(1-abs(zz+(1 if zz<mid else -1)-mid)/15))
    state='minecraft:deepslate_tiles'
    if zz!=mid and nxt>top:state=f'minecraft:deepslate_tile_stairs[facing={"south" if zz<mid else "north"},half=bottom,shape=straight,waterlogged=false]'
    put((xx,top,zz),state,'Complete retained pitched station roof: charcoal tile courses with shaped uphill nosing')
    if (xx-x)%8==0 and all(c.measured.get(xx,yy,zz) in AIR for yy in range(top-5,top)):
     add((xx,top-1,zz),'minecraft:stripped_spruce_log[axis=z]','Exposed rafter attached to measured roof, with five-block original clear volume below')
   if c.measured.get(xx,Y,mid)=='minecraft:gray_concrete':
    add((xx,Y+1,mid),'minecraft:deepslate_tile_slab[type=bottom,waterlogged=false]','Continuous half-block raised tile ridge attached to existing roof')
   for zz,sgn in [(z,-1),(Z,1)]:
    if c.measured.get(xx,edge,zz)=='minecraft:gray_concrete':
     for distance in [1,2]:
      put((xx,edge,zz+sgn*distance),'minecraft:deepslate_tile_slab[type=top,waterlogged=false]','Complete measured outer canopy border receives thin tiled eave profile',{'minecraft:light_gray_concrete'})
     if c.measured.get(xx,edge,zz+sgn*2)=='minecraft:light_gray_concrete':
      add((xx,edge,zz+sgn*3),'minecraft:deepslate_tile_slab[type=bottom,waterlogged=false]','One-block attached weather eave beyond actual outer canopy border')
     put((xx,edge-1,zz),'minecraft:spruce_planks','Warm timber soffit on retained continuous roof fascia',{'minecraft:dark_oak_planks'})
  # Full real end gables: cream panels, timber king post and horizontal tie.
  for xx in [x,X]:
   for zz in range(z,Z+1):
    for yy in range(edge,Y):
     if c.measured.get(xx,yy,zz)=='projectseele:residential_plaster':
      state='minecraft:stripped_spruce_log[axis=y]' if zz==mid else 'minecraft:stripped_spruce_log[axis=z]' if yy==edge else 'minecraft:smooth_sandstone'
      put((xx,yy,zz),state,'Complete existing gable uses plaster-toned infill and expressed timber frame')
  # Frame cladding is confined to real columns; no new ground-level obstacles.
  for zz in [z,Z]:
   for xx in range(x,X+1):
    for yy in range(105,edge):
     old=c.measured.get(xx,yy,zz)
     if old in {'projectseele:residential_plaster','minecraft:light_gray_concrete'}:
      put((xx,yy,zz),'minecraft:stripped_spruce_log[axis=y]' if yy%7!=0 else 'minecraft:dark_oak_planks','Existing station colonnade receives timber wraps and expressed beam collars')
  # Keep the original full hall lamp layout; adding another row here doubled
  # the fixtures and mixed white cubes with warm pendant lights.
  for xx in range(x+8,X-6,8):
   for zz in range(z+1,Z):
    if c.measured.get(xx,111,zz)=='minecraft:oak_planks':
     put((xx,111,zz),'minecraft:stripped_spruce_log[axis=z]','Complete lower concourse ceiling: measured transverse timber beam rhythm')
  c.components.append(dict(id=station['id']+'/r54_art',bounds=station['bounds'],features=['tile_nosings','raised_ridge','projecting_eaves','exposed_rafters','timber_gables','column_wraps','ceiling_beams','original_layout_warm_lamps']))
 # Six already registered service rooms remain in place. Rebuild their actual
 # opaque frontage into a timber shopfront, retaining every glazed opening/door.
 for room in meta['components']:
  if room['kind']=='full_retained_operating_station_building':continue
  x,y,z,X,Y,Z=room['bounds'];front=z if room['kind'] in {'waiting_room','staff_office'} else Z;sgn=-1 if front==z else 1
  for xx in range(x,X+1):
   for yy in range(y+1,Y):
    for zz in [z,Z]:
     old=c.measured.get(xx,yy,zz)
     if old!='projectseele:residential_plaster':continue
     state='minecraft:stripped_spruce_log[axis=y]' if xx in [x,X] or (xx-x)%4==0 else 'minecraft:spruce_planks' if yy==y+1 else 'minecraft:smooth_sandstone'
     if yy==Y-1:state='minecraft:stripped_dark_oak_log[axis=x]'
     put((xx,yy,zz),state,'Complete named service-room frontage: wood plinth, cream infill, timber lintel and bay posts')
   for zz in range(z,Z+1):
    put((xx,Y,zz),'minecraft:spruce_planks','Named service-room full ceiling receives warm continuous wood finish',{'minecraft:oak_planks'})
   # Attached shop awning uses the existing solid lintel, never an inferred bay.
   if c.measured.get(xx,Y-1,front)=='projectseele:residential_plaster':
    add((xx,Y,front+sgn),'minecraft:deepslate_tile_slab[type=top,waterlogged=false]','Complete shopfront tiled drip edge attached directly to existing roof; four-block passage headroom retained')
  c.components.append(dict(id=room['id']+'/r54_shopfront',bounds=room['bounds'],features=['timber_bays','cream_infill','tiled_drip_edge','wood_lintel']))
 for owner,q in source_lamp_targets(meta['components']):
  put(q,WARM,'Use one warm lamp at each original station ceiling-light position; no second fixture row',{'minecraft:sea_lantern'})
 c.cameras=[dict(id='whole_station',position=[-1367.5,106.62,708.5],look_at=[-1480,125,656]),dict(id='S1_hall',position=[-1521.5,106.6,675.5],look_at=[-1460,108,670]),dict(id='R1_shops',position=[-1526.5,106.6,636.5],look_at=[-1475,108,630]),dict(id='street_eaves',position=[-1490,108,700],look_at=[-1480,126,676])]
 rows=[c.target[q] for q in sorted(c.target)]
 OUT.mkdir(parents=True,exist_ok=True)
 for name,inverse in [('forward',False),('inverse',True)]:
  with gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
   for row in rows:
    r=dict(row)
    if inverse:r['before'],r['after']=row['after'],row['before'];r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
    f.write(json.dumps(r,ensure_ascii=False)+'\n')
 with gzip.open(OUT/'positive_edit_mask.jsonl.gz','wt',encoding='utf8') as f:
  for r in rows:f.write(json.dumps(r['pos'])+'\n')
 for name,data in [('components.json',c.components),('camera_itinerary.json',c.cameras),('requested_native_states.json',sorted({r['after'] for r in rows})),('preserved_block_entities.json',[dict(pos=list(q),state=c.measured.block(q),snbt=t) for q,t in c.tags.items()])]:
  (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
 summary=dict(world=str(WORLD),dimension='projectseele:geofront',cells=len(rows),features=dict(Counter(r['reason'] for r in rows)),original_block_entities_preserved=len(c.tags),modified_original_block_entities=0,traffic_topology_modified=False,floors_doors_stairs_unchanged=True,world_written=False,visual_native_pending=True,adaptation='Hakone hot-spring town timber/cream/tile language on the existing R1/S1 elevated four-platform station; not a reconstruction of the real three-track terminal',sources=['https://www.odakyu.jp/station/hakone_yumoto/index.html','https://www.hakonenavi.jp/transportation/station/hakone-yumoto/'])
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8')
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf8');main()
