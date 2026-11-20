"""Restore clipped survey woodland in Odawara and taper straight canopy margins on rural ground."""
import argparse
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path
import numpy as np
from scipy import ndimage as nd
from plan_r64_playtest_terrain import smooth
from plant_r64_playtest_woodland import GROWS,surround
from query_blocks import iter_chunks,dimension_dir,decode_modern_section
from write_deep_cells import REGION,read_chunk,write_chunk,clear_light,decode,encode
from survey_r64_playtest_terrain import kind


def d8(a):return a.reshape(64,8,64,8).mean((1,3)).astype('f')

def hash_field(x,z,seed):
    v=x.astype('uint64')*np.uint64(341873128712)^z.astype('uint64')*np.uint64(132897987541)^np.uint64(seed)
    v^=v>>np.uint64(30);v*=np.uint64(0xbf58476d1ce4e5b9);v^=v>>np.uint64(27);v*=np.uint64(0x94d049bb133111eb)
    return v^(v>>np.uint64(31))

def design(d,classes):
    survey=d/'after-final'; old=d/'survey';out=d/'woodland-plan';out.mkdir(exist_ok=True)
    pairs=[tuple(map(int,f.stem.split('.')[1:])) for f in survey.glob('*.npz')]
    x0,z0=min(x for x,z in pairs),min(z for x,z in pairs)
    size=((max(z for x,z in pairs)-z0+1)*64,(max(x for x,z in pairs)-x0+1)*64)
    pre,now,valid,dry,hard,mean=[np.zeros(size,'f') for i in range(6)]
    def sl(rx,rz):return np.s_[(rz-z0)*64:(rz-z0+1)*64,(rx-x0)*64:(rx-x0+1)*64]
    for rx,rz in pairs:
        name=f'r.{rx}.{rz}.npz';a=np.load(survey/name);k=a['k'];cut=sl(rx,rz)
        pre[cut]=d8(np.load(old/name)['v']);now[cut]=d8(a['v']);valid[cut]=d8(k>0)
        dry[cut]=d8(k==3);hard[cut]=d8((k==5)|(k==4))
        mean[cut]=d8(np.where(k>0,a['h'],0))/np.maximum(valid[cut],.001)
    zs,xs=np.ogrid[0:size[0],0:size[1]];x=x0*512+xs*8+4;z=z0*512+zs*8+4
    data=np.load(classes);bx,bz,ex,ez=map(int,data['bounds']);source=data['classes']
    # The historic survey raster has 4-m/block civil geometry and full planting classes.
    # A missing capture tile is inferred from its actual Ministry vegetation polygons.
    j=np.clip(z-bz,0,ez-bz);i=np.clip(x-bx,0,ex-bx)
    inside=(x>=bx)&(x<=ex)&(z>=bz)&(z<=ez)
    cls=source[j,i]
    tree=np.isin(cls,(2,3,4,5)).astype('f')
    survey_probability=nd.gaussian_filter(tree,3.4)
    origin=nd.gaussian_filter(pre,1.55)
    regional=nd.maximum_filter(nd.gaussian_filter(pre,4),size=67)
    seam=np.zeros(size,bool)
    for axis in (0,1):
        g=np.roll(origin,3,axis)-np.roll(origin,-3,axis)
        long=nd.uniform_filter1d(g,size=11,axis=1-axis)
        cross=nd.uniform_filter1d(np.abs(np.gradient(origin,axis=1-axis)),size=11,axis=1-axis)
        seam|=(np.abs(long)>.20)&(np.abs(long)>.68*np.abs(g))&(np.abs(long)>3.2*cross)
    seam&=dry>.50
    distance=nd.distance_transform_edt(~seam)*8
    cover=nd.gaussian_filter(now,1.7)
    tree_seed=nd.distance_transform_edt(origin<.42)*8
    terrain=nd.gaussian_filter(mean,2.25)
    grade=np.hypot(*np.gradient(terrain))/8
    agricultural=nd.gaussian_filter(hard,3)
    climate=np.clip(.90+.09*np.sin(x/73+z/154)+.09*np.cos(z/87-x/223)+.045*np.sin(x/29-z/53),.63,1.08)
    margin=nd.distance_transform_edt(inside)*8
    outside=nd.distance_transform_edt(~inside)*8
    odawara=(x>=1536)&(x<4800)&(z>=-1800)&(z<1800)
    # Explicit survey classes carry the missing hillside all the way across a tile;
    # agricultural lowlands and streets retain their open habitat.
    mapped=(.57+.19*np.clip(regional/.8,0,1))*survey_probability
    general=regional*.76*smooth(1-tree_seed/335)
    inherited=mapped*smooth(1-outside/360)
    target=np.where(inside, mapped, np.maximum(inherited,general))
    # Permit a loose brush transition on high-relief open land immediately beyond
    # very straight woods, while keeping mapped fields and settled plains clear.
    shoulder=regional*.60*smooth(1-distance/140)*smooth(.2+grade/.45)
    target=np.maximum(target,shoulder)
    scope=np.maximum(smooth(1-distance/380),odawara*inside*survey_probability*smooth(1-tree_seed/550))
    scope*=smooth(1-tree_seed/560)*smooth((nd.distance_transform_edt(valid>.75)*8-8)/60)
    scope*=smooth((.42-agricultural)/.32)*smooth((2.35-grade)/1.45)*smooth((235-terrain)/75)
    target*=climate
    deficit=np.clip((target-cover-.025)*scope,0,.83)
    # Ease the dense side over about 70 m. Every retained root remains an anchor
    # when assigning the adjacent leaves of the selected stems.
    thin=.48*smooth((origin-.30)/.40)*smooth(1-distance/85)*scope*(.77+.23*np.sin(x/29+z/58))
    thin*=np.clip((origin-nd.gaussian_filter(pre,9))/.22,0,1)
    # Keep the exact mountain facility, island, airport and launch footprints.
    mountain=np.hypot(np.maximum(0,np.maximum(-1343-x,x+1129)),np.maximum(0,np.maximum(-1452-z,z+1332)))
    protected=smooth((mountain-32)/32)
    deficit*=protected;thin*=protected
    records=[]
    for rx,rz in pairs:
        cut=sl(rx,rz);add=np.rint(deficit[cut]*255).astype('B');remove=np.rint(thin[cut]*255).astype('B');species=cls[cut].astype('B')
        if (rx,rz) in {(-1,0),(0,0),(-1,1)}:add.fill(0);remove.fill(0)
        np.savez_compressed(out/f'r.{rx}.{rz}.npz',add=add,remove=remove,classes=species)
        records.append((rx,rz,int((add>6).sum()),int((remove>6).sum())))
    print('plan',len(records),sum(r[2] for r in records),sum(r[3] for r in records),flush=True)

def anchors(job):
    world,d,rx,rz=job;dest=d/'woodland-roots'/f'r.{rx}.{rz}.npz'
    if dest.exists():return
    name=dest.name;sur=d/'after-final';spec=np.load(d/'woodland-plan'/name)
    add,remove,cl=spec['add'],spec['remove'],spec['classes']
    if not (add.any() or remove.any()):
        np.savez_compressed(dest,add=np.empty((0,5),'i4'),remove=np.empty((0,3),'i4'));return
    a=np.load(sur/name);h=a['h'];margin=12;k=surround(sur,rx,rz,'k',0);v=surround(sur,rx,rz,'v',0)
    roots=surround(sur,rx,rz,'r',False)
    safe=nd.distance_transform_edt(k==3)[margin:-margin,margin:-margin]
    open_dist=nd.distance_transform_edt(v==0)[margin:-margin,margin:-margin]
    stem_dist=nd.distance_transform_edt(~roots)[margin:-margin,margin:-margin]
    terrain=surround(sur,rx,rz,'h',-32768).astype('f')
    slope=np.hypot(*np.gradient(nd.gaussian_filter(terrain,1.8)))[margin:-margin,margin:-margin]
    iz,ix=np.mgrid[0:128,0:128];r=hash_field(ix+rx*128,iz+rz*128,487923)
    xx=ix*4+1+((r>>14)%3).astype(int);zz=iz*4+1+((r>>19)%3).astype(int)
    p=nd.map_coordinates(add.astype('f')/255,((zz-4)/8,(xx-4)/8),order=1,mode='nearest')
    use=((r&65535)/65536 < p*.97)&(safe[zz,xx]>=5.5)&(stem_dist[zz,xx]>=3.1)&(open_dist[zz,xx]>=1)&(slope[zz,xx]<1.7)
    selected=[]
    for j,i in zip(*np.nonzero(use)):
        x,z=int(xx[j,i]),int(zz[j,i]);typ=cl[z>>3,x>>3];rr=int(r[j,i])
        species=(2 if (typ==2 and (rr>>25)%9<7) or (typ==3 and (rr>>25)%9<5) or (h[z,x]>100 and (rr>>27)%5<2) else (1 if (rr>>32)%5==0 else 0))
        height=(7 if species==2 else 5)+(rr>>36)%4
        selected.append((rx*512+x,rz*512+z,int(h[z,x]),species,height))
    zz,xx=np.nonzero(a['r']&(safe>7)&((a['t']-h)>=4)&((a['t']-h)<=17));r=hash_field(xx+rx*512,zz+rz*512,9021)
    thin=nd.map_coordinates(remove.astype('f')/255,((zz-4)/8,(xx-4)/8),order=1,mode='nearest')
    which=((r&65535)/65536 < thin)
    fell=[(int(rx*512+x),int(rz*512+z),int(h[z,x])) for z,x in zip(zz[which],xx[which])]
    # A surface classification is not a soil licence to plant on stone or gravel.
    chunks=defaultdict(list)
    for row in selected:chunks[row[0]>>4,row[1]>>4].append(row)
    accepted=[]
    for cx,cz,c in iter_chunks(dimension_dir(world,'projectseele:geofront'),(rx*32,rx*32+31,rz*32,rz*32+31),chunks):
        parts=defaultdict(list)
        for row in chunks[cx,cz]:parts[row[2]>>4].append(row)
        for sec in c['sections']:
            sy=int(sec['Y'])
            if sy not in parts:continue
            pal,ids=decode_modern_section(sec)
            for row in parts[sy]:
                x,z,y,sp,ht=row;at=((y&15)<<8)|((z&15)<<4)|(x&15)
                if str(pal[ids[at]]['Name']).removeprefix('minecraft:') in GROWS:accepted.append(row)
    np.savez_compressed(dest,add=np.array(accepted,'i4').reshape(-1,5),remove=np.array(fell,'i4').reshape(-1,3))
    return rx,rz,len(accepted),len(fell)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['plan','roots','stage'])
    p.add_argument('--work',required=True,type=Path);p.add_argument('--world',required=True,type=Path);p.add_argument('--classes',type=Path)
    p.add_argument('--workers',type=int,default=7)
    a=p.parse_args();d=a.work
    if a.mode=='plan':return design(d,a.classes)
    branch='woodland-roots' if a.mode=='roots' else 'woodland-staged'
    (d/branch).mkdir(exist_ok=True)
    coords=[tuple(map(int,f.stem.split('.')[1:])) for f in (d/'after-final').glob('*.npz')]
    coords.sort(key=lambda c:(min(abs(c[0]-4)+abs(c[1]),abs(c[0]-8)+abs(c[1]+3)),c))
    with ProcessPoolExecutor(a.workers) as pool:
        for i,rec in enumerate(pool.map(anchors if a.mode=='roots' else installable,[(a.world,d,*c) for c in coords]),1):
            print(i,len(coords),rec,flush=True)


@lru_cache(maxsize=48)
def crown(species,h,variation):
    masks=defaultdict(set)
    for y in range(1,h+1):masks[0].add((0,y,0))
    for y in range(2,h+2):
        down=h-y
        if species==2:
            if down<0:r=0
            else:r=min(3,1+(down+1)//2) if down%2==0 else min(2,1+down//4)
        else:
            if down>3:continue
            r=1 if down==-1 else 3 if down in (0,1) else 2
        for z in range(-r,r+1):
            for x in range(-r,r+1):
                if x*x+z*z>r*r+1 or (x,y,z) in masks[0]:continue
                if r>=2 and abs(x)+abs(z)>r and ((x*31+z*17+y*3+variation)%7==0):continue
                masks[1].add((x,y,z))
    return [(sp,np.array(sorted(cells),np.int32)) for sp,cells in masks.items()]

def installation_groups(d,rx,rz):
    roots=[];removed=np.zeros((536,536),bool)
    for j in (-1,0,1):
        for i in (-1,0,1):
            f=d/'woodland-roots'/f'r.{rx+i}.{rz+j}.npz'
            if not f.exists():continue
            u=np.load(f);rows=u['add'];felled=u['remove']
            if len(rows):
                x=rows[:,0]-rx*512;z=rows[:,1]-rz*512
                roots.extend(rows[(x>=-3)&(x<=514)&(z>=-3)&(z<=514)].tolist())
            if len(felled):
                x=felled[:,0]-rx*512+12;z=felled[:,1]-rz*512+12
                use=(x>=0)&(x<536)&(z>=0)&(z<536);removed[z[use],x[use]]=True
    by={}
    if roots:
        rows=np.array(roots,'i4')
        for sp in (0,1,2):
            wood=('oak','birch','spruce')[sp]
            for ht in range(5,11):
                for variant in (0,1):
                    use=(rows[:,3]==sp)&(rows[:,4]==ht)&((rows[:,0]&1)==variant);r=rows[use]
                    if not len(r):continue
                    for leaf,shape in crown(sp,ht,variant):
                        x=(r[:,0,None]+shape[:,0]).ravel();y=(r[:,2,None]+shape[:,1]).ravel();z=(r[:,1,None]+shape[:,2]).ravel()
                        own=((x>>9)==rx)&((z>>9)==rz);x,y,z=x[own],y[own],z[own]
                        if not len(x):continue
                        key=(y//16+16)*1024+((z>>4)&31)*32+((x>>4)&31)
                        order=np.argsort(key,kind='stable');key=key[order];at=(((y&15)<<8)|((z&15)<<4)|(x&15))[order].astype(np.uint16)
                        starts=np.r_[0,np.flatnonzero(np.diff(key))+1,len(key)]
                        state='minecraft:'+wood+('_leaves[distance=1,persistent=true,waterlogged=false]' if leaf else '_log[axis=y]')
                        for a,b in zip(starts[:-1],starts[1:]):
                            ix=int(key[a]);cx=(rx<<5)+(ix&31);cz=(rz<<5)+((ix>>5)&31);sy=(ix>>10)-16
                            by.setdefault((cx,cz),defaultdict(list))[sy].append((leaf,state,at[a:b]))
    survey=d/'after-final'
    if not removed.any():return by,None,None
    roots=surround(survey,rx,rz,'r',False)
    distance,(j,i)=nd.distance_transform_edt(~roots,return_indices=True)
    h=surround(survey,rx,rz,'h',-32768);v=np.load(survey/f'r.{rx}.{rz}.npz')['v']
    sl=np.s_[12:-12,12:-12]
    cut=(removed[j,i]&(distance<=6))[sl]&(v!=0);feet=h[j,i][sl]
    for cz,cx in zip(*np.nonzero(cut.reshape(32,16,32,16).any((1,3)))):by.setdefault((rx*32+int(cx),rz*32+int(cz)),defaultdict(list))
    return by,cut,feet

def installable(job):
    from stage_r64_playtest_terrain import save_verified_region
    world,d,rx,rz=job;tag=f'r.{rx}.{rz}';out=d/'woodland-staged';receipt=out/(tag+'.json')
    if receipt.exists():return
    groups,cut,feet=installation_groups(d,rx,rz)
    if not groups:
        receipt.write_text(json.dumps({'cells':0,'chunks':[],'columns':0}));return
    source=world/REGION/(tag+'.mca');oldbuf=source.read_bytes();buf=bytearray(oldbuf)
    names=[];ids={}
    def lookup(s):
        if s not in ids:ids[s]=len(names);names.append(s)
        return ids[s]
    removed=added=0;journal={};chunks=[]
    for cx,cz,root in iter_chunks(dimension_dir(world,'projectseele:geofront'),(rx*32,rx*32+31,rz*32,rz*32+31),groups):
        if str(root['Status']).split(':')[-1]!='full':continue
        plans=groups[cx,cz];ix=(cx&31)*16;iz=(cz&31)*16;sl=np.s_[iz:iz+16,ix:ix+16]
        land=cut[sl] if cut is not None else None
        clearing=land is not None and land.any()
        if clearing:
            heights=feet[sl]
            low=int(heights[land].min())+1;high=int(heights[land].max())+18
        edits=0
        for sec in root['sections']:
            sy=int(sec['Y']);base=sy*16
            clear=clearing and base<=high and base+15>=low
            if not clear and sy not in plans:continue
            bs=sec.get('block_states')
            if bs is None:continue
            old,pal=decode(bs);new=old.copy();lookup_local={s:i for i,s in enumerate(pal)}
            def local(s):
                if s not in lookup_local:lookup_local[s]=len(pal);pal.append(s)
                return lookup_local[s]
            if clear:
                wood=np.array([kind(s.partition('[')[0])==2 for s in pal])[old].reshape(16,16,16)
                y=base+np.arange(16)[:,None,None]
                mask=land[None,:,:]&(y>heights)&(y<=heights+18)&wood
                new[mask.ravel()]=local('minecraft:air')
            for leaf,state,at in sorted(plans.get(sy,()),key=lambda r:-r[0]):
                allowed=np.array([kind(s.partition('[')[0]) in (0,1) for s in pal])[new[at]]
                if not leaf:
                    ownleaf=np.array([s.partition('[')[0].endswith('_leaves') for s in pal])[new[at]]
                    allowed|=ownleaf&(old[at]!=new[at])
                new[at[allowed]]=local(state)
            at=np.flatnonzero(old!=new)
            if not len(at):continue
            for be in root.get('block_entities',[]):
                yy=int(be['y'])
                if yy>>4==sy:
                    index=((yy&15)<<8)|((int(be['z'])&15)<<4)|(int(be['x'])&15)
                    if old[index]!=new[index]:raise ValueError('Natural forest patch intersects a block entity')
            rem=np.array([s=='minecraft:air' for s in pal])[new[at]]
            removed+=int(rem.sum());added+=len(at)-int(rem.sum());edits+=len(at)
            table=np.array([lookup(s) for s in pal],np.uint16)
            journal[cx,cz,sy]=np.stack((at,table[old[at]],table[new[at]]),1).astype(np.uint16)
            encode(bs,new,pal)
        if edits:
            chunks.append((cx,cz));clear_light(root);root.pop('Heightmaps',None)
            index=4*((cx&31)+32*(cz&31));loc=int.from_bytes(oldbuf[index:index+3],'big');count=oldbuf[index+3]
            write_chunk(buf,index,loc,count,root)
    save_verified_region(out,tag,buf,oldbuf,journal,names,chunks)
    receipt.write_text(json.dumps(dict(chunks=chunks,cells=added+removed,columns=0,removed=removed,added=added)))
    return rx,rz,added,removed

if __name__=='__main__':main()
