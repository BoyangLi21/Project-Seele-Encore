"""Install the nine frame-derived controls against actual original wall faces."""
from pathlib import Path
import argparse
import hashlib
import json
import msvcrt
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import read_box, iter_block_entities


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'hangar_operator_controls'
    assert not (out/'APPLIED.json').exists()
    plan=json.loads((base/'ROOT_SPATIAL_PLAN.json').read_text('utf8'))
    assert plan['components']['hangar']==dict(turn=180,dx=60,dy=-620,dz=88)
    assert plan['delivery_scope']['id']=='scope124'
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-1344,320));rows=[]
    state='minecraft:polished_blackstone_button[face=wall,facing=west,powered=false]'
    for variant,x in enumerate((91,49,7)):
        for action,z in zip(('PREPARE','STATUS','CANCEL'),(342,340,338)):
            q=(x,-1013,z);back=(x+1,-1013,z)
            before=read_box(world,vox.DIM,q,back)
            assert before[q]=='minecraft:air', (q,before[q])
            assert before[back] in ('projectseele:nerv_machine_edge','projectseele:nerv_shaft_panel'),(back,before[back])
            assert not list(iter_block_entities(world,vox.DIM,q,back))
            painter.exact((*q,*q),'minecraft:air',state,'current_original_gantry_operator_key')
            rows.append(dict(variant=variant,action=action,position=q,state=state,
                             backing=back,backing_state=before[back]))
    source=Path(__file__).resolve().parents[1]/'src/main/java/com/projectseele/world/NervHangarControlsR53.java'
    painter.meta.update(root_author=True,source_code_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                        original_frames_unchanged=True,native_interaction_pending=True)
    painter.save_plan('nine_frame_derived_controls')
    report=dict(world_written=False,buttons=rows,declared_geometry_only=True,
                actual_native_button_shape_and_runtime_check_pending=True)
    (out/'CANDIDATE.json').write_text(json.dumps(report,indent=2),'utf8')
    if not a.apply:return
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('nine_frame_derived_controls',session_lock=lock)
        for row in rows:
            q=tuple(row['position']);back=tuple(row['backing'])
            actual=read_box(world,vox.DIM,q,back)
            assert actual[q]==row['state'] and actual[back]==row['backing_state']
        report.update(world_written=True,exact_installed_buttons_read_back=9,receipt=receipt)
        (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8')
        print(json.dumps(dict(installed_buttons=9,receipt=receipt)),flush=True)
    finally:
        msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
