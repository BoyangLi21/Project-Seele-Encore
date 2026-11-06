"""Root's bounded MTR-style tunnel lining from measured native rail curves.

Keeps complete retained stations and their foundations. The rail graph, signal
blocks and vehicle progress migration are separately required before service.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
import regional_voxels as vox
from query_blocks import iter_block_entities
from r52_spatial_plan import BASE

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    folder=BASE/'hq_tunnels';world=BASE/'WORLD_R52'
    report=json.loads((folder/'MEASUREMENT.json').read_text('utf8'))
    samples_path=ROOT/'artifacts/r52_hq_approach_candidate/NATIVE_TUNNEL_SAMPLES.json'
    assert hashlib.sha256(samples_path.read_bytes()).hexdigest()==report['sample_sha256']
    bed=json.loads((folder/'RAIL_BED_OWNERSHIP.json').read_text('utf8'))
    assert bed['all_match_retired_HQ_approach_bed'] and bed['metal_cells']==sum(report['nonnatural_states'].get(s,0)for s in ('projectseele:nerv_structural_panel','minecraft:polished_deepslate'))
    d=np.load(folder/'CORRIDOR_SOURCE.npz');points=d['points'];before=d['before'];palette=list(map(str,d['palette']));bore=d['bore']
    natural={'minecraft:air','minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]',
        'minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:gravel','minecraft:water[level=0]',
        'minecraft:grass','minecraft:fern','projectseele:nerv_structural_panel','minecraft:polished_deepslate'}
    assert all(s in natural or '_leaves['in s or '_log['in s for s in palette if s in {palette[int(i)]for i in np.unique(before)})
    samples=json.loads(samples_path.read_text('utf8'))
    track=np.concatenate([np.asarray(r['points'])for r in samples if not r['id'].startswith('platform_')])
    nearest=cKDTree(track);_,idx=nearest.query(points+.5,workers=1);near=track[idx]
    after=np.full(len(points),'projectseele:nerv_wall_panel',dtype=object)
    floor=(points[:,1]==np.floor(near[:,1])-1)&(np.linalg.norm((points+.5-near)[:,[0,2]],axis=1)<2.3)
    after[floor]='minecraft:gravel';after[bore]='minecraft:air'
    states={tuple(map(int,q)):(palette[int(old)],str(new))for q,old,new in zip(points,before,after)}
    lights=set()
    for row in samples:
        if row['id'].startswith('platform_'):continue
        a=np.asarray(row['points']);step=max(1,round(len(a)*16/max(1,row['native_length'])))
        for v in a[step//2::step]:
            x,y,z=map(int,np.floor(v));q=(x,y+7,z)
            if q in states and states[q][1]=='projectseele:nerv_wall_panel':
                states[q]=(states[q][0],'projectseele:nerv_strip_light[lit=true]');lights.add(q)
    trees=json.loads((folder/'TREE_COMPONENTS.json').read_text('utf8'))['trees'];tree_cells=0
    for tree in trees:
        for row in tree['cells']:
            q=tuple(row['pos'])
            if q in states:assert states[q][0]==row['before']
            else:states[q]=(row['before'],row['after']);tree_cells+=1
    changes={q:v for q,v in states.items()if v[0]!=v[1]}
    selected={(x//16,z//16)for x,y,z in changes};lo=tuple(min(q[i]for q in changes)for i in range(3));hi=tuple(max(q[i]for q in changes)for i in range(3))
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi,selected_chunks=selected))
    assert not changes.keys()&tags.keys(),('Original device in tunnel edits',changes.keys()&tags.keys())
    vox.WORLD=world;vox.OUT=BASE/'hq_tunnel_construction';vox.DIM='projectseele:geofront'
    p=vox.Painter(vertical_bounds=(-960,320))
    protected=json.loads((ROOT/'artifacts/r52_hq_rail_boundary/HQ_PROTECTION_MANIFEST.json').read_text('utf8'))['protected_stations']
    for row in protected:
        t=row['data'];a=t['position1'];b=t['position2']
        if a['y']<0:
            box=(a['x'],min(-490,a['y']),a['z'],b['x'],b['y'],b['z']);p.protect(box,'original_station_'+t['name'])
            assert not any(box[0]<=x<=box[3]and box[1]<=y<=box[4]and box[2]<=z<=box[5]for x,y,z in changes),'Retained station touched'
    # Exact sparse row runs keep every surveyed before-state as a precondition.
    rows=sorted(changes,key=lambda q:(q[1],q[2],q[0]));start=last=None;value=None
    def flush():
        if start is not None:p.exact((*start,*last),value[0],value[1],'R52_measured_HQ_railway_tunnel')
    for q in rows:
        v=changes[q]
        if last is not None and q==(last[0]+1,last[1],last[2])and v==value:last=q
        else:flush();start=last=q;value=v
    flush()
    p.meta.update(root_author=True,native_curve_source_sha256=report['sample_sha256'],
        original_mod_tunnel_cross_section='MTR RailAction horizontal normal; radius3 clear,7 high; radius4 lining',
        protected_original_station_ids=[r['data']['id']for r in protected],
        measured_complete_tree_retirements=[{k:v for k,v in t.items()if k!='cells'}for t in trees],
        rail_database_unchanged=True,playable=False)
    plan=p.save_plan('native_HQ_approach_tunnels')
    result=dict(world_written=False,playable=False,changed_cells=len(changes),operations=len(p.ops),chunks=len(selected),
                retained_station_count=len(protected),native_station_devices_preserved=True,roof_lights=len(lights),
                complete_tree_components=len(trees),additional_tree_cells=tree_cells,
                pending=['native rail database and signal graph migration','original vehicles local-progress preservation','native transit and portal visual checks'])
    (plan/'PLAN.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(result),flush=True)
    if args.apply:
        assert not list(plan.glob('applied_*')),'Applied tunnel stage must not be replayed'
        receipt=p.apply('native_HQ_approach_tunnels')
        assert {q:t.snbt()for q,t in iter_block_entities(world,'projectseele:geofront',lo,hi,selected_chunks=selected)}=={q:t.snbt()for q,t in tags.items()}
        result.update(world_written=True,receipt=receipt)
        (plan/'PLAN.json').write_text(json.dumps(result,indent=2),'utf8')


if __name__=='__main__':main()
