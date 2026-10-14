"""Read the fourteen exact authored gate motion scopes and native shapes, without World writes."""
from pathlib import Path
import json,gzip,math,hashlib,collections,argparse
import numpy as np
from query_blocks import iter_selected_sections,iter_block_entities,chunk_statuses,dimension_dir,AIR
R=Path(__file__).resolve().parents[1];A=R/'.Codex/map_complete_20261013/route_audit';ap=argparse.ArgumentParser();ap.add_argument('--output-name',default='gate14_world_current');ap.add_argument('--interface-directory',default='typed_gates_terminal84');args=ap.parse_args();O=A/args.output_name;G=A/args.interface_directory;W=Path('D:/eva/artifacts/map_complete_20261013/WORLD')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 doc=json.loads((O/'GATE14_CURRENT_ENVELOPES.json').read_text('utf8'));interface=G/'CURRENT_TYPED_GATE_INTERFACE.json';assert doc['interface_sha256']==sha(interface);declaration=json.loads(interface.read_text('utf8'));shapes=json.loads((W/'native_collision_shapes.json').read_text('utf8'))
 for name in ('CURRENT_PRODUCTION_SUPPLEMENTAL_SHAPES.json','CURRENT_PRODUCTION_REBASED_SHAPES.json','GATE14_RESOLVED_PRODUCTION_SHAPES.json'):
  p=A/'prelaunch_world_current'/name
  shapes.update({s:r['native_boxes'] for s,r in json.loads(p.read_text('utf8'))['rows'].items()})
 allboxes=np.array([b for boxes in shapes.values() for b in boxes]);ext=np.r_[allboxes[:,:3].min(0),allboxes[:,3:].max(0)]
 ownership=collections.defaultdict(set)
 for gate in declaration['gates']:
  p=G/gate['collision_steps']['cells_file'];assert sha(p)==gate['collision_steps']['sha256']
  for step in json.loads(gzip.decompress(p.read_bytes())):
   for c in step:ownership[tuple(c['position'])].add(gate['resource'])
 result=[];regions=set()
 for gate in doc['gates']:
  env=np.array([p['bounds'] for p in gate['parts']]);lo=tuple(math.floor(float(env[:,i].min()-ext[i+3])) for i in range(3));hi=tuple(math.floor(float(env[:,i+3].max()-ext[i])) for i in range(3));selected={(x,z):set(range(lo[1]//16,hi[1]//16+1)) for x in range(lo[0]//16,hi[0]//16+1) for z in range(lo[2]//16,hi[2]//16+1)}
  status=chunk_statuses(W,'projectseele:geofront',selected);assert all(v=='full' for v in status.values()),(gate['resource'],{str(k):v for k,v in status.items() if v!='full'})
  files={dimension_dir(W,'projectseele:geofront')/'region'/f'r.{cx//32}.{cz//32}.mca' for cx,cz in selected};before={str(p):sha(p) for p in files};rows=[];unknown=[];bearings={tuple(p['candidate_cell']):p for p in gate['actual_bearing_contacts']}
  for cx,cz,sy,palette,indices in iter_selected_sections(W,'projectseele:geofront',selected):
   for k,state in enumerate(palette):
    if state in AIR:continue
    native=shapes.get(state)
    if native==[]:continue
    for ly,lz,lx in np.argwhere(indices.reshape(16,16,16)==k):
     p=(cx*16+int(lx),sy*16+int(ly),cz*16+int(lz))
     if not all(lo[i]<=p[i]<=hi[i] for i in range(3)):continue
     if native is None:unknown.append(dict(position=p,state=state));continue
     boxes=[]
     for b in native:
      world=np.r_[np.array(p)+b[:3],np.array(p)+b[3:]]
      if np.any(np.all((env[:,3:]>world[:3])&(env[:,:3]<world[3:]),axis=1)):boxes.append(world.tolist())
     if boxes:rows.append(dict(position=p,state=state,native_boxes=boxes,own_dynamic_proxy=gate['resource'] in ownership.get(p,set()),foreign_proxy_resources=sorted(ownership.get(p,set())-{gate['resource']}),declared_bearing=bearings.get(p)))
  assert before=={str(p):sha(p) for p in files},'World changed during gate read';regions.update(files)
  result.append(dict(resource=gate['resource'],read_bounds=[lo,hi],cells=rows,unknown_shapes=unknown,block_entities=[dict(position=p,snbt=t.snbt()) for p,t in iter_block_entities(W,'projectseele:geofront',lo,hi)]));print(gate['resource'],'actual candidates',len(rows),'unknown',len(unknown),flush=True)
 report=dict(world_written=False,game_started=False,interface_sha256=sha(interface),native_shapes_sha256=sha(W/'native_collision_shapes.json'),region_sha256={str(p):sha(p) for p in regions},gates=result);(O/'GATE14_CURRENT_NATIVE_CANDIDATES.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
if __name__=='__main__':main()
