"""Survey actual saved paving at every height, with explicit read coverage.

Section palettes nominate material candidates only. The neighbouring sections
are decoded before measuring clearance/support. No plan masks, floor-height
selection, or clearance filter may hide a buried or stacked candidate.
"""
import argparse
import json
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from query_blocks import iter_chunks, dimension_dir, decode_modern_section, palette_state
from install_r53_carrier_trays import stopped_world
from map_pipeline.roads import ASPHALT, MARKING, road_layers, layer_graph, summarize


def chunk_layers(chunk):
    sections = {int(s['Y']): s for s in chunk.get('sections', [])}
    selected = [sy for sy,s in sections.items() if any(
        str(p.get('Name', '')) in ASPHALT | MARKING
        for p in s.get('block_states', {}).get('palette', []))]
    decoded = {}
    names = ['minecraft:air']; codes = {names[0]: 0}

    def section(sy):
        if sy not in decoded:
            s = sections.get(sy)
            if s is None:
                decoded[sy] = np.zeros((16,16,16), np.uint16)
            else:
                p = s.get('block_states', {}).get('palette', [])
                if len(p) > 1:
                    per = 64 // max(4, (len(p)-1).bit_length())
                    if len(s.get('block_states', {}).get('data', []))*per < 4096:
                        raise ValueError('truncated block-state indices at section '+str(sy))
                pal, ids = decode_modern_section(s)
                if len(pal) and (ids.min() < 0 or ids.max() >= len(pal)):
                    raise ValueError('invalid palette index at section '+str(sy))
                remap = []
                for entry in pal:
                    state = palette_state(entry)
                    if state not in codes:
                        codes[state] = len(names); names.append(state)
                    remap.append(codes[state])
                decoded[sy] = (np.asarray(remap, np.uint16)[ids].reshape(16,16,16)
                               if pal else np.zeros((16,16,16),np.uint16))
        return decoded[sy]

    rows = []
    for sy in sorted(selected):
        volume = np.concatenate([section(sy+d) for d in (-1,0,1)])
        found = road_layers(volume, names, (sy-1)*16)
        rows.append(found[(found[:,1] >= sy*16) & (found[:,1] < (sy+1)*16)])
    return np.concatenate(rows) if rows else np.empty((0,8),np.int32)


def survey_region(job):
    world, out, rx, rz = job; world=Path(world); out=Path(out)
    rows=[]; states=[]; diagnostics=[]; sections=Counter()
    for cx,cz,chunk in iter_chunks(dimension_dir(world,'projectseele:geofront'),
            (rx*32,rx*32+31,rz*32,rz*32+31),diagnostics=diagnostics):
        status=str(chunk.get('Status','')).removeprefix('minecraft:')
        states.append([cx,cz,status])
        if status != 'full': continue
        sections.update(int(s['Y']) for s in chunk.get('sections',[]))
        try:
            points=chunk_layers(chunk)
        except (ValueError,IndexError) as error:
            diagnostics.append(dict(chunk=[cx,cz],kind='invalid_section',error=str(error)))
            states[-1][2]='corrupt'; continue
        if len(points):
            points[:,0] += cx*16; points[:,2] += cz*16; rows.append(points)
    points=np.concatenate(rows) if rows else np.empty((0,8),np.int32)
    full=np.asarray([[cx,cz]for cx,cz,s in states if s=='full'],np.int32).reshape(-1,2)
    np.savez_compressed(out/'regions'/f'r.{rx}.{rz}.npz',roads=points,chunks=full)
    report=dict(region=[rx,rz],states=states,diagnostics=diagnostics,
                section_counts=dict(sections),layers=len(points))
    (out/'coverage'/f'r.{rx}.{rz}.json').write_text(json.dumps(report,indent=2),'utf8')
    return dict(region=[rx,rz],counts=dict(Counter(s for x,z,s in states)),
                layers=len(points),diagnostics=diagnostics)


def refresh_snapshot(world, previous, out, workers):
    """Reuse immutable sources only when the saved region predates the capture."""
    from capture_hakone_dimension_surface import region
    for folder in ('current/source','current/delta','proto/source','proto/delta','measure'):
        (out/folder).mkdir(parents=True,exist_ok=True)
    prior=json.loads((previous/'capture.json').read_text('utf8'))
    previous_rows={tuple(r['region']):r for r in prior['regions']}
    jobs=[]; rows=[]; reused=[]
    for path in sorted((dimension_dir(world,'projectseele:geofront')/'region').glob('r.*.*.mca')):
        rx,rz=map(int,path.stem.split('.')[1:]); name=path.stem+'.npz'
        evidence=previous/'measure'/(path.stem+'.json')
        # Empty/PROTO-only regions also have coverage in the old capture.
        stamp=evidence if evidence.exists() else previous/'capture.json'
        if (rx,rz) in previous_rows and path.stat().st_mtime_ns <= stamp.stat().st_mtime_ns:
            for sub in ('current/source','proto/source','measure'):
                src=previous/sub/name
                if src.exists(): os.link(src,out/sub/name)
            if evidence.exists(): os.link(evidence,out/'measure'/evidence.name)
            rows.append(previous_rows[rx,rz]); reused.append([rx,rz])
        else:
            jobs.append((str(world),str(out),rx,rz))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(region,j) for j in jobs]),1):
            r=f.result(); rows.append(r); print('Refreshed',i,len(jobs),r['region'],flush=True)
    counts=Counter()
    for r in rows: counts.update(r['counts'])
    report=dict(world=str(world),bounds_xz=prior['bounds_xz'],bounds_y=[-128,319],
                regions=rows,chunk_statuses=dict(counts),reused_unchanged_regions=reused,
                refreshed_regions=len(jobs),world_written=False)
    (out/'capture.json').write_text(json.dumps(report,indent=2),'utf8')
    for group in ('current','proto'):
        (out/group/'manifest.json').write_text(json.dumps(dict(world=str(world),regions=[],cells=0,
            bounds_xz=prior['bounds_xz'],world_written=False),indent=2),'utf8')


def main(a):
    a.out.mkdir(parents=True,exist_ok=False)
    for sub in ('regions','coverage'): (a.out/sub).mkdir()
    with stopped_world(a.world):
        if a.previous_snapshot:
            refresh_snapshot(a.world,a.previous_snapshot,a.out/'snapshot',a.workers)
        paths=sorted((dimension_dir(a.world,'projectseele:geofront')/'region').glob('r.*.*.mca'))
        jobs=[(str(a.world),str(a.out),*map(int,p.stem.split('.')[1:])) for p in paths]
        rows=[]
        with ProcessPoolExecutor(max_workers=a.workers) as pool:
            for i,f in enumerate(as_completed([pool.submit(survey_region,j) for j in jobs]),1):
                r=f.result(); rows.append(r)
                if r['layers'] or i%25==0: print('Surveyed',i,len(jobs),r['region'],r['layers'],flush=True)
    points=[]; chunks=[]
    for p in sorted((a.out/'regions').glob('*.npz')):
        with np.load(p) as f: points.append(f['roads']); chunks.append(f['chunks'])
    points=np.concatenate(points); chunks=np.concatenate(chunks)
    labels=layer_graph(points)
    np.savez_compressed(a.out/'observed.npz',points=points,component=labels,chunks=chunks)
    counts=Counter()
    for r in rows: counts.update(r['counts'])
    report=dict(world=str(a.world),bounds_y=[-1344,319],chunk_statuses=dict(counts),
        full_chunks=len(chunks),road_material_layers=len(points),regions=rows,
        components=summarize(points,labels),below_previous_scan=int((points[:,1]<-128).sum()),
        generation_masks_used_for_discovery=False,blocked_layers_excluded=False,
        world_written=False,material_candidates_are_not_road_authority=True)
    (a.out/'survey.json').write_text(json.dumps(report,indent=2),'utf8')
    print('SURVEY COMPLETE',dict(counts),'material layers',len(points),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--world',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    p.add_argument('--previous-snapshot',type=Path); p.add_argument('--workers',type=int,default=3)
    main(p.parse_args())
