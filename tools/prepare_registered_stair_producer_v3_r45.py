"""Complete final B2 layout keepout + existing four producer edits; no world write."""
from pathlib import Path
import ast,collections,copy,difflib,gzip,hashlib,json,sys,types
sys.dont_write_bytecode=True
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from prepare_b2_stair_component_r45 import full_body_status
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45';PYRAMID=ART/'pyramid_components_sol_v1';OUT=PYRAMID/'stair_producer_keepouts_v3'
WORLD=ART/'composition_candidates/R45_source_candidate_20261004_v5_01/world'
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def rows(p):return [json.loads(x)for x in gzip.open(p,'rt',encoding='utf8')if x.strip()]
HELPER='''def registered_b2_complete_cells():
    # Keep commissioned components and their exact retired legacy voids.
    # This is a protection mask, never a floor/air-authoring or route permit.
    cells=set()
    # Original west switchback plus the old east axes: retired east upper
    # tread/stringer cells must not be rebuilt by an obsolete hall pass.
    for first,second in ((range(-13,-10),range(-5,-2)),(range(67,70),range(59,62))):
        for xs,count,base,z0,dz in ((first,7,-449,304,1),(second,6,-456,310,-1)):
            for i in range(count):
                for x in xs:
                    for h in (-1,0,1,2,3):cells.add((x,base-i+h,z0+dz*i))
    # Final relocated upper flight: all3 lanes, bearing and1.8m headroom.
    for i in range(7):
        y,z=-449-i,304+i
        for x in range(55,58):
            for h in (-1,0,1,2,3):cells.add((x,y+h,z))
        # Both complete supported side guards, including surviving risers.
        for x in (54,58):
            for h in (-1,0,1,2,3):cells.add((x,y+h,z))
    # Expanded middle platform: complete bearing, all15x3 clear rows and
    # the fourth-row outer screen/north-east roof edge. A centreline is
    # insufficient: stale lower-hall ceiling touches these actual cells.
    for x in range(54,71):
        for z in range(310,315):
            for y in range(-457,-452):cells.add((x,y,z))
    # Six registered final entry-to-same-floor lift approaches. Reserve
    # existing three-cell circulation envelopes including corner joins,
    # bearing and clear headroom; do not infer walkability from this mask.
    approaches=((55,57,303,303,-448),(57,57,291,303,-448),
                (57,84,291,291,-448),(84,84,289,291,-448),
                (84,86,289,289,-448),(86,86,289,309,-448),
                (66,86,309,309,-448),(57,61,304,304,-461),
                (57,57,304,310,-461),(57,66,310,310,-461),
                (66,66,309,310,-461))
    for x0,x1,z0,z1,feet in approaches:
        for x in range(x0-1,x1+2):
            for z in range(z0-1,z1+2):
                for y in range(feet-2,feet+3):cells.add((x,y,z))
    return cells


'''

def producer_run(source,name):
    out=OUT/name;out.mkdir();captured=[]
    class Painter:
        def __init__(self):self.ops=[];self.meta={}
        def match(self,box,before,after,owner):
            assert tuple(box[:3])==tuple(box[3:]);row=dict(pos=list(box[:3]),before=before,after=after,owner=owner);self.ops.append(row);captured.append(row)
        def save_plan(self,name):pass
    ns={'__name__':'r45_nonworld_source_test'};exec(compile(source,name+'.py','exec'),ns)
    ns.update(WORLD=WORLD,OUT=out,MeasuredWorld=lambda:MeasuredWorld(WORLD),v=types.SimpleNamespace(WORLD=WORLD,OUT=out,DIM='projectseele:geofront',Painter=Painter))
    ns['main'](False)
    return captured,read(out/'contract.json')

def main():
    if OUT.exists():assert {p.name for p in OUT.iterdir()}=={'initial_full_body_coverage_failure.json'}
    else:OUT.mkdir()
    receipt=read(WORLD.parent/'composition_v5_readback.json');expected=receipt['full_after_inventory'];assert len(expected)==1736
    def inventory():
        actual={p.relative_to(WORLD).as_posix():sha(p)for p in WORLD.rglob('*')if p.is_file()};assert actual==expected;return actual
    before=inventory();r40=ROOT/'tools/repair_pyramid_junctions_r40.py';source=r40.read_text('utf8');assert 'registered_b2_complete_cells'not in source
    candidate=source.replace('def main(apply=False):',HELPER+'def main(apply=False):',1)
    needle='    def put(q,after,owner):\n        old=w.block(q)\n';assert candidate.count(needle)==1
    replacement="    stair_cells=registered_b2_complete_cells()\n    def put(q,after,owner):\n        old=w.block(q)\n        if q in stair_cells and old!=after:\n            held.append(dict(pos=q,state=old,desired=after,reason='Final registered B2 stairs/platform/bearing/full-width headroom and same-floor approaches'));return\n"
    candidate=candidate.replace(needle,replacement);ast.parse(candidate)
    ns={};exec(compile(HELPER,'complete_keepout_helper','exec'),ns);protected=ns['registered_b2_complete_cells']()
    complete=rows(PYRAMID/'b2_east_complete_stair_v3/forward.jsonl.gz');assert len(complete)==203 and all(tuple(r['pos'])in protected for r in complete)
    current243=rows(PYRAMID/'registered_stair_complete_batch_v2/forward.jsonl.gz');m=MeasuredWorld(WORLD)
    for r in current243:m.around(r['pos'],0)
    lanes=read(PYRAMID/'b2_east_complete_stair_v3/all_six_full_width_half_step_requests.json');approaches=read(PYRAMID/'registered_stair_complete_batch_v2/all6_original_entries_to_same_floor_actual_lift.json')
    points=[p for lane in lanes for p in lane['points']]+[p for row in approaches for p in row['actual_shape_points']]+[[x+.5,-455,z+.5]for x in range(55,70)for z in range(311,314)]
    for p in points:m.around(p,2)
    m.load();assert all(s=='full'for s in m.status.values());assert all(m.block(tuple(r['pos']))==r['after']for r in current243);g=ActualGeometry(m)
    coverage=[]
    from math import floor
    for p in points:
        assert full_body_status(g,p)=='CLEAR'
        envelope={(x,y,z)for x in range(floor(p[0]-.3),floor(p[0]+.3)+1)for z in range(floor(p[2]-.3),floor(p[2]+.3)+1)for y in range(floor(p[1]+1e-6),floor(p[1]+1.8)+1)}
        envelope|={(floor(p[0]),floor(p[1]-1e-6)-h,floor(p[2]))for h in (0,1)}
        assert envelope<=protected,('Missing final component envelope',p,sorted(envelope-protected));coverage.append(dict(feet=p,all_full_body_and_bearing_cells_protected=True))
    for a,b in [(a,b)for row in lanes for a,b in zip(row['points'],row['points'][1:])]+[(a,b)for row in approaches for a,b in zip(row['actual_shape_points'],row['actual_shape_points'][1:])]:
        y=max(a[1],b[1]);envelope={(x,Y,z)for x in range(floor(min(a[0],b[0])-.3),floor(max(a[0],b[0])+.3)+1)for z in range(floor(min(a[2],b[2])-.3),floor(max(a[2],b[2])+.3)+1)for Y in range(floor(y+1e-6),floor(y+1.8)+1)}
        assert envelope<=protected and full_body_status(g,a,b)=='CLEAR'
    bad,bad_contract=producer_run(source,'original_R40_RAM_negative');fixed,contract=producer_run(candidate,'candidate_R40_RAM_positive')
    harmed=[r for r in bad if tuple(r['pos'])in protected];residual=[r for r in fixed if tuple(r['pos'])in protected];assert harmed and not residual
    # Other old R40 objects retain exactly their previous proposed delta.
    assert {(tuple(r['pos']),r['before'],r['after'],r['owner'])for r in bad if tuple(r['pos'])not in protected}=={(tuple(r['pos']),r['before'],r['after'],r['owner'])for r in fixed}
    (OUT/'repair_pyramid_junctions_r40.before.txt').write_bytes(source.encode('utf8'));(OUT/'repair_pyramid_junctions_r40.candidate.txt').write_bytes(candidate.encode('utf8'))
    patch=''.join(difflib.unified_diff(source.splitlines(True),candidate.splitlines(True),fromfile='a/tools/repair_pyramid_junctions_r40.py',tofile='b/tools/repair_pyramid_junctions_r40.py'))
    old=(PYRAMID/'v5_combined_entry_v2/root_templates_combined.forward.patch').read_text('utf8');start=old.index('--- a/tools/guard_pyramid_edges_r23.py');combined=patch+old[start:]
    (OUT/'root_producers_complete_v3.forward.patch').write_bytes(combined.encode('utf8'))
    # Standard complete inverse with old/new headers and +/- swapped.
    import re
    inverse=[]
    for line in combined.splitlines(True):
        if line.startswith('--- a/'):inverse.append(line.replace('--- a/','+++ a/',1))
        elif line.startswith('+++ b/'):inverse[-1],line=line.replace('+++ b/','--- b/',1),inverse[-1];inverse.append(line)
        elif line.startswith('@@ '):
            h=re.match(r'@@ -(\d+(?:,\d+)?) \+(\d+(?:,\d+)?) @@(.*)',line);inverse.append('@@ -'+h[2]+' +'+h[1]+' @@'+h[3]+'\n')
        elif line.startswith('+'):inverse.append('-'+line[1:])
        elif line.startswith('-'):inverse.append('+'+line[1:])
        else:inverse.append(line)
    (OUT/'root_producers_complete_v3.inverse.patch').write_bytes(''.join(inverse).encode('utf8'))
    assert inventory()==before
    write(OUT/'actual_v5_243_full_component_and_R40_replay.json',dict(source_world=str(WORLD),actual_v5_receipt=str(WORLD.parent/'composition_v5_readback.json'),actual_v5_receipt_sha256=sha(WORLD.parent/'composition_v5_readback.json'),full_v5_1736_unchanged=True,all_current243_after_states_actual=True,all203_B2_changed_coords_protected=True,protected_cells=len(protected),all6_half_step_routes_and6_same_floor_approaches_and45_middle_cells_body_bearing_sweeps_protected=True,full_body_and_bearing_points=len(points),original_R40_proposed_destructive_cells=len(harmed),candidate_R40_destructive_cells=0,original_R40_other_objects_delta_exactly_preserved=True,actual_proposals=harmed,protection_held=contract['protected'],world_written=False,Java_MC_started=False,producer_patch_applied=False,fresh_generation_native=False,forward_sha256=sha(OUT/'root_producers_complete_v3.forward.patch'),inverse_sha256=sha(OUT/'root_producers_complete_v3.inverse.patch')))
    print('Prepared complete v3 keepout',len(protected),'cells;',len(harmed),'actual staleR40 proposals held; no world writes.',flush=True)
if __name__=='__main__':main()
