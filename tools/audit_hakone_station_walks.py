"""Triage retained station walks against current sections and recorded shapes.

The shape export predates this survey: successful static checks remain provisional
until current native runtime validation. Failed historical paths never authorize
excavation; station membership and the current intended entrance need review.
"""
import argparse,json,math
from collections import Counter
from pathlib import Path
import numpy as np
from query_blocks import AIR
from map_pipeline.station_sections import StationSections


class Walker:
    def __init__(self,source,shapes):
        self.reader=StationSections(source);self.shapes=shapes;self.cache={}
    def boxes(self,x,y,z):
        p=x,y,z
        if p in self.cache:return self.cache[p]
        state=self.reader.state(*p)
        if state is None:return None,None
        if state.split('[')[0]in AIR|{'minecraft:light'}:boxes=[]
        else:boxes=self.shapes.get(state)
        self.cache[p]=(state,boxes)
        return state,boxes
    def body(self,x,y,z):
        lo=(x-.3,y+.0001,z-.3);hi=(x+.3,y+1.7999,z+.3)
        for X in range(math.floor(lo[0]),math.floor(hi[0]-.00001)+1):
            for Y in range(math.floor(lo[1]),math.floor(hi[1]) +1):
                for Z in range(math.floor(lo[2]),math.floor(hi[2]-.00001)+1):
                    state,boxes=self.boxes(X,Y,Z)
                    if boxes is None:return dict(kind='unknown',pos=[X,Y,Z],state=state)
                    for b in boxes:
                        if all(lo[i]<[X,Y,Z][i]+b[i+3]and hi[i]>[X,Y,Z][i]+b[i]for i in range(3)):
                            return dict(kind='body_obstruction',pos=[X,Y,Z],state=state)
        return None
    def floors(self,x,y,z):
        result=[];unknown=[]
        for X in range(math.floor(x-.2999),math.floor(x+.2999)+1):
            for Z in range(math.floor(z-.2999),math.floor(z+.2999)+1):
                for Y in range(math.floor(y-1.05)-1,math.floor(y+.601)+1):
                    state,boxes=self.boxes(X,Y,Z)
                    if boxes is None:unknown.append(dict(kind='unknown',pos=[X,Y,Z],state=state));continue
                    for b in boxes:
                        top=Y+b[4]
                        if x-.2999<X+b[3]and x+.2999>X+b[0]and z-.2999<Z+b[5]and z+.2999>Z+b[2]and y-1.05<=top<=y+.6001:
                            result.append(top)
        return sorted(set(result),reverse=True),unknown
    def follow(self,route):
        x,y,z=map(float,route[0]);floors,unknown=self.floors(x,y,z)
        if not any(abs(v-y)<.01 for v in floors):return dict(kind='start_without_measured_bearing',pos=[x,y,z],nearby=floors,unknown=unknown[:1])
        issue=self.body(x,y,z)
        if issue:return issue
        distance=0;samples=1
        for a,b in zip(route,route[1:]):
            horizontal=math.hypot(b[0]-a[0],b[2]-a[2])
            if horizontal<.001 and abs(b[1]-a[1])>.6:return dict(kind='vertical_transport_or_missing_path',pos=b)
            steps=max(1,math.ceil(horizontal*8))
            for k in range(1,steps+1):
                f=k/steps;x=a[0]+(b[0]-a[0])*f;z=a[2]+(b[2]-a[2])*f
                expected=a[1]+(b[1]-a[1])*f;floors,unknown=self.floors(x,y,z)
                permitted=[v for v in floors if abs(v-expected)<=1.05]
                issues=[];next_y=None
                for top in permitted:
                    issue=self.body(x,top,z)
                    if issue:issues.append(issue)
                    else:next_y=top;break
                if next_y is None:return dict(kind='path_has_no_clear_supported_step',pos=[x,y,z],expected_y=expected,
                    floor_heights=floors,issues=issues[:2],unknown=unknown[:1])
                y=next_y;samples+=1
            distance+=horizontal
        if abs(y-route[-1][1])>.01:return dict(kind='destination_height_mismatch',pos=[x,y,z],expected=route[-1])
        return dict(kind='static_clear_provisional',samples=samples,distance=distance)


def audit(a):
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    cases=json.loads((a.metadata/'quality_walk_cases.json').read_text('utf8'))
    walker=Walker(a.source,shapes);results=[]
    for case in cases:
        if 'station'not in case.get('id',''):continue
        route=case.get('path')or[case.get('start'),case.get('end')]
        if any(p is None for p in route):raise ValueError('Missing retained walk points')
        proof=walker.follow(route)
        results.append(dict(id=case['id'],source_path=route,result=proof,
            intended_current_station_path_verified=False,repair_authorized=False))
    a.out.mkdir(exist_ok=False)
    report=dict(cases=results,counts=dict(Counter(r['result']['kind']for r in results)),
        source=str(a.source),historical_shape_export=str(a.metadata/'native_collision_shapes.json'),
        current_runtime_validation_pending=True,static_success_is_not_whole_station_acceptance=True,world_written=False)
    (a.out/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Retained station walks:',len(results),report['counts'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','metadata','out'):p.add_argument('--'+n,type=Path,required=True)
    audit(p.parse_args())
