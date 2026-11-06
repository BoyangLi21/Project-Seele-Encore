"""Current World read of the actual seated plug's finite prelaunch envelopes."""
from pathlib import Path
import json,math,hashlib,collections
import numpy as np
from query_blocks import iter_selected_sections,dimension_dir,AIR,iter_block_entities
R=Path(__file__).resolve().parents[1];A=R/'.Codex/map_complete_20261013/route_audit';O=A/'seated_plug_prelaunch';W=Path('D:/eva/artifacts/map_complete_20261013/WORLD')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 data=json.loads((O/'TRUE_PLUG_ENVELOPES.json').read_text('utf8'));env=np.array([p['bounds'] for leg in data['legs'] for p in leg['parts']]);shapes=json.loads((W/'native_collision_shapes.json').read_text('utf8'))
 for name in ['CURRENT_PRODUCTION_SUPPLEMENTAL_SHAPES.json','CURRENT_PRODUCTION_REBASED_SHAPES.json','GATE14_RESOLVED_PRODUCTION_SHAPES.json']:shapes.update({k:v['native_boxes'] for k,v in json.loads((A/'prelaunch_world_current'/name).read_text('utf8'))['rows'].items()})
 allboxes=np.array([b for boxes in shapes.values() for b in boxes]);ext=np.r_[allboxes[:,:3].min(0),allboxes[:,3:].max(0)];selected={}
 for e in env:
  lo=np.floor(e[:3]-ext[3:]).astype(int);hi=np.floor(e[3:]-ext[:3]).astype(int)
  for x in range(lo[0]//16,hi[0]//16+1):
   for z in range(lo[2]//16,hi[2]//16+1):selected.setdefault((x,z),set()).update(range(lo[1]//16,hi[1]//16+1))
 files={dimension_dir(W,'projectseele:geofront')/'region'/f'r.{cx//32}.{cz//32}.mca' for cx,cz in selected};before={str(p):sha(p) for p in files};rows=[];unknown=[]
 for cx,cz,sy,palette,indices in iter_selected_sections(W,'projectseele:geofront',selected):
  for k,state in enumerate(palette):
   if state in AIR:continue
   boxes=shapes.get(state)
   if boxes==[]:continue
   for ly,lz,lx in np.argwhere(indices.reshape(16,16,16)==k):
    p=np.array([cx*16+int(lx),sy*16+int(ly),cz*16+int(lz)])
    if not np.any(np.all((env[:,3:]>p+ext[:3])&(env[:,:3]<p+ext[3:]),axis=1)):continue
    if boxes is None:unknown.append(dict(position=p.tolist(),state=state));continue
    native=[]
    for b in boxes:
     world=np.r_[p+b[:3],p+b[3:]]
     if np.any(np.all((env[:,3:]>world[:3])&(env[:,:3]<world[3:]),axis=1)):native.append(world.tolist())
    if native:rows.append(dict(position=p.tolist(),state=state,native_boxes=native,conditional_closed_barrier=state=='minecraft:barrier'))
 assert before=={str(p):sha(p) for p in files},'World changed during finite read'
 (O/'CURRENT_NATIVE_CANDIDATES.json').write_text(json.dumps(dict(world_written=False,source_region_sha256=before,envelopes_sha256=sha(O/'TRUE_PLUG_ENVELOPES.json'),unknown_shapes=unknown,cells=rows),ensure_ascii=False,indent=2),'utf8');print('actual shapes',len(rows),'unknown',len(unknown),'states',collections.Counter(c['state'] for c in rows),flush=True)
if __name__=='__main__':main()
