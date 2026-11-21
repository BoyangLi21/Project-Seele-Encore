"""Exact gate-cell decisions for Root; no edits or blanket removal authority."""
from pathlib import Path
import json,collections,hashlib
R=Path(__file__).resolve().parents[1];O=R/'.Codex/map_complete_20261013/route_audit/gate14_world_current';S=O/'GATE14_CURRENT_WORLD_HITS.json'
def main():
 data=json.loads(S.read_text('utf8'));groups=[]
 for gate in data['gates']:
  be={tuple(c['position']):c['snbt'] for c in gate['block_entities']};cells={}
  for hit in gate['part_cell_hits']:
   if not hit['strict_interior_hit']:continue
   p=tuple(hit['position']);row=cells.setdefault(p,dict(position=p,state=hit['state'],native_boxes=hit['native_boxes'],declared_bearing=hit.get('declared_bearing'),foreign_proxy_resources=hit['foreign_proxy_resources'],block_entity_snbt=be.get(p),parts=[]));row['parts'].append({k:hit[k] for k in ['part','moving','actual_source_phase_intervals']})
  for row in cells.values():row['required_root_hold']=bool(row['declared_bearing'] or row['foreign_proxy_resources'] or row['block_entity_snbt']);row['front_floor_seal_geometry_replaced_pending_new_current']=any('/bottom_seal/' in p['part'] for p in row['parts'])
  c=list(cells.values());groups.append(dict(resource=gate['resource'],cells=len(c),bounds=[[min(v['position'][i] for v in c) for i in range(3)],[max(v['position'][i] for v in c) for i in range(3)]] if c else None,hold_cells=sum(v['required_root_hold'] for v in c),real_moving_obstruction_cells=sum(any(p['moving'] for p in v['parts']) for v in c),materials=dict(collections.Counter(v['state'] for v in c)),actual_cells=c))
 result=dict(world_written=False,apply_authorized=False,source_sha256=hashlib.sha256(S.read_bytes()).hexdigest(),interface_sha256=data['interface_sha256'],groups=groups,scope='Exact actual triangle/native-shape interior intersections. Only own leaf proxies excluded. Declared bearings, foreign proxies and all BE are HOLD. Front floor-seal part entries must be replaced by the new 879-mask mesh before Root makes that cavity; unaffected frame/vertical leaves and six rear/three pit/two air entries remain source-specific actual facts.')
 (O/'ROOT_FINITE_GATE14_OBSTRUCTIONS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
 for g in groups:print(g['resource'],g['cells'],'holds',g['hold_cells'],'moving',g['real_moving_obstruction_cells'])
if __name__=='__main__':main()
