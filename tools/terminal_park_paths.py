"""Lay out the footways between the pyramid park, second command entrance and science precinct."""

import math

import numpy as np

from dogma_recommission import AIR, AIRS
from terminal_forecourt import DIRT, GRASS, LOBBY_FLOOR, PATH, PAVING, wooded


# Walking surfaces at the original west path, the public lobby threshold and the
# pedestrian brink of the science precinct, north of the tracks.
WEST = (82, 389, -467)
THRESHOLD = (220, 395, LOBBY_FLOOR)
SCIENCE = (225, 474, -467)
ROUTES = (
    (
        6.35,
        (
            WEST,
            (96, 389, -467),
            (113, 394, -467),
            (126, 395, -467),
            (150, 395, -467),
            (166, 395, -468),
            (182, 395, -469),
            (196, 395, -470.5),
            (205, 395, -471),
            THRESHOLD,
        ),
    ),
    (
        4.15,
        (
            WEST,
            (96, 388, -467),
            (112, 382, -467),
            (131, 376, -467),
            (146, 373, -467.5),
            (156, 374, -468),
            (166, 378, -468.5),
            (178, 384, -469),
            (191, 392, -470),
            (202, 395, -471),
        ),
    ),
    (
        4.15,
        (
            (184, 395, -469),
            (184, 408, -469.5),
            (186, 423, -470),
            (190, 441, -471),
            (195, 451, -472),
            (203, 457, -472),
            (213, 461, -471),
            (221, 468, -469),
            SCIENCE,
        ),
    ),
)
# These tree bases were traced in the full native site preview; several are on
# the park's outer path or behind a wing and extend into the public sightline.
VIEW_GROVES = (
    (147, 491),
    (150, 483),
    (162, 491),
    (164, 479),
    (171, 341),
    (174, 481),
    (166, 357),
    (166, 387),
    (166, 462),
    (167, 435),
    (173, 414),
    (180, 355),
    (186, 337),
    (197, 339),
    (197, 363),
    (201, 352),
    (207, 358),
    (210, 351),
    (212, 323),
    (215, 452),
    (224, 336),
    (225, 431),
    (231, 362),
    (232, 426),
    (240, 434),
    (249, 444),
    (257, 428),
    (259, 407),
    (260, 418),
)

# Half-widths of the softly tapered arrival terrace. Z=395 is the entrance axis.
TERRACE = ((195, 6), (196, 7), (198, 8), (204, 11), (211, 13), (217, 13), (220, 12))


def park_pavement():
    """Return twice the block grade, so gradual slopes can use half-height treads."""
    surface = {}
    best = {}
    for width, controls in ROUTES:
        for (x, z, y), (xx, zz, yy) in zip(controls, controls[1:]):
            length = (xx - x) ** 2 + (zz - z) ** 2
            for a in range(
                math.floor(min(x, xx) - width), math.ceil(max(x, xx) + width) + 1
            ):
                for c in range(
                    math.floor(min(z, zz) - width), math.ceil(max(z, zz) + width) + 1
                ):
                    # The lit northern lip at the seam belongs to the pyramid plinth.
                    if a <= 88 and c < 387:
                        continue
                    point = (a, c)
                    if a < WEST[0] or c >= SCIENCE[1] or (a > 220 and c < 420):
                        continue
                    t = max(
                        0, min(1, ((a - x) * (xx - x) + (c - z) * (zz - z)) / length)
                    )
                    distance = (a - x - t * (xx - x)) ** 2 + (c - z - t * (zz - z)) ** 2
                    seam_width = min(width, 2.5 + max(0, a - WEST[0]) * 0.28)
                    if distance <= seam_width**2 and distance < best.get(
                        point, math.inf
                    ):
                        best[point] = distance
                        surface[point] = round(2 * (y + t * (yy - y)))
    for (x0, w0), (x1, w1) in zip(TERRACE, TERRACE[1:]):
        for x in range(x0, x1 + 1):
            width = round(w0 + (x - x0) * (w1 - w0) / (x1 - x0))
            for z in range(395 - width, 395 + width + 1):
                surface[x, z] = 2 * LOBBY_FLOOR
    return surface


def clear_wing_bays(b, pavement, mesh):
    # The inside of each wing is the side facing the park (-X). At its widest
    # part this includes the courtyards between X=220 and the curved back wall.
    clearing = {
        (x, z)
        for x in range(163, 201)
        for z in range(365, 422)
        if ((x - 184) / 25) ** 2 + ((z - 394) / 32) ** 2 < 1
    }
    clearing.update(VIEW_GROVES)
    for j in range(mesh.shape[1]):
        solid = np.flatnonzero(mesh[:, j, :40].any(axis=1))
        if len(solid) and 337 <= 334 + j <= 452:
            clearing.update((x, 334 + j) for x in range(194, 201 + int(solid[0])))
    for x, z in pavement:
        for i in range(-3, 4):
            for j in range(-3, 4):
                clearing.add((x + i, z + j))
    # Clear trees rooted close enough to overhang the paths and bays. Attribute
    # canopy columns to their nearest trunk so preserved woodland keeps its full crowns.
    lower_x = min(x for x, z in clearing) - 6
    upper_x = max(x for x, z in clearing) + 6
    lower_z = min(z for x, z in clearing) - 6
    upper_z = max(z for x, z in clearing) + 6
    trunks = set()
    wood = {}
    for x in range(lower_x, upper_x + 1):
        for z in range(lower_z, upper_z + 1):
            cells = []
            for y in range(-484, -425):
                s = b.get(x, y, z)
                if wooded(s):
                    cells.append(y)
                    if "_log[" in s:
                        trunks.add((x, z))
            if cells:
                wood[x, z] = cells
    cut = {t for t in trunks if t in clearing}
    for (x, z), ys in wood.items():
        if (x, z) not in clearing:
            neighbor = [t for t in trunks if abs(t[0] - x) <= 6 and abs(t[1] - z) <= 6]
            if (
                not neighbor
                or min(neighbor, key=lambda t: ((t[0] - x) ** 2 + (t[1] - z) ** 2, t))
                not in cut
            ):
                continue
        root_y = min(ys) - 1
        if (x, z) in cut and b.get(x, root_y, z) == DIRT:
            b.put(x, root_y, z, GRASS)
        for y in ys:
            b.put(x, y, z, AIR)


def _meadow(b, x, z):
    # The end of the old abutment used native-looking stone at the grass surface.
    # Reconstruct this last rectangle using the natural profiles just north and south.
    if x <= 165 and 350 <= z <= 451:
        return -467
    for y in range(-459, -490, -1):
        if b.get(x, y, z) == "minecraft:stone":
            return min(-467, y + 4)
    raise ValueError(("Missing rock under the park", x, z))


def _place(b, x, z, floor, state, slab=None):
    allowed = {
        GRASS,
        DIRT,
        PATH,
        PAVING,
        "minecraft:andesite",
        "minecraft:stone",
        "minecraft:coarse_dirt",
    }
    height = None
    for y in range(-466, -485, -1):
        old = b.get(x, y, z)
        if old in AIRS or wooded(old):
            continue
        if old not in allowed:
            return False
        height = y
        break
    if height is None:
        return False
    # Do not bury a woodland trunk or excavate another building's blocks.
    if any(
        b.get(x, y, z) not in allowed | AIRS
        for y in range(min(height, floor), max(height, floor) + 1)
    ):
        return False
    for y in range(min(height, floor), max(height, floor) + 1):
        s = DIRT if y < floor else state if y == floor else AIR
        if b.get(x, y, z) != s:
            b.put(x, y, z, s)
    if slab:
        b.put(x, floor + 1, z, slab)
    return True


def lay_out_park(b, mesh):
    surface = park_pavement()
    clear_wing_bays(b, surface, mesh)
    # Remove the previous fork, paved wedge, isolated stone footing and straight
    # grass benches. The lobby wall starts at X=221. The precinct paving starts at Z=474.
    for x in range(133, 221):
        for z in range(358, 423):
            if (x, z) in surface:
                continue
            if x < 150 and z > 391:
                continue
            if x <= 165 and z >= 405:
                continue
            if x > 196 and z >= 415 and x > 218:
                continue
            floor = _meadow(b, x, z)
            _place(b, x, z, floor, GRASS)
    # Smooth the entire public lawn across the original wedge and approach. Only
    # exposed park soil is graded. Paved facilities, structural feet and rails
    # at either side retain their existing geometry.
    for x in range(141, 244):
        for z in range(321, 474):
            if (x, z) in surface:
                continue
            t = max(
                0.0,
                min(
                    1.0,
                    min((x - 140) / 18, (244 - x) / 21, (z - 321) / 22, (474 - z) / 24),
                ),
            )
            native = _meadow(b, x, z)
            grade = -467 - min(4, max(0, (x - 149) / 13))
            y = round(native + (grade - native) * t)
            for height in range(-466, -485, -1):
                state = b.get(x, height, z)
                if state in AIRS:
                    continue
                if state in (GRASS, DIRT) and height != y:
                    _place(b, x, z, y, GRASS)
                break
    # Rejoin the surrounding country at its own height over a sloped grassy verge.
    verge = {}
    for (x, z), grade in surface.items():
        for i in range(-9, 10):
            for j in range(-9, 10):
                d = i * i + j * j
                p = x + i, z + j
                if d <= 81 and p not in surface and d < verge.get(p, (100, None))[0]:
                    verge[p] = d, grade
    for (x, z), (d, grade) in verge.items():
        if x < WEST[0] or z >= 474 or (x > 220 and z < 420):
            continue
        native = next(
            (y for y in range(-466, -485, -1) if b.get(x, y, z) == GRASS),
            _meadow(b, x, z),
        )
        dist = math.sqrt(d)
        margin = max(0, min(1, (dist - 0.8) / 8))
        floor = round(grade / 2 + (native - grade / 2) * margin)
        _place(b, x, z, floor, GRASS)
    # Ease the lawn against the podium's raised stone shoe on either flank of the canopy.
    # Read the open meadow only; the original plinth, doors and canopy posts stop this pass.
    for x in range(196, 247):
        for z in range(366, 427):
            if (x, z) in surface:
                continue
            dx = max(0, 212 - x, x - 219)
            dz = max(0, 385 - z, z - 405)
            distance = math.hypot(dx, dz)
            grade = LOBBY_FLOOR - max(0, round((distance - 4) / 3))
            for y in range(-466, -484, -1):
                state = b.get(x, y, z)
                if state in AIRS:
                    continue
                if state == GRASS and y < grade:
                    _place(b, x, z, grade, GRASS)
                break
    for (x, z), grade in surface.items():
        edge = any(
            (x + i, z + j) not in surface for i, j in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
        light_edge = (
            edge and x > WEST[0] + 3 and x < THRESHOLD[0] and z < SCIENCE[1] - 2
        )
        state = "minecraft:smooth_quartz" if light_edge else PAVING
        half = (
            "minecraft:smooth_quartz_slab"
            if light_edge
            else "minecraft:smooth_stone_slab"
        ) + "[type=bottom,waterlogged=false]"
        if not _place(b, x, z, grade // 2, state, half if grade % 2 else None):
            raise ValueError(("Obstruction on the surveyed public way", x, z))
