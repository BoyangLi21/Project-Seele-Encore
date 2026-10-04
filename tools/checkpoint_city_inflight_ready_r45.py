"""Audit the exact cold READY/full96 transaction for a new lease; never cancel or write a world."""
from pathlib import Path
from collections import Counter
import argparse,copy,json,sqlite3,sys,uuid
import nbtlib
import prepare_city_atomic_binding_r45 as base
import prepare_city_qa_copy_r45 as qa
import install_city_rigid_metadata_r45 as metadata
from query_blocks import iter_block_entities,palette_state
from measure_world_r40 import MeasuredWorld
from measure_city_placements_r45 import unpack_pos
from transplant_s22_authority import read_region,parse_chunk

ROOT=base.ROOT;ART=base.ART
FROZEN=ART/'city_transport_xhigh_r45/hatch_failure_v5/native_v6_inflight_frozen_v1/index.json'
PREVIOUS=ART/'city_atomic_integration_r45/qa_checkpoint_revision_v1/native_checkpoint_v5/native_binding.json'
OUT=ART/'city_atomic_integration_r45/qa_inflight_ready_revision_v1'

def uid(tag):return str(uuid.UUID(int=sum((int(v)&0xffffffff)<<(96-32*i)for i,v in enumerate(tag))))

def entities(world):
    ids={};owners={};prefix='r45_city_rigid/'
    for path in world.rglob('*.mca'):
        if 'entities'not in path.relative_to(world).parts or path.stat().st_size==0:continue
        for slot,blob in enumerate(read_region(path)[1]):
            if blob is None:continue
            for tag in parse_chunk(blob).get('Entities',[]):
                if 'UUID'not in tag:continue
                key=uid(tag['UUID']);assert key not in ids,'Duplicate actor UUID';ids[key]=str(tag.get('id',''))
                if any(str(t).startswith(prefix)for t in tag.get('Tags',[])):
                    owners[key]=dict(tag=tag,region=path.relative_to(world).as_posix(),slot=slot)
    return ids,owners

def verify_owner(entity,plan,control):
    assert str(entity['id'])=='create:contraption'and uid(entity['UUID'])==uid(plan['Owner'])
    expected=f"r45_city_rigid/{control['WorldUUID']}/{int(control['Origin'])}"
    assert expected in map(str,entity['Tags'])and metadata.same_tag(entity['ForgeData']['R45CityJourney'],control['Journey'])
    cx,cy,cz=unpack_pos(int(plan['Centre']));assert [float(x)for x in entity['Pos']]==[cx+.5,int(plan['SourceY']),cz+.5],'READY owner pose changed'
    assert not entity.get('Passengers'), 'Occupied READY owner needs its own explicit reviewed recovery'
    current=entity['Contraption'];assert str(current['Type'])=='create:pulley'
    palette=current['Blocks']['Palette'];actual=current['Blocks']['BlockList'];cells={int(c['Pos']):c for c in plan['Cells']}
    assert len(actual)==len(cells);seen=set();be=0
    for row in actual:
        key=int(row['Pos']);assert key in cells and key not in seen;seen.add(key);old=cells[key]
        assert metadata.same_tag(palette[int(row['State'])],old['State']),'Current owner cargo state differs from its full original journal'
        assert ('Data'in row)==('Data'in old),'Current owner BE membership differs'
        if 'Data'in old:assert metadata.same_tag(row['Data'],old['Data']),'Current owner full BE changed';be+=1
    return len(cells),be

def image_ok(measured,tags,q,state,snbt):
    if measured.block(q)!=state:return False
    expected=nbtlib.parse_nbt(snbt)if snbt else None
    return metadata.serialized_be_tag_matches(expected,tags.get(q))[0]

def audit(out):
    assert out.parent==OUT and not out.exists();out.mkdir(parents=True);(out/'owners96').mkdir()
    previous=base.read(PREVIOUS);frozen=base.read(FROZEN);target=Path(previous['world']);copy_receipt=base.read(previous['copy_receipt']['path'])
    source=Path(copy_receipt['source_world']);copy_plan=base.read(copy_receipt['copy_plan']['path']);qa.check_ref(copy_receipt['copy_plan'])
    with qa.cold_source(source)as source_lock,qa.cold_source(target)as target_lock:
        source_files=qa.inventory(source,source_lock);current_files=qa.inventory(target,target_lock)
        assert source_files=={r['relative']:r['sha256']for r in copy_plan['files']},'Protected source1736 changed'
        row=frozen['control_current'];qa.check_ref(row);qa.check_ref(frozen['control_frozen']);control_path=Path(row['path'])
        control_root=nbtlib.load(control_path);control=control_root['data'];assert metadata.same_tag(nbtlib.Compound(control_root),nbtlib.parse_nbt(frozen['complete_typed_snbt']))
        assert str(control['Phase'])=='READY'and int(control['WorldTouched'])==1 and int(control['SavedPlans'])==int(control['Created'])==96
        assert int(control['Index'])==int(control['Cursor'])==int(control['MotionTick'])==0 and float(control['Progress'])==0
        assert int(control['Depth'])==int(control['JourneySourceDepth'])==312 and int(control['Target'])==int(control['JourneyTargetDepth'])==0
        assert not str(control['Fault'])and not bool(control['Rollback'])and not bool(control['AllowMissingRecovery'])
        file=out/'control.before.dat';file.write_bytes(control_path.read_bytes());assert base.sha(file)==row['sha256']
        assert str(control['WorldUUID'])==previous['world_id']and uid(control['Journey'])==frozen['current_journey']
        originals,old_owners=entities(source);current,owners=entities(target);assert not old_owners and len(owners)==96
        assert set(originals).issubset(current)and set(current)-set(originals)==set(owners),'Foreign/new/lost actor identities beyond original96 owners'
        prefix={};plans=[];owner_rows=[];cells=0;be=0
        for index,journal in enumerate(frozen['new96_journals']):
            qa.check_ref(journal['current']);qa.check_ref(journal['frozen_original']);plan=nbtlib.load(journal['frozen_original']['path'])
            assert journal['current']['sha256']==str(control['JournalSHA256s'][index])and int(plan['Index'])==index
            assert metadata.same_tag(plan['Journey'],control['Journey'])and str(plan['WorldUUID'])==str(control['WorldUUID'])
            key=uid(plan['Owner']);assert key in owners;entity=owners[key]['tag'];n,b=verify_owner(entity,plan,control);cells+=n;be+=b
            saved=out/'owners96'/f'{index}.dat';nbtlib.File(entity).save(saved,gzipped=True)
            owner_rows.append(dict(index=index,owner_uuid=key,region=owners[key]['region'],slot=owners[key]['slot'],full_entity_snapshot=base.ref(saved),cargo_cells=n,full_BE=b))
            for stage in (0,1):
                for op in plan['Ops'+str(stage)]:
                    q=unpack_pos(int(op['Pos']));value=op['After'];prefix[q]=(palette_state(value['State']),value['Data'].snbt()if 'Data'in value else None)
            plans.append(journal)
        assert cells==749242 and be==1471 and len(owner_rows)==96
        for journal in frozen['old62_journals']:qa.check_ref(journal['current']);qa.check_ref(journal['existing_frozen_original'])
        actual_journals={p.resolve()for p in (control_path.parent/'city_rigid_journal_r45').rglob('*')if p.is_file()}
        assert actual_journals=={Path(r['current']['path']).resolve()for r in frozen['new96_journals']+frozen['old62_journals']}
        historical=base.read(previous['binding_plan']['path']);manifest=base.read(historical['metadata_manifest']['path'])
        assert len(manifest['operations'])==807 and all(base.sha(target/r['target'])==r['after_sha256']for r in manifest['operations'])
        database=Path(historical['journal'])/'cells.sqlite';db=sqlite3.connect(database.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
        selected={};measured=MeasuredWorld(target)
        for cx,cz,sy in db.execute('select distinct cx,cz,sy from cells'):measured.selected[cx,cz].add(sy)
        for q in prefix:measured.around(q,0)
        measured.load();lo=(min(x for x,z in measured.selected)*16,min(min(ys)for ys in measured.selected.values())*16,min(z for x,z in measured.selected)*16)
        hi=(max(x for x,z in measured.selected)*16+15,max(max(ys)for ys in measured.selected.values())*16+15,max(z for x,z in measured.selected)*16+15)
        tags=dict(iter_block_entities(target,'projectseele:geofront',lo,hi,selected_chunks=set(measured.selected)))
        errors=[];static_count=0;overlap=0;states=dict(db.execute('select id,value from states'))
        for cx,cz,sy,off,a,an in db.execute('select cx,cz,sy,off,a,an from cells'):
            q=(cx*16+(off&15),sy*16+(off>>8),cz*16+((off>>4)&15));static_count+=1
            if q in prefix:overlap+=1;continue
            if not image_ok(measured,tags,q,states[a],an):errors.append(dict(pos=q,scope='UNCHANGED_BASE_STATIC',expected=states[a],actual=measured.block(q)))
        db.close();assert static_count==2859160
        for q,(state,snbt)in prefix.items():
            if not image_ok(measured,tags,q,state,snbt):errors.append(dict(pos=q,scope='EXACT_COMMITTED_OPEN_DETACH_PREFIX',expected=state,actual=measured.block(q)))
        base.write(out/'complete_static_and_owned_prefix_readback.json',dict(base_static_rows=static_count,unchanged_base_static_rows=static_count-overlap,
            base_rows_covered_by_runtime_prefix=overlap,complete_runtime_prefix_coordinates=len(prefix),errors=errors,
            original_expected_static_SQL_unchanged=True,runtime_prefix_derived_only_from_full96_original_journals=True,world_written=False))
        assert not errors,'Current static/prefix images differ; do not promote an in-flight lease'
        assert qa.inventory(source,source_lock)==source_files and qa.inventory(target,target_lock)==current_files
        checkpoint=dict(schema='projectseele.city-qa-cold-inflight-ready-checkpoint-r45.v1',role='QA_ONLY',world=str(target),source_world=str(source),
            world_id=previous['world_id'],world_seed=previous['world_seed'],phase='READY',WorldTouched=True,Created=96,SavedPlans=96,MotionTick=0,Progress=0,
            source_depth=312,target_depth=0,journey_uuid=frozen['current_journey'],source1736_exact=True,
            complete96_original_journals_passed=True,all158_original_journal_bytes_retained=True,complete96_original_owner_full_cargo_passed=True,
            full_cargo_cells=cells,full_BE=be,complete_static2859160_and_owned_prefix_passed=True,complete_metadata807_passed=True,
            original_actor_ids=len(originals),current_actor_ids=len(current),original_actor_ids_preserved=True,
            current_control=dict(**row,complete_typed_snbt=control_root.snbt()),frozen_control=base.ref(file),frozen_inflight_authority=base.ref(FROZEN),
            current_original96_journals=frozen['new96_journals'],retained_old62_journals=frozen['old62_journals'],original96_owner_snapshots=owner_rows,
            complete_static_and_prefix_readback=base.ref(out/'complete_static_and_owned_prefix_readback.json'),original_copy_receipt=previous['copy_receipt'],
            previous_used_lease=base.ref(PREVIOUS),previous_native_process_receipt=base.ref(PREVIOUS.parent.parent/'native_city_checkpoint_run_v6/process_receipt.json'),
            current_files=[dict(relative=k,sha256=v)for k,v in sorted(current_files.items())],native_motion_pass=False,performance_pass=False,
            no_unplaced_fault_recovery=True,no_QA_progress_for_delivery=True,world_written=False,Java_started=False)
        base.write(out/'checkpoint.json',checkpoint);print('Strict actual READY/full96 in-flight cold checkpoint complete:',out)

def ready(checkpoint_file,compiled_file,out):
    checkpoint=base.read(checkpoint_file);assert checkpoint['schema']=='projectseele.city-qa-cold-inflight-ready-checkpoint-r45.v1'
    assert checkpoint['phase']=='READY'and checkpoint['WorldTouched']and checkpoint['no_unplaced_fault_recovery']
    compiled=base.read(compiled_file);assert compiled['schema']=='projectseele.city-preworld-runtime-compiled-proof-r45.v1'and compiled['passed']is True
    for row in [*compiled['source_epoch'],*compiled['classes']]:qa.check_ref(row)
    previous=base.read(PREVIOUS);target=Path(checkpoint['world']);source=Path(checkpoint['source_world'])
    receipt=base.read(previous['copy_receipt']['path']);copy_plan=base.read(receipt['copy_plan']['path'])
    with qa.cold_source(source)as source_lock,qa.cold_source(target)as target_lock:
        assert qa.inventory(source,source_lock)=={r['relative']:r['sha256']for r in copy_plan['files']}
        assert qa.inventory(target,target_lock)=={r['relative']:r['sha256']for r in checkpoint['current_files']}
    assert out.parent==OUT and not out.exists();out.mkdir()
    revision=out/'runtime_revision.json';base.write(revision,dict(schema='projectseele.city-inflight-ready-admission-runtime-revision-r45.v1',
        checkpoint=base.ref(checkpoint_file),compiled_proof=base.ref(compiled_file),tool=base.ref(Path(__file__)),
        no_unplaced_fault_recovery=True,original_journey_and_96_owners_preserved=True,all158_original_journals_retained=True,
        stock_collider_readiness_not_bypassed=True,world_written=False,Java_started=False))
    lease=copy.deepcopy(previous);lease.pop('qa_checkpoint',None)
    lease.update(qa_inflight_checkpoint=base.ref(checkpoint_file),runtime_revision=base.ref(revision),runtime_compiled_proof=base.ref(compiled_file),
        source_epoch=[*compiled['source_epoch'],*compiled['classes'],base.ref(compiled_file),base.ref(Path(__file__))],
        world_files=[r for r in checkpoint['current_files']if r['relative']!='session.lock'],preworld_receipt_output=str(out/'preworld_admission.json'))
    base.write(out/'native_binding.json',lease)
    for kind in ('control','quality'):
        job=base.read(PREVIOUS.parent/f'restore_all96.{kind}.json');job.pop('unplaced_fault_recovery',None)
        job.update(candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=base.sha(out/'native_binding.json'))
        if kind=='control':job.update(request_on_start=False,inflight_ready_resume=base.ref(checkpoint_file),expected_original_journey=checkpoint['journey_uuid'])
        else:job.update(write_progress_diagnostics=True,output=str(out/'restore_all96_result'))
        base.write(out/f'restore_all96.{kind}.json',job)
    base.write(out/'launch_properties.json',dict(properties=[f'-Dprojectseele.nativeCandidateBindingR45={(out/"native_binding.json").as_posix()}',
        f'-Dprojectseele.nativeCandidateBindingR45SHA256={base.sha(out/"native_binding.json")}',f'-Dprojectseele.nativeCandidateAdmissionR45={(out/"preworld_admission.json").as_posix()}'],
        MC_started=False,preworld_receipt_must_be_actual_not_prepared=True,root_should_enable_JFR_and_GC_log=True))
    print('Prepared fresh exact READY/full96 lease, not an unplaced recovery:',out)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--action',choices=('audit','ready'),default='audit');ap.add_argument('--checkpoint',type=Path);ap.add_argument('--compiled-proof',type=Path);a=ap.parse_args()
    if a.action=='audit':audit(a.out.resolve())
    else:assert a.checkpoint and a.compiled_proof;ready(a.checkpoint.resolve(),a.compiled_proof.resolve(),a.out.resolve())

if __name__=='__main__':main()
