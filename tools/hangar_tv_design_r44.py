"""Static material hierarchy for all retained wet/transfer/launch instances.

These are the project world's measured civil faces, not asserted TV dimensions.
Callers may finish only an existing known full cube; this module never fills
the vessel, personnel openings, glass or dynamic machinery sweeps.
"""
import math

BLUE = "projectseele:nerv_shaft_panel"
GREEN = "projectseele:nerv_machine_panel"
EDGE = "projectseele:nerv_machine_edge"
STRUCT = "projectseele:nerv_structural_panel"
LIGHT = "projectseele:nerv_strip_light"
FULL_CUBE = [[0., 0., 0., 1., 1., 1.]]
FINISHABLE = {BLUE, GREEN, EDGE, STRUCT, LIGHT,
    "projectseele:nerv_wall_panel", "projectseele:nerv_wall_datum",
    "minecraft:gray_concrete", "minecraft:light_gray_concrete",
    "minecraft:white_concrete", "minecraft:polished_deepslate",
    "minecraft:deepslate_bricks", "minecraft:deepslate_tiles",
    "minecraft:polished_blackstone_bricks", "minecraft:sea_lantern"}


def wet_faces(cx):
    points = set()
    for x in range(cx - 20, cx + 21):
        for y in range(-442, -355):
            points.update(((x, y, -267), (x, y, -213)))
    for x in (cx - 20, cx + 20):
        for z in range(-266, -213):
            for y in range(-442, -355):
                points.add((x, y, z))
    for x in range(cx - 20, cx + 21):
        for z in range(-267, -212):
            points.add((x, -355, z))
    return points


def wet_finish(cx, q, before):
    x, y, z = q
    if before in ("minecraft:sea_lantern", LIGHT):
        return LIGHT
    if x in (cx - 20, cx + 20) and (z + 267) % 12 in (0, 1):
        return EDGE
    return STRUCT if y in (-442, -374, -356) else BLUE


def transfer_faces(guide_y):
    points = set()
    for z in range(-212, -53):
        floor = math.floor(guide_y(z))
        for x in (-35, 95):
            for y in range(floor + 1, floor + 86):
                points.add((x, y, z))
        for x in range(-35, 96):
            points.add((x, floor + 86, z))
    return points


def transfer_finish(q, before):
    return LIGHT if before in ("minecraft:sea_lantern", LIGHT) else (
        EDGE if (q[2] + 212) % 20 in (0, 1) else GREEN)


def launch_faces(cx):
    points = set()
    for y in range(-410, 96):
        for d in range(-17, 18):
            points.update(((cx + d, y, -53), (cx + d, y, -19),
                (cx - 17, y, -36 + d), (cx + 17, y, -36 + d)))
    return points


def launch_finish(cx, q, before):
    x, y, z = q
    collar = any(abs(y - h) <= 2 for h in (-332, -192, -52))
    return LIGHT if before in ("minecraft:sea_lantern", LIGHT) else (
        EDGE if collar or (z == -19 and abs(x - cx) in (9, 10)) else BLUE)


def upper_pressure_members():
    """Complete the retained common copied roof, leaving its inside bays open.

    The actual roof spans X-40..104, Z-286..-214 at Y-355. A copied cage
    facade stopped below it; its open upper band was never a labelled vent.
    The one-row Z-213 seam joins the narrower X-35..95 transfer hall.
    Callers must preserve real personnel ports and all existing whole parts.
    """
    points = {}
    for x in (-40, 104):
        for z in range(-289, -213):
            for y in range(-367, -355):
                points[x, y, z] = STRUCT if y == -356 or (z + 286) % 12 in (0, 1) else BLUE
    for x in range(-40, 105):
        for y in range(-367, -355):
            points[x, y, -289] = STRUCT if y == -356 or (x + 40) % 12 in (0, 1) else BLUE
    # The actual upper lift pocket reaches Z-288. Close outside that authored
    # floor, not across the room at the old roof's Z-286 edge. A three-metre
    # two-layer extension retains the same roof elevation and bearings.
    for x in range(-40, 105):
        for z in range(-289, -286):
            points[x, -355, z] = BLUE
            points[x, -354, z] = STRUCT
    # Width transitions stay outside every carrier/core, with the common
    # observation floor and its two-metre headroom open through the middle.
    for x in list(range(-40, -34)) + list(range(95, 105)):
        for y in range(-367, -355):
            points[x, y, -213] = BLUE
    for x in range(-40, 105):
        for y in (-355, -354):
            points[x, y, -213] = BLUE if y == -355 else STRUCT
    # The retained shared hall's roof starts two metres lower (-357).
    # A short overlap above that existing slab makes a sealed stepped joint.
    for x in range(-35, 96):
        for y in range(-356, -352):
            points[x, y, -212] = BLUE if y == -356 else STRUCT
    return points


def lower_pressure_seam_members():
    """Close the copied side-facade seam below the retained upper gallery.

    At Y-373 the six original side faces have a perforated one-cell band,
    with whole pressure cubes directly above and below. These are wall
    seams, outside the crane wheels, capsule envelope and personnel slabs.
    North observation ports and the rear transport shutter stay separate.
    """
    return {(cx + side * 20, -373, z): EDGE if (z + 267) % 12 in (0, 1) else BLUE
            for cx in (-12, 30, 72) for side in (-1, 1) for z in range(-260, -213)}
