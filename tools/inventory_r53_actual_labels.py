"""Inventory current GeoFront labels and original three-metre room nameplates."""
import argparse,json
from collections import Counter
from pathlib import Path
from query_blocks import iter_block_entities
from measure_world_r40 import MeasuredWorld

def run(world,out):
    dim='projectseele:geofront';rows=[];fixtures=[];m=MeasuredWorld(world,dim)
    for p,t in iter_block_entities(world,dim,(-30000000,-2048,-30000000),(30000000,512,30000000)):
        kind=str(t.get('id',''));text=[]
        if kind=='minecraft:sign':
            text=[str(v) for v in t.get('front_text',{}).get('messages',[])]+[str(t[k]) for k in ('Text1','Text2','Text3','Text4') if k in t]
        elif kind=='projectseele:station_departure_board':
            text=[str(t.get(k,'')) for k in ('Station','Route','Row0','Row1','Row2')]
        elif kind=='projectseele:period_fixture' and ('Title' in t or 'Lines' in t):
            fixtures.append(dict(pos=p,kind=kind,text=[str(t.get('Title',''))]+[str(s) for s in t.get('Lines',[])],nbt=t.snbt()));m.box(p,p);continue
        else:continue
        rows.append(dict(pos=p,kind=kind,text=text,room=bool(t.get('RoomPlaqueR52',False)),wayfinding=bool(t.get('Wayfinding',False)),nbt=t.snbt()))
    m.load();plates=[]
    for r in fixtures:
        r['state']=m.block(r['pos'])
        if 'kind=shop_sign' in r['state']:plates.append(r)
    out.mkdir(parents=True,exist_ok=True)
    (out/'inventory.json').write_text(json.dumps(dict(world=str(world),dimension=dim,rows=rows),ensure_ascii=False,indent=2),'utf8')
    (out/'room_nameplates.json').write_text(json.dumps(plates,ensure_ascii=False,indent=2),'utf8')
    print('Labels',len(rows),'by_type',dict(Counter(r['kind'] for r in rows)),'shop_sign',len(plates))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.world,a.output)
