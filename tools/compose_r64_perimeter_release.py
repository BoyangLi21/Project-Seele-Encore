"""Compose a verified follow-up journal over a previous complete R64 generation release.

Unchanged generation members are linked byte-for-byte. Updated regional members
are rebuilt from the complete baseline-to-final voxel journal and the installed
MCA readback. The optional checkout install writes only the ignored private
generation resources, publishing the new index after every member is present.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import struct

import numpy as np

from blend_r64_map_perimeter import freeze,install,link_or_copy,parallel
from compose_r64_playtest_terrain import merge
from package_r64_playtest_terrain import package
from verify_r64_map_perimeter import digest
from verify_r64_playtest_refinement import rescan
from stage_r64_playtest_terrain import save_verified_region
from write_deep_cells import REGION,read_chunk,write_chunk,encode,decode,clear_light

RESOURCES=Path("data/projectseele/worldgen/playtest_landscape_r64")



def rebase_region(job):
    incoming,baseline,out,tag=job
    source=baseline/REGION/(tag+".mca")
    receipt=out/(tag+".json")
    if receipt.exists():
        return
    fresh=json.loads((incoming/(tag+".json")).read_bytes())
    if not fresh["cells"]:
        receipt.write_text(json.dumps(fresh))
        return
    with np.load(incoming/(tag+".delta.npz")) as journal:
        sections=journal["sections"].tolist();lengths=journal["lengths"].tolist()
        rows=journal["rows"];states=journal["states"].tolist()
    offset=0
    chunks=defaultdict(dict)
    for (cx,cz,sy),count in zip(sections,lengths,strict=True):
        chunks[cx,cz][sy]=rows[offset:offset+count];offset+=count
    old=source.read_bytes()
    buf=bytearray(old)
    new_journal={};written=[];already=0
    index={name:i for i,name in enumerate(states)}
    def code(name):
        if name not in index:
            index[name]=len(states);states.append(name)
        return index[name]
    for (cx,cz),parts in chunks.items():
        idx,loc,count,chunk=read_chunk(old,cx,cz)
        touched=False
        for section in chunk["sections"]:
            sy=int(section["Y"])
            if sy not in parts:continue
            part=parts[sy]
            pos,before,after=part.T
            ids,names=decode(section["block_states"])
            lut=np.array([code(n) for n in names],np.uint16)
            current=lut[ids[pos]]
            conflict=(current!=before)&(current!=after)
            if conflict.any():
                first=int(np.flatnonzero(conflict)[0])
                i=int(pos[first])
                where=(cx*16+i%16,sy*16+(i>>8),cz*16+((i>>4)&15))
                raise ValueError(f"Conflicting proposed change at {where}: {states[current[first]]}, expected {states[before[first]]}")
            take=current==before
            already+=int((~take).sum())
            if not take.any():continue
            reverse={name:i for i,name in enumerate(names)}
            for v in np.unique(after[take]):
                name=states[v]
                if name not in reverse:
                    reverse[name]=len(names);names.append(name)
            local=np.zeros(len(states),np.int32)
            for v in np.unique(after[take]):
                local[v]=reverse[states[v]]
            ids[pos[take]]=local[after[take]]
            encode(section["block_states"],ids,names)
            new_journal[cx,cz,sy]=part[take]
            touched=True
        if touched:
            written.append((cx,cz))
            clear_light(chunk);chunk.pop("Heightmaps",None)
            write_chunk(buf,idx,loc,count,chunk)
    save_verified_region(out,tag,buf,old,new_journal,states,written)
    receipt.write_text(json.dumps(dict(chunks=written,cells=sum(map(len,new_journal.values())),
                                       identical_preexisting_changes=already,columns=fresh.get("columns",0))))


def rebase(incoming,world,out,workers):
    """Stage a parallel native journal against installed blocks without losing other work."""
    tags=[p.stem for p in sorted((incoming/"staged").glob("r.*.json")) if json.loads(p.read_bytes())["cells"]]
    pairs=[tuple(map(int,t.split(".")[1:3])) for t in tags]
    out.mkdir(exist_ok=True,parents=True)
    cold=freeze(world,out,pairs)
    stage=out/"staged";stage.mkdir(exist_ok=True)
    # Exact matching cold MCAs can be reused directly. Overlapping regional
    # histories require verifying the before/after state of each planned cell.
    jobs=[]
    for tag in tags:
        path=incoming/"cold"/REGION/(tag+".mca")
        if not path.exists() and (incoming/"cold"/(tag+".mca")).is_file():
            path=incoming/"cold"/(tag+".mca")
        if path.exists() and digest(path)==digest(cold/REGION/path.name):
            for f in (incoming/"staged").glob(tag+".*"):
                link_or_copy(f,stage/f.name)
        else:
            jobs.append((incoming/"staged",cold,stage,tag))
    parallel(rebase_region,jobs,workers)
    rows=[json.loads(f.read_bytes()) for f in stage.glob("r.*.json")]
    cc=sorted(c for r in rows for c in r["chunks"])
    (out/"changed-chunks.json").write_text(json.dumps(cc,separators=(",",":")))
    print("rebased regions/chunks/cells",len(rows),len(cc),sum(r["cells"] for r in rows),flush=True)


def compose(previous,follow,out,workers):
    stage=follow/"staged"
    prior=previous/"net-stage"
    former=previous/"ship_mod_resources"/RESOURCES
    resource=out/"ship_mod_resources"/RESOURCES
    resource.mkdir(exist_ok=True,parents=True)
    local=out/"net-stage";local.mkdir(exist_ok=True)
    for sub in ("original-surface","final-surface","partial","subnet","subset","empty-stage"):
        (out/sub).mkdir(exist_ok=True)
    new={f.stem for f in stage.glob("r.*.json") if json.loads(f.read_bytes())["cells"]}
    tags=new|{f.stem for f in prior.glob("r.*.json")}
    scans=[];merges=[]
    for tag in sorted(tags):
        name=tag+".npz"
        orig=previous/"original-surface"/name
        pre=previous/"final-surface"/name
        if not orig.is_file() or not pre.is_file():
            if not (follow/"before"/name).is_file():
                raise FileNotFoundError("Missing surface baseline: "+tag)
            orig=pre=follow/"before"/name
        link_or_copy(orig,out/"original-surface"/name)
        if tag in new:
            base=prior
            if not (prior/(tag+".json")).is_file():
                base=out/"empty-stage"
                (base/(tag+".json")).write_text('{"chunks":[],"cells":0,"columns":0}')
            merges.append((base,stage,local,tag))
            updates=json.loads((stage/(tag+".json")).read_bytes())["chunks"]
            link_or_copy(stage/(tag+".mca"),out/"readback-world"/REGION/(tag+".mca"))
            scans.append((out/"readback-world",pre.parent,out/"partial",out/"final-surface",tag,updates))
        else:
            for f in prior.glob(tag+".*"):
                link_or_copy(f,local/f.name)
            link_or_copy(pre,out/"final-surface"/name)
    parallel(merge,merges,workers)
    parallel(rescan,scans,workers)
    for tag in new:
        for path in local.glob(tag+".*"):
            if path.suffix!=".mca":
                link_or_copy(path,out/"subnet"/path.name)
    package(out/"subnet",out/"original-surface",out/"final-surface",out/"subset")
    coords=[]
    for f in sorted(local.glob("r.*.delta.npz")):
        rx,rz=map(int,f.stem.split(".")[1:3])
        coords.append((rx,rz))
        name=f"{rx}_{rz}.bin.gz"
        base=out/"subset" if f"r.{rx}.{rz}" in new else former
        link_or_copy(base/name,resource/name)
    (resource/"index.bin").write_bytes(struct.pack(">IH",0x534c3634,len(coords))+b"".join(struct.pack(">hh",*c) for c in coords))
    cells=sum(json.loads(f.read_bytes())["cells"] for f in local.glob("r.*.json"))
    hashes={f.name:digest(f) for f in sorted(resource.iterdir())}
    manifest=dict(regions=len(coords),repackaged=len(new),cumulative_voxels=cells,
                  bytes=sum(f.stat().st_size for f in resource.iterdir()),sha256=hashes)
    (out/"delivery.json").write_text(json.dumps(manifest,indent=2),"utf8")
    print({k:v for k,v in manifest.items() if k!="sha256"},flush=True)


def publish(release,checkout):
    source=release/"ship_mod_resources"/RESOURCES
    manifest=json.loads((release/"delivery.json").read_bytes())
    dest=checkout/"src/main/resources"/RESOURCES
    dest.mkdir(exist_ok=True,parents=True)
    order=sorted(n for n in manifest["sha256"] if n!="index.bin")+["index.bin"]
    extras={f.name for f in dest.iterdir()}-set(order)
    if extras:
        raise ValueError(f"Unexpected private resource entries in the checkout: {extras}")
    for name in order:
        expected=manifest["sha256"][name]
        path=dest/name
        if path.exists() and digest(path)==expected:
            continue
        tmp=path.with_suffix(path.suffix+".stage")
        link_or_copy(source/name,tmp)
        if digest(tmp)!=expected:
            raise ValueError("Corrupt staged member: "+name)
        os.replace(tmp,path)
    actual={f.name:digest(f) for f in dest.iterdir()}
    if actual!=manifest["sha256"]:
        raise ValueError("Private generation resource readback failed")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("previous",type=Path)
    p.add_argument("follow",type=Path)
    p.add_argument("out",type=Path)
    p.add_argument("--workers",type=int,default=3)
    p.add_argument("--publish",type=Path)
    p.add_argument("--rebase-on",type=Path,help="Rebase follow/staged over this installed world into out/staged")
    p.add_argument("--install",action="store_true",help="Install the rebased result on the cold world")
    args=p.parse_args()
    if args.rebase_on:
        rebase(args.follow,args.rebase_on,args.out,args.workers)
        if args.install:
            install(args.rebase_on,args.out)
        return
    compose(args.previous,args.follow,args.out,args.workers)
    if args.publish:
        publish(args.out,args.publish)


if __name__=="__main__":
    main()
