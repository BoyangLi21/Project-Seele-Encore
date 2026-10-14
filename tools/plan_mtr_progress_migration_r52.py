"""Create an uninstalled in-memory MTR migration proposal from native probe data."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = [([6, 8], 0x525201), ([2, 3], 0x525202), ([4, 5], 0x525203)]


def point(p):
    return tuple(p[k] for k in ("x", "y", "z")) if isinstance(p, dict) else tuple(p)


def as_pos(p):
    return dict(zip(("x", "y", "z"), p))


def edge(a, b):
    return tuple(sorted((point(a), point(b))))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output-directory", type=Path, default=ROOT / "artifacts/r52_mtr_progress_review/proposal")
    args = parser.parse_args()
    out = args.output_directory.resolve()
    allowed = (ROOT / "artifacts/r52_mtr_progress_review").resolve()
    assert allowed in out.parents and not out.exists()
    out.mkdir(parents=True)
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    boundary = ROOT / "artifacts/r52_hq_rail_boundary"
    records = read(boundary / "original_mtr_records.json")
    ten = [r["data"] for r in read(boundary / "hq_ten_rails.json")]
    probe = read(ROOT / "artifacts/r52_mtr_progress_review/NATIVE_READONLY_PROBE_V3.json")
    candidate_path = ROOT / "artifacts/r52_hq_approach_candidate/CANDIDATE.json"
    candidate = read(candidate_path)
    segments = {s["id"]: s for s in probe["candidate_native_segments"]}
    chains = {int(k.split("_")[1]): v for k, v in candidate["routes"].items()}
    original_edges = {edge(d["position1"], d["position2"]): i for i, d in enumerate(ten)}
    existing_colors = {c for r in records["rails"] for c in r["data"].get("signalColors", [])}
    blocks = []
    for group, color in GROUPS:
        assert color not in existing_colors
        shared = [s for s in segments.values() if set(group) <= set(s["source_original_indices"])]
        ends = {tuple(p) for s in shared for p in (s["from"], s["to"])}
        adjacent = [s for s in segments.values() if s not in shared and set(group) & set(s["source_original_indices"])
                    and {tuple(s["from"]), tuple(s["to"])} & ends]
        members = [s["id"] for s in shared + adjacent]
        blocks.append(dict(original_sources=group, color=color, hex_color=f"0x{color:06X}",
                           shared=[s["id"] for s in shared], adjacent=[s["id"] for s in adjacent], members=members))
    color_by_segment = {name: b["color"] for b in blocks for name in b["members"]}
    new_rails = []
    for s in segments.values():
        sources = s["source_original_indices"]
        rail = copy.deepcopy(ten[sources[0]])
        for original in sources[1:]:
            for key in ("styles", "isPlatform", "isSiding", "canAccelerate", "canTurnBack", "canConnectRemotely", "canHaveSignal", "transportMode"):
                assert rail[key] == ten[original][key], (s["id"], "incompatible inherited metadata", key)
        rail.update(position1=as_pos(s["from"]), position2=as_pos(s["to"]), angle1=s["from_angle"], angle2=s["to_angle"],
                    shape=s["shape"], verticalRadius=s["vertical_radius"])
        rail["speedLimit1"] = max(ten[i]["speedLimit1"] for i in sources)
        rail["speedLimit2"] = max(ten[i]["speedLimit2"] for i in sources)
        if len(sources) > 1:
            assert rail["speedLimit1"] == rail["speedLimit2"] == 60
        rail["signalColors"] = [color_by_segment[s["id"]]] if s["id"] in color_by_segment else []
        new_rails.append({"member": "UNINSTALLED_CANDIDATE/rails/" + s["id"], "data": rail})
    for i, chain in chains.items():
        assert all(segments[a]["to"] == segments[b]["from"] for a, b in zip(chain, chain[1:])), (i, "discontinuous chain")

    def replacement(p):
        index = original_edges.get(edge(p["startPosition"], p["endPosition"]))
        if index is None:
            return [copy.deepcopy(p)]
        reverse = point(p["startPosition"]) != point(ten[index]["position1"])
        names = list(reversed(chains[index])) if reverse else chains[index]
        result = []
        for j, name in enumerate(names):
            s = segments[name]
            q = copy.deepcopy(p)
            q.update(startPosition=as_pos(s["to"] if reverse else s["from"]),
                     endPosition=as_pos(s["from"] if reverse else s["to"]),
                     startAngle=s["to_angle"] if reverse else s["from_angle"],
                     endAngle=s["from_angle"] if reverse else s["to_angle"],
                     shape=s["shape"], verticalRadius=s["vertical_radius"])
            if j < len(names) - 1:
                q.update(savedRailBaseId=0, dwellTime=0)
            result.append(q)
        return result

    plans, affected_depots = [], []
    for depot in probe["depots"]:
        hits = [p["changed_original_rail_index"] for p in depot["path"] if "changed_original_rail_index" in p]
        if hits:
            affected_depots.append(dict(id=depot["id"], hex_id=depot["hex_id"], original_rail_occurrences=hits))
    for siding in probe["sidings"]:
        for v in siding["vehicles"]:
            path, mapping, prefix = [], {}, 0.
            for old_index, old in enumerate(v["path"]):
                pieces = replacement(old)
                indices = []
                for piece in pieces:
                    q = copy.deepcopy(piece)
                    if old.get("endDistance", 0) > 1e300:
                        length = float("inf")
                    elif "changed_original_rail_index" in old:
                        name = next(n for n, s in segments.items() if edge(s["from"], s["to"]) == edge(q["startPosition"], q["endPosition"]))
                        length = segments[name]["native_rail_length"]
                        q["candidate_segment_id"] = name
                    else:
                        length = old["native_rail_length"]
                    q.update(startDistance=prefix, endDistance=1.7976931348623157e308 if length == float("inf") else prefix + length,
                             source_old_path_index=old_index)
                    if length != float("inf"):
                        q["native_rail_length"] = length
                    indices.append(len(path)); path.append(q)
                    if length != float("inf"):
                        prefix += length
                mapping[old_index] = indices
            old_index = v["native_current_path_index"]
            old = v["path"][old_index]
            target = mapping[old_index]
            new_start, new_end = path[target[0]]["startDistance"], path[target[-1]]["endDistance"]
            if "changed_original_rail_index" in old:
                local = v["native_local_fraction"] * (new_end - new_start)
                policy = "changed edge: same traversal fraction along its complete replacement chain"
            else:
                local = v["native_local_distance"]
                policy = "unchanged edge: identical local distance and native world position"
            mapped = new_start + local
            ato, manual = (mapping[int(v[k])][-1] for k in ("nextStoppingIndexAto", "nextStoppingIndexManual"))
            changed = mapped != v["railProgress"] or ato != v["nextStoppingIndexAto"] or manual != v["nextStoppingIndexManual"]
            plans.append(dict(vehicle_id=str(v["id"]), siding_id=siding["id"], affected=changed, policy=policy,
                              old_progress=v["railProgress"], railProgress=mapped,
                              old_next_ato=v["nextStoppingIndexAto"], old_next_manual=v["nextStoppingIndexManual"],
                              nextStoppingIndexAto=ato, nextStoppingIndexManual=manual,
                              old_current_path_index=old_index, changed_original_rail_index=old.get("changed_original_rail_index"),
                              old_native_progress_position=v.get("native_progress_position"),
                              old_native_head_position=v.get("native_head_position"), new_expected_path=path,
                              preserved_state={k:v[k] for k in ("id", "speed", "elapsedDwellTime", "reversed", "departureIndex", "sidingDepartureTime")},
                              logical_next_stop={k:v["path"][int(v["nextStoppingIndexAto"])] [k] for k in ("savedRailBaseId", "stopIndex", "dwellTime")}))
    plan_by_id = {p["vehicle_id"]: p for p in plans}
    proposed_records = copy.deepcopy(records)
    proposed_records["rails"] = [r for r in proposed_records["rails"] if edge(r["data"]["position1"], r["data"]["position2"]) not in original_edges] + new_rails
    for row in proposed_records["depots"]:
        d = row["data"]; d["path"] = [piece for p in d["path"] for piece in replacement(p)]
    for row in proposed_records["sidings"]:
        d = row["data"]
        for key in ("pathSidingToMainRoute", "pathMainRouteToSiding"):
            d[key] = [piece for p in d[key] for piece in replacement(p)]
        for v in d["vehicles"]:
            plan = plan_by_id[str(v["id"])]
            for key in ("railProgress", "nextStoppingIndexAto", "nextStoppingIndexManual"):
                v[key] = plan[key]
    for row in proposed_records["platforms"]:
        d = row["data"]
        if edge(d["position1"], d["position2"]) in original_edges:
            for key in ("position1", "position2"):
                d[key]["y"] -= 93
    for row in proposed_records["stations"]:
        if row["data"]["id"] == 9166787716217601435:
            for key in ("position1", "position2"):
                row["data"][key]["y"] -= 93
    report = dict(schema="projectseele.r52.uninstalled-native-mtr-migration-proposal.v1", installed=False,
                  candidate_sha256=hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
                  original_signal_colors=sorted(existing_colors), blocks=blocks, affected_depots=affected_depots,
                  all_vehicles=plans, operating_diff="Root-approved shared bidirectional max60 and three independent complete signal blocks",
                  requires_native_reassembly_verification=True)
    (out / "PROPOSAL.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "IN_MEMORY_NATIVE_RECORDS.json").write_text(json.dumps(proposed_records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "affected_vehicle_ids": [p["vehicle_id"] for p in plans if p["affected"]],
                      "block_members": [(b["hex_color"], len(b["members"])) for b in blocks]}))


if __name__ == "__main__":
    main()
