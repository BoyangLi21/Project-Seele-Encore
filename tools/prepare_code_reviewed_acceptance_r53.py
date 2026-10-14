"""Exact final Root code review -> private fixed manual acceptance report.

No build, game, World mutation, native PASS or future Jar prediction.
Root supplies the actual final BR, authorization and completed review receipt.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path('C:/Users/liboy/.codex/worktrees/r51-nonmap/eva')
sys.path.insert(0,str(ROOT/'tools'))
from release_scope124_r53 import read,sha,need,reference,SOURCE_REPORTS
from package_release_r52 import SCOPE124_ACCEPTANCE
QUALIFICATION='CODE_REVIEWED_RUNTIME_UNVERIFIED'
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(Path(p)))
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('world','build-receipt','authorization','code-review','source-pipeline','navigation-receipt','out'):ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();world=a.world.resolve();need(world==Path('D:/eva/artifacts/map_complete_20261013/WORLD').resolve(),'Explicit sole current World required')
    need(not a.out.exists()and not a.out.resolve().is_relative_to(world),'Fresh acceptance outside World required')
    build=read(a.build_receipt);auth=read(a.authorization);review=read(a.code_review);pipeline=read(a.source_pipeline);nav=read(a.navigation_receipt)
    need(build['build_exit']==0 and build['changed_during_build']==[],'Actual successful final frozen build required')
    buildrow=ref(a.build_receipt);need(review.get('schema')=='projectseele.r53.final-code-review.v1' and review.get('draft')is not True and review.get('code_review_complete')is True and review.get('known_implementation_blockers')==[] and review.get('native_verified')is False and review.get('build_receipt')==buildrow and review.get('jar_sha256')==build['sha256'],'Root completed code review must select actual final build')
    need(review.get('review_evidence'),'Concrete final code-review evidence required')
    for row in review['review_evidence']:reference(row)
    need(auth.get('schema')=='projectseele.r53.explicit-private-code-review-authorization.v1' and auth.get('draft')is not True and auth.get('user_authorized')is True and auth.get('private_two_packages_authorized')is True and auth.get('further_stress_validation_cancelled')is True and auth.get('user_request') and auth.get('qualification')==QUALIFICATION and auth.get('feature_scope')=='124' and Path(auth['world']).resolve()==world,'Exact latest user private/manual acceptance scope required')
    need(Path(pipeline['world']).resolve()==world and reference(pipeline['source_inputs']['selected_build_receipt'])==a.build_receipt.resolve() and pipeline['source_inputs']['selected_jar']['sha256']==build['sha256'],'Final Source association differs')
    need(Path(nav['world']).resolve()==world and nav['jar_sha256']==build['sha256'] and nav['current_round']is True and nav['installed']is True,'Current final navigation byte receipt required')
    reviewrow=ref(a.code_review);rows={name:dict(path=str((a.source_pipeline.parent/name).resolve()),sha256=pipeline['reports'][name])for name in SOURCE_REPORTS}
    for row in rows.values():reference(row)
    walking=world/'r53_personnel_walking_graph.json.gz';walkingrow=ref(walking)
    bundle=read(world/'ROOT_ASSEMBLY_BUNDLE.json');need(nav['directory_fingerprint']==bundle['directory_fingerprint'],'Current accepted directory identity differs')
    checks={name:dict(status='RUNTIME_UNVERIFIED',runtime_verified=False,evidence=[reviewrow],note='代码审查与现有事实保留；本固定版本的实际功能、画面或性能等待人工验收。')for name in sorted(SCOPE124_ACCEPTANCE)}
    report=dict(schema='projectseele.r53.private-code-reviewed-acceptance.v1',draft=False,release_ready=True,release_type='code_reviewed_runtime_unverified',qualification=QUALIFICATION,private_delivery=True,manual_acceptance_required=True,native_verified=False,
        verification_scope='FINAL_SOURCE_CODE_REVIEW_WITH_EXACT_CURRENT_WORLD_BYTES',feature_scope='124',deferred_scope=['3_yashima_combat','6_unrelated_global_configuration'],world=str(world),jar_sha256=build['sha256'],directory_fingerprint=bundle['directory_fingerprint'],known_implementation_blockers=[],code_review_complete=True,
        code_review_authorization=ref(a.authorization),code_review_receipt=reviewrow,code_review_build_receipt=buildrow,checks=checks,
        bindings=dict(schema='projectseele.r53.current-release-bindings.v1',source_pipeline=ref(a.source_pipeline),source_reports=rows,navigation=dict(files=nav['files'],receipt=ref(a.navigation_receipt)),walking_navigation=walkingrow,native_installation=dict(status='RUNTIME_UNVERIFIED')),
        preserved_observations=review.get('preserved_observations',[]),runtime_not_verified=sorted(SCOPE124_ACCEPTANCE),status_for_user='代码审查完成并构建通过；固定人工验收版本，运行功能、画面和性能尚未完成验收。')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8');print(json.dumps(dict(acceptance=ref(a.out),qualification=QUALIFICATION,native_verified=False,world_written=False,jar_bytes_not_rescanned=True),ensure_ascii=True))
if __name__=='__main__':main()
