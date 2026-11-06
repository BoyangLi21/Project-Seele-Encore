"""Independent bounded step sweeps, fault injection, and two offline cutaways."""
import argparse
import json
import math
from pathlib import Path

from audit_hakone_station_walks import Walker
from map_pipeline.station_sections import StationSections
from render_hakone_voxel_3d import render


def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')


def strict_walk(w,route):
    x,y,z=route[0]
    base=w.follow([route[0],route[0]])
    if base['kind']!='static_clear_provisional':return base
    largest=0.;samples=1
    for a,b in zip(route,route[1:]):
        distance=math.hypot(b[0]-a[0],b[2]-a[2])
        for k in range(1,max(1,math.ceil(distance*8))+1):
            f=k/max(1,math.ceil(distance*8));x=a[0]+(b[0]-a[0])*f;z=a[2]+(b[2]-a[2])*f
            expect=a[1]+(b[1]-a[1])*f
            floors,unknown=w.floors(x,y,z)
            possible=[h for h in floors if abs(h-y)<=.600001 and abs(h-expect)<=1.05 and w.body(x,h,z) is None]
            if not possible:return dict(kind='strict_step_or_body_failure',position=[x,y,z],floor_heights=floors,unknown=unknown[:1])
            new=possible[0];largest=max(largest,abs(new-y));y=new;samples+=1
    if abs(y-route[-1][1])>.01:return dict(kind='wrong_destination_height',actual=y,expected=route[-1][1])
    return dict(kind='strict_static_clear',maximum_observed_step=largest,samples=samples)


class Overlay:
    def __init__(self,source,changes):self.source=source;self.changes=changes
    def state(self,x,y,z):return self.changes.get((x,y,z),self.source.state(x,y,z))


def run(a):
    a.out.mkdir(exist_ok=False)
    report=json.loads((a.review/'review.json').read_text('utf8'))
    shapes=json.loads(Path(report['shape_export']).read_text('utf8'))
    source=Path(report['source']);results=[];negative=[]
    for path in sorted(a.review.glob('native-*.json')):
        row=json.loads(path.read_text('utf8'));w=Walker(source,shapes)
        for goal in row['deck_goals']:
            if goal['status']!='reached':continue
            forward=strict_walk(w,goal['path']);reverse=strict_walk(w,list(reversed(goal['path'])))
            if forward['kind']!=reverse['kind'] or forward['kind']!='strict_static_clear':raise ValueError(str((row['name'],goal['platform_id'],forward,reverse))[:450])
            results.append(dict(station=row['name'],platform=goal['platform_id'],side=goal['side'],fraction=goal['fraction'],forward=forward,reverse=reverse))
        for label,changes,route in (
            ('missing_entry_floor',{(math.floor(row['entry'][0]),int(row['entry'][1])-1,math.floor(row['entry'][2])):'minecraft:air'},[row['entry'],row['entry']]),
            ('glass_in_headroom',{(math.floor(row['entry'][0]),int(row['entry'][1])+1,math.floor(row['entry'][2])):'minecraft:glass'},[row['entry'],row['entry']]),
        ):
            fw=Walker(source,shapes);before=[dict(pos=list(p),state=fw.reader.state(*p)) for p in changes]
            fw.reader=Overlay(fw.reader,changes);proof=strict_walk(fw,route)
            if proof['kind']=='strict_static_clear':raise ValueError('Injected defect was not rejected')
            negative.append(dict(station=row['name'],case=label,original=before,in_memory_changes=[dict(pos=list(p),state=s) for p,s in changes.items()],result=proof,rejected=True))
    reader=StationSections(source)
    views=[render(reader,[-12,-563,470,72,-551,538],a.out/'hq-platform-stair-cut.png','NERV 总部：当前轨面 -560 / 站台与越线楼梯断面'),
           render(reader,[105,-446,-58,193,-433,-22],a.out/'hangar-platform-stair-cut.png','EVA 机库：当前轨面 -443 / 双侧站台与越线楼梯断面')]
    result=dict(paths=results,paths_verified=len(results),directions_verified=2*len(results),negative_cases=negative,
        maximum_observed_step=max(r[d]['maximum_observed_step'] for r in results for d in ('forward','reverse')),
        views=views,source_world_opened=False,world_written=False,
        pending=['current-runtime collision-shape confirmation','12 dynamic ticket barriers','live train boarding and doors','lifts and remote corridors beyond captured station areas'],
        static_station_access_proved=True,whole_stage_two_accepted=False,repair_cells=0)
    write(a.out/'evidence.json',result)
    print('Deep-station evidence:',result['paths_verified'],'paths,',result['directions_verified'],'directions,',len(negative),'negative cases; maximum step',result['maximum_observed_step'])


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('review','out'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
