"""Preview two missing continuations of declared office-lift platform rails.

Uses a prior cold freeze only. The actual world is never opened or modified;
installation requires a new cold precondition check by the owning agent.
"""
import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

from audit_r53_intermediate_floors import Audit, load
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from query_blocks import read_box, iter_block_entities
from repair_r53_reported_landings import apply, DIM

LO, HI = (23, -485, 309), (34, -429, 324)
LEVELS = (-481, -433)
RAIL = 'projectseele:nerv_edge_rail[east=true,north=false,south=false,west=false]'
LEFT = 'projectseele:nerv_edge_rail[east=false,north=false,south=false,west=true]'
NAV = ('nerv_routes_r24.json.gz', 'nearest_lift_paths_r44.json.gz',
       'r53_personnel_walking_graph.json.gz', 'local_lift_routes_r45.json.gz',
       'local_nearest_lift_paths_r45.json.gz')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    data = json.dumps(value, ensure_ascii=False, indent=2).encode('utf8')
    p.write_bytes(gzip.compress(data, mtime=0) if p.suffix == '.gz' else data)


def run(a):
    a.output.mkdir(parents=True, exist_ok=False)
    regression = load(a.regression)
    assert regression['passed'] and len(regression['guard_missing_before']) == 4
    assert not regression['guard_missing_after']
    cells = read_box(a.frozen, DIM, LO, HI)
    tags = dict(iter_block_entities(a.frozen, DIM, LO, HI))
    write(a.output/'LOCAL_BEFORE.json.gz', [dict(pos=p, state=s,
        nbt=tags[p].snbt() if p in tags else None) for p, s in sorted(cells.items())])
    lift = next(r for r in load(a.frozen/'personnel_lifts_r52.json')['lifts']
                if r['id'] == 's23-commander-office-x28-z321-v1')
    floors = [r for r in lift['floors'] if r['cabin'][1] in LEVELS]
    assert len(floors) == 2
    rows = []
    doors = set()
    for floor in floors:
        y = floor['cabin'][1]
        assert floor['cabin'] == [28, y, 321] and floor['exit'] == 'north'
        assert len(floor['calls']) == 1
        call = floor['calls'][0]
        assert call['kind'] == 'seele_reader' and call['position'] == [25, y+1, 316]
        assert cells[25, y+1, 316] == call['state']
        assert (25, y+1, 316) in tags
        assert cells[30, y-1, 316] == 'minecraft:sea_lantern'
        assert cells[30, y, 316] == 'minecraft:air' and (30, y, 316) not in tags
        assert cells[30, y, 315] == RAIL and cells[26, y, 316] == LEFT
        assert cells[31, y+1, 316].startswith('minecraft:polished_blackstone_button[')
        for r in floor['landing_doors']:
            p = tuple(r['pos'])
            assert r['closed_state'] == 'minecraft:gray_stained_glass'
            assert cells[p] == 'projectseele:lift_door_interlock_r53'
            doors.add(p)
        rows.append(dict(pos=[30, y, 316], before='minecraft:air', after=RAIL,
            before_nbt=None, after_nbt=None,
            reason='one_cell_continuation_of_existing_office_landing_east_rail'))
    m = MeasuredWorld(a.frozen)
    m.box(LO, HI)
    m.load()
    overrides = {tuple(r['pos']): r['after'] for r in rows}

    class StateView:
        world = a.frozen
        def __init__(self, patch=(), opened=False):
            self.patch, self.opened = dict(patch), opened
        def block(self, p):
            p = tuple(p)
            if self.opened and p in doors:
                return 'minecraft:air'
            return self.patch.get(p, m.block(p))
        def get(self, x, y, z):
            return self.block((x, y, z))

    before, after = ActualGeometry(m), ActualGeometry(StateView(overrides))
    old, new = Audit.__new__(Audit), Audit.__new__(Audit)
    old.m, old.g = m, before
    new.m, new.g = StateView(overrides), after
    expected = {((30, y, 316), (31, y, 316)) for y in LEVELS}
    observed = {(tuple(r['cell']), tuple(r['to'])) for p in overrides for r in old.drops(p)}
    assert observed == expected
    assert not [r for p in overrides for r in new.drops(p)]
    assert all(new.status(p) == 'STATIC_STANDING' for p in overrides)
    # Both originally guarded neighbouring cells are detector negatives.
    assert all(not old.drops((30, y, 315)) for y in LEVELS)
    open_before = ActualGeometry(StateView(opened=True))
    open_after = ActualGeometry(StateView(overrides, opened=True))
    paths = []
    for y, stair_z in ((-481, 313), (-433, 314)):
        for x in (26.42, 26.5, 27.5, 28.5, 29.5, 30.5, 30.58):
            # Rise across the original half steps, never horizontally through
            # their risers. Door-open geometry is diagnostic, not a map edit.
            paths += [((x, y-1, stair_z-.4), (x, y-1, stair_z-.3)),
                      ((x, y-.5, stair_z-.3), (x, y-.5, stair_z+.2)),
                      ((x, y, stair_z+.2), (x, y, stair_z+.8)),
                      ((x, y, stair_z+.8), (x, y, 316.5)),
                      ((x, y, 316.5), (x, y, 317.7))]
        # Lateral full-width circulation immediately before the door is kept.
        paths += [((26.42, y, 316.5), (30.58, y, 316.5))]
    for p, q in paths:
        assert open_before.clear(p, target=q) == open_after.clear(p, target=q) == 'CLEAR', (p, q)
    # The new rail's top is 1.375. Rays from normal player eye height to both
    # the actual left reader and the retained old right button stay above it.
    ray_proof = []
    for y in LEVELS:
        boxes = after.boxes((30, y, 316))
        top = max(b[4] for b in boxes)
        assert top == 1.375
        ray_proof.append(dict(from_eye=[30.5, y+1.62, 316.5],
            to_old_button=[31.5, y+1.5, 316.06], rail_top=y+top,
            minimum_ray_height=y+1.5, left_reader=[25, y+1, 316],
            full_NBT_preserved=True))
    graph, nearest, walk, local, local_nearest = [load(a.navigation/n) for n in NAV]
    assert nearest['graph_sha256'] == sha(a.navigation/NAV[0])
    assert local_nearest['graph_sha256'] == sha(a.navigation/NAV[3])
    nodes = [tuple(p) for p in walk['nodes']]
    assert nodes == [tuple(p[:3]) for p in graph['nodes']]
    near = lambda p: any(abs(p[1]-y) <= 1 and 25 <= p[0] <= 32 and 313 <= p[2] <= 318 for y in LEVELS)
    checks = []
    for i, j, *_ in walk['walking_edges']:
        p, q = nodes[i], nodes[j]
        if not (near(p) or near(q)):
            continue
        # Check each endpoint height for sloping edges as well as flat ones;
        # a new narrow side rail must not change their collision envelopes.
        for height in sorted({p[1], q[1]}):
            start, end = (p[0]+.5, height, p[2]+.5), (q[0]+.5, height, q[2]+.5)
            b, c = open_before.clear(start, target=end), open_after.clear(start, target=end)
            assert b == c, (p, q, height, b, c)
            checks.append(dict(a=p, b=q, body_height=height, status=c))
    assert not before.unknown and not after.unknown
    assert not open_before.unknown and not open_after.unknown
    sources = ['src/main/java/com/projectseele/world/S20PhysicalElevatorDirector.java',
               'tools/refine_architecture_r14.py', 'tools/finish_gallery_roof_r14.py']
    evidence = dict(frozen=str(a.frozen.resolve()), manifest_sha256=sha(a.frozen/'personnel_lifts_r52.json'),
        owner='Original office elevator raised five-wide north landing', floors=floors,
        sources={s: sha(a.source/s) for s in sources},
        generator='buildLanding: sides -2..2, depths CABIN_DOOR_DISTANCE+1..THRESHOLD_END; side+depth=7 lamp at right corner',
        original_stairs='Five-wide authored south-facing riser, lower z313 and upper z314',
        call_access='Current office manifest readers left x25; retained legacy button right x31 unchanged',
        no_construction_permission_inferred_from_air=True)
    write(a.output/'PURPOSE_EVIDENCE.json', evidence)
    patch = a.output/'patch'
    patch.mkdir()
    for name, data in (('EXACT_DELTA.json.gz', rows),
        ('INVERSE_DELTA.json.gz', [dict(r, before=r['after'], after=r['before']) for r in rows]),
        ('POSITIVE_EDIT_MASK.json.gz', [r['pos'] for r in rows])):
        write(patch/name, data)
    write(patch/'PLAN.json', dict(changed_cells=2, source_world_written=False,
        frozen=str(a.frozen.resolve()), purpose=evidence, before_unguarded_directions=2,
        after_unguarded_directions=0, normal_entry_exit_sweeps=len(paths),
        navigation_body_envelopes_checked=len(checks), changed_navigation_edges=[],
        navigation_sha256={n: sha(a.navigation/n) for n in NAV},
        button_access=ray_proof, native_visual_review_required=True,
        installation_requires_current_cold_freeze_and_static_ownership_check=True))
    write(a.output/'NAVIGATION_CHECKS.json.gz', checks)
    preview = a.output/'preview'
    shutil.copytree(a.frozen, preview)
    for n in NAV:
        shutil.copy2(a.navigation/n, preview/n)
    receipt = a.output/'preview-receipt'
    receipt.mkdir()
    shutil.copy2(patch/'EXACT_DELTA.json.gz', receipt/'EXACT_DELTA.json.gz')
    apply(preview, receipt)
    actual = read_box(preview, DIM, LO, HI)
    new_tags = dict(iter_block_entities(preview, DIM, LO, HI))
    assert {p: (cells[p], s) for p, s in actual.items() if cells[p] != s} == {
        tuple(r['pos']): (r['before'], r['after']) for r in rows}
    assert {p: t.snbt() for p, t in tags.items()} == {p: t.snbt() for p, t in new_tags.items()}
    assert all(sha(preview/n) == sha(a.navigation/n) for n in NAV)
    write(a.output/'VERIFIED.json', dict(changed_cells=2, full_local_cells=len(cells),
        full_NBT_unchanged=len(tags), all_five_navigation_files_unchanged=True,
        full_width_entry_exit_sweeps=len(paths), navigation_envelopes=len(checks),
        local_unprotected_directions_after=0, actual_world_written=False,
        final_current_world_freeze_and_native_review_pending=True))
    print('Two-cell preview verified;', len(paths), 'full-width sweeps;', len(checks), 'nav envelopes')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('frozen', 'navigation', 'regression', 'source', 'output'):
        p.add_argument('--'+n, type=Path, required=True)
    run(p.parse_args())
