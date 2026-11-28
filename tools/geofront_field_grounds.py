"""Ground works around the second command post, the lake-side research yard and the GeoFront airfield."""

import math

from dogma_recommission import AIR, AIRS
from terminal_forecourt import DIRT, GRASS, LOBBY_FLOOR
from terminal_park_paths import park_pavement

STONE = "minecraft:stone"
PAVING = "minecraft:smooth_stone"
WHITE = "minecraft:smooth_quartz"
ASPHALT = "minecraft:gray_concrete"
LAMP = "minecraft:sea_lantern"
TRIM = "minecraft:polished_andesite"
FRAME = "projectseele:nerv_structural_panel"
WALL = "projectseele:nerv_wall_panel"
FLOOR = "projectseele:nerv_floor_panel"
GLASS = "minecraft:light_blue_stained_glass"
YELLOW = "minecraft:yellow_terracotta"
DECK = -461
RUNWAY = (146, 174, 474, 1068)
STANDS = ((199.5, -460, 517.5), (232.5, -460, 517.5))
PAVEMENTS = {PAVING, WHITE, TRIM, ASPHALT, STONE, "minecraft:andesite"}
SOIL = {GRASS, DIRT, STONE, "minecraft:coarse_dirt", "minecraft:podzol[snowy=false]"}


def change(b, x, y, z, s):
    if b.get(x, y, z) != s:
        b.put(x, y, z, s)


def plant(state):
    if not state:
        return False
    return (
        any(
            p in state
            for p in (
                "_leaves[",
                "_log[",
                "minecraft:grass[",
                "minecraft:tall_grass",
                "minecraft:short_grass",
                "fern",
                "azure_bluet",
                "dandelion",
                "poppy",
                "oxeye_daisy",
                "sapling",
                "minecraft:grass",
                "allium",
                "lilac",
                "lily_of_the_valley",
                "rose_bush",
                "peony",
            )
        )
        and state != GRASS
    )


def ground(b, x, z, maximum=-448, minimum=-502):
    for y in range(maximum, minimum - 1, -1):
        state = b.get(x, y, z)
        if (
            state not in AIRS
            and not plant(state)
            and state
            and not state.startswith("minecraft:light[")
        ):
            return y, state
    raise ValueError(("Missing GeoFront ground", x, z))


def cell_grade(b, x, z, current, target, top):
    for y in range(min(current, target), max(current, target) + 1):
        state = (
            AIR
            if y > target
            else top
            if y == target
            else DIRT
            if y >= target - 3
            else STONE
        )
        change(b, x, y, z, state)
    if top == GRASS:
        for y in range(target - 2, target):
            if b.get(x, y, z) in SOIL | PAVEMENTS:
                change(b, x, y, z, DIRT)


def clear_trees(b, rectangles, selected):
    """Match overhanging crown columns to their nearest stem, including truncated stems."""
    for x0, x1, z0, z1 in rectangles:
        trunks = set()
        cells = {}
        for z in range(z0 - 5, z1 + 6):
            for x in range(x0 - 5, x1 + 6):
                values = []
                for y in range(-489, -417):
                    s = b.get(x, y, z)
                    if s and ("_leaves[" in s or "_log[" in s):
                        values.append(y)
                        if "_log[" in s:
                            trunks.add((x, z))
                if values:
                    cells[(x, z)] = values
        for (x, z), levels in cells.items():
            candidates = [
                (i, k)
                for i in range(x - 5, x + 6)
                for k in range(z - 5, z + 6)
                if (i, k) in trunks
            ]
            if candidates:
                stem = min(
                    candidates, key=lambda p: ((p[0] - x) ** 2 + (p[1] - z) ** 2, p)
                )
                if not selected(*stem):
                    continue
            elif not selected(x, z):
                continue
            if b.get(x, min(levels) - 1, z) == DIRT:
                change(b, x, min(levels) - 1, z, GRASS)
            for y in levels:
                change(b, x, y, z, AIR)


def direct_walk(b):
    old = park_pavement()
    plan = {}
    for x in range(82, 221):
        t = (x - 82) / 138
        center = 389 + 6 * t
        half = min(6.4, 2.4 + (x - 82) * 0.38) + min(6, max(0, (x - 192) * 0.28))
        grade = round(2 * (-467 - 4 * min(1, max(0, (x - 149) / 53))))
        for z in range(math.ceil(center - half), math.floor(center + half) + 1):
            if x <= 88 and z < 387:
                continue
            edge = abs(z - center) > half - 1
            inset = (
                104 < x < 199
                and abs(z - center) > half - 2
                and abs(z - center) <= half - 1
            )
            cap = WHITE if edge else TRIM if inset else PAVING
            if edge and (x - 108) % 16 == 0 and 100 <= x <= 210 and grade % 2 == 0:
                cap = LAMP
            plan[(x, z)] = (grade, cap)
    paved = {PAVING, WHITE, TRIM, LAMP}
    for (x, z), grade in old.items():
        if (
            (x, z) in plan
            or z >= 400
            and 177 <= x <= 190
            or z >= 405
            and x < 196
            or z >= 411
        ):
            continue
        y = grade // 2
        s = b.get(x, y, z)
        if s in paved:
            if "slab[" in b.get(x, y + 1, z):
                change(b, x, y + 1, z, AIR)
            change(b, x, y, z, GRASS)
    for (x, z), (grade, cap) in plan.items():
        y = grade // 2
        current, state = ground(b, x, z, maximum=-465, minimum=-482)
        if state not in SOIL | paved | PAVEMENTS and "slab[" not in state:
            raise ValueError(("Protected object along HQ walk", x, current, z, state))
        cell_grade(b, x, z, current, y, cap)
        if grade % 2:
            slab = (
                "smooth_quartz_slab"
                if cap == WHITE
                else "polished_andesite_slab"
                if cap == TRIM
                else "smooth_stone_slab"
            )
            change(
                b, x, y + 1, z, "minecraft:" + slab + "[type=bottom,waterlogged=false]"
            )
    return plan


def old_stands(b):
    for x in range(40, 165):
        for z in range(415, 453):
            if not (x >= 120 or z >= 444):
                continue
            if b.get(x, -467, z) in {ASPHALT, "minecraft:white_concrete", LAMP}:
                target = -467 - int(x >= 158)
                cell_grade(b, x, z, -467, target, GRASS)


def surface_color(x, z):
    left, right, start, end = RUNWAY
    if left <= x <= right and start <= z <= end:
        dx = x - 160
        distance = min(z - start, end - z)
        if abs(dx) == 14:
            return LAMP if distance % 18 == 4 else TRIM
        if (
            abs(dx) == 12
            or abs(dx) in (4, 7, 10)
            and 6 <= distance <= 15
            or dx == 0
            and distance > 24
            and (z - start) % 18 < 7
        ):
            return WHITE
        return ASPHALT
    color = PAVING
    for cx, _, cz in STANDS:
        dx, dz = x - int(cx), z - int(cz)
        if max(abs(dx), abs(dz)) <= 14:
            color = TRIM
            if abs(dx) in (13, 14) and abs(dz) > 6 or abs(dz) == 14 and abs(dx) > 7:
                color = WHITE
            if dx == 0 and (dz <= 1 or dz == 4) or abs(dx) <= 3 and dz == 1:
                color = YELLOW
    if z == 496 and 175 <= x <= 233 or x in (199, 232) and 496 <= z <= 503:
        color = YELLOW
    if 176 <= x <= 287 and (z in (475, 543) or x == 287):
        color = LAMP if (x + z) % 18 == 0 else TRIM
    return color


def airfield(b):
    # The old apron at -467 shares an active underground railway. This independent
    # structural deck bridges the entire two-track corridor with five blocks of air.
    outer = [(119, 299, 450, 563), (122, 198, 554, 1092)]

    def selected(x, z):
        return (
            124 <= x <= 291
            and 459 <= z <= 551
            or 125 <= x <= 195
            and 459 <= z <= 1088
            or 162 <= x <= 192
            and 452 <= z <= 485
        )

    clear_trees(b, outer, selected)
    for z in range(453, 1090):
        platform = z <= 558
        for x in range(120, 289 if platform else 197):
            ax = max(140 - x, 0, x - 288)
            az = max(474 - z, 0, z - 545)
            apron_dist = math.hypot(ax, az)
            strip_dist = math.hypot(max(146 - x, 0, x - 174), max(474 - z, 0, z - 1068))
            dist = min(apron_dist, strip_dist)
            if dist > 23 or x >= 192 and z >= 547:
                continue
            # Keep laboratory wall and southeast public passage in their original
            # elevation. Existing slabs stay under the deck with their native air.
            main = dist == 0
            raised = 213 <= x <= 288 and 474 <= z <= 546
            crossings = 478 <= z <= 504 or x >= 272 and 477 <= z <= 525
            if main:
                cap = surface_color(x, z)
                half_steps = min(12, max(0, z - 533)) if x >= 183 else 0
                y = (2 * DECK - half_steps) // 2
                if x >= 264 and z < 477:
                    y = max(-467, DECK - (x - 264) // 4)
                for yy in range(y + 1, max(y + 2, -448)):
                    if plant(b.get(x, yy, z)):
                        change(b, x, yy, z, AIR)
                if raised or crossings:
                    for yy in range(y + 1, -435):
                        if plant(b.get(x, yy, z)):
                            change(b, x, yy, z, AIR)
                    if y == DECK:
                        change(b, x, y - 1, z, TRIM)
                    change(b, x, y, z, cap)
                    if half_steps % 2:
                        change(
                            b,
                            x,
                            y + 1,
                            z,
                            "minecraft:smooth_stone_slab[type=bottom,waterlogged=false]",
                        )
                    continue
                current, state = ground(b, x, z)
                if state not in SOIL:
                    raise ValueError(
                        (
                            "Unexpected structure within landing grounds",
                            x,
                            current,
                            z,
                            state,
                        )
                    )
                cell_grade(b, x, z, current, y, cap)
                if half_steps % 2:
                    change(
                        b,
                        x,
                        y + 1,
                        z,
                        "minecraft:smooth_stone_slab[type=bottom,waterlogged=false]",
                    )
                continue
            current, state = ground(b, x, z)
            if state not in SOIL:
                continue
            # Ease the surrounding meadow to the runway edge over two to three
            # horizontal blocks per rise. Near the tracks, skip the soil fill.
            if crossings:
                continue
            end_grade = DECK
            if x >= 183 and z > 536:
                end_grade = max(-467, DECK - (z - 536))
            if z < 474 and x >= 211:
                end_grade = DECK - max(0, (x - 264) // 4)
            grade = round(end_grade + (current - end_grade) * min(1, dist / 21))
            if grade != current:
                cell_grade(b, x, z, current, grade, GRASS)
    # North pedestrian ramp uses the surveyed approach just before the parked jets.
    for z in range(460, 479):
        grade = -940 + z - 460
        y = grade // 2
        for dx in range(-4, 5):
            x = 218 + round((z - 460) * 7 / 18) + dx
            current, state = ground(b, x, z, maximum=-458)
            cap = WHITE if abs(dx) == 4 else PAVING
            if z >= 474:
                for yy in range(y + 1, DECK + 1):
                    change(b, x, yy, z, AIR)
                change(b, x, y, z, cap)
            elif state in SOIL | PAVEMENTS | {WHITE} or "slab[" in state:
                cell_grade(b, x, z, current, y, cap)
            else:
                raise ValueError(
                    ("Unexpected material at science park ramp", x, current, z, state)
                )
            if grade % 2:
                slab = "smooth_quartz_slab" if cap == WHITE else "smooth_stone_slab"
                change(
                    b,
                    x,
                    y + 1,
                    z,
                    "minecraft:" + slab + "[type=bottom,waterlogged=false]",
                )


def forest_margin(b):
    # One side of the previous earthwork severed the fir crowns over the
    # low meadow and left an eleven-block pier under the handrail at Z538.
    clear_trees(b, [(-2, 68, 520, 580)], lambda x, z: -1 <= x <= 65 and 524 <= z <= 574)
    for x in range(25, 36):
        for y in range(-493, -464):
            s = b.get(x, y, 538)
            if s in {PAVING, "minecraft:polished_deepslate"} or "nerv_edge_rail" in s:
                change(b, x, y, 538, AIR if y >= -467 else DIRT if y >= -470 else STONE)
    for x in range(6, 78):
        for z in range(531, 579):
            for y in (-467, -466):
                if x == 7 and 533 <= z <= 574 and "nerv_edge_rail" in b.get(x, y, z):
                    change(b, x, y, z, AIR)
            now, s = ground(b, x, z)
            if s not in SOIL:
                continue
            west, _ = ground(b, 5, z)
            east, _ = ground(b, 78, max(547, z))
            t = min(1, (x - 5) / 55)
            north = min(1, max(0, (z - 532) / 16))
            target = round(
                west
                + (east - west) * t * t * (3 - 2 * t) * north * north * (3 - 2 * north)
            )
            fade = min(1, (z - 531) / 6, (579 - z) / 10, (78 - x) / 9)
            y = round(now + (target - now) * fade)
            if now != y or s != GRASS:
                cell_grade(b, x, z, now, y, GRASS)


def test_campus(b):
    # The three synchronisation pools, the pilot stations and their scripts sit
    # in the open centre. The roof is carried on the two dry gallery edges.
    for x in range(-18, 106):
        for z in range(-145, -55):
            if 8 <= x <= 86 and -140 <= z <= -74:
                continue
            s = b.get(x, -468, z)
            if s not in SOIL | {
                "minecraft:black_concrete",
                "minecraft:deepslate_bricks",
            }:
                continue
            if not (b.get(x, -467, z) in AIRS):
                continue
            line = x in (3, 92) or z in (-142, -70)
            pattern = (x + 2) % 13 == 0 if z < -135 or z > -78 else (z + 4) % 13 == 0
            cap = WHITE if line else TRIM if pattern else PAVING
            if line and (x + z) % 13 == 0:
                cap = LAMP
            change(b, x, -468, z, cap)
    for z in range(-138, -74):
        for x in range(5, 91):
            side = min(x - 5, 90 - x)
            if not (side <= 10 or side <= 15 and z % 12 in (0, 1)):
                continue
            height = -451 + min(4, side // 3)
            if z % 12 in (0, 1):
                cap = FRAME
                change(b, x, height - 1, z, WHITE if side >= 2 else FRAME)
            elif side in (0, 1, 10):
                cap = WHITE
            else:
                cap = GLASS
            change(b, x, height, z, cap)
            public_entrance = x >= 89 and -87 <= z <= -80
            if side <= 1 and not public_entrance and z % 12 in (0, 1):
                for y in range(-468, height):
                    if b.get(x, y, z) in AIRS:
                        change(
                            b,
                            x,
                            y,
                            z,
                            LAMP if y in (-463, -455) and side == 0 else FRAME,
                        )
    # Four open transverse portal frames connect the galleries 21 blocks above
    # the occupied floor, with a clear overhead span for every pool and entry.
    for z in (-132, -108, -84):
        for zz in (z, z + 1):
            for x in range(16, 80):
                arch = min(5, min(x - 16, 79 - x) // 3)
                h = -447 + arch
                change(b, x, h, zz, WHITE)
                change(b, x, h + 1, zz, FRAME)
                if x % 8 == 3 and arch == 5:
                    change(b, x, h, zz, LAMP)
    # North face: a deep existing retaining wall backed onto bare rock. Cap it
    # with a continuous cornice and introduce panel bays and a service-light band.
    for x in range(-18, 99):
        for z in (-146, -145, -144):
            for y in range(-486, -467):
                s = b.get(x, y, z)
                if s != "minecraft:deepslate_bricks":
                    continue
                facing = b.get(x, y, z - 1) in AIRS
                if facing or y >= -469:
                    cap = (
                        WHITE
                        if y == -468 or (x + 18) % 12 in (0, 1)
                        else TRIM
                        if y == -469
                        else WALL
                    )
                    if facing and y == -472 and (x + 18) % 12 in (3, 4, 5, 6):
                        cap = LAMP
                    change(b, x, y, z, cap)


def repair(builder):
    direct_walk(builder)
    old_stands(builder)
    airfield(builder)
    forest_margin(builder)
    test_campus(builder)
