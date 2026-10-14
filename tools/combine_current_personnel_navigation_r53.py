"""Build typed current routing from named floors, inherited nodes and real lift ports.

Draft artifacts only. Walking, native lift journeys and player train guidance
are separate; this tool never mutates a save or grants a door credential.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import argparse, collections, gzip, hashlib, json, math
import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree
from query_blocks import read_box, iter_selected_sections, AIR


def active_native_escalator_flow(state):
    """MTR4.0.5 onEntityCollision2: true follows FACING, false reverses it.

    This is the horizontal operating force, including orientation=flat moving
    walkways. It does not infer a riser, a new floor, or permission from air.
    Inactive step blocks and ordinary stairs impose no conveyor direction.
    """
    if not state.startswith('mtr:escalator_step['):return None
    props=dict(part.split('=')for part in state.split('[',1)[1].rstrip(']').split(','))
    if props['status']!='true':return None
    facing={'north':(0,-1),'east':(1,0),'south':(0,1),'west':(-1,0)}
    if props['direction']not in('true','false')or props['facing']not in facing:
        raise ValueError(('Unknown actual native conveyor properties',state))
    dx,dz=facing[props['facing']];sign=1 if props['direction']=='true'else-1
    return dx*sign,dz*sign


def native_escalator_allows_edge(from_support,to_support,dx,dz):
    """Subtract actual active counterflow; keep lateral and ordinary edges."""
    for state in (*from_support,*to_support):
        flow=active_native_escalator_flow(state)
        if flow is not None and dx*flow[0]+dz*flow[1]<0:return False
    return True



def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--rail-geometry',type=Path,required=True)
    a=p.parse_args();base=a.base.resolve();world=base/'WORLD';out=a.out.resolve();dest=out/'combined';dest.mkdir(exist_ok=True)
    root=Path(__file__).resolve().parents[1];pyr=root/'.Codex/map_complete_20261013/pyramid_connectivity_sol'
    shapes=json.loads((out/'CURRENT_BOUND_SHAPES.json').read_text('utf8'))
    original=np.load(out/'ORIGINAL_NODE_MIGRATION.npz');inherited=original['current'][original['valid_original_indices']];owners=original['ownership'][original['valid_original_indices']]
    lifts=json.loads((world/'personnel_lifts_r52.json').read_text('utf8'))
    floors={-554,-541,-527,-513,-499,-485,-471,-457,-434,-422,-516,-512,-502,-481,-433,-535}
    stair_points=set()
    def collect(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k=='points'and isinstance(v,list)and all(isinstance(q,list)and len(q)==3 and all(isinstance(c,(float,int))for c in q)for q in v):stair_points.update(map(tuple,v))
                else:collect(v)
        elif isinstance(x,list):
            for v in x:collect(v)
    collect(json.loads((pyr/'BOTH_MAIN_LIFT_EXISTING_STAIR_ACCESS.json').read_text('utf8')))
    collect(json.loads((pyr/'HIGHEST_COMPLETE_TEN_FLOOR_RING_GHOST_PROOF.json').read_text('utf8')))
    for i in range(24):
        for x in range(5,8):stair_points.add((x,-457+i,301+i))
    source_stairs=set(stair_points)
    for x,y,z in source_stairs:
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):stair_points.add((x+dx,y,z+dz))
    groups=[];state_cache={};purposes={};component_reports=[]
    for name in ('hq','lab','hangar'):
        folder=out/'components'/name;data=np.load(folder/'walkable_graph.npz');c=data['coords'].astype(np.int32)
        volume=np.load(folder/'CURRENT.npz');v=volume['states'];pal=list(map(str,volume['palette']));lo=volume['origin']
        def sample(q):
            x,y,z=np.asarray(q)-lo
            return pal[int(v[y,z,x])]
        if name=='hq':keep=np.asarray([int(q[1])in floors or tuple(map(int,q))in stair_points for q in c])
        else:
            ys={-468,-442}if name=='lab'else{-1088,-1014,-987}
            keep=np.asarray([int(q[1])in ys or'stairs'in sample(q-[0,1,0])or'escalator_step'in sample(q-[0,1,0])for q in c])
        selected=c[keep];groups.append(selected)
        for q0 in selected:
            q=tuple(map(int,q0));purposes[q]=name+'/named_active_floor_or_source_stair'
            for dy in(-1,0,1):
                p0=(q[0],q[1]+dy,q[2]);s=sample(p0)
                if p0 in state_cache:assert state_cache[p0]==s,('Component state overlap differs',p0)
                state_cache[p0]=s
        component_reports.append(dict(component=name,raw_graph_nodes=len(c),active_named_floor_nodes=len(selected),removed_roof_technical_or_nonfloor_nodes=int((~keep).sum()),permission_source='Explicit registered floor datums, original 50 room entries, proven old stair routes/new24 treads; no air-based room discovery'))
    # These are existing declared nodes with exact current owner-frame and
    # physical revalidation, including original half-storey landings and the
    # named headquarters-station access stair. New HQ nodes alone receive
    # the narrower registered-plane/stair mask above.
    groups.append(inherited)
    for q in inherited:purposes.setdefault(tuple(map(int,q)),'inherited/original_declared_public_node')
    # The original routing cache has no surface nodes. Only the retained named
    # native pavilion's registered 75m landing is added, never general terrain.
    upper=next(f for l in lifts['lifts']if l['id']=='s20-surface-transit-v2'for f in l['floors']if f['approach_y']==75)
    pavement=read_box(world,'projectseele:geofront',(119,74,268),(125,77,278));surface=[]
    for x in range(119,126):
        for z in range(268,279):
            q=(x,75,z)
            state_cache.update({(x,y,z):pavement[x,y,z]for y in(74,75,76)})
            surface.append(q);purposes[q]='registered_original_public_lift/pavilion75'
    groups.append(np.asarray(surface,np.int32))
    coords=np.unique(np.concatenate(groups),axis=0);lookup={tuple(map(int,q)):i for i,q in enumerate(coords)}
    wanted=collections.defaultdict(set);selected=collections.defaultdict(set)
    for q0 in coords:
        q=tuple(map(int,q0))
        for dy in(-1,0,1):
            p0=(q[0],q[1]+dy,q[2])
            if p0 in state_cache:continue
            key=(p0[0]//16,p0[2]//16,p0[1]//16);wanted[key].add(p0);selected[key[:2]].add(key[2])
    for cx,cz,sy,pal,idx in iter_selected_sections(world,'projectseele:geofront',selected):
        for q in wanted[cx,cz,sy]:state_cache[q]=pal[int(idx[((q[1]&15)<<8)|((q[2]&15)<<4)|(q[0]&15)])]
    operations={};door_requirements=[]
    for door in json.loads((world/'r52/headquarters_command_doors.json').read_text('utf8'))['doors']:
        for q in door['aperture']:operations[tuple(q)]='minecraft:air'
        door_requirements.append(dict(kind='original_command_door',id=door['id'],aperture=door['aperture'],requires_actual_use=True))
    for x,y,z in ((24,-516,254),(28,-541,282),(48,-541,282)):
        for dy in (0,1):
            q=(x,y+dy,z);s=state_cache.get(q)
            if s is not None and 'city_personnel_door[' in s:operations[q]=s.replace('open=false','open=true')
        door_requirements.append(dict(kind='original_native_free_latch',lower=[x,y,z],requires_actual_use=True))
    for gate in json.loads((world/'r44_public_station_gates.json').read_text('utf8'))['gates']:operations[tuple(gate['position'])]=gate['open_state']
    for lift in lifts['lifts']:
        for floor in lift['floors']:
            for role in('landing_doors','cabin_doors'):
                for cell in floor[role]:operations[tuple(cell['pos'])]='minecraft:air'
    for door in lifts['office_access']['room_controls']['pilot_guard_doors']:
        x,y,z=door['lower']
        for dy in(0,1):
            q=(x,y+dy,z);s=state_cache.get(q)
            if s is not None:operations[q]=s.replace('open=false','open=true')
    unknown=collections.Counter();stair=np.zeros(len(coords),bool);safe=np.ones(len(coords),bool);foot=[];head=[];rejected=[]
    def shape(s):
        if s in shapes:return shapes[s]
        if s.split('[')[0]in AIR|{'minecraft:light'}:return []
        if s.startswith('mtr:escalator_step[')and'orientation=flat'in s:return [[0,0,0,1,.9375,1]]
        unknown[s]+=1;return None
    def free(boxes,height):return boxes is not None and not any(b[3]>.205 and b[0]<.795 and b[5]>.205 and b[2]<.795 and b[4]>.01 and b[1]<height for b in boxes)
    for i,q0 in enumerate(coords):
        q=tuple(map(int,q0));actual=[state_cache.get((q[0],q[1]+dy,q[2]),'UNMEASURED')for dy in(-1,0,1)];operated=[operations.get((q[0],q[1]+dy,q[2]),s)for dy,s in zip((-1,0,1),actual)];floor,f,h=map(shape,operated)
        supported=floor is not None and any(.9<=b[4]<=1.001 and b[0]<=.5<=b[3]and b[2]<=.5<=b[5]for b in floor)
        safe[i]=supported and free(f,1)and free(h,.79)and not any(s.startswith(('minecraft:water','minecraft:lava','projectseele:lcl'))for s in actual[1:])
        stair[i]='stairs'in actual[0]or'escalator_step'in actual[0];foot.append(f);head.append(h)
        if not safe[i]:rejected.append(dict(point=list(q),purpose=purposes[q],actual=actual,operated=operated))
    # Keep physical rail gauge separate from personnel floors. This bound comes
    # from actual production RailMath samples, not old static transit metadata.
    rail=json.loads(a.rail_geometry.read_text('utf8'))
    rails=rail if isinstance(rail,list)else rail.get('rails',rail.get('curves',rail.get('rows',[])))
    rail_points=[]
    for r in rails:
        if r.get('mode','TRAIN')!='TRAIN':continue
        points=r.get('points',r.get('samples',[]))
        if isinstance(points,list)and points and isinstance(points[0],list):rail_points.extend(points)
    assert rail_points,'Production rail centre samples missing; inspect native export schema'
    rp=np.asarray(rail_points,float)[:,:3];tree=cKDTree(rp[:,[0,2]]);around=tree.query_ball_point(coords[:,[0,2]],2.2,p=np.inf)
    gauge_removed=0
    for i,ids in enumerate(around):
        if ids:
            dy=coords[i,1]-rp[ids,1]
            if ((dy>=-1)&(dy<=5)).any():safe[i]=False;gauge_removed+=1
    remap=np.full(len(coords),-1,np.int32);remap[safe]=np.arange(int(safe.sum()));oldcoords=coords;coords=coords[safe];lookup={tuple(map(int,q)):i for i,q in enumerate(oldcoords)}
    rows=[];cols=[];weights=[]
    def blocked(boxes,dx,dz,height,low):
        if boxes is None:return True
        axis=0 if dx else 2;tangent=2 if dx else 0;positive=dx+dz>0
        return any(b[tangent]<.795 and b[tangent+3]>.205 and(b[axis+3]>.795 if positive else b[axis]<.205)and b[4]>(.6 if low else .01)and b[1]<height for b in boxes)
    for i,q0 in enumerate(oldcoords):
        if not safe[i]:continue
        x,y,z=map(int,q0)
        for dx,dz in((1,0),(0,1)):
            for dy in(-1,0,1):
                j=lookup.get((x+dx,y+dy,z+dz))
                if j is None or not safe[j]or dy and not(stair[i]or stair[j]):continue
                if any(blocked(bs,sx,sz,h,l)for bs,sx,sz,h,l in((foot[i],dx,dz,1.79,True),(head[i],dx,dz,.79,False),(foot[j],-dx,-dz,1.79,True),(head[j],-dx,-dz,.79,False))):continue
                # Existing node mask and native collision-boundary check above remain
                # exact. Each previously bidirectional edge is now independently
                # checked against its measured active native support force.
                for first,second,sx,sz in((i,j,dx,dz),(j,i,-dx,-dz)):
                    p0=tuple(map(int,oldcoords[first]));p1=tuple(map(int,oldcoords[second]))
                    from_support=[state_cache[(p0[0],p0[1]+h,p0[2])]for h in(-1,0)]
                    to_support=[state_cache[(p1[0],p1[1]+h,p1[2])]for h in(-1,0)]
                    if not native_escalator_allows_edge(from_support,to_support,sx,sz):continue
                    rows.append(int(remap[first]));cols.append(int(remap[second]));weights.append(math.sqrt(2)if dy else 1.)
    n=len(coords);walking=sparse.csr_matrix((weights,(rows,cols)),shape=(n,n));tree=cKDTree(coords);landings=[];issues=[];lift_edges=[]
    def nearest(point,radius=4):
        ids=[i for i in tree.query_ball_point(point,radius)if abs(coords[i,1]-point[1])<.1]
        return None if not ids else min(ids,key=lambda i:float(np.linalg.norm(coords[i]-point)))
    for lift in lifts['lifts']:
        local=[]
        for floor in lift['floors']:
            door=np.asarray([d['pos']for d in floor['landing_doors']],float);point=door.mean(0);point[1]=floor['approach_y'];point+={'north':(0,0,-1),'south':(0,0,1),'west':(-1,0,0),'east':(1,0,0)}[floor['exit']]
            node=nearest(point)
            if node is None:issues.append(dict(kind='missing_named_native_landing',lift=lift['id'],requested=point.tolist()));continue
            local.append(node);landings.append(dict(lift_id=lift['id'],label=floor['label'],node=int(node),requested=point.tolist(),actual=coords[node].tolist(),restricted=floor['restricted']))
        for i in local:
            for j in local:
                if i!=j:lift_edges.append(dict(id=lift['id'],a=int(i),b=int(j),kind='NATIVE_LIFT',cost=24+abs(int(coords[i,1]-coords[j,1]))/.85))
    travel=root/'.Codex/map_complete_20261013/coordinate_lift_audit/final_personnel_68cc/travel_CANDIDATE_NOT_INSTALLED.json'
    arrivals=json.loads(travel.read_text('utf8'))['destinations'];source=json.loads((out/'SOURCE_AUDIT.json').read_text('utf8'));goals=[]
    for g in source['goals']:
        point=g['current']
        if g['id']=='launch_station':point=list(map(math.floor,next(r['position']for r in arrivals if r['key']=='experiment_station')))
        node=nearest(point,6)
        if node is None:issues.append(dict(kind='missing_named_goal',goal=g['id'],point=point));continue
        goals.append(dict(id=g['id'],name=g['name'],node=int(node),requested=point,actual=coords[node].tolist()))
    lr=[r['a']for r in lift_edges];lc=[r['b']for r in lift_edges];lw=[r['cost']for r in lift_edges]
    lift_graph=walking+sparse.csr_matrix((lw,(lr,lc)),shape=(n,n));train_edges=[]
    byid={g['id']:g for g in goals}
    if 'pyramid_station'in byid and'launch_station'in byid:
        transit=json.loads((world/'native_transit_r28.json').read_text('utf8'))
        route=next(r for r in transit['routes']if r['routeNumber']=='U2')
        ids=[int(r['platformId'])for r in route['routePlatformData']]
        assert 8431810501538351356 in ids and -4991105154196472855 in ids
        for first,last,station,target in(('pyramid_station','launch_station','9166787716217601435','6417785485925618840'),('launch_station','pyramid_station','6417785485925618840','9166787716217601435')):
            train_edges.append(dict(kind='TRAIN',**{'from':byid[first]['node'],'to':byid[last]['node']},line='U2',destination='原实验区站'if last=='launch_station'else'NERV 总部站',source_station_id=station,destination_station_id=target,native_route_id=str(route['id']),cost=20.,npc_walking_edge=False))
        # Preserve the other original underground station services. Their
        # original nodes remain in place; only the three Root-owned HQ
        # platforms have the explicit -93 frame. No surface node is inferred.
        stations={int(s['id']):s for s in transit['stations']}
        platforms={int(s['id']):s for s in transit['platforms']};boarding={}
        hq_platforms={8431810501538351356,-7994891824548717036,6885833474752774166}
        for pid,platform in platforms.items():
            p1=np.array([platform['position1'][k]for k in('x','y','z')],float);p2=np.array([platform['position2'][k]for k in('x','y','z')],float);centre=(p1+p2)/2
            if centre[1]>=0:continue
            source_station=next((sid for sid,s in stations.items()if all(min(s['position1'][k],s['position2'][k])<=centre[i]<=max(s['position1'][k],s['position2'][k])for i,k in enumerate(('x','y','z')))),None)
            if source_station is None:continue
            if pid in hq_platforms and centre[1]>-530:centre[1]-=93
            centre[1]+=1;dx,dz=p2[0]-p1[0],p2[2]-p1[2];length=math.hypot(dx,dz)
            if length<1:continue
            normal=np.array([-dz/length,0,dx/length]);candidates=[]
            for side in(-1,1):
                point=centre+normal*(3.5*side);node=nearest(point,10)
                if node is not None:candidates.append((float(np.linalg.norm(coords[node]-point)),node))
            if candidates:boarding[pid]=(min(candidates)[1],source_station)
        known={(r['from'],r['to'])for r in train_edges}
        for route in transit['routes']:
            ids=[int(r['platformId'])for r in route['routePlatformData']]
            for p1,p2 in zip(ids,ids[1:]):
                if p1 not in boarding or p2 not in boarding:continue
                i,s1=boarding[p1];j,s2=boarding[p2]
                if i==j or s1==s2 or(i,j)in known:continue
                known.add((i,j));train_edges.append(dict(kind='TRAIN',**{'from':int(i),'to':int(j)},line=route['routeNumber']or'原地下服务',destination=stations[s2]['name'],source_station_id=str(s1),destination_station_id=str(s2),native_route_id=str(route['id']),source_platform_id=str(p1),destination_platform_id=str(p2),cost=20.,npc_walking_edge=False))
    player=lift_graph+sparse.csr_matrix(([r['cost']for r in train_edges],([r['from']for r in train_edges],[r['to']for r in train_edges])),shape=(n,n))
    dist,parents=dijkstra(player.T.tocsr(),directed=True,indices=[g['node']for g in goals],return_predecessors=True)
    active=np.isfinite(dist).all(axis=0)
    for k,g in enumerate(goals):parents[k,g['node']]=g['node']
    for i in np.flatnonzero(~active):parents[:,i]=i
    assert np.all(parents>=0)
    payload=dict(version=2,dimension='projectseele:geofront',r52_navigation=True,r53_navigation=True,goals=goals,nodes=np.column_stack((coords,parents.T)).tolist(),node_active=active.tolist(),lift_edges=[dict(id=r['id'],a=r['a'],b=r['b'])for r in lift_edges],lift_landings=[coords[r['node']].tolist()for r in landings],named_lift_landings=landings,transport_edges=[{k:v for k,v in r.items()if k!='cost'}for r in train_edges],native_verified=False,permission_policy='Original command, office/SEELE and highest chamber access remain native; graph annotations do not grant credentials. TRAIN is player guidance only; NPC walking is separate.',source='Current explicit named floors and original owned nodes; exact current boundaries and25 original native lift landings; roofs/rail gauge/technical surfaces excluded')
    encoded=gzip.compress(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf8'),mtime=0);(dest/'nerv_routes_r24.json.gz').write_bytes(encoded)
    np.savez_compressed(dest/'CURRENT_GRAPH.npz',coords=coords,walking_indptr=walking.indptr,walking_indices=walking.indices,walking_weights=walking.data,npc_indptr=lift_graph.indptr,npc_indices=lift_graph.indices,npc_weights=lift_graph.data,player_indptr=player.indptr,player_indices=player.indices,player_weights=player.data,active=active)
    report=dict(world_written=False,native_verified=False,nodes=n,active_player_guidance_nodes=int(active.sum()),inactive_not_public_or_unreachable_nodes=int((~active).sum()),original_surface_nodes=0,old_mapped_nodes_before_current_role_filter=int(len(original['current'])),inherited_safe_nodes=len(inherited),component_roles=component_reports,rail_gauge_removed=gauge_removed,unknown_states=dict(unknown),native_lift_landings=len(landings),native_lift_edges=len(lift_edges),player_train_edges=len(train_edges),npc_train_edges=0,issues=issues,rejected_physical_nodes=rejected[:100],named_goals=goals,goal_reachability=np.isfinite(dist[:,[g['node']for g in goals]]).tolist(),rail_input=str(a.rail_geometry.resolve()),rail_sha256=hashlib.sha256(a.rail_geometry.read_bytes()).hexdigest(),actual_transit_metadata_sha256=hashlib.sha256((world/'native_transit_r28.json').read_bytes()).hexdigest(),graph_sha256=hashlib.sha256(encoded).hexdigest(),pending=['Resolve any actual missing named interfaces or remaining current public-floor defects','walking-only nearest-lift table','Root exact derived installation, actual walk/lift/reader/train and final delivered byte readback'])
    (dest/'REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8');print(json.dumps({k:v for k,v in report.items()if k not in('rejected_physical_nodes','pending','component_roles')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
