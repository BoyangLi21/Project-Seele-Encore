"""Root applies the exact reviewed square-basin ops, never regenerating them."""
from pathlib import Path
import argparse,json,gzip,hashlib,msvcrt
import regional_voxels as vox
from extend_world_depth_r52 import acquire_world_lock
from r52_spatial_plan import BASE

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--review',type=Path,required=True);ap.add_argument('--review-sha256',required=True);a=ap.parse_args()
    review=a.review.resolve();assert sha(review)==a.review_sha256
    data=json.loads(review.read_text('utf-8-sig'));assert data['status']=='PASS' and not data['world_written']
    candidate=BASE/'final_map_audit/tv_square_reservoir_nw/aligned_square_northwest_corner'
    out=BASE/'final_map_audit/tv_square_reservoir_nw/ROOT_ACTUAL_INSTALL_20261012'
    assert not out.exists(),'Do not replay or reset an installed stage'
    locks=data['source_locks']
    for p,h in locks.items():assert sha(p)==h,('Reviewed source changed',p)
    assert any(Path(p).resolve()==(candidate/'ops.json.gz').resolve()for p in locks)
    assert any(Path(p).resolve()==(candidate/'EXPECTED.npz').resolve()for p in locks)
    plan=json.loads((candidate/'PLAN.json').read_text('utf8'));assert plan['changed_cells']==1976106 and not plan['world_written']
    assert data['candidate_actual_delta_cells']==plan['changed_cells']
    # Native input and all edits remain explicit under the one construction save.
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-960,320))
    for op in json.loads(gzip.decompress((candidate/'ops.json.gz').read_bytes())):
        assert op['mode']=='exact' and len(op['extra'])==1
        painter.exact(op['box'],op['extra'][0],op['state'],op['owner'])
    painter.meta=json.loads((candidate/'places.json').read_text('utf8'))
    painter.meta.update(reviewed_candidate=str(candidate),reviewed_ops_sha256=sha(candidate/'ops.json.gz'),review_receipt_sha256=sha(review))
    lock=acquire_world_lock()
    try:
        for p,h in locks.items():assert sha(p)==h,('Source changed before held-lock application',p)
        receipt=painter.apply('aligned_square_northwest_corner',session_lock=lock)
        result=dict(world_written=True,world=str(vox.WORLD),review=str(review),review_sha256=sha(review),candidate_ops_sha256=sha(candidate/'ops.json.gz'),candidate_expected_sha256=sha(candidate/'EXPECTED.npz'),changed_cells=plan['changed_cells'],receipt=receipt,native_art_accepted=False,source_candidate_kept_immutable=True)
        (out/'APPLIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
        print(json.dumps(result,ensure_ascii=False),flush=True)
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
