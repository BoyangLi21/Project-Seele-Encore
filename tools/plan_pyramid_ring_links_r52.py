"""Root-only proposed missing public ring connections; inspect before writing."""
import json
from collections import Counter,defaultdict
import numpy as np
from r52_spatial_plan import BASE

LINKS={
    -554:[(-30,270),(-30,266),(89,266),(89,270)],
    -541:[(-30,285),(-30,244),(89,244),(89,290)],
    -527:[(-4,273),(-4,261),(76,261),(76,273)],
    -513:[(-4,272),(-4,244),(76,244),(76,272)],
    -485:[(0,274),(0,265),(76,265),(76,274)],
    -457:[(12,310),(5,310),(5,283),(58,283),(58,309)],
}


def main():
    out=BASE/'pyramid_floor_review';d=np.load(out/'CURRENT.npz');a=d['states'];pal=list(map(str,d['palette']));origin=d['origin']
    report=[];allpoints={}
    for y,nodes in LINKS.items():
        points=set()
        for (x,z),(X,Z) in zip(nodes,nodes[1:]):
            assert x==X or z==Z
            for px in range(min(x,X)-1,max(x,X)+2):
                for pz in range(min(z,Z)-1,max(z,Z)+2):points.add((px,pz))
        hits=Counter();first=defaultdict(list);floors=Counter()
        for x,z in sorted(points):
            floors[pal[a[y-1-origin[1],z-origin[2],x-origin[0]]]]+=1
            for Y in range(y,y+3):
                s=pal[a[Y-origin[1],z-origin[2],x-origin[0]]]
                if s in ('minecraft:air','minecraft:cave_air','minecraft:void_air') or s.startswith('minecraft:light['):continue
                hits[s]+=1
                if len(first[s])<12:first[s].append([x,Y,z])
        report.append(dict(y=y,path=nodes,footprint_cells=len(points),floor_states=dict(floors),obstacles=dict(hits),examples=first))
        allpoints[str(y)]=sorted(points)
    (out/'RING_LINK_PREFLIGHT.json').write_text(json.dumps(dict(world_written=False,links=report),indent=2),'utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
