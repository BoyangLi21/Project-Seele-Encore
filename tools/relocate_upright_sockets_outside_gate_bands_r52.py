"""Move only exact weld requests out of real shutter working bands.

Reads actual steel and existing gate frames; never edits route/model/World.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from prepare_upright_socket_and_port_corrections_r52 import records

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--steel',type=Path,required=True);ap.add_argument('--gates',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--pending-only',type=Path);ap.add_argument('--gate-interface',type=Path);a=ap.parse_args()
 sockets=json.loads(a.steel.with_suffix('.SOCKETS.json').read_text('utf8'));gates=json.loads(a.gates.read_text('utf8'))['gates'];targets=[]
 input_sha=hashlib.sha256(a.steel.with_suffix('.SOCKETS.json').read_bytes()).hexdigest()
 pending=None
 if a.pending_only:
  prior=json.loads(a.pending_only.read_text('utf8'));assert prior['socket_requests_sha256']==input_sha
  pending={q['socket_id'] for q in prior['pending'] if q.get('failures',{}).get('complete_gate_envelope',0)>0}
 actual_gates=None
 if a.gate_interface:
  from upright_native_anchor_selection_r53 import Gates
  actual_gates=Gates(a.gates,a.gate_interface)
 for q in sockets['sockets']:
  if pending is not None and q['socket_id'] not in pending:continue
  A=np.array(q['rail_bearing'])
  if actual_gates:
   gate=actual_gates.intersects(A,A+np.array(q['normal'])*.5,.18)
   if gate:targets.append(dict(old=q,gate=gate,best=None))
   continue
  for g in gates:
   if not g.get('silo_hatch',{}).get('upright_guide_ports'):continue
   assert g['frame']['quaternion']==[0,0,0,1]
   X,Y,Z=g['frame']['position']
   if abs(A[0]-X)<=18 and abs(A[2]-Z)<=18 and Y-.2<=A[1]<=Y+5.63:targets.append(dict(old=q,gate=g['resource'],target_y=Y-8.,best=None))
 for p in records(a.steel,'pieces'):
  if p['component']!='web':continue
  xyz=np.array(p['triangles_rgb']).reshape(-1,6)[:,:3]+p['frame']['translation'];tri=xyz.reshape(-1,3,3)[4];A=tri.mean(0)
  for t in targets:
   q=t['old']
   if p['leg']==q['leg'] and p['side']==q['side'] and (actual_gates or A[1]<=t['target_y']):
    normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);normal/=np.linalg.norm(normal)
    score=float(np.linalg.norm(A-np.array(q['rail_bearing']))) if actual_gates else t['target_y']-A[1]
    if actual_gates and (score>32 or actual_gates.intersects(A,A+normal*.5,.3)):continue
    if t['best'] is None or score<t['best']['score']:t['best']=dict(score=float(score),piece=p['name'],A=A.tolist(),tri=tri.tolist())
 updates=[]
 for t in targets:
  q=t['old'];b=t['best'];assert b is not None
  old_point=q['rail_bearing'];old_piece=q['rail_piece'];tri=np.array(b['tri']);normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);normal/=np.linalg.norm(normal)
  q.update(rail_piece=b['piece'],rail_bearing=b['A'],actual_rail_weld_triangle=b['tri'],normal=normal.tolist(),actual_rail_interval_index=int(b['piece'].split('/')[-2]),relocation_reason='nearest finite same-leg same-side web outside complete current gate envelope within32m' if actual_gates else 'below actual shutter working band by at least8m',replaced_rail_piece=old_piece)
  q['original_socket_along_curve_m']=q.get('along_curve_m')
  updates.append(dict(socket_id=q['socket_id'],gate=t['gate'],old_bearing=old_point,new_bearing=q['rail_bearing'],actual_rail_piece=q['rail_piece'],actual_rail_weld_triangle=q['actual_rail_weld_triangle']))
 sockets.update(status='FINAL_GEOMETRY_NATIVE_RESELECT_REQUIRED',source_sha256=hashlib.file_digest(a.steel.open('rb'),'sha256').hexdigest(),gate_source_sha256=hashlib.sha256(a.gates.read_bytes()).hexdigest(),relocated_socket_ids=[t['old']['socket_id'] for t in targets],world_written=False)
 a.output.write_text(json.dumps(sockets,indent=2),'utf8');a.output.with_suffix('.RELOCATION_RECEIPT.json').write_text(json.dumps(dict(source=str(a.output.resolve()),sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),input_sockets_sha256=input_sha,model_source_sha256=sockets['model_source_sha256'],directory_geometry_sha256=sockets['directory_geometry_sha256'],steel_sha256=sockets['source_sha256'],relocated=updates,producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),world_written=False),indent=2),'utf8');print(a.output,'requests',len(sockets['sockets']),'relocated',len(updates),flush=True)
if __name__=='__main__':main()
