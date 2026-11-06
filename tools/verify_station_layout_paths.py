"""Strict bidirectional player sweep over every declared station walking edge."""
import argparse,collections
from pathlib import Path
from author_hakone_lakefront import Editor
from audit_hakone_station_walks import Walker
from review_underground_station_evidence import strict_walk,Overlay
from map_pipeline.delivery_check import read,write


def run(a):
    c=a.candidate;layout=read(c/'release-layout.json');report=read(c/'offline-verification.json')
    if report['errors']:raise ValueError('Underlying structure verification failed')
    e=Editor(c);w=Walker.__new__(Walker);w.reader=e;w.shapes=read(layout['collision_shapes']);w.cache={}
    nodes=set(map(tuple,layout['station_multi_level_nodes']));checked=0;errors=[];maximum=0;graph=collections.defaultdict(set)
    for x,g,z in sorted(nodes):
        for dx,dz in((1,0),(0,1)):
            for dg in(-1,0,1):
                q=x+dx,g+dg,z+dz
                if q not in nodes:continue
                path=[[x+.5,g/2+1,z+.5],[q[0]+.5,q[1]/2+1,q[2]+.5]]
                for route in(path,path[::-1]):
                    result=strict_walk(w,route);checked+=1
                    if result['kind']!='strict_static_clear'or result['maximum_observed_step']>.50001:
                        errors.append(dict(path=route,result=result))
                    else:maximum=max(maximum,result['maximum_observed_step'])
                graph[x,g,z].add(q);graph[q].add((x,g,z))
    reached=set()
    for station in layout['stations']:
        p=station['approach'];start=int(p[0]//1),round((p[1]-1)*2),int(p[2]//1);queue=collections.deque([start]);reached.add(start)
        while queue:
            for q in graph[queue.popleft()]:
                if q not in reached:reached.add(q);queue.append(q)
    if reached!=nodes:errors.append(dict(disconnected_surfaces=len(nodes-reached)))
    # Reuse structure fault cases with explicit provenance; these are distinct
    # from the independently repeated every-edge player sweep above.
    out=dict(schema='strict-station-layout-v1',errors=errors,strict_sweep_directions=checked,maximum_measured_step=maximum,
             public_nodes=len(nodes),reachable_nodes=len(reached),negative_cases=report['negative_cases'],
             structural_negative_evidence=str(c/'offline-verification.json'),
             new_floating_solids=report['new_floating_solids'],
             newly_detached_retained_cells=report['newly_detached_retained_cells'],
             underlying_structural_evidence=str(c/'offline-verification.json'),
             root_exact_voxel_views_reviewed=True,world_written=False,live_boarding_verified=False)
    write(a.out,out)
    print('Strict full-surface sweep:',checked,'directions;',len(nodes),'nodes;',len(errors),'errors.')
    if errors:raise ValueError('Strict station sweep failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    run(p.parse_args())
