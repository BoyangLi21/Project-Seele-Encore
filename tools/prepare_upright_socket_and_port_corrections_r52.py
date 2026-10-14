"""Finite corrections from actual authored steel: move 18 socket facets below
gate working bands and measure narrow ports against all real source vertices.
Geometry/requests only. Never writes World or enables production."""
from pathlib import Path
import json,hashlib,math
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.Codex/r52_continuous_route_migration_20261012'
def records(path,key):
 marker='"'+key+'":['; decoder=json.JSONDecoder()
 with path.open('r',encoding='utf8') as f:
  buf=''
  while marker not in buf:
   chunk=f.read(65536)
   if not chunk:raise ValueError(key)
   buf=(buf+chunk)[-131072:]
  buf=buf.split(marker,1)[1];pos=0
  while True:
   while pos<len(buf) and buf[pos] in ' \n\r\t,':pos+=1
   if pos<len(buf) and buf[pos]==']':return
   try:obj,end=decoder.raw_decode(buf,pos)
   except json.JSONDecodeError:
    chunk=f.read(65536)
    if not chunk:raise
    buf=buf[pos:]+chunk;pos=0;continue
   yield obj;pos=end
   if pos>65536:buf=buf[pos:];pos=0
def clip(poly,axis,value,above):
 out=[];prev=poly[-1];old=prev[axis]>=value if above else prev[axis]<=value
 for cur in poly:
  now=cur[axis]>=value if above else cur[axis]<=value
  if old!=now:out.append(prev+(cur-prev)*(value-prev[axis])/(cur[axis]-prev[axis]))
  if now:out.append(cur)
  prev=cur;old=now
 return out
def main():
 steel=OUT/'D31_61C9_UPRIGHT_STEEL_UNANCHORED.json';sock=json.loads(steel.with_suffix('.SOCKETS.json').read_text('utf8'));gates=json.loads((OUT/'D31_61C9_ROOT_GATES_REAR_REFLECTED_CANDIDATE.json').read_text('utf8'))['gates'];gate={g['resource']:g for g in gates};bad=json.loads((OUT/'ACTUAL_GATES_SEAT_RELOCATION_REQUIRED.json').read_text('utf8'));q={v['socket_id']:v for v in sock['sockets']};targets=[]
 for b in bad:
  a=q[b['socket_id']];gy=gate[b['gate']]['frame']['position'][1];targets.append(dict(old=a,gate=b['gate'],target_y=gy-8.,best=None))
 bounds={};ported=[g for g in gates if g.get('silo_hatch',{}).get('upright_guide_ports')]
 for i,p in enumerate(records(steel,'pieces')):
  if p['component'] not in ('web','head'):continue
  assert p['frame']['quaternion_xyzw']==[0,0,0,1]
  xyz=np.array(p['triangles_rgb']).reshape(-1,6)[:,:3]+p['frame']['translation'];lo=xyz.min(0);hi=xyz.max(0)
  if p['component']=='web':
   tri=xyz.reshape(-1,3,3)[4];A=tri.mean(0)
   for t in targets:
    a=t['old']
    if p['leg']==a['leg'] and p['side']==a['side'] and A[1]<=t['target_y']:
     score=t['target_y']-A[1]
     if t['best'] is None or score<t['best']['score']:t['best']=dict(score=float(score),piece=p['name'],A=A.tolist(),tri=tri.tolist())
  for g in ported:
   O=np.array(g['frame']['position']);assert g['frame']['quaternion']==[0,0,0,1]
   if hi[1]<O[1] or lo[1]>O[1]+5.38 or hi[0]<O[0]-18 or lo[0]>O[0]+18 or hi[2]<O[2]-17 or lo[2]>O[2]+17:continue
   local=xyz-O
   for tri in local.reshape(-1,3,3):
    poly=clip(list(tri),1,0,True)
    if poly:poly=clip(poly,1,5.38,False)
    if not poly:continue
    poly=np.array(poly);side=-1 if poly[:,0].mean()<0 else 1;k=(side,p['component']);xz=poly[:,[0,2]]
    if k not in bounds:bounds[k]=[xz.min(0),xz.max(0)]
    else:bounds[k]=[np.minimum(bounds[k][0],xz.min(0)),np.maximum(bounds[k][1],xz.max(0))]
  if i%20000==0:print('actual pieces',i,flush=True)
 updates=[]
 for t in targets:
  old=t['old'];b=t['best'];assert b is not None,(old['socket_id'],t['target_y']);new=dict(old);new.update(rail_piece=b['piece'],rail_bearing=b['A'],actual_rail_weld_triangle=b['tri'],normal=(np.cross(np.array(b['tri'][1])-b['tri'][0],np.array(b['tri'][2])-b['tri'][0])/np.linalg.norm(np.cross(np.array(b['tri'][1])-b['tri'][0],np.array(b['tri'][2])-b['tri'][0]))).tolist(),actual_rail_interval_index=int(b['piece'].split('/')[-2]),relocation_reason='below full door moving band by at least8m',replaced_rail_piece=old['rail_piece']);new.pop('along_curve_m',None);q[old['socket_id']]=new;updates.append(dict(socket_id=old['socket_id'],gate=t['gate'],old_bearing=old['rail_bearing'],new_bearing=new['rail_bearing'],new_rail_piece=b['piece'],actual_rail_weld_triangle=b['tri']))
 sock['sockets']=[q[v['socket_id']] for v in sock['sockets']];sock['status']='ROOT_NATIVE_RESELECT_REQUIRED_18_RELOCATED_PLUS36_PENDING';sock['source_sha256']=hashlib.file_digest(steel.open('rb'),'sha256').hexdigest();sock['relocated_socket_ids']=[t['old']['socket_id'] for t in targets]
 target=OUT/'D31_61C9_RELOCATED_EXACT_SOCKET_REQUESTS.json';target.write_text(json.dumps(sock,indent=2),'utf8')
 port=[]
 for (side,component),(lo,hi) in sorted(bounds.items()):
  lo-=.005;hi+=.005;assert np.all(hi-lo<1.3),(side,component,lo,hi);port.append(dict(side=side,component=component,min_xz=lo.tolist(),max_xz=hi.tolist()))
 (OUT/'D31_61C9_ACTUAL_GATE_PORT_AND_SOCKET_CORRECTIONS.json').write_text(json.dumps(dict(model_source_sha256=sock['model_source_sha256'],directory_geometry_sha256=sock['directory_geometry_sha256'],actual_clipped_rail_y_band_m=[0,5.38],guard_m=.005,ports=port,relocated=updates,world_written=False),indent=2),'utf8')
 print('PORTS',port,'RELOCATED',len(updates),target,flush=True)
if __name__=='__main__':main()
