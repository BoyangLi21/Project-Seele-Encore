"""Build the detached white sub-terminal around a translated copy of the commissioned bridge."""

import json
import nbtlib
from dogma_recommission import AIR, AIRS, source_entity
from plan_r66_civic_rooms import Plan, second_command
from map_buildings.mca import World


def lift(b):
    from map_buildings import comfort17_lift as template

    # Use the production public-lift cabin, controls, doors and manifest construction.
    stops = [
        (-496, "B2 / 分析廊"),
        (-474, "1F / 地表大堂"),
        (-460, "2F / 第二発令所"),
        (-442, "3F / 展望回廊"),
    ]

    class Empty:
        def get(self, *p):
            return AIR

    original = template.stops
    try:
        template.stops = lambda: [
            dict(y=y + 629, label=label, color=i + 1)
            for i, (y, label) in enumerate(stops)
        ]
        # Translate the prototype lobby y=133 to the lowest landing. Build the
        # above-roof extension in the same shaft up to the dedicated upper cap.
        cap = template.CAP
        template.CAP = stops[-1][0] + 629 + 6
        cells, entities, spec = template.plan(Empty())
    finally:
        template.stops = original
        template.CAP = cap
    dx, dy, dz = 332, -629, -435

    def pos(p):
        return [p[0] + dx, p[1] + dy, p[2] + dz]

    for p, s in cells.items():
        b.put(*pos(p), s)
    for p, entry in entities.items():
        tag = nbtlib.parse_nbt(entry["snbt"])
        tag["id"] = nbtlib.String(entry["id"])
        d = tag["data"]
        if "controllerX" in d:
            for axis, value in zip(
                "XYZ", pos([int(d["controller" + a]) for a in "XYZ"])
            ):
                d["controller" + axis] = nbtlib.Int(value)
        b.tags[tuple(pos(p))] = tag
    for floor in spec["floors"]:
        for key in ("cabin", "controller"):
            floor[key] = pos(floor[key])
        floor["approach_y"] += dy
        for call in floor["calls"]:
            for key in ("position", "target_controller"):
                call[key] = pos(call[key])
        for door in floor["landing_doors"] + floor["cabin_doors"]:
            door["pos"] = pos(door["pos"])
    spec["id"] = "r65-public-sub-terminal"
    path = "public_lifts_r65.json"
    data = json.loads((b.world / path).read_bytes())
    data["lifts"] = [v for v in data["lifts"] if v["id"] != spec["id"]] + [spec]
    b.output(path, json.dumps(data, ensure_ascii=False, indent=1).encode())
    b.reports["terminal_elevator"] = stops


def terminal(b, previous_civic):
    removed = Plan.__new__(Plan)
    removed.reader = World(previous_civic)
    removed.cells = {}
    removed.signs = []
    second_command(removed)
    # Restore the old footprint, including the tree canopy on site, only where
    # the fitted building still matches the original author's output.
    for p, state in removed.cells.items():
        if b.reader.get(*p) == state:
            b.put(*p, removed.reader.get(*p))
    painted = 0
    for x in range(210, 301):
        for z in range(303, 379):
            inset = max(0, 9 - min(x - 210, 300 - x))
            if not 303 + inset <= z <= 378 - inset:
                continue
            if b.reader.block_entity(x, -475, z):
                raise ValueError(("occupied terminal", x, z))
            h0 = -498
            top = -440
            for y in range(h0, top + 1):
                side = x in (210, 300) or z in (303 + inset, 378 - inset)
                s = AIR
                if y in (h0, top):
                    s = "smooth_stone"
                elif side:
                    s = "smooth_quartz"
                    if y < -474:
                        s = "polished_deepslate"
                    elif y % 8 in (0, 1, 2) and (x + z) % 18 > 1:
                        s = "light_gray_stained_glass"
                    elif y % 8 == 3:
                        s = "polished_andesite"
                b.put(x, y, z, s)
            for y in range(-439, -365):
                s = b.reader.get(x, y, z)
                if "_leaves" in s or "_log" in s:
                    b.put(x, y, z, AIR)
    # Exact source bridge tiers, office seats, suspended balconies, lamps and non-MAGI consoles.
    for x in range(-7, 64):
        for z in range(247, 312):
            for y in range(-536, -482):
                s = b.reader.get(x, y, z)
                if (
                    not s
                    or s in AIRS
                    or any(
                        k in s
                        for k in (
                            "nerv_pyramid",
                            "magi",
                            "elevator",
                            "station_departure_board",
                            "direction_panel",
                            "staff_gate",
                            "access_reader",
                            "command_block",
                            "_button",
                            "barrier",
                            "sign",
                            "tuff",
                            "deepslate[",
                            "redstone_wire",
                            "escalator",
                        )
                    )
                ):
                    continue
                if s == "minecraft:stone" and not (261 <= z <= 292 and 18 <= x <= 42):
                    continue
                p = x + 224, y + 39, z + 63
                if b.reader.block_entity(x, y, z):
                    if "wall_artwork" not in s:
                        continue
                    b.tags[p] = source_entity(b.reader, (x, y, z))
                b.put(*p, s)
                painted += 1
    # A second bridge has its own passive plot wall, laid on the rear of the auditorium.
    for x in range(222, 286):
        z = 369 - max(0, (abs(x - 254) - 15) // 3)
        b.box(x, -491, z, x, -451, z, "polished_blackstone")
        for y in range(-487, -454):
            band = abs(x - 254)
            s = "black_concrete"
            if x % 13 == 0 or y % 7 == 0:
                s = "gray_terracotta"
            if (x + y * 2) % 53 in (0, 1) or (x - y) % 69 == 0:
                s = "cyan_terracotta"
            if band in (24, 27) and y % 9 in (2, 3, 4):
                s = "ochre_froglight[axis=y]"
            b.put(x, y, z - 1, s)
    # The elongated blade is a narrow three-dimensional shell rising at the east end.
    # A concave western face gives it a low projecting toe and a tall, rounded crown.
    for y in range(-439, -359):
        t = (y + 439) / 79
        east = 291 - round(4 * t * t)
        west = east - (9 + round(52 * (1 - t) ** 3))
        half = 8 - round(3 * t)
        for x in range(west, east + 1):
            for z in range(340 - half, 341 + half):
                if (
                    x not in (west, east)
                    and abs(z - 340) != half
                    and y not in (-439, -360)
                ):
                    continue
                s = "smooth_quartz"
                if x == east or z == 340 + half and x > east - 3:
                    s = "light_gray_concrete"
                if x == west and y % 19 in (0, 1):
                    s = "light_blue_stained_glass"
                if y == -360:
                    s = "white_concrete"
                b.put(x, y, z, s)
    # Each landing opens on the same dry aisle. The upper command gallery
    # terminates beside the original commander's seat at translated (28,269).
    for floor in (-497, -475, -461, -443):
        b.box(286, floor, 340, 297, floor, 348, "smooth_stone")
        b.box(286, floor + 1, 341, 297, floor + 4, 348, AIR)
        b.box(284, floor, 329, 288, floor, 344, "smooth_stone")
        b.box(284, floor + 1, 329, 288, floor + 4, 344, AIR)
        if floor == -475:
            b.box(208, floor, 342, 289, floor, 346, "polished_andesite")
            b.box(208, floor + 1, 342, 287, floor + 4, 346, AIR)
        else:
            b.box(251, floor, 330, 286, floor, 333, "smooth_stone")
            b.box(251, floor + 1, 330, 286, floor + 3, 333, AIR)
        b.put(287, floor, 343, "sea_lantern")
    lift(b)
    b.sign(211, -472, 341, "west", "NERV 本部", "SUB TERMINAL", "第二発令所", "入口 →")
    # A low graded access walk follows the wooded slope from the original forecourt.
    points = [
        (53, -467, 392),
        (97, -467, 388),
        (138, -467, 373),
        (165, -468, 369),
        (184, -471, 359),
        (207, -475, 344),
    ]
    for a, c in zip(points, points[1:]):
        steps = max(abs(c[0] - a[0]), abs(c[2] - a[2]))
        for i in range(steps + 1):
            x, y, z = [round(u + (v - u) * i / steps) for u, v in zip(a, c)]
            for X in range(x - 2, x + 3):
                for Z in range(z - 2, z + 3):
                    s = b.get(X, y, Z)
                    if "pyramid" in s:
                        continue
                    for Y in range(y - 1, y - 8, -1):
                        if b.get(X, Y, Z) not in AIRS and "leaves" not in b.get(
                            X, Y, Z
                        ):
                            break
                        b.put(X, Y, Z, "stone_bricks")
                    b.put(X, y, Z, "smooth_stone")
                    for Y in range(y + 1, y + 5):
                        s = b.get(X, Y, Z)
                        if any(
                            k in s for k in ("dirt", "grass", "leaves", "_log", "fern")
                        ):
                            b.put(X, Y, Z, AIR)
    b.reports["bridge_template_blocks"] = painted
