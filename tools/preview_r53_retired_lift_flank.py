"""Prepare one cold, reversible old-shaft flank closure.

R23 assigns the two lip cells behind the old Z257 door to the shaft side.
The later civil migration retired that door. The three-cell wall closes its
remaining side bypass while preserving the R20 public vestibule and new lift.
Actual installation requires the explicit --install mode and an exact frozen
candidate; default preview mode never writes the supplied world.
"""
import argparse
import gzip
import hashlib
import json
import math
import msvcrt
import shutil
from collections import defaultdict
from pathlib import Path

import nbtlib
from PIL import Image, ImageDraw, ImageFont

from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from query_blocks import read_box, iter_block_entities, dimension_dir
from refresh_r53_repaired_navigation import dijkstra, encode
from repair_r53_reported_landings import apply as apply_preview
from review_r53_remaining_purposes import Overlay
from apply_s20_approved_semantic_repairs import Change, rewrite_region, atomic_replace

DIM = 'projectseele:geofront'
NAV = ('nerv_routes_r24.json.gz', 'nearest_lift_paths_r44.json.gz',
       'r53_personnel_walking_graph.json.gz', 'local_lift_routes_r45.json.gz',
       'local_nearest_lift_paths_r45.json.gz')
LO, HI = (3, -518, 249), (26, -507, 262)
TARGETS = [(15, y, 256) for y in range(-512, -509)]
RETIRED = [(x, -512, 256) for x in (13, 14, 15, 16)]
WALL = 'projectseele:nerv_structural_panel'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix == '.gz'
                      else p.read_text('utf8'))


def write(p, value):
    raw = json.dumps(value, ensure_ascii=False, indent=2).encode('utf8')
    p.write_bytes(gzip.compress(raw, mtime=0) if p.suffix == '.gz' else raw)


def snapshot(world, out):
    frozen = out/'frozen'
    frozen.mkdir()
    dim = dimension_dir(world, DIM)
    files = {dim/'region/r.0.0.mca', dim/'entities/r.0.0.mca'}
    files.update(world/n for n in NAV + ('personnel_lifts_r52.json',
        'native_collision_shapes.json', 'level.dat', 'level.dat_old',
        '.projectseele_lift_sliding_doors_r01.json'))
    for folder in ('r52', 'playerdata', 'data', 'dimensions/projectseele/geofront/data'):
        files.update(p for p in (world/folder).glob('*') if p.is_file()
                     and 'DistantHorizons' not in p.name)
    files.update(p for p in (world/'mtr').rglob('*') if p.is_file())
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        headers = list((dim/'data').glob('projectseele_city_rigid_topology_r45_*.dat'))
        assert len(headers) == 1
        cache = dim/'data'/str(nbtlib.load(headers[0])['data']['GenerationFolder'])/'chunks/0_16.dat'
        owned = []
        if cache.exists():
            files.add(cache)
            for entry in nbtlib.load(cache)['Static']:
                n = int(entry['Pos']); x = n >> 38; y = n & 4095; z = (n >> 12) & 67108863
                if y >= 2048: y -= 4096
                if z >= 33554432: z -= 67108864
                if (x, y, z) in TARGETS: owned.append((x, y, z))
        assert not owned, ('Resolve maintained-static owner first', owned)
        hashes = {}
        for p in sorted(files):
            if not p.exists(): continue
            rel = p.relative_to(world); q = frozen/rel
            q.parent.mkdir(parents=True, exist_ok=True)
            h = sha(p); shutil.copy2(p, q)
            assert h == sha(q) == sha(p)
            hashes[str(rel)] = h
    (frozen/'session.lock').write_bytes(b'\0\0\0')
    write(out/'FREEZE.json', dict(world=str(world.resolve()), bounds=[LO, HI],
        copied_sha256=hashes, cold_exclusive_session_lock=True,
        maintained_static_touched_cells=owned, actual_world_written=False))
    return frozen, hashes


def read_guards(world, artifact):
    rows = []
    for name in ('install-landings-v1', 'install-floor-edges-v1', 'install-office-edges-v1'):
        rows += read(artifact/name/'EXACT_DELTA.json.gz')
    assert len(rows) == len({tuple(r['pos']) for r in rows}) == 30
    by_chunk = defaultdict(list)
    for r in rows: by_chunk[r['pos'][0]//16, r['pos'][2]//16].append(r)
    observations = []
    for (cx, cz), group in by_chunk.items():
        ymin, ymax = min(r['pos'][1] for r in group), max(r['pos'][1] for r in group)
        cells = read_box(world, DIM, (cx*16, ymin, cz*16), (cx*16+15, ymax, cz*16+15))
        tags = dict(iter_block_entities(world, DIM, (cx*16, ymin, cz*16), (cx*16+15, ymax, cz*16+15)))
        for row in group:
            p = tuple(row['pos'])
            assert cells[p] == row['after'] and p not in tags
            observations.append(dict(pos=p, state=cells[p]))
    return observations


def geometry_checks(frozen, cells):
    m = MeasuredWorld(frozen); m.box(LO, HI); m.load()
    changes = {p: WALL for p in TARGETS}
    before, after = ActualGeometry(m), ActualGeometry(Overlay(m, changes))
    assert all(cells[p] == 'minecraft:air' for p in TARGETS)
    assert cells[15, -513, 256] == 'projectseele:nerv_floor_panel'
    assert all(cells[15, y, 255] == WALL for y in range(-512, -509))
    assert all(cells[x, y, 257] == WALL for x in (12, 13, 14) for y in range(-512, -509))
    bounds, source = (7, 250, 25, 261), (23, 258)
    bp, ap = {}, {}
    for p in ((13, 256), (14, 256), (16, 256)):
        bp[str(p)] = before.path(source, p, bounds, -512)
        ap[str(p)] = after.path(source, p, bounds, -512)
        assert bp[str(p)] and ap[str(p)] is None
    assert before.clear((13.5, -512, 258.5), target=(13.5, -512, 256.5)) == 'ACTUAL_BODY_OBSTRUCTION'
    negative = ActualGeometry(Overlay(m, {(15, -510, 256): WALL}))
    assert negative.path(source, (13, 256), bounds, -512)
    # X16 is the blind pocket between the R53-restored original Tree backing,
    # original north shaft wall and east quartz wall. Its sole entrance is the
    # same closing neck. It has no public continuation or lift control.
    pocket_witnesses = []
    for x,z,state in ((16,255,WALL),(16,257,'minecraft:black_concrete'),
                      (17,256,'minecraft:quartz_block')):
        for y in range(-512,-509):
            assert cells[x,y,z] == state
            pocket_witnesses.append(dict(pos=(x,y,z),state=state))
    assert before.standing((16.5,-512,256.5)) == 'STATIC_STANDING'
    assert after.clear((16.5,-512,256.5),target=(15.5,-512,256.5)) == 'ACTUAL_BODY_OBSTRUCTION'
    public = []
    for x in range(15, 18):
        for z in range(256, 261):
            p = (x+.5, -512, z+.5)
            if before.standing(p) == 'STATIC_STANDING':
                if (x,-512,z) in RETIRED: continue
                assert after.standing(p) == 'STATIC_STANDING'
                assert after.path(source, (x, z), bounds, -512)
                public.append(p)
    lift = next(r for r in read(frozen/'personnel_lifts_r52.json')['lifts']
                if r['id'] == 's20-command-rear-x12-z253-v4')
    floor = next(r for r in lift['floors'] if r['cabin'][1] == -512)
    opened = {tuple(r['pos']): 'minecraft:air' for kind in ('landing_doors', 'cabin_doors') for r in floor[kind]}
    b_open = ActualGeometry(Overlay(m, opened)); a_open = ActualGeometry(Overlay(m, {**opened, **changes}))
    aperture = []
    for x in range(7, 12):
        for offset in (.3, .5, .7):
            p, q = (x+offset, -512, 256.5), (x+offset, -512, 258.5)
            assert b_open.clear(p, target=q) == a_open.clear(p, target=q) == 'CLEAR'
            aperture.append(dict(start=p, end=q))
    assert not before.unknown | after.unknown | negative.unknown | b_open.unknown | a_open.unknown
    return dict(side_routes_before=bp, side_routes_after=ap,
        centreline_alone_misses_bypass=True, reopened_lower_flank_negative_detected=True,
        retained_public_standing_points=public, retained_door_full_width=aperture,
        full_R20_vestibule_band_checked=[15,17,256,260],
        x16_blind_pocket_existing_three_sided_enclosure=pocket_witnesses,
        x16_source='tools/repair_r53_reported_landings.py: original_tree_solid_backing X16..25/Z257')


def navigation(frozen, out, artifact):
    graph, nearest, walking, local, ln = [read(frozen/n) for n in NAV]
    points = [tuple(r) for r in walking['nodes']]; lookup = {p:i for i,p in enumerate(points)}
    assert points == [tuple(r[:3]) for r in graph['nodes']]
    assert nearest['graph_sha256'] == sha(frozen/NAV[0]) and ln['graph_sha256'] == sha(frozen/NAV[3])
    assert len(points) == len(nearest['nodes']) == len(nearest['node_floor_keys'])
    assert len(local['nodes']) == len(ln['nodes']) == len(ln['node_floor_keys'])
    assert not set(RETIRED) & {tuple(r[:3]) for r in local['nodes']}
    retired = {lookup[p] for p in RETIRED}
    active = graph['node_active'][:]
    assert all(active[i] for i in retired)
    assert not retired & {r['node'] for r in graph['goals']+graph['named_lift_landings']}
    original_edges = walking['walking_edges']
    previously_removed = read(artifact/'upper-navigation-v2/BLOCKED_CONNECTIONS.json')['connections']
    delivered_hashes = read(artifact/'upper-navigation-v2/VERIFIED.json')['proposed_sha256']
    assert all(sha(frozen/n)==delivered_hashes[n] for n in NAV), 'Current navigation differs from delivered four-edge batch'
    excluded_pairs = {(lookup[tuple(r['a'])], lookup[tuple(r['b'])]) for r in previously_removed}
    assert len(excluded_pairs) == 4
    assert not excluded_pairs & {tuple(r[:2]) for r in original_edges}
    edges = [r for r in original_edges if not retired & set(r[:2])]
    removed = [r for r in original_edges if retired & set(r[:2])]
    assert len(removed) == 8
    for i in retired: active[i] = False
    backwards = [[] for _ in points]
    for a,b,c in edges: backwards[b].append((a,c))
    player = [r[:] for r in backwards]
    for e in graph['lift_edges']:
        a,b = e['a'], e['b']; player[b].append((a, 5+abs(points[a][1]-points[b][1])/8))
    for e in graph['transport_edges']: player[e['to']].append((e['from'],20))
    results = [dijkstra(player,[g['node']]) for g in graph['goals']]
    disconnected = [i for i,on in enumerate(active) if on and not all(math.isfinite(r[0][i]) for r in results)]
    assert not disconnected, ('Unexpected disconnected public nodes', disconnected[:20])
    old_nodes = graph['nodes']
    graph['nodes'] = [list(p)+[r[1][i] if active[i] else i for r in results] for i,p in enumerate(points)]
    graph['node_active'] = active; graph['native_verified'] = False
    raw = encode(graph); keys = nearest['node_floor_keys']; seeds = [r['node'] for r in graph['named_lift_landings']]
    distances, parents, sources = dijkstra(backwards, seeds, keys=keys)
    fixed = list(map(math.isfinite, distances))
    distances, parents, sources = dijkstra(backwards, [i for i,b in enumerate(fixed) if b],
        fixed=fixed, initial=(distances,parents,sources))
    table, unresolved = [], []
    for i,on in enumerate(active):
        if not on: table.append(None); continue
        if not math.isfinite(distances[i]):
            assert nearest['nodes'][i] is None, ('Previously reachable lift lost', points[i])
            table.append(None); unresolved.append(list(points[i])); continue
        table.append(dict(next=list(points[parents[i]]), nearest_landing=list(points[sources[i]]),
            walking_metres=distances[i], floor_key=keys[i], requires_floor_transfer=not fixed[i]))
    diffs = dict(goals=[dict(node=i,position=points[i],before=p[3:],after=q[3:])
        for i,(p,q) in enumerate(zip(old_nodes,graph['nodes'])) if p[3:]!=q[3:]],
        nearest=[dict(node=i,position=points[i],before=p,after=q)
        for i,(p,q) in enumerate(zip(nearest['nodes'],table)) if p!=q])
    nearest.update(graph_sha256=hashlib.sha256(raw).hexdigest(),nodes=table,
        unresolved_coordinates=unresolved,native_verified=False)
    walking.update(walking_edges=edges,native_verified=False)
    out.mkdir(); (out/'before').mkdir()
    for name,data in zip(NAV[:3],(raw,encode(nearest),encode(walking))): (out/name).write_bytes(data)
    for name in NAV[3:]: shutil.copy2(frozen/name,out/name)
    for name in NAV: shutil.copy2(frozen/name,out/'before'/name)
    assert not excluded_pairs & {tuple(r[:2]) for r in read(out/NAV[2])['walking_edges']}
    assert read(out/NAV[1])['graph_sha256'] == sha(out/NAV[0])
    assert read(out/NAV[4])['graph_sha256'] == sha(out/NAV[3])
    assert all(read(out/NAV[1])['nodes'][i] is None for i in retired)
    write(out/'GUIDANCE_DIFF.json', diffs)
    report = dict(retired_nodes=[dict(node=i,position=points[i],purpose=(
        'R53-restored Tree backing and old shaft-wall blind pocket; sole neck closed' if points[i][0]==16
        else 'R23 obsolete shaft side or its closed access neck; retired Z257 door')) for i in sorted(retired)],
        removed_edges=removed, prior_four_directed_edges_still_absent=True,
        remaining_public_nodes_connected_to_all_goals=True, local_two_caches_unchanged=True,
        current_five_hashes_match_previously_delivered_four_edge_batch=True,
        goal_rows_changed=len(diffs['goals']), nearest_rows_changed=len(diffs['nearest']),
        previous_sha256={n:sha(frozen/n) for n in NAV}, proposed_sha256={n:sha(out/n) for n in NAV},
        world_written=False)
    write(out/'PLAN.json',report)
    return report


def browser_diagram(out, cells, routes):
    scale, x0, z0 = 35, 5, 250
    im = Image.new('RGB', (1520, 660), '#101820'); d = ImageDraw.Draw(im)
    font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 15)
    small = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 12)
    colors = {'wall':'#70818b','air':'#233745','door':'#779daf','guard':'#ffd16b','patch':'#e46d50','void':'#070e15'}
    for col, title in enumerate(('CURRENT ACTUAL / feet Y=-512', 'PREVIEW / 3-cell side closure')):
        ox, oy = 35+col*750, 64
        d.text((ox,20),title,font=font,fill='white')
        for x in range(5,26):
            d.text((ox+(x-x0)*scale+9,oy-20),str(x),font=small,fill='#b9c9d4')
            for z in range(250,263):
                p=(x,-512,z); state=cells[p]
                key='air' if state=='minecraft:air' else 'wall'
                if 'door' in state:key='door'
                if 'rail' in state or 'guard' in state:key='guard'
                if state=='minecraft:air' and cells.get((x,-513,z))=='minecraft:air':key='void'
                if col and p in TARGETS:key='patch'
                rect=(ox+(x-x0)*scale,oy+(z-z0)*scale,ox+(x-x0+1)*scale-1,oy+(z-z0+1)*scale-1)
                d.rectangle(rect,fill=colors[key],outline='#34505d')
                if x==5:d.text((ox-29,oy+(z-z0)*scale+10),str(z),font=small,fill='#b9c9d4')
                if p in RETIRED:d.text((rect[0]+11,rect[1]+9),'X' if col else 'o',font=font,fill='#ffdfbd')
        if not col:
            route=next(iter(routes.values()))
            pts=[(ox+(p[0]-x0)*scale,oy+(p[2]-z0)*scale) for p in route]
            d.line(pts,fill='#f76c6c',width=4)
        d.text((ox,532),'NORTH ^   blue: current lift door   amber: retained edge guards',font=small,fill='#c9dce4')
        d.text((ox,554),'Old lip X13/14,Z256 | new lift aperture X7..11,Z257',font=small,fill='#c9dce4')
        d.text((ox,576),'Public R20 vestibule stays open south/east of closure',font=small,fill='#c9dce4')
    d.text((35,622),'Measured block plan, not a game rendering. Full Y=-512..-510 closure; native visual review pending.',font=font,fill='#ffd16b')
    im.save(out/'flank-plan.png')
    cameras=[]
    for name,feet,target in [('flank_from_public',(15.5,-512,258.5),(15.5,-511,256.5)),
                             ('retained_new_lift_aperture',(9.5,-512,259.5),(9.5,-511,257.5))]:
        eye=(feet[0],feet[1]+1.62,feet[2]); dx,dy,dz=(target[i]-eye[i] for i in range(3))
        cameras.append(dict(id=name,dimension=DIM,feet=feet,eye=eye,target=target,
            yaw=math.degrees(math.atan2(-dx,dz)),pitch=-math.degrees(math.atan2(dy,math.hypot(dx,dz))),
            operation='Static camera only; do not alter player/progress',native_capture_pending=True))
    write(out/'CAMERAS.json',cameras)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>R53 retired lift flank</title><style>body{background:#101820;color:#d7e5ec;font:18px sans-serif;margin:24px}img{width:100%;max-width:1520px}a{color:#82caff}</style><h1>旧主梯侧绕封口：实际冻结与三格候选</h1><p>仅预览，未安装。红线为现状可绕入旧井唇的路径；右图橙红色为三格高封口。新门全宽、公共前厅与原护栏保留。控制台两处继续 HOLD。</p><img src="flank-plan.png"><p><a href="CAMERAS.json">原生静态相机坐标</a> · <a href="VERIFIED.json">完整回读与缓存清单</a></p>', 'utf8')


def run(a):
    a.output.mkdir(parents=True,exist_ok=False)
    artifact=a.purpose.parent
    evidence=read(a.purpose/'PURPOSE_RECOVERY.json')
    assert evidence['old_shaft']['classification']=='SOURCE_PURPOSE_RECOVERED_OBSOLETE_SHAFT_LIP_WITH_SIDE_BYPASS'
    for rel,h in evidence['sources'].items():
        assert sha(Path(__file__).resolve().parents[1]/rel)==h,('Purpose source changed',rel)
    frozen,hashes=snapshot(a.world,a.output)
    guards=read_guards(frozen,artifact)
    cells=read_box(frozen,DIM,LO,HI);tags=dict(iter_block_entities(frozen,DIM,LO,HI))
    write(a.output/'LOCAL_BEFORE.json.gz',[dict(pos=p,state=s,nbt=tags[p].snbt() if p in tags else None) for p,s in sorted(cells.items())])
    checks=geometry_checks(frozen,cells)
    assert not set(TARGETS)&set(tags)
    rows=[dict(pos=p,before=cells[p],after=WALL,before_nbt=None,after_nbt=None,
        reason='close_side_bypass_of_retired_R23_old_shaft') for p in TARGETS]
    patch=a.output/'patch';patch.mkdir()
    write(patch/'EXACT_DELTA.json.gz',rows)
    write(patch/'INVERSE_DELTA.json.gz',[dict(r,before=r['after'],after=r['before']) for r in rows])
    write(patch/'POSITIVE_EDIT_MASK.json.gz',TARGETS)
    write(patch/'PURPOSE_EVIDENCE.json',dict(source=str(a.purpose),sha256=sha(a.purpose/'PURPOSE_RECOVERY.json'),
        purpose=evidence['old_shaft']['purpose_evidence'],control_recess_status='HOLD_NO_EDITS',
        exact_bypass_and_negative=checks,retired_node_positions=RETIRED,
        tree_backing_source_sha256=sha(Path(__file__).resolve().parents[1]/'tools/repair_r53_reported_landings.py')))
    nav=navigation(frozen,a.output/'navigation',artifact)
    preview=a.output/'preview';shutil.copytree(frozen,preview)
    receipt=a.output/'preview-receipt';receipt.mkdir();shutil.copy2(patch/'EXACT_DELTA.json.gz',receipt/'EXACT_DELTA.json.gz')
    apply_preview(preview,receipt)
    for name in NAV:shutil.copy2(a.output/'navigation'/name,preview/name)
    new=read_box(preview,DIM,LO,HI);newtags=dict(iter_block_entities(preview,DIM,LO,HI))
    assert {p:(cells[p],s) for p,s in new.items() if cells[p]!=s}=={tuple(r['pos']):(r['before'],r['after']) for r in rows}
    assert {p:t.snbt() for p,t in tags.items()}=={p:t.snbt() for p,t in newtags.items()}
    assert read_guards(preview,artifact)==guards
    changed_files={str(dimension_dir(frozen,DIM).relative_to(frozen)/'region/r.0.0.mca'),*NAV[:3]}
    assert all(sha(preview/rel)==h for rel,h in hashes.items() if rel not in changed_files)
    assert all(sha(preview/n)==nav['proposed_sha256'][n] for n in NAV)
    # Test the exact inverse in a separate sparse region-only copy.
    inverse=a.output/'inverse-check';(inverse/'dimensions/projectseele/geofront/region').mkdir(parents=True)
    region=Path('dimensions/projectseele/geofront/region/r.0.0.mca')
    shutil.copy2(preview/region,inverse/region);(inverse/'session.lock').write_bytes(b'\0\0\0')
    ir=a.output/'inverse-receipt';ir.mkdir();shutil.copy2(patch/'INVERSE_DELTA.json.gz',ir/'EXACT_DELTA.json.gz');apply_preview(inverse,ir)
    assert read_box(inverse,DIM,LO,HI)==cells
    assert {p:t.snbt() for p,t in iter_block_entities(inverse,DIM,LO,HI)}=={p:t.snbt() for p,t in tags.items()}
    with (a.world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        assert all(sha(a.world/rel)==h for rel,h in hashes.items()),'Actual changed during preview preparation'
    report=dict(actual_world_written=False,preview_world=str(preview),changed_cells=3,full_local_nbt_preserved=len(tags),
        exact_inverse_readback=True,retained_previously_delivered_guards=guards,
        prior_four_directed_edges_still_absent=True,geometry=checks,navigation=nav,
        preserved_progress_sha256={rel:h for rel,h in hashes.items() if rel not in changed_files},
        actual_cold_hashes_still_match=True,control_recess_status='TWO_DIRECTIONS_HOLD_ZERO_EDITS',
        native_visual_and_door_state_review_required=True)
    write(a.output/'VERIFIED.json',report)
    write(patch/'PLAN.json',dict(source=str(a.world.resolve()),frozen=str(frozen),changed_cells=3,
        before_sha256=hashes,navigation_before=nav['previous_sha256'],navigation_after=nav['proposed_sha256'],
        must_install_same_batch='EXACT_DELTA plus all five navigation files; do not install only the main graph',
        source_world_written=False,native_visual_review_required=True))
    browser_diagram(a.output,cells,checks['side_routes_before'])
    print(json.dumps(dict(output=str(a.output),cells=3,retired_nodes=len(nav['retired_nodes']),removed_edges=len(nav['removed_edges']),
        previous_guards_preserved=len(guards),unchanged_local_block_entities=len(tags),actual_written=False)))


def install(a):
    """Install only the verified three cells plus their five caches, cold."""
    candidate = a.candidate.resolve()
    manifest = read(candidate/'FREEZE.json')
    verified = read(candidate/'VERIFIED.json')
    assert Path(manifest['world']).resolve() == a.world.resolve()
    assert not verified['actual_world_written'] and verified['changed_cells'] == 3
    rows = read(candidate/'patch/EXACT_DELTA.json.gz')
    inverse = read(candidate/'patch/INVERSE_DELTA.json.gz')
    assert [tuple(r['pos']) for r in rows] == TARGETS
    assert read(candidate/'patch/POSITIVE_EDIT_MASK.json.gz') == [list(p) for p in TARGETS]
    assert all(r['before']=='minecraft:air' and r['after']==WALL and
               r['before_nbt'] is None and r['after_nbt'] is None for r in rows)
    assert all(p['pos']==q['pos'] and p['before']==q['after'] and p['after']==q['before']
               for p,q in zip(rows,inverse)) and len(inverse)==3
    nav = verified['navigation']; hashes = manifest['copied_sha256']
    region = Path('dimensions/projectseele/geofront/region/r.0.0.mca')
    affected_files = [str(region), *NAV]
    assert all(sha(candidate/'navigation'/n)==nav['proposed_sha256'][n] for n in NAV)
    assert all(sha(candidate/'navigation/before'/n)==nav['previous_sha256'][n] for n in NAV)
    a.output.mkdir(parents=True,exist_ok=False)
    backup = a.output/'before'; backup.mkdir()
    with (a.world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        assert all(sha(a.world/rel)==h for rel,h in hashes.items()), 'Actual input changed since preview'
        before = read_box(a.world,DIM,LO,HI)
        tags = dict(iter_block_entities(a.world,DIM,LO,HI))
        frozen_rows = read(candidate/'LOCAL_BEFORE.json.gz')
        assert before == {tuple(r['pos']):r['state'] for r in frozen_rows}
        assert {p:t.snbt() for p,t in tags.items()} == {
            tuple(r['pos']):r['nbt'] for r in frozen_rows if r['nbt'] is not None}
        assert all(before[tuple(r['pos'])]==r['before'] and tuple(r['pos']) not in tags for r in rows)
        guards = read_guards(a.world,candidate.parent)
        assert {tuple(r['pos']):r['state'] for r in guards} == {
            tuple(r['pos']):r['state'] for r in verified['retained_previously_delivered_guards']}
        for rel in affected_files:
            dest=backup/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(a.world/rel,dest);assert sha(dest)==hashes[rel]
        for name in ('EXACT_DELTA.json.gz','INVERSE_DELTA.json.gz','POSITIVE_EDIT_MASK.json.gz','PURPOSE_EVIDENCE.json'):
            shutil.copy2(candidate/'patch'/name,a.output/name)
        write(a.output/'INSTALL_PLAN.json',dict(world=str(a.world.resolve()),candidate=str(candidate),
            source_hashes=hashes,patch_sha256=sha(candidate/'patch/EXACT_DELTA.json.gz'),
            geometry_and_nav_one_cold_batch=True,progress_replacement=False))
        changes=[Change('r53-retired-shaft-flank',*r['pos'],r['before'],r['after'],'restore',r['reason']) for r in rows]
        region_bytes=rewrite_region(a.world/region,{(0,16):changes},set(),{})
        replacements={str(region):region_bytes,**{n:(candidate/'navigation'/n).read_bytes() for n in NAV}}
        written=[]
        try:
            for rel,data in replacements.items():
                atomic_replace(a.world/rel,data);written.append(rel)
            after=read_box(a.world,DIM,LO,HI)
            assert {p:(before[p],s) for p,s in after.items() if before[p]!=s} == {
                tuple(r['pos']):(r['before'],r['after']) for r in rows}
            after_tags=dict(iter_block_entities(a.world,DIM,LO,HI))
            assert {p:t.snbt() for p,t in tags.items()}=={p:t.snbt() for p,t in after_tags.items()}
            assert read_guards(a.world,candidate.parent)==guards
            assert all(sha(a.world/n)==nav['proposed_sha256'][n] for n in NAV)
            main,near,walking,local,local_near=[read(a.world/n) for n in NAV]
            assert near['graph_sha256']==sha(a.world/NAV[0]) and local_near['graph_sha256']==sha(a.world/NAV[3])
            assert [r[:3] for r in main['nodes']]==walking['nodes']
            lookup={tuple(p):i for i,p in enumerate(walking['nodes'])}
            ids={lookup[p] for p in RETIRED}
            assert all(not main['node_active'][i] and near['nodes'][i] is None for i in ids)
            assert all(not ids & set(e[:2]) for e in walking['walking_edges'])
            old_removed=read(candidate.parent/'upper-navigation-v2/BLOCKED_CONNECTIONS.json')['connections']
            old_pairs={(lookup[tuple(r['a'])],lookup[tuple(r['b'])]) for r in old_removed}
            assert not old_pairs & {tuple(e[:2]) for e in walking['walking_edges']}
            protected={rel:h for rel,h in hashes.items() if rel not in affected_files}
            assert all(sha(a.world/rel)==h for rel,h in protected.items())
        except Exception:
            for rel in reversed(written):atomic_replace(a.world/rel,(backup/rel).read_bytes())
            assert all(sha(a.world/rel)==h for rel,h in hashes.items())
            write(a.output/'ROLLED_BACK.json',dict(actual_original_hashes_restored=True,written_before_failure=written))
            raise
        receipt=dict(world=str(a.world.resolve()),candidate=str(candidate),cold_exclusive_lock=True,
            changed_cells=3,full_local_block_entities_preserved=len(tags),
            retired_nodes=nav['retired_nodes'],removed_directed_edges=8,
            prior_30_guards_exact=True,prior_four_directed_edges_still_absent=True,
            five_navigation_sha256={n:sha(a.world/n) for n in NAV},
            navigation_bindings_exact=True,region_before_sha256=hashes[str(region)],
            region_after_sha256=sha(a.world/region),protected_file_count=len(protected),
            protected_sha256=protected,progress_unchanged=True,actual_readback=True,
            console_two_directions='HOLD_NO_EDITS',native_visual_pending=True)
        write(a.output/'INSTALLED.json',receipt)
        write(a.output/'COLD_READBACK.json',receipt)
    print(json.dumps(dict(installed=str(a.output),cells=3,retired_nodes=4,removed_edges=8,
        previous_guards=30,progress_unchanged=True,native_pending=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('world','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--purpose',type=Path);p.add_argument('--candidate',type=Path)
    p.add_argument('--install',action='store_true')
    args=p.parse_args()
    assert args.candidate if args.install else args.purpose
    (install if args.install else run)(args)
