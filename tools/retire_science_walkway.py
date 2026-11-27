"""Upgrade an offline R753 world copy. Keep the R752 site survey and unmodified R753 input separate."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "map_buildings"))
from dogma_recommission import Works
from dogma_terminal_finish import (
    clear_entrance,
    remove_east_jamb,
    remove_upper_walk,
    repaint_existing,
)
from map_buildings.mca import World
from science_walk_routes import rewrite_routes, lost_floor
from write_deep_cells import REGION


def retire_fixtures(source, dest, before, after):
    path = "facility_lighting_r30.json"
    lights = json.loads((source / path).read_bytes())
    lights["constant_lamps"] = [
        p
        for p in lights["constant_lamps"]
        if not (
            192 <= p[0] <= 211
            and 403 <= p[2] <= 546
            and before.get(*p) != after.get(*p)
        )
    ]
    (dest / path).write_text(
        json.dumps(lights, ensure_ascii=False, separators=(",", ":")), encoding="utf8"
    )
    name = "quality_walk_cases.json"
    cases = json.loads((source / name).read_bytes())

    def retired(row):
        points = row.get("path", []) + [
            row[key] for key in ("start", "end") if key in row
        ]
        return any(lost_floor(np.floor(p).astype(int), before, after) for p in points)

    keep = [c for c in cases if not retired(c)]
    (dest / name).write_text(
        json.dumps(keep, ensure_ascii=False, separators=(",", ":")), encoding="utf8"
    )


def commission(source, world, survey, backup):
    if len({p.resolve() for p in (source, world, survey, backup)}) != 4:
        raise ValueError(
            "Use distinct paths for the baseline, staging copy, clean survey and output."
        )
    if (world / "public_lifts_r65.json").read_bytes() != (
        source / "public_lifts_r65.json"
    ).read_bytes():
        raise ValueError(
            "The staging copy must use the same lift configuration as the R753 source."
        )
    builder = Works(world, source, backup)
    with np.load(
        Path(__file__).with_name("plans") / "subterminal_geofront.npz"
    ) as raster:
        repaint_existing(builder, raster)
    remove_east_jamb(builder, World(survey / REGION))
    clear_entrance(builder)
    remove_upper_walk(builder)
    rewrite_routes(source, world, builder.old, builder)
    retire_fixtures(source, world, builder.old, builder)
    builder.write()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Unmodified R753 world")
    parser.add_argument("world", type=Path, help="A stopped working copy of that world")
    parser.add_argument(
        "survey", type=Path, help="R752 snapshot with the earlier tower already removed"
    )
    parser.add_argument(
        "backup",
        type=Path,
        help="Directory for original region files and change counts",
    )
    args = parser.parse_args()
    commission(args.source, args.world, args.survey, args.backup)
