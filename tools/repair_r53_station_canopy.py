"""Support the surveyed old experiment-station guide canopy; retire orphan lamps.

The original survey and native photographs define this small repair. No floor,
rail aperture, lift sweep, navigation node or device identity is moved.
"""
import argparse
import gzip
import json
from pathlib import Path

from query_blocks import read_box, iter_block_entities
from trim_r53_restored_station_roof import digest, install

DIM = "projectseele:geofront"


def plan(world, frozen, output):
    bounds = [((99, -469, -86), (107, -462, -78)),
              ((113, -438, -19), (121, -431, -11))]
    cells, tags = {}, {}
    for lo, hi in bounds:
        cells.update(read_box(frozen, DIM, lo, hi))
        tags.update(iter_block_entities(frozen, DIM, lo, hi))
    rows = []

    def put(point, expected, after, reason):
        assert cells[point] == expected, (point, cells[point], expected)
        assert point not in tags, ("Keep full device identity", point)
        rows.append(dict(pos=point, before=expected, after=after,
                         before_nbt=None, after_nbt=None, reason=reason))

    # Two short side piers use the existing passage wall, outside the full
    # five-block walking width. Their heads join the original canopy edge.
    for z in (-84, -80):
        assert cells[106, -467, z] == "projectseele:nerv_wall_panel"
        assert cells[105, -464, z] == "projectseele:nerv_wall_panel"
        for y in range(-466, -463):
            put((106, y, z), "minecraft:air", "projectseele:nerv_structural_panel",
                "support_existing_guide_canopy_from_passage_sidewall")
    # These are flush ceiling fixtures, not long hanging meshes. The frozen
    # columns and native view show that their former roof no longer exists.
    for x, z in ((114, -12), (120, -18)):
        assert all(cells[x, y, z] == "minecraft:air" for y in range(-436, -430))
        put((x, -437, z), "projectseele:nerv_ceiling_light[hanging=true,lit=true]",
            "minecraft:air", "retire_orphan_fixture_after_old_roof_retirement")
    changed = {tuple(r["pos"]) for r in rows}
    graph = json.loads(gzip.decompress((world / "nerv_routes_r24.json.gz").read_bytes()))
    affected = [n[:3] for n in graph["nodes"]
                if any((n[0], n[1] + dy, n[2]) in changed for dy in (-1, 0, 1))]
    assert not affected, ("Keep personnel floors and full body clearance", affected)
    # Match the actual delivery copy before accepting a frozen-original plan.
    for lo, hi in bounds:
        actual = read_box(world, DIM, lo, hi)
        actual_tags = dict(iter_block_entities(world, DIM, lo, hi))
        for r in rows:
            q = tuple(r["pos"])
            if q in actual:
                assert actual[q] == r["before"] and q not in actual_tags, q
    output.mkdir(parents=True, exist_ok=True)
    for name, data in (("EXACT_DELTA.json.gz", rows),
                       ("INVERSE_DELTA.json.gz", [dict(r, before=r["after"], after=r["before"]) for r in rows])):
        (output / name).write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
    report = dict(world=str(world), frozen_original=str(frozen), changed_cells=len(rows),
                  graph_sha256=digest(world / "nerv_routes_r24.json.gz"),
                  declared_navigation_nodes_affected=0, block_entities_affected=0,
                  retained_guide=[103, -466, -82], canopy_support_piers=2,
                  orphan_ceiling_fixtures=2, native_visual="pending", installed=False)
    (output / "PLAN.json").write_text(json.dumps(report, indent=2), "utf8")
    print(json.dumps(report))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world", required=True, type=Path)
    p.add_argument("--frozen", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    if a.apply:
        install(a.world, a.output)
    else:
        plan(a.world, a.frozen, a.output)
