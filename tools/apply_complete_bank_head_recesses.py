"""Eighteen measured, non-bearing voxel recesses for the actual bank head."""
import argparse,hashlib,json,msvcrt
from pathlib import Path
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import read_box,iter_block_entities


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--proof',type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args();base=a.base.resolve();world=base/'WORLD'
    root=Path(__file__).resolve().parents[1];out=base/'bank_head_recesses';assert not(out/'APPLIED.json').exists()
    proof=json.loads(a.proof.read_text('utf8'));rows=proof['cells']
    assert proof['deep_frame_source']==hashlib.sha256((root/'src/main/resources/assets/projectseele/mesh/legacy_deep_frame_r53.json').read_bytes()).hexdigest()
    assert len(rows)==18 and len({tuple(r['position']) for r in rows})==18
    assert all(not r['finite_any_face_contacts'] for r in rows)
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-1344,320))
    for row in rows:
        q=tuple(row['position']);x,y,z=q
        assert x in (87,45,3) and y in (-1035,-1034) and z in (140,92,44)
        assert row['before_state']=='projectseele:nerv_structural_panel'
        assert read_box(world,vox.DIM,q,q)[q]==row['before_state']
        assert not list(iter_block_entities(world,vox.DIM,q,q))
        painter.exact((*q,*q),row['before_state'],'minecraft:air','actual_bank_head_clearance_nonbearing_voxel_only')
    painter.meta.update(root_author=True,source_sha256=hashlib.sha256(a.proof.read_bytes()).hexdigest(),
                        independent_fixed_steel_geometry_preserved=True,finite_bearing_face_contacts=0)
    painter.save_plan('eighteen_nonbearing_head_recesses')
    if not a.apply:return
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('eighteen_nonbearing_head_recesses',session_lock=lock)
        for row in rows:
            q=tuple(row['position']);assert read_box(world,vox.DIM,q,q)[q]=='minecraft:air'
        report=dict(world_written=True,changed_cells=18,whole_changed_cell_readback=True,
                    original_fixed_steel_not_modified=True,receipt=receipt)
        (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
