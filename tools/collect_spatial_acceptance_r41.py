"""Merge immutable native results only where their exact current paths match."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'


def read(path):return json.loads(path.read_text('utf8'))


def main():
    full=ART/'native_spatial/full';results={}
    sources=[full/'edges_results.json',full/'passages_results.json',ART/'native_spatial/final_recheck_results.json']
    for path in sources:
        for r in read(path):results[r['id']]=r
    current=read(full/'passages.json');focused=[r for r in read(full/'edges.json') if 'barrier' not in r]
    public={r['id']:r for r in current+focused if 'barrier' not in r};evidence=[]
    for key,row in public.items():
        proof=results.get(key);assert proof and proof['status']=='pass',(key,proof and proof['status'])
        for k in ('path','start','end'):
            if k in row:assert row[k]==proof.get(k),('Path changed after its native proof',key,k)
        evidence.append(proof)
    equipment=read(ART/'native_spatial/fixed_weapon_exemptions.json');excepted={r['id'] for r in equipment['excluded_probes']}
    safety=[r for r in read(full/'edges.json') if 'barrier' in r]
    for row in safety:
        proof=results[row['id']]
        if row['id'] in excepted:
            assert proof['status']=='probe_start_obstructed' and any('entity.superbwarfare.hpj_11 ' in s for s in proof.get('nearbyEntities',[]))
        else:assert proof['status']=='pass',(row['id'],proof['status'])
    endpoint=[r for r in read(ART/'native_spatial/final_recheck_results.json') if r['id'].startswith('r41/endpoint/')]
    assert len(endpoint)==read(ART/'native_spatial/final_recheck_manifest.json')['one_way_endpoint_probes'] and all(r['status']=='pass' for r in endpoint)
    nav=read(ART/'navigation/navigation_manifest.json');assert hashlib.sha256((ROOT/'run/saves/SEELE_FIELD_R41_REVIEW'/nav['file']).read_bytes()).hexdigest()==nav['sha256']
    connect=read(ART/'navigation/destination_connectivity.json');assert all(all(row) for row in connect['reachable_pairs'])
    signs=read(ART/'signage/contract.json');assert not signs['unreadable']
    (ART/'final_public_passages.json').write_text(json.dumps(list(public.values()),ensure_ascii=False),'utf8')
    (ART/'final_passage_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False),'utf8')
    (ART/'final_safety_evidence.json').write_text(json.dumps([results[r['id']] for r in safety],ensure_ascii=False),'utf8')
    report=dict(passed=True,public_passages=len(public),safety_passes=len(safety)-len(excepted),fixed_weapon_probe_exclusions=len(excepted),one_way_endpoint_checks=len(endpoint),
                source_files=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources],navigation=nav,
                rejected_navigation_edges=read(ART/'navigation/boundary_collision_audit.json')['blocked_candidate_edges'],direction_boards=len(signs['updated']),
                scope='Actual native voxel movement, whole-flight widths, supported grade transitions and dangerous edges. Fixed HPJ11 occupied starts are explicitly not counted as human walking passes. Does not assert arbitrary natural terrain or every aesthetic view is defect-free.')
    (ART/'spatial_acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(report,flush=True)


if __name__=='__main__':main()
