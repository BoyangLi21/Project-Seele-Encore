"""Rebuild the secondary command building and curved light-collector blade on its surveyed site."""

import copy
import json
import math

import nbtlib

from dogma_recommission import AIR, AIRS, source_entity
from map_buildings.mca import World

GROUND = -475
AXIS = 340
CAP = -281
WATCH = -321
ROOM_FLOORS = (-497, GROUND, -461, -443)
WALL = "projectseele:nerv_structural_panel"
FLOOR = "projectseele:nerv_floor_panel"
LAMP = "sea_lantern"
GLASS = "gray_stained_glass"
LIFT_ID = "r65-public-sub-terminal"


def tree(state):
    return any(
        name in state
        for name in ("leaves", "_log", "fern", "sapling", "vine", "tall_grass")
    )


def restore_grove(b, previous):
    # Return all site vegetation before selecting which whole crowns should clear the new shell.
    # The previous rectangular housing removed the hillside and its tree canopy down to B2.
    # Restore the surveyed site outside the new footprint, keeping the active car and lower shaft.
    for x in range(210, 301):
        for z in range(303, 379):
            if (
                not 303 + max(0, 9 - min(x - 210, 300 - x))
                <= z
                <= 378 - max(0, 9 - min(x - 210, 300 - x))
            ):
                continue
            for y in range(-498, -359):
                if 289 <= x <= 295 and 334 <= z <= 341 and y <= -436:
                    continue
                state = previous.get(x, y, z)
                if state is None:
                    raise ValueError(("missing original landscape", x, y, z))
                if state != b.reader.get(x, y, z):
                    b.put(x, y, z, state)


def clear_crowns(b, previous):
    def footprint(x, z):
        return (232 <= x <= 305 and abs(z - AXIS) <= 22) or (
            207 <= x < 242 and abs(z - 344) <= 5
        )

    trunks = set()
    for x in range(201, 314):
        for z in range(309, 372):
            if any("_log" in previous.get(x, y, z) for y in range(-480, -451)):
                trunks.add((x, z))
    grove = [
        (x, z)
        for x in range(202, 313)
        for z in range(311, 370)
        if any(tree(b.get(x, y, z)) for y in range(-482, -407))
    ]
    for x, z in grove:
        near = [
            (u, v)
            for u in range(x - 6, x + 7)
            for v in range(z - 6, z + 7)
            if (u, v) in trunks
        ]
        trunk = (
            min(near, key=lambda p: (x - p[0]) ** 2 + (z - p[1]) ** 2) if near else None
        )
        if footprint(x, z) or trunk and footprint(*trunk):
            for y in range(-482, -407):
                if tree(b.get(x, y, z)):
                    b.put(x, y, z, AIR)


def room_plan(y):
    if y < GROUND:
        return 254, 299, 16
    if y <= -462:
        return 242, 299, 19
    if y <= -449:
        return 245, 299, 17
    return 256, 298, 15


def building(b):
    for y in range(-498, -435):
        front, back, half = room_plan(y)
        for z in range(AXIS - half, AXIS + half + 1):
            edge = half - abs(z - AXIS)
            left = front + max(0, 6 - edge)
            right = back - max(0, 3 - edge)
            for x in range(left, right + 1):
                if 289 <= x <= 295 and 334 <= z <= 341 and y <= -436:
                    continue
                facade = x in (left, right) or edge == 0
                state = AIR
                if y == -498 or y in ROOM_FLOORS or y in (-462, -449, -436):
                    state = FLOOR if not facade else "polished_deepslate"
                    if facade and y >= -462:
                        state = "smooth_quartz"
                elif facade:
                    state = WALL if y < GROUND else "smooth_quartz"
                    if -472 <= y <= -465 or -458 <= y <= -453 or -440 <= y <= -438:
                        state = GLASS
                        if (
                            (z - AXIS) % 7 == 0
                            and x <= left + 1
                            or edge == 0
                            and x % 8 == 0
                        ):
                            state = "polished_blackstone"
                    if y in (-464, -452):
                        state = "oxidized_cut_copper"
                b.put(x, y, z, state)

    # Continue the old forecourt directly to the new recessed west entrance.
    for x in range(207, 248):
        width = 4 if x > 231 else 2
        for z in range(344 - width, 345 + width):
            for y in range(GROUND - 6, GROUND):
                if b.get(x, y, z) in AIRS:
                    b.put(x, y, z, "andesite")
            b.put(x, GROUND, z, "polished_andesite" if abs(z - 344) == width else FLOOR)
            b.box(x, GROUND + 1, z, x, GROUND + 5, z, AIR)
        if x in (222, 231, 240):
            b.put(x, GROUND, 344 - width, LAMP)
    # Rooms have independent doors and working clearance in front of each landing.
    for y in ROOM_FLOORS:
        b.box(289, y, 341, 295, y, 346, FLOOR)
        b.box(290, y + 1, 342, 294, y + 4, 347, AIR)
        ceiling = {-497: -475, -475: -462, -461: -449, -443: -436}[y]
        floor_light = ceiling - 1
        if y != -443:
            for x in range(260, 286, 6):
                for z in (329, 351):
                    b.put(x, floor_light, z, LAMP)
                    b.put(
                        x,
                        floor_light - 1,
                        z,
                        "iron_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]",
                    )
        for x in (268, 280, 287):
            b.put(x, y, 345, LAMP)

    # The auxiliary bridge is a compact forward-facing operating room, with a separate gallery above.
    for x in (252, 261, 270):
        for z in (331, 338, 347):
            b.put(x, -460, z, "projectseele:military_seat[facing=east]")
            for off in (-1, 0, 1):
                b.put(x + 2, -460, z + off, "polished_blackstone")
                b.put(
                    x + 2,
                    -459,
                    z + off,
                    "warped_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]",
                )
            b.put(x + 3, -459, z, "cyan_stained_glass")
            b.put(x + 3, -460, z, LAMP)
    # Continuous relief map and status gutter on the inboard bulkhead.
    for z in range(327, 354):
        for y in range(-460, -449):
            b.put(281, y, z, "polished_blackstone")
            dz, h = z - AXIS, y + 460
            state = "black_concrete"
            if abs(dz) in (0, 7, 14) or h in (2, 5, 8):
                state = "cyan_terracotta"
            if h == round(5 + 2.6 * math.sin(dz / 4)) or h == round(4 - dz * 0.2):
                state = "oxidized_copper"
            if abs(dz) >= 12 and h in (3, 4, 7):
                state = LAMP
            b.put(
                280, y, z, state if abs(dz) < 15 and 0 < h < 10 else "deepslate_tiles"
            )
    # A service aisle outside the ends of the screen links the lift and operating room.
    for z in (324, 354):
        b.box(278, -461, z, 286, -461, z + 1, FLOOR)
        b.box(278, -460, z, 286, -457, z + 1, AIR)

    for x in (261, 267, 273, 279):
        for z in (330, 349):
            b.box(x, -496, z, x + 2, -493, z + 1, "projectseele:nerv_machine_panel")
            b.put(x + 1, -494, z, "cyan_stained_glass")
            b.put(x, -496, z + 2, LAMP)
    for z in (328, 350):
        b.box(254, -474, z, 261, -474, z, "polished_deepslate")
        for x in (256, 258, 260):
            b.put(
                x,
                -473,
                z,
                "projectseele:station_seat[facing="
                + ("south" if z == 328 else "north")
                + "]",
            )
    b.box(263, -474, 331, 266, -472, 331, "polished_andesite")
    b.sign(
        265,
        -472,
        332,
        "south",
        "NERV / GEOFRONT",
        "第二発令所",
        "SUB TERMINAL",
        "← 指揮  /  EV →",
    )
    b.sign(281, -459, 354, "south", "第二発令所", "作戦管制", "OPERATIONS", "02")
    for z in (335, 339, 347):
        b.put(261, -442, z, "projectseele:station_seat[facing=west]")
    for z in (338, 350):
        b.box(237, GROUND, z, 237, -470, z, "polished_andesite")
    b.box(235, -469, 338, 246, -469, 350, "polished_andesite")
    b.box(
        235,
        -468,
        338,
        246,
        -468,
        350,
        "smooth_quartz_slab[type=bottom,waterlogged=false]",
    )


def blade_span(y, z):
    h = y - GROUND
    half = 16 - 2 * (h / 194) + 1.4 * math.sin(h / 194 * math.pi)
    u = (z - AXIS) / half
    if abs(u) >= 1:
        return None
    # The crown descends in an arc from its north tip; the wide lens bows forward.
    roof = CAP - round(3 * (u + 1) + 3.8 * (u + 1) ** 2)
    if y > roof:
        return None
    arc = math.sqrt(1 - u * u)
    rear = round(295 + 7.5 * arc + 0.8 * math.sin(h / 194 * math.pi))
    front = round(292 - 7.5 * arc)
    return front, rear, roof


def blade(b):
    for y in range(GROUND, CAP + 1):
        h = y - GROUND
        for z in range(AXIS - 18, AXIS + 19):
            section = blade_span(y, z)
            if section is None:
                continue
            front, back, roof = section
            for x in range(front, back + 1):
                if y <= -436 and x <= 298:
                    continue  # inside the hull of the command annex
                outside = (
                    x in (front, back)
                    or z in (AXIS - 17, AXIS + 17)
                    or y == roof
                    or any(blade_span(y, z + dz) is None for dz in (-1, 1))
                )
                # Cover changes of profile with a continuous underside and crown.
                if not outside:
                    above = blade_span(y + 1, z)
                    below = blade_span(y - 1, z)
                    outside = any(
                        span is None or not span[0] <= x <= span[1]
                        for span in (above, below)
                    )
                if not outside:
                    for neighbor in (blade_span(y, z + 1), blade_span(y, z - 1)):
                        if neighbor is None or not neighbor[0] <= x <= neighbor[1]:
                            outside = True
                if not outside:
                    continue
                state = "smooth_sandstone" if x <= 292 else "white_terracotta"
                if abs(z - AXIS) >= 13 or y >= roof - 1:
                    state = "smooth_quartz"
                if x == back and abs(z - AXIS) >= 7:
                    state = "cut_copper"
                # Sloping luminous cuts wrap into the back of the skin at decreasing intensity.
                diagonal = h + (z - AXIS) * 0.48 - max(0, x - front) * 0.32
                distance = min(abs(diagonal - row) for row in (58, 102, 147))
                if distance < 2.4 and y < roof - 4:
                    state = "white_terracotta" if x > front + 2 else "cut_copper"
                    if distance < 0.95 and x <= front + 1 and abs(z - AXIS) <= 12:
                        state = "pearlescent_froglight[axis=y]"
                b.put(x, y, z, state)
    # The scooped launch hood reaches forward from the lens. Its plan fans into two spars,
    # leaving the operations building visible and the west entrance unobstructed.
    for x in range(238, 293):
        t = (x - 238) / 54
        half = 11 + 8 * math.sin(t * math.pi * 0.85) - 3 * t
        for z in range(AXIS - math.ceil(half), AXIS + math.ceil(half) + 1):
            u = abs((z - AXIS) / half)
            if u > 1:
                continue
            crown = -443 + 25 * (t**0.75) + 8 * math.sin(t * math.pi) - 9 * u**1.9
            top = round(crown)
            thickness = 2 if u < 0.9 else 3
            for y in range(top - thickness, top + 1):
                state = "smooth_quartz" if u > 0.93 or x < 241 else "smooth_sandstone"
                if y == top - thickness:
                    state = "cut_copper" if u > 0.83 else "polished_andesite"
                b.put(x, y, z, state)
            # Shallow scored joints divide the curved fairing into formed metal panels.
            if x > 241 and (x - round(u * 3)) in (250, 264, 279) and u < 0.94:
                b.put(x, top, z, "white_terracotta")
    for sign in (-1, 1):
        for i in range(44):
            t = i / 43
            x = round(245 + 43 * t)
            z = AXIS + sign * round(20 - 7 * t)
            y = GROUND + round(55 * (t**0.85))
            for dx in range(4):
                b.box(x + dx, y - 2, z - 1, x + dx, y + 1, z + 1, "white_terracotta")
                b.put(x + dx, y + 1, z, "smooth_quartz")


def extend_lift(b):
    path = "public_lifts_r65.json"
    spec = json.loads((b.world / path).read_bytes())
    lift = next(lift for lift in spec["lifts"] if lift["id"] == LIFT_ID)
    template = next(f for f in lift["floors"] if f["approach_y"] == -442)
    target = copy.deepcopy(template)
    dy = WATCH - template["approach_y"]
    target.update(approach_y=WATCH, label="4F / 上部光学観測室")
    for pos in [target["cabin"], target["controller"]]:
        pos[1] += dy
    for call in target["calls"]:
        for key in ("position", "target_controller"):
            call[key][1] += dy
    for door in target["landing_doors"] + target["cabin_doors"]:
        door["pos"][1] += dy
    lift["floors"] = [f for f in lift["floors"] if f["approach_y"] != WATCH] + [target]

    for y in range(-436, WATCH + 7):
        for x in range(289, 296):
            for z in range(334, 341):
                edge = x in (289, 295) or z in (334, 340)
                b.put(x, y, z, "light_gray_concrete" if edge or y == WATCH + 6 else AIR)
    # The shell wraps fully around the optical station. Glazing is bounded by the real blade outline.
    for z in range(327, 354):
        front, back, _ = blade_span(WATCH, z)
        for x in range(front + 1, back):
            if 289 <= x <= 295 and 334 <= z <= 340:
                continue
            b.put(x, WATCH - 1, z, FLOOR)
            b.put(x, WATCH + 5, z, WALL)
            if z in (327, 353):
                b.box(x, WATCH, z, x, WATCH + 4, z, WALL)
            if x == front + 2 and z % 7 == 0:
                b.put(x, WATCH + 5, z, LAMP)
        if 331 <= z <= 349:
            bottom = WATCH + 1 + round((349 - z) * 0.11)
            for y in range(bottom, bottom + 2):
                b.put(
                    blade_span(y, z)[0], y, z, GLASS if z % 8 else "polished_andesite"
                )
    controller = target["controller"]
    b.put(*controller, b.reader.get(*template["controller"]))
    tag = source_entity(b.reader, tuple(template["controller"]))
    tag["data"]["name"] = nbtlib.String(target["label"])
    b.tags[tuple(controller)] = tag
    for door in target["landing_doors"]:
        b.put(*door["pos"], "projectseele:lift_door_interlock_r53")
    for call in target["calls"]:
        b.put(*call["position"], call["state"])
    b.output(path, json.dumps(spec, ensure_ascii=False, indent=1).encode("utf8"))


def command_tower(b, original_region):
    previous = World(original_region)
    restore_grove(b, previous)
    clear_crowns(b, previous)
    building(b)
    blade(b)
    extend_lift(b)
    b.reports["command_tower"] = {
        "forecourt": [207, GROUND, 344],
        "highest_shell_cell": CAP,
        "operating_room_arrival": [249.5, -460, 343.5],
        "yaw": -90,
        "lift_feet": [-496, -474, -460, -442, WATCH],
    }
