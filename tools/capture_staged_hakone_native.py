"""Capture an attested native export for offline design before its cold merge.

The source is explicitly staged, never called an installed FULL source. Both
recipe preparation and installation require the eventual native merge receipt.
"""
import argparse,json,shutil
from argparse import Namespace
from collections import defaultdict
from pathlib import Path
import nbtlib
from capture_hakone_corridor import main as capture
from install_r53_carrier_trays import stopped_world
from transplant_s22_authority import read_region,build_region,parse_chunk
from apply_s20_approved_semantic_repairs import chunk_blob
from query_blocks import chunk_statuses

DIM=Path('dimensions/projectseele/geofront')

def require_installed(candidate,world):
    file=candidate/'capture.json'
    if not file.exists():return
    cap=json.loads(file.read_text('utf8'))
    if not cap.get('staged_native_source'):return
    receipt_path=Path(cap['required_native_installation'])
    if not receipt_path.exists():raise ValueError('Original native generation must be installed before publishing this staged candidate')
    receipt=json.loads(receipt_path.read_text('utf8'))
    plan=json.loads((Path(cap['native_bake'])/'plan.json').read_text('utf8'))
    if receipt['status']!='installed'or Path(receipt['world']).resolve()!=world.resolve()or receipt['chunks']!=len(plan['chunks']):raise ValueError('Staged source native merge is not installed')
    if Path(receipt['source']).resolve()!=Path(plan['cache_world']).resolve()or receipt['existing_full_chunks_replaced']!=0:raise ValueError('Native receipt differs from staged source')
    bounds=cap['bounds_xz'];x,z,X,Z=bounds;chosen={(cx,cz)for cx in range(x//16,X//16+1)for cz in range(z//16,Z//16+1)}
    if any(s!='full'for s in chunk_statuses(world,'projectseele:geofront',chosen).values()):raise ValueError('Staged candidate still has uninstalled chunks')

def prepare(a):
    if a.out.exists():raise ValueError('Fresh staged source required')
    exp=json.loads((a.export/'plan.json').read_text('utf8'));bake=Path(exp['bake']);plan=json.loads((bake/'plan.json').read_text('utf8'))
    receipt=json.loads((a.export/'receipt.json').read_text('utf8'));progress=json.loads((a.export/'progress.json').read_text('utf8'))
    requested=set(map(tuple,json.loads((a.export/'chunks.json').read_text('utf8'))))
    if not progress['exported']or progress['completed']!=len(requested)or receipt['exported_chunks']!=len(requested)or(a.export/'error.txt').exists():raise ValueError('Incomplete native export')
    if Path(receipt['bake']).resolve()!=bake.resolve()or Path(plan['actual_world']).resolve()!=a.world.resolve():raise ValueError('Different native/world binding')
    prefix=set(map(tuple,plan['chunks'][:receipt['completed_prefix_at_start']]))
    x,z,X,Z=exp['bounds_xz'];selected={(cx,cz)for cx in range(x//16,X//16+1)for cz in range(z//16,Z//16+1)}
    if requested!=selected or not requested<=prefix:raise ValueError('This source must consist entirely of completed generated chunks')
    frozen=a.out/'frozen-world';frozen.mkdir(parents=True);(frozen/'session.lock').write_bytes(bytes(8))
    shutil.copy2(bake/'actual-before/level.dat',frozen/'level.dat')
    groups=defaultdict(list)
    for q in selected:groups[q[0]//32,q[1]//32].append(q)
    with stopped_world(a.world):
        for(rx,rz),coords in groups.items():
            name=f'r.{rx}.{rz}.mca';actual=a.world/DIM/'region'/name;prior=bake/'actual-before'/DIM/'region'/name
            before=read_region(prior)[1]if prior.exists()else[None]*1024;current=read_region(actual)[1]if actual.exists()else[None]*1024;rows=[None]*1024
            for cx,cz in coords:
                slot=cz%32*32+cx%32
                if before[slot]!=current[slot]:raise ValueError(('Actual target changed during candidate export',cx,cz))
                tag=nbtlib.load(a.export/'chunks'/f'{cx}_{cz}.dat')
                if str(tag['Status']).removeprefix('minecraft:')!='full'or(int(tag['xPos']),int(tag['zPos']))!=(cx,cz):raise ValueError('Invalid generated chunk')
                for k in('block_entities','entities','block_ticks','fluid_ticks','ToBeTicked','LiquidsToBeTicked'):
                    if tag.get(k):raise ValueError(('Export contains persistent objects/ticks',cx,cz,k))
                rows[slot]=chunk_blob(tag)
            target=frozen/DIM/'region'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(build_region(bytes(4096),rows))
    source=a.out/'source-capture';capture(Namespace(world=frozen,out=source,bounds=exp['bounds_xz'],reuse_captured_arrays=False))
    cap=json.loads((source/'capture.json').read_text('utf8'))
    cap.update(world=str(a.world),captured_world=str(frozen),staged_native_source=True,actual_world_current_full=False,
        native_bake=str(bake),native_export=str(a.export),required_native_installation=str(a.installation),world_written=False)
    (source/'capture.json').write_text(json.dumps(cap,ensure_ascii=False,indent=2),'utf8')
    print('Staged candidate source captured:',len(selected),'attested native FULL chunks; actual merge still required.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('export','world','installation','out'):p.add_argument('--'+n,type=Path,required=True)
    prepare(p.parse_args())
