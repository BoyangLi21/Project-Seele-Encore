"""Exact cold downward MOVE1 full-world checkpoint/new observation lease; no recovery/write/JVM."""
from pathlib import Path
import argparse,copy,sqlite3
import nbtlib
import prepare_city_atomic_binding_r45 as base
import prepare_city_qa_copy_r45 as qa
import install_city_rigid_metadata_r45 as metadata
from release_combat_r36 import guard
from checkpoint_city_inflight_ready_r45 import entities,uid,image_ok
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,palette_state
from measure_city_placements_r45 import unpack_pos
ROOT=base.ROOT;ART=base.ART
OUT=ART/'city_atomic_integration_r45/qa_ground2_motion_resume_revision_v1'
FROZEN=ART/'city_transport_xhigh_r45/ground_contract2_roundtrip_v1/move591_after_oracle_frozen_v1/index.json'
OLD=ART/'city_transport_xhigh_r45/ground_bidirectional_source_v2/actual_endpoint312_cold_v1/readback.json'
PREVIOUS=ART/'city_atomic_integration_r45/qa_ground_contract2_roundtrip_revision_v1/native_roundtrip_v1/native_binding.json'

def verify_control(root,expected,world_id,journey):
    assert metadata.same_tag(nbtlib.Compound(root),nbtlib.parse_nbt(expected))
    t=root['data'];assert str(t['Phase'])=='MOVE'and int(t['MotionTick'])==591 and float(t['Progress'])>0 and float(t['Progress'])<1
    assert int(t['WorldTouched'])==1 and int(t['SavedPlans'])==int(t['Created'])==96 and int(t['Index'])==int(t['Cursor'])==0
    assert int(t['Depth'])==int(t['JourneySourceDepth'])==312 and int(t['Target'])==int(t['JourneyTargetDepth'])==0 and int(t['Queued'])==-1
    assert not bool(t['Rollback'])and not bool(t['AllowMissingRecovery'])and not str(t['Fault'])
    assert str(t['WorldUUID'])==world_id and int(t['Origin'])==8246338109520 and uid(t['Journey'])==journey and len(t['JournalSHA256s'])==96
    return t

def audit(out):
    guard();assert out.parent==OUT and not out.exists();out.mkdir(parents=True)
    previous=base.read(PREVIOUS);frozen=base.read(FROZEN);old=base.read(OLD);target=Path(previous['world'])
    receipt=base.read(previous['copy_receipt']['path']);source=Path(receipt['source_world']);copyplan=base.read(receipt['copy_plan']['path'])
    with qa.cold_source(source)as source_lock,qa.cold_source(target)as qa_lock:
        source_files=qa.inventory(source,source_lock);current=qa.inventory(target,qa_lock)
        assert source_files=={r['relative']:r['sha256']for r in copyplan['files']}
        assert current==frozen['complete_actual_file_epoch'],'Current MOVE1 world bytes drifted after original frozen failure'
        control=Path(frozen['control_current']['path']);qa.check_ref(frozen['control_current']);qa.check_ref(frozen['control_frozen'])
        root=nbtlib.load(control);tag=verify_control(root,frozen['complete_typed_snbt'],previous['world_id'],frozen['journey_uuid'])
        snapshot=out/'control.before.dat';snapshot.write_bytes(control.read_bytes())
        originals,old_owners=entities(source);actual,owners=entities(target);assert not old_owners and len(originals)==897 and len(actual)==993 and len(owners)==96
        assert all(actual.get(k)==v for k,v in originals.items())and set(actual)-set(originals)==set(owners)
        actors=out/'actor_identity_readback.json';base.write(actors,dict(original_uuid_to_type=originals,current_uuid_to_type=actual,moving_owner_uuids=sorted(owners)))
        rows={Path(r['current']['path']).resolve():r for r in frozen['journals350']};plans=[];retained=[];prefix={};core_positions=set();cells=bes=0
        # Prior completed depth0 final images are the actual starting state, not the original depth312 static alone.
        for row in old['current_original96_journals']:
            plan=nbtlib.load(row['frozen_original']['path'])
            for stage in range(4):
                for op in plan[f'Ops{stage}']:
                    image=op['After'];prefix[unpack_pos(int(op['Pos']))]=(palette_state(image['State']),image['Data'].snbt()if 'Data'in image else None)
            if 'Core'in plan:core_positions.add(unpack_pos(int(plan['Core'])))
        for index in range(96):
            path=control.parent/'city_rigid_journal_r45'/frozen['journey_uuid']/f'{index}.dat';row=rows[path.resolve()]
            qa.check_ref(row['current']);qa.check_ref(row['frozen_original']);plan=nbtlib.load(row['frozen_original']['path'])
            assert int(plan['Index'])==index and row['current']['sha256']==str(tag['JournalSHA256s'][index])
            assert uid(plan['Journey'])==frozen['journey_uuid']and str(plan['WorldUUID'])==previous['world_id']
            actor=frozen['owners96'][index];qa.check_ref(actor['full_entity_snapshot']);entity=nbtlib.load(actor['full_entity_snapshot']['path']);key=uid(plan['Owner'])
            assert key==actor['owner_uuid']and metadata.same_tag(nbtlib.Compound(entity),owners[key]['tag'])and not entity.get('Passengers')
            cells+=len(plan['Cells']);bes+=sum('Data'in c for c in plan['Cells']);plans.append(dict(index=index,**row))
            for stage in (0,1):
                for op in plan[f'Ops{stage}']:
                    image=op['After'];prefix[unpack_pos(int(op['Pos']))]=(palette_state(image['State']),image['Data'].snbt()if 'Data'in image else None)
        for path,row in rows.items():
            qa.check_ref(row['current']);qa.check_ref(row['frozen_original'])
            if path.parent.name!=frozen['journey_uuid']:retained.append(row)
        assert cells==749242 and bes==1471 and len(retained)==254 and len(prefix)==1499312 and len(core_positions)==64
        assert set(rows)=={p.resolve()for p in (control.parent/'city_rigid_journal_r45').rglob('*')if p.is_file()}
        history=base.read(previous['binding_plan']['path']);manifest=base.read(history['metadata_manifest']['path'])
        assert len(manifest['operations'])==807 and all(base.sha(target/r['target'])==r['after_sha256']for r in manifest['operations'])
        db=sqlite3.connect((Path(history['journal'])/'cells.sqlite').resolve().as_uri()+'?mode=ro&immutable=1',uri=True);states=dict(db.execute('select id,value from states'))
        measured=MeasuredWorld(target)
        for cx,cz,sy in db.execute('select distinct cx,cz,sy from cells'):measured.selected[cx,cz].add(sy)
        for q in prefix:measured.around(q,0)
        for q in core_positions:measured.around(q,0)
        measured.load();lo=(min(x for x,z in measured.selected)*16,min(min(v)for v in measured.selected.values())*16,min(z for x,z in measured.selected)*16)
        hi=(max(x for x,z in measured.selected)*16+15,max(max(v)for v in measured.selected.values())*16+15,max(z for x,z in measured.selected)*16+15)
        tags=dict(iter_block_entities(target,'projectseele:geofront',lo,hi,selected_chunks=set(measured.selected)));errors=[];count=overlap=0
        for cx,cz,sy,off,state_id,snbt in db.execute('select cx,cz,sy,off,a,an from cells'):
            q=(cx*16+(off&15),sy*16+(off>>8),cz*16+((off>>4)&15));count+=1
            if q in prefix:overlap+=1;continue
            state=states[state_id]
            if q in core_positions:assert 'armed=true'in state
            if not image_ok(measured,tags,q,state,snbt):errors.append(dict(pos=q,scope='UNCHANGED_BASE_OR_EXPLICIT_SOURCE0_CORE',expected=state,actual=measured.block(q)))
        db.close();assert count==2859160
        for q,(state,snbt)in prefix.items():
            if not image_ok(measured,tags,q,state,snbt):errors.append(dict(pos=q,scope='PRIOR_COMPLETED0_PLUS_NEW_COMMITTED_DETACH',expected=state,actual=measured.block(q)))
        readback=out/'complete_static_and_owned_prefix_readback.json';base.write(readback,dict(base_static_rows=count,base_rows_covered_by_runtime_prefix=overlap,
            complete_runtime_prefix_coordinates=len(prefix),errors=errors,expected_images_derived_only_from_prior_completed96_and_current_original96_journals=True,world_written=False))
        assert not errors,'Full MOVE1 static/prefix differs; no lease'
        assert qa.inventory(source,source_lock)==source_files and qa.inventory(target,qa_lock)==current
        proof=dict(schema='projectseele.city-qa-cold-inflight-motion-checkpoint-r45.v2',role='QA_ONLY',world=str(target),source_world=str(source),world_id=previous['world_id'],world_seed=previous['world_seed'],
            phase='MOVE',WorldTouched=True,Created=96,SavedPlans=96,MotionTick=591,Progress=float(tag['Progress']),source_depth=312,target_depth=0,journey_uuid=frozen['journey_uuid'],
            source1736_exact=True,all_original_journal_bytes_retained=True,original_journal_count=350,previous_settled_journey=old['journey_uuid'],all96_actual_owner_full_cargo_NBT_equal=True,full_cargo_cells=cells,full_BE=bes,
            complete_static2859160_and_owned_prefix_passed=True,complete_metadata807_passed=True,original_actor_ids=897,current_actor_ids=993,original_actor_ids_preserved=True,
            current_control=dict(**base.ref(control),complete_typed_snbt=root.snbt()),frozen_control=base.ref(snapshot),frozen_move1_authority=base.ref(FROZEN),
            current_original96_journals=plans,retained_original_journals=retained,original96_owner_snapshots=frozen['owners96'],actor_identity_readback=base.ref(actors),
            complete_static_and_prefix_readback=base.ref(readback),original_copy_receipt=previous['copy_receipt'],native_process_receipt=frozen['native_process_receipt'],
            current_files=[dict(relative=k,sha256=v)for k,v in sorted(current.items())],no_unplaced_fault_recovery=True,no_QA_progress_for_delivery=True,world_written=False,Java_started=False,native_passed=False)
        base.write(out/'checkpoint.json',proof)
    print('Strict actual MOVE1/254/full96 checkpoint complete; locks released:',base.ref(out/'checkpoint.json'))

def ready(checkpoint_file,compiled_file,out):
    guard();c=base.read(checkpoint_file);compiled=base.read(compiled_file);assert c['schema']=='projectseele.city-qa-cold-inflight-motion-checkpoint-r45.v2'and compiled['passed']
    for row in [*compiled['source_epoch'],*compiled['classes']]:qa.check_ref(row)
    previous=base.read(PREVIOUS);receipt=base.read(previous['copy_receipt']['path']);copyplan=base.read(receipt['copy_plan']['path'])
    with qa.cold_source(Path(c['source_world']))as s,qa.cold_source(Path(c['world']))as q:
        assert qa.inventory(Path(c['source_world']),s)=={r['relative']:r['sha256']for r in copyplan['files']}
        assert qa.inventory(Path(c['world']),q)=={r['relative']:r['sha256']for r in c['current_files']}
    assert out.parent==OUT and not out.exists();out.mkdir()
    revision=out/'runtime_revision.json';base.write(revision,dict(schema='projectseele.city-inflight-MOVE1-observation-revision-r45.v1',checkpoint=base.ref(checkpoint_file),compiled_proof=base.ref(compiled_file),
        tool=base.ref(Path(__file__)),same_original_journey_no_request_or_recover=True,world_written=False,Java_started=False))
    lease=copy.deepcopy(previous)
    for key in ('qa_checkpoint','qa_inflight_checkpoint','qa_settled_checkpoint','qa_inflight_move1_checkpoint','qa_ground_compensated_checkpoint'):lease.pop(key,None)
    lease.update(qa_inflight_move1_checkpoint=base.ref(checkpoint_file),runtime_revision=base.ref(revision),runtime_compiled_proof=base.ref(compiled_file),
        source_epoch=[*compiled['source_epoch'],*compiled['classes'],base.ref(compiled_file),base.ref(Path(__file__))],world_files=[r for r in c['current_files']if r['relative']!='session.lock'],preworld_receipt_output=str(out/'preworld_admission.json'))
    base.write(out/'native_binding.json',lease)
    for kind in ('control','quality'):
        job=base.read(PREVIOUS.parent/f'restore_all96.{kind}.json')
        for key in ('settled_endpoint_trip','expected_previous_journey','unplaced_fault_recovery','inflight_ready_resume','ground_compensated_move1_resume','collider_oracle_receipt','await_collider_oracle','settled_relogin'):job.pop(key,None)
        job.update(candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=base.sha(out/'native_binding.json'),expected_source_endpoint=312,expected_original_journey=c['journey_uuid'],expected_previous_journey=c['previous_settled_journey'])
        if kind=='control':job.update(request_on_start=False,inflight_move1_resume=base.ref(checkpoint_file),expected_original_journey=c['journey_uuid'],terrain_block_witness_output=str(out/'first_stock_blocked_fact.json'))
        else:job.update(mode='resume_roundtrip',endpoint_depth=312,timeout_ticks=18000,write_progress_diagnostics=True,output=str(out/'restore_all96_result'))
        base.write(out/f'restore_all96.{kind}.json',job)
    base.write(out/'launch_properties.json',dict(properties=[f'-Dprojectseele.nativeCandidateBindingR45={(out/"native_binding.json").as_posix()}',f'-Dprojectseele.nativeCandidateBindingR45SHA256={base.sha(out/"native_binding.json")}',
        f'-Dprojectseele.nativeCandidateAdmissionR45={(out/"preworld_admission.json").as_posix()}'],extra_properties=base.read(ROOT/'artifacts/rebuild_r45/city_transport_xhigh_r45/balanced_union_production_v1/patches_v1/PATCH_RECEIPT.json')['root_opt_in_properties'],preworld_receipt_must_be_actual_not_prepared=True,MC_started=False))
    print('New original MOVE1 observation lease prepared:',base.ref(out/'native_binding.json'))
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--action',choices=('audit','ready'),default='audit');ap.add_argument('--checkpoint',type=Path);ap.add_argument('--compiled-proof',type=Path);a=ap.parse_args()
    if a.action=='audit':audit(a.out.resolve())
    else:assert a.checkpoint and a.compiled_proof;ready(a.checkpoint.resolve(),a.compiled_proof.resolve(),a.out.resolve())
if __name__=='__main__':main()
