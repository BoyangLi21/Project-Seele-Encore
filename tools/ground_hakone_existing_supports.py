"""Extend confirmed existing bridge/ropeway footings after offline earthworks."""
import argparse,json
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL


def run(a):
    posts=[]
    for p in json.loads((a.gis/'station-corridor-ready/manifest.json').read_text('utf8'))['pylons']:
        x,_,z=map(int,p['foot']);posts.append((x,int(p['node'][1])+1,z,0))
    prior=json.loads((a.gis/'network-integration-20261031/delivery-candidate/structure-completion.json').read_text('utf8'))
    for x,ground,z,deck in prior['rail_piers']:posts.append((x,deck,z,1))
    for x,y,z in json.loads((a.gis.parent/'world_rebuild_r20/transit/civil/viaduct_stations_and_streets/places.json').read_text('utf8'))['piers']:posts.append((x,y,z,1))
    materials={'minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:stone_bricks'};empty=AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:water'}
    e=Editor(a.candidate);changes=[];checked=set()
    def state(x,y,z):
        try:return e.state(x,y,z).split('[')[0]if -128<=y<320 else '__outside__'
        except (KeyError,FileNotFoundError):return '__outside__'
    for x,head,z,radius in sorted(set(posts),key=lambda p:(p[0]//512,p[2]//512)):
        for X in range(x-radius,x+radius+1):
            for Z in range(z-radius,z+radius+1):
                if(X,Z)in checked:continue
                checked.add((X,Z));y=min(319,head)
                while y>head-10 and state(X,y,Z)not in materials:y-=1
                material=state(X,y,Z)
                if material not in materials:continue
                while y>-128 and state(X,y-1,Z)in materials:y-=1
                foot=y;ground=y-1
                while ground>-128 and state(X,ground,Z)in empty:ground-=1
                if ground==foot-1 or state(X,ground,Z)not in SOIL|materials:continue
                for Y in range(ground+1,foot):e.put(X,Y,Z,material)
                changes.append([X,ground,Z,foot])
        if len(e.regions)>2:e.save();e.regions.clear()
    rows=e.save();m=json.loads((a.candidate/'manifest.json').read_text('utf8'));m.update(regions=rows,cells=sum(r['cells']for r in rows));(a.candidate/'manifest.json').write_text(json.dumps(m,indent=2),'utf8')
    (a.candidate/'grounded-supports.json').write_text(json.dumps(dict(checked_columns=len(checked),extended=changes),indent=2),'utf8')
    print('Confirmed footing columns extended',len(changes),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','gis'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
