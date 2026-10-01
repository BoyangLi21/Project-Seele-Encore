"""Whole school road datum joins installed Tokyo and existing ports continuously."""
from pathlib import Path
import argparse,json,gzip,math,shutil
import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from plan_new_city_blocks_r44 import SOIL,SMALL,PAVING
from regional_voxels import canonical_state
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
def main():
 p=argparse.ArgumentParser();p.add_argument('school',type=Path);p.add_argument('tokyo',type=Path);p.add_argument('output',type=Path);p.add_argument('--campus-only',action='store_true');p.add_argument('--south-campus',action='store_true');a=p.parse_args();assert not a.output.exists()
 d=json.loads((a.school/'new_district.json').read_text('utf8'));base=[json.loads(r) for r in gzip.open(a.school/'forward.jsonl.gz','rt',encoding='utf8')];trows={tuple(r['pos']):r for r in map(json.loads,gzip.open(a.tokyo/'forward.jsonl.gz','rt',encoding='utf8'))};roads=json.loads((a.school/'road_authority.json').read_text('utf8'));cols={tuple(c['pos']):dict(c) for c in roads['columns']};tcols={tuple(c['pos']):c for c in json.loads((a.tokyo/'road_authority.json').read_text('utf8'))['columns']}
 if a.campus_only:
  cols={q:c for q,c in cols.items() if (150<=q[0]<=294 and -670<=q[1]<=-658) or (246<=q[0]<=258 and -682<=q[1]<=-664)}
  d['road_lines']=[[156,-664,288,-664],[252,-664,252,-676]];d['retained_current_street_authorities']=[str((a.tokyo/'road_authority.json').resolve())];d['retired_uninstalled_road_design']='Retire the redundant164m north plus128m eastern high embankment loop and its dead-end wetland deck. Actual installed Tokyo street is the station successor; dry campus entrance road stops before the real eastern water. All school/gym/floor/roof goals remain.'
  gym=next(b for b in d['buildings'] if b['kind']=='tv_gym');gym['actual_street_handoff']=[294,73,-670]
 if a.south_campus:
  network={}
  for q,c in cols.items():
   if q in tcols and 150<=q[0]<=214 and -670<=q[1]<=-658:network[q]=c
  lines=[[162,-664,218,-664],[218,-664,218,-676],[218,-676,288,-676]]
  for x,z,X,Z in lines:
   length=max(abs(X-x),abs(Z-z))
   for step in range(length+1):
    px=round(x+(X-x)*step/max(1,length));pz=round(z+(Z-z)*step/max(1,length))
    for side in range(-4,5):
     q=px+(side if x==X else 0),pz+(side if z==Z else 0)
     network[q]=dict(pos=list(q),native_feet=73,height2=146,carriage=abs(side)<=2,source_id='r44/tv_school_north/whole_campus_entrance_street')
  cols=network;d['road_lines']=lines;d['retained_current_street_authorities']=[str((a.tokyo/'road_authority.json').resolve())];d['retired_uninstalled_road_design']='Reuse the complete installed Tokyo valley street; retire the tall north/east loop and wet dead-end. Dry9m campus street turns south before the eastern low stream and reaches the actual school/gym forecourts.'
  gym=next(b for b in d['buildings'] if b['kind']=='tv_gym');gym['actual_street_handoff']=[286,73,-672]
 raw=np.load(ROOT/'artifacts/rebuild_r44/surface_network/road_complete_authority_stage3.columns.npz');orig={tuple(map(int,q)):float(f) for q,f,flags in zip(raw['coordinates'],raw['actual_feet'],raw['flags']) if flags&7==7};keys=list(cols);index={q:i for i,q in enumerate(keys)};fixed={}
 for q,c in cols.items():
  if q in tcols:fixed[q]=tcols[q]['native_feet']
  elif q in orig:fixed[q]=orig[q]
  elif q[0]>=221 and q[1]<=-670 if a.south_campus else q[0]>=240 and q[1]<=-657:fixed[q]=73.
 # Dirichlet harmonic datum over the actual full-width road lattice. This
 # distributes the4m valley junction over its whole approach, rather than
 # push a .5m climb into each of eight consecutive1m cells.
 matrix=lil_matrix((len(keys),len(keys)));right=np.zeros(len(keys))
 for q,i in index.items():
  if q in fixed:matrix[i,i]=1;right[i]=fixed[q];continue
  neighbours=[(q[0]+dx,q[1]+dz) for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)] if (q[0]+dx,q[1]+dz) in index]
  if not neighbours:matrix[i,i]=1;right[i]=cols[q]['native_feet'];continue
  matrix[i,i]=len(neighbours)
  for n in neighbours:matrix[i,index[n]]=-1
 solved=spsolve(matrix.tocsr(),right);heights={q:round(float(solved[i])*2)/2 for q,i in index.items()};steps=[]
 for q,h in heights.items():
  for dx,dz in [(1,0),(0,1)]:
   n=q[0]+dx,q[1]+dz
   if n in heights and abs(h-heights[n])>.501:steps.append(dict(first=q,second=n,heights=[h,heights[n]]))
 w=MeasuredWorld(WORLD);x0,x1,z0,z1=d['bounds'];w.box((x0-16,40,z0-16),(x1+16,220,z1+16));w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x0-16,40,z0-16),(x1+16,220,z1+16),selected_chunks=set(w.selected)));target={};held=[];retired=[]
 for r in base:
  q=tuple(r['pos'])
  if r['owner']=='r44/tokyo_north/complete_new_streets':continue
  if q in trows:retired.append(dict(pos=q,reason='Full exact installed Tokyo component retained'));continue
  actual=w.block(q);tag=tags[q].snbt() if q in tags else None
  if actual!=r['before'] or tag!=r.get('before_nbt'):held.append(dict(pos=q,reason='Non-road prior component changed',expected=r['before'],actual=actual));continue
  target[q]=r
 def put(q,s,reason):
  q=tuple(q);old=w.block(q);s=canonical_state(s);column=q[0],q[2]
  if q in trows or column in tcols:return
  if old is None or q in tags or old.split('[')[0] not in SOIL|SMALL|PAVING|AIR:
   held.append(dict(pos=q,state=old,reason=reason));return
  if s==old:target.pop(q,None)
  else:target[q]=dict(pos=q,before=old,after=s,before_nbt=None,after_nbt=None,owner='r44/tv_school_north/complete_new_streets',reason=reason)
 profiles=[]
 for (x,z),c in cols.items():
  feet=heights[x,z];c['native_feet']=feet;c['height2']=round(feet*2)
  if (x,z) in tcols or (x,z) in orig:continue
  g=max([y for y in range(40,191) if (w.get(x,y,z) or '').split('[')[0] in SOIL],default=None);water=max([y for y in range(40,191) if (w.get(x,y,z) or '').split('[')[0]=='minecraft:water'],default=None)
  if g is None or water is not None and water>=g:held.append(dict(pos=[x,z],reason='Regraded new school road requires actual dry bearing'));continue
  yy=(round(feet*2)-1)//2
  if abs(yy-g)>8:held.append(dict(pos=[x,yy,z],ground=g,reason='Whole regraded street exceeds restrained8m formation'));continue
  for y in range(g+1,yy):put((x,y,z),'minecraft:stone','Full current dry bearing below the whole blended school road datum')
  carriage=c['carriage'];material='minecraft:black_concrete' if carriage else 'minecraft:smooth_stone';state=material if float(feet).is_integer() else 'minecraft:polished_blackstone_slab[type=bottom,waterlogged=false]' if carriage else 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
  put((x,yy,z),state,'Complete full-width school road / installed Tokyo valley / original elevated port half-slab datum join')
  for y in range(yy+1,max(yy+6,g+3)):put((x,y,z),'minecraft:air','Whole adjusted school road headroom; retired original higher deck never hangs over the protected Tokyo street')
  profiles.append(dict(pos=[x,z],ground=g,feet=feet,cut_fill=yy-g))
 a.output.mkdir(parents=True);rows=[target[q] for q in sorted(target)]
 for name,inverse in [('forward',False),('inverse',True)]:
  with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as out:
   for r in rows:
    v=dict(r)
    if inverse:v['before'],v['after']=r['after'],r['before'];v['before_nbt'],v['after_nbt']=r.get('after_nbt'),r.get('before_nbt')
    out.write(json.dumps(v,ensure_ascii=False)+'\n')
 for name in ['architecture_components.json','parcel_components.json','source_shape_candidates.json','school_entry_revision.json']:shutil.copy2(a.school/name,a.output/name)
 cases=json.loads((a.school/'native_cases.json').read_text('utf8'))
 if a.campus_only or a.south_campus:
  for case in cases:
   if case['id'].startswith(gym['id']+'/public_entry'):
    hx,hy,hz=gym['actual_street_handoff'];path=[[hx+.5,hy,hz+.5],[hx+.5,hy,-691.5],[gym['door'][0]+.5,73,-691.5],[gym['door'][0]+.5,73,gym['door'][2]-1.5]];case['retired_before_path']=case['path'];case['path']=path[::-1] if case['id'].endswith('/return') else path;case['revision_reason']='Same actual gym goal via complete founded court and dry campus street; retired uninstalled marsh dead-end/oversized loop'
 (a.output/'native_cases.json').write_text(json.dumps(cases,indent=2),'utf8')
 (a.output/'new_district.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')
 roads['columns']=list(cols.values());(a.output/'road_authority.json').write_text(json.dumps(roads,indent=2),'utf8')
 protections=json.loads((a.school/'ecology_reservations.json').read_text('utf8'));protections['reservations'].extend(dict(bounds=[x,math.floor(h)-4,z,x,math.ceil(h)+6,z],owner='r44/tv_school_north/complete_new_streets',role='Whole current road half-slab datum and real vehicle/public clearance') for (x,z),h in heights.items());(a.output/'ecology_reservations.json').write_text(json.dumps(protections,indent=2),'utf8')
 audit=json.loads((a.school/'audit.json').read_text('utf8'));audit.update(changed_cells=len(rows),held=held,ready=False,native_passed=False,visual_passed=False);(a.output/'audit.json').write_text(json.dumps(audit,indent=2),'utf8')
 (a.output/'whole_current_road_datum.json').write_text(json.dumps(dict(producer=str(Path(__file__).resolve()),installed_tokyo=str(a.tokyo.resolve()),fixed_actual_ports=len(fixed),datum_method='Whole-width lattice harmonic Dirichlet solution between actual installed Tokyo/existing ports and the73m school plateau; rounded to native half-block heights',remaining_steps=steps,current_dry_profiles=profiles,retired_conflicting_rows=retired,held=held,world_written=False),indent=2),'utf8');print('Whole school datum',len(rows),'cells','fixed',len(fixed),'steps',len(steps),'held',len(held))
if __name__=='__main__':main()
