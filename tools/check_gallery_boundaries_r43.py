"""Run the unchanged geometric detector against frozen and candidate surfaces."""
from pathlib import Path
import gzip,json
import audit_spatial_envelopes_r41 as detector

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43'

def main():
    folder=ART/'gallery_boundaries/complete_bearing_edges'
    with gzip.open(folder/'ops.json.gz','rt',encoding='utf8') as f:ops=json.load(f)
    coords={tuple(o['box'][:3]) for o in ops};cores=sorted({(x//16,y//16,z//16) for x,y,z in coords});report={}
    for label,world in [('before',ART/'source_world_backup'),('after',ROOT/'run/saves/SEELE_FIELD_R43_REVIEW')]:
        atlas=detector.Atlas(world,cores);rows=[r for c in cores for r in detector.inspect(atlas,c) if tuple(r['pos']) in coords]
        report[label]=dict(world=str(world),findings=rows,non_unknown_missing_shapes=sorted(atlas.missing-{'UNKNOWN'}))
    before={tuple(r['pos']) for r in report['before']['findings'] if r['kind']=='unguarded_drop'}
    after={tuple(r['pos']) for r in report['after']['findings'] if r['kind']=='unguarded_drop'}
    report.update(cells=len(coords),before_detected=len(before),after_detected=len(after),
        static_passed=before==coords and not after and not report['after']['non_unknown_missing_shapes'],
        native_passed=False,visual_self_review='PENDING after-repair photos',lifecycle='PENDING reload check')
    (ART/'gallery_boundaries/geometric_before_after.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Before detected',len(before),'/',len(coords),'after',len(after),'static passed',report['static_passed']);assert report['static_passed']

if __name__=='__main__':main()
