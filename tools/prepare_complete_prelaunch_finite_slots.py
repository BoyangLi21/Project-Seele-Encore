"""Root-authorized finite clearances and two-layer bottoms, candidate only; never writes WORLD."""
from pathlib import Path
import json,hashlib,collections
import numpy as np
from query_blocks import read_box,iter_selected_sections,iter_block_entities,dimension_dir,AIR
R=Path(__file__).resolve().parents[1];W=Path('D:/eva/artifacts/map_complete_20261013/WORLD');A=R/'.Codex/map_complete_20261013/route_audit';P=A/'prelaunch_world_current';O=A/'prelaunch_slots_candidate';O.mkdir(exist_ok=True)
ROLES={'bank/original_deck_ring','bank/original_foundation','bank/original_end_reinforcement','bank/original_trench_floor','ramp/sealed_common_underside','ramp/recessed_trench_floor','ramp/one_cell_edge_strip','ramp/trench_side_lip','ramp/authored_transport_negative'}
NATURAL={'minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]','minecraft:granite','minecraft:diorite','minecraft:andesite','minecraft:tuff','minecraft:calcite'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def measure(points):
 selected={};by=collections.defaultdict(list)
 for p in points:selected.setdefault((p[0]//16,p[2]//16),set()).add(p[1]//16);by[p[0]//16,p[2]//16,p[1]//16].append(p)
 result={}
 for cx,cz,sy,palette,indices in iter_selected_sections(W,'projectseele:geofront',selected):
  for p in by[cx,cz,sy]:result[p]=palette[int(indices[((p[1]&15)<<8)|((p[2]&15)<<4)|(p[0]&15)])]
 assert result.keys()==set(points);return result
def main():
 attribution=json.loads((P/'PRELAUNCH_AUTHORED_COMPONENT_GROUPS.json').read_text('utf8'));current=json.loads((P/'CURRENT_PRELAUNCH_STATIC_STEEL_CLASSIFICATION.json').read_text('utf8'));rows={tuple(c['position']):c for c in current['cells']};valid=json.loads((P/'VALID_EVA_CARRIER_HEAD_STATIC_CELLS.json').read_text('utf8'));valid_points={tuple(c['position']) for c in valid['cells']};head=json.loads((A/'bank_world_current/EXACT_STATIC_HIT_CELLS_FOR_ROOT.json').read_text('utf8'));head_points={tuple(c['position']) for c in head['actual_cells']}
 protected={p for p,c in rows.items() if c['typed_gate_dynamic_masks'] or c['original_retractable_bridge'] or c['actual_finite_native_face_contacts'] or c['explicit_service_wall_bearings'] or c.get('block_entity_snbt')}
 cuts={};holds=[]
 for c in attribution['cells']:
  p=tuple(c['position']);role=c['group_role'];rock=role.startswith('SOURCE_STATE_CHANGED_OR_NOT_COPIED/') and c['state'] in NATURAL
  if role not in ROLES and not rock:continue
  if p in protected:continue
  assert p in valid_points and any(m['family']!='PLUG' for m in c['motion_witnesses'])
  cuts[p]=dict(role=role,original_attribution=c['actual_original_block_index'],source_refs=c['authored_operations'],expected=c['state'])
 # Already-applied eighteen authorized head slots remain clearance, including
 # below the originally horizontal prelaunch head. Do not refill them as a floor.
 cut_columns={}
 for x,y,z in cuts:cut_columns[x,z]=min(y,cut_columns.get((x,z),y))
 for x,y,z in head_points:
  if (x,z) in cut_columns:cut_columns[x,z]=min(y,cut_columns[x,z])
 bottoms={(x,y-d,z) for (x,z),y in cut_columns.items() for d in (1,2)}
 points=set(cuts)|bottoms
 for p in list(bottoms):
  for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):points.add((p[0]+dx,p[1]+dy,p[2]+dz))
 actual=measure(points);lo=tuple(min(p[i] for p in points) for i in range(3));hi=tuple(max(p[i] for p in points) for i in range(3));bes={p:t.snbt() for p,t in iter_block_entities(W,'projectseele:geofront',lo,hi)};shapes=json.loads((W/'native_collision_shapes.json').read_text('utf8'));changes=[];owned=[]
 for p,c in cuts.items():
  state=actual[p]
  if p in bes:holds.append(dict(position=p,reason='actual_block_entity_in_authorized_cut',nbt=bes[p]));continue
  if state!=c['expected'] and state not in AIR:holds.append(dict(position=p,reason='exact_before_changed',expected=c['expected'],actual=state));continue
  owned.append(dict(position=p,before=state,after='minecraft:air',operation='authorized_finite_swept_clearance',role=c['role']))
  if state not in AIR:changes.append(owned[-1])
 floors=[];retained=[]
 for p in sorted(bottoms):
  state=actual[p]
  if p in cuts or p in protected or p in head_points or p in valid_points:holds.append(dict(position=p,reason='new_bottom_intersects_protected_or_proved_moving_clearance',actual=state));continue
  if p in bes:holds.append(dict(position=p,reason='actual_block_entity_at_bottom',nbt=bes[p]));continue
  if state in AIR or state in NATURAL:
   floors.append(dict(position=p,before=state,after='projectseele:nerv_structural_panel',operation='root_two_layer_slot_bottom'));continue
  if shapes.get(state)!=[[0.,0.,0.,1.,1.,1.]]:holds.append(dict(position=p,reason='existing_non_full_or_unknown_bottom_retained',actual=state));continue
  retained.append(dict(position=p,state=state,reason='Root keeps existing solid material'))
 # No candidate bottom is applied before independent fixed-steel and actual
 # moving-part checks. Rows use proposed actual full-cube shape only.
 floor_rows=[dict(position=c['position'],state=c['after'],before_state=c['before'],native_boxes=[[c['position'][0],c['position'][1],c['position'][2],c['position'][0]+1,c['position'][1]+1,c['position'][2]+1]]) for c in floors]
 (O/'PROPOSED_BOTTOM_NATIVE_SHAPES.json').write_text(json.dumps(dict(world_written=False,unknown_shapes=[],source_region_sha256={},typed_interface_sha256=current['typed_interface_sha256'],cells=floor_rows),ensure_ascii=False,indent=2),'utf8')
 after={p:s for p,s in actual.items()};after.update({tuple(c['position']):c['after'] for c in changes+floors});floor_set={tuple(c['position']) for c in floors}|{tuple(c['position']) for c in retained};components=[];pending=set(floor_set)
 while pending:
  first=pending.pop();todo=[first];part={first};contacts=set()
  while todo:
   p=todo.pop()
   for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
    q=(p[0]+dx,p[1]+dy,p[2]+dz)
    if q in pending:pending.remove(q);part.add(q);todo.append(q)
    elif q not in floor_set and q not in cuts and shapes.get(after.get(q,''))==[[0.,0.,0.,1.,1.,1.]]:contacts.add(q)
  components.append(dict(cells=len(part),bounds=[[min(p[i] for p in part) for i in range(3)],[max(p[i] for p in part) for i in range(3)]],unchanged_full_cube_neighbor_contacts=sorted(contacts)))
  if not contacts:holds.append(dict(component_bounds=components[-1]['bounds'],reason='new_bottom_component_has_no_measured_existing_solid_connection'))
 report=dict(world_written=False,apply_authorized=False,root_authorized_geometry=True,dimension='projectseele:geofront',cut_cells=len(cuts),cut_changes=len(changes),bottom_columns=len(cut_columns),new_bottom_candidates=len(floors),retained_solid_bottoms=len(retained),holds=holds,cut_changes_rows=changes,bottom_candidate_rows=floors,retained_solid_bottom_rows=retained,bottom_components=components,protected_six_faces=sorted(p for p,c in rows.items() if c['actual_finite_native_face_contacts']),source_sha256={str(p):sha(p) for p in [P/'PRELAUNCH_AUTHORED_COMPONENT_GROUPS.json',P/'VALID_EVA_CARRIER_HEAD_STATIC_CELLS.json',Path(__file__)]},pending=['candidate bottom vs independent current fixed steel','candidate bottom vs actual current swept body/carrier/head','Root applies only verified concrete plan; WORLD untouched'])
 (O/'PREPARED_FINITE_SLOTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print({k:report[k] for k in ('cut_cells','cut_changes','bottom_columns','new_bottom_candidates','retained_solid_bottoms')});print('holds',len(holds))
if __name__=='__main__':main()
