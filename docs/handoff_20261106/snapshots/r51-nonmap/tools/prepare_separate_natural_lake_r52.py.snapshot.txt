"""Root-authored distant lake, separated from the HQ engineered reservoir."""
import argparse,json,msvcrt
from pathlib import Path
import numpy as np
from scipy.ndimage import label,generate_binary_structure
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from prepare_west_reservoir_r52 import smooth
from extend_world_depth_r52 import acquire_world_lock
from query_blocks import iter_block_entities
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    base=args.base.resolve();world=base/'WORLD';lo=(-1430,-525,365);hi=(-850,-440,835)
    assert (base/'BASELINE.json').is_file()
    survey.WORLD=extension.WORLD=world
    file=base/'lake_survey/distant_natural_final_footprint.npz';file.parent.mkdir(exist_ok=True)
    if file.exists():
        s=np.load(file);before=s['states'];names=list(map(str,s['palette']))
    else:
        before,names=measure(lo,hi);np.savez_compressed(file,origin=lo,states=before,palette=names)
    names=list(names)
    for v in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]',
              'minecraft:gravel','minecraft:sand','minecraft:water[level=0]'):
        if v not in names:names.append(v)
    ids={v:i for i,v in enumerate(names)};yy,zz,xx=np.ogrid[:before.shape[0],:before.shape[1],:before.shape[2]]
    x,y,z=xx+lo[0],yy+lo[1],zz+lo[2]
    rho=np.sqrt(((x+1140)/220.)**2+((z-600)/170.)**2)
    angle=np.arctan2((z-600)/170.,(x+1140)/220.)
    rho=rho/(1+.055*np.sin(3*angle)+.035*np.sin(5*angle+.6))
    claimed_xy=(rho<=1.20)[0]
    assert not list(iter_block_entities(world,'projectseele:geofront',lo,hi)), 'A full fixture must be protected, not removed for landscaping'
    natural={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone','minecraft:dirt','minecraft:grass_block',
        'minecraft:water','minecraft:gravel','minecraft:sand','minecraft:clay','minecraft:coarse_dirt','minecraft:tuff','minecraft:podzol',
        'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:azure_bluet','minecraft:poppy','minecraft:dandelion',
        'minecraft:oak_log','minecraft:oak_leaves','minecraft:birch_log','minecraft:birch_leaves'}
    assert all(names[int(v)].split('[')[0] in natural for v in np.unique(before[:,claimed_xy])),'Authored structure in explicit far lake footprint'
    solid_ids=[i for i,s in enumerate(names) if s.split('[')[0] in natural-{'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:water',
        'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:azure_bluet','minecraft:poppy','minecraft:dandelion',
        'minecraft:oak_log','minecraft:oak_leaves','minecraft:birch_log','minecraft:birch_leaves'}]
    natural_solid=np.isin(before,solid_ids)
    old_ground=np.max(np.where(natural_solid,y,-2000),axis=0)
    assert np.all(old_ground[claimed_xy]>lo[1]),'Survey did not reach all original lake-footprint soil'
    r=rho[0];bottom=np.floor(-505+32*smooth((r-.15)/.85)).astype(int)
    shore=np.floor(-472*(1-smooth((r-1)/.20))+old_ground*smooth((r-1)/.20)).astype(int)
    target_ground=np.where(r<=1,bottom,shore)
    after=before.copy()
    # Retire only whole connected original tree components intersecting the
    # explicitly graded footprint; do not leave underwater trunks or stumps.
    trees=np.isin(before,[i for i,s in enumerate(names) if s.split('[')[0].endswith(('_log','_leaves'))])
    components,total=label(trees,generate_binary_structure(3,1))
    touched=np.unique(components[:,claimed_xy]);touched=touched[touched!=0]
    cleared_trees=np.isin(components,touched)&trees
    assert not (np.any(cleared_trees[0]) or np.any(cleared_trees[-1]) or np.any(cleared_trees[:,0,:]) or np.any(cleared_trees[:,-1,:]) or np.any(cleared_trees[:,:,0]) or np.any(cleared_trees[:,:,-1])), 'Tree component crosses measured footprint'
    after[cleared_trees]=ids['minecraft:air']
    for iy,world_y in enumerate(range(lo[1],hi[1]+1)):
        submerged=r<1
        values=np.where(world_y>target_ground,np.where(submerged&(world_y<=-473),ids['minecraft:water[level=0]'],ids['minecraft:air']),
            np.where(world_y==target_ground,np.where(submerged,ids['minecraft:gravel'],ids['minecraft:grass_block[snowy=false]']),
            np.where(world_y>=target_ground-3,np.where(submerged,ids['minecraft:sand'],ids['minecraft:dirt']),ids['minecraft:stone'])))
        after[iy][claimed_xy]=values[claimed_xy]
    current,cp=measure(lo,hi);assert np.array_equal(np.asarray(names)[before],np.asarray(cp)[current]),'Far lake source changed'
    air_ids=[i for i,n in enumerate(names) if n in ('minecraft:air','minecraft:cave_air','minecraft:void_air')]
    water_owned=(after==ids['minecraft:water[level=0]'])&np.broadcast_to((r<1)[None,:,:],after.shape)
    for dy,dz,dx in ((0,0,1),(0,0,-1),(0,1,0),(0,-1,0),(-1,0,0)):
        aa=tuple(slice(max(0,-q),min(n,n-q)) for n,q in zip(after.shape,(dy,dz,dx)))
        bb=tuple(slice(max(0,q),min(n,n+q)) for n,q in zip(after.shape,(dy,dz,dx)))
        assert not (water_owned[aa]&np.isin(after[bb],air_ids)).any(),'Natural basin has an open underwater face'
    # The original hive at -833,-476,597 lies beyond this whole component and
    # remains unchanged. This is not an exemption for an intersecting hive.
    assert hi[0]<-833
    vox.WORLD=world;vox.OUT=base/'separate_natural_lake';vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-1344,320))
    count=runs(painter,lo,before,after,names,'R52_distant_natural_lake_whole_terrain_and_tree_components')
    painter.meta.update(root_author=True,centre=[-1140,600],nominal_radii=[220,170],water_level=-473,
        original_tree_components_retired=len(touched),tree_cells=int(cleared_trees.sum()),other_facilities_and_original_hive_preserved=True,
        artificial_lake_separated_by_more_than_500_blocks=True)
    folder=painter.save_plan('separate_distant_natural_lake')
    report=dict(world_written=False,cells=count,centre=[-1140,600],radii=[220,170],water_level=-473,
        native_water_and_visual_check_pending=True,retired_whole_tree_components=len(touched),retired_tree_cells=int(cleared_trees.sum()),
        basin_separate_from_hq_reservoir=True)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    np.savez_compressed(folder/'EXACT_BEFORE_AFTER.npz',origin=lo,palette=names,before=before,after=after,owned_columns=claimed_xy)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False})
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for ax,arr,title in zip(axes,(before,after),('施工前：远侧自然地形','远侧自然湖 · 与总部方湖分离')):
        layer=arr[-473-lo[1]];rgb=np.full((*layer.shape,3),[.47,.56,.40])
        rgb[layer==ids['minecraft:water[level=0]']]=[.11,.43,.56]
        ax.imshow(rgb,extent=[lo[0],hi[0]+1,hi[2]+1,lo[2]],interpolation='nearest')
        ax.set(title=title,xlabel='X / m',ylabel='Z / m（北向上）');ax.set_aspect('equal')
    fig.savefig(folder/'NATURAL_LAKE_PLAN.png',dpi=140);plt.close(fig)
    if args.apply:
        assert not list(folder.glob('applied_*'));lock=acquire_world_lock()
        try:
            report.update(world_written=True,receipt=painter.apply('separate_distant_natural_lake',session_lock=lock))
            actual,ap=measure(lo,hi)
            assert np.array_equal(np.array([ids[s] for s in ap],np.uint16)[actual],after)
            report['complete_envelope_exact_readback']=True
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
        (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
