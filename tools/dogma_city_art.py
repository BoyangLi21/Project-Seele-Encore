"""Add street-scale details to surveyed fixed buildings and link the lake mirrors to the GeoFront ceiling."""

import csv
import gzip
import json
from collections import Counter
from dogma_recommission import AIRS
from map_buildings.city_body_sync import topology


def street_fronts(b, authority, survey):
    boxes = []
    for tower in topology(authority).values():
        x, _, z = tower["centre"]
        a, c, d, e = tower["fp"]
        boxes.append((x + a - 2, x + c + 2, z + d - 2, z + e + 2))
    zones = json.loads((authority / "regional_plan.json").read_bytes())["zones"]
    groups = Counter()
    with gzip.open(survey, "rt", encoding="utf8") as stream:
        for row in csv.reader(stream, delimiter="\t"):
            x, y, z = map(int, row[:3])
            if any(a <= x <= c and d <= z <= e for a, c, d, e in boxes):
                continue
            if (-215 <= x <= -125 and 488 <= z <= 557) or (
                -81 <= x <= 4 and 752 <= z <= 816
            ):
                continue
            anchor = b.reader.get(x, y, z)
            if anchor != row[4] or b.reader.block_entity(x, y, z):
                continue
            # A continuous daylight opening is an identifiable outside shop or office frontage.
            for h in (y, y + 1):
                if "glass" not in b.reader.get(x, h, z):
                    continue
                for u, v in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    X, Z = x + u, z + v
                    if any(
                        b.get(X, k, Z) not in AIRS
                        or b.reader.get(X + u, k, Z + v) not in AIRS
                        for k in (h, h + 1)
                    ):
                        continue
                    if not any(
                        "glass" in b.reader.get(x + n * v, h, z + n * u)
                        for n in (-1, 1)
                    ):
                        continue
                    region = next(
                        (
                            t["id"]
                            for t in zones
                            if t["kind"] == "district"
                            and t["bounds"][0] <= x <= t["bounds"][1]
                            and t["bounds"][2] <= z <= t["bounds"][3]
                        ),
                        "tokyo_core",
                    )
                    j = x if v else z
                    if h < 104 or (region == "new_hakone" and h < 138):
                        # Narrow metal hoods above the storefronts keep thresholds and sightlines clear.
                        if b.get(X, h + 2, Z) not in AIRS or "air" in b.get(
                            x, h + 2, z
                        ):
                            continue
                        tone = {
                            "new_hakone": "brick",
                            "tokyo_south": "polished_andesite",
                            "tokyo_west": "smooth_sandstone",
                            "harbour_ward": "oxidized_cut_copper",
                        }.get(region, "smooth_quartz")
                        b.put(X, h + 2, Z, tone + "_slab[type=top,waterlogged=false]")
                    elif j % 6 == 0:
                        if b.get(X, h - 1, Z) not in AIRS or "glass" in b.get(
                            x, h - 1, z
                        ):
                            continue
                        b.put(
                            X,
                            h - 1,
                            Z,
                            "smooth_quartz_slab[type=top,waterlogged=false]",
                        )
                        b.put(X, h, Z, "quartz_pillar[axis=y]")
                    else:
                        continue
                    groups[region] += 1
                    break
                else:
                    continue
                break
    b.reports["fixed_frontage_details"] = dict(groups)


def lake_mirrors(b):
    panels = [(-479, 1018), (-452, 1027), (-425, 1035)]
    for i, (cx, cz) in enumerate(panels):
        for x in range(cx - 11, cx + 12):
            for z in range(cz - 6, cz + 7):
                if abs(x - cx) + abs(z - cz) > 15:
                    continue
                b.put(
                    x,
                    100,
                    z,
                    "smooth_stone" if abs(x - cx) < 10 else "polished_andesite",
                )
                if abs(x - cx) == 8 and abs(z - cz) == 4:
                    for y in range(99, 58, -1):
                        if "water" not in b.get(x, y, z):
                            break
                        b.put(x, y, z, "stone_bricks")
        for x in (cx - 7, cx + 7):
            b.box(x - 1, 101, cz - 1, x + 1, 111, cz + 1, "polished_andesite")
        for x in range(cx - 10, cx + 11):
            for k in range(15):
                z = cz - 5 + round(k * (0.67 + 0.05 * i))
                y = 105 + k
                frame = abs(x - cx) == 10 or k in (0, 14)
                prism = (
                    "light_blue_stained_glass"
                    if (x - cx) % 5 and k % 5
                    else "white_stained_glass"
                )
                b.put(x, y, z, "smooth_quartz" if frame else prism)
                b.put(
                    x,
                    y,
                    z + 1,
                    "polished_andesite" if frame or (x - cx) % 5 == 0 else "packed_ice",
                )
        # Twin apertures are set directly into the local natural ceiling, around the light guide.
        for x in range(cx - 5, cx + 6):
            for z in range(cz - 3, cz + 4):
                ceiling = next(
                    y for y in range(-50, 51) if b.reader.get(x, y, z) not in AIRS
                )
                st = b.reader.get(x, ceiling, z)
                if (
                    st
                    not in (
                        "minecraft:stone",
                        "minecraft:deepslate",
                        "minecraft:dirt",
                        "minecraft:andesite",
                        "minecraft:tuff",
                        "projectseele:nerv_structural_panel",
                    )
                    and "geofront" not in st
                ):
                    continue
                outer = abs(x - cx) == 5 or abs(z - cz) == 3
                b.put(x, ceiling, z, "smooth_quartz" if outer else "sea_lantern")
                if not outer:
                    b.put(x, ceiling - 1, z, "white_stained_glass")
    # A level inspection walk ties the three independently angled reflector stages together.
    points = [(-452, 966), (-452, 1003), (-479, 1012), (-452, 1021), (-425, 1029)]
    for (x, z), (X, Z) in zip(points, points[1:]):
        n = max(abs(X - x), abs(Z - z))
        for i in range(n + 1):
            a = round(x + (X - x) * i / n)
            c = round(z + (Z - z) * i / n)
            for u in range(a - 1, a + 2):
                for v in range(c - 1, c + 2):
                    b.put(u, 100, v, "smooth_stone")
            if i % 8 == 0:
                for y in range(99, 60, -1):
                    s = b.reader.get(a, y, c)
                    if s not in AIRS and "water" not in s:
                        break
                    b.put(a, y, c, "polished_andesite")
    # Footstairs link the quay to the existing northern bank.
    for n in range(21):
        z = 966 - n
        y = 100 - n // 2
        for x in range(-453, -450):
            ground = next(
                (
                    h
                    for h in range(y, 59, -1)
                    if "grass_block" in b.reader.get(x, h, z)
                    or "dirt" in b.reader.get(x, h, z)
                    or "stone" in b.reader.get(x, h, z)
                ),
                y - 2,
            )
            if y < ground:
                continue
            for h in range(ground + 1, y):
                b.put(x, h, z, "stone_bricks")
            b.put(x, y, z, "smooth_stone")
    b.reports["reflector_centres"] = panels
