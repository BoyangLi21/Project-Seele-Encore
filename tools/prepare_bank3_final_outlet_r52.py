"""Install only the final parallel bank-three civil from measured full meshes.

Root owns this map change. Old rejected fan layouts never feed this stage.
No runtime readiness or visual acceptance follows from the block readback.
"""
import argparse,json,hashlib
from collections import defaultdict,Counter
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from prepare_terminal_move_r52 import runs
from query_blocks import iter_selected_sections,iter_block_entities
from survey_r52_original_complex import measure
from scipy.ndimage import label


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    out=BASE/'bank3_outlet_final';stage='final_parallel_full_assembly_civil'
    assert not list((out/stage).glob('applied_*')),'Already installed; never replay'
    source=out/'SECTION_SOURCE.npz';data=np.load(source)
    design=json.loads((out/'DESIGN.json').read_text('utf8'))
    assert design['source_measurement_complete'] and design['missing_chunks']==0
    assert all(r['body_roots'][0][2]==-781.5 for r in design['routes'])
    keys=data['section_keys'];before=data['before'];names=list(map(str,data['palette']))
    for name in ('minecraft:air','projectseele:nerv_shaft_panel','projectseele:nerv_machine_edge','projectseele:nerv_strip_light[lit=true]'):
        if name not in names:names.append(name)
    ids={s:i for i,s in enumerate(names)};after=before.copy();local=np.indices((16,16,16)).reshape(3,-1).T[:,[2,0,1]]
    selected=defaultdict(set);lookup={}
    for i,(cx,cz,sy) in enumerate(keys):selected[int(cx),int(cz)].add(int(sy));lookup[int(cx),int(cz),int(sy)]=i
    # The plan uses the immutable measured source. apply() independently
    # enforces every exact old-state run before writing the affected region.
    count=Counter();surface_plants=set();wood_hits=[]
    for i,(cx,cz,sy) in enumerate(keys):
        xyz=local+[cx*16,sy*16,cz*16];x,y,z=xyz.T
        core=data['core'][i];shell=data['shell'][i]
        # Carry the sealed lining only to the surface foundation. The model
        # sweep above grade is a clearance check, never an above-ground tower.
        below=shell&(y<=67);after[i,below]=ids['projectseele:nerv_shaft_panel']
        rib=below&~core&((y%24)==0);after[i,rib]=ids['projectseele:nerv_machine_edge']
        # All channels share the same restrained structural palette. Embedded
        # lighting sits in the shell, outside the actual swept clearance.
        light=below&~core&(y%24==1)&(x%12==0)&(z%12==0)
        after[i,light]=ids['projectseele:nerv_strip_light[lit=true]']
        after[i,core]=ids['minecraft:air']
        old=before[i]
        # Preserve the source loading gallery, gates and original mechanisms.
        keep=(y<=-584)&(x>=-54)&(x<=108)&(z>=-800)&(z<=-348)
        keep|=np.isin(old,[j for j,s in enumerate(names)if s in ('minecraft:barrier','minecraft:structure_void')])
        after[i,keep]=old[keep]
        altered=old!=after[i]
        wood=np.isin(old,[j for j,s in enumerate(names)if '_log['in s or '_leaves['in s])
        wood_hits.extend(map(tuple,xyz[altered&wood]))
        for value,n in zip(*np.unique(old[altered],return_counts=True)):count[names[int(value)]]+=int(n)
        for value in np.unique(old[altered&(y>=0)]):surface_plants.add(names[int(value)])
        # Glazed personnel galleries are outside the new bore, not collateral.
        glass=np.isin(old,[j for j,s in enumerate(names)if 'glass'in s])
        assert not np.any(altered&glass),('A personnel window would be overwritten',cx,cz,sy)
    # Refuse a surface tree before its complete component is measured.
    assert not any('_log'in s or '_leaves'in s for s in surface_plants),surface_plants
    extra=[];whole_trees=[]
    if wood_hits:
        w=np.array(wood_hits);lo=tuple(map(int,w.min(0)-[9,12,9]));hi=tuple(map(int,w.max(0)+[9,12,9]))
        trees,pal=measure(lo,hi)
        for s in pal:
            if s not in ids:ids[s]=len(names);names.append(s)
        wood=np.isin(trees,[i for i,s in enumerate(pal)if '_log['in s or '_leaves['in s]);labels,_=label(wood)
        groups={int(labels[y-lo[1],z-lo[2],x-lo[0]])for x,y,z in wood_hits}
        for group in groups:
            assert group>0
            yy,zz,xx=np.where(labels==group)
            assert xx.min()>0 and xx.max()<trees.shape[2]-1 and yy.min()>0 and yy.max()<trees.shape[0]-1 and zz.min()>0 and zz.max()<trees.shape[1]-1,'Tree leaves bounded survey'
            for ix,iy,iz in zip(xx,yy,zz):
                x,y,z=int(ix+lo[0]),int(iy+lo[1]),int(iz+lo[2]);i=lookup.get((x//16,z//16,y//16));j=(y%16)*256+(z%16)*16+x%16
                old=ids[pal[int(trees[iy,iz,ix])]]
                if i is not None:
                    assert before[i,j]==old
                    if after[i,j]==old:after[i,j]=ids['minecraft:air']
                else:extra.append(((x,y,z),old,ids['minecraft:air']))
            whole_trees.append(dict(cells=len(xx),bounds=[[int(xx.min()+lo[0]),int(yy.min()+lo[1]),int(zz.min()+lo[2])],[int(xx.max()+lo[0]),int(yy.max()+lo[1]),int(zz.max()+lo[2])]]))
    bounds=[np.min(keys[:,[0,2,1]]*16,axis=0),np.max(keys[:,[0,2,1]]*16+15,axis=0)]
    devices=dict(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',*bounds,selected_chunks=selected))
    for (x,y,z),tag in devices.items():
        i=lookup.get((x//16,z//16,y//16))
        if i is not None:
            j=(y%16)*256+(z%16)*16+x%16
            assert before[i,j]==after[i,j],('Original device intersects bore',(x,y,z),str(tag['id']))
    allowed_minecraft={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone','minecraft:deepslate[axis=y]','minecraft:deepslate','minecraft:bedrock','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:sand','minecraft:gravel','minecraft:water[level=0]','minecraft:grass','minecraft:fern','minecraft:large_fern[half=lower]','minecraft:large_fern[half=upper]','minecraft:tall_grass[half=lower]','minecraft:tall_grass[half=upper]','minecraft:polished_basalt[axis=y]','minecraft:ladder[facing=south,waterlogged=false]','minecraft:black_concrete','minecraft:sea_lantern','minecraft:iron_block'}
    assert all(s.startswith('projectseele:nerv_')or s in allowed_minecraft or '_log['in s or '_leaves['in s for s in count),dict(count)
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
    changed=0
    for i,(cx,cz,sy) in enumerate(keys):
        changed+=runs(p,(int(cx)*16,int(sy)*16,int(cz)*16),before[i].reshape(16,16,16),after[i].reshape(16,16,16),names,'R52_final_parallel_bank3_bore')
    for pos,old,new in extra:p.exact((*pos,*pos),names[old],names[new],'R52_complete_bore_tree_retirement');changed+=1
    p.meta.update(root_author=True,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),routes=design['routes'],surface_floor_y=68,lining_stops_at_y=67,pressure_planes_retained=True,playable=False)
    plan=p.save_plan(stage)
    report=dict(world_written=False,changed_cells=changed,sections=len(keys),old_states_changed=count,original_device_cells_untouched=len(devices),surface_obstacles=sorted(surface_plants),complete_retired_trees=whole_trees,source_sha256=p.meta['source_sha256'],surface_floor_y=68,above_grade_lining_cells=0,pending=['founded surface receivers','real guide and door installation','full native transport commissioning'])
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');np.savez_compressed(plan/'EXPECTED.npz',section_keys=keys,after=after,palette=names)
    print(json.dumps(report),flush=True)
    if args.apply:
        receipt=p.apply(stage);checked=0
        for cx,cz,sy,pal,values in iter_selected_sections(vox.WORLD,vox.DIM,selected):
            i=lookup[cx,cz,sy];actual=np.asarray([ids[s]for s in pal],np.uint16)[values]
            assert np.array_equal(actual,after[i]),('Readback mismatch',cx,cz,sy);checked+=1
        assert checked==len(keys)
        report.update(world_written=True,receipt=receipt,all_sections_exact_readback=True)
        (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
