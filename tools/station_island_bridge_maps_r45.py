"""Two-sided island diagrams attached to the retained complete R23 passenger bridge.

This is a planner only. Complete existing bridge attachment, all native reader
shapes, both display envelopes and original authored track clearance are gates.
"""
from pathlib import Path
import math
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities
from prepare_school_hakone_native_r45 import ActualGeometry
from prepare_b2_stair_component_r45 import full_body_status
from station_sign_readers_r44 import reader_visibility

def island_bridge_map_rows(world, records, diagrams):
    world=Path(world)
    records=[s for s in records if s['line'] in ('R1','S1') and len(s['platform_ids'])==2 and all(int(p) in diagrams.served for p in s['platform_ids'])]
    platforms={int(p['id']):p for p in diagrams.native['platforms']};rows=[];maps=[];held=[]
    for s in records:
        x,y,z=s['center'];h=s['half'];horizontal=s['horizontal'];head=h-8
        def at(u,Y,cross):return (x+u,Y,z+cross)if horizontal else(x+cross,Y,z+u)
        def local(q):return (q[0]-x,q[2]-z)if horizontal else(q[2]-z,q[0]-x)
        w=MeasuredWorld(world);w.box(at(head-6,y-2,-7),at(head+7,y+10,7));w.load();g=ActualGeometry(w)
        tags=dict(iter_block_entities(world,'projectseele:geofront',at(head-6,y-2,-7),at(head+7,y+10,7)))
        axis='z'if horizontal else'x';origin=z if horizontal else x
        offsets={p:(platforms[p]['position1'][axis]+platforms[p]['position2'][axis])/2-origin for p in s['platform_ids']}
        assert sorted(offsets.values())==[-4,4]
        roof=[at(head,y+7,c)for c in(-1,0,1)]
        if not all(w.block(q)in{'minecraft:smooth_stone','projectseele:period_station_floor'}and g.boxes(q)==[[0,0,0,1,1,1]]and q not in tags for q in roof):held.append(dict(station=s['station'],why='Complete original R23 passenger bridge attachment absent'));continue
        frame=[at(head,y+dy,c)for dy in(3,4)for c in(-1,0,1)]+[at(head,y+dy,0)for dy in(5,6)]
        anchors=[at(head-1,y+3,0),at(head+1,y+3,0)]
        span=[at(head+d,y+dy,c)for d in(-1,1)for dy in(3,4)for c in(-1,0,1)]
        if any(q in tags or w.block(q)not in AIR for q in frame+span):held.append(dict(station=s['station'],why='Original fixture or nonair in complete new hanger/display envelope'));continue
        # Explicit R22 cleared rail envelope is offset +/-1, rail datum..+6.
        assert all(not any(abs(local(q)[1]-offset)<=1 and y<=q[1]<=y+6 for offset in offsets.values())for q in frame+span)
        proposed={q:'projectseele:nerv_structural_panel'for q in frame};newmaps=[]
        for number,(direction,q)in enumerate(zip((-1,1),anchors)):
            face=('west'if direction<0 else'east')if horizontal else('north'if direction<0 else'south')
            pid=min(offsets,key=offsets.get)if number==0 else max(offsets,key=offsets.get)
            d=diagrams.diagram(pid,face,s['line']);reader=at(head+direction*4,y+1,0);point=[reader[0]+.5,reader[1],reader[2]+.5]
            state=f'projectseele:station_departure_board[facing={face},wayfinding=true]';proposed[q]=state
            class Image:
                def __init__(self):self.world=world
                def block(self,p):return proposed.get(tuple(p),w.block(p))
                def get(self,X,Y,Z):return self.block(tuple(map(math.floor,(X,Y,Z))))
            image=Image();after=ActualGeometry(image);proof=reader_visibility(image.block,lambda v:[]if v in AIR else after.shapes.get(v),q,face,reader,direction=True,route_map=True)
            start=at(head+direction*5,y+1,0);start=[start[0]+.5,start[1],start[2]+.5]
            if after.standing(point)!='STATIC_STANDING'or after.standing(start)!='STATIC_STANDING'or full_body_status(after,start,point)!='CLEAR'or not proof['clear']:break
            tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Wayfinding':nbtlib.Byte(1),'Station':nbtlib.String(d['station']+' · '+(('北侧'if number==0 else'南侧')if horizontal else('西侧'if number==0 else'东侧'))+'轨道'),'Route':nbtlib.String(s['line']+' '+(('北侧'if number==0 else'南侧')if horizontal else('西侧'if number==0 else'东侧'))+'轨道 / 全线站序'),'NativePlatformId':nbtlib.Long(pid),'TrackSide':nbtlib.String(('north'if number==0 else'south')if horizontal else('west'if number==0 else'east')),'AirService':nbtlib.Byte(0),'MapRows':nbtlib.List[nbtlib.String]([nbtlib.String(t)for t in d['rows']]),'Clock':nbtlib.Long(0),**{'Row'+str(i):nbtlib.String(t)for i,t in enumerate(d['rows'][:3])}})
            newmaps.append(dict(station=s['station'],platform=pid,anchor=q,reader=reader,reader_approach=[start,point],actual_diagram=d,full9ray=proof,load_path=dict(full_attachment=roof,full_frame=frame),after_nbt=tag.snbt()))
        if len(newmaps)!=2:held.append(dict(station=s['station'],why='Both island faces need real clear front/aisle and all9 lettering rays'));continue
        for q,state in proposed.items():
            tag=next((m['after_nbt']for m in newmaps if tuple(m['anchor'])==q),None)
            rows.append(dict(pos=list(q),before=w.block(q),after=state,before_nbt=None,after_nbt=tag,owner='r45/double_R1/island_bridge_suspended_route_maps',reason='Existing active inner APG aisle; complete existing passenger bridge load path; outside original authored three-wide rail clearance'))
        maps.extend(newmaps)
    return rows,maps,held
