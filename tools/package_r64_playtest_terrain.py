"""Export exact terrain heights and reversible generation spans from verified region journals.

An indexed gzip member per region permits lazy decoding. Coordinates are local to a
chunk or a section. The index stays small when the infinite world grows beyond the survey.
"""
import argparse
import gzip
import io
import json
from pathlib import Path
import struct
import numpy as np


def package(staged,before,after,out):
    out.mkdir(exist_ok=True,parents=True)
    files=sorted(staged.glob('*.delta.npz'));coords=[];total=0
    for f in files:
        rx,rz=map(int,f.name.split('.')[1:3]);coords.append((rx,rz))
        d=np.load(f);sections=d['sections'];lengths=d['lengths'];rows=d['rows'];palette=d['states'].tolist()
        # A palette from a measured source may contain unrelated roof materials.
        # Only states referenced by a planned cell are needed for regeneration.
        used=np.unique(rows[:,1:]).tolist();lut=np.zeros(len(palette),np.uint16)
        for i,k in enumerate(used):lut[k]=i
        pal=[palette[k] for k in used]
        stream=io.BytesIO()
        def write(fmt,*values):stream.write(struct.pack('>'+fmt,*values))
        write('H',len(pal))
        for state in pal:
            name=state.encode('ascii');write('H',len(name));stream.write(name)
        mask=np.load(before/f'r.{rx}.{rz}.npz')
        newer=np.load(after/f'r.{rx}.{rz}.npz')
        newh=newer['h']
        # Link soil to the exact measured surface even for a newly planted tree on a
        # legacy authored datum. A fresh world without that tree still has a footing.

        heightmask=(mask['k']==3)&(newer['k']==3)
        chunks={};offset=0
        for (cx,cz,sy),n in zip(sections.tolist(),lengths.tolist(),strict=True):
            part=rows[offset:offset+n];offset+=n
            # Vertical, contiguous before/after state pairs become one replay span.
            at=part[:,0].astype(np.int32)
            col=(at&255);y=at>>8
            order=np.lexsort((y,col));col=col[order];y=y[order]
            old=lut[part[order,1]];new=lut[part[order,2]]
            start=np.r_[0,np.flatnonzero((np.diff(col)!=0)|(np.diff(y)!=1)|(np.diff(old.astype(int))!=0)|(np.diff(new.astype(int))!=0))+1]
            end=np.r_[start[1:]-1,len(y)-1]
            runs=np.stack((col[start],(y[start]<<4)|y[end],old[start],new[start]),axis=1)
            chunks.setdefault((cx,cz),[]).append((sy,runs))
        if len(pal)>255:raise ValueError('byte palette exceeded')
        write('H',len(chunks))
        for (cx,cz),slices in sorted(chunks.items()):
            xi,zi=(cx&31)*16,(cz&31)*16
            sel=np.s_[zi:zi+16,xi:xi+16];idx=np.flatnonzero(heightmask[sel])
            write('HH',((cz&31)<<5)|(cx&31),len(idx))
            # Separate streams of offsets and absolute heights compress more tightly.
            stream.write(idx.astype('B').tobytes());stream.write(newh[sel].ravel()[idx].astype('>i2').tobytes())
            write('B',len(slices))
            for sy,runs in slices:
                write('bH',sy,len(runs));stream.write(runs.astype('B').tobytes())
                total+=int((1+(runs[:,1]&15)-(runs[:,1]>>4)).sum())
        (out/f'{rx}_{rz}.bin.gz').write_bytes(gzip.compress(stream.getvalue(),compresslevel=7,mtime=0))
    # No classpath directory enumeration or file probing is needed while generating.
    (out/'index.bin').write_bytes(struct.pack('>IH',0x534c3634,len(coords))+b''.join(struct.pack('>hh',x,z) for x,z in coords))
    expected=sum(json.loads(f.read_bytes())['cells'] for f in staged.glob('r.*.json'))
    if total!=expected:raise ValueError(f'replay count {total} != {expected}')
    print(len(coords),total,sum(f.stat().st_size for f in out.iterdir()),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('staged','before','after','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();package(a.staged,a.before,a.after,a.out)
