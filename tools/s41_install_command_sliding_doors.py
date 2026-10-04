#!/usr/bin/env python3
"""Replace all measured R28 command-room vanilla doors with 3x2 ports."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

from apply_s20_approved_semantic_repairs import Change, atomic_replace, rewrite_region
from query_blocks import AIR, dimension_dir, read_box, iter_block_entities


ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_S20_RECOVERY_R28"
DIMENSION = "projectseele:geofront"
PACKET = "S41-COMMAND-ROOM-SLIDING-DOORS-R01"
MARKER = ".projectseele_command_sliding_doors_r01.json"
DOORS = (
    (0, 8, -429, 282, "north"),
    (1, 13, -429, 282, "north"),
    (2, 43, -429, 282, "north"),
    (3, 48, -429, 282, "north"),
    (4, 28, -424, 286, "south"),
    (5, 24, -423, 254, "west"),
    (6, 11, -423, 268, "north"),
    (7, 17, -423, 268, "north"),
    (8, 39, -423, 268, "north"),
    (9, 45, -423, 268, "north"),
    (10, 20, -423, 278, "east"),
    (11, 36, -423, 278, "east"),
    (12, 21, -422, 283, "north"),
    (13, 35, -422, 283, "north"),
    (14, 24, -418, 254, "west"),
    (15, 28, -413, 284, "south"),
    (16, 24, -409, 270, "north"),
    (17, 32, -409, 270, "north"),
    (18, 28, -406, 272, "north"),
)
APERTURE_ALLOWED = {
    "minecraft:birch_door", "minecraft:spruce_door",
    "minecraft:smooth_stone", "minecraft:stone",
    "minecraft:red_concrete", "minecraft:blue_concrete",
    "minecraft:black_concrete", "minecraft:air",
    "minecraft:cave_air", "minecraft:void_air",
}


def name(state: str) -> str:
    return state.split("[", 1)[0]


def vectors(facing: str) -> tuple[tuple[int, int], tuple[int, int]]:
    if facing in {"north", "south"}:
        return (1, 0), (0, 1)
    return (0, 1), (1, 0)


def complete_id15_stair_throat(cells, block_entities):
    expected = {(27, -414, 283): ('minecraft:smooth_stone', 'minecraft:stone_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]'), (27, -413, 283): ('minecraft:black_concrete', 'minecraft:air'), (27, -412, 283): ('minecraft:smooth_stone', 'minecraft:air'), (29, -414, 283): ('minecraft:smooth_stone', 'minecraft:stone_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]'), (29, -413, 283): ('minecraft:black_concrete', 'minecraft:air'), (29, -412, 283): ('minecraft:smooth_stone', 'minecraft:air')}
    guards = {(28, -414, 283): 'minecraft:stone_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]', (28, -415, 282): 'minecraft:white_concrete', (27, -414, 284): 'minecraft:polished_andesite', (28, -414, 284): 'minecraft:polished_andesite', (29, -414, 284): 'minecraft:polished_andesite', (26, -414, 283): 'minecraft:smooth_stone', (26, -413, 283): 'minecraft:yellow_concrete', (26, -412, 283): 'minecraft:smooth_stone', (30, -414, 283): 'minecraft:smooth_stone', (30, -413, 283): 'minecraft:yellow_concrete', (30, -412, 283): 'minecraft:smooth_stone'}
    for pos, state in guards.items():
        if cells.get(pos) != state or pos in block_entities:
            raise RuntimeError("ID15 authored approach guard changed: " + str(pos))
    changes = []
    for pos, (before, after) in sorted(expected.items()):
        if pos in block_entities or cells.get(pos) not in {before, after}:
            raise RuntimeError("ID15 exact approach preimage or full BE changed: " + str(pos))
        if cells[pos] != after:
            changes.append((pos, after))
    return changes


def plan(world: Path) -> tuple[list[Change], list[dict]]:
    cells = read_box(world, DIMENSION, (-20, -445, 225),
                     (80, -285, 380), None)
    changes: dict[tuple[int, int, int], Change] = {}
    report = []

    def add(pos: tuple[int, int, int], after: str, reason: str) -> None:
        before = cells.get(pos, "minecraft:air")
        if before != after:
            changes[pos] = Change(
                PACKET, *pos, before, after,
                "human_authorized_command_sliding_doors", reason)

    for door_id, x, y, z, facing in DOORS:
        lower = cells.get((x, y, z), "minecraft:air")
        upper = cells.get((x, y + 1, z), "minecraft:air")
        if not name(lower).endswith("_door") or "half=lower" not in lower:
            raise RuntimeError(
                f"door {door_id} lower cell changed at {(x, y, z)}: {lower}")
        if name(upper) != name(lower) or "half=upper" not in upper:
            raise RuntimeError(
                f"door {door_id} upper cell changed at {(x, y + 1, z)}: {upper}")
        measured_facing = re.search(r"facing=([a-z]+)", lower)
        if measured_facing is None or measured_facing.group(1) != facing:
            raise RuntimeError(
                f"door {door_id} facing changed: {lower}")

        (wx, wz), (nx, nz) = vectors(facing)
        aperture = []
        for vertical in (0, 1):
            for width in (-1, 0, 1):
                pos = (x + wx * width, y + vertical, z + wz * width)
                before = cells.get(pos, "minecraft:air")
                if name(before) not in APERTURE_ALLOWED:
                    raise RuntimeError(
                        f"door {door_id} aperture has authored fixture at {pos}: {before}")
                add(pos, "minecraft:barrier", "install_closed_3x2_aperture")
                aperture.append(pos)

        # Three silver lintel blocks keep the enlarged port legible without
        # replacing the authored side walls, stairs or nearby ladder shafts.
        for width in (-1, 0, 1):
            add((x + wx * width, y + 2, z + wz * width),
                "minecraft:iron_block", "install_silver_lintel")

        buttons = []
        for sign, button_facing in ((1, "south" if nx == 0 else "east"),
                                    (-1, "north" if nx == 0 else "west")):
            pos = (x + nx * sign, y + 2, z + nz * sign)
            before = cells.get(pos, "minecraft:air")
            if before not in AIR:
                continue
            add(pos, "minecraft:stone_button[face=wall,facing="
                + button_facing + ",powered=false]",
                "install_sliding_door_button")
            buttons.append(pos)
        if not buttons:
            raise RuntimeError(f"door {door_id} has no accessible button face")
        report.append({
            "id": door_id,
            "lower": [x, y, z],
            "facing": facing,
            "axis": "x" if wx else "z",
            "aperture": aperture,
            "buttons": buttons,
        })

    approach_tags = dict(iter_block_entities(
        world, DIMENSION, (26, -415, 282), (30, -412, 284)))
    for pos, after in complete_id15_stair_throat(cells, approach_tags):
        add(pos, after, "complete_ID15_original_three_lane_south_stair_throat")

    return (sorted(changes.values(), key=lambda c: (c.y, c.z, c.x)),
            report)


def apply(world: Path, changes: list[Change], doors: list[dict]) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    artifact = ROOT / "artifacts" / f"s41_command_sliding_doors_{stamp}"
    backup = artifact / "region_before"
    backup.mkdir(parents=True, exist_ok=False)
    root = dimension_dir(world, DIMENSION)
    by_region: dict[tuple[int, int], list[Change]] = defaultdict(list)
    for change in changes:
        by_region[(change.x >> 9, change.z >> 9)].append(change)
    originals = {}
    replaced = []
    try:
        for (rx, rz), selected in sorted(by_region.items()):
            path = root / "region" / f"r.{rx}.{rz}.mca"
            before = path.read_bytes()
            shutil.copy2(path, backup / path.name)
            originals[path] = before
            grouped: dict[tuple[int, int], list[Change]] = defaultdict(list)
            for change in selected:
                grouped[(change.x >> 4, change.z >> 4)].append(change)
            atomic_replace(path, rewrite_region(path, grouped))
            replaced.append(path)
    except Exception:
        for path in replaced:
            atomic_replace(path, originals[path])
        raise

    for filename, reverse in (("block_diff.csv", False),
                              ("inverse_patch.csv", True)):
        with (artifact / filename).open("w", encoding="utf-8",
                                        newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("x", "y", "z", "before", "after", "reason"))
            for change in changes:
                writer.writerow((change.x, change.y, change.z,
                                 change.after if reverse else change.before,
                                 change.before if reverse else change.after,
                                 change.reason))
    receipt = {
        "schema": 1,
        "status": "APPLIED_WITH_EXACT_REGION_BACKUP",
        "packet": PACKET,
        "world": str(world),
        "doors": doors,
        "blocks": len(changes),
        "reasons": dict(sorted(Counter(
            change.reason for change in changes).items())),
        "regionBeforeSha256": {
            path.name: hashlib.sha256(data).hexdigest()
            for path, data in originals.items()
        },
    }
    (artifact / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    (world / MARKER).write_text(json.dumps({
        "schema": 1,
        "packet": PACKET,
        "doors": len(doors),
        "artifact": str(artifact.resolve()),
    }, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, default=WORLD)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    world = args.world.resolve()
    changes, doors = plan(world)
    summary = {
        "packet": PACKET,
        "world": str(world),
        "doorCount": len(doors),
        "blocks": len(changes),
        "buttons": sum(len(door["buttons"]) for door in doors),
        "reasons": dict(sorted(Counter(
            change.reason for change in changes).items())),
    }
    print(json.dumps(summary, indent=2))
    if args.apply:
        print(json.dumps({"applied": True,
                          "artifact": str(apply(world, changes, doors))},
                         indent=2))


if __name__ == "__main__":
    main()
