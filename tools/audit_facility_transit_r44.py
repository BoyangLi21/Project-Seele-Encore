"""Read-only R44 facility/transport ledger with complete object denominators.

Exact save reads stay in query_blocks/MeasuredWorld. Static geometry is never
promoted to a successful live boarding, a working call, or a lifecycle pass.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict, deque
from pathlib import Path

from measure_world_r40 import MeasuredWorld, properties
from query_blocks import AIR, iter_block_entities
from regional_voxels import canonical_state

ROOT = Path(__file__).resolve().parents[1]
ART43 = ROOT / "artifacts/repair_r43"
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44"
NORMAL = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
STAGES = ("outside_call", "wait", "door_open", "threshold_cross", "ride",
          "arrive", "exit", "return", "same_jvm_reload", "cold_reload")

# These axes/exit normals come from installed runtime specs, not controller
# facing (which describes the fixed shaft wall, not the passenger doorway).
LIFT_GEOMETRY = {
    (-368, 750): (-360, 750, "north", "RegionalGatewayDirector"),
    (-26, -278): (-29, -278, "north", "FacilityLiftsR25.OBSERVATION"),
    (9, 253): (12, 253, "south", "S20PhysicalElevatorDirector.commandRearLift"),
    (31, 321): (28, 321, "north", "S20PhysicalElevatorDirector.commanderOfficeLift"),
    (63, 302): (66, 302, "south", "FacilityLiftsR25.EAST / installed R26 manifest"),
    (96, -52): (93, -52, "south", "RegionalFacilityLayout / oldCommandToCompactCageLift"),
    (130, 269): (130, 273, "west", "S20PhysicalElevatorDirector.surfaceTransitLift"),
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review():
    return {k: "UNVERIFIED" for k in ("function", "fresh_native", "visual",
                                      "user_approved", "lifecycle", "installed_copy")}


class Geometry:
    def __init__(self, world):
        self.world = world
        self.shapes = {canonical_state(k): v for k, v in
                       read(world.world / "native_collision_shapes.json").items()}
        self.unknown = set()

    def boxes(self, state):
        if state is None:
            return None
        if state.partition("[")[0] in AIR | {"minecraft:light"}:
            return []
        if state not in self.shapes:
            self.unknown.add(state)
            return None
        return self.shapes[state]

    def standing(self, q):
        x, y, z = q
        states = [self.world.get(x, y + dy, z) for dy in (-1, 0, 1)]
        boxes = [self.boxes(s) for s in states]
        if any(b is None for b in boxes):
            return {"position": q, "states": states, "status": "UNKNOWN"}
        # All nine points on the player's footprint need full-datum bearing;
        # one iron-bar collision box is not a supporting floor.
        top = .9375 if states[0] and states[0].startswith("mtr:escalator_step[") \
            and properties(states[0]).get("orientation") == "flat" else 1.
        bearing = all(any(b[0] <= a <= b[3] and b[2] <= c <= b[5]
                          and abs(b[4] - top) <= .001 for b in boxes[0])
                      for a in (.2, .5, .8) for c in (.2, .5, .8))
        clear = all(not any(b[0] < .8 and b[3] > .2 and b[2] < .8 and b[5] > .2
                            and b[1] < height and b[4] > .001 for b in row)
                    for row, height in zip(boxes[1:], (1., .8)))
        if not bearing and clear and states[0] and states[0].partition("[")[0].endswith("_stairs"):
            return {"position": q, "states": states, "status": "SHAPED_STAIR_INTERFACE",
                    "measured_standing_y": None, "requires_native_stair_motion": True}
        return {"position": q, "states": states, "measured_standing_y": y - 1 + top,
                "status": "STATIC_STANDING" if bearing and clear else
                          "OBSERVED_OBSTRUCTION" if bearing else "NO_BEARING"}

    def edge_clear(self, a, b):
        x, y, z = a
        dx, _, dz = tuple(q - p for p, q in zip(a, b))
        low = (x + .2 + min(0, dx), y, z + .2 + min(0, dz))
        high = (x + .8 + max(0, dx), y + 1.8, z + .8 + max(0, dz))
        for X in range(math.floor(low[0]), math.floor(high[0]) + 1):
            for Z in range(math.floor(low[2]), math.floor(high[2]) + 1):
                for Y in range(math.floor(low[1]), math.floor(high[1]) + 1):
                    boxes = self.boxes(self.world.get(X, Y, Z))
                    if boxes is None:
                        return False
                    if any(X + box[0] < high[0] and X + box[3] > low[0]
                           and Y + box[1] < high[1] and Y + box[4] > low[1]
                           and Z + box[2] < high[2] and Z + box[5] > low[2] for box in boxes):
                        return False
        return True

    def flat_path(self, start, finish, radius=12):
        start, finish = tuple(start), tuple(finish)
        if self.standing(start)["status"] != "STATIC_STANDING" or self.standing(finish)["status"] != "STATIC_STANDING":
            return None
        queue, previous = deque([start]), {start: None}
        while queue:
            current = queue.popleft()
            if current == finish:
                route = []
                while current is not None:
                    route.append(current)
                    current = previous[current]
                route.reverse()
                return route
            x, y, z = current
            for q in ((x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)):
                if q in previous or abs(q[0] - start[0]) > radius or abs(q[2] - start[2]) > radius:
                    continue
                if self.standing(q)["status"] == "STATIC_STANDING" and self.edge_clear(current, q):
                    previous[q] = current
                    queue.append(q)
        return None


def classify_component(c):
    lo, hi = c["bounds"]
    if lo[2] >= 350 and hi[2] <= 362 and lo[0] >= 62 and hi[0] <= 71:
        return "east_stair_vestibule", "R43 four complete stair-core vestibules; R44 framed portals"
    if lo[0] >= 65 and hi[0] <= 67 and lo[2] == hi[2] == 305:
        return "lift_threshold_dynamic", "R26 east lift south doorway/cabin sweep; closed door is not an isolated room"
    if lo[0] >= 182 and hi[0] <= 340 and lo[2] >= 94 and hi[2] <= 290:
        return "armament_service_interface", "Authored armament/rail intersection; all station and device states still require native review"
    if c["component"] == 4431:
        return "hangar_lower_service_apron", "Authored perimeter around wet cages; fixed outer access and enclosure require repair"
    if c["component"] in (4410, 4415):
        return "launch_well_service_apron", "R16 three launch shells; public floor stays outside the 31x31 EVA/pallet sweeps"
    if -44 <= lo[0] and hi[0] <= 108 and -294 <= lo[2] and hi[2] <= -18:
        if lo[1] >= -395 and hi[2] <= -198:
            return "hangar_machine_shell_or_gantry", "Three wet-cage shell/gantry owner volumes; machinery is not a public room"
        if lo[2] >= -212 and hi[2] <= -50 and -447 <= lo[1] <= -411:
            return "eva_carrier_ramp_and_shoulder", "Retained three graded carrier lines from -443 cages to -411 launch beds"
        return "plant_fixed_machine_component", "Installed cage/launch structural owner; no permission to fill from floor material"
    return "UNRESOLVED", "Owner/use not established by the installed mechanical or personnel specifications"


def main(world=WORLD, out=OUT):
    world, out = Path(world), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    catalogue = read(ART43 / "facility_catalogue/catalogue.json")
    native = read(ART43 / "transit_resolved/native_snapshot.json")
    unreachable = read(ART43 / "navigation/unreachable_authored_components.json")
    cases = read(world / "quality_walk_cases.json")
    platform_station = {p["id"]: s["id"] for s in catalogue["stations"] for p in s["platforms"]}

    w = MeasuredWorld(world)
    for c in unreachable:
        lo, hi = c["bounds"]
        w.box(tuple(q - 1 for q in lo), tuple(q + 1 for q in hi))
    for lift in catalogue["lifts"]:
        for landing in lift["landings"]:
            w.around(landing["controller"], 18)
    # Registered station paths are evidence of intended use. Full-width and
    # dynamic interfaces have independent ledgers below.
    station_paths = defaultdict(list)
    for case in cases:
        tokens = case["id"].split("/")
        if case["id"].startswith("r23/station/") and len(tokens) >= 4:
            sid = platform_station.get(tokens[2])
            if sid:
                station_paths[sid].append(case)
                for q in case.get("path", []):
                    w.around(q, 3)
    w.load()
    geom = Geometry(w)
    tags = {}
    for lift in catalogue["lifts"]:
        for landing in lift["landings"]:
            q = landing["controller"]
            tags.update((p, copy.deepcopy(t)) for p, t in iter_block_entities(
                world, lift["dimension"], tuple(v - 18 for v in q), tuple(v + 18 for v in q)))

    components = []
    for c in unreachable:
        kind, basis = classify_component(c)
        changed = 0
        observed = Counter()
        for r in c["rows"]:
            x, y, z = r["pos"]
            observed[geom.standing((x, y, z))["status"]] += 1
            changed += w.get(x, y - 1, z) != canonical_state(r["floor"])
        components.append({k: v for k, v in c.items() if k != "rows"} | {
            "classification": kind, "basis": basis, "measured_standing_states": dict(observed),
            "floor_changed_since_R43_discovery": changed, "review": review(),
            "acceptance": "Classification only; no public-route or device lifecycle pass"})

    lifts, walk_cases, lifecycle_cases = [], [], []
    for lift in catalogue["lifts"]:
        key = tuple(lift["controller_column"])
        cx, cz, ordinary_exit, source = LIFT_GEOMETRY[key]
        landings = []
        for source_landing in lift["landings"]:
            controller = tuple(source_landing["controller"])
            y = controller[1]
            face = "north" if key == (96, -52) and y == -370 else ordinary_exit
            dx, dz = NORMAL[face]
            lx, lz = -dz, dx
            approach_y = -369 if key == (96, -52) and y == -370 else y
            if key == (-368, 750):
                call = (-355, y + 1, 740)
                reader = (-355, y, 738)
                handoff = (-360, y, 738)
                plane = (-360, y, 741)
            else:
                call = (cx + 5 * dx + 3 * lx, y + 1, cz + 5 * dz + 3 * lz)
                reader = (cx + 5 * dx + 2 * lx, approach_y, cz + 5 * dz + 2 * lz)
                handoff = (cx + 7 * dx, approach_y, cz + 7 * dz)
                plane = (cx + 4 * dx, y, cz + 4 * dz)
            legacy_call = call
            if key == (63, 302):
                # R44 moves the complete ordinary exterior call/backing to
                # the public side of the west glass wall. Detect the measured
                # commissioned button, not merely its template declaration.
                commissioned = (65, y + 1, 308)
                measured = w.block(commissioned)
                if measured and measured.partition("[")[0] in {"minecraft:stone_button", "minecraft:polished_blackstone_button"} and properties(measured).get("facing") == "east":
                    call, reader = commissioned, (66, approach_y, 309)
            intended_handoff = handoff
            if geom.standing(handoff)["status"] == "SHAPED_STAIR_INTERFACE":
                # The commissioned office threshold joins a real stair. Use
                # its existing flat landing for an outside-call seed; keep the
                # stair separately in the full exit/lifecycle requirement.
                choices = [(handoff[0] + a, approach_y, handoff[2] + b)
                           for a, b in ((0, -1), (0, 1), (-1, 0), (1, 0))]
                handoff = next((q for q in choices if geom.standing(q)["status"] == "STATIC_STANDING"), handoff)
            face_vector = NORMAL.get(properties(w.block(call) or "").get("facing"), (dx, dz))
            candidate_readers = [reader] + [(call[0] + face_vector[0] * d, approach_y,
                                             call[2] + face_vector[1] * d) for d in (1, 2, 3)]
            approach_path = None
            for point in candidate_readers:
                route = geom.flat_path(handoff, point)
                if route is not None:
                    reader, approach_path = point, route
                    break
            actual_tag = tags.get(controller)
            hardware = [{"position": p, "id": str(t.get("id", "")), "nbt": t.snbt()}
                        for p, t in tags.items() if str(t.get("id", "")).startswith("movingelevators:")
                        and abs(p[0] - controller[0]) <= 20 and abs(p[2] - controller[2]) <= 20
                        and abs(p[1] - y) <= 3]
            probes = [geom.standing(reader), geom.standing(handoff)]
            for lane in (-1, 0, 1):
                probes.append(geom.standing((handoff[0] + lane * lx, approach_y,
                                             handoff[2] + lane * lz)))
            # Calls and panels are different blocks. A missing legacy button
            # is not a missing interface if the linked native remote is present.
            linked = [h for h in hardware if h["id"] == "movingelevators:button_tile"
                      and tuple(int(tags[tuple(h["position"])].get("data", {}).get("controller" + a, -9999))
                                for a in ("X", "Y", "Z")) == controller]
            status = "STATIC_INTERFACE_CANDIDATE" if actual_tag is not None else "MISSING_CONTROLLER"
            landing = {"controller": controller, "controller_nbt": actual_tag.snbt() if actual_tag else None,
                       "cabin_centre": [cx, y, cz], "exit": face, "approach_y": approach_y,
                       "door_plane": plane, "legacy_call": legacy_call, "outside_call": call, "reader": reader, "handoff": handoff,
                       "intended_route_handoff": intended_handoff,
                       "input_surface_state": w.block(call),
                       "outside_call_path": approach_path,
                       "linked_native_remotes": linked, "hardware": hardware, "geometry": probes,
                       "status": status, "stages": {k: "UNVERIFIED" for k in STAGES}, "review": review()}
            landings.append(landing)
            if approach_path is not None:
                walk_cases.append({"id": f"r44/lift/{key[0]}_{key[1]}/{y}/call_approach",
                                   "path": [[q[0] + .5, q[1], q[2] + .5] for q in approach_path],
                                   "scope": "Native-shape candidate including every horizontal collision sweep; live input remains unverified"})
            lifecycle_cases.append({"lift": lift["id"], "source_controller": controller,
                                    "reader": reader, "call": call, "destinations": [l["controller"][1]
                                    for l in lift["landings"] if l["controller"][1] != y],
                                    "required_phases": list(STAGES), "status": "UNVERIFIED",
                                    "outside_call_candidate_available": approach_path is not None,
                                    "test_requirement": "Actual input and passenger movement; geometry and controller NBT alone cannot pass"})
        lifts.append({"id": lift["id"], "source": source, "landings": landings, "review": review()})

    stations = []
    for s in catalogue["stations"]:
        paths = station_paths[s["id"]]
        entrances = [{"source_case": c["id"], "path": c["path"],
                      "observed_endpoints": [geom.standing(tuple(map(math.floor, q))) for q in (c["path"][0], c["path"][-1])],
                      "status": "AUTHOR_INTENT_SEED"} for c in paths
                     if "/ground_entrance_" in c["id"] and not c["id"].endswith("/return")]
        stations.append({"id": s["id"], "name": s["name"], "bounds": s["bounds"],
                         "platforms": s["platforms"], "entrance_intent_seeds": entrances,
                         "declared_path_ids": [c["id"] for c in paths],
                         "halls": "UNVERIFIED entire floor/ports", "fare_gates": "UNVERIFIED physical discovery/operation",
                         "transfers": "UNVERIFIED complete source-to-destination operation",
                         "boarding": "UNVERIFIED live train/aircraft door alignment and passenger crossing",
                         "review": review()})
    denominator = {"station_areas": len(stations), "train_platforms": sum(p["mode"] == "TRAIN" for s in stations for p in s["platforms"]),
                   "air_interfaces": sum(p["mode"] == "AIRPLANE" for s in stations for p in s["platforms"]),
                   "lift_columns": len(lifts), "lift_stops": sum(len(l["landings"]) for l in lifts),
                   "authored_components": len(components), "virtual_rail_curves": len(native["curves"]),
                   "complete_station_passes": 0, "complete_lift_passes": 0}
    assert [denominator[k] for k in ("station_areas", "train_platforms", "air_interfaces", "lift_columns", "lift_stops", "authored_components")] == [20, 34, 4, 7, 24, 393]
    provenance = {"world": str(world), "native_snapshot_sha256": digest(ART43 / "transit_resolved/native_snapshot.json"),
                  "navigation_sha256": digest(world / "nerv_routes_r24.json.gz"),
                  "collision_shapes_sha256": digest(world / "native_collision_shapes.json"),
                  "interpretation": "171 rail curves are native virtual geometry, not missing rail blocks. Unknown cells/shapes never become air."}
    for name, data in (("components", components), ("lifts", lifts), ("stations", stations),
                       ("lifecycle_cases", lifecycle_cases), ("call_approach_cases", walk_cases)):
        (out / (name + ".json")).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")
    report = {"denominator": denominator, "provenance": provenance,
              "component_classes": dict(Counter(c["classification"] for c in components)),
              "unknown_shapes": sorted(geom.unknown), "status": "INCOMPLETE: native lifecycle and whole-station review required"}
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, default=WORLD)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    main(args.world, args.out)
