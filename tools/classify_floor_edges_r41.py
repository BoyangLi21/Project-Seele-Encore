"""Attach purpose and measured approach geometry to globally expanded floor edges.

Classification does not write blocks. Door, lift, stair and shipping interfaces
remain distinct from ordinary perimeter drops; roofs do not inherit floor use.
"""
from pathlib import Path
from collections import Counter,defaultdict
import json
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'
WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW'


def main():
    original=json.loads((ART/'floor_components/connected_floor_edges.json').read_text('utf8'))
    selected={(tuple(r['pos']),tuple(r['normal'])) for r in original}
    rows=[r for r in json.loads((ART/'post_v2/findings.json').read_text('utf8'))['findings']
          if r['kind']=='unguarded_drop' and (tuple(r['pos']),tuple(r['normal'])) in selected]
    places=json.loads((ROOT/'artifacts/world_quality_r02/surface_layout.json').read_text('utf8'))['kept_plots']
    places+=json.loads((ROOT/'artifacts/world_quality_r02/kirisato_apartments/places.json').read_text('utf8'))['landmarks']
    stations=json.loads((ROOT/'artifacts/world_rebuild_r20/transit/civil/viaduct_stations_and_streets/places.json').read_text('utf8'))['stations']
    stations+=json.loads((ROOT/'artifacts/access_r22/transit/civil/station_contract.json').read_text('utf8'))['stations']
    lookup=defaultdict(list)
    for b in places:
        if 'storeys' not in b:continue
        x0,x1,z0,z1=b['bounds']
        for x in range(x0//64,x1//64+1):
            for z in range(z0//64,z1//64+1):lookup[x,z].append(b)
    w=MeasuredWorld(WORLD)
    for r in rows:w.around(r['pos'],3)
    w.load();out=[]
    for row in rows:
        x,y,z=row['pos'];dx,_,dz=row['normal'];q=(x+dx,y,z+dz)
        floor=w.get(x,y-1,z);state=w.get(x,y,z);base=lambda s:(s or '').partition('[')[0]
        descending=[]
        for d in (1,2):
            for low in (1,2,3):
                s=w.get(x+d*dx,y-low,z+d*dz)
                facing=properties(s or '').get('facing');direction={'east':(1,0),'west':(-1,0),'north':(0,-1),'south':(0,1)}.get(facing)
                if s and ('stairs[' in s or 'escalator_step[' in s) and direction==(-dx,-dz):descending.append([x+d*dx,y-low,z+d*dz,s])
        buildings=[b for b in lookup[x//64,z//64] if b['bounds'][0]<=x<=b['bounds'][1] and b['bounds'][2]<=z<=b['bounds'][3]
                   and b['floor']+1<=y<b['floor']+5*b['storeys'] and (y-b['floor']-1)%5==0]
        reason='unresolved_context';purpose=''
        station_pads=[]
        for st in stations:
            cx,_,cz=st['center'];h=st['half'];u,v=(x-cx,z-cz) if st['horizontal'] else (z-cz,x-cx)
            if y==st['ground']+1 and abs(u)<=h+1 and abs(v)<=18:station_pads.append(st['station'])
        gates=any((w.get(x+dx*d,y,z+dz*d) or '').startswith(('mtr:apg_','mtr:psd_')) for d in (0,1,2))
        if gates or base(floor).startswith('mtr:platform') and 'door_type=apg' in floor:
            reason='native_platform_boarding_port'
        elif any('ladder' in (w.get(q[0],y-d,q[2]) or '') for d in (0,1,2)):
            reason='vertical_ladder_port'
        elif 89<=x<=97 and -56<=z<=-48 and -443<=y<=-367:
            reason='compact_lift_swept_volume'
        elif -144<=x<=207 and 41<=z<=392 and y>=80:
            reason='dynamic_city_building_owned_geometry'
        elif descending:
            reason='measured_descending_stair_axis'
        elif buildings:
            reason='authored_building_floor_edge';purpose=buildings[0]['id']
        elif station_pads:
            reason='authored_station_ground_pad';purpose=' / '.join(sorted(set(station_pads)))
        elif 6312<=x<=6325 and -6264<=z<=-6247 and 77<=y<=128:
            reason='un_gantry_stair_floor_edge';purpose='R07 gantry stairs, relocated west in the UN hangar enlargement'
        elif 6472<=x<=6487 and -6264<=z<=-6247 and 77<=y<=128:
            reason='un_gantry_stair_floor_edge';purpose='R07 gantry stairs'
        elif y<0 and base(floor) in {'projectseele:nerv_floor_panel','projectseele:nerv_machine_panel','minecraft:smooth_stone','minecraft:gray_concrete'}:
            reason='underground_facility_floor_edge'
        elif y==81 and ((x in (-194,254) and -4<=z<=444) or (z in (-4,444) and -194<=x<=254)):
            reason='central_city_one_metre_shoulder'
        elif 1224<=x<=1515 and 320<=z<=588 and y in (65,69):
            reason='port_yard_or_quay_edge'
        elif row.get('drop_blocks')==1:
            reason='one_metre_external_grade_change'
        out.append({**row,'floor':floor,'current_state':state,'classification':reason,'purpose':purpose,'descending_stairs':descending})
    path=ART/'floor_components/classification.json';path.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),'utf8')
    counts=Counter(r['classification'] for r in out)
    (path.parent/'classification_counts.json').write_text(json.dumps(counts,indent=2),'utf8');print('Classified',len(out),dict(counts),flush=True)
    for kind in ['unresolved_context','underground_facility_floor_edge']:
        sample=[r for r in out if r['classification']==kind]
        (path.parent/(kind+'.json')).write_text(json.dumps(sample,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':main()
