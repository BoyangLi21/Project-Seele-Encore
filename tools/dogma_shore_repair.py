"""Repair the perched northern shore of Ashi and the two photographed mountain-road junctions.

Works on a staged copy. The existing surveyed embankments, highway endpoints and inspection
quay control the new horizontal alignments and eighth-block road grades.
"""

import math
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
import nbtlib
from convert_roads_trafficcraft import trace, WHITE, YELLOW, ENTITY
from dogma_recommission import AIR, AIRS
from plan_ashi_landscape_r54 import PLANTS, SOIL

WATER = "minecraft:water[level=0]"
STONE = "minecraft:stone"
DIRT = "minecraft:dirt"
GRASS = "minecraft:grass_block[snowy=false]"
CENTRES = ((-479, 1018), (-452, 1027), (-425, 1035))
LAKE_BOUNDS = (-548, 892, -331, 1078)
ROAD_BOUNDS = (-236, 951, -81, 1085)

# x, z, walking surface Y. Common vertices mark actual junctions.
LAKE_ROADS = [
    [
        (-516, 973, 98.2),
        (-517, 959, 94.1),
        (-514, 950, 91.3),
        (-502, 941, 87.8),
        (-484, 932, 86.4),
        (-470, 924, 86.5),
        (-455, 921, 87.0),
        (-439, 923, 87.4),
    ],
    [
        (-516, 973, 98.2),
        (-521, 985, 98.1),
        (-522, 993, 98.4),
        (-519, 999, 98.9),
        (-513, 1001, 99.8),
        (-504, 993, 101.5),
        (-493, 984, 101.7),
        (-476, 972, 100.5),
        (-462, 960, 97.0),
        (-452, 950, 93.8),
        (-445, 938, 90.0),
        (-439, 923, 87.4),
    ],
    [(-439, 923, 87.4), (-433, 916, 85.8), (-429, 908, 86.0), (-428, 900, 86.8)],
]
HILL_ROADS = [
    [
        (-230, 1025, 107.1),
        (-222, 1037, 105.6),
        (-214, 1047, 104.2),
        (-201, 1053, 103.2),
        (-187, 1058, 104.2),
        (-173, 1063, 105.6),
        (-164, 1065, 106.5),
        (-153, 1061, 107.3),
        (-137, 1049, 109.3),
        (-122, 1038, 110.3),
        (-112, 1028, 109.0),
        (-106, 1019, 107.9),
        (-106, 1012, 106.7),
    ],
    [
        (-201, 1053, 103.2),
        (-189, 1048, 103.7),
        (-173, 1037, 104.5),
        (-157, 1024, 105.4),
        (-146, 1015, 106.0),
        (-135, 1015, 107.3),
        (-122, 1024, 108.7),
        (-112, 1028, 109.0),
    ],
    [
        (-146, 1015, 106.0),
        (-145, 1007, 106.9),
        (-151, 999, 106.8),
        (-154, 991, 106.8),
        (-151, 984, 108.0),
        (-142, 977, 108.5),
        (-134, 971, 107.8),
        (-125, 965, 105.1),
        (-119, 962, 103.5),
    ],
]


def pavement(s):
    return (
        s.startswith(
            (
                "trafficcraft:asphalt",
                "trafficcraft:concrete",
                "projectseele:road_asphalt",
                "projectseele:road_marking",
                "minecraft:smooth_stone",
            )
        )
        or s == "minecraft:black_concrete"
    )


def vegetation(s):
    return s.split("[")[0] in PLANTS or any(
        v in s
        for v in (
            "_leaves",
            "_log",
            "_wood",
            "_sapling",
            "moss_carpet",
            "grass[",
            "snow[",
            "_bush",
            "_flower",
            "lilac",
            "sunflower",
        )
    )


def soil(s):
    return s.split("[")[0] in SOIL or s in (
        "minecraft:moss_block",
        "minecraft:dirt_path",
    )


def capture(world, bounds):
    x0, z0, x1, z1 = bounds
    shape = (z1 - z0 + 1, x1 - x0 + 1)
    maps = {
        k: np.zeros(shape, np.int16)
        for k in ("soil", "road", "foot", "wet", "highest", "water99")
    }
    for cx in range(x0 >> 4, (x1 >> 4) + 1):
        for cz in range(z0 >> 4, (z1 >> 4) + 1):
            chunk = world.chunk(cx, cz)
            if not chunk:
                raise ValueError(("unmeasured terrain", cx, cz))
            bx, bz = cx * 16, cz * 16
            lx, lz, hx, hz = (
                max(x0, bx),
                max(z0, bz),
                min(x1 + 1, bx + 16),
                min(z1 + 1, bz + 16),
            )
            s = np.s_[lz - z0 : hz - z0, lx - x0 : hx - x0]
            for cy, (ids, pal) in chunk[0].items():
                if not 2 <= cy <= 13:
                    continue
                grid = ids.reshape(16, 16, 16)[:, lz - bz : hz - bz, lx - bx : hx - bx]
                ys = np.arange(cy * 16, cy * 16 + 16)[:, None, None]
                for key, predicate in (
                    ("soil", soil),
                    ("wet", lambda v: v.startswith("minecraft:water[")),
                    (
                        "road",
                        lambda v: (
                            pavement(v)
                            and not v.startswith(
                                ("trafficcraft:concrete", "minecraft:smooth_stone")
                            )
                        ),
                    ),
                    (
                        "foot",
                        lambda v: v.startswith(
                            ("trafficcraft:concrete", "minecraft:smooth_stone")
                        ),
                    ),
                    (
                        "highest",
                        lambda v: (
                            v not in AIRS and not v.startswith("minecraft:light[")
                        ),
                    ),
                ):
                    flags = np.asarray([predicate(v) for v in pal])
                    if flags.any():
                        mask = flags[grid]
                        maps[key][s] = np.maximum(
                            maps[key][s], np.where(mask, ys, 0).max(0)
                        )
                        if key == "wet" and cy == 6:
                            maps["water99"][s] = mask[3]
    return maps


def put(b, x, y, z, state):
    if b.get(x, y, z) != state:
        b.put(x, y, z, state)


def remove_panels(b):
    count = 0
    for xc, zc in CENTRES:
        for x in range(xc - 10, xc + 11):
            for z in range(zc - 6, zc + 9):
                for y in range(101, 120):
                    s = b.get(x, y, z)
                    if s.startswith("minecraft:") and s.split(":")[1] in (
                        "packed_ice",
                        "light_blue_stained_glass",
                        "white_stained_glass",
                        "polished_andesite",
                        "smooth_quartz",
                    ):
                        b.put(x, y, z, AIR)
                        count += 1
    return count


def bank(b, data):
    x0, z0, x1, z1 = LAKE_BOUNDS
    zz, xx = np.mgrid[z0 : z1 + 1, x0 : x1 + 1]
    labels, _ = ndimage.label(data["water99"])
    lake = ndimage.binary_fill_holes(labels == labels[1040 - z0, -460 - x0])
    # Smooth the artificial northward tongue and the abrupt notch at the old construction edge.
    # The crest joins the existing rocks at both ends. The wet side gets a continuous clay bed.
    control = [
        (-530, 1036),
        (-520, 1021),
        (-509, 1009),
        (-501, 995),
        (-491, 984),
        (-478, 979),
        (-462, 978),
        (-450, 980),
        (-438, 981),
        (-422, 984),
        (-409, 988),
        (-395, 995),
        (-380, 998),
    ]
    profile = np.interp(xx, [p[0] for p in control], [p[1] for p in control])
    profile = ndimage.gaussian_filter1d(profile, 2.2, axis=1, mode="nearest")
    band = (xx >= control[0][0]) & (xx <= control[-1][0])

    # Outside the fitted bay follow the original water, preserving the shapes of adjoining headlands.
    wet = lake.copy()
    wet[band & (zz < 1048)] = zz[band & (zz < 1048)] >= profile[band & (zz < 1048)]
    wet = ndimage.binary_fill_holes(wet)
    exterior = ndimage.distance_transform_edt(~wet)
    interior = ndimage.distance_transform_edt(wet)
    scope = (zz >= 935) & (zz <= 1050) & (xx >= -534) & (xx <= -372)
    oldsoil = data["soil"].astype(int)
    # Four adjacent cells at the water level must meet dry ground. Fade the rest of the
    # embankment gradually to the measured drainage gully and feather the western tie-in.
    drytop = np.maximum(
        oldsoil, np.rint(101.1 - np.maximum(0, exterior - 2) * 0.64)
    ).astype(int)
    terrain = oldsoil.copy()
    shore = scope & ~wet & (exterior <= 39)
    shelf = scope & wet & (interior <= 5.5)
    terrain[shore] = drytop[shore]
    terrain[shelf] = np.minimum(
        98,
        np.maximum(
            oldsoil[shelf],
            np.rint(99 - 0.72 * interior[shelf] + 0.13 * np.sin(xx[shelf] * 0.2)),
        ),
    ).astype(int)
    extent = shore | shelf | (scope & lake & ~wet)
    for i, j in np.argwhere(extent):
        x, z, h = int(xx[i, j]), int(zz[i, j]), int(terrain[i, j])
        orig = int(oldsoil[i, j])
        oldwater = int(data["wet"][i, j])
        underwater = bool(wet[i, j])
        if underwater:
            # Restore any plants or isolated old water above the low, submerged beach.
            for y in range(min(h - 1, orig), max(100, orig + 1)):
                s = b.get(x, y, z)
                if not (
                    s in AIRS
                    or soil(s)
                    or vegetation(s)
                    or s.startswith("minecraft:water[")
                ):
                    continue
                target = (
                    "minecraft:gravel"
                    if y == h
                    else "minecraft:clay"
                    if y < h
                    else WATER
                    if y <= 99
                    else AIR
                )
                put(b, x, y, z, target)
        elif h > orig or oldwater > orig and exterior[i, j] < 25:
            for y in range(max(48, orig), max(h, oldwater) + 1):
                s = b.get(x, y, z)
                if not (
                    s in AIRS
                    or soil(s)
                    or vegetation(s)
                    or s.startswith("minecraft:water[")
                ):
                    continue
                if y > h and oldwater < 92 and h == orig:
                    continue
                target = (
                    (GRASS if y == h else DIRT if y >= h - 2 else STONE)
                    if y <= h
                    else AIR
                )
                put(b, x, y, z, target)
    # The old high sources spilled down a pre-existing shallow stream. Retire the
    # escaping high column above native ground; the low stream remains fed upstream.
    retired = scope & ~wet & (data["wet"] >= 94) & (data["wet"] > terrain)
    for i, j in np.argwhere(retired):
        for y in range(max(int(terrain[i, j]) + 1, 85), int(data["wet"][i, j]) + 1):
            x, z = int(xx[i, j]), int(zz[i, j])
            if b.get(x, y, z).startswith("minecraft:water["):
                put(b, x, y, z, AIR)
    return terrain, wet, scope


def rounded(points):
    """Chaikin corner rounding includes Y, so road position and grade have the same tangents."""
    p = np.asarray(points, float)
    for _ in range(3):
        a, b = p[:-1], p[1:]
        p = np.vstack(
            [
                p[0],
                np.stack((0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b), axis=1).reshape(
                    -1, 3
                ),
                p[-1],
            ]
        )
    d = np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1)
    run = np.r_[0, np.cumsum(d)]
    ticks = np.linspace(0, run[-1], math.ceil(run[-1] / 0.18) + 1)
    return np.stack([np.interp(ticks, run, p[:, k]) for k in range(3)], axis=1)


def draw_roads(b, data, bounds, routes, terrain, retire, junctions):
    x0, z0, x1, z1 = bounds
    zz, xx = np.mgrid[z0 : z1 + 1, x0 : x1 + 1]
    query = np.c_[xx.ravel(), zz.ravel()]
    tracks = [rounded(way) for way in routes]
    path = np.vstack(tracks)
    dist, idx = cKDTree(path[:, :2]).query(query)
    dist, idx = dist.reshape(xx.shape), idx.reshape(xx.shape)
    driving = dist <= 3.05
    walk = dist <= 4.45
    # Blend complete intersection planes, rather than creating two adjacent banking steps.
    h = path[idx, 2]
    for x, z, height in junctions:
        blend = np.clip(1 - np.hypot(xx - x, zz - z) / 9, 0, 1)
        h = h * (1 - blend) + height * blend
    grade = np.rint(h * 8).astype(int)
    paint = {}
    for p in tracks:
        tangent = np.gradient(p[:, :2], axis=0)
        normal = (
            np.c_[-tangent[:, 1], tangent[:, 0]]
            / np.linalg.norm(tangent, axis=1)[:, None]
        )
        for offset in (0, -2.67, 2.67):
            centres = np.rint(p[:, :2] + normal * offset).astype(int)
            unique = centres[np.r_[True, np.any(np.diff(centres, axis=0), axis=1)]]
            chain = [(z - z0, x - x0) for x, z in unique]
            for (i, j), piece, _ in trace(chain, driving):
                if all(
                    math.hypot(xx[i, j] - x, zz[i, j] - z) > 6 for x, z, _ in junctions
                ):
                    paint[i, j] = (*piece, YELLOW if offset == 0 else WHITE)
    existing = (data["road"] > 0) | (
        (data["foot"] > 0) & (ndimage.distance_transform_edt(data["road"] == 0) <= 4)
    )
    # Regrass abandoned shoulders using the adjacent terrain, including old stacked slabs.
    retired = retire & existing & ~walk
    for i, j in np.argwhere(retired):
        x, z = int(xx[i, j]), int(zz[i, j])
        h0 = int(terrain[i, j])
        low = max(
            50,
            min(
                v
                for v in (h0, int(data["road"][i, j]), int(data["foot"][i, j]))
                if v > 0
            )
            - 5,
        )
        for y in range(
            low, max(int(data["road"][i, j]), int(data["foot"][i, j]), h0) + 2
        ):
            s = b.get(x, y, z)
            if pavement(s) or s.endswith(("white_concrete", "gray_concrete")):
                put(b, x, y, z, DIRT if y <= h0 else AIR)
        if soil(b.get(x, h0, z)) and b.get(x, h0 + 1, z) in AIRS:
            put(b, x, h0, z, GRASS)
    for i, j in np.argwhere(walk):
        x, z = int(xx[i, j]), int(zz[i, j])
        drive = bool(driving[i, j])
        solid = "trafficcraft:asphalt" if drive else "trafficcraft:concrete"
        height = int(grade[i, j]) + (0 if drive else 1)
        top, part = divmod(height, 8)
        cap = top if part else top - 1
        oldtop = int(terrain[i, j])
        for y in range(min(oldtop - 1, cap - 2), cap):
            s = b.get(x, y, z)
            if (
                soil(s)
                or s in AIRS
                or pavement(s)
                or vegetation(s)
                or s.startswith("minecraft:water[")
            ):
                put(b, x, y, z, STONE if y < cap - 1 else solid)
        mark = paint.get((i, j))
        if mark:
            ident, face, color = mark
            st = (
                f"trafficcraft:asphalt_slope_pattern_{ident}[facing={face},layers={part},waterlogged=false]"
                if part
                else f"trafficcraft:asphalt_pattern_{ident}[facing={face}]"
            )
            b.tags[x, cap, z] = nbtlib.Compound(
                {
                    "id": nbtlib.String(ENTITY),
                    "color": nbtlib.Int(color),
                    "keepPacked": nbtlib.Byte(0),
                }
            )
        else:
            st = f"{solid}_slope[layers={part},waterlogged=false]" if part else solid
        put(b, x, cap, z, st)
        # Always write marked blocks so changed paint has a corresponding BE update.
        if mark:
            b.put(x, cap, z, st)
        for y in range(
            cap + 1, max(cap + 5, int(data["highest"][i, j]) + 1, oldtop + 1)
        ):
            s = b.get(x, y, z)
            if (
                soil(s)
                or pavement(s)
                or vegetation(s)
                or s.startswith("minecraft:water[")
                or s.endswith(("gray_concrete", "white_concrete"))
            ):
                put(b, x, y, z, AIR)
    # Blend cuttings and fills into the slope. On the water side the bank is the
    # lower limit of the footing; cars and the old gully no longer share the same opening.
    for i, j in np.argwhere((dist > 4.45) & (dist < 12)):
        x, z = int(xx[i, j]), int(zz[i, j])
        ground = int(terrain[i, j])
        if (
            data["road"][i, j]
            and not retire[i, j]
            or data["foot"][i, j]
            and not existing[i, j]
        ):
            continue
        shoulder = int(np.floor(h[i, j] - 0.75))
        padding = math.floor((dist[i, j] - 4) * 0.7)
        target = int(np.clip(ground, shoulder - padding, shoulder + padding))
        if (
            target == ground
            or data["wet"][i, j]
            and data["wet"][i, j] >= ground
            and ground < 99
        ):
            continue
        for y in range(min(target, ground) - 1, max(target, ground) + 2):
            s = b.get(x, y, z)
            if not (soil(s) or vegetation(s) or s in AIRS):
                continue
            put(b, x, y, z, GRASS if y == target else DIRT if y < target else AIR)
    return dict(columns=int(walk.sum()), reclaimed=int(retired.sum()), paint=len(paint))


def access_walk(b):
    # Replace the stopped stair with one graded footway from the roadside to the
    # original inspection quay. This section reaches the road at walking height.
    for z in range(946, 973):
        for x in range(-453, -450):
            for y in range(82, 101):
                if b.get(x, y, z) in (
                    "minecraft:smooth_stone",
                    "minecraft:stone_bricks",
                ):
                    put(
                        b,
                        x,
                        y,
                        z,
                        DIRT if y < 92 and b.get(x, y + 1, z) not in AIRS else AIR,
                    )
    for z in range(954, 1005):
        walking = min(101, round((94.875 + (z - 956) * 0.365) * 2) / 2)
        h = math.ceil(walking) - 1
        half = walking % 1 == 0.5
        for x in range(-453, -450):
            if any(
                b.get(x, y, z).startswith("trafficcraft:") for y in range(h - 2, h + 2)
            ):
                continue
            for y in range(h - 1, 76, -1) if z <= 974 else ():
                s = b.get(x, y, z)
                if soil(s) or s.startswith("trafficcraft:"):
                    break
                put(b, x, y, z, "minecraft:stone_bricks")
            put(
                b,
                x,
                h,
                z,
                "minecraft:smooth_stone_slab[type=bottom,waterlogged=false]"
                if half
                else "minecraft:smooth_stone",
            )
            for y in range(h + 1, h + 4):
                s = b.get(x, y, z)
                if soil(s) or vegetation(s) or pavement(s):
                    put(b, x, y, z, AIR)


def repair(b):
    result = {"old_panel_blocks_removed": remove_panels(b)}
    lake = capture(b.reader, LAKE_BOUNDS)
    hill = capture(b.reader, ROAD_BOUNDS)
    ground, wet, scope = bank(b, lake)
    x0, z0, x1, z1 = LAKE_BOUNDS
    zz, xx = np.mgrid[z0 : z1 + 1, x0 : x1 + 1]
    retire = (xx >= -526) & (xx <= -427) & (zz >= 907) & (zz <= 1005)
    result["lake_roads"] = draw_roads(
        b, lake, LAKE_BOUNDS, LAKE_ROADS, ground, retire, [(-439, 923, 87.4)]
    )
    x0, z0, x1, z1 = ROAD_BOUNDS
    zz, xx = np.mgrid[z0 : z1 + 1, x0 : x1 + 1]
    retire = (xx >= -226) & (xx <= -110) & (zz >= 982) & (zz <= 1076)
    result["hill_roads"] = draw_roads(
        b,
        hill,
        ROAD_BOUNDS,
        HILL_ROADS,
        hill["soil"],
        retire,
        [(-201, 1053, 103.2), (-146, 1015, 106), (-112, 1028, 109)],
    )
    access_walk(b)
    result["lake_level"] = 99
    b.reports["northern_ashi"] = result
