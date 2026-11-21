"""Measure and reshape selected lake shorelines from the installed GeoFront save."""
from collections import defaultdict
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as nd

from blend_r64_map_perimeter import freeze,install,parallel
from inspect_map_assets import region_chunks
from plan_r64_playtest_terrain import smooth
from stage_r64_playtest_terrain import save_verified_region
from survey_r64_playtest_terrain import kind
from write_deep_cells import REGION,clear_light,decode,encode,read_chunk,write_chunk

EMPTY=-32768
SITES=("western_facility","northwest_lakes","east_shelf")
WATER="minecraft:water[level=0]"
GRASS="minecraft:grass_block[snowy=false]"
BED_TYPES=("minecraft:gravel","minecraft:stone","minecraft:clay","minecraft:dirt","minecraft:sand","minecraft:mud")


def ground_chunk(chunk,names,registry):
    h=np.full((16,16),EMPTY,np.int16);bed=h.copy();mat=np.zeros(h.shape,np.uint16)
    klass=np.zeros(h.shape,np.uint8);canopy=np.zeros(h.shape,bool);root=np.zeros_like(canopy)
    gap=np.zeros_like(canopy);trunk=np.full(h.shape,32767,np.int16)
    for s in sorted(chunk["sections"],key=lambda q:-int(q["Y"])):
        base=16*int(s["Y"])
        if base>320:continue
        if base<-128 or np.all(bed!=EMPTY):break
        states=s.get("block_states")
        if not states:continue
        palette=[str(p["Name"]) for p in states["palette"]]
        if len(palette)==1 and kind(palette[0])==0:
            gap|=(h!=EMPTY)&(bed==EMPTY)
            continue
        ids,_=decode(states);ids=ids.reshape(16,16,16)
        cats=np.array([kind(n) for n in palette],np.uint8)[ids]
        y=base+np.arange(16)[:,None,None]
        top=cats>=3;found=(h==EMPTY)&top.any(axis=0);i=15-top[::-1].argmax(axis=0)
        h[found]=(base+i)[found];klass[found]=np.take_along_axis(cats,i[None],axis=0)[0][found]
        trees=cats==2
        canopy|=(trees&((h==EMPTY)|(y>h))).any(axis=0)
        woody=np.array([n.endswith(("_log","_wood")) for n in palette])[ids]
        alive=(woody&((h==EMPTY)|(y>h)))
        trunk=np.minimum(trunk,np.where(alive.any(axis=0),base+alive.argmax(axis=0),32767)).astype(np.int16)
        solid=(cats==3)|(cats==5);got=(bed==EMPTY)&solid.any(axis=0)
        iy=15-solid[::-1].argmax(axis=0)
        bed[got]=(base+iy)[got]
        known=[]
        for n in palette:
            if n not in registry:
                registry[n]=len(names);names.append(n)
            known.append(registry[n])
        mat[got]=np.take(np.array(known,np.uint16),np.take_along_axis(ids,iy[None],axis=0)[0])[got]
        gap|=((cats==0)&(y<h)&((bed==EMPTY)|(y>bed))).any(axis=0)
    root=(h!=EMPTY)&(trunk==h+1)
    return dict(h=h,k=klass,bed=bed,bed_material=mat,v=canopy,r=root,gap=gap)


def survey_site(job):
    regions,dest,site,bounds=job
    x0,z0,x1,z1=bounds
    cx0,cz0,cx1,cz1=x0//16,z0//16,(x1-1)//16,(z1-1)//16
    shape=((cz1-cz0+1)*16,(cx1-cx0+1)*16)
    out={s:np.full(shape,EMPTY if s in ("h","bed") else 0,
                   np.int16 if s in ("h","bed") else (np.uint16 if s=="bed_material" else np.uint8))
         for s in ("h","k","bed","bed_material","v","r","gap")}
    names=["minecraft:air"];registry={names[0]:0}
    for rx in range(cx0//32,cx1//32+1):
        for rz in range(cz0//32,cz1//32+1):
            file=regions/f"r.{rx}.{rz}.mca"
            for cx,cz,c in region_chunks(file,(cx0,cx1,cz0,cz1)):
                if str(c["Status"]).split(":")[-1]!="full":continue
                block=ground_chunk(c,names,registry)
                i,j=(cz-cz0)*16,(cx-cx0)*16
                for key in out:out[key][i:i+16,j:j+16]=block[key]
    select=np.s_[z0-cz0*16:z1-cz0*16,x0-cx0*16:x1-cx0*16]
    cropped={s:v[select] for s,v in out.items()}
    dest.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(dest/(site+".npz"),x0=x0,z0=z0,materials=np.array(names),**cropped)
    return site,shape


def project(a,key,origin,shape,default):
    field=np.full(shape,default)
    if key not in a:return field
    value=a[key]
    if value.ndim==0:return np.full(shape,value.item())
    x,z=int(a["x0"])-origin[0],int(a["z0"])-origin[1]
    if x<0 or z<0 or x+value.shape[1]>shape[1] or z+value.shape[0]>shape[0]:
        raise ValueError("Design exceeds the measured lake window")
    field[z:z+value.shape[0],x:x+value.shape[1]]=value
    return field


def plan_site(work,site):
    with np.load(work/"survey"/(site+".npz")) as survey:
        x0,z0=int(survey["x0"]),int(survey["z0"])
        h,k,bed,tree,roots,gap=(survey[v] for v in ("h","k","bed","v","r","gap"))
        mat=survey["materials"][survey["bed_material"]]
    with np.load(work/"design"/(site+".npz")) as design:
        origin=(x0,z0);shape=h.shape
        add=project(design,"add",origin,shape,False);fill=project(design,"fill",origin,shape,False)
        level=int(design["level"]) if "level" in design else 62
        requested_bank=project(design,"land_y",origin,shape,EMPTY)
        requested_depth=project(design,"depth",origin,shape,0)
    high=(k==4)&(h==level);low=(k==4)&(h<level);dry=k==3
    hard_dist=nd.distance_transform_edt((k!=5)&(k!=0))
    tree_dist=nd.distance_transform_edt((tree==0)&(roots==0))
    initial=(int(add.sum()),int(fill.sum()))
    add&=dry&(hard_dist>5)&(tree==0)&(gap==0)
    fill&=high&(hard_dist>5)&(gap==0)
    wet=(high&~fill)|add;change=add|fill
    if not change.any():raise ValueError("Empty shoreline design for "+site)
    margin=nd.distance_transform_edt(~change)
    # A pre-existing vertical wall can extend a few blocks past a designed
    # headland. Retire a narrow high-water lip only where a directly adjacent
    # lower lake would otherwise spill. The lower lake retains its waterline.
    steep_low=low&(h<level-3)
    immediate=wet&nd.binary_dilation(steep_low)&(margin<=15)
    if immediate.any():
        outward=nd.distance_transform_edt(~immediate)
        toward,ij=nd.distance_transform_edt(~steep_low,return_indices=True)
        dz,dx=np.indices(h.shape)
        width=2+1.5*(level-h[tuple(ij)])+np.sin((dx+x0)/7+(dz+z0)/9)
        retreat=high&wet&(toward<width*smooth((24-outward)/11))&(gap==0)&(hard_dist>5)
        fill|=retreat;wet&=~retreat;change|=retreat
        margin=nd.distance_transform_edt(~change)
    shore_dist=nd.distance_transform_edt(~wet);in_water=nd.distance_transform_edt(wet)
    zz,xx=np.ogrid[z0:z0+shape[0],x0:x0+shape[1]]
    ripple=np.sin(xx/19+zz/33)*.35+np.cos(zz/27-xx/17)*.22
    tight=site=="east_shelf"
    near=smooth(((48 if tight else 88)-margin)/(28 if tight else 52))
    protected=smooth((hard_dist-3)/12)*smooth(tree_dist/7)
    # Extrapolate the measured low-bank or island hillside through newly
    # restored land. Both sides of the old rectangular cut use this same field.
    sigma=6 if tight else 10
    sample=dry&(hard_dist>4)
    weight=nd.gaussian_filter(sample.astype(np.float32),sigma)
    smooth_land=nd.gaussian_filter(np.where(sample,h,0).astype(np.float32),sigma)/np.maximum(weight,1e-8)
    neighbor=nd.distance_transform_edt(~sample,return_distances=False,return_indices=True)
    land=np.where(weight>.04,smooth_land,h[tuple(neighbor)])
    slope=.76+.09*np.sin(xx/49+zz/32)
    rise=np.maximum(0,shore_dist-1)
    lower=level+.75-rise*slope
    upper=level+1.15+rise*(.65+.09*np.cos(zz/43-xx/62))
    ground=np.clip(land+ripple,lower,upper)
    # Where a lower natural lake abuts the high reservoir, shape a complete
    # divide. Its low side meets that lake at its original surveyed elevation.
    if low.any():
        dlo,ij=nd.distance_transform_edt(~low,return_indices=True)
        low_y=h[tuple(ij)]
        mix=smooth((2*(level-low_y)+12-dlo)/(1.2*(level-low_y)+10))
        fraction=dlo/np.maximum(dlo+shore_dist,1)
        divide=low_y+(level-low_y)*smooth(fraction)+1+.6*np.sin(np.pi*fraction)
        ground=ground*(1-mix)+divide*mix
    ground=np.where(shore_dist<=1, np.maximum(ground,level),ground)
    ground=np.where(requested_bank!=EMPTY,requested_bank,ground)
    dry_target=np.rint(h+(ground-h)*near*protected).astype(np.int16)
    dry_target[fill]=np.rint(ground[fill]).astype(np.int16)
    final_ground=bed.copy()
    dry_zone=(dry|fill)&~wet&(near>0)&(hard_dist>3)
    final_ground[dry_zone]=dry_target[dry_zone]
    # Retain each established visible bank of a lower pool when grading the
    # slope toward the high lake. A previously open natural sill retains its
    # original crest height; the grade must not lower it by another block.
    all_water=np.where(wet,level,np.where((k==4)&~fill,h,EMPTY))
    adjacent=nd.maximum_filter(all_water,footprint=nd.generate_binary_structure(2,1))
    crest=np.where(fill,adjacent,np.minimum(adjacent,h))
    final_ground[dry_zone]=np.maximum(final_ground[dry_zone],crest[dry_zone])
    # Recent lake extensions can have a one-block ledge right on the old line.
    # Join the measured basin progressively over a few dozen blocks.
    depth=np.clip(1+np.floor(np.maximum(0,in_water-1)*(.40+.06*np.sin(xx/40+zz/35))+ripple+.5),
                  1,12 if not tight else 8)
    desired=level-depth
    wet_weight=near*smooth(((25 if tight else 40)-in_water)/(16 if tight else 24))*protected
    near_bed=np.rint(bed+(desired-bed)*wet_weight).astype(np.int16)
    final_ground[wet]=near_bed[wet]
    final_ground[add]=desired[add].astype(np.int16)
    explicit=wet&(requested_depth>0)
    final_ground[explicit]=level-requested_depth[explicit]
    water=np.where(k==4,h,EMPTY).astype(np.int16)
    final_water=water.copy();final_water[fill]=EMPTY;final_water[add]=level
    active=((final_ground!=bed)|(final_water!=water))&(gap==0)&(tree==0)&((k==3)|(k==4))
    active&=(hard_dist>3)
    # Keep native substrate at surviving beds. Newly submerged columns use
    # the nearest surveyed sediment of the adjoining high lake.
    igr=nd.distance_transform_edt(~high,return_distances=False,return_indices=True)
    sediment=mat[tuple(igr)]
    sediment=np.where(high,mat,sediment)
    sed_code=np.zeros(shape,np.uint8)
    for i,n in enumerate(BED_TYPES):sed_code[sediment==n]=i
    ground_mat=np.where(fill,mat[tuple(neighbor)],mat)
    dry_code=np.ones(shape,np.uint8)
    # Naturally grassy land can have local gravel, sand, stone or clay along
    # its shore. Keep them where present, allowing the site's own upland soil
    # to supply restored island and headland interiors.
    for i,n in enumerate(BED_TYPES):dry_code[ground_mat==n]=i+2
    active_z,active_x=np.where(active)
    regions=np.unique(np.column_stack(((active_x+x0)//512,(active_z+z0)//512)),axis=0)
    for rx,rz in regions:
        z,x=np.where(active & (((xx//512)==rx)&((zz//512)==rz)))
        dest=work/"plan"/f"r.{rx}.{rz}";dest.mkdir(exist_ok=True,parents=True)
        vals=dict(x=(x+x0).astype(np.int32),z=(z+z0).astype(np.int32),before=bed[z,x],prior_water=water[z,x],
                  ground=final_ground[z,x],water=final_water[z,x],dry=dry_code[z,x],sediment=sed_code[z,x])
        np.savez_compressed(dest/(site+".npz"),**vals)
    return dict(site=site,requested=list(initial),accepted=[int(add.sum()),int(fill.sum())],
                planned_columns=int(active.sum()))


def region_stage(job):
    work,tag=job
    out=work/"staged";receipt=out/(tag+".json")
    if receipt.exists():return
    data=defaultdict(list)
    for p in sorted((work/"plan"/tag).glob("*.npz")):
        with np.load(p) as a:
            for key in a.files:data[key].append(a[key])
    data={k:np.concatenate(v) for k,v in data.items()}
    chunks=defaultdict(list)
    for i,(x,z) in enumerate(zip(data["x"],data["z"])):chunks[int(x)//16,int(z)//16].append(i)
    old=(work/"cold"/REGION/(tag+".mca")).read_bytes();buf=bytearray(old)
    palette=["minecraft:air","minecraft:stone","minecraft:dirt",WATER,GRASS,*[n for n in BED_TYPES if n not in ("minecraft:stone","minecraft:dirt")]]
    lookup={s:i for i,s in enumerate(palette)}
    def code(name):
        if name not in lookup:lookup[name]=len(palette);palette.append(name)
        return lookup[name]
    journal={};written=[];overrides=[];blocked=[]
    for (cx,cz),indices in sorted(chunks.items()):
        idx,loc,count,c=read_chunk(old,cx,cz);sections={int(s["Y"]):s for s in c["sections"] if "block_states" in s}
        oldg=data["before"][indices];newg=data["ground"][indices]
        top=np.maximum.reduce([oldg,newg,data["prior_water"][indices],data["water"][indices]])
        low=(int(min(oldg.min(),newg.min()))-1)//16;high=(int(top.max())+4)//16
        sylist=list(range(low,high+1))
        v=[]
        for sy in sylist:
            ids,names=decode(sections[sy]["block_states"])
            v.append(np.array([code(n) for n in names],np.uint16)[ids.reshape(16,16,16)])
        raw=np.concatenate(v);new=raw.copy();y0=low*16
        cats=np.array([kind(n.partition("[")[0]) for n in palette])
        entities={(int(e["x"]),int(e["z"])) for e in c.get("block_entities",[])}
        for i in indices:
            x,z=int(data["x"][i]),int(data["z"][i]);xx,zz=x%16,z%16
            a,b=int(data["before"][i]),int(data["ground"][i])
            u,w=int(data["prior_water"][i]),int(data["water"][i])
            col=raw[:,zz,xx];target=col.copy()
            lower=min(a,b);upper=max(a,b,u,w)
            oldstates=cats[col[lower-y0:upper-y0+1]]
            if (x,z) in entities or np.any((oldstates==5)|(oldstates==2)) or (b<a and (cats[col[b-y0-1:a-y0+1]]==0).any()):
                blocked.append((x,z));continue
            wet=w!=EMPTY
            if wet:
                surface=code(BED_TYPES[int(data["sediment"][i])])
            else:
                d=int(data["dry"][i]);surface=code(BED_TYPES[d-2]) if d>=2 else code(GRASS)
                if d==1 and u==EMPTY:surface=int(col[a-y0])
            for yy in range(lower,upper+1):
                if yy>b:
                    value=code(WATER) if wet and yy<=w else 0
                    if wet and yy<=min(u,w) and cats[col[yy-y0]]==4:value=int(col[yy-y0])
                elif yy==b:
                    value=surface
                elif yy<b-2:value=code("minecraft:stone")
                else:value=code("minecraft:dirt") if palette[surface] in (GRASS,"minecraft:dirt") else surface
                target[yy-y0]=value
            # Clear stem remnants after excavation or flooding. Preserve rooted
            # plants above unchanged shores and canopy elsewhere.
            if b<a or u!=w:
                for yy in range(upper-y0+1,len(target)):
                    if cats[col[yy]]!=1:break
                    target[yy]=0
            if np.array_equal(target,col):continue
            new[:,zz,xx]=target;overrides.append((x,z,b,w))
        if np.array_equal(new,raw):continue
        for j,sy in enumerate(sylist):
            original=raw[j*16:j*16+16].ravel();final=new[j*16:j*16+16].ravel()
            pos=np.flatnonzero(original!=final)
            if not pos.size:continue
            journal[cx,cz,sy]=np.stack([pos,original[pos],final[pos]],axis=1).astype(np.uint16)
            encode(sections[sy]["block_states"],final,palette)
        clear_light(c);c.pop("Heightmaps",None);write_chunk(buf,idx,loc,count,c);written.append((cx,cz))
    save_verified_region(out,tag,buf,old,journal,palette,written)
    arr=np.array(overrides,np.int32).reshape(-1,4)
    np.savez_compressed(work/"ground-water"/(tag+".npz"),x=arr[:,0],z=arr[:,1],
                        ground=arr[:,2].astype(np.int16),water=arr[:,3].astype(np.int16))
    receipt.write_text(json.dumps(dict(chunks=written,cells=sum(map(len,journal.values())),columns=len(overrides),blocked=blocked)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("survey","plan","stage","install"))
    p.add_argument("world",type=Path);p.add_argument("sites",type=Path)
    p.add_argument("work",type=Path);p.add_argument("--workers",type=int,default=3)
    a=p.parse_args();a.work.mkdir(exist_ok=True,parents=True)
    sites={r["id"]:r["bounds"] for r in json.loads(a.sites.read_bytes()) if r["id"] in SITES}
    if a.mode=="install":return install(a.world,a.work)
    if a.mode=="plan":
        (a.work/"plan").mkdir(exist_ok=True)
        records=[plan_site(a.work,s) for s in sites]
        (a.work/"plan.json").write_text(json.dumps(records,indent=2));print(records);return
    if a.mode=="stage":
        for s in ("staged","ground-water"):(a.work/s).mkdir(exist_ok=True)
        parallel(region_stage,[(a.work,f.name) for f in (a.work/"plan").glob("r.*")],a.workers)
        records=[json.loads(f.read_bytes()) for f in (a.work/"staged").glob("r.*.json")]
        chunks=sorted(c for row in records for c in row["chunks"])
        (a.work/"changed-chunks.json").write_text(json.dumps(chunks,separators=(",",":")))
        print(len(records),len(chunks),sum(r["cells"] for r in records));return
    pairs=set()
    for x,z,X,Z in sites.values():
        pairs.update((i,j) for i in range(x//512,(X-1)//512+1) for j in range(z//512,(Z-1)//512+1))
    cold=freeze(a.world,a.work,sorted(pairs))
    parallel(survey_site,[(cold/REGION,a.work/"survey",key,b) for key,b in sites.items()],a.workers)


if __name__=="__main__":main()
