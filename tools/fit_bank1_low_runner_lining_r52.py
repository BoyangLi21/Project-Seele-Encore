"""Fit the existing R52 lower bank1 lining to the final low runner envelope.

Only below-foot height bands are measured. The original upper well, second
bank, loading floor, doors, equipment and structural panels stay untouched.
"""
import json, hashlib, msvcrt
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
import regional_voxels as vox
from query_blocks import iter_block_entities
from r52_spatial_plan import BASE
from prepare_continuous_upright_civil_r52 import xyz_for,cuboids
from extend_world_depth_r52 import acquire_world_lock

SOURCE=BASE/'continuous_upright/final_0262_bank1_lower_measurement'
OUT=BASE/'continuous_upright/final_0262_bank1_low_lining'
WORLD=BASE/'WORLD_R52';STAGE='clear_low_runner_floor_without_air_infill'

def main():
    assert not list((OUT/STAGE).glob('applied_*')), 'Never replay'
    src=np.load(SOURCE/'MEASURED_SOURCE.npz');meta=json.loads((SOURCE/'MEASURED_REPORT.json').read_text())
    assert meta['measured_height_range_m']==[-8.,0.] and meta['hulls_sha256']=='9807a1f2675872ade60661e310f1da5c4c435bc9a5c732ba6ece9310ab329c29'
    names=list(map(str,src['palette']));ids={s:i for i,s in enumerate(names)}
    def code(s):
        if s not in ids:ids[s]=len(names);names.append(s)
        return ids[s]
    air=code('minecraft:air');panel=code('projectseele:nerv_machine_panel');edge=code('projectseele:nerv_machine_edge')
    allowed={code(s) for s in ('minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]',
        'projectseele:nerv_machine_panel','projectseele:nerv_machine_edge','projectseele:nerv_shaft_panel','projectseele:nerv_strip_light[lit=true]')}
    selected=defaultdict(set)
    for cx,cz,sy in src['section_keys']:selected[int(cx),int(cz)].add(int(sy))
    devices={p for p,_ in iter_block_entities(WORLD,'projectseele:geofront',(-54,-584,-80),(110,-474,155),selected_chunks=selected)}
    p=vox.Painter(vertical_bounds=(-960,320));count=0;kept=Counter()
    for k,before,core,shell in zip(src['section_keys'],src['before'],src['core'],src['shell']):
        key=tuple(map(int,k));xyz=xyz_for(key);x,y,z=xyz.T;after=before.copy()
        active=shell&(y>-584)&(y<-473)&(x>=-54)&(x<=110)&(z>=-80)&(z<=155)
        writable=active&np.isin(before,list(allowed))
        for pos in devices:
            X,Y,Z=pos
            if (X//16,Z//16,Y//16)==key:writable[(Y%16)*256+(Z%16)*16+X%16]=False
        after[writable&core]=air
        # A partial low-band shell is not an upper-body free-space bound:
        # filling its top ring would manufacture a ceiling through the EVA.
        # Only recolour already-solid lining/native backing; never fill air.
        solid=~np.isin(before,[code('minecraft:air'),code('minecraft:cave_air'),code('minecraft:void_air')])
        after[writable&~core&solid]=panel
        after[writable&~core&solid&(y%24==0)]=edge
        for state,n in zip(*np.unique(before[active&core&~writable],return_counts=True)):kept[names[int(state)]]+=int(n)
        count+=cuboids(p,(key[0]*16,key[2]*16,key[1]*16),before.reshape(16,16,16),after.reshape(16,16,16),names,'R52_bank1_final_low_runner_lining')
    vox.WORLD=WORLD;vox.OUT=OUT;vox.DIM='projectseele:geofront'
    p.meta.update(root_author=True,partial_low_band_source=True,body_posture_unchanged=True,original_upper_well_unchanged=True,
                  original_structural_panels_and_all_devices_preserved=True,measurement_sha256=hashlib.sha256((SOURCE/'MEASURED_SOURCE.npz').read_bytes()).hexdigest())
    lock=acquire_world_lock()
    try:receipt=p.apply(STAGE,session_lock=lock)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    report=dict(world_written=True,changed_cells=count,protected_low_band_cells=dict(kept),receipt=receipt,native_game_passed=False)
    (OUT/STAGE/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':main()
