"""Build compact, reversible main-map terrain deltas from the real GSI relief.

Only measured FULL chunks and natural surface columns are changed. Existing
facilities, city shafts and approaches are retained for their component pass.
Water bodies are reserved for a complete basin pass, not cut at this tile edge.
This command prepares actual block edits; it never writes the playable save.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
from query_blocks import AIR,chunk_statuses,iter_selected_sections
from install_r53_carrier_trays import stopped_world
from plan_ashi_landscape_r54 import SOIL,NATURAL

DIM="projectseele:geofront"
MIN_Y,MAX_Y=-128,320
SHAPE=(MAX_Y-MIN_Y,16,16)
SURFACES=("minecraft:air","minecraft:stone","minecraft:dirt","minecraft:grass_block[snowy=false]")


def smooth(value):
    t=np.clip(value,0,1)
    return t*t*(3-2*t)


def sample_grid(data,key,x,z,nearest=False):
    xs,zs=data["x"],data["z"];values=data[key]
    fx=np.clip((x-xs[0])/(xs[1]-xs[0]),0,len(xs)-1)
    fz=np.clip((z-zs[0])/(zs[1]-zs[0]),0,len(zs)-1)
    if nearest:return values[np.rint(fz).astype(int),np.rint(fx).astype(int)]
    ix,iz=fx.astype(int),fz.astype(int);jx=np.minimum(ix+1,len(xs)-1);jz=np.minimum(iz+1,len(zs)-1)
    dx,dz=fx-ix,fz-iz
    return ((values[iz,ix]*(1-dx)+values[iz,jx]*dx)*(1-dz)
            +(values[jz,ix]*(1-dx)+values[jz,jx]*dx)*dz)


def capture(world,bounds,out):
    x0,z0,x1,z1=bounds;shape=(z1-z0+1,x1-x0+1)
    selected={(cx,cz):set(range(MIN_Y//16,MAX_Y//16)) for cx in range(x0//16,x1//16+1) for cz in range(z0//16,z1//16+1)}
    status=chunk_statuses(world,DIM,selected)
    groups=defaultdict(dict)
    for p,ys in selected.items():
        if status[p]=="full":groups[p[0]//32,p[1]//32][p]=ys
    top=np.full(shape,MIN_Y-1,dtype=np.int16);highest=top.copy()
    protected=np.zeros(shape,bool);full=np.zeros(shape,bool);files=[]
    yy=np.arange(MIN_Y,MAX_Y,dtype=np.int16)[:,None,None]
    for region,chosen in sorted(groups.items()):
        palette=list(SURFACES);lookup={s:i for i,s in enumerate(palette)}
        coords=sorted(chosen);index={c:i for i,c in enumerate(coords)}
        # Missing sections of a FULL chunk are native air. Unfinished chunks
        # never enter this array, so missing generation is not treated as air.
        blocks=np.zeros((len(coords),*SHAPE),dtype=np.uint16)
        for cx,cz,sy,pal,ids in iter_selected_sections(world,DIM,chosen):
            for s in pal:
                if s not in lookup:lookup[s]=len(palette);palette.append(s)
            if len(palette)>65535:raise ValueError("Palette overflow")
            codes=np.asarray([lookup[s]for s in pal],dtype=np.uint16)
            start=sy*16-MIN_Y;blocks[index[cx,cz],start:start+16]=codes[ids].reshape(16,16,16)
        names=[s.split("[")[0]for s in palette]
        soil=np.asarray([s in SOIL for s in names]);natural=np.asarray([s in NATURAL for s in names]);air=np.asarray([s in AIR for s in names])
        for i,(cx,cz)in enumerate(coords):
            section=(slice(cz*16-z0,cz*16-z0+16),slice(cx*16-x0,cx*16-x0+16))
            b=blocks[i];ground=np.where(soil[b],yy,MIN_Y-1).max(0)
            top[section]=ground;highest[section]=np.where(~air[b],yy,MIN_Y-1).max(0)
            # Keep all authored surface columns, including material well
            # below a bridge, so grading cannot undermine the approach.
            protected[section]=((~natural[b])&(yy>=32)).any(0)
            full[section]=True
        path=f"source/r.{region[0]}.{region[1]}.npz"
        np.savez_compressed(out/path,coordinates=np.asarray(coords,dtype=np.int32),palette=np.asarray(palette),blocks=blocks)
        files.append(path)
        print(f"Measured main terrain {len(files)}/{len(groups)} regions",flush=True)
    return dict(top=top,highest=highest,protected=protected,full=full),files,status


def design(gis,bounds,measured):
    x0,z0,x1,z1=bounds
    zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    # Decompress each design array once, never per chunk/sample.
    with np.load(gis/"terrain-design.npz")as saved:
        data={k:saved[k]for k in ("x","z","height_y","sea","inland_water","city_platform")}
    height=sample_grid(data,"height_y",xx,zz)
    water=sample_grid(data,"sea",xx,zz,True)|sample_grid(data,"inland_water",xx,zz,True)
    city=sample_grid(data,"city_platform",xx,zz,True)
    # Full waterways and the complete lift component are separate batches.
    held=measured["protected"]|~measured["full"]|water|city|~np.isfinite(height)|(measured["top"]<MIN_Y)
    held=np.asarray(Image.fromarray(held).filter(ImageFilter.MaxFilter(25)),dtype=bool)
    distance=np.where(held,0,65).astype(np.int16)
    distance=np.minimum(distance,np.minimum.reduce([xx-x0,x1-xx,zz-z0,z1-zz]).astype(np.int16))
    # Bounded Manhattan feather; no optional scipy/native runtime dependency.
    for _ in range(64):
        for dest,src in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),(np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])]:
            distance[dest]=np.minimum(distance[dest],distance[src]+1)
    blend=smooth(distance/64)
    target=np.rint(measured["top"]+(np.nan_to_num(height)-measured["top"])*blend).astype(np.int16)
    active=(distance>0)&measured["full"]&(target!=measured["top"])
    return dict(target=target,active=active,water_reserved=water,city_reserved=city,feather_distance=distance)


def deltas(out,bounds,measured,design,files):
    x0,z0,_,_=bounds;yy=np.arange(MIN_Y,MAX_Y)[:,None,None]
    result=[];count=0;held_cells=0
    for number,source in enumerate(files):
        with np.load(out/source)as saved:
            coords=saved["coordinates"];palette=list(map(str,saved["palette"]));blocks=saved["blocks"]
        allowed=np.asarray([s.split("[")[0]in NATURAL for s in palette])
        ranges=[0];indices=[];before=[];after=[];changed=[]
        for i,(cx,cz)in enumerate(coords):
            area=(slice(cz*16-z0,cz*16-z0+16),slice(cx*16-x0,cx*16-x0+16))
            active=design["active"][area];height=design["target"][area]
            if not active.any():continue
            old=blocks[i]
            lower=np.minimum(measured["top"][area],height)-3
            upper=np.maximum(measured["highest"][area],height)
            band=active[None,:,:]&(yy>=lower)&(yy<=upper)
            # Any buried device in the affected vertical band retains its
            # whole column, including its air volume; no disconnected pillars.
            unsafe=(band&~allowed[old]).any(0);held_cells+=int(unsafe.sum())
            band&=~unsafe[None,:,:]
            proposed=np.where(yy>height,0,np.where(yy==height,3,np.where(yy>=height-3,2,1))).astype(np.uint16)
            offsets=np.flatnonzero((band&(old!=proposed)).ravel()).astype(np.uint32)
            if not len(offsets):continue
            indices.append(offsets);before.append(old.ravel()[offsets]);after.append(proposed.ravel()[offsets])
            ranges.append(ranges[-1]+len(offsets));changed.append((cx,cz))
        if changed:
            path="delta/"+Path(source).name
            np.savez_compressed(out/path,coordinates=np.asarray(changed,dtype=np.int32),ranges=np.asarray(ranges,dtype=np.int64),
                                indices=np.concatenate(indices),before=np.concatenate(before),after=np.concatenate(after),palette=np.asarray(palette))
            result.append(dict(path=path,chunks=len(changed),cells=ranges[-1]));count+=ranges[-1]
        print(f"Prepared terrain delta {number+1}/{len(files)} regions; {count:,} changed cells",flush=True)
    return result,count,held_cells


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("world","gis","out"):p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--bounds",type=int,nargs=4,default=[-1024,-768,1535,1023],metavar=("X0","Z0","X1","Z1"))
    a=p.parse_args();bounds=a.bounds
    if any(v%16 for v in bounds[:2])or any((v+1)%16 for v in bounds[2:]):p.error("Bounds must cover complete chunks")
    if bounds[2]<bounds[0]or bounds[3]<bounds[1]:p.error("Ordered bounds required")
    if a.out.exists():p.error("A fresh output directory is required")
    if a.world.resolve()==a.out.resolve()or a.world.resolve()in a.out.resolve().parents:p.error("Output must stay outside the actual save")
    (a.out/"source").mkdir(parents=True);(a.out/"delta").mkdir()
    with stopped_world(a.world):
        measured,files,status=capture(a.world,bounds,a.out)
        planned=design(a.gis,bounds,measured)
        changes,count,held=deltas(a.out,bounds,measured,planned,files)
        np.savez_compressed(a.out/"surface.npz",bounds=np.asarray(bounds),**measured,**planned)
        report=dict(schema="projectseele.hakone.natural-terrain-delta.v1",world=str(a.world.resolve()),dimension=DIM,
                    bounds_xz=bounds,vertical_bounds=[MIN_Y,MAX_Y],world_written=False,cells=count,
                    regions=changes,chunk_statuses=dict(Counter(status.values())),
                    unavailable_chunks=[[*pos,state]for pos,state in status.items()if state!="full"],
                    original_surface_columns_retained=int(measured["protected"].sum()),buried_device_columns_retained=held,
                    active_columns=int(planned["active"].sum()),identity_progress_files_modified=False,
                    inverse="Same region indices/palette; swap before and after arrays",
                    pending=["component relocation and street reconstruction","complete lake/river basin pass",
                             "cold installation and changed-region LOD"]
                            +(["missing-chunk terrain generation"]if any(s!="full"for s in status.values())else[]))
        (a.out/"manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        print(json.dumps({k:v for k,v in report.items()if k not in ("regions","unavailable_chunks")},ensure_ascii=False),flush=True)


if __name__=="__main__":main()
