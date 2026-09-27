"""Make surveyed reader paving continuous; material changes on existing full ground only."""
from pathlib import Path
import argparse,json,math
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from plan_station_entrances_r42 import NORMAL

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r42';WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW'
OUT=ART/'station_forecourts';FLOOR='projectseele:period_station_floor'


def main(apply=False):
    layout=json.loads((ART/'station_entrances/contract.json').read_text('utf8'))['placements']
    paths=json.loads((ART/'station_reader_paths/contract.json').read_text('utf8'))['reading_approaches']
    w=MeasuredWorld(WORLD)
    for row in layout:w.around(row['start'],22)
    w.load();shapes=json.loads((WORLD/'native_collision_shapes.json').read_text('utf8'))
    full=[[0,0,0,1,1,1]];assert shapes[FLOOR]==full
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();targets=set();details=[]
    for row,path in zip(layout,paths):
        assert row['board']==path['board'];x,y,z=row['board'];y-=2;nx,nz=NORMAL[row['face']];sx,sz=-nz,nx
        pad={(x+sx*u+nx*d,y,z+sz*u+nz*d) for u in range(-2,3) for d in range(-1,5)}
        for a,b in zip(path['walk'],path['walk'][1:]):
            for k in range(math.ceil(math.dist(a,b))*2+1):
                t=k/max(1,math.ceil(math.dist(a,b))*2)
                X,Z=math.floor(a[0]*(1-t)+b[0]*t),math.floor(a[2]*(1-t)+b[2]*t)
                pad.update((X+dx,y,Z+dz) for dx in range(-1,2) for dz in range(-1,2))
        selected=[]
        for q in sorted(pad):
            before=w.block(q)
            if q in targets or not (before or '').startswith('minecraft:grass_block'):continue
            assert shapes[before]==full,('Not a cosmetic full-cube substitution',q,before)
            targets.add(q);selected.append(q);p.match((*q,*q),before,FLOOR,'r42/station/continuous_reader_paving')
        details.append(dict(station=row['station'],board=row['board'],ground_level=y,changed=selected))
    p.meta.update(reason='Native photos exposed fragmented T-shaped reading paving. Finish a five-wide pad and three-wide connection on already solid ground; no new support or height changes.',
                  identical_native_collision=True,locations=details)
    p.save_plan('continuous_paving');print('Existing full-cube material changes',len(targets),flush=True)
    if apply:
        from release_combat_r36 import guard
        guard();p.apply('continuous_paving')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
