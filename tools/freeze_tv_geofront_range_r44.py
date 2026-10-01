"""Read-only exact terrain preflight with current native mode-specific envelopes."""
from pathlib import Path
import argparse,json,gzip,hashlib,shutil,ast,math,io
from collections import Counter
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('transport',type=Path);p.add_argument('--name',default='frozen_whole_geometry_v2');a=p.parse_args();out=a.plan/a.name;assert not out.exists();out.mkdir()
 original=json.loads((a.plan/'terrain_contract.json').read_text('utf8'));field=np.load(a.plan/'whole_heightfield.npz');before=field['before'];after=field['after'];eligible=field['eligible'];ox,oz=map(int,field['origin']);zsize,xsize=before.shape
 X,Z=np.meshgrid(np.arange(xsize)+ox,np.arange(zsize)+oz);transport=json.loads(a.transport.read_text('utf8'));conflicts=[];summary=[]
 # Conservative actual-metre envelopes, separate by mode. They do not
 # assert native swept vehicle acceptance; root retains that obligation.
 envelopes={'TRAIN':dict(horizontal=6,below=3,above=10),'AIRPLANE':dict(horizontal=64,below=24,above=80)}
 for c in transport['curves']:
  assert c['mode'] in envelopes,c['mode'];e=envelopes[c['mode']];points=np.asarray(c['points'],float);near=(points[:,0]>=ox-e['horizontal'])&(points[:,0]<=ox+xsize-1+e['horizontal'])&(points[:,2]>=oz-e['horizontal'])&(points[:,2]<=oz+zsize-1+e['horizontal'])
  # A curve outside the sector but inside its full vehicle halo participates.
  samples=0;contacts=0;classification='OUTSIDE_HORIZONTAL_HALO'
  if near.any():
   pts=points[near];classification='ABOVE_TERRAIN_LAYER' if pts[:,1].min()-e['below']>int(after[eligible].max())+1 else 'FULL3D_CHECKED';samples=len(pts)
   if classification=='FULL3D_CHECKED':
    for x,y,z in pts:
     i0=max(0,math.floor(x-e['horizontal'])-ox);i1=min(xsize-1,math.floor(x+e['horizontal'])-ox);j0=max(0,math.floor(z-e['horizontal'])-oz);j1=min(zsize-1,math.floor(z+e['horizontal'])-oz)
     if i0>i1 or j0>j1:continue
     hit=eligible[j0:j1+1,i0:i1+1]&(after[j0:j1+1,i0:i1+1]+1>y-e['below'])&(before[j0:j1+1,i0:i1+1]<y+e['above'])
     contacts+=int(hit.sum())
     if hit.any():
      jj,ii=np.argwhere(hit)[0];conflicts.append(dict(curve=c['id'],mode=c['mode'],sample=[x,y,z],pos=[int(i0+ii+ox),int(after[j0+jj,i0+ii]),int(j0+jj+oz)]))
  summary.append(dict(id=c['id'],mode=c['mode'],classification=classification,halo_samples=samples,conflict_samples=contacts,conservative_envelope=e))
 provider=WORLD/'datapacks/tv_world_preview/data/projectseele/dimension/geofront.json';volumes=json.loads(provider.read_text('utf8'))['generator']['biome_source']['protected_volumes'];protected_hits=[]
 for index,(x,y,z,A,Y,C) in enumerate(volumes):
  hit=eligible&(X>=x)&(X<=A)&(Z>=z)&(Z<=C)&(after+1>y)&(before<=Y)
  if hit.any():protected_hits.append(dict(index=index,bounds=[x,y,z,A,Y,C],columns=int(hit.sum())))
 # The whole launch/transfer envelope stays in the preserved central disc.
 launch_boxes=[[-38,-460,-260,102,96,-19]]
 launch_hits=[]
 for x,y,z,A,Y,C in launch_boxes:
  if (eligible&(X>=x)&(X<=A)&(Z>=z)&(Z<=C)&(after+1>y)&(before<=Y)).any():launch_hits.append([x,y,z,A,Y,C])
 w=MeasuredWorld(WORLD);bounds=original['whole_sector_bounds'];w.box(tuple(bounds[:3]),tuple(bounds[3:]));w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',tuple(bounds[:3]),tuple(bounds[3:]),selected_chunks=set(w.selected)));errors=[];count=0;sectors=[]
 for sector in original['sectors']:
  forward=Path(sector['forward']);inverse=Path(sector['inverse']);assert sha(forward)==sector['forward_sha256'];local=0
  with gzip.open(forward,'rt',encoding='utf8') as f,gzip.open(inverse,'rt',encoding='utf8') as inv:
   for line,backline in zip(f,inv,strict=True):
    r=json.loads(line);back=json.loads(backline);q=tuple(r['pos']);observed=w.block(q);tag=tags[q].snbt() if q in tags else None
    if observed!=r['before'] or tag!=r.get('before_nbt'):
     if len(errors)<40:errors.append(dict(pos=q,expected=r['before'],actual=observed,actual_nbt=tag))
    assert q==tuple(back['pos']) and r['before']==back['after'] and r['after']==back['before'] and r.get('before_nbt')==back.get('after_nbt') and r.get('after_nbt')==back.get('before_nbt')
    count+=1;local+=1
  assert local==sector['changed_cells'];sectors.append(dict(sector,forward_sha256=sha(forward),inverse_sha256=sha(inverse),exact_current_checked_cells=local))
 assert count==original['changed_cells']
 resource=out/'absolute_eligible_heightfield.json.gz'
 with resource.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as compressed,io.TextIOWrapper(compressed,encoding='utf8') as stream:
  json.dump(dict(format='r44_absolute_eligible_ground_v1',bounds=[ox,oz,ox+xsize-1,oz+zsize-1],default_outside='retain original ground and exact wood/protection collars',columns=[[int(X[j,i]),int(Z[j,i]),int(after[j,i])] for j,i in np.argwhere(eligible)]),stream,separators=(',',':'))
 sources=[Path(e['original_path']) for e in original['source_epochs']]+[Path(__file__),ROOT/'tools/plan_new_city_blocks_r44.py',a.transport,a.transport.with_name('source_hashes.json')]
 seen=set(sources);todo=list(sources)
 while todo:
  source=todo.pop()
  if source.suffix!='.py':continue
  for node in ast.walk(ast.parse(source.read_text('utf8'))):
   modules=[v.name for v in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
   for name in modules:
    for base in [source.parent,ROOT/'tools']:
     dep=base/(name.replace('.','/')+'.py')
     if dep.exists() and dep not in seen:seen.add(dep);sources.append(dep);todo.append(dep)
 snapshot=out/'source_inputs';snapshot.mkdir();epochs=[]
 for index,source in enumerate(sources):
  copy=snapshot/(str(index).zfill(2)+'_'+source.name);shutil.copy2(source,copy);epochs.append(dict(path=str(copy.resolve()),original_path=str(source.resolve()),sha256=sha(copy),immutable_snapshot=True))
 minimum=int((field['ceilings'][eligible]-after[eligible]).min());ready=not errors and not conflicts and not protected_hits and not launch_hits and not original['held'] and minimum>=24
 report=dict(original,sectors=sectors,source_epochs=epochs,current_transport_snapshot=str(a.transport.resolve()),current_transport_sha256=sha(a.transport),mode_specific_clearance_envelopes=envelopes,whole_curve_clearance=summary,transport_conflicts=conflicts,existing_3D_protection_count=len(volumes),existing_3D_protection_conflicts=protected_hits,whole_launch_transfer_bounds=launch_boxes,launch_conflicts=launch_hits,exact_current_checked_cells=count,exact_current_errors=errors,full_inverse_verified=True,absolute_heightfield_resource=dict(path=str(resource.resolve()),sha256=sha(resource),columns=int(eligible.sum()),zero_outside_eligible_overrides=True),spherical_roof_clearance_min=minimum,root_apply_ready=ready,world_written=False,native_passed=False,visual_passed=False,root_must_verify_actual_vehicle_dimensions=True,source_future_generation_proposed='Root alone loads this exact eligible absolute-height resource; no recreated similar formula may discard original wood/protection collars')
 (out/'terrain_contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('Whole range exact',count,'rail/air',dict(Counter(v['classification'] for v in summary)),'conflicts',len(conflicts),'protected',len(protected_hits),'roof',minimum,'ready',ready,flush=True)
if __name__=='__main__':main()
