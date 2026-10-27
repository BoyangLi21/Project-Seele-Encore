"""Re-seat the existing two-cell rear bridge frame; produce candidates only."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np

from query_blocks import read_box, iter_block_entities

AIR = "minecraft:air"
DECK = "projectseele:entry_plug_bridge_deck"
GUARD = "projectseele:entry_plug_bridge_guard"
SIDES = {"east": (1, 0), "north": (0, -1), "south": (0, 1), "west": (-1, 0)}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def state(name, flags, unit=None):
    props = {k: str(v).lower() for k, v in flags.items()}
    if unit is not None:
        props["unit"] = str(unit)
    return name + "[" + ",".join(k + "=" + v for k, v in sorted(props.items())) + "]"


def reshape(rows, unit):
    old = {tuple(r["position"]): r["state"] for r in rows}
    new = dict(old)
    dx = -42 * unit
    moving = [(p, s) for p, s in old.items()
              if 56 + dx <= p[0] <= 88 + dx and p[2] in (313, 314)
              and (s.startswith(DECK) or s.startswith(GUARD))]
    for p, _ in moving:
        new[p] = AIR
    # Move the continuous rear cross-member and both guard edges as one unit.
    # The unchanged side landings already contain full supports at z312/313.
    for p, s in moving:
        target = (p[0], p[1], p[2] - 1)
        assert old.get(target, AIR) == AIR or old[target].startswith((DECK, GUARD)), (target, old.get(target))
        new[target] = s
    # At the two retained longitudinal connections, remove internal rails and
    # join the relocated frame. Keep every exposed edge guarded in every state.
    affected = {(p[0], -1015, p[2] - 1) for p, s in moving if s.startswith(DECK)}
    for p in affected:
        assert new[p].startswith(DECK)
        flags = {k: new.get((p[0] + v[0], p[1], p[2] + v[1]), AIR) == AIR
                 for k, v in SIDES.items()}
        new[p] = state(DECK, flags, unit)
        above = (p[0], p[1] + 1, p[2])
        assert new.get(above, AIR) == AIR or new[above].startswith(GUARD)
        new[above] = state(GUARD, flags) if any(flags.values()) else AIR
    # All entries remain in the state table, including the retired rear cells.
    return [{"position": list(p), "state": s} for p, s in new.items()]


def boxes(s):
    if s == AIR:
        return []
    flags = {k: k + "=true" in s for k in SIDES}
    raw = []
    if s.startswith(DECK):
        raw = [(0, 13.5, 0, 16, 16, 16), (1, 0, 1, 3, 13.5, 15),
               (13, 0, 1, 15, 13.5, 15), (3, 2, 7, 13, 4, 9)]
        fascia = {"north": (0, 2, 0, 16, 13.5, .8), "south": (0, 2, 15.2, 16, 13.5, 16),
                  "west": (0, 2, 0, .8, 13.5, 16), "east": (15.2, 2, 0, 16, 13.5, 16)}
        raw += [fascia[k] for k in SIDES if flags[k]]
    elif s.startswith(GUARD):
        rail = {
            "north": [(0, 0, 0, .8, 17.6, .8), (15.2, 0, 0, 16, 17.6, .8), (0, 8, 0, 16, 8.8, .8), (0, 16.8, 0, 16, 17.6, .8)],
            "east": [(15.2, 0, 0, 16, 17.6, .8), (15.2, 0, 15.2, 16, 17.6, 16), (15.2, 8, 0, 16, 8.8, 16), (15.2, 16.8, 0, 16, 17.6, 16)],
            "south": [(0, 0, 15.2, .8, 17.6, 16), (15.2, 0, 15.2, 16, 17.6, 16), (0, 8, 15.2, 16, 8.8, 16), (0, 16.8, 15.2, 16, 17.6, 16)],
            "west": [(0, 0, 0, .8, 17.6, .8), (0, 0, 15.2, .8, 17.6, 16), (0, 8, 0, .8, 8.8, 16), (0, 16.8, 0, .8, 17.6, 16)]}
        raw = [b for k in SIDES if flags[k] for b in rail[k]]
    else:
        raw = [(0, 0, 0, 16, 16, 16)]
    return [np.asarray(b, float).reshape(2, 3) / 16 for b in raw]


def triangle_box_indices(triangles, lo, hi):
    candidates = np.flatnonzero(np.all((triangles.max(1) > lo + 1e-8)
                                      & (triangles.min(1) < hi - 1e-8), axis=1))
    found = []
    center, half = (lo + hi) / 2, (hi - lo) / 2
    for index in candidates:
        t = triangles[index] - center
        edges = np.roll(t, -1, axis=0) - t
        axes = np.concatenate((np.eye(3), [np.cross(edges[0], edges[1])],
                               np.cross(edges[:, None], np.eye(3)[None]).reshape(-1, 3)))
        length = np.linalg.norm(axes, axis=1)
        axes = axes[length > 1e-12] / length[length > 1e-12, None]
        projection = t @ axes.T
        radius = np.abs(axes) @ half
        if not np.any((projection.min(0) >= radius - 1e-8) | (projection.max(0) <= -radius + 1e-8)):
            found.append(int(index))
    return found


def verify_mesh(tables, detail):
    # The canonical rigid assembly is the actual original source geometry;
    # export frames are the obsolete parked pose and are deliberately unused.
    meshes = [(m["name"], np.asarray(m["xyz"]).reshape(-1, 3, 3) * [-1, 1, -1]
               + [72.5, -1062, 328.5]) for m in detail["carrierParts"]
              if not m["name"].startswith(("rear/", "sole_"))]
    unique = {(tuple(r["position"]), r["state"]) for rows in tables for r in rows if r["state"] != AIR}
    collisions = []
    for pos, s in sorted(unique):
        p = np.asarray(pos)
        for box in boxes(s):
            lo, hi = box + p
            for name, triangles in meshes:
                if np.any(triangles.max((0, 1)) <= lo) or np.any(triangles.min((0, 1)) >= hi):
                    continue
                hits = triangle_box_indices(triangles, lo, hi)
                if hits:
                    collisions.append({"pos": pos, "state": s, "part": name, "triangles": hits})
    return {"canonical_root": [72.5, -1062, 328.5], "mesh_parts": len(meshes),
            "source_triangles": sum(len(a) for _, a in meshes), "unique_interface_states": len(unique),
            "collisions": collisions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("world", type=Path)
    parser.add_argument("detail", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--geometry-only", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    owner = json.loads((args.world / "ROOT_MECHANICAL_OWNER.json").read_bytes())
    originals, candidates = [], []
    for unit in range(3):
        ref = owner["units"][unit]["bridge_states"]["cells_file"]
        original = json.loads(gzip.decompress((args.world / ref).read_bytes()))
        originals.append(original)
        candidates.append([reshape(rows, unit) for rows in original])
    normalized = [[{"position": [r["position"][0] + 42 * unit, *r["position"][1:]],
                    "state": r["state"].replace("unit=" + str(unit), "unit=0")}
                   for r in rows] for unit, tables in enumerate(candidates) for rows in tables]
    geometry = verify_mesh(normalized, json.loads(args.detail.read_bytes()))
    write(args.output / "interface-geometry.json", geometry)
    print(json.dumps({k: v for k, v in geometry.items() if k != "collisions"}
                     | {"collision_count": len(geometry["collisions"])}))
    if geometry["collisions"] or args.geometry_only:
        return
    forward, summaries, table_files, patches = [], [], [], []
    for unit in range(3):
        before_tables = [{tuple(r["position"]): r["state"] for r in rows} for rows in originals[unit]]
        after_tables = [{tuple(r["position"]): r["state"] for r in rows} for rows in candidates[unit]]
        delta = {p for old, new in zip(before_tables, after_tables) for p in new if old.get(p, AIR) != new[p]}
        # The entire board path, its original full-width deck and entrance,
        # the two fixed bearings and all other mechanism cells remain exact.
        for old, new in zip(before_tables, after_tables):
            assert old.keys() == new.keys()
            assert all(old[p] == new[p] for p in old if p[2] < 312 or p[0] < 56 - 42 * unit or p[0] > 88 - 42 * unit)
        lo = tuple(min(p[a] for p in delta) for a in range(3))
        hi = tuple(max(p[a] for p in delta) for a in range(3))
        source_file = args.output / f"source-unit{unit}.json"
        if source_file.exists():
            source = json.loads(source_file.read_bytes())
            assert source["world"] == str(args.world) and source["lo"] == list(lo) and source["hi"] == list(hi)
            measured = {tuple(r["pos"]): r["state"] for r in source["cells"]}
            devices = set(map(tuple, source["block_entities"]))
        else:
            measured = read_box(args.world, "projectseele:geofront", lo, hi)
            devices = {p for p, _ in iter_block_entities(args.world, "projectseele:geofront", lo, hi)}
            write(source_file, {"world": str(args.world), "lo": lo, "hi": hi,
                               "cells": [{"pos": p, "state": s} for p, s in measured.items()],
                               "block_entities": sorted(devices)})
        assert delta <= measured.keys() and not delta.intersection(devices)
        matching = [i for i, old in enumerate(before_tables) if all(measured[p] == old[p] for p in delta)]
        assert len(matching) == 1, (unit, "Actual interface does not select exactly one original state", matching)
        current = matching[0]
        for p in sorted(delta):
            if measured[p] != after_tables[current][p]:
                forward.append({"pos": list(p), "before": measured[p], "after": after_tables[current][p],
                                "before_nbt": None, "after_nbt": None, "purpose": "original_bridge_rear_frame_reseat"})
        # The source path and unit identity remain stable. Binding calculation
        # belongs to the root's single integration transaction, not this tool.
        relative = owner["units"][unit]["bridge_states"]["cells_file"]
        target = args.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gzip.compress(json.dumps(candidates[unit], separators=(",", ":")).encode(), mtime=0))
        inverse_target = args.output / "inverse" / relative
        inverse_target.parent.mkdir(parents=True, exist_ok=True)
        inverse_target.write_bytes((args.world / relative).read_bytes())
        table_files.append(relative)
        patches.append({"unit": unit, "json_path": f"units[{unit}].bridge_states", "cells_file": relative,
                        "binding": "Recompute existing required binding during root integration; retain source path and all other owner fields."})
        summaries.append({"unit": unit, "actual_state": current, "state_count": len(candidates[unit]),
                          "table_delta_cells": len(delta), "table_delta_per_state": [sum(o[p] != n[p] for p in o) for o, n in zip(before_tables, after_tables)],
                          "actual_source_cells": len(measured), "source_bounds": [lo, hi],
                          "rear_frame_width_m": 2, "guard_clear_width_m": 1.9,
                          "original_side_bearings": [[55 - 42 * unit, -1015, 312], [55 - 42 * unit, -1015, 313],
                                                     [89 - 42 * unit, -1015, 312], [89 - 42 * unit, -1015, 313]],
                          "board_path_retained": owner["units"][unit]["board_path"]})
    write(args.output / "forwardPatch.json", forward)
    write(args.output / "inversePatch.json", [{**r, "before": r["after"], "after": r["before"]} for r in forward])
    write(args.output / "positiveEditMask.json", [r["pos"] for r in forward])
    write(args.output / "owner-delta.json", patches)
    # This exact original is only a merge base, never an installable new owner.
    write(args.output / "inverse" / "ROOT_MECHANICAL_OWNER.json", owner)
    write(args.output / "construction.json", {
        "world": str(args.world), "dimension": "projectseele:geofront", "installed": False,
        "units": summaries, "changed_static_cells": len(forward), "tables": table_files,
        "design": "Move original dynamic two-cell rear cross-member z313/314 to z312/313; join original full-width side bearings at x55/89 (translated per unit). Preserve original longitudinal connections; recompute only rear frame guard edges.",
        "scope": "Only existing bridge equipment interface. All cells outside rear-frame positive mask, original entrance, board_path and navigation remain unchanged.",
        "metadata_integration": "Merge owner-delta into latest ROOT_MECHANICAL_OWNER; update its existing table bindings and ROOT_ASSEMBLY_BUNDLE mechanical binding in the same root installation transaction. Do not install inverse owner as a candidate.",
        "identity_and_progress": "No entity, player, pilot, task, vehicle, epoch or directory changes. Current physical bridge state is selected from original saved block states.",
        "native_pending": "Root installs after review; observe original carrier upright and original bridge normal retraction/deployment, then walk original board_path. No gameplay claim from static geometry."})
    print(json.dumps({"changed_static_cells": len(forward), "units": summaries}))


if __name__ == "__main__":
    main()
