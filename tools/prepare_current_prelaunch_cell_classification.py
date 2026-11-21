"""Re-read exact already-measured prelaunch cells; attach explicit installed dynamic masks."""
from pathlib import Path
import json,gzip,hashlib,collections
import numpy as np
from query_blocks import iter_selected_sections,iter_block_entities,dimension_dir,AIR
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'.Codex/map_complete_20261013/route_audit/prelaunch_world_current';W=Path('D:/eva/artifacts/map_complete_20261013/WORLD');G=ROOT/'.Codex/map_complete_20261013/route_audit/typed_gates_current'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 doc=json.loads((O/'EXACT_PRELAUNCH_STATIC_CELLS_FOR_ROOT.json').read_text('utf8'));shapes=json.loads((W/'native_collision_shapes.json').read_text('utf8'));supp=json.loads((O/'CURRENT_PRODUCTION_SUPPLEMENTAL_SHAPES.json').read_text('utf8'))['rows'];shapes.update({s:v['native_boxes'] for s,v in supp.items()})
 if (O/'CURRENT_PRODUCTION_REBASED_SHAPES.json').exists():shapes.update({s:v['native_boxes'] for s,v in json.loads((O/'CURRENT_PRODUCTION_REBASED_SHAPES.json').read_text('utf8'))['rows'].items()})
 wanted={tuple(c['position']):c for c in doc['cells']};bysection=collections.defaultdict(list);selected={}
 for p in wanted:bysection[p[0]//16,p[2]//16,p[1]//16].append(p);selected.setdefault((p[0]//16,p[2]//16),set()).add(p[1]//16)
 regions={dimension_dir(W,'projectseele:geofront')/'region'/f'r.{cx//32}.{cz//32}.mca' for cx,cz in selected};before={str(p):sha(p) for p in regions};current={}
 for cx,cz,sy,palette,indices in iter_selected_sections(W,'projectseele:geofront',selected):
  for p in bysection[cx,cz,sy]:current[p]=palette[int(indices[((p[1]&15)<<8)|((p[2]&15)<<4)|(p[0]&15)])]
 assert current.keys()==wanted.keys();assert before=={str(p):sha(p) for p in regions},'World changed during bounded reread'
 interface=json.loads((G/'CURRENT_TYPED_GATE_INTERFACE.json').read_text('utf8'));masks=collections.defaultdict(dict)
 for gate in interface['gates']:
  source=G/gate['collision_steps']['cells_file'];assert sha(source)==gate['collision_steps']['sha256'];steps=json.loads(gzip.decompress(source.read_bytes()))
  for step in steps:
   for c in step:
    if c['closed']!=c['open']:masks[tuple(c['position'])][gate['resource']]=dict(closed=c['closed'],open=c['open'])
 lo=tuple(min(p[i] for p in wanted) for i in range(3));hi=tuple(max(p[i] for p in wanted) for i in range(3));bes={p:t.snbt() for p,t in iter_block_entities(W,'projectseele:geofront',lo,hi)}
 rows=[];unknown=[]
 for p,c in wanted.items():
  state=current[p];local=shapes.get(state,[] if state in AIR else None)
  if local is None:unknown.append(dict(position=p,state=state));local=[]
  rows.append(dict(position=p,original_scan_state=c['state'],state=state,native_boxes=[[b[i]+p[i%3] for i in range(6)] for b in local],already_air=state in AIR,installed_state_changed=state!=c['state'],typed_gate_dynamic_masks=masks.get(p,{}),original_retractable_bridge=state.startswith('projectseele:entry_plug_bridge_'),block_entity_snbt=bes.get(p),motion_witnesses=c['motions']))
 result=dict(world_written=False,game_started=False,source_static_cells_sha256=sha(O/'EXACT_PRELAUNCH_STATIC_CELLS_FOR_ROOT.json'),typed_interface_sha256=sha(G/'CURRENT_TYPED_GATE_INTERFACE.json'),source_region_sha256=before,native_shapes_sha256=sha(W/'native_collision_shapes.json'),cells=rows,unknown_shapes=unknown)
 (O/'CURRENT_PRELAUNCH_CELLS_REBASED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print(dict(cells=len(rows),already_air=sum(r['already_air'] for r in rows),typed_mask=sum(bool(r['typed_gate_dynamic_masks']) for r in rows),bridge=sum(r['original_retractable_bridge'] for r in rows),BE=sum(r['block_entity_snbt'] is not None for r in rows),unknown=len(unknown)))
if __name__=='__main__':main()
