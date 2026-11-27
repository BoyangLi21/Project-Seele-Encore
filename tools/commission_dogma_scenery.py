"""Apply the museum, gallery and shore revisions to an offline copy of the commissioned save."""

import argparse
import json
from pathlib import Path
import sys
import nbtlib

sys.path.insert(0, str(Path(__file__).resolve().parent / "map_buildings"))
from dogma_recommission import Works, LCL
from dogma_lilith_gallery import gallery
from dogma_command_tower import command_tower


def clear_casts(b):
    count = 0
    for x in range(-82, -36):
        for z in range(128, 186):
            for y in range(-1246, -1237):
                if b.get(x, y, z) in (
                    "minecraft:smooth_quartz",
                    "minecraft:calcite",
                    "minecraft:bone_block[axis=z]",
                ):
                    b.put(x, y, z, LCL)
                    count += 1
    b.reports["removed_voxel_cast_cells"] = count
    # A glazed section at spectator eye level preserves the continuous pool guard.
    for z in range(150, 166):
        state = b.get(-35, -1230, z)
        if state.startswith("minecraft:iron_bars["):
            b.put(
                -35,
                -1230,
                z,
                state.replace("minecraft:iron_bars[", "minecraft:glass_pane["),
            )


def commissioning(world, original_region, output, shore_ready=False, cursor=0):
    b = Works(world, world, output)
    if not shore_ready:
        from dogma_shore_repair import repair

        repair(b)
    command_tower(b, original_region)
    gallery(b, cursor=cursor)
    clear_casts(b)
    travel = "r52/travel.json"
    doc = json.loads((world / travel).read_bytes())
    headings = {"lake_mirrors": -18, "eva_graveyard": 19, "lilith": -24}
    viewpoints = {
        "sub_terminal": (249, -460, 343, -90),
        "lake_mirrors": (-452, 101, 973, 0),
        "eva_graveyard": (-34, -1230, 157, 90),
    }
    for row in doc["destinations"]:
        key = row["key"]
        if key in headings:
            row["pitch"] = headings[key]
        if key in viewpoints:
            x, y, z, yaw = viewpoints[key]
            row.update(
                position=[x + 0.5, y, z + 0.5],
                requested_position=[x + 0.5, y, z + 0.5],
                yaw=yaw,
                actual_cells=[
                    dict(position=[x, y + h, z], state=b.get(x, y + h, z))
                    for h in (-1, 0, 1)
                ],
            )
    b.output(travel, json.dumps(doc, ensure_ascii=False, indent=1).encode())
    # This marker opts an existing single-player world into the two matching survey models.
    b.output(
        "r52/survey_scenery.json",
        json.dumps(
            {
                "revision": 1,
                "locations": ["eva_graveyard", "lake_mirrors"],
                "credits": [
                    {
                        "title": "Evo No Armor as a marble sculpture",
                        "author": "SmileyMan10000",
                        "license": "CC BY 4.0",
                        "url": "https://sketchfab.com/3d-models/evo-no-armor-as-a-marble-sculpture-3139cbd2727b4297b12f8648ec397a86",
                        "changes": "Separated and posed heads, eyes and limbs, vertex-sampled original albedo and AO; original rib and vertebral geometry added.",
                    },
                    {
                        "title": "Solar Harvester from Evangelion",
                        "author": "K-Kazama",
                        "license": "CC BY 4.0",
                        "url": "https://sketchfab.com/3d-models/solar-harvester-from-evangelion-c52a028006494b278164e5480d66427c",
                        "changes": "Applied FBX scene transforms and surveyed placement, material colours and directional lighting.",
                    },
                ],
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
            },
            ensure_ascii=False,
            indent=2,
        ).encode(),
    )
    b.write()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["world", "original_region", "output"]:
        parser.add_argument(name, type=Path)
    parser.add_argument(
        "--cursor", type=int, default=None, help="Saved emergency interlock progress"
    )
    args = parser.parse_args()
    state = list(
        (args.world / "dimensions/projectseele/geofront/data").glob(
            "*dogma*interlock*.dat"
        )
    )
    cursor = args.cursor
    if cursor is None:
        cursor = int(nbtlib.load(state[0])["data"]["Cursor"]) if state else 0
    commissioning(args.world, args.original_region, args.output, cursor=cursor)
