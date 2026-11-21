"""Apply only reviewed carrier bearing columns and bridge ownership properties."""
import argparse,hashlib,json,msvcrt,re
from collections import defaultdict
from pathlib import Path
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import iter_selected_sections,iter_block_entities


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';folder=a.candidate.resolve();out=base/'hangar_native_bindings'
    assert not (out/'APPLIED.json').exists()
    foundation=json.loads((folder/'SERVICE_FOUNDATION_MINIMAL_CANDIDATE.json').read_text('utf8'))
    bridge=json.loads((folder/'BRIDGE_PROPERTY_ONLY_CANDIDATE.json').read_text('utf8'))
    proof=json.loads((folder/foundation['source_proof_file']).read_text('utf8'))
    assert len(proof)==3 and all(not row['carrier_full_0_to_1_affine_sweep_hits'] for row in proof)
    assert len(foundation['changes'])==48 and len(bridge['changes'])==753
    allowed_top={tuple(map(int,s.split(','))) for row in proof for s in row['whole_face_cover_cells']}
    assert len(allowed_top)==24
    for row in foundation['changes']:
        x,y,z=row['position'];assert (x,-1131,z) in allowed_top and y in (-1131,-1132)
        assert row['before']=='minecraft:air' and row['after']=='projectseele:nerv_shaft_panel'
    for row in bridge['changes']:
        assert row['before'].startswith('projectseele:entry_plug_bridge_deck[')
        assert re.sub(r'unit=[012],?', '', row['after']).replace(',]',']')==row['before']
        assert f"unit={row['variant']}" in row['after']
    changes=foundation['changes']+bridge['changes'];points={tuple(r['position']) for r in changes}
    assert len(points)==801
    checks={tuple(r['position']):r['state'] for r in foundation['current_readback']}
    checks.update({tuple(r['position']):r['before'] for r in changes})
    selected=defaultdict(set)
    for x,y,z in checks:selected[x//16,z//16].add(y//16)
    actual={}
    for cx,cz,sy,palette,values in iter_selected_sections(world,'projectseele:geofront',selected):
        for q in checks:
            x,y,z=q
            if (x//16,z//16,y//16)==(cx,cz,sy):actual[q]=palette[int(values[(y%16)*256+(z%16)*16+x%16])]
    assert actual==checks,[(q,checks[q],actual.get(q)) for q in checks if checks[q]!=actual.get(q)][:10]
    low=tuple(min(q[i] for q in checks) for i in range(3));high=tuple(max(q[i] for q in checks) for i in range(3))
    assert not any(tuple(q) in points for q,_ in iter_block_entities(world,'projectseele:geofront',low,high,selected_chunks=selected))
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-1344,320))
    for row in changes:
        q=row['position'];painter.exact((*q,*q),row['before'],row['after'],'reviewed_original_hangar_binding_cell')
    painter.meta.update(root_author=True,bridge_geometry_unchanged=True,original_boarding_stair_open=True,
                        original_actors_changed=False,source_sha256={n:hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in ('SERVICE_FOUNDATION_MINIMAL_CANDIDATE.json','BRIDGE_PROPERTY_ONLY_CANDIDATE.json',foundation['source_proof_file'])})
    painter.save_plan('real_carrier_bearings_and_bridge_unit_ownership')
    if not a.apply:return
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('real_carrier_bearings_and_bridge_unit_ownership',session_lock=lock)
        checks.update({tuple(r['position']):r['after'] for r in changes});actual={}
        for cx,cz,sy,palette,values in iter_selected_sections(world,vox.DIM,selected):
            for q in checks:
                x,y,z=q
                if (x//16,z//16,y//16)==(cx,cz,sy):actual[q]=palette[int(values[(y%16)*256+(z%16)*16+x%16])]
        assert actual==checks
        report=dict(world_written=True,changed_cells=len(changes),bridge_property_cells=753,
                    physical_bearing_cells=48,original_stairs_unchanged=True,actual_readback_cells=len(checks),
                    carrier_top_bearing_cells=24,source_geometry_only_proof=True,native_cycle_pending=True,receipt=receipt)
        (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
