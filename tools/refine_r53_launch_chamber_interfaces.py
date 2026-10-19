"""Retire backed-over windows and open the three existing lanes visually.

The rear gate pockets, lower pipe plinths, roof and original tracks stay put.
Every changed cell has an exact old state; no entity or route data is written.
"""
from pathlib import Path
import argparse,collections,gzip,json,msvcrt
import regional_voxels as vox
from query_blocks import read_box,iter_block_entities
from finish_r53_launch_armor import protected_cells

DIM='projectseele:geofront'
LO=(-35,-1029,-7);HI=(93,-951,144)
AIR={'minecraft:air','minecraft:cave_air','minecraft:void_air'}

def plan(world,out):
    c=read_box(world,DIM,LO,HI);tags=dict(iter_block_entities(world,DIM,LO,HI))
    protected=protected_cells(world);rows=[];blind=[]
    retained_posts={(x,z)for x,y,z in set(protected)|set(tags)if x in (5,13,47,55) and -1024<=y<=-957}
    for p,s in c.items():
        x,y,z=p
        if x!=-28 or 'glass' not in s:continue
        backing=[c.get((x-i,y,z),'minecraft:air') for i in (1,2,3)]
        if not all(v not in AIR and 'glass' not in v for v in backing):continue
        assert p not in tags and p not in protected,('Protected blind window',p)
        target=f'projectseele:nerv_launch_armor[column={z%8},row={(y+1030)%16}]'
        blind.append(dict(pos=p,backing=backing))
        rows.append(dict(pos=p,old=s,new=target,reason='existing_glass_backed_by_solid_retired_wall'))
    allowed={'projectseele:nerv_launch_armor','projectseele:nerv_machine_edge','projectseele:nerv_strip_light'}
    # These are the known original internal side partitions, not an air-space
    # based room guess. Gate pockets extend 5.73m behind each rear gate.
    for bank,z0,z1 in ((1,114,140),(2,66,92),(3,18,44)):
        for x in (5,13,47,55):
            for y in range(-1024,-956):
                for z in range(z0,z1+1):
                    if (x,z) in retained_posts:continue
                    p=(x,y,z);s=c[p]
                    if s in AIR:continue
                    assert s.split('[')[0] in allowed,('Unknown divider member',p,s)
                    assert p not in tags and p not in protected,('Protected divider',p)
                    rows.append(dict(pos=p,old=s,new='minecraft:air',reason=f'bank_{bank}_shared_chamber_above_pipe_plinth'))
    out.mkdir(parents=True,exist_ok=True)
    assert not (out/'EXACT_DELTA.json.gz').exists(),'Preserve the frozen baseline'
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    report=dict(cells=len(rows),blind_windows=blind,reasons=dict(collections.Counter(r['reason']for r in rows)),
                route_centres_unchanged=[-11.5,30.5,72.5],gate_pockets_preserved=True,
                lower_pipe_plinth_top=-1025,roof_unchanged=True,world_written=False)
    report['retained_full_height_bearing_posts']=sorted(retained_posts)
    (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print({k:v for k,v in report.items()if k!='blind_windows'})

def install(world,out):
    rows=json.loads(gzip.decompress((out/'EXACT_DELTA.json.gz').read_bytes()))
    with (world/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        c=read_box(world,DIM,LO,HI);tags=dict(iter_block_entities(world,DIM,LO,HI));protected=protected_cells(world)
        for r in rows:
            p=tuple(r['pos']);assert c[p]==r['old'] and p not in tags and p not in protected,(p,c[p])
        vox.WORLD=world;vox.DIM=DIM;vox.OUT=out;painter=vox.Painter(vertical_bounds=(-1440,320))
        for r in rows:painter.exact((*r['pos'],*r['pos']),r['old'],r['new'],r['reason'])
        painter.apply('launch_shared_chamber_finish',session_lock=lock)
        c=read_box(world,DIM,LO,HI);assert all(c[tuple(r['pos'])]==r['new']for r in rows)
    (out/'INSTALLED.json').write_text(json.dumps(dict(exact_readback=True,cells=len(rows))),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('world',type=Path);p.add_argument('output',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
    install(a.world,a.output)if a.apply else plan(a.world,a.output)
