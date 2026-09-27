"""Recompute headquarters navigation from actual 3D floors, without route masks."""
import json,shutil
from pathlib import Path
import plan_pyramid_navigation_r22 as nav
from measure_world_r40 import WORLD,ROOT
OUT=ROOT/'artifacts/world_combat_r40/wayfinding'

def main():
    nav.WORLD=WORLD;nav.LO=(-90,-574,-310);nav.HI=(340,-310,625)
    nav.PUBLIC_DOMAINS=None;nav.PUBLIC_PATHS=None
    nav.RAIL_CURVES=json.loads((WORLD/'native_transit_r28.json').read_text())['curves']
    nav.LIFT_GROUPS=[dict(id='command_dogma',points=[(12,y,258) for y in (-566,-448,-423,-419,-409)]),
        dict(id='hangar_observation',points=[(93,-442,-47),(93,-394,-57),(93,-370,-57)]),
        dict(id='east_command',points=[(66,y,309) for y in (-461,-448,-434,-420,-406,-392,-378,-364)]),
        dict(id='west_observation',points=[(-29,y,-284) for y in (-394,-367)]),
        dict(id='commander_office',points=[(28,y,314) for y in (-388,-340)])]
    nav.GOALS=[('command','指挥室入口',(28,-406,269)),('hangars','机库登机通道',(90,-394,-255)),
        ('station','总部火车站',(30,-466,451)),('pyramid_station','金字塔接驳站',(30,-466,518)),
        ('launch_station','发射区车站',(150,-442,-28)),('observation','机库观景走廊',(90,-367,-221)),('dogma','终极教条前厅',(30,-566,280))]
    nav.LIFT_BOARD_COST=4.;nav.LIFT_VERTICAL_COST=.12;nav.LIFT_DIRECT=True;nav.STAIR_COST=4.
    nav.main(False,OUT,OUT/'nerv_routes_r24.json.gz')
    with __import__('gzip').open(OUT/'nerv_routes_r24.json.gz','rt',encoding='utf8') as f:data=json.load(f)
    data['source']='R40 exact 3D floors throughout the measured headquarters/connector envelope; no historical path mask. Registered operating doors and native lift connections remain explicit.'
    with __import__('gzip').open(OUT/'nerv_routes_r24.json.gz','wt',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'))
    shutil.copy2(OUT/'nerv_routes_r24.json.gz',WORLD/'nerv_routes_r24.json.gz')
    print('Independent routing nodes',len(data['nodes']))

if __name__=='__main__':main()
