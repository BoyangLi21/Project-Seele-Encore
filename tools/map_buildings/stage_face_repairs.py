"""Stage a face-survey repair plan with exact chunk SHA and per-block disk readback."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stage_r64_playtest_terrain import save_verified_region
from write_deep_cells import clear_light, decode, encode, read_chunk, write_chunk


def stage(job):
    path,regions,survey,out=job
    tag=path.stem
    before=(regions/(tag+'.mca')).read_bytes()
    sha=hashlib.sha256(before).hexdigest()
    index=survey/'source-sha256.json'
    if index.is_file():
        expected=json.loads(index.read_bytes())[tag+'.mca']
    else:
        with np.load(survey/'floating-runs'/path.name) as s:expected=s['source'].item()
    if sha!=expected:raise ValueError('Survey source changed: '+tag)
    with np.load(path) as p:
        rows=p['rows'].tolist()
        names=p['palette'].tolist()
    groups=defaultdict(lambda:defaultdict(list))
    for x,y,z,old,new,_ in rows:
        groups[x//16,z//16][y//16].append(((y&15)*256+(z&15)*16+(x&15),old,new))
    exact=[];ids={}
    def intern(name):
        if name not in ids:
            ids[name]=len(exact);exact.append(name)
        return ids[name]
    buf=bytearray(before)
    journal={};contained_water=0
    for (cx,cz),sections in groups.items():
        i,loc,count,root=read_chunk(before,cx,cz)
        block_entities={(int(ent['x']),int(ent['y']),int(ent['z'])) for ent in root.get('block_entities',())}
        available={int(s['Y']):s for s in root['sections']}
        for sy,changes in sections.items():
            sec=available[sy]['block_states']
            vals,palette=decode(sec)
            cells=[];lookup={s:j for j,s in enumerate(palette)}
            for at,old,new in sorted(changes):
                current=palette[vals[at]];expected=names[old];replacement=names[new]
                if current!=expected and ('[' in expected or current.partition('[')[0]!=expected):
                    raise ValueError(('Unexpected state',tag,cx,cz,sy,at,current,expected))
                x=cx*16+(at%16);z=cz*16+(at//16%16);y=sy*16+(at//256)
                if (x,y,z) in block_entities:raise ValueError(('Block entity',x,y,z))
                if current.startswith(('minecraft:water[','minecraft:lava[')) or current in ('minecraft:water','minecraft:lava'):
                    raise ValueError(('Fluid overwrite',x,y,z))
                if 'waterlogged=true' in current and replacement=='minecraft:air':
                    replacement='minecraft:water[level=0]';contained_water+=1
                if current==replacement:raise ValueError('Empty edit')
                if replacement not in lookup:
                    lookup[replacement]=len(palette);palette.append(replacement)
                vals[at]=lookup[replacement]
                cells.append((at,intern(current),intern(replacement)))
            journal[cx,cz,sy]=np.asarray(cells,dtype=np.uint16)
            encode(sec,vals,palette)
        clear_light(root);root.pop('Heightmaps',None)
        write_chunk(buf,i,loc,count,root)
    save_verified_region(out,tag,buf,before,journal,exact,list(groups))
    report=dict(chunks=sorted(groups),cells=len(rows),original_sha256=sha,
                staged_sha256=hashlib.sha256((out/(tag+'.mca')).read_bytes()).hexdigest(),
                contained_water_preserved=contained_water)
    (out/(tag+'.json')).write_text(json.dumps(report,separators=(',',':')))
    return tag,report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('plan','survey','regions','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    files=sorted(a.plan.glob('r.*.npz'))
    chunks=set();reports={}
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        jobs={pool.submit(stage,(f,a.regions,a.survey,a.out)):f for f in files}
        for done in as_completed(jobs):
            tag,report=done.result()
            reports[tag]=report
            chunks.update(map(tuple,report['chunks']))
            print(tag,len(reports),len(files),report['cells'],flush=True)
    (a.out/'changed-chunks.json').write_text(json.dumps(sorted(chunks),separators=(',',':')))
    (a.out/'regions.json').write_text(json.dumps(reports,sort_keys=True,separators=(',',':')))
    print(len(chunks),'chunks',sum(r['cells'] for r in reports.values()),'verified block changes',flush=True)

if __name__=='__main__':main()
