"""Independently read back a natural geographic boundary and all future seams."""
import argparse,json
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from map_pipeline.outer_surface_field import Sampler
from plan_ashi_landscape_r54 import SOIL,NATURAL
from query_blocks import AIR

def verify(a):
    C=a.candidate;m=json.loads((C/'manifest.json').read_text('utf8'));g=m['geographic_boundary']
    with np.load(Path(g['native'])/'native-grid.npz')as f:bounds=f['bounds'];native=f['ground']
    x,z,X,Z=map(int,bounds);zz,xx=np.mgrid[z:Z+1,x:X+1]
    terrain=C/'terrain-inputs';future=Sampler(terrain/'hakone_surface.bin.gz',terrain/'hakone_surface_blend.bin.gz').sample(xx,zz,native)
    previous=Path(g['previous_field']);old=Sampler(previous/'hakone_surface.bin.gz',previous/'hakone_surface_blend.bin.gz').sample(xx,zz,native)
    heights=future[0].copy();waters=np.where(future[0]<future[1],future[1],-32768)
    old_heights=old[0].copy();old_waters=np.where(old[0]<old[1],old[1],-32768)
    e=Editor(C);yy=np.arange(-128,320)[:,None,None];full=np.zeros(native.shape,bool);errors=[];changed_cells=0;chunks=0
    for path in sorted((C/'source').glob('*.npz')):
        rx,rz=map(int,path.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        base=[s.split('[')[0]for s in r['names']];soil=np.array([s in SOIL for s in base]);wet=np.array([s=='minecraft:water'for s in base]);natural=np.array([s in NATURAL for s in base])
        for (cx,cz),before,after in zip(r['coords'],r['before'],r['after']):
            q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];full[q]=True;chunks+=1
            before_ground=np.where(soil[before],yy,-129).max(0);after_ground=np.where(soil[after],yy,-129).max(0)
            before_water=np.where(wet[before]&(yy>before_ground),yy,-32768).max(0);after_water=np.where(wet[after]&(yy>after_ground),yy,-32768).max(0)
            active=(old[0][q]!=future[0][q])|(old_waters[q]!=waters[q])
            if np.any(active&((after_ground!=future[0][q])|(after_water!=waters[q]))):errors.append(['surface',int(cx),int(cz)])
            change=before!=after;changed_cells+=int(change.sum())
            if np.any(change&~natural[before]):errors.append(['foreign-material',int(cx),int(cz)])
            if np.any(change&~active):errors.append(['unchanged-column-edited',int(cx),int(cz)])
            heights[q]=after_ground;waters[q]=after_water;old_heights[q]=before_ground;old_waters[q]=before_water
        e.regions.clear();print('Verified saved boundary',path.name,'chunks',chunks,flush=True)
    if chunks!=g['full_chunks']or changed_cells!=m['cells']:errors.append(['incomplete-voxel-review',chunks,changed_cells])
    exposed=0;new_steep=[];maximum=[];core_maximum=[]
    core=(xx>=4384)&(xx<=4512)&(zz>=-1328)&(zz<=1600)
    for axis in (0,1):
        l=[slice(None),slice(None)];r=l.copy();l[axis]=slice(None,-1);r[axis]=slice(1,None);l,r=tuple(l),tuple(r)
        h,H,w,W=heights[l],heights[r],waters[l],waters[r]
        exposure=np.maximum(np.where(w>h,w-np.maximum(H,W),0),np.where(W>H,W-np.maximum(h,w),0))
        exposed+=int((exposure>0).sum())
        step=np.abs(h.astype(int)-H);previous_step=np.abs(old_heights[l].astype(int)-old_heights[r])
        for j,i in np.argwhere((step>8)&(step>previous_step)):new_steep.append([int(x+i),int(z+j),axis,int(step[j,i]),int(previous_step[j,i])])
        maximum.append(int(step.max()));core_maximum.append(int(step[core[l]&core[r]].max()))
        for i in (0,-1):
            s=[slice(None),slice(None)];s[axis]=i;s=tuple(s)
            if not(np.array_equal(heights[s],old_heights[s])and np.array_equal(waters[s],old_waters[s])):errors.append(['outer-seam',axis,i])
    if exposed:errors.append(['exposed-water-edges',exposed])
    if new_steep:errors.append(['increased-native-cliffs',new_steep[:20]])
    report=dict(errors=errors,full_chunks=chunks,changed_cells=changed_cells,future_columns=int(native.size),
        missing_chunks=int((~full).sum()/256),exposed_water_edges=exposed,maximum_adjacent_steps=maximum,
        commissioned_core_maximum_steps=core_maximum,newly_increased_steps_above8=len(new_steep),outer_seams_exact=not any(r[0]=='outer-seam'for r in errors),
        natural_saved_ownership_exact=not any(r[0]in('foreign-material','unchanged-column-edited')for r in errors),world_written=False)
    (C/'geographic-boundary-check.json').write_text(json.dumps(report,indent=2),'utf8')
    p=C/'functional-check.json';check=json.loads(p.read_text('utf8'));check['errors']=errors;check['geographic_boundary_verified']=not errors
    check['production_recipe_replay_required']=True;p.write_text(json.dumps(check,indent=2),'utf8')
    if errors:raise ValueError(errors[:12])
    print(json.dumps(report),flush=True)

def require_verified(candidate):
    m=json.loads((candidate/'manifest.json').read_text('utf8'))
    if 'geographic_boundary'not in m:return
    r=json.loads((candidate/'geographic-boundary-check.json').read_text('utf8'))
    if r['errors']or r['changed_cells']!=m['cells']or r['full_chunks']!=m['geographic_boundary']['full_chunks']:
        raise ValueError('Incomplete geographic boundary verification')
    ready=json.loads((candidate/'geographic-release-check.json').read_text('utf8'))
    if not all(ready[k]for k in('production_recipe_replay_passed','complete_runtime_vectors_passed','no_floating_components','identity_snapshot_ready')):
        raise ValueError('Geographic boundary release checks are incomplete')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);verify(p.parse_args())
