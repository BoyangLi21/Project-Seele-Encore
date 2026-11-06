"""Read exact current-world native obstacles for all nine declared bank heads."""
from pathlib import Path
import hashlib,json,math
import numpy as np
from query_blocks import read_box,iter_block_entities,AIR,dimension_dir

ROOT=Path(__file__).resolve().parents[1];WORLD=Path('D:/eva/artifacts/map_complete_20261013/WORLD')
OUT=ROOT/'.Codex/map_complete_20261013/route_audit/bank_world_current'
INPUT=ROOT/'.Codex/map_complete_20261013/route_audit/phases_r53/BANK_HEAD_CIVIL_INTERFACE.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def intersects(a,b):return all(a[i+3]>b[i]and a[i]<b[i+3]for i in range(3))

def main():
 doc=json.loads((OUT/'CURRENT_ALL48_PART_ENVELOPES.json').read_text('utf8'));assert doc['interface_sha256']==sha(INPUT)
 shapes=json.loads((WORLD/'native_collision_shapes.json').read_text('utf8'));allboxes=np.array([b for boxes in shapes.values()for b in boxes]);ext=np.concatenate([allboxes[:,:3].min(0),allboxes[:,3:].max(0)]).tolist()
 result=[];regions=set()
 for bank in doc['banks']:
  envelopes=[p['bounds']for p in bank['parts']];limits=np.array(envelopes)
  lo=tuple(math.floor(float(limits[:,i].min())-ext[i+3])for i in range(3));hi=tuple(math.floor(float(limits[:,i+3].max())-ext[i])for i in range(3))
  c=read_box(WORLD,'projectseele:geofront',lo,hi);unknown=[];rows=[]
  for p,s in c.items():
   if s in AIR:continue
   local=shapes.get(s)
   if local is None:unknown.append(dict(position=p,state=s));continue
   boxes=[]
   for b in local:
    w=[p[i]+b[i]for i in range(3)]+[p[i]+b[i+3]for i in range(3)]
    if any(intersects(w,e)for e in envelopes):boxes.append(w)
   if boxes:rows.append(dict(position=p,state=s,native_boxes=boxes,conditional_closed_barrier=s=='minecraft:barrier'))
  tags=[dict(position=p,nbt=t.snbt())for p,t in iter_block_entities(WORLD,'projectseele:geofront',lo,hi)]
  for rx in range(lo[0]//512,hi[0]//512+1):
   for rz in range(lo[2]//512,hi[2]//512+1):regions.add(dimension_dir(WORLD,'projectseele:geofront')/'region'/f'r.{rx}.{rz}.mca')
  result.append(dict(bank=bank['bank'],root_translation=bank['root_translation'],read_box=[lo,hi],measured_cells=len(c),cells=rows,unknown_shapes=unknown,block_entities_in_scope=tags))
  print(bank['bank'],'exact native candidates',len(rows),'unknown',len(unknown),flush=True)
 output=dict(world=str(WORLD),world_written=False,interface_sha256=sha(INPUT),native_shapes_sha256=sha(WORLD/'native_collision_shapes.json'),
  native_shape_local_extrema=ext,region_sha256={str(p):sha(p)for p in sorted(regions)},banks=result,
  rule='All48 actual member continuous envelopes select potential native box cells only. Collision and permission are not inferred from envelopes; unknown shapes remain unresolved.')
 (OUT/'CURRENT_WORLD_NATIVE_CANDIDATES.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n','utf8')

if __name__=='__main__':main()
