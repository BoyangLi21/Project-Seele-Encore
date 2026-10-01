"""Route diagrams from exact native platform visits and real departure rails.

Only the current verified symmetric out-and-back services get one linear
diagram. A branch cannot silently be flattened by station-name deduplication.
Both train and flight services participate in actual station interchange.
"""
from collections import defaultdict
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "artifacts/repair_r43/transit_resolved/native_snapshot.json"
CATALOGUE = ROOT / "artifacts/repair_r43/facility_catalogue/catalogue.json"
NORMAL = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}


class RouteDiagrams:
    def __init__(self, native_path=NATIVE, catalogue_path=CATALOGUE):
        self.native = json.loads(Path(native_path).read_text(encoding="utf8"))
        catalogue = json.loads(Path(catalogue_path).read_text(encoding="utf8"))
        self.station = {int(p["id"]): s for s in catalogue["stations"] for p in s["platforms"]}
        self.routes = {int(r["id"]): r for r in self.native["routes"]}
        self.served = defaultdict(list)
        self.lines = defaultdict(set)
        for route in self.routes.values():
            for visit in route["routePlatformData"]:
                pid = int(visit["platformId"])
                if pid not in self.station:
                    raise RuntimeError(("Route visit has no actual native station", pid))
                if route not in self.served[pid]:
                    self.served[pid].append(route)
                self.lines[self.station[pid]["id"]].add(route["routeNumber"])

    def departure(self, pid, route):
        for depot in self.native["depots"]:
            if int(route["id"]) not in [int(i) for i in depot["routeIds"]]:
                continue
            path = depot["path"]
            for i, leg in enumerate(path):
                if int(leg.get("savedRailBaseId", -1)) != pid:
                    continue
                for offset in range(1, len(path) + 1):
                    following = path[(i + offset) % len(path)]
                    a, b = following["startPosition"], following["endPosition"]
                    dx, dz = b["x"] - a["x"], b["z"] - a["z"]
                    if dx or dz:
                        return (dx, dz)
        raise RuntimeError(("No exact actual outgoing native rail", pid, route["routeNumber"]))

    def diagram(self, pid, face, preferred_line=""):
        pid = int(pid)
        options = self.served.get(pid, [])
        if not options:
            raise RuntimeError(("No live served platform identity", pid))
        route = next((r for r in options if r["routeNumber"] in preferred_line), options[0])
        sequence = [int(v["platformId"]) for v in route["routePlatformData"]]
        names = [self.station[p]["name"] for p in sequence]
        index = sequence.index(pid)
        if len(sequence) % 2 != 1 or sequence[0] != sequence[-1]:
            raise RuntimeError(("Diagram requires an explicit branch/loop design", route["routeNumber"]))
        turn = (len(sequence) - 1) // 2
        forward = names[:turn + 1]
        if names != forward + forward[-2::-1] or len(set(forward)) != len(forward):
            raise RuntimeError(("Native visit order is not a simple symmetric line", route["routeNumber"], names))
        order = forward if index < turn else forward[::-1]
        next_index = (index + 1) % (len(sequence) - 1)
        next_station = names[next_index]
        here = self.station[pid]
        dx, dz = self.departure(pid, route)
        nx, nz = NORMAL[face]
        right, away = dx * nz - dz * nx, -dx * nx - dz * nz
        arrow = "→" if right > abs(away) else "←" if -right > abs(away) else "↑" if away >= 0 else "↓"
        transfers = sorted(self.lines[here["id"]] - {route["routeNumber"]})
        rows = [("● " + name + "  本站") if name == here["name"] else "│ " + name for name in order]
        rows += ["行车方向 " + arrow + "  下一站 " + next_station,
            "发车时间见本侧实时板",
            "换乘 " + " / ".join(transfers) + " · 按站内导向" if transfers else "出口与楼梯 · 按本侧导向"]
        if len(rows) > 18:
            raise RuntimeError("Installed board cannot silently truncate the full native station diagram")
        return {"platform": pid, "station_id": here["id"], "station": here["name"],
            "line": route["routeNumber"], "mode": route["transportMode"], "route_id": str(route["id"]),
            "rows": rows, "all_native_visits": sequence, "next_platform": str(sequence[next_index]),
            "native_departure_vector": [dx, dz], "physical_face": face, "transfer_services": transfers,
            "next_station": next_station}
