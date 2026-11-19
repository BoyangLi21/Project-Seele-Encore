"""Check a regional GeoFront road manifest against a cold world copy.

The input is the batches.json produced for the R64 road-end handoff. Pass
--expected old before a trial or --expected new after it. No world data is written.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from query_blocks import iter_selected_sections


DIMENSION = "projectseele:geofront"


def load_rows(index_path):
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index["dimension"] != DIMENSION:
        raise ValueError(f"Unsupported dimension {index['dimension']}")
    aggregate = (index_path.parent / index["aggregate"]).read_bytes()
    if hashlib.md5(aggregate).hexdigest() != index["md5"]:
        raise ValueError("Aggregate MD5 mismatch")
    rows = json.loads(aggregate)
    if len(rows) != index["cells"]:
        raise ValueError("Aggregate row count differs from the manifest")
    aggregate_rows = {tuple(row[:3]): row for row in rows}
    coordinates = {}
    for batch in index["files"]:
        path = index_path.parent / batch["file"]
        payload = path.read_bytes()
        if hashlib.md5(payload).hexdigest() != batch["md5"]:
            raise ValueError(f"MD5 mismatch in {path}")
        rows = json.loads(payload)
        if len(rows) != batch["cells"]:
            raise ValueError(f"Unexpected row count in {path}")
        for row in rows:
            x, y, z, old, new, *_ = row
            position = x, y, z
            if position in coordinates or [x // 512, z // 512] != batch["region"]:
                raise ValueError(f"Duplicate or wrongly grouped coordinate {position}")
            if aggregate_rows.pop(position, None) != row:
                raise ValueError(f"Aggregate differs at {position}")
            if old == new:
                raise ValueError(f"Unchanged block at {position}")
            coordinates[position] = old, new
    if aggregate_rows or len(coordinates) != index["cells"]:
        raise ValueError("Total region row count differs from the manifest")
    return coordinates


def verify(world, coordinates):
    by_chunk = defaultdict(lambda: defaultdict(list))
    for x, y, z in coordinates:
        by_chunk[x // 16, z // 16][y // 16].append((x, y, z))
    count = Counter()
    first_conflicts = []
    for cx, cz, sy, palette, indices in iter_selected_sections(world, DIMENSION, by_chunk):
        positions = by_chunk[cx, cz].pop(sy)
        for x, y, z in positions:
            old, new = coordinates[x, y, z]
            offset = (y % 16) * 256 + (z % 16) * 16 + x % 16
            actual = palette[indices[offset]]
            if actual == old:
                count["old"] += 1
            elif actual == new:
                count["new"] += 1
            else:
                count["conflict"] += 1
                if len(first_conflicts) < 10:
                    first_conflicts.append(dict(x=x, y=y, z=z, old=old, new=new, found=actual))
    count["missing"] = sum(len(points) for sections in by_chunk.values() for points in sections.values())
    return count, first_conflicts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--expected", choices=("old", "new"), required=True)
    args = parser.parse_args()
    coordinates = load_rows(args.index)
    count, conflicts = verify(args.world, coordinates)
    print(json.dumps(dict(dimension=DIMENSION, cells=len(coordinates), observed=count, first_conflicts=conflicts)))
    return 0 if count[args.expected] == len(coordinates) else 1


if __name__ == "__main__":
    raise SystemExit(main())
