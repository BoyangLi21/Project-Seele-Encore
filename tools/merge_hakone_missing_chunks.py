"""Merge explicitly absent/unfinished lake chunks from the isolated native bake.

Never replaces an existing FULL chunk, actor region, player or progress file.
The original region bytes are retained before replacing only selected slots.
"""
import argparse,json,shutil,time
from pathlib import Path
from collections import defaultdict,Counter
from transplant_s22_authority import read_region,parse_chunk,build_region
from apply_s20_approved_semantic_repairs import atomic_replace
from install_r53_carrier_trays import stopped_world
from query_blocks import chunk_statuses


def merge(a):
    if a.out.exists():raise ValueError('Use a fresh reversible installation directory')
    if '/cache-server/'not in a.source.resolve().as_posix():raise ValueError('Expected the isolated authoring save')
    progress=json.loads((a.list.parent/'progress.json').read_text('utf8'))
    if not progress.get('generated'):raise ValueError('Native generation incomplete')
    chosen={tuple(p)for p in json.loads(a.list.read_text('utf8'))}
    groups=defaultdict(list)
    for x,z in chosen:groups[x//32,z//32].append((x,z))
    relative=Path('dimensions/projectseele/geofront/region');prepared=[];prior=Counter()
    a.out.mkdir(parents=True);(a.out/'before').mkdir();(a.out/'after').mkdir()
    for rx,rz in sorted(groups):
        name=f'r.{rx}.{rz}.mca';actual=a.world/relative/name
        existed=actual.exists()
        if existed:
            timestamps,rows=read_region(actual);shutil.copy2(actual,a.out/'before'/name)
        else:timestamps,rows=bytes(4096),[None]*1024
        _,source=read_region(a.source/relative/name)
        for cx,cz in groups[rx,rz]:
            slot=cz%32*32+cx%32;old=rows[slot]
            if old is not None:
                tag=parse_chunk(old);status=str(tag.get('Status','')).removeprefix('minecraft:')
                if status=='full':raise ValueError(f'Already FULL; preserve actual chunk {(cx,cz)}')
                if tag.get('block_entities')or tag.get('entities'):raise ValueError(f'Unfinished chunk has persistent objects {(cx,cz)}')
            else:status='absent'
            prior[status]+=1
            if source[slot]is None:raise ValueError(f'Native bake did not save {(cx,cz)}')
            tag=parse_chunk(source[slot])
            if str(tag.get('Status','')).removeprefix('minecraft:')!='full' or (int(tag['xPos']),int(tag['zPos']))!=(cx,cz):
                raise ValueError(f'Invalid generated native chunk {(cx,cz)}')
            rows[slot]=source[slot]
        staging=a.out/'after'/name;atomic_replace(staging,build_region(timestamps,rows))
        prepared.append((actual,staging,existed))
    written=[]
    try:
        for actual,staging,existed in prepared:
            actual.parent.mkdir(parents=True,exist_ok=True);atomic_replace(actual,staging.read_bytes());written.append((actual,existed))
        statuses=chunk_statuses(a.world,'projectseele:geofront',chosen)
        if any(s!='full'for s in statuses.values()):raise ValueError('Generated chunk save incomplete')
    except BaseException:
        for actual,existed in reversed(written):
            if existed:atomic_replace(actual,(a.out/'before'/actual.name).read_bytes())
            else:actual.unlink(missing_ok=True)
        raise
    report=dict(status='installed native terrain for lake authoring',world=str(a.world),chunks=len(chosen),
        before_statuses=dict(prior),existing_full_chunks_replaced=0,progress_files_written=[],
        source=str(a.source),remaining='Apply the real shoreline/bed and refresh changed LOD before lake delivery')
    (a.out/'installation.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('world','source','list','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    with stopped_world(a.source),stopped_world(a.world):merge(a)
