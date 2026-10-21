"""Replace the disconnected guards on the measured 24-step white stair.

The authored stair is retained, including all three tread lanes. The new
guards occupy the same narrow edge strips and finish the unguarded first step.
"""
import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path
from query_blocks import read_box, iter_block_entities, dimension_dir
from repair_r53_reported_landings import apply, DIM


def rail_gaps(rows):
    """Compare neighboring top-rail endpoints, including their world rise."""
    gaps = []
    for a, b in zip(rows, rows[1:]):
        def ends(row):
            pos, state = row
            if state.startswith('projectseele:tv_personnel_guard_r44['):
                return pos[1]+1.35, pos[1]+1.35
            if state.startswith('projectseele:personnel_stair_guard_r53['):
                return pos[1]+.375, pos[1]+1.375
            raise ValueError('Unclassified guard geometry: '+state)
        if b[0][2] != a[0][2]+1 or b[0][0] != a[0][0]:
            raise ValueError('Nonadjacent guard run')
        gap = abs(ends(a)[1]-ends(b)[0])
        if gap > .05: gaps.append({'a': a[0], 'b': b[0], 'gap': gap})
    return gaps


def plan(frozen, output):
    cells = read_box(frozen, DIM, (4,-460,300), (8,-430,326))
    tags = dict(iter_block_entities(frozen, DIM, (4,-460,300), (8,-430,326)))
    rows = []; before_runs = []; after_runs = []
    tread = 'minecraft:smooth_quartz_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]'
    for x in (5,7):
        previous = []; following = []
        for i in range(24):
            y, z = -458+i, 301+i
            assert all(cells[lane,y,z] == tread for lane in (5,6,7)), 'Authored stair changed'
            p = (x,y+1,z); old = cells[p]
            expected = ('projectseele:tv_personnel_guard_r44[drop=0,east=false,north=false,south=false,west=true]'
                        if x == 5 else 'projectseele:tv_personnel_guard_r44[drop=0,east=true,north=false,south=false,west=false]')
            assert old == ('minecraft:air' if i == 0 else expected) and p not in tags, (p,old)
            new = f'projectseele:personnel_stair_guard_r53[facing=south,left={str(x==7).lower()}]'
            rows.append(dict(pos=p,before=old,after=new,before_nbt=None,after_nbt=None,
                             reason='continuous_guard_on_existing_white_stair'))
            if i: previous.append((p,old))
            following.append((p,new))
        before_runs += rail_gaps(previous); after_runs += rail_gaps(following)
    assert len(before_runs) == 44 and not after_runs, 'Frozen fault must be detected before repair'
    output.mkdir(parents=True,exist_ok=False)
    (output/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    (output/'PLAN.json').write_text(json.dumps(dict(frozen=str(frozen),changed_cells=len(rows),
        existing_flat_rail_gaps=before_runs,proposed_rail_gaps=after_runs,tread_width=3,
        edge_strip_width=.055,world_written=False),indent=2),'utf8')


def install(world, output):
    if (output/'INSTALLED.json').exists(): raise ValueError('Inspect existing installation')
    # A cold region backup and exact inverse cells precede the shared strict
    # state/NBT writer. Actor, transport and navigation files are never copied.
    import msvcrt
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        region=dimension_dir(world,DIM)/'region/r.0.0.mca'
        shutil.copy2(region,output/'region-before.mca')
        protected={p for p in world.iterdir() if p.is_file() and p.name!='session.lock'}
        for folder in ('playerdata','entities','data','dimensions/projectseele/geofront/entities'):
            protected.update(p for p in (world/folder).rglob('*') if p.is_file() and 'DistantHorizons' not in p.name)
        data=world/'dimensions/projectseele/geofront/data'
        protected.update(p for p in data.iterdir() if p.is_file() and 'DistantHorizons' not in p.name)
        import nbtlib
        headers=list(data.glob('projectseele_city_rigid_topology_r45_*.dat'))
        assert len(headers)==1
        cache=data/str(nbtlib.load(headers[0])['data']['GenerationFolder'])/'chunks'
        rows=json.loads(gzip.decompress((output/'EXACT_DELTA.json.gz').read_bytes()))
        wanted={tuple(r['pos']) for r in rows}
        for cx,cz in {(p[0]//16,p[2]//16) for p in wanted}:
            path=cache/f'{cx}_{cz}.dat'
            if not path.exists(): continue
            protected.add(path)
            for entry in nbtlib.load(path)['Static']:
                value=int(entry['Pos']); x=value>>38; y=value&4095; z=(value>>12)&67108863
                if y>=2048:y-=4096
                if z>=33554432:z-=67108864
                assert (x,y,z) not in wanted, 'Resolve the matching maintained-static cell before installing'
        hashes={str(p.relative_to(world)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
        (output/'PROTECTED_BEFORE.json').write_text(json.dumps(hashes,indent=2),'utf8')
    apply(world,output)
    assert hashes=={str(p.relative_to(world)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--frozen',type=Path);p.add_argument('--world',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    install(a.world,a.output) if a.apply else plan(a.frozen,a.output)
