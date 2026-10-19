"""Enlarge the explicitly authored far lake, preserving structures and whole trees."""
import argparse,json,msvcrt
from pathlib import Path
import numpy as np
from scipy.ndimage import label,generate_binary_structure,distance_transform_cdt
import regional_voxels as vox
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities
from prepare_terminal_move_r52 import runs

LO=(-1555,-560,180);HI=(-830,-430,1020)
DIM='projectseele:geofront'
AIR={'minecraft:air','minecraft:cave_air','minecraft:void_air'}
PLANTS={'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern',
        'minecraft:azure_bluet','minecraft:poppy','minecraft:dandelion'}
NATURAL=AIR|PLANTS|{'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:water',
    'minecraft:gravel','minecraft:sand','minecraft:clay','minecraft:coarse_dirt','minecraft:tuff',
    'minecraft:podzol','minecraft:oak_log','minecraft:oak_leaves','minecraft:birch_log','minecraft:birch_leaves'}

def smooth(v):
    q=np.clip(v,0,1);return q*q*(3-2*q)

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('world',type=Path);ap.add_argument('out',type=Path)
    ap.add_argument('--apply',action='store_true');a=ap.parse_args();survey.WORLD=a.world
    a.out.mkdir(parents=True,exist_ok=True);f=a.out/'EXACT_BEFORE_AFTER.npz'
    if f.exists():
        s=np.load(f);before=s['before'];after=s['after'];names=list(map(str,s['palette']))
    else:
        source=a.out/'SOURCE.npz'
        if source.exists():
            s=np.load(source);before=s['states'];names=list(map(str,s['palette']))
        else:before,names=survey.measure(LO,HI);names=list(names)
        for n in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]',
                  'minecraft:gravel','minecraft:sand','minecraft:water[level=0]'):
            if n not in names:names.append(n)
        ids={n:i for i,n in enumerate(names)}
        zz,xx=np.ogrid[LO[2]:HI[2]+1,LO[0]:HI[0]+1]
        angle=np.arctan2((zz-600)/330.,(xx+1190)/285.)
        r=np.sqrt(((xx+1190)/285.)**2+((zz-600)/330.)**2)/(1+.04*np.sin(3*angle)+.025*np.sin(5*angle+.6))
        claimed=r<=1.16
        tags=dict(iter_block_entities(a.world,DIM,LO,HI))
        assert all(not claimed[p[2]-LO[2],p[0]-LO[0]]for p in tags),'Fixture inside claimed natural lake'
        unknown={names[int(v)]for v in np.unique(before[:,claimed])if names[int(v)].split('[')[0]not in NATURAL}
        assert not unknown,('Authored structure inside lake',unknown)
        yy=np.arange(LO[1],HI[1]+1)[:,None,None]
        ground_ids=[i for i,n in enumerate(names)if n.split('[')[0]in NATURAL-AIR-PLANTS-{'minecraft:water','minecraft:oak_log','minecraft:oak_leaves','minecraft:birch_log','minecraft:birch_leaves'}]
        old_ground=np.max(np.where(np.isin(before,ground_ids),yy,-2000),axis=0)
        assert np.all(old_ground[claimed]>LO[1])
        # Keep a sloping littoral shelf; deeper central water accommodates EVA scale.
        bottom=np.floor(-548+75*smooth((r-.18)/.82)).astype(int)
        shore=np.floor(-472*(1-smooth((r-1)/.16))+old_ground*smooth((r-1)/.16)).astype(int)
        target=np.where(r<1,bottom,shore)
        trees=np.isin(before,[i for i,n in enumerate(names)if n.split('[')[0].endswith(('_log','_leaves'))])
        # Touching leaf crowns can connect an entire forest. Attribute each
        # crown cell to its nearest connected trunk instead of treating all
        # touching leaves as one tree and deleting an unbounded forest.
        occupied=np.flatnonzero(trees.any(axis=(1,2)));low=int(occupied.min());high=int(occupied.max())+1
        logs=np.isin(before[low:high],[i for i,n in enumerate(names)if n.split('[')[0].endswith('_log')])
        trunks,_=label(logs,generate_binary_structure(3,1))
        nearest=distance_transform_cdt(~logs,return_distances=False,return_indices=True)
        owners=trunks[tuple(nearest)];owners[~trees[low:high]]=0
        touched=np.unique(owners[:,claimed]);touched=touched[touched!=0]
        cleared=np.zeros_like(trees);cleared[low:high]=np.isin(owners,touched)&trees[low:high]
        assert not any(np.any(face)for face in (cleared[0],cleared[-1],cleared[:,0],cleared[:,-1],cleared[:,:,0],cleared[:,:,-1])),'Whole tree leaves survey envelope'
        for p in tags:
            x,y,z=p
            for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                q=(y+dy-LO[1],z+dz-LO[2],x+dx-LO[0])
                if all(0<=q[i]<before.shape[i]for i in range(3)):assert not cleared[q],'Preserve tree supporting original hive'
        del trunks,owners,nearest,logs,trees
        after=before.copy();after[cleared]=ids['minecraft:air']
        for iy,y in enumerate(range(LO[1],HI[1]+1)):
            values=np.where(y>target,np.where((r<1)&(y<=-473),ids['minecraft:water[level=0]'],ids['minecraft:air']),
                np.where(y==target,np.where(r<1,ids['minecraft:gravel'],ids['minecraft:grass_block[snowy=false]']),
                np.where(y>=target-3,np.where(r<1,ids['minecraft:sand'],ids['minecraft:dirt']),ids['minecraft:stone'])))
            after[iy,claimed]=values[claimed]
        water=(after==ids['minecraft:water[level=0]'])&claimed[None,:,:]
        air_lookup=np.array([n in AIR for n in names])
        for d in ((0,0,1),(0,0,-1),(0,1,0),(0,-1,0),(-1,0,0)):
            aa=tuple(slice(max(0,-q),min(n,n-q))for n,q in zip(after.shape,d))
            bb=tuple(slice(max(0,q),min(n,n+q))for n,q in zip(after.shape,d))
            assert not np.any(water[aa]&air_lookup[after[bb]]),'Open underwater basin face'
        for p in tags:assert after[p[1]-LO[1],p[2]-LO[2],p[0]-LO[0]]==before[p[1]-LO[1],p[2]-LO[2],p[0]-LO[0]]
        np.savez_compressed(f,before=before,after=after,palette=names,origin=LO,owned_columns=claimed)
        report=dict(old_nominal_size=[440,340],new_nominal_size=[570,660],old_max_depth=32,new_max_depth=75,
            centre=[-1190,600],water_y=-473,preserved_block_entities={str(p):v.snbt()for p,v in tags.items()},
            retired_whole_tree_components=len(touched),retired_tree_cells=int(cleared.sum()),basin_watertight=True,
            cells=int(np.count_nonzero(before!=after)),world_written=False)
        (a.out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(report,flush=True)
    vox.WORLD=a.world;vox.OUT=a.out;vox.DIM=DIM;painter=vox.Painter(vertical_bounds=(-1440,320))
    runs(painter,LO,before,after,names,'R53_explicit_far_natural_lake_enlargement')
    if not a.apply:painter.save_plan('natural_lake');return
    with (a.world/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        current,cp=survey.measure(LO,HI);ids={n:i for i,n in enumerate(names)}
        assert np.array_equal(np.asarray([ids[n]for n in cp],np.uint16)[current],before),'Frozen whole envelope changed'
        painter.apply('natural_lake',session_lock=lock)
        current,cp=survey.measure(LO,HI)
        assert np.array_equal(np.asarray([ids[n]for n in cp],np.uint16)[current],after),'Whole envelope readback mismatch'
    (a.out/'INSTALLED.json').write_text(json.dumps(dict(exact_full_envelope_readback=True,cells=int(np.count_nonzero(before!=after)))),'utf8')

if __name__=='__main__':main()
