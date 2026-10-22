"""Freeze current navigation and preview removal of four false guard crossings."""
import argparse
import gzip
import hashlib
import json
import math
import msvcrt
import shutil
from pathlib import Path

from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from query_blocks import read_box, iter_block_entities, dimension_dir
from retire_r53_navigation_cells import FILES
from refresh_r53_repaired_navigation import dijkstra, encode

LOCAL=('local_lift_routes_r45.json.gz','local_nearest_lift_paths_r45.json.gz')
PAIRS=(((16,-422,305),(16,-422,306)),((16,-422,309),(16,-422,308)))
LO,HI=(12,-429,301),(23,-418,313)


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text('utf8'))
def write(p,v):
    b=json.dumps(v,ensure_ascii=False,indent=2).encode('utf8')
    p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)


def rebuild_navigation(frozen,preview,connections):
    """Use the delivered graph's routing policy, changing only proved edges."""
    graph,nearest,walking=[read(frozen/n) for n in FILES]
    points=[tuple(r) for r in walking['nodes']];lookup={q:i for i,q in enumerate(points)}
    rejected={(lookup[tuple(r['a'])],lookup[tuple(r['b'])]) for r in connections}
    original_edges=walking['walking_edges']
    assert rejected <= {tuple(r[:2]) for r in original_edges}
    edges=[r for r in original_edges if tuple(r[:2]) not in rejected]
    backwards=[[] for _ in points]
    for a,b,c in edges:backwards[b].append((a,c))
    player=[row[:] for row in backwards]
    for e in graph['lift_edges']:
        a,b=e['a'],e['b'];player[b].append((a,5+abs(points[a][1]-points[b][1])/8))
    for e in graph['transport_edges']:player[e['to']].append((e['from'],20))
    results=[dijkstra(player,[g['node']]) for g in graph['goals']]
    active=graph['node_active']
    assert all(not on or all(math.isfinite(r[0][i]) for r in results) for i,on in enumerate(active))
    graph['nodes']=[list(p)+[r[1][i] if active[i] else i for r in results] for i,p in enumerate(points)]
    graph['native_verified']=False
    raw=encode(graph);keys=nearest['node_floor_keys'];seeds=[r['node'] for r in graph['named_lift_landings']]
    distances,parents,sources=dijkstra(backwards,seeds,keys=keys)
    fixed=list(map(math.isfinite,distances))
    distances,parents,sources=dijkstra(backwards,[i for i,b in enumerate(fixed) if b],
        fixed=fixed,initial=(distances,parents,sources))
    table=[];unresolved=[]
    for i,on in enumerate(active):
        if not on:table.append(None);continue
        if not math.isfinite(distances[i]):
            assert nearest['nodes'][i] is None
            table.append(None);unresolved.append(list(points[i]));continue
        table.append(dict(next=list(points[parents[i]]),nearest_landing=list(points[sources[i]]),
            walking_metres=distances[i],floor_key=keys[i],requires_floor_transfer=not fixed[i]))
    nearest.update(graph_sha256=hashlib.sha256(raw).hexdigest(),nodes=table,
        unresolved_coordinates=unresolved,native_verified=False)
    walking.update(walking_edges=edges,native_verified=False)
    preview.mkdir();(preview/'before').mkdir()
    for n,b in zip(FILES,(raw,encode(nearest),encode(walking))):
        (preview/n).write_bytes(b);shutil.copy2(frozen/n,preview/'before'/n)
    write(preview/'PLAN.json',dict(world=str(frozen),affected=0,retired=[],added_connections=[],
        removed_connections=connections,excluded_nodes=[],removed_edges=4,world_written=False,
        preserved_all_landing_and_goal_connections=True,
        previous_sha256={n:sha(frozen/n) for n in FILES},
        installed_sha256={n:sha(preview/n) for n in FILES}))


def run(a):
    a.output.mkdir(parents=True,exist_ok=False)
    frozen=a.output/'frozen';frozen.mkdir()
    paths=[a.world/n for n in FILES+LOCAL+('native_collision_shapes.json','personnel_lifts_r52.json')]
    paths += [dimension_dir(a.world,'projectseele:geofront')/'region/r.0.0.mca']
    with (a.world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        hashes={}
        for p in paths:
            rel=p.relative_to(a.world);q=frozen/rel;q.parent.mkdir(parents=True,exist_ok=True)
            h=sha(p);shutil.copy2(p,q);assert sha(q)==h==sha(p)
            hashes[str(rel)]=h
    (frozen/'session.lock').write_bytes(b'\x00\x00\x00')
    write(a.output/'FREEZE.json',dict(world=str(a.world.resolve()),sha256=hashes,bounds=[LO,HI],world_written=False))
    graph,nearest,walking=[read(frozen/n) for n in FILES]
    local,local_nearest=[read(frozen/n) for n in LOCAL]
    assert nearest['graph_sha256']==sha(frozen/FILES[0])
    assert local_nearest['graph_sha256']==sha(frozen/LOCAL[0])
    coords=[tuple(p[:3]) for p in graph['nodes']]
    assert coords==[tuple(p) for p in walking['nodes']]
    assert len(coords)==len(nearest['nodes'])==len(nearest['node_floor_keys'])
    assert len(local['nodes'])==len(local_nearest['nodes'])==len(local_nearest['node_floor_keys'])
    local_coords={tuple(p[:3]) for p in local['nodes']}
    assert not any(p in local_coords for pair in PAIRS for p in pair)
    cells=read_box(frozen,'projectseele:geofront',LO,HI)
    tags=dict(iter_block_entities(frozen,'projectseele:geofront',LO,HI))
    write(a.output/'LOCAL_GEOMETRY_BEFORE.json.gz',[
        dict(pos=p,state=s,nbt=tags[p].snbt() if p in tags else None) for p,s in sorted(cells.items())])
    m=MeasuredWorld(frozen);m.box(LO,HI);m.load();g=ActualGeometry(m)
    centre=lambda q:(q[0]+.5,q[1],q[2]+.5)
    crossing=lambda a,b:g.clear(centre(a),target=centre(b))
    connections=[]
    for start,finish in PAIRS:
        assert g.standing(centre(start))=='STATIC_STANDING'
        # A stair node is not a flat nine-point standing datum. Its authored
        # rise is kept; test the horizontal body envelope at the upper step
        # height and isolate the rail's obstruction without changing the map.
        assert cells[finish[0],finish[1]-1,finish[2]].startswith('minecraft:quartz_stairs[facing=west,half=bottom,')
        assert crossing(start,finish)=='ACTUAL_BODY_OBSTRUCTION'
        state=cells[finish]
        assert state.startswith('projectseele:personnel_stair_guard_r53[facing=west,')
        class WithoutWitness:
            world=frozen
            def block(self,q):return 'minecraft:air' if tuple(q)==finish else m.block(q)
            def get(self,x,y,z):return self.block((x,y,z))
        diagnostic=ActualGeometry(WithoutWitness())
        assert diagnostic.clear(centre(start),target=centre(finish))=='CLEAR'
        for x,y in ((start,finish),(finish,start)):
            connections.append(dict(a=x,b=y,body_test_height=-422,
                destination_support='Authored shaped stair; no flat-datum or new standing permission inferred',
                isolated_guard_obstruction=True,witnesses=[dict(pos=finish,state=state)],
                reason='Existing upper stair side guard blocks lateral walking; centre approach remains'))
    # The three-wide authored stair throat is entered from its free east
    # landing. Keep its centre and all existing rising stair edges unchanged.
    entry=((15,-422,307),(16,-422,307))
    assert g.standing(centre(entry[0]))=='STATIC_STANDING'
    assert cells[16,-423,307].startswith('minecraft:quartz_stairs[facing=west,half=bottom,')
    assert crossing(entry[0],entry[1])=='CLEAR'
    assert not g.unknown
    blocked=a.output/'BLOCKED_CONNECTIONS.json';write(blocked,dict(connections=connections))
    delta=a.output/'NO_MAP_DELTA.json.gz';write(delta,[])
    preview=a.output/'navigation';rebuild_navigation(frozen,preview,connections)
    for n in LOCAL:
        shutil.copy2(frozen/n,preview/n);shutil.copy2(frozen/n,preview/'before'/n)
    after_graph,after_nearest,after_walking=[read(preview/n) for n in FILES]
    assert graph['node_active']==after_graph['node_active']
    assert graph['lift_edges']==after_graph['lift_edges'] and graph['transport_edges']==after_graph['transport_edges']
    assert graph['named_lift_landings']==after_graph['named_lift_landings']
    assert graph['goals']==after_graph['goals']
    assert coords==[tuple(p[:3]) for p in after_graph['nodes']]
    edges_before={tuple(r) for r in walking['walking_edges']};edges_after={tuple(r) for r in after_walking['walking_edges']}
    lookup={q:i for i,q in enumerate(coords)}
    expected={(lookup[tuple(r['a'])],lookup[tuple(r['b'])]) for r in connections}
    assert not(edges_after-edges_before)
    removed=edges_before-edges_after
    assert {r[:2] for r in removed}==expected and len(removed)==4
    assert all(r in edges_after for r in edges_before if coords[r[0]][1]!=coords[r[1]][1]),'Vertical stair edges changed'
    assert (lookup[entry[0]],lookup[entry[1]]) in {r[:2] for r in edges_after}
    assert after_nearest['graph_sha256']==sha(preview/FILES[0])
    changed_guidance=[dict(node=i,position=coords[i],before=p[3:],after=q[3:])
        for i,(p,q) in enumerate(zip(graph['nodes'],after_graph['nodes'])) if p[3:]!=q[3:]]
    changed_nearest=[dict(node=i,position=coords[i],before=p,after=q)
        for i,(p,q) in enumerate(zip(nearest['nodes'],after_nearest['nodes'])) if p!=q]
    for pair in expected:
        i,j=pair
        assert j not in after_graph['nodes'][i][3:]
        assert after_nearest['nodes'][i]['next']!=list(coords[j])
    assert all(sha(a.world/rel)==h for rel,h in hashes.items()),'Actual inputs changed during preparation'
    receipt=dict(source_world=str(a.world.resolve()),world_written=False,
        changed_static_cells=0,removed_directed_edges=4,retired_nodes=0,
        changed_goal_rows=len(changed_guidance),changed_nearest_lift_rows=len(changed_nearest),
        original_stair_vertical_edges_unchanged=True,original_centre_approach_unchanged=True,
        lifts_transport_goals_nodes_unchanged=True,
        previous_sha256={n:sha(frozen/n) for n in FILES+LOCAL},
        proposed_sha256={n:sha(preview/n) for n in FILES+LOCAL},
        local_navigation_unchanged=True,native_visual_and_navigation_review_required=True)
    write(a.output/'VERIFIED.json',receipt)
    write(a.output/'GUIDANCE_DIFF.json',dict(goals=changed_guidance,nearest_lift=changed_nearest))
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())
