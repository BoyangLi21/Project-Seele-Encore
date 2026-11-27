"""Place the curved command wall, operations podium and aboveground public lift."""

from dogma_recommission import AIR, AIRS, FLOOR, WALL, source_entity
from dogma_command_tower import tree
import json
import math
import nbtlib
from map_buildings import comfort17_lift as lift
from unittest.mock import patch
import numpy as np

# Voxel origin of the surveyed FBX component. Local axes are X, Z across the blade, height.
X, Z, GROUND = 200, 334, -471
LIFT_X, LIFT_Z = X + 53, Z + 59
STOPS = [
    (GROUND + 1, "1F / 地表入口"),
    (GROUND + 9, "2F / 第二発令所"),
    (GROUND + 20, "3F / 作戦展望席"),
    (GROUND + 147, "4F / 集光壁観測廊"),
]
ENTRY = (X + 26, GROUND + 9, Z + 62)


def restore_site(b, survey):
    # Both preceding tower revisions and their graded access ended within these bounds.
    for x in range(169, 314):
        for z in range(301, 381):
            if x < 200 and not (342 <= z <= 372):
                continue
            for y in range(-498 if x >= 200 else -481, -279 if x >= 230 else -365):
                s = survey.get(x, y, z)
                if s is None:
                    raise ValueError(("unknown original site", x, y, z))
                if s == b.reader.get(x, y, z):
                    continue
                b.put(x, y, z, s)
                if survey.block_entity(x, y, z):
                    b.tags[x, y, z] = source_entity(survey, (x, y, z))


def shell(b, raster):
    m, c = raster["m"].astype(bool), raster["c"]
    pad = set(zip(*(axis.tolist() for axis in np.nonzero(m.any(2)))))
    for i in range(21, 57):
        for j in range(39, 84):
            if i >= 21 + max(0, (abs(j - 61) - 15) // 2):
                pad.add((i, j))
    # Clear complete trunks confined to the development footprint; trim overhanging branches above it.
    trunks = set()
    for i in range(-4, 64):
        for j in range(-4, 126):
            for y in range(-480, -433):
                s = b.get(X + i, y, Z + j)
                if s and "_log" in s:
                    trunks.add((i, j))
                    break
    cut = {t for t in trunks if t in pad}
    for i in range(-4, 64):
        for j in range(-4, 126):
            near = [t for t in trunks if abs(t[0] - i) <= 5 and abs(t[1] - j) <= 5]
            if (i, j) not in pad and (
                not near
                or min(near, key=lambda t: (t[0] - i) ** 2 + (t[1] - j) ** 2) not in cut
            ):
                continue
            x, z = X + i, Z + j
            for y in range(-482, -405):
                s = b.get(x, y, z)
                if s and tree(s):
                    b.put(x, y, z, AIR)
            if (i, j) not in pad:
                continue
            for y in range(GROUND - 1, GROUND - 19, -1):
                s = b.get(x, y, z)
                if s not in AIRS:
                    break
                b.put(x, y, z, "polished_andesite" if y >= GROUND - 2 else "andesite")
            b.put(x, GROUND, z, "polished_andesite")
    for i, j, k in zip(*np.nonzero(m)):
        i, j, k = int(i), int(j), int(k)
        r, g, blue = map(int, c[i, j, k])
        l = 0.27 * r + 0.63 * g + 0.10 * blue
        s = (
            "smooth_sandstone"
            if l > 219
            else "cut_sandstone"
            if l > 195
            else "white_terracotta"
            if l > 158
            else "light_gray_terracotta"
            if l > 122
            else "polished_andesite"
            if l > 82
            else "polished_deepslate"
        )
        # Collector's structural back is deeper bronze; the front lens has inset horizontal status slots.
        if i >= 50 and j in range(27, 97) and c[i, j, k, 2] < 107 and k > 19:
            s = "cut_copper"
        if (
            k > 48
            and i < 53
            and 17 < j < 107
            and min(abs(k - 0.23 * (j - 61) - t) for t in (72, 117, 159)) < 0.60
        ):
            s = "ochre_froglight[axis=y]"
        b.put(X + i, GROUND + k, Z + j, s)
    b.reports["fbx_shell"] = {
        "triangles": 1964,
        "occupied_shell_cells": int(m.sum()),
        "bounds": [[X + 3, GROUND + 1, Z + 3], [X + 57, GROUND + 201, Z + 118]],
    }


def interiors(b):
    def put(i, h, j, state):
        b.put(X + i, GROUND + h, Z + j, state)

    # Chamfered command podium and setback upper watch bridge nest between the original flared wings.
    for h in range(24):
        front, half = (21, 22) if h <= 8 else (24, 20) if h <= 18 else (32, 15)
        for j in range(61 - half, 62 + half):
            left = front + max(0, (abs(j - 61) - (half - 7)) // 2)
            for i in range(left, 54):
                exterior = i == left or abs(j - 61) == half
                if h in (0, 8, 18, 19, 23):
                    s = "smooth_quartz" if exterior else FLOOR
                elif exterior:
                    s = (
                        "gray_stained_glass"
                        if (2 <= h <= 5 or 10 <= h <= 15 or 20 <= h <= 22)
                        and (j % 8 != 0 if i == left else i % 8 != 0)
                        else "white_terracotta"
                    )
                else:
                    s = AIR
                put(i, h, j, s)
    # Entrance under the wedge, leading directly past reception towards the public lift.
    for i in range(20, 24):
        for j in range(59, 65):
            for h in range(1, 6):
                put(i, h, j, AIR)
    for j in (55, 67):
        for i in range(15, 22):
            put(i, 6, j, "polished_andesite")
    for i in range(15, 24):
        for j in range(55, 68):
            put(i, 7, j, "smooth_quartz_slab[type=bottom,waterlogged=false]")
    for i in range(25, 48, 7):
        for j in (46, 54, 70, 77):
            put(i, 7, j, "sea_lantern")
            put(i, 17, j, "sea_lantern")
    for j in range(45, 77):
        if 50 <= j <= 72:
            for h in range(10, 17):
                state = "black_concrete"
                if h in (11, 15) or j in (53, 61, 69):
                    state = "cyan_terracotta"
                if h == round(13 + 2 * math.sin((j - 50) * 0.30)):
                    state = "oxidized_copper"
                if j in (50, 72) and h % 3 == 0:
                    state = "sea_lantern"
                put(47, h, j, state)
    for i in (29, 35, 41):
        for j in (48, 55, 62, 69, 76):
            put(i, 9, j, "projectseele:military_seat[facing=east]")
            for off in (-1, 0, 1):
                put(i + 2, 9, j + off, "polished_blackstone")
                put(
                    i + 2,
                    10,
                    j + off,
                    "warped_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]",
                )
            put(i + 3, 9, j, "sea_lantern")
            put(i + 3, 10, j, "cyan_stained_glass")
    for j in (47, 74):
        for i in range(33, 47, 4):
            put(i, 1, j, "projectseele:station_seat[facing=west]")
    for j in range(47, 76, 5):
        put(36, 20, j, "projectseele:station_seat[facing=west]")
    # Narrow optical gallery follows the curvature of the real blade. Shaft door opens south.
    for j in range(63, 86):
        centre = (j - 61) / 24
        left = 50 - round(2.2 * centre * centre)
        for i in range(left, 57 - round(1.4 * centre * centre)):
            put(i, 146, j, "polished_deepslate")
            put(i, 152, j, WALL)
            for h in range(147, 152):
                s = AIR
                if i == left:
                    s = (
                        "gray_stained_glass"
                        if h in (148, 149, 150) and j % 8
                        else "polished_andesite"
                    )
                if j == 85:
                    s = WALL
                put(i, h, j, s)
            if j in (66, 74, 82):
                put(i, 152, j, "sea_lantern")
    # The observation and command landings have a continuous 2-high approach on every floor.
    for h, _ in STOPS:
        b.box(LIFT_X - 2, h - 1, LIFT_Z + 3, LIFT_X + 2, h - 1, LIFT_Z + 7, FLOOR)
        b.box(LIFT_X - 2, h, LIFT_Z + 4, LIFT_X + 2, h + 3, LIFT_Z + 7, AIR)
    b.sign(
        X + 47,
        GROUND + 12,
        Z + 73,
        "south",
        "第二発令所",
        "作戦表示盤",
        "OPERATIONS",
        "02",
    )
    put(31, 1, 57, "polished_deepslate")
    put(31, 2, 57, "polished_andesite")
    b.sign(
        X + 31,
        GROUND + 2,
        Z + 58,
        "south",
        "NERV / GEOFRONT",
        "第二発令所",
        "作戦管制 ↑",
        "観測廊 EV →",
    )


def walk(b):
    # Join the retained approach at the fork. Pass north of the occupied rail gallery.
    line = [
        (167, -468, 369),
        (184, -470, 374),
        (201, -471, 380),
        (209, -471, 388),
        (215, -471, 395),
        (222, -471, 395),
    ]
    for a, c in zip(line, line[1:]):
        n = max(abs(c[0] - a[0]), abs(c[2] - a[2]))
        for i in range(n + 1):
            x, y, z = [round(p + (q - p) * i / n) for p, q in zip(a, c)]
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    X0, Z0 = x + dx, z + dz
                    for yy in range(y - 1, y - 14, -1):
                        if b.get(X0, yy, Z0) not in AIRS:
                            break
                        b.put(X0, yy, Z0, "andesite")
                    b.put(X0, y, Z0, "polished_andesite")
                    for yy in range(y + 1, y + 5):
                        s = b.get(X0, yy, Z0)
                        if tree(s) or "grass" in s or "dirt" in s:
                            b.put(X0, yy, Z0, AIR)


def elevator(b):
    dy = STOPS[0][0] - (lift.LOBBY_FLOOR + 1)

    def pos(p):
        return [p[0] + LIFT_X - lift.CX, p[1] + dy, p[2] + LIFT_Z - lift.CZ]

    stops = [
        dict(y=y - dy, label=label, color=i + 1) for i, (y, label) in enumerate(STOPS)
    ]

    class Shaft:
        def get(self, *p):
            return AIR

    with (
        patch.object(lift, "stops", return_value=stops),
        patch.object(lift, "CAP", stops[-1]["y"] + 6),
    ):
        cells, entities, spec = lift.plan(Shaft())
    for p, s in cells.items():
        b.put(*pos(p), s)
    for p, e in entities.items():
        tag = nbtlib.parse_nbt(e["snbt"])
        tag["id"] = nbtlib.String(e["id"])
        d = tag["data"]
        if "controllerX" in d:
            for axis, value in zip(
                "XYZ", pos([int(d["controller" + a]) for a in "XYZ"])
            ):
                d["controller" + axis] = nbtlib.Int(value)
        b.tags[tuple(pos(p))] = tag
    for index, f in enumerate(spec["floors"]):
        for k in ("cabin", "controller"):
            f[k] = pos(f[k])
        f["approach_y"] += dy
        for call in f["calls"]:
            for k in ("position", "target_controller"):
                call[k] = pos(call[k])
        for door in f["landing_doors"] + f["cabin_doors"]:
            door["pos"] = pos(door["pos"])
        for door in f["landing_doors"]:
            b.put(
                *door["pos"],
                AIR if index == 0 else "projectseele:lift_door_interlock_r53",
            )
        if index == 0:
            for door in f["cabin_doors"]:
                b.put(*door["pos"], AIR)
    spec["id"] = "r65-public-sub-terminal"
    fn = "public_lifts_r65.json"
    d = json.loads((b.world / fn).read_bytes())
    d["lifts"] = [spec if s["id"] == spec["id"] else s for s in d["lifts"]]
    b.output(fn, json.dumps(d, ensure_ascii=False, indent=1).encode())


def skin(b):
    for x in range(LIFT_X - 3, LIFT_X + 4):
        for z in range(LIFT_Z - 3, LIFT_Z + 4):
            for h in range(24, 147):
                p = x, GROUND + h, z
                if b.get(*p) != "minecraft:light_gray_concrete":
                    continue
                # Follow the surrounding lens's three diagonal luminous strips, including across the shaft.
                s = "smooth_sandstone" if x <= LIFT_X else "cut_copper"
                if (
                    x <= LIFT_X
                    and min(abs(h - 0.23 * (z - 395) - k) for k in (72, 117, 159))
                    < 0.60
                ):
                    s = "ochre_froglight[axis=y]"
                b.put(*p, s)
