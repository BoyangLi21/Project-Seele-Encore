"""Native three-dimensional views of defects, repairs and retained interfaces."""
from pathlib import Path
import math,json,argparse

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW';OUT=ROOT/'artifacts/spatial_repair_r41/photos'


def main(expanded=False):
    OUT.mkdir(exist_ok=True);views=[]
    def add(name,at,target,required):
        dx=target[0]-at[0];dy=target[1]-(at[1]+1.62);dz=target[2]-at[2]
        views.append(dict(file='r41_'+name+'.png',position=at,yaw=math.degrees(math.atan2(-dx,dz)),pitch=-math.degrees(math.atan2(dy,math.hypot(dx,dz))),warmupTicks=260,requiredSections=required))
    add('reported_lower_foyer',[94.5,-442,-46.5],[95,-440.5,-42.5],[[89,-443,-48],[97,-441,-43],[112,-442,-49]])
    add('reported_removed_wall',[100.5,-390,-33.5],[105,-391,-42],[[105,-390,-42],[105,-395,-44],[113,-390,-42]])
    add('reported_full_width_exit',[82.5,-394,-269.5],[88,-392.4,-269.5],[[85,-395,-270],[86,-390,-270],[90,-395,-268]])
    add('stairwell_edge',[67.5,-434,364.5],[69,-434.7,361],[[68,-435,363],[69,-434,359],[72,-434,361]])
    add('boarding_bridge_rails',[38.5,-393,-219.5],[30,-392.8,-222],[[30,-395,-220],[34,-395,-224],[49,-395,-220]])
    add('airport_restored_facade',[375.5,73,33.5],[378,76,38],[[374,73,38],[385,78,38],[377,82,40]])
    add('transfer_pier_bearing',[101,-475,-186],[94,-470,-191],[[94,-478,-192],[94,-466,-191],[94,-436,-172]])
    add('observer_external_support',[135,-440,-115],[113,-408,-82],[[114,-437,-82],[114,-400,-82],[112,-388,-82]])
    add('observer_corridor_clear',[108.5,-394,-89.5],[112,-389.5,-82],[[105,-395,-90],[112,-388,-82],[113,-393,-85]])
    add('upper_lounge_edge',[9.5,-389,357.5],[2,-388,364],[[2,-388,364],[10,-390,360],[10,-383,360]])
    add('un_workshop_headers',[6634.5,77,-6352],[6634,83,-6344],[[6634,82,-6344],[6640,76,-6340],[6630,85,-6340]])
    if expanded:
        views[:]=[r for r in views if any(n in r['file'] for n in ('reported_','stairwell_edge','boarding_bridge_rails'))]
        add('dogma_arrival_guard',[28.5,-564,286.5],[30,-566,305],[[23,-567,303],[37,-566,303],[30,-568,296]])
        add('dogma_side_wall_seam',[-31.5,-566,310.5],[-35,-565,321],[[-35,-568,319],[-36,-562,319],[-30,-567,319]])
        add('city_stair_full_width',[-487.5,86,-499.5],[-492,85,-503],[[-492,85,-502],[-494,87,-505],[-489,90,-506]])
        add('estate_roof_stair',[-2778.5,111,-1008.5],[-2787,110,-1008],[[-2788,110,-1009],[-2790,115,-1007],[-2780,110,-1007]])
        add('west_station_forecourt',[-734.5,101,222.5],[-720,97,200],[[-720,96,200],[-730,96,222],[-721,108,200]])
        add('central_station_forecourt',[-188.5,84,-181.5],[-175,81,-172],[[-178,80,-172],[-187,80,-181],[-180,91,-170]])
        add('harbour_quay_guard',[1419.5,65,455.5],[1424,65.5,467],[[1424,64,465],[1424,65,465],[1428,62,466]])
        add('city_grade_shoulder',[258.5,83,145.5],[254,80.5,158],[[254,80,158],[255,80,158],[256,79,158]])
        add('west_street_edge',[-663.5,97,62.5],[-659,94,71],[[-660,94,70],[-658,92,72],[-665,94,69]])
        add('un_guard_tower_edge',[6346,83,-5973],[6345,80,-5979],[[6345,79,-5979],[6348,80,-5978],[6340,74,-5978]])
        add('un_stair_landing',[6319.5,84,-6250.5],[6320,80,-6256],[[6319,81,-6255],[6324,81,-6255],[6317,76,-6250]])
        add('central_station_nonboarding_end',[-191.5,95,-178.5],[-187,94.7,-173],[[-188,94,-170],[-188,95,-172],[-187,94,-176]])
    file=WORLD/'r30_photo_views.json';file.write_text(json.dumps(views,ensure_ascii=False,indent=2),'utf8');(OUT/'itinerary.json').write_bytes(file.read_bytes())
    spec=json.loads((ROOT/'.Codex/client-r40-all-photos.json').read_text('utf8'))
    command=[('-Dprojectseele.regionalBuild=r41-facility-photos' if s.startswith('-Dprojectseele.regionalBuild=') else '-Xmx5G' if s.startswith('-Xmx') else s) for s in spec['command']]
    command[command.index('--quickPlaySingleplayer')+1]=WORLD.name;spec['command']=command
    (ROOT/'.Codex/client-r41-facility-photos.json').write_text(json.dumps(spec),'utf8');print('Prepared',len(views),'native facility views')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expanded',action='store_true');main(p.parse_args().expanded)
