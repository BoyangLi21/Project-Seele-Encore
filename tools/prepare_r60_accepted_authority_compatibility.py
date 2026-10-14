"""Fresh reviewed R60 source association with the exact actually accepted R55 definitions.

No World/source/progress mutation, Gradle, game, new directory or runtime authority.
"""
import argparse,copy,json,re,shutil,subprocess,sys
from pathlib import Path
from release_scope124_r53 import (sha,read,need,reference,saved_runtime_authority,
    compatible_accepted_authority,reviewed_r60_delta,SOURCE_REPORTS)
from prepare_current_runtime_bundle_r53 import export_sources,source_spaces,asset_pins,selected

ROOT=Path(__file__).resolve().parents[1]
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def argument(p,values):p.write_text('\n'.join('"'+str(v).replace('\\','/').replace('"','\\"')+'"'for v in values)+'\n',encoding='utf8')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','build-receipt','accepted-pipeline','previous-pipeline','previous-native-command','out'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--resume-source-export',action='store_true')
    a=ap.parse_args();need(not a.out.exists()or a.resume_source_export,'Fresh R60 association output required')
    need(not(a.out/'CURRENT_BUNDLE_PIPELINE_RECEIPT.json').exists(),'Completed R60 association must remain immutable')
    inputs=read(a.inputs);world=Path(inputs['world']).resolve();need(not a.out.resolve().is_relative_to(world),'Output must remain outside World')
    pins=reviewed_r60_delta();build=read(a.build_receipt);need(build['build_exit']==0 and not build['changed_during_build']
        and build['sha256']==pins['current60_jar_sha256'],'Exact completed frozen build60 required')
    previous=read(a.previous_pipeline);accepted_pipeline=read(a.accepted_pipeline)
    need(Path(previous['world']).resolve()==world and previous['world_written'] is False,'Previous measurement refers to another World')
    # Its named directory now holds60; keep the immutable historical measurement truthful.
    prior=read(reference(previous['compatible_accepted_authority']))
    need(prior['case']=='r56-sbw-loaded-los-preserve-epoch53'
        and reference(prior['current_build_receipt'])==reference(previous['source_inputs']['selected_build_receipt'])
        and previous['source_inputs']['selected_jar']['sha256']==pins['measurement56_jar_sha256'],
        'Exact previous56 Source measurement association required')
    accepted=reference(accepted_pipeline['bundle']);state=saved_runtime_authority(world)
    need(state['claimed']and not state['fault']and state['jobs']==0 and not state['pending_installation']
        and state['bundle_sha256']==sha(accepted),'Current stopped accepted authority required')
    a.out.mkdir(parents=True,exist_ok=a.resume_source_export);copied=a.out/'accepted_authority_bundle'
    if not copied.exists():shutil.copytree(accepted.parent,copied)
    bound=copied/accepted.name;need(sha(bound)==sha(accepted),'Accepted byte stream changed')
    files=copy.deepcopy(previous['source_inputs']);files['selected_build_receipt']=ref(a.build_receipt);files['selected_jar']=ref(build['jar'])
    f={k:selected(v)for k,v in files.items()};fresh=a.out/'fresh_current60_source';fresh.mkdir(exist_ok=a.resume_source_export)
    java=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe')
    if a.resume_source_export:
        parser_args=fresh/'production_source_export.args';producer=parser_args.read_text('utf8')
        need(all(str(p).replace('\\','/')in producer for p in [f['selected_jar'],f['ground'],f['guide_source'],f['units'],f['gates']]),
             'Resume export arguments do not bind the same actual60 inputs')
        manifest=read(build['named_class_manifest']);need(all(sha(Path(build['named_class_directory'])/k)==v for k,v in manifest.items()),
             'Actual60 production classes changed after the fresh export')
    else:
        parser_args=export_sources(f,fresh,java);source_spaces(f,fresh,asset_pins(f['selected_jar']),inputs.get('space_domains'))
    fresh_names=['CURRENT_GUIDEWAY_REPORT.json','CURRENT_LEGACY_LEAD_REPORT.json','CURRENT_SOURCE_ENVELOPES.json',
        'CURRENT_SPACE_DIRECTORY.json','CURRENT_AIR_SPACE_MERGE.json']
    original56=reference(read(reference(previous['original_current_pipeline']))['source_inputs']['selected_build_receipt'])
    measured_folder=reference(previous['original_current_pipeline']).parent
    # Run the reviewed baseline comparison with the actual60 named classes first.
    state_cp=read(f['compile_state'])['classpath'];review=ROOT/'.Codex/map_complete_20261013/transit_finish/plant_near_collision_perf_r58'
    original_drive=ROOT/'.Codex/map_complete_20261013/transit_finish/cage_collision_perf_r57/ACTUAL_SAVED_FOOT_DRIVE_SPECS.json'
    cp=[build['named_class_directory'],build['jar'],str(review/'classes')]+state_cp
    bbox=a.out/'CURRENT60_COMPILED_BBOX_QUERY_CHECKS.json';bbox_args=a.out/'compiled60_bbox.args'
    argument(bbox_args,['-Xmx1800m','-cp',';'.join(cp),'com.projectseele.world.CurrentPlantBBoxQueryR58',
        original_drive,bbox,ROOT/'src/main/resources/assets/projectseele/eva/cage_collision_r52_sources.json'])
    if not bbox.exists():
        r=subprocess.run([str(java),'@'+str(bbox_args)],capture_output=True);(a.out/'compiled60_bbox.log').write_bytes(r.stdout+r.stderr)
        need(r.returncode==0,'Actual60 compiled collision regression failed')
    else:need(a.resume_source_export,'Fresh actual60 collision report required')
    measured_checks=read(reference(pins['reviewed_change_evidence']['collision_checks']));fresh_checks=read(bbox)
    for doc in (measured_checks,fresh_checks):
        for timing in ('elapsed_seconds','near1000_baseline_ms','near1000_cached_ms'):doc.pop(timing)
    need(measured_checks==fresh_checks,'Actual60 compiled collision output/guard checks differ')
    visual=ROOT/'.Codex/map_complete_20261013/client_visual_contract_current56'
    contract=a.out/'CURRENT60_COMPILED_VISUAL_CONTRACT_CHECKS.json';visual_args=a.out/'compiled60_visual.args'
    argument(visual_args,['-Xmx768m','-Djava.awt.headless=true','-cp',';'.join([build['named_class_directory'],str(visual/'classes')]+state_cp),
        'CurrentReviewedVisualContractCheck',build['jar'],contract])
    if not contract.exists():
        r=subprocess.run([str(java),'@'+str(visual_args)],capture_output=True);(a.out/'compiled60_visual.log').write_bytes(r.stdout+r.stderr)
        need(r.returncode==0,'Actual60 compiled reviewed visual contract failed')
    else:need(a.resume_source_export,'Fresh actual60 visual report required')
    visual_result=read(contract)
    if 'actual_jar56_sha256'in visual_result:
        visual_result['actual_jar_sha256']=visual_result.pop('actual_jar56_sha256');write(contract,visual_result)
    manual=ROOT/'.Codex/map_complete_20261013/route_audit/manual_original_npc_r60'
    manual_result=a.out/'CURRENT60_COMPILED_MANUAL_NPC_CHECKS.json';manual_args=a.out/'compiled60_manual.args'
    argument(manual_args,['-Xmx256m','-cp',';'.join([build['named_class_directory'],str(manual/'classes')]+state_cp),
        'com.projectseele.world.CurrentManualNpcDelegationR60Check',manual/'ACTUAL59_ORDINARY_BOARDING_FACTS.json',manual_result])
    r=subprocess.run([str(java),'@'+str(manual_args)],capture_output=True);(a.out/'compiled60_manual.log').write_bytes(r.stdout+r.stderr)
    need(r.returncode==0,'Actual60 manualNPC and cold retained progress checks failed')
    render=ROOT/'.Codex/map_complete_20261013/transit_finish/render_source_fix_r60'
    render_result=a.out/'CURRENT60_COMPILED_RENDER_CPU_CHECKS.json';render_args=a.out/'compiled60_render.args'
    argument(render_args,['-Xmx256m','-cp',';'.join([build['named_class_directory'],build['jar'],str(render/'classes')]+state_cp),
        'com.projectseele.client.render.VerifyRigidClipAndRopeCacheR60',render_result])
    r=subprocess.run([str(java),'@'+str(render_args)],capture_output=True);(a.out/'compiled60_render.log').write_bytes(r.stdout+r.stderr)
    need(r.returncode==0,'Actual60 source render clip and immutable rope cache checks failed')
    source_proof=dict(schema='projectseele.r60.current-source-measurement-association.v1',current_build_receipt=ref(a.build_receipt),
        previous_build_receipt=ref(original56),measurement_source_pipeline=ref(a.previous_pipeline),
        fresh_source_reports={},previous_source_reports={},source_reports_equal=True,
        current60_compiled_collision_checks=ref(bbox),current60_compiled_visual_checks=ref(contract),
        current60_compiled_manual_npc_checks=ref(manual_result),current60_compiled_render_cpu_checks=ref(render_result),
        functional_policy_change=pins['functional_policy_change'],native60_functional_pass=False,
        compiled60_classpath_priority=[build['named_class_directory'],build['jar']],
        world_written=False,game_started=False,native60_pass_imported=False,
        scope='Fresh60 production parsers and complete mechanical geometry outputs equal the actual56 Source outputs. Reviewed NPC empty-mission admission changes reading current ordinary-phone ownership; its actual60 functional and cold run remain required. Saved measured native faces retain their historical meaning, no native PASS imported.')
    for name in fresh_names:
        old=measured_folder/name;need(old.is_file()and read(old)==read(fresh/name),'Fresh60 Source output values differ: '+name)
        source_proof['fresh_source_reports'][name]=ref(fresh/name);source_proof['previous_source_reports'][name]=ref(old)
    # The measurement keeps its original factual meaning and its false native-cycle flag.
    for name in SOURCE_REPORTS:
        old=a.previous_pipeline.parent/name;need(sha(old)==previous['reports'][name],'Previous actual measurement changed')
        shutil.copyfile(fresh/name if (fresh/name).is_file()else old,a.out/name)
        need(sha(a.out/name)==sha(old),'Current60 Source/measurement association changed values')
    # Parser proof uses the unchanged accepted byte stream, never regenerated receipt-bearing definitions.
    lines=parser_args.read_text('utf8').splitlines();at=next(i for i,s in enumerate(lines)if s.strip('"')in ('-cp','-classpath'))
    parseargs=a.out/'accepted_current60_parser.args';argument(parseargs,['-Xmx512m','-cp',lines[at+1].strip('"'),
        'com.projectseele.world.R52DirectoryFingerprint',copied/'ROOT_RUNTIME_DIRECTORY.json'])
    r=subprocess.run([str(java),'@'+str(parseargs)],capture_output=True);(a.out/'accepted_current60_parser.log').write_bytes(r.stdout+r.stderr)
    match=re.search(r'R52_DIRECTORY_FINGERPRINT=([0-9a-f]{64})',r.stdout.decode('utf8','replace'))
    need(r.returncode==0 and match and match.group(1)==state['directory_fingerprint'],'Current60 rejected exact accepted Directory')
    proof_path=a.out/'CURRENT60_SOURCE_EQUIVALENCE.json';write(proof_path,source_proof)
    # This is a current Source association entry, with no claim of a new physical measurement or native PASS.
    current=copy.deepcopy(previous);current.pop('compatible_accepted_authority',None)
    current.update(source_inputs=files,bundle=ref(bound),reports={name:sha(a.out/name)for name in SOURCE_REPORTS},
        world_written=False,game_started=False,native_verified=False,native_install_command=None,
        original_measurement_pipeline=ref(a.previous_pipeline),current60_source_equivalence=ref(proof_path),
        next='Root current60 same-authority cold restoration, client performance and gameplay checks remain required.')
    current_path=a.out/'CURRENT60_SOURCE_PIPELINE.json';write(current_path,current)
    sidecar=dict(schema='projectseele.r53.compatible-accepted-authority.v1',case='r60-reviewed-manual-npc-and-render-preserve-epoch53',
        world=str(world),world_written=False,game_started=False,native_verified=False,
        accepted_bundle=ref(accepted),current_candidate_bundle=ref(bound),exact_accepted_bundle_copy=ref(bound),
        accepted_build_receipt=accepted_pipeline['source_inputs']['selected_build_receipt'],current_build_receipt=ref(a.build_receipt),
        accepted_pipeline=ref(a.accepted_pipeline),current_pipeline=ref(current_path),
        accepted_physical_receipt=ref(a.accepted_pipeline.parent/'CURRENT_PHYSICAL_READBACK.json'),
        current_physical_receipt=ref(a.out/'CURRENT_PHYSICAL_READBACK.json'),
        current_reports={name:ref(a.out/name)for name in SOURCE_REPORTS},
        accepted_authority={k:state[k]for k in ('epoch','directory_fingerprint','bundle_relative','bundle_sha256','guide_sha256')},
        initial_saved_runtime=state,saved_data_unchanged_during_preparation_sha256=state['sha256'],
        source_geometry_directory_fingerprint=read(a.out/'CURRENT_GUIDEWAY_REPORT.json')['directory_fingerprint'],
        reviewed_change_evidence=pins['reviewed_change_evidence'],current60_source_equivalence=ref(proof_path),
        measurement_source_pipeline=ref(a.previous_pipeline),scope=source_proof['scope'])
    sidecar_path=a.out/'CURRENT_R60_ACCEPTED_AUTHORITY_COMPATIBILITY.json';write(sidecar_path,sidecar)
    compatible_accepted_authority(ref(sidecar_path),world,a.build_receipt)
    command=read(a.previous_native_command);argv=copy.deepcopy(command['argv'])
    for key,value in [('build-receipt',a.build_receipt),('jar',build['jar']),('jar-sha256',build['sha256']),
                      ('out',a.out.parent/'current_runtime_bundle_release60/native_1')]:argv[argv.index('--'+key)+1]=str(value)
    native_path=a.out/'ROOT_NATIVE_CURRENT60_ACCEPTED_AUTHORITY_COMMAND.json'
    write(native_path,dict(argv=argv,new_current_native_run=True,historical_PASS_imported=False,executed=False,
        accepted_authority=sidecar['accepted_authority'],current60_source_equivalence=ref(proof_path)))
    native_folder=argv[argv.index('--out')+1]
    current.update(compatible_accepted_authority=ref(sidecar_path),original_current_pipeline=ref(current_path),
        native_install_command=argv,current_native_command=ref(native_path),
        current_native_installation_directory=native_folder,current_native_inputs_path=str(Path(native_folder)/'INPUTS.json'),
        current_native_result_path=str(Path(native_folder)/'RESULT.json'),native_executed_by='Root new60 run; this tool starts no game')
    wrapper=a.out/'CURRENT_BUNDLE_PIPELINE_RECEIPT.json';write(wrapper,current)
    need(sha(Path(state['path']))==state['sha256'],'SavedData changed during read-only Source association')
    result=dict(world_written=False,src_modified=False,game_started=False,native60_pass_imported=False,
        current_production_parser_passed=True,current_build_receipt=ref(a.build_receipt),current_jar=ref(build['jar']),
        current_pipeline=ref(wrapper),compatibility=ref(sidecar_path),fresh_source_equivalence=ref(proof_path),
        current_native_command=ref(native_path),accepted_authority=sidecar['accepted_authority'])
    write(a.out/'PREPARATION_RECEIPT.json',result);print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
