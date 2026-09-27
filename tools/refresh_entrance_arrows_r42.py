"""Correct existing entrance legends against the actual approach, without adding signs."""
from pathlib import Path
import argparse,copy,json,nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW';OUT=ROOT/'artifacts/rebuild_r42/station_entrance_arrows'


def main(apply=False):
    contract=ROOT/'artifacts/rebuild_r42/station_entrances/contract.json';layout=json.loads(contract.read_text('utf8'))
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();w=MeasuredWorld(WORLD)
    for row in layout['placements']:w.around(row['board'],1)
    w.load();records=[]
    for row in layout['placements']:
        q=tuple(row['board']);fx,fz=row['forward'];right=(-fz,fx);goal=row['path'][-1];reader=row['reader'];dx=goal[0]-reader[0];dz=goal[2]-reader[2]
        ahead=dx*fx+dz*fz;side=dx*right[0]+dz*right[1]
        arrow=('→' if side>0 else '←') if abs(side)>abs(ahead)*1.15 else ('↑' if ahead>=0 else '↓')
        old=dict(iter_block_entities(WORLD,v.DIM,q,q))[q];new=copy.deepcopy(old);new['Row0']=nbtlib.String(arrow+' 双向扶梯 · 站台')
        if old!=new:p.update_block_entity(q,w.block(q),old,new,'r42/station/actual_entrance_bearing')
        records.append(dict(board=q,station=row['station'],reader=reader,target=goal,arrow=arrow))
    p.meta.update(orientation=records,rule='Arrow is relative to the reader-facing side of the existing panel, derived from the actual authored staircase entrance')
    p.save_plan('actual_entrance_bearings')
    if apply:
        from release_combat_r36 import guard
        guard();p.apply('actual_entrance_bearings')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
