"""Compile an exact reversible emergency pavement after real city retraction."""
import json
from pathlib import Path
import numpy as np
import scan_regional_completion as scan
from query_blocks import iter_block_entities,AIR
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_R21_REVIEW';OUT=ROOT/'artifacts/world_repair_r21/battlefield'
def fixed_power_pylon(q):
 x,y,z=q;y-=80
 if not 1<=y<=28:return False
 for cx in(-150,210):
  for cz in(60,220,380):
   if z!=cz:continue
   dx=abs(x-cx);spread=max(0,4-y//7)
   if y in(22,27)and dx<=5 or dx==spread or y%6==0 and dx<=spread:return True
 return False
def main():
 scan.WORLD=WORLD;lo=(-144,80,41);hi=(207,180,392);a,p=scan.volume(lo,hi);be=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi));rows=[];counts={}
 assert not any('movingelevators' in str(t['id']) for q,t in be.items()),'All public-lift controls must be below the battle plane'
 for i,state in enumerate(p):
  base=state.split('[')[0]
  if base in AIR|{'minecraft:light','minecraft:structure_void'}:continue
  points=np.argwhere(a[1:]==i)
  for yy,zz,xx in points:
   q=(int(xx+lo[0]),int(yy+lo[1]+1),int(zz+lo[2]))
   if fixed_power_pylon(q):continue
   row=[*q,state,'minecraft:air']
   if q in be:row.append(be[q].snbt())
   rows.append(row)
  counts[state]=len(points)
 for zz,xx in np.ndindex(a.shape[1:]):
  state=p[a[0,zz,xx]]
  if state.split('[')[0] in AIR or any(k in state for k in ['_stairs[','_slab[','_trapdoor[','_bars[']):
   q=(xx+lo[0],80,zz+lo[2]);rows.append([*q,state,'projectseele:nerv_machine_panel'])
 rows.sort(key=lambda a:(-a[1],a[2],a[0]))
 data=dict(version=21,center=[32,80,217],bounds=[-144,41,207,392],span=[352,352],cells=rows,source='Actual native city retraction to depth 312; exact field cells and block-entity NBT',surface_floor=80)
 OUT.mkdir(parents=True,exist_ok=True);(WORLD/'battlefield_r21.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');(OUT/'manifest.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');(OUT/'remaining_materials.json').write_text(json.dumps(counts,indent=2),encoding='utf8');print('Emergency reversible cells',len(rows),'block entities',len(be))
if __name__=='__main__':main()
