"""Retire the complete positively traced static guards across native air ports."""
from pathlib import Path
import argparse
import hashlib
import json
from collections import Counter

import regional_voxels as v
from aircraft_boarding_authority_r44 import AircraftBoardingAuthority
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/air_port_static_guard_retirement_v1"


def plan():
    authority = AircraftBoardingAuthority(WORLD)
    old_path = ROOT / "artifacts/spatial_repair_r41/remaining_edges/dispositions.json"
    old = json.loads(old_path.read_text(encoding="utf8"))
    traced = {}
    for row in old:
        point = row.get("guard_cell")
        if point is not None and row.get("final_disposition") == "connected_public_paving_edge_guard":
            traced.setdefault(tuple(point), []).append(row)
    world = MeasuredWorld(WORLD)
    for component in authority.components:
        cells = list(component["owned"]) + [component["lo"], component["hi"]]
        component["read_lo"] = tuple(min(p[i] for p in cells) - 1 for i in range(3))
        component["read_hi"] = tuple(max(p[i] for p in cells) + 1 for i in range(3))
        world.box(component["read_lo"], component["read_hi"])
    world.load()
    v.WORLD = WORLD
    v.OUT = OUT
    painter = v.Painter()
    groups = []
    held = []
    native = json.loads((WORLD / "native_collision_shapes.json").read_text(encoding="utf8"))
    shapes = {v.canonical_state(k): boxes for k, boxes in native.items()}
    for component in authority.components:
        tags = dict(iter_block_entities(WORLD, v.DIM, component["read_lo"], component["read_hi"]))
        rails = []
        for x in range(component["read_lo"][0], component["read_hi"][0] + 1):
            for y in range(component["read_lo"][1], component["read_hi"][1] + 1):
                for z in range(component["read_lo"][2], component["read_hi"][2] + 1):
                    point = (x, y, z)
                    state = world.block(point)
                    if state is None:
                        held.append(dict(position=point, why="Unloaded or incomplete current world section"))
                        continue
                    if not state.startswith("projectseele:nerv_edge_rail[") or authority.owner(point) != component["id"]:
                        continue
                    old_rows = traced.get(point)
                    if not old_rows or point in tags:
                        held.append(dict(position=point, state=state, why="Untraced guard or block entity"))
                        continue
                    directions = {(1, 0, 0): "east", (-1, 0, 0): "west", (0, 0, 1): "south", (0, 0, -1): "north"}
                    sides = {directions[tuple(row["normal"])] for row in old_rows}
                    expected = "projectseele:nerv_edge_rail[" + ",".join(f"{key}={str(key in sides).lower()}" for key in ("east", "north", "south", "west")) + "]"
                    if state != expected or state not in shapes:
                        held.append(dict(position=point, state=state, expected=expected, why="State/actual native shape differs from traced producer"))
                        continue
                    rails.append(dict(position=point, before=state, after="minecraft:air", native_shape=shapes[state], old_decisions=old_rows))
                    painter.match((*point, *point), state, "minecraft:air", "r44/retire_complete_R41_aircraft_port_guard")
        groups.append(dict(id=component["id"], current_recipe_sha256=hashlib.sha256(authority.path.read_bytes()).hexdigest(),
                           deployed_recipe_cells=len(component["owned"]), dynamic_device_cells_preserved=True,
                           full_port_volume=[component["lo"], component["hi"]], removed_component=rails,
                           touched_block_entities=0))
    OUT.mkdir(parents=True, exist_ok=True)
    report = dict(scope="All four saved native aircraft gate devices and complete boarding mouths", groups=groups, held=held,
                  retired_cells=sum(len(g["removed_component"]) for g in groups),
                  source_ledger=str(old_path), source_ledger_sha256=hashlib.sha256(old_path.read_bytes()).hexdigest(),
                  first_runtime_negative="transit_lifecycle/20261001_200439/result.json",
                  root_cause="R41 unresolved airport port was unconditionally reclassified as public paving edge; static guard crossed a dynamic native doorway.",
                  source_fix="Both floor-edge producers now preserve finite saved native gate/device authority before filling or guarding.",
                  not_verified=["Actual repeat boarding and all four aircraft interfaces", "Whole station art and lifecycle", "Sideways approach safety against actual native aircraft body"])
    (OUT / "all_aircraft_port_components.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    assert not held, f"Held {len(held)} unproven cells; no patch accepted"
    assert len(groups) == 4 and report["retired_cells"] == 3
    painter.meta.update(report)
    painter.save_plan("retired_aircraft_port_guards")
    print(json.dumps(dict(groups=len(groups), retired_cells=report["retired_cells"], held=len(held), output=str(OUT))))
    return painter


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        from release_combat_r36 import guard
        guard()
    painter = plan()
    if args.apply:
        painter.apply("retired_aircraft_port_guards")
