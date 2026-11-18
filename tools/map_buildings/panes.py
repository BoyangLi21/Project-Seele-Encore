"""Glass pane and iron bar connection states, as the game would set them after a neighbour update.

write_deep_cells writes states exactly and sends no neighbour updates, so a pane written with every side false stays
a thin post until something next to it changes. A pane or bar joins another pane or bar, a wall block, or any block
with a full sturdy side; doors, slabs, stairs, signs, fences and the like are not sturdy at the side.
"""
from blocks import base

SIDES = (('north', 0, -1), ('south', 0, 1), ('west', -1, 0), ('east', 1, 0))
NOT_STURDY = ('slab', 'stairs', 'door', 'fence', 'sign', 'button', 'pressure_plate', 'carpet', 'candle', 'bed', 'lever',
              'cauldron', 'lantern', 'torch', 'leaves', 'rail', 'banner', 'chain', 'rod', 'head', 'skull', 'pot', 'ladder',
              'vine', 'brewing_stand', 'street_light', 'flower', 'sapling', 'grass', 'fern', 'snow', 'scaffolding', 'campfire',
              'anvil', 'bell', 'hopper', 'enchanting', 'stonecutter', 'grindstone', 'lectern', 'cake', 'frame', 'pickle', 'coral')
STURDY_HINTS = ('concrete', 'planks', 'stone', 'brick', 'quartz', 'deepslate', 'terracotta', 'wool', '_log', '_wood', 'andesite',
                'diorite', 'granite', 'tuff', 'glass', 'iron_block', 'prismarine', 'sandstone', 'dirt', 'grass_block', 'barrel',
                'furnace', 'redstone_lamp', 'asphalt', 'shaft_panel', 'calcite', 'basalt', 'blackstone', 'mud_bricks', 'copper',
                'obsidian', 'clay', 'smithing_table', 'crafting_table', 'bookshelf', 'hay_block', 'sponge', 'gravel', 'sand')


def is_pane(s):
    b = base(s) if s else ''
    return b.endswith('glass_pane') or b == 'minecraft:iron_bars'


def joins(s):
    """Whether a pane or bar beside this block reaches over to it."""
    if not s:
        return False
    b = base(s)
    if is_pane(s) or b.endswith('_wall'):
        return True
    name = b.split(':')[-1]
    if name in ('grass_block', 'snow_block'):
        return True
    if any(k in name for k in NOT_STURDY):
        return False
    return any(k in name for k in STURDY_HINTS)


def connected(state, x, y, z, get):
    """The pane or bar state at (x, y, z) with its four sides set from its neighbours (get(x, y, z) -> state)."""
    b = base(state)
    props = dict(p.split('=') for p in state[state.index('[') + 1:-1].split(',')) if '[' in state else {}
    for side, dx, dz in SIDES:
        props[side] = 'true' if joins(get(x + dx, y, z + dz)) else 'false'
    props.setdefault('waterlogged', 'false')
    return b + '[' + ','.join(f'{k}={props[k]}' for k in sorted(props)) + ']'
