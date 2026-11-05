"""Verify exact coastal voxel ownership, water levels, slopes and public land."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import label,distance_transform_edt
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL,SOIL
from query_blocks import AIR

def inspect_water_sides(editor,bounds,ground,water,original=False):
    """Resolve soil-height suspects against actual water and full side blocks.

    A retained structural column is not missing ground. Unknown non-cubic
    materials remain unresolved rather than being treated as a sealed bank.
    """
    x,z,X,Z=map(int,bounds);h,width=ground.shape;opened=set();unknown=set();contained=0;rows=[]
    full_blocks=SOIL|{'projectseele:nerv_structural_panel','projectseele:nerv_floor_panel'}
    for dz,dx in ((0,1),(0,-1),(1,0),(-1,0)):
        l=(slice(max(0,-dz),h-max(0,dz)),slice(max(0,-dx),width-max(0,dx)))
        r=(slice(max(0,dz),h-max(0,-dz)),slice(max(0,dx),width-max(0,-dx)))
        suspect=(water[l]>ground[l])&(water[l]>np.maximum(ground[r],water[r]))
        for J,I in np.argwhere(suspect):
            j=int(J+l[0].start);i=int(I+l[1].start);jj,ii=j+dz,i+dx;bad=[];unresolved=[];materials=set()
            low=max(int(ground[j,i]),int(ground[jj,ii]),int(water[jj,ii]))
            for y in range(low+1,int(water[j,i])+1):
                if editor.state(x+i,y,z+j,original=original).split('[')[0]!='minecraft:water':continue
                state=editor.state(x+ii,y,z+jj,original=original).split('[')[0];key=(x+i,y,z+j,dx,dz)
                materials.add(state)
                if state in AIR|{'minecraft:light','minecraft:structure_void'}:opened.add(key);bad.append(y)
                elif state not in full_blocks|{'minecraft:water'}:unknown.add(key);unresolved.append(y)
            sealed=not bad and not unresolved;contained+=int(sealed)
            rows.append(dict(water_xz=[x+i,z+j],side_xz=[x+ii,z+jj],open_heights=bad,
                unresolved_heights=unresolved,side_materials=sorted(materials),contained=sealed))
    editor.regions.clear()
    return opened,unknown,contained,rows

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
    # Independently reconstruct the geographical and physical exclusions;
    # the candidate's blocked bitmap alone is not evidence of ownership.
    zz,xx=np.mgrid[z:Z+1,x:X+1];port_buffer=int(spec.get('retained_port_buffer_blocks',32))
    if not 0<=port_buffer<=32:errors.append(['invalid-port-buffer'])
    port=(xx>=3040-port_buffer)&(xx<=3360+port_buffer)&(zz>=960-port_buffer)&(zz<=1216+port_buffer)
    if np.any(d['active']&port):errors.append(['retained-port-intersection'])
    cap=json.loads((Path(spec['source'])/'capture.json').read_text('utf8'))
    for actor in cap['actors']:
        px,_,pz=actor['pos']
        if np.any(d['active']&(abs(xx-px)<=64)&(abs(zz-pz)<=64)):errors.append(['retained-actor-intersection'])
    with np.load(Path(spec['programme'])/'watercourse-reference.npz')as f:
        ox,oz,oX,oZ=map(int,f['bounds']);river=f['river'][z-oz:Z-oz+1,x-ox:X-ox+1]
    if np.any(d['active']&(distance_transform_edt(~river)<=spec['river_mouth_buffer_blocks'])):
        errors.append(['retained-river-intersection'])
    edge=np.minimum.reduce([xx-x,X-xx,zz-z,Z-zz])
    if np.any(d['active']&(edge<spec['source_edge_guard_blocks'])):errors.append(['retained-source-edge-intersection'])
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
            if not np.array_equal(actual[q],d['old_ground'][q])or not np.array_equal(actual_water[q],old_water[q]):
                errors.append(['changed-outer-seam',axis,edge])
    if new_steps:errors.append(['new-increased-cliffs-above-two',new_steps])
    if new_exposed:errors.append(['new-exposed-water-faces',new_exposed])
    old_open,old_unknown,old_contained,old_sides=inspect_water_sides(e,d['bounds'],d['old_ground'],old_water,original=True)
    new_open,new_unknown,contained,side_rows=inspect_water_sides(e,d['bounds'],actual,actual_water)
    if new_open-old_open:errors.append(['new-actual-water-side-gap',len(new_open-old_open)])
    if new_unknown-old_unknown:errors.append(['new-unresolved-water-side',len(new_unknown-old_unknown)])
    (C/'actual-water-side-review.json').write_text(json.dumps(dict(before=old_sides,after=side_rows),indent=2),'utf8')
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
        actual_open_water_side_cells=len(new_open),previous_actual_open_water_side_cells=len(old_open),
        actual_open_water_edges=sum(bool(r['open_heights'])for r in side_rows),
        actual_unresolved_water_side_cells=len(new_unknown),structurally_contained_candidate_edges=contained,
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
