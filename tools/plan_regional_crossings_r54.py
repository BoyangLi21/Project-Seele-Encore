"""Complete street crossings on existing surveyed regional junctions.
No road elevation, width, rail, intersection device or block-entity change.
"""
from pathlib import Path
import argparse,json,gzip,math,collections
import numpy as np
from query_blocks import read_box,iter_block_entities

JUNCTIONS=[('tokyo_west_north',-648,8),('tokyo_west_civic',-536,176),('tokyo_north_west',-508,-352),('tokyo_north_east',-340,-296),('tokyo_south_west',-448,632),('tokyo_south_east',-224,744),('hakone_centre_west',-1688,492),('hakone_centre_east',-1432,748),('harbour_north',336,192),('harbour_east',392,248)]
ROAD={'minecraft:black_concrete','minecraft:white_concrete','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}
PAVING={'minecraft:smooth_stone','minecraft:light_gray_concrete','minecraft:gray_concrete'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--authority',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--all-declared',action='store_true');a=ap.parse_args();source=np.load(a.authority)
 junctions=JUNCTIONS
 if a.all_declared:
  junctions=[]
  for zone in json.loads((a.world/'regional_plan.json').read_text('utf8'))['zones']:
   if zone['kind']!='district':continue
   x0,x1,z0,z1=zone['bounds'];step=zone['spacing']
   # These are the original source-generated street axes, not inferred air or
   # walkable terrain. The current road authority below must also accept all arms.
   for x in range(x0+step,x1-16,step):
    for z in range(z0+step,z1-16,step):junctions.append((f"{zone['id']}_{x}_{z}",x,z))
 wanted={(x+dx,z+dz)for _,x,z in junctions for dx in range(-16,17)for dz in range(-16,17)}
 authority={tuple(map(int,q)):(float(y),int(f))for q,y,f in zip(source['coordinates'],source['actual_feet'],source['flags'])if tuple(map(int,q))in wanted and np.isfinite(y)}
 rows={};sites=[];held=[]
 for name,cx,cz in junctions:
  levels=[authority[(x,z)][0]for x in range(cx-16,cx+17)for z in range(cz-16,cz+17)if (x,z)in authority]
  if not levels:held.append(dict(id=name,reason='Original crossing is no longer in current road authority'));continue
  lo=(cx-16,math.floor(min(levels))-2,cz-16);hi=(cx+16,math.ceil(max(levels))+3,cz+16);actual=read_box(a.world,'projectseele:geofront',lo,hi);bes=dict(iter_block_entities(a.world,'projectseele:geofront',lo,hi));patch={};footpaths=[];failure=[]
  def mark(x,z,white):
   entry=authority.get((x,z))
   if entry is None or not entry[1]&16:failure.append([x,z,'outside original carriageway']);return
   y=math.ceil(entry[0])-1;q=(x,y,z);old=actual.get(q);block=(old or'').split('[')[0]
   if block not in ROAD or q in bes:failure.append([x,z,old]);return
   if '['in old:new=('projectseele:road_marking_slab'if white else'projectseele:road_asphalt_slab')+'['+old.split('[',1)[1]
   else:new='minecraft:white_concrete'if white else'minecraft:black_concrete'
   if old!=new:patch[q]=dict(pos=q,before=old,after=new,before_nbt=None,after_nbt=None,owner='r54/crossing/'+name,reason='Complete white zebra bands and left-traffic approach stop lines on unchanged existing road surfaces')
  # Remove the inherited centre dashes inside the junction itself.
  for dx in range(-7,8):
   for dz in range(-7,8):
    if abs(dx)<=4 or abs(dz)<=4:mark(cx+dx,cz+dz,False)
  for axis in(0,1):
   for side in(-1,1):
    for depth in range(8,12):
     for across in range(-4,5):
      dx,dz=(side*depth,across)if axis==0 else(across,side*depth);mark(cx+dx,cz+dz,across%2==0)
    # Stop line two metres before the crossing, only in the incoming left-traffic lane.
    for across in range(1,5):
     incoming=side*across if axis==0 else-side*across
     dx,dz=(side*14,incoming)if axis==0 else(incoming,side*14);mark(cx+dx,cz+dz,True)
    for across in(-6,-5,5,6):
     dx,dz=(side*9,across)if axis==0 else(across,side*9);x,z=cx+dx,cz+dz;entry=authority.get((x,z))
     if entry is None or entry[1]&16 or not entry[0].is_integer():continue
     q=(x,int(entry[0])-1,z);old=actual.get(q)
     if old not in PAVING or q in bes:continue
     patch[q]=dict(pos=q,before=old,after='projectseele:station_tactile_warning',before_nbt=None,after_nbt=None,owner='r54/crossing/'+name,reason='Flush tactile warning pads at the existing pedestrian curb; existing route datum is unchanged')
    walk=[(cx+side*9,cz-6),(cx+side*9,cz+6)]if axis==0 else[(cx-6,cz+side*9),(cx+6,cz+side*9)];footpaths.append(walk)
  if failure:held.append(dict(id=name,reason='Whole crossing retained because current roadway differs',examples=failure[:6]));continue
  rows.update(patch);sites.append(dict(id=name,centre=[cx,cz],cells=len(patch),four_arms=True,stopline_setback=2,crossing_paths=footpaths))
 a.out.mkdir(parents=True,exist_ok=True)
 forward=list(rows.values());inverse=[]
 for row in forward:
  r=row.copy();r['before'],r['after']=r['after'],r['before'];inverse.append(r)
 for name,rs in [('forward',forward),('inverse',inverse)]:
  with gzip.open(a.out/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
   for r in rs:f.write(json.dumps(r)+'\n')
 m=dict(schema='projectseele.r54.regional-crossings.v1',world=str(a.world),dimension='projectseele:geofront',static_cells=len(rows),sites=sites,held=held,metadata_preconditions=[],world_tables=[],world_written=False,native_passed=False,visual_self_review='pending',references=['https://www.npa.go.jp/laws/notification/koutuu/kisei/kisei20240301_1.pdf','https://www.hakonenavi.jp/transportation/station/hakone-yumoto/'])
 for name,value in [('forwardPatch.json',forward),('inversePatch.json',inverse),('positiveEditMask.json',[r['pos']for r in forward]),('installation_manifest.json',m)]:
  (a.out/name).write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf8')
 print('Prepared',len(sites),'complete junctions,',len(rows),'cells; changed sites retained',len(held))
if __name__=='__main__':main()
