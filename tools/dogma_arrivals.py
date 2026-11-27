"""Measure dry personnel arrivals on the installed geometry, in both interlock positions."""

import json
import math
from dogma_recommission import AIRS
from map_buildings.mca import World
from write_deep_cells import REGION


def arrivals(world, authority, emergency):
    current = World(world / REGION)
    external = World(authority / REGION)
    open_world = World(emergency / REGION)
    path = world / "r52/travel.json"
    doc = json.loads(path.read_bytes())
    rows = {e["key"]: e for e in doc["destinations"]}
    for key, label, x, y, z, yaw in [
        ("port", "港区 · 海上作战平台", 1519, 65, 771, 180),
        ("dogma", "终极教条 · 天堂之门步行入口", -3, -1230, 246, -90),
        ("sub_terminal", "第二发令所 · 指挥席", 252, -460, 332, 0),
        ("rei_lab", "第一实验室 · 402 室复原", -27, -1230, 198, -90),
        ("eva_graveyard", "EVA 墓场 · LCL 池边", -32, -1230, 164, 90),
        ("dummy_plant", "模拟人格工厂 · 控制台", -11, -1230, 119, 180),
        ("lilith", "天堂之门 · 莉莉丝侧面观景台", 8, -1255, 309, -25),
        ("climb_gate", "机库 · 冬月紧急通道门前", 84, -1051, 242, -90),
        ("geofront_hatch", "GeoFront · 隐蔽井口外侧", 165, -466, 188, 90),
        ("lake_mirrors", "芦之湖 · 地下采光镜群", -452, 101, 1004, 0),
    ]:
        previous = rows.get(key, {})
        rows[key] = dict(
            **{
                **previous,
                "key": key,
                "component": previous.get("component", key),
                "entry_id": "survey/" + key,
                "position": [x + 0.5, y, z + 0.5],
                "yaw": yaw,
                "label": label,
            }
        )

    def cells(w, x, y, z):
        return [
            dict(position=[x, y + h, z], state=w.get(x, y + h, z)) for h in (-1, 0, 1)
        ]

    def dry(v):
        s, f, h = [c["state"] for c in v]
        return bool(
            s
            and s not in AIRS
            and not any(
                k in s
                for k in (
                    "water",
                    "lcl",
                    "_leaves",
                    "_sign",
                    "_door",
                    "button",
                    "light[",
                )
            )
            and f in AIRS
            and h in AIRS
        )

    for row in rows.values():
        request = row["position"]
        x, y, z = map(math.floor, request)
        w = current if current.get(x, y, z) is not None else external
        other = (
            open_world
            if open_world.get(x, y, z) is not None
            and row["key"]
            in (
                "dogma",
                "climb_gate",
                "geofront_hatch",
                "lilith",
                "dummy_plant",
                "rei_lab",
                "eva_graveyard",
            )
            else w
        )
        # Respect the original story destination, floor and heading. Check the nearest walkable cell before
        # changing any endpoint; an unexpected failure needs an explicit new surveyed point.
        offsets = sorted(
            (
                (dx, dy, dz)
                for dx in range(-5, 6)
                for dz in range(-5, 6)
                for dy in (0, 1, -1, 2, -2)
            ),
            key=lambda p: abs(p[0]) + abs(p[2]) + 3 * abs(p[1]),
        )
        for dx, dy, dz in offsets:
            at = x + dx, y + dy, z + dz
            v = cells(w, *at)
            if dry(v) and dry(cells(other, *at)):
                break
        else:
            raise ValueError(
                ("no surveyed arrival", row["key"], request, cells(w, x, y, z))
            )
        row["requested_position"] = request
        if any((dx, dy, dz)):
            row["position"] = [at[0] + 0.5, at[1], at[2] + 0.5]
        row["actual_cells"] = v
    doc["destinations"] = list(rows.values())
    doc["measured"] = True
    doc["native_verified"] = False
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf8")
    return [(r["key"], r["position"]) for r in rows.values()]
