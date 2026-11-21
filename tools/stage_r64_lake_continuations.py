"""Grade, fill and validate natural lake continuations from one-block design masks.

Each design NPZ contains integer x0,z0 and a boolean water array [z,x].
An optional positive integer depth array gives depths for new source columns.
Existing water cells and constructed blocks are never candidates for editing.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as nd

from blend_r64_map_perimeter import freeze,install,parallel,seal_ponds
from inspect_map_assets import region_chunks,decode_modern_section
from plan_r64_playtest_terrain import smooth
from stage_r64_playtest_terrain import stage,WATER_BEDS
from survey_r64_playtest_terrain import kind,scan
from write_deep_cells import REGION,decode


def layout(design):
    proposals=[]
    for f in sorted(design.glob("*.npz")):
        with np.load(f) as v:
            water=np.asarray(v["water"],bool)
            x0,z0=int(v["x0"]),int(v["z0"])
            level=int(v["level"]) if "level" in v else 62
            depth=np.asarray(v["depth"],np.uint8) if "depth" in v else None
        if not water.any():
            continue
        if level==0:
            raise ValueError("An external lake at Y0 needs a separate presence mask")
        z,x=np.where(water)
        west,east=int(x.min()),int(x.max())+1
        north,south=int(z.min()),int(z.max())+1
        cropped=water[north:south,west:east]
        dep=None if depth is None else depth[north:south,west:east]
        proposals.append((f.stem,x0+west,z0+north,cropped,level,dep))
    if not proposals:raise ValueError("No new water in the input design")
    return proposals


def native_regions(plans):
    all_pairs=set()
    for _,x,z,wet,_,_ in plans:
        h,w=wet.shape;margin=168
        for rx in range((x-margin)//512,(x+w+margin-1)//512+1):
            for rz in range((z-margin)//512,(z+h+margin-1)//512+1):
                all_pairs.add((rx,rz))
    return sorted(all_pairs)


def read_window(work,bounds,keys):
    x0,z0,x1,z1=bounds
    out={k:np.zeros((z1-z0,x1-x0),np.int16 if k=="h" else np.uint8) for k in keys}
    for rx in range(x0//512,(x1-1)//512+1):
        for rz in range(z0//512,(z1-1)//512+1):
            f=work/"before"/f"r.{rx}.{rz}.npz"
            if not f.exists():continue
            ax,az,bx,bz=max(x0,rx*512),max(z0,rz*512),min(x1,rx*512+512),min(z1,rz*512+512)
            dst=np.s_[az-z0:bz-z0,ax-x0:bx-x0];src=np.s_[az-rz*512:bz-rz*512,ax-rx*512:bx-rx*512]
            with np.load(f) as row:
                for k in keys:out[k][dst]=row[k][src]
    return out


def check_beds(work,eligible,ground,level,x0,z0,depth):
    # Query only columns which require excavation. Keep the whole cave roof
    # when a hole, a fluid or a protected material interrupts the proposed bed.
    good=eligible.copy()
    z,x=np.where(eligible&(ground>level-depth))
    groups=defaultdict(lambda:defaultdict(list))
    for xx,zz in zip(x.tolist(),z.tolist()):
        wx,wz=x0+xx,z0+zz
        groups[wx//512,wz//512][wx//16,wz//16].append((xx,zz))
    for (rx,rz),chunks in groups.items():
        path=work/"cold"/REGION/f"r.{rx}.{rz}.mca"
        for cx,cz,chunk in region_chunks(path,(rx*32,rx*32+31,rz*32,rz*32+31),chunks):
            coords=chunks[cx,cz]
            xx=np.array([p[0] for p in coords]);zz=np.array([p[1] for p in coords])
            lo=(level-depth[zz,xx].astype(np.int16)-2);hi=ground[zz,xx]
            for sec in chunk["sections"]:
                y0=int(sec["Y"])*16
                affected=(lo<y0+16)&(hi>=y0)&good[zz,xx]
                if not affected.any():continue
                pal,ids=decode_modern_section(sec)
                if not pal:good[zz[affected],xx[affected]]=False;continue
                codes=[kind(str(s["Name"]))==3 for s in pal]
                ss=np.array(codes)[ids.reshape(16,16,16)[:,(zz[affected]+z0)%16,(xx[affected]+x0)%16]]
                ys=np.arange(y0,y0+16)[:,None]
                bad=((ys>=lo[affected])&(ys<=hi[affected])&~ss).any(axis=0)
                good[zz[affected][bad],xx[affected][bad]]=False
    return good



def lake_sediment(work,old,wet,x0,z0,level):
    # Read the first solid bed beneath current sources along this actual lake.
    # Even neighboring clipped basins can expose different substrate palettes.
    near=old&(nd.distance_transform_edt(~wet)<38)
    samples=np.argwhere(near)
    if len(samples)>48:samples=samples[np.linspace(0,len(samples)-1,48).astype(int)]
    by=defaultdict(lambda:defaultdict(list))
    for zz,xx in samples.tolist():
        x,z=x0+xx,z0+zz;by[x//512,z//512][x//16,z//16].append((x,z))
    evidence=Counter()
    for (rx,rz),chunks in by.items():
        path=work/"cold"/REGION/f"r.{rx}.{rz}.mca"
        for cx,cz,chunk in region_chunks(path,(rx*32,rx*32+31,rz*32,rz*32+31),chunks):
            for x,z in chunks[cx,cz]:
                col={}
                for sec in chunk["sections"]:
                    y=int(sec["Y"])*16
                    if y>level or y+16<=level-38:continue
                    pal,ids=decode_modern_section(sec)
                    if not pal:continue
                    col.update({y+i:str(pal[v]["Name"]) for i,v in enumerate(ids.reshape(16,16,16)[:,z%16,x%16])})
                for y in range(level,level-39,-1):
                    native=col.get(y,"minecraft:air")
                    if native in WATER_BEDS:
                        evidence[native]+=1;break
                    if kind(native) not in (0,1,4):break
    chosen=evidence.most_common(1)[0][0] if evidence else "minecraft:gravel"
    return WATER_BEDS.index(chosen)+1,dict(evidence)


def region_plan(work,plans,pairs):
    updates={}
    rows=[];windows=[];accepted_by=[]
    for name,x,z,requested,level,depth in plans:
        margin=160;h,w=requested.shape
        x0,z0=x-margin,z-margin;x1,z1=x+w+margin,z+h+margin
        bounds=(x0,z0,x1,z1)
        data=read_window(work,bounds,("h","k","v","r"))
        ground=data["h"];categories=data["k"]
        old=(categories==4)&(ground==level)
        req=np.pad(requested,margin)
        hard=nd.distance_transform_edt((categories!=5)&(categories!=0))
        # Canopies above player-made sites belong to the protected envelope.
        # Natural existing trees outside the new footprint track moving slopes.
        other=(categories==4)&(ground!=level)
        level_buffer=np.ones(ground.shape,bool)
        preserve_other=np.ones(ground.shape,np.float32)
        if other.any():
            separation,other_at=nd.distance_transform_edt(~other,return_indices=True)
            difference=abs(ground[other_at[0],other_at[1]].astype(float)-level)
            level_buffer=separation>=np.minimum(45,4+2.4*difference)
            preserve_other=smooth((separation-3)/(16+np.minimum(20,difference)))
        eligible=req&(categories==3)&(hard>7)&(data["v"]==0)&level_buffer
        depth_map=np.pad(np.clip(depth,1,5),margin) if depth is not None else np.minimum(3,1+(nd.distance_transform_edt(old|eligible)//3)).astype(np.uint8)
        eligible=check_beds(work,eligible,ground,level,x0,z0,depth_map)
        label,_=nd.label(old|eligible)
        wet=eligible&np.isin(label,np.unique(label[old]))
        if not wet.any():
            raise ValueError(f"{name}: no source-connected natural columns survived; verify the snapped shoreline")
        soil,evidence=lake_sediment(work,old,wet,x0,z0,level)
        combined=old|wet
        dist=nd.distance_transform_edt(~combined)
        near=nd.distance_transform_edt(~wet)
        zz,xx=np.ogrid[z0:z1,x0:x1]
        reach=128+22*np.sin(xx/94+zz/143)+12*np.cos(zz/83-xx/175)
        slope=.48+.11*np.sin(xx/83+zz/153)+.06*np.cos(zz/61-xx/116)
        toe=np.maximum(dist-2,0)
        bank=np.clip(ground,level+1-toe*slope,level+2+toe*(slope+.17))
        weight=smooth((reach-near)/(.68*reach))*smooth((hard-3)/24)*preserve_other
        goal=np.where(categories==3,np.rint(ground+(bank-ground)*weight),ground).astype(np.int16)
        depth_map=np.where(wet,depth_map,0).astype(np.int16)
        goal[wet]=level-depth_map[wet]
        write=(goal!=ground)|wet
        for rx,rz in pairs:
            ax,az,bx,bz=max(x0,rx*512),max(z0,rz*512),min(x1,rx*512+512),min(z1,rz*512+512)
            if ax>=bx or az>=bz:continue
            ss=np.s_[az-z0:bz-z0,ax-x0:bx-x0];rr=np.s_[az-rz*512:bz-rz*512,ax-rx*512:bx-rx*512]
            if not write[ss].any():continue
            if (rx,rz) not in updates:
                with np.load(work/"before"/f"r.{rx}.{rz}.npz") as s:raw=s["h"]
                updates[rx,rz]=[raw.copy(),raw.copy(),np.zeros_like(raw),np.zeros(raw.shape,np.uint8)]
            raw,target,water,beds=updates[rx,rz];old_target=target[rr];water=water[rr]
            # If banks overlap, select the closer-to-water dry contour. Exact
            # wet cells outrank either bank and equal levels merge directly.
            take=write[ss]&(water==0)&((abs(goal[ss]-raw[rr])>abs(old_target-raw[rr]))|wet[ss])
            old_target[take]=goal[ss][take]
            if np.any(wet[ss]&(water!=0)&(water!=level)):raise ValueError("Intersecting water levels")
            water[wet[ss]]=level
            beds[rr][wet[ss]]=soil
        ynew,xnew=np.where(wet)
        bounds=[int(xnew.min()+x0-12),int(ynew.min()+z0-12),int(xnew.max()+x0+13),int(ynew.max()+z0+13)]
        windows.append(dict(id=name,bounds=bounds,level=level,contactRadius=6,lower=level-48,preserveWaterlines=True))
        rows.append(dict(id=name,requested_pixels=int(req.sum()),overlapping_old=int((req&old).sum()),
                         new_water=int(wet.sum()),unsafe_or_disconnected=int((req & ~old & ~wet).sum()),
                         min_depth=int(depth_map[wet].min()),max_depth=int(depth_map[wet].max()),sediment=WATER_BEDS[soil-1],bed_samples=evidence))
        accepted_by.append((name,wet[margin:margin+h,margin:margin+w],x,z))
    for rx,rz in pairs:
        if (rx,rz) in updates:raw,goal,wet,beds=updates[rx,rz]
        else:
            with np.load(work/"before"/f"r.{rx}.{rz}.npz") as s:raw=s["h"]
            goal=raw;wet=np.zeros_like(raw);beds=np.zeros(raw.shape,np.uint8)
        np.savez_compressed(work/"plan"/f"r.{rx}.{rz}.npz",h=raw,target=goal,water_y=wet,water_bed=beds,forest=np.zeros((64,64),np.uint8))
    (work/"water-windows.json").write_text(json.dumps(windows,indent=2),"utf8")
    (work/"geometry.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),"utf8")
    (work/"approved-mask").mkdir(exist_ok=True)
    for name,wet,x,z in accepted_by:
        np.savez_compressed(work/"approved-mask"/(name+".npz"),x0=x,z0=z,water=wet)
    print("connected new water",sum(v["new_water"] for v in rows),flush=True)


def check_sources(work,name,*,regions=None,flooded_cane=None):
    """Read every new source and its designed sediment back from the native MCA."""
    with np.load(work/"plan"/(name+".npz")) as a:
        y=a["water_y"];bed=a["target"];sand=a["water_bed"]
    if not y.any():
        return 0
    rx,rz=map(int,name.split(".")[1:])
    chunks={(rx*32+i,rz*32+j) for j,i in np.argwhere((y!=0).reshape(32,16,32,16).any(axis=(1,3)))}
    path=(work/"staged" if regions is None else regions)/(name+".mca")
    count=0
    for cx,cz,c in region_chunks(path,(rx*32,rx*32+31,rz*32,rz*32+31),chunks):
        dx,dz=(cx%32)*16,(cz%32)*16
        xz=np.s_[dz:dz+16,dx:dx+16]
        zz,xx=np.where(y[xz]!=0)
        top=y[xz][zz,xx];floor=bed[xz][zz,xx]
        wanted=sand[xz][zz,xx]
        sections={int(s["Y"]):s for s in c["sections"] if "block_states" in s}
        section_cache={}
        def read_layer(sy):
            if sy not in section_cache:
                section_cache[sy]=decode(sections[sy]["block_states"])
            return section_cache[sy]
        for sy in range((int(floor.min())-1)//16,int(top.max())//16+1):
            indices,palette=read_layer(sy)
            blocks=indices.reshape(16,16,16)[:,zz,xx]
            ys=sy*16+np.arange(16)[:,None]
            fluid=(ys>floor)&(ys<=top)
            matches=np.array([p=="minecraft:water[level=0]" for p in palette])[blocks]
            if (fluid&~matches).any():
                raise ValueError(f"Expected water source missing in chunk {cx},{cz}")
            is_bed=(ys==floor)
            materials=np.array([WATER_BEDS.index(p)+1 if p in WATER_BEDS else 0 for p in palette])[blocks]
            if (is_bed&(materials!=wanted)).any():
                raise ValueError(f"Exposed lakebed differs from the sediment in chunk {cx},{cz}")
            solid=np.array([kind(p.partition("[")[0])>=3 and kind(p.partition("[")[0])!=4 for p in palette])[blocks]
            if ((ys==floor-1)&~solid).any():
                raise ValueError(f"Unsupported lakebed in chunk {cx},{cz}")
        for sy in np.unique((top+1)//16):
            if sy not in sections:continue
            ids,palette=read_layer(sy)
            cane=np.array([p.partition("[")[0]=="minecraft:sugar_cane" for p in palette])
            if not cane.any():continue
            above=(top+1)%16*256+zz*16+xx
            rooted=(top+1)//16==sy
            for i in np.flatnonzero(rooted&cane[ids[above]]):
                x,z=int(xx[i]),int(zz[i]);stem_y=int(top[i])+1
                while stem_y//16 in sections:
                    ids,palette=read_layer(stem_y//16)
                    state=palette[ids[(stem_y%16)*256+z*16+x]]
                    if state.partition("[")[0]!="minecraft:sugar_cane":break
                    loc=(cx*16+x,stem_y,cz*16+z,state)
                    if flooded_cane is None:raise ValueError(f"Unsupported cane above a new lake source: {loc}")
                    flooded_cane.append(loc)
                    stem_y+=1
        count+=len(zz)
    if count!=np.count_nonzero(y):
        raise ValueError("Incomplete native water readback: "+name)
    return count


def water_atlas(design,work):
    checked=sum(check_sources(work,p.stem) for p in sorted((work/"plan").glob("r.*.npz")))
    meta=json.loads((design/"sites.json").read_bytes())
    verified=[]
    output=work/"water-surfaces";output.mkdir(exist_ok=True)
    tiles={}
    for site in meta:
        with np.load(work/"approved-mask"/(site["id"]+".npz")) as a:
            tiles[site["id"]]=(int(a["x0"]),int(a["z0"]),a["water"],site["level"])
    for s in meta:
        name=s["id"];level=s["level"]
        x0,z0,x1,z1=s["bounds"]
        data=read_window(work,s["bounds"],("k","h"))
        old_y=np.where(data["k"]==4,data["h"],-32768).astype(np.int16)
        new_y=np.full(old_y.shape,-32768,np.int16)
        own=np.zeros(old_y.shape,bool)
        for site,(x,z,mask,sy) in tiles.items():
            xx,zz=max(x,x0),max(z,z0);xe,ze=min(x+mask.shape[1],x1),min(z+mask.shape[0],z1)
            if xx>=xe or zz>=ze:continue
            clip=mask[zz-z:ze-z,xx-x:xe-x]
            roi=np.s_[zz-z0:ze-z0,xx-x0:xe-x0]
            new_y[roi][clip]=sy
            if site==name:own[roi]=clip
        if np.any((new_y!=-32768)&(old_y!=-32768)):
            raise ValueError("Old and new water overlap: "+name)
        final_y=np.maximum(old_y,new_y)
        walk=nd.label(final_y==level)[0]
        if not np.isin(walk[own],np.unique(walk[old_y==level])).all():
            raise ValueError("New water island disconnected from the original lake: "+name)
        np.savez_compressed(output/(name+".npz"),x0=x0,z0=z0,nodata=-32768,old_y=old_y,
                            new_y=new_y,final_y=final_y,site_new=own)
        rr,cc=np.where(own)
        yy,nn=np.unique(old_y[old_y!=-32768],return_counts=True)
        verified.append(dict(id=name,window=s["bounds"],new_bounds=[int(cc.min()+x0),int(rr.min()+z0),
                             int(cc.max()+x0+1),int(rr.max()+z0+1)],new_columns=len(cc),new_level=level,
                             new_columns_in_window=int((new_y!=-32768).sum()),
                             prior_water_columns_by_level={str(h):int(n) for h,n in zip(yy,nn)}))
    if sum(v["new_columns"] for v in verified)!=checked:
        raise ValueError("Water design windows do not exactly account for all native new source columns")
    (output/"index.json").write_text(json.dumps(dict(checked_native_columns=int(checked),windows=verified),indent=2))
    files=sorted(design.glob("*.npz"))+[design/"sites.json"]
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (work/"design-snapshot.json").write_text(json.dumps(hashes,indent=2))
    print("checked source columns",checked,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("plan","stage","verify","install"));p.add_argument("world",type=Path)
    p.add_argument("design",type=Path);p.add_argument("work",type=Path);p.add_argument("--workers",type=int,default=3)
    a=p.parse_args()
    if a.mode=="install":return install(a.world,a.work)
    if a.mode=="verify":return water_atlas(a.design,a.work)
    for name in ("before","plan","trees","staged"):(a.work/name).mkdir(parents=True,exist_ok=True)
    proposals=layout(a.design);pairs=native_regions(proposals)
    source=freeze(a.world,a.work,pairs)
    if a.mode=="plan":
        jobs=[(source,a.work/"before",rx,rz,{(rx*32+x,rz*32+z) for x in range(32) for z in range(32)}) for rx,rz in pairs]
        parallel(scan,jobs,a.workers);region_plan(a.work,proposals,pairs)
        return
    jobs=[(source,a.work/"before",a.work/"plan",a.work/"trees",a.work/"staged",rx,rz,True,True) for rx,rz in pairs]
    parallel(stage,jobs,a.workers)
    seal_ponds(a.work)
    records=[json.loads(p.read_bytes()) for p in (a.work/"staged").glob("r.*.json")]
    changed=sorted(c for r in records for c in r["chunks"])
    (a.work/"changed-chunks.json").write_text(json.dumps(changed,separators=(",",":")))
    print("regions/chunks/voxels",sum(bool(r["cells"]) for r in records),len(changed),sum(r["cells"] for r in records))


if __name__=="__main__":
    main()
