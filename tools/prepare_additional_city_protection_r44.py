"""Exact additive provider candidates; preserve every current 3D protection.

Only root may install these bytes and refreeze/revalidate the ecology epochs.
"""
from pathlib import Path
import argparse,json,hashlib,shutil,re
from prepare_city_ecology_protection_r44 import compress_columns

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--city',type=Path,action='append',required=True);a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    plans=[];new=[]
    for city in a.city:
        candidates=list(city.glob('construction_contract_refrozen_v*.json'))
        contract=max(candidates,key=lambda q:int(re.search(r'_v(\d+)',q.stem).group(1))) if candidates else city/'construction_contract.json'
        c=json.loads(contract.read_text('utf8'))
        assert c['static_full_component_passed'] and c['exact_current_preconditions_passed'] and c['station_journeys_complete']
        receipts=[q for q in (city/'root_install').rglob('receipt.json') if q.parent.name.startswith('applied_')]
        assert receipts,('Actual city installation receipt required',city)
        receipt=max(receipts,key=lambda q:q.parent.name);applied=json.loads(receipt.read_text('utf8'))
        assert applied['verified'] and Path(applied['world']).resolve()==WORLD.resolve(),('Unverified/different world city receipt',receipt)
        file=city/'ecology_reservations.json';data=json.loads(file.read_text('utf8'))['reservations'];new.extend(data)
        plans.append(dict(city=str(city.resolve()),contract=str(contract.resolve()),contract_sha256=sha(contract),reservation_sha256=sha(file),
                          actual_installed_receipt=str(receipt.resolve()),actual_installed_receipt_sha256=sha(receipt),
                          native_and_art_quality_separate=True))
    new=compress_columns(new);unique={tuple(r['bounds']) for r in new};forward=[];inverse=[];reports=[]
    key='data/projectseele/dimension/geofront.json'
    for i,target in enumerate([ROOT/'src/main/resources'/key,WORLD/'datapacks/tv_world_preview'/key]):
        old=target.read_bytes();data=json.loads(old);provider=data['generator']['biome_source'];assert provider['type']=='projectseele:regional_ecology'
        before=provider['protected_volumes'];oldset={tuple(v) for v in before};add=sorted(unique-oldset);after=before+[list(v) for v in add]
        assert after[:len(before)]==before and oldset<=set(map(tuple,after));provider['protected_volumes']=after
        pre=a.output/f'provider_{i:02d}.before.json';post=a.output/f'provider_{i:02d}.after.json';pre.write_bytes(old);post.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
        forward.append(dict(target=str(target.resolve()),expected_sha256=sha(pre),bytes_from=str(post.resolve())))
        inverse.append(dict(target=str(target.resolve()),expected_sha256=sha(post),bytes_from=str(pre.resolve())))
        reports.append(dict(target=str(target.resolve()),existing_volumes=len(before),exact_old_prefix_preserved=True,added_volumes=len(add),total_volumes=len(after)))
    dependencies=[Path(__file__),ROOT/'tools/prepare_city_ecology_protection_r44.py'];snap=a.output/'source_inputs';snap.mkdir();epochs=[]
    for i,f in enumerate(dependencies):
        copy=snap/(str(i)+'_'+f.name);shutil.copy2(f,copy);epochs.append(dict(path=str(copy.resolve()),original_path=str(f.resolve()),sha256=sha(copy),immutable_snapshot=True))
    (a.output/'provider_plan.json').write_text(json.dumps(dict(forward=forward,inverse=inverse,reports=reports,city_epochs=plans,source_epochs=epochs,
        original30_prefix_unchanged=True,world_written=False,source_written=False,native_future_verified=False,
        requires=['Root confirms each current installed city receipt and performs an exact provider BEFORE hash check. Pending uninstalled landscape components are not included here.',
            'Root alone installs these protected_volumes-only additive provider bytes. No player/entity/traffic/progress data is involved.',
            'Any provider or compiled source change invalidates older full-ecology preflight; Root refreezes full46177/361batch contract and reruns preflight before its single4G author JVM.',
            'Do not slice, renumber or relabel the full ecology queue. New outside552-corridor volumes are not future-verified until Root native CARVERS and protection fixtures pass.']),indent=2),'utf8')
    print('Exact additive provider candidates',reports,'world/source unchanged',flush=True)


if __name__=='__main__':main()
