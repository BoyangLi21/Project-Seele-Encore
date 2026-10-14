"""Root exact notches for the finally measured lower-frame machine source."""
import argparse,hashlib,json
from pathlib import Path
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure

def main():
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    source=root/'artifacts/r52_original_owner_candidate_20261010/ACTUAL_FINAL_LOWER_SOURCE_NOTCH_OCT11.json'
    report=json.loads(source.read_text('utf8'))
    assert hashlib.sha256((root/'src/main/resources/assets/projectseele/mesh/cage_lower_telescopes_r52.json').read_bytes()).hexdigest()==report['source_sha']
    cells=[c for u in report['units'] for c in u['cells']];assert len(cells)==144
    assert len({tuple(c['position'])for c in cells})==144
    out=BASE/'carrier_service_pits';stage='final_lower_frame_source_pockets'
    assert not list((out/stage).glob('applied_*'))
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-960,320))
    for c in cells:
        pos=tuple(c['position']);a,pal=measure(pos,pos)
        assert pal[int(a[0,0,0])]==c['state'],(pos,pal)
        assert c['state']=='projectseele:nerv_shaft_panel'
        painter.exact((*pos,*pos),c['state'],'minecraft:air','R52_actual_lower_frame_recess')
    painter.meta.update(root_author=True,actual_source_sha256=report['source_sha'])
    plan=painter.save_plan(stage)
    receipt=dict(world_written=False,source_measurement_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),actual_machine_source=report['source_sha'],cells=144)
    if args.apply:
        receipt['application']=painter.apply(stage)
        for c in cells:
            pos=tuple(c['position']);a,pal=measure(pos,pos);assert pal[int(a[0,0,0])]=='minecraft:air'
        receipt.update(world_written=True,all_144_exact_readback=True)
    (plan/'PLAN.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
