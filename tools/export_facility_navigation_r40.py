"""Recompute headquarters navigation from actual 3D floors, without route masks."""
import argparse,json,shutil
from pathlib import Path
import plan_pyramid_navigation_r22 as nav
from measure_world_r40 import WORLD,ROOT
OUT=ROOT/'artifacts/world_combat_r40/wayfinding'

def main(world=WORLD,out=OUT,interfaces=None):
    nav.WORLD=world;nav.LO=(-90,-574,-310);nav.HI=(340,-310,625)
    nav.PUBLIC_DOMAINS=None;nav.PUBLIC_PATHS=None
    nav.RAIL_CURVES=json.loads((world/'native_transit_r28.json').read_text('utf8'))['curves']
    nav.LIFT_GROUPS=[dict(id='command_dogma',points=[(12,y,258) for y in (-566,-448,-423,-419,-409)]),
        dict(id='hangar_observation',points=[(93,-442,-47),(93,-394,-57),(93,-370,-57)]),
        dict(id='east_command',points=[(66,y,309) for y in (-461,-448,-434,-420,-406,-392,-378,-364)]),
        dict(id='west_observation',points=[(-29,y,-284) for y in (-394,-367)]),
        dict(id='commander_office',points=[(28,y,314) for y in (-388,-340)])]
    if interfaces is not None:
        from collections import defaultdict
        import math
        resolved=json.loads(interfaces.read_text('utf8'))['resolved_interfaces'];groups=defaultdict(list)
        for row in resolved:
            point=tuple(math.floor(v) for v in row['approach'])
            if all(nav.LO[i]<=point[i]<=nav.HI[i] for i in range(3)):groups[row['lift']].append(point)
        nav.LIFT_GROUPS=[dict(id=k,points=p) for k,p in groups.items() if len(p)>1]
        assert len(nav.LIFT_GROUPS)==5,'Expected five multi-stop lifts inside the HQ navigation envelope'
    nav.GOALS=[('command','指挥室入口',(28,-406,269)),('hangars','机库登机通道',(90,-394,-255)),
        ('station','总部火车站',(30,-466,451)),('pyramid_station','金字塔接驳站',(30,-466,518)),
        ('launch_station','发射区车站',(150,-442,-28)),('observation','机库观景走廊',(90,-367,-221)),('dogma','终极教条前厅',(30,-566,280))]
    nav.LIFT_BOARD_COST=4.;nav.LIFT_VERTICAL_COST=.12;nav.LIFT_DIRECT=True;nav.STAIR_COST=4.
    nav.main(False,out,out/'nerv_routes_r24.json.gz')
    with __import__('gzip').open(out/'nerv_routes_r24.json.gz','rt',encoding='utf8') as f:data=json.load(f)
    data['source']='Exact HQ/connector floor graph; current native lift approach ports' if interfaces else 'R40 exact 3D floors throughout the measured headquarters/connector envelope; no historical path mask. Registered operating doors and native lift connections remain explicit.'
    if interfaces:data['native_lift_interface_source']=str(interfaces)
    with __import__('gzip').open(out/'nerv_routes_r24.json.gz','wt',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'))
    shutil.copy2(out/'nerv_routes_r24.json.gz',world/'nerv_routes_r24.json.gz')
    print('Independent routing nodes',len(data['nodes']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,default=WORLD);p.add_argument('--out',type=Path,default=OUT);p.add_argument('--interfaces',type=Path);args=p.parse_args();main(args.world,args.out,args.interfaces)
