"""Root's full physical after-readback, before enabling four appended city members."""
from pathlib import Path
import argparse,gzip,json,sys
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
import regional_voxels as v

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--world',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    base=ROOT/'artifacts/rebuild_r48';world=a.world.resolve();a.out=a.out.resolve()
    if world not in ((base/'construction/SEELE_R48_WORLD').resolve(),(base/'native_qa/worlds/SEELE_R48_QA').resolve()):raise ValueError('Explicit Root source or retained QA only')
    candidate=base/'city/c03_lowrise_restore_final_v2';manifest=json.loads((candidate/'manifest.json').read_text('utf8'))
    expected={};boxes=[]
    for component in manifest['components']:
        box=component['complete_static_and_clearance_inspection_box'];boxes.append(box)
        with gzip.open(component['full_before_preimage'],'rt',encoding='utf8')as stream:
            for line in stream:
                row=json.loads(line);expected[tuple(row['pos'])]=(row['state'],row['full_nbt'])
    with gzip.open(candidate/'forward.jsonl.gz','rt',encoding='utf8')as stream:
        for line in stream:
            row=json.loads(line);expected[tuple(row['pos'])]=(row['after'],row['after_nbt'])
    measured=MeasuredWorld(world)
    for b in boxes:measured.box(b[:3],b[3:])
    measured.load();nbts={}
    for b in boxes:nbts.update(iter_block_entities(world,v.DIM,b[:3],b[3:]))
    for point,(state,data)in expected.items():
        if measured.block(point)!=state:raise ValueError(('Complete component after mismatch',point,state,measured.block(point)))
        target=None if data is None else nbtlib.parse_nbt(data)
        if nbts.get(point)!=target:raise ValueError(('Complete block-entity after mismatch',point))
    control='projectseele_city_rigid_control_r45_8246338109520.dat';directory=world/'dimensions/projectseele/geofront/data'
    if (directory/control).read_bytes()!=(candidate/'metadata_before'/control).read_bytes():raise ValueError('Original complete settled city ledger changed')
    result=dict(world=str(world),complete_after_cells=len(expected),changed_cells=manifest['changed_cells'],complete_four_templates_shafts_lattice_support_and_NBT_equal=True,
        original_settled_ledger_bytes_unchanged=True,world_written=False,native_motion_verified=False)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2),'utf8');print(result)

if __name__=='__main__':main()
