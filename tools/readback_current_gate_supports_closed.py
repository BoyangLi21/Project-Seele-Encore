"""Targeted final gate bearings and closed-state cells, through query_blocks only."""
from pathlib import Path
import json,gzip,hashlib,collections,math,argparse
from prepare_complete_prelaunch_finite_slots import measure,W
from query_blocks import AIR,iter_block_entities
R=Path(__file__).resolve().parents[1];A=R/'.Codex/map_complete_20261013/route_audit';ap=argparse.ArgumentParser();ap.add_argument('--interface-directory',default='wet_floor_expansion_v2/full_throat');ap.add_argument('--output-name',default='final_gate_native_readback');ap.add_argument('--expected-sha',default='bc521d1dbddb9e1075a0b5a7bedf2da26f509312b9b6839d9835f8296fc9192c');args=ap.parse_args();G=A/args.interface_directory;O=A/args.output_name;O.mkdir(exist_ok=True,parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def on_face(point,normal,boxes):
 axis=max(range(3),key=lambda i:abs(normal[i]));side=3+axis if normal[axis]>0 else axis
 return any(abs(point[axis]-b[side])<=2e-6 and all(b[i]-2e-6<=point[i]<=b[i+3]+2e-6 for i in range(3) if i!=axis) for b in boxes)
def main():
 interface=G/'CURRENT_TYPED_GATE_INTERFACE.json';doc=json.loads(interface.read_text('utf8'));assert sha(interface)==args.expected_sha;candidate=G/doc['root_gate_candidate']['file'];assert sha(candidate)==doc['root_gate_candidate']['sha256'];c=json.loads(candidate.read_text('utf8'));auth={g['resource']:g for g in c['gates']};points=set();closed={};support=set()
 for g in doc['gates']:
  for b in g['bearing_contacts']:
   support.add(tuple(b['candidate_cell']));normal=b['normal_world'];axis=max(range(3),key=lambda i:abs(normal[i]));uv=[i for i in range(3) if i!=axis];half=b['half_width_m']
   for a in (-half,0,half):
    for z in (-half,0,half):q=list(b['point_world']);q[uv[0]]+=a;q[uv[1]]+=z;q[axis]-=normal[axis]*1e-5;points.add(tuple(math.floor(v) for v in q))
  table=G/g['collision_steps']['cells_file'];assert sha(table)==g['collision_steps']['sha256'];steps=json.loads(gzip.decompress(table.read_bytes()));assert len(steps)==1;closed[g['resource']]=steps[0];points.update(tuple(v['position']) for v in steps[0])
 points|=support;actual=measure(points);shapes=json.loads((W/'native_collision_shapes.json').read_text('utf8'))
 for name in ['CURRENT_PRODUCTION_SUPPLEMENTAL_SHAPES.json','CURRENT_PRODUCTION_REBASED_SHAPES.json','GATE14_RESOLVED_PRODUCTION_SHAPES.json']:shapes.update({k:v['native_boxes'] for k,v in json.loads((A/'prelaunch_world_current'/name).read_text('utf8'))['rows'].items()})
 readbacks=[];mismatches=[];missing=[];supportrows=[];closedrows=[];unknown=[]
 for g in doc['gates']:
  resource=g['resource'];expected={tuple(v['position']):v['state'] for v in auth[resource]['supports']};srows=[]
  for b in g['bearing_contacts']:
   p=tuple(b['candidate_cell']);state=actual[p];native=shapes.get(state);point=b['point_world'];normal=b['normal_world'];axis=max(range(3),key=lambda i:abs(normal[i]));uv=[i for i in range(3) if i!=axis];half=b['half_width_m'];samples=[];facecells={p}
   for a in (-half,0,half):
    for z in (-half,0,half):q=list(point);q[uv[0]]+=a;q[uv[1]]+=z;q[axis]-=normal[axis]*1e-5;facecells.add(tuple(math.floor(v) for v in q))
   boxes=[[q[i%3]+v for i,v in enumerate(bb)] for q in facecells for bb in shapes.get(actual[q],[])];
   for a in (-half,0,half):
    for z in (-half,0,half):q=list(point);q[uv[0]]+=a;q[uv[1]]+=z;samples.append(dict(point=q,native_face=on_face(q,normal,boxes)))
   row=dict(resource=resource,position=p,expected=expected[p],actual=state,state_match=state==expected[p],native_face_supported=all(v['native_face'] for v in samples),actual_model_contact=b,actual_native_boxes=boxes,nine_face_points=samples);supportrows.append(row);srows.append(row)
   if native is None:unknown.append(dict(position=p,state=state))
   if not row['native_face_supported']:missing.append(row)
   if not row['state_match']:mismatches.append(row)
  wrong=[]
  for cell in closed[resource]:
   p=tuple(cell['position']);row=dict(resource=resource,position=p,expected=cell['closed'],actual=actual[p],match=cell['closed']==actual[p]);closedrows.append(row)
   if not row['match']:wrong.append(row)
  readbacks.append(dict(resource=resource,support_declarations=len(srows),supported=sum(x['native_face_supported'] for x in srows),support_state_matches=sum(x['state_match'] for x in srows),closed_cells=len(closed[resource]),closed_state_matches=len(closed[resource])-len(wrong),closed_differences=wrong))
 # Only finite neighborhoods along each declared missing support normal/downward
 # to the already-authored floor are read. No new room or route is inferred.
 near=set()
 for c in missing:
  p=tuple(c['position']);normal=c['actual_model_contact']['normal_world'];axis=max(range(3),key=lambda i:abs(normal[i]));step=-1 if normal[axis]>0 else 1
  for d in range(0,5):q=list(p);q[axis]+=d*step;near.add(tuple(q))
  for d in range(0,5):near.add((p[0],p[1]-d,p[2]))
  for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):near.add((p[0]+dx,p[1]+dy,p[2]+dz))
 neighbors=measure(near) if near else {};be=[]
 if near:
  lo=tuple(min(p[i] for p in near) for i in range(3));hi=tuple(max(p[i] for p in near) for i in range(3));be=[dict(position=p,snbt=t.snbt()) for p,t in iter_block_entities(W,'projectseele:geofront',lo,hi) if p in near]
 result=dict(world_written=False,game_started=False,interface_sha256=sha(interface),candidate_sha256=sha(candidate),dimension='projectseele:geofront',targeted_unique_cells=len(points),unique_declared_support_cells=len(support),support_declarations=len(supportrows),missing_actual_native_faces=missing,material_state_differences=mismatches,all_support_rows=supportrows,all_closed_rows=closedrows,gates=readbacks,unknown_shapes=unknown,finite_missing_support_neighbors=[dict(position=p,state=s) for p,s in sorted(neighbors.items())],block_entities_at_finite_missing_neighbors=be)
 (O/'CURRENT354_SUPPORTS_AND_CLOSED_READBACK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');rear=[r for r in mismatches if r['resource'].startswith(('bank_1_rear','bank_2_rear'))];(O/'REAR6_EXPECTED_MATERIAL_DIFFERENCES.json').write_text(json.dumps(dict(world_written=False,rows=rear),ensure_ascii=False,indent=2),'utf8');print('unique supports',len(support),'refs',len(supportrows),'missingface',len(missing),'materialdiff',len(mismatches),'rear',len(rear),'closed diffs',sum(len(g['closed_differences']) for g in readbacks),'unknown',len(unknown));print('missing positions',[m['position'] for m in missing])
if __name__=='__main__':main()
