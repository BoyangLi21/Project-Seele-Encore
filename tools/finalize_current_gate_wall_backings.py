"""Finalize the finite wall insert after existing source envelopes and steel checks."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1];A=R/'.Codex/map_complete_20261013/route_audit';O=A/'final_gate_native_readback';F=O/'FINITE_TWELVE_WALL_BACKINGS_CANDIDATE.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 doc=json.loads(F.read_text('utf8'));assert not doc['holds'];points={tuple(c['position']) for c in doc['changes']};assert len(points)==25
 steel=A/'prelaunch_slots_candidate/wall_backing_checks/BOTTOM_FIXED_STEEL.json';s=json.loads(steel.read_text('utf8'));assert {tuple(c['position']) for c in s['cells']}==points;assert not any(c['actual_fixed_steel_interior_members'] or c['actual_finite_native_face_contacts'] for c in s['cells'])
 env=A/'gate14_final_879/GATE14_CURRENT_ENVELOPES.json';g=json.loads(env.read_text('utf8'));boxes=[c['bounds'] for gate in g['gates'] for c in gate['parts']];hits=[dict(position=p,bounds=b) for p in points for b in boxes if all(p[i]+1>b[i] and p[i]<b[i+3] for i in range(3))];assert not hits
 doc['pending']=[];doc['root_apply_ready']=True;doc['necessary_finite_collision_checks']=dict(new_cells=25,current_original_fixed_steel_interiors=0,finite_original_native_face_contacts=0,current_whole_gate_motion_conservative_envelope_intersections=0,current_prelaunch_body_positive_Y_gap=doc['carrier_prelaunch_min_y']-doc['new_block_max_y'],current_lower_full_stroke_positive_Z_gap=doc['lower_full_stroke_min_z']-doc['new_block_max_z'],source_sha256={str(p):sha(p) for p in [steel,env]});F.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n','utf8');print('READY',len(doc['changes']),'SHA',sha(F))
if __name__=='__main__':main()
