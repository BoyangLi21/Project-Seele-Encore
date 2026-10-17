"""Rebind only the personnel-manifest revision of the same saved installation.

The installed directory, epoch, routes, mechanical owner, identities, pending
request mode and job progress must all remain unchanged. This is an exact
offline configuration migration, not removal of restoration/claim guards.
"""
from pathlib import Path
import argparse
import copy
import gzip
import hashlib
import io
import json
import msvcrt
import nbtlib
from apply_s20_approved_semantic_repairs import atomic_replace


def rebind(world,before_bundle,after_bundle):
    old=json.loads(before_bundle);new=json.loads(after_bundle)
    before=copy.deepcopy(old);after=copy.deepcopy(new)
    old_lifts=before.pop('personnel_lifts');new_lifts=after.pop('personnel_lifts')
    assert before==after and old_lifts['file']==new_lifts['file']=='personnel_lifts_r52.json'
    assert before_bundle!=after_bundle
    path=world/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat'
    data=nbtlib.load(path);original=copy.deepcopy(data);tag=data['data']
    old_key=hashlib.sha256(before_bundle).hexdigest();new_key=hashlib.sha256(after_bundle).hexdigest()
    assert int(tag['Epoch'])==new['epoch'] and str(tag['DirectoryFingerprint'])==new['directory_fingerprint']
    assert bool(tag['Claimed']) and not str(tag.get('Fault',''))
    changed=[]
    if 'InstallationBundleSHA' in tag:
        assert str(tag['InstallationBundle'])=='ROOT_ASSEMBLY_BUNDLE.json'
        assert str(tag['InstallationBundleSHA'])==old_key
        tag['InstallationBundleSHA']=nbtlib.String(new_key);changed.append('InstallationBundleSHA')
    if 'PendingInstallation' in tag:
        pending=tag['PendingInstallation']
        assert str(pending['Bundle'])=='ROOT_ASSEMBLY_BUNDLE.json' and str(pending['SHA'])==old_key
        assert int(pending['Epoch'])==new['epoch'] and str(pending['Directory'])==new['directory_fingerprint']
        pending['SHA']=nbtlib.String(new_key);changed.append('PendingInstallation/SHA')
    assert changed
    check=copy.deepcopy(data)
    if 'InstallationBundleSHA' in changed:check['data']['InstallationBundleSHA']=original['data']['InstallationBundleSHA']
    if 'PendingInstallation/SHA' in changed:check['data']['PendingInstallation']['SHA']=original['data']['PendingInstallation']['SHA']
    assert check.snbt()==original.snbt(),'Non-configuration runtime progress changed'
    stream=io.BytesIO();data.write(stream)
    return path,gzip.compress(stream.getvalue(),mtime=0),changed


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,required=True);ap.add_argument('--world',type=Path,required=True)
    args=ap.parse_args();base=args.base.resolve();world=args.world.resolve()
    assert world in [base/'CANDIDATE',base/'server/SEELE_R53_ACCESS_TEST']
    out=base/'personnel-access-install';backup=out/('runtime_reference_before_'+world.name+'.dat')
    assert not backup.exists(),'Reference already migrated; inspect rather than replay'
    lock=(world/'session.lock').open('r+b');msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        path,raw,changed=rebind(world,(out/'before_ROOT_ASSEMBLY_BUNDLE.json').read_bytes(),(world/'ROOT_ASSEMBLY_BUNDLE.json').read_bytes())
        backup.write_bytes(path.read_bytes());atomic_replace(path,raw);assert path.read_bytes()==raw
        (out/('runtime_reference_'+world.name+'.json')).write_text(json.dumps(dict(world=str(world),changed_paths=changed,
            original_directory_epoch_identities_jobs_and_pending_mode_preserved=True),indent=2),'utf8')
        print(world.name,'same-installation personnel reference updated; all job and actor state preserved')
    finally:lock.close()


if __name__=='__main__':main()
