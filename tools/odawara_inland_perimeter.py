"""Design the north/east land approaches and southeast cape of the Odawara base.

The CLI reads a four-block survey in Z,X order. The NPZ contains origin=(X,Z),
native_ground, native_water, native_fixture, dh_ground and dh_water. Datum -2048
marks an unobserved native column or absent water. DH covers the whole survey.
The resulting target/water arrays are absolute elevations. Apply active cells
to native chunks, preserve fixtures, and close one-block coastal seams after
rounding to individual columns.
"""
from argparse import ArgumentParser
from pathlib import Path

import numpy as np
from scipy import ndimage

SAMPLE_STEP = 4
SEA_LEVEL = -82
APRON = -70
NO_WATER = -2048


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def cape_distance(x, z):
    """Approximate signed inland distance along the surveyed southern coastline."""
    shore_z = [-980, -770, -640, -570, -500, -415, -300, -190, -80, -10, 55, 96, 140, 220]
    shore_x = [6020, 6010, 5915, 5810, 5705, 5625, 5590, 5535, 5430, 5350, 5206, 5080, 4980, 4770]
    alignment = np.interp(z[:, 0], shore_z, shore_x)
    edge = ndimage.gaussian_filter1d(alignment, 5)[:, None]
    edge = edge + 12 * np.sin(z / 68) + 6 * np.cos(z / 31)
    return (edge - x) / np.hypot(1, np.gradient(edge, SAMPLE_STEP, axis=0))


def design(origin, native_ground, native_water, native_fixture, dh_ground, dh_water):
    shape = native_ground.shape
    if len(shape) != 2 or min(shape) < 2 or any(
        array.shape != shape for array in (native_water, native_fixture, dh_ground, dh_water)
    ):
        raise ValueError("All survey layers must cover the same two-dimensional area")
    if np.any(dh_ground < -1700):
        raise ValueError("The site needs surveyed ground heights across the exterior")

    floor = dh_ground.astype(np.float32)
    water = dh_water.copy()
    native = native_ground > -1700
    floor[native] = native_ground[native]
    water[native] = native_water[native]
    was_wet = water > floor
    x0, z0 = map(int, origin)
    z, x = np.mgrid[z0 : z0 + shape[0] * SAMPLE_STEP : SAMPLE_STEP,
                    x0 : x0 + shape[1] * SAMPLE_STEP : SAMPLE_STEP]
    east = x - 5071
    north = -1168 - z
    south = z + 10
    signed = np.maximum(np.maximum(east, north), south)
    distance = np.sqrt(np.maximum(east, 0) ** 2 + np.maximum(north, 0) ** 2 + np.maximum(south, 0) ** 2)

    # The runway covers a low foundation. Its paved height anchors the outside grade.
    deck = native & (native_fixture >= floor) & (native_fixture > -80) & (native_fixture < -64)
    hills = ndimage.gaussian_filter(np.where(deck, native_fixture, floor).astype(np.float32), 7)
    spurs = 5 * np.sin(x / 113 + np.sin(z / 156)) + 3 * np.sin(z / 65 + x / 194) + 2 * np.cos(x / 57 - z / 104)

    inland = cape_distance(x, z)
    new_shore = SEA_LEVEL + np.minimum(42, np.maximum(inland, -160) * 0.175)
    new_shore += spurs * smooth((inland - 10) / 92)
    shore_bed = np.where(inland >= 0, new_shore, np.maximum(-125, SEA_LEVEL + inland * .22))
    hillside = np.maximum(hills, shore_bed - (1 - smooth((z + 750) / 220)) * 60)
    hillside = np.where(z < -720, np.maximum(hillside, -65 + spurs * .55), hillside)

    # Build the walkable shoulder before climbing toward the original high ground.
    climb = (.36 + .043 * np.sin(z / 138 + x / 233) + .032 * np.cos(z / 209 - x / 188)) * np.maximum(0, distance - 11)
    envelope = APRON + climb + spurs * smooth(distance / 98)
    proposed = APRON + (np.minimum(hillside, envelope) - APRON) * smooth((distance - 2) / 55)
    proposed += spurs * .42 * smooth(distance / 65) * (1 - smooth((distance - 420) / 240))
    reach = 685 + 65 * np.sin(z / 119 + x / 196) + 42 * np.cos(z / 155 - x / 158)
    blend = (1 - smooth((distance - reach + 165) / 165)) * smooth((x - 4310) / 130) * (1 - smooth((z - 76) / 116))
    blend *= smooth((signed + 16) / 14)
    blend *= 1 - smooth((z - 13) / 71) * (1 - smooth((x - 4910) / 155))
    target = np.rint(floor + blend * (proposed - floor)).astype(np.int16)

    allowed = (blend > .018) & (signed >= -15)
    water = np.where(allowed & (blend > .08), np.where(target < SEA_LEVEL, SEA_LEVEL, NO_WATER), water).astype(np.int16)
    dry = (signed >= -12) & (distance < 270) & (x >= 4448) & (z < 0) & (inland >= 12)
    target[dry] = np.maximum(target[dry], -78)
    water[dry] = NO_WATER
    active = allowed & ((target != floor) | (was_wet != (water > target)))
    return dict(ground=floor.astype(np.int16), target=target, water=water, active=active, alpha=blend.astype(np.float32), dry=dry)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("survey", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with np.load(args.survey) as inputs:
        result = design(*(inputs[key] for key in (
            "origin", "native_ground", "native_water", "native_fixture", "dh_ground", "dh_water"
        )))
    np.savez_compressed(args.output, **result)


if __name__ == "__main__":
    main()
