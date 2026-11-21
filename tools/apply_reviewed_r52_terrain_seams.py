"""Apply the frozen Root terrain ops without regenerating reviewed artifacts."""
from pathlib import Path
import json,gzip,msvcrt
import regional_voxels as vox
from extend_world_depth_r52 import acquire_world_lock
from fit_original_outer_guide_slots_r52 import sha
from r52_spatial_plan import BASE


def main():
    root=Path(__file__).resolve().parents[1]
    source=BASE/'final_map_audit/r45_seam_feather'
    out=source/'ROOT_FINAL_INSTALLED_20261012'
    assert not out.exists() or not list(out.iterdir()), 'Do not repeat or reset a terrain installation'
    out.mkdir(exist_ok=True)
    reviews=[root/'.Codex/r52_global_height_ownership_readonly/FINAL_SIX_ROOT_HEIGHT_AND_RIGID_TREE_REVIEW.json',root/'.Codex/r52_seam_feather_mechanics_readonly/FINAL_TREE_AWARE_SIX_PATCH_COMPLETE_READONLY.json']
    assert sha(reviews[0])=='2b3fb2da477a364970113293608b57ea3771bb76e88e5c474767d8594c776f66'
    assert sha(reviews[1])=='8b568a0cc3129eab79f64caec2eb3f113f29ccc0f9defe5e4c66441954895f1a'
    review=json.loads(reviews[1].read_text())
    assert not review['cross_patch_overlaps'] and not review['rail_new_soil_findings'] and not review['possible_removed_native_rail_support_soil']
    locks={}
    for rp in reviews:
        locks.update(json.loads(rp.read_text())['source_locks'])
    for p,h in locks.items():
        assert sha(p)==h,('Reviewed source changed',p)
    result=dict(schema='projectseele.r52.root-final-six-terrain-installation.v1',world_written=False,reviewed_sources={str(p):sha(p) for p in reviews},stages=[],native_art_passed=False,changed_cells=0)
    vox.WORLD,vox.OUT,vox.DIM=BASE/'WORLD_R52',out,'projectseele:geofront'
    lock=acquire_world_lock()
    try:
        for number,expected in [(6114,21861),(7670,137226),(8169,29214),(8801,73148),(9222,82354),(10621,93458)]:
            stage=f'component_{number}_natural_transition'
            folder=source/stage
            old=json.loads((folder/'PLAN.json').read_text())
            assert old['changed_cells']==expected and not old['pending_boundary_edges'] and not old['new_or_worsened_all_neighbor_edges']
            operations=json.loads(gzip.decompress((folder/'ops.json.gz').read_bytes()))
            painter=vox.Painter(vertical_bounds=(-960,320))
            for o in operations:
                assert o['mode']=='exact' and len(o['extra'])==1
                painter.exact(o['box'],o['extra'][0],o['state'],o['owner'])
            painter.meta=json.loads((folder/'places.json').read_text())
            painter.meta['reviewed_candidate_plan_sha256']=sha(folder/'PLAN.json')
            painter.meta['reviewed_candidate_ops_sha256']=sha(folder/'ops.json.gz')
            receipt=painter.apply(stage,session_lock=lock)
            item=dict(component=number,reviewed_candidate=str(folder),reviewed_plan_sha256=sha(folder/'PLAN.json'),reviewed_ops_sha256=sha(folder/'ops.json.gz'),expected_changed_cells=expected,world_written=True,receipt=receipt)
            (out/stage/'PLAN.json').write_text(json.dumps(item,indent=2),encoding='utf8')
            result['stages'].append(item)
            result['changed_cells']+=expected
            result['world_written']=True
            (out/'APPLIED.json').write_text(json.dumps(result,indent=2),encoding='utf8')
        assert result['changed_cells']==437261
        result['all_six_exact_readbacks_complete']=True
        (out/'APPLIED.json').write_text(json.dumps(result,indent=2),encoding='utf8')
        print('All six Root terrain patches applied with exact readback:',result['changed_cells'],flush=True)
    finally:
        msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()


if __name__=='__main__':main()
