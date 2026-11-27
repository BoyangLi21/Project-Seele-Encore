"""Use a common furniture plan for Rei's apartment and the First Laboratory reconstruction."""

import nbtlib
from dogma_recommission import AIR

ROOMS = {"rei": (-191, 102, 514), "rei_lab": (-25, -1231, 194)}
FIXTURE = "projectseele:rei_room_fixture"


def furnish(b):
    interior = {(x, y, z): AIR for x in range(5) for z in range(6) for y in (1, 2)}
    # The west iron door is in the original jamb. Keep its inside pressure plate and release button.
    interior[0, 1, 4] = "minecraft:stone_pressure_plate[powered=false]"
    interior[0, 2, 5] = "minecraft:stone_button[face=wall,facing=east,powered=false]"
    for name, (x, z) in {
        "entrance_sink": (0, 1),
        "medicine_fridge": (2, 0),
        "eyeglass_cabinet": (1, 5),
        "folding_chair": (0, 0),
    }.items():
        interior[x, 1, z] = FIXTURE + "[kind=" + name + "]"
    for z, part in ((3, "head"), (4, "foot")):
        interior[3, 1, z] = (
            f"minecraft:white_bed[facing=north,occupied=false,part={part}]"
        )
    for x in (1, 2, 3):
        interior[x, 1, 6] = FIXTURE + "[kind=blind_bottom]"
        interior[x, 2, 6] = FIXTURE + "[kind=blind_top]"
    for a, y0, c in ROOMS.values():
        for (x, y, z), state in interior.items():
            pos = a + x, y0 + y, c + z
            b.put(*pos, state)
            if state.startswith("minecraft:white_bed"):
                b.tags[pos] = nbtlib.Compound(
                    {"id": nbtlib.String("minecraft:bed"), "keepPacked": nbtlib.Byte(0)}
                )
