"""All station diagrams follow the live native platform identities and stop order."""
import argparse,copy,json,math
from pathlib import Path
import nbtlib
import regional_voxels as v
from measure_world_r40 import WORLD,ROOT,MeasuredWorld
from query_blocks import iter_block_entities
OUT=ROOT/'artifacts/world_combat_r40/station_maps'

def main(apply=False):
    v.WORLD=WORLD;v.OUT=OUT;OUT.mkdir(parents=True,exist_ok=True);p=v.Painter()
    native=json.loads((WORLD/'native_transit_r28.json').read_text());platforms={q['id']:q for q in native['platforms'] if q['transportMode']=='TRAIN'};routes=[r for r in native['routes'] if r['transportMode']=='TRAIN'];selected=set()
    def centre(q):return [(q['position1'][k]+q['position2'][k])/2 for k in ('x','y','z')]
    def name(pid):
        c=centre(platforms[pid]);candidates=[]
        for s in native['stations']:
            if s['transportMode']=='TRAIN' and all(min(s['position1'][k],s['position2'][k])<=c[i]<=max(s['position1'][k],s['position2'][k]) for i,k in enumerate(('x','y','z'))):
                candidates.append((math.prod(abs(s['position1'][k]-s['position2'][k])+1 for k in ('x','y','z')),s['name']))
        return min(candidates)[1]
    names={pid:name(pid) for pid in platforms}
    for q in platforms.values():
        a,b=q['position1'],q['position2']
        for x in range((min(a['x'],b['x'])-27)//16,(max(a['x'],b['x'])+27)//16+1):
            for z in range((min(a['z'],b['z'])-27)//16,(max(a['z'],b['z'])+27)//16+1):selected.add((x,z))
    tags={q:t for q,t in iter_block_entities(WORLD,v.DIM,(-4000,-480,-6400),(7300,190,1700),selected_chunks=selected) if str(t.get('id',''))=='projectseele:station_departure_board' and 'MapRows' in t}
    w=MeasuredWorld()
    for q in tags:w.around(q,0)
    w.load();updated=[];held=[]
    for q,before in tags.items():
        pid=int(before.get('NativePlatformId',-1))
        if pid not in platforms:
            nearby=[(sum((centre(a)[i]-q[i])**2*(3 if i==1 else 1) for i in range(3)),i) for i,a in platforms.items() if names[i] in str(before.get('Station',''))]
            if not nearby:held.append(dict(position=q,reason='No unambiguous live station identity'));continue
            distance,pid=min(nearby)
            if distance>20000:held.append(dict(position=q,reason='Retired station location'));continue
        options=[r for r in routes if any(a['platformId']==pid for a in r['routePlatformData'])]
        if not options:held.append(dict(position=q,reason='No served route'));continue
        route=next((r for r in options if r['routeNumber'] in str(before.get('Route',''))),options[0]);seq=[a['platformId'] for a in route['routePlatformData']];i=seq.index(pid);here=names[pid];nxt=names[seq[i+1 if i+1<len(seq) else 1]]
        order=list(dict.fromkeys(names[a] for a in seq))
        if order.index(nxt)<order.index(here):order.reverse()
        lines=[('● '+n+'  本站') if n==here else '│ '+n for n in order]
        lines+=['下一站  '+nxt,'每分钟一班 · 北京时间']
        interchange=sorted({r['routeNumber'] for r in routes if any(names[a['platformId']]==here for a in r['routePlatformData'])}-{route['routeNumber']})
        if interchange:lines.append('换乘  '+' / '.join(interchange))
        after=copy.deepcopy(before);after['NativePlatformId']=nbtlib.Long(pid);after['Station']=nbtlib.String(here);after['Route']=nbtlib.String(route['routeNumber']+' 全线站序');after['MapRows']=nbtlib.List[nbtlib.String]([nbtlib.String(s) for s in lines])
        for k,s in enumerate(lines[:3]):after['Row'+str(k)]=nbtlib.String(s)
        p.update_block_entity(q,w.block(q),before,after,'r40/actual_station_order')
        updated.append(dict(position=q,platform=pid,station=here,line=route['routeNumber'],next=nxt,rows=lines))
    p.meta.update(updated=updated,held=held,native_platforms=len(platforms),physical_left_right_arrows_not_inferred_from_city_positions=True)
    p.save_plan('native_station_sequences')
    if apply:p.apply('native_station_sequences')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Station maps updated',len(updated),'held',len(held))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
