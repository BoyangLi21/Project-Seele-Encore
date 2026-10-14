"""Small reusable R52 fixed-guide mesh and Root-authored installed instances."""
import json
from pathlib import Path
import build_tv_machinery_r16 as m
from r52_spatial_plan import BASE,HANGAR,BANK_CENTRES_Z


def main():
    root=Path(__file__).resolve().parents[1];assets=root/'src/main/resources/assets/projectseele'
    receipt=json.loads((BASE/'launch_banks/serial_banks_and_tracked_halls/PLAN.json').read_text('utf8'))
    assert receipt['world_written']
    m.use('r52_level_guide_16m')
    for cx in (-42,0,42):
        for z in range(0,16,4):
            for x in range(-15,15,5):m.box(cx+x,-4.96,z,5,.05,4,0x626e66 if (x+z)%2 else 0x67726a)
        for dx in (-6,6):
            # Actual raised source deck is flat at -2.20000005m at both
            # x=+/-6 running strips. The previous -1.44m cap cut .76m into it.
            top=-2.200000047683716;cap_bottom=top-.07
            m.box(cx+dx-.60,cap_bottom,0,1.20,.07,16,m.STEEL)
            m.box(cx+dx-.16,-4.86,0,.32,cap_bottom+4.86,16,m.BLUE)
            m.box(cx+dx-.80,-4.86,0,1.60,.13,16,m.EDGE)
        for dx in (-15,15):m.box(cx+dx-.14,.08,0,.28,.08,16,m.STEEL)
    path=assets/'mesh/tv_guide_r52.json';path.write_text(json.dumps({'part':m.PARTS['r52_level_guide_16m']},separators=(',',':')),'utf8')
    segments=[];z=BANK_CENTRES_Z[-1]
    while z<140.5:
        end=min(z+16,140.5);segments.append({'origin':[30.5,-646,z],'length':end-z});z=end
    spec=dict(schema='projectseele.r52.fixed-guides.v1',required_marker={'pos':[30,-679,301],'block':'projectseele:nerv_machine_hazard'},
        original_incline={'origin':HANGAR.point((30.5,-442.96,-239.5)),'yaw_degrees':180},level_segments=segments,
        only_static_rendering=True,not_a_runtime_route_admission=True)
    path=assets/'facility/r52_fixed_guides.json';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(spec,indent=2),'utf8')
    print('R52 level guide:',len(m.PARTS['r52_level_guide_16m'])//18,'triangles reused by',len(segments),'segments; server map claim required')


if __name__=='__main__':main()
