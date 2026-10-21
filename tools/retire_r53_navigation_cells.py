"""Remove declared walking nodes occupied by a precise installed map delta."""
import argparse,gzip,hashlib,json,math,msvcrt
from pathlib import Path
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from refresh_r53_repaired_navigation import dijkstra,encode,unpack
from apply_s20_approved_semantic_repairs import atomic_replace

FILES=('nerv_routes_r24.json.gz','nearest_lift_paths_r44.json.gz','r53_personnel_walking_graph.json.gz')

def plan(world,delta,out,connections=None,blocked_connections=None,excluded_nodes=None):
    original={name:(world/name).read_bytes() for name in FILES}
    graph,nearest,npc=[json.loads(gzip.decompress(original[n])) for n in FILES]
    assert nearest['graph_sha256']==hashlib.sha256(original[FILES[0]]).hexdigest()
    points=[tuple(p) for p in npc['nodes']];active=graph['node_active'][:]
    assert points==[tuple(r[:3]) for r in graph['nodes']]
    edits=json.loads(gzip.decompress(delta.read_bytes()));changed={tuple(r['pos']) for r in edits if r['before']!=r['after']}
    affected=[i for i,(x,y,z) in enumerate(points) if any((x,y+dy,z) in changed for dy in (-1,0,1))]
    world_read=MeasuredWorld(world)
    for i in affected:world_read.around(points[i],2)
    world_read.load();geometry=Geometry(world_read);retired=[]
    for i in affected:
        observation=geometry.standing(points[i]);assert observation['status']!='UNKNOWN',observation
        if observation['status']!='STATIC_STANDING':active[i]=False;retired.append(dict(node=i,position=points[i],observation=observation))
    exclusions=[]
    if excluded_nodes:
        contract=json.loads(excluded_nodes.read_text('utf8'))
        assert contract['purpose']=='HQ station perimeter glass is enclosure, not pedestrian floor'
        assert contract['source']=='tools/build_transit_civil_r20.py:station/perimeter_wall'
        lookup={p:i for i,p in enumerate(points)}
        for row in contract['nodes']:
            p=tuple(row['position']);i=lookup[p]
            assert row['node']==i and active[i]
            assert 39<=p[0]<=53 and p[1]==-556 and p[2] in (475,505,507,537)
            world_read.around(p,2)
        world_read.load()
        for row in contract['nodes']:
            p=tuple(row['position']);i=lookup[p]
            witnesses=row['witnesses']
            assert [r['pos'] for r in witnesses]==[[p[0],p[1]-1,p[2]],[p[0],p[1]-2,p[2]]]
            assert all(r['state']=='minecraft:light_gray_stained_glass' and world_read.block(tuple(r['pos']))==r['state'] for r in witnesses)
            active[i]=False;exclusions.append(row)
            retired.append(dict(node=i,position=p,observation={'status':'DECLARED_ENCLOSURE_CAP','purpose':contract['purpose']}))
        assert len(exclusions)==len({r['node'] for r in exclusions})
    landings=graph['named_lift_landings']
    assert all(active[r['node']] for r in landings)
    retired_ids={r['node'] for r in retired}
    edges=[r for r in npc['walking_edges'] if r[0] not in retired_ids and r[1] not in retired_ids]
    removed_connections=[]
    if blocked_connections:
        lookup={p:i for i,p in enumerate(points)}
        records=json.loads(blocked_connections.read_text('utf8'))['connections']
        for row in records:
            for key in ('a','b'):world_read.around(row[key],2)
        world_read.load()
        rejected=set()
        for row in records:
            a,b=tuple(row['a']),tuple(row['b']);i,j=lookup[a],lookup[b]
            assert a[1]==b[1] and math.dist(a,b)==1 and active[i] and active[j]
            states=[world_read.block(tuple(r['pos'])) for r in row['witnesses']]
            assert states==[r['state'] for r in row['witnesses']],('Changed guard evidence',a,b)
            assert any(s.startswith('projectseele:personnel_stair_guard_r53[') for s in states)
            assert all(geometry.standing(p)['status']=='STATIC_STANDING' for p in (a,b))
            assert not geometry.edge_clear(a,b),('Existing guard no longer separates nodes',a,b)
            assert any(u==i and v==j for u,v,_ in edges),('Missing source edge',a,b)
            rejected.add((i,j));removed_connections.append(row)
        edges=[r for r in edges if tuple(r[:2]) not in rejected]
    added=[]
    if connections:
        lookup={p:i for i,p in enumerate(points)};existing={(a,b) for a,b,_ in edges}
        records=json.loads(connections.read_text('utf8'))['connections']
        for row in records:
            for key in ('a','b'):world_read.around(row[key],2)
        world_read.load()
        for row in records:
            a,b=tuple(row['a']),tuple(row['b']);i,j=lookup[a],lookup[b]
            assert math.dist(a,b)==1 and i not in retired_ids and j not in retired_ids
            assert all(geometry.standing(p)['status']=='STATIC_STANDING' for p in (a,b)) and geometry.edge_clear(a,b)
            if (i,j) not in existing:edges.append([i,j,1.]);existing.add((i,j));added.append(row)
    backwards=[[] for _ in points]
    for a,b,c in edges:backwards[b].append((a,c))
    player=[r[:] for r in backwards]
    for e in graph['lift_edges']:
        a,b=e['a'],e['b'];player[b].append((a,5+abs(points[a][1]-points[b][1])/8))
    for e in graph['transport_edges']:player[e['to']].append((e['from'],20))
    results=[dijkstra(player,[g['node']]) for g in graph['goals']]
    disconnected=[i for i in range(len(points)) if active[i] and not all(math.isfinite(r[0][i]) for r in results)]
    assert not disconnected,('Retirement must not disconnect another destination',disconnected[:12])
    # An already surveyed component may become connected after restoring a
    # missing edge. No new walking coordinates are invented here.
    if added:
        used={a for a,b,_ in edges}|{b for a,b,_ in edges}
        for i in used:
            if i not in retired_ids and all(math.isfinite(r[0][i]) for r in results):active[i]=True
    graph['nodes']=[list(p)+[r[1][i] if active[i] else i for r in results] for i,p in enumerate(points)]
    graph['node_active']=active;graph['native_verified']=False
    raw=encode(graph);keys=nearest['node_floor_keys'];seeds=[r['node'] for r in landings]
    distances,parents,sources=dijkstra(backwards,seeds,keys=keys)
    fixed=list(map(math.isfinite,distances))
    distances,parents,sources=dijkstra(backwards,[i for i,b in enumerate(fixed) if b],fixed=fixed,initial=(distances,parents,sources))
    table=[];unresolved=[]
    for i in range(len(points)):
        if not active[i]:table.append(None);continue
        if not math.isfinite(distances[i]):
            assert nearest['nodes'][i] is None,('Previously reachable lift lost',points[i])
            table.append(None);unresolved.append(list(points[i]));continue
        table.append(dict(next=list(points[parents[i]]),nearest_landing=list(points[sources[i]]),walking_metres=distances[i],floor_key=keys[i],requires_floor_transfer=not fixed[i]))
    nearest.update(graph_sha256=hashlib.sha256(raw).hexdigest(),nodes=table,unresolved_coordinates=unresolved,native_verified=False)
    npc.update(walking_edges=edges,native_verified=False)
    out.mkdir(parents=True,exist_ok=True)
    (out/'before').mkdir(exist_ok=True)
    for name,data in original.items():(out/'before'/name).write_bytes(data)
    for name,data in zip(FILES,(raw,encode(nearest),encode(npc))):(out/name).write_bytes(data)
    report=dict(world=str(world),delta_sha256=hashlib.sha256(delta.read_bytes()).hexdigest(),affected=len(affected),retired=retired,
        preserved_all_landing_and_goal_connections=True,removed_edges=len(json.loads(gzip.decompress(original[FILES[2]]))['walking_edges'])-len(edges),
        added_connections=added,removed_connections=removed_connections,excluded_nodes=exclusions,
        previous_sha256={n:hashlib.sha256(b).hexdigest() for n,b in original.items()},
        installed_sha256={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in FILES},world_written=False)
    (out/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Affected',len(affected),'retired',len(retired),'net removed edges',report['removed_edges'],'added',len(added))

def install(world,out):
    report=json.loads((out/'PLAN.json').read_text('utf8'))
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        for n in FILES:assert hashlib.sha256((world/n).read_bytes()).hexdigest()==report['previous_sha256'][n]
        if report.get('removed_connections') or report.get('excluded_nodes'):
            measured=MeasuredWorld(world)
            evidence=report.get('removed_connections',[])+report.get('excluded_nodes',[])
            for row in evidence:
                for witness in row['witnesses']:measured.around(witness['pos'],1)
            measured.load()
            for row in evidence:
                for witness in row['witnesses']:
                    assert measured.block(tuple(witness['pos']))==witness['state'],'Guard changed since plan'
        for n in FILES:
            atomic_replace(world/n,(out/n).read_bytes())
            assert hashlib.sha256((world/n).read_bytes()).hexdigest()==report['installed_sha256'][n]
        report['world_written']=True;report['actual_readback']=True
        (out/'INSTALLED.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Installed navigation; runtime progress untouched')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--delta',type=Path);p.add_argument('--connections',type=Path);p.add_argument('--blocked-connections',type=Path);p.add_argument('--excluded-nodes',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    if a.apply:install(a.world,a.output)
    else:plan(a.world,a.delta,a.output,a.connections,a.blocked_connections,a.excluded_nodes)
