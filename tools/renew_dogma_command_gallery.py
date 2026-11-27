"""Upgrade a stopped R752 staging copy using the surveyed original terrain and gallery bed."""

import argparse
import json
from pathlib import Path
import sys

import nbtlib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "map_buildings"))

from dogma_apartment_402 import ROOMS, furnish
from dogma_observation_arm import LANDING, lower_arm
from dogma_terminal_finish import clear_entrance
from dogma_recommission import Works
from dogma_surface_command import (
    ENTRY,
    elevator,
    interiors,
    restore_site,
    shell,
    skin,
    walk,
)
from map_buildings.mca import World
from write_deep_cells import REGION


def commission(world, original_world, original_gallery, output):
    if world.resolve() in (original_world.resolve(), original_gallery.resolve()):
        raise ValueError("The staging copy and the original surveys must be separate.")
    travel_path = "r52/travel.json"
    travel = json.loads((world / travel_path).read_bytes())
    destinations = {row["key"]: row for row in travel["destinations"]}
    if destinations["sub_terminal"]["position"] != [249.5, -460, 343.5]:
        raise ValueError(
            "This upgrade expects the earlier command building in the R752 staging copy."
        )
    state = world / Path(REGION).parent / "data/seele_dogma_interlocks.dat"
    cursor = int(nbtlib.load(state)["data"]["Cursor"]) if state.exists() else 0
    builder = Works(world, original_world, output)
    restore_site(builder, builder.old)
    with np.load(
        Path(__file__).with_name("plans") / "subterminal_geofront.npz"
    ) as raster:
        shell(builder, raster)
    interiors(builder)
    walk(builder)
    elevator(builder)
    skin(builder)
    clear_entrance(builder)
    lower_arm(builder, World(original_gallery / REGION), cursor)
    furnish(builder)
    arrivals = {
        "sub_terminal": (ENTRY, -90, 0, "第二发令所 · 作战指挥席"),
        "lilith": (LANDING, -38, -26, "莉莉丝层 · 正面观测折桥"),
    }
    for key, (x, y, z) in ROOMS.items():
        label = "绫波丽 · 402室" if key == "rei" else "第一实验室 · 402室复原房"
        arrivals[key] = ((x + 1, y + 1, z + 4), -101, 16, label)
    for key, ((x, y, z), yaw, pitch, label) in arrivals.items():
        position = [x + 0.5, y, z + 0.5]
        destinations[key].update(
            position=position,
            requested_position=position,
            yaw=yaw,
            pitch=pitch,
            label=label,
            actual_cells=[
                dict(position=[x, y + dy, z], state=builder.get(x, y + dy, z))
                for dy in (-1, 0, 1)
            ],
        )
    builder.output(
        travel_path, json.dumps(travel, ensure_ascii=False, indent=1).encode()
    )
    builder.write()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("world", type=Path, help="Offline copy of the R752 world")
    parser.add_argument(
        "original_world",
        type=Path,
        help="Survey from before the secondary command building",
    )
    parser.add_argument(
        "original_gallery",
        type=Path,
        help="Survey from before the R752 lower observation arm",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Write the edit report and original region backups here",
    )
    opts = parser.parse_args()
    commission(opts.world, opts.original_world, opts.original_gallery, opts.output)
