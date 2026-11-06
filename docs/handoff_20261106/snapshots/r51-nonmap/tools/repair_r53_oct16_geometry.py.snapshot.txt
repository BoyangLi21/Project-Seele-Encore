"""Exact candidate edits at the reported transfer pits and black corridor walls.

The three repeated bank-one pockets use the original lane centres and the
measured existing floor height. No route, entity or traffic save is rewritten.
"""
from pathlib import Path
import argparse,json,gzip
from query_blocks import read_box
import regional_voxels as vox

def prepare(base,world):
 vox.WORLD=world;vox.DIM='projectseele:geofront';vox.OUT=base/'oct16-static-repair'/world.name
 p=vox.Painter(vertical_bounds=(-1440,320));rows=[]
 def change(at,before,after,reason):
  if before==after:return
  p.exact((*at,*at),before,after,reason)
  rows.append(dict(pos=at,before=before,after=after,reason=reason))
 for centre in (-12,30,72):
  lo=(centre-15,-1043,124);hi=(centre+15,-1038,139)
  measured=read_box(world,vox.DIM,lo,hi)
  for at,state in measured.items():
   if state!='minecraft:air':continue
   change(at,state,'projectseele:nerv_floor_panel' if at[1]==-1038 else 'projectseele:nerv_structural_panel','reported_bank_one_redundant_floor_pockets')
 lo=(-46,-499,368);hi=(53,-496,377)
 measured=read_box(world,vox.DIM,lo,hi)
 painted={'minecraft:gray_concrete','projectseele:nerv_wall_panel','projectseele:nerv_wall_datum'}
 for at,state in measured.items():
  if at[2] not in (368,369,375,377) or state not in painted:continue
  change(at,state,'minecraft:black_concrete','reported_complete_corridor_wall_finish')
 p.meta.update(reported_coordinates=[[-14,-1039,131],[27,-499,368]],floor_reference=[28,-1037,154],floor_reference_mesh_height=-1037.22646,upper_floor_cap_y=-1038)
 if rows:
  p.apply('reported_bank_pockets_and_corridor_finish')
  out=vox.OUT/'EXACT_DELTA.json.gz';out.write_bytes(gzip.compress(json.dumps(rows).encode('utf8'),mtime=0))
  for lo,hi in [((-28,-1043,124),(88,-1038,139)),((-46,-499,368),(53,-496,377))]:
   back=read_box(world,vox.DIM,lo,hi)
   for row in rows:
    at=tuple(row['pos'])
    if at in back:assert back[at]==row['after'],at
 print(json.dumps(dict(world=str(world),changed=len(rows),readback=True)))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--base',type=Path,required=True);a.add_argument('--world',type=Path,required=True);q=a.parse_args();prepare(q.base,q.world)
