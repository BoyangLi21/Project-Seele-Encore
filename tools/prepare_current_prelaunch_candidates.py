"""Finite exact saved blocks and native shapes for Root's actual complete prelaunch envelopes."""
from pathlib import Path
import hashlib,json,math
import numpy as np
from query_blocks import iter_selected_sections,iter_block_entities,chunk_statuses,AIR,dimension_dir
from verify_main_r20 import entities

ROOT=Path(__file__).resolve().parents[1];WORLD=Path('D:/eva/artifacts/map_complete_20261013/WORLD')
OUT=ROOT/'.Codex/map_complete_20261013/route_audit/prelaunch_world_current'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def overlap(a,b):return all(a[i+3]>b[i] and a[i]<b[i+3] for i in range(3))

def main():
 doc=json.loads((OUT/'CURRENT_PRELAUNCH_PART_ENVELOPES.json').read_text('utf8'));shapep=WORLD/'native_collision_shapes.json';shapes=json.loads(shapep.read_text('utf8'))
 allboxes=np.array([b for boxes in shapes.values() for b in boxes]);ext=np.r_[allboxes[:,:3].min(0),allboxes[:,3:].max(0)].tolist()
 regions=set();selected={};groups=[]
 for leg in doc['legs']:
  env=np.array([p['bounds'] for p in leg['parts']]);lo=tuple(math.floor(float(env[:,i].min())-ext[i+3]) for i in range(3));hi=tuple(math.floor(float(env[:,i+3].max())-ext[i]) for i in range(3))
  groups.append(dict(leg=leg['leg'],variant=leg['variant'],envelopes=env,lo=lo,hi=hi,cells=[],unknown_shapes=[],measured_nonair=0))
  for x in range(lo[0]//16,hi[0]//16+1):
   for z in range(lo[2]//16,hi[2]//16+1):selected.setdefault((x,z),set()).update(range(lo[1]//16,hi[1]//16+1))
 for cx,cz in selected:regions.add(dimension_dir(WORLD,'projectseele:geofront')/'region'/f'r.{cx//32}.{cz//32}.mca')
 before={str(p):sha(p) for p in sorted(regions)};status=chunk_statuses(WORLD,'projectseele:geofront',selected);assert all(s=='full' for s in status.values()),{p:s for p,s in status.items() if s!='full'}
 sections=0
 for cx,cz,sy,palette,indices in iter_selected_sections(WORLD,'projectseele:geofront',selected):
  sections+=1;sec=[cx*16,sy*16,cz*16,cx*16+16,sy*16+16,cz*16+16];localgroups=[g for g in groups if overlap(sec,list(g['lo'])+[a+1 for a in g['hi']])]
  if not localgroups:continue
  for k,state in enumerate(palette):
   if state in AIR:continue
   native=shapes.get(state)
   if native==[]:continue
   points=np.argwhere(indices.reshape(16,16,16)==k)
   if not len(points):continue
   for ly,lz,lx in points:
    p=(cx*16+int(lx),sy*16+int(ly),cz*16+int(lz))
    for g in localgroups:
     if not all(g['lo'][i]<=p[i]<=g['hi'][i] for i in range(3)):continue
     g['measured_nonair']+=1
     if native is None:g['unknown_shapes'].append(dict(position=p,state=state));continue
     boxes=[];env=g['envelopes']
     for b in native:
      w=np.r_[np.array(p)+b[:3],np.array(p)+b[3:]]
      if np.any(np.all((env[:,3:]>w[:3])&(env[:,:3]<w[3:]),axis=1)):boxes.append(w.tolist())
     if boxes:g['cells'].append(dict(position=p,state=state,native_boxes=boxes))
  if sections%500==0:print('sections',sections,'candidates',sum(len(g['cells']) for g in groups),flush=True)
 after={str(p):sha(p) for p in sorted(regions)};assert before==after,'World changed during read; discard and rerun'
 lo=tuple(min(g['lo'][i] for g in groups) for i in range(3));hi=tuple(max(g['hi'][i] for g in groups) for i in range(3))
 bes=list(iter_block_entities(WORLD,'projectseele:geofront',lo,hi));rows=[]
 for g in groups:
  rows.append({k:v for k,v in g.items() if k!='envelopes'}|dict(block_entities_in_scope=[dict(position=p,nbt=t.snbt()) for p,t in bes if all(g['lo'][i]<=p[i]<=g['hi'][i] for i in range(3))]))
  print(g['leg'],'native',len(g['cells']),'unknown',len(g['unknown_shapes']),flush=True)
 actors=[]
 for uid,tag in entities(WORLD).items():
  if str(tag.get('id','')) not in ('projectseele:nerv_hangar_door','projectseele:nerv_silo_door','projectseele:nerv_carrier_platform'):continue
  p=list(map(float,tag.get('Pos',[])))
  if len(p)==3 and all(lo[i]-150<=p[i]<=hi[i]+150 for i in range(3)):actors.append(dict(uuid_ints=uid,entity_id=str(tag['id']),position=p,nbt_snbt=tag.snbt()))
 result=dict(world=str(WORLD),world_written=False,directory_fingerprint=doc['directory_fingerprint'],windows_sha256=sha(OUT/'CURRENT_PRELAUNCH_WINDOWS.json'),native_shapes_sha256=sha(shapep),native_shape_local_extrema=ext,region_sha256=before,read_sections=sections,legs=rows,actual_saved_gate_and_carrier_entities=actors,scope='Exact native shape boxes filtered by all actual part envelopes, never by an entity AABB. Unknown shapes remain unresolved. Current saved machine NBT is evidence, not final owner admission.')
 (OUT/'CURRENT_WORLD_NATIVE_CANDIDATES.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
 (OUT/'CURRENT_SAVED_GATE_AND_CARRIER_NBT.json').write_text(json.dumps(actors,ensure_ascii=False,indent=2)+'\n','utf8')

if __name__=='__main__':main()
