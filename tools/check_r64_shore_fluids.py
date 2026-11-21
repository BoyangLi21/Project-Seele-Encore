"""Read changed shores and a one-block halo from both sets of serialized chunk sections."""
from pathlib import Path
import argparse,json,os
import numpy as np
from scipy import ndimage as nd
from blend_r64_map_perimeter import link_or_copy,parallel,seal_ponds
from inspect_map_assets import region_chunks
from write_deep_cells import REGION,decode
from reshape_r64_lake_shores import SITES,EMPTY,kind,survey_site

def read(regions,bounds,low,high,fallback=None):
    x,z,X,Z=bounds
    a=np.zeros((high-low,Z-z,X-x),np.uint8)
    for rx in range(x//512,(X-1)//512+1):
        for rz in range(z//512,(Z-1)//512+1):
            p=regions/f"r.{rx}.{rz}.mca"
            if not p.exists() and fallback is not None:p=fallback/p.name
            for cx,cz,c in region_chunks(p,(x//16,(X-1)//16,z//16,(Z-1)//16)):
                i,j=cx*16-x,cz*16-z
                for s in c["sections"]:
                    y0=int(s["Y"])*16
                    if y0+16<=low or y0>=high:continue
                    ids,pal=decode(s["block_states"])
                    classes=[]
                    for state in pal:
                        n=state.partition("[")[0]
                        liquid=n in ("minecraft:water","minecraft:seagrass","minecraft:tall_seagrass","minecraft:kelp","minecraft:kelp_plant")
                        classes.append(1 if liquid else 0 if kind(n) in (0,1) else 2)
                    chunk=np.array(classes,np.uint8)[ids].reshape(16,16,16)
                    yy,Y=max(y0,low),min(y0+16,high)
                    a[yy-low:Y-low,j:j+16,i:i+16]=chunk[yy-y0:Y-y0]
    return a

def check(work,site,overrides):
    s=np.load(work/"survey"/(site+".npz"));t=np.load(work/"post-survey"/(site+".npz"))
    X,Z=int(s["x0"]),int(s["z0"]);H,W=s["k"].shape
    shape=np.zeros((H,W),bool)
    for vals in overrides:
        x=vals["x"]-X;z=vals["z"]-Z;inside=(x>=0)&(x<W)&(z>=0)&(z<H)
        shape[z[inside],x[inside]]=True
    expanded=nd.binary_dilation(shape)
    z,x=np.where(expanded);x0,z0,X1,Z1=(X+x.min()-2)//16*16,(Z+z.min()-2)//16*16,((X+x.max()+3+15)//16)*16,((Z+z.max()+3+15)//16)*16
    zz0,xx0=z0-Z,x0-X;zz1,xx1=Z1-Z,X1-X
    cut=np.s_[zz0:zz1,xx0:xx1]
    if zz0<0 or xx0<0 or zz1>H or xx1>W:raise ValueError("Fluid check exceeds surveyed window")
    ow=(s["k"][cut]==4);nw=t["k"][cut]==4
    oldbed=s["bed"][cut];newbed=t["bed"][cut];oldh=s["h"][cut];newh=t["h"][cut]
    use=expanded[cut]
    low=int(min(oldbed[ow&use].min(),newbed[nw&use].min()))-1
    high=int(max(oldh[ow&use].max(),newh[nw&use].max()))+2
    bounds=(x0,z0,X1,Z1);cold=work/"cold"/REGION
    before=read(cold,bounds,low,high);after=read(work/"staged",bounds,low,high,cold)
    y=np.arange(low,high)[:,None,None]
    was=(before==1)&ow&(y>oldbed)&(y<=oldh)&use
    wet=(after==1)&nw&(y>newbed)&(y<=newh)&use
    created=0;prior=0;total=0;locations=[]
    for axis,d in ((0,1),(1,1),(1,-1),(2,1),(2,-1)):
        oldface=was&np.roll(before==0,d,axis=axis)
        face=wet&np.roll(after==0,d,axis=axis)
        gained=face&~oldface
        for row in np.argwhere(gained):
            iy,iz,ix=map(int,row)
            neighbor=[iy,iz,ix];neighbor[axis]-=d
            yy,zz,xx=neighbor
            if nw[zz,xx] or yy+low>=newh[zz,xx]:
                raise ValueError(f"An added water face opens toward a lower water surface or sky at {ix+x0},{iy+low},{iz+z0}")
            locations.append((int(xx+x0),int(yy+low),int(zz+z0)))
        created+=int(gained.sum());prior+=int(oldface.sum());total+=int(face.sum())
    return dict(site=site,new_faces=created,prior_faces=prior,remaining_faces=total,open_cells=locations)

def gaps(w):
    ov=[dict(np.load(p)) for p in (w/"ground-water").glob("*.npz")]
    checks=[check(w,s,ov) for s in SITES]
    cells=sorted({cell for r in checks for cell in r["open_cells"]})
    if cells:
        (w/"shoreline-seal-points.json").write_text(json.dumps(cells))
    (w/"fluid-face-verification.json").write_text(json.dumps(checks,indent=2))
    print([(r["site"],r["new_faces"],r["prior_faces"],r["remaining_faces"]) for r in checks])
    return cells

def expose(w):
    for original in (w/"cold"/REGION).glob("*.mca"):
        selected=w/"staged"/original.name
        dst=w/"result-world"/REGION/original.name
        tmp=dst.with_suffix(".incoming")
        link_or_copy(selected if selected.exists() else original,tmp)
        os.replace(tmp,dst)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("work",type=Path);p.add_argument("sites",type=Path)
    a=p.parse_args();w=a.work
    expose(w)
    (w/"post-survey").mkdir(exist_ok=True)
    sites=[s for s in json.loads(a.sites.read_bytes()) if s["id"] in SITES]
    jobs=[(w/"result-world"/REGION,w/"post-survey",s["id"],s["bounds"]) for s in sites
          if not (w/"post-survey"/(s["id"]+".npz")).exists()]
    parallel(survey_site,jobs,3)
    seal_ponds(w,gaps)
    expose(w)
    added=w/"shoreline-seal-points.json"
    if added.exists():
        # Include even a subsurface wall in the explicit terrain override for
        # its column. The checks above ensure the measured top stays identical.
        for name in SITES:
            with np.load(w/"post-survey"/(name+".npz")) as a:
                x0,z0=int(a["x0"]),int(a["z0"]);h,k,bed=a["h"],a["k"],a["bed"]
            groups={}
            for x,y,z in json.loads(added.read_bytes()):
                j,i=z-z0,x-x0
                if 0<=i<h.shape[1] and 0<=j<h.shape[0]:
                    groups.setdefault((x//512,z//512),{})[x,z]=(int(bed[j,i]),int(h[j,i]) if k[j,i]==4 else EMPTY)
            for (rx,rz),extra in groups.items():
                f=w/"ground-water"/f"r.{rx}.{rz}.npz"
                with np.load(f) as a:arr={key:a[key] for key in a.files}
                for x,z in zip(arr["x"],arr["z"]):extra.pop((x,z),None)
                if extra:
                    rows=np.array([(x,z,*v) for (x,z),v in sorted(extra.items())],np.int32)
                    for col,key in enumerate(("x","z","ground","water")):
                        arr[key]=np.r_[arr[key],rows[:,col].astype(arr[key].dtype)]
                    np.savez_compressed(f,**arr)
    cc=sorted(c for f in (w/"staged").glob("*.json") for c in json.loads(f.read_bytes())["chunks"])
    (w/"changed-chunks.json").write_text(json.dumps(cc,separators=(",",":")))

if __name__=="__main__":main()
