"""Discover every saved surface-band road layer before testing its clearance.

Material observations are candidates, never construction permission. Blocked
roads and small components remain in the output. No generator mask defines the
denominator, and no edge joins vertically stacked floors at the same X/Z.
"""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from author_hakone_lakefront import Editor
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL, PLANTS

ASPHALT = {'minecraft:black_concrete', 'projectseele:road_asphalt_slab',
           'projectseele:road_marking_slab'}
MARKING = {'minecraft:white_concrete', 'minecraft:yellow_concrete',
           'minecraft:gray_concrete', 'minecraft:smooth_stone',
           'minecraft:smooth_stone_slab'}
EMPTY = AIR | PLANTS | {'minecraft:light', 'minecraft:structure_void'}


def road_layers(v, names):
    bare = [s.split('[')[0] for s in names]
    asphalt = np.array([s in ASPHALT for s in bare])
    marking = np.array([s in MARKING for s in bare])
    pavement = asphalt | marking
    # A buried road is retained; only the inside of a solid pavement stack is
    # excluded. Half slabs have their own physical surface height.
    selected = pavement[v]
    selected[:-1] &= ~pavement[v[1:]]
    iy, iz, ix = np.nonzero(selected)
    if not len(iy):
        return np.empty((0, 8), np.int32)
    material = v[iy, iz, ix]
    offsets = np.array([1 if 'type=bottom' in s else 2 for s in names])
    empty = np.array([s in EMPTY for s in bare])
    soil = np.array([s in SOIL for s in bare])
    soil_hits = np.zeros(len(iy), np.int32)
    object_hits = soil_hits.copy()
    for dy in range(1, 4):
        inside = iy + dy < len(v)
        above = v[np.minimum(iy + dy, len(v)-1), iz, ix]
        soil_hits += inside & soil[above]
        object_hits += inside & ~soil[above] & ~empty[above]
    gap = np.zeros(len(iy), np.int32)
    alive = np.ones(len(iy), bool)
    for dy in range(1, 17):
        alive &= (iy >= dy) & empty[v[np.maximum(0, iy-dy), iz, ix]]
        gap += alive
    return np.column_stack((ix, iy-128, iz, 2*(iy-128)+offsets[material],
                            asphalt[material], soil_hits, object_hits, gap)).astype(np.int32)


def extract_region(job):
    source, out, name = map(Path, job)
    rx, rz = map(int, name.stem.split('.')[1:])
    e = Editor(source)
    r = e.region(rx*512, rz*512)
    rows = []
    for (cx, cz), v in zip(r['coords'], r['after']):
        row = road_layers(v, r['names'])
        if len(row):
            row[:, 0] += int(cx)*16
            row[:, 2] += int(cz)*16
            rows.append(row)
    rows = np.concatenate(rows) if rows else np.empty((0, 8), np.int32)
    np.savez_compressed(out/name.name, roads=rows, chunks=r['coords'])
    return name.name, len(rows)


def keys(x, z, h):
    # Fixed bias/stride is explicit and collision-free within the recorded
    # world bounds. This is coordinate indexing, not a file fingerprint.
    if np.any(abs(x) >= 32768) or np.any(abs(z) >= 32768) or np.any((h < -256) | (h > 640)):
        raise ValueError('Road coordinate outside supported encoding')
    return ((x.astype(np.int64)+32768)*65536 + z+32768)*1024 + h+256


def layer_graph(points):
    encoded = keys(points[:,0], points[:,2], points[:,3])
    order = np.argsort(encoded)
    ordered = encoded[order]
    rr, cc = [], []
    # Cardinal interfaces only; diagonal corner contact is not a road link.
    for dx, dz in ((1,0),(0,1)):
        for dh in (-2,-1,0,1,2):
            k = keys(points[:,0]+dx, points[:,2]+dz, points[:,3]+dh)
            at = np.searchsorted(ordered, k)
            valid = at < len(ordered)
            valid[valid] &= ordered[at[valid]] == k[valid]
            rr.append(np.flatnonzero(valid)); cc.append(order[at[valid]])
    rr, cc = np.concatenate(rr), np.concatenate(cc)
    graph = coo_matrix((np.ones(len(rr),np.uint8),(rr,cc)), shape=(len(points),len(points))).tocsr()
    return connected_components(graph, directed=False)[1]


def summarize(points, labels):
    counts = np.bincount(labels)
    n = len(counts)
    lo = np.full((n,3), 2**30, np.int32); hi = -lo
    np.minimum.at(lo, labels, points[:,:3]); np.maximum.at(hi, labels, points[:,:3])
    soil = np.bincount(labels, weights=points[:,5]>0).astype(int)
    other = np.bincount(labels, weights=points[:,6]>0).astype(int)
    floating = np.bincount(labels, weights=points[:,7]>3).astype(int)
    return [dict(id=int(i), columns=int(counts[i]), bounds=[*map(int,lo[i]),*map(int,hi[i])],
                 soil_obstructed=int(soil[i]), other_obstructed=int(other[i]),
                 suspended=int(floating[i]), classification='CANDIDATE')
            for i in np.argsort(counts)[::-1]]


def discover(a):
    a.out.mkdir(parents=True, exist_ok=False)
    raw = a.out/'regions'; raw.mkdir()
    jobs = [(str(a.source),str(raw),str(p.name)) for p in (a.source/'source').glob('*.npz')]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, f in enumerate(as_completed([pool.submit(extract_region,j) for j in jobs]),1):
            name,n=f.result()
            if n: print('Observed',i,'/',len(jobs),name,n,flush=True)
    rows=[]; chunks=[]
    for p in raw.glob('*.npz'):
        with np.load(p) as f: rows.append(f['roads']); chunks.append(f['chunks'])
    points=np.concatenate(rows); saved_chunks=np.concatenate(chunks)
    # Keep concrete streets even if no black asphalt is nearby (the city
    # cross uses grey concrete). Roofs and interiors are classified later.
    labels=layer_graph(points)
    np.savez_compressed(a.out/'observed.npz',points=points,component=labels,chunks=saved_chunks)
    rows=summarize(points,labels)
    report=dict(source=str(a.source),bounds_y=[-128,319],full_chunks=len(saved_chunks),
                road_material_layers=len(points),components=rows,
                soil_obstructed_layers=int((points[:,5]>0).sum()),
                other_obstructed_layers=int((points[:,6]>0).sum()),
                generation_masks_used_for_discovery=False,blocked_layers_excluded=False,
                small_components_excluded=False,world_written=False,
                note='Material candidates include roofs/interiors. Classification is mandatory before edits; graph tests floor adjacency, not vehicle swept volumes.')
    (a.out/'survey.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('DISCOVERY COMPLETE',len(points),'layers',len(rows),'components',flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=2)
    discover(p.parse_args())
