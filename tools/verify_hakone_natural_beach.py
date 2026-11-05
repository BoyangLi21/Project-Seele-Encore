"""Verify exact coastal voxel ownership, water levels, slopes and public land."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import label
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL,SOIL

def verify(C):
    m=json.loads((C/'manifest.json').read_text('utf8'));spec=m['natural_beach']
    with np.load(C/'beach-design.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);e=Editor(C);yy=np.arange(-128,320)[:,None,None];errors=[];cells=chunks=0
    actual=d['old_ground'].copy();actual_water=d['water'].copy()
    old_water=d.get('original_water',d['water'])
    marine_voids=d.get('marine_voids',np.zeros(d['active'].shape,bool));sea=int(spec['original_sea_level_retained'])
    if int(marine_voids.sum())!=spec.get('marine_void_columns',0):errors.append(['marine-void-count'])
    if marine_voids.any():
        if np.any(marine_voids&(~d['active']|~d['sea_reference']|(old_water!=-32768)|(d['old_ground']>=sea)|(d['water']!=sea))):
            errors.append(['unauthorized-marine-void'])
        with np.load(Path(spec['programme'])/'watercourse-reference.npz')as source_reference:
            sx,sz,sX,sZ=map(int,source_reference['bounds'])
            reference_sea=source_reference['sea'][z-sz:Z-sz+1,x-sx:X-sx+1]
        if not np.array_equal(reference_sea,d['sea_reference']):errors.append(['marine-reference-differs'])
    if np.any((d['water']!=old_water)&~marine_voids):errors.append(['undeclared-water-change'])
    if np.any(d['active']&(d['blocked']|d['public'])):errors.append(['protected-column-in-authoring-scope'])
    if int(d['active'].sum())!=spec['active_columns']:errors.append(['active-column-count'])
    for path in sorted((C/'source').glob('*.npz')):
        rx,rz=map(int,path.stem.split('.')[1:]);r=e.region(rx*512,rz*512);base=[s.split('[')[0]for s in r['names']]
        natural=np.asarray([s in NATURAL for s in base]);soil=np.asarray([s in SOIL for s in base]);wet=np.asarray([s=='minecraft:water'for s in base])
        authored=np.asarray([s in {'minecraft:air','minecraft:stone','minecraft:gravel','minecraft:sand','minecraft:water'}for s in base])
        trees=np.asarray([s in NATURAL and s.endswith(('_log','_leaves'))for s in base])
        for(cx,cz),before,after in zip(r['coords'],r['before'],r['after']):
            q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];chunks+=1;delta=before!=after;cells+=int(delta.sum())
            original_ground=np.where(soil[before],yy,-129).max(0)
            original_surface_water=np.where(wet[before]&(yy>original_ground),yy,-32768).max(0)
            if not np.array_equal(original_ground,d['old_ground'][q])or not np.array_equal(original_surface_water,old_water[q]):
                errors.append(['source-baseline-differs',int(cx),int(cz)])
            bottom=np.minimum(d['old_ground'][q],d['ground'][q])-3
            if np.any(delta&(~d['active'][q]|~natural[before]|(yy<bottom))):errors.append(['unauthorized-cell',int(cx),int(cz)])
            if np.any(delta&~authored[after]):errors.append(['unexpected-authored-material',int(cx),int(cz)])
            if spec.get('retained_tree_vegetation')and np.any(delta&trees[before]&(yy>d['ground'][q])):
                errors.append(['retained-tree-changed',int(cx),int(cz)])
            ground=np.where(soil[after],yy,-129).max(0);water=np.where(wet[after]&(yy>ground),yy,-32768).max(0)
            if np.any(ground!=d['ground'][q]):errors.append(['saved-ground-differs',int(cx),int(cz)])
            if np.any(water!=d['water'][q]):errors.append(['retained-water-level-changed',int(cx),int(cz)])
            if np.any(marine_voids[q]&(yy>ground)&(yy<=d['water'][q])&~wet[after]):
                errors.append(['marine-water-column-gap',int(cx),int(cz)])
            actual[q]=ground;actual_water[q]=water
        e.regions.clear();print('Verified coastal region',path.name,flush=True)
    if cells!=m['cells']or chunks!=spec['full_chunks']:errors.append(['incomplete-voxel-review',cells,chunks])
    new_steps=new_exposed=old_exposed=after_exposed=0;maximum=[]
    def exposure(h,H,w,W):return np.maximum(np.where(w>h,w-np.maximum(H,W),0),np.where(W>H,W-np.maximum(h,w),0))
    for axis in(0,1):
        l=[slice(None),slice(None)];r=l.copy();l[axis]=slice(None,-1);r[axis]=slice(1,None);l,r=tuple(l),tuple(r)
        soilstep=np.abs(actual[l].astype(int)-actual[r]);maximum.append(int(soilstep.max()))
        crossing=((d['water'][l]>actual[l])!=(d['water'][r]>actual[r]))|((old_water[l]>d['old_ground'][l])!=(old_water[r]>d['old_ground'][r]))
        P=np.where(crossing,np.maximum(actual[l],actual_water[l]),actual[l]);Q=np.where(crossing,np.maximum(actual[r],actual_water[r]),actual[r])
        oldP=np.where(crossing,np.maximum(d['old_ground'][l],old_water[l]),d['old_ground'][l]);oldQ=np.where(crossing,np.maximum(d['old_ground'][r],old_water[r]),d['old_ground'][r])
        step=np.abs(P.astype(int)-Q);oldstep=np.abs(oldP.astype(int)-oldQ);new_steps+=int((step>np.maximum(2,oldstep)).sum())
        old=exposure(d['old_ground'][l],d['old_ground'][r],old_water[l],old_water[r]);new=exposure(actual[l],actual[r],actual_water[l],actual_water[r])
        new_exposed+=int((new>old).sum());old_exposed+=int((old>0).sum());after_exposed+=int((new>0).sum())
        for edge in (0,-1):
            q=[slice(None),slice(None)];q[axis]=edge;q=tuple(q)
            if not np.array_equal(actual[q],d['old_ground'][q]):errors.append(['changed-outer-seam',axis,edge])
    if new_steps:errors.append(['new-increased-cliffs-above-two',new_steps])
    if new_exposed:errors.append(['new-exposed-water-faces',new_exposed])
    checked_void_sides=0
    if marine_voids.any():
        ids,_=label((actual_water==sea)&(actual<sea))
        ocean_ids=np.unique(ids[(old_water==sea)&d['sea_reference']]);ocean_ids=ocean_ids[ocean_ids>0]
        if np.any(marine_voids&~np.isin(ids,ocean_ids)):errors.append(['marine-void-not-sea-connected'])
        side_editor=Editor(C)
        for j,i in np.argwhere(marine_voids):
            px,pz=int(x+i),int(z+j)
            for height in range(int(actual[j,i])+1,sea+1):
                for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                    state=side_editor.state(px+dx,height,pz+dz).split('[')[0]
                    checked_void_sides+=1
                    if state not in SOIL|{'minecraft:water'}:errors.append(['marine-void-side-gap',px+dx,height,pz+dz])
        side_editor.regions.clear()
    report=dict(errors=errors,full_chunks=chunks,changed_cells=cells,active_columns=spec['active_columns'],wet_columns=spec['wet_columns'],dry_columns=spec['dry_columns'],
        new_increased_cliffs_above_two=new_steps,maximum_adjacent_ground_steps=maximum,new_exposed_water_edges=new_exposed,
        slope_comparison='soil within wet/dry zones; visible surfaces at wet/dry boundaries',
        previous_exposed_water_edges=old_exposed,resulting_exposed_water_edges=after_exposed,
        all_original_surface_water_levels_equal=bool(np.array_equal(actual_water[old_water>d['old_ground']],old_water[old_water>d['old_ground']])),
        original_dry_columns_changed_to_sea=int(marine_voids.sum()),declared_water_map_exact=bool(np.array_equal(actual_water,d['water'])),marine_void_side_cells_checked=checked_void_sides,
        declared_public_column_intersections=int((d['active']&d['public']).sum()),natural_ownership_only=not any(r[0]=='unauthorized-cell'for r in errors),
        minimum_ground_delta=int((actual-d['old_ground']).min()),maximum_ground_delta=int((actual-d['old_ground']).max()),world_written=False)
    for name in('natural-beach-check.json','independent-check.json'):(C/name).write_text(json.dumps(report,indent=2),'utf8')
    p=C/'functional-check.json';r=json.loads(p.read_text('utf8'));r['errors']=errors;r['natural_beach_verified']=not errors;p.write_text(json.dumps(r,indent=2),'utf8')
    if errors:raise ValueError(errors[:12])
    print(json.dumps(report),flush=True)

def require_verified(C):
    m=json.loads((C/'manifest.json').read_text('utf8'))
    if 'natural_beach'not in m:return
    r=json.loads((C/'natural-beach-check.json').read_text('utf8'));ready=json.loads((C/'natural-beach-release-check.json').read_text('utf8'))
    if r['errors']or r['changed_cells']!=m['cells']or r['full_chunks']!=m['natural_beach']['full_chunks']:raise ValueError('Incomplete natural coast verification')
    if not all(ready[k]for k in('production_recipe_replay_passed','no_floating_components','identity_snapshot_ready','exact_voxel_views_reviewed','negative_fault_checks_passed')):raise ValueError('Unfinished natural coast release checks')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);verify(p.parse_args().candidate)
