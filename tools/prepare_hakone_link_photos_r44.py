"""Actual measured bridge/tunnel/junction cameras and section anchors; no world writes."""
from pathlib import Path
import math,json
from measure_world_r40 import MeasuredWorld

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/space_photos/hakone_link_v11'

def main():
    assert not OUT.exists(),'Keep the earlier itinerary'
    views=[]
    def add(name,at,target,required,night=False):
        d=[target[i]-at[i] for i in range(3)];d[1]-=1.62
        views.append(dict(file='r44_hakone_link_'+name+'.png',position=at,yaw=math.degrees(math.atan2(-d[0],d[2])),pitch=-math.degrees(math.atan2(d[1],math.hypot(d[0],d[2]))),warmupTicks=360,requiredSections=required,action='daytime:18000' if night else 'daytime:6000'))
    add('valley_whole',[-1010,135,221],[-1000,91,302],[[-1080,102,302],[-1000,99,303],[-904,95,308],[-1010,54,303]])
    add('valley_foundations',[-1010,66,281],[-1000,80,302],[[-994,55,302],[-994,96,302],[-1010,99,303]])
    add('bridge_full_width',[-1080.5,104,300.5],[-980,102,304],[[-1060,102,300],[-1030,101,302],[-1000,100,302]])
    add('bridge_curve_shoulders',[-946.5,106,288.5],[-966,102,306],[[-966,100,297],[-966,100,306],[-966,101,313]])
    add('west_approach',[-1140,108,281],[-1117,103,300],[[-1130,103,295],[-1118,102,300],[-1100,99,303]])
    add('west_tunnel_portal',[-902.5,101,308.5],[-870,104,308],[[-872,106,297],[-872,106,319],[-876,103,308]])
    add('north_walk_and_bypass',[-870.5,98.9375,301.5],[-827,100,301.5],[[-855,98,301],[-855,98,299],[-850,100,303],[-850,106,308]])
    add('south_walk_and_bypass',[-790.5,98.9375,314.5],[-834,100,314.5],[[-824,98,314],[-824,98,316],[-824,100,313],[-824,106,308]])
    add('tunnel_carriage',[-847.5,99,308.5],[-812,100,308.5],[[-832,99,304],[-832,99,312],[-832,106,308]])
    add('east_landing_steps',[-782.5,103,291.5],[-784,99,307],[[-784,98,299],[-784,98,316],[-782,98,302],[-778,97,314]])
    add('tokyo_junction_north',[-760.5,97,286.5],[-760.5,99,323],[[-764,96,301],[-756,96,315],[-760,96,308]])
    add('tokyo_junction_south',[-760.5,97,329.5],[-760.5,99,291],[[-764,96,315],[-756,96,301],[-760,96,308]])
    add('mature_trees_kept',[-780,119,286],[-779,108,309],[[-779,103,300],[-779,103,317],[-783,98,302]])
    add('valley_night',[-1006,115,278],[-1000,103,303],[[-1030,106,308],[-994,106,309],[-980,99,306]],True)
    add('tunnel_night',[-849.5,99,308.5],[-810,101,308],[[-848,106,300],[-812,106,316],[-830,98,301]],True)
    w=MeasuredWorld(WORLD)
    for v in views:w.around([v['position'][0],v['position'][1]+1.62,v['position'][2]],0)
    w.load()
    for v in views:
        eye=[v['position'][0],v['position'][1]+1.62,v['position'][2]]
        assert w.block(eye) in ('minecraft:air','minecraft:cave_air'),(v['file'],eye,w.block(eye))
    OUT.mkdir(parents=True);(OUT/'itinerary.json').write_text(json.dumps(views,indent=2),'utf8')
    (OUT/'scope.json').write_text(json.dumps(dict(views=len(views),all_cameras_measured_non_solid=True,world_written=False,
        requires_before_capture='Root applies exact original junction restoration after v11 and compiles RegionalStationPhoto explicit R44 daytime action. Day/night capture must show real shader world, both city crossing directions, valley foundation and all tunnel lanes.',
        actual_photos_captured=False,client_motion_approved=False),indent=2),'utf8')
    print('Actual non-solid cameras',len(views),OUT/'itinerary.json',flush=True)

if __name__=='__main__':main()
