"""Verify the installed R64 perimeter against its water, building and area-map constraints."""
from collections import Counter
from functools import lru_cache
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import argparse
import hashlib
import gzip
import io
import struct
import json

import numpy as np
from PIL import Image

from survey_r64_playtest_terrain import kind
from write_deep_cells import REGION


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


@lru_cache(None)
def atlas(folder):
    return [r for r in json.loads((folder/"index.json").read_bytes())["layers"] if r["id"]!="surface"]


@lru_cache(None)
def raster(folder,name,mask):
    with Image.open(folder/name.split("/")[-1]) as im:
        if mask:
            return np.array(im.convert("RGBA"))[:,:,3]!=0
        rgb=np.array(im.convert("RGB"))
    return (rgb[:,:,0].astype(np.int32)*256+rgb[:,:,1]-32768).astype(np.int16)


def contains(folder,layer,x,y,z):
    use=(x>=layer["minX"])&(x<layer["maxX"])&(z>=layer["minZ"])&(z<layer["maxZ"])&(y>=layer["minY"])&(y<layer["maxY"])
    if not use.any():
        return 0
    x=x[use];y=y[use];z=z[use]
    keep=np.ones(len(y),bool)
    for key in ("mask","bottom","ceiling"):
        if key not in layer:
            continue
        data=raster(folder,layer[key],key=="mask")
        zz=(z-layer["minZ"])*data.shape[0]//(layer["maxZ"]-layer["minZ"])
        xx=(x-layer["minX"])*data.shape[1]//(layer["maxX"]-layer["minX"])
        value=data[zz,xx]
        if key=="mask":
            keep&=value
        elif key=="bottom":
            keep&=y>=value
        else:
            keep&=y<value
    return int(keep.sum())


def audit(job):
    work,folder,world,rec=job
    detail=json.loads(rec.read_bytes());name=rec.stem
    if not detail["cells"]:
        return {}
    mc=name+".mca";current=digest(world/REGION/mc)
    if current!=digest(work/"staged"/mc):
        raise ValueError("Candidate changed since its native readback: "+mc)
    with np.load(work/"staged"/(name+".delta.npz")) as d:
        rows=d["rows"];pal=d["states"].tolist();sec=d["sections"];lens=d["lengths"].astype(int)
        counts=np.bincount(rows[:,1],minlength=len(pal));placed=np.bincount(rows[:,2],minlength=len(pal))
        artificial={s:int(n) for s,n in zip(pal,counts) if n and kind(s.partition("[")[0])==5 and
                    not s.partition("[")[0].endswith("_ore") and s not in ("minecraft:cobblestone","minecraft:mossy_cobblestone")}
        water=sum(int(n) for s,n in zip(pal,counts) if n and kind(s.partition("[")[0])==4)
        newwater=sum(int(n) for s,n in zip(pal,placed) if n and s.partition("[")[0]=="minecraft:water")
        y0=int(sec[:,2].min())*16
        y1=int(sec[:,2].max())*16+15
        begin=np.cumsum(np.r_[0,lens[:-1]])
        cx,cz,sy=sec.astype(np.int32).T
        hits={}
        for layer in atlas(folder):
            cand=(16*cx<layer["maxX"])&(16*cx+16>layer["minX"])&(16*cz<layer["maxZ"])&(16*cz+16>layer["minZ"])&(16*sy<layer["maxY"])&(16*sy+16>layer["minY"])
            checked=0
            for i in np.flatnonzero(cand):
                at=rows[begin[i]:begin[i]+lens[i],0].astype(np.int32)
                checked+=contains(folder,layer,cx[i]*16+(at&15),sy[i]*16+(at>>8),cz[i]*16+((at>>4)&15))
            if checked:
                hits[layer["id"]]=checked
    return dict(region=name,sha256=current,cells=len(rows),chunks=len(detail["chunks"]),original_water=water,new_water=newwater,
                other_artificial=artificial,mapped_underground=hits,section_floor_y=y0,section_roof_y=y1)


def validate_shard(job):
    work,file=job
    rx,rz=(int(v) for v in file.name.split(".")[0].split("_"))
    tag=f"r.{rx}.{rz}"
    with np.load(work/"net-stage"/(tag+".delta.npz")) as journal:
        palette=journal["states"].tolist()
        sections=journal["sections"].tolist()
        rows=journal["rows"]
        lengths=journal["lengths"]
    tested={}
    offset=0
    for key,count in zip(sections,lengths,strict=True):
        count=int(count)
        tested[tuple(key)]=rows[offset:offset+count]
        offset+=count
    before=np.load(work/"original-surface"/(tag+".npz"))
    after=np.load(work/"final-surface"/(tag+".npz"))
    dry=(before["k"]==3)&(after["k"]==3)
    height=after["h"]
    before.close()
    after.close()
    stream=io.BytesIO(gzip.decompress(file.read_bytes()))
    def nbyte():
        return stream.read(1)[0]
    def nshort():
        return struct.unpack(">H",stream.read(2))[0]
    names=[stream.read(nshort()).decode("ascii") for _ in range(nshort())]
    lut=np.array([palette.index(v) for v in names],np.int32)
    seen=set()
    count=0
    height_count=0
    for _ in range(nshort()):
        slot=nshort()
        cx=rx*32+(slot&31);cz=rz*32+(slot>>5)
        n=nshort()
        offsets=np.frombuffer(stream.read(n),np.uint8)
        wireh=np.frombuffer(stream.read(n*2),">i2")
        ix=(cx%32)*16;iz=(cz%32)*16
        expected=np.flatnonzero(dry[iz:iz+16,ix:ix+16].ravel())
        assert np.array_equal(offsets,expected) and np.array_equal(wireh,height[iz:iz+16,ix:ix+16].ravel()[expected]),(tag,cx,cz)
        height_count+=n
        for _ in range(nbyte()):
            sy=struct.unpack("b",stream.read(1))[0]
            key=(cx,cz,sy)
            if key in seen or key not in tested:
                raise ValueError("Unexpected or duplicate generation section")
            seen.add(key)
            runs=np.frombuffer(stream.read(4*nshort()),np.uint8).reshape(-1,4).astype(np.int32)
            span=(runs[:,1]&15)-(runs[:,1]>>4)+1
            if np.any(span<=0):
                raise ValueError("Inverted generation interval")
            section=tested[key]
            # Reconstruct both sides independently from the binary runs as
            # consumed by the Java generator, comparing every indexed voxel.
            if int(span.sum())!=len(section):
                raise ValueError("Truncated generation journal")
            old=np.full(4096,-1,np.int32);new=old.copy()
            for k in range(int(span.max())):
                valid=span>k
                ids=((runs[valid,1]>>4)+k)*256+runs[valid,0]
                if np.any(old[ids]!=-1) or len(np.unique(ids))!=len(ids):
                    raise ValueError("Overlapping generated voxels")
                old[ids]=lut[runs[valid,2]];new[ids]=lut[runs[valid,3]]
            pos=section[:,0]
            assert np.array_equal(np.flatnonzero(old>=0),pos)
            assert np.array_equal(old[pos],section[:,1]) and np.array_equal(new[pos],section[:,2])
            count+=len(pos)
    if seen!=set(tested) or stream.read(1):
        raise ValueError("Generation shard does not cover its cold journal")
    return file.name,count,height_count,digest(file)


def verify_recipe(work,workers):
    path=work/"ship_mod_resources/data/projectseele/worldgen/playtest_landscape_r64"
    header=(path/"index.bin").read_bytes()
    magic,num=struct.unpack(">IH",header[:6])
    coords=list(struct.iter_unpack(">hh",header[6:]))
    if magic!=0x534c3634 or len(coords)!=num or len(set(coords))!=num:
        raise ValueError("Invalid installed generation index")
    blobs={path/f"{x}_{z}.bin.gz" for x,z in coords}
    if blobs!=set(path.glob("*.bin.gz")):
        raise ValueError("Unindexed generation shard")
    with ProcessPoolExecutor(workers) as pool:
        checks=list(pool.map(validate_shard,[(work,f) for f in sorted(blobs)]))
    total=sum(c[1] for c in checks)
    n=sum(c[2] for c in checks)
    hashes={c[0]:c[3] for c in checks}
    hashes["index.bin"]=digest(path/"index.bin")
    report=dict(regions=num,verified_voxels=total,verified_heights=n,bytes=sum(f.stat().st_size for f in path.iterdir()),sha256=hashes)
    (work/"recipe-verification.json").write_text(json.dumps(report,indent=2),"utf8")
    print({k:v for k,v in report.items() if k!="sha256"},flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("work","atlas","world"):
        p.add_argument(key,type=Path)
    p.add_argument("--workers",type=int,default=4)
    p.add_argument("--recipe",action="store_true")
    a=p.parse_args()
    if a.recipe:
        verify_recipe(a.work,a.workers)
        return
    jobs=[(a.work,a.atlas,a.world,f) for f in sorted((a.work/"staged").glob("r.*.json"))]
    with ProcessPoolExecutor(a.workers) as pool:
        rows=[r for r in pool.map(audit,jobs) if r]
    report=dict(regions=len(rows),chunks=sum(r["chunks"] for r in rows),cells=sum(r["cells"] for r in rows),
                changed_existing_water=sum(r["original_water"] for r in rows),new_water_cells=sum(r["new_water"] for r in rows),
                changed_authored_states=dict(sum((Counter(r["other_artificial"]) for r in rows),Counter())),
                intersections_with_underground_layers=dict(sum((Counter(r["mapped_underground"]) for r in rows),Counter())))
    (a.work/"world-verification.json").write_text(json.dumps(dict(**report,regions_sha256={r["region"]:r["sha256"] for r in rows}),indent=2),"utf8")
    print(report)
    if report["changed_authored_states"] or report["changed_existing_water"] or report["intersections_with_underground_layers"]:
        raise ValueError("Review changed protected cells")


if __name__=="__main__":
    main()
