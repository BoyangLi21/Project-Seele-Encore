"""Freeze a mixed-layer untouched calibration and the installed first-prefix provenance."""
from pathlib import Path
import argparse,hashlib,json
from collections import Counter

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/ecology';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
    old=ART/'uniform_3d_configuration_v1/calibration.json';base=json.loads(old.read_text('utf8'))
    installed={(q['x'],q['z'],q['layer']) for q in base['chunks']}
    completed=old.with_name(old.name+'.complete.json');result=old.with_name('calibration.result.json')
    proof=json.loads(completed.read_text('utf8'));native=json.loads(result.read_text('utf8'))
    assert proof['complete'] and proof['completed_origins']==15 and native['native_preview_complete']
    assert all(not(not r['placed'] and r['candidate_cells']>0) for r in native['feature_trials'])
    receipts=list((ART/'replay_native_calibration_393_v1').rglob('receipt.json'));assert len(receipts)==2
    for r in receipts:assert json.loads(r.read_text('utf8'))['verified']
    manifest=ART/'layer_resolved_infrastructure_single_jvm_v4_uniform_guard/manifest.json';selection=json.loads(manifest.read_text('utf8'))
    available={};allq=[];by_key={}
    for path in selection['jobs']:
        job=json.loads(Path(path).read_text('utf8'))
        for q in job['chunks']:
            k=q['x'],q['z'],q['layer'];by_key[k]=q;available[k]=job['available_chunks'];allq.append(q)
    groups=[];chosen=[];used=set(installed)
    def select(label,layer,biome,target,count,min_soil=200):
        candidates=[q for q in allq if q['layer']==layer and (not biome or q['biome'].endswith(biome)) and q['measured_soil_cells']>=min_soil and (q['x'],q['z'],q['layer']) not in used]
        candidates.sort(key=lambda q:(q['x']*16+8-target[0])**2+(q['z']*16+8-target[1])**2)
        picked=candidates[:count];assert len(picked)==count
        for q in picked:used.add((q['x'],q['z'],q['layer']));chosen.append(q)
        groups.append(dict(role=label,origin_keys=[[q['x'],q['z'],q['layer']] for q in picked]))
    for key in [(-64,18,'surface'),(-62,18,'surface'),(-62,19,'surface')]:
        q=by_key[key];assert key not in used;chosen.append(q);used.add(key)
    groups.append(dict(role='Actual natural ground below the installed elevated viaduct, no XY-only exclusion',origin_keys=[list(k) for k in used-installed]))
    select('Surface meadow', 'surface','_meadow',[-2300,800],2)
    select('Surface woodland','surface','_woodland',[-2300,800],2)
    select('Surface highland','surface','_highland',[-2300,800],2)
    select('Uncovered cavern woodland','geofront','_woodland',[-700,440],3)
    select('Uncovered cavern meadow','geofront','_meadow',[-680,740],3)
    assert len(chosen)==15 and not installed&{(q['x'],q['z'],q['layer']) for q in chosen}
    halo=set()
    for q in chosen:
        k=q['x'],q['z'],q['layer'];declared={tuple(p) for p in available[k]}
        neighbourhood={(q['x']+dx,q['z']+dz) for dx in (-1,0,1) for dz in (-1,0,1)}
        assert neighbourhood<=declared;halo.update(neighbourhood)
    a.output.mkdir(parents=True)
    prefix=dict(installed_origin_keys=[list(k) for k in sorted(installed)],native_input=str(old),native_input_sha256=sha(old),
        native_complete=str(completed),native_complete_sha256=sha(completed),native_result=str(result),native_result_sha256=sha(result),
        applied_cells=3573,applied_biome_sections=86,applied_biome_quarts=3986,
        receipts=[dict(path=str(r),sha256=sha(r)) for r in receipts],
        inheritance='Prior 66 native trials contain no false placement with staged writes; adding whole-false rollback does not invalidate this applied prefix. Existing natural growth/state remains current authority. Do not replay or count this prefix as new trees.',world_written=False)
    (a.output/'installed_prefix.json').write_text(json.dumps(prefix,ensure_ascii=False,indent=2),'utf8')
    job=dict(base,chunks=chosen,available_chunks=[list(k) for k in sorted(halo)],require_staging_controls=True,
        calibration_scope=groups,installed_prior_prefix_provenance=str((a.output/'installed_prefix.json').resolve()))
    (a.output/'calibration.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),'utf8')
    (a.output/'selection.json').write_text(json.dumps(dict(groups=groups,layer_counts=dict(Counter(q['layer'] for q in chosen)),
        no_prior_installed_origin_repeated=True,prior_prefix_origins=15,all_origins_measured_complete_from_frozen_selection=True,
        world_written=False,native_execution_pending=True),ensure_ascii=False,indent=2),'utf8')
    print('New mixed calibration',len(chosen),'origins',dict(Counter(q['layer'] for q in chosen)),'halo',len(halo),'installed prefix retained15')


if __name__=='__main__':main()
