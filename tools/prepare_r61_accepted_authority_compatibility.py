"""Offline Root actual61 Source association preserving pre-start two-Job evidence.

No live World read, Source mutation, Java, Gradle, game, installation or native PASS.
The game may progress meanwhile; initial saved progress is historical evidence.
"""
import argparse,copy,importlib.util,json,shutil,sys
from pathlib import Path
ROOT=Path('C:/Users/liboy/.codex/worktrees/r51-nonmap/eva')
sys.path.insert(0,str(ROOT/'tools'))
HERE=Path(__file__).resolve().parent
if HERE.name=='tools':import accepted_authority_r61 as contract
else:
    spec=importlib.util.spec_from_file_location('accepted_authority_r61',HERE/'accepted_authority_r61.proposal.py');contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
read,ref,sha,need,reference=contract.read,contract.ref,contract.sha,contract.need,contract.reference
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf8')
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--fresh-association',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--native-directory',type=Path,required=True);a=ap.parse_args()
    p=contract.pins();previous=read(reference(p['previous_pipeline']));world=Path(previous['world']).resolve();need(not a.out.exists() and not a.out.resolve().is_relative_to(world),'Fresh output outside World required')
    state=contract.frontier(p,world,False);freshrow=ref(a.fresh_association)
    need(freshrow['sha256']=='032eab3c864a4cd4701f08c70eb6cdc47154db40654f4bb29749c0a553628cfd','Exact Root actual61 fresh pre-start association required')
    proof=read(reference(freshrow));prior=read(reference(p['previous_compatibility']))
    a.out.mkdir(parents=True);accepted=reference(prior['accepted_bundle']);copied=a.out/'accepted_authority_bundle';shutil.copytree(accepted.parent,copied);bound=copied/accepted.name
    for name in contract.READBACKS:
        source=reference(proof['fresh_source_reports'][name]) if name in proof['fresh_source_reports'] else reference(p['previous_pipeline']).parent/name
        need(sha(source)==previous['reports'][name],'Unaffected report byte stream differs: '+name);shutil.copyfile(source,a.out/name)
    current=copy.deepcopy(previous)
    for key in ('compatible_accepted_authority','original_current_pipeline','current_native_command','current60_source_equivalence'):current.pop(key,None)
    current.update(world_written=False,game_started=False,native_verified=False,bundle=ref(bound),source_inputs=proof['source_inputs'],reports={name:sha(a.out/name)for name in contract.READBACKS},native_install_command=None,
        current61_source_association=freshrow,current_native_installation_directory=str(a.native_directory.resolve()),current_native_inputs_path=str((a.native_directory/'INPUTS.json').resolve()),current_native_result_path=str((a.native_directory/'RESULT.json').resolve()),
        original_measurement_pipeline=previous['original_measurement_pipeline'],native_executed_by='Root ordinary61 cold start; this Source association starts no game and issues no installation command',
        navigation_sha256=proof['navigation_sha256'],source_geometry_delta=True,all_geometry_equal=False,progress_frontier=p['normal_saved_frontier'],actual_current61_cold_continuation=None,
        next='Actual61 original two-task cold continuation, gameplay/performance and all17 checks remain PENDING.')
    currentpath=a.out/'CURRENT61_SOURCE_PIPELINE.json';write(currentpath,current)
    sidecar=dict(schema='projectseele.r53.compatible-accepted-authority.v1',case=contract.CASE,world=str(world),world_written=False,game_started=False,native_verified=False,native61_pass_imported=False,all_geometry_equal=False,source_geometry_delta=True,
        current_build_receipt=p['current_build_receipt'],previous_compatibility=p['previous_compatibility'],current_pipeline=ref(currentpath),current_candidate_bundle=ref(bound),exact_accepted_bundle_copy=ref(bound),
        current_physical_receipt=ref(a.out/'CURRENT_PHYSICAL_READBACK.json'),current_reports={name:ref(a.out/name)for name in contract.READBACKS},accepted_authority=p['accepted_authority'],initial_saved_runtime=state,
        saved_data_unchanged_during_pre_start_source_proof_sha256=state['sha256'],current61_source_association=freshrow,progress_frontier=p['normal_saved_frontier'],current61_native_status='PENDING',actual_current61_cold_continuation=None,
        live_world_read_during_wrapper_preparation=False,source_geometry_directory_fingerprint=read(a.out/'CURRENT_GUIDEWAY_REPORT.json')['directory_fingerprint'],measurement_source_pipeline=previous['original_measurement_pipeline'],
        scope='Exact Source61 motor-center/first-hose geometry delta. Original accepted five definitions remain byte-exact; pre-start original two INSERT/PrepareTicks=0 tasks have exact SNBT. Historical physical reports cover unchanged guide/SPACE/gates. This offline wrapper does not read current live progress or certify changed crane action/cold continuation.')
    for k in ('accepted_pipeline','accepted_bundle','accepted_build_receipt','accepted_physical_receipt'):sidecar[k]=prior[k]
    path=a.out/'CURRENT_R61_ACCEPTED_AUTHORITY_COMPATIBILITY.json';write(path,sidecar);contract.validate(ref(path),world,reference(p['current_build_receipt']),read_live_authority=False)
    current.update(compatible_accepted_authority=ref(path),original_current_pipeline=ref(currentpath));wrapper=a.out/'CURRENT_BUNDLE_PIPELINE_RECEIPT.json';write(wrapper,current)
    result=dict(schema='projectseele.r61.offline-source-authority-wrapper.v1',current_pipeline=ref(wrapper),compatibility=ref(path),source_association=freshrow,exact_delta_manifest_sha256=contract.MANIFEST_SHA,
        current_build_receipt=p['current_build_receipt'],current_jar=proof['current_jar'],accepted_authority=p['accepted_authority'],pre_start_saved_runtime=state,progress_frontier=p['normal_saved_frontier'],navigation_sha256=proof['navigation_sha256'],world_written=False,live_world_read=False,src_modified=False,game_started=False,installation_command_issued=False,jobs_reset=False,source_geometry_delta=True,all_geometry_equal=False,native61_functional_pass=False,native61_cold_continuation='PENDING')
    write(a.out/'PREPARATION_RECEIPT.json',result);print(json.dumps(dict(current_pipeline=ref(wrapper),compatibility=ref(path),preparation_receipt=ref(a.out/'PREPARATION_RECEIPT.json'),native61_functional_pass=False,live_world_read=False,world_written=False),ensure_ascii=True))
if __name__=='__main__':main()
