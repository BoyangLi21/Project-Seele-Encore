"""Prepare bounded bottom alternatives for Root's finite slots; never writes WORLD."""
from pathlib import Path
import json,sys,collections
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_complete_prelaunch_finite_slots import measure,W
from query_blocks import AIR,iter_block_entities
R=Path(__file__).resolve().parents[1];A=R/'.Codex/map_complete_20261013/route_audit';O=A/'prelaunch_slots_candidate';V=O/'v2';V.mkdir(exist_ok=True)
def main():
 plan=json.loads((O/'PREPARED_FINITE_SLOTS.json').read_text('utf8'));body=json.loads((O/'BOTTOM_CURRENT_BODY.json').read_text('utf8'));steel=json.loads((O/'BOTTOM_FIXED_STEEL.json').read_text('utf8'))
 bad={tuple(c['position']) for l in body['legs'] for c in l['part_cell_hits']}|{tuple(c['position']) for c in steel['cells'] if c['actual_fixed_steel_interior_members']};columns={(x,z) for x,y,z in bad}
 cuts={tuple(c['position']):c for c in plan['cut_changes_rows']};wet=json.loads((A/'prelaunch_world_current/ROOT_AUTHORIZED_WET_THROAT_AND_R49_STAIRS.json').read_text('utf8'));added=[]
 for c in wet['wet_throat_candidates']:
  x,y,z=c['position']
  if y>=-1063:continue
  assert not c['actual_finite_native_face_contacts'] and not c['explicit_service_wall_bearings'] and not c['typed_gate_dynamic_masks']
  p=(x,y,z);row=dict(position=p,before=c['state'],after='minecraft:air',operation='root_wet_throat_lower_mechanical_cavity',role='wet_throat_lower_fixed_void',original_source_position=c['actual_original_block_index'],fixed_steel_retained=c['actual_fixed_steel_interior_members']);cuts[p]=row;added.append(p)
 lowest={}
 for x,y,z in cuts:lowest[x,z]=min(lowest.get((x,z),y),y)
 # Keep the already-installed head slots below a floor from being filled back.
 for c in json.loads((A/'bank_world_current/EXACT_STATIC_HIT_CELLS_FOR_ROOT.json').read_text('utf8'))['actual_cells']:
  x,y,z=c['position']
  if (x,z) in lowest:lowest[x,z]=min(lowest[x,z],y)
 points=set()
 for x,z in columns:
  points.update((x,lowest[x,z]-d,z) for d in range(1,13))
 wetcols={(x,z) for x,y,z in added}
 for x,z in wetcols:points.update((x,lowest[x,z]-d,z) for d in range(1,5))
 for c in plan['bottom_candidate_rows']:
  p=tuple(c['position'])
  if (p[0],p[2]) not in columns:points.add(p)
 actual=measure(points|set(cuts));lo=tuple(min(p[i] for p in points) for i in range(3));hi=tuple(max(p[i] for p in points) for i in range(3));be={p:t.snbt() for p,t in iter_block_entities(W,'projectseele:geofront',lo,hi)}
 rows=[dict(position=p,state='projectseele:nerv_structural_panel',before_state=actual[p],native_boxes=[[p[0],p[1],p[2],p[0]+1,p[1]+1,p[2]+1]]) for p in sorted(points)]
 (V/'PROPOSED_BOTTOM_NATIVE_SHAPES.json').write_text(json.dumps(dict(world_written=False,unknown_shapes=[],source_region_sha256={},typed_interface_sha256=steel.get('typed_interface_sha256'),cells=rows),ensure_ascii=False,indent=2),'utf8')
 (V/'BOTTOM_ALTERNATIVES.json').write_text(json.dumps(dict(world_written=False,bad_previous_floor_cells=sorted(bad),revise_columns=sorted(columns),new_wet_columns=sorted(wetcols),lowest_cut_by_column=[dict(x=x,z=z,y=y) for (x,z),y in sorted(lowest.items())],cut_changes_rows=list(cuts.values()),current_states=[dict(position=p,state=s) for p,s in actual.items()],block_entities=[dict(position=p,snbt=t) for p,t in be.items()],current_before_mismatches=[dict(position=p,expected=c['before'],actual=actual[p]) for p,c in cuts.items() if actual[p]!=c['before'] and actual[p] not in AIR],candidate_depths_per_old_conflict_column=12),ensure_ascii=False,indent=2),'utf8')
 print('original cuts',plan['cut_changes'],'added lower wet',len(added),'total cuts',len(cuts),'floor candidate cubes',len(points),'affected columns',len(columns),'wetcolumns',len(wetcols),'blockentities',len(be),flush=True)
if __name__=='__main__':main()
