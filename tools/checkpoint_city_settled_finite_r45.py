"""Reuse a full actual cold readback for a finite depth0/312 settled lease; never write a world."""
from pathlib import Path
import argparse,copy,json
import nbtlib
import prepare_city_atomic_binding_r45 as base
import prepare_city_qa_copy_r45 as qa
import install_city_rigid_metadata_r45 as metadata
from checkpoint_city_inflight_ready_r45 import entities,uid
from checkpoint_city_settled_endpoint_r45 import verify_control as verify_original_zero
ROOT=base.ROOT;ART=base.ART
OUT=ART/'city_atomic_integration_r45/qa_ground_contract2_roundtrip_revision_v1'
PREVIOUS=ART/'city_atomic_integration_r45/qa_ground_compensated_revision_v1/native_compensated_move1_v1/native_binding.json'
FROZEN=ART/'city_transport_xhigh_r45/ground_bidirectional_source_v2/compensated_move1_frozen_v1/index.json'
DATA='dimensions/projectseele/geofront/data/'

def without_lock(files):return {k:v for k,v in files.items()if k!='session.lock'}
def verify_control(root,world_id,journey,endpoint):
    assert endpoint in (0,312)
    for key,value in dict(Depth=endpoint,Target=endpoint,JourneySourceDepth=312-endpoint,JourneyTargetDepth=endpoint).items():
        assert type(root['data'][key])is nbtlib.Int and int(root['data'][key])==value,key
    normalized=copy.deepcopy(root)
    for key,value in dict(Depth=0,Target=0,JourneySourceDepth=312,JourneyTargetDepth=0).items():normalized['data'][key]=nbtlib.Int(value)
    verify_original_zero(normalized,world_id,journey)
    return root['data']

def journal_rows(readback):
    rows=readback['current_original96_journals'];assert len(rows)==96
    prior=readback.get('retained_original_journals',readback.get('prior_original158_journals',[]));old=[]
    for row in prior:
        frozen=row.get('existing_frozen_original',row.get('frozen_original'));assert frozen
        old.append(dict(current=row['current'],existing_frozen_original=frozen))
    total=len(rows)+len(old);assert total>=158 and (total-62)%96==0
    return rows,old,total

def validate_readback(readback):
    schema=readback['schema']
    if schema=='projectseele.city-settled-endpoint312-cold-readback-r45.v1':
        endpoint=312;assert readback['native_retraction_passed']and readback['complete254_original_journals_unchanged']
    elif schema=='projectseele.city-settled-endpoint-cold-readback-r45.v2':
        endpoint=readback['depth'];assert readback['native_travel_passed']and readback['all_original_journal_bytes_retained']
    else:raise AssertionError('Use an actual complete finite endpoint cold readback')
    assert endpoint in (0,312)and readback['cold_static_endpoint_passed']and not readback['errors']
    assert readback['full_cargo_cells']==749242 and readback['complete_BE']==1471 and readback['full_original_static_rows']==2859160
    assert readback['metadata807_scope']==807 and readback['all807_metadata_original_bytes_unchanged']
    assert readback['source1736_original_copyplan_all_bytes_unchanged']and readback['no_moving_city_owner']
    assert readback['original_all_dimension_actor_ids']==readback['current_actor_ids']==897
    assert not readback['lost_original_actor_ids']and not readback['added_actual_actor_ids']and not readback['actor_types_changed']
    return endpoint

def audit(readback_file,out):
    assert out.parent==OUT and not out.exists();readback=base.read(readback_file);endpoint=validate_readback(readback)
    previous=base.read(PREVIOUS);receipt=base.read(previous['copy_receipt']['path']);copyplan=base.read(receipt['copy_plan']['path'])
    complete_file=Path(readback['native_complete']['path']);process_file=Path(readback['native_process_receipt']['path'])
    qa.check_ref(readback['native_complete']);qa.check_ref(readback['native_process_receipt']);qa.check_ref(readback['control'])
    complete=base.read(complete_file);process=base.read(process_file)
    assert complete['passed']and not complete['helper_replacement']and complete['actual_existing_city_objects']==96
    assert complete['phase']=='IDLE'and complete['depth']==endpoint and complete['motion_tick']==724 and complete['journey_uuid']==readback['journey_uuid']
    assert process['process_exit']==0 and process['stop_reason']=='native_complete'and not process['forced_termination']and process['process_and_output_gate']
    assert process['complete_present']and not process['failure_present']
    source=Path(receipt['source_world']);target=Path(previous['world']);new,old,total=journal_rows(readback)
    if readback['schema'].endswith('.v1'):assert total==254
    else:assert total==readback['original_journal_count']
    out.mkdir(parents=True)
    with qa.cold_source(source)as source_lock,qa.cold_source(target)as target_lock:
        source_files=qa.inventory(source,source_lock);current=qa.inventory(target,target_lock)
        assert source_files=={r['relative']:r['sha256']for r in copyplan['files']},'Protected source1736 changed'
        assert without_lock(current)==without_lock(readback['world_file_epoch']),'World bytes changed since full physical endpoint proof; do not fake a fresh readback'
        control=target/(DATA+'projectseele_city_rigid_control_r45_8246338109520.dat');root=nbtlib.load(control)
        tag=verify_control(root,previous['world_id'],readback['journey_uuid'],endpoint)
        assert base.sha(control)==readback['control']['sha256']and metadata.same_tag(nbtlib.Compound(root),nbtlib.parse_nbt(readback['complete_typed_snbt']))
        snapshot=out/'control.before.dat';snapshot.write_bytes(control.read_bytes())
        original_ids,source_owners=entities(source);actual_ids,owners=entities(target)
        assert len(original_ids)==len(actual_ids)==897 and original_ids==actual_ids and not source_owners and not owners
        actors=out/'actor_identity_readback.json';base.write(actors,dict(original_uuid_to_type=original_ids,current_uuid_to_type=actual_ids,moving_owner_uuids=[],all_dimensions=True))
        cells=bes=0
        for index,row in enumerate(new):
            qa.check_ref(row['current']);qa.check_ref(row['frozen_original']);plan=nbtlib.load(row['frozen_original']['path'])
            assert row['index']==index and row['current']['sha256']==row['frozen_original']['sha256']==str(tag['JournalSHA256s'][index])
            assert int(plan['Index'])==index and uid(plan['Journey'])==uid(tag['Journey'])and str(plan['WorldUUID'])==previous['world_id']and int(plan['Origin'])==8246338109520
            cells+=len(plan['Cells']);bes+=sum('Data'in cell for cell in plan['Cells'])
        assert cells==749242 and bes==1471
        for row in old:
            qa.check_ref(row['current']);qa.check_ref(row['existing_frozen_original']);assert row['current']['sha256']==row['existing_frozen_original']['sha256']
        expected={Path(row['current']['path']).resolve()for row in new+old}
        assert len(expected)==total and expected=={p.resolve()for p in (target/(DATA+'city_rigid_journal_r45')).rglob('*')if p.is_file()}
        assert qa.inventory(source,source_lock)==source_files and qa.inventory(target,target_lock)==current
        base.write(out/'checkpoint.json',dict(schema='projectseele.city-qa-cold-settled-endpoint-checkpoint-r45.v2',role='QA_ONLY',world=str(target),source_world=str(source),
            world_id=previous['world_id'],world_seed=previous['world_seed'],phase='IDLE',depth=endpoint,target_depth=endpoint,MotionTick=724,Progress=1,SavedPlans=96,Created=96,
            journey_uuid=readback['journey_uuid'],source1736_exact=True,complete_city_cargo_passed=True,complete_static2859160_passed=True,complete_metadata807_passed=True,
            full_cargo_cells=cells,full_BE=bes,original_actor_ids=897,current_actor_ids=897,original_actor_ids_preserved=True,no_moving_city_owner=True,
            original_journal_count=total,all_original_journal_bytes_retained=True,current_original96_journals=new,retained_original_journals=old,
            complete_settled_readback=base.ref(readback_file),native_complete=base.ref(complete_file),native_process_receipt=base.ref(process_file),actor_identity_readback=base.ref(actors),
            current_control=dict(**base.ref(control),complete_typed_snbt=root.snbt()),frozen_control=base.ref(snapshot),frozen_inflight_authority=base.ref(FROZEN),
            original_copy_receipt=previous['copy_receipt'],current_files=[dict(relative=k,sha256=v)for k,v in sorted(current.items())],
            no_unplaced_fault_recovery=True,no_QA_progress_for_delivery=True,new_ground_contract2_roundtrip_passed=False,relogin_passed=False,performance_passed=False,world_written=False,Java_started=False))
    print('Finite settled proof complete; both locks released:',base.ref(out/'checkpoint.json'))

def ready(checkpoint_file,compiled_file,out,mode,oracle=False):
    checkpoint=base.read(checkpoint_file);assert checkpoint['schema']=='projectseele.city-qa-cold-settled-endpoint-checkpoint-r45.v2'
    compiled=base.read(compiled_file);assert compiled['schema']=='projectseele.city-preworld-runtime-compiled-proof-r45.v1'and compiled['passed']
    for row in [*compiled['source_epoch'],*compiled['classes']]:qa.check_ref(row)
    target=Path(checkpoint['world']);source=Path(checkpoint['source_world']);receipt=base.read(checkpoint['original_copy_receipt']['path']);copyplan=base.read(receipt['copy_plan']['path'])
    with qa.cold_source(source)as source_lock,qa.cold_source(target)as target_lock:
        assert qa.inventory(source,source_lock)=={r['relative']:r['sha256']for r in copyplan['files']}
        assert qa.inventory(target,target_lock)=={r['relative']:r['sha256']for r in checkpoint['current_files']}
    assert out.parent==OUT and not out.exists();out.mkdir()
    assert mode in ('roundtrip','relogin')and (mode!='roundtrip'or checkpoint['depth']==312)and (not oracle or mode=='roundtrip')
    revision=out/'runtime_revision.json';base.write(revision,dict(schema='projectseele.city-finite-settled-admission-runtime-revision-r45.v2',checkpoint=base.ref(checkpoint_file),compiled_proof=base.ref(compiled_file),
        tool=base.ref(Path(__file__)),mode=mode,fresh_new_ground_contract2_journeys=2 if mode=='roundtrip'else 0,original_journal_count=checkpoint['original_journal_count'],world_written=False,Java_started=False))
    lease=copy.deepcopy(base.read(PREVIOUS))
    for key in ('qa_checkpoint','qa_inflight_checkpoint','qa_inflight_move1_checkpoint','qa_ground_compensated_checkpoint','qa_settled_checkpoint'):lease.pop(key,None)
    lease.update(qa_settled_checkpoint=base.ref(checkpoint_file),runtime_revision=base.ref(revision),runtime_compiled_proof=base.ref(compiled_file),
        source_epoch=[*compiled['source_epoch'],*compiled['classes'],base.ref(compiled_file),base.ref(Path(__file__))],world_files=[r for r in checkpoint['current_files']if r['relative']!='session.lock'],
        preworld_receipt_output=str(out/'preworld_admission.json'))
    base.write(out/'native_binding.json',lease)
    for kind in ('control','quality'):
        job=base.read(PREVIOUS.parent/f'restore_all96.{kind}.json')
        for key in ('unplaced_fault_recovery','inflight_ready_resume','inflight_move1_resume','ground_compensated_move1_resume','expected_original_journey','checkpoint_report','terrain_block_witness_output'):job.pop(key,None)
        job.update(candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=base.sha(out/'native_binding.json'),expected_source_endpoint=checkpoint['depth'],expected_previous_journey=checkpoint['journey_uuid'])
        if kind=='control':job.update(request_on_start=mode=='roundtrip'and not oracle,retract=checkpoint['depth']==0,settled_endpoint_trip=base.ref(checkpoint_file),settled_relogin=mode=='relogin',await_collider_oracle=oracle)
        else:
            job.update(mode=mode,endpoint_depth=checkpoint['depth'],write_progress_diagnostics=True,output=str(out/'restore_all96_result'),timeout_ticks=24000 if mode=='roundtrip'else 2400)
            if oracle:job.update(collider_oracle_receipt=str(out/'full96_collider_oracle_actual.json'),timeout_ticks=36000)
        base.write(out/f'restore_all96.{kind}.json',job)
    if oracle:
        authority_path=ART/'city_transport_xhigh_r45/hatch_failure_v5/native_v6_inflight_frozen_v1/index.json';authority=base.read(authority_path)
        job=dict(schema='projectseele.city-native-collider-oracle-r45.v1',root_reviewed_bound_job=True,world_path=checkpoint['world'],world_uuid=checkpoint['world_id'],seed=checkpoint['world_seed'],
            dimension='projectseele:geofront',origin=8246338109520,journey_uuid=authority['current_journey'],output=str(out/'full96_collider_oracle_actual.json'),
            journals=[dict(index=r['index'],**r['frozen_original'],complete_cells=r['complete_cells'],complete_BE=r['complete_BE'])for r in authority['new96_journals']],
            frozen_authority=base.ref(authority_path),native_executed=False,production_provider_replaced=False)
        base.write(out/'full96_collider_oracle.job.json',job)
    properties=[f'-Dprojectseele.nativeCandidateBindingR45={(out/"native_binding.json").as_posix()}',f'-Dprojectseele.nativeCandidateBindingR45SHA256={base.sha(out/"native_binding.json")}',
                f'-Dprojectseele.nativeCandidateAdmissionR45={(out/"preworld_admission.json").as_posix()}']
    base.write(out/'launch_properties.json',dict(properties=properties,extra_properties=[f'-Dprojectseele.r45CityColliderOracle={(out/"full96_collider_oracle.job.json").as_posix()}']if oracle else [],
        MC_started=False,preworld_receipt_must_be_actual_not_prepared=True,root_should_enable_JFR_and_GC_log=True))
    print('Fresh finite settled single-use lease prepared; no locks held:',base.ref(out/'native_binding.json'))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--action',choices=('audit','ready'),default='audit')
    ap.add_argument('--readback',type=Path);ap.add_argument('--checkpoint',type=Path);ap.add_argument('--compiled-proof',type=Path);ap.add_argument('--mode',choices=('roundtrip','relogin'),default='roundtrip');ap.add_argument('--with-oracle',action='store_true');a=ap.parse_args()
    if a.action=='audit':assert a.readback;audit(a.readback.resolve(),a.out.resolve())
    else:assert a.checkpoint and a.compiled_proof;ready(a.checkpoint.resolve(),a.compiled_proof.resolve(),a.out.resolve(),a.mode,a.with_oracle)
if __name__=='__main__':main()
