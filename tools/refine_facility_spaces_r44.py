"""Measured second revision: service spaces, industrial services and destinations.

The first R44 floors/envelopes/belts are completed prerequisites, not overwritten
plans. This command only authors exact forward/inverse operations. Root alone
applies the world, checks native riders and approves the real shader photographs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import Counter, deque
from pathlib import Path

import nbtlib
import regional_voxels as v
from audit_facility_transit_r44 import Geometry, NORMAL
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/spatial_refinement_v3"
STRUCT = "projectseele:nerv_structural_panel"
WALL = "projectseele:nerv_wall_panel"
DATUM = "projectseele:nerv_wall_datum"
MACHINE = "projectseele:nerv_machine_panel"
EDGE = "projectseele:nerv_machine_edge"
GLASS = "projectseele:clear_glass"
FLOOR = "projectseele:nerv_floor_panel"
LIGHT = "projectseele:nerv_ceiling_light[hanging=true,lit=true]"
STORAGE = "projectseele:nerv_storage_panel[facing=south]"


class Revision:
    def __init__(self, world, out, name, lo, hi, mask, y, negatives=()):
        self.world, self.out, self.name = Path(world), Path(out), name
        if list(self.out.glob(name + "/applied_*/receipt.json")):
            raise RuntimeError("Applied refinement is immutable; use another revision directory")
        self.out.mkdir(parents=True, exist_ok=True)
        self.w = MeasuredWorld(self.world)
        self.w.box(lo, hi)
        self.w.load()
        self.tags = {q: copy.deepcopy(t) for q, t in iter_block_entities(self.world, v.DIM, lo, hi)}
        self.mask, self.y, self.negatives = mask, y, negatives
        self.changes, self.new_tags, self.tag_updates = {}, {}, {}
        self.boards, self.zones, self.cases, self.reserved = [], [], [], set()
        self.shapes = Geometry(self.w)

    def put(self, q, state, purpose):
        q = tuple(q)
        before, state = self.w.block(q), v.canonical_state(state)
        if before is None or (q[0], q[2]) not in self.mask:
            raise RuntimeError(("Unknown or outside declared component", q, before))
        if any(all(b[i] <= q[i] <= b[i + 3] for i in range(3)) for b in self.negatives):
            raise RuntimeError(("Native mechanical/door negative mask", q))
        if q in self.tags or before.startswith(("mtr:", "movingelevators:")) or before.partition("[")[0].endswith("_stairs"):
            raise RuntimeError(("Preserved complete native fixture", q, before, purpose))
        allowed = AIR | {STRUCT, WALL, GLASS, FLOOR, MACHINE, EDGE, DATUM, STORAGE.partition("[")[0],
            "projectseele:nerv_ceiling_light", "projectseele:nerv_strip_light", "projectseele:nerv_workstation",
            "minecraft:chain", "minecraft:gray_terracotta", "minecraft:cyan_terracotta", "minecraft:polished_andesite"}
        if before.partition("[")[0] not in allowed:
            raise RuntimeError(("Other component material", q, before, purpose))
        if state.partition("[")[0] not in AIR and self.shapes.boxes(state) is None:
            raise RuntimeError(("No exported native collision shape", q, state))
        if before == state:
            self.changes.pop(q, None)
        else:
            self.changes[q] = (state, purpose)

    def board(self, q, face, title, rows, *, housing=True):
        """Complete 3x2 opaque backing; header can never clip person headroom."""
        dx, dz = NORMAL[face]
        if q[1] < self.y + 2:
            raise RuntimeError(("Low overhanging board", q))
        if housing:
            for lateral in (-1, 0, 1):
                for h in (0, 1):
                    self.put((q[0] - dx + lateral * dz, q[1] + h, q[2] - dz + lateral * dx), EDGE, "complete_direction_housing")
        tag = nbtlib.Compound({"id": nbtlib.String("projectseele:station_departure_board"),
            "x": nbtlib.Int(q[0]), "y": nbtlib.Int(q[1]), "z": nbtlib.Int(q[2]),
            "Wayfinding": nbtlib.Byte(1), "Station": nbtlib.String(title), "Route": nbtlib.String("通行指引"),
            "PlatformCentre": nbtlib.Long(0), **{"Row" + str(i): nbtlib.String(t) for i, t in enumerate(rows)}})
        self.put(q, f"projectseele:station_departure_board[facing={face},wayfinding=true]", "named_destination_board")
        self.new_tags[q] = tag
        self.boards.append({"position": q, "facing": face, "title": title, "rows": rows})

    def path(self, ident, a, b):
        geometry = self.geometry()
        path = geometry.flat_path(a, b, radius=260)
        if path is None or geometry.unknown:
            raise RuntimeError(("Named access not reachable with actual collision shape", ident, a, b, sorted(geometry.unknown)))
        nodes = [[x + .5, y, z + .5] for x, y, z in path]
        self.cases.extend(({"id": ident, "path": nodes}, {"id": ident + "/return", "path": nodes[::-1]}))

    def geometry(self):
        parent = self
        class Overlay:
            world = parent.world
            def get(self, x, y, z):
                q = tuple(map(int, (x, y, z)))
                return parent.changes[q][0] if q in parent.changes else parent.w.block(q)
        return Geometry(Overlay())

    def save(self, seed):
        g = self.geometry()
        for q in sorted(self.reserved):
            if g.standing(q)["status"] != "STATIC_STANDING":
                raise RuntimeError(("Two-metre operator/customer reserved clearance obstructed", q))
        standing = {(x, self.y, z) for x, z in self.mask if g.standing((x, self.y, z))["status"] == "STATIC_STANDING"}
        if seed not in standing:
            raise RuntimeError(("Original public seed obstructed", seed))
        reached, queue = {seed}, deque([seed])
        while queue:
            a = queue.popleft()
            x, y, z = a
            for b in ((x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)):
                if b in standing and b not in reached and g.edge_clear(a, b):
                    reached.add(b)
                    queue.append(b)
        disconnected = sorted(standing - reached)
        if disconnected or g.unknown:
            raise RuntimeError(("Refinement isolates real available floors", len(disconnected), sorted(g.unknown)))
        # Every board receives a connected body approach and a real collision
        # ray to its front surface. This remains static evidence, not a text
        # legibility, live rendered-visibility or operating-device pass.
        for board in self.boards:
            q, face = board["position"], board["facing"]
            dx, dz = NORMAL[face]
            reader = None
            for d in (4, 3, 5, 2):
                a = (q[0] + d * dx, self.y, q[2] + d * dz)
                if a not in reached:
                    continue
                eye = (a[0] + .5, a[1] + 1.62, a[2] + .5)
                target = (q[0] + .5 + dx * .14, q[1] + .85, q[2] + .5 + dz * .14)
                distance = math.dist(eye, target)
                clear = True
                for k in range(max(2, math.ceil(distance * 12)) + 1):
                    t = k / max(2, math.ceil(distance * 12))
                    point = tuple(eye[i] + (target[i] - eye[i]) * t for i in range(3))
                    cell = tuple(map(math.floor, point))
                    if cell == tuple(q):
                        continue
                    boxes = g.boxes(g.world.get(*cell))
                    if boxes is None or any(all(cell[i] + b[i] + .001 < point[i] < cell[i] + b[i + 3] - .001 for i in range(3)) for b in boxes):
                        clear = False
                        break
                if clear:
                    reader = a
                    break
            if reader is None:
                raise RuntimeError(("No connected unobstructed front reader", board))
            board["reader"] = reader
            board["static_front_ray_clear"] = True
            self.path(f"r44/{self.name}/read/{q[0]}_{q[1]}_{q[2]}", seed, reader)
        p, inverse = v.Painter(), v.Painter()
        v.WORLD, v.OUT = self.world, self.out
        for box in self.negatives:
            p.protect(box, "retained_native_mechanical_component")
        for q, (after, purpose) in sorted(self.changes.items()):
            before = self.w.block(q)
            p.match((*q, *q), before, after, "r44/refinement/" + purpose)
            inverse.match((*q, *q), after, before, "inverse/r44/refinement/" + purpose)
        p.block_entities.update(copy.deepcopy(self.new_tags))
        for q, after in self.tag_updates.items():
            state, before = self.w.block(q), self.tags[q]
            p.update_block_entity(q, state, before, after, "r44/refinement/complete_existing_board_nbt")
            inverse.update_block_entity(q, state, after, before, "inverse/r44/refinement/complete_existing_board_nbt")
        contract = {"component": self.name, "cells": len(self.changes), "world": str(self.world),
            "whole_available_floor": len(standing), "whole_available_connected": len(reached), "unknown_shapes": sorted(g.unknown),
            "negative_masks": self.negatives, "zones": self.zones, "boards": self.boards,
            "old_block_entities": [{"position": q, "snbt": t.snbt()} for q, t in sorted(self.tags.items())],
            "static_operator_reserved_cells": sorted(self.reserved), "new_boards": len(self.new_tags),
            "native_cases": self.cases, "purpose_counts": dict(Counter(t[1] for t in self.changes.values())),
            "source": {"TV": "D-level original service interpretation under docs/TV_NERV_ARCHITECTURE_REFERENCE.md sections 6/8; no claim of exact TV floorplan",
                "Japan_station": "https://media.jreast.co.jp/articles/498 — named meeting/service anchor, seating outside circulation and elevator-to-destination signs",
                "technical_guidance": "https://www.mlit.go.jp/common/001255403.pdf — direction at decision points and visible reading approach"},
            "native": {k: "UNVERIFIED" for k in ("all_floor_walks", "moving_walk_motion", "NPC_interaction", "all_sign_readers", "art_shader_photos", "restart", "installed_copy")}}
        p.meta.update(contract)
        p.save_plan(self.name)
        inverse.meta.update({"forward": self.name, "cells": len(self.changes), "retained_nbt": contract["old_block_entities"]})
        inverse.save_plan("inverse_" + self.name)
        contract["forward_sha256"] = hashlib.sha256((self.out / self.name / "ops.json.gz").read_bytes()).hexdigest()
        (self.out / (self.name + "_contract.json")).write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf8")
        print(self.name, len(self.changes), "exact cells;", len(standing), "connected available floors;", len(self.cases), "native routes", flush=True)
        return p


def arrival(world=WORLD, out=OUT):
    y = -466
    hall = {(x, z) for x in range(-403, -314) for z in range(710, 742)}
    corridor = {(x, z) for x in range(-313, -304) for z in range(722, 771)}
    handoff = {(x, z) for x in range(-315, -312) for z in range(722, 731)}
    join = {(x, z) for x in range(-334, -304) for z in range(764, 773)}
    r = Revision(world, out, "arrival_service_refinement", (-405, -470, 708), (-303, -450, 774), hall | corridor | handoff | join, y,
        ((-370, -491, 741, -350, 100, 759), (-356, -466, 739, -353, -462, 741)))
    # Public side bays have a distinct wearing surface. Existing seats, MTR
    # belts, lift threshold and whole original bearing slab are retained.
    for x in range(-400, -384):
        for z in range(713, 722):
            r.put((x, y - 1, z), "minecraft:polished_andesite", "waiting_bay_finished_floor")
    for x in range(-400, -385):
        for z in range(732, 740):
            r.put((x, y - 1, z), "minecraft:gray_terracotta", "service_bay_finished_floor")
    # One supported off-route service room uses the established counter. Its
    # two-cell staff opening and low counter's open sightline stay unobstructed.
    for x in range(-399, -389):
        for z in range(733, 740):
            r.put((x, y + 4, z), STRUCT, "service_room_supported_canopy")
    for x in range(-399, -390):
        for z in (733, 739):
            if z == 733 and x in (-395, -394):
                continue
            for h in range(4):
                r.put((x, y + h, z), DATUM if h == 1 else WALL, "service_room_side_partition")
    for z in range(734, 739):
        for h in range(4):
            r.put((-399, y + h, z), GLASS if h in (1, 2) else WALL, "service_room_west_glazed_partition")
    for z in (734, 738):
        for h in (0, 1):
            r.put((-398, y + h, z), "projectseele:nerv_storage_panel[facing=east]", "service_records_and_equipment_cabinet")
    for x in (-396, -393):
        r.put((x, y + 3, 736), LIGHT, "service_task_lighting")
    r.reserved.update((x, y, z) for x in (-393, -392, -391) for z in (735, 736, 737))
    r.reserved.update((x, y, z) for x in (-389, -388) for z in (735, 736, 737))
    r.board((-390, y + 2, 733), "east", "到达服务 · 通行协助", ["警卫值勤 · 人员服务", "站台与出口见南侧导向", "台前请留出通道"], housing=False)
    # The rear board plate attaches to the complete partition at x=-391.
    for z in range(732, 735):
        for h in (2, 3):
            r.put((-391, y + h, z), WALL, "service_counter_header_backing")
    # Waiting information attaches to the north wall; no island blocks the
    # large hall, and there is no invented shop/security permission.
    r.board((-390, y + 3, 711), "south", "到达候车 · 集合点", ["稍候与会合请使用侧座", "U1 乘车 · 大厅南侧", "地面出口 · 大直梯"], housing=True)
    # Finish a narrow coloured datum around the two destination portals,
    # keeping their whole physical clearance and the protected lift call.
    for x in range(-340, -329):
        r.put((x, y + 6, 740), DATUM, "U1_portal_identity_header")
    for z in range(722, 731):
        r.put((-315, y + 6, z), DATUM, "old_east_port_identity_header")
    r.board((-360, y + 4, 736), "north", "地面出口 · 大直梯", ["↑ 地面接待层", "门外呼叫 · 轿厢内选层", "请保持门口净空"])
    # The sign housing is held to the real roof by two narrow hangers.
    for x in (-361, -359):
        for yy in range(y + 6, -453):
            r.put((x, yy, 737), "minecraft:chain[axis=y,waterlogged=false]", "lift_destination_roof_hanger")
    r.zones += [{"purpose": "Waiting and meeting bay", "bounds": [-400, y, 713, -385, y + 4, 721], "retained_seats": 4},
        {"purpose": "Single staffed arrival service room", "bounds": [-399, y, 733, -390, y + 4, 739], "fixed_guard_post": [-390.5, y, 736.5], "two_cell_opening": [-395, -394]}]
    seed = (-360, y, 735)
    for ident, q in (("service_operator", (-391, y, 736)), ("service_customer", (-389, y, 736)),
                     ("service_staff_opening", (-394, y, 734)), ("waiting_left", (-400, y, 719)),
                     ("waiting_right", (-386, y, 719)), ("old_east_port", (-315, y, 726)),
                     ("new_U1_port", (-335, y, 740)), ("old_U1_join", (-330, y, 770)),
                     ("west_north_corner", (-400, y, 713)), ("west_south_corner", (-400, y, 738)),
                     ("east_north_corner", (-318, y, 713)), ("east_south_corner", (-319, y, 737))):
        r.path("r44/refined_arrival/" + ident, seed, q)
    return r.save(seed)


def low_plant(world=WORLD, out=OUT):
    raise RuntimeError("R46 retired the complete lower service layer; use the measured retirement component, never rebuild it")
    y = -442
    gallery = {(x, z) for x in range(-43, 108) for z in range(-292, -275)}
    access = {(x, z) for x in range(99, 108) for z in range(-276, -48)}
    masks = [(cx - 20, -443, -267, cx + 20, -362, -213) for cx in (-12, 30, 72)]
    masks += [(cx - 20, -446, -56, cx + 20, 100, -16) for cx in (-12, 30, 72)]
    masks += [(89, -446, -56, 98, -364, -48)]
    r = Revision(world, out, "low_service_refinement", (-45, -448, -294), (113, -435, -32), gallery | access, y, tuple(masks))
    # Personnel route remains two unobstructed fixed lanes + the original two
    # full-width MTR belts. Services use the east pressure wall and its top.
    for z in range(-275, -49):
        for h in (1, 2):
            r.put((107, y + h, z), WALL if h == 1 else DATUM, "east_service_pressure_wall")
        r.put((106, y + 3, z), EDGE, "high_level_ventilation_and_cable_tray")
        if z % 16 == 0:
            r.put((106, y + 4, z), STRUCT, "duct_roof_clamp")
    # Three specific service panels live within the wall; none consumes a belt
    # or a pedestal on the central pedestrian route. Their furnished cabinets
    # are static architecture, and do not claim simulated power/ventilation.
    for z, purpose in ((-230, "机库支线"), (-166, "移送区侧廊"), (-102, "发射区接驳")):
        for zz in (z - 1, z, z + 1):
            for h in (0, 1, 2):
                r.put((107, y + h, zz), MACHINE if zz != z else "projectseele:nerv_storage_panel[facing=west]", "enclosed_corridor_service_cabinet")
        for zz in range(z - 3, z + 4):
            r.put((103, y - 1, zz), "minecraft:gray_terracotta", "pedestrian_zone_floor_datum")
        r.zones.append({"purpose": purpose + "检修柜", "wall": [107, y, z], "pedestrian_clear": [102, y, z - 3, 103, y + 2, z + 3]})
    # A pair of signs reads from each travel direction. All 3x2 housings begin
    # three metres above the floor, reach the roof, and have real end goals.
    for z in (-240, -172, -104):
        r.board((103, y + 3, z - 1), "north", "发射区层站 · 南行", ["↑ 发射区车站／层站电梯", "机库上层：在层站换乘", "固定步行道在中间"])
        r.board((103, y + 3, z + 1), "south", "机库低位整备 · 北行", ["↑ EVA 00／01／02 检修厅", "器材与巡检记录在北端", "固定步行道在中间"])
    # Three small working bays occupy only the existing north public slab,
    # never wet-vessel pits, transfer clear cores or original portal columns.
    for index, cx in enumerate((-12, 30, 72)):
        for x in range(cx - 4, cx + 5):
            for z in range(-291, -284):
                r.put((x, y - 1, z), "minecraft:gray_terracotta", "low_service_room_floor")
                r.put((x, y + 3, z), STRUCT, "low_service_room_supported_roof")
        for x in range(cx - 4, cx + 5):
            for h in (0, 1, 2):
                r.put((x, y + h, -291), WALL, "service_room_rear_wall")
                if x not in (cx, cx + 1):
                    r.put((x, y + h, -285), GLASS if h in (1, 2) and abs(x - cx) > 1 else WALL, "service_room_front_window")
        for z in range(-290, -285):
            for x in (cx - 4, cx + 4):
                for h in (0, 1, 2):
                    r.put((x, y + h, z), WALL if h != 1 else DATUM, "service_room_side_wall")
        for h in (0, 1):
            r.put((cx - 3, y + h, -290), STORAGE, "restricted_room_equipment_cabinet")
        r.put((cx - 2, y, -289), MACHINE, "inspection_record_workbench")
        r.put((cx - 2, y + 1, -289), "projectseele:nerv_workstation[facing=south]", "static_CRT_record_furnishing")
        r.put((cx + 2, y + 2, -288), LIGHT, "inspection_bay_task_light")
        r.board((cx, y + 3, -284), "south", f"低位整备 · EVA 0{index}", ["器材与巡检记录", "湿式机库与机械坑请按指引", "登机层：南侧电梯换乘"])
        r.reserved.update((x, y, z) for x in range(cx - 2, cx + 2) for z in (-288, -287, -286))
        r.zones.append({"purpose": f"EVA 0{index} low-level inspection record/equipment bay", "bounds": [cx - 4, y, -291, cx + 4, y + 3, -285], "two_cell_opening": [cx, cx + 1], "simulated_controls": False})
    # One continuous conduit on the room side of the north gallery connects
    # all three service bays; the open south glass preserves machine views.
    for x in range(-42, 107):
        r.put((x, y + 4, -278), EDGE, "north_gallery_high_service_tray")
        if x % 14 == 0:
            r.put((x, y + 3, -278), LIGHT, "gallery_side_task_lighting")
    # The longitudinal duct turns into the gallery tray, rather than ending
    # in open air at a different height. Wall/roof clamps carry both sections.
    for z in (-278, -277, -276):
        r.put((106, y + 3, z), EDGE, "continuous_duct_turn_into_gallery")
    seed = (103, y, -50)
    for ident, q in (("north_west", (-40, y, -289)), ("north_east", (104, y, -289)),
                     ("south_west", (-40, y, -278)), ("south_east", (104, y, -278))):
        r.path("r44/refined_low_plant/" + ident, seed, q)
    for index, cx in enumerate((-12, 30, 72)):
        for suffix, q in (("entry", (cx, y, -286)), ("workbench", (cx - 2, y, -288)), ("interior_far_corner", (cx + 3, y, -290))):
            r.path(f"r44/refined_low_plant/bay{index}/" + suffix, seed, q)
    for x in (102, 103):
        r.path(f"r44/refined_low_plant/fixed_lane{x}", (x, y, -50), (x, y, -274))
    # Real belt cases remain requirements, not static geometry passes.
    for first, travel in ((100, "northbound"), (104, "southbound")):
        for lane in (0, 1):
            a, b = [first + lane + .5, y, -55.5], [first + lane + .5, y, -273.5]
            if travel == "southbound":
                a, b = b, a
            r.cases.append({"id": f"r44/refined_low_plant/MTR/{travel}/lane{lane}", "path": [a, b], "requires_real_passenger_transport": True})
    return r.save(seed)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--world", type=Path, default=WORLD)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--part", choices=("arrival",), default="arrival")
    a = p.parse_args()
    if a.part == "arrival":
        arrival(a.world, a.out)
