"""Guard the measured outside corner of the existing B1 rear-lift landing."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from query_blocks import read_box, iter_block_entities
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from repair_r53_long_stair_guard import install
from repair_r53_reported_landings import DIM, FLOOR


def plan(frozen, report, output):
    directions = {(6,-541,258): ('west',),
                  (6,-541,259): ('west','south'),
                  (7,-541,259): ('south',)}
    expected = {((6,-541,258),(5,-541,258)),
                ((6,-541,259),(5,-541,259)),
                ((6,-541,259),(6,-541,260)),
                ((7,-541,259),(7,-541,260))}
    evidence = json.loads(report.read_text('utf8'))
    assert not evidence['unknown_shapes']
    observed = evidence['drop_candidates']
    assert {(tuple(r['cell']),tuple(r['to'])) for r in observed} == expected
    lo,hi = (3,-546,253),(17,-537,265)
    cells = read_box(frozen,DIM,lo,hi)
    tags = dict(iter_block_entities(frozen,DIM,lo,hi))
    assert cells[6,-540,258] == 'minecraft:polished_blackstone_button[face=wall,facing=south,powered=false]'
    assert all(cells[x,-541,257] == 'projectseele:lift_door_interlock_r53' for x in range(7,12))
    rows = []
    for p,sides in directions.items():
        assert cells[p] == 'minecraft:air' and p not in tags
        assert cells[p[0],p[1]-1,p[2]] == FLOOR
        state = 'projectseele:nerv_edge_rail[' + ','.join(
            side+'='+str(side in sides).lower() for side in ('east','north','south','west'))+']'
        rows.append(dict(pos=p,before=cells[p],after=state,before_nbt=None,after_nbt=None,
                         reason='supported_outer_edge_of_existing_rear_lift_call_landing'))
    m = MeasuredWorld(frozen);m.box(lo,hi);m.load()
    class Candidate:
        world = frozen
        def block(self,q):
            return next((r['after'] for r in rows if tuple(r['pos']) == tuple(q)),m.block(q))
        def get(self,x,y,z):return self.block((x,y,z))
    before,after = ActualGeometry(m),ActualGeometry(Candidate())
    def centre(q):return(q[0]+.5,q[1],q[2]+.5)
    for a,b in expected:
        assert before.clear(centre(a),target=centre(b)) == 'CLEAR'
        assert after.clear(centre(a),target=centre(b)) == 'ACTUAL_BODY_OBSTRUCTION'
    for p in directions:assert after.standing(centre(p)) == 'STATIC_STANDING'
    # The original two-row landing, doorway and access to the wall button
    # remain usable; only travel over the unsupported perimeter is blocked.
    paths = [((x,-541,z),(x+1,-541,z)) for z in (258,259) for x in range(6,13)]
    paths += [((x,-541,258),(x,-541,259)) for x in range(6,14)]
    for a,b in paths:
        assert before.clear(centre(a),target=centre(b)) == 'CLEAR'
        assert after.clear(centre(a),target=centre(b)) == 'CLEAR'
    assert not before.unknown and not after.unknown
    output.mkdir(parents=True,exist_ok=False)
    inverse=[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt']) for r in rows]
    for name,data in [('EXACT_DELTA.json.gz',rows),('INVERSE_DELTA.json.gz',inverse),
                      ('POSITIVE_EDIT_MASK.json.gz',[r['pos'] for r in rows])]:
        (output/name).write_bytes(gzip.compress(json.dumps(data).encode(),mtime=0))
    (output/'PLAN.json').write_text(json.dumps(dict(frozen=str(frozen),
        source_report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
        purpose='Existing rear lift B1 call landing, outside the Z257 door and Z255 cabin planes',
        changed_cells=len(rows),before_unguarded_directions=4,after_unguarded_directions=0,
        retained_full_width_crossings=len(paths),door_and_button_unchanged=True,
        world_written=False),indent=2),'utf8')
    print('Planned three supported rails; four drop directions closed; all22 landing crossings retained')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frozen',type=Path);p.add_argument('--report',type=Path)
    p.add_argument('--world',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    install(a.world,a.output) if a.apply else plan(a.frozen,a.report,a.output)
