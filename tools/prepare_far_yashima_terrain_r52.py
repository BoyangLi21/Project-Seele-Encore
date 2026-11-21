"""Exact Root far-ridge terrain, whole native tree retirement and supported planting."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse,json,math
from collections import Counter
import numpy as np
from scipy.ndimage import label
from scipy.spatial import cKDTree
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    out=BASE/'far_yashima';stage='far_ridge_native_blend';assert not list((out/stage).glob('applied_*'))
    data=np.load(out/'RIDGE_HEIGHTS.npz');origin=data['origin'];active=data['active'];zz,xx=np.where(active)
    a=max(0,int(xx.min())-16);A=min(active.shape[1]-1,int(xx.max())+16);b=max(0,int(zz.min())-16);B=min(active.shape[0]-1,int(zz.max())+16)
    lo=(int(origin[0]+a),32,int(origin[1]+b));hi=(int(origin[0]+A),223,int(origin[1]+B))
    old_height=data['before'][b:B+1,a:A+1];height=data['after'][b:B+1,a:A+1];active=active[b:B+1,a:A+1]
    before,names=measure(lo,hi);after=before.copy()
    for s in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:oak_log[axis=y]','minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)}
    soil=np.array([s.split('[')[0]in('minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand','minecraft:sandstone','minecraft:clay')for s in names])
    actual_height=np.full(height.shape,-32768,np.int16)
    for iy in range(before.shape[0]):actual_height=np.where(soil[before[iy]],iy+lo[1],actual_height)
    assert np.array_equal(actual_height,old_height),'Native terrain changed since ridge selection'
    assert not list(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi))
    # Assign actual leaves to their nearest original trunk. Whole touched log
    # components and only their crowns are retired; adjoining trees keep roots.
    log_ids=[i for i,s in enumerate(names)if s.split('[')[0].endswith('_log')]
    leaf_ids=[i for i,s in enumerate(names)if s.split('[')[0].endswith('_leaves')]
    logs=np.isin(before,log_ids);labels,n=label(logs);log_points=np.argwhere(logs)
    touched=set(map(int,np.unique(labels[:,active])))-{0};removed_logs=0;removed_leaves=0
    if len(log_points):
        owners=labels[tuple(log_points.T)];tree=cKDTree(log_points)
        for owner in touched:
            points=log_points[owners==owner];assert points[:,1].min()>0 and points[:,1].max()<before.shape[1]-1 and points[:,2].min()>0 and points[:,2].max()<before.shape[2]-1,'Touched trunk leaves context'
            after[tuple(points.T)]=ids['minecraft:air'];removed_logs+=len(points)
        for iy in range(before.shape[0]):
            zs,xs=np.where(np.isin(before[iy],leaf_ids))
            if not len(xs):continue
            points=np.column_stack([np.full(len(xs),iy),zs,xs]);dist,near=tree.query(points,p=1)
            remove=np.isin(owners[near],list(touched))
            after[iy,zs[remove],xs[remove]]=ids['minecraft:air'];removed_leaves+=int(remove.sum())
    del labels,logs,log_points
    changed_states=Counter()
    for iy in range(before.shape[0]):
        y=iy+lo[1];mask=active&(y>=old_height-3)&(y<=height)
        target=np.where(y==height,ids['minecraft:grass_block[snowy=false]'],np.where(y>=height-3,ids['minecraft:dirt'],ids['minecraft:stone']))
        after[iy,mask]=target[mask]
        # Future low plants cannot remain buried in a replaced surface.
        plants=np.isin(after[iy],[i for i,s in enumerate(names)if s.split('[')[0]in('minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:snow','minecraft:dandelion','minecraft:poppy')])
        after[iy,active&plants&(y>height)]=ids['minecraft:air']
    # Sparse complete oak trees cover new slopes while both assembly areas,
    # the city-facing gun line and all declared paths remain physically clear.
    design=json.loads((out/'RIDGE_DESIGN.json').read_text('utf8'));centre=np.array(design['centre_xz']);f=np.array(design['forward_xz']);right=np.array(design['right_xz']);rng=np.random.default_rng(52);planted=[]
    for x in range(lo[0]+8,hi[0]-8,17):
        for z in range(lo[2]+8,hi[2]-8,17):
            x1=x+int(rng.integers(-4,5));z1=z+int(rng.integers(-4,5));iz,ix=z1-lo[2],x1-lo[0]
            if not active[iz,ix]:continue
            uv=np.array([x1,z1])-centre;u=float(uv@right);v=float(uv@f)
            if (u/137)**2+((v+2)/153)**2<1 or v>75 and abs(u)<55:continue
            top=int(height[iz,ix]);local=height[iz-3:iz+4,ix-3:ix+4]
            if int(local.max()-local.min())>8 or rng.random()<.25:continue
            trunk=int(rng.integers(6,10));cy=top+trunk
            if cy+2>hi[1]:continue
            # Never cut remaining native trees to fit new trees.
            check=after[top+1-lo[1]:cy+3-lo[1],iz-3:iz+4,ix-3:ix+4]
            if np.any(~np.isin(check,[ids['minecraft:air']])):continue
            for dy,radius in ((-3,3),(-2,3),(-1,2),(0,2),(1,1)):
                for dz in range(-radius,radius+1):
                    for dx in range(-radius,radius+1):
                        if dx*dx+dz*dz>radius*radius+1:continue
                        after[cy+dy-lo[1],iz+dz,ix+dx]=ids['minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]']
            after[top+1-lo[1]:cy+1-lo[1],iz,ix]=ids['minecraft:oak_log[axis=y]'];planted.append([x1,top+1,z1,trunk])
    for iy in range(before.shape[0]):
        for value,count in zip(*np.unique(before[iy][before[iy]!=after[iy]],return_counts=True)):changed_states[names[int(value)]]+=int(count)
    assert all(s.startswith('minecraft:')and not any(t in s for t in('concrete','bricks','planks','rail','barrier','iron_block'))for s in changed_states),dict(changed_states)
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
    changed=runs(p,lo,before,after,names,'R52_far_native_mountain_and_whole_trees');p.meta.update(root_author=True,site_design=design,playable=False)
    plan=p.save_plan(stage);report=dict(world_written=False,changed_cells=changed,changed_columns=int(active.sum()),bounds=[lo,hi],removed_complete_native_trunks=len(touched),removed_log_cells=removed_logs,removed_owned_leaf_cells=removed_leaves,new_complete_trees=len(planted),existing_construction_overwritten=False,soil_height_exact=True,pending=['actual cannon/supply/control construction','native sightline and landing/aiming'])
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');(plan/'NEW_TREES.json').write_text(json.dumps(planted),'utf8');print(json.dumps(report),flush=True)
    if args.apply:
        receipt=p.apply(stage);actual,pal=measure(lo,hi);assert np.array_equal(np.array([ids[s]for s in pal],np.uint16)[actual],after)
        report.update(world_written=True,receipt=receipt,whole_surface_exact_readback=True);(plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
