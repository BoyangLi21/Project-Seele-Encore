"""Prepare Root's 201-cell throat cavity and actual new-seal-safe two-layer bed."""
from pathlib import Path
import json,hashlib
from prepare_complete_prelaunch_finite_slots import measure,W,NATURAL
from query_blocks import AIR,iter_block_entities
R=Path(__file__).resolve().parents[1];A=R/'.Codex/map_complete_20261013/route_audit';O=A/'prelaunch_slots_candidate/wet_current';O.mkdir(exist_ok=True);I=A/'wet_floor_expansion_v2/full_throat/CURRENT_TYPED_GATE_INTERFACE.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert sha(I)=='bc521d1dbddb9e1075a0b5a7bedf2da26f509312b9b6839d9835f8296fc9192c'
 wet=json.loads((A/'prelaunch_world_current/ROOT_AUTHORIZED_WET_THROAT_AND_R49_STAIRS.json').read_text('utf8'));cuts={tuple(c['position']):c for c in wet['wet_throat_candidates'] if c['position'][1]<-1063};assert len(cuts)==201
 cols={(x,z) for x,y,z in cuts};floors={(x,y,z) for x,z in cols for y in (-1071,-1070)};points=floors|cuts.keys()
 for p in list(floors):
  for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):points.add((p[0]+dx,p[1]+dy,p[2]+dz))
 actual=measure(points);lo=tuple(min(p[i] for p in points) for i in range(3));hi=tuple(max(p[i] for p in points) for i in range(3));bes={p:t.snbt() for p,t in iter_block_entities(W,'projectseele:geofront',lo,hi)};shape=json.loads((W/'native_collision_shapes.json').read_text('utf8'));changes=[];retained=[];holds=[]
 for p,c in cuts.items():
  assert not c['actual_finite_native_face_contacts'] and not c['explicit_service_wall_bearings'] and not c['typed_gate_dynamic_masks']
  if p in bes:holds.append(dict(position=p,reason='BE_in_cavity',snbt=bes[p]));continue
  if actual[p]!=c['state'] and actual[p] not in AIR:holds.append(dict(position=p,reason='cavity_before_changed',expected=c['state'],actual=actual[p]));continue
  if actual[p] not in AIR:changes.append(dict(position=p,before=actual[p],after='minecraft:air',operation='root_wet_throat_lower_mechanical_cavity',original_source_position=c['actual_original_block_index'],independent_steel_members_preserved=c['actual_fixed_steel_interior_members']))
 for p in sorted(floors):
  s=actual[p]
  if p in bes:holds.append(dict(position=p,reason='BE_in_bottom',snbt=bes[p]));continue
  if s in AIR or s in NATURAL:changes.append(dict(position=p,before=s,after='projectseele:nerv_structural_panel',operation='root_wet_cavity_two_layer_bottom'))
  elif shape.get(s)==[[0.,0.,0.,1.,1.,1.]]:retained.append(dict(position=p,state=s))
  else:holds.append(dict(position=p,reason='unknown_or_partial_bottom',state=s))
 envelope=json.loads((A/'prelaunch_world_current/CURRENT_PRELAUNCH_PART_ENVELOPES.json').read_text('utf8'));body_min=min(p['bounds'][1] for leg in envelope['legs'] for p in leg['parts'] if p['family']!='PLUG');plug_min=min(p['bounds'][1] for leg in json.loads((A/'seated_plug_prelaunch/TRUE_PLUG_ENVELOPES.json').read_text('utf8'))['legs'] for p in leg['parts']);assert body_min>-1069 and plug_min>-1069
 contacts={}
 for x,z in cols:
  p=(x,-1071,z);pairs=[]
  for dx,dy,dz in ((1,0,0),(-1,0,0),(0,-1,0),(0,0,1),(0,0,-1)):
   q=(p[0]+dx,p[1]+dy,p[2]+dz)
   if q not in floors and q not in cuts and shape.get(actual.get(q,''))==[[0.,0.,0.,1.,1.,1.]]:pairs.append(q)
  contacts[f'{x},{z}']=pairs
  if not pairs:holds.append(dict(column=[x,z],reason='bottom_has_no_immediate_actual_solid_attachment'))
 newly=[c for c in changes if c['after']!='minecraft:air'];rows=[dict(position=c['position'],state=c['after'],native_boxes=[[c['position'][0],c['position'][1],c['position'][2],c['position'][0]+1,c['position'][1]+1,c['position'][2]+1]]) for c in newly]
 (O/'PROPOSED_BOTTOM_NATIVE_SHAPES.json').write_text(json.dumps(dict(world_written=False,unknown_shapes=[],cells=rows),ensure_ascii=False,indent=2),'utf8')
 result=dict(world_written=False,root_apply_ready=False,changes=changes,holds=holds,cut_count=sum(c['after']=='minecraft:air' for c in changes),new_bottom_count=len(newly),retained_solid_bottoms=retained,all_two_layer_bottom_positions=sorted(floors),per_column_original_solid_contacts=contacts,body_y_separation=dict(actual_all_prelaunch_body_carrier_head_min_y=body_min,true_seated_plug_min_y=plug_min,bottom_max_y=-1069),current_gate_y_separation=dict(interface=str(I),sha256=sha(I),actual_fixed_and_full_motion_min_y=-1068.26,bottom_max_y=-1069,minimum_gap_m=.74),pending=['new bottom cells vs current independent fixed steel'],preserve_lower_original_steel_inside_six_cut_native_cubes=True)
 (O/'PREPARED_WET_THROAT_CAVITY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print('cuts',result['cut_count'],'newfloors',len(newly),'retained',len(retained),'holds',len(holds))
if __name__=='__main__':main()
