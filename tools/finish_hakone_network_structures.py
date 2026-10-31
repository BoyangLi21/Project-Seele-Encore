"""Finish moved entrances and support complete, currently active transport."""
import argparse,json,math
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled
from plan_ashi_landscape_r54 import SOIL,NATURAL
from query_blocks import AIR

def run(a):
    e=Editor(a.candidate);d=load_grid(a.plan/'network.npz');curves=json.loads((a.plan/'native-curves.json').read_text('utf8'))['trains']
    catalog=json.loads((a.plan/'catalog.json').read_text('utf8'));boxes=[r['occupied_bounds']for r in catalog]+json.loads((a.plan/'station-volumes.json').read_text('utf8'))
    boxes += [[-110,25,-155,225,180,15],[-425,20,690,-285,180,830]]
    empty=AIR|{'minecraft:water','minecraft:grass','minecraft:tall_grass','minecraft:light'}
    materials={'minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:stone_bricks'}
    points=np.concatenate([np.asarray(r['points'])for r in curves]);tree=cKDTree(points)
    changed=set();report=dict(retired_piers=[],grounded_pylons=[],rail_piers=[],cleared_old_approach_cells=0,tunnel_portal_columns=[])
    def state(x,y,z):
        if not -128<=y<320:return '__missing__'
        try:return e.state(int(x),int(y),int(z)).split('[')[0]
        except (FileNotFoundError,KeyError):return '__missing__'
    def put(x,y,z,s):e.put(int(x),int(y),int(z),s);changed.add((int(x)//16,int(z)//16))
    def protected(x,y,z):return any(b[0]-2<=x<=b[3]+2 and b[2]-2<=z<=b[5]+2 and b[1]-1<=y<=b[4]+8 for b in boxes)
    def walk(x,z):return bool(sampled(d,'walk',np.asarray(x),np.asarray(z)))
    def flush():e.save();e.regions.clear()
    tunnel_file=a.candidate.parent/'existing-tunnels.json'
    if tunnel_file.exists():
        t=json.loads(tunnel_file.read_text('utf8'));known=np.array(t['points']);nearest=cKDTree(known[:,[0,2]])
        for x,_,z in t['missing']:
            dist,at=nearest.query([x,z],k=4);floor=int(round(np.median(known[at,1])))
            body=[state(x,Y,z)for Y in range(floor,floor+3)]
            # Only geological infill in an already authored road tunnel is
            # removed. Masonry portal sides and other equipment are retained.
            if all(s in NATURAL for s in body):
                put(x,floor,z,'minecraft:smooth_stone')
                for Y in (floor+1,floor+2):put(x,Y,z,'minecraft:air')
                report['tunnel_portal_columns'].append([x,floor,z])
        flush()
    old=json.loads((a.gis/'street-refinement-20261031/candidate-v1/catalog.json').read_text('utf8'))
    moves={r['id']:r for r in json.loads((a.plan/'building-moves.json').read_text('utf8'))}
    for row in old:
        if row['id']not in moves:continue
        for x,y,z in row.get('footway',[]):
            for X in range(x-2,x+3):
                for Z in range(z-2,z+3):
                    target=int(sampled(d,'grade2',np.asarray(X),np.asarray(Z))+1)//2
                    for Y in range(y-2,y+3):
                        if Y<=target or protected(X,Y,Z):continue
                        if state(X,Y,Z)in {'minecraft:smooth_stone','minecraft:stone_bricks','minecraft:stone_brick_stairs','minecraft:stone_brick_wall','minecraft:polished_andesite'}:
                            put(X,Y,Z,'minecraft:air');report['cleared_old_approach_cells']+=1
        flush()
    oldpiers=json.loads((a.gis.parent/'world_rebuild_r20/transit/civil/viaduct_stations_and_streets/places.json').read_text('utf8'))['piers']
    for number,(x,y,z)in enumerate(oldpiers):
        dist,nearest=tree.query([x,y,z])
        if dist<9:continue
        removed=0
        for X in range(x-1,x+2):
            for Z in range(z-1,z+2):
                for Y in range(max(32,y-125),min(319,y+3)+1):
                    road_floor=(int(sampled(d,'grade2',np.asarray(X),np.asarray(Z)))+1)//2
                    if not protected(X,Y,Z)and not(walk(X,Z)and Y==road_floor)and state(X,Y,Z)=='minecraft:light_gray_concrete':
                        put(X,Y,Z,'minecraft:air');removed+=1
        if removed:report['retired_piers'].append([x,y,z,removed])
        if len(e.regions)>3:flush()
    flush()
    poles=json.loads((a.gis/'station-corridor-ready/manifest.json').read_text('utf8'))['pylons']
    for p in poles:
        x,_,z=map(int,p['foot']);head=int(p['node'][1]);start=head
        while start>=head-9 and state(x,start,z)not in materials:start-=1
        if state(x,start,z)not in materials:continue
        foot=start
        while foot>-127 and state(x,foot-1,z)in materials:foot-=1
        ground=foot-1
        while ground>-127 and state(x,ground,z)in empty:ground-=1
        if ground<foot-1 and state(x,ground,z)in SOIL|materials:
            for Y in range(ground+1,foot):put(x,Y,z,'minecraft:gray_concrete')
            report['grounded_pylons'].append([x,ground,z,foot])
        if len(e.regions)>3:flush()
    flush()
    # Rebuild load-bearing piers along the actual native curves. A removed old
    # pier is not a reason to leave its still-operational rail bed hovering.
    selected=[];seen=set()
    for r in curves:
        travelled=0.;last=None;interval=0.
        for point in r['points']:
            if last is not None:travelled+=math.dist(point,last)
            last=point
            if travelled<interval:continue
            interval=travelled+40
            x,y,z=map(math.floor,point)
            if y<-120 or y>=300 or (y<32 and 'FFFFFFFF'in str(r['id']))or any(abs(x-X)<15 and abs(z-Z)<15 for X,Z in seen):continue
            if any(walk(X,Z)for X in range(x-3,x+4)for Z in range(z-3,z+4)):continue
            if any(protected(x,Y,z)for Y in range(max(-128,y-60),y)):continue
            seen.add((x,z));selected.append([x,y,z])
    for x,y,z in sorted(selected,key=lambda p:(p[0]//512,p[2]//512)):
        deck=y-1
        if state(x,deck,z)not in materials:continue
        # Native beds can be several blocks thick. Start below that bed,
        # rather than mistaking its second layer for solid ground.
        while deck>y-8 and state(x,deck-1,z)in materials:deck-=1
        ground=deck-1
        while ground>-127 and state(x,ground,z)in empty:ground-=1
        if deck-ground<7 or state(x,ground,z)not in SOIL|materials:continue
        ops=[];valid=True
        for X in range(x-1,x+2):
            for Z in range(z-1,z+2):
                G=deck-1
                while G>-127 and state(X,G,Z)in empty:G-=1
                if state(X,G,Z)not in SOIL|materials:valid=False;break
                for Y in range(G+1,deck):
                    if protected(X,Y,Z):valid=False;break
                    ops.append((X,Y,Z))
        if valid:
            for p in ops:put(*p,'minecraft:light_gray_concrete')
            report['rail_piers'].append([x,ground,z,deck])
        if len(e.regions)>3:flush()
    regions=e.save();m=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    m.update(regions=regions,cells=sum(r['cells']for r in regions),structural_completion=report)
    (a.candidate/'manifest.json').write_text(json.dumps(m,indent=2),'utf8')
    path=a.candidate/'transport-changed-chunks.json';changed|=set(map(tuple,json.loads(path.read_text('utf8'))));path.write_text(json.dumps(sorted(changed)),'utf8')
    (a.candidate/'structure-completion.json').write_text(json.dumps(report,indent=2),'utf8')
    print({k:len(v)if isinstance(v,list)else v for k,v in report.items()},flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','plan','gis'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
