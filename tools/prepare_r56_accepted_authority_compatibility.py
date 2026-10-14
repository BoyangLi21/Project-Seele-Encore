"""Current R56 source/report association with exact actually accepted R55 authority.

No saved-data, World, source or game mutation. Root deploys the exact candidate.
"""
import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from release_scope124_r53 import sha, read, need, saved_runtime_authority, compatible_accepted_authority, SOURCE_REPORTS


def ref(p): return dict(path=str(Path(p).resolve()),sha256=sha(p))
def write(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','accepted-pipeline','current-pipeline','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--current-native-command',type=Path)
    a=p.parse_args();need(not a.out.exists(),'Fresh compatibility candidate required')
    inputs=read(a.inputs);world=Path(inputs['world']).resolve();need(not a.out.resolve().is_relative_to(world),'Candidate must remain outside World')
    old,new=read(a.accepted_pipeline),read(a.current_pipeline);accepted=Path(old['bundle']['path']);current=Path(new['bundle']['path'])
    need(sha(accepted)==old['bundle']['sha256'] and sha(current)==new['bundle']['sha256'],'Actual selected bundle bytes changed')
    state=saved_runtime_authority(world);bundle=read(accepted)
    need(state['claimed'] and not state['fault'] and state['jobs']==0 and not state['pending_installation'],'Current stopped zero-job accepted authority required')
    need(state['epoch']==bundle['epoch']==53 and state['directory_fingerprint']==bundle['directory_fingerprint'] and state['bundle_sha256']==sha(accepted),
         'The supplied previous bundle is not the actual persisted accepted authority')
    a.out.mkdir(parents=True);bundle_copy= a.out/'accepted_authority_bundle';shutil.copytree(accepted.parent,bundle_copy)
    copied=bundle_copy/accepted.name;need(sha(copied)==state['bundle_sha256'],'Accepted bundle copy changed')
    for name in SOURCE_REPORTS:
        path=a.current_pipeline.parent/name;need(sha(path)==new['reports'][name],'Current fresh source report changed');shutil.copyfile(path,a.out/name)
    old_build=Path(old['source_inputs']['selected_build_receipt']['path']);new_build=Path(new['source_inputs']['selected_build_receipt']['path'])
    need(sha(new_build)==inputs['files']['selected_build_receipt']['sha256'],'Current input build differs')
    sidecar=dict(schema='projectseele.r53.compatible-accepted-authority.v1',case='r56-sbw-loaded-los-preserve-epoch53',
        world=str(world),world_written=False,game_started=False,native_verified=False,
        accepted_bundle=ref(accepted),current_candidate_bundle=ref(current),exact_accepted_bundle_copy=ref(copied),
        accepted_build_receipt=ref(old_build),current_build_receipt=ref(new_build),
        accepted_pipeline=ref(a.accepted_pipeline),current_pipeline=ref(a.current_pipeline),
        accepted_physical_receipt=ref(a.accepted_pipeline.parent/'CURRENT_PHYSICAL_READBACK.json'),
        current_physical_receipt=ref(a.current_pipeline.parent/'CURRENT_PHYSICAL_READBACK.json'),
        current_reports={name:ref(a.current_pipeline.parent/name)for name in SOURCE_REPORTS},
        accepted_authority={k:state[k]for k in ('epoch','directory_fingerprint','bundle_relative','bundle_sha256','guide_sha256')},
        initial_saved_runtime=state,saved_data_unchanged_during_preparation_sha256=sha(Path(state['path'])),
        source_geometry_directory_fingerprint=read(a.out/'CURRENT_GUIDEWAY_REPORT.json')['directory_fingerprint'],
        scope='Current56 code/resources/current physical reports bound to the unchanged actually accepted runtime definitions. Previous receipts retain their historical meaning. Live56 restoration/gameplay still required.')
    sidecar_path=a.out/'CURRENT_R56_ACCEPTED_AUTHORITY_COMPATIBILITY.json';write(sidecar_path,sidecar)
    compatible_accepted_authority(ref(sidecar_path),world,new_build)
    # Use the current production parser with the copied accepted byte stream.
    java=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe')
    source_args=(a.current_pipeline.parent/'production_source_export.args').read_text(encoding='utf8').splitlines()
    at=next(i for i,line in enumerate(source_args)if line.strip('"')in ('-cp','-classpath'));cp=source_args[at+1].strip('"')
    args=a.out/'accepted_current_parser.args';values=['-Xmx512m','-cp',cp,'com.projectseele.world.R52DirectoryFingerprint',str(bundle_copy/'ROOT_RUNTIME_DIRECTORY.json')]
    args.write_text('\n'.join('"'+x.replace('\\','/')+'"'for x in values)+'\n',encoding='utf8')
    r=subprocess.run([str(java),'@'+str(args)],capture_output=True);(a.out/'accepted_current_parser.log').write_bytes(r.stdout+r.stderr)
    match=re.search(r'R52_DIRECTORY_FINGERPRINT=([0-9a-f]{64})',r.stdout.decode('utf8','replace'))
    need(r.returncode==0 and match and match.group(1)==state['directory_fingerprint'],'Current56 production parser did not accept identical accepted directory')
    f=inputs['files'];deployment=a.out/'metadata_redeploy_candidate';root=Path(__file__).resolve().parents[1]
    argv=[sys.executable,str(root/'tools/prepare_r52_runtime_deployment_candidate.py'),'--bundle',str(copied),'--out',str(deployment),
        '--world',str(world),'--baseline',f['baseline']['path'],'--baseline-sha256',f['baseline']['sha256'],
        '--root-plan',f['root_plan']['path'],'--root-plan-sha256',f['root_plan']['sha256']]
    r=subprocess.run(argv,capture_output=True);(a.out/'metadata_redeploy_candidate.log').write_bytes(r.stdout+r.stderr)
    need(r.returncode==0,'Exact accepted metadata candidate failed; see metadata_redeploy_candidate.log')
    deploy=deployment/'DEPLOYMENT_PREPARATION.json';need(read(deploy)['ready'],'Exact accepted metadata candidate is not ready')
    wrapper=copy.deepcopy(new);wrapper.update(world=str(world),bundle=ref(copied),deployment=ref(deploy),
        source_inputs=copy.deepcopy(new['source_inputs']),reports={name:sha(a.out/name)for name in SOURCE_REPORTS},
        compatible_accepted_authority=ref(sidecar_path),original_current_pipeline=ref(a.current_pipeline),
        native_install_command=None,world_written=False,game_started=False,native_verified=False,
        next='Root redeploys this exact accepted metadata candidate, then performs normal restoration using current56 Jar. SavedData/guard/epoch/accepted bundle path and bytes remain unchanged.')
    if a.current_native_command:
        command=read(a.current_native_command);argv=command['argv'];folder=argv[argv.index('--out')+1]
        need(command['new_current_native_run']is True and command['historical_PASS_imported']is False
             and argv[argv.index('--jar-sha256')+1]==new['source_inputs']['selected_jar']['sha256'],
             'Current native command is not the actual56 run')
        wrapper.update(native_install_command=argv,current_native_command=ref(a.current_native_command),
            current_native_installation_directory=folder,current_native_inputs_path=str(Path(folder)/'INPUTS.json'),
            current_native_result_path=str(Path(folder)/'RESULT.json'),native_executed_by='Root current56 run; compatibility tool starts no game')
    write(a.out/'CURRENT_BUNDLE_PIPELINE_RECEIPT.json',wrapper)
    need(sha(Path(state['path']))==state['sha256'],'SavedData changed during read-only candidate preparation')
    result=dict(world_written=False,src_modified=False,game_started=False,current_production_parser_passed=True,
        current_jar=new['source_inputs']['selected_jar'],current_pipeline=ref(a.out/'CURRENT_BUNDLE_PIPELINE_RECEIPT.json'),
        compatibility=ref(sidecar_path),metadata_redeploy=ref(deploy),accepted_authority=sidecar['accepted_authority'],
        same2024_existing_named_and_jar_classes_and_all_resources=True,only_approved_new_mixin_registration_and_build_timestamp=True)
    write(a.out/'PREPARATION_RECEIPT.json',result);print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
