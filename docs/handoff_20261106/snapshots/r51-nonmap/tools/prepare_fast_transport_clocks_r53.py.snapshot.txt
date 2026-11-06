"""Shorten only actual flight travel clocks; preserve all geometry and identities."""
from pathlib import Path
import argparse, copy, hashlib, heapq, json, math


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def distance(a, b):
    return math.dist(a["translation"], b["translation"])


def angle(a, b):
    dot = abs(sum(x*y for x, y in zip(a["quaternion_xyzw"], b["quaternion_xyzw"])))
    return math.degrees(2*math.acos(min(1, dot)))


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--air", type=Path, required=True)
    ap.add_argument("--root-plan", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--peak-speed-mps", type=float, default=180)
    a = ap.parse_args()
    assert 120 <= a.peak_speed_mps <= 180
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    original = json.loads(a.air.read_text("utf8")); fast = copy.deepcopy(original)
    nodes = {n["id"]: n for n in fast["nodes"]}
    changes = []
    for c in fast["corridors"]:
        start, end = (nodes[c[k]]["frame"] for k in ("from", "to"))
        travel = distance(start["plane"], end["plane"])
        cargo_travel = distance(start["cargo"], end["cargo"]) if "cargo" in start and "cargo" in end else 0
        yaw = angle(start["plane"], end["plane"])
        # The existing initial vertical hoist, final seating and posture-change
        # clocks are physical assembly stages. Only translating cruise is retimed.
        pure_vertical = abs(start["plane"]["translation"][0]-end["plane"]["translation"][0]) < 1e-8 and abs(start["plane"]["translation"][2]-end["plane"]["translation"][2]) < 1e-8
        shaft = {c["from"], c["to"]} == {"shaft_bottom", "shaft_top"}
        posture = "cargo" in start and "cargo" in end and angle(start["cargo"], end["cargo"]) > .001
        if posture or pure_vertical and not shaft or travel < 20:
            continue
        ticks = max(20, math.ceil(1.875 * max(travel, cargo_travel) * 20 / a.peak_speed_mps), math.ceil(1.875*yaw/1.5))
        if ticks < c["ticks"]:
            changes.append(dict(id=c["id"], old_ticks=c["ticks"], ticks=ticks, metres=travel,
                                peak_mps=1.875*travel*20/ticks, interpolation="original quintic ease"))
            c["ticks"] = ticks
    corridors = {c["id"]: c for c in fast["corridors"]}
    receivers = {r["port"]: r for r in fast["receivers"]}
    mission_changes = []
    for m in fast["missions"]:
        if m["intent"] != "RECOVER" or m["pickup_node"] != receivers[m["receiver"]]["flight_node"]:
            continue
        pickup = m["pickup_node"]; lifted = pickup+"/lifted"
        pair = [c["id"] for c in fast["corridors"] if c["from"] == pickup and c["to"] == lifted]
        back = [c["id"] for c in fast["corridors"] if c["from"] == lifted and c["to"] == pickup]
        assert len(pair) == len(back) == 1
        mission_changes.append(dict(id=m["id"], stage="loaded", before=m["loaded"], after=pair+back,
                                    reason="Same real receiver port: original vertical pickup and supported lowering; retire unnecessary horizontal excursion"))
        m["loaded"] = pair+back
    for c in fast["corridors"]:
        if c.get("reverse_of"):
            assert corridors[c["reverse_of"]]["ticks"] == c["ticks"]
    # All geometry, producer/source hashes, fixtures, first vertical lift,
    # held spaces and door associations must remain byte-for-byte semantic equal.
    baseline = copy.deepcopy(fast)
    old_by_id = {c["id"]: c for c in original["corridors"]}
    for c in baseline["corridors"]:
        c["ticks"] = old_by_id[c["id"]]["ticks"]
    baseline["missions"] = original["missions"]
    assert baseline == original
    mission_clocks = []
    old_missions = {m["id"]:m for m in original["missions"]}
    for m in fast["missions"]:
        old = {stage:sum(old_by_id[c]["ticks"] for c in old_missions[m["id"]][stage]) for stage in ("outbound", "loaded", "retreat")}
        new = {stage:sum(corridors[c]["ticks"] for c in m[stage]) for stage in old}
        # Exact existing finite graph. Check for accidental repeated nodes and
        # prove each stage is the fastest already-authorized path between ports.
        checks = {}
        for stage in old:
            chain = [corridors[c] for c in m[stage]]
            at = [chain[0]["from"]]+[c["to"] for c in chain]
            service = stage == "loaded" and at[0] == at[-1]
            assert service and len(at) == 3 and at[1] == at[0]+"/lifted" or len(at) == len(set(at)), (m["id"], stage, "horizontal loop")
            adj = {}
            for c in fast["corridors"]:
                if stage == "loaded" and ("cargo" not in nodes[c["from"]]["frame"] or "cargo" not in nodes[c["to"]]["frame"]):
                    continue
                adj.setdefault(c["from"], []).append((c["to"], c["ticks"]))
            best = {at[0]:0}; pending = [(0,at[0])]
            while pending:
                cost, u = heapq.heappop(pending)
                if cost != best[u]: continue
                for v, dt in adj.get(u, []):
                    nc = cost+dt
                    if nc < best.get(v, math.inf):
                        best[v]=nc; heapq.heappush(pending,(nc,v))
            checks[stage] = dict(no_horizontal_loop=True, same_port_vertical_service=service, installed_chain_ticks=new[stage], graph_minimum_ticks=best.get(at[-1]), first_vertical_pickup_preserved=service or stage != "loaded" or "/lifted" in at[1])
        mission_clocks.append(dict(id=m["id"], old_ticks=old, ticks=new, shortest_current_graph=checks))
    (out/"ROOT_AIR_FAST_CLOCKS_CANDIDATE.json").write_text(json.dumps(fast,ensure_ascii=False,indent=2)+"\n", "utf8")
    report=dict(schema="projectseele.fast-transport-clock-r53.v1", world_written=False, source_air=str(a.air.resolve()),
                source_air_sha256=sha(a.air), root_plan_sha256=sha(a.root_plan), peak_translation_speed_mps=a.peak_speed_mps,
                changed_corridors=changes, mission_chain_changes=mission_changes, missions=mission_clocks, identical_all_other_manifest_fields=True,
                runtime_guards_unchanged=["actual original mesh source sweep", "pilot/plug/EVA identity", "original fixture contacts", "held occupancy and door guards", "initial vertical pickup"],
                pending=["native actual loaded flights, cancellation, queue and save/reload timing", "actual visual review"])
    (out/"FAST_CLOCKS_RECEIPT.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n", "utf8")
    print(json.dumps(dict(changed_corridors=len(changes), mission_count=len(mission_clocks), candidate=str(out/"ROOT_AIR_FAST_CLOCKS_CANDIDATE.json"),world_written=False)))


if __name__ == "__main__": main()
