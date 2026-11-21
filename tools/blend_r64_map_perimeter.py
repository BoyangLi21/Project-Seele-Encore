"""Continue measured GSI landforms and installed woodland across the four R64 DEM edges.

Run the survey, plan, stage, install and deliver modes in order with the game
closed. All work products and reversible voxel journals live outside Git.
The 8-block GSI grid carries projected GeoFront height; NaN denotes no land.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import filecmp
import shutil
from collections import defaultdict
from functools import partial
import json
import os
from pathlib import Path

import numpy as np
from scipy import ndimage as nd

from compose_r64_playtest_terrain import merge
from finish_r64_playtest_woodland import d8
from install_r53_carrier_trays import stopped_world
from package_r64_playtest_terrain import package
from plan_r64_playtest_terrain import smooth
from plant_r64_playtest_woodland import surround, treejob
from stage_r64_playtest_terrain import stage
from survey_r64_playtest_terrain import scan
from verify_r64_playtest_refinement import rescan
from inspect_map_assets import region_chunks, decode_modern_section
from survey_r64_playtest_terrain import kind
from stage_r64_playtest_terrain import save_verified_region
from write_deep_cells import REGION, read_chunk, write_chunk, decode, encode, clear_light

DEM=(-1982,-1548,4386,3720)
REGION_SIZE=512
STEP=8


def coords(path):
    return tuple(map(int,path.stem.split(".")[1:3]))


def distance(x,z):
    x0,z0,x1,z1=DEM
    return np.maximum(np.maximum(x0-x,x-x1),np.maximum(z0-z,z-z1))


def choose(world,work):
    with np.load(work/"gsi-grid.npz") as dem:
        h=dem["h"]
        ox,oz,step=(int(dem[k]) for k in ("x0","z0","step"))
        out=[]
        for f in sorted((world/REGION).glob("r.*.*.mca")):
            rx,rz=coords(f)
            x=rx*512+np.arange(8,512,16)[None,:]
            z=rz*512+np.arange(8,512,16)[:,None]
            if x.min()<ox or z.min()<oz or x.max()>ox+step*(h.shape[1]-1) or z.max()>oz+step*(h.shape[0]-1):
                continue
            sd=distance(x,z)
            valid=np.isfinite(h[(z-oz)//step,(x-ox)//step])
            if np.any((sd>=-880)&(sd<=1410)&valid):
                out.append((rx,rz))
    return out


def parallel(fn,jobs,workers):
    with ProcessPoolExecutor(workers) as pool:
        for i,result in enumerate(pool.map(fn,jobs),1):
            if i%10==0 or i==len(jobs):
                print(i,len(jobs),result,flush=True)


def survey(world,work,workers):
    out=work/"before"
    out.mkdir(exist_ok=True)
    jobs=[(world,out,rx,rz,{(rx*32+i,rz*32+j) for i in range(32) for j in range(32)})
          for rx,rz in choose(world,work)]
    parallel(scan,jobs,workers)


def normalize(values,observed,sigma):
    weights=nd.gaussian_filter(observed.astype("f"),sigma)
    return nd.gaussian_filter(np.where(observed,values,0).astype("f"),sigma)/np.maximum(.0001,weights)


def mosaic(work):
    source=work/"before"
    files=sorted(source.glob("r.*.*.npz"))
    pairs=[coords(f) for f in files]
    minx,minz=np.min(pairs,axis=0)
    maxx,maxz=np.max(pairs,axis=0)
    shape=((maxz-minz+1)*64,(maxx-minx+1)*64)
    h,k,cover,hard,water=[np.zeros(shape,"f") for _ in range(5)]
    for f,(rx,rz) in zip(files,pairs):
        iz,ix=(rz-minz)*64,(rx-minx)*64
        cut=np.s_[iz:iz+64,ix:ix+64]
        with np.load(f) as v:
            categories=v["k"]
            dry=categories==3
            k[cut]=d8(dry)
            h[cut]=d8(np.where(dry,v["h"],0))/np.maximum(.001,k[cut])
            cover[cut]=d8(v["v"]!=0)
            hard[cut]=d8(categories==5)
            water[cut]=d8(categories==4)
    x=minx*512+np.arange(shape[1])[None,:]*8+3.5
    z=minz*512+np.arange(shape[0])[:,None]*8+3.5
    with np.load(work/"gsi-grid.npz") as g:
        raw=g["h"]
        zz,xx=np.broadcast_arrays((z-int(g["z0"]))/8,(x-int(g["x0"]))/8)
        obs=np.isfinite(raw)
        # Fill only the interpolation kernel; leave unmapped ocean excluded.
        weight=nd.map_coordinates(obs.astype("f"),(zz,xx),order=1,mode="constant",cval=0)
        ref=nd.map_coordinates(np.where(obs,raw,0).astype("f"),(zz,xx),order=1,mode="constant",cval=0)/np.maximum(.001,weight)
        measured=(weight>.995)&(k>.45)
    h=normalize(h,k>.45,1.05)
    ref=normalize(ref,measured,.78)
    mx=distance(x,z)
    # A curved and varying transition width follows distinct valleys and ridge
    # spurs. The mask approaches zero continuously on both sides of its range.
    variation=.46*np.sin(x/287+z/461)+.29*np.sin(z/221-x/589)+.25*np.cos(x/587+z/179)
    outer=980+310*variation
    inner=205+95*variation
    alpha=smooth((mx+inner)/inner)*smooth((outer-mx)/(.53*outer))
    # Preserve the close match inside the surveyed rectangle. Outside,
    # reconcile the measured 16–250 m ridge/valley pattern first; correct
    # the longer datum gently. Avoid excavating or filling whole mountains.
    residual=ref-h
    bias=normalize(residual,measured,24)
    long_move=20*np.tanh(.62*bias/20)
    relief=residual-bias
    change=alpha*(long_move+38*np.tanh(relief/38))
    # Dampen the approach to sea, routes and contiguous missing data before
    # resolving their exact block-by-block protection below.
    near_sea=nd.distance_transform_edt(water<.35)*8
    near_hard=nd.distance_transform_edt(hard<.13)*8
    reliability=smooth((nd.distance_transform_edt(measured)*8-4)/56)
    change*=reliability*smooth((near_sea+4)/66)*smooth((near_hard+12)/82)
    change=np.where(measured,change,0).astype("f")
    # Extend the dense side into adjacent dry land over hundreds of blocks.
    # Site probability is controlled by actual nearby crowns, local ridge
    # aspect/moisture, and the existing pattern of settlement and water.
    canopy=nd.gaussian_filter(cover,2)
    seed=nd.gaussian_filter(cover,4)>.33
    tree_dist,nearest=nd.distance_transform_edt(~seed,return_indices=True)
    source_cover=canopy[nearest[0],nearest[1]]
    span=490+150*variation
    forest_reach=smooth(1-tree_dist*8/span)
    grade=np.hypot(*np.gradient(nd.gaussian_filter(h+change,2)))/8
    valley=nd.gaussian_filter(h+change,4)-nd.gaussian_filter(h+change,16)
    stand=.72+.17*np.sin(x/94+z/143+valley/26)+.11*np.sin(z/64-x/131)
    desired=source_cover*forest_reach*stand*np.clip(.91+valley*.012,.63,1.18)
    forestry=smooth((mx+640)/340)*smooth((outer+120-mx)/370)
    # A clipped urban forest margin can sit inside the DEM; include the
    # photographed Odawara northeast shoulders but hold inhabited lots clear.
    ne=smooth((x-1660)/510)*smooth((1650-z)/610)*smooth((z+2700)/630)*smooth((5800-x)/690)
    forestry=np.maximum(forestry,ne)
    plant=np.clip((desired-canopy-.012)*2.0,0,.93)*forestry*reliability
    plant*=smooth((near_sea+1)/42)*smooth((near_hard-12)/112)*smooth((1.1-grade)/.7)
    plant*=np.clip((k-.45)/.50,0,1)
    # Exact surveyed forest on the dense side meets the new shoulder organically.
    # Agricultural/urban fragments remain anchored by their infrastructure.
    plant=np.where(measured,plant,0).astype("f")
    np.savez_compressed(work/"macro.npz",x0=int(minx*512),z0=int(minz*512),change=change,plant=plant,
                        native=h,reference=ref,measured=measured)
    print("coarse land/terrain/woodland cells",measured.sum(),(abs(change)>.5).sum(),(plant>.05).sum(),flush=True)


def northern_banks(work,rx,rz,target,raw,categories,clearance):
    """Join severed Y62 ponds to their native highland without moving water."""
    if rx not in (1,2,3) or rz not in (-4,-3):
        return target,np.zeros(raw.shape,np.int16)
    halo=190
    k=surround(work/"before",rx,rz,"k",0,halo)
    h=surround(work/"before",rx,rz,"h",0,halo).astype("f")
    fullz,fullx=np.ogrid[-halo:512+halo,-halo:512+halo]
    wx=fullx+rx*512;wz=fullz+rz*512
    ponds=(k==4)&(h>=60)&(h<=64)&(wx>=800)&(wx<=1700)&(wz>=-1830)&(wz<=-1685)
    if not ponds.any():
        return target,np.zeros(raw.shape,np.int16)
    original_dist=nd.distance_transform_edt(~ponds)
    infrastructure=nd.distance_transform_edt(k!=5)
    trees=surround(work/"before",rx,rz,"v",0,halo)
    reach=4+12*(.5+.5*np.cos(wx/23+wz/113))+7*(.5+.5*np.sin(wx/47-wz/71))
    # Only round the clipped side. The intact southern pond shores and
    # existing sources retain their shape, level and complete water volume.
    new_water=(k==3)&(h<=58)&(trees==0)&(infrastructure>18)&(wz<=-1791)&(wz>=-1822)&(original_dist<reach)
    new_water &= (wx>=912)&(wx<=1574)
    labels,_=nd.label(ponds|new_water)
    new_water &= np.isin(labels,np.unique(labels[ponds]))
    all_water=ponds|new_water
    dist,where=nd.distance_transform_edt(~all_water,return_indices=True)
    water=np.where(new_water,62,h)[where[0],where[1]]
    im=np.s_[halo:-halo,halo:-halo]
    dist=dist[im]
    water=water[im]
    x=rx*512+np.arange(512)[None,:];z=rz*512+np.arange(512)[:,None]
    reach=168+24*np.sin(x/79+z/173)+20*np.cos(z/67-x/121)
    influence=smooth(1-dist/reach)
    # Remove the one-column steps between adjacent pond basins. A smooth
    # measured surface retains inter-basin spurs while bridging the old grid.
    dry=(k==3)|(k==4)
    soft=normalize(h,dry,16)[im]
    nearcut=smooth((200-abs(z+1792))/144)
    rolled=target+(soft-target)*nearcut*influence*.85
    toe=np.maximum(dist-2,0)
    slope=.43+.11*np.sin(x/83+z/153)+.07*np.cos(z/61-x/116)
    # A pond whose water sits 60 m above a truncated neighbouring chunk
    # needs a real soil-backed slope to retain its measured shoreline.
    lower=water+1-toe*slope
    upper=water+2+toe*(slope+.17)
    joined=np.clip(rolled,lower,upper)
    joined=np.where(dist<reach,joined,rolled)
    # Constraint tapers to the unchanged outer bank when the spring meets
    # valley floors below pond level. Existing roads and blocks are anchors.
    joined=target+(joined-target)*smooth((reach-dist)/45)*smooth((clearance-3)/27)
    new_water=new_water[im]
    depth=np.minimum(3,1+np.floor(nd.distance_transform_edt(all_water)[im]/3)).astype(np.int16)
    ground=np.where(categories==3,np.rint(joined),raw)
    return np.where(new_water,62-depth,ground).astype(np.int16),np.where(new_water,62,0).astype(np.int16)


def plan_region(job):
    work,rx,rz=job
    tag=f"r.{rx}.{rz}.npz"
    out=work/"plan"/tag
    if out.exists():
        return
    # Global coarse arrays are memory-mapped once by each worker.
    global _macro
    if _macro is None:
        with np.load(work/"macro.npz") as f:
            _macro={k:f[k] for k in ("x0","z0","change","plant")}
    ox,oz=int(_macro["x0"]),int(_macro["z0"])
    ix,iz=(rx*512-ox)//8,(rz*512-oz)//8
    zz,xx=np.ogrid[:512,:512]
    ji=np.broadcast_arrays(iz+(zz-3.5)/8,ix+(xx-3.5)/8)
    delta=nd.map_coordinates(_macro["change"],ji,order=1,mode="nearest")
    canopy=np.clip(_macro["plant"][iz:iz+64,ix:ix+64],0,1)
    with np.load(work/"before"/tag) as v:
        raw=v["h"]
        categories=v["k"]
    halo=80
    k=surround(work/"before",rx,rz,"k",0,halo)
    man=nd.distance_transform_edt((k!=5)&(k!=0))[halo:-halo,halo:-halo]
    wet=nd.distance_transform_edt(k!=4)[halo:-halo,halo:-halo]
    # A long ramp protects buildings, rails, riverbanks and other authored
    # surfaces. Bounding the slope change by distance avoids a ring berm.
    dry=(categories==3)
    delta*=smooth((man-6)/58)*smooth((wet-4)/52)*dry
    limit=np.minimum((np.maximum(0,man-6))*.42,np.maximum(0,wet-4)*.36)
    delta=np.clip(delta,-limit,limit)
    target=np.where(dry,np.where(delta!=0,np.clip(np.rint(raw+delta),-112,297),raw),raw).astype(np.int16)
    target,water=northern_banks(work,rx,rz,target,raw,categories,man)
    # Crops and facility parcels are kept free from new crowns by a precise
    # local clearance in addition to the coarse density gradient.
    probability=canopy*d8((man>11)&(wet>5)&dry)
    trees=(np.rint(probability*255)).astype(np.uint8)
    np.savez_compressed(out,h=raw,target=target,forest=trees,water_y=water)
    cuts=target.astype(int)-raw
    return rx,rz,int((cuts!=0).sum()),int(abs(cuts).sum())


_macro=None


def link_or_copy(src,dest):
    if dest.exists():
        if not filecmp.cmp(src,dest,shallow=False):
            raise ValueError("Previous result at "+str(dest))
        return
    dest.parent.mkdir(parents=True,exist_ok=True)
    try:
        os.link(src,dest)
    except OSError:
        shutil.copy2(src,dest)


def freeze(world,work,pairs):
    source=work/"cold"
    with stopped_world(world):
        for rx,rz in pairs:
            name=f"r.{rx}.{rz}.mca"
            link_or_copy(world/REGION/name,source/REGION/name)
    return source


def install(world,work):
    done=work/"installed"
    done.mkdir(exist_ok=True)
    with stopped_world(world):
        for receipt in sorted((work/"staged").glob("r.*.json")):
            data=json.loads(receipt.read_bytes())
            if not data["cells"]:
                continue
            tag=receipt.stem
            name=tag+".mca"
            original=work/"cold"/REGION/name
            staged=work/"staged"/name
            current=world/REGION/name
            record=done/(tag+".done")
            if record.exists():
                if not filecmp.cmp(staged,current,shallow=False):
                    raise ValueError("Previously installed region changed: "+tag)
                continue
            if not filecmp.cmp(current,original,shallow=False):
                if filecmp.cmp(current,staged,shallow=False):
                    record.write_text(str(data["cells"]))
                    continue
                raise ValueError("Cold source changed: "+tag)
            tmp=current.with_suffix(".seam-install")
            link_or_copy(staged,tmp)
            os.replace(tmp,current)
            if not filecmp.cmp(staged,current,shallow=False):
                raise ValueError("Installed readback mismatch: "+tag)
            record.write_text(str(data["cells"]))


def deliver(args,world,work):
    previous=args.previous
    if not previous:
        raise ValueError("Supply the --previous terrain delivery with its original journals.")
    step=work/"staged"
    original=previous/"shipped-staged"
    early,late,net=[work/k for k in ("previous-stage","incremental-stage","net-stage")]
    before,after,delta=[work/k for k in ("original-surface","final-surface","rescan")]
    for d in (early,late,net,before,after,delta):
        d.mkdir(exist_ok=True)
    tags={p.stem for src in (original,step) for p in src.glob("r.*.json")}
    reports={}
    scans=[]
    for tag in sorted(tags):
        for src,dest in ((original,early),(step,late)):
            record=src/(tag+".json")
            if record.exists():
                for item in src.glob(tag+".*"):
                    link_or_copy(item,dest/item.name)
            elif not (dest/(tag+".json")).exists():
                (dest/(tag+".json")).write_text('{"chunks":[],"cells":0,"columns":0}')
        inc=json.loads((late/(tag+".json")).read_bytes())
        reports[tag]=inc["chunks"]
        fn=tag+".npz"
        src0=previous/"shipped-original"/fn
        pre=work/"before"/fn
        old=previous/"shipped-surface"/fn
        if not pre.exists():
            pre=old
        # Add full current coverage in previously unmeasured columns without
        # losing the pre-R64 values in already repaired areas.
        dest=before/fn
        if not dest.exists() and src0.is_file() and (work/"before"/fn).is_file():
            with np.load(src0) as a,np.load(work/"before"/fn) as b:
                use=a["k"]!=0
                np.savez_compressed(dest,**{k:(np.where(use,a[k],b[k]) if k in a.files else b[k]) for k in b.files})
        elif not dest.exists():
            link_or_copy(src0 if src0.exists() else pre,dest)
        scans.append((world,pre.parent,delta,after,tag,inc["chunks"]))
    parallel(merge,[(early,late,net,tag) for tag in sorted(tags)],args.workers)
    parallel(rescan,scans,args.workers)
    changed=sorted(p for block in reports.values() for p in block)
    (work/"changed-chunks.json").write_text(json.dumps(changed,separators=(",",":")))
    package(net,before,after,work/"ship_mod_resources/data/projectseele/worldgen/playtest_landscape_r64")


def water_contacts(work,bounds,level,*,near_new=None,lower=None,preserve_waterlines=False):
    """Read every fluid face near the clipped ponds from the final staged MCA."""
    x0,z0,x1,z1=bounds
    x0,z0,x1,z1=x0//16*16,z0//16*16,((x1+15)//16)*16,((z1+15)//16)*16
    y0,y1=level-62 if lower is None else lower,level+4
    cube=np.full((y1-y0,z1-z0,x1-x0),2,np.uint8)
    plane=np.zeros(cube.shape[1:],bool)
    requested=np.zeros_like(plane)
    old_water_y=np.full(plane.shape,-32768,np.int16)
    for rx in range(x0//512,(x1-1)//512+1):
        for rz in range(z0//512,(z1-1)//512+1):
            tag=f"r.{rx}.{rz}"
            path=work/"staged"/(tag+".mca")
            if not path.exists():
                path=work/"cold"/REGION/path.name
            ax,az,bx,bz=max(x0,rx*512),max(z0,rz*512),min(x1,rx*512+512),min(z1,rz*512+512)
            dst=np.s_[az-z0:bz-z0,ax-x0:bx-x0]
            src=np.s_[az-rz*512:bz-rz*512,ax-rx*512:bx-rx*512]
            with np.load(work/"before"/(tag+".npz")) as a,np.load(work/"plan"/(tag+".npz")) as b:
                requested[dst]=b["water_y"][src]==level
                h=a["h"][src];wet=a["k"][src]==4
                plane[dst]=(wet&(h==level))|requested[dst]
                if preserve_waterlines:old_water_y[dst]=np.where(wet,h,-32768)
            for cx,cz,ch in region_chunks(path,(x0//16,(x1-1)//16,z0//16,(z1-1)//16)):
                dx,dz=cx*16-x0,cz*16-z0
                for sec in ch["sections"]:
                    sy=int(sec["Y"])*16
                    a0,a1=max(y0,sy),min(y1,sy+16)
                    if a0>=a1:
                        continue
                    pal,ids=decode_modern_section(sec)
                    if not pal:
                        continue
                    cats=[]
                    for state in pal:
                        name=str(state["Name"])
                        cats.append(1 if name=="minecraft:water" else (0 if kind(name) in (0,1) else 2))
                    part=ids.reshape(16,16,16)[a0-sy:a1-sy]
                    cube[a0-y0:a1-y0,dz:dz+16,dx:dx+16]=np.array(cats,np.uint8)[part]
    if near_new is not None:
        if not requested.any():
            return []
        plane &= nd.distance_transform_edt(~requested)<=near_new
    wet=(cube==1)&plane
    # Four sides and the bottom must retain source water. The open top belongs
    # to the pond. Exclude neighboring water columns which lie outside the box.
    contacts=np.zeros_like(wet)
    contacts[:-1]|=wet[1:]
    contacts[:,:,1:]|=wet[:,:,:-1];contacts[:,:,:-1]|=wet[:,:,1:]
    contacts[:,1:,:]|=wet[:,:-1,:];contacts[:,:-1,:]|=wet[:,1:,:]
    contacts[:,[0,-1],:]=False;contacts[:,:,[0,-1]]=False
    if preserve_waterlines:
        # A natural cascade between two original lake levels already has an
        # open face above the lower surface. Keep it visible. Every wall or bed
        # immediately adjacent to newly placed water still needs containment.
        old_only=(old_water_y!=-32768)&(old_water_y<level)&~nd.binary_dilation(requested)
        contacts &= ~(old_only & (np.arange(y0,y1)[:,None,None]>old_water_y))
    leaks=np.argwhere(contacts&(cube==0))
    return [(x0+int(x),y0+int(y),z0+int(z)) for y,z,x in leaks]


def survey_ponds(work):
    windows=work/"water-windows.json"
    if not windows.exists():
        return water_contacts(work,(832,-1840,1648,-1664),62,lower=0)
    leaks=set()
    for spec in json.loads(windows.read_bytes()):
        leaks.update(water_contacts(work,spec["bounds"],spec["level"],near_new=spec.get("contactRadius",6),
                                    lower=spec.get("lower"),preserve_waterlines=spec.get("preserveWaterlines",False)))
    return sorted(leaks)


def seal_ponds(work):
    """Place clay only on confirmed open faces of the measured pond basins."""
    done=work/"pond-seals.json"
    if done.exists():
        if survey_ponds(work):
            raise ValueError("Previously sealed basin has an exposed face")
        return
    gaps=survey_ponds(work)
    groups=defaultdict(lambda:defaultdict(list))
    for x,y,z in gaps:
        groups[(x//512,z//512)][(x//16,z//16)].append((x,y,z))
    base,seal,net=[work/p for p in ("pre-seal","seal-pass","merged-seals")]
    for path in (base,seal,net):
        path.mkdir(exist_ok=True)
    for (rx,rz),chunks in groups.items():
        tag=f"r.{rx}.{rz}"
        for f in (work/"staged").glob(tag+".*"):
            link_or_copy(f,base/f.name)
        if not (seal/(tag+".json")).exists():
            if not (base/(tag+".mca")).exists():
                link_or_copy(work/"cold"/REGION/(tag+".mca"),base/(tag+".mca"))
            old=(base/(tag+".mca")).read_bytes()
            buf=bytearray(old)
            palette=["minecraft:clay"]
            journal={}
            for (cx,cz),points in chunks.items():
                i,loc,count,chunk=read_chunk(old,cx,cz)
                sections={int(s["Y"]):s for s in chunk["sections"]}
                by=defaultdict(list)
                for x,y,z in points:
                    by[y//16].append((y%16)*256+(z%16)*16+x%16)
                for sy,indices in by.items():
                    states=sections[sy]["block_states"]
                    ids,names=decode(states)
                    if "minecraft:clay" not in names:
                        names.append("minecraft:clay")
                    clay=names.index("minecraft:clay")
                    rows=[]
                    for at in sorted(indices):
                        oldname=names[ids[at]]
                        if kind(oldname.partition("[")[0]) not in (0,1):
                            raise ValueError("Shore contact changed")
                        if oldname not in palette:
                            palette.append(oldname)
                        rows.append([at,palette.index(oldname),0])
                        ids[at]=clay
                    encode(states,ids,names)
                    journal[cx,cz,sy]=np.array(rows,np.uint16)
                clear_light(chunk)
                chunk.pop("Heightmaps",None)
                write_chunk(buf,i,loc,count,chunk)
            save_verified_region(seal,tag,buf,old,journal,palette,list(chunks))
            (seal/(tag+".json")).write_text(json.dumps(dict(chunks=list(chunks),cells=sum(map(len,chunks.values())))))
        merge((base,seal,net,tag))
        for ext in (".mca",".delta.npz",".json"):
            current=work/"staged"/(tag+ext)
            temp=current.with_name(current.name+".sealed")
            link_or_copy(net/(tag+ext),temp)
            os.replace(temp,current)
    remaining=survey_ponds(work)
    if remaining:
        raise ValueError(f"Unsealed water faces: {remaining[:10]}")
    report=dict(clay_cells=len(gaps),exposed_faces_after=0,bounds=[[min(p[i] for p in gaps),max(p[i] for p in gaps)] for i in range(3)] if gaps else [])
    done.write_text(json.dumps(report,indent=2))


def dispatch(args,world,work,pairs):
    if args.mode=="stage":
        source=freeze(world,work,pairs)
        trees=work/"trees";trees.mkdir(exist_ok=True)
        staged=work/"staged";staged.mkdir(exist_ok=True)
        parallel(treejob,[(source,work/"before",work/"plan",trees,*p) for p in pairs],args.workers)
        # Largest highland blocks first so the expensive jobs do not accrue
        # behind a final wave of sparse coastal regions.
        pairs.sort(key=lambda c:-(work/"plan"/f"r.{c[0]}.{c[1]}.npz").stat().st_size)
        parallel(stage,[(source,work/"before",work/"plan",trees,staged,*p,True) for p in pairs],args.workers)
        seal_ponds(work)
        records={f.stem:json.loads(f.read_bytes()) for f in staged.glob("r.*.json")}
        cells=sorted(c for rec in records.values() for c in rec["chunks"])
        (work/"changed-chunks.json").write_text(json.dumps(cells,separators=(",",":")))
        print("verified incremental regions/chunks/cells",sum(bool(r["cells"]) for r in records.values()),
              len(cells),sum(r["cells"] for r in records.values()),flush=True)
    elif args.mode=="install":
        install(world,work)
    elif args.mode=="deliver":
        deliver(args,world,work)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("survey","plan","stage","install","deliver"))
    p.add_argument("world",type=Path)
    p.add_argument("work",type=Path)
    p.add_argument("--previous",type=Path)
    p.add_argument("--workers",type=int,default=7)
    args=p.parse_args()
    world,work=args.world.resolve(),args.work.resolve()
    work.mkdir(parents=True,exist_ok=True)
    if args.mode=="survey":
        survey(world,work,args.workers)
        return
    pairs=sorted(coords(f) for f in (work/"before").glob("r.*.*.npz"))
    if args.mode=="plan":
        (work/"plan").mkdir(exist_ok=True)
        mosaic(work)
        parallel(plan_region,[(work,*p) for p in pairs],args.workers)
        return
    dispatch(args,world,work,pairs)


if __name__=="__main__":
    main()
