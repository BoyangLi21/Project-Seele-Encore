"""Audit two cold worlds into a named QA-only checkpoint; never write a world or launch Java."""
from pathlib import Path
from collections import Counter
import argparse, copy, gzip, json, re, sys, uuid
import nbtlib
import prepare_city_qa_copy_r45 as qa
import prepare_city_atomic_binding_r45 as base
import install_city_rigid_metadata_r45 as metadata
import migrate_city_atomic_candidate_r45 as migration
from transplant_s22_authority import read_region,parse_chunk

ROOT=base.ROOT;ART=base.ART
OUT=ART/'city_atomic_integration_r45/qa_checkpoint_revision_v1'
PREVIOUS=ART/'city_atomic_integration_r45/qa_copy_revision_v1/native_copy_v2/native_binding.json'
RETAINED62_AUTHORITY=ART/'city_transport_xhigh_r45/hatch_failure_v5/frozen_authority/index.json'
RETAINED62_CONTROL_SHA256='34e5db818410667436087ba26eb1070cc3dc99eb90e8151003a989682b2b9e8e'

def classify_unplaced_control(root,world_id,retained=False):
    assert isinstance(root,nbtlib.Compound) and isinstance(root.get('data'),nbtlib.Compound),'Missing complete control data'
    tag=root['data']
    count=62 if retained else 0
    integer_fields={'Version':1,'SavedPlans':count,'Created':0,'Index':count,'Cursor':0,'MotionTick':0,
        'Depth':312,'JourneySourceDepth':312,'Target':0,'JourneyTargetDepth':0,'Queued':-1}
    string_fields={'WorldUUID':world_id,'MotionProfile':'c1_trapezoid_v1','Phase':'FAULT','FaultPhase':'PREPARE'if retained else'WAL_WAIT','QueueFault':''}
    for key,value in integer_fields.items():assert type(tag.get(key))is nbtlib.Int and int(tag[key])==value,'Unsafe/missing typed control '+key
    for key,value in string_fields.items():assert type(tag.get(key))is nbtlib.String and str(tag[key])==value,'Unsafe/missing typed control '+key
    for key in ('WorldTouched','Rollback','AllowMissingRecovery'):
        assert type(tag.get(key))is nbtlib.Byte and int(tag[key])==0,'Unsafe/missing typed control '+key
    assert type(tag.get('Origin'))is nbtlib.Long and int(tag['Origin'])==8246338109520,'Foreign controller origin'
    assert type(tag.get('Progress'))is nbtlib.Double and float(tag['Progress'])==0,'Unexpected motion progress'
    assert type(tag.get('Journey'))is nbtlib.IntArray and len(tag['Journey'])==4,'Missing original journey UUID'
    assert isinstance(tag.get('JournalSHA256s'),nbtlib.List) and len(tag['JournalSHA256s'])==count,'Unexpected durable journal hash count'
    if retained:
        assert all(type(v)is nbtlib.String and re.fullmatch('[0-9a-f]{64}',str(v))for v in tag['JournalSHA256s']),'Incomplete typed original journal hashes'
        assert type(tag.get('Fault'))is nbtlib.String and str(tag['Fault'])=='java.lang.IllegalStateException: Street hatch state/NBT changed without ownership migration at BlockPos{x=183, y=80, z=342}','A different failed preparation needs its own reviewed classification'
    assert type(tag.get('Fault'))is nbtlib.String and str(tag['Fault']).strip(),'Missing original failure'
    assert type(root.get('DataVersion'))is nbtlib.Int,'Missing complete native root metadata'
    return 'SAFE_UNPLACED_PREPARATION_WITH_RETAINED62_JOURNALS'if retained else'SAFE_UNPLACED_PREPARATION_FAULT'

def preserve_unplaced_fault(out,target,control,journals,moving,world_id):
    assert not moving,'Moving owner forbids unplaced admission'
    if not control:
        assert not journals,'Journal without control authority cannot be admitted'
        return None
    assert len(control)==1 and control[0].name=='projectseele_city_rigid_control_r45_8246338109520.dat','Unexpected control authority'
    file=control[0];root=nbtlib.load(file);retained=bool(journals);classification=classify_unplaced_control(root,world_id,retained)
    journal_rows=[]
    if retained:
        authority=base.read(RETAINED62_AUTHORITY);original=authority['control']
        assert base.sha(file)==original['sha256']==RETAINED62_CONTROL_SHA256,'Retained62 admission requires the exact reviewed native failure bytes'
        assert base.sha(original['frozen_file'])==RETAINED62_CONTROL_SHA256 and metadata.same_tag(nbtlib.Compound(root),nbtlib.parse_nbt(original['complete_typed_snbt'])),'Frozen original control authority differs'
        assert authority['journal_count']==len(authority['journals'])==62,'Incomplete reviewed original journal inventory'
        tag=root['data'];journey=str(uuid.UUID(int=sum((int(v)&0xffffffff)<<(96-32*i)for i,v in enumerate(tag['Journey']))))
        expected=[file.parent/'city_rigid_journal_r45'/journey/f'{i}.dat'for i in range(62)]
        assert len(journals)==62 and set(journals)==set(expected),'Foreign, extra, missing or duplicate retained journal'
        folder=out/'retained62_original_journals';folder.mkdir()
        for index,path in enumerate(expected):
            digest=str(tag['JournalSHA256s'][index]);reviewed=authority['journals'][index]
            assert reviewed['index']==index and base.sha(path)==digest==reviewed['sha256']==base.sha(reviewed['frozen_file']),'Retained journal differs from original reviewed durable ledger'
            saved=nbtlib.load(path)
            assert type(saved.get('WorldUUID'))is nbtlib.String and str(saved['WorldUUID'])==world_id and type(saved.get('Origin'))is nbtlib.Long and int(saved['Origin'])==8246338109520 and type(saved.get('Index'))is nbtlib.Int and int(saved['Index'])==index
            assert type(saved.get('Journey'))is nbtlib.IntArray and metadata.same_tag(saved['Journey'],tag['Journey']) and isinstance(saved.get('Cells'),nbtlib.List)and saved['Cells'].subtype is nbtlib.Compound and len(saved['Cells'])>0,'Foreign/incomplete original journal'
            snapshot=folder/path.name;snapshot.write_bytes(path.read_bytes());assert base.sha(snapshot)==digest
            journal_rows.append(dict(index=index,**base.ref(path),original_snapshot=base.ref(snapshot),complete_cells=len(saved['Cells'])))
    before=out/'unplaced_city_control.before.dat';before.write_bytes(file.read_bytes())
    proof=dict(schema='projectseele.city-unplaced-fault-proof-r45.v1',classification=classification,
        world=str(target.resolve()),world_id=world_id,control=dict(**base.ref(file),complete_typed_snbt=root.snbt()),
        original_control_bytes=base.ref(before),no_moving_city_owner=True,no_durable_city_journal=not retained,
        retained_journals=journal_rows,original_current_journal_bytes_retained=True,
        fault_is_not_idle=True,native_city_passed=False,world_written=False,
        recovery='Only a new explicit native QA job referencing this proof may invoke existing recover(..., false). Old jobs keep FAULT; no ordinary production recovery.')
    if retained:proof['retained_original_authority']=base.ref(RETAINED62_AUTHORITY)
    path=out/'unplaced_city_fault_proof.json';base.write(path,proof);return base.ref(path)

def tag_text(t):return None if t is None else t.snbt()

def region_image(path):
    if not path.exists():return [None]*1024,'ABSENT'
    if path.stat().st_size==0:return [None]*1024,'EXACT_ZERO_BYTE_PLACEHOLDER'
    _,records=read_region(path);return records,'NATIVE_REGION'

def nbt_diffs(before,after,path='$'):
    if metadata.same_tag(before,after):return
    if isinstance(before,nbtlib.Compound) and isinstance(after,nbtlib.Compound):
        for k in sorted(set(before)|set(after)):yield from nbt_diffs(before.get(k),after.get(k),path+'.'+k)
    else:yield dict(path=path,before_type=type(before).__name__,after_type=type(after).__name__,before_full_snbt=tag_text(before),after_full_snbt=tag_text(after))

def file_diff(source,target,relative,stream):
    a=source/relative;b=target/relative;summary=dict(relative=relative,before_sha256=base.sha(a) if a.exists() else None,after_sha256=base.sha(b) if b.exists() else None,nbt_field_differences=0)
    if relative.endswith('.mca'):
        old,before_kind=region_image(a);new,after_kind=region_image(b)
        summary.update(before_region_image=before_kind,after_region_image=after_kind)
        if before_kind=='EXACT_ZERO_BYTE_PLACEHOLDER'or after_kind=='EXACT_ZERO_BYTE_PLACEHOLDER':
            stream.write(json.dumps(dict(relative=relative,before_kind=before_kind,after_kind=after_kind,
                before_complete_zero_byte_hex=''if before_kind=='EXACT_ZERO_BYTE_PLACEHOLDER'else None,
                after_complete_zero_byte_hex=''if after_kind=='EXACT_ZERO_BYTE_PLACEHOLDER'else None,
                nonempty_truncated_regions_remain_hard_error=True))+'\n')
        changed=0
        for slot,(x,y) in enumerate(zip(old,new)):
            if x==y:continue
            t1=parse_chunk(x) if x else None;t2=parse_chunk(y) if y else None;changed+=1
            for delta in nbt_diffs(t1,t2):stream.write(json.dumps(dict(relative=relative,slot=slot,**delta),ensure_ascii=False)+'\n');summary['nbt_field_differences']+=1
        summary['changed_chunk_slots']=changed;summary['classification']='FULL_TYPED_NBT_REGION_DIFF'
    elif relative.endswith(('.dat','.dat_old')):
        t1=nbtlib.load(a) if a.exists() else None;t2=nbtlib.load(b) if b.exists() else None
        for delta in nbt_diffs(t1,t2):stream.write(json.dumps(dict(relative=relative,**delta),ensure_ascii=False)+'\n');summary['nbt_field_differences']+=1
        summary['classification']='FULL_TYPED_NBT_DAT_DIFF'
    else:
        before=a.read_bytes() if a.exists() else None;after=b.read_bytes() if b.exists() else None
        try:
            x=json.loads(before) if before is not None else None;y=json.loads(after) if after is not None else None
            stream.write(json.dumps(dict(relative=relative,before_full_json=x,after_full_json=y),ensure_ascii=False)+'\n');summary['classification']='FULL_JSON_DIFF'
        except (ValueError,UnicodeError):
            # MTR stores opaque binary. Preserve every before/after byte as hex, not a guessed schema.
            stream.write(json.dumps(dict(relative=relative,before_full_hex=before.hex() if before else None,after_full_hex=after.hex() if after else None))+'\n');summary['classification']='COMPLETE_OPAQUE_BINARY_DIFF'
    return summary

def actor_inventory(world,files):
    ids={};moving=[];empty_placeholders=[]
    for relative in files:
        if 'entities' not in Path(relative).parts or not relative.endswith('.mca'):continue
        if (world/relative).stat().st_size==0:
            empty_placeholders.append(relative);continue
        _,blobs=read_region(world/relative)
        for slot,blob in enumerate(blobs):
            if blob is None:continue
            root=parse_chunk(blob)
            for entity in root.get('Entities',[]):
                key=entity['UUID'].snbt() if 'UUID' in entity else None
                if key is not None:
                    assert key not in ids,'Duplicate original actor UUID';ids[key]=dict(id=str(entity.get('id','')),region=relative,slot=slot,full_snbt=entity.snbt())
                if any(str(t).startswith('r45_city_rigid/') for t in entity.get('Tags',[])):moving.append(dict(region=relative,slot=slot,full_snbt=entity.snbt()))
    return ids,moving,empty_placeholders

def audit(out):
    assert not out.exists() and out.parent==OUT;out.mkdir(parents=True)
    previous=base.read(PREVIOUS);copy_receipt=base.read(previous['copy_receipt']['path']);target=Path(previous['world']).resolve();source=Path(copy_receipt['source_world']).resolve()
    assert target==qa.QA.absolute() and not qa.reparse(target);qa.check_ref(previous['copy_receipt']);assert copy_receipt['copy_complete']
    historical=base.read(previous['binding_plan']['path']);bundle=Path(historical['metadata_bundle']);manifest=base.read(bundle/'manifest.json')
    plan_file=Path(copy_receipt['copy_plan']['path']);copy_plan=base.read(plan_file);qa.check_ref(copy_receipt['copy_plan'])
    with qa.cold_source(source) as source_lock,qa.cold_source(target) as target_lock:
        source_files=qa.inventory(source,source_lock);target_files=qa.inventory(target,target_lock)
        assert source_files=={r['relative']:r['sha256'] for r in copy_plan['files']},'Original candidate/source progress changed'
        changed=sorted(k for k in set(source_files)|set(target_files) if source_files.get(k)!=target_files.get(k));summaries=[]
        with gzip.open(out/'all_file_nbt_differences.jsonl.gz','wt',encoding='utf8') as stream:
            for relative in changed:
                if relative=='session.lock':
                    # Read lock bytes with their already held handles only.
                    p1=source_lock.tell();p2=target_lock.tell();source_lock.seek(0);target_lock.seek(0)
                    stream.write(json.dumps(dict(relative=relative,before_full_hex=source_lock.read().hex(),after_full_hex=target_lock.read().hex()))+'\n');source_lock.seek(p1);target_lock.seek(p2)
                    summaries.append(dict(relative=relative,before_sha256=source_files[relative],after_sha256=target_files[relative],classification='LOCK_BYTES_SAME_HELD_HANDLES'))
                else:summaries.append(file_diff(source,target,relative,stream))
        errors,counts=metadata.actual_candidate_check(target,bundle,manifest)
        base.write(out/'cargo_readback.json',dict(errors=errors,counts=counts,complete=True,world_written=False));assert not errors,'Full current City cargo/NBT differs; checkpoint cannot be promoted'
        static_file=Path(historical['static_manifest']['path']);run=base.read(Path(historical['journal'])/'run.json');codec=migration.codec_module();codec.TARGET=target
        import sqlite3
        db_path=Path(historical['journal'])/'cells.sqlite';db=sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
        checked=0
        try:
            static=base.read(static_file)
            for row in run['regions']:checked+=codec.inspect_region(static,db,row,codec.region_path(static,row['region']),after=True)
        finally:db.close()
        assert checked==2859160
        mismatches=[]
        for row in manifest['operations']:
            if base.sha(target/row['target'])!=row['after_sha256']:mismatches.append(row['target'])
        assert not mismatches and len(manifest['operations'])==807
        depth_file=target/'dimensions/projectseele/geofront/data/projectseele_tokyo3_retraction.dat';district=nbtlib.load(depth_file)['data']['Districts'][0]
        assert int(district['Depth'])==int(district['TargetDepth'])==312 and int(district['Cursor'])==int(district['VoxelCursor'])==0 and not str(district['Fault'])
        assert base.sha(depth_file)==base.sha(source/depth_file.relative_to(target)),'City progress changed during a failed pre-preparation run'
        identity=nbtlib.load(target/'dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID'];seed=nbtlib.load(target/'level.dat')['Data']['WorldGenSettings']['seed']
        assert str(identity)==previous['world_id'] and int(seed)==previous['world_seed']
        marker=nbtlib.load(target/manifest['marker_target'])['data'];assert str(marker['Stage'])=='CANDIDATE_DISABLED' and not bool(marker['RuntimeEnabled']) and not bool(marker['NativeStructurePassed'])
        assert base.sha(target/manifest['marker_target'])==base.sha(source/manifest['marker_target'])
        control=list((target/'dimensions/projectseele/geofront/data').glob('projectseele_city_rigid_control_r45_*.dat'));journals=[p for p in (target/'dimensions/projectseele/geofront/data/city_rigid_journal_r45').rglob('*') if p.is_file()]
        before_actors,_,source_empty=actor_inventory(source,source_files);after_actors,moving,qa_empty=actor_inventory(target,target_files)
        base.write(out/'actor_identity_audit.json',dict(original_ids=len(before_actors),current_ids=len(after_actors),lost_ids=sorted(set(before_actors)-set(after_actors)),added_ids=sorted(set(after_actors)-set(before_actors)),moving_city_owners=moving,
            changed_original_actors=[dict(uuid=k,before=before_actors[k],after=after_actors.get(k)) for k in before_actors if before_actors[k]!=after_actors.get(k)],QA_progress_never_for_delivery=True))
        base.write(out/'zero_byte_entity_region_placeholders.json',dict(source=source_empty,QA=qa_empty,policy='Only exact zero-byte files have no readable entity records; every nonempty truncated region remains a hard error',original_file_hashes_preserved=True))
        from measure_world_r40 import MeasuredWorld
        from query_blocks import iter_block_entities,palette_state
        from measure_city_placements_r45 import unpack_pos
        ground={};recipe=target/'dimensions/projectseele/geofront/data'/str(marker['GenerationFolder'])
        for path in sorted((recipe/'chunks').glob('*.dat')):
            saved=nbtlib.load(path)
            for cell in saved['Ground']:
                q=unpack_pos(int(cell['Pos']));assert q not in ground;ground[q]=palette_state(saved['Palette'][int(cell['StateId'])])
        assert len(ground)==34881
        measured=MeasuredWorld(target)
        for q in ground:measured.around(q,0)
        measured.load();lo=tuple(min(q[i]for q in ground)for i in range(3));hi=tuple(max(q[i]for q in ground)for i in range(3))
        ground_tags=dict(iter_block_entities(target,'projectseele:geofront',lo,hi,selected_chunks=set(measured.selected)))
        ground_errors=[dict(pos=q,expected=value,actual=measured.block(q),full_nbt=ground_tags[q].snbt()if q in ground_tags else None)for q,value in ground.items()if measured.block(q)!=value or q in ground_tags]
        base.write(out/'complete34881_ground_readback.json',dict(cells=len(ground),errors=ground_errors,complete=True,world_written=False))
        assert not ground_errors,'Complete city hatch Ground differs; cannot promote a checkpoint over original holes'
        unplaced_fault=preserve_unplaced_fault(out,target,control,journals,moving,str(identity))
        assert qa.inventory(source,source_lock)==source_files and qa.inventory(target,target_lock)==target_files,'Cold world changed during checkpoint audit'
        checkpoint=dict(schema='projectseele.city-qa-cold-checkpoint-r45.v1',role='QA_ONLY',world=str(target),source_world=str(source),original_copy_receipt=previous['copy_receipt'],previous_failed_lease=base.ref(PREVIOUS),
            previous_failed_report=base.ref(PREVIOUS.parent/'restore_all96_result/failed.json'),world_id=str(identity),world_seed=int(seed),source1736_exact=True,complete_city_cargo_pass=True,complete_static2859160_pass=True,complete_metadata807_pass=True,
            no_city_control_or_moving_owner=not control,no_moving_owner_or_durable_city_journal=not journals,no_moving_city_owner=True,complete_ground34881_pass=True,candidate_disabled=True,depth=312,full_cargo_counts=counts,static_coordinates=checked,metadata_operations=807,
            current_files=[dict(relative=k,sha256=v) for k,v in sorted(target_files.items())],changed_file_count=len(changed),changed_files=summaries,complete_differences=base.ref(out/'all_file_nbt_differences.jsonl.gz'),actor_identity_audit=base.ref(out/'actor_identity_audit.json'),
            lost_original_actor_ids=len(set(before_actors)-set(after_actors)),native_motion_pass=False,native_art_pass=False,runtime_enabled=False,QA_progress_migration_to_source=False,world_written=False,Java_started=False)
        if unplaced_fault:checkpoint['unplaced_fault_proof']=unplaced_fault
        base.write(out/'checkpoint.json',checkpoint);print('Named cold QA checkpoint complete:',out/'checkpoint.json','changed files',len(changed),'cargo BE',counts['actual_cargo_be'])

def ready(checkpoint_file,out,compiled_file):
    checkpoint=base.read(checkpoint_file);assert checkpoint['schema']=='projectseele.city-qa-cold-checkpoint-r45.v1'
    target=Path(checkpoint['world']);source=Path(checkpoint['source_world']);assert target==qa.QA.absolute()
    previous=base.read(PREVIOUS);compile=base.read(compiled_file);assert compile['schema']=='projectseele.city-preworld-runtime-compiled-proof-r45.v1' and compile['passed'] is True
    for row in [*compile['source_epoch'],*compile['classes']]:qa.check_ref(row)
    assert {'CityAtomicCandidateBindingR45','CityCreateDistrictR45','CityRigidQualityR45','CityRigidTopologyR45','CityCreateCargoR45','CityRigidGenerationR45'}<={Path(r['path']).stem for r in compile['classes']}
    with qa.cold_source(source) as source_lock,qa.cold_source(target) as target_lock:
        copy_receipt=base.read(previous['copy_receipt']['path']);copy_plan=base.read(copy_receipt['copy_plan']['path'])
        assert qa.inventory(source,source_lock)=={r['relative']:r['sha256'] for r in copy_plan['files']}
        assert qa.inventory(target,target_lock)=={r['relative']:r['sha256'] for r in checkpoint['current_files']}
    assert not out.exists() and out.parent==OUT;out.mkdir()
    runtime_revision=out/'runtime_revision.json'
    base.write(runtime_revision,dict(schema='projectseele.city-preworld-admission-runtime-revision-r45.v2',
        previous_preWorld_revision=base.ref(OUT/'runtime_preWorld_revision.json'),current_compiled_proof=base.ref(compiled_file),
        current_source_epoch=compile['source_epoch'],checkpoint_tool=base.ref(ROOT/'tools/checkpoint_city_qa_r45.py'),
        current_checkpoint=base.ref(checkpoint_file),unplaced_fault_proof=checkpoint.get('unplaced_fault_proof'),
        exact_unplaced_fault_only=bool(checkpoint.get('unplaced_fault_proof')),implicit_production_recovery=False,
        old_FAULT_and_failed_receipts_retained=True,WorldTouched_WAL_owner_checks_not_relaxed=True,
        new_explicit_job_invokes_existing_recover_only=True,world_written=False,Java_started=False))
    lease=copy.deepcopy(previous);lease.update(schema='projectseele.city-atomic-native-binding-r45.v3',qa_checkpoint=base.ref(checkpoint_file),preworld_receipt_output=str(out/'preworld_admission.json'),
        runtime_revision=base.ref(runtime_revision),runtime_compiled_proof=base.ref(compiled_file),source_epoch=[*compile['source_epoch'],*compile['classes'],base.ref(compiled_file),base.ref(ROOT/'tools/checkpoint_city_qa_r45.py')],
        world_files=[r for r in checkpoint['current_files'] if r['relative']!='session.lock'])
    base.write(out/'native_binding.json',lease)
    for kind in ('control','quality'):
        job=base.read(PREVIOUS.parent/f'restore_all96.{kind}.json');job.update(candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=base.sha(out/'native_binding.json'))
        if kind=='control' and checkpoint.get('unplaced_fault_proof'):job['unplaced_fault_recovery']=checkpoint['unplaced_fault_proof']
        if kind=='quality':job['output']=str(out/'restore_all96_result')
        base.write(out/f'restore_all96.{kind}.json',job)
    base.write(out/'launch_properties.json',dict(properties=[f'-Dprojectseele.nativeCandidateBindingR45={(out/"native_binding.json").as_posix()}',f'-Dprojectseele.nativeCandidateBindingR45SHA256={base.sha(out/"native_binding.json")}',f'-Dprojectseele.nativeCandidateAdmissionR45={(out/"preworld_admission.json").as_posix()}'],MC_started=False,preworld_receipt_must_be_actual_not_prepared=True))
    print('Prepared exact checkpoint lease; no MC started:',out)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--action',choices=('audit','ready'),default='audit');ap.add_argument('--out',required=True,type=Path);ap.add_argument('--checkpoint',type=Path);ap.add_argument('--compiled-proof',type=Path);a=ap.parse_args()
    if a.action=='audit':audit(a.out.resolve())
    else:assert a.checkpoint and a.compiled_proof;ready(a.checkpoint.resolve(),a.out.resolve(),a.compiled_proof.resolve())

if __name__=='__main__':main()
