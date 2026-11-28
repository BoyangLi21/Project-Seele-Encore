"""Glaze the full curved fourth floor of the secondary command tower."""

import numpy as np

from dogma_recommission import AIR
from dogma_surface_command import GROUND, LIFT_X, LIFT_Z, X, Z

FLOOR_Y = GROUND + 146
GLASS = "projectseele:clear_glass"


def gallery_footprint(mask):
    """Follow the optical blade at this storey, with room to walk around the lift."""
    section = mask[:, :, 146:153].any(axis=2)
    footprint = set()
    for j in np.flatnonzero(section.any(axis=0)):
        line = np.flatnonzero(section[:, j])
        # The shaft occupies the entire thickness of the old blade at its middle.
        # Ease the facade out on both faces for a public aisle past the lift core.
        bypass = max(0, 4 - max(0, abs(int(j) - (LIFT_Z - Z)) - 5) // 3)
        for x in range(X + int(line[0]) - bypass, X + int(line[-1]) + bypass + 1):
            footprint.add((x, Z + int(j)))
    return footprint


def glaze_gallery(builder, mask):
    footprint = gallery_footprint(mask)
    # At the southern bend the old R753 window extended one column outside the blade.
    # Its sill, glass, mullion and lintel otherwise stand on their own in front of 4F.
    old_jamb = (248, 415)
    if old_jamb not in footprint:
        for y in range(FLOOR_Y, FLOOR_Y + 7):
            builder.put(old_jamb[0], y, old_jamb[1], AIR)
    for x, z in sorted(footprint):
        perimeter = any(
            p not in footprint for p in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1))
        )
        # Keep the working lift enclosure, buttons and doors on their existing supports.
        shaft = abs(x - LIFT_X) <= 3 and LIFT_Z - 3 <= z <= LIFT_Z + 3
        if shaft:
            # Finish the lift enclosure behind the glazing, including its exposed
            # top lip. Controllers, buttons and the interlocked doors use other states.
            for y in range(FLOOR_Y + 1, FLOOR_Y + 8):
                if builder.get(x, y, z) == "minecraft:light_gray_concrete":
                    builder.put(x, y, z, "smooth_quartz")
            continue
        for rise in range(7):
            y = FLOOR_Y + rise
            if builder.get(x, y, z).startswith("minecraft:polished_blackstone_button"):
                continue
            if rise == 0:
                state = (
                    "smooth_quartz" if perimeter else "projectseele:nerv_floor_panel"
                )
            elif rise == 6:
                state = "smooth_quartz"
                if not perimeter and z % 8 == 0 and (x + z) % 5 == 0:
                    state = "sea_lantern"
            else:
                state = GLASS if perimeter else AIR
            builder.put(x, y, z, state)
    return footprint
