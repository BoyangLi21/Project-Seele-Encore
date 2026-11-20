"""Compose verified terrain and woodland journals so regeneration and restoration use exact endpoints."""
import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from verify_r64_playtest_refinement import journal

def merge(job):
    early,late,out,tag=job;result=out/(tag+'.json')
    if result.exists():return
    first,second=[json.loads((d/(tag+'.json')).read_bytes())for d in (early,late)]
    if not first['cells'] or not second['cells']:
        source=early if first['cells'] else late
        rec=first if first['cells'] else second
        if rec['cells']:
            for suffix in ('.delta.npz','.mca'):os.link(source/(tag+suffix),out/(tag+suffix))
        result.write_text(json.dumps(rec));return
    a,aa=journal(early/(tag+'.delta.npz'));b,bb=journal(late/(tag+'.delta.npz'))
    palette=sorted(set(aa)|set(bb));ix={s:i for i,s in enumerate(palette)}
    alut=np.array([ix[s] for s in aa],np.uint16);blut=np.array([ix[s] for s in bb],np.uint16)
    rows=[];keys=[];lengths=[];chunks=set()
    for key in sorted(set(a)|set(b)):
        left=a.get(key);right=b.get(key)
        if left is None or right is None:
            data=left.copy() if right is None else right.copy()
            lut=alut if right is None else blut
            data[:,1:]=lut[data[:,1:]]
        else:
            before=np.full(4096,-1,np.int32);after=before.copy()
            idx=left[:,0];before[idx]=alut[left[:,1]];after[idx]=alut[left[:,2]]
            idx=right[:,0];expected=blut[right[:,1]]
            hit=after[idx]!=-1
            if not np.array_equal(after[idx[hit]],expected[hit]):raise ValueError(f'Intermediate state conflicts in {key}')
            before[idx[~hit]]=expected[~hit];after[idx]=blut[right[:,2]]
            idx=np.flatnonzero(before!=after)
            data=np.stack((idx,before[idx],after[idx]),axis=1).astype(np.uint16)
        if len(data):
            keys.append(key);rows.append(data);lengths.append(len(data));chunks.add(key[:2])
    cols=first.get('columns',0)
    np.savez_compressed(out/(tag+'.delta.npz'),sections=np.array(keys,np.int16),lengths=np.array(lengths,np.uint16),rows=np.concatenate(rows),states=np.array(palette))
    os.link(late/(tag+'.mca'),out/(tag+'.mca'))
    result.write_text(json.dumps(dict(chunks=sorted(chunks),cells=sum(lengths),columns=cols)))
def main():
    p=argparse.ArgumentParser();p.add_argument('first',type=Path);p.add_argument('second',type=Path);p.add_argument('out',type=Path);p.add_argument('--workers',type=int,default=6)
    a=p.parse_args();a.out.mkdir(exist_ok=True)
    tags={f.stem for f in a.first.glob('r.*.json')}
    if tags!={f.stem for f in a.second.glob('r.*.json')}:raise ValueError('Both frozen stages must cover the same surveyed region set')
    with ProcessPoolExecutor(a.workers) as pool:list(pool.map(merge,[(a.first,a.second,a.out,t) for t in tags]))
    rec=[json.loads(f.read_bytes())for f in a.out.glob('r.*.json')]
    print(sum(r['cells'] for r in rec),sum(bool(r['cells'])for r in rec),sum(len(r['chunks'])for r in rec))
if __name__=='__main__':main()
