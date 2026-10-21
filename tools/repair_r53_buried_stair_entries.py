"""Restore level landings over five observed buried first stair rows.

The authored flight and its upper landing stay fixed. An existing stair whose
entire top is at the approach floor becomes that same floor, removing its
half-block depression. This is not an automatic repair of arbitrary stairs.
"""
import argparse
import gzip
import json
import math
from pathlib import Path
from query_blocks import read_box, iter_block_entities
from repair_r53_long_stair_guard import install
from repair_r53_reported_landings import DIM, FLOOR
from prepare_school_hakone_native_r45 import ActualGeometry
from measure_world_r40 import properties
from station_sign_readers_r44 import NORMAL


def plan(frozen, report, output):
    observed = {(3,-528,z) for z in range(266,269)} | {(56,-528,z) for z in range(266,269)}
    observed |= {(x,-486,z) for x in (5,55) for z in range(268,271)}
    observed |= {(x,-458,301) for x in range(5,8)}
    findings = [row for flight in json.loads(report.read_text('utf8'))['flights']
                for row in flight['buried_first_treads']]
    assert {tuple(r['first_tread']) for r in findings} == observed
    cells, tags, rows = {}, {}, []
    for r in findings:
        x,y,z = q = tuple(r['first_tread'])
        lo,hi = (x-4,y-2,z-4),(x+4,y+6,z+4)
        cells.update(read_box(frozen,DIM,lo,hi))
        tags.update(dict(iter_block_entities(frozen,DIM,lo,hi)))
    for r in findings:
        q = tuple(r['first_tread'])
        assert cells[q] == r['stair_state'] and q not in tags
        assert r['floor_state'] == FLOOR and r['covered_height'] == 1
        rows.append(dict(pos=q,before=cells[q],after=FLOOR,before_nbt=None,after_nbt=None,
                         reason='observed_buried_first_tread_becomes_level_approach_floor'))
    proposed = cells | {tuple(r['pos']):r['after'] for r in rows}
    class View:
        world = frozen
        def __init__(self, states):self.states=states
        def get(self,x,y,z):return self.states.get((math.floor(x),math.floor(y),math.floor(z)))
        def block(self,q):return self.get(*q)
    before,after = ActualGeometry(View(cells)),ActualGeometry(View(proposed))
    def height(g,x,z,y):
        tops=[]
        for Y in range(y-1,y+3):
            q=(math.floor(x),Y,math.floor(z))
            boxes=g.boxes(q)
            assert boxes is not None,(q,g.unknown)
            for b in boxes:
                if q[0]+b[0]<=x<=q[0]+b[3] and q[2]+b[2]<=z<=q[2]+b[5]:
                    tops.append(Y+b[4])
        assert tops,(x,z,y)
        return max(tops)
    profiles=[]
    for r in findings:
        x,y,z=r['first_tread'];dx,dz=NORMAL[properties(r['stair_state'])['facing']]
        old,new=[],[];clear=[]
        for offset in (-.14,0,.14):
            sequence=[]
            for step in range(25):
                d=-1.2+step*.1
                px,pz=x+.5+dx*d+dz*offset,z+.5+dz*d-dx*offset
                prior=height(before,px,pz,y);now=height(after,px,pz,y)
                sequence.append(now);old.append(prior);new.append(now)
                foot=max(height(after,px+ox,pz+oz,y) for ox in (-.29,0,.29) for oz in (-.29,0,.29))
                status=after.clear((px,foot,pz))
                assert status=='CLEAR',((px,foot,pz),status)
                clear.append(status)
            assert all(0<=b-a<=.501 for a,b in zip(sequence,sequence[1:])),sequence
        assert min(old)<y+1 and min(new)>=y+1
        profiles.append(dict(first_tread=r['first_tread'],before=old,after=new,
                             clear_full_body_samples=len(clear),maximum_riser=.5))
    output.mkdir(parents=True,exist_ok=False)
    (output/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    (output/'ENTRY_PROFILES.json').write_text(json.dumps(profiles,indent=2),'utf8')
    (output/'PLAN.json').write_text(json.dumps(dict(frozen=str(frozen),source_report=str(report),
        observed_flights=5,changed_cells=len(rows),full_body_samples=sum(r['clear_full_body_samples'] for r in profiles),
        complete_flight_width=3,removed_approach_dips=15,world_written=False),indent=2),'utf8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen',type=Path);parser.add_argument('--report',type=Path)
    parser.add_argument('--world',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    install(args.world,args.output) if args.apply else plan(args.frozen,args.report,args.output)
