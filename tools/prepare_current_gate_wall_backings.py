"""Finite original-wall-backed inserts for twelve declared missing gate faces."""
from pathlib import Path
import json,gzip,hashlib,collections
from prepare_complete_prelaunch_finite_slots import measure,W
from query_blocks import AIR,iter_block_entities
R=Path(__file__).resolve().parents[1];A=R/'.Codex/map_complete_20261013/route_audit';O=A/'final_gate_native_readback';I=A/'wet_floor_expansion_v2/full_throat/CURRENT_TYPED_GATE_INTERFACE.json';U=R/'.Codex/map_complete_20261013/requirements_audit/typed_units_current/ROOT_TYPED_UNITS_V3_FULL_FOUNDATION_CANDIDATE.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 doc=json.loads((O/'CURRENT354_SUPPORTS_AND_CLOSED_READBACK.json').read_text('utf8'));assert len(doc['missing_actual_native_faces'])==12;points=set();anchors=[];components=[]
 for dx in (0,-42,-84):
  right={(89+dx,-1068,z) for z in (306,307,308)};ra=(89+dx,-1068,309);left={(x+dx,-1068,305) for x in (53,54,55)}|{(55+dx,-1068,z) for z in (306,307)};la=(52+dx,-1068,305)
  if dx==-84:left.add((-32,-1068,305));la=(-33,-1068,305)
  points|=right|left;anchors.extend([ra,la]);components.extend([dict(positions=sorted(right),anchor=ra),dict(positions=sorted(left),anchor=la)])
 assert len(points)==25
 actual=measure(points|set(anchors));lo=tuple(min(p[i] for p in points) for i in range(3));hi=tuple(max(p[i] for p in points) for i in range(3));be={p:t.snbt() for p,t in iter_block_entities(W,'projectseele:geofront',lo,hi)};shapes=json.loads((W/'native_collision_shapes.json').read_text('utf8'));holds=[];changes=[]
 for p in sorted(points):
  if p in be:holds.append(dict(position=p,reason='actual_BE',snbt=be[p]));continue
  if actual[p] not in AIR:holds.append(dict(position=p,reason='source_not_air',actual=actual[p]));continue
  changes.append(dict(position=p,before=actual[p],after='projectseele:nerv_structural_panel'))
 for p in anchors:
  if shapes.get(actual[p])!=[[0.,0.,0.,1.,1.,1.]]:holds.append(dict(position=p,reason='authored_backing_not_actual_full_cube',actual=actual[p]))
 envelopes=json.loads((A/'prelaunch_world_current/CURRENT_PRELAUNCH_PART_ENVELOPES.json').read_text('utf8'));bodymin=min(v['bounds'][1] for g in envelopes['legs'] for v in g['parts'] if v['family']!='PLUG');assert bodymin>max(p[1]+1 for p in points)
 lower=json.loads((A/'lower_current/CURRENT_FACTORY_CONTRACT.json').read_text('utf8'));lowermin=min(v['canonical_envelope'][2] for v in lower['intervals']);assert lowermin>max(p[2]+1 for p in points)
 rows=[dict(position=p,state='projectseele:nerv_structural_panel',native_boxes=[[p[0],p[1],p[2],p[0]+1,p[1]+1,p[2]+1]],own_dynamic_proxy=False,foreign_proxy_resources=[],declared_bearing=None) for p in sorted(points)]
 target=A/'prelaunch_slots_candidate/wall_backing_checks';target.mkdir(exist_ok=True);(target/'PROPOSED_BOTTOM_NATIVE_SHAPES.json').write_text(json.dumps(dict(world_written=False,unknown_shapes=[],cells=rows),indent=2),'utf8');gates=json.loads(I.read_text('utf8'));selected=lambda n:n.startswith('bay_') or n.startswith(('bank_1_rear','bank_2_rear','remote_airshaft_'));gdata=dict(region_sha256={},native_shapes_sha256='proposed_actual_full_structural_cubes',gates=[dict(resource=g['resource'],cells=rows,unknown_shapes=[],block_entities=[]) for g in gates['gates'] if selected(g['resource'])]);check=O/'wall_candidate';check.mkdir(exist_ok=True);(check/'GATE14_CURRENT_NATIVE_CANDIDATES.json').write_text(json.dumps(gdata),'utf8')
 patch=[dict(resource=r['resource'],position=r['position'],before_expected=r['expected'],after_expected=r['actual'],world_block_change=False,actual_nine_point_face_supported=True) for r in doc['material_state_differences'] if r['native_face_supported']]
 report=dict(world_written=False,root_apply_ready=False,holds=holds,changes=changes,reversible_inverse=[dict(position=c['position'],before=c['after'],after=c['before']) for c in changes],components_with_existing_whole_block_anchor=[dict(c,anchor_state=actual[tuple(c['anchor'])]) for c in components],missing_face_positions=[v['position'] for v in doc['missing_actual_native_faces']],native_face_footprints_use_adjacent_blocks_when_the_contact_straddles_a_grid_line=True,material_expectation_only_patches=patch,carrier_prelaunch_min_y=bodymin,new_block_max_y=max(p[1]+1 for p in points),lower_full_stroke_min_z=lowermin,new_block_max_z=max(p[2]+1 for p in points),pending=['25 new cubes against current conservative all-gate motion envelopes and original independent steel'],source_sha256={str(p):sha(p) for p in [I,O/'CURRENT354_SUPPORTS_AND_CLOSED_READBACK.json',Path(__file__)]});(O/'FINITE_TWELVE_WALL_BACKINGS_CANDIDATE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
 # All ten states are checked explicitly; a one-state deployed match cannot
 # substitute for retaining the original R49 stairs through retraction.
 units=json.loads(U.read_text('utf8'));stair_source=json.loads((A/'prelaunch_world_current/ROOT_AUTHORIZED_WET_THROAT_AND_R49_STAIRS.json').read_text('utf8'));stairs={tuple(c['position']):c for c in stair_source['r49_original_retractable_stairs']};actual_stairs=measure(stairs);r=[];seen=set()
 for u in units['units']:
  ref=u['bridge_states'];file=U.parent/ref['cells_file'];assert sha(file)==ref['sha256'];states=json.loads(gzip.decompress(file.read_bytes()));assert len(states)==10;maps=[{tuple(c['position']):c['state'] for c in s} for s in states]
  for p in stairs:
   if p not in maps[0]:continue
   assert all(p in m for m in maps);seen.add(p);r.append(dict(variant=u['variant'],position=p,states_0_through_9=[m[p] for m in maps],current_native_state=actual_stairs[p],current_matches_states=[i for i,m in enumerate(maps) if m[p]==actual_stairs[p]],table_sha256=sha(file)))
 assert seen==stairs.keys() and len(r)==12
 (O/'CURRENT_R49_TWELVE_STAIRS_TEN_STATES.json').write_text(json.dumps(dict(world_written=False,units_candidate=str(U),units_sha256=sha(U),original_high_stair_cells=12,state_count=10,all_twelve_in_every_state=True,rows=r),ensure_ascii=False,indent=2),'utf8');print('wall changes',len(changes),'holds',len(holds),'material-only patches',len(patch),'12stairs all10 true')
if __name__=='__main__':main()
