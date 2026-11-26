"""Plan GS service on the existing GeoFront viaduct using MTR 4 records.

    python spiral_service.py plan WORLD PACKAGE
    python spiral_service.py check|apply|verify|rollback WORLD PACKAGE --journal BACKUP

Apply only to a stopped world. The native simulator must run on an isolated copy.
Changed configuration fields are merged into the current records so running vehicles
keep their original IDs, progress, and passengers. Civil rows are installed separately.
"""

import argparse
import json
import math
import os
from copy import deepcopy
from pathlib import Path

from mtr_patch_records import load, pack, path_of, rail_path

SIDING = 7095002157700150526
DEPOT = 2035010765233218271
# Consecutive triplets on the freight-free spiral. Each middle segment passes its opposite.
LOOPS = ((1795, -383, 319), (258, -2, 1148))
COLORS = (0xE24E2E, 0x06BD77, 0x236ADC)
SPEED, OFFSET = 500, 2.7


def xyz(p):
    return tuple(p[k] for k in "xyz")


def ends(edge):
    return dict(position1=edge["startPosition"], position2=edge["endPosition"])


def offset(p, side):
    angle = math.atan2(p["z"] - 290, p["x"] - 30)
    return dict(
        x=p["x"] + round(side * OFFSET * math.cos(angle)),
        y=p["y"],
        z=p["z"] + round(side * OFFSET * math.sin(angle)),
    )


def plan(base):
    depot_path = path_of(base, "depots", DEPOT)
    siding_path = path_of(base, "sidings", SIDING)
    depot, siding = load(depot_path), load(siding_path)
    old_path = depot["path"]
    path = deepcopy(old_path)
    keys = [rail_path(base, ends(edge)) for edge in path]
    # The surface station is the turnaround at the other end. ENTRY is served beyond FLOOR on the way back.
    turn = next(i for i in range(len(keys) - 1) if keys[i] == keys[i + 1])
    start = [next(i for i in range(turn) if xyz(path[i]["startPosition"]) == node) for node in LOOPS]
    owned = set(keys)
    for kind, lists in (
        ("depots", ("path",)),
        ("sidings", ("pathSidingToMainRoute", "pathMainRouteToSiding")),
    ):
        for file in (base / kind).glob("*/*"):
            if file in (depot_path, siding_path) or not file.is_file():
                continue
            other = load(file)
            if any(rail_path(base, ends(e)) in owned for field in lists for e in other.get(field, [])):
                raise ValueError(f"GS shares its running line with {file}")
    records = {}

    def change(file, before, after, fields=None):
        key = file.relative_to(base).as_posix()
        if fields is not None:
            fields = [f for f in fields if before[f] != after[f]]
            if not fields:
                return
            before, after = ({f: row[f] for f in fields} for row in (before, after))
        records[key] = dict(before=before, after=after, fields=fields is not None)

    branches, new_rails = {}, []
    for i, (file, edge) in enumerate(zip(keys, path)):
        rail = load(file)
        if edge["savedRailBaseId"] and not rail["isPlatform"]:
            raise ValueError(f"Unrecognized stop at {file}")
        if rail["signalColors"]:
            raise ValueError(f"Existing signals at {file}")
        fast = (
            not rail["isPlatform"]
            and not rail["isSiding"]
            and rail["speedLimit1"] == rail["speedLimit2"] == 200
        )
        if fast:
            edge["speedLimit"] = SPEED
        if i > turn and file in branches:
            aa, bb = branches[file]
            edge["startPosition"], edge["endPosition"] = bb, aa
            continue
        if file.relative_to(base).as_posix() in records or i > turn and file in keys[: turn + 1]:
            continue
        junction = next((n for n in start if n <= i <= n + 2), None)
        section = sum(n + 2 < i for n in start) if i <= turn else 0
        color = [COLORS[section]]
        updated = dict(rail, signalColors=color)
        if fast:
            updated.update(speedLimit1=SPEED, speedLimit2=SPEED)
        if junction is None:
            change(file, rail, updated, ("signalColors", "speedLimit1", "speedLimit2"))
            continue
        if not fast:
            raise ValueError("Passing tracks require the surveyed plain line")
        # Reserve each turnout together with the adjacent single track, through to the separated rail centers.
        color = [COLORS[section]] if i == junction else [COLORS[section + 1]] if i == junction + 2 else []
        a, b = edge["startPosition"], edge["endPosition"]
        for side in (-1, 1):
            aa = offset(a, side) if i > junction else a
            bb = offset(b, side) if i < junction + 2 else b
            branch = dict(
                updated,
                signalColors=color,
                position1=aa,
                position2=bb,
                angle1=edge["startAngle"],
                angle2=edge["endAngle"],
                speedLimit1=SPEED if side == -1 else 0,
                speedLimit2=SPEED if side == 1 else 0,
            )
            new = rail_path(base, branch)
            if new.exists():
                raise ValueError(f"Passing track already exists at {new}")
            change(new, None, branch)
            new_rails.append([xyz(aa), xyz(bb)])
            if side == -1:
                edge["startPosition"], edge["endPosition"] = aa, bb
            else:
                branches[file] = aa, bb
        change(file, rail, None)
    if len(branches) != 6 or any(a["endPosition"] != b["startPosition"] for a, b in zip(path, path[1:])):
        raise ValueError("Incomplete GS passing layout")
    change(
        depot_path,
        depot,
        dict(depot, path=path, useRealTime=True, realTimeDepartures=[0, 198000, 396000]),
        ("path", "useRealTime", "realTimeDepartures"),
    )
    change(siding_path, siding, dict(siding, maxVehicles=3), ("maxVehicles",))
    return records, new_rails


def current(file):
    return load(file) if file.exists() else None


def matches(value, expected, fields):
    return (
        (value is not None and all(value.get(k) == v for k, v in expected.items()))
        if fields
        else value == expected
    )


def store(file, value):
    if value is None:
        file.unlink(missing_ok=True)
        return
    file.parent.mkdir(exist_ok=True, parents=True)
    tmp = file.with_name(file.name + ".gs-service.tmp")
    with tmp.open("wb") as stream:
        stream.write(pack(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, file)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "check", "apply", "verify", "rollback"))
    parser.add_argument("world", type=Path)
    parser.add_argument("package", type=Path)
    parser.add_argument("--journal", type=Path)
    args = parser.parse_args()
    base = args.world.resolve() / "mtr/projectseele/geofront"
    if not (base / "depots").is_dir():
        parser.error("Expected a world with native GeoFront MTR records")
    manifest = args.package / "transit.json"
    if args.action == "plan":
        records, rails = plan(base)
        args.package.mkdir(exist_ok=True, parents=True)
        manifest.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf8")
        (args.package / "passing-rails.json").write_text(json.dumps(rails), encoding="utf8")
        return
    records = json.loads(manifest.read_text(encoding="utf8"))
    for k in records:
        if len(Path(k).parts) != 3 or not (base / k).resolve().is_relative_to(base):
            raise ValueError(f"Unexpected MTR member {k}")

    def check(which):
        for k, op in records.items():
            if not matches(current(base / k), op[which], op["fields"]):
                raise ValueError(f"{which} mismatch in {k}")

    if args.action in ("check", "verify"):
        check("before" if args.action == "check" else "after")
        print(args.action, len(records), "native members")
        return
    if args.journal is None or args.journal.resolve().is_relative_to(args.world.resolve()):
        parser.error("Supply a rollback journal outside the stopped world")
    backup = args.journal / "transit-backup.json"

    def restore():
        journal = json.loads(backup.read_text(encoding="utf8"))
        if journal["world"] != str(base) or set(journal["records"]) != set(records):
            raise ValueError("Rollback journal belongs to another installation")
        for k, before in journal["records"].items():
            op = records[k]
            val = current(base / k)
            if matches(val, op["before"], op["fields"]):
                continue
            if not matches(val, op["after"], op["fields"]):
                raise ValueError(f"Unexpected changes to {k}")
            store(base / k, dict(val, **op["before"]) if op["fields"] else before)
        check("before")

    from install_r53_carrier_trays import stopped_world

    with stopped_world(args.world):
        if args.action == "rollback":
            restore()
        else:
            check("before")
            args.journal.mkdir(parents=True, exist_ok=True)
            with backup.open("x", encoding="utf8") as stream:
                json.dump(dict(world=str(base), records={k: current(base / k) for k in records}), stream)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                for k, op in records.items():
                    store(base / k, dict(current(base / k), **op["after"]) if op["fields"] else op["after"])
                check("after")
            except BaseException:
                restore()
                raise
    print(args.action, len(records), "native members")


if __name__ == "__main__":
    main()
