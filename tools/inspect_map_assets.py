#!/usr/bin/env python3
"""Inspect local-only Minecraft worlds used by Project SEELE.

The project evaluates maps from several Minecraft generations.  The Bilibili
Tokyo-3 world predates the flattening (numeric block ids), while the command
module is a 1.21.7 palette world and the runtime remains Forge 1.20.1.  Loading
those worlds blindly either loses blocks or rejects the save.  This tool reads
both Anvil layouts without starting Minecraft and produces a compact report and
an artificial-block plan view that can be reviewed before conversion.

Third-party inputs and generated reports stay below ``external-assets/`` and
must not be committed or redistributed without the authors' permission.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import struct
from collections import Counter
from typing import Iterator
import zlib

import nbtlib
import numpy as np


AIR_NAMES = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
NATURAL_NAMES = AIR_NAMES | {
    "minecraft:stone", "minecraft:deepslate", "minecraft:dirt",
    "minecraft:grass_block", "minecraft:bedrock", "minecraft:water",
    "minecraft:lava", "minecraft:gravel", "minecraft:sand",
    "minecraft:red_sand", "minecraft:clay", "minecraft:snow",
    "minecraft:snow_block", "minecraft:ice", "minecraft:packed_ice",
    "minecraft:blue_ice", "minecraft:andesite", "minecraft:diorite",
    "minecraft:granite", "minecraft:tuff", "minecraft:calcite",
    "minecraft:dripstone_block", "minecraft:netherrack", "minecraft:end_stone",
}

# Numeric ids that are normally terrain, vegetation, fluids or ore in 1.7.x.
# Everything else is treated as authored construction for the density pass.
LEGACY_NATURAL_IDS = {
    0, 1, 2, 3, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 21, 24,
    31, 32, 37, 38, 39, 40, 48, 49, 56, 73, 74, 78, 79, 80, 81, 82, 83,
    86, 87, 88, 89, 97, 106, 110, 111, 112, 121, 129, 153, 161, 162, 174,
}

MASK_64 = (1 << 64) - 1


def read_level(world: Path) -> dict:
    root = nbtlib.load(world / "level.dat")
    data = root.get("Data", root)
    version = data.get("Version", {})
    return {
        "name": str(data.get("LevelName", world.name)),
        "data_version": int(data.get("DataVersion", 0)),
        "version_name": str(version.get("Name", "pre-flattening"))
        if hasattr(version, "get") else "pre-flattening",
        "spawn": [int(data.get("SpawnX", 0)), int(data.get("SpawnY", 64)),
                  int(data.get("SpawnZ", 0))],
    }


def region_chunks(region_path: Path, bounds: tuple[int, int, int, int], selected_chunks=None
                  ) -> Iterator[tuple[int, int, nbtlib.File]]:
    """Yield chunks inside inclusive chunk-coordinate bounds."""
    parts = region_path.stem.split(".")
    region_x, region_z = int(parts[1]), int(parts[2])
    min_x, max_x, min_z, max_z = bounds
    if region_x*32>max_x or region_x*32+31<min_x or region_z*32>max_z or region_z*32+31<min_z:return
    data = region_path.read_bytes()
    if len(data) < 8192:
        return
    min_x, max_x, min_z, max_z = bounds
    for index in range(1024):
        chunk_x = region_x * 32 + index % 32
        chunk_z = region_z * 32 + index // 32
        if not (min_x <= chunk_x <= max_x and min_z <= chunk_z <= max_z):
            continue
        if selected_chunks is not None and (chunk_x,chunk_z) not in selected_chunks:continue
        location = struct.unpack_from(">I", data, index * 4)[0]
        sector = location >> 8
        if sector == 0:
            continue
        position = sector * 4096
        if position + 5 > len(data):
            continue
        length = struct.unpack_from(">I", data, position)[0]
        compression = data[position + 4]
        raw = data[position + 5:position + 4 + length]
        try:
            if compression == 1:
                raw = gzip.decompress(raw)
            elif compression == 2:
                raw = zlib.decompress(raw)
            elif compression != 3:
                continue
            yield chunk_x, chunk_z, nbtlib.File.parse(BytesIO(raw))
        except Exception:
            # Corrupt or unsupported chunks should not invalidate the rest of
            # a local evaluation world.  The report counts successful chunks.
            continue


def iter_chunks(world: Path, bounds: tuple[int, int, int, int], selected_chunks=None
                ) -> Iterator[tuple[int, int, nbtlib.File]]:
    region_dir = world / "region"
    for region_path in region_dir.glob("r.*.*.mca"):
        yield from region_chunks(region_path, bounds, selected_chunks)


def palette_name(entry) -> str:
    return str(entry.get("Name", "minecraft:air"))


def palette_state(entry) -> str:
    name = palette_name(entry)
    properties = entry.get("Properties")
    if not properties:
        return name
    values = ",".join(f"{key}={properties[key]}" for key in sorted(properties))
    return f"{name}[{values}]"


def decode_modern_section(section) -> tuple[list, np.ndarray]:
    states = section.get("block_states")
    if not states:
        return [], np.zeros(4096, dtype=np.int32)
    palette = list(states.get("palette", []))
    if len(palette) <= 1:
        return palette, np.zeros(4096, dtype=np.int32)
    bits = max(4, (len(palette) - 1).bit_length())
    values_per_long = 64 // bits
    packed = np.array([int(value) & MASK_64
                       for value in states.get("data", [])], dtype=np.uint64)
    unpacked = np.empty(packed.size * values_per_long, dtype=np.int32)
    mask = np.uint64((1 << bits) - 1)
    for offset in range(values_per_long):
        unpacked[offset::values_per_long] = (
            (packed >> np.uint64(offset * bits)) & mask).astype(np.int32)
    if unpacked.size < 4096:
        padded = np.zeros(4096, dtype=np.int32)
        padded[:unpacked.size] = unpacked
        unpacked = padded
    return palette, unpacked[:4096]


def decode_legacy_section(section) -> tuple[np.ndarray, np.ndarray]:
    low = np.frombuffer(bytes(int(value) & 0xFF
                              for value in section["Blocks"]), dtype=np.uint8)
    block_ids = low.astype(np.uint16)
    if "Add" in section:
        packed_add = np.frombuffer(bytes(int(value) & 0xFF
                                         for value in section["Add"]),
                                   dtype=np.uint8)
        high = np.empty(4096, dtype=np.uint16)
        high[0::2] = packed_add & 0x0F
        high[1::2] = packed_add >> 4
        block_ids |= high << 8
    packed_data = np.frombuffer(bytes(int(value) & 0xFF
                                      for value in section.get("Data", [])),
                                dtype=np.uint8)
    metadata = np.zeros(4096, dtype=np.uint8)
    if packed_data.size:
        metadata[0::2] = packed_data & 0x0F
        metadata[1::2] = packed_data >> 4
    return block_ids, metadata


def state_colour(state: str) -> tuple[int, int, int]:
    text = state.lower()
    colours = (
        ("orange", (230, 104, 28)), ("red", (192, 45, 45)),
        ("purple", (120, 65, 170)), ("magenta", (190, 65, 170)),
        ("pink", (232, 130, 170)), ("lime", (110, 190, 45)),
        ("green", (45, 130, 70)), ("cyan", (45, 150, 165)),
        ("light_blue", (90, 170, 220)), ("blue", (55, 80, 175)),
        ("yellow", (230, 195, 45)), ("brown", (115, 78, 48)),
        # Black concrete is the dominant command-module shell.  Keep it dark
        # in reports, but visibly separated from the near-black canvas.
        ("black", (62, 66, 76)), ("gray", (105, 110, 118)),
        ("grey", (95, 100, 108)), ("white", (224, 226, 228)),
        ("quartz", (226, 220, 207)), ("iron", (190, 195, 198)),
        ("glass", (135, 190, 205)), ("water", (48, 94, 190)),
        ("lcl", (235, 105, 24)), ("wood", (145, 105, 65)),
        ("plank", (145, 105, 65)), ("brick", (150, 78, 66)),
        ("stone", (115, 118, 122)), ("deepslate", (60, 62, 68)),
    )
    for needle, colour in colours:
        if needle in text:
            return colour
    # Python randomizes hash() between processes. A diagnostic palette must
    # not recolour unchanged buildings in successive before/after renders.
    value = int.from_bytes(hashlib.sha256(state.encode('utf8')).digest()[:4], 'little')
    return 70 + value % 130, 70 + (value >> 8) % 130, 70 + (value >> 16) % 130


def legacy_colour(block_id: int, metadata: int) -> tuple[int, int, int]:
    if block_id == 35:
        wool = [(220, 220, 220), (230, 125, 35), (185, 80, 175),
                (85, 160, 210), (220, 190, 45), (100, 180, 50),
                (225, 130, 165), (75, 75, 75), (150, 150, 150),
                (45, 130, 145), (110, 55, 160), (45, 65, 150),
                (105, 70, 45), (55, 120, 45), (165, 45, 45), (28, 30, 35)]
        return wool[metadata & 15]
    table = {
        5: (145, 105, 65), 20: (135, 190, 205), 41: (230, 190, 45),
        42: (190, 195, 198), 45: (150, 78, 66), 57: (75, 210, 220),
        89: (230, 190, 85), 98: (105, 108, 112), 101: (88, 90, 95),
        102: (150, 195, 205), 123: (210, 65, 55), 133: (45, 165, 115),
        152: (175, 45, 40), 155: (226, 220, 207), 159: (145, 145, 145),
    }
    return table.get(block_id, (80 + block_id * 31 % 140,
                                80 + block_id * 53 % 140,
                                80 + block_id * 71 % 140))


def update_plan(plan_y: np.ndarray, plan_rgb: np.ndarray, indices: np.ndarray,
                chunk_x: int, chunk_z: int, section_y: int,
                bounds: tuple[int, int, int, int], colour_for_index) -> None:
    min_chunk_x, _, min_chunk_z, _ = bounds
    image_x = (chunk_x - min_chunk_x) * 16
    image_z = (chunk_z - min_chunk_z) * 16
    for local_y in range(16):
        layer = indices[(indices >> 8) == local_y]
        if layer.size == 0:
            continue
        xs = layer & 15
        zs = (layer >> 4) & 15
        absolute_y = section_y * 16 + local_y
        colours = np.array([colour_for_index(int(index)) for index in layer],
                           dtype=np.uint8)
        plan_y[image_z + zs, image_x + xs] = absolute_y
        plan_rgb[image_z + zs, image_x + xs] = colours


def inspect_world(world: Path, radius: int, output: Path,
                  slice_levels: list[int] | None = None) -> dict:
    from PIL import Image

    level = read_level(world)
    spawn_x, _, spawn_z = level["spawn"]
    centre_x, centre_z = spawn_x // 16, spawn_z // 16
    bounds = (centre_x - radius, centre_x + radius,
              centre_z - radius, centre_z + radius)
    width = (bounds[1] - bounds[0] + 1) * 16
    length = (bounds[3] - bounds[2] + 1) * 16
    plan_y = np.full((length, width), -32768, dtype=np.int16)
    plan_rgb = np.zeros((length, width, 3), dtype=np.uint8)
    plan_rgb[:] = (22, 25, 31)
    requested_slices = sorted(set(slice_levels or []))
    slice_rgb = {y: np.full((length, width, 3), (22, 25, 31),
                            dtype=np.uint8) for y in requested_slices}
    block_counts: Counter[str] = Counter()
    y_counts: Counter[int] = Counter()
    chunk_density: list[dict] = []
    bbox = [10**9, 10**9, 10**9, -10**9, -10**9, -10**9]
    parsed_chunks = 0
    legacy = level["data_version"] == 0
    natural_lookup = np.zeros(4096, dtype=np.bool_)
    natural_lookup[list(LEGACY_NATURAL_IDS)] = True

    for chunk_x, chunk_z, root in iter_chunks(world, bounds):
        parsed_chunks += 1
        data = root.get("Level", root)
        sections = data.get("Sections", data.get("sections", []))
        density = 0
        for section in sections:
            section_y = int(section["Y"])
            if legacy:
                ids, metadata = decode_legacy_section(section)
                values, counts = np.unique(ids[ids != 0], return_counts=True)
                for value, count in zip(values, counts):
                    block_counts[str(int(value))] += int(count)
                artificial = np.flatnonzero((ids != 0) & ~natural_lookup[ids])
                colour = lambda index, ids=ids, metadata=metadata: legacy_colour(
                    int(ids[index]), int(metadata[index]))
            else:
                palette, indices = decode_modern_section(section)
                if not palette:
                    continue
                names = [palette_name(entry) for entry in palette]
                counts = np.bincount(indices, minlength=len(names))
                for name, count in zip(names, counts):
                    if count:
                        block_counts[name] += int(count)
                artificial_palette = np.array(
                    [name not in NATURAL_NAMES for name in names], dtype=np.bool_)
                artificial = np.flatnonzero(artificial_palette[indices])
                colour = lambda index, indices=indices, palette=palette: state_colour(
                    palette_state(palette[int(indices[index])]))
            if artificial.size == 0:
                continue
            density += int(artificial.size)
            xs = chunk_x * 16 + (artificial & 15)
            zs = chunk_z * 16 + ((artificial >> 4) & 15)
            ys = section_y * 16 + (artificial >> 8)
            bbox[0] = min(bbox[0], int(xs.min()))
            bbox[1] = min(bbox[1], int(ys.min()))
            bbox[2] = min(bbox[2], int(zs.min()))
            bbox[3] = max(bbox[3], int(xs.max()))
            bbox[4] = max(bbox[4], int(ys.max()))
            bbox[5] = max(bbox[5], int(zs.max()))
            levels, counts = np.unique(ys, return_counts=True)
            for y, count in zip(levels, counts):
                y_counts[int(y)] += int(count)
            update_plan(plan_y, plan_rgb, artificial, chunk_x, chunk_z,
                        section_y, bounds, colour)
            for absolute_y in requested_slices:
                local_y = absolute_y - section_y * 16
                if not 0 <= local_y < 16:
                    continue
                layer = artificial[(artificial >> 8) == local_y]
                if layer.size == 0:
                    continue
                image_x = (chunk_x - bounds[0]) * 16
                image_z = (chunk_z - bounds[2]) * 16
                xs = layer & 15
                zs = (layer >> 4) & 15
                colours = np.array([colour(int(index)) for index in layer],
                                   dtype=np.uint8)
                slice_rgb[absolute_y][image_z + zs, image_x + xs] = colours
        if density:
            chunk_density.append({"x": chunk_x, "z": chunk_z,
                                  "artificial_blocks": density})

    output.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(plan_rgb, "RGB")
    image.save(output / "artificial_plan.png")
    slice_paths = {}
    for y, pixels in slice_rgb.items():
        path = output / f"artificial_slice_y{y}.png"
        Image.fromarray(pixels, "RGB").save(path)
        slice_paths[str(y)] = str(path.resolve())
    valid_bbox = bbox if bbox[0] != 10**9 else None
    report = {
        **level,
        "legacy": legacy,
        "chunk_radius": radius,
        "chunk_bounds": list(bounds),
        "parsed_chunks": parsed_chunks,
        "artificial_bbox": valid_bbox,
        "artificial_blocks": int(sum(y_counts.values())),
        "top_blocks": block_counts.most_common(60),
        "top_y_levels": y_counts.most_common(60),
        "dense_chunks": sorted(chunk_density,
                               key=lambda value: value["artificial_blocks"],
                               reverse=True)[:100],
        "plan": str((output / "artificial_plan.png").resolve()),
        "slices": slice_paths,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("world", type=Path)
    parser.add_argument("--radius-chunks", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--slice-y", type=int, action="append", default=[])
    args = parser.parse_args()
    report = inspect_world(args.world.resolve(), args.radius_chunks,
                           args.output.resolve(), args.slice_y)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
