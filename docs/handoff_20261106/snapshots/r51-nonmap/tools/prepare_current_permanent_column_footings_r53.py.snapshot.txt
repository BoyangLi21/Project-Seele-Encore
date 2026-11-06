"""Root-only twelve original permanent-pad floor cells, after exact source fit."""
import argparse
import hashlib
import json
import msvcrt
from collections import defaultdict
from pathlib import Path
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import iter_selected_sections, iter_block_entities


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, value): p.write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'proof', 'out'): p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--apply', action='store_true'); a = p.parse_args(); world = a.base/'WORLD'
    assert not (a.out/'APPLIED.json').exists()
    source = json.loads(a.proof.read_text('utf8')); assert source['actual_original_columns_triangles'] == 4912
    cells = {tuple(row['cell']): row for row in source['rows']}; assert len(cells) == 12
    assert all(not row['candidate_full_cube_conflicts'] and row['top_error_m'] <= .000002 and row['actual_permanent_bottom_triangles'] == 2 for row in source['rows'])
    selected, wanted = defaultdict(set), defaultdict(set)
    for x, y, z in cells:
        for q in ((x, y, z), (x, y-1, z), (x-1, y, z), (x+1, y, z), (x, y, z-1), (x, y, z+1)):
            selected[q[0]//16, q[2]//16].add(q[1]//16); wanted[q[0]//16, q[2]//16, q[1]//16].add(q)
    actual = {}
    for cx, cz, sy, palette, values in iter_selected_sections(world, 'projectseele:geofront', selected):
        for x, y, z in wanted[cx, cz, sy]: actual[x, y, z] = palette[int(values[(y%16)*256+(z%16)*16+x%16])]
    assert all(actual.get(point) == 'minecraft:air' for point in cells), 'Current permanent pad cells must retain exact measured air'
    bes = [tuple(point) for point, nbt in iter_block_entities(world, 'projectseele:geofront', (-30,-1063,322), (90,-1063,334), selected_chunks=selected) if tuple(point) in cells]
    assert not bes, 'Protected NBT at original pad cell'
    changes = [dict(position=list(point), before=actual[point], after='projectseele:nerv_floor_panel', before_nbt_snbt=None,
        after_nbt_snbt=None, source_pad=cells[point]['bearing_parts'][0], actual_bearing_world=cells[point]['bearing_world']) for point in sorted(cells)]
    a.out.mkdir(parents=True, exist_ok=True)
    receipt = dict(world_written=False, root_author=True, world=str(world.resolve()), source_proof_sha256=sha(a.proof),
        selected_lower_frame_source=source['selected_lower_frame_source'], pad_cells=12, model_geometry_unchanged=True,
        body_and_original_columns_and_leaf_geometry_unchanged=True, original_pad_contact_top_error_m=0,
        actual_full_cube_static_hatch_and_complete_leaf_stroke_conflicts=0,
        positiveEditMask=[row['position'] for row in changes], changes=changes,
        inversePatch=[dict(position=row['position'],before=row['after'],after=row['before'],before_nbt_snbt=None,after_nbt_snbt=None) for row in changes],
        current_neighbour_states=[dict(position=list(point),state=state) for point,state in sorted(actual.items()) if point not in cells])
    write(a.out/'CANDIDATE.json', receipt)
    print(json.dumps(dict(pad_cells=12, source_fit_conflicts=0, candidate=str(a.out/'CANDIDATE.json'), world_written=False)), flush=True)
    if not a.apply: return
    vox.WORLD = extension.WORLD = world; vox.OUT = a.out; vox.DIM = 'projectseele:geofront'
    painter = vox.Painter(vertical_bounds=(-1344,320))
    for row in changes:
        point = row['position']; painter.exact((*point,*point),row['before'],row['after'],'Root_original_permanent_column_pad_native_footing')
    painter.meta.update(receipt); painter.save_plan('original_permanent_column_pad_footings')
    lock = extension.acquire_world_lock()
    try:
        applied = painter.apply('original_permanent_column_pad_footings',session_lock=lock); readback = {}
        for cx,cz,sy,palette,values in iter_selected_sections(world,vox.DIM,selected):
            for point in cells:
                x,y,z=point
                if (x//16,z//16,y//16)==(cx,cz,sy): readback[point]=palette[int(values[(y%16)*256+(z%16)*16+x%16])]
        assert len(readback)==12 and set(readback.values())=={'projectseele:nerv_floor_panel'}
        receipt.update(world_written=True,receipt=applied,exact_native_pad_cells_readback=12)
        write(a.out/'APPLIED.json',receipt)
    finally:
        msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__ == '__main__': main()
