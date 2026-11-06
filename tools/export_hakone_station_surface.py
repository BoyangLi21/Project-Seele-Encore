"""Export FULL surface chunks from the current height-aware station snapshot."""
import argparse,copy,json
from collections import defaultdict
from pathlib import Path
import nbtlib
import numpy as np
from map_pipeline.station_sections import StationSections
from plan_ashi_landscape_r54 import SOIL,NATURAL
from query_blocks import AIR

def export(source,bounds,out):
    x,z,X,Z=bounds
    if x%16 or z%16 or(X+1)%16 or(Z+1)%16:raise ValueError('Whole chunks required')
    out.mkdir(exist_ok=False);(out/'source').mkdir();(out/'delta').mkdir()
    e=StationSections(source);groups=defaultdict(list)
    for cx in range(x//16,X//16+1):
        for cz in range(z//16,Z//16+1):groups[cx//32,cz//32].append((cx,cz))
    top=np.full((Z-z+1,X-x+1),-129,np.int16);highest=top.copy();protected=np.zeros(top.shape,bool)
    for(rx,rz),coords in groups.items():
        r=e.region(rx,rz)
        if r is None:raise ValueError('Uncaptured region')
        arrays=[];soil=np.asarray([s.split('[')[0]in SOIL for s in r['names']])
        air=np.asarray([s.split('[')[0]in AIR for s in r['names']]);natural=np.asarray([s.split('[')[0]in NATURAL for s in r['names']])
        yy=np.arange(-128,320)[:,None,None]
        for cx,cz in coords:
            parts=[]
            for sy in range(-8,20):
                key=cx,sy,cz
                if key not in r['index']:raise ValueError(f'Uncaptured or unfinished chunk/section: {key}')
                parts.append(r['blocks'][r['index'][key]])
            block=np.concatenate(parts,axis=0);arrays.append(block)
            area=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16]
            top[area]=np.where(soil[block],yy,-129).max(0);highest[area]=np.where(~air[block],yy,-129).max(0)
            protected[area]=((~natural[block])&(yy>=32)).any(0)
        np.savez_compressed(out/'source'/f'r.{rx}.{rz}.npz',coordinates=np.asarray(coords,np.int32),blocks=np.asarray(arrays,np.uint16),palette=np.asarray(r['names']))
    actors=[];occupied=np.zeros(top.shape,bool)
    for tag in nbtlib.load(source/'actors.dat')['Actors']:
        p=list(map(float,tag['Pos']))
        if x<=p[0]<=X and z<=p[2]<=Z and -128<=p[1]<320:
            actors.append(dict(id=str(tag['id']),pos=p,uuid=list(map(int,tag.get('UUID',[])))))
            px,pz=map(int,[p[0],p[2]])
            occupied[max(0,pz-z-16):min(Z-z+1,pz-z+17),max(0,px-x-16):min(X-x+1,px-x+17)]=True
    devices=[]
    for tag in nbtlib.load(source/'devices.dat')['Devices']:
        px,py,pz=(int(tag[k])for k in('x','y','z'))
        if x<=px<=X and z<=pz<=Z and -128<=py<320:devices.append(copy.deepcopy(tag))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](devices)}).save(out/'captured-devices.dat',gzipped=True)
    np.savez_compressed(out/'measured.npz',bounds=bounds,top=top,highest=highest,protected=protected,full=np.ones(top.shape,bool),actors=occupied)
    capture=dict(world=e.report['world'],bounds_xz=bounds,source_files=[p.relative_to(out).as_posix()for p in sorted((out/'source').glob('*.npz'))],
        actors=actors,chunk_statuses={'full':sum(map(len,groups.values()))},unavailable_chunks=[],
        exact_station_source=str(source),world_written=False)
    (out/'capture.json').write_text(json.dumps(capture,ensure_ascii=False,indent=2),'utf8')
    print('Exported current station surface:',capture['chunk_statuses'],'devices',len(devices),'actors',len(actors),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--bounds',type=int,nargs=4,required=True);a=p.parse_args();export(a.source,a.bounds,a.out)
