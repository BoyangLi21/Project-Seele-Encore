"""Author the central school shuttle, raised school pool and six moving skyline landmarks.

rail-plan writes the input for RegionalTransitAuthor --append. That author emits the
track_samples.json required by the surface step. crowns reads an idle, extended source
world and its matching mod jar; it creates the registered owner-relative plans and LOD
resources. surface combines the seven fixed signs, pool and line with those plans.
Run Tokyo3CargoR66 WORLD OUTPUT/plan CARGO_OUTPUT --school-district to update the
ledger, generation cargo and both journals. Neither step edits the original save.
"""

import argparse, gzip, json, math, sys, struct, zipfile
from math import ceil, floor
from pathlib import Path
from collections import Counter
from surface_renewal_io import open_overlay, save_overlay, Surface, reg
from dogma_recommission import AIR, AIRS
from private_cleanup import DATA, unpack, state
from city_body_sync import topology
from tokyo3_r66_design import model
from tokyo3_r66_plan import mesh
import tokyo3_r66_lights as lights
import nbtlib

M = "minecraft:"


def service_plan():
    stations = [
        dict(
            id="central_school",
            existing_id=-946477054342182766,
            min=[-115, 75, -190],
            max=[-115, 75, -155],
        ),
        dict(
            id="school",
            name="第壱中学校前|第一中学|Daiichi Junior High",
            min=[237, 55, -679],
            max=[260, 76, -626],
            color=0x3F8878,
        ),
    ]
    nodes = [
        (-115, 75, -103),
        (-115, 75, -136),
        (-115, 75, -154),
        (-115, 75, -190),
        (-115, 72, -218),
        (-85, 67, -278),
        (185, 59, -548),
        (250, 60, -623),
        (250, 60, -630),
        (250, 60, -667),
        (250, 60, -689),
        (250, 60, -718),
    ]
    angles = ["N", "N", "N", "N", "N", "NE", "NE", "N", "N", "N", "N", "N"]
    reverse = {"N": "S", "NE": "SW"}
    keys = [
        "garage",
        "yard",
        "cplatform",
        "head",
        "bend",
        "diagonal",
        "schoolbend",
        "throat",
        "splatform",
        "exit",
        "turn",
    ]
    rails = [
        dict(
            id=k,
            kind={
                "garage": "siding",
                "cplatform": "platform",
                "splatform": "platform",
                "turn": "turnback",
            }.get(k, "rail"),
            speed=45,
            from_angle=angles[i],
            to_angle=reverse[angles[i + 1]],
            **{"from": u, "to": v},
        )
        for i, (k, u, v) in enumerate(zip(keys, nodes, nodes[1:]))
    ]
    cars = [
        dict(
            id="eidan_9000_cab_1",
            length=20.0,
            width=2.0,
            bogie1=-6.0,
            bogie2=6.0,
            padding1=1.0,
            padding2=0.0,
        )
    ]
    return dict(
        commission_clock=True,
        rails=rails,
        stations=stations,
        lines=[
            dict(
                id="S",
                name="学園線|学园线|School Shuttle",
                platforms=["cplatform", "splatform", "cplatform"],
                cars=cars,
                siding="garage",
                trains=1,
                dwell=8500,
                frequency=4,
                steady=True,
                color=0x379384,
            )
        ],
    )


FENCE = "iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]"


def bars(along):
    return (
        "iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]"
        if along == "z"
        else FENCE
    )


def school(b):
    # The old deck footprint abuts the retained changing rooms along its west side.
    # Lift the basin and deck seven metres. Two flights occupy the gap beside those rooms.
    for x in range(276, 309):
        for z in range(-747, -729):
            basin = 280 <= x <= 304 and -743 <= z <= -734
            wall = 279 <= x <= 305 and -744 <= z <= -733
            rim = x in (276, 308) or z in (-747, -730)
            stair = x in (276, 277, 278)
            for y in range(73, 82):
                v = "air"
                if y == 73 and not stair:
                    v = "smooth_stone"
                if wall and y >= 74 and y <= 79:
                    if basin:
                        bottom = 77 if x < 288 else 76
                        if y < bottom:
                            v = "smooth_stone"
                        elif y == bottom:
                            v = (
                                "blue_concrete"
                                if (z + 743) % 2 == 0 and 281 <= x <= 303
                                else "light_blue_concrete"
                            )
                            if x in (282, 301) and z in (-742, -735):
                                v = "sea_lantern"
                        else:
                            v = "water[level=0]"
                    else:
                        v = "white_concrete" if y == 79 else "light_gray_concrete"
                elif not stair and not basin:
                    if y in (76, 77, 78) and (x in (279, 305) or z in (-744, -733)):
                        v = "light_gray_concrete"
                    if y == 79:
                        v = "smooth_quartz" if not rim else "smooth_stone"
                    if rim and y == 80:
                        v = bars("z" if x in (276, 308) else "x")
                    if rim and x % 8 == 4 and z % 3 == 0 and y < 79:
                        v = "smooth_stone"
                if stair:
                    distance = min(z + 747, -730 - z)
                    sy = min(79, 72 + distance)
                    if y <= sy:
                        v = (
                            "white_concrete"
                            if y < sy
                            else (
                                "smooth_stone"
                                if sy == 79 or not distance
                                else f'quartz_stairs[facing={"south" if z<-739 else "north"},half=bottom,shape=straight,waterlogged=false]'
                            )
                        )
                    if x == 276 and y == sy + 1 and 0 < distance:
                        v = bars("z")
                b.put(x, y, z, v)
            if stair and z in (-747, -730):
                b.put(x, 72, z, "smooth_stone")
                if x in (277, 278):
                    b.put(
                        x,
                        73,
                        z,
                        "oak_fence_gate[facing="
                        + ("north" if z == -747 else "south")
                        + ",in_wall=false,open=false,powered=false]",
                    )
            if not stair and x == 279 and -740 <= z <= -737:
                b.put(x, 80, z, "air")
    for x, z, face in [(280, -742, "east"), (304, -735, "west")]:
        for y in range(77 if x == 280 else 76, 80):
            if y > (77 if x == 280 else 76):
                b.put(x, y, z, f"ladder[facing={face},waterlogged=true]")
    # Low rim ladders have both a backing wall and a handhold above the pool surface.
    # It is also possible to step straight out of the source-water surface all around.
    for z in range(-743, -733, 2):
        b.put(306, 80, z, "smooth_quartz_slab[type=bottom,waterlogged=false]")
    for x in (285, 298):
        b.box(
            x,
            80,
            -746,
            x + 2,
            80,
            -746,
            "smooth_quartz_slab[type=bottom,waterlogged=false]",
        )
    b.put(279, 81, -735, "light_gray_concrete")
    b.sign(278, 81, -735, "west", "水泳部", "POOL DECK", "25 m ・ 5 lanes", "足元注意")


def demolishtower(b, live):
    t = topology(live)[77]
    cx, cy, cz = t["centre"]
    root = nbtlib.load(live / DATA / "city_rigid_generation_r45/cargo/77.dat")["data"][
        "Buildings"
    ][0]
    cargo = {
        tuple(a + b for a, b in zip(t["centre"], unpack(c["Pos"]))): state(c["State"])
        for c in root["Cargo"]
    }
    removed = Counter()
    for x in range(15, 46):
        for z in range(180, 201):
            for y in range(81, 90):
                p = x, y, z
                v = b.get(*p)
                if p in cargo:
                    continue
                if not v or v in AIRS or not v.startswith(M):
                    continue
                if v.split("[")[0] in {
                    M + s
                    for s in (
                        "polished_blackstone_bricks",
                        "smooth_stone",
                        "gray_stained_glass",
                        "sea_lantern",
                        "glass",
                        "beacon",
                        "iron_block",
                        "gray_concrete",
                        "black_concrete",
                        "orange_stained_glass",
                        "smooth_quartz",
                        "andesite_wall",
                    )
                }:
                    if x in (15, 45) or z in (180, 181):
                        continue
                    if z in (199, 200) and not 25 <= x <= 35:
                        continue
                    if b.reader.block_entity(*p) and v != M + "beacon":
                        raise ValueError(("unexpected block entity", p, v))
                    b.put(*p, "air")
                    removed[v.split("[")[0]] += 1
    # Actual material of the retained taller building is identical to the saved moving cargo everywhere touched.
    assert all(b.get(*p) == s for p, s in cargo.items())
    print("old low building", dict(removed), flush=True)


def tunnel(b, track_samples):
    samples = json.loads(track_samples.read_bytes())
    grid = {}
    for section in samples:
        points = section["points"]
        for a, c in zip(points, points[1:]):
            for f in (0.0, 0.5, 1.0):
                px, py, pz = (u + (v - u) * f for u, v in zip(a, c))
                for x in range(floor(px) - 4, floor(px) + 5):
                    for z in range(floor(pz) - 4, floor(pz) + 5):
                        dist = math.hypot(x + 0.5 - px, z + 0.5 - pz)
                        if dist > 3.8 or dist >= grid.get((x, z), (999, 0))[0]:
                            continue
                        grid[x, z] = dist, py
    old = Counter()
    bes = []
    for (x, z), (d, py) in grid.items():
        lo = floor(py + 0.00001)
        hi = ceil(py - 0.00001) + 5
        for y in range(lo - 1, hi + 1):
            v = b.get(x, y, z)
            if not v:
                raise RuntimeError(("missing", x, y, z))
            if y == hi and v not in AIRS:
                continue
            if b.reader.block_entity(x, y, z):
                bes.append((x, y, z, v))
            if v not in AIRS and "minecraft:" not in v:
                old[v] += 1
            if (
                y == hi
                and -145 >= z >= -197
                and -120 <= x <= -110
                and hi == 80
                and v not in AIRS
            ):
                continue
            if y == lo - 1:
                mat = "polished_deepslate" if d < 1.7 else "stone_bricks"
            elif d >= 2.92 or y == hi:
                mat = "light_gray_concrete" if y in (lo + 1, hi - 1) else "stone_bricks"
            else:
                mat = "air"
            if d >= 2.92 and y == lo + 2 and (x + z) % 19 in (0, 1):
                mat = "sea_lantern"
            b.put(x, y, z, mat)
    print("transit occupied mod blocks", old, "block entities", bes[:15], flush=True)
    if bes:
        raise ValueError(bes)
    door = "mtr:platform[door_type=none,facing=north,side=0]"
    for cx, y, za, zb, stairz, stop, ground in [
        (-115, 75, -190, -154, -156, "東京３中央", 80),
        (250, 60, -668, -630, -668, "第壱中学校前", 72),
    ]:
        # The open side runs the entire train length, with the genuine door sensors directly beneath the warning strip.
        for x in range(cx + 2, cx + 9):
            for z in range(za - 3, zb + 3):
                south = z in (za - 3, zb + 2)
                b.put(
                    x,
                    y - 1,
                    z,
                    door if x == cx + 2 and za <= z <= zb else "stone_bricks",
                )
                b.put(x, y, z, "yellow_concrete" if x == cx + 2 else "smooth_stone")
                for yy in range(y + 1, y + 5):
                    block = "light_gray_concrete" if x == cx + 8 or south else "air"
                    if block != "air" and yy == y + 3 and z % 9 in (0, 1):
                        block = "sea_lantern"
                    b.put(x, yy, z, block)
                if y + 5 != 80 or b.get(x, y + 5, z) in AIRS:
                    b.put(x, y + 5, z, "smooth_stone")
        # Tile stairs rise directly to the existing concourse and to the school's approach pavement.
        stair0 = cx + 5
        for x in range(stair0, stair0 + ground - y + 3):
            floorY = min(ground, y + x - stair0)
            for z in range(stairz - 1, stairz + 2):
                b.box(x, y - 1, z, x, floorY - 1, z, "stone_bricks")
                b.put(
                    x,
                    floorY,
                    z,
                    (
                        "smooth_stone"
                        if floorY in (ground, y)
                        else "stone_brick_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]"
                    ),
                )
                for yy in range(floorY + 1, ground + 3):
                    b.put(x, yy, z, "air")
        for z in (stairz - 2, stairz + 2):
            for x in range(stair0 + 3, stair0 + ground - y):
                if b.get(x, ground, z) in AIRS:
                    b.put(x, ground, z, "smooth_stone")
                b.put(
                    x,
                    ground + 1,
                    z,
                    "iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]",
                )
        # Shoppers and students follow the landing south-west to the existing front gate road.
        if ground == 72:
            for x in range(stair0 + ground - y, stair0 + ground - y + 3):
                for z in range(-673, stairz + 2):
                    b.put(x, ground, z, "smooth_stone")
                    b.box(x, ground + 1, z, x, ground + 3, z, "air")
        for z in (za + 7, zb - 8):
            b.sign(
                cx + 7,
                y + 3,
                z,
                "west",
                stop,
                "学園線　S",
                "東京３中央 ⇄ 第壱中学",
                "School Shuttle",
            )
        b.put(stair0 + ground - y + 1, ground + 2, stairz + 2, "light_gray_concrete")
        b.sign(
            stair0 + ground - y + 1,
            ground + 2,
            stairz + 1,
            "north",
            "学園線　S",
            "↓ 乗車ホーム",
            "学校 ⇄ 中央駅",
            "School Shuttle",
        )


def build_crowns(live, jar, here):
    if not here.exists():
        here.mkdir(parents=True)
    targets = {
        34: (117, 21),
        39: (131, 43),
        40: (124, 37),
        23: (119, 8),
        35: (111, 37),
        29: (117, 43),
    }
    a = Surface(live / reg)
    ts = topology(live)
    res = "assets/projectseele/city/"
    plan = here / "plan"
    plan.mkdir(exist_ok=True)
    (here / "resources").mkdir(exist_ok=True)
    selected = {}
    clears = {}
    with zipfile.ZipFile(jar) as j, gzip.GzipFile(
        fileobj=j.open(res + "city_shells_r66.bin.gz")
    ) as src, gzip.open(
        here / "resources/city_shells_r66.bin.gz", "wb", compresslevel=4
    ) as dst:
        dst.write(src.read(6))
        for i, t in ts.items():
            frame = src.read(16)
            raw = src.read(4)
            encoded = src.read(13 * struct.unpack(">I", raw)[0])
            if i not in targets:
                dst.write(frame + raw + encoded)
                continue
            height, variant = targets[i]
            cx, cy, cz = t["centre"]
            xa, xb, za, zb = t["fp"]
            ret = t["ret"]
            cargo = nbtlib.load(
                live / DATA / f"city_rigid_generation_r45/cargo/{i}.dat"
            )["data"]["Buildings"][0]["Cargo"]
            orig = {unpack(c["Pos"]): state(c["State"]) for c in cargo}
            shape = model(variant, height, min(xb, zb), orig)
            for c in cargo:
                if "NBT" in c:
                    shape[unpack(c["Pos"])] = state(c["State"])
            bad = Counter()
            clear = {}
            for x in range(xa, xb + 1):
                for z in range(za, zb + 1):
                    for y in range(ret, cy + height + 4):
                        current = a.get(cx + x, y, cz + z)
                        expect = orig.get((x, y - cy, z), AIR)
                        if current == expect:
                            continue
                        if (
                            y < cy
                            and current
                            in (
                                "minecraft:stone",
                                "minecraft:dirt",
                                "minecraft:deepslate",
                                "minecraft:tuff",
                                "minecraft:andesite",
                            )
                            and not a.block_entity(cx + x, y, cz + z)
                        ):
                            clear[cx + x, y, cz + z] = current
                        else:
                            bad[current] += 1
            if bad:
                print("blocked", i, bad, flush=True)
                dst.write(frame + raw + encoded)
                continue
            edits = {
                p: (orig.get(p, AIR), shape.get(p, AIR))
                for p in orig.keys() | shape.keys()
                if orig.get(p, AIR) != shape.get(p, AIR)
            }
            assert all(9 <= p[1] <= height + 3 for p in edits) and height + ret + 3 < cy
            with gzip.open(plan / f"{i}.tsv.gz", "wt") as f:
                for (x, y, z), (old, new) in sorted(edits.items()):
                    f.write(f"{x}\t{y}\t{z}\t{old}\t{new}\n")
            selected[i] = dict(
                old=t["H"],
                new=height,
                centre=t["centre"],
                lower=ret,
                carve=len(clear),
                edits=len(edits),
                body=len(shape),
            )
            clears.update(clear)
            mesh(i, t, shape, dst)
            print("OK", i, selected[i], flush=True)
        assert not src.read(1)
        with j.open(res + "night_lights_r65.bin.gz") as f:
            (here / "lights-old.gz").write_bytes(f.read())
    with gzip.open(plan / "shaft.tsv.gz", "wt") as f:
        for (x, y, z), old in sorted(clears.items()):
            f.write(f"{x}\t{y}\t{z}\t{old}\t{AIR}\n")
    (plan / "targets.json").write_text(json.dumps(selected, indent=1))
    (plan / "crown-heights.tsv").write_text(
        "".join(f"{i}\t{v['old']}\t{v['new']}\n" for i, v in selected.items())
    )
    if selected.keys() != targets.keys():
        raise RuntimeError(
            ("Unobstructed owners required", sorted(targets.keys() - selected.keys()))
        )
    lights.rebuild(
        here / "lights-old.gz",
        here / "resources/city_shells_r66.bin.gz",
        here / "resources/night_lights_r65.bin.gz",
        set(selected),
    )


def build_surface(live, samples, out):
    b = open_overlay(live, out)
    school(b)
    demolishtower(b, live)
    tunnel(b, samples)
    targets = json.loads((out / "plan/targets.json").read_bytes())
    plans = [(out / "plan/shaft.tsv.gz", (0, 0, 0), True)]
    plans += [
        (out / f"plan/{i}.tsv.gz", t["centre"], False) for i, t in targets.items()
    ]
    count, chunks = save_overlay(b, live, out, plans)
    print(count, "blocks in", chunks, "chunks")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    def command(name, *fields):
        pp = sub.add_parser(name)
        for field in fields:
            pp.add_argument(field, type=Path)

    command("rail-plan", "file")
    command("crowns", "world", "jar", "output")
    command("surface", "world", "track_samples", "output")
    args = p.parse_args()
    if args.command == "rail-plan":
        args.file.write_text(
            json.dumps(service_plan(), ensure_ascii=False), encoding="utf8"
        )
    else:
        if (
            args.world.resolve() == args.output.resolve()
            or args.world.resolve() in args.output.resolve().parents
            or args.output.resolve() in args.world.resolve().parents
        ):
            raise ValueError("Choose a separate output directory")
        if args.command == "crowns":
            build_crowns(args.world, args.jar, args.output)
        else:
            build_surface(args.world, args.track_samples, args.output)
