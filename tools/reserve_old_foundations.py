"""Restore the disused HQ bridge footing and the north edge of the former science apron."""

from dogma_recommission import AIR
from science_lower_gallery import _rock_surface

GRASS = "minecraft:grass_block[snowy=false]"


def _soil_column(b, x, z, height):
    rock = _rock_surface(b, x, z)
    for y in range(rock + 1, -464):
        before = b.get(x, y, z)
        if "_log[" in before or ("_leaves[" in before and y > height):
            continue
        state = "minecraft:dirt" if y < height else GRASS if y == height else AIR
        if before != state:
            b.put(x, y, z, state)


def restore_old_foundations(b):
    # The westbound gallery disappeared in a previous revision; its naked abutment
    # matches the original four-layer soil profile along both sides, even at the cut.
    for z in range(395, 404):
        for x in range(165, 201):
            _soil_column(b, x, z, _rock_surface(b, x, z) + 4)
    for x in range(192, 201):
        _soil_column(b, x, 404, _rock_surface(b, x, 404) + 4)

    # The two gray strips in the facade view are pieces of one fractured perimeter
    # slab. The paved district beyond z=473 is at -467. Regrade the approach into
    # it, retaining the bases of the three established trees on the former green.
    apron_top = -467
    trees = []
    for x in range(213, 289):
        for z in range(453, 474):
            if "_log[" in b.get(x, apron_top + 1, z) and "_log[" not in b.get(
                x, apron_top, z
            ):
                trees.append((x, z))
    for x in range(213, 289):
        for z in range(453, 474):
            grade = max(_rock_surface(b, x, z) + 4, apron_top - (474 - z + 1) // 2)
            for tx, tz in trees:
                distance = abs(tx - x) + abs(tz - z)
                grade = max(grade, apron_top - (distance + 1) // 2)
            _soil_column(b, x, z, grade)
    # Blind tongue projecting from the north edge, ending in free air at z=439.
    for x in range(271, 280):
        for z in range(439, 453):
            _soil_column(b, x, z, _rock_surface(b, x, z) + 4)
