"""Guard measured walking edges; preserve operating lift and door sweeps."""
from pathlib import Path
import json,argparse,numpy as np
import regional_voxels as v,scan_regional_completion as scan,plan_factory_r20 as f
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R22_REVIEW';OUT=ROOT/'artifacts/facility_r23/safety'
def main(apply=False):
 d=np.load(ROOT/'artifacts/facility_r23/navigation/check_after/measured_public_space.npz');lo=d['lo'];hi=d['hi'];f.LO=lo;f.HI=hi;v.WORLD=scan.WORLD=WORLD;v.OUT=OUT;s=f.Scene();p=v.Painter()
 report=json.loads((OUT/'pyramid_edges.json').read_text());sweeps=json.loads((ROOT/'artifacts/world_rebuild_r20/lifts/sweep_masks.json').read_text());held=[];guards=[];seen=set();native=[]
 def mechanical(q):
  for r in sweeps:
   a,b=r['sweep']
   if all(a[i]-1<=q[i]<=b[i]+1 for i in range(3)):return True
  return False
 def at(q):return s.palette[s.after[q[1]-lo[1],q[2]-lo[2],q[0]-lo[0]]]
 for r in report['fall_edges']:
  x,y,z=r['floor'];dx,dz=r['outward'];q=(x+dx,y,z+dz)
  if q in seen:continue
  seen.add(q)
  # These are the original full-width R04 descending stair throats. A void
  # beside the top-floor centreline is headroom for the same stair, not a
  # location for a new bracket/glass column. Guard the last supported floor.
  if q[0] in (68,70) and q[2]==360 and y in (-434,-420,-406,-392,-378,-364):
   assert x in (67,71) and z==360
   supported=(x,y,z);old=at(supported)
   if old not in {'minecraft:air','minecraft:cave_air','minecraft:light'} and not old.startswith('projectseele:nerv_edge_rail['):
    held.append(dict(**r,reason='Registered stair boundary has an existing fixture; preserve'));continue
   sides={k:'false'for k in ('east','north','south','west')}
   if old.startswith('projectseele:nerv_edge_rail['):sides.update(dict(v.split('=',1)for v in old.split('[',1)[1].rstrip(']').split(',')))
   sides['east'if dx>0 else'west']='true'
   rail='projectseele:nerv_edge_rail['+','.join(k+'='+sides[k]for k in sorted(sides))+']'
   s.fill((*supported,*supported),rail);guards.append(dict(**r,guard=supported,registered_stair_throat=True))
   native.append(dict(id='r23/pyramid_guard/'+str(len(guards)),start=[x+.5,y,z+.5],direction=[dx,0,dz],barrier=list(supported)))
   continue
  if any(mechanical((q[0],Y,q[2])) for Y in (y-1,y,y+1)):held.append(dict(**r,reason='native moving cabin/landing exclusion'));continue
  cells=[(q[0],Y,q[2]) for Y in (y-1,y,y+1)]
  if not all(at(c).split('[')[0] in {'minecraft:air','minecraft:cave_air','minecraft:light'} for c in cells):held.append(dict(**r,reason='occupied edge, requires shaped-collision check'));continue
  s.fill((*cells[0],*cells[0]),'projectseele:nerv_structural_panel')
  s.fill((*cells[1],*cells[2]),'projectseele:clear_glass');guards.append(dict(**r,guard=q))
  # Physically press the player toward each newly protected edge at native
  # movement speed. Separate driver handles this as a barrier, not a route.
  native.append(dict(id='r23/pyramid_guard/'+str(len(guards)),start=[x+.5,y,z+.5],direction=[dx,0,dz],barrier=list(q)))
 count=s.delta(p,'r23/supported_clear_perimeter_guards') if np.any(s.before!=s.after) else 0
 p.meta.update(changed_cells=count,guards=guards,held=held,edge_test_cases=native,room_entries=report['rooms'],preservation='Only measured air outside the original walking footprint receives a bracket and transparent guard; original room blocks remain intact.')
 p.save_plan('public_floor_edge_guards')
 if apply:p.apply('public_floor_edge_guards')
 (OUT/'guard_contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Guarded',len(guards),'held mechanical/occupied',len(held),'changes',count)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
