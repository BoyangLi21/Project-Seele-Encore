"""Retire complete unsupported edge posts and the reported sealed side pockets."""
from pathlib import Path
from collections import deque
import argparse,json
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
from prepare_continuous_upright_civil_r52 import cuboids
from query_blocks import iter_block_entities

def detached_posts(world):
    survey.WORLD=world;lo=(-35,-1060,5);hi=(96,-930,165);a,p=survey.measure(lo,hi)
    edge=p.index('projectseele:nerv_machine_edge');pending=set(map(tuple,np.argwhere(a==edge)));parts=[]
    transparent={i for i,s in enumerate(p) if s in ('minecraft:air','minecraft:void_air','minecraft:cave_air','minecraft:barrier')}
    directions=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
    while pending:
        start=pending.pop();queue=[start];component={start};anchored=False
        for q in queue:
            for d in directions:
                n=tuple(q[i]+d[i] for i in range(3))
                if any(n[i]<0 or n[i]>=a.shape[i] for i in range(3)):anchored=True;continue
                if a[n]==edge:
                    if n in pending:pending.remove(n);component.add(n);queue.append(n)
                elif int(a[n]) not in transparent:anchored=True
        if not anchored:parts.append(component)
    return lo,a,p,parts

def main():
    q=argparse.ArgumentParser();q.add_argument('--base',type=Path,required=True);q.add_argument('--world',type=Path,required=True);args=q.parse_args();world=args.world
    lo,a,p,parts=detached_posts(args.base/'WORLD')
    target=(-974-lo[1],108-lo[2],-22-lo[0]);assert any(target in c for c in parts),'Generic detector must find original reported defect'
    lo,a,p,parts=detached_posts(world);after=a.copy()
    for c in parts:
        for at in c:after[at]=p.index('minecraft:air')
    vox.WORLD=world;vox.DIM=survey.DIM;vox.OUT=args.base/'reported-dead-components'/world.name
    painter=vox.Painter(vertical_bounds=(-1440,320));cuboids(painter,lo,a,after,p,'unsupported_complete_edge_components')
    # These are the same retired cross-bank side-pocket ownership boxes as
    # the eastern counterparts. Keep the western personnel gallery X<=-47
    # and the real bank wall/interfaces X>=-29, including all escalators.
    boxes=[]
    for z,Z in ((47,57),(95,105)):
        l=(-46,-979,z);h=(-30,-971,Z);survey.WORLD=world;b,pal=survey.measure(l,h)
        assert not list(iter_block_entities(world,vox.DIM,l,h))
        assert not any(s.startswith('mtr:escalator') or 'elevator' in s for s in pal if s in {pal[int(i)] for i in np.unique(b)})
        if 'minecraft:deepslate[axis=y]' not in pal:pal.append('minecraft:deepslate[axis=y]')
        c=np.full_like(b,pal.index('minecraft:deepslate[axis=y]'))
        cuboids(painter,l,b,c,pal,'retired_sealed_cross_bank_side_pocket');boxes.append((l,h))
    painter.meta.update(unsupported_components=len(parts),unsupported_cells=sum(map(len,parts)),reported_original_detected=True,retained_west_gallery=True)
    painter.apply('reported_posts_and_west_dead_pockets')
    _,_,_,remaining=detached_posts(world);assert not remaining
    for l,h in boxes:
        survey.WORLD=world;b,pal=survey.measure(l,h);assert set(np.asarray(pal)[b].flat)=={'minecraft:deepslate[axis=y]'}
    print(json.dumps(dict(world=str(world),removed_components=len(parts),removed_post_cells=sum(map(len,parts)),closed_dead_pockets=len(boxes),readback=True)))

if __name__=='__main__':main()
