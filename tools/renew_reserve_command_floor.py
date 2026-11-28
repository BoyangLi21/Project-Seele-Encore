"""Apply the reserve command floor and retire the former science underpass in an offline R754 copy."""

import argparse
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "map_buildings"))

from dogma_optics_gallery import glaze_gallery
from dogma_recommission import Works
from dogma_reserve_console import furnish
from science_lower_gallery import remove_lower_gallery, update_lower_routes
from reserve_old_foundations import restore_old_foundations
from terminal_forecourt import grade_forecourt
from terminal_park_paths import lay_out_park


def remodel(builder):
    with np.load(
        Path(__file__).with_name("plans") / "subterminal_geofront.npz"
    ) as raster:
        shell = raster["m"]
        glaze_gallery(builder, shell)
    remove_lower_gallery(builder)
    grade_forecourt(builder)
    restore_old_foundations(builder)
    lay_out_park(builder, shell)
    furnish(builder)


def commission(original, staging, backup):
    if len({path.resolve() for path in (original, staging, backup)}) != 3:
        raise ValueError(
            "Use separate paths for the original world, offline working copy and backups."
        )
    builder = Works(staging, original, backup)
    remodel(builder)
    update_lower_routes(original, staging)
    builder.write()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path, help="Unmodified R754 world")
    parser.add_argument(
        "staging", type=Path, help="Offline working copy of the R754 world"
    )
    parser.add_argument(
        "backup", type=Path, help="Original region backups and edit report"
    )
    args = parser.parse_args()
    commission(args.original, args.staging, args.backup)
