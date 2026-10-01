"""One exact 3D feature protection set for shipped source and effective world pack."""
from pathlib import Path
import argparse, hashlib, json
from validate_ecology_plans_r44 import verify_blocks

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44';WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
KEY='data/projectseele/dimension/geofront.json';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
    original=ART/'surface_network/hakone_tokyo_link_ready_v11/ecology_reservations.json'
    old=json.loads(original.read_text('utf8'));reservations=list(old['reservations']);receipts=[]
    additions=[('tokyo_harbour_link_v2','tokyo_harbour_link_ready_v2',[244,78,514,286,86,526]),
               ('harbour_active_s1_link_v2','harbour_active_s1_link_ready_v2',[378,79,228,386,83,230])]
    for name,folder,bounds in additions:
        receipt=next((ART/'ecology'/('replay_'+name)/name).glob('applied_*/receipt.json'))
        actual=json.loads(receipt.read_text('utf8'));assert actual.get('verified',actual.get('verified_native_states',False))
        inverse=ART/'surface_network'/folder/'inverse.jsonl.gz';assert verify_blocks(inverse)['passed'],'Full applied road states/NBT changed'
        receipts.append(dict(path=str(receipt),sha256=sha(receipt),inverse_current_readback=str(inverse),inverse_sha256=sha(inverse)))
        reservations.append(dict(bounds=bounds,layer='surface',owner='r44/'+name,source_complete_apply=str(receipt)))
    assert len(reservations)==393
    a.output.mkdir(parents=True)
    protection=a.output/'ecology_reservations.json';protection.write_text(json.dumps(dict(old,reservations=reservations,source_original=str(original),source_original_sha256=sha(original),new_complete_road_receipts=receipts),indent=2),'utf8')
    providers=[]
    for i,target in enumerate([ROOT/'src/main/resources'/KEY,WORLD/'datapacks/tv_world_preview'/KEY]):
        before=target.read_bytes();data=json.loads(before);source=data['generator']['biome_source'];assert source['type']=='projectseele:regional_ecology'
        source['protected_volumes']=[r['bounds'] for r in reservations]
        candidate=json.dumps(data,ensure_ascii=False,indent=2)+'\n';new=a.output/f'provider_{i:02d}.after.json';backup=a.output/f'provider_{i:02d}.before.json'
        new.write_text(candidate,'utf8');backup.write_bytes(before)
        providers.append(dict(target=str(target.resolve()),before=str(backup.resolve()),after=str(new.resolve()),before_sha256=sha(backup),after_sha256=sha(new)))
    calibration=ART/'ecology/layer_resolved_calibration/calibration.json';job=json.loads(calibration.read_text('utf8'))
    job['protected_volumes']=[r['bounds'] for r in reservations];job['protected_infrastructure_source']=str(protection.resolve());job['protected_infrastructure_sha256']=sha(protection)
    job['require_staging_controls']=True
    (a.output/'calibration.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),'utf8')
    plan=dict(providers=providers,forward=[dict(target=r['target'],expected_sha256=r['before_sha256'],bytes_from=r['after']) for r in providers],
        inverse=[dict(target=r['target'],expected_sha256=r['after_sha256'],bytes_from=r['before']) for r in providers],
        protected_volumes=393,protection=str(protection.resolve()),protection_sha256=sha(protection),world_written=False,source_written=False,
        required='Root installs exact two provider candidates and cold-loads rebuilt source. Retrofit verifies exact list equality to the loaded source before the first origin. Freeze new 361 manifest after provider application; include the actual source/pack/type SHA and protection helper/mixin source epochs. Run native staging rejection/BE/budget controls and 15 actual feature origins before the 361 batches.',
        semantics='Features below an elevated protection volume remain eligible. A feature touching a protected member is rejected as a complete staged feature. No world daytime, road state, entity or transportation progress is copied.')
    (a.output/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),'utf8');print('Exact source/worldpack candidates',len(providers),'volumes393; installed road inverse preconditions PASS')


if __name__=='__main__':main()
