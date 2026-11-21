"""Follow-up native corrections for the isolated northern skin and incomplete planted trees.

Takes the fully installed first perimeter revision as read-only baseline.
Each stage produces a smaller reversible journal and a separate installation.
"""
from collections import defaultdict
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as nd

from blend_r64_map_perimeter import freeze,install,link_or_copy,normalize,parallel
from compose_r64_playtest_terrain import merge
from inspect_map_assets import decode_modern_section
from plan_r64_playtest_terrain import smooth
from stage_r64_playtest_terrain import stage,save_verified_region,tree_shape
from survey_r64_playtest_terrain import kind,scan
from write_deep_cells import REGION,read_chunk,write_chunk,decode,encode,clear_light


def notch_plan(a,work):
    # Given bounds cover the lone cross-chunk step and its sloping approaches.
    # Original and staged columns show two grass skins separated by 40–60 m of
    # air. No built surface exists in the measured 400 × 272 m neighborhood.
    frame=(-768,-2048,0,-1536)
    x0,z0,x1,z1=frame
    h,k=[np.zeros((z1-z0,x1-x0),t) for t in (np.int16,np.uint8)]
    for rx in (-2,-1):
        tag=f"r.{rx}.-4.npz"
        with np.load(a/"final-surface"/tag) as region:
            start=max(x0,rx*512);end=min(x1,rx*512+512)
            h[:,start-x0:end-x0]=region["h"][:,start-rx*512:end-rx*512]
            k[:,start-x0:end-x0]=region["k"][:,start-rx*512:end-rx*512]
    z,x=np.ogrid[z0:z1,x0:x1]
    radius=np.sqrt(((x+409)/185.)**2+((z+1793)/165.)**2)
    # A second detached soil cap crosses the same line diagonally farther west.
    radius=np.minimum(radius,np.sqrt(((x+617)/67.)**2+((z+1793)/57.)**2))
    cliff=nd.maximum_filter(h,5)-nd.minimum_filter(h,5)>17
    dist=nd.distance_transform_edt(~(cliff&(radius<1)))
    soft=normalize(h,k==3,21)
    weight=smooth((1.16-radius)/.36)*smooth((86-dist)/53)
    water=nd.distance_transform_edt(k!=4)
    hard=nd.distance_transform_edt(k!=5)
    weight*=smooth((water-4)/30)*smooth((hard-4)/38)
    goal=np.where(k==3,np.rint(h+(soft-h)*weight),h).astype(np.int16)
    for rx in (-2,-1):
        name=f"r.{rx}.-4.npz"
        with np.load(a/"final-surface"/name) as region:
            orig=region["h"]
        after=orig.copy()
        start=max(x0,rx*512);end=min(x1,rx*512+512)
        after[:,start-rx*512:end-rx*512]=goal[:,start-x0:end-x0]
        np.savez_compressed(work/"plan"/name,h=orig,target=after,forest=np.zeros((64,64),np.uint8))
    return [(-2,-4),(-1,-4)]


def find_tree_gaps(a,source):
    """Look up the actual blocks on each unrooted planned trunk's centerline."""
    sites=[]
    for f in (a/"trees").glob("r.*.*.npy"):
        planned=np.load(f)
        if not len(planned):
            continue
        with np.load(a/"final-surface"/(f.stem+".npz")) as d:
            heights,rooted,top=d["h"],d["r"],d["t"]
        points=defaultdict(list)
        for x,z,_,sp,h in planned.tolist():
            y=int(heights[z%512,x%512])
            if not rooted[z%512,x%512] and top[z%512,x%512]>y:
                points[x//16,z//16].append((x,z,y,sp,h))
        if not points:
            continue
        raw=(source/REGION/(f.stem+".mca")).read_bytes()
        for (cx,cz),spots in points.items():
            chunk=read_chunk(raw,cx,cz)[3];sections={int(s["Y"]):s for s in chunk["sections"]}
            for x,z,y,sp,h in spots:
                col=[]
                for sy in range((y+1)//16,(y+h+4)//16+1):
                    pal,indices=decode_modern_section(sections[sy])
                    for dy,index in enumerate(indices.reshape(16,16,16)[:,z%16,x%16]):
                        height=sy*16+dy
                        if y<height<=y+h+4:
                            col.append((height,str(pal[index]["Name"])))
                logs=[yy for yy,state in col if state.endswith(("_log","_wood"))]
                if logs and logs[0]>y+1:
                    sites.append((x,z,sp,h,"gap",logs[0]-y-1))
                if not logs and any(name.endswith("_leaves") for _,name in col):
                    sites.append((x,z,sp,h,"crown",0))
    return sites


def tree_patch(a,work,sites):
    changes=defaultdict(lambda:defaultdict(list))
    roots=[]
    for x,z,sp,height,mode,gap in sites:
        tag=f"r.{x//512}.{z//512}.npz"
        survey=work/"notch-surface"/tag
        if not survey.exists():
            survey=a/"final-surface"/tag
        with np.load(survey) as measured:
            ground=int(measured["h"][z%512,x%512])
            if measured["k"][z%512,x%512]!=3:
                raise ValueError("Tree footing changed")
        roots.append((x,ground+1,z))
        for dx,dy,dz,state in tree_shape(sp,height):
            if mode=="gap" and (dx or dz or dy>gap):
                continue
            xx,yy,zz=x+dx,ground+dy,z+dz
            changes[xx//512,zz//512][xx//16,zz//16].append((xx,yy,zz,state))
    target=work/"tree-pass"
    for (rx,rz),chunks in changes.items():
        tag=f"r.{rx}.{rz}"
        if (target/(tag+".json")).exists():
            continue
        path=work/"notch"/(tag+".mca")
        if not path.exists():
            path=work/"cold"/REGION/path.name
        old=path.read_bytes();buf=bytearray(old);journal={};palette=[];edited_chunks=[]
        for (cx,cz),cells in chunks.items():
            index,loc,sectors,chunk=read_chunk(old,cx,cz);by=defaultdict(list)
            for cell in cells:by[cell[1]//16].append(cell)
            dirty=False
            for section in chunk["sections"]:
                sy=int(section["Y"])
                if sy not in by:continue
                states=section["block_states"];ids,names=decode(states)
                modified=[]
                for x,y,z,state in by[sy]:
                    i=(y%16)*256+(z%16)*16+x%16;pre=names[ids[i]]
                    if pre==state:continue
                    log=state.partition("[")[0].endswith("_log")
                    if kind(pre.partition("[")[0]) not in (0,1) and not (log and pre.partition("[")[0].endswith("_leaves")):
                        continue
                    if state not in names:names.append(state)
                    ids[i]=names.index(state)
                    for name in (pre,state):
                        if name not in palette:palette.append(name)
                    modified.append([i,palette.index(pre),palette.index(state)])
                if modified:
                    encode(states,ids,names)
                    journal[cx,cz,sy]=np.array(sorted(modified),np.uint16);dirty=True
            if dirty:
                clear_light(chunk);chunk.pop("Heightmaps",None)
                write_chunk(buf,index,loc,sectors,chunk);edited_chunks.append((cx,cz))
        save_verified_region(target,tag,buf,old,journal,palette,edited_chunks)
        cells=sum(map(len,journal.values()))
        (target/(tag+".json")).write_text(json.dumps(dict(chunks=edited_chunks,cells=cells,columns=0)))
    return roots


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("stage","install"));p.add_argument("world",type=Path)
    p.add_argument("first",type=Path);p.add_argument("work",type=Path);a=p.parse_args()
    work=a.work
    if a.mode=="install":
        return install(a.world,work)
    for name in ("plan","trees","notch","notch-surface","tree-pass","staged"):
        (work/name).mkdir(parents=True,exist_ok=True)
    notch=notch_plan(a.first,work)
    sites=find_tree_gaps(a.first,a.world)
    touched=set(notch)
    for x,z,sp,h,mode,gap in sites:
        for dx,dy,dz,_ in tree_shape(sp,h):
            touched.add(((x+dx)//512,(z+dz)//512))
    source=freeze(a.world,work,touched)
    parallel(stage,[(source,a.first/"final-surface",work/"plan",work/"trees",work/"notch",*q) for q in notch],2)
    for q in notch:
        tag="r.%d.%d"%q;dest=work/"notch-world"/REGION/(tag+".mca")
        link_or_copy(work/"notch"/dest.name,dest)
        selected={(q[0]*32+x,q[1]*32+z) for x in range(32) for z in range(32)}
        scan((work/"notch-world",work/"notch-surface",*q,selected))
    roots=tree_patch(a.first,work,sites)
    for x,z in sorted(touched):
        tag=f"r.{x}.{z}"
        for folder in (work/"tree-pass",work/"notch"):
            if not (folder/(tag+".json")).exists():
                (folder/(tag+".json")).write_text('{"chunks":[],"cells":0,"columns":0}')
        merge((work/"notch",work/"tree-pass",work/"staged",tag))
    reports=[json.loads(f.read_bytes()) for f in (work/"staged").glob("r.*.json")]
    chunks=sorted(c for r in reports for c in r["chunks"])
    (work/"changed-chunks.json").write_text(json.dumps(chunks,separators=(",",":")))
    (work/"affected-trees.json").write_text(json.dumps(dict(sites=sites,expected_feet=roots),indent=2))
    print("regions/chunks/voxels/checked trees",sum(bool(r["cells"]) for r in reports),len(chunks),sum(r["cells"] for r in reports),len(roots))


if __name__=="__main__":
    main()
