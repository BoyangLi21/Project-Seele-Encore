"""Remove the legacy Y=62 ocean immediately beyond the installed east corridor.

Existing terrain-generation stages are preserved. Chunks that have not reached
noise are left for the corrected generator; no empty chunk is promoted to FULL.
"""
import argparse,json,math
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
from query_blocks import chunk_statuses,iter_selected_sections,iter_block_entities,dimension_dir,AIR
from install_hakone_array_patch import Palette
from install_r53_carrier_trays import stopped_world
from plan_ashi_landscape_r54 import NATURAL,SOIL
from prepare_hakone_main_terrain import sample_grid
from transplant_s22_authority import read_region,parse_chunk


def main(a):
    if a.out.exists():raise ValueError('Use a new reversible boundary candidate')
    (a.out/'source').mkdir(parents=True);(a.out/'delta').mkdir()
    with np.load(a.gis/'runtime-surface-field.npz')as f:grid={k:f[k]for k in f.files}
    # Scope this repair to the already installed valley's eastern seam.
    # Uninstalled northern/southern districts remain a separate accepted task.
    bounds=[2432,512,4607,1407];x0,z0,x1,z1=bounds
    selected={(cx,cz)for cx in range(x0//16,x1//16+1)for cz in range(z0//16,z1//16+1)}
    stages={'noise','surface','carvers','features','initialize_light','light','spawn','full'}
    regions=[];statuses={};protected=[];actors=[];groups=defaultdict(dict)
    with stopped_world(a.world):
        statuses=chunk_statuses(a.world,'projectseele:geofront',selected)
        for p,s in statuses.items():
            if s in stages:groups[p[0]//32,p[1]//32][p]=set(range(-8,20))
        for rx,rz in groups:
            file=dimension_dir(a.world,'projectseele:geofront')/'entities'/f'r.{rx}.{rz}.mca'
            if not file.exists()or not file.stat().st_size:continue
            _,rows=read_region(file)
            for row in rows:
                if row is None:continue
                for actor in parse_chunk(row).get('Entities',[]):
                    p=list(map(float,actor.get('Pos',[])))
                    if len(p)==3 and x0<=p[0]<=x1 and z0<=p[2]<=z1 and -128<=p[1]<320:actors.append(p)
        yy=np.arange(-128,320)[:,None,None]
        for key,chosen in sorted(groups.items()):
            name=f'r.{key[0]}.{key[1]}.npz';palette=Palette();coords=sorted(chosen);index={p:i for i,p in enumerate(coords)}
            blocks=np.zeros((len(coords),448,16,16),np.uint16)
            for cx,cz,sy,names,ids in iter_selected_sections(a.world,'projectseele:geofront',chosen,expected_statuses=statuses):
                blocks[index[cx,cz],sy*16+128:sy*16+144]=palette.codes(names)[ids].reshape(16,16,16)
            codes=palette.codes(['minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:water[level=0]','minecraft:gravel'])
            base=[s.split('[')[0]for s in palette.names];natural=np.array([s in NATURAL for s in base]);soil=np.array([s in SOIL for s in base]);air=np.array([s in AIR for s in base])
            coordinates=[];ranges=[0];offsets=[];before=[];after=[]
            for chunk,old in zip(coords,blocks):
                cx,cz=chunk;zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
                height=sample_grid(grid,'height_y',xx,zz);water=sample_grid(grid,'water',xx,zz,True)
                native=np.where(soil[old],yy,-129).max(0);highest=np.where(~air[old],yy,-129).max(0)
                distance=np.maximum.reduce([grid['x'][0]-xx,xx-grid['x'][-1],grid['z'][0]-zz,zz-grid['z'][-1]])
                t=np.clip(distance/256,0,1);t=t*t*(3-2*t)
                height=height*(1-t)+np.maximum(-120,native-144)*t
                water=np.where(distance>0,np.where(height<-82,-82,-32768),water)
                height=np.floor(height+.5).astype(np.int16)
                foreign=~natural[old];low=np.where(foreign,yy,320).min(0)-1;high=np.where(foreign,yy,-129).max(0)+5
                keep=(yy>=low)&(yy<=high)
                for px,py,pz in actors:
                    keep|=(abs(xx-px)<=4)&(abs(zz-pz)<=4)
                for Z,X in np.argwhere(foreign.any(0)):
                    protected.append([int(cx*16+X),int(low[Z,X]+1),int(cz*16+Z),int(high[Z,X]-5)])
                band=(yy>=np.maximum(-128,np.minimum(native,height)-3))&(yy<=np.maximum.reduce([highest,height,water]))&natural[old]&~keep
                desired=np.where(yy>height,np.where(yy<=water,4,0),np.where(yy==height,np.where(water>height,5,3),np.where(yy>=height-3,2,1)))
                new=old.copy();new[band]=codes[desired[band]]
                at=np.flatnonzero((old!=new).ravel()).astype(np.uint32)
                if len(at):coordinates.append(chunk);ranges.append(ranges[-1]+len(at));offsets.append(at);before.append(old.ravel()[at]);after.append(new.ravel()[at])
            np.savez_compressed(a.out/'source'/name,coordinates=np.asarray(coords,np.int32),blocks=blocks,palette=np.asarray(palette.names))
            if coordinates:
                np.savez_compressed(a.out/'delta'/name,coordinates=np.asarray(coordinates,np.int32),ranges=np.asarray(ranges,np.int64),indices=np.concatenate(offsets),before=np.concatenate(before),after=np.concatenate(after),palette=np.asarray(palette.names))
                regions.append(dict(path='delta/'+name,cells=ranges[-1]))
            print('East boundary',name,ranges[-1],'cells;',len(protected),'retained columns',flush=True)
    manifest=dict(world=str(a.world),world_written=False,bounds_xz=bounds,regions=regions,cells=sum(r['cells']for r in regions),
        preserved_generation_statuses=[[*p,s]for p,s in statuses.items()if s in stages],generation_counts=dict(Counter(statuses.values())),
        preserved_actors=actors,preserved_columns=protected,pending=['boundary interface check','cold installation and LOD'])
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=['Boundary interface check pending'],visual_verified=False),indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('world','gis','out'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
