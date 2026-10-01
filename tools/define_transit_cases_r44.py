"""Define every native TRAIN platform/AIR interface and its actual next stop.

No native dispatch, compilation or world write. Frozen authored station/airport
walk cases remain mandatory independent cases; a short rider test cannot pass
the complete station just because it reaches a vehicle.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

from audit_facility_transit_r44 import Geometry
from measure_world_r40 import MeasuredWorld

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/native_transit_cases"
ART43 = ROOT / "artifacts/repair_r43"


def main(world=WORLD, out=OUT):
    world, out = Path(world), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    native_path = ART43 / "transit_resolved/native_snapshot.json"
    native = json.loads(native_path.read_text(encoding="utf8"))
    catalogue = json.loads((ART43 / "facility_catalogue/catalogue.json").read_text(encoding="utf8"))
    platforms = {int(p["id"]): p for p in native["platforms"]}
    station = {int(p["id"]): s for s in catalogue["stations"] for p in s["platforms"]}
    owned = {int(p["id"]): p for p in json.loads((ART43 / "station_edge_ownership/actual_platforms.json").read_text(encoding="utf8"))["platforms"]}
    gates = json.loads((world / "regional_boarding_gates.json").read_text(encoding="utf8"))["gates"]
    walks = [c for c in json.loads((world / "quality_walk_cases.json").read_text(encoding="utf8")) if c.get("path")]
    interfaces = json.loads((ROOT / "artifacts/rebuild_r44/facility_transit_r44/platform_interfaces/interfaces.json").read_text(encoding="utf8"))["platforms"]
    physical = {int(p["id"]): p for p in interfaces}
    w = MeasuredWorld(world)
    profiles = {}
    for pid, p in platforms.items():
        if p["transportMode"] not in ("TRAIN", "AIRPLANE") or pid not in station:
            continue
        if p["transportMode"] == "TRAIN":
            gates_actual = [g for g in physical[pid]["gates"] if g["approach_usable"]]
            if not gates_actual:
                raise RuntimeError(("No actual boarding-door approach", pid))
            centre = owned[pid]["centre"]
            g = min(gates_actual, key=lambda g: sum((g["approach"][i] - centre[i]) ** 2 for i in (0, 2)))
            start = tuple(g["approach"])
            edges = owned[pid]["edges"]
            lo = [min(c["pos"][i] for row in edges.values() for c in row) for i in range(3)]
            hi = [max(c["pos"][i] for row in edges.values() for c in row) for i in range(3)]
            profile = {"staging": [start[0] + .5, start[1], start[2] + .5], "platform_lo": lo, "platform_hi": hi,
                "axis": owned[pid]["axis"], "actual_APG_pairs": len(gates_actual), "all_actual_door_approaches": [g["approach"] for g in gates_actual]}
            # Read the whole strip and its passenger apron, not just a sphere
            # around the selected doorway. Otherwise the middle of an actual
            # concourse can be unmeasured between two separately loaded ends.
            w.box((lo[0] - 18, lo[1] - 2, lo[2] - 18), (hi[0] + 18, hi[1] + 5, hi[2] + 18))
        else:
            centre = [(p["position1"][a] + p["position2"][a]) / 2 for a in ("x", "y", "z")]
            g = min(gates, key=lambda g: sum((g["head"][i] - centre[i]) ** 2 for i in range(3)))
            profile = {"staging": g["entry"], "air_stairs": {k: g[k] for k in ("id", "head", "entry", "landing", "direction")},
                "scope": "The stairs' source geometry and actual native door are independently tested; no aircraft-floor teleport"}
        s = station[pid]
        if pid == -4820290924094918262:
            # The return platform reaches the west concourse over its actual
            # six-metre stair/bridge. A flat-only BFS cannot audit that route.
            w.box(tuple(s["bounds"][0]), tuple(s["bounds"][1]))
        same_station_platforms = {p["id"] for p in s["platforms"]}
        relevant = [c for c in walks if c["id"].startswith("r23/station/") and c["id"].split("/")[2] in same_station_platforms]
        if p["transportMode"] == "AIRPLANE":
            key = profile["air_stairs"]["id"]
            relevant += [c for c in walks if c["id"].startswith((f"r20/airport/{key}/", f"r21/airport/{key}/", f"r22/airport/{key}/"))]
        # R23's surface-station bundles omit underground station handoffs and
        # some shared S1/R1 levels. Include geographically shared, explicitly
        # authored personnel transit paths, never every room in a station box.
        lo, hi = s["bounds"]
        selected_ids = {c["id"] for c in relevant}
        for c in walks:
            if c["id"] in selected_ids or not any(token in c["id"] for token in ("station", "boarding", "concourse", "foyer", "arrival", "transfer", "nerv_airport/stair")):
                continue
            if any(all(lo[i] - 4 <= q[i] <= hi[i] + 4 for i in range(3)) for q in c["path"]):
                relevant.append(c)
        # All inherited authored paths are separate obligations, including
        # both entrances, stairs, full-width boarding corridors and bridges.
        profile["station_walk_case_ids"] = [c["id"] for c in relevant]
        floor = math.floor(profile["staging"][1])
        goals = [tuple(map(math.floor, q)) for c in relevant for q in c["path"] if abs(q[1] - floor) < .15]
        for c in relevant:
            lo = tuple(math.floor(min(q[i] for q in c["path"])) - 4 for i in range(3))
            hi = tuple(math.ceil(max(q[i] for q in c["path"])) + 4 for i in range(3))
            w.box(lo, hi)
        w.around(profile["staging"], 18)
        profile["candidate_exit_goals"] = goals
        profiles[pid] = profile
    w.load()
    geometry = Geometry(w)
    held = []
    for pid, profile in profiles.items():
        start = tuple(map(math.floor, profile["staging"]))
        observed = geometry.standing(start)
        if observed["status"] != "STATIC_STANDING":
            held.append({"platform": str(pid), "stage": "staging", "observed": observed})
        # Exit reaches a documented concourse/airport-terminal path anchor,
        # not just a nearby empty point. Missing paths remain unresolved.
        goals = sorted(set(profile.pop("candidate_exit_goals")), key=lambda q: math.dist(start, q), reverse=True)
        best = None
        candidates = [start]
        if "axis" in profile:
            # Both actual passenger sides belong to this native platform.
            # A platform's first enumerated edge is not an entrance oracle.
            side_axis = 2 if profile["axis"] == "x" else 0
            sides = {q[side_axis] for q in profile["all_actual_door_approaches"]}
            for side in sides:
                a = [tuple(q) for q in profile["all_actual_door_approaches"] if q[side_axis] == side]
                candidates.append(min(a, key=lambda q: math.dist(q, start)))
        for candidate in dict.fromkeys(candidates):
            for q in goals:
                if math.dist(candidate, q) < 6:
                    continue
                route = geometry.flat_path(candidate, q, radius=180)
                if route is not None:
                    best = [[x + .5, y, z + .5] for x, y, z in route]
                    start = candidate
                    profile["staging"] = [start[0] + .5, start[1], start[2] + .5]
                    break
            if best:
                break
        if best is None and pid == -4820290924094918262:
            bottom_east, top_east = (312, -466, 197), (312, -460, 204)
            top_west, bottom_west, reader = (288, -460, 204), (288, -466, 197), (289, -466, 179)
            pieces = [geometry.flat_path(start, bottom_east, radius=100),
                      geometry.flat_path(top_east, top_west, radius=100),
                      geometry.flat_path(bottom_west, reader, radius=100)]
            if all(pieces):
                for x in (312, 288):
                    for step in range(6):
                        q = (x, -466 + step, 198 + step)
                        state = w.block(q)
                        if not state or not state.startswith("minecraft:smooth_quartz_stairs[facing=south,half=bottom,"):
                            raise RuntimeError(("Existing stair assembly changed", q, state))
                        for dy, height in ((1, 1.), (2, .8)):
                            boxes = geometry.boxes(w.get(x, q[1] + dy, q[2]))
                            if boxes is None or any(b[1] < height and b[4] > .001 for b in boxes):
                                raise RuntimeError(("Existing stair lacks real headroom", q, dy))
                staircase = [(312, -465 + step, 198 + step) for step in range(6)] + [top_east]
                descending = [(288, -465 + step, 198 + step) for step in reversed(range(6))] + [bottom_west]
                raw = pieces[0] + staircase + pieces[1][1:] + descending + pieces[2][1:]
                best = [[x + .5, y, z + .5] for x, y, z in raw]
                profile["existing_stair_bridge"] = {"east_stair_x": 312, "west_stair_x": 288, "floor": -460,
                    "headroom": "Both six-step native stair assemblies measured; actual movement UNVERIFIED",
                    "interpretation": "Existing station overbridge, no new map construction and no walking on the running tracks"}
        profile["exit_path"] = best
        profile["exit_status"] = "STATIC_CONNECTED_AUTHORED_CONCOURSE_ANCHOR" if best else "UNRESOLVED_AUTHORED_EXIT_CONNECTION"
        if best is None:
            held.append({"platform": str(pid), "stage": "exit", "reason": profile["exit_status"]})
        profile["station_name"] = station[pid]["name"]
        profile["station_id"] = station[pid]["id"]
    cases = []
    for pid, source in profiles.items():
        options = []
        for route in native["routes"]:
            seq = [int(p["platformId"]) for p in route["routePlatformData"]]
            for i in range(len(seq) - 1):
                if seq[i] == pid and seq[i + 1] != pid:
                    options.append((route, seq[i + 1]))
        if not options:
            raise RuntimeError(("No actual next native stop in route", pid))
        route, target = options[0]
        if target not in profiles:
            raise RuntimeError(("Uncatalogued native destination", pid, target))
        cases.append({"id": f"r44/transit/{pid}", "source_platform": str(pid), "destination_platform": str(target),
            "mode": platforms[pid]["transportMode"], "service": route["routeNumber"], "route_id": str(route["id"]),
            "source": source, "destination": profiles[target], "native": "UNVERIFIED",
            "required": ["source_station_paths", "exact_origin_stop_and_doors", "walk_native_door", "client_and_server_rider", "correct_destination_stop_and_doors", "walk_off_to_supported_platform", "server_detached", "destination_exit_path"]})
    assert sum(c["mode"] == "TRAIN" for c in cases) == 34
    assert sum(c["mode"] == "AIRPLANE" for c in cases) == 4
    selected_ids = {i for p in profiles.values() for i in p["station_walk_case_ids"]}
    station_walks = [c for c in walks if c["id"] in selected_ids]
    data = {"schema": 1, "world": str(world), "cases": cases, "station_areas": 20, "train_platforms": 34, "air_interfaces": 4,
        "required_station_walk_cases": len(station_walks), "held_static_interfaces": held, "unknown_shapes": sorted(geometry.unknown),
        "native_snapshot_sha256": hashlib.sha256(native_path.read_bytes()).hexdigest(), "status": "UNVERIFIED; no station or interface is passed by defining cases"}
    (out / "cases.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")
    (out / "station_walk_cases.json").write_text(json.dumps(station_walks, ensure_ascii=False, indent=2), encoding="utf8")
    print("Defined", len(cases), "exact native origin/next-stop cases;", len(station_walks), "station paths; held", len(held), flush=True)
    return data


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--world", type=Path, default=WORLD)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    main(a.world, a.out)
