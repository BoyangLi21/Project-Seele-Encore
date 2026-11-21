"""Join saved-world six-face components across MCA boundaries and inventory genuine free groups."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import struct

import numpy as np

FACE=np.dtype([('lo','>i2'),('hi','>i2'),('id','>i4')])
SIZES=np.dtype([('size','>i4'),('flags','u1')])
CELLS=np.dtype([('group','>i4'),('column','>i4'),('lo','>i2'),('hi','>i2'),
                ('material','>u2'),('gap','>u2'),('near','u1')])


class Reader:
    def __init__(self,path):
        self.data=gzip.decompress(path.read_bytes())
        self.i=0
    def unpack(self,fmt):
        val=struct.unpack_from(fmt,self.data,self.i)
        self.i+=struct.calcsize(fmt)
        return val
    def integer(self):return self.unpack('>i')[0]
    def string(self):
        size=self.unpack('>H')[0]
        b=self.data[self.i:self.i+size];self.i+=size
        return b.decode('utf8')
    def array(self,dtype,n):
        a=np.frombuffer(self.data,dtype,count=n,offset=self.i)
        self.i+=a.nbytes
        return a


def read(path,edges=True):
    r=Reader(path)
    magic,rx,rz,y0,y1,full,partial,sections=r.unpack('>8i')
    if magic!=0x46435231:raise ValueError(path)
    sha=r.string()
    statuses={r.string():r.integer() for _ in range(r.integer())}
    chunks=r.array(np.uint8,1024).reshape(32,32)
    names=[r.string() for _ in range(r.integer())]
    sides=[]
    for _ in range(4):
        offsets=[0];segments=[]
        for _ in range(512):
            n=r.unpack('>H')[0]
            if n:
                spans=r.array(FACE,n)
                if edges:segments.append(spans)
            offsets.append(offsets[-1]+n)
        if edges:sides.append((offsets,np.concatenate(segments) if segments else np.empty(0,FACE)))
    sizes=r.array(SIZES,r.integer())
    cells=np.frombuffer(r.data,CELLS,offset=r.i)
    return (rx,rz),dict(path=path,sha=sha,full=full,partial=partial,sections=sections,statuses=statuses,
                        chunks=chunks,sides=sides,names=names,sizes=sizes,cells=cells,y=(y0,y1))


class Groups:
    def __init__(self,n):
        self.parents=np.arange(n,dtype=np.int32)
        self.pending=np.zeros(n,bool)
    def root(self,a):
        p=self.parents
        while a!=p[a]:
            p[a]=p[p[a]];a=int(p[a])
        return a
    def join(self,a,b):
        a,b=self.root(a),self.root(b)
        if a==b:return
        lo,hi=min(a,b),max(a,b)
        self.parents[hi]=lo;self.pending[lo]|=self.pending[hi]


def global_groups(regions):
    n=1
    for region in regions.values():
        region['offset']=n-1;n+=len(region['sizes'])
    groups=Groups(n)
    for region in regions.values():
        indices=np.flatnonzero(region['sizes']['flags']&2)+region['offset']+1
        groups.pending[indices]=True
    def gid(region,local):
        return int(local)+region['offset'] if local else 0
    for (rx,rz),region in regions.items():
        for side,(dx,dz) in enumerate([(-1,0),(1,0),(0,-1),(0,1)]):
            neighbor=regions.get((rx+dx,rz+dz))
            a,rows=region['sides'][side]
            other=side^1
            if neighbor:
                b,cols=neighbor['sides'][other]
                if side<2:status=neighbor['chunks'][:,31 if side==0 else 0]
                else:status=neighbor['chunks'][31 if side==2 else 0,:]
            for k in range(512):
                if a[k]==a[k+1]:continue
                if neighbor is None or status[k//16]!=2:
                    for local in rows['id'][a[k]:a[k+1]]:
                        if local:groups.pending[groups.root(gid(region,local))]=True
                if neighbor is None or side in (0,2):continue
                i,j=a[k],b[k]
                while i<a[k+1] and j<b[k+1]:
                    l,h,g=rows[i];ll,hh,gg=cols[j]
                    if l<=hh and ll<=h and (g or gg):groups.join(gid(region,g),gid(neighbor,gg))
                    if h<hh:i+=1
                    else:j+=1
    return groups


def resolve(args):
    region_data={};statuses=Counter()
    for path in sorted(args.survey.glob('r.*.mca.survey.gz')):
        key,data=read(path)
        # Keep only cross-region graph data on the first pass. Re-read cell runs
        # after the real neighboring support has been resolved.
        data['chunks']=data['chunks'].copy();data['sizes']=data['sizes'].copy()
        del data['cells'],data['names']
        statuses.update(data['statuses']);region_data[key]=data
    groups=global_groups(region_data)
    args.out.mkdir(exist_ok=True,parents=True)
    sources={f'r.{x}.{z}.mca':r['sha'] for (x,z),r in region_data.items()}
    stream=args.out/'floating-runs';stream.mkdir(exist_ok=True)
    catalog={};pending=set();expected_total=0;current_runs=[]
    for key,data in region_data.items():
        _,part=read(data['path'],edges=False)
        mapping=np.zeros(len(data['sizes'])+1,np.int32)
        for local,size in enumerate(data['sizes']['size'],1):
            g=groups.root(local+data['offset'])
            if not g:continue
            if groups.pending[g]:pending.add(g);continue
            mapping[local]=g
            expected_total+=int(size)
        rows=part['cells'];roots=mapping[rows['group']]
        good=roots>0
        if not good.any():continue
        rows=rows[good].copy();rows['group']=roots[good]
        pal=part['names'];rx,rz=key
        filename=f'r.{rx}.{rz}.npz'
        np.savez_compressed(stream/filename,rows=rows,palette=np.array(pal),source=data['sha'])
        current_runs.append(filename)
        for row in rows:
            g,pos,lo,hi,material,gap,near=(int(n) for n in row)
            x,z=rx*512+(pos&511),rz*512+(pos>>9)
            if g not in catalog:
                catalog[g]=[0,[x,lo,z,x+1,hi+1,z+1],Counter(),gap,gap,False]
            rec=catalog[g];length=hi-lo+1
            rec[0]+=length;b=rec[1]
            b[:]=min(b[0],x),min(b[1],lo),min(b[2],z),max(b[3],x+1),max(b[4],hi+1),max(b[5],z+1)
            rec[2][pal[material]]+=length;rec[3]=min(rec[3],gap);rec[4]=max(rec[4],gap);rec[5]|=bool(near)
    output=args.out/'floating-groups.jsonl'
    with output.open('w',encoding='utf8') as file:
        for g,(n,b,materials,ming,maxg,near) in catalog.items():
            file.write(json.dumps(dict(id=g,size=n,bounds=b,materials=materials,gap=[ming,maxg],diagonal=near),
                                  separators=(',',':'))+'\n')
    if sum(r[0] for r in catalog.values())!=expected_total:
        raise ValueError("The voxel inventory does not cover every disconnected component")
    summary=dict(regions=len(region_data),full=sum(r['full'] for r in region_data.values()),
                 partial=sum(r['partial'] for r in region_data.values()),observed_sections=sum(r['sections'] for r in region_data.values()),
                 statuses=statuses,min_y=min(r['y'][0] for r in region_data.values()),
                 max_y_exclusive=max(r['y'][1] for r in region_data.values()),
                 fully_bounded_groups=len(catalog),unknown_boundary_groups=len(pending),
                 bounded_group_cells=sum(r[0] for r in catalog.values()))
    # A region with no free groups no longer has a run file in the active
    # inventory, even when the destination already contains an earlier scan.
    (stream/'index.json').write_text(json.dumps(sorted(current_runs)),encoding='utf8')
    (args.out/'source-sha256.json').write_text(json.dumps(sources,sort_keys=True),encoding='utf8')
    (args.out/'connectivity.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(summary,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--survey',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    resolve(p.parse_args())
