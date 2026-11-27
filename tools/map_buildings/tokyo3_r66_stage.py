"""Prepare and verify an R66 stopped-world overlay. Never overwrites its input.

Usage: --authority <world with the current IDLE ledger> --regions <combined region folder>
       --plan <R66 design directory> --out <fresh external folder> --jdk <JDK bin directory>
"""
import argparse,gzip,hashlib,json,subprocess,struct
from collections import defaultdict
from pathlib import Path
import nbtlib
from private_cleanup import DATA,control,state
from city_body_sync import topology

def sha(p):
    with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def state_nbt(name):
    base,_,properties=name.partition('[')
    tag=nbtlib.Compound({'Name':nbtlib.String(base)})
    if properties:
        tag['Properties']=nbtlib.Compound({k:nbtlib.String(v) for item in properties[:-1].split(',') for k,v in [item.split('=')]})
    return tag

def surface_recipes(authority,plan,out,ledger):
    chunks=defaultdict(dict)
    with gzip.open(plan/'streetscape.tsv.gz','rt',encoding='utf8')as f:
        for line in f:
            sx,sy,sz,before,after=line.rstrip().split('\t');x,y,z=map(int,(sx,sy,sz));chunks[x>>4,z>>4][x,y,z]=after
    for (cx,cz),updates in chunks.items():
        rel=DATA/'city_rigid_generation_r45/surface'/f'{cx}_{cz}.dat';src=authority/rel
        if src.is_file():
            t=nbtlib.load(src);assert str(t['WorldUUID'])==ledger['uuid']
        else:t=nbtlib.File({'Version':nbtlib.Int(1),'WorldUUID':nbtlib.String(ledger['uuid']),'Palette':nbtlib.List[nbtlib.Compound]([]),'Spans':nbtlib.List[nbtlib.IntArray]([]),'BlockEntities':nbtlib.List[nbtlib.Compound]([])})
        palette=t['Palette'];names={state(e):i for i,e in enumerate(palette)};columns=defaultdict(dict)
        for row in t['Spans']:
            x,z,y0,y1,sid=map(int,row)
            if (x>>4,z>>4)!=(cx,cz):raise ValueError('foreign surface span '+str(rel))
            columns[x,z].update((y,sid)for y in range(y0,y1+1))
        for (x,y,z),new in updates.items():
            if new not in names:
                names[new]=len(palette);palette.append(state_nbt(new))
            columns[x,z][y]=names[new]
        spans=[]
        for (x,z),ys in sorted(columns.items()):
            first=last=None;sid=None
            for y,val in sorted(ys.items()):
                if first is None:first=last=y;sid=val
                elif y==last+1 and val==sid:last=y
                else:spans.append(nbtlib.IntArray([x,z,first,last,sid]));first=last=y;sid=val
            if first is not None:spans.append(nbtlib.IntArray([x,z,first,last,sid]))
        t['Spans']=nbtlib.List[nbtlib.IntArray](spans);dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);t.save(dest,gzipped=True)
        r=nbtlib.load(dest);check={(int(x),y,int(z)):int(s) for x,z,y0,y1,s in r['Spans'] for y in range(int(y0),int(y1)+1)}
        assert all(state(r['Palette'][check[pos]])==target for pos,target in updates.items())
    return chunks

def main():
    p=argparse.ArgumentParser();p.add_argument('--authority',required=True,type=Path);p.add_argument('--regions',required=True,type=Path);p.add_argument('--plan',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--jdk',required=True,type=Path);p.add_argument('--classes',type=Path)
    a=p.parse_args();root=a.out.resolve();world=a.authority.resolve();geometry=a.regions.resolve();plan=a.plan.resolve();jdk=a.jdk.resolve();repo=Path(__file__).resolve().parent
    if root in (world,geometry) or world in root.parents or geometry in root.parents or root in world.parents or root in geometry.parents:raise ValueError('overlay and source must be separate')
    if root.exists() and any(root.iterdir()):raise ValueError('use a new overlay directory')
    root.mkdir(parents=True,exist_ok=True);classes=a.classes or root/'classes';classes.mkdir(parents=True,exist_ok=True)
    java=jdk/'java.exe' if (jdk/'java.exe').exists() else jdk/'java';javac=java.with_name(java.name.replace('java','javac'))
    if not a.classes:subprocess.run([javac,'-d',classes,repo/'R66RegionPatch.java',repo/'Tokyo3CargoR66.java'],check=True)
    ledger=control(world);assert ledger['phase']=='IDLE'
    stats=json.loads((plan/'owners.json').read_text('utf8'));ts=topology(world)
    for i,t in ts.items():
        s=stats[str(i)]
        if list(t['centre'])!=s['centre'] or list(t['fp'])!=s['fp'] or t['ret']!=s['base'] or t['H']!=s['height']:raise ValueError(f'owner {i} geometry differs from baked moving mesh')
    args=[java,'-Xmx1700m','-XX:ActiveProcessorCount=2','-cp',classes]
    subprocess.run([*args,'Tokyo3CargoR66',world,plan,root],check=True)
    region_out=root/DATA.parent/'region';subprocess.run([*args,'R66RegionPatch',geometry,root/'deltas',region_out],check=True)
    surface=surface_recipes(world,plan,root,ledger)
    chunks=set();sections=set();regions={}
    for delta in sorted((root/'deltas').glob('*.delta.gz')):
        _,rx,rz,_,_=delta.name.split('.');rx,rz=int(rx),int(rz);reg=f'r.{rx}.{rz}.mca'
        regions[reg]={'input':sha(geometry/reg),'output':sha(region_out/reg)}
        with gzip.open(delta,'rb') as f:
            def read(fmt):return struct.unpack(fmt,f.read(struct.calcsize(fmt)))[0]
            assert read('>I')==0x46423444
            for _ in range(read('>H')):f.read(read('>H'))
            for _ in range(read('>I')):
                idx=read('>H');cx=(idx&31)+32*rx;cz=(idx>>5)+32*rz;chunks.add((cx,cz))
                for _ in range(read('>H')):
                    y=read('>h');n=read('>H');f.read(n*6);sections.add((cx,y,cz))
            assert not f.read()
    # Include neighbouring columns affected by removal/re-lighting in both native caches.
    lighting={(x+dx,z+dz)for x,z in chunks for dx in (-1,0,1) for dz in (-1,0,1)}
    manifest={'schema':1,'world_uuid':ledger['uuid'],'depth':ledger['depth'],'current_trip':ledger['current'][0],'previous_trip':ledger['previous'][0],
      'owners':[int(i) for i,s in stats.items() if s['changes']],'regions':regions,'chunks':sorted(chunks),'native_cache_chunks':sorted(lighting),
      'dh_l0':sorted({(x>>2,z>>2) for x,z in lighting}),'sections':sorted(sections),'static_regeneration_chunks':len(surface),'data':{}}
    for dest in sorted((root/DATA).rglob('*.dat')):
        rel=dest.relative_to(root);src=world/rel;manifest['data'][rel.as_posix()]={'input':sha(src) if src.exists() else None,'output':sha(dest)}
    (root/'manifest.json').write_text(json.dumps(manifest,indent=1),'utf8')
    print(json.dumps({'depth':ledger['depth'],'regions':len(regions),'chunks':len(chunks),'cached_leaves':len(manifest['dh_l0']),'data':len(manifest['data'])}),flush=True)
if __name__=='__main__':main()
