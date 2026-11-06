"""Offline old-city station-to-street endpoint evidence; no edits to saved blocks.

Network masks are bounded strictly, never indexed with negative coordinates.
Historical street endpoints remain probes and do not authorize excavation.
"""
import argparse,json,math
from collections import deque
from pathlib import Path
import numpy as np
from audit_mountain_station_access import SupplementedSections
from audit_oldcity_surface_station_access import MainlineSweep,StationNav
from build_gora_protected_transfer import IndependentWalker
from review_underground_station_evidence import strict_walk

def component(nav,goal):
    start=nav.nearest_goal(goal);parents={start:None}if start else{};queue=deque(parents)
    while queue:
        a=queue.popleft()
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            for b in nav.column.get((a[0]+dx,a[2]+dz),[]):
                if b not in parents and nav.edge(a,b):parents[b]=a;queue.append(b)
    return parents

def trace(parents,q):
    path=[]
    if q in parents:
        while q is not None:path.append([q[0]+.5,q[1]/2,q[2]+.5]);q=parents[q]
    return list(reversed(path))

def run(a):
    a.out.mkdir(exist_ok=False)
    reader=SupplementedSections(a.source,a.supplement)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    cases=json.loads((a.metadata/'quality_walk_cases.json').read_text('utf8'))
    native=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'))
    with np.load(a.authority/'network.npz')as f:
        ax,az,aX,aZ=map(int,f['bounds']);road=f['road'];walk=f['walk'];grade=f['grade2']
    summary=[];overrides=json.loads(a.bounds_overrides.read_text('utf8'))if a.bounds_overrides else{}
    for p in sorted(a.review.glob('native-*.json')):
        base=json.loads(p.read_text('utf8'));site=base['site_id']
        if a.sites and site not in a.sites:continue
        box=overrides.get(site,base['bounds']);x,y,z,X,Y,Z=box
        sweep=MainlineSweep(native,model,box);nav=StationNav(reader,box,shapes,sweep)
        root=next(q for q in base['measurements']if q['key']==base['selected_graph_root'])
        goals={'retained_stair_foot':root['goal']};origins={};requests=[]
        # Current walk candidates must be close to the mapped road itself,
        # within captured station bounds, and at a measured support height.
        xx,zz,XX,ZZ=max(x+1,ax),max(z+1,az),min(X-1,aX),min(Z-1,aZ)
        nearroad=[]
        if xx<=XX and zz<=ZZ:
            mask=walk[zz-az:ZZ-az+1,xx-ax:XX-ax+1]
            for dz,dx in np.argwhere(mask):
                px,pz=xx+int(dx),zz+int(dz);gy=float(grade[pz-az,px-ax])/2+1
                if not y+1<=gy<=Y-2:continue
                rl,rr=max(0,px-ax-3),min(road.shape[1],px-ax+4)
                rt,rb=max(0,pz-az-3),min(road.shape[0],pz-az+4)
                if not road[rt:rb,rl:rr].any():continue
                if nav.nearest_goal([px,gy,pz])is None:continue
                score=(px-root['goal'][0])**2+(pz-root['goal'][2])**2+(gy-root['goal'][1])**2
                nearroad.append((score,[px,gy,pz]))
        chosen=set()
        for _,pos in sorted(nearroad):
            area=(pos[0]//8,pos[2]//8)
            if area in chosen:continue
            chosen.add(area);key='current_network_street_'+str(len(chosen));goals[key]=pos
            origins[key]={'kind':'current_network_road_adjacent_walk','authority':str(a.authority)}
            if len(chosen)==16:break
        # Retained old road-footway paths and station ground-entrance cases.
        for case in cases:
            ident=case['id'];path=case.get('path')or[case.get('start'),case.get('end')]
            if any(q is None for q in path)or'/return'in ident:continue
            eligible=('station_road'in ident or'ground_entrance'in ident)
            if not eligible or not any(x<=q[0]<=X+1 and z<=q[2]<=Z+1 for q in path):continue
            for label,q in [('start',path[0]),('end',path[-1])]:
                pos=[math.floor(q[0]),q[1],math.floor(q[2])]
                if not(x+1<=pos[0]<=X-1 and z+1<=pos[2]<=Z-1 and y+1<=pos[1]<=Y-2):
                    requests.append({'id':ident,'label':label,'pos':pos,'kind':'outside_station_capture'})
                    continue
                key='retained_interface_'+str(len(origins));goals[key]=pos
                origins[key]={'kind':'historical_current_support_probe','old_id':ident,'label':label,'old_path':path}
        for q in base['measurements']:
            if q['key'].startswith('entry'):
                goals[q['key']]=q['goal'];origins[q['key']]={'kind':'historical_entry_anchor'}
        if site=='native-21':
            goals['verified_surface_street']=[151,160.5,786]
            origins['verified_surface_street']={'kind':'previously_verified_existing_surface_stair'}
        parents=component(nav,goals['retained_stair_foot'])
        complete_network_nodes=[pos for _,pos in nearroad if nav.nearest_goal(pos)in parents]
        if complete_network_nodes:
            goals['exhaustive_current_network_street']=complete_network_nodes[0]
            origins['exhaustive_current_network_street']={'kind':'current_network_road_adjacent_walk_exhaustive'}
        rows=[]
        for key,pos in goals.items():
            q=nav.nearest_goal(pos);path=trace(parents,q)
            rows.append(dict(name=key,requested=pos,measured_goal=q,reachable=bool(path),path=path))
        count=len(parents);walker=IndependentWalker(reader,shapes,sweep)
        measured=[]
        for row in rows:
            pos=row['requested'];q=dict(key=row['name'],requested=pos,measured_goal=row['measured_goal'],reachable=row['reachable'],origin=origins.get(row['name']))
            q['below']=reader.state(pos[0],math.ceil(pos[1])-1,pos[2]);q['body_at_requested']=walker.body(pos[0]+.5,pos[1],pos[2]+.5)
            if row['reachable']:
                q['path']=row['path'];q['forward']=strict_walk(walker,row['path']);q['reverse']=strict_walk(walker,list(reversed(row['path'])))
                q['strict_pass']=all(q[d]['kind']=='strict_static_clear'for d in('forward','reverse'))
            measured.append(q)
        boundaries=[list(q)for q in parents if q[0]in(x,X)or q[2]in(z,Z)or q[1]/2<y+2 or q[1]/2>Y-3]
        rec=dict(station=base['name'],site=site,bounds=box,graph_root=root['goal'],reachable_nodes=count,measurements=measured,
            exhaustive_road_adjacent_walk_node_count=len(nearroad),exhaustive_reachable_road_adjacent_walk_node_count=len(complete_network_nodes),
            component_boundary_nodes=boundaries,
            unavailable_endpoint_probes=requests,native_sweep=sweep.info(),world_written=False,
            ordinary_wooden_doors_conditionally_open=True,dynamic_native_gates_bypassed=False,
            live_boarding_and_gate_operations_pending=True,
            current_network_covers_site=ax<=x and X<=aX and az<=z and Z<=aZ)
        (a.out/(site+'.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=2),'utf8')
        counts=dict(site=site,station=base['name'],successful_paths=sum(q.get('strict_pass',False)for q in measured),
            network_street_paths=sum(q.get('strict_pass',False)and q['key'].startswith('current_network')for q in measured),
            unavailable_probes=len(requests),all_network_candidates=len(nearroad),reachable_network_candidates=len(complete_network_nodes),component_boundary_count=len(boundaries))
        summary.append(counts);(a.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8')
        print(json.dumps(counts,ensure_ascii=False)[:490],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('source','metadata','native','models','authority','review','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--supplement',type=Path);p.add_argument('--sites',nargs='*');p.add_argument('--bounds-overrides',type=Path);run(p.parse_args())
