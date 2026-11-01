"""Measure actual saved/candidate voxel envelopes independently of edit masks."""
import argparse,json
from pathlib import Path
from collections import defaultdict
import numpy as np
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR

def verify(a):
    rails=defaultdict(set)
    for row in json.loads(a.curves.read_text('utf8'))['trains']:
        for p in row['points']:
            x,y,z=map(int,np.floor(p))
            if not -120<y<310:continue
            for px in range(x-2,x+3):
                for pz in range(z-2,z+3):rails[px//16,pz//16].add((px,y,pz))
    e=Editor(a.source);blocked=[];checked=0;foreign=[];airport=[];ballast=0
    for file in sorted((a.source/'source').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:])
        needed=any(q[0]//32==rx and q[1]//32==rz for q in rails)
        needed|=rx in (0,1,2,-5,-4,-3) and rz in (-1,0,2)
        if not needed:continue
        r=e.region(rx*512,rz*512);bare=[s.split('[')[0] for s in r['names']]
        soil=np.array([s in SOIL for s in bare]);other=np.array([s not in SOIL|AIR|{'minecraft:light','minecraft:barrier','minecraft:grass','minecraft:tall_grass'} for s in bare])
        for q,v in zip(r['coords'],r['after']):
            key=tuple(map(int,q))
            for x,y,z in rails[key]:
                c=v[y+128:y+134,z%16,x%16];checked+=1
                if soil[c].any():blocked.append([x,y,z,int(soil[c].sum())])
                if other[c].any():foreign.append([x,y,z,sorted(set(r['names'][i] for i in c[other[c]]))])
            # Airport evidence samples every existing concrete apron column,
            # not the repairer's airport footprint or terrain mask.
            cx,cz=key
            if (500<=cx*16<=1220 and 1050<=cz*16<=1500) or (-2150<=cx*16<=-1450 and -320<=cz*16<=80):
                for iz,ix in np.argwhere(np.isin(v[208],[i for i,n in enumerate(bare) if n in {'minecraft:gray_concrete','minecraft:black_concrete','minecraft:yellow_concrete','minecraft:white_concrete'}])):
                    above=v[209:,iz,ix]
                    if soil[above].any():
                        x,z=cx*16+int(ix),cz*16+int(iz);heights=np.flatnonzero(soil[above])+81
                        if all(bare[v[y+128,iz,ix]]=='minecraft:gravel' and any(abs(px-x)<=1 and abs(pz-z)<=1 and py==y+1 for px,py,pz in rails[key]) for y in heights):ballast+=1
                        else:airport.append([x,80,z,int(soil[above].sum())])
        e.regions.clear()
    report=dict(checked_rail_columns=checked,rail_soil_blocked_columns=len(blocked),rail_findings=blocked,
        rail_non_geological_columns=len(foreign),rail_non_geological_findings=foreign,airport_soil_ceiling_columns=len(airport),airport_findings=airport,airport_retained_elevated_track_ballast_columns=ballast,
        scope='Fixed-width/height envelope around the supplied exported train curves, and actual apron paving. Not a fresh all-vehicle continuous sweep. No edit mask used; non-geological objects require review.',visual_verified=False)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2),'utf8')
    print({k:v for k,v in report.items() if not isinstance(v,list)},flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in ['source','curves','out']:p.add_argument('--'+k,type=Path,required=True)
    verify(p.parse_args())
