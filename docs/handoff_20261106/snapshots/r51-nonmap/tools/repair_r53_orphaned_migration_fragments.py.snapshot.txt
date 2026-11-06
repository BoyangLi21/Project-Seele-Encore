"""Remove two user-reported, fully measured remnants missed by migration masks."""
from collections import deque
from pathlib import Path
import argparse
import json
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
from query_blocks import AIR, iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids

DIM = 'projectseele:geofront'
CASES = (
    ('hangar_roof_edge', 'original_hangar_transfer_launch',
     (-35, -356, -212), (95, -353, -212), 524, (47, -353, -212)),
    ('pyramid_south_fragment', 'headquarters_and_original_station',
     (24, -461, 444), (36, -458, 446), 66, (25, -459, 446)),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--world', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    base = args.base.resolve(); frozen = base/'WORLD'
    world = args.world.resolve() if args.world else frozen
    assert not args.apply or args.world and world != frozen
    survey.WORLD = frozen
    vox.WORLD = world; vox.DIM = DIM; vox.OUT = base/'fragment-repair'
    stage = world.name if args.apply else 'plan'
    assert not args.apply or not list((vox.OUT/stage).glob('applied_*'))
    painter = vox.Painter(vertical_bounds=(-1344, 320))
    measured = []; changed = set()
    for name, source, minimum, maximum, count, complaint in CASES:
        lo = tuple(v-1 for v in minimum); hi = tuple(v+1 for v in maximum)
        before, palette = survey.measure(lo, hi)
        selected = ~np.isin(before, [i for i, state in enumerate(palette) if state in AIR])
        assert int(selected.sum()) == count, ('Changed complete component', name)
        assert not any(np.any(np.take(selected, edge, axis=axis))
                       for axis in range(3) for edge in (0, -1)), 'Component touches survey boundary'
        cells = {tuple(map(int, p)) for p in np.argwhere(selected)}
        queue = deque([next(iter(cells))]); reached = set(queue)
        while queue:
            p = queue.popleft()
            for axis in range(3):
                for sign in (-1, 1):
                    q = list(p); q[axis] += sign; q = tuple(q)
                    if q in cells and q not in reached: reached.add(q); queue.append(q)
        assert reached == cells, 'Entire isolated fragment required'
        with np.load(base.parent/'map_complete_20261013/survey'/f'{source}.npz') as old:
            original_origin = old['origin']; original_states = old['states']; original_palette = old['palette']
        for y, z, x in cells:
            pos = (x+lo[0], y+lo[1], z+lo[2]); ox, oy, oz = np.asarray(pos)-original_origin
            assert palette[int(before[y,z,x])] == str(original_palette[original_states[oy,oz,ox]]), ('Original state changed', pos)
            changed.add(pos)
        assert not list(iter_block_entities(frozen, DIM, lo, hi)), 'Preserve all device NBT'
        after = before.copy(); after[selected] = palette.index('minecraft:air')
        cuboids(painter, lo, before, after, palette, name)
        measured.append((name, lo, hi, before, after, palette))
        painter.meta.setdefault('reported_fragments', []).append(dict(
            name=name, complaint=complaint, complete_component_cells=count,
            all_states_match_original_source=True, no_external_block_contacts=True))
    owner = json.loads((frozen/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    def protect(value):
        if isinstance(value, dict):
            for row in value.get('supports', []):
                assert tuple(row['position']) not in changed, 'Declared support protected'
            for child in value.values(): protect(child)
        elif isinstance(value, list):
            for child in value: protect(child)
    protect(owner)
    painter.meta.update(source='original R53 delivered save', entities_and_progress_unchanged=True,
                        visual_acceptance_pending=True)
    folder = painter.save_plan(stage)
    for name, lo, hi, before, after, palette in measured:
        np.savez_compressed(folder/f'{name}.npz', origin=lo, palette=palette,
                            before=before, after=after, positive_edit_mask=before!=after)
    if args.apply:
        assert (world/'level.dat').is_file()
        painter.apply(stage)
        survey.WORLD = world
        for name, lo, hi, before, after, palette in measured:
            actual, names = survey.measure(lo, hi)
            expected = {state: i for i, state in enumerate(palette)}
            remap = np.asarray([expected.get(state, 65535) for state in names], np.uint16)
            assert np.array_equal(remap[actual], after), ('Complete local readback mismatch', name)
    print(json.dumps(dict(world_written=args.apply, removed=len(changed),
                          complete_components=2, all_device_and_progress_data_unchanged=True)))


if __name__ == '__main__':
    main()
