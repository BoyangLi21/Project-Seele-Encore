"""Current-save Hakone station outer frame and the two named station-street shops."""
import sys,json,gzip
from pathlib import Path
from collections import Counter
sys.path.append(str(Path(__file__).resolve().parents[1]/'.Codex/map-deps'))
from school_hakone_patch_r45 import Candidate
from author_hakone_station_r45 import protect_existing
from query_blocks import AIR
WORLD=Path('F:/eva/artifacts/r53_repair_20261015/client/saves/HOTFIX_20261025')
OUT=Path('F:/eva/artifacts/r54_update_20261026/hakone_street_art')

def main():
 c=Candidate(WORLD,[-1616,104,563,-1402,148,695],'r54/hakone_station_street_art')
 protect_existing(c,json.loads((WORLD/'native_transit_r28.json').read_text('utf8')),json.loads((WORLD/'quality_walk_cases.json').read_text('utf8')))
 first={tuple(json.loads(r)['pos']) for r in gzip.open(OUT.parent/'hakone_art/forward.jsonl.gz','rt',encoding='utf8')}
 c.hard.update(first)
 def put(q,s,reason,allowed):
  if c.measured.block(q) in allowed:c.put(q,s,reason)
 meta=json.loads((WORLD/'r45_school_hakone_components.json').read_text('utf8'))['hakone']
 for st in meta['components']:
  if st['kind']!='full_retained_operating_station_building':continue
  x,y,z,X,Y,Z=st['bounds'];feet=st['feet'][1]
  for zz in [z-2,Z+2]:
   for xx in range(x,X+1):
    for yy in range(105,Y-4):
     put((xx,yy,zz),'minecraft:stripped_spruce_log[axis=y]' if yy not in [feet-2,feet-1] else 'minecraft:stripped_dark_oak_log[axis=x]','Complete measured outer station columns and platform fascia timber finish; solid collision unchanged',{'minecraft:light_gray_concrete','projectseele:residential_plaster'})
  c.components.append(dict(id=st['id']+'/outer_frame',bounds=st['bounds'],source='Actual outer columns at metadata Z edge plus two; measured complete original station frame'))
 # Existing shop names, use and bounds are confirmed by actual fixture NBT
 # and the original land-use catalogue. No new shop, door or room is invented.
 shops=[('new_hakone/05-05','Yamate tea room',-1613,-1571,567,609,7),('new_hakone/06-05','Hakone stationery',-1549,-1507,567,609,6)]
 for ident,title,x,X,z,Z,floors in shops:
  mid=(x+X)//2;top=104+5*floors
  for xx in range(x,X+1):
   for yy in range(105,top):
    band=(yy-104)%5
    floor=104+((yy-105)//5)*5
    opaque={'minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:smooth_sandstone','minecraft:white_concrete'}
    pier=all(c.measured.get(xx,floor+dy,Z) in opaque for dy in [1,2,3])
    state='minecraft:stripped_spruce_log[axis=y]' if pier else 'minecraft:smooth_sandstone'
    if band==4:state='minecraft:stripped_dark_oak_log[axis=x]'
    put((xx,yy,Z),state,'Whole named station-street facade: cream upper offices, regular timber bays and continuous floor cornices',{'minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:smooth_sandstone','minecraft:white_concrete'})
   # Existing R24 wall-attached two-deep canopy is kept at its actual elevation.
   for zz in [Z+1,Z+2]:
    put((xx,108,zz),'minecraft:deepslate_tile_slab[type=top,waterlogged=false]','Entire measured shop arcade canopy becomes a charcoal tiled rain shelter',{'minecraft:smooth_stone_slab[type=top,waterlogged=false]'})
   if c.measured.get(xx,108,Z+2)=='minecraft:smooth_stone_slab[type=top,waterlogged=false]':
    put((xx,108,Z+3),'minecraft:deepslate_tile_slab[type=bottom,waterlogged=false]','Attached one-block drooped arcade eave above the existing public browsing apron',AIR)
   # Five-block repeating storey remains visible. Added shades are attached
   # only to measured opaque lintels above each actual window row.
   for yy in range(113,top,5):
    if c.measured.get(xx,yy,Z) in {'minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:smooth_sandstone','minecraft:white_concrete'}:
     put((xx,yy,Z+1),'minecraft:spruce_slab[type=top,waterlogged=false]','Thin projecting timber sunshade on measured complete upper-floor lintel',AIR)
  # Side returns tie the street-facing timber work into actual building corners.
  for xx in [x,X]:
   for zz in range(Z-5,Z+1):
    for yy in range(105,top):
     state='minecraft:stripped_spruce_log[axis=y]' if zz==Z or zz==Z-5 else 'minecraft:smooth_sandstone'
     put((xx,yy,zz),state,'Six-block return of the named building facade, without touching interior circulation',{'minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:white_concrete','minecraft:smooth_sandstone'})
  c.components.append(dict(id=ident,title=title,bounds=[x,104,z,X,top,Z],scope='Entire street-facing facade, six-block side returns, all upper storey sunshades and original ground shop canopy',retained='All original shops, offices, doors, glazing, signs, fixtures, floors, stairs and public approaches'))
 rows=[c.target[q] for q in sorted(c.target)];OUT.mkdir(parents=True,exist_ok=True)
 for name,inverse in [('forward',False),('inverse',True)]:
  with gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
   for a in rows:
    b=dict(a)
    if inverse:b['before'],b['after']=a['after'],a['before'];b['before_nbt'],b['after_nbt']=a['after_nbt'],a['before_nbt']
    f.write(json.dumps(b,ensure_ascii=False)+'\n')
 for name,data in [('components.json',c.components),('requested_native_states.json',sorted({r['after'] for r in rows})),('preserved_block_entities.json',[dict(pos=list(q),state=c.measured.block(q),snbt=t) for q,t in c.tags.items()]),('camera_itinerary.json',[dict(id='station_street',position=[-1560,108,615],look_at=[-1560,120,609]),dict(id='station_outer_frame',position=[-1440,108,700],look_at=[-1480,119,693])])]:
  (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
 with gzip.open(OUT/'positive_edit_mask.jsonl.gz','wt',encoding='utf8') as f:
  for r in rows:f.write(json.dumps(r['pos'])+'\n')
 assert not (first&set(c.target))
 assert all(not r['before'].startswith('mtr:') and 'door[' not in r['before'] and r['before_nbt'] is None for r in rows)
 summary=dict(world=str(WORLD),dimension='projectseele:geofront',cells=len(rows),modified_existing_block_entities=0,preserved_existing_block_entities=len(c.tags),first_batch_overlap=0,features=dict(Counter(r['reason'] for r in rows)),world_written=False,native_visual_pending=True,scope='Station outer frame and the existing Yamate tea room / Hakone stationery street-front buildings; no whole-map completion claim')
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8');print(json.dumps(summary))
if __name__=='__main__':main()
