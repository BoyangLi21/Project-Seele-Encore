"""Make every city-building iron entrance operable; keep NERV security doors out of scope."""
from pathlib import Path
import argparse,json
import regional_voxels as v
from measure_world_r40 import MeasuredWorld

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/public_doors'
def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    OUT.mkdir(exist_ok=True);owners=json.loads((ROOT/'artifacts/repair_r43/facility_catalogue/authored_ownership.json').read_text())['buildings']
    w=MeasuredWorld(WORLD)
    for owner in owners:
        a,b=owner['planned_bounds'];w.box(tuple(a),tuple(b))
    w.load();v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();done=set();groups=[]
    for owner in owners:
        lo,hi=owner['planned_bounds'];points=[]
        for x in range(lo[0],hi[0]+1):
            for z in range(lo[2],hi[2]+1):
                for y in range(lo[1],hi[1]+1):
                    q=x,y,z;s=w.block(q)
                    if s is None or not s.startswith('minecraft:iron_door[') or q in done:continue
                    p.match((*q,*q),s,s.replace('minecraft:iron_door[','projectseele:city_personnel_door['),'r44/public_door/'+owner['id']);done.add(q);points.append(q)
        groups.append(dict(building=owner['id'],changed_door_cells=points,entrance=owner['entry']))
    p.meta.update(affected_buildings=[r['building'] for r in groups if r['changed_door_cells']],doors=groups,
                  reason='Correctly paired metal-door halves still had no usable public latch; geometry-only tests assumed the door was already open.',
                  preservation='Exact facing, hinge, half, powered/open state retained; no NERV secure doors included',
                  validation='Native closed-use-open-traverse-close tests and full entrance approach still pending')
    p.save_plan('public_latches')
    if apply:p.apply('public_latches')
    print('Complete public-door set:',len(done),'cells in',len(p.meta['affected_buildings']),'buildings',flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
