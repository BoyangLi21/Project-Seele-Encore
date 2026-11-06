"""Root consumes exact actual-mesh door notches, preserving all controlled seals."""
import argparse,gzip,hashlib,json
from pathlib import Path
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from query_blocks import iter_block_entities
from prepare_terminal_move_r52 import runs

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];folder=root/'artifacts/r52_original_owner_candidate_20261010'
    source=folder/'ACTUAL_FINAL_DOOR_CIVIL_MEASUREMENTS_OCT11.json';d=json.loads(source.read_text('utf8'));table=folder/d['unique_extra_notches']['file']
    assert hashlib.sha256(table.read_bytes()).hexdigest()==d['unique_extra_notches']['sha256']
    with gzip.open(table,'rt',encoding='utf8')as f:cells=json.load(f)
    assert len(cells)==21955 and len({tuple(c['position'])for c in cells})==21955
    out=BASE/'vertical_gate_pockets';stage='nine_exact_machine_cassettes';assert not list((out/stage).glob('applied_*'))
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-960,320));snapshots=[];count=0
    for group in(0,1,2):
        rows=[c for c in cells if(0 if c['position'][2]>200 else 1 if c['position'][2]>0 else 2)==group]
        pts=np.asarray([r['position']for r in rows]);lo=tuple(map(int,pts.min(0)));hi=tuple(map(int,pts.max(0)));a,names=measure(lo,hi)
        if 'minecraft:air'not in names:names.append('minecraft:air')
        ids={s:i for i,s in enumerate(names)};b=a.copy()
        for row in rows:
            x,y,z=row['position'];key=y-lo[1],z-lo[2],x-lo[0]
            assert names[int(a[key])]==row['before'],(row['position'],row['before'],names[int(a[key])])
            assert row['after']=='minecraft:air'and row['before']!='minecraft:barrier'
            b[key]=ids['minecraft:air']
        for pos,tag in iter_block_entities(vox.WORLD,vox.DIM,lo,hi):
            x,y,z=pos;assert a[y-lo[1],z-lo[2],x-lo[0]]==b[y-lo[1],z-lo[2],x-lo[0]],(pos,str(tag['id']))
        count+=runs(painter,lo,a,b,names,'R52_exact_door_source_clearance');snapshots.append((lo,hi,b,names))
    assert count==21955
    painter.meta.update(root_author=True,source_measurement_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),sealed_cells_preserved=36828)
    plan=painter.save_plan(stage);receipt=dict(world_written=False,cells=count,door_count=9,sealed_cells_preserved=36828,source_measurement_sha256=painter.meta['source_measurement_sha256'],native_acceptance=False)
    if args.apply:
        receipt['application']=painter.apply(stage)
        for lo,hi,b,names in snapshots:
            a,p=measure(lo,hi);ids={s:i for i,s in enumerate(names)};assert np.array_equal(np.asarray([ids[s]for s in p])[a],b)
        receipt.update(world_written=True,exact_whole_readback=True)
    (plan/'PLAN.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
