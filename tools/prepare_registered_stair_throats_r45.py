"""Restore complete six registered stair-throat interfaces; no world writer."""
from __future__ import annotations
import argparse,collections,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha,jsonl,gzread
from measure_world_r40 import MeasuredWorld,properties
from prepare_school_hakone_native_r45 import ActualGeometry
from prepare_b2_stair_component_r45 import full_body_status
from query_blocks import AIR,iter_block_entities

def main(out):
    out=out.resolve();assert not out.exists() and not out.is_relative_to(WORLD)
    expected={r['relative']:r['sha256']for r in read(BASELINE)['files']};assert len(expected)==1736
    def inventory():
        result={p.relative_to(WORLD).as_posix():sha(p)for p in WORLD.rglob('*')if p.is_file()};assert result==expected;return result
    before=inventory();m=MeasuredWorld(WORLD);m.box((61,-452,350),(74,-355,369));m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(61,-452,350),(74,-355,369)));geometry=ActualGeometry(m)
    author=ROOT/'artifacts/facility_r23/safety/public_floor_edge_guards';receipt=author/'applied_20260918_193825_519007/receipt.json'
    assert read(receipt)['verified'];ops=gzread(author/'ops.json.gz');owner={tuple(op['box'][:3]):op for op in ops if op['box'][:3]==op['box'][3:]}
    current={};instances=[];failure_count=0
    def full(q):return dict(pos=list(q),state=m.block(q),full_nbt=tags[q].snbt()if q in tags else None)
    for f in range(-449,-365,14):
        datum=f+15;miss=[];before_probes=[]
        for x in(68,69,70):
            for i in range(7):
                y,z=f+8+i,357+i
                assert m.block((x,y,z)).startswith('minecraft:polished_andesite_stairs[facing=south,'),'Registered original tread changed'
                for foot,Z in[(y+.5,z+.1),(y+1,z+.6)]:
                    p=[x+.5,foot,Z];s=full_body_status(geometry,p);before_probes.append(dict(feet=p,status=s))
                    if s!='CLEAR':miss.append(dict(feet=p,status=s));failure_count+=s=='BODY_OBSTRUCTION'
        if miss:
            assert len(miss)==2 and all(p['status']=='BODY_OBSTRUCTION'for p in miss)
            for x in(68,70):
                for y in(datum-1,datum,datum+1):
                    q=x,y,360;old=m.block(q);expected_state='projectseele:nerv_structural_panel'if y==datum-1 else'projectseele:clear_glass'
                    assert old==expected_state and q not in tags and q in owner and owner[q]['state']==old and owner[q]['extra']==['minecraft:air'],('Full R23 original owner/preimage required',q,old)
                    current[q]=dict(pos=list(q),before=old,after='minecraft:air',before_nbt=None,after_nbt=None,owner='r45/registered_stair_complete_throat',source_owner=owner[q]['owner'])
            for x,side in[(67,'east'),(71,'west')]:
                q=x,datum,360;old=m.block(q);assert q not in tags and m.block((x,datum-1,360))=='projectseele:nerv_floor_panel'
                assert old in AIR or old.startswith('projectseele:nerv_edge_rail[')
                fields={k:'false'for k in('east','north','south','west')};fields.update(properties(old));fields[side]='true'
                new='projectseele:nerv_edge_rail['+','.join(k+'='+fields[k]for k in sorted(fields))+']';assert new in geometry.shapes
                if old!=new:current[q]=dict(pos=list(q),before=old,after=new,before_nbt=None,after_nbt=None,owner='r45/registered_stair_supported_throat_boundary',source_owner='Actual last supported corridor floor; original R23 unsafe in-well guard retired')
        instances.append(dict(stair_from_floor=f+1,to_floor=datum,original3_wide_treads21=True,before_full0p6x1p8=before_probes,actual_failed_side_probes=miss,repair_required=bool(miss),native_walk=False,
            whole_interface_before=[full((x,y,z))for x in range(67,72)for y in range(datum-2,datum+3)for z in range(359,364)]))
    assert len(instances)==6 and sum(r['repair_required']for r in instances)==5 and failure_count==10 and len(current)==40
    class Image:
        world=WORLD
        def block(self,q):return current.get(tuple(q),{}).get('after',m.block(q))
        def get(self,x,y,z):return self.block(tuple(map(math.floor,(x,y,z))))
    candidate=ActualGeometry(Image());requests=[]
    for f in range(-449,-365,14):
        for flight,cx,z0,start,dz,facing in [('a',64,364,f,-1,'north'),('b',69,357,f+7,1,'south')]:
            for x in range(cx-1,cx+2):
                points=[]
                for i in range(7):
                    y,z=start+i+1,z0+dz*i;points.extend([[x+.5,y+.5,z+(.9 if facing=='north'else .1)],[x+.5,y+1,z+(.4 if facing=='north'else .6)]])
                clear=[full_body_status(candidate,p)for p in points];sweeps=[full_body_status(candidate,a,b)for a,b in zip(points,points[1:])]
                assert all(s=='CLEAR'for s in clear+sweeps),(f,flight,x,clear,sweeps)
                requests.append(dict(flight=f'R04/{f}/{flight}',lane_x=x,points=points,full0p6x1p8_body=clear,higher_datum_sweeps=sweeps,native_walk=False))
    # Whole wider throat has no inward guard/support; retained north header and
    # south stair landing stay exact. Both side rails sit on existing full floor.
    for row in instances:
        y=row['to_floor']
        if row['repair_required']:
            for x in(68,69,70):
                assert candidate.boxes((x,y-1,360))==[] and candidate.boxes((x,y,360))==[] and candidate.boxes((x,y+1,360))==[]
        for x in(67,71):
            assert candidate.standing([x+.5,y,360.5])=='STATIC_STANDING'
        row['candidate_all3_body_lanes_CLEAR']=True
        row['candidate_complete_inward_R23_guard_retired']=row['repair_required']
        row['retained_north_glass_header_exact']=all(Image().block((x,Y,359))==m.block((x,Y,359))for x in(68,69,70)for Y in(y-1,y,y+1))
    after=inventory();assert before==after;out.mkdir();forward=[current[q]for q in sorted(current)];inverse=[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt'])for r in forward]
    jsonl(out/'forward.jsonl.gz',forward);jsonl(out/'inverse.jsonl.gz',inverse);jsonl(out/'positive_edit_mask.jsonl.gz',[r['pos']for r in forward]);write(out/'all6_original_throat_before_after.json',instances);write(out/'all36_actual_half_step_lane_requests.json',requests)
    jsonl(out/'source1736_before_after.jsonl.gz',[dict(relative=k,before_sha256=v,after_sha256=after[k])for k,v in sorted(before.items())])
    write(out/'original_R23_guard_applied_owner.json',dict(applied_receipt=str(receipt),applied_receipt_sha256=sha(receipt),author_source=str(ROOT/'tools/guard_pyramid_edges_r23.py'),author_source_sha256=sha(ROOT/'tools/guard_pyramid_edges_r23.py'),matched_original_ops=[owner[tuple(r['pos'])]for r in forward if r['source_owner'].startswith('r23/')]))
    write(out/'report.json',dict(source_world=str(WORLD),source1736_SHA_unchanged=True,original_interfaces=6,affected_whole_interfaces=5,source_side_body_failures=10,changes=40,candidate_all12_flights_all36_lanes_504_full_body_probes_CLEAR=True,all468_higher_datum_sweeps_CLEAR=True,all252_original_primary_treads_preserved=True,all_BE_preserved=True,
        original_first_interface_correct_and_not_modified=True,physical_native_walk=False,installed=False,world_written=False,Java_Gradle_MC_started=False,model_modified=False,forward_sha256=sha(out/'forward.jsonl.gz'),inverse_sha256=sha(out/'inverse.jsonl.gz')))
    print('Prepared all5 complete registered stair throats40 cells; original6th correct and retained.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
