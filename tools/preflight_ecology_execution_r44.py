"""Read-only mandatory check of every input/current source/four effective provider epochs."""
from pathlib import Path
import argparse,json,hashlib

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('contract',type=Path);a=p.parse_args();c=json.loads(a.contract.read_text('utf8'));errors=[]
    manifest=Path(c['input']);data=json.loads(manifest.read_text('utf8'))
    if sha(manifest)!=c['input_sha256']:errors.append(dict(kind='manifest_hash',path=str(manifest)))
    for name in ['source_epochs','provider_epochs']:
        for e in c[name]:
            file=Path(e['path']);actual=sha(file) if file.exists() else None
            if actual!=e['sha256']:errors.append(dict(kind=name,path=str(file),expected=e['sha256'],actual=actual))
    for e in data['input_epochs']:
        file=Path(e['job'])
        if sha(file)!=e['sha256']:errors.append(dict(kind='native_input_epoch',path=str(file)))
    protection=Path(c['protected_infrastructure']);volumes=[r['bounds'] for r in json.loads(protection.read_text('utf8'))['reservations']]
    if sha(protection)!=c['protected_infrastructure_sha256']:errors.append(dict(kind='protection_hash'))
    for e in c['provider_epochs'][:2]:
        file=Path(e['path']);provider=json.loads(file.read_text('utf8'))
        if provider['generator']['biome_source']['protected_volumes']!=volumes:errors.append(dict(kind='actual_protection_list_mismatch',path=str(file)))
    seen=set()
    for name in data['jobs']:
        job=json.loads(Path(name).read_text('utf8'));assert len(job['chunks'])<=128 and len(job['available_chunks'])<=1152
        assert job['protected_volumes']==volumes and job['read_only'] and job.get('require_staging_controls',False)
        for q in job['chunks']:
            key=q['x'],q['z'],q['layer'];assert key not in seen;seen.add(key)
    prefix=data['installed_prefix_provenance'];pfx=Path(prefix['path']);assert sha(pfx)==prefix['sha256']
    installed={tuple(k) for k in json.loads(pfx.read_text('utf8'))['installed_origin_keys']};assert len(installed)==30 and not seen&installed and len(seen)==46177
    result=dict(passed=not errors,errors=errors,remaining_origins=len(seen),installed_prefix_origins=30,total_origins=46207,jobs=len(data['jobs']),
        checked_sources=len(c['source_epochs']),four_provider_epochs=len(c['provider_epochs']),world_written=False,native_started=False,
        root_must_still_verify='Current compiled runtime/resources must correspond to the source epochs. Final native complete marker, controls, per-origin coverage, merged-biome-only plans and exact inverse apply preflight remain separate mandatory steps.')
    target=a.contract.with_name('root_dispatch_preflight.json');target.write_text(json.dumps(result,indent=2),'utf8');print(json.dumps({k:v for k,v in result.items() if k!='errors'}),flush=True)
    if errors:print('Blocked: input/source/provider epochs are not installed or have changed',len(errors),flush=True);raise SystemExit(1)


if __name__=='__main__':main()
