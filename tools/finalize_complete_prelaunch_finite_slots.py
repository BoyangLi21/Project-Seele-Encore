"""Finalize only independently checked slot floors, with exact before values; no WORLD write."""
from pathlib import Path
import json,collections
from prepare_complete_prelaunch_finite_slots import measure,W,NATURAL
from query_blocks import AIR,iter_block_entities
R=Path(__file__).resolve().parents[1];A=R/'.Codex/map_complete_20261013/route_audit';O=A/'prelaunch_slots_candidate';V=O/'v2'
def main():
 old=json.loads((O/'PREPARED_FINITE_SLOTS.json').read_text('utf8'));alt=json.loads((V/'BOTTOM_ALTERNATIVES.json').read_text('utf8'));b=json.loads((V/'BOTTOM_CURRENT_BODY.json').read_text('utf8'));s=json.loads((V/'BOTTOM_FIXED_STEEL.json').read_text('utf8'));g=json.loads((V/'gates/GATE14_CURRENT_WORLD_HITS.json').read_text('utf8'))
 blocked={tuple(c['position']) for l in b['legs'] for c in l['part_cell_hits']}|{tuple(c['position']) for c in s['cells'] if c['actual_fixed_steel_interior_members'] or c['actual_finite_native_face_contacts']}|{tuple(c['position']) for l in g['gates'] for c in l['part_cell_hits']}
 known={tuple(c['position']) for c in s['cells']};lowest={(c['x'],c['z']):c['y'] for c in alt['lowest_cut_by_column']};cols={tuple(c) for c in alt['revise_columns']};wetcols={tuple(c) for c in alt['new_wet_columns']};floors={tuple(c['position']) for c in old['bottom_candidate_rows'] if (c['position'][0],c['position'][2]) not in cols};shifts=[];holds=[]
 for x,z in sorted(cols):
  y=lowest[x,z];chosen=None
  for d in range(1,12):
   pair={(x,y-d,z),(x,y-d-1,z)}
   if pair<=known and not pair&blocked:chosen=pair;shifts.append(dict(column=[x,z],previous_cut_y=y,top_floor_y=y-d,additional_depth=d-1));break
  if chosen is None:holds.append(dict(column=[x,z],reason='bounded_12m_floor_alternatives_not_clear'));continue
  floors|=chosen
 assert not floors&blocked
 cuts={tuple(c['position']):c for c in old['cut_changes_rows']};points=set(cuts)|floors
 for p in floors:
  for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):points.add((p[0]+dx,p[1]+dy,p[2]+dz))
 actual=measure(points);lo=tuple(min(p[i] for p in points) for i in range(3));hi=tuple(max(p[i] for p in points) for i in range(3));bes={p:t.snbt() for p,t in iter_block_entities(W,'projectseele:geofront',lo,hi)};shape=json.loads((W/'native_collision_shapes.json').read_text('utf8'));changes=[];retained=[]
 for p,c in cuts.items():
  if actual[p]!=c['before'] and actual[p] not in AIR:holds.append(dict(position=p,reason='cut_before_changed',expected=c['before'],actual=actual[p]));continue
  if p in bes:holds.append(dict(position=p,reason='cut_BE',snbt=bes[p]));continue
  if actual[p] not in AIR:changes.append(dict(c,before=actual[p]))
 for p in sorted(floors):
  state=actual[p]
  if p in bes:holds.append(dict(position=p,reason='floor_BE',snbt=bes[p]));continue
  if state in AIR or state in NATURAL:changes.append(dict(position=p,before=state,after='projectseele:nerv_structural_panel',operation='verified_two_layer_slot_bottom'))
  elif shape.get(state)==[[0.,0.,0.,1.,1.,1.]]:retained.append(dict(position=p,state=state))
  else:holds.append(dict(position=p,reason='unknown_or_partial_floor',state=state))
 # Connection proof is applied to each newly placed connected floor component,
 # retaining the actual current solid material for all pre-existing bottoms.
 after=dict(actual);after.update({tuple(c['position']):c['after'] for c in changes});full={p for p in floors};pending=set(full);components=[]
 while pending:
  first=pending.pop();todo=[first];part={first};contacts=set()
  while todo:
   p=todo.pop()
   for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
    q=(p[0]+dx,p[1]+dy,p[2]+dz)
    if q in pending:pending.remove(q);part.add(q);todo.append(q)
    elif q not in full and q not in cuts and shape.get(after.get(q,''))==[[0.,0.,0.,1.,1.,1.]]:contacts.add(q)
  row=dict(cells=len(part),bounds=[[min(p[i] for p in part) for i in range(3)],[max(p[i] for p in part) for i in range(3)]],unchanged_solid_contacts=sorted(contacts));components.append(row)
  if not contacts:holds.append(dict(reason='disconnected_lower_floor',component=row))
 report=dict(world_written=False,root_apply_ready=not holds,holds=holds,changes=changes,cut_cells=len(cuts),cut_changes=sum(c['after']=='minecraft:air' for c in changes),new_floor_changes=sum(c['after']!='minecraft:air' for c in changes),new_floor_cells_checked=len(floors),retained_existing_solid_floor=retained,original_unchanged_bottoms=old['retained_solid_bottom_rows'],revised_columns=shifts,unchanged_solid_connections=components,proof_sources=['v2/BOTTOM_CURRENT_BODY.json','v2/BOTTOM_FIXED_STEEL.json','v2/gates/GATE14_CURRENT_WORLD_HITS.json'],pending_separate='201 lower wet throat clearance and its floor must bind the new 879-cell actual front floor seal before installation',protected_six_faces=old['protected_six_faces'])
 (O/'READY_NON_WET_FINITE_SLOTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print({k:report[k] for k in ['root_apply_ready','cut_cells','cut_changes','new_floor_changes','new_floor_cells_checked']});print('holds',len(holds),'floor depth',collections.Counter(c['additional_depth'] for c in shifts))
if __name__=='__main__':main()
