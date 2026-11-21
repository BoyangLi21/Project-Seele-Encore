"""Compare Root-observed original controller identities across a cold restart.

Candidate reports only. This never starts a game, installs or edits a world.
"""
from pathlib import Path
import argparse, json
CANDIDATE=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/runtime_directory/candidate').resolve()
def candidate_path(value):
    path=Path(value).resolve()
    if not path.is_relative_to(CANDIDATE):raise ValueError('Candidate report path required')
    return path
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before',type=candidate_path);parser.add_argument('after',type=candidate_path);parser.add_argument('--output',type=candidate_path,default=CANDIDATE/'NATIVE_COLD_RESTART_UUID_COMPARISON.json')
    args=parser.parse_args();before=json.loads(args.before.read_text(encoding='utf-8'));after=json.loads(args.after.read_text(encoding='utf-8'));checks=[]
    def check(name,okay):checks.append({'check':name,'pass':bool(okay)})
    check('Both snapshots were actual read-only native observations',all(not d.get('error') and d.get('world_written') is False and d.get('actor_task_or_pose_written') is False and d.get('chunks_requested') is False for d in (before,after)))
    for key in ('directory_fingerprint','epoch','persisted_world_relative_bundle','persisted_bundle_sha256','expected_bundle_sha256'):
        check('Same saved Root authority: '+key,before.get(key)==after.get(key) and before.get(key) not in ('',None))
    check('Exact bundle bytes match remembered native authority',before.get('persisted_same_bundle_authority') is True and after.get('persisted_same_bundle_authority') is True)
    a={r['uuid']:r for r in before.get('controllers',[])};b={r['uuid']:r for r in after.get('controllers',[])}
    check('Original controller roster preserved',a.keys()==b.keys() and len(a)==before.get('expected_original_controller_count')==after.get('expected_original_controller_count') and len(a)>=57)
    check('All original UUIDs loaded with current source in both observations',before.get('all_expected_original_uuid_and_source_observed') is True and after.get('all_expected_original_uuid_and_source_observed') is True)
    for uid in sorted(a.keys()&b.keys()):check('Same original role/type/source: '+uid,a[uid].get('role')==b[uid].get('role') and a[uid].get('actual_class')==b[uid].get('actual_class') and a[uid].get('loaded') is True and b[uid].get('loaded') is True and a[uid].get('actual_source_declared',True) is True and b[uid].get('actual_source_declared',True) is True)
    report={'world_written':False,'native_cycle_passed':False,'original_uuid_cold_restart_observation_valid':all(c['pass'] for c in checks),'before':str(args.before),'after':str(args.after),'checks':checks,'scope':'Compares actual Root-controlled native snapshots of UUID/type/source and saved bundle authority. Position clocks may advance normally. Physical transport, foundation and full-cycle acceptance remain separate Root checks.'}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'identity_observation_valid':report['original_uuid_cold_restart_observation_valid'],'checks':len(checks),'world_written':False}));raise SystemExit(0 if report['original_uuid_cold_restart_observation_valid'] else 2)
if __name__=='__main__':main()
