"""Author the complete GSI Lake Ashi shoreline and restore the old scaled basin.

The plan uses the cached geographic water polygon and a playable graded bed,
not a claim to surveyed bathymetry. Real station and road interfaces follow in
the same basin batch before installation. Existing devices stay untouched.
"""
import argparse, json, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from prepare_hakone_main_terrain import capture, sample_grid, smooth, MIN_Y, MAX_Y
from plan_ashi_landscape_r54 import NATURAL
from export_patch_lod_r54 import stopped_world
from query_blocks import dimension_dir
from transplant_s22_authority import read_region,parse_chunk


def actor_columns(world,bounds):
    x0,z0,x1,z1=bounds;mask=np.zeros((z1-z0+1,x1-x0+1),bool);rows=[]
    folder=dimension_dir(world,'projectseele:geofront')/'entities'
    for rx in range(x0//512,x1//512+1):
        for rz in range(z0//512,z1//512+1):
            file=folder/f'r.{rx}.{rz}.mca'
            if not file.exists()or not file.stat().st_size:continue
            _,records=read_region(file)
            for raw in records:
                if raw is None:continue
                for e in parse_chunk(raw).get('Entities',[]):
                    pos=list(map(float,e.get('Pos',[])))
                    if len(pos)!=3 or not(x0<=pos[0]<=x1 and z0<=pos[2]<=z1 and 32<=pos[1]<MAX_Y):continue
                    x,z=math.floor(pos[0]),math.floor(pos[2])
                    mask[max(0,z-z0-4):min(z1-z0+1,z-z0+5),max(0,x-x0-4):min(x1-x0+1,x-x0+5)]=True
                    rows.append(dict(id=str(e.get('id','')),pos=pos,uuid=list(map(int,e.get('UUID',[])))))
    return mask,rows


def distance_from(mask, maximum):
    d=np.where(mask,0,maximum+1).astype(np.int16)
    for _ in range(maximum):
        for a,b in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),
                    (np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])]:
            d[a]=np.minimum(d[a],d[b]+1)
    return d


def prepare(a):
    bounds=(-1216,768,639,2495);x0,z0,x1,z1=bounds
    if a.out.exists():raise ValueError('Use a new candidate directory')
    (a.out/'source').mkdir(parents=True);(a.out/'delta').mkdir()
    measured,files,status=capture(a.world,bounds,a.out)
    zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    with np.load(a.gis/'terrain-design.npz')as saved:grid={k:saved[k]for k in ('x','z','height_y')}
    with np.load(a.gis/'lake-basin-mask.npz')as saved:water_grid={k:saved[k]for k in ('x','z','lake')}
    lake=sample_grid(water_grid,'lake',xx,zz,True)
    if np.any(lake&~measured['full']):raise ValueError('Complete lake basin contains unfinished chunks; generate them in the offline staging world first')
    height=sample_grid(grid,'height_y',xx,zz)
    actors,actor_rows=actor_columns(a.world,bounds)
    held=measured['protected']|actors|~measured['full']|~np.isfinite(height)|(measured['top']<MIN_Y)
    held=np.asarray(Image.fromarray(held).filter(ImageFilter.MaxFilter(13)),bool)
    distance=distance_from(held,64)
    border=np.minimum.reduce([xx-x0,x1-xx,zz-z0,z1-zz])
    blend=smooth(np.minimum(distance,border)/64)
    target=np.rint(measured['top']+(np.nan_to_num(height)-measured['top'])*blend).astype(np.int16)
    water_y=99
    # Up to twelve blocks of depth; shallow margins permit swimming/walking
    # approaches. Depth is authored gameplay geometry, coastline is GSI.
    depth=np.clip(1+distance_from(~lake,60)//5,1,12)
    wet=lake&~held
    target[wet]=water_y-depth[wet]
    active=(distance>0)&(border>0)&measured['full']
    yy=np.arange(MIN_Y,MAX_Y)[:,None,None];count=0;changes=[];conflicts=[]
    for number,file in enumerate(files):
        with np.load(a.out/file)as saved:coords=saved['coordinates'];palette=list(map(str,saved['palette']));blocks=saved['blocks']
        for s in ('minecraft:water[level=0]','minecraft:gravel','minecraft:sand'):
            if s not in palette:palette.append(s)
        water_id,gravel_id,sand_id=(palette.index(s)for s in ('minecraft:water[level=0]','minecraft:gravel','minecraft:sand'))
        allowed=np.asarray([s.split('[')[0]in NATURAL for s in palette])
        ranges=[0];indices=[];before=[];after=[];changed=[]
        for i,(cx,cz)in enumerate(coords):
            area=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16]
            mask=active[area];h=target[area];w=wet[area]
            if not mask.any():continue
            old=blocks[i];lower=np.minimum(measured['top'][area],h)-3
            upper=np.maximum(measured['highest'][area],np.where(w,water_y,h))
            band=mask[None,:,:]&(yy>=lower)&(yy<=upper)
            unsafe=(band&~allowed[old]).any(0)
            if np.any(unsafe&w):conflicts.append(dict(chunk=[int(cx),int(cz)],columns=int((unsafe&w).sum())))
            band&=~unsafe[None,:,:]
            proposed=np.where(yy>h,0,np.where(yy==h,3,np.where(yy>=h-3,2,1)))
            proposed=np.where(w[None,:,:],np.where(yy>water_y,0,np.where(yy>h,water_id,np.where(yy>=h-2,np.where(depth[area]<4,sand_id,gravel_id),1))),proposed).astype(np.uint16)
            at=np.flatnonzero((band&(old!=proposed)).ravel()).astype(np.uint32)
            if not len(at):continue
            indices.append(at);before.append(old.ravel()[at]);after.append(proposed.ravel()[at]);changed.append((cx,cz));ranges.append(ranges[-1]+len(at))
        if changed:
            name='delta/'+Path(file).name
            np.savez_compressed(a.out/name,coordinates=np.asarray(changed,np.int32),ranges=np.asarray(ranges,np.int64),
                indices=np.concatenate(indices),before=np.concatenate(before),after=np.concatenate(after),palette=np.asarray(palette))
            count+=ranges[-1];changes.append(dict(path=name,cells=ranges[-1]))
        print(f'Lake basin {number+1}/{len(files)} regions; {count:,} changed blocks',flush=True)
    np.savez_compressed(a.out/'surface.npz',bounds=bounds,**measured,target=target,lake=lake,wet=wet,active=active,held=held)
    report=dict(schema='projectseele.hakone.complete-lake-basin.v1',world=str(a.world.resolve()),world_written=False,
        bounds_xz=bounds,vertical_bounds=[MIN_Y,MAX_Y],water_y=water_y,cells=count,regions=changes,
        protected_lake_columns=int((lake&held).sum()),buried_conflicts=conflicts,protected_actors=actor_rows,
        lake_source='cached GSI water polygon',bed='graded gameplay basin; not surveyed bathymetry',
        remaining=['Resolve authored lake interfaces','Togendai station, pier and shoreline street','Cold installation and changed LOD'])
    (a.out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k!='regions'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('world','gis','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    with stopped_world(a.world):prepare(a)
