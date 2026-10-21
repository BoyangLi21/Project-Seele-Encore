"""Retract the obsolete north apron outside the retained compact-lift wall.

The native station survey locates this dead extension on the closed north face.
The actual station landing exits south; its wall foot, lift and platform remain.
"""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

from query_blocks import read_box, iter_block_entities
from trim_r53_restored_station_roof import digest, install

DIM = "projectseele:geofront"
LO, HI = (89, -447, -64), (114, -443, -58)
FINISHES = {"projectseele:nerv_floor_panel", "projectseele:nerv_structural_panel",
            "minecraft:chiseled_polished_blackstone", "minecraft:polished_deepslate",
            "minecraft:light_gray_concrete", "minecraft:deepslate_bricks"}


def plan(world, frozen, base, output):
    cells = read_box(frozen, DIM, LO, (114, -437, -58))
    current = read_box(world, DIM, LO, (114, -437, -58))
    assert not list(iter_block_entities(world, DIM, LO, (114, -437, -58)))
    prior = {tuple(r["pos"]): r for r in json.loads(gzip.decompress(
        (base / "station-port254/EXACT_DELTA.json.gz").read_bytes()))}
    rows = []
    for x in range(LO[0], HI[0] + 1):
        for z in range(LO[2], HI[2] + 1):
            # This is a surveyed dead apron, not a platform/room inferred from
            # the free space. Guard against removing any later added structure.
            assert all(cells[x, y, z] == current[x, y, z] == "minecraft:air"
                       for y in range(-442, -436))
            for y in range(LO[1], HI[1] + 1):
                q = (x, y, z)
                state = cells[q]
                assert current[q] == state
                if state == "minecraft:air":
                    continue
                assert state in FINISHES, ("Keep unknown member", q, state)
                old = prior.get(q)
                if old is not None:
                    assert old["after"] == state and old["before"] == "minecraft:air"
                rows.append(dict(pos=q, before=state, after="minecraft:air",
                                 before_nbt=None, after_nbt=None,
                                 reason="retire_native_confirmed_closed_north_lift_apron",
                                 prior_restoration=old is not None))
    changed = {tuple(r["pos"]) for r in rows}
    graph = json.loads(gzip.decompress((world / "nerv_routes_r24.json.gz").read_bytes()))
    assert not any((n[0], n[1] + dy, n[2]) in changed for n in graph["nodes"] for dy in (-1, 0, 1))
    output.mkdir(parents=True, exist_ok=True)
    for name, data in (("EXACT_DELTA.json.gz", rows),
                       ("INVERSE_DELTA.json.gz", [dict(r, before=r["after"], after=r["before"]) for r in rows])):
        (output / name).write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
    report = dict(world=str(world), frozen_original=str(frozen), bounds=[LO, HI],
                  changed_cells=len(rows), materials=Counter(r["before"] for r in rows),
                  prior_restoration_cells=sum(r["prior_restoration"] for r in rows),
                  graph_sha256=digest(world / "nerv_routes_r24.json.gz"),
                  declared_navigation_nodes_affected=0, block_entities_affected=0,
                  retained_wall_foot_z=-57, actual_lift_centre=[93, -442, -52],
                  lift_exit="south", native_visual="pending", installed=False)
    (output / "PLAN.json").write_text(json.dumps(report, indent=2), "utf8")
    print(json.dumps(report))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world", required=True, type=Path)
    p.add_argument("--frozen", required=True, type=Path)
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    if a.apply:
        install(a.world, a.output)
    else:
        plan(a.world, a.frozen, a.base, a.output)
