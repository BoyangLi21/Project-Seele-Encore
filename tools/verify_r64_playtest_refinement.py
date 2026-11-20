import argparse, json, os, sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from survey_r64_playtest_terrain import scan
from write_deep_cells import REGION

def journal(path):
    if not path.exists():return {},[]
    a=np.load(path);sections=a['sections'];rows=a['rows'];lengths=a['lengths']
    z={};start=0
    for s,l in zip(sections.tolist(),lengths.tolist()):
        z[tuple(s)]=rows[start:start+l];start+=l
    return z,a['states'].tolist()

def compare(job):
    first,last,tag=job
    old,opa=journal(first/(tag+'.delta.npz'));new,npa=journal(last/(tag+'.delta.npz'))
    states={s:i for i,s in enumerate(sorted(set(opa)|set(npa)))}
    o=np.array([states[k]for k in opa],np.int16);n=np.array([states[k]for k in npa],np.int16)
    changed=set()
    for key in old.keys()|new.keys():
        if key[:2] in changed:continue
        a=old.get(key);b=new.get(key)
        if a is None or b is None or not np.array_equal(a[:,0],b[:,0]) or not np.array_equal(o[a[:,2]],n[b[:,2]]):
            changed.add(key[:2])
    return tag,sorted(changed)

def rescan(job):
    actual,before,partial,out,tag,updates=job
    rx,rz=map(int,tag.split('.')[1:]);f=before/(tag+'.npz');dest=out/f.name
    if dest.exists():return
    if not updates:
        os.link(f,dest);return
    selected=set(map(tuple,updates))
    scan((actual,partial,rx,rz,selected))
    with np.load(f) as old,np.load(partial/f.name) as new:
        arrays={k:old[k] for k in old.files}
        for cx,cz in selected:
            zz,xx=(cz&31)*16,(cx&31)*16
            cut=np.s_[zz:zz+16,xx:xx+16]
            for key in arrays:arrays[key][cut]=new[key][cut]
        np.savez_compressed(dest,**arrays)

def main():
    p=argparse.ArgumentParser(description='Compare both exact cell journals and resurvey only the incremental chunks on the stopped world.')
    p.add_argument('mode',choices=['compare','survey']);p.add_argument('work',type=Path);p.add_argument('world',type=Path)
    p.add_argument('--workers',type=int,default=7)
    a=p.parse_args();d=a.work
    with ProcessPoolExecutor(a.workers) as pool:
        if a.mode=='compare':
            tags=[f.stem for f in (d/'final-staged').glob('r.*.json')]
            if len(tags)!=len(list((d/'landscape').glob('*.npz'))):raise ValueError('Final stage incomplete')
            reports=dict(pool.map(compare,[(d/'staged',d/'final-staged',tag) for tag in tags]))
            (d/'incremental-regions.json').write_text(json.dumps(reports,separators=(',',':')))
            (d/'incremental-chunks.json').write_text(json.dumps(sorted(c for cc in reports.values() for c in cc),separators=(',',':')))
            records=[json.loads(f.read_bytes()) for f in (d/'final-staged').glob('*.json')]
            (d/'final-changed_chunks.json').write_text(json.dumps(sorted(c for rec in records for c in rec['chunks']),separators=(',',':')))
            print(len(tags),sum(bool(cc) for cc in reports.values()),sum(map(len,reports.values())),sum(rec['cells'] for rec in records))
        else:
            reports=json.loads((d/'incremental-regions.json').read_bytes())
            out=d/'after-final';partial=d/'correction-survey';partial.mkdir(exist_ok=True);out.mkdir(exist_ok=True)
            tags=sorted(reports,key=lambda tag:(tag!='r.6.-5',tag))
            for i,_ in enumerate(pool.map(rescan,[(a.world,d/'after',partial,out,tag,reports[tag]) for tag in tags]),1):
                if i%10==0:print(i,len(tags),flush=True)
if __name__=='__main__':main()
