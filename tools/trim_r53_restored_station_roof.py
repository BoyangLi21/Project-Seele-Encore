"""Retire the old well roof accidentally restored south of the experiment station.

The exact prior retirement and restoration supply ownership. This does not
discover construction permission from air, or remove the retained station floor.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from query_blocks import read_box, iter_block_entities

DIM = "projectseele:geofront"
LO, HI = (89, -447, -8), (111, -443, 12)
MATERIALS = {"minecraft:deepslate_bricks", "minecraft:polished_deepslate"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan(world, base, output):
    inherited = json.loads(gzip.decompress(
        (base / "station-port254/EXACT_DELTA.json.gz").read_bytes()))
    owners = {tuple(row["pos"]): row for row in inherited}
    cells = read_box(world, DIM, LO, HI)
    tags = dict(iter_block_entities(world, DIM, LO, HI))
    rows = []
    # This roof ends well south of the measured enclosed station lobby.
    # Its polished top has no declared personnel node; the lower ground stays.
    for x in range(LO[0], HI[0] + 1):
        for z in range(LO[2], HI[2] + 1):
            top = (x, HI[1], z)
            if cells[top] != "minecraft:polished_deepslate":
                continue
            for y in range(LO[1], HI[1] + 1):
                point = (x, y, z)
                old = owners.get(point)
                assert old is not None, ("No authored restoration", point)
                assert old["after"] == cells[point], ("Changed since restoration", point)
                assert old["before"] in {"minecraft:air", "minecraft:black_concrete"}, (
                    "Unexpected prior retirement surface", point)
                assert cells[point] in MATERIALS, ("Keep station fabric", point, cells[point])
                assert point not in tags and old.get("before_nbt") is None and old.get("after_nbt") is None
                rows.append(dict(pos=point, before=cells[point], after=old["before"],
                                 before_nbt=None, after_nbt=None,
                                 reason="retire_restored_old_well_roof_outside_station_lobby"))
    assert rows
    changed = {tuple(row["pos"]) for row in rows}
    graph = json.loads(gzip.decompress((world / "nerv_routes_r24.json.gz").read_bytes()))
    affected = [node[:3] for node in graph["nodes"]
                if any((node[0], node[1] + dy, node[2]) in changed for dy in (-1, 0, 1))]
    assert not affected, ("Preserve every declared personnel floor", affected)
    output.mkdir(parents=True, exist_ok=True)
    for name, delta in (
            ("EXACT_DELTA.json.gz", rows),
            ("INVERSE_DELTA.json.gz", [dict(row, before=row["after"], after=row["before"]) for row in rows])):
        (output / name).write_bytes(gzip.compress(json.dumps(delta).encode(), mtime=0))
    report = dict(world=str(world), bounds=[LO, HI], changed_cells=len(rows),
                  declared_navigation_nodes_affected=0, block_entities_affected=0,
                  source="Exact prior station-port254 restoration of retired old well roof",
                  station_lobby_floor_and_lift_preserved=True, native_visual="pending",
                  graph_sha256=digest(world / "nerv_routes_r24.json.gz"), installed=False)
    (output / "PLAN.json").write_text(json.dumps(report, indent=2), "utf8")
    print(json.dumps(report))

def install(world, output):
    import msvcrt
    import shutil
    import nbtlib
    from repair_r53_reported_landings import apply
    from retire_r53_old_yashima_platform import packed
    from apply_s20_approved_semantic_repairs import parse_state

    rows = json.loads(gzip.decompress((output / "EXACT_DELTA.json.gz").read_bytes()))
    report = json.loads((output / "PLAN.json").read_text("utf8"))
    assert digest(world / "nerv_routes_r24.json.gz") == report["graph_sha256"]
    data = world / "dimensions/projectseele/geofront/data"
    headers = list(data.glob("projectseele_city_rigid_topology_r45_*.dat"))
    assert len(headers) == 1
    folder = data / str(nbtlib.load(headers[0])["data"]["GenerationFolder"]) / "chunks"
    chunks = {}
    for row in rows:
        chunks.setdefault((row["pos"][0] // 16, row["pos"][2] // 16), []).append(row)
    caches, cache_cells = {}, 0
    for (cx, cz), batch in chunks.items():
        path = folder / f"{cx}_{cz}.dat"
        if not path.exists():
            continue
        document = nbtlib.load(path)
        entries = {int(entry["Pos"]): entry for entry in document["Static"]}
        palette = document["Palette"]
        lookup = {state.snbt(): index for index, state in enumerate(palette)}
        for row in batch:
            entry = entries.get(packed(row["pos"]))
            if entry is None:
                continue
            assert palette[int(entry["StateId"])] == parse_state(row["before"]), (
                "Changed static maintenance cache", row["pos"])
            state = parse_state(row["after"])
            if state.snbt() not in lookup:
                lookup[state.snbt()] = len(palette)
                palette.append(state)
            entry["StateId"] = nbtlib.Int(lookup[state.snbt()])
            cache_cells += 1
        caches[path] = document
    regions = {world / "dimensions/projectseele/geofront/region" / f"r.{cx//32}.{cz//32}.mca"
               for cx, cz in chunks}
    # Files below are independent from block geometry and the derived static cache.
    protected = [world / "level.dat"]
    for folder_path in (world / "playerdata", world / "data",
                        world / "dimensions/projectseele/geofront/entities", data):
        protected.extend(p for p in folder_path.glob("*") if p.is_file())
    protected.extend(world / name for name in (
        "nerv_routes_r24.json.gz", "nearest_lift_paths_r44.json.gz", "r53_personnel_walking_graph.json.gz"))
    progress = {str(path.relative_to(world)): digest(path) for path in protected}
    # Stage cache files and cold backups before any world replacement.
    for path in regions | caches.keys():
        backup = output / "before" / path.relative_to(world)
        backup.parent.mkdir(parents=True, exist_ok=True)
        assert not backup.exists(), ("Installation already started; inspect receipt", backup)
        shutil.copy2(path, backup)
    apply(world, output)
    with (world / "session.lock").open("r+b") as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        for path, document in caches.items():
            staged = path.with_suffix(".roof-trim.tmp")
            document.save(staged, gzipped=True)
            staged.replace(path)
            assert nbtlib.load(path) == document
        assert progress == {str(path.relative_to(world)): digest(path) for path in protected}
    (output / "INSTALL_RECEIPT.json").write_text(json.dumps(dict(
        world=str(world), changed_cells=len(rows), derived_static_cells=cache_cells,
        progress_files=progress, navigation_unchanged=True, native_visual="pending"), indent=2), "utf8")
    print("Installed roof retirement:", len(rows), "static cache cells:", cache_cells)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        install(args.world, args.output)
    else:
        plan(args.world, args.base, args.output)
