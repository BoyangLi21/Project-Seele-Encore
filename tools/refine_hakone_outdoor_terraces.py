"""Expand existing occupied plots into usable outdoor terraces on the shared height field."""
import argparse,gzip,json,struct
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from hakone_earthworks import min_slope_envelope
from prepare_hakone_main_terrain import sample_grid
from query_blocks import AIR,iter_block_entities

def design(a):
    rows=json.loads((a.candidate/'catalog.json').read_text('utf8'))
    with gzip.open(a.resource,'rb')as f:
        magic,x0,z0,step,w,h=struct.unpack('>6i',f.read(24))
        old=np.frombuffer(f.read(w*h*2),'>i2').reshape(h,w).astype(np.float32)/16
        water=np.frombuffer(f.read(w*h*2),'>i2').reshape(h,w).astype(np.int16)
    with np.load(a.installed/'ground-fit-v6/surface-atlas.npz')as f:
        xx=f['x'];zz=f['z'];owner=f['owner']
    startx=(int(xx[0])-x0)//step;startz=(int(zz[0])-z0)//step
    owned=np.zeros(old.shape,np.uint8);owned[startz:startz+len(zz),startx:startx+len(xx)]=owner
    fixed=owned>0;bank=old.copy();wet=water!=-32768;bank[wet]=water[wet]-1
    target=np.full(old.shape,np.nan,np.float32);overlap=np.zeros(old.shape,bool)
    X=np.arange(w)*step+x0;Z=np.arange(h)*step+z0;sites=[]
    for row in rows:
        x,y,z,xx,Y,zz=row['occupied_bounds']
        # The parcel may include a whole raised shop rather than just its walls.
        # Four metres outside the owned body is a minimum outdoor plot here.
        ix=np.flatnonzero((X>=x-4)&(X<=xx+4));iz=np.flatnonzero((Z>=z-4)&(Z<=zz+4))
        area=np.ix_(iz,ix);prior=target[area];different=np.isfinite(prior)&(prior!=y)
        overlap[area]|=different;target[area]=y
        sites.append(dict(id=row['id'],outdoor_bounds=[x-4,z-4,xx+4,zz+4],floor=y))
    upper=min_slope_envelope(np.where(fixed,bank,np.inf),4)
    lower=-min_slope_envelope(np.where(fixed,-bank,np.inf),4)
    proposed=np.isfinite(target)&~overlap&~wet&~fixed&(target>=lower)&(target<=upper)
    # Neighbouring plots can have different actual floors. Drop only conflicting
    # extension pixels; never move a live building or override a street anchor.
    anchor=bank.copy();anchor[proposed]=target[proposed]
    upper=min_slope_envelope(np.where(fixed|proposed,anchor,np.inf),4)
    lower=-min_slope_envelope(np.where(fixed|proposed,-anchor,np.inf),4)
    proposed&=lower<=upper+.001;anchor[proposed]=target[proposed];anchor[~proposed]=bank[~proposed]
    upper=min_slope_envelope(np.where(fixed|proposed,anchor,np.inf),4)
    lower=-min_slope_envelope(np.where(fixed|proposed,-anchor,np.inf),4)
    if np.any((lower>upper+.001)&~fixed):raise ValueError('Outdoor terrace constraints still conflict')
    new=np.clip(old,lower,upper);new[fixed|wet]=old[fixed|wet];new[proposed]=target[proposed]
    new=np.rint(new*16)/16
    np.savez_compressed(a.candidate/'terrace-grading.npz',x=X,z=Z,old=old,height=new,water=water,proposed=proposed)
    with gzip.open(a.candidate/'hakone_surface.bin.gz','wb',compresslevel=6)as f:
        f.write(struct.pack('>6i',magic,x0,z0,step,w,h));f.write((new*16).astype('>i2').tobytes());f.write(water.astype('>i2').tobytes())
    (a.candidate/'outdoor-plots.json').write_text(json.dumps(sites,ensure_ascii=False),'utf8')
    print('Outdoor plot anchors',int(proposed.sum()),'changed field pixels',int((new!=old).sum()),flush=True)

def terrain(a):
    with np.load(a.candidate/'terrace-grading.npz')as f:d={k:f[k]for k in f.files}
    rows=json.loads((a.candidate/'catalog.json').read_text('utf8'));boxes=[r['occupied_bounds']for r in rows]
    e=Editor(a.candidate);report=[];yy=np.arange(-128,320)[:,None,None]
    soil_names={'minecraft:grass_block','minecraft:dirt','minecraft:stone','minecraft:andesite','minecraft:granite','minecraft:diorite','minecraft:coarse_dirt','minecraft:rooted_dirt','minecraft:podzol'}
    errors=[];devices=0
    for file in sorted((a.candidate/'source').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512);names=r['names']
        def code(s):
            if s not in r['ids']:r['ids'][s]=len(names);names.append(s)
            return r['ids'][s]
        air=code('minecraft:air');grass=code('minecraft:grass_block[snowy=false]');dirt=code('minecraft:dirt');stone=code('minecraft:stone')
        bare=[s.split('[')[0]for s in names];soil=np.array([s in soil_names for s in bare]);editable=np.array([s in soil_names|AIR|{'minecraft:grass','minecraft:tall_grass','minecraft:fern'}for s in bare])
        local=[b for b in boxes if b[0]<=rx*512+511 and b[3]>=rx*512 and b[2]<=rz*512+511 and b[5]>=rz*512]
        edited=0;declined=0;selected=set()
        for (cx,cz),b in zip(r['coords'],r['after']):
            cx,cz=int(cx),int(cz);zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
            old=np.rint(sample_grid(d,'old',xx,zz)).astype(int);new=np.rint(sample_grid(d,'height',xx,zz)).astype(int)
            mask=old!=new
            for x,y,z,X,Y,Z in local:mask&=~((xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z))
            if not mask.any():continue
            top=np.where(soil[b],yy,-129).max(0)
            for iz,ix in np.argwhere(mask):
                g=int(top[iz,ix]);target=int(new[iz,ix])
                if g<-127 or target<-127 or target>=319 or abs(g-int(old[iz,ix]))>4:declined+=1;continue
                lo,hi=min(g,target),max(g,target);v=b[lo+128:hi+129,iz,ix]
                if not editable[v].all():declined+=1;continue
                if target>g:b[g+129:target+129,iz,ix]=stone
                else:b[target+129:g+129,iz,ix]=air
                cap=b[max(-128,target-2)+128:target+128,iz,ix]
                cap[soil[cap]]=dirt
                b[target+128,iz,ix]=grass;edited+=1;selected.add((cx,cz))
        for pos,tag in iter_block_entities(a.world,'projectseele:geofront',(rx*512,-128,rz*512),(rx*512+511,319,rz*512+511),selected_chunks=selected):
            devices+=1
            if e.state(*pos)!=e.state(*pos,original=True):errors.append(['terrain-device',*pos])
        e.save();e.regions.clear();report.append(dict(region=file.name,columns=edited,held_structure_columns=declined))
        print('Outdoor terrain',file.name,edited,flush=True)
    regions=e.save();m=json.loads((a.candidate/'manifest.json').read_text('utf8'));m.update(regions=regions,cells=sum(r['cells']for r in regions),terrace_regions=report)
    (a.candidate/'manifest.json').write_text(json.dumps(m,indent=2),'utf8')
    (a.candidate/'functional-check.json').write_text(json.dumps(dict(errors=errors+[['detail-authoring-pending']],devices_checked=devices),indent=2),'utf8')
    print('Outdoor terrain columns',sum(r['columns']for r in report),'errors',len(errors),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('phase',choices=('design','terrain'))
    for n in('candidate','installed','world','resource'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();design(a)if a.phase=='design'else terrain(a)
