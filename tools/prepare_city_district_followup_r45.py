"""Freeze final metadata/source inputs and Root-only native queue; no world mutations."""
from pathlib import Path
import json,hashlib,shutil,copy,subprocess,sys,ast
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r45/city_motion_sol_followup'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    initial=OUT/'install_bundle_v5';final=OUT/'install_bundle_v6'
    assert initial.is_dir() and not final.exists()
    shutil.copytree(initial,final)
    manifest_path=final/'manifest.json';manifest=json.loads(manifest_path.read_text('utf8'))
    amendments=[]
    for entry in manifest['source_epoch']:
        source=ROOT/entry['repository_path'];target=final/entry['frozen_copy'];before=entry['sha256']
        target.write_bytes(source.read_bytes());entry['sha256']=sha(source)
        if before!=entry['sha256']:amendments.append(dict(source=entry['repository_path'],previous_sha256=before,current_sha256=entry['sha256']))
    manifest['followup_source_epoch_amendments']=amendments
    manifest['native_or_performance_passed']=False
    manifest['actual_source_inventory']=str(OUT/'actual96_inventory.json')
    manifest['source_BE_serialization_evidence']=str(OUT/'complete1471_BE_serialized_differences.json')
    manifest['known_generation_v1_v2_equivalence']=str(OUT/'generation_topology_semantic_epoch.json')
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n','utf8')
    for op in manifest['operations']:assert sha(final/op['source'])==op['after_sha256']
    jobs=OUT/'native_jobs_v2'
    subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'tools/prepare_city_rigid_native_jobs_r45.py'),'--out',str(jobs)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    manual=[dict(id='queued_occupied_after_successful_commit',steps=['During MOVE queue the opposite endpoint','Place the existing review actor at an explicit next-trip occupied footprint before commit','Assert completed endpoint IDLE/Queued persisted; no source/destination write for next trip','Normal save/close; same-world reopen, wait still held','Move actor naturally outside; original full96 next trip starts','Verify original actor UUID/inventory/progress and both endpoint cargo/NBT']),
        dict(id='queue_backend_preflight_and_explicit_cancel',steps=['At an already-complete endpoint schedule a trip with missing Create or below-largest-cargo config in an isolated copy','Assert QueueFault/QUEUED_BLOCKED, successful depth unchanged and queued target retained','Request same completed depth to cancel queue; verify no world mutation','Restore original config; explicit requeue then full original96 travel']),
        dict(id='immutable_WAL_hash_and_all96_authority',steps=['Normal interrupt SAVE/CLOSE at exact native checkpoint','Keep original96 journals and control bytes as inverse','On an isolated fault copy change one original journal byte or one footprint/anchor/controller/owner field','Load and assert fail-closed before any world operation or new moving owner','Restore exact original bytes and run same-world cold resume with original96 UUIDs']),
        dict(id='mid_slice_and_atomic_IO_failures',steps=['At OPEN/DETACH/PLACE/COVER partial cursor save/close on isolated original-progress copy','Read exact durable96 inverse and source/target/ground before/after images','Resume/rollback separately; compare every full cargo/NBT and no duplicate moving owner','Fail temporary-create/force/atomic-rename in isolation before first WorldTouched; verify original city unchanged','Record native phase/tick/CPU/storage timing; stock spawn/collision and one endpoint level.save remain synchronous barriers']),
        dict(id='future_chunk_and_two_clients',steps=['Cold reopen final installed marker/recipes and validate originalWorldUUID/96 membership','Generate only authorized fresh recipe chunks and compare full static/cargo/controller/anchor fields','Check two native clients track the same96 owners, request/reversal/status and disconnect/rejoin','Verify maxBlocksMoved>=19382 (reviewed current32768); final server -Xms2G/-Xmx20G','No published package/user progress copied from test world'])]
    sources=json.loads((OUT/'java_ready_source_epoch.json').read_text('utf8'))
    queue=dict(schema='projectseele.city-followup-root-queue-r45.v1',world_written=False,Java_launched_by_agent=False,
        exact_final_metadata_bundle=str(final),baseline_root_static_proof=str(final/'required_root_static_proof_TEMPLATE.json'),
        static_forward_sha256=manifest['static_forward_sha256'],static_inverse_sha256=manifest['static_inverse_sha256'],
        source_epoch=sources,compiled_epoch_must_match_current_sources=True,compile_command_owned_by_root=True,
        initial_actions=['Root cold/exclusive guard and exact forward/inverse+full1471BE preservation','Root complete96 structural/port/bearing/native verification; do not set template booleans from C1','Stage/finish original archive+recipe metadata with RuntimeEnabled=false','Compile final source SHA epoch and use only the original review world identity'],
        automatic_native_suite=str(jobs/'suite.json'),additional_manual_native=manual,
        video_requested=False,native_art_and_performance_pass=False,
        C1_inheritance_only=str(OUT/'c1_effective_scope.json'),memory_source='tools/build_server_ready_pack.py already emits Xms2G/Xmx20G; archived R44 package remains unchanged')
    (OUT/'root_native_queue.json').write_text(json.dumps(queue,indent=2)+'\n','utf8')
    print('Final metadata bundle',final,'operations',len(manifest['operations']),'native jobs',jobs,'manual lifecycle groups',len(manual))
if __name__=='__main__':main()
