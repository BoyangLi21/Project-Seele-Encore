"""Rebind only the 46 valid original support materials and associate unchanged proofs."""
from pathlib import Path
import json,hashlib,copy,shutil
R=Path(__file__).resolve().parents[1];A=R/'.Codex/map_complete_20261013/route_audit';S=A/'wet_floor_expansion_v2/full_throat';O=A/'final_gate_native_readback/rebound_current';O.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n','utf8')
def main():
 ci=S/'CURRENT_TYPED_GATE_INTERFACE.json';candidate=S/'ROOT_TYPED_GATES_CANDIDATE.json';peer=S/'CURRENT_GATE_PEER_CYCLE.json';assert sha(ci)=='bc521d1dbddb9e1075a0b5a7bedf2da26f509312b9b6839d9835f8296fc9192c';source=json.loads(candidate.read_text('utf8'));changed=copy.deepcopy(source);data=json.loads((O.parent/'CURRENT354_SUPPORTS_AND_CLOSED_READBACK.json').read_text('utf8'));patches=[r for r in data['material_state_differences'] if r['native_face_supported']];assert len(patches)==46;gateindex={g['resource']:g for g in changed['gates']};applied=[]
 for row in patches:
  g=gateindex[row['resource']];matches=[v for v in g['supports'] if v['position']==row['position']];assert len(matches)==1;v=matches[0];assert v['state']==row['expected'];v['state']=row['actual'];applied.append(dict(resource=row['resource'],position=row['position'],before_expected=row['expected'],after_expected=row['actual']))
 restored=copy.deepcopy(changed);idx={g['resource']:g for g in restored['gates']}
 for row in applied:
  next(v for v in idx[row['resource']]['supports'] if v['position']==row['position'])['state']=row['before_expected']
 assert restored==source
 save(O/candidate.name,changed);interface=json.loads(ci.read_text('utf8'));oldinterface=copy.deepcopy(interface);interface['root_gate_candidate']['sha256']=sha(O/candidate.name);save(O/ci.name,interface);assert {k:v for k,v in interface.items() if k!='root_gate_candidate'}=={k:v for k,v in oldinterface.items() if k!='root_gate_candidate'}
 files={p['mesh_file']:p['mesh_sha256'] for p in interface['profiles'].values()};files.update({g['collision_steps']['cells_file']:g['collision_steps']['sha256'] for g in interface['gates']});copied=[]
 for name,expected in files.items():
  p=S/name;q=O/name;assert sha(p)==expected;q.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(p,q);assert sha(q)==expected;copied.append(dict(file=name,sha256=expected))
 proof=json.loads(peer.read_text('utf8'));assert proof['passed'] and not proof['hits'];assert proof['source_interface_sha256']==sha(ci);original_proof=copy.deepcopy(proof);proof['source_interface']=str(O/ci.name);proof['source_interface_sha256']=sha(O/ci.name);proof['geometry_association']=dict(original_proof=str(peer),original_proof_sha256=sha(peer),original_interface_sha256=sha(ci),method='46 expected support block-state labels only; actual bearing points, frames, profile triangles, motion frames, clocks and collision tables are exactly identical; previous exact geometric proof reused, not rerun');save(O/peer.name,proof)
 association=dict(world_written=False,game_started=False,only_expected_support_material_changes=46,rear_support_material_changes=40,front_valid_original_deepslate_changes=6,world_material_changed=False,geometry_and_bearing_points_identical=True,closed_collision_cells_identical=True,full_triangles_and_motion_frames_identical=True,source_candidate_sha256=sha(candidate),candidate_sha256=sha(O/candidate.name),source_interface_sha256=sha(ci),interface_sha256=sha(O/ci.name),source_peer_proof_sha256=sha(peer),associated_peer_sha256=sha(O/peer.name),geometric_proof_not_rerun=True,source_peer_pair_windows=original_proof['pair_windows'],source_peer_hits=original_proof['hits'],changes=applied,unchanged_geometry_and_collision_files=copied,native_support_completion='Root applies the separate25-block wall backing candidate, then actual native face readback is required; this association does not assert that absent walls already exist.')
 save(O/'SUPPORT_MATERIAL_ONLY_GEOMETRY_ASSOCIATION.json',association);print('candidate',association['candidate_sha256']);print('interface',association['interface_sha256']);print('peer',association['associated_peer_sha256']);print('changes',len(applied),'geometryfilesidentical',len(copied))
if __name__=='__main__':main()
