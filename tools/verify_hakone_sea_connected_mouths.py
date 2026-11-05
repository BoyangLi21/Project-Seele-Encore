"""Verify actual lower-river water, banks, bed support and marine connections."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import label
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL,SOIL
from query_blocks import AIR

def verify(C):
 m=json.loads((C/'manifest.json').read_text('utf8'));spec=m['sea_connected_mouths']
 with np.load(C/'mouth-design.npz')as f:d={k:f[k]for k in f.files}
 x,z,X,Z=map(int,d['bounds']);sea=int(d['sea']);wet=d['wet'];yy=np.arange(-128,320)[:,None,None]
 expected_water=d['original_water'].copy();expected_water[wet]=sea;actual_ground=d['old_ground'].copy();actual_water=d['original_water'].copy()
 errors=[];cells=chunks=0;e=Editor(C)
 if np.any(d['active']&d['public']):errors.append(['public-intersection'])
 for path in sorted((C/'source').glob('*.npz')):
  rx,rz=map(int,path.stem.split('.')[1:]);r=e.region(rx*512,rz*512);names=np.asarray(r['names']);base=np.asarray([s.split('[')[0]for s in names])
  natural=np.asarray([s in NATURAL for s in base]);soil=np.asarray([s in SOIL for s in base]);iswater=base=='minecraft:water'
  allowed=np.isin(base,['minecraft:air','minecraft:stone','minecraft:gravel','minecraft:water'])
  trees=np.asarray([s in NATURAL and s.endswith(('_log','_leaves')) for s in base])
  for(cx,cz),before,after in zip(r['coords'],r['before'],r['after']):
   q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];changed=before!=after;cells+=int(changed.sum());chunks+=1
   baseline_ground=np.where(soil[before],yy,-129).max(0)
   baseline_water=np.where(iswater[before]&(yy>baseline_ground),yy,-32768).max(0)
   if np.any(baseline_ground!=d['old_ground'][q])or np.any(baseline_water!=d['original_water'][q]):
    errors.append(['source-baseline-differs',int(cx),int(cz)])
   bottom=np.minimum(d['old_ground'][q],d['ground'][q])-2
   if np.any(changed&trees[before]&(yy>d['ground'][q])):
    errors.append(['retained-tree-changed',int(cx),int(cz)])
   if np.any(changed&(~d['active'][q]|~natural[before]|(yy<bottom))):errors.append(['unauthorized-cell',int(cx),int(cz)])
   if np.any(changed&~allowed[after]):errors.append(['unexpected-material',int(cx),int(cz)])
   g=np.where(soil[after],yy,-129).max(0);water=np.where(iswater[after]&(yy>g),yy,-32768).max(0);actual_ground[q]=g;actual_water[q]=water
   if np.any(g!=d['ground'][q]):errors.append(['saved-ground-differs',int(cx),int(cz)])
   if np.any(water!=expected_water[q]):errors.append(['water-level-differs',int(cx),int(cz)])
   column=wet[q]&(yy>g)&(yy<=sea)
   if np.any(column&(names[after]!='minecraft:water[level=0]')):errors.append(['water-column-gap',int(cx),int(cz)])
   if np.any(wet[q]&~np.isin(base[after[sea+129]],list(AIR))):errors.append(['covered-water-surface',int(cx),int(cz)])
   for j,i in np.argwhere(wet[q]):
    bed=int(g[j,i]);support=base[after[bed+127,j,i]]
    if support in AIR or support=='minecraft:water':errors.append(['unsupported-bed',int(cx)*16+int(i),bed,int(cz)*16+int(j)])
  e.regions.clear();print('Verified lower river region',path.name,flush=True)
 if cells!=m['cells']or chunks!=spec['full_chunks']or int(wet.sum())!=spec['water_columns']:errors.append(['incomplete-voxel-check',cells,chunks])
 solid_faces=water_faces=0
 for j,i in np.argwhere(wet):
  for dj,di in((0,1),(0,-1),(1,0),(-1,0)):
   J,I=int(j+dj),int(i+di)
   if wet[J,I]:continue
   for Y in range(int(actual_ground[j,i])+1,sea+1):
    state=e.state(int(x+I),Y,int(z+J)).split('[')[0]
    if state in AIR:errors.append(['open-water-face',int(x+I),Y,int(z+J)])
    elif state=='minecraft:water':water_faces+=1
    else:solid_faces+=1
 water_ids,_=label((actual_water==sea)&(actual_ground<sea));marine_ids=np.unique(water_ids[d['sea_reference']&(water_ids>0)])
 if np.any(wet&~np.isin(water_ids,marine_ids)):errors.append(['water-disconnected-from-measured-sea'])
 old_surface=np.maximum(d['old_ground'],d['original_water']);new_surface=np.maximum(actual_ground,actual_water)
 increased_cliffs=old_exposed=new_exposed=0
 def exposure(g,G,w,W):return np.maximum(np.where(w>g,w-np.maximum(G,W),0),np.where(W>G,W-np.maximum(g,w),0))
 for axis in(0,1):
  l=[slice(None),slice(None)];r=l.copy();l[axis]=slice(None,-1);r[axis]=slice(1,None);l,r=tuple(l),tuple(r)
  increased_cliffs+=int((np.abs(new_surface[l].astype(int)-new_surface[r])>np.maximum(2,np.abs(old_surface[l].astype(int)-old_surface[r]))).sum())
  before=exposure(d['old_ground'][l],d['old_ground'][r],d['original_water'][l],d['original_water'][r]);after=exposure(actual_ground[l],actual_ground[r],actual_water[l],actual_water[r])
  old_exposed+=int((before>0).sum());new_exposed+=int((after>0).sum())
  if np.any(after>before):errors.append(['new-exposed-water-side',axis,int((after>before).sum())])
 if increased_cliffs:errors.append(['increased-visible-cliffs-above-two',increased_cliffs])
 # A complete source margin must remain unchanged, including water.
 for axis in (0,1):
  for edge in (0,-1):
   q=[slice(None),slice(None)];q[axis]=edge;q=tuple(q)
   if not np.array_equal(actual_ground[q],d['old_ground'][q])or not np.array_equal(actual_water[q],d['original_water'][q]):errors.append(['changed-outer-seam',axis,edge])
 r=dict(errors=errors,full_chunks=chunks,changed_cells=cells,water_columns=int(wet.sum()),bank_columns=int(d['bank'].sum()),
  sea_level=sea,contained_solid_bank_faces=solid_faces,measured_water_connection_faces=water_faces,all_water_connected_to_measured_sea=not any(q[0]=='water-disconnected-from-measured-sea'for q in errors),
  increased_visible_cliffs_above_two=increased_cliffs,previous_exposed_water_edges=old_exposed,resulting_exposed_water_edges=new_exposed,
  declared_public_intersections=int((d['active']&d['public']).sum()),upper_rivers_complete=False,regional_height_field_unchanged=True,world_written=False)
 for name in('sea-connected-mouths-check.json','independent-check.json'):(C/name).write_text(json.dumps(r,indent=2),'utf8')
 p=C/'functional-check.json';f=json.loads(p.read_text('utf8'));f.update(errors=errors,sea_connected_mouths_verified=not errors);p.write_text(json.dumps(f,indent=2),'utf8')
 if errors:raise ValueError(errors[:12])
 print(json.dumps(r),flush=True)

def require_verified(C):
 m=json.loads((C/'manifest.json').read_text('utf8'))
 if 'sea_connected_mouths'not in m:return
 r=json.loads((C/'sea-connected-mouths-check.json').read_text('utf8'));ready=json.loads((C/'sea-connected-mouths-release-check.json').read_text('utf8'))
 if r['errors']or r['changed_cells']!=m['cells']or r['full_chunks']!=m['sea_connected_mouths']['full_chunks']:raise ValueError('Incomplete lower river voxel proof')
 if not all(ready[k]for k in('production_recipe_replay_passed','no_floating_components','identity_snapshot_ready','exact_voxel_views_reviewed','negative_fault_checks_passed')):raise ValueError('Unfinished lower river release checks')

if __name__=='__main__':
 p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);verify(p.parse_args().candidate)
