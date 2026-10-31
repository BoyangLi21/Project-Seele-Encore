"""Distinguish thin overhead decks from vertical piers in the current save."""
import argparse,json
import numpy as np
from scipy.spatial import cKDTree
from collections import defaultdict
from pathlib import Path
from author_hakone_lakefront import Editor
from plan_hakone_main_districts import ROAD_MATERIALS
from plan_ashi_landscape_r54 import NATURAL,SOIL

def run(a):
    e=Editor(a.source);samples=defaultdict(dict)
    tree=cKDTree(np.concatenate([np.asarray(r['points'])for r in json.loads(a.curves.read_text('utf8'))['trains']]))
    for file in a.errors:
        for kind,x,y,z,states in json.loads(file.read_text('utf8'))['errors']:
            if kind!='road-object':continue
            if not any(s.split('[')[0]in {'minecraft:light_gray_concrete','projectseele:nerv_machine_edge','minecraft:iron_bars'}for s in states):continue
            for X in range(x-6,x+7):
                for Z in range(z-6,z+7):samples[X//512,Z//512][X,Z]=y
    ceilings={};obstacles={};pins={};witness=[]
    for region,rows in samples.items():
        for (x,z),y in rows.items():
            try:column=[e.state(x,Y,z).split('[')[0]for Y in range(-128,320)]
            except (KeyError,FileNotFoundError):continue
            pavement=ROAD_MATERIALS|{'minecraft:smooth_stone','minecraft:stone_bricks','minecraft:polished_deepslate','projectseele:nerv_floor_panel','minecraft:blackstone_slab'}
            walking=[Y for Y in range(max(-120,y-2),min(310,y+9))if column[Y+128]in pavement and all(s in {'minecraft:air','minecraft:cave_air','minecraft:light'}for s in column[Y+129:Y+132])]
            if walking:
                floor=min(walking,key=lambda Y:abs(Y-y))
                # Existing ground-level platforms are approaches to preserve,
                # not overhead decks to tunnel beneath.
                below=column[floor+120:floor+128]
                if tree.query([x,floor,z])[0]>8 and sum(s in {'minecraft:light_gray_concrete','minecraft:gray_concrete'}for s in below)>=2 and sum(s in SOIL for s in below)>=2 and not any(s in {'minecraft:air','minecraft:cave_air'}for s in below):
                    pins[x,z]=floor;witness.append(['ground-platform',x,z,floor]);continue
            matches=[Y for Y in range(max(-120,y-3),min(310,y+9))if column[Y+128]=='minecraft:light_gray_concrete']
            if matches:
                at=min(matches,key=lambda Y:abs(Y-y));lo=hi=at
                while lo>-127 and column[lo+127]=='minecraft:light_gray_concrete':lo-=1
                while hi<319 and column[hi+129]=='minecraft:light_gray_concrete':hi+=1
                if hi-lo+1<=6 and lo>y-3:
                    ceilings[x,z]=min(ceilings.get((x,z),320),lo-4)
                    witness.append(['deck',x,z,lo,hi])
                elif hi-lo+1>6:
                    obstacles[x,z]=[x,y,z];witness.append(['pier',x,z,lo,hi])
            if any(s.startswith('projectseele:nerv_machine_')for s in column[max(0,y+128):min(448,y+133)]):obstacles[x,z]=[x,y,z]
        e.regions.clear()
    if pins:
        xy=list(pins);levels=np.asarray(list(pins.values()));near=cKDTree(xy)
        pins={p:int(levels[i])for i,p in enumerate(xy)if np.ptp(levels[near.query_ball_point(p,8)])==0}
    a.out.write_text(json.dumps(dict(ceilings=[[x,y,z]for(x,z),y in ceilings.items()],obstacles=list(obstacles.values()),pins=[[x,y,z]for(x,z),y in pins.items()],witness=witness)),encoding='utf8')
    print('Measured',len(ceilings),'thin deck columns and',len(obstacles),'vertical structural columns',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--errors',type=Path,nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--curves',type=Path,required=True)
    run(p.parse_args())
