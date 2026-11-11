"""Block classes shared by the building scans."""
from mca import AIR

DOORS = {'minecraft:dark_oak_door', 'minecraft:oak_door', 'projectseele:city_personnel_door', 'mcwdoors:store_door',
         'minecraft:spruce_door', 'minecraft:birch_door', 'minecraft:iron_door', 'minecraft:jungle_door', 'minecraft:acacia_door'}
FACING = {'north': (0, -1), 'south': (0, 1), 'west': (-1, 0), 'east': (1, 0)}
NATURAL = {'grass_block', 'dirt', 'coarse_dirt', 'podzol', 'rooted_dirt', 'mud', 'stone', 'granite', 'diorite', 'andesite',
           'deepslate', 'tuff', 'calcite', 'gravel', 'sand', 'red_sand', 'clay', 'moss_block', 'mycelium', 'dirt_path',
           'farmland', 'snow_block', 'packed_mud', 'smooth_basalt', 'basalt'}
SOFT = ('torch', 'sign', 'button', 'pressure_plate', 'carpet', 'flower', 'sapling', 'tall_grass', 'fern', 'vine', 'rail',
        'dandelion', 'poppy', 'tulip', 'orchid', 'allium', 'bluet', 'daisy', 'lily', 'rose', 'bush', 'lever',
        'tripwire', 'redstone_wire', 'cobweb', 'banner', 'seagrass', 'kelp', 'glow_lichen', 'sugar_cane')
OPEN_EXACT = {'minecraft:grass', 'minecraft:snow', 'minecraft:light', 'minecraft:water', 'minecraft:large_fern'}


def base(s):
    return s.split('[')[0]


def short(s):
    return base(s).split(':', 1)[1] if s and ':' in s else str(s)


def is_open(s):
    """Air or something a player walks through. Unknown (ungenerated) counts as closed."""
    if s is None:
        return False
    if s in AIR:
        return True
    b = base(s)
    return b in OPEN_EXACT or any(k in b for k in SOFT)


def is_natural(s):
    return s is not None and base(s).startswith('minecraft:') and short(s) in NATURAL


def is_door(s):
    return s is not None and base(s) in DOORS


def props(s):
    if '[' not in s:
        return {}
    return dict(p.split('=') for p in s[s.index('[') + 1:-1].split(','))
