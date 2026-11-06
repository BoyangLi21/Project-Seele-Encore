"""Check explicit chunk write boundaries without discarding unknown NBT fields."""
import copy
from collections.abc import Mapping
import numpy as np

ROOT_DERIVED = frozenset(('Heightmaps', 'isLightOn', 'starlight.light_version'))
SECTION_DERIVED = frozenset(('BlockLight', 'SkyLight', 'starlight.blocklight_state', 'starlight.skylight_state'))


def require_nbt_equal(before, after, path='chunk'):
    """NBT type, compound keys, list order and array values all matter."""
    if type(before) is not type(after):
        raise ValueError(f'Protected NBT type changed: {path}')
    if isinstance(before, Mapping):
        if before.keys() != after.keys():
            raise ValueError(f'Protected NBT fields changed: {path}')
        for key in before:
            require_nbt_equal(before[key], after[key], f'{path}/{key}')
    elif isinstance(before, np.ndarray):
        if before.dtype != after.dtype or not np.array_equal(before, after):
            raise ValueError(f'Protected NBT array changed: {path}')
    elif isinstance(before, (list, tuple)):
        if len(before) != len(after):
            raise ValueError(f'Protected NBT list changed: {path}')
        for i, (left, right) in enumerate(zip(before, after)):
            require_nbt_equal(left, right, f'{path}/{i}')
    elif before != after:
        raise ValueError(f'Protected NBT value changed: {path}')


def position(tag):
    return tuple(int(tag[k]) for k in ('x', 'y', 'z'))


def assert_chunk_preserved(before, after, edited_sections, device_changes):
    """Only declared block states, device migrations and derived light may differ."""
    excluded = ROOT_DERIVED | {'sections', 'block_entities'}
    require_nbt_equal({k:v for k,v in before.items() if k not in excluded},
                      {k:v for k,v in after.items() if k not in excluded})
    old_sections = {int(s['Y']):s for s in before['sections']}
    new_sections = {int(s['Y']):s for s in after['sections']}
    if len(old_sections) != len(before['sections']) or len(new_sections) != len(after['sections']):
        raise ValueError('Duplicate section identity')
    if set(new_sections) != set(old_sections) | set(edited_sections):
        raise ValueError('Undeclared section added or removed')
    for sy, old in old_sections.items():
        excluded = SECTION_DERIVED | ({'block_states'} if sy in edited_sections else set())
        require_nbt_equal({k:v for k,v in old.items() if k not in excluded},
                          {k:v for k,v in new_sections[sy].items() if k not in excluded}, f'sections/{sy}')
    original_tags = before.get('block_entities', [])
    expected = {position(tag):copy.deepcopy(tag) for tag in original_tags}
    if len(expected) != len(original_tags):
        raise ValueError('Duplicate block entity identity')
    for pos, change in device_changes.items():
        require_nbt_equal(expected.get(pos), change.get('Before'), f'device-before/{pos}')
        if 'After' in change: expected[pos] = change['After']
        else: expected.pop(pos, None)
    require_nbt_equal(list(expected.values()), list(after.get('block_entities', [])), 'block_entities')
