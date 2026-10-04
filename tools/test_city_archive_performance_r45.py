"""Read-only R44 cargo scale, lossless gzip and write-ahead scope regression.

This does not launch Minecraft or write a world. Python compression timings
are reproducible CPU evidence, not a claim about native tick/travel duration.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import statistics
import time
from pathlib import Path

import nbtlib

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "projectseele_tokyo3_building_archive_r44_"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "artifacts/server-ready-r44-stage/stage/world/dimensions/projectseele/geofront/data")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/rebuild_r45/city_performance/archive_scale_and_lossless.json")
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    assert 1 <= args.repeat <= 10
    paths = sorted(args.data.glob(PREFIX + "*.dat"))
    assert len(paths) == 93, f"Expected all 93 per-tower archives, got {len(paths)}"
    identity_path = args.data / "projectseele_tokyo3_building_world_id_r44.dat"
    identity = str(nbtlib.load(identity_path)["data"]["WorldUUID"])
    retraction_path = args.data / "projectseele_tokyo3_retraction.dat"
    retraction = nbtlib.load(retraction_path).unpack()
    records, raw_archives = [], []
    for path in paths:
        packed = path.read_bytes()
        raw = gzip.decompress(packed)
        parsed = nbtlib.File.parse(io.BytesIO(raw))
        data = parsed["data"]
        assert int(data["Version"]) == 1
        assert str(data["WorldUUID"]) == identity
        assert len(data["Buildings"]) == 1
        building = data["Buildings"][0]
        assert "FixedStreetCore" in building
        cargo = building["Cargo"]
        unique_states = {cell["State"].snbt() for cell in cargo}
        transaction = building.get("Transaction", {})
        old_keys = [int(cell["Pos"]) for cell in cargo]
        new_keys = [int(write["Pos"]) for write in transaction.get("Writes", [])]
        # Primitive sorting preserves the old signed TreeMap traversal order,
        # including negative X/Y/Z packed positions and overlapping ownership.
        before = dict.fromkeys(old_keys)
        after = dict.fromkeys(new_keys)
        old_union = dict(before)
        old_union.update(after)
        ordered = sorted(set(before) | set(after))
        assert ordered == sorted(old_union)
        height = int(building["Height"])
        def visible(depth: int) -> tuple[int, int]:
            return max(0, height - depth), max(0, min(height, depth - max(height, 60)))
        active = sum(visible(d) != visible(d + 1) for d in range(312))
        records.append(dict(file=path.name, sha256=sha(packed), raw_sha256=sha(raw),
            bytes=len(packed), raw_bytes=len(raw), height=height, half=int(building["Half"]),
            active_layers_one_direction=active, cargo_cells=len(cargo),
            unique_cargo_states=len(unique_states),
            block_entities=sum("NBT" in cell for cell in cargo),
            fixed_core=bool(building["FixedStreetCore"]),
            fixed_anchors=len(building["NegativeDomeAnchorMask"]),
            journal_writes=len(transaction.get("Writes", []))))
        raw_archives.append(raw)
    compression = {}
    # Alternate levels each repeat to reduce warm-cache/order distortion.
    for repetition in range(args.repeat):
        for level in ((6, 1) if repetition % 2 == 0 else (1, 6)):
            began = time.perf_counter()
            outputs = [gzip.compress(raw, compresslevel=level, mtime=0) for raw in raw_archives]
            elapsed = time.perf_counter() - began
            assert all(gzip.decompress(packed) == raw for packed, raw in zip(outputs, raw_archives))
            entry = compression.setdefault(str(level), dict(seconds=[], bytes=sum(map(len, outputs))))
            entry["seconds"].append(elapsed)
    for entry in compression.values():
        entry["median_seconds"] = statistics.median(entry["seconds"])
    archive_source = (ROOT / "src/main/java/com/projectseele/world/Tokyo3BuildingArchiveR44.java").read_text("utf8")
    director_source = (ROOT / "src/main/java/com/projectseele/world/Tokyo3RetractionDirector.java").read_text("utf8")
    assert "level.getDataStorage().save()" not in archive_source
    assert "file.force(true)" in archive_source and "StandardCopyOption.ATOMIC_MOVE" in archive_source
    assert archive_source.index("persistWriteAhead();") < archive_source.index("TravelStep step = apply(level, cargo.transaction")
    assert "2048" in archive_source and "writes<4096" in director_source and "8_000_000L" in director_source
    assert 'TICKS_PER_LAYER = 5;' in director_source
    pack_source = (ROOT / "tools/build_server_ready_pack.py").read_text("utf8")
    heap = pack_source.split("def jvm_args() -> str:", 1)[1].split("def build_server", 1)[0]
    assert "-Xmx20G" in heap and "-Xms2G" in heap and "-Xms20G" not in heap
    result = dict(schema="projectseele.city-performance-r45.v1", data_directory=str(args.data.resolve()),
        world_uuid=identity, identity_sha256=sha(identity_path.read_bytes()),
        retraction_sha256=sha(retraction_path.read_bytes()), retraction=retraction,
        archives=len(records), fixed_cores=sum(r["fixed_core"] for r in records),
        cargo_cells=sum(r["cargo_cells"] for r in records), block_entities=sum(r["block_entities"] for r in records),
        state_nbt_builds_per_full_save_before=sum(r["cargo_cells"] for r in records),
        state_nbt_builds_per_full_save_after=sum(r["unique_cargo_states"] for r in records),
        raw_bytes=sum(r["raw_bytes"] for r in records), compressed_bytes=sum(r["bytes"] for r in records),
        active_tower_layers_one_direction=sum(r["active_layers_one_direction"] for r in records),
        raw_compression_lower_bound_one_direction=sum(r["raw_bytes"] * r["active_layers_one_direction"] for r in records),
        compression=compression, gzip_level_6_over_1_cpu_ratio=compression["6"]["median_seconds"] / compression["1"]["median_seconds"],
        modified_source_sha256=dict(archive=sha(archive_source.encode()), director=sha(director_source.encode()), pack=sha(pack_source.encode())),
        read_only_world=True, native_minecraft_test=False, records=records)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("records", "retraction", "modified_source_sha256")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
