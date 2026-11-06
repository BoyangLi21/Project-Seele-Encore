"""Prepare an expanded geographic eastern surface; never change a saved world.

The old geographic core ended at X4386. A finite DEM/vector extension supplies
the commissioned city through X4511 and a separately identified outer blend.
Applying this design still requires a fresh FULL-block and ownership survey.
"""
import argparse,gzip,json,math,struct
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt
from shapely.geometry import shape,box
from shapely.ops import unary_union
from shapely import contains_xy
from hakone_geography import Frame,tile_xy,fetch_tile,decode_dem,sample_dem
from plan_hakone_geography import close_dem_gaps
from map_pipeline.outer_surface_field import read_field,smooth

def prepare(a):
    a.out.mkdir(parents=True,exist_ok=False)
    cfg=json.loads((a.gis/'geography.json').read_text('utf8'));frame=Frame(cfg);zoom=int(cfg['dem_zoom'])
    source=json.load(gzip.open(a.geography/'features.world.geojson.gz','rt',encoding='utf8'))
    bounds=[4256,-1456,4766,1726];x,z,X,Z=bounds
    if not source['provenance']['complete']:raise ValueError('Incomplete eastern vector survey')
    gb=source['provenance']['bounds_xz']
    if not(gb[0]<=x<X<=gb[2]and gb[1]<=z<Z<=gb[3]):raise ValueError('Terrain exceeds finite geographic coverage')
    west,north=frame.geographic(x,z);east,south=frame.geographic(X,Z)
    tx,ty=map(math.floor,tile_xy(west,north,zoom));TX,TY=map(math.floor,tile_xy(east,south,zoom))
    counts=Counter();jobs=[(i,j)for i in range(tx,TX+1)for j in range(ty,TY+1)]
    if len(jobs)>100:raise ValueError('Unbounded DEM request')
    if a.fetch:
        with ThreadPoolExecutor(max_workers=4)as pool:
            pending=[pool.submit(fetch_tile,a.gis,'dem_png',zoom,i,j,'png')for i,j in jobs]
            for p in as_completed(pending):_,status=p.result();counts[status]+=1
    mosaic=np.full(((TY-ty+1)*256,(TX-tx+1)*256),np.nan,np.float32)
    absent=[]
    for i,j in jobs:
        path=a.gis/f'tiles/dem_png/{zoom}/{i}/{j}.png'
        if not path.exists():absent.append([zoom,i,j]);continue
        mosaic[(j-ty)*256:(j-ty+1)*256,(i-tx)*256:(i-tx+1)*256]=decode_dem(path)
    zz,xx=np.mgrid[z:Z+1:2,x:X+1:2];lon,lat=frame.geographic(xx,zz);elevation=sample_dem((mosaic,tx,ty,zoom),lon,lat)
    clip=box(*bounds);seas=[];rivers=[]
    for f in source['features']:
        if f['properties']['source_layer']!='WA':continue
        g=shape(f['geometry'])
        if not g.intersects(clip):continue
        (seas if f['properties']['vt_code']==5100 else rivers).append(g.intersection(clip))
    sea=contains_xy(unary_union(seas),xx,zz);inland=contains_xy(unary_union(rivers),xx,zz)
    measured=np.isfinite(elevation);elevation,filled=close_dem_gaps(elevation,sea,iterations=4)
    if not np.isfinite(elevation).all():raise ValueError(('Unresolved geographic elevation gaps',int((~np.isfinite(elevation)).sum())))
    geographic=frame.height(elevation)
    # Open sea DEM has no seabed measurement. Its designed submerged bed is
    # explicitly distinct from measured dry-land elevation, and slopes away
    # from shore rather than forming a cliff at the first wet column.
    shore_distance=distance_transform_edt(sea,sampling=2)
    geographic[sea]=-83-np.minimum(12,shore_distance[sea]*.4)
    geographic[~sea]=np.maximum(geographic[~sea],-81)
    header,height,water=read_field(a.previous_field/'hakone_surface.bin.gz');_,fx,fz,step,w,h=header
    if step!=2 or (x-fx)%step or (z-fz)%step:raise ValueError('Misaligned runtime field')
    raw=gzip.decompress((a.previous_field/'hakone_surface_blend.bin.gz').read_bytes())
    if struct.unpack('>6i',raw[:24])!=(0x484B4231,*header[1:]):raise ValueError('Mismatched blend resource')
    blend=np.frombuffer(raw[24:],np.uint8).reshape(h,w).copy()
    area=np.s_[(z-fz)//2:(Z-fz)//2+1,(x-fx)//2:(X-fx)//2+1]
    old=height[area].astype(float)/16;oldwater=water[area].copy();oldblend=blend[area].copy()
    if old.shape!=geographic.shape:raise ValueError('Finite extension exceeds bounded field')
    if np.any(oldwater==62):raise ValueError('Legacy high water requires its own surveyed bank design')
    weight=smooth((xx-x)/128)*smooth((X-xx)/254)*smooth((zz-z)/128)*smooth((Z-zz)/126)
    fixed=np.rint((old*(1-weight)+geographic*weight)*16).astype(np.int16)
    proposed_water=np.where(sea,-82,-32768).astype(np.int16)
    chosen=weight>=.5;newwater=np.where(chosen,proposed_water,oldwater)
    # Keep the low sea's potential datum under reclaimed dry land. Switching
    # it to NO_WATER while native blending is nonzero activates the runtime
    # water-mode divide and makes a false crest beside the same low ocean.
    # Ground at/above -81 remains dry even with the potential datum at -82.
    newwater[weight>0]=-82
    # Contain the retained low sea on both sides of a mode boundary.
    dry=chosen&~sea;fixed[dry]=np.maximum(fixed[dry],-81*16)
    newblend=np.rint(oldblend*(1-weight)).astype(np.uint8)
    height[area]=fixed;water[area]=newwater;blend[area]=newblend
    payload=struct.pack('>6i',*header)+height.astype('>i2').tobytes()+water.astype('>i2').tobytes()
    (a.out/'hakone_surface.bin.gz').write_bytes(gzip.compress(payload,compresslevel=6,mtime=0))
    (a.out/'hakone_surface_blend.bin.gz').write_bytes(gzip.compress(struct.pack('>6i',0x484B4231,*header[1:])+blend.tobytes(),compresslevel=6,mtime=0))
    np.savez_compressed(a.out/'geographic-design.npz',bounds=bounds,x=xx[0],z=zz[:,0],height_y=geographic,sea=sea,inland_water=inland,
        measured_dem=measured,old_height=old,old_water=oldwater,old_blend=oldblend,weight=weight,proposed_height=fixed.astype(float)/16,proposed_water=newwater,proposed_blend=newblend)
    core=(xx>=4384)&(xx<=4512)&(zz>=-1328)&(zz<=1600)
    if np.any(weight[core]<1-1e-8)or np.any(newblend[core]):raise ValueError('Commissioned eastern core still uses old/noise blend')
    report=dict(status='geographic design only; fresh saved-block ownership and edge verification required',bounds_xz=bounds,commissioned_core=[4384,-1328,4512,1600],
        dem_zoom=zoom,dem_tiles=len(jobs),absent_dem_tiles=absent,retrieval_counts=dict(counts),land_gap_samples_interpolated=int((~measured&~sea).sum()),
        remaining_dem_gaps=0,sea_samples=int(sea.sum()),inland_water_samples_reserved=int(inland.sum()),
        maximum_old_core_land_height_error=float(abs(old[core&~sea]-geographic[core&~sea]).max()),
        proposed_core_land_quantization_error=float(abs(fixed[core&~sea]/16-geographic[core&~sea]).max()),
        old_core_sea_without_water=int((core&sea&(oldwater!=-82)).sum()),proposed_core_sea_without_water=int((core&sea&(newwater!=-82)).sum()),
        changed_height_samples=int((fixed!=np.rint(old*16)).sum()),changed_water_samples=int((newwater!=oldwater).sum()),
        old_field=str(a.previous_field),geographic_source=str(a.geography),world_written=False,approved_for_installation=False,
        caveat='Dry elevations follow cached GSI DEM; seabed is an explicit coastal slope design. Narrow rivers remain reserved for measured channel authoring.')
    (a.out/'design.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('gis','geography','previous-field','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--fetch',action='store_true');prepare(p.parse_args())
