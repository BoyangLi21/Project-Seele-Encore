"""Read back public-garden circulation, retained geometry and basin containment."""
import argparse,json
from pathlib import Path
import nbtlib
import numpy as np
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from install_r53_carrier_trays import stopped_world
from plan_ashi_landscape_r54 import PLANTS
from query_blocks import AIR
from verify_hakone_togendai_neighbourhood import verify
from prepare_hakone_togendai_neighbourhood import save_json

def check(candidate):
    common=verify(candidate);errors=list(common['errors']);e=Editor(candidate)
    details=json.loads((candidate/'garden-details.json').read_text('utf8'));spec=details['design']
    with np.load(candidate/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);empty=AIR|PLANTS|{'minecraft:light'}
    goals=[]
    for goal in spec['goals']:
        px,py,pz=goal['feet'];valid=bool(d['walk'][pz-z,px-x])and float(d['grade2'][pz-z,px-x])/2+1==py
        if not valid:errors.append(['unreachable garden goal',goal])
        goals.append(dict(**goal,connected_to_public_component=valid and common['full_width_columns']==common['reachable_columns']))
    retained=0
    for j,i in np.argwhere(d['retained_walk']):
        px,pz=int(i+x),int(j+z);floor,_=road_blocks(d['grade2'][j,i]);floor=int(floor)
        if any(e.state(px,Y,pz)!=e.state(px,Y,pz,True)for Y in range(floor-1,floor+4)):errors.append(['retained street section changed',px,pz])
        retained+=1
    for px,py,pz in spec['contacts']:
        if not d['retained_walk'][pz-z,px-x]or d['grade2'][pz-z,px-x]/2+1!=py:errors.append(['garden entrance misses saved street',px,py,pz])
    benches=0
    for px,py,pz in spec['benches']:
        for Q in range(px,px+3):
            if e.state(Q,py,pz)!='minecraft:dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]':errors.append(['missing garden seat',Q,py,pz])
        nearby=[(Q,R)for Q in range(px-1,px+4)for R in (pz-1,pz+1)if d['walk'][R-z,Q-x]and d['grade2'][R-z,Q-x]==(py-1)*2]
        if not nearby:errors.append(['garden seat lacks level access',px,py,pz])
        benches+=1
    water=0;changed_water=0
    for file in (candidate/'source').glob('*.npz'):
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512);wet=np.asarray([s.split('[')[0]=='minecraft:water'for s in r['names']])
        for before,after in zip(r['before'],r['after']):
            mask=wet[before];water+=int(mask.sum());changed_water+=int((mask&(before!=after)).sum())
        e.regions.clear()
    if changed_water:errors.append(['original water changed',changed_water])
    basin=spec['basin'];cx,cz=basin['centre'];Y=basin['water_y'];radius=basin['radius'];pool=0
    for px in range(cx-radius+1,cx+radius):
        for pz in range(cz-radius+1,cz+radius):
            if px==cx and pz==cz:continue
            if e.state(px,Y,pz)!='minecraft:water[level=0]':errors.append(['basin water missing',px,Y,pz])
            if e.state(px,Y-1,pz).split('[')[0]in empty|{'minecraft:water'}:errors.append(['basin bottom open',px,pz])
            for Q,R in ((px-1,pz),(px+1,pz),(px,pz-1),(px,pz+1)):
                if e.state(Q,Y,R).split('[')[0]in empty:errors.append(['basin side open',Q,Y,R])
            pool+=1
    changes=nbtlib.load(candidate/'block-entities.dat')['Changes'];signs=[]
    for row in changes:
        tag=row['After'];pos=tuple(int(tag[k])for k in ('x','y','z'))
        if 'Before'in row or str(tag['id'])!='minecraft:sign'or e.state(*pos).split('[')[0]!='minecraft:oak_wall_sign':errors.append(['unexpected garden device',pos])
        signs.append(list(pos))
    if sorted(signs)!=sorted(r['pos']for r in spec['signs']):errors.append(['garden sign set differs'])
    capture=json.loads((candidate/'capture.json').read_text('utf8'));actor_count=0
    for actor in capture['actors']:
        px,py,pz=map(int,np.floor(actor['pos']))
        for Q in range(max(x,px-2),min(X,px+2)+1):
            for R in range(max(z,pz-2),min(Z,pz+2)+1):
                for Y in range(max(-128,py-2),min(319,py+4)+1):
                    if e.state(Q,Y,R)!=e.state(Q,Y,R,True):errors.append(['actor surroundings changed',actor['pos']])
        actor_count+=1
    W=Path(capture['world']);players=[]
    with stopped_world(W):
        for p in (W/'playerdata').glob('*.dat'):players.append((p.name,nbtlib.load(p)))
        for p in (W/'level.dat',W/'level.dat_old'):
            tag=nbtlib.load(p).get('Data',{}).get('Player')
            if tag is not None:players.append((p.name+'/Player',tag))
    for name,tag in players:
        locations=[]
        if str(tag.get('Dimension',''))=='projectseele:geofront':locations.append(list(map(float,tag.get('Pos',[]))))
        if str(tag.get('SpawnDimension',''))=='projectseele:geofront'and all(k in tag for k in ('SpawnX','SpawnY','SpawnZ')):locations.append([int(tag[k])for k in ('SpawnX','SpawnY','SpawnZ')])
        for pos in locations:
            if len(pos)!=3:continue
            px,py,pz=map(int,np.floor(pos))
            if not(x+2<=px<=X-2 and z+2<=pz<=Z-2):continue
            if any(e.state(Q,Y,R)!=e.state(Q,Y,R,True)for Q in range(px-1,px+2)for R in range(pz-1,pz+2)for Y in range(py-1,py+4)):errors.append(['player position or respawn changed',name])
    report=dict(errors=errors,public_columns=common['full_width_columns'],reachable_columns=common['reachable_columns'],retained_street_columns_exact=retained,goals=goals,usable_bench_groups=benches,closed_basin_water_cells=pool,original_water_cells_unchanged=water,original_device_tags_exact=common['retained_device_tags_unchanged'],original_actor_surroundings_exact=actor_count,player_records_checked=len(players),fresh_sign_tags=len(signs),visual_acceptance=False)
    save_json(candidate/'garden-check.json',report)
    functional=json.loads((candidate/'functional-check.json').read_text('utf8'));functional['errors']=errors;save_json(candidate/'functional-check.json',functional)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True)
    if check(p.parse_args().candidate)['errors']:raise SystemExit(1)
