"""Grade the west approach and entrance court to the existing lobby door at (221, -470, 395)."""

from dogma_recommission import AIR, AIRS

GRASS = "minecraft:grass_block[snowy=false]"
DIRT = "minecraft:dirt"
PATH = "minecraft:polished_andesite"
PAVING = "minecraft:smooth_stone"
LOBBY_FLOOR = -471

# X, existing branch centre Z, and road surface (the public fork begins at Y=-468).
APPROACH = (
    (166, 369, -468),
    (184, 374, -470),
    (201, 380, -471),
    (209, 388, -471),
    (215, 395, -471),
    (220, 395, -471),
)


def forecourt_plan():
    paved = {}
    for (x0, z0, y0), (x1, z1, y1) in zip(APPROACH, APPROACH[1:]):
        for x in range(x0, x1 + 1):
            fraction = (x - x0) / (x1 - x0)
            z = round(z0 + fraction * (z1 - z0))
            floor = round(y0 + fraction * (y1 - y0))
            width = 2 if x < 173 else 3
            for offset in range(-width, width + 1):
                paved[x, z + offset] = floor
    # The apron flares out from the path, then meets the entire width of the lobby canopy.
    # Leave the separately surveyed transverse gallery and rail corridor north-west of the court.
    for x in range(196, 221):
        near = max(379, 384 - (x - 196))
        far = min(409, 386 + 2 * (x - 196))
        if x < 202:
            far = min(far, 392)
        for z in range(near, far + 1):
            paved[x, z] = LOBBY_FLOOR
    return paved


def wooded(s):
    return s and ("_leaves[" in s or "_log[" in s or s.startswith("minecraft:vine["))


def cut_front_grove(b, paved):
    # Survey tree bases as well as overhangs, so an entire tree around the doorway can be removed.
    def front(x, z):
        if 187 <= x <= 228 and 368 <= z <= 419:
            return True
        return any((x + i, z + j) in paved for i in (-4, 0, 4) for j in (-4, 0, 4))

    grove = {(x, z) for x in range(162, 229) for z in range(357, 420) if front(x, z)}
    crowns = set(grove)
    for x, z in grove:
        if any("_log[" in (b.get(x, y, z) or "") for y in range(-480, -444)):
            crowns.update((x + i, z + j) for i in range(-6, 7) for j in range(-6, 7))
    for x, z in crowns:
        for y in range(-480, -425):
            if wooded(b.get(x, y, z)):
                b.put(x, y, z, AIR)


def grade_forecourt(b):
    paved = forecourt_plan()
    cut_front_grove(b, paved)
    # Native meadow varies from -467 at the old branch to -476 below the doorstep.
    # Keep a flat lawn at the court perimeter before tapering back into the native slope.
    verge = {}
    for (x, z), y in paved.items():
        for i in range(-10, 11):
            for j in range(-10, 11):
                pos = (x + i, z + j)
                distance = max(abs(i), abs(j))
                if pos not in verge or distance < verge[pos][0]:
                    verge[pos] = distance, y
    ground = {
        GRASS,
        DIRT,
        "minecraft:coarse_dirt",
        "minecraft:stone",
        "minecraft:andesite",
        PATH,
        PAVING,
    }
    for (x, z), (distance, floor) in verge.items():
        if x > 220 or x < 166 or (x <= 201 and z >= 394):
            continue
        # Only landscape the documented west entrance. Ignore the overhead canopy and
        # start below its soffit. A foreign foundation or wall always terminates the survey.
        surface_y = None
        for y in range(-466, -483, -1):
            s = b.get(x, y, z)
            if s in AIRS or wooded(s):
                continue
            if s in ground:
                surface_y = y
            break
        if surface_y is None:
            continue
        if distance:
            relief = max(0, (distance - 2) // 2)
            level = max(floor - relief, min(floor + relief, surface_y))
            if level == surface_y:
                continue
            material = GRASS
        else:
            level = floor
            # A single quiet, dark edging outlines the open court. The original road
            # has its own andesite finish west of the fan.
            edge = any(
                (x + i, z + j) not in paved
                for i, j in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            material = PATH if x < 196 or (edge and x != 220) else PAVING
        if surface_y > level:
            for y in range(level + 1, surface_y + 1):
                if b.get(x, y, z) in ground:
                    b.put(x, y, z, AIR)
        else:
            for y in range(surface_y, level):
                b.put(x, y, z, DIRT)
        b.put(x, level, z, material)
