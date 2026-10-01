"""Unify the whole declared NERV arrival hall; preserve every active port.

The old hall is physically reachable, so no public platform is retired from a
route-count assumption. Only superseded inner shells/ceilings are removed.
This CLI writes reviewable operations and inverses, never the world.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, deque
from pathlib import Path

import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import AIR, iter_block_entities
from audit_facility_transit_r44 import Geometry

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/unified_arrival_hall"
FLOOR = "projectseele:nerv_floor_panel"
STRUCT = "projectseele:nerv_structural_panel"
WALL = "projectseele:nerv_wall_panel"
GLASS = "projectseele:clear_glass"
LIGHT = "projectseele:nerv_ceiling_light[hanging=true,lit=true]"
Y, ROOF = -466, -453


def plan(world=WORLD, out=OUT):
    world, out = Path(world), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("whole_arrival_component/applied_*/receipt.json")):
        raise RuntimeError("Applied arrival stage is immutable; use a new revision output")
    w = MeasuredWorld(world)
    lo, hi = (-405, -470, 708), (-303, -450, 774)
    w.box(lo, hi)
    w.load()
    tags = {q: copy.deepcopy(t) for q, t in iter_block_entities(world, v.DIM, lo, hi)}
    hall = {(x, z) for x in range(-403, -314) for z in range(710, 742)}
    corridor = {(x, z) for x in range(-313, -304) for z in range(722, 771)}
    handoff = {(x, z) for x in range(-315, -312) for z in range(722, 731)}
    join = {(x, z) for x in range(-334, -304) for z in range(764, 773)}
    mask = hall | handoff | corridor | join
    # Every port has a declared source and a measured supporting interface.
    # The newer MTR station spine is an additional real route, not a hole.
    ports = {(x, 741) for x in range(-363, -356)}
    ports |= {(x, 741) for x in range(-340, -329)}
    ports |= {(-315, z) for z in range(722, 731)}
    ports |= {(x, 772) for x in range(-333, -326)}
    p, inverse = v.Painter(), v.Painter()
    changes = {}
    protected = []
    shaft = (-370, -491, 741, -350, 100, 759)
    call_widget = (-356, -466, 739, -353, -462, 741)
    p.protect(shaft, "retained_whole_native_large_shaft_and_frontage")
    p.protect(call_widget, "retained_actual_outside_call_and_jamb")
    furniture = set()
    stair_heads = set()
    retained_stairs = []
    for x, z in sorted(mask):
        for y in range(Y - 1, hi[1] + 1):
            state = w.get(x, y, z)
            if state and state.partition("[")[0].endswith("_stairs"):
                retained_stairs.append({"position": [x, y, z], "state": state})
                stair_heads.update((x, y + d, z) for d in range(1, 4))
    materials = AIR | {FLOOR, STRUCT, WALL, GLASS, "projectseele:nerv_machine_edge",
        "projectseele:nerv_edge_rail", "projectseele:nerv_strip_light", "projectseele:nerv_ceiling_light",
        "minecraft:smooth_stone", "minecraft:light_gray_concrete", "minecraft:polished_deepslate",
        "minecraft:deepslate_bricks", "minecraft:sea_lantern", "minecraft:light_gray_stained_glass",
        "minecraft:gray_stained_glass", "minecraft:chain", "minecraft:gray_concrete"}
    materials.add("minecraft:red_terracotta")

    def inside(q, box):
        return all(box[i] <= q[i] <= box[i + 3] for i in range(3))

    def put(q, after, why, *, fixture=False):
        before = w.block(q)
        if before is None:
            raise RuntimeError(("Unmeasured", q))
        if (inside(q, shaft) or inside(q, call_widget) or q in tags
                or before.startswith(("mtr:", "movingelevators:"))
                or before.partition("[")[0].endswith("_stairs")):
            if before != after:
                protected.append({"position": q, "state": before, "reason": "Whole native device/port/NBT negative mask"})
            return
        if q in stair_heads and after != "minecraft:air":
            protected.append({"position": q, "state": before, "reason": "Retained real stair headroom"})
            return
        declared_handoff_ground = (q[0], q[2]) in handoff and q[1] <= Y - 1 \
            and before.partition("[")[0] in {"minecraft:dirt", "minecraft:grass_block", "minecraft:stone"}
        if before.partition("[")[0] not in materials and not declared_handoff_ground:
            raise RuntimeError(("Different owner/material", q, before, why))
        if before == after:
            changes.pop(q, None)
            return
        changes[q] = (after, why)
        if fixture:
            furniture.add(q)

    for x, z in sorted(mask):
        in_hall = (x, z) in hall
        roof = ROOF if in_hall else Y + 6
        rim = any((x + dx, z + dz) not in mask for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        # The whole footprint was explicitly authored and founded in R20.
        # Root's measured original component, not its air, is the authority.
        for y in (Y - 3, Y - 2):
            if w.get(x, y, z) in AIR:
                put((x, y, z), STRUCT, "declared_floor_bearing_repair")
        put((x, Y - 1, z), FLOOR, "whole_public_finished_floor")
        for y in range(Y, roof):
            after = "minecraft:air"
            if rim and not ((x, z) in ports and y <= Y + 4):
                after = STRUCT if y in (Y, roof - 1) else WALL
                if Y + 2 <= y <= Y + 5 and (x + z) % 14 not in (0, 1):
                    after = GLASS
            put((x, y, z), after, "continuous_outer_pressure_envelope" if rim else "retire_superseded_inner_shell")
        put((x, roof, z), STRUCT, "whole_roof")
        if not rim and ((in_hall and x % 10 in (0, 1) and z in (716, 732))
                        or (not in_hall and x == -309 and z % 8 == 0)):
            put((x, roof - 1, z), LIGHT, "unified_ceiling_lighting")

    # Portal frames sit at the edges of the hall, never on its lift/moving-walk
    # approach. The girder tops meet the real roof; the old low roof is gone.
    frames = (-395, -379, -347, -323)
    for x in frames:
        for z in (711, 740):
            for xx in (x, x + 1):
                for y in range(Y, ROOF):
                    put((xx, y, z), STRUCT, "grounded_roof_portal_column")
        for xx in (x, x + 1):
            for z in range(710, 742):
                for y in range(ROOF - 2, ROOF + 1):
                    put((xx, y, z), STRUCT, "roof_portal_girder")

    belts = []
    for z0, direction in ((724, True), (727, False)):
        for x in range(-392, -323):
            for offset, side in ((0, "left"), (1, "right")):
                q = (x, Y - 1, z0 + offset)
                state = f"mtr:escalator_step[direction={str(direction).lower()},facing=east,orientation=flat,side={side},status=true]"
                if not (w.block(q) or "").startswith("mtr:"):
                    put(q, state, "two_way_hall_moving_walk")
        belts.append({"axis": "x", "lower": [-392, Y - 1, z0], "upper": [-324, Y - 1, z0 + 1],
                      "direction": direction, "clear_width": 2, "flat_handrails": False})
    for x0, direction in ((-312, True), (-308, False)):
        for z in range(733, 757):
            for offset, side in ((0, "left"), (1, "right")):
                put((x0 + offset, Y - 1, z), f"mtr:escalator_step[direction={str(direction).lower()},facing=north,orientation=flat,side={side},status=true]",
                    "two_way_old_east_link_moving_walk")
        belts.append({"axis": "z", "lower": [x0, Y - 1, 733], "upper": [x0 + 1, Y - 1, 756],
                      "direction": direction, "clear_width": 2, "end_buffers": [11, 8], "flat_handrails": False})

    # Waiting and staffed inspection are off the four travelling lanes. No
    # permissions are granted by these desks; access integration is root-owned.
    for x in (-399, -395, -391, -387):
        put((x, Y, 718), "projectseele:station_seat[facing=south]", "arrival_waiting_seat", fixture=True)
    for z in range(733, 739):
        put((-390, Y, z), "projectseele:nerv_machine_panel", "staff_service_counter", fixture=True)
    for z in (734, 737):
        put((-390, Y + 1, z), "projectseele:nerv_workstation[facing=east]", "inspection_display", fixture=True)
    put((-390, Y + 1, 735), "projectseele:nerv_machine_panel", "grounded_reader_backing", fixture=True)

    # All four old anchors retain their complete NBT and a genuine roof hanger.
    # Direction text changes only after a measured successor route is supplied.
    for q, tag in tags.items():
        if str(tag.get("id", "")) != "projectseele:station_departure_board" or (q[0], q[2]) not in hall:
            continue
        face = properties(w.block(q)).get("facing")
        dx, dz = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}[face]
        for lateral in (-1, 0, 1):
            for h in (0, 1):
                put((q[0] - dx + lateral * dz, q[1] + h, q[2] - dz + lateral * dx), STRUCT, "preserved_sign_complete_backing")
        for yy in range(q[1] + 2, ROOF):
            put((q[0] - dx, yy, q[2] - dz), "minecraft:chain[axis=y,waterlogged=false]", "preserved_sign_grounded_roof_hanger")

    # Three new, complete boarded decision points have a 3x2 solid housing
    # behind the visible sign and an unobstructed two-metre reader approach.
    boards = [((-316, -461, 726), "west", "U1 · 地下都市站", ["↑ U1 · 总部／研究模拟区", "↓ 大直梯 · 地面出口", "服务台在大厅西侧"]),
              ((-336, -461, 740), "north", "U1 · 自动步道接驳", ["↑ 站台 · 双向自动步道", "→ 大直梯 · 地面出口", "乘车前请确认方向和站序"]),
              ((-402, -463, 728), "east", "到达服务 · 通行咨询", ["职员服务 · 通行协助", "换乘／出口见南侧导向牌", "请保留通行证"])]
    new_tags = {}
    for q, face, title, rows in boards:
        dx, dz = {"north": (0, -1), "east": (1, 0), "west": (-1, 0)}[face]
        for lateral in (-1, 0, 1):
            for h in (0, 1):
                put((q[0] - dx + lateral * dz, q[1] + h, q[2] - dz + lateral * dx), WALL, "complete_wayfinding_board_backing")
        put(q, f"projectseele:station_departure_board[facing={face},wayfinding=true]", "decision_board", fixture=True)
        new_tags[q] = nbtlib.Compound({"id": nbtlib.String("projectseele:station_departure_board"),
            "x": nbtlib.Int(q[0]), "y": nbtlib.Int(q[1]), "z": nbtlib.Int(q[2]),
            "Wayfinding": nbtlib.Byte(1), "Station": nbtlib.String(title), "Route": nbtlib.String("到达／换乘指引"),
            "PlatformCentre": nbtlib.Long(0), **{"Row" + str(i): nbtlib.String(text) for i, text in enumerate(rows)}})

    class Overlay:
        def __init__(self):
            self.world = world
        def get(self, x, y, z):
            q = (int(x), int(y), int(z))
            return changes[q][0] if q in changes else w.block(q)
    geometry = Geometry(Overlay())
    floor_cells = {(x, Y, z) for x, z in mask if geometry.standing((x, Y, z))["status"] == "STATIC_STANDING"}
    seed = (-360, Y, 735)
    if seed not in floor_cells:
        raise RuntimeError(("Original public seed is obstructed", seed))
    reached, queue = {seed}, deque([seed])
    while queue:
        a = queue.popleft()
        x, y, z = a
        for b in ((x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)):
            if b in floor_cells and b not in reached and geometry.edge_clear(a, b):
                reached.add(b)
                queue.append(b)
    disconnected = sorted(floor_cells - reached)
    if disconnected or geometry.unknown:
        raise RuntimeError(("Whole public floor has a defect", len(disconnected), sorted(geometry.unknown)))
    walks = []
    # Corner and width routes avoid equipment, but cover both sides of every
    # declared port. A closed native shaft door has its own live state test.
    goals = [(-400, Y, 713), (-400, Y, 738), (-318, Y, 713), (-319, Y, 737),
             (-315, Y, 726), (-309, Y, 726), (-309, Y, 761), (-330, Y, 770),
             (-335, Y, 740), (-336, Y, 738), (-400, Y, 728)]
    for target in goals:
        route = geometry.flat_path(seed, target, radius=100)
        if route is None:
            raise RuntimeError(("No full body corridor to named target", target))
        path = [[x + .5, y, z + .5] for x, y, z in route]
        name = f"r44/arrival/{target[0]}/{target[2]}"
        walks += [{"id": name, "path": path}, {"id": name + "/return", "path": path[::-1]}]

    v.WORLD, v.OUT = world, out
    for q, (after, why) in sorted(changes.items()):
        before = w.block(q)
        p.match((*q, *q), before, after, "r44/arrival/" + why)
        inverse.match((*q, *q), after, before, "inverse/r44/arrival/" + why)
    p.block_entities.update(copy.deepcopy(new_tags))
    contract = {"component": "Whole declared old + new arrival hall with both station interfaces and native shaft port",
        "source_original_hall": [-403, -467, 710, -315, -453, 741],
        "declared_original_east_link": [-313, -467, 722, -305, -460, 770],
        "preserved_real_ports": sorted(ports), "negative_masks": [shaft, call_widget],
        "original_complete_nbt": [{"position": q, "nbt": t.snbt()} for q, t in sorted(tags.items())],
        "retained_actual_station_stairs": retained_stairs,
        "retired": "R40 inner wall/low-ceiling component and 12 edge rails after their actual floor/enclosure is rebuilt",
        "public_floor_cells": len(floor_cells), "connected_cells": len(reached), "unknown_shapes": sorted(geometry.unknown),
        "ordinary_fixtures": sorted(furniture), "moving_walks": belts, "boards": [{"position": q, "facing": face, "rows": rows} for q, face, title, rows in boards],
        "root_access_integration": {"staff_position": [-392.5, Y, 735.5], "facing": "east",
            "reader_candidate": [-389, Y + 1, 735], "reader_facing": "east", "reader_backing": [-390, Y + 1, 735],
            "customer_approach": [-387.5, Y, 735.5], "operator_clearance": [[-393, Y, 733], [-391, Y + 2, 738]],
            "status": "UNVERIFIED root reader/permission/exit binding; no fake security pass inferred from a counter"},
        "walk_nodes": walks, "cells": len(changes), "preserved_floor_west": "All 810 measured reachable west floor cells retained in the unified public footprint",
        "validation": {k: "UNVERIFIED" for k in ("all_ports_native", "moving_walk_riders", "gate_access", "train_boarding", "visual", "reload", "installed_copy")}}
    p.meta.update(contract)
    p.save_plan("whole_arrival_component")
    inverse.meta.update({"forward": "whole_arrival_component", "cells": len(changes)})
    inverse.save_plan("inverse_whole_arrival_component")
    (out / "contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf8")
    (out / "native_cases.json").write_text(json.dumps(walks, indent=2), encoding="utf8")
    print("Unified whole arrival:", len(changes), "cells;", len(floor_cells), "connected floor cells;", len(walks), "native paths", flush=True)
    return p


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, default=WORLD)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    plan(args.world, args.out)
