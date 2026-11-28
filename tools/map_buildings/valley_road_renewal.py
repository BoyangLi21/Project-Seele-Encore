"""Rebuild surveyed forest road junctions, restore unused roads and write an offline Anvil overlay.

Usage: python valley_road_renewal.py WORLD SURVEY_DIRECTORY OUTPUT_DIRECTORY
The survey directory contains the nine-channel big-endian SurfaceRoadSurvey rasters.
The author never modifies the input world. blocks.tsv.gz, tags.json, data.json and the
staged Anvil regions can be merged by coordinate with other surface or facility edits.
"""

import argparse
import json
import math
import sys
from collections import Counter
from itertools import product
from math import ceil, floor
from pathlib import Path
import nbtlib
import numpy as np
from scipy import ndimage as nd
from scipy.spatial import cKDTree

r = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(r / "tools"))
from dogma_recommission import AIRS
from functools import lru_cache
import ast

reg = Path("dimensions/projectseele/geofront/region")


from surface_renewal_io import open_overlay, read_survey, save_overlay


def data(name):
    return read_survey(survey, name)


M = "minecraft:"
g = "grass_block[snowy=false]"
native = {
    "stone",
    "andesite",
    "diorite",
    "granite",
    "gravel",
    "dirt",
    "grass_block",
    "podzol",
    "coarse_dirt",
    "moss_block",
    "grass",
    "fern",
    "tall_grass",
    "large_fern",
    "short_grass",
    "snow",
    "sand",
    "clay",
    "rooted_dirt",
    "dandelion",
    "poppy",
    "brown_mushroom",
    "red_mushroom",
    "sweet_berry_bush",
}


def plain(s):
    return s.split("[")[0]


def veg(s):
    n = plain(s)
    return n.startswith(M) and (
        n.endswith(("_leaves", "_log", "_sapling"))
        or n[10:]
        in (
            "grass",
            "fern",
            "tall_grass",
            "large_fern",
            "short_grass",
            "dandelion",
            "poppy",
            "brown_mushroom",
            "sweet_berry_bush",
        )
    )


def natural(s):
    return s in AIRS or veg(s) or (s.startswith(M) and plain(s)[10:] in native)


zones = {
    "sw": ("valley", (1780, 1199, 2160, 1415)),
    "north": ("valley", (2260, 932, 2606, 1228)),
    "house": ("house", (2939, 1388, 3098, 1515)),
    "south": ("south", (70, 1599, 672, 2100)),
}


def thin(mask):
    a = np.pad(mask, 1)
    d = a[1:-1, 1:-1]
    while True:
        n = 0
        for mode in (0, 1):
            p = [
                a[:-2, 1:-1],
                a[:-2, 2:],
                a[1:-1, 2:],
                a[2:, 2:],
                a[2:, 1:-1],
                a[2:, :-2],
                a[1:-1, :-2],
                a[:-2, :-2],
            ]
            total = sum(x.astype("uint8") for x in p)
            transitions = sum(
                ((~q) & s).astype("uint8") for q, s in zip(p, p[1:] + p[:1])
            )
            cut = d & (total >= 2) & (total <= 6) & (transitions == 1)
            if mode:
                cut &= ~(p[0] & p[2] & p[6]) & ~(p[0] & p[4] & p[6])
            else:
                cut &= ~(p[0] & p[2] & p[4]) & ~(p[2] & p[4] & p[6])
            n += int(cut.sum())
            d[cut] = False
        if not n:
            return d.copy()


def create(key):
    name, (x0, z0, x1, z1) = zones[key]
    x, z, a = data(name)
    s = np.s_[z0 - z : z1 - z + 1, x0 - x : x1 - x + 1]
    asphalt = a[4][s] > -300
    core = nd.binary_closing(asphalt, iterations=1)
    skel = thin(core)
    imask = np.zeros_like(core)
    pnts = set(zip(*np.where(skel)))

    def neigh(p):
        i, j = p
        for di, dj in [
            (i, j + 1),
            (i + 1, j),
            (i, j - 1),
            (i - 1, j),
            (i + 1, j + 1),
            (i + 1, j - 1),
            (i - 1, j - 1),
            (i - 1, j + 1),
        ]:
            if (di, dj) in pnts and not (
                di != i and dj != j and ((di, j) in pnts or (i, dj) in pnts)
            ):
                yield int(di), int(dj)

    adj = {p: list(neigh(p)) for p in pnts}
    for p, e in adj.items():
        if len(e) != 2:
            imask[p] = True
    lab, n = nd.label(imask, structure=np.ones((3, 3)))
    seen = set()
    paths = []
    for u in sorted(pnts):
        if not lab[u]:
            continue
        for v in adj[u]:
            if lab[v] and lab[u] == lab[v] or (u, v) in seen:
                continue
            route = [u, v]
            seen.add((u, v))
            seen.add((v, u))
            a0, b = u, v
            while not lab[b]:
                c = next(c for c in adj[b] if c != a0)
                route.append(c)
                seen.add((b, c))
                seen.add((c, b))
                a0, b = b, c
            if len(route) < 3:
                continue
            paths.append([(int(j + x0), int(i + z0)) for i, j in route])
    expected_segments = {"sw": 31, "north": 42, "south": 148, "house": 1}
    if len(paths) != expected_segments[key]:
        raise ValueError(
            f"{key} contains {len(paths)} road segments, expected {expected_segments[key]}"
        )
    dst = W / (key + ".json")
    dst.write_text(json.dumps(paths))


remove = {
    "sw": set(range(3, 30)),
    "north": {
        1,
        5,
        6,
        8,
        9,
        10,
        11,
        13,
        14,
        15,
        16,
        17,
        18,
        21,
        22,
        25,
        26,
        27,
        28,
        29,
        30,
        31,
        32,
        35,
        36,
        37,
        38,
        39,
    },
    "south": {
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        14,
        19,
        23,
        25,
        30,
        32,
        35,
        36,
        37,
        40,
        56,
        57,
        59,
        61,
        68,
        70,
        71,
        72,
        86,
        92,
        93,
        97,
        98,
        121,
        125,
        128,
        139,
    },
    "house": set(),
}


def road(s):
    return s.startswith(
        (
            "trafficcraft:asphalt",
            "trafficcraft:concrete",
            "projectseele:road_marking",
            "projectseele:road_asphalt",
            "projectseele:road_sidewalk",
        )
    )


def fixture(s):
    return plain(s) == "minecraft:lantern" or any(
        i in s
        for i in (
            "street_light",
            "streetlight",
            "road_lamp",
            "utility_pole",
            "power_line",
            "street_lamp",
        )
    )


def cls(name):
    return name.startswith(M) and plain(name)[10:] in (
        "smooth_stone",
        "cobblestone",
        "stone_bricks",
        "polished_andesite",
        "andesite_wall",
        "iron_bars",
        "stone_brick_wall",
    )


def cutpoint(k, i, p):
    x, z = p
    if i in remove[k]:
        return True
    if k == "north":
        if i == 0 and z > 1026 or i == 2 and z <= 1059:
            return True
    if k == "house" and z >= 1469 and x <= 3039:
        return True
    if k == "south" and i == 33 and x < 410:
        return True
    return False


def remove_old(b, k):
    name, (x0, z0, x1, z1) = zones[k]
    x, z, all_ = data(name)
    sub = np.s_[z0 - z : z1 - z + 1, x0 - x : x1 - x + 1]
    a = all_[:, sub[0], sub[1]]
    paths = json.loads((W / (k + ".json")).read_bytes())
    bad = np.zeros(a.shape[1:], bool)
    good = bad.copy()
    for i, path in enumerate(paths):
        for xx, zz in path:
            (bad if cutpoint(k, i, (xx, zz)) else good)[zz - z0, xx - x0] = True
    bd = nd.distance_transform_edt(~bad)
    gd = nd.distance_transform_edt(~good)
    roadY = np.maximum(a[4], a[5])
    parcel = (roadY != -2048) & (bd <= 10) & (bd < gd)
    # Subtract a two-cell buffer around occupied buildings and active railway engineering.
    rail = a[8]
    railclear = (rail == -2048) | (abs(rail - np.maximum(roadY, -500)) > 7)
    parcel &= railclear
    # Fit the contour to real neighbouring ground on each side, excluding all road fill and water-covered pixels from dry-land interpolation.
    origin = a[:2].max(0).astype(float)
    wet = (a[2] > origin) & (a[2] > -2048)
    badground = (roadY != -2048) | (origin < -250)
    near = nd.distance_transform_edt(
        badground, return_distances=False, return_indices=True
    )
    dem = np.where(badground, origin[tuple(near)], origin)
    for _ in range(38):
        v = nd.convolve(
            dem, np.array([[0, 0.25, 0], [0.25, 0, 0.25], [0, 0.25, 0]]), mode="nearest"
        )
        dem[parcel] = v[parcel]
    watercopy = a[2][tuple(near)]
    flood = wet[tuple(near)] & (watercopy > dem - 0.8)
    cells = []
    counts = Counter()
    blocked = Counter()
    for iz, ix in zip(*np.where(parcel)):
        xx, zz = int(ix + x0), int(iz + z0)
        yy = int(roadY[iz, ix])
        h = round(dem[iz, ix])
        if h < -150 or h > yy + 13 or h < yy - 25:
            h = min(yy - 1, max(yy - 4, int(origin[iz, ix])))
        water = int(watercopy[iz, ix]) if flood[iz, ix] else -2048
        if water != -2048 and h >= water:
            h = water - 1
        if water > yy + 1:
            water = -2048
        candidates = list(range(min(h - 2, yy - 2), max(yy + 2, h + 1, water + 1) + 1))
        obstruct = False
        for y in candidates:
            s = b.get(xx, y, zz)
            if s is None or (
                not (
                    natural(s)
                    or road(s)
                    or fixture(s)
                    or cls(s)
                    or s.startswith(("minecraft:water", "minecraft:light["))
                )
            ):
                blocked[s] += 1
                obstruct = True
                break
        if obstruct:
            continue
        for y in candidates:
            s = b.get(xx, y, zz)
            if y < h - 2 and not road(s):
                continue
            new = (
                "water[level=0]"
                if y > h and y <= water
                else (
                    "air"
                    if y > h
                    else (
                        "gravel"
                        if y == h and water != -2048
                        else (
                            "grass_block[snowy=false]"
                            if y == h
                            else "dirt" if y >= h - 3 else "stone"
                        )
                    )
                )
            )
            b.put(xx, y, zz, new)
        for y in range(yy + 2, yy + 16):
            s = b.get(xx, y, zz)
            if fixture(s) or plain(s) in (
                "minecraft:iron_bars",
                "minecraft:sea_lantern",
                "minecraft:end_rod",
            ):
                b.put(xx, y, zz, "air")
        if (
            water == -2048
            and (xx * 1061 + zz * 1597) % 13 == 0
            and b.get(xx, h + 1, zz) in AIRS
        ):
            b.put(xx, h + 1, zz, "grass")
        cells.append((xx, h, zz))
    # Streetlights may sit just outside the road kerb.
    for iz, ix in zip(*np.where((bd <= 9) & (bd + 1 < gd) & ~parcel)):
        xx, zz = int(ix + x0), int(iz + z0)
        sy = int(origin[iz, ix])
        yy = sy
        if sy < -160:
            continue
        for y in range(yy + 1, yy + 17):
            s = b.get(xx, y, zz)
            if fixture(s):
                b.put(xx, y, zz, "air")
    print(
        k,
        "retired surface columns",
        len(cells),
        "guarded",
        dict(blocked.most_common(8)),
        flush=True,
    )
    return cells


def replanted(b, retired):
    import random

    total = 0
    for key, xzs in retired.items():
        if key == "house":
            continue
        name, (xmin, zmin, xmax, zmax) = zones[key]
        X, Z, a = data(name)
        rng = random.Random({"sw": 719, "north": 868, "south": 543}[key])
        tree = cKDTree([(x, z) for x, y, z in xzs])
        roads = json.loads((W / (key + ".json")).read_bytes())
        newroads = {
            (x, z)
            for (x, y, z), v in b.changes.items()
            if v.startswith("trafficcraft:asphalt")
        }
        retained = cKDTree(
            [
                (x, z)
                for i, path in enumerate(roads)
                for x, z in path
                if not cutpoint(key, i, (x, z))
            ]
            + list(newroads)
        )
        doors = (
            json.loads((W / (key + "-doors.json")).read_bytes())
            if (W / (key + "-doors.json")).exists()
            else []
        )
        doors = cKDTree([(x, z) for x, y, z, _ in doors]) if doors else None
        tops = {(x, z): y for x, y, z in xzs}
        planted = []
        for u, v in product(range(xmin + 4, xmax - 4, 8), range(zmin + 4, zmax - 4, 8)):
            x = u + rng.randrange(7)
            z = v + rng.randrange(7)
            if not xmin + 3 <= x <= xmax - 3 or not zmin + 3 <= z <= zmax - 3:
                continue
            near = tree.query((x, z))[0]
            if (
                near > 6
                or retained.query((x, z))[0] < 11
                or (doors is not None and doors.query((x, z))[0] < 19)
            ):
                continue
            ix, iz = x - X, z - Z
            # This strip formerly carried a road. Seed only the sections abutting recorded forest.
            if (
                np.count_nonzero(a[3][iz - 16 : iz + 17, ix - 16 : ix + 17] > -2048)
                < 65
            ):
                continue
            if (
                np.any(a[8][iz - 5 : iz + 6, ix - 5 : ix + 6] > -2048)
                or rng.random() < 0.18
            ):
                continue
            h = tops.get((x, z), int(a[:2, iz, ix].max()))
            if not plain(b.get(x, h, z)).endswith(("grass_block", "podzol")):
                continue
            if any(
                not (
                    b.get(x + dx, h + yy, z + dz) in AIRS
                    or veg(b.get(x + dx, h + yy, z + dz))
                )
                for dx, dz, yy in (
                    (0, 0, 2),
                    (0, 0, 5),
                    (-2, 0, 3),
                    (2, 0, 3),
                    (0, -2, 3),
                    (0, 2, 3),
                )
            ):
                continue
            if any((xx - x) ** 2 + (zz - z) ** 2 < 29 for xx, zz in planted):
                continue
            kind = rng.choices(("oak", "spruce", "birch"), weights=(4, 5, 1))[0]
            height = rng.randint(6, 10) if kind == "spruce" else rng.randint(5, 7)
            for yy in range(1, height + 1):
                b.put(x, h + yy, z, kind + "_log[axis=y]")
            for yy in range(3, height + 2):
                radius = (
                    0
                    if yy == height + 1
                    else (
                        1
                        if yy >= height - 1
                        else (3 if kind == "spruce" and yy == 4 else 2)
                    )
                )
                for dx, dz in product(range(-radius, radius + 1), repeat=2):
                    if (
                        dx == dz == 0
                        and yy <= height
                        or radius
                        and abs(dx) == abs(dz) == radius
                        and rng.random() < 0.75
                    ):
                        continue
                    if b.get(x + dx, h + yy, z + dz) in AIRS:
                        b.put(
                            x + dx,
                            h + yy,
                            z + dz,
                            f"{kind}_leaves[distance=1,persistent=true,waterlogged=false]",
                        )
            planted.append((x, z))
        print(key, "restored trees", len(planted), flush=True)
        total += len(planted)
    return total


@lru_cache(maxsize=1)
def mark_patterns():
    # Read the canonical texture table without importing shapefile planning dependencies.
    tree = ast.parse((r / "tools/convert_roads_trafficcraft.py").read_text("utf8"))
    return next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "LINE_PIECES"
    )


def paint_pieces(nodes):
    # The installed resource pack supplies sixteen line textures. Match their documented edge crossings.
    def rotate(p, n):
        a, b = p
        for _ in range(n):
            a, b = 1 - b, a
        return np.array((a, b))

    variants = [
        (i, f, rotate(s, n), rotate(t, n))
        for i, (s, t) in mark_patterns().items()
        for n, f in enumerate(("north", "east", "south", "west"))
    ]
    lines = {}
    for (ox, _, oz), (tx, __, tz) in zip(nodes, nodes[1:]):
        x, z = ox + 0.503, oz + 0.493
        X, Z = tx + 0.503, tz + 0.493
        ts = {0.0, 1.0}
        for u, v in ((x, X), (z, Z)):
            if u != v:
                ts.update(
                    (n - u) / (v - u) for n in range(ceil(min(u, v)), ceil(max(u, v)))
                )
        ts = sorted(t for t in ts if 0 <= t <= 1)
        for u, v in zip(ts, ts[1:]):
            m = (u + v) / 2
            p = (floor(x + (X - x) * m), floor(z + (Z - z) * m))
            a = np.array((x + (X - x) * u - p[0], z + (Z - z) * u - p[1]))
            c = np.array((x + (X - x) * v - p[0], z + (Z - z) * v - p[1]))
            if p not in lines:
                lines[p] = [a, c]
            else:
                lines[p][1] = c
    return {
        p: min(
            variants,
            key=lambda k: min(
                np.abs(k[2] - a).sum() + np.abs(k[3] - c).sum(),
                np.abs(k[3] - a).sum() + np.abs(k[2] - c).sum(),
            ),
        )[:2]
        for p, (a, c) in lines.items()
    }


def runline(b, id, nodes, width, margin, color=None, dashed=False, bridge=False):
    result = {}
    path = []
    s = 0
    for (x, h, z), (X, H, Z) in zip(nodes, nodes[1:]):
        length = math.hypot(X - x, Z - z)
        step = math.ceil(length * 3)
        for j in range(step + 1):
            t = j / step
            px = x + (X - x) * t
            pz = z + (Z - z) * t
            hh = h + (H - h) * t
            pos = (round(px), round(hh * 8), round(pz))
            if not path or pos != path[-1]:
                path.append(pos)
            for xx, zz in product(
                range(floor(px - width - margin), ceil(px + width + margin) + 1),
                range(floor(pz - width - margin), ceil(pz + width + margin) + 1),
            ):
                d = math.hypot(xx - px, zz - pz)
                if d > width + margin:
                    continue
                p = xx, zz
                if p not in result or d < result[p][0]:
                    result[p] = d, hh, s + t * length
        s += length
    marks = paint_pieces(nodes) if color is not None else {}
    for (x, z), (d, hh, progress) in result.items():
        # End caps taper into the original carriageway without disturbing the main bridge deck.
        if (
            id == "bridge"
            and z >= 1062
            and any("asphalt" in b.get(x, y, z) for y in range(-64, -59))
        ):
            continue
        kerb = d > width
        if kerb and id != "foot" and (progress < 0.001 or progress > s - 0.001):
            a, c = (nodes[0], nodes[1]) if progress < 0.001 else (nodes[-1], nodes[-2])
            dx, dz = c[0] - a[0], c[2] - a[2]
            # The curved stone shoulder continues on the sides of a tie-in, leaving the running lanes open.
            if (
                abs(dx * (z - a[2]) - dz * (x - a[0])) / math.hypot(dx, dz)
                < width - 0.1
            ):
                kerb = False
        if id == "foot":
            kerb = True
        eighth = round(8 * hh) + (int(kerb) if id != "foot" else 0)
        base = eighth // 8 - 1
        layers = eighth % 8
        obstacles = []
        core = width - d > 0
        for yy in range(base - 2, base + 7):
            v = b.get(x, yy, z)
            if not v or (
                not (
                    natural(v)
                    or road(v)
                    or cls(v)
                    or fixture(v)
                    or v.startswith(("minecraft:water", "minecraft:light["))
                )
            ):
                obstacles.append((yy, v))
        if obstacles:
            if (
                core
                and id != "foot"
                and any(base <= yy <= base + 3 for yy, v in obstacles)
            ):
                raise ValueError(("road building contact", id, x, z, base, obstacles))
            continue
        for yy in range(base + 1, base + 6):
            v = b.get(x, yy, z)
            if v not in AIRS:
                b.put(x, yy, z, "air")
        mat = "concrete" if kerb else "asphalt"
        b.put(x, base, z, "trafficcraft:" + mat)
        if layers:
            b.put(
                x,
                base + 1,
                z,
                f"trafficcraft:{mat}_slope[layers={layers},waterlogged=false]",
            )
        # Keep flowing channels beneath a bearing slab. Earth shoulders use the nearby native stone.
        for yy in range(base - 1, base - 6, -1):
            v = b.get(x, yy, z)
            if v.startswith("minecraft:water"):
                if bridge and yy == base - 1:
                    b.put(x, yy, z, "stone_bricks")
                break
            if v not in AIRS and not veg(v):
                if road(v):
                    b.put(x, yy, z, "stone")
                break
            if bridge:
                b.put(x, yy, z, "stone_bricks")
                break
            b.put(x, yy, z, "dirt" if yy == base - 1 else "stone")
        if (
            (x, z) in marks
            and not kerb
            and 2 <= progress <= s - 2
            and (not dashed or progress % 8 < 3)
        ):
            pat, face = marks[x, z]
            y = base + int(layers > 0)
            v = (
                f"trafficcraft:asphalt_slope_pattern_{pat}[facing={face},layers={layers},waterlogged=false]"
                if layers
                else f"trafficcraft:asphalt_pattern_{pat}[facing={face}]"
            )
            b.put(x, y, z, v)
            b.tags[x, y, z] = nbtlib.Compound(
                {
                    "id": nbtlib.String("trafficcraft:colored_block_entity"),
                    "color": nbtlib.Int(color),
                }
            )
    print(id, "graded", len(result), "columns", flush=True)
    return path


def design(b):
    return [
        (
            "bridge",
            runline(
                b,
                "bridge",
                [
                    (2534, -66.50, 1025),
                    (2533, -66.25, 1030),
                    (2531, -65.75, 1035),
                    (2528, -65.0, 1041),
                    (2525, -64.125, 1047),
                    (2523, -63.125, 1053),
                    (2522, -61.875, 1058),
                    (2521, -60.625, 1064),
                ],
                2.55,
                1,
                4,
                bridge=True,
            ),
        ),
        (
            "through",
            runline(
                b,
                "through",
                [
                    (2348, -60.5, 1125),
                    (2355, -60.875, 1126),
                    (2361, -60.5, 1124),
                    (2368, -59.5, 1120),
                    (2376, -58.25, 1116),
                    (2382, -58.125, 1113),
                    (2389, -58.75, 1109),
                ],
                3.05,
                1.05,
                4,
                bridge=True,
            ),
        ),
        (
            "shore",
            runline(
                b,
                "shore",
                [
                    (207, 103.125, 1838),
                    (212, 103.0, 1839),
                    (216, 102.875, 1841),
                    (218, 102.875, 1846),
                    (219, 103.0, 1852),
                    (221, 103.125, 1857),
                    (223, 103.125, 1861),
                    (225, 103.25, 1866),
                ],
                2.0,
                0.95,
                None,
                bridge=True,
            ),
        ),
        (
            "drive",
            runline(
                b,
                "drive",
                [
                    (3041, -65.0, 1470),
                    (3037, -65.0, 1472),
                    (3033, -65.0, 1474),
                    (3029, -65.0, 1475),
                ],
                2.65,
                0.9,
            ),
        ),
        (
            "foot",
            runline(
                b,
                "foot",
                [
                    (3019, -65.0, 1469),
                    (3020, -65.0, 1471),
                    (3022, -65.0, 1473),
                    (3026, -65.0, 1475),
                ],
                1.05,
                0.45,
            ),
        ),
    ]


PROTECTED_DOORS = {
    "sw": [
        [2075, -50, 1261, "south"],
        [2076, -50, 1261, "south"],
        [2081, -53, 1222, "south"],
        [2082, -53, 1222, "south"],
        [2092, -37, 1306, "north"],
        [2093, -37, 1306, "north"],
        [2106, -55, 1217, "east"],
        [2106, -55, 1218, "east"],
        [2122, -39, 1299, "north"],
        [2123, -39, 1299, "north"],
    ],
    "north": [
        [2262, -59, 1135, "east"],
        [2262, -59, 1136, "east"],
        [2294, -58, 1098, "south"],
        [2295, -58, 1098, "south"],
        [2313, -58, 1103, "south"],
        [2314, -58, 1103, "south"],
        [2310, -52, 1220, "north"],
        [2311, -52, 1220, "north"],
        [2334, -61, 1112, "south"],
        [2335, -61, 1112, "south"],
        [2572, -66, 997, "north"],
        [2573, -66, 997, "north"],
    ],
    "house": [[3019, -65, 1468, "south"], [3020, -65, 1468, "south"]],
    "south": [
        [329, 104, 1928, "south"],
        [330, 104, 1928, "south"],
        [340, 123, 1861, "north"],
        [341, 123, 1861, "north"],
        [348, 104, 1934, "south"],
        [349, 104, 1934, "south"],
        [363, 123, 1871, "north"],
        [364, 123, 1871, "north"],
        [367, 105, 1937, "west"],
        [367, 105, 1938, "west"],
        [379, 124, 1846, "south"],
        [380, 124, 1846, "south"],
        [391, 124, 1884, "north"],
        [392, 124, 1884, "north"],
        [414, 130, 1834, "east"],
        [414, 130, 1835, "east"],
        [412, 122, 1893, "north"],
        [413, 122, 1893, "north"],
        [403, 105, 1955, "south"],
        [404, 105, 1955, "south"],
        [429, 132, 1765, "west"],
        [429, 132, 1766, "west"],
        [431, 132, 1791, "west"],
        [431, 132, 1792, "west"],
        [438, 105, 1946, "south"],
        [439, 105, 1946, "south"],
        [474, 130, 1785, "south"],
        [475, 130, 1785, "south"],
        [469, 111, 1891, "north"],
        [470, 111, 1891, "north"],
        [469, 106, 1928, "south"],
        [470, 106, 1928, "south"],
        [492, 135, 1751, "east"],
        [492, 135, 1752, "east"],
        [502, 140, 1733, "south"],
        [503, 140, 1733, "south"],
        [503, 114, 1862, "north"],
        [504, 114, 1862, "north"],
        [522, 136, 1729, "south"],
        [523, 136, 1729, "south"],
        [517, 115, 1854, "west"],
        [517, 115, 1855, "west"],
        [535, 106, 1900, "west"],
        [535, 106, 1901, "west"],
        [538, 101, 2030, "east"],
        [563, 135, 1735, "north"],
        [564, 135, 1735, "north"],
        [568, 120, 2090, "west"],
        [568, 120, 2091, "west"],
        [597, 117, 1999, "west"],
        [597, 117, 2000, "west"],
        [604, 116, 2046, "north"],
        [605, 116, 2046, "north"],
        [629, 141, 1724, "south"],
        [630, 141, 1724, "south"],
        [624, 120, 2004, "south"],
        [625, 120, 2004, "south"],
        [641, 120, 1978, "west"],
        [641, 120, 1979, "west"],
    ],
}
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("world", type=Path)
    parser.add_argument("survey", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    live = args.world.resolve()
    survey = args.survey.resolve()
    W = args.output.resolve()
    if live == W or live in W.parents:
        raise ValueError("Output must be outside the input world")
    W.mkdir(exist_ok=True, parents=True)
    for key in zones:
        create(key)
    for key, doors in PROTECTED_DOORS.items():
        (W / (key + "-doors.json")).write_text(json.dumps(doors), "utf8")

    b = open_overlay(live, W)
    retired = {k: remove_old(b, k) for k in zones}
    lines = design(b)
    plant_count = replanted(b, retired)
    count, chunk_count = save_overlay(b, live, W)
    (W / "proof-input.json").write_text(
        json.dumps(dict(retired=retired, lines=lines, trees=plant_count)), "utf8"
    )
    print(count, "blocks in", chunk_count, "chunks")
