"""Apply the finite, bottomed rail slots selected from the original authoring."""
import argparse,hashlib,json,msvcrt
from collections import defaultdict
from pathlib import Path
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import iter_selected_sections,iter_block_entities


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--remaining',action='store_true');p.add_argument('--apply',action='store_true');a=p.parse_args();base=a.base.resolve();world=base/'WORLD'
    out=base/('remaining_transfer_and_gate_pockets' if a.remaining else 'prelaunch_finite_slots');assert not(out/'APPLIED.json').exists()
    d=json.loads(a.candidate.read_text('utf8'));assert d['root_apply_ready'] and not d['holds']
    rows=d['changes']
    if a.remaining:assert len(rows)==14443
    else:assert len(rows)==10626 and d['cut_changes']==7578 and d['new_floor_changes']==3048
    index={tuple(r['position']):r for r in rows};assert len(index)==len(rows)
    if not a.remaining:assert not set(map(tuple,d['protected_six_faces']))&set(index)
    selected=defaultdict(set);by_section=defaultdict(list)
    for q in index:
        x,y,z=q;assert (-36<=x<=98 and -1140<=y<=-930 and -1<=z<=352) if a.remaining else (-31<=x<=91 and -1075<=y<=-979 and 9<=z<=301),q
        selected[x//16,z//16].add(y//16);by_section[x//16,z//16,y//16].append(q)
    def read():
        actual={}
        for cx,cz,sy,palette,values in iter_selected_sections(world,'projectseele:geofront',selected):
            for q in by_section[cx,cz,sy]:
                x,y,z=q;actual[q]=palette[int(values[(y%16)*256+(z%16)*16+x%16])]
        return actual
    actual=read();assert all(actual.get(q)==r['before'] for q,r in index.items()),[(q,r['before'],actual.get(q)) for q,r in index.items() if actual.get(q)!=r['before']][:10]
    lo=tuple(min(q[i] for q in index) for i in range(3));hi=tuple(max(q[i] for q in index) for i in range(3))
    assert not any(tuple(q) in index for q,_ in iter_block_entities(world,'projectseele:geofront',lo,hi,selected_chunks=selected))
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-1344,320))
    for q,r in index.items():painter.exact((*q,*q),r['before'],r['after'],'bounded_original_ramp_and_bank_bottomed_rail_slot')
    proofs={} if a.remaining else {str(name):hashlib.sha256((a.candidate.parent/name).read_bytes()).hexdigest() for name in d['proof_sources']}
    painter.meta.update(root_author=True,candidate_sha256=hashlib.sha256(a.candidate.read_bytes()).hexdigest(),
                        proof_sha256=proofs,original_fixed_steel_preserved=True,wet_throat_deferred_to_real_seal=not a.remaining)
    painter.save_plan('original_transfer_bottomed_clearance')
    if not a.apply:return
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('original_transfer_bottomed_clearance',session_lock=lock)
        actual=read();assert all(actual.get(q)==r['after'] for q,r in index.items())
        report=dict(world_written=True,changed_cells=len(rows),finite_cuts=sum(r['after']=='minecraft:air' for r in rows),
                    new_supported_bottom_cells=sum(r['after']!='minecraft:air' for r in rows),
                    original_six_near_faces='proved zero-area then released' if a.remaining else 'preserved pending exact classification',
                    independent_steel_unchanged=True,exact_readback=True,receipt=receipt)
        (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
