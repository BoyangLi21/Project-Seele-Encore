"""Read station snapshots at their actual section heights, including underground.

Unknown sections return None. Only captured FULL chunks supply implicit air.
The reader never modifies its source or a live world.
"""
import json
from collections import OrderedDict
from pathlib import Path
import numpy as np


class StationSections:
    def __init__(self,source,cache_regions=3):
        self.source=Path(source);self.cache=OrderedDict();self.limit=cache_regions
        self.report=json.loads((self.source/'capture.json').read_text('utf8'))
        check=self.source/'source-check.json'
        if self.report['diagnostics']:
            if not check.exists():raise ValueError('Snapshot diagnostics need explicit review')
            proof=json.loads(check.read_text('utf8'))
            if proof['decode_errors']or not proof['source_usable_with_explicit_unknown_chunks']:
                raise ValueError('Snapshot source is not usable')

    def region(self,rx,rz):
        key=rx,rz
        if key in self.cache:self.cache.move_to_end(key);return self.cache[key]
        file=self.source/'sections'/f'r.{rx}.{rz}.npz'
        if not file.exists():return None
        with np.load(file)as a:
            row=dict(blocks=a['blocks'],names=list(map(str,a['palette'])),
                index={tuple(map(int,p)):i for i,p in enumerate(a['coordinates'])})
        self.cache[key]=row
        while len(self.cache)>self.limit:self.cache.popitem(last=False)
        return row

    def state(self,x,y,z):
        r=self.region(x//512,z//512)
        if r is None:return None
        index=r['index'].get((x//16,y//16,z//16))
        if index is None:return None
        return r['names'][int(r['blocks'][index,y%16,z%16,x%16])]

    def box(self,bounds):
        x,y,z,X,Y,Z=map(int,bounds)
        result=np.zeros((Y-y+1,Z-z+1,X-x+1),np.uint16)
        palette=['__unavailable__'];ids={palette[0]:0}
        for rx in range(x//512,X//512+1):
            for rz in range(z//512,Z//512+1):
                r=self.region(rx,rz)
                if r is None:continue
                codes=[]
                for name in r['names']:
                    if name not in ids:ids[name]=len(palette);palette.append(name)
                    codes.append(ids[name])
                if len(palette)>65535:raise ValueError('Box palette exceeds uint16')
                codes=np.asarray(codes,np.uint16)
                for (cx,sy,cz),index in r['index'].items():
                    l,t,b=max(x,cx*16),max(y,sy*16),max(z,cz*16)
                    R,T,B=min(X,cx*16+15),min(Y,sy*16+15),min(Z,cz*16+15)
                    if l>R or t>T or b>B:continue
                    result[t-y:T-y+1,b-z:B-z+1,l-x:R-x+1]=codes[r['blocks'][index,t-sy*16:T-sy*16+1,b-cz*16:B-cz*16+1,l-cx*16:R-cx*16+1]]
        return result,palette
