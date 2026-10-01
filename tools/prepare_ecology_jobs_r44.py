"""Select all measured natural chunks for native feature previews, with no writes.

The native generator is the only vegetation author. The shared query_blocks
reader determines FULL chunks and existing soil; no duplicate Anvil decoder is
introduced here. Every generated feature still checks every touched coordinate.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import argparse, json, hashlib
import numpy as np
from query_blocks import iter_matching_sections, chunk_statuses

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/ecology'
MASK=(1<<64)-1

def unit(x,z,seed):
    h=(seed^(x*341873128712&MASK)^(z*132897987541&MASK))&MASK
    h^=h>>33;h=h*0xff51afd7ed558ccd&MASK;h^=h>>33;h=h*0xc4ceb9fe1a85ec53&MASK;h^=h>>33
    return (h>>32)/4294967295

def noise(x,z,seed):
    import math
    ix,iz=math.floor(x),math.floor(z);a,b=x-ix,z-iz;a=a*a*(3-2*a);b=b*b*(3-2*b)
    left=unit(ix,iz,seed)*(1-b)+unit(ix,iz+1,seed)*b
    right=unit(ix+1,iz,seed)*(1-b)+unit(ix+1,iz+1,seed)*b
    return left*(1-a)+right*a

def mosaic(x,z,seed):return noise(x/192,z/192,seed)*.78+noise(x/56,z/56,seed^0x6a09e667f3bcc909)*.22

def main():
    global OUT
    configuration_path=OUT/'biome_source.completed.json'
    p=argparse.ArgumentParser();p.add_argument('--batch-size',type=int,default=48);p.add_argument('--layer',choices=['surface','geofront','both'],default='both');p.add_argument('--refresh-existing',action='store_true');p.add_argument('--output',type=Path);args=p.parse_args()
    if args.output:OUT=args.output;OUT.mkdir(parents=True,exist_ok=True)
    assert 1<=args.batch_size<=128
    configuration=json.loads(configuration_path.read_text('utf8'));reservations=configuration['reserved_bounds']
    if args.refresh_existing:
        previous=json.loads((OUT/'retrofit_jobs.json').read_text('utf8'));selected=[]
        for path in previous['jobs']:selected.extend(json.loads(Path(path).read_text('utf8'))['chunks'])
        selected=[q for q in selected if q['layer']!='geofront' or not any(q['x']*16-12<=r[2] and q['x']*16+27>=r[0] and q['z']*16-12<=r[3] and q['z']*16+27>=r[1] for r in configuration['underground_reserved_bounds'])]
        jobs=[]
        for offset in range(0,len(selected),args.batch_size):
            chunks=selected[offset:offset+args.batch_size]
            available=sorted({(q['x']+dx,q['z']+dz) for q in chunks for dx in (-1,0,1) for dz in (-1,0,1)})
            path=OUT/f'jobs_{offset//args.batch_size:04d}.json'
            data=dict(world=WORLD.resolve().as_posix(),dimension='projectseele:geofront',chunks=chunks,available_chunks=available,
                reserved_bounds=reservations,underground_reserved_bounds=configuration['underground_reserved_bounds'],seed=configuration['seed'],read_only=True)
            path.write_text(json.dumps(data),'utf8');jobs.append(path.resolve().as_posix())
        previous.update(jobs=jobs,eligible_chunks=len(selected),surface_chunks=sum(q['layer']=='surface' for q in selected),geofront_chunks=sum(q['layer']=='geofront' for q in selected),underground_reservations=len(configuration['underground_reserved_bounds']))
        (OUT/'retrofit_jobs.json').write_text(json.dumps(previous,indent=2),'utf8')
        sample=[]
        for layer,biome,target in [('surface','geofront_woodland',(-900,1200)),('surface','geofront_meadow',(500,-700)),('geofront','geofront_woodland',(-800,600)),('geofront','geofront_meadow',(800,800))]:
            choices=[q for q in selected if q['layer']==layer and q['biome'].endswith(biome)]
            centre=min(choices,key=lambda q:(q['x']*16+8-target[0])**2+(q['z']*16+8-target[1])**2)
            sample.extend(q for q in choices if abs(q['x']-centre['x'])<=1 and abs(q['z']-centre['z'])<=1)
        sample=sorted([dict(t) for t in {tuple(q.items()) for q in sample}],key=lambda q:(q['layer'],q['x'],q['z']))
        calibration=OUT/'calibration.json';data.update(chunks=sample,available_chunks=sorted({(q['x']+dx,q['z']+dz) for q in sample for dx in (-1,0,1) for dz in (-1,0,1)}))
        calibration.write_text(json.dumps(data),'utf8')
        print('Refreshed jobs',len(jobs),'natural chunks',len(selected),'calibration chunks',len(sample),flush=True)
        return
    reserved=lambda x0,z0,x1,z1:any(x0<=r[2] and x1>=r[0] and z0<=r[3] and z1>=r[1] for r in reservations)
    candidates={};heights={};stats={}
    for cx,cz,sy,palette,ids in iter_matching_sections(WORLD,'projectseele:geofront',('minecraft:grass_block',),stats):
        if args.layer!='geofront' and 4<=sy<=19:
            layer='surface'
        elif args.layer!='surface' and -32<=sy<=-27 and np.hypot(cx*16+8-30,cz*16+8-296)<1650:
            layer='geofront'
        else:continue
        layer_bounds=reservations if layer=='surface' else configuration['underground_reserved_bounds']
        if any(cx*16-12<=r[2] and cx*16+27>=r[0] and cz*16-12<=r[3] and cz*16+27>=r[1] for r in layer_bounds):continue
        indices=[i for i,s in enumerate(palette) if s.partition('[')[0]=='minecraft:grass_block']
        soil=np.flatnonzero(np.isin(ids,indices))
        if len(soil)<20:continue
        key=(cx,cz,layer);top=sy*16+int(soil.max()>>8)
        candidates[key]=len(soil)+candidates.get(key,0);heights[key]=max(top,heights.get(key,-999))
    neighbours={(x+dx,z+dz) for x,z,_ in candidates for dx in (-1,0,1) for dz in (-1,0,1)}
    statuses=chunk_statuses(WORLD,'projectseele:geofront',neighbours);complete={p for p,s in statuses.items() if s=='full'}
    selected=[];unfinished=[]
    for x,z,layer in sorted(candidates):
        if layer=='geofront' and any(x*16-12<=r[2] and x*16+27>=r[0] and z*16-12<=r[3] and z*16+27>=r[1] for r in configuration['underground_reserved_bounds']):continue
        if not all((x+dx,z+dz) in complete for dx in (-1,0,1) for dz in (-1,0,1)):
            unfinished.append([x,z,layer]);continue
        pattern=mosaic(x*16+8,z*16+8,configuration['seed'])
        biome='geofront_highland' if layer=='surface' and heights[x,z,layer]>=136 and pattern>.34 else 'geofront_woodland' if pattern>.43 else 'geofront_meadow'
        selected.append(dict(x=x,z=z,layer=layer,biome='projectseele:'+biome,measured_soil_cells=candidates[x,z,layer],soil_top=heights[x,z,layer]))
    batches=[]
    for offset in range(0,len(selected),args.batch_size):
        batch=selected[offset:offset+args.batch_size]
        neighbourhood=sorted({(q['x']+dx,q['z']+dz) for q in batch for dx in (-1,0,1) for dz in (-1,0,1)})
        path=OUT/f'jobs_{offset//args.batch_size:04d}.json'
        data=dict(world=WORLD.resolve().as_posix(),dimension='projectseele:geofront',chunks=batch,available_chunks=neighbourhood,reserved_bounds=reservations,underground_reserved_bounds=configuration['underground_reserved_bounds'],
            native_generator='RegionalEcologyRetrofitR44',feature_layer=9,read_only=True,seed=configuration['seed'],
            invocation='-Dprojectseele.r44EcologyJob='+path.resolve().as_posix(),feature_policy='Vanilla registered placed features, whole-feature protection rollback, full natural-ground state preconditions')
        path.write_text(json.dumps(data,ensure_ascii=False),'utf8');batches.append(path.resolve().as_posix())
    summary=dict(measured_world=WORLD.resolve().as_posix(),stats=stats,eligible_chunks=len(selected),jobs=batches,
        surface_chunks=sum(q['layer']=='surface' for q in selected),geofront_chunks=sum(q['layer']=='geofront' for q in selected),
        skipped_unfinished_neighbourhood=unfinished,reservations=len(reservations),
        no_new_chunks_generated=True,world_changed=False,vegetation_generated=False,native_execution_pending=True,
        reference_boundary='Hakone mixed woodland/meadow is approximated with vanilla oak/birch/spruce. Species, seasons and exact TV landscaping are not claimed.')
    (OUT/'retrofit_jobs.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8')
    print({k:v for k,v in summary.items() if k not in ('jobs','skipped_unfinished_neighbourhood')},flush=True)

if __name__=='__main__':main()
