"""Restore the retired runway, retire the school hillside spur and grade all nine house approaches."""

import argparse, json, math, random
from pathlib import Path
from itertools import product
import numpy as np
from scipy import ndimage as nd
from surface_renewal_io import open_overlay, read_survey, save_overlay
from dogma_recommission import AIRS
from valley_road_renewal import g, natural, plain, veg


def runway(b):
    x0, z0, X, Z = 280, -610, 433, -180
    mask = np.zeros((Z - z0 + 1, X - x0 + 1), bool)
    kinds = {
        "gray_concrete",
        "white_concrete",
        "smooth_stone",
        "polished_deepslate",
        "iron_trapdoor",
    }
    for x, z in product(range(x0, X + 1), range(z0, Z + 1)):
        mask[z - z0, x - x0] = b.get(x, 80, z).split("[")[0][10:] in kinds
    l, n = nd.label(mask)
    sel = l == l[-399 - z0, 382 - x0]
    zs, xs = np.where(sel)
    if len(xs) != 19512:
        raise ValueError(("Unexpected former runway footprint", len(xs)))
    return xs + x0, zs + z0


def airport(b, survey):
    X, Z, a = read_survey(survey, "air")
    h = a[:2].max(0).astype(float)
    xs, zs = runway(b)
    mask = np.zeros_like(h, dtype=bool)
    mask[zs - Z, xs - X] = True
    # Surviving turf above y80, including wooded banks over the runway, supplies unchanged elevation anchors.
    missing = mask & (h <= 80)
    dist = nd.distance_transform_edt(missing)
    nearest = nd.distance_transform_edt(
        missing, return_distances=False, return_indices=True
    )
    dem = h[tuple(nearest)]
    kernel = np.array([[0, 0.25, 0], [0.25, 0, 0.25], [0, 0.25, 0]])
    sl = np.s_[min(zs) - Z - 3 : max(zs) - Z + 4, min(xs) - X - 3 : max(xs) - X + 4]
    u = dem[sl].copy()
    sub = missing[sl]
    for i in range(450):
        mean = nd.convolve(u, kernel, mode="nearest")
        u[sub] = mean[sub]
    dem[sl] = u
    grass = {}
    rng = random.Random(6756)
    fixtures = {"minecraft:iron_bars", "projectseele:nerv_strip_light"}
    for xx, zz in zip(xs, zs):
        x, z = int(xx), int(zz)
        iz, ix = z - Z, x - X
        terrain = int(h[iz, ix])
        y = terrain
        for yy in range(81, 89):
            if plain(b.get(x, yy, z)) in fixtures:
                b.put(x, yy, z, "air")
        if missing[iz, ix]:
            weight = min(1.0, dist[iz, ix] / 13)
            v = (
                math.sin(x * 0.104 + z * 0.024) + 0.7 * math.cos(z * 0.106 + x * 0.037)
            ) * 0.87 - 2.5
            y = round(dem[iz, ix] + weight * v)
            for yy in range(min(80, y - 2), max(80, y) + 1):
                b.put(
                    x,
                    yy,
                    z,
                    (
                        "air"
                        if yy > y
                        else g if yy == y else "dirt" if yy >= y - 3 else "stone"
                    ),
                )
            grass[x, z] = y
        else:
            b.put(x, 80, z, "dirt" if terrain - 80 <= 3 else "stone")
    trees = []
    for i in range(286, 400, 8):
        for j in range(-512, -277, 8):
            x = i + rng.randrange(1, 7)
            z = j + rng.randrange(1, 7)
            if (x, z) not in grass or any(
                (x + dx, z + dz) not in grass
                for dx, dz in ((3, 0), (-3, 0), (0, 3), (0, -3))
            ):
                continue
            if rng.random() < (0.30 if math.sin(x * 0.07 + z * 0.03) > 0.7 else 0.12):
                continue
            if any((x - X) ** 2 + (z - Z) ** 2 < 31 for X, Z in trees):
                continue
            y = grass[x, z]
            if any(
                b.get(x + dx, y + dy, z + dz) not in AIRS
                and not veg(b.get(x + dx, y + dy, z + dz))
                for dx, dz, dy in [
                    (0, 0, 3),
                    (-2, 0, 4),
                    (2, 0, 4),
                    (0, 2, 4),
                    (0, -2, 4),
                ]
            ):
                continue
            kind = rng.choices(["spruce", "oak", "birch"], [7, 2, 1])[0]
            height = rng.randint(7, 12) if kind == "spruce" else rng.randint(5, 7)
            for dy in range(1, height + 1):
                b.put(x, y + dy, z, kind + "_log[axis=y]")
            for dy in range(3, height + 2):
                radius = (
                    (
                        0
                        if dy == height + 1
                        else (
                            1
                            if dy >= height - 1
                            else 2 if dy % 3 != 1 or dy > height - 4 else 3
                        )
                    )
                    if kind == "spruce"
                    else (0 if dy == height + 1 else 1 if dy >= height else 2)
                )
                for dx, dz in product(range(-radius, radius + 1), repeat=2):
                    if (
                        (dx, dz) == (0, 0)
                        and dy <= height
                        or radius
                        and abs(dx) == radius
                        and abs(dz) == radius
                        and rng.random() < 0.72
                    ):
                        continue
                    if b.get(x + dx, y + dy, z + dz) in AIRS:
                        b.put(
                            x + dx,
                            y + dy,
                            z + dz,
                            f"{kind}_leaves[distance=1,persistent=true,waterlogged=false]",
                        )
            trees.append((x, z))
    for (x, z), y in grass.items():
        if b.get(x, y + 1, z) in AIRS and rng.random() < 0.115:
            b.put(
                x,
                y + 1,
                z,
                rng.choice(["grass", "grass", "fern", "fern", "grass", "dandelion"]),
            )
    print(
        "old airfield",
        len(xs),
        "unburied restored",
        len(grass),
        "trees",
        len(trees),
        flush=True,
    )
    return trees, grass


def deadroad(b, survey):
    X, Z, a = read_survey(survey, "schoolroad")
    base = a[:2].max(0)
    road = a[4]
    curb = a[5]
    h = a.max(0)
    q = np.maximum(road, curb)
    z, x = np.indices(q.shape)
    old = (x + X >= -35) & (x + X <= 7) & (z + Z >= -708) & (z + Z <= -540) & (q > 50)
    comps, n = nd.label(old)
    sel = comps == comps[-614 - Z, -1 - X]
    bounds = nd.distance_transform_edt(sel, return_distances=False, return_indices=True)
    dem = base[tuple(bounds)].astype(float)
    weight = nd.distance_transform_edt(sel)
    sub = np.s_[-712 - Z : -533 - Z, -39 - X : 12 - X]
    close = sel[sub]
    d = dem[sub].copy()
    for _ in range(160):
        f = nd.convolve(
            d, np.array([[0, 0.25, 0], [0.25, 0, 0.25], [0, 0.25, 0]]), mode="nearest"
        )
        d[close] = f[close]
    dem[sub] = d
    removed = []
    for iz, ix in zip(*np.where(sel)):
        x, z = int(ix + X), int(iz + Z)
        y = int(q[iz, ix])
        end = (
            round(dem[iz, ix])
            if z <= -545
            else round((int(base[iz, ix]) * (z + 545) + dem[iz, ix] * (-540 - z)) / 5)
        )
        for yy in range(min(end - 3, y - 3), max(y, int(h[iz, ix]), end) + 1):
            s = b.get(x, yy, z)
            if not (
                natural(s)
                or s.startswith("trafficcraft:")
                or s.startswith("projectseele:road_mark")
            ):
                raise ValueError(("old road structure", x, yy, z, s))
            b.put(
                x,
                yy,
                z,
                (
                    "air"
                    if yy > end
                    else g if yy == end else "dirt" if yy >= end - 3 else "stone"
                ),
            )
        removed.append((x, end, z))
    # Round off the corner where the surviving road turns east into the village.
    for z in (-540, -539):
        for x in range(-5, 3):
            yy = int(q[z - Z, x - X])
            if yy < 50 or x > -3 and z == -539:
                continue
            if yy < 85:
                b.put(x, yy, z, "smooth_stone")
    print("cul-de-sac removed", len(removed), flush=True)
    return removed


def points(nodes):
    result = []
    for p, q in zip(nodes, nodes[1:]):
        n = max(1, math.ceil(math.hypot(p[0] - q[0], p[2] - q[2]) * 2))
        for i in range(n):
            t = i / n
            cell = tuple(round(u + (v - u) * t) for u, v in zip(p, q))
            if not result or cell != result[-1]:
                result.append(cell)
    if result[-1] != nodes[-1]:
        result.append(nodes[-1])
    return result


def village(b, survey):
    X, Z, a = read_survey(survey, "air")
    native_top = a[:2].max(0)
    treetop = a[3]
    pave = np.maximum(a[4], a[5])
    trace = []
    cleared_trunks = set()
    heights = {}

    def build(nodes, width, kind):
        line = points(nodes)
        cells = {}
        for cx, sy, cz in line:
            for dx, dz in product(
                range(-math.ceil(width), math.ceil(width) + 1), repeat=2
            ):
                d = math.hypot(dx, dz)
                if d > width:
                    continue
                p = cx + dx, cz + dz
                if p not in cells or d < cells[p][0]:
                    cells[p] = d, sy
        for (x, z), (d, sy) in cells.items():
            iz, ix = z - Z, x - X
            v = int(pave[iz, ix])
            onroad = v > 30
            if onroad:
                continue
            if heights.get((x, z), (None, None))[0] == "street" and kind == "foot":
                continue
            if any("door[" in b.get(x, yy, z) for yy in range(sy - 2, sy + 4)):
                continue
            # Preserve all buildings, authored porch steps and their signs. The new approaches start outside the thresholds.
            if any(
                not (
                    natural(s)
                    or s.startswith("trafficcraft:")
                    or plain(s)
                    in (
                        "minecraft:smooth_stone",
                        "minecraft:smooth_stone_slab",
                        "minecraft:stone_bricks",
                        "minecraft:quartz_stairs",
                        "minecraft:gray_concrete",
                        "minecraft:polished_andesite",
                    )
                )
                for s in (b.get(x, yy, z) for yy in range(sy, sy + 4))
            ):
                continue
            surface = int(native_top[iz, ix])
            high = max(surface, sy + 2, int(treetop[iz, ix]))
            # Clear natural shoulders, the old path and foliage immediately above each new lane. Remove the canopy of trees rooted on the lane by trunk, not by a rectangular clearing.
            for yy in range(sy + 1, high + 1):
                p = (x, yy, z)
                st = b.get(*p)
                if st in AIRS:
                    continue
                if plain(st).endswith("_log"):
                    cleared_trunks.add((x, z))
                if natural(st) or plain(st) in (
                    "minecraft:smooth_stone",
                    "minecraft:smooth_stone_slab",
                    "minecraft:stone_bricks",
                    "minecraft:polished_andesite",
                ):
                    b.put(*p, "air")
            if sy > surface:
                for yy in range(max(surface + 1, sy - 14), sy):
                    st = b.get(x, yy, z)
                    if natural(st):
                        b.put(x, yy, z, "dirt" if yy > sy - 3 else "stone")
            which = (
                "trafficcraft:asphalt"
                if kind == "street" and d < 2.1
                else (
                    "smooth_stone"
                    if kind == "street"
                    else "polished_andesite" if d >= 1.1 else "smooth_stone"
                )
            )
            b.put(x, sy, z, which)
            heights[x, z] = (kind, sy)
        return line

    # Connect both ends to the local lane. Its inside edge serves the house whose former front walk ended on the hillside.
    loop = [
        (140, 131, -282),
        (134, 131, -281),
        (128, 132, -283),
        (123, 132, -287),
        (122, 132, -293),
        (125, 132, -298),
        (130, 132, -300),
        (138, 131, -300),
        (146, 130, -301),
        (153, 128, -303),
        (161, 127, -305),
        (169, 126, -306),
    ]
    build(loop, 3.35, "street")
    # Threshold, path turning nodes and actual adjacent carriageway. Each approach has its own measured grade.
    routes = [
        [(106, 126, -369), (111, 126, -369), (116, 125, -372), (119, 125, -372)],
        [(128, 132, -307), (128, 132, -302), (128, 132, -298)],
        [(139, 132, -251), (139, 132, -259), (138, 131, -269), (138, 131, -271)],
        [(173, 120, -403), (173, 120, -410), (170, 119, -414), (167, 117, -421)],
        [(189, 126, -344), (186, 126, -344), (182, 124, -344), (177, 122, -344)],
        [(184, 126, -291), (184, 126, -298), (181, 124, -302), (180, 124, -304)],
        [
            (202, 126, -373),
            (202, 126, -367),
            (198, 126, -365),
            (180, 124, -365),
            (178, 123, -363),
            (178, 123, -352),
            (177, 123, -350),
        ],
        [
            (220, 125, -299),
            (220, 125, -302),
            (207, 124, -302),
            (205, 124, -305),
            (205, 123, -314),
        ],
        [(224, 125, -316), (216, 125, -316), (210, 124, -316), (205, 123, -318)],
    ]
    for path in routes:
        trace.append(build(path, 1.5, "foot"))
    for x, z in cleared_trunks:
        sy = heights.get((x, z), ("", int(native_top[z - Z, x - X])))[1]
        for xx, zz in product(range(x - 3, x + 4), range(z - 3, z + 4)):
            if math.hypot(x - xx, z - zz) > 3.3:
                continue
            h = int(treetop[zz - Z, xx - X])
            for yy in range(sy + 3, min(sy + 17, h) + 1):
                if plain(b.get(xx, yy, zz)).endswith("_leaves"):
                    b.put(xx, yy, zz, "air")
    print(
        "village",
        len(heights),
        "graded cells; removed trees",
        len(cleared_trunks),
        flush=True,
    )
    return trace, heights


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("world", "survey", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    world, survey, out = args.world, args.survey, args.output
    b = open_overlay(world, out)
    trees, grass = airport(b, survey)
    retired = deadroad(b, survey)
    routes, grade = village(b, survey)
    (out / "proof-input.json").write_text(
        json.dumps({"trees": trees, "roads": retired, "routes": routes}),
        encoding="utf8",
    )
    count, chunks = save_overlay(b, world, out)
    print(count, "blocks in", chunks, "chunks")
