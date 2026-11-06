"""Exact sparse absolute-height recipes; caller holds stopped_world for world IO."""
from collections import defaultdict
import copy
import re
import shutil
from pathlib import Path
import numpy as np
import nbtlib
from apply_s20_approved_semantic_repairs import parse_state
from inspect_map_assets import decode_modern_section, palette_state
from map_pipeline.delta_geometry import checked_indices
from map_pipeline.delivery_check import read, write
from map_pipeline.install.invariants import require_nbt_equal
from map_pipeline.station_sections import StationSections
from map_pipeline.verify_corridors import write_replay_expected
from transplant_s22_authority import read_region, parse_chunk

DATA = Path('dimensions/projectseele/geofront/data/city_rigid_generation_r45/surface')
REGIONS = Path('dimensions/projectseele/geofront/region')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def validate_delta(candidate, changes_file='exact-edits.json', section_source=None, source_overlay=None):
    """Validate package/source only. Unknown captured sections never mean air."""
    candidate = Path(candidate)
    manifest = read(candidate/'manifest.json')
    rows = read(candidate/changes_file)
    for row in rows:
        require(len(row['pos']) == 3 and all(type(n) is int for n in row['pos']), 'Invalid exact cell coordinate')
        require(isinstance(row['before'], str) and isinstance(row['after'], str)
                and row['before'] != row['after'], 'Invalid exact cell transition')
    changes = {tuple(row['pos']): row for row in rows}
    require(len(changes) == len(rows) == manifest['cells'] > 0, 'Section patch cell scope differs')
    source = StationSections(section_source or manifest.get('section_source') or manifest['source'])
    declared = {row['path']: row for row in manifest['regions']}
    files = sorted((candidate/'delta').glob('*.npz'))
    require(len(declared) == len(manifest['regions']) and set(declared) ==
            {p.relative_to(candidate).as_posix() for p in files}, 'Delta region inventory differs')
    seen, chunks, extents = set(), defaultdict(list), set()
    for file in files:
        match = re.fullmatch(r'r\.(-?\d+)\.(-?\d+)\.npz', file.name)
        require(match is not None, 'Invalid region filename')
        region = tuple(map(int, match.groups()))
        with np.load(file) as data:
            bottom, height, indices = checked_indices(data)
            require({'y_origin', 'height'}.issubset(data.files), 'Section patch requires explicit extent')
            coords, ranges, old, new, names = (data[k] for k in ('coordinates','ranges','before','after','palette'))
        require(coords.ndim == 2 and coords.shape[1] == 2 and coords.dtype.kind in 'iu', 'Invalid chunk coordinates')
        require(len(coords) == len({tuple(p) for p in coords}) > 0, 'Repeated or empty chunk scope')
        require(ranges.ndim == 1 and ranges.dtype.kind in 'iu' and len(ranges) == len(coords)+1
                and int(ranges[0]) == 0 and int(ranges[-1]) == len(indices)
                and np.all(np.diff(ranges.astype(np.int64)) > 0), 'Invalid delta chunk ranges')
        require(names.ndim == 1 and names.dtype.kind in 'US' and len(names) > 0, 'Invalid delta palette')
        for values in (old, new):
            require(values.shape == indices.shape and values.dtype.kind in 'iu'
                    and np.all(values >= 0) and np.all(values < len(names)), 'Invalid delta palette index')
        declared_row = declared[file.relative_to(candidate).as_posix()]
        require((declared_row['cells'], declared_row['y_origin'], declared_row['height']) ==
                (len(indices), bottom, height), 'Declared delta geometry differs')
        require(manifest['vertical_extent'] == [bottom, bottom+height-1], 'Manifest extent differs')
        extents.add((bottom, height))
        for i, (cx, cz) in enumerate(coords):
            cx, cz = int(cx), int(cz)
            require((cx//32, cz//32) == region, 'Delta chunk belongs to another region')
            lo, hi = map(int, ranges[i:i+2])
            for offset, oldid, newid in zip(indices[lo:hi], old[lo:hi], new[lo:hi]):
                offset = int(offset)
                pos = (cx*16+offset%16, bottom+offset//256, cz*16+(offset//16)%16)
                before, after = str(names[oldid]), str(names[newid])
                row = changes.get(pos)
                require(pos not in seen, 'Repeated section patch cell')
                require(row is not None and row['before'] == before and row['after'] == after,
                        'Sparse delta differs from exact declared cells')
                captured = source.state(*pos)
                require(captured is not None, 'Unknown source section at '+str(pos))
                actual = (source_overlay or {}).get(pos, captured)
                require(actual == before, 'Sparse delta source precondition differs at '+str(pos))
                seen.add(pos); chunks[cx, cz].append(row)
    require(seen == set(changes), 'Some declared section cells have no delta')
    return dict(manifest=manifest, rows=rows, changes=changes, chunks=dict(chunks), source=source, extents=extents)


def actual_cells(world, checked, *, after=False):
    """Read exact cells and all device payloads in touched FULL chunks."""
    world = Path(world); grouped = defaultdict(list)
    for cx, cz in checked['chunks']:
        grouped[cx//32, cz//32].append((cx, cz))
    devices, count = [], 0
    for (rx, rz), coordinates in sorted(grouped.items()):
        _, raw = read_region(world/REGIONS/f'r.{rx}.{rz}.mca')
        for cx, cz in sorted(coordinates):
            blob = raw[(cz%32)*32+cx%32]
            require(blob is not None, 'Missing actual target chunk')
            chunk = parse_chunk(blob)
            require(str(chunk.get('Status', '')).removeprefix('minecraft:') == 'full', 'Actual target chunk is not FULL')
            sections = {int(s['Y']): s for s in chunk['sections']}
            require(len(sections) == len(chunk['sections']), 'Duplicate actual section')
            decoded = {}; tags = chunk.get('block_entities', [])
            positions = [tuple(int(tag[k]) for k in ('x','y','z')) for tag in tags]
            require(len(positions) == len(set(positions)), 'Duplicate actual device host')
            require(not set(positions).intersection(checked['changes']), 'Section patch touches an actual device host')
            devices.extend(copy.deepcopy(tags))
            for row in checked['chunks'][cx, cz]:
                x, y, z = row['pos']; sy = y//16
                if sy not in decoded:
                    # A missing section in a positively verified FULL chunk is
                    # implicit air. Missing captured sections failed above.
                    decoded[sy] = decode_modern_section(sections[sy]) if sy in sections else ([], [])
                palette, indices = decoded[sy]
                actual = palette_state(palette[indices[(y%16)*256+(z%16)*16+x%16]]) if palette else 'minecraft:air'
                require(actual == row['after' if after else 'before'], 'Actual cell precondition/readback differs at '+str(row['pos']))
                count += 1
    return nbtlib.File({'Devices': nbtlib.List[nbtlib.Compound](devices)}), count


def prepare(world, candidate, changes_file='exact-edits.json', source_overlay=None):
    world, candidate = Path(world), Path(candidate)
    checked = validate_delta(candidate, changes_file, source_overlay=source_overlay)
    require(checked['manifest'].get('device_changes', 0) == 0, 'Device changes are forbidden')
    require(not (candidate/'before').exists() and not (candidate/'after').exists(), 'Recipes already prepared')
    devices, count = actual_cells(world, checked)
    example = next((world/DATA).glob('*.dat'), None)
    require(example is not None, 'An actual generation WorldUUID reference is required')
    identity = copy.deepcopy(nbtlib.load(example)['WorldUUID'])
    for (cx, cz), rows in sorted(checked['chunks'].items()):
        relative = DATA/f'{cx}_{cz}.dat'; original = world/relative
        exists = original.is_file()
        data = nbtlib.load(original) if exists else nbtlib.File({
            'Version': nbtlib.Int(1), 'WorldUUID': copy.deepcopy(identity),
            'Palette': nbtlib.List[nbtlib.Compound](), 'Spans': nbtlib.List[nbtlib.IntArray](),
            'BlockEntities': nbtlib.List[nbtlib.Compound]()})
        require(int(data['Version']) == 1, 'Foreign sparse generation recipe version')
        require_nbt_equal(data['WorldUUID'], identity, 'WorldUUID')
        prior = copy.deepcopy(data); palette, codes, columns = data['Palette'], {}, defaultdict(list)
        for row in rows:
            x, y, z = row['pos']; after = row['after']
            if after not in codes:
                state = parse_state(after)
                codes[after] = next((j for j, p in enumerate(palette) if p == state), len(palette))
                if codes[after] == len(palette): palette.append(state)
            columns[x, z].append((y, codes[after]))
        for (x, z), entries in sorted(columns.items()):
            entries.sort(); low = high = entries[0][0]; state = entries[0][1]
            for y, value in entries[1:]+[(10000, -1)]:
                if y == high+1 and value == state:
                    high = y; continue
                data['Spans'].append(nbtlib.IntArray([x, z, low, high, state])); low = high = y; state = value
        for key in prior:
            if key not in ('Palette', 'Spans'): require_nbt_equal(prior[key], data[key], 'recipe/'+key)
        for key in ('Palette', 'Spans'):
            require_nbt_equal(list(prior[key]), list(data[key][:len(prior[key])]), 'recipe-prefix/'+key)
        before_path, after_path = candidate/'before'/relative, candidate/'after'/relative
        after_path.parent.mkdir(parents=True, exist_ok=True)
        if exists:
            before_path.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(original, before_path)
        data.save(after_path, gzipped=True)
        require_nbt_equal(data, nbtlib.load(after_path), 'saved-recipe')
    devices.save(candidate/'target-devices-before.dat', gzipped=True)
    write_replay_expected(candidate)
    proof = dict(errors=[], updated_recipes=len(checked['chunks']), actual_old_cells_verified=count,
                 actual_touched_chunk_devices=len(devices['Devices']), device_changes=0,
                 new_complete_surface_recipes=0, recipe_scope='absolute sparse cells appended; existing spans, UUID and devices retained')
    write(candidate/'recipe-preparation.json', proof)
    return proof
