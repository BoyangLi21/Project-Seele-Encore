"""Offline62 Source association; retain reviewed61 geometry and real INSERT42 Jobs.

No live World read, game/Java/Gradle, reinstall, task reset or native PASS.
"""
import argparse,copy,importlib.util,json,shutil,sys
from pathlib import Path
ROOT=Path('C:/Users/liboy/.codex/worktrees/r51-nonmap/eva')
sys.path.insert(0,str(ROOT/'tools'));HERE=Path(__file__).resolve().parent
if HERE.name=='tools':import accepted_authority_r62 as contract
else:
    spec=importlib.util.spec_from_file_location('accepted_authority_r62',HERE/'accepted_authority_r62.proposal.py');contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
read,ref,sha,need,reference=contract.read,contract.ref,contract.sha,contract.need,contract.reference
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf8')
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--native-directory',type=Path,required=True);a=ap.parse_args()
    p=contract.pins();previous=read(reference(p['previous_pipeline']));prior=read(reference(p['previous_compatibility']));world=Path(previous['world']).resolve()
    need(not a.out.exists() and not a.out.resolve().is_relative_to(world),'Fresh external output required');state=contract.frontier(p,world);build=read(reference(p['current_build_receipt']))
    a.out.mkdir(parents=True);accepted=reference(prior['accepted_bundle']);copied=a.out/'accepted_authority_bundle';shutil.copytree(accepted.parent,copied);bound=copied/accepted.name
    for name in contract.READBACKS:
        source=reference(p['previous_pipeline']).parent/name;need(sha(source)==previous['reports'][name],'Actual61 physical report changed: '+name);shutil.copyfile(source,a.out/name)
    files=copy.deepcopy(previous['source_inputs']);files['selected_build_receipt']=p['current_build_receipt'];files['selected_jar']=ref(build['jar'])
    proof=dict(schema='projectseele.r62.current-source-publisher-association.v1',current_build_receipt=p['current_build_receipt'],current_jar=ref(build['jar']),previous_pipeline=p['previous_pipeline'],historical61_source_association=p['historical61_source_association'],historical61_mechanical_loader=p['historical61_mechanical_loader'],
        exact_delta_manifest_sha256=contract.MANIFEST_SHA,source_inputs=files,behavior_delta_from61=p['behavior_delta'],source_geometry_reports_reused_from_actual61=True,geometry_reuse_basis='Exactly one publisher Source/class changed; all geometry producer classes, all resource bytes and all clocks/postconditions match61. Actual61 mechanical proof retains its original meaning.',
        mechanical_geometry_changed_from61=False,source_geometry_delta_from60_retained=True,all_geometry_equal_from60=False,geometry_production_export_reexecuted=False,progress_frontier=p['normal_saved_frontier'],initial_saved_runtime=state,
        world_written=False,live_world_read=False,game_started=False,java_started=False,authority_reset=False,jobs_reset=False,native62_pass_imported=False,native62_functional_pass=False)
    proofpath=a.out/'CURRENT62_SOURCE_ASSOCIATION.json';write(proofpath,proof)
    current=copy.deepcopy(previous)
    for k in ('compatible_accepted_authority','original_current_pipeline','current61_source_association','actual_current61_cold_continuation','current_native_command'):current.pop(k,None)
    current.update(world_written=False,game_started=False,native_verified=False,bundle=ref(bound),source_inputs=files,reports={n:sha(a.out/n)for n in contract.READBACKS},current62_source_association=ref(proofpath),historical61_source_association=p['historical61_source_association'],native_install_command=None,
        current_native_installation_directory=str(a.native_directory.resolve()),current_native_inputs_path=str((a.native_directory/'INPUTS.json').resolve()),current_native_result_path=str((a.native_directory/'RESULT.json').resolve()),
        progress_frontier=p['normal_saved_frontier'],source_geometry_delta_from60_retained=True,mechanical_geometry_changed_from61=False,all_geometry_equal_from60=False,actual_current62_cold_continuation=None,
        native_executed_by='Root unique ordinary62 client; association starts no game',next='Original INSERT42 tasks must actually continue in62; nine routes/air/lifts/MTR/performance/all17 and final both-world readbacks remain PENDING.')
    currentpath=a.out/'CURRENT62_SOURCE_PIPELINE.json';write(currentpath,current)
    sidecar=dict(schema='projectseele.r53.compatible-accepted-authority.v1',case=contract.CASE,world=str(world),world_written=False,game_started=False,native_verified=False,native62_pass_imported=False,all_geometry_equal_from60=False,
        source_geometry_delta_from60_retained=True,mechanical_geometry_changed_from61=False,behavior_delta_from61=p['behavior_delta'],current_build_receipt=p['current_build_receipt'],historical61_source_association=p['historical61_source_association'],current62_source_association=ref(proofpath),
        previous_compatibility=p['previous_compatibility'],current_pipeline=ref(currentpath),current_candidate_bundle=ref(bound),exact_accepted_bundle_copy=ref(bound),current_physical_receipt=ref(a.out/'CURRENT_PHYSICAL_READBACK.json'),current_reports={n:ref(a.out/n)for n in contract.READBACKS},
        accepted_authority=p['accepted_authority'],initial_saved_runtime=state,progress_frontier=p['normal_saved_frontier'],live_world_read_during_wrapper_preparation=False,current62_native_status='PENDING',actual_current62_cold_continuation=None,
        source_geometry_directory_fingerprint=read(a.out/'CURRENT_GUIDEWAY_REPORT.json')['directory_fingerprint'],measurement_source_pipeline=previous['original_measurement_pipeline'],
        scope='Only reviewed publisher deadband changes from61. Its pre-start saved INSERT42 two tasks/actors are exact. Actual61 mechanical geometry proof remains separate; current62 functional continuation and all release checks are pending.')
    for k in ('accepted_pipeline','accepted_bundle','accepted_build_receipt','accepted_physical_receipt'):sidecar[k]=prior[k]
    sidepath=a.out/'CURRENT_R62_ACCEPTED_AUTHORITY_COMPATIBILITY.json';write(sidepath,sidecar);contract.validate(ref(sidepath),world,reference(p['current_build_receipt']),read_live_authority=False,check_live_source=False)
    current.update(compatible_accepted_authority=ref(sidepath),original_current_pipeline=ref(currentpath));wrapper=a.out/'CURRENT_BUNDLE_PIPELINE_RECEIPT.json';write(wrapper,current)
    result=dict(schema='projectseele.r62.offline-source-authority-wrapper.v1',current_pipeline=ref(wrapper),compatibility=ref(sidepath),source_association=ref(proofpath),current_build_receipt=p['current_build_receipt'],current_jar=ref(build['jar']),pre_start_saved_runtime=state,progress_frontier=p['normal_saved_frontier'],
        exact_delta_manifest_sha256=contract.MANIFEST_SHA,geometry_reexecuted=False,world_written=False,live_world_read=False,src_modified=False,java_started=False,game_started=False,installation_command_issued=False,authority_reset=False,jobs_reset=False,native62_pass_imported=False,native62_functional_pass=False)
    resultpath=a.out/'PREPARATION_RECEIPT.json';write(resultpath,result);print(json.dumps(dict(current_pipeline=ref(wrapper),compatibility=ref(sidepath),preparation_receipt=ref(resultpath),native62_functional_pass=False,live_world_read=False,world_written=False),ensure_ascii=True))
if __name__=='__main__':main()
