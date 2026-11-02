"""Stream a cold whole-dimension surface capture through query_blocks."""
import argparse,json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from collections import Counter
import numpy as np
from query_blocks import iter_chunks,dimension_dir,decode_modern_section,palette_state,AIR
from plan_ashi_landscape_r54 import SOIL,NATURAL
from install_r53_carrier_trays import stopped_world

def region(job):
    world,out,rx,rz=job[:4];world=Path(world);out=Path(out)
    wanted=('noise','surface','carvers')if len(job)>4 and job[4]=='early'else('full','features','initialize_light','light','spawn')
    coords=[];blocks=[];palette=['minecraft:air'];lookup={palette[0]:0};statuses=[];devices=[];counts=Counter()
    for cx,cz,chunk in iter_chunks(dimension_dir(world,'projectseele:geofront'),(rx*32,rx*32+31,rz*32,rz*32+31)):
        status=str(chunk.get('Status','')).removeprefix('minecraft:');counts[status]+=1
        if status not in wanted:continue
        v=np.zeros((448,16,16),np.uint16)
        for sec in chunk.get('sections',[]):
            sy=int(sec.get('Y',-1000))
            if not -8<=sy<20:continue
            pal,indices=decode_modern_section(sec)
            if not pal:continue
            remap=[]
            for p in pal:
                s=palette_state(p)
                if s not in lookup:lookup[s]=len(palette);palette.append(s)
                remap.append(lookup[s])
            v[sy*16+128:sy*16+144]=np.asarray(remap,np.uint16)[indices].reshape(16,16,16)
        coords.append([cx,cz]);blocks.append(v);statuses.append(status)
        for t in chunk.get('block_entities',[]):
            p=[int(t.get(k,-99999))for k in ('x','y','z')]
            if -128<=p[1]<320:devices.append(dict(pos=p,id=str(t.get('id',''))))
    if not coords:return dict(region=[rx,rz],counts=dict(counts),chunks=0)
    arrays=np.asarray(blocks);del blocks
    name=f'r.{rx}.{rz}.npz'
    full=np.array([s=='full' for s in statuses])
    for group,keep in [('current',full),('proto',~full)]:
        if keep.any():np.savez_compressed(out/group/'source'/name,coordinates=np.asarray(coords,np.int32)[keep],blocks=arrays[keep],palette=palette)
    yy=np.arange(-128,320)[:,None,None];bare=[s.split('[')[0]for s in palette]
    soil=np.array([s in SOIL for s in bare]);air=np.array([s in AIR|{'minecraft:light','minecraft:barrier','minecraft:structure_void'}for s in bare])
    top=np.full((512,512),-129,np.int16);highest=top.copy();known=np.zeros((512,512),bool)
    for p,v,k in zip(coords,arrays,full):
        if not k:continue
        x,z=p[0]%32*16,p[1]%32*16;ar=np.s_[z:z+16,x:x+16]
        top[ar]=np.where(soil[v],yy,-129).max(0);highest[ar]=np.where(~air[v],yy,-129).max(0);known[ar]=True
    np.savez_compressed(out/'measure'/name,top=top,highest=highest,full=known)
    (out/'measure'/f'r.{rx}.{rz}.json').write_text(json.dumps(dict(statuses=[[*p,s]for p,s in zip(coords,statuses)],devices=devices)),encoding='utf8')
    return dict(region=[rx,rz],counts=dict(counts),chunks=len(coords),devices=len(devices))

def main(a):
    for q in ['current/source','current/delta','proto/source','proto/delta','measure']:(a.out/q).mkdir(parents=True,exist_ok=True)
    jobs=[]
    for f in (dimension_dir(a.world,'projectseele:geofront')/'region').glob('r.*.*.mca'):
        _,rx,rz=f.stem.split('.');job=(str(a.world),str(a.out),int(rx),int(rz))
        jobs.append((*job,'early')if getattr(a,'early_stages_only',False)else job)
    # Capture witness regions first, then all remaining saved regions.
    jobs.sort(key=lambda j:(0 if (j[2],j[3])in[(0,1),(0,-1),(-4,2),(1,2)]else 1,j[2],j[3]))
    rows=[]
    with stopped_world(a.world),ProcessPoolExecutor(max_workers=a.workers)as pool:
        futures={pool.submit(region,j):j for j in jobs}
        for f in as_completed(futures):
            r=f.result();rows.append(r);print('Captured',len(rows),'/',len(jobs),r['region'],r['counts'],flush=True)
    counts=Counter()
    for r in rows:counts.update(r['counts'])
    bounds=[min(j[2]for j in jobs)*512,min(j[3]for j in jobs)*512,max(j[2]for j in jobs)*512+511,max(j[3]for j in jobs)*512+511]
    report=dict(world=str(a.world),bounds_xz=bounds,bounds_y=[-128,319],regions=rows,chunk_statuses=dict(counts),world_written=False)
    (a.out/'capture.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    for group in ['current','proto']:
        m=dict(world=str(a.world),bounds_xz=bounds,regions=[],cells=0,world_written=False)
        if group=='proto':
            m['preserved_generation_statuses']=[p for f in(a.out/'measure').glob('*.json')for p in json.loads(f.read_text())['statuses']if p[2]!='full']
        (a.out/group/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf8')
    print('CAPTURE COMPLETE',dict(counts),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--world',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--workers',type=int,default=2)
    p.add_argument('--early-stages-only',action='store_true',help='Capture existing noise/surface/carvers chunks without advancing generation')
    main(p.parse_args())

