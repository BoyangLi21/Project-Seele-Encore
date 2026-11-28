"""Verify native block deltas and traverse authored roads, station entries, track clearances and school steps."""

import argparse, gzip, json, math, re
from pathlib import Path
from collections import Counter, defaultdict, deque
from functools import lru_cache
import numpy as np
from surface_renewal_io import Surface, reg, read_survey
from school_hillside_renewal import runway
from dogma_recommission import AIRS
import valley_road_renewal as road_graph
from valley_road_renewal import plain


def park(old, stage):
    class Merged(Surface):
        def _region(self, rx, rz):
            if not (self.dir / f"r.{rx}.{rz}.mca").is_file():
                return old._region(rx, rz)
            return super()._region(rx, rz)

    return Merged(stage / reg)


def delta(old, new, out, protect_rail):
    changes = defaultdict(set)
    with gzip.open(out / "blocks.tsv.gz", "rt", encoding="utf8") as f:
        for line in f:
            x, y, z, before, after = line.rstrip().split("\t")
            p = tuple(map(int, (x, y, z)))
            if new.get(*p) != after or old.get(*p) != before:
                raise ValueError(("block mismatch", p))
            if protect_rail and ("rail" in before or before.startswith("mtr:")):
                raise ValueError(("modified rail", p))
            changes[p[0], p[2]].add(p[1])
    return changes


def hills(old, a, proof, rows):
    oldmaterials = {
        "gray_concrete",
        "white_concrete",
        "smooth_stone",
        "polished_deepslate",
        "iron_trapdoor",
    }
    for x, z in zip(*runway(old)):
        assert plain(a.get(x, 80, z))[10:] not in oldmaterials, (x, z)
    for x, z in map(tuple, proof["trees"]):
        assert any(plain(a.get(x, y, z)).endswith("_log") for y in range(72, 102)), (
            x,
            z,
        )
    for x, y, z in proof["roads"]:
        if z <= -541:
            assert "grass_block" in a.get(x, y, z)

    @lru_cache(None)
    def free(x, y, z):
        s = a.get(x, y, z)
        return s in AIRS or (
            s
            and s.startswith(
                (
                    "trafficcraft:concrete_slope",
                    "trafficcraft:asphalt_slope",
                    "minecraft:grass[",
                    "minecraft:fern",
                    "minecraft:light[",
                )
            )
        )

    @lru_cache(None)
    def walk(x, y, z):
        if not (80 <= x <= 255 and -428 <= z <= -233 and 110 <= y <= 137):
            return False
        s = a.get(x, y, z)
        return (
            s
            and (
                s.startswith("trafficcraft:")
                and not "slope" in s
                or plain(s)
                in (
                    "minecraft:smooth_stone",
                    "minecraft:smooth_stone_slab",
                    "minecraft:stone_bricks",
                    "minecraft:polished_andesite",
                    "minecraft:light_gray_concrete",
                    "minecraft:white_concrete",
                    "minecraft:quartz_block",
                    "minecraft:stone_brick_stairs",
                )
            )
            and free(x, y + 1, z)
            and free(x, y + 2, z)
        )

    def path(start):
        x, y, z = start
        seeds = [(x, h, z) for h in range(y - 1, y + 2) if walk(x, h, z)]
        q = deque((p, 0) for p in seeds)
        seen = set(seeds)
        while q:
            (x, y, z), n = q.popleft()
            s = old.get(x, y, z)
            if (
                s
                and s.startswith("trafficcraft:asphalt")
                and "slope" not in s
                and n >= 4
            ):
                return n, (x, y, z)
            for dx, dz in ((-1, 0), (1, 0), (0, 1), (0, -1)):
                for dy in (0, 1, -1):
                    p = (x + dx, y + dy, z + dz)
                    if p not in seen and walk(*p):
                        seen.add(p)
                        q.append((p, n + 1))
        return None, sorted(seen)[:7]

    failed = []
    for route in proof["routes"]:
        s = route[0]
        n, p = path(s)
        print("walk", s, "->", n, p, flush=True)
        if n is None:
            failed.append(s)
    print(
        "reforest and road before/after verified",
        rows,
        "unique road areas",
        len(proof["roads"]),
        "trees",
        len(proof["trees"]),
        "missing entries",
        failed,
    )
    if failed:
        raise AssertionError(failed)


def valley(old, new, survey, W, proof, changes):
    def car(s):
        return s and s.startswith(
            (
                "trafficcraft:asphalt",
                "projectseele:road_mark",
                "projectseele:road_asphalt",
            )
        )

    def foot(s):
        return s and (
            car(s)
            or s.startswith(("trafficcraft:concrete", "projectseele:road_sidewalk"))
            or plain(s)
            in (
                "minecraft:smooth_stone",
                "minecraft:smooth_stone_slab",
                "minecraft:stone_bricks",
                "minecraft:polished_andesite",
            )
        )

    def height(y, s):
        if "slope" in s:
            return y + int(re.search(r"layers=(\d+)", s)[1]) / 8
        if "slab" in s:
            return y + 0.5
        return y + 1

    for x, y, z in json.loads((W / "tags.json").read_bytes()):
        assert new.block_entity(x, y, z) == "trafficcraft:colored_block_entity"

    def surface(k):
        name, (x0, z0, x1, z1) = road_graph.zones[k]
        X, Z, all_ = read_survey(survey, name)
        a = all_[:, z0 - Z : z1 - Z + 1, x0 - X : x1 - X + 1]
        rows = {}
        walk = {}
        q = np.maximum(a[4], a[5])
        col = {(int(x + x0), int(z + z0)) for z, x in zip(*np.where(q > -600))}
        if k == "house":
            col.update((x, z) for x in range(3017, 3032) for z in range(1468, 1478))
        col.update(p for p in changes if x0 <= p[0] <= x1 and z0 <= p[1] <= z1)
        for x, z in col:
            h = int(q[z - z0, x - x0])
            c = set(range(h - 1, h + 2)) if h > -600 else set()
            c.update(changes.get((x, z), ()))
            if k == "house" and 3017 <= x <= 3031 and 1468 <= z <= 1477:
                c.update(range(-68, -63))
            if not c:
                continue
            for yy in sorted(c, reverse=True):
                v = new.get(x, yy, z)
                if not v:
                    continue
                if foot(v):
                    if car(v):
                        rows[x, z] = height(yy, v)
                    walk[x, z] = height(yy, v)
                    break
        return rows, walk

    def reach(s, start, end, radius=5, grade=1.0):
        candidates = [
            (math.hypot(x - start[0], z - start[1]), (x, z))
            for x, z in s
            if abs(x - start[0]) <= radius and abs(z - start[1]) <= radius
        ]
        if not candidates:
            return False, ("start miss", start)
        q = deque([min(candidates)[1]])
        seen = set(q)
        while q:
            p = q.popleft()
            x, z = p
            if math.hypot(x - end[0], z - end[1]) <= radius:
                return True, (len(seen), p)
            for n in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                if n not in seen and n in s and abs(s[n] - s[p]) <= grade:
                    seen.add(n)
                    q.append(n)
        return False, ("disconnected", start, end, len(seen))

    failed = []
    paths = {
        "sw": [((2125, 1237), (2059, 1240))],
        "north": [
            ((2332, 1124), (2473, 1077)),
            ((2521, 1065), (2570, 979)),
            ((2473, 1077), (2572, 1074)),
        ],
        "south": [
            ((146, 1794), (472, 1940)),
            ((472, 1940), (545, 2000)),
            ((225, 1760), (405, 1870)),
        ],
        "house": [((3046, 1444), (3026, 1475))],
    }
    maps = {}
    for k in road_graph.zones:
        rows, walk = surface(k)
        maps[k] = (rows, walk)
        for start, end in paths[k]:
            ok, result = reach(rows, start, end)
            print("drive", k, start, end, ok, result, flush=True)
            if not ok:
                failed.append((k, start, end))
        for x, y, z, facing in json.loads((W / (k + "-doors.json")).read_bytes()):
            assert new.get(x, y, z) == old.get(x, y, z), (x, y, z)
        if k == "house":
            ok, result = reach(walk, (3019, 1469), (3045, 1465), radius=1.8)
            print("front door to street", ok, result, flush=True)
            if not ok:
                failed.append(("house-foot", result))
    for name, route in proof["lines"]:
        k = (
            "north"
            if name in ("through", "bridge")
            else "south" if name == "shore" else "house"
        )
        s = maps[k][int(name == "foot")]
        missing = [(x, z) for x, y, z in route if (x, z) not in s]
        outlier = [
            (x, z, round(s[x, z] - y / 8, 2))
            for x, y, z in route
            if (x, z) in s and abs(s[x, z] - y / 8) > 0.7
        ]
        print(
            "new vertical grade",
            name,
            "centres missing",
            missing[:6],
            "disagreement > 0.7 blocks",
            outlier[:6],
            flush=True,
        )
        if missing or outlier:
            failed.append((name, len(missing), len(outlier)))
    print("negative checks", failed)
    if failed:
        raise AssertionError(failed)


def city(a, here, track_samples, n):
    stats = Counter()
    for x in range(280, 305):
        for z in range(-743, -733):
            bottom = 77 if x < 288 else 76
            for y in range(bottom + 1, 80):
                st = a.get(x, y, z)
                assert st == "minecraft:water[level=0]" or "waterlogged=true" in st
                stats["water" if st == "minecraft:water[level=0]" else "ladder"] += 1
    for x in (276, 277, 278):
        for z in range(-747, -729):
            sy = min(79, 72 + min(z + 747, -730 - z))
            if x > 276 and z not in (-747, -730):
                assert a.get(x, sy + 1, z) in AIRS and a.get(x, sy, z) not in AIRS, (
                    x,
                    sy,
                    z,
                )
    for x in (279, 305):
        for z in range(-744, -732):
            for y in (77, 78, 79):
                assert "concrete" in a.get(x, y, z)
    for z in (-744, -733):
        for x in range(279, 306):
            for y in (77, 78, 79):
                assert "concrete" in a.get(x, y, z)
    for cx, y, za, zb, stairz, ground in [
        (-115, 75, -190, -154, -156, 80),
        (250, 60, -668, -630, -668, 72),
    ]:
        for z in range(za, zb + 1):
            assert a.get(cx + 2, y - 1, z).startswith("mtr:platform[")
            for yy in range(y, y + 4):
                assert a.get(cx, yy, z) in AIRS, (cx, yy, z)
        for x in range(cx + 5, cx + 5 + ground - y + 3):
            sy = min(ground, y + x - cx - 5)
            assert a.get(x, sy, stairz) not in AIRS and all(
                a.get(x, h, stairz) in AIRS for h in (sy + 1, sy + 2)
            ), (x, sy, stairz)
    for section in json.loads(track_samples.read_bytes()):
        for px, py, pz in section["points"]:
            x, z = math.floor(px), math.floor(pz)
            for y in range(math.ceil(py), math.ceil(py) + 4):
                assert a.get(x, y, z) in AIRS, (section["id"], x, y, z, a.get(x, y, z))
    for p in json.loads((here / "tags.json").read_bytes()):
        assert a.block_entity(*p), p
    print("disk checks", n, stats, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("kind", choices=("hills", "city", "valley"))
    p.add_argument("world", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--survey", type=Path)
    p.add_argument("--track-samples", type=Path)
    args = p.parse_args()
    out = args.output
    old = Surface(args.world / reg)
    new = park(old, out / "stage")
    changes = delta(old, new, out, args.kind != "city")
    count = sum(map(len, changes.values()))
    if args.kind == "city":
        if not args.track_samples:
            p.error("city requires --track-samples")
        city(new, out, args.track_samples, count)
    else:
        proof = json.loads((out / "proof-input.json").read_bytes())
        if args.kind == "hills":
            hills(old, new, proof, count)
        else:
            if not args.survey:
                p.error("valley requires --survey")
            valley(old, new, args.survey, out, proof, changes)
    print("Verified", count, "blocks")
