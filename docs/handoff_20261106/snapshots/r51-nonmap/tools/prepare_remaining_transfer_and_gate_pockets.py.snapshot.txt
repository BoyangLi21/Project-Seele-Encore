"""Root's single final remaining civil candidate. No WORLD writes or admission flags."""
from pathlib import Path
import json,gzip,hashlib,collections
from prepare_complete_prelaunch_finite_slots import measure,W
from query_blocks import AIR,iter_block_entities
R=Path(__file__).resolve().parents[1];A=R/'.Codex/map_complete_20261013/route_audit';P=A/'prelaunch_world_current';O=A/'prelaunch_slots_candidate';G=A/'wet_floor_expansion_v2/full_throat';F=O/'READY_REMAINING_TRANSFER_AND_GATE_POCKETS.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 interface=G/'CURRENT_TYPED_GATE_INTERFACE.json';assert sha(interface)=='bc521d1dbddb9e1075a0b5a7bedf2da26f509312b9b6839d9835f8296fc9192c';doc=json.loads(interface.read_text('utf8'));gatefile=A/'gate14_final_879/GATE14_CURRENT_WORLD_HITS.json';gates=json.loads(gatefile.read_text('utf8'));assert gates['interface_sha256']==sha(interface)
 protected={};proxies=collections.defaultdict(set)
 for gate in doc['gates']:
  for c in gate['bearing_contacts']:protected.setdefault(tuple(c['candidate_cell']),[]).append(dict(resource=gate['resource'],contact=c))
  path=G/gate['collision_steps']['cells_file'];assert sha(path)==gate['collision_steps']['sha256']
  for step in json.loads(gzip.decompress(path.read_bytes())):
   for cell in step:proxies[tuple(cell['position'])].add(gate['resource'])
 original=json.loads((P/'CURRENT_PRELAUNCH_STATIC_STEEL_CLASSIFICATION.json').read_text('utf8'));by={tuple(c['position']):c for c in original['cells']};remaining=json.loads((P/'REMAINING_171_EXACT_LOCAL_STRUCTURES.json').read_text('utf8'));wet=json.loads((P/'ROOT_AUTHORIZED_WET_THROAT_AND_R49_STAIRS.json').read_text('utf8'));old=json.loads((O/'READY_NON_WET_FINITE_SLOTS.json').read_text('utf8'));installed_floors={tuple(c['position']) for c in old['changes'] if c['after']!='minecraft:air'};oldbeds=installed_floors|{tuple(c['position']) for c in old['retained_existing_solid_floor']}|{tuple(c['position']) for c in old['original_unchanged_bottoms']};oldbedcols=collections.defaultdict(set)
 for x,y,z in oldbeds:oldbedcols[x,z].add(y)
 cuts={};exclusions=[];holds=[];taskcounts=collections.Counter()
 def add(p,state,source,parts=None):
  if p in protected or p in proxies or by.get(p,{}).get('original_retractable_bridge'):
   exclusions.append(dict(position=p,source=source,actual_gate_bearing=protected.get(p),dynamic_proxy_resources=sorted(proxies.get(p,set())),original_bridge=by.get(p,{}).get('original_retractable_bridge',False)));return
  row=cuts.setdefault(p,dict(position=p,expected=state,after='minecraft:air',sources=[],actual_collision_parts=[]))
  if row['expected']!=state:holds.append(dict(position=p,reason='source_state_disagreement',first=row['expected'],second=state))
  if source not in row['sources']:row['sources'].append(source)
  for part in parts or []:
   if part not in row['actual_collision_parts']:row['actual_collision_parts'].append(part)
 for c in remaining['cells']:
  p=tuple(c['position']);kind='original_ramp_top_black_row_87' if p[1]==-1031 else 'original_low_trench_strip_84';taskcounts[kind]+=1;add(p,c['state'],kind,[m['part'] for m in c['motion_witnesses'] if m['family']!='PLUG'])
 for c in wet['wet_throat_candidates']:
  if c['position'][1]>=-1063:continue
  p=tuple(c['position']);taskcounts['wet_throat_lower_201']+=1;add(p,c['state'],'wet_throat_lower_201',[m['part'] for m in c['motion_witnesses'] if m['family']!='PLUG'])
 for c in original['cells']:
  if not c['actual_finite_native_face_contacts']:continue
  p=tuple(c['position']);taskcounts['original_zero_area_line_contacts_6']+=1;add(p,c['state'],'original_zero_area_line_contacts_6',[m['part'] for m in c['motion_witnesses'] if m['family']!='PLUG'])
 gate_summary=[]
 for gate in gates['gates']:
  points=set()
  for c in gate['part_cell_hits']:
   if not c['strict_interior_hit']:continue
   p=tuple(c['position']);points.add(p);add(p,c['state'],'actual_gate/'+gate['resource'],[dict(part=c['part'],moving=c['moving'],phase_intervals=c['actual_source_phase_intervals'])])
  gate_summary.append(dict(resource=gate['resource'],actual_interior_cells=len(points)))
 assert dict(taskcounts)=={'original_ramp_top_black_row_87':87,'original_low_trench_strip_84':84,'wet_throat_lower_201':201,'original_zero_area_line_contacts_6':6}
 # Only the lower front mechanical cavity is given a new bounded two-layer bed.
 # Six rear vertical wall recesses keep their existing carrier trench floor;
 # service-pit frame recesses keep Root's already-installed complete dry pit.
 lowcols={(x,z) for (x,y,z),r in cuts.items() if y<=-1064 and (any(s in r['sources'] for s in ['original_low_trench_strip_84','wet_throat_lower_201']) or any(s.startswith('actual_gate/bay_') and s.endswith('_front') for s in r['sources']))}
 beds={(x,y,z) for x,z in lowcols for y in (-1071,-1070)};bed_provenance=[]
 for p,row in cuts.items():
  x,y,z=p
  if not any(s in row['sources'] for s in ['original_ramp_top_black_row_87','original_zero_area_line_contacts_6']):continue
  ys=sorted(oldbedcols.get((x,z),[]));pair=None
  for bottom in ys:
   if bottom+1 in ys and bottom+1<y:pair=[bottom,bottom+1];break
  if pair is None:pair=[y-2,y-1]
  beds.update((x,yy,z) for yy in pair);bed_provenance.append(dict(column=[x,z],retained_or_proposed_floor_y=pair,root_existing_verified_bed=bool(ys)))
 points=set(cuts)|beds
 for p in list(beds):
  for dx,dy,dz in ((1,0,0),(-1,0,0),(0,-1,0),(0,0,1),(0,0,-1)):points.add((p[0]+dx,p[1]+dy,p[2]+dz))
 actual=measure(points);lo=tuple(min(p[i] for p in points) for i in range(3));hi=tuple(max(p[i] for p in points) for i in range(3));be={p:t.snbt() for p,t in iter_block_entities(W,'projectseele:geofront',lo,hi)};shapes=json.loads((W/'native_collision_shapes.json').read_text('utf8'));changes=[];already=[];floors=[];retained=[]
 for p,r in sorted(cuts.items()):
  if p in beds:holds.append(dict(position=p,reason='actual_gate_or_carrier_hits_planned_bed'));continue
  if p in be:holds.append(dict(position=p,reason='actual_BE',snbt=be[p]));continue
  if actual[p] in AIR:already.append(p);continue
  if actual[p]!=r['expected']:holds.append(dict(position=p,reason='actual_before_changed',expected=r['expected'],actual=actual[p]));continue
  changes.append(dict(position=p,before=actual[p],after='minecraft:air',operation='root_final_finite_clearance',sources=r['sources'],actual_collision_parts=r['actual_collision_parts'],replaces_previous_applied_bottom=p in installed_floors))
 for p in sorted(beds):
  state=actual[p]
  if p in be:holds.append(dict(position=p,reason='BE_at_two_layer_bed',snbt=be[p]));continue
  if p in protected or p in proxies:holds.append(dict(position=p,reason='bed_reaches_gate_support_or_proxy'));continue
  if shapes.get(state)==[[0.,0.,0.,1.,1.,1.]]:retained.append(dict(position=p,state=state));continue
  if state in AIR:floors.append(dict(position=p,before=state,after='projectseele:nerv_structural_panel',operation='root_final_two_layer_mechanical_bottom'));continue
  holds.append(dict(position=p,reason='unknown_or_partial_bed',state=state))
 new_floor_set={tuple(c['position']) for c in floors};after=dict(actual);after.update({tuple(c['position']):c['after'] for c in changes+floors});components=[];pending=set(beds)
 while pending:
  first=pending.pop();todo=[first];part={first};contacts=set()
  while todo:
   p=todo.pop()
   for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
    q=(p[0]+dx,p[1]+dy,p[2]+dz)
    if q in pending:pending.remove(q);part.add(q);todo.append(q)
    elif q not in beds and q not in cuts and shapes.get(after.get(q,''))==[[0.,0.,0.,1.,1.,1.]]:contacts.add(q)
  components.append(dict(cells=len(part),bounds=[[min(p[i] for p in part) for i in range(3)],[max(p[i] for p in part) for i in range(3)]],existing_solid_contact_count=len(contacts),existing_solid_contacts=sorted(contacts)))
  if not contacts:holds.append(dict(reason='bed_component_disconnected',component_bounds=components[-1]['bounds']))
 pending_checks=[];bottom_verification={}
 if floors:
  steelpath=O/'final_bottom_checks/BOTTOM_FIXED_STEEL.json'
  if not steelpath.exists():pending_checks=['Only newly placed bottom cubes vs current actual fixed steel; body and gate conservative envelopes can prove exact separation.']
  else:
   steel=json.loads(steelpath.read_text('utf8'));assert {tuple(c['position']) for c in steel['cells']}==new_floor_set
   assert not any(c['actual_fixed_steel_interior_members'] or c['actual_finite_native_face_contacts'] for c in steel['cells'])
   gateenv=A/'gate14_final_879/GATE14_CURRENT_ENVELOPES.json';ge=json.loads(gateenv.read_text('utf8'));assert ge['interface_sha256']==sha(interface);boxes=[p['bounds'] for g in ge['gates'] for p in g['parts']]
   assert not any(all(p[i]+1>b[i] and p[i]<b[i+3] for i in range(3)) for p in new_floor_set for b in boxes)
   bodyenv=P/'CURRENT_PRELAUNCH_PART_ENVELOPES.json';body=json.loads(bodyenv.read_text('utf8'));bodymin=min(p['bounds'][1] for g in body['legs'] for p in g['parts'] if p['family']!='PLUG')
   plugenv=A/'seated_plug_prelaunch/TRUE_PLUG_ENVELOPES.json';plug=json.loads(plugenv.read_text('utf8'));plugmin=min(p['bounds'][1] for g in plug['legs'] for p in g['parts']);floor_top=max(p[1]+1 for p in new_floor_set);assert floor_top<bodymin and floor_top<plugmin
   bottom_verification=dict(new_floor_cells=len(new_floor_set),actual_fixed_steel_interior_hits=0,actual_finite_fixed_native_face_contacts=0,actual_all_gate_motion_part_envelope_overlaps=0,floor_top_y=floor_top,current_body_carrier_head_conservative_min_y=bodymin,current_true_seated_plug_conservative_min_y=plugmin,positive_world_y_separation_to_complete_prelaunch=True,source_sha256={str(p):sha(p) for p in [steelpath,gateenv,bodyenv,plugenv]})
 rows=[dict(position=c['position'],state=c['after'],native_boxes=[[c['position'][0],c['position'][1],c['position'][2],c['position'][0]+1,c['position'][1]+1,c['position'][2]+1]]) for c in floors];(O/'FINAL_NEW_BOTTOM_NATIVE_SHAPES.json').write_text(json.dumps(dict(world_written=False,unknown_shapes=[],cells=rows),indent=2),'utf8')
 report=dict(world_written=False,game_started=False,root_apply_ready=not holds and not pending_checks,dimension='projectseele:geofront',directory_fingerprint=doc['directory_sha256'],interface_sha256=sha(interface),changes=changes+floors,finite_cut_changes=len(changes),new_two_layer_bottom_changes=len(floors),retained_existing_two_layer_bottom_cells=retained,root_approved_task_counts=dict(taskcounts),gate_summary=gate_summary,protected_exclusions=exclusions,actual_gate_support_cells=sorted(protected),already_air_deduplicated=already,prior_applied_bottom_replaced_by_lower_current_seal_bed=[c['position'] for c in changes if c['replaces_previous_applied_bottom']],bed_provenance=bed_provenance,bed_components=components,holds=holds,pending_checks=pending_checks,bottom_verification=bottom_verification,minimum_front_mechanism_y=-1068.26,lower_front_bed_top_y=-1069,current_all_prelaunch_nonplug_conservative_min_y=-1066.9814895001612,current_true_plug_conservative_min_y=-1019.7330617750102,source_sha256={str(p):sha(p) for p in [interface,gatefile,P/'REMAINING_171_EXACT_LOCAL_STRUCTURES.json',P/'ROOT_AUTHORIZED_WET_THROAT_AND_R49_STAIRS.json',O/'six_existing_faces/EXACT_SIX_NEAR_FACES.json',O/'READY_NON_WET_FINITE_SLOTS.json',Path(__file__)]},preserved='All original fixed steel meshes, typed dynamic masks, actual native support cells, personnel bridges, original actors and state; service-pit frame replaces only its exact intersected floor cubes, with Root installed dry pit below unchanged.')
 F.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print({k:report[k] for k in ['root_apply_ready','finite_cut_changes','new_two_layer_bottom_changes']});print('retained beds',len(retained),'prior 90 revisits',len(report['prior_applied_bottom_replaced_by_lower_current_seal_bed']),'holds',len(holds),'pending',len(pending_checks),'protected exclusions',len(exclusions))
if __name__=='__main__':main()
