"""Rebuild27 closed/open native proxy tables from the actual ported primitive.

Uses the existing controller's one closed->open table format. Retains its
exact owned cell domain; no new walls, supports, controllers or World writes.
Actual triangle/voxel intersection decides each cell, rather than clearing a
door bounding box because a narrow rail slot touches it.
"""
import argparse,gzip,hashlib,json
from pathlib import Path
import numpy as np

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def matrix(q):
 x,y,z,w=q;return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def rigid(a):
 v=a['translation'];return np.array([v['x'],v['y'],v['z']]),matrix([a['qx'],a['qy'],a['qz'],a['qw']])
def intersects(t,lo,hi):
 e=(hi-lo)/2;t=t-(hi+lo)/2;m=np.all(np.max(t,axis=1)>=-e-1e-9,axis=1)&np.all(np.min(t,axis=1)<=e+1e-9,axis=1);t=t[m]
 if len(t)==0:return False
 edges=[t[:,1]-t[:,0],t[:,2]-t[:,1],t[:,0]-t[:,2]];live=np.ones(len(t),bool)
 for ax in [np.cross(edges[0],edges[1])]+[np.cross(v,a) for v in edges for a in np.eye(3)]:
  p=np.einsum('nvc,nc->nv',t,ax);radius=np.sum(np.abs(ax)*e,axis=1);live &= (np.max(p,axis=1)>=-radius-1e-9)&(np.min(p,axis=1)<=radius+1e-9)
 return bool(np.any(live))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--gates',type=Path,required=True);ap.add_argument('--primitive',type=Path,required=True);ap.add_argument('--rear-primitive',type=Path);ap.add_argument('--floor-primitive',type=Path);ap.add_argument('--old-tables',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();d=json.loads(a.gates.read_text('utf8'));p=json.loads(a.primitive.read_text('utf8'));rear={v['resource']:v for v in json.loads(a.rear_primitive.read_text('utf8'))['gates']} if a.rear_primitive else {};floors={v['resource']:v for v in json.loads(a.floor_primitive.read_text('utf8'))['gates']} if a.floor_primitive else {};closed=next(f for f in p['phases'] if f['progress']==0);local=[]
 for part in closed['parts']:
  if not part['moving']:continue
  xyz=np.array(p['templates'][part['part']]).reshape(-1,6)[:,:3];origin,R=rigid(part['local']);local.append((xyz@R.T+origin).reshape(-1,3,3))
 tri=np.concatenate(local);a.output.mkdir(parents=True,exist_ok=True);reports=[]
 for g in d['gates']:
  ref=g['collision_steps'];old=a.old_tables/ref['cells_file'];assert sha(old)==ref['sha256'];rows=json.loads(gzip.decompress(old.read_bytes()))
  target=a.output/Path(ref['cells_file']).name
  if g.get('silo_hatch',{}).get('upright_guide_ports',False) or g.get('hangar_stack',{}).get('depth_direction',1)==-1:
   if g['resource'] in rear:
    q=rear[g['resource']];closed=next(f for f in q['phases'] if f['progress']==0);parts=[]
    for v in closed['moving']:
     xyz=np.array(q['templates_rgb'][v['part']]).reshape(-1,6)[:,:3];origin,R=rigid(v['frame']);parts.append((xyz@R.T+origin).reshape(-1,3,3))
    world=np.concatenate(parts)
   else:R=matrix(g['frame']['quaternion']);world=tri@R.T+np.array(g['frame']['position'])
   changed=[];out=[]
   for group in rows:
    dst=[]
    for cell in group:
     q=np.array(cell['position'],float);solid=intersects(world,q,q+1);row=dict(cell)
     if not solid:row['closed']=row['open']
     if row!=cell:changed.append(dict(position=cell['position'],old_closed=cell['closed'],new_closed=row['closed']))
     dst.append(row)
    out.append(dst)
   encoded=gzip.compress(json.dumps(out,separators=(',',':')).encode(),mtime=0);target.write_bytes(encoded);reports.append(dict(resource=g['resource'],owned_domain_cells=sum(map(len,rows)),changed_closed_cells=changed,projection='actual moving closed primitive triangle/voxel SAT, existing owned domain only'))
  else:target.write_bytes(old.read_bytes())
  if g.get('hangar_stack',{}).get('floor_seal'):
   assert g['resource'] in floors,('Actual latest bottomSeal primitive required',g['resource'])
   floor=floors[g['resource']];expected={tuple(c) for c in g['floor_seal_original_cells']};assert len(expected)==14
   phase_tri={}
   for progress in (0,1):
    phase=next(v for v in floor['actual_81_phases'] if v['progress']==progress);pieces=[]
    for part in phase['parts']:
     if not part['part'].startswith('bottom_seal/leaf/'):continue
     xyz=np.array(floor['actual_templates_rgb'][part['part']]).reshape(-1,6)[:,:3];origin,R=rigid(part['world_frame']);pieces.append((xyz@R.T+origin).reshape(-1,3,3))
    phase_tri[progress]=np.concatenate(pieces)
   groups=json.loads(gzip.decompress(target.read_bytes()));owned={tuple(c['position'])for group in groups for c in group};assert not owned&expected,'New wet seal cells already owned'
   added=[]
   for at in sorted(expected):
    q=np.array(at,float);assert intersects(phase_tri[0],q,q+1) and not intersects(phase_tri[1],q,q+1),('Actual leaf closed/open does not match exact owned floor cell',at)
    added.append(dict(position=list(at),closed='projectseele:nerv_floor_panel',open='minecraft:air'))
   groups[0].extend(added);target.write_bytes(gzip.compress(json.dumps(groups,separators=(',',':')).encode(),mtime=0));reports.append(dict(resource=g['resource'],added_owned_wet_floor_cells=added,projection='actual14 leaf primitive closed/open SAT; original gate group retained'))
  g['collision_steps']=dict(cells_file=target.name,sha256=sha(target))
 d['status']='PORT_PRIMITIVES_AND_PROXY_TABLES_COMPLETE_WORLD_PENDING';d['world_written']=False;d['native_controllers_installed']=False;result=a.output/'ROOT_GATES_UPRIGHT_FINAL_CANDIDATE.json';result.write_text(json.dumps(d,separators=(',',':')),'utf8');receipt=dict(gates_input_sha256=sha(a.gates),actual_primitive_sha256=sha(a.primitive),actual_floor_primitive_sha256=sha(a.floor_primitive) if a.floor_primitive else None,output_gates=str(result.resolve()),output_sha256=sha(result),tables_sha256={f.name:sha(f) for f in a.output.glob('*_cells.json.gz')},changed_gate_reports=reports,world_written=False,native_acceptance=False);(a.output/'PORTED_GATE_PROXY_PROJECTION_RECEIPT.json').write_text(json.dumps(receipt,indent=2),'utf8');print(result,sha(result),sum(len(r.get('changed_closed_cells',[])) for r in reports),flush=True)
if __name__=='__main__':main()
