"""Use measured remaining faces to extend short dry toes from the fixed, higher bank."""
import argparse
from collections import defaultdict
from pathlib import Path
import numpy as np

def finish(work,faces,measured):
    groups=defaultdict(list)
    cache={}
    def level(x,z):
        key=(x>>9,z>>9)
        if key not in cache:cache[key]=np.load(measured/('r.%d.%d.npz'%key))['h']
        return int(cache[key][z&511,x&511])
    for x,z,ax,old,delta in np.load(faces).tolist():
        if delta<=3:continue
        a=(x,z);b=(x+int(ax==1),z+int(ax==0));left,right=level(*a),level(*b)
        lx,lz=a if left<right else b
        high=max(left,right)
        # The measured cases are short dry shoulders beside a retained water datum.
        # A 1:1.3 toe ties into the lower ground and ends where it already reaches grade.
        for rx in range((lx-18)>>9,((lx+18)>>9)+1):
            for rz in range((lz-18)>>9,((lz+18)>>9)+1):
                groups[rx,rz].append((lx,lz,high))
    for (rx,rz),points in groups.items():
        f=work/'final-plan'/f'r.{rx}.{rz}.npz'
        if not f.exists():continue
        with np.load(f) as a:payload={k:a[k] for k in a.files}
        k=np.load(work/'survey'/f.name)['k']
        t=payload['target'];old=t.copy()
        gz,gx=np.ogrid[rz*512:(rz+1)*512,rx*512:(rx+1)*512]
        for x,z,top in points:
            dist=np.hypot(gx-x,gz-z)
            toe=np.rint(top-1-.78*dist).astype(np.int16)
            eligible=(k==3)&(dist<=18)&(toe>t)
            t[eligible]=toe[eligible]
        if np.any(t!=old):
            np.savez_compressed(f,**payload)
            yield rx,rz,int((t!=old).sum())
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('work',type=Path);p.add_argument('faces',type=Path);p.add_argument('measured',type=Path)
    a=p.parse_args()
    for rec in finish(a.work,a.faces,a.measured):print(*rec)
