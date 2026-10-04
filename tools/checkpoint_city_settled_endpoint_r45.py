"""Fresh cold endpoint0 admission: unchanged complete physical readback plus current897/158 identity checks."""
from pathlib import Path
import argparse, copy, json
import nbtlib
import prepare_city_atomic_binding_r45 as base
import prepare_city_qa_copy_r45 as qa
import install_city_rigid_metadata_r45 as metadata
from checkpoint_city_inflight_ready_r45 import entities, uid

ROOT=base.ROOT; ART=base.ART
OUT=ART/'city_atomic_integration_r45/qa_settled_endpoint_revision_v1'
FROZEN=ART/'city_transport_xhigh_r45/hatch_failure_v5/native_v6_inflight_frozen_v1/index.json'
READBACK=ART/'city_transport_xhigh_r45/hatch_failure_v5/settled_endpoint0_cold_v2/readback.json'
PREVIOUS=ART/'city_atomic_integration_r45/qa_inflight_ready_revision_v1/native_ready_v2/native_binding.json'
COMPLETE=PREVIOUS.parent/'restore_all96_result/complete.json'
PROCESS=PREVIOUS.parent.parent/'native_ready_diagnostic_run_v2/process_receipt.json'
DATA='dimensions/projectseele/geofront/data/'

def without_lock(files):return {k:v for k,v in files.items()if k!='session.lock'}

def verify_control(root,world_id,journey):
    t=root['data']
    integers=dict(Version=1,Depth=0,Target=0,Index=0,Cursor=0,SavedPlans=96,Created=96,MotionTick=724,
                  JourneySourceDepth=312,JourneyTargetDepth=0,Queued=-1)
    for key,value in integers.items():assert type(t[key])is nbtlib.Int and int(t[key])==value,key
    for key,value in dict(WorldTouched=1,Rollback=0,AllowMissingRecovery=0).items():assert type(t[key])is nbtlib.Byte and int(t[key])==value,key
    for key,value in dict(WorldUUID=world_id,Phase='IDLE',Fault='',QueueFault='',MotionProfile='c1_trapezoid_v1').items():assert type(t[key])is nbtlib.String and str(t[key])==value,key
    assert type(root['DataVersion'])is nbtlib.Int and type(t['Origin'])is nbtlib.Long and int(t['Origin'])==8246338109520
    assert type(t['Progress'])is nbtlib.Double and float(t['Progress'])==1
    assert type(t['Journey'])is nbtlib.IntArray and len(t['Journey'])==4 and uid(t['Journey'])==journey
    assert isinstance(t['JournalSHA256s'],nbtlib.List)and t['JournalSHA256s'].subtype is nbtlib.String and len(t['JournalSHA256s'])==96
    return t

def audit(out):
    assert out.parent==OUT and not out.exists();out.mkdir(parents=True)
    previous=base.read(PREVIOUS);readback=base.read(READBACK);frozen=base.read(FROZEN)
    assert readback['schema']=='projectseele.city-settled-endpoint0-cold-readback-r45.v1'and readback['cold_static_endpoint_passed']and readback['single_native_ascent_passed']
    assert not readback['errors']and readback['full_cargo_cells']==749242 and readback['complete_BE']==1471
    assert readback['full_original_static_rows']==2859160 and readback['metadata807_scope']==807 and readback['all807_metadata_original_bytes_unchanged']
    assert readback['original158_journal_SHA_unchanged']and readback['original_all_dimension_actor_ids']==readback['current_actor_ids']==897
    complete=base.read(COMPLETE);process=base.read(PROCESS)
    assert complete['passed']and not complete['helper_replacement']and complete['actual_existing_city_objects']==96
    assert complete['phase']=='IDLE'and complete['depth']==0 and complete['motion_tick']==724 and complete['journey_uuid']==frozen['current_journey']
    assert process['process_exit']==0 and process['stop_reason']=='native_complete'and not process['forced_termination']and process['process_and_output_gate']
    assert process['complete_present']and not process['failure_present']
    target=Path(previous['world']);receipt=base.read(previous['copy_receipt']['path']);source=Path(receipt['source_world']);copyplan=base.read(receipt['copy_plan']['path'])
    with qa.cold_source(source)as source_lock,qa.cold_source(target)as qa_lock:
        source_files=qa.inventory(source,source_lock);current=qa.inventory(target,qa_lock)
        assert source_files=={r['relative']:r['sha256']for r in copyplan['files']},'Protected source1736 changed'
        # Every byte carrying the complete former physical readback must still match; only the OS lock bytes are exempt.
        assert without_lock(current)==without_lock(readback['world_file_epoch']),'Settled physical endpoint bytes changed: require a new full readback'
        control=target/(DATA+'projectseele_city_rigid_control_r45_8246338109520.dat');root=nbtlib.load(control)
        tag=verify_control(root,previous['world_id'],frozen['current_journey'])
        qa.check_ref(readback['control']);assert base.sha(control)==readback['control']['sha256']
        assert metadata.same_tag(nbtlib.Compound(root),nbtlib.parse_nbt(readback['complete_typed_snbt']))
        copy=out/'control.before.dat';copy.write_bytes(control.read_bytes())
        original_ids,source_owners=entities(source);actual_ids,owners=entities(target)
        assert len(original_ids)==len(actual_ids)==897 and original_ids==actual_ids and not source_owners and not owners
        actors=out/'actor_identity_readback.json';base.write(actors,dict(original_uuid_to_type=original_ids,current_uuid_to_type=actual_ids,moving_owner_uuids=[],all_dimensions=True))
        cells=bes=0
        for index,row in enumerate(frozen['new96_journals']):
            qa.check_ref(row['current']);qa.check_ref(row['frozen_original']);plan=nbtlib.load(row['frozen_original']['path'])
            assert row['current']['sha256']==row['frozen_original']['sha256']==str(tag['JournalSHA256s'][index])
            assert int(plan['Index'])==index and uid(plan['Journey'])==uid(tag['Journey'])and str(plan['WorldUUID'])==previous['world_id']and int(plan['Origin'])==8246338109520
            cells+=len(plan['Cells']);bes+=sum('Data'in cell for cell in plan['Cells'])
        assert cells==749242 and bes==1471
        for row in frozen['old62_journals']:qa.check_ref(row['current']);qa.check_ref(row['existing_frozen_original'])
        journals={p.resolve()for p in (target/(DATA+'city_rigid_journal_r45')).rglob('*')if p.is_file()}
        assert journals=={Path(row['current']['path']).resolve()for row in frozen['new96_journals']+frozen['old62_journals']}
        assert qa.inventory(source,source_lock)==source_files and qa.inventory(target,qa_lock)==current
        proof=dict(schema='projectseele.city-qa-cold-settled-endpoint0-checkpoint-r45.v1',role='QA_ONLY',world=str(target),source_world=str(source),
                   world_id=previous['world_id'],world_seed=previous['world_seed'],phase='IDLE',depth=0,target_depth=0,MotionTick=724,Progress=1,SavedPlans=96,Created=96,
                   journey_uuid=frozen['current_journey'],source1736_exact=True,complete_city_cargo_passed=True,complete_static2859160_passed=True,complete_metadata807_passed=True,
                   full_cargo_cells=cells,full_BE=bes,original_actor_ids=897,current_actor_ids=897,original_actor_ids_preserved=True,no_moving_city_owner=True,
                   all158_original_journal_bytes_retained=True,complete_settled_readback=base.ref(READBACK),native_complete=base.ref(COMPLETE),native_process_receipt=base.ref(PROCESS),
                   actor_identity_readback=base.ref(actors),current_control=dict(**base.ref(control),complete_typed_snbt=root.snbt()),frozen_control=base.ref(copy),
                   frozen_inflight_authority=base.ref(FROZEN),current_original96_journals=frozen['new96_journals'],retained_old62_journals=frozen['old62_journals'],
                   original_copy_receipt=previous['copy_receipt'],current_files=[dict(relative=k,sha256=v)for k,v in sorted(current.items())],
                   no_unplaced_fault_recovery=True,no_QA_progress_for_delivery=True,return_trip_passed=False,relogin_passed=False,performance_passed=False,world_written=False,Java_started=False)
        base.write(out/'checkpoint.json',proof)
    print('Fresh strict endpoint0 checkpoint complete; both locks released:',base.ref(out/'checkpoint.json'))

def ready(checkpoint_file,compiled_file,out):
    checkpoint=base.read(checkpoint_file);assert checkpoint['schema']=='projectseele.city-qa-cold-settled-endpoint0-checkpoint-r45.v1'
    compiled=base.read(compiled_file);assert compiled['schema']=='projectseele.city-preworld-runtime-compiled-proof-r45.v1'and compiled['passed']
    for row in [*compiled['source_epoch'],*compiled['classes']]:qa.check_ref(row)
    previous=base.read(PREVIOUS);target=Path(checkpoint['world']);source=Path(checkpoint['source_world']);receipt=base.read(previous['copy_receipt']['path']);copyplan=base.read(receipt['copy_plan']['path'])
    with qa.cold_source(source)as source_lock,qa.cold_source(target)as target_lock:
        assert qa.inventory(source,source_lock)=={r['relative']:r['sha256']for r in copyplan['files']}
        assert qa.inventory(target,target_lock)=={r['relative']:r['sha256']for r in checkpoint['current_files']}
    assert out.parent==OUT and not out.exists();out.mkdir()
    revision=out/'runtime_revision.json';base.write(revision,dict(schema='projectseele.city-settled-endpoint0-admission-runtime-revision-r45.v1',checkpoint=base.ref(checkpoint_file),
        compiled_proof=base.ref(compiled_file),tool=base.ref(Path(__file__)),fresh_retract_request=True,all158_original_journals_retained=True,world_written=False,Java_started=False))
    lease=copy.deepcopy(previous);lease.pop('qa_checkpoint',None);lease.pop('qa_inflight_checkpoint',None)
    lease.update(qa_settled_checkpoint=base.ref(checkpoint_file),runtime_revision=base.ref(revision),runtime_compiled_proof=base.ref(compiled_file),
                 source_epoch=[*compiled['source_epoch'],*compiled['classes'],base.ref(compiled_file),base.ref(Path(__file__))],
                 world_files=[r for r in checkpoint['current_files']if r['relative']!='session.lock'],preworld_receipt_output=str(out/'preworld_admission.json'))
    base.write(out/'native_binding.json',lease)
    for kind in ('control','quality'):
        job=base.read(PREVIOUS.parent/f'restore_all96.{kind}.json');job.pop('unplaced_fault_recovery',None);job.pop('inflight_ready_resume',None);job.pop('expected_original_journey',None)
        job.update(candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=base.sha(out/'native_binding.json'))
        if kind=='control':job.update(request_on_start=True,retract=True,expected_source_endpoint=0,settled_endpoint_trip=base.ref(checkpoint_file),expected_previous_journey=checkpoint['journey_uuid'])
        else:job.update(mode='travel',endpoint_depth=312,write_progress_diagnostics=True,output=str(out/'restore_all96_result'))
        base.write(out/f'restore_all96.{kind}.json',job)
    base.write(out/'launch_properties.json',dict(properties=[f'-Dprojectseele.nativeCandidateBindingR45={(out/"native_binding.json").as_posix()}',
        f'-Dprojectseele.nativeCandidateBindingR45SHA256={base.sha(out/"native_binding.json")}',f'-Dprojectseele.nativeCandidateAdmissionR45={(out/"preworld_admission.json").as_posix()}'],
        MC_started=False,preworld_receipt_must_be_actual_not_prepared=True,root_should_enable_JFR_and_GC_log=True))
    print('Fresh settled endpoint0 single-use retract lease prepared:',base.ref(out/'native_binding.json'))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--action',choices=('audit','ready'),default='audit')
    ap.add_argument('--checkpoint',type=Path);ap.add_argument('--compiled-proof',type=Path);a=ap.parse_args()
    if a.action=='audit':audit(a.out.resolve())
    else:assert a.checkpoint and a.compiled_proof;ready(a.checkpoint.resolve(),a.compiled_proof.resolve(),a.out.resolve())

if __name__=='__main__':main()
