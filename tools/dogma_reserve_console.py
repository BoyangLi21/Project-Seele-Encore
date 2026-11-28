"""Fit the full S20 operator banks and five working display panels to the reserve command floor."""

import json
from pathlib import Path

LAYOUT = (
    Path(__file__).resolve().parents[1]
    / "src/main/resources/assets/projectseele/command/reserve_console.json"
)


def furnish(builder):
    # The dark backing sits against the east side of the existing operations room.
    # Keep the two circulation aisles around its ends and the shaft behind it open.
    builder.box(247, -462, 384, 247, -454, 406, "black_concrete")
    # Trim and a header extend across the top, one block above the video raster.
    for z in range(384, 407):
        builder.put(247, -453, z, "projectseele:nerv_structural_panel")
    for station in json.loads(LAYOUT.read_bytes()):
        x, z = station["x"], station["z"]
        for offset, key in enumerate(station["keys"], -1):
            at_z = z + offset
            if key["id"] == "lights":
                state = "lever[face=floor,facing=east,powered=true]"
            else:
                state = key["block"] + "[face=floor,facing=east,powered=false]"
            builder.put(x, -461, at_z, state)
            builder.sign(
                x - 1, -462, at_z, "west", "", station["label"], key["label"], ""
            )
    # The ceiling fixtures use the reserve lighting lever independent of HQ chunk loading.
    for x in range(225, 248, 7):
        for z in (380, 388, 404, 411):
            builder.put(
                x, -454, z, "projectseele:nerv_ceiling_light[hanging=true,lit=true]"
            )
