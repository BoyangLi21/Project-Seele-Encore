"""Complete the actual 166m closed leaf lap around the 164m airshaft opening."""
import argparse,gzip,hashlib,json,msvcrt
from pathlib import Path
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--gates',type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args();base=a.base.resolve();world=base/'WORLD'
    out=base/'air_transport_shaft/complete_surface_leaf_lap';assert not(out/'APPLIED.json').exists()
    d=json.loads(a.gates.read_text('utf8'));g=next(g for g in d['gates'] if g['resource']=='remote_airshaft_surface')
    assert g['frame']['position']==[-1120,68.01,-720]
    ref=g['collision_steps'];path=a.gates.parent/ref['cells_file'];raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==ref['sha256']
    phases=json.loads(gzip.decompress(raw));assert len(phases)==1 and len(phases[0])==27556
    cells=phases[0];points=np.asarray([c['position'] for c in cells]);lo=tuple(map(int,points.min(0)));hi=tuple(map(int,points.max(0)))
    assert lo==(-1203,68,-803) and hi==(-1038,68,-638)
    vox.WORLD=survey.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront'
    before,names=survey.measure(lo,hi);after=before.copy();barrier=names.index('minecraft:barrier')
    assert not list(iter_block_entities(world,vox.DIM,lo,hi))
    changed=[]
    for c in cells:
        x,y,z=c['position'];assert c['closed']=='minecraft:barrier' and c['open']=='minecraft:air'
        old=names[int(before[y-lo[1],z-lo[2],x-lo[0]])]
        if old!=c['closed']:
            assert x in (-1203,-1038) or z in (-803,-638)
            assert old.startswith('projectseele:nerv_') or old in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]')
            changed.append(dict(position=c['position'],before=old,after=c['closed']))
        after[y-lo[1],z-lo[2],x-lo[0]]=barrier
    assert len(changed)==660
    painter=vox.Painter(vertical_bounds=(-1344,320));n=cuboids(painter,lo,before,after,names,'actual_closed_airshaft_leaf_lap')
    painter.meta.update(root_author=True,source_gate_candidate_sha256=hashlib.sha256(a.gates.read_bytes()).hexdigest(),actual_closed_leaf_cells=27556)
    painter.save_plan('actual_166m_surface_leaf_lap')
    if not a.apply:return
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('actual_166m_surface_leaf_lap',session_lock=lock)
        actual,palette=survey.measure(lo,hi);assert np.array_equal(np.asarray([names.index(s) for s in palette])[actual],after)
        (out/'APPLIED.json').write_text(json.dumps(dict(world_written=True,changed_cells=n,closed_cells=27556,
            supports_unchanged=True,complete_actual_leaf_readback=True,receipt=receipt),indent=2),'utf8')
        print('Actual airshaft leaf lap complete: 660 cells; all 27556 closed cells read back.',flush=True)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
