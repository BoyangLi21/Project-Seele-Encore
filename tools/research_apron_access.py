"""Connect the research station and its existing west gallery to the two GeoFront apron stands.

The baseline gallery floor is Y=-467 and the flat aircraft deck is Y=-461.
The aircraft approach, parking positions and the railway are outside the passenger walk.
"""

import math

AIR = "minecraft:air"
STONE = "minecraft:smooth_stone"
WHITE = "minecraft:smooth_quartz"
TRIM = "minecraft:polished_andesite"
DARK = "minecraft:polished_deepslate"
LAMP = "minecraft:sea_lantern"
GLASS = "minecraft:light_gray_stained_glass"
HALL_DOOR = (275, -466, 549)
STATION = (306, -466, 565)
BUILDING = (261, -466, 597)
STANDS = ((199, -460, 531), (232, -460, 531))


def ramp_eighths(z):
    """Absolute eighth-block elevation of the walking surface at the apron south edge."""
    return -460 * 8 - 4 * min(12, max(0, z - 533))


def ground_tile(editor, x, z, grade, block):
    half = grade % 8
    if half not in (0, 4):
        raise ValueError((x, z, grade))
    y = (grade - 1) // 8
    if half:
        if block == LAMP:
            block = WHITE
        block += "_slab[type=bottom,waterlogged=false]"
    editor.put(x, y, z, block)


def apply(editor):
    """Build into the usual offline Works editor; signs are returned in its native block-entity table."""
    for x in range(271, 280):
        for y in range(-466, -462):
            current = editor.get(x, y, 549)
            expected = (
                "minecraft:red_terracotta"
                if y == -465
                else "minecraft:light_gray_concrete"
            )
            if current not in (expected, AIR):
                raise ValueError(("unexpected reception wall", x, y, 549, current))
            editor.put(x, y, 549, AIR)

    # The surveyed north lobby of the large building is separate from the cell entry at Z607.
    # Its east facade directly adjoins the public travelator gallery; open a second doorway there.
    expected_wall = (
        "minecraft:gray_concrete",
        "minecraft:red_terracotta",
        "minecraft:light_gray_concrete",
        "minecraft:light_gray_concrete",
    )
    for z in range(592, 597):
        for y, expected in zip(range(-466, -462), expected_wall):
            current = editor.get(272, y, z)
            if current not in (expected, AIR):
                raise ValueError(("unexpected north lobby facade", 272, y, z, current))
            editor.put(272, y, z, AIR)
    for x in range(267, 273):
        for z in range(591, 598):
            cap = TRIM if x == 267 or z in (591, 597) else GLASS
            if x == 270 and z in (592, 596):
                cap = LAMP
            editor.put(x, -462, z, cap)
    for z in (591, 597):
        for y in range(-466, -462):
            editor.put(267, y, z, WHITE if y > -466 else TRIM)
    for x in range(259, 273):
        for z in (592, 596):
            if editor.get(x, -467, z) == STONE:
                editor.put(x, -467, z, TRIM)
    editor.sign(
        271, -464, 597, "west", "研究棟 北玄関", "车站／停机坪", "STATION / APRON", "→"
    )

    # The arched portal continues the two existing walls. All nine central columns remain open.
    for z in range(541, 550):
        grade = ramp_eighths(z)
        roof = max(-462, math.ceil(grade / 8 + 3.5))
        for x in range(269, 282):
            frame = x in (269, 270, 280, 281) or z in (541, 549)
            tile = TRIM if frame else GLASS
            if z in (542, 547) and x in (272, 273, 277, 278):
                tile = LAMP
            editor.put(x, roof, z, tile)
        for x in (270, 280):
            if z not in (542, 548, 549):
                continue
            for y in range(math.ceil(grade / 8), roof):
                editor.put(
                    x, y, z, TRIM if y in (roof - 1, math.ceil(grade / 8)) else WHITE
                )
    # Make the existing half-block ramp legible from either end. The neighboring underside
    # remains available to services because all work here follows the original inclined surface.
    for z in range(532, 551):
        for x in range(271, 280):
            cap = WHITE if x in (271, 279) else TRIM if x in (272, 278) else STONE
            ground_tile(editor, x, z, ramp_eighths(z), cap)
        if 534 <= z <= 540:
            for x in (270, 280):
                y = math.ceil(ramp_eighths(z) / 8)
                editor.put(
                    x,
                    y,
                    z,
                    "iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]",
                )
    # Level passenger strip immediately behind the stands. Retain the stand-corner white
    # paint at Z531 and all docking lines in front. Recess the lights into the surface.
    for x in range(197, 280):
        for z in range(531, 534):
            if x >= 271 and z >= 532:
                continue
            if z == 531 and editor.get(x, -461, z) == WHITE:
                continue
            material = TRIM if z == 531 else WHITE if z == 533 else STONE
            if z == 533 and ((x - 199) % 12 == 0 or x in (199, 232)):
                material = LAMP
            editor.put(x, -461, z, material)
    for x in (199, 232):
        for xx in range(x - 2, x + 3):
            editor.put(xx, -461, 532, WHITE if xx != x else TRIM)

    # Translate the floor-mounted guide lights at the concourse turns into flush lighting,
    # including the entire ordinary centre lane between the two opposing flat travelators.
    for x0, x1, z0, z1 in (
        (273, 277, 550, 607),
        (273, 293, 550, 554),
        (289, 293, 550, 565),
        (289, 302, 563, 567),
    ):
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if editor.get(x, -466, z).startswith("projectseele:nerv_ceiling_light"):
                    if editor.get(x, -467, z) in (STONE, WHITE, TRIM):
                        editor.put(x, -467, z, LAMP)
                        editor.put(x, -466, z, AIR)

    # The first sign faces the receiving hall; the opposite face points arriving passengers to rail.
    editor.sign(
        270, -464, 550, "south", "飛行場連絡口", "停机坪 ↑", "A01    A02", "APRON"
    )
    editor.sign(
        280,
        -464,
        548 - 1,
        "north",
        "研究棟  •  駅",
        "研究楼／车站",
        "↓ 研究模拟区站",
        "RESEARCH STN",
    )
    editor.sign(
        277,
        -464,
        560,
        "west",
        "駐機場   ↑ 北",
        "中央接待廊",
        "Apron A01・02",
        "研究模拟区站 →",
    )
    # South-facing passengers at the stand exit look toward the same gallery opening.
    editor.sign(
        280, -461, 541, "north", "旅客連絡口", "研究楼・车站", "RESEARCH STN", "↓"
    )
