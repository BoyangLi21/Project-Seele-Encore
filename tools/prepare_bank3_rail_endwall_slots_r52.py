"""Root's finite static rail slots in the third bank's fixed end wall."""
import argparse,hashlib,json,msvcrt
from pathlib import Path
from collections import defaultdict
import numpy as np
import regional_voxels as vox
from query_blocks import iter_selected_sections,iter_block_entities
from r52_spatial_plan import BASE
from extend_world_depth_r52 import acquire_world_lock


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];source=root/'.Codex/r52_continuous_route_migration_20261012/D31_61C9_UPRIGHT_STEEL_UNANCHORED.json'
    doc=json.loads(source.read_text());requested=set();parts=[]
    for p in doc['pieces']:
        if '/exit3/' not in p['leg']:continue
        frame=p['frame'];assert frame['quaternion_xyzw']==[0,0,0,1]
        vertices=np.array(p['triangles_rgb']).reshape(-1,6)[:,:3]+frame['translation']
        lo=vertices.min(0)-.035;hi=vertices.max(0)+.035
        if hi[2]<-800 or lo[2]>=-798 or hi[1]<-646 or lo[1]>-585:continue
        low=np.floor(lo).astype(int);high=np.floor(hi).astype(int)
        for y in range(max(-646,low[1]),min(-585,high[1])+1):
            for z in range(max(-800,low[2]),min(-799,high[2])+1):
                for x in range(low[0],high[0]+1):requested.add((x,y,z))
        parts.append(dict(name=p['name'],bounds=[lo.tolist(),hi.tolist()]))
    assert requested and max(x for x,y,z in requested)<90 and min(x for x,y,z in requested)>-30
    selected=defaultdict(set);sections=defaultdict(set)
    wanted=requested|{(x,y,z-1)for x,y,z in requested}
    for x,y,z in wanted:selected[x//16,z//16].add(y//16);sections[x//16,z//16,y//16].add((x,y,z))
    actual={}
    for cx,cz,sy,pal,data in iter_selected_sections(BASE/'WORLD_R52','projectseele:geofront',selected):
        for x,y,z in sections[cx,cz,sy]:actual[x,y,z]=pal[int(data[(y%16)*256+(z%16)*16+x%16])]
    retired=[p for p in requested if actual[p]=='minecraft:barrier']
    assert retired and all(actual[p] in ('minecraft:barrier','minecraft:air','minecraft:void_air') for p in requested)
    for x,y,z in retired:
        assert (x,y,z-1) not in retired,'No unmeasured through-hole in the fixed wall'
        assert actual[x,y,z-1] not in ('minecraft:air','minecraft:void_air'),'The local groove must retain its sealed backing'
    lower=tuple(min(p[i]for p in wanted)for i in range(3));upper=tuple(max(p[i]for p in wanted)for i in range(3))
    tags=dict(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lower,upper,selected_chunks=selected))
    assert not set(retired)&set(tags)
    out=BASE/'continuous_upright/endwall_slots';stage='three_finite_rail_start_slots';assert not list((out/stage).glob('applied_*'))
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';paint=vox.Painter(vertical_bounds=(-960,320))
    for p in retired:paint.exact((*p,*p),actual[p],'minecraft:air','R52_fixed_third_bank_rail_slot')
    # The backing of each rail recess is made visible and usable as a real
    # full block bearing face; no invisible barrier is used as a foundation.
    backs=sorted({(x,y,z-1)for x,y,z in retired})
    for p in backs:
        assert actual[p]=='minecraft:barrier',('Unexpected backing',p,actual[p])
        paint.exact((*p,*p),actual[p],'projectseele:nerv_structural_panel','R52_closed_rail_slot_backing')
    paint.meta.update(root_author=True,actual_static_rail_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        actual_part_bounds=parts,not_an_operated_gate=True,sealed_backing_preserved=True)
    folder=paint.save_plan(stage);report=dict(world_written=False,slot_cells=len(retired),backing_cells=len(backs),
        slots=retired,backing=backs,source_sha256=paint.meta['actual_static_rail_source_sha256'],native_body_admission=False)
    if args.apply:
        lock=acquire_world_lock()
        try:report.update(world_written=True,receipt=paint.apply(stage,session_lock=lock))
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items()if k not in('slots','backing')}),flush=True)


if __name__=='__main__':main()
