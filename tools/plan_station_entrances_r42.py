"""Surveyed station entrance wayfinding and period fixtures, outside circulation.

Seeds are previously authored ground-entrance paths tied to live MTR platform
IDs. Air alone never creates an entrance or grants a furnishing footprint.
"""
from pathlib import Path
from collections import defaultdict
import argparse,json,math,nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import AIR,iter_block_entities
from build_station_boards_r19 import packed

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW'
OUT=ROOT/'artifacts/rebuild_r42/station_entrances'
NORMAL={'south':(0,1),'north':(0,-1),'east':(1,0),'west':(-1,0)}
FLOORS={'minecraft:smooth_stone','minecraft:polished_andesite','minecraft:quartz_block','minecraft:smooth_quartz',
        'minecraft:stone_bricks','minecraft:polished_deepslate','projectseele:nerv_floor_panel','projectseele:period_station_floor',
        'minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:white_concrete','projectseele:station_tactile_path','projectseele:station_tactile_warning'}


def main(apply=False):
    assert not list(OUT.glob('station_entry_legibility/applied_*/receipt.json')),'This layout was already applied; revise its recorded anchors instead of adding duplicate signs'
    native=json.loads((WORLD/'native_transit_r28.json').read_text('utf8'))
    platforms={p['id']:p for p in native['platforms'] if p['transportMode']=='TRAIN'}
    audit=json.loads((ROOT/'artifacts/world_combat_r40/stations/actual_platforms.json').read_text('utf8'))['platforms']
    titles={p['id']:p['station'] for p in audit};paths=json.loads((WORLD/'quality_walk_cases.json').read_text('utf8'))
    seeds=[];protected=set()
    for row in paths:
        if row['id'].startswith('r23/station/') and '/ground_entrance_' in row['id'] and not row['id'].endswith('/return'):
            pid=int(row['id'].split('/')[2]);route=row['path'];start=route[0]
            if pid not in platforms:continue
            if any(sum((start[i]-s['start'][i])**2 for i in (0,2))<14**2 and start[1]==s['start'][1] for s in seeds):continue
            dx,dz=route[1][0]-start[0],route[1][2]-start[2];forward=(int(math.copysign(1,dx)),0) if abs(dx)>abs(dz) else (0,int(math.copysign(1,dz)))
            seeds.append(dict(id=row['id'],platform=pid,station=titles[pid],start=start,forward=forward,path=route))
        if not row['id'].startswith(('r23/station/','r23/native_escalator/')):continue
        line=row.get('path',[row.get('start'),row.get('end')])
        if any(p is None for p in line):continue
        for a,b in zip(line,line[1:]):
            for t in range(max(1,math.ceil(math.dist(a,b))*2)+1):
                f=t/max(1,math.ceil(math.dist(a,b))*2);q=tuple(math.floor(a[i]*(1-f)+b[i]*f) for i in range(3))
                protected.add(q)
    w=MeasuredWorld(WORLD)
    for s in seeds:w.around(s['start'],13)
    w.load();v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();changes={};placements=[];held=[];walks=[]
    def state(q):return changes.get(q,w.block(q))
    def empty(q):return state(q) in AIR or state(q)=='minecraft:light[level=15,waterlogged=false]'
    def floor(q):return (state(q) or '').partition('[')[0] in FLOORS|{'minecraft:grass_block'}
    def reserve(q,after,reason):
        assert q not in protected,(q,'authored circulation')
        before=w.block(q);assert before is not None,(q,'outside measured space')
        if q in changes:assert changes[q]==after,(q,'conflicting fixture')
        elif before!=after:p.match((*q,*q),before,after,'r42/station/'+reason);changes[q]=after
    for s in seeds:
        x,y,z=map(math.floor,s['start']);fx,fz=s['forward'];side=(-fz,fx)
        face=next(n for n,(a,b) in NORMAL.items() if (a,b)==(-fx,-fz));nx,nz=NORMAL[face]
        selected=None
        for lateral in (4,-4,6,-6,8,-8,10,-10):
            for depth in (2,0,-2,4,-4,6,-6):
                q=(x+side[0]*lateral+fx*depth,y,z+side[1]*lateral+fz*depth)
                frame=[(q[0]+side[0]*u,Y,q[2]+side[1]*u) for u in (-1,0,1) for Y in range(y,y+4)]
                foot=[(q[0]+side[0]*u,y-1,q[2]+side[1]*u) for u in (-1,0,1)]
                front=[(q[0]+nx*d,Y,q[2]+nz*d) for d in (1,2,3) for Y in (y,y+1)]
                if not all(floor(b) for b in foot) or not all(empty(b) and b not in protected for b in frame):continue
                if not all(empty(b) for b in front) or not all(floor((q[0]+nx*d,y-1,q[2]+nz*d)) for d in (1,2,3)):continue
                approach=[q[0]+nx*2.5+.5,y,q[2]+nz*2.5+.5]
                link=[s['start'],[approach[0],y,s['start'][2]],approach]
                support=[]
                for a,b in zip(link,link[1:]):
                    steps=max(1,math.ceil(math.dist(a,b)))
                    for k in range(steps+1):support.append((math.floor(a[0]+(b[0]-a[0])*k/steps),y-1,math.floor(a[2]+(b[2]-a[2])*k/steps)))
                if not all(floor(c) and empty((c[0],y,c[2])) and empty((c[0],y+1,c[2])) for c in support):continue
                if any('mtr:escalator' in (state((q[0]+dx,Y,q[2]+dz)) or '') for dx in range(-2,3) for dz in range(-2,3) for Y in range(y-1,y+3)):continue
                selected=q;break
            if selected:break
        if selected is None:held.append(dict(**s,reason='No surveyed footprint clear of stairs and passenger approaches'));continue
        q=selected;post='minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]'
        # A small waiting/reading recess continues the measured forecourt at
        # its existing elevation; no embankment, road lane or void is filled.
        for cell in set(foot+[(q[0]+nx*d,y-1,q[2]+nz*d) for d in (1,2,3)]+support):
            if (state(cell) or '').startswith('minecraft:grass_block'):reserve(cell,'projectseele:period_station_floor','entrance_reading_recess')
        for u in (-1,1):
            for Y in range(y,y+3):reserve((q[0]+side[0]*u,Y,q[2]+side[1]*u),post,'grounded_sign_posts')
        for u in (-1,0,1):reserve((q[0]+side[0]*u,y+3,q[2]+side[1]*u),f'minecraft:iron_trapdoor[facing={face},half=bottom,open=false,powered=false,waterlogged=false]','thin_steel_sign_header')
        board=(q[0],y+1,q[2]);reserve(board,f'projectseele:station_departure_board[facing={face},wayfinding=true]','entrance_identifier')
        route_names=[]
        for r in native['routes']:
            if r['transportMode']=='TRAIN' and any(t['platformId']==s['platform'] for t in r['routePlatformData']):
                name=r.get('routeNumber','')+' · '+r.get('name','')
                if name not in route_names:route_names.append(name)
        tag=nbtlib.Compound(dict(id=nbtlib.String('projectseele:station_departure_board'),x=nbtlib.Int(board[0]),y=nbtlib.Int(board[1]),z=nbtlib.Int(board[2]),
            Station=nbtlib.String('站前导览'),Route=nbtlib.String(s['station']),Wayfinding=nbtlib.Byte(1),PlatformCentre=nbtlib.Long(packed(tuple(int(platforms[s['platform']]['position1'][key]) for key in ('x','y','z'))))))
        rows=['↑ 双向扶梯 · 站台']+route_names[:1]+['每分钟一班 · 线路图见站台入口']
        for i,text in enumerate(rows):tag['Row'+str(i)]=nbtlib.String(text)
        p.block_entities[board]=tag
        approach=[q[0]+nx*2.5+.5,y,q[2]+nz*2.5+.5]
        walks.append(dict(id=f'r42/station_entrance/{len(placements)}/board_approach',path=[s['start'],[approach[0],y,s['start'][2]],approach]))
        placements.append(dict(**s,board=board,face=face,reader=approach,rows=rows))
    p.meta.update(placements=placements,held=held,walk_nodes=walks,seed_rule='Existing authored station ground entrances tied to actual live platform IDs; no new station inferred from air',
                  sources=['https://tokyu.shibuyaphotomuseum.jp/special/8/','https://www.jreast.co.jp/estation/stations/1039.html'],
                  safety='Full 3x4 sign envelope, three reader cells and both native escalator cells reserved; exact original floor retained')
    p.save_plan('station_entry_legibility');OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')
    print('Surveyed entrances',len(seeds),'candidate signs',len(placements),'held',len(held))
    if apply:
        from release_combat_r36 import guard
        guard();p.apply('station_entry_legibility')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
