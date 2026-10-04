"""Single Root writer entry for a named full City96 transaction. Default check is read-only."""
from pathlib import Path
import argparse, gzip, hashlib, importlib.util, io, json, sys
import nbtlib
from prepare_city_atomic_binding_r45 import check_plan, read, sha
import install_city_rigid_metadata_r45 as metadata

ROOT=Path(__file__).resolve().parents[1]

def codec_module():
    path=ROOT/'artifacts/rebuild_r45/terrain_global_agent/stream_exact_install_r45_v2.py'
    spec=importlib.util.spec_from_file_location('city_candidate_shared_exact_codec',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def known_candidate(plan,world):
    expected={k:{v} for k,v in plan['composition_files'].items()};bundle=Path(plan['metadata_bundle']);manifest=read(bundle/'manifest.json')
    journal=Path(plan['journal']);run=read(journal/'run.json') if (journal/'run.json').exists() else None
    if run:
        assert run['world']==str(world) and run['manifest_sha256']==plan['static_manifest']['sha256']
        for row in run['regions']:
            if 'before_sha256' not in row:continue
            path=Path(row['current_region']);assert path.is_relative_to(world)
            relative=path.relative_to(world).as_posix();assert row['before_sha256'] in expected[relative]
            if row.get('after_sha256'):expected[relative].add(row['after_sha256'])
    wal=read(bundle/'metadata_wal.json') if (bundle/'metadata_wal.json').exists() else None
    if wal:
        assert wal['manifest_sha256']==sha(bundle/'manifest.json') and wal['world_id']==plan['world_id']
        for row in manifest['operations']:
            expected[row['target']]={v for v in (row['before_sha256'],row['after_sha256']) if v is not None}
        expected[manifest['marker_target']]={sha(bundle/manifest['installing_marker'])}
        if wal.get('marker_after_sha256'):expected[manifest['marker_target']].add(wal['marker_after_sha256'])
        elif wal.get('root_proof_sha256'):
            tag=nbtlib.load(bundle/manifest['installed_marker']);tag['data']['NativeStructurePassed']=nbtlib.Byte(1);tag['data']['ExactCargoMigrationPassed']=nbtlib.Byte(1)
            tag['data']['RootStaticProofSHA256']=nbtlib.String(wal['root_proof_sha256']);tag['data']['RuntimeEnabled']=nbtlib.Byte(0)
            stream=io.BytesIO();tag.write(stream)
            expected[manifest['marker_target']].add(hashlib.sha256(gzip.compress(stream.getvalue(),compresslevel=1,mtime=0)).hexdigest())
    actual={p.relative_to(world).as_posix():p for p in world.rglob('*') if p.is_file() and p.name!='session.lock'}
    for relative,path in actual.items():assert relative in expected and sha(path) in expected[relative],'Unowned full file/progress bytes changed: '+relative
    # Only transaction-defined newly created metadata/marker can be absent at an interrupted phase.
    optional={r['target'] for r in manifest['operations'] if r['before_sha256'] is None}|{manifest['marker_target']}
    assert set(expected)-set(actual)<=optional,'Original candidate/progress file disappeared'
    assert not metadata.metadata_current_errors(world,manifest)
    return manifest,wal

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',required=True,type=Path)
    ap.add_argument('--action',choices=['check','preflight-static','stage-metadata','replay-static','finish-metadata','rollback-static','rollback-metadata'],default='check')
    ap.add_argument('--execute-root',action='store_true');ap.add_argument('--root-proof',type=Path);args=ap.parse_args()
    plan,world=check_plan(args.plan.resolve());manifest,wal=known_candidate(plan,world);codec=codec_module();codec.TARGET=world
    journal=Path(plan['journal']);bundle=Path(plan['metadata_bundle']);action=args.action
    if action=='check':print(json.dumps(dict(read_only=True,world_written=False,entire_city_cells=2859160,metadata_operations=807,phase=wal['phase'] if wal else 'NOT_STAGED',runtime_enabled=False)));return
    mutating=action!='preflight-static'
    if mutating:assert args.execute_root,'Only an explicit Root writer may mutate the candidate'
    if action in ('preflight-static','replay-static','rollback-static'):
        if action=='replay-static':assert wal and wal['phase']=='INSTALLING','Complete durable metadata stage/legacy inhibition precedes geometry replay'
        if action=='rollback-static':assert wal and wal['phase'] in ('INSTALLING','APPLYING_METADATA','INSTALLED_DISABLED','ROLLING_BACK_METADATA'),'Keep exact ownership while rolling static inverse back'
        with codec.locked_journal(journal):
            m,run,db=codec.stage(Path(plan['static_manifest']['path']),journal,resume=journal.exists())
            try:
                assert run['final_exact_cells']==2859160 and run['source_rows']==2859160
                if action=='preflight-static':codec.preflight(m,run,db,journal)
                else:codec.install(m,run,db,journal,rollback=action=='rollback-static')
            finally:db.close()
        return
    if action=='finish-metadata':
        run=read(journal/'run.json');assert run['phase']=='COMPLETE' and run['all_exact_final_actual_voxels_and_nbt_readback']
        assert args.root_proof and args.root_proof.resolve().is_relative_to(args.plan.resolve().parent),'Keep the named complete static proof with this exact binding'
    if action=='rollback-metadata':
        assert args.root_proof and read(journal/'run.json')['phase']=='ROLLED_BACK','Exact static inverse must complete before releasing old generators'
    call=[str(bundle),'--world',str(world),'--'+action.split('-')[0]+'-root']
    if args.root_proof:call+=['--root-proof',str(args.root_proof.resolve())]
    old_argv=sys.argv
    try:
        # The shared metadata implementation retains its UUID/depth/SHA/proof checks.
        # This exact outer lease adds absolute-world and all-progress guards and a physical lock.
        with codec.locked_journal(args.plan.resolve().parent/'metadata_controller'),codec.locked_world():
            known_candidate(plan,world);sys.argv=['install_city_rigid_metadata_r45.py',*call];metadata.main()
    finally:sys.argv=old_argv

if __name__=='__main__':main()
