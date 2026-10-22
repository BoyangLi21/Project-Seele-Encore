"""One reversible preview for authored upper stairwell and escalator edges."""
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

LO,HI=(2,-486,267),(34,-418,328)


def write(p,v):
    b=json.dumps(v,ensure_ascii=False,indent=2).encode('utf8')
    p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)


def run(a):
    a.output.mkdir(parents=True,exist_ok=False)
    regression=load(a.regression)
    assert regression['passed'] and len(regression['guard_missing_before'])==4 and not regression['guard_missing_after']
    cells=read_box(a.frozen,DIM,LO,HI);tags=dict(iter_block_entities(a.frozen,DIM,LO,HI))
    m=MeasuredWorld(a.frozen);m.box(LO,HI);m.load()
    before=ActualGeometry(m);old=Audit.__new__(Audit);old.m=m;old.g=before
    locations={}
    for z in range(321,324):locations[4,-434,z]=('east',);locations[8,-434,z]=('west',)
    for x in range(5,8):locations[x,-434,320]=('south',)
    for x in range(17,21):locations[x,-422,305]=('south',);locations[x,-422,309]=('north',)
    for z in range(306,309):locations[21,-422,z]=('west',)
    locations[25,-482,271]=('east',);locations[31,-482,271]=('west',)
    vectors={'east':(1,0),'west':(-1,0),'north':(0,-1),'south':(0,1)}
    rows=[];expected=set()
    for p,sides in sorted(locations.items()):
        assert cells[p]=='minecraft:air' and p not in tags,(p,cells[p])
        assert cells[p[0],p[1]-1,p[2]] in ('minecraft:white_concrete','minecraft:black_concrete')
        state='projectseele:nerv_edge_rail['+','.join(side+'='+str(side in sides).lower()
              for side in ('east','north','south','west'))+']'
        rows.append(dict(pos=p,before=cells[p],after=state,before_nbt=None,after_nbt=None,
            reason='supported_upper_floor_perimeter_of_original_stairwell' if p[1]!=-482
                   else 'one_cell_continuation_of_existing_fixed_escalator_side_rail'))
        for side in sides:
            dx,dz=vectors[side];expected.add((p,(p[0]+dx,p[1],p[2]+dz)))
    observed={(tuple(r['cell']),tuple(r['to'])) for p in locations for r in old.drops(p)}
    assert observed==expected,(observed-expected,expected-observed)
    overrides={tuple(r['pos']):r['after'] for r in rows}
    class Candidate:
        world=a.frozen
        def block(self,p):return overrides.get(tuple(p),m.block(p))
        def get(self,x,y,z):return self.block((x,y,z))
    after=ActualGeometry(Candidate());new=Audit.__new__(Audit);new.m=Candidate();new.g=after
    assert not [r for p in locations for r in new.drops(p)]
    assert all(new.status(p)=='STATIC_STANDING' for p in locations)
    # Existing complete stair flights retain their original three lanes and
    # the previously accepted inner foot clearance beside both sloped rails.
    samples=[]
    for step in range(24):
        for offset in (.36,.5,1.5,2.5,2.64):
            samples.append((5+offset,-457+step,301+step+.7))
    for step in range(12):
        for offset in (.36,.5,1.5,2.5,2.64):
            samples.append((27-step+.3,-433+step,306+offset))
    for p in samples:
        assert before.clear(p)==after.clear(p)=='CLEAR',(p,before.clear(p),after.clear(p))
    entries=[]
    for x in (5.36,5.5,6.5,7.5,7.64):
        entries += [((x,-434,324.7),(x,-434,325.6)),((x,-457,299.6),(x,-457,300.6))]
    for z in (306.36,306.5,307.5,308.5,308.64):
        entries += [((16.3,-422,z),(15.4,-422,z)),((28.6,-434,z),(28.3,-434,z)),
                    ((28.3,-433.5,z),(27.8,-433.5,z)),((27.8,-433,z),(27.3,-433,z))]
    for p,q in entries:
        assert before.clear(p,target=q)==after.clear(p,target=q)=='CLEAR',(p,q,before.clear(p,target=q),after.clear(p,target=q))
    # Every native MTR block is read back unchanged; new rails remain on the
    # original fixed floor outside both two-lane escalator footprints.
    mtr={p:s for p,s in cells.items() if s.startswith('mtr:')}
    assert not(set(mtr)&set(overrides))
    escalator_samples=[]
    for base in (26,29):
        for dx in (.36,.5,1.5,1.64):
            for z in (271.25,271.75,272.25,272.75,273.25,273.75):
                p=(base+dx,-482,z)
                assert before.clear(p)==after.clear(p),(p,'Escalator body envelope changed')
                escalator_samples.append(dict(point=p,status=after.clear(p)))
    nav=load(a.frozen/'nerv_routes_r24.json.gz');walk=load(a.frozen/'r53_personnel_walking_graph.json.gz')
    points=[tuple(p) for p in walk['nodes']]
    near=lambda p:any(p[1]==q[1] and max(abs(p[0]-q[0]),abs(p[2]-q[2]))<=1 for q in locations)
    changed_edges=[];checked=0
    for i,j,*_ in walk['walking_edges']:
        p,q=points[i],points[j]
        if not(near(p) or near(q)) or p[1]!=q[1] or max(abs(p[0]-q[0]),abs(p[2]-q[2]))>1:continue
        p1=(p[0]+.5,p[1],p[2]+.5);q1=(q[0]+.5,q[1],q[2]+.5);checked+=1
        old_status=before.clear(p1,target=q1);new_status=after.clear(p1,target=q1)
        if old_status!=new_status:changed_edges.append(dict(a=p,b=q,before=old_status,after=new_status))
    assert not changed_edges,changed_edges
    assert not before.unknown and not after.unknown,(before.unknown,after.unknown)
    patch=a.output/'patch';patch.mkdir()
    inverse=[dict(r,before=r['after'],after=r['before']) for r in rows]
    for name,data in (('EXACT_DELTA.json.gz',rows),('INVERSE_DELTA.json.gz',inverse),
                      ('POSITIVE_EDIT_MASK.json.gz',[r['pos'] for r in rows])):write(patch/name,data)
    write(patch/'PLAN.json',dict(frozen=str(a.frozen.resolve()),changed_cells=len(rows),
        before_unguarded_directions=len(expected),after_unguarded_directions=0,
        stair_full_width_samples=len(samples),stair_entry_exit_sweeps=len(entries),
        unchanged_MTR_blocks=len(mtr),escalator_body_samples=escalator_samples,
        navigation_edges_checked=checked,changed_navigation_edges=changed_edges,
        regression_sha256=hashlib.sha256(a.regression.read_bytes()).hexdigest(),
        source_world_written=False,native_visual_review_required=True,
        purpose='Original declared upper floor beside two original stair wells; continuation of two existing escalator fixed rails',
        installation_requires_current_static_ownership_check=True))
    preview=a.output/'preview';shutil.copytree(a.frozen,preview)
    receipt=a.output/'preview-receipt';receipt.mkdir();shutil.copy2(patch/'EXACT_DELTA.json.gz',receipt/'EXACT_DELTA.json.gz')
    apply(preview,receipt)
    actual=read_box(preview,DIM,LO,HI);after_tags=dict(iter_block_entities(preview,DIM,LO,HI))
    assert {p:(cells[p],s) for p,s in actual.items() if cells[p]!=s}=={tuple(r['pos']):(r['before'],r['after']) for r in rows}
    assert {p:t.snbt() for p,t in tags.items()}=={p:t.snbt() for p,t in after_tags.items()}
    write(a.output/'VERIFIED.json',dict(changed_cells=22,full_local_readback=True,local_cells=len(cells),
        original_full_NBT_count=len(tags),MTR_unchanged=len(mtr),stair_samples=len(samples),
        stair_entry_exit_sweeps=len(entries),native_visual_review_required=True,actual_world_written=False))
    print('Preview verified:',len(rows),'cells;',len(samples),'stair samples;',len(entries),'entry/exit sweeps;',checked,'navigation edges unchanged')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('frozen','regression','output'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
