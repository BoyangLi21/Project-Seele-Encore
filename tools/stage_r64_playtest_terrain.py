"""Stage and check exact reversible GeoFront surface edits, one complete region per worker."""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path
import numpy as np
from scipy import ndimage as nd
from query_blocks import iter_chunks,dimension_dir
from write_deep_cells import REGION,decode,encode,read_chunk,write_chunk,clear_light
from survey_r64_playtest_terrain import kind
from plant_r64_playtest_woodland import shapes,surround,GROWS

AIR='minecraft:air'
DIRT='minecraft:dirt'
STONE='minecraft:stone'
TREE_SPECIES=('oak','birch','spruce')
@lru_cache(maxsize=32)
def tree_shape(species,height):
    name=TREE_SPECIES[species]
    trunk='minecraft:'+name+'_log[axis=y]'
    leaves='minecraft:'+name+'_leaves[distance=1,persistent=true,waterlogged=false]'
    return [(dx,dy,dz,leaves if part else trunk) for dx,dy,dz,part in shapes(species,height)]

def tree_cells(trees,plan,rx,rz):
    chunks={}
    for j in (-1,0,1):
        for i in (-1,0,1):
            file=trees/f'r.{rx+i}.{rz+j}.npy'
            if not file.exists():continue
            elevation=np.load(plan/f'r.{rx+i}.{rz+j}.npz')['target']
            for xx,zz,y,sp,ht in np.load(file):
                x,z=int(xx),int(zz);y=int(elevation[z&511,x&511])
                if (x&511)>2 and (z&511)>2 and (x&511)<509 and (z&511)<509 and (i!=0 or j!=0):continue
                for dx,dy,dz,name in tree_shape(int(sp),int(ht)):
                    bx,bz=x+dx,z+dz
                    if (bx>>9,bz>>9)==(rx,rz):
                        chunks.setdefault((bx>>4,bz>>4),[]).append((bx,int(y)+dy,bz,name))
    return chunks

def stage(job):
    source,survey,plan,trees,out,rx,rz=job
    tag=f'r.{rx}.{rz}'
    receipt=out/(tag+'.json')
    if receipt.exists():return
    geom=np.load(plan/(tag+'.npz'));survey_region=np.load(survey/(tag+'.npz'))
    hh,goal=geom['h'],geom['target']
    vegetation=survey_region['v'];tops=survey_region['t'];stem=survey_region['r']
    h=surround(plan,rx,rz,'h',-32768);target=surround(plan,rx,rz,'target',-32768)
    root=surround(survey,rx,rz,'r',False)
    # Cobble and mossy cobble also occur in the authored mountain geology. Keep
    # them near mapped construction; a remote buried streak can be graded.
    rural=nd.distance_transform_edt(surround(survey,rx,rz,'k',0)!=5)[12:-12,12:-12]>12
    # Preserve each measured trunk and canopy together when the ground moves underneath it.
    # Existing stems control neighbouring leaves; ground plants follow their own column.
    if root.any():
        dist,(iz,ix)=nd.distance_transform_edt(~root,return_indices=True)
        crown=np.where(dist<=7,target[iz,ix].astype(int)-h[iz,ix],0)[12:-12,12:-12]
    else:crown=np.zeros(hh.shape,int)
    trees_in=tree_cells(trees,plan,rx,rz)
    wanted=(hh!=goal)|((crown!=0)&(vegetation>0))
    chunks={(cx+rx*32,cz+rz*32) for cz,cx in zip(*np.nonzero(wanted.reshape(32,16,32,16).any((1,3))))}|set(trees_in)
    path=source/REGION/(tag+'.mca')
    if not chunks or not path.exists():
        receipt.write_text(json.dumps({'chunks':[],'cells':0,'columns':0}));return (rx,rz,0)
    old_bytes=path.read_bytes();buf=bytearray(old_bytes)
    # Compare the serialized disk result to a compact cell journal after writing.
    journal={};names=[];lookup={};chunks_changed=[];ncols=nvox=0;blocked=0;clipped_trees=0
    def global_id(s):
        if s not in lookup:
            lookup[s]=len(names);names.append(s)
        return lookup[s]
    for cx,cz,nbt in iter_chunks(dimension_dir(source,'projectseele:geofront'),(rx*32,rx*32+31,rz*32,rz*32+31),chunks):
        if str(nbt['Status']).split(':')[-1]!='full':continue
        xx,zz=(cx&31)*16,(cz&31)*16
        cut=np.s_[zz:zz+16,xx:xx+16]
        oldh=hh[cut].astype(int);to=goal[cut].astype(int)
        motion=crown[cut];top=tops[cut].astype(int);eligible=wanted[cut] & (oldh>-32768)
        plants=trees_in.get((cx,cz),[])
        lows=[r[1] for r in plants]; highs=lows[:]
        if eligible.any():
            lows.append(max(-128,int(np.minimum(oldh,to)[eligible].min())-66))
            highs.append(int(np.maximum.reduce((top,top+motion,top+to-oldh))[eligible].max())+1)
        if not lows:continue
        low=min(lows)//16; high=max(highs)//16
        secs={int(sec['Y']):sec for sec in nbt['sections'] if 'block_states' in sec}
        if any(sy not in secs for sy in range(low,high+1)):raise ValueError(f'missing block section {cx,cz,low,high}')
        pal=[AIR,DIRT,STONE];index={s:i for i,s in enumerate(pal)}
        def local(s):
            if s not in index:index[s]=len(pal);pal.append(s)
            return index[s]
        def readvol():
            volume=np.empty(((high-low+1)*16,16,16),np.int16)
            for sy in range(low,high+1):
                ids,p=decode(secs[sy]['block_states']);lut=np.array([local(s) for s in p],np.int16)
                volume[(sy-low)*16:(sy-low+1)*16]=lut[ids.reshape(16,16,16)]
            return volume
        old=readvol();new=old.copy()
        y0=low*16;ys=np.arange(y0,(high+1)*16)[:,None,None]
        cat=np.array([kind(s.partition('[')[0]) for s in pal],np.uint8)[old]
        iz,ix=np.indices((16,16))
        bed=old[np.clip(oldh-y0,0,len(old)-1),iz,ix]
        # Examine the whole cut and cap, including buried foundations and cave air.
        # Artificial material, fluids and unsupported proposed tops hold a column.
        work=eligible & (to!=oldh)
        lower_bound=np.where(to>oldh,oldh,np.minimum(oldh,to)-2)
        inside=(ys>=lower_bound)&(ys<=oldh)
        geology=np.array([s.partition('[')[0].endswith('_ore') for s in pal])[old] | (cat==3)
        buried=np.array([s in ('minecraft:cobblestone','minecraft:mossy_cobblestone') for s in pal])[old]
        geology |= buried & rural[cut] & (ys<oldh)
        # Retired generators sometimes left a four-block skin floating well above
        # the original hill. An air gap is not a foundation to protect. Preserve
        # fluids, buildings and underground works; tie a moved surface to geology.
        anchor_y=lower_bound
        below=(ys<=anchor_y)&(cat!=0)
        found=below.any(0)
        rock_index=(len(old)-1)-below[::-1].argmax(0)
        foot=y0+rock_index
        footing=geology[rock_index,iz,ix]
        obstruct=((~geology)&(cat!=0)&inside).any(0) | (~found) | (~footing)
        blocked+=int((work&obstruct).sum())
        work &= ~obstruct
        to=np.where(work,to,oldh)
        sub=np.array([s.partition('[')[0].removeprefix('minecraft:') in GROWS for s in pal])[bed]
        strata=np.where(ys==to,bed,np.where(sub & (ys>=to-2),1,2))
        # Soil depth is retained for soil-topped hills; exposed sand or gravel continues beneath its cap.
        loose=np.array([s.partition('[')[0] in ('minecraft:sand','minecraft:red_sand','minecraft:gravel','minecraft:snow_block','minecraft:clay') for s in pal])[bed]
        strata=np.where(loose&(ys>=to-2),bed,strata)
        change=work&(ys>=lower_bound)&(ys<=np.maximum(oldh,to))
        new[change]=np.where(ys>to,0,strata)[change]
        support=work & (ys>foot) & (ys<lower_bound) & (cat==0)
        new[support]=2
        for typ,delta in ((1,to-oldh),(2,motion)):
            # Existing wood directly on the ground must remain rooted if a
            # protected sub-surface foundation kept its own column stationary.
            if typ==2:
                delta=np.where(stem[cut],to-oldh,delta)
            live=(cat==typ)&(ys>oldh)&(delta!=0)
            ay,az,ax=np.nonzero(live)
            if not len(ay):continue
            clear=(ys>to)&live
            new[clear]=0
            dy=ay+delta[az,ax]
            valid=(dy>=0)&(dy<len(new))&(dy+y0>to[az,ax])
            ay,az,ax,dy=(a[valid] for a in (ay,az,ax,dy))
            ok=(cat[dy,az,ax]<=2)
            # Newly excavated air also accepts its translated tree.
            ok|=(new[dy,az,ax]==0)
            new[dy[ok],az[ok],ax[ok]]=old[ay[ok],az[ok],ax[ok]]
        for x,y,z,state in plants:
            j,i=z&15,x&15
            if y<=to[j,i] or y-y0>=len(new):clipped_trees+=1;continue
            v=new[y-y0,j,i]
            if kind(pal[v].partition('[')[0]) in (0,1) or (state.partition('[')[0].endswith('_log') and pal[v].partition('[')[0].endswith('_leaves') and cat[y-y0,j,i]<=1):
                new[y-y0,j,i]=local(state)
            elif pal[v]!=state:clipped_trees+=1
        changed=new!=old
        if not changed.any():continue
        # Cells with block-entity data cannot be part of this natural-surface patch.
        for entity in nbt.get('block_entities',[]):
            bx,by,bz=(int(entity[t]) for t in ('x','y','z'))
            if y0<=by<y0+len(new) and changed[by-y0,bz&15,bx&15]:
                raise ValueError(f'block entity at {bx,by,bz}')
        global_lut=np.array([global_id(s) for s in pal],np.uint16)
        for sy in range(low,high+1):
            sl=slice((sy-low)*16,(sy-low+1)*16);at=np.flatnonzero(changed[sl])
            if not len(at):continue
            oldsec,newsec=old[sl].ravel(),new[sl].ravel()
            journal[(cx,cz,sy)]=np.stack((at,global_lut[oldsec[at]],global_lut[newsec[at]]),axis=1).astype(np.uint16)
            encode(secs[sy]['block_states'],newsec,pal)
        clear_light(nbt);nbt.pop('Heightmaps',None)
        idx=4*((cx&31)+32*(cz&31));loc=int.from_bytes(old_bytes[idx:idx+3],'big');count=old_bytes[idx+3]
        write_chunk(buf,idx,loc,count,nbt)
        chunks_changed.append((cx,cz));nvox+=int(changed.sum());ncols+=int(work.sum())
    save_verified_region(out,tag,buf,old_bytes,journal,names,chunks_changed)
    receipt.write_text(json.dumps(dict(chunks=chunks_changed,cells=nvox,columns=ncols,protected_columns=blocked,clipped_tree_cells=clipped_trees)))
    return rx,rz,nvox
def save_verified_region(out,tag,buf,old_bytes,journal,names,chunks_changed):
    lookup={s:i for i,s in enumerate(names)}
    def known(s):
        if s not in lookup:lookup[s]=len(names);names.append(s)
        return lookup[s]
    if journal:
        stagefile=out/(tag+'.mca');stagefile.write_bytes(buf);disk=stagefile.read_bytes()
        # Validate unplanned sections, changed cells, and independent block entities on disk.
        for cx,cz in chunks_changed:
            original=read_chunk(old_bytes,cx,cz)[3];edited=read_chunk(disk,cx,cz)[3]
            if original.get('block_entities')!=edited.get('block_entities'):raise ValueError('changed block entity')
            for a,b in zip(original['sections'],edited['sections'],strict=True):
                sy=int(a['Y'])
                if sy!=int(b['Y']):raise ValueError('section identity')
                rows=journal.get((cx,cz,sy))
                if rows is None:
                    if a.get('block_states')!=b.get('block_states'):raise ValueError('unplanned section')
                    continue
                ids,p=decode(a['block_states']);before=np.array([known(s) for s in p],np.uint16)[ids]
                ids,p=decode(b['block_states']);after=np.array([known(s) for s in p],np.uint16)[ids]
                pos,oldv,newv=rows.T
                if not np.array_equal(np.flatnonzero(before!=after),pos) or not np.array_equal(before[pos],oldv) or not np.array_equal(after[pos],newv):
                    raise ValueError(f'readback or collateral {cx,cz,sy}')
        keys=np.array(list(journal),np.int16)
        lengths=np.array([len(v) for v in journal.values()],np.uint16)
        np.savez_compressed(out/(tag+'.delta.npz'),sections=keys,lengths=lengths,rows=np.concatenate(list(journal.values())),states=np.array(names))

def main():
    p=argparse.ArgumentParser()
    for arg in ('world','survey','plan','trees','out'):p.add_argument('--'+arg,required=True,type=Path)
    p.add_argument('--workers',type=int,default=5)
    p.add_argument('--region',nargs=2,type=int)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    coords=[tuple(map(int,s.stem.split('.')[1:])) for s in a.plan.glob('*.npz')] if not a.region else [tuple(a.region)]
    coords.sort(key=lambda c:(c!=(6,-5),c))
    jobs=[(a.world,a.survey,a.plan,a.trees,a.out,*c) for c in coords]
    with ProcessPoolExecutor(a.workers) as pool:
        for i,r in enumerate(pool.map(stage,jobs),1):print(i,len(jobs),r,flush=True)
if __name__=='__main__':main()
