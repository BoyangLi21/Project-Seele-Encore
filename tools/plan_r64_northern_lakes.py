"""Plan modest additions to clipped Y62 lake shores along the north Hakone map boundary.

Inputs are native survey_r64_playtest_terrain region arrays. Outputs contain only
new water columns; existing water and the ensuing bank/bed construction are
checked separately against the target world during staging.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage as nd


@dataclass(frozen=True)
class LakeSite:
    name: str
    bounds: tuple[int, int, int, int]
    reach: float


# Bounds enclose the photographed water bodies. Rivers through downtown
# Odawara and the working portions of the western facility have other owners.
SITES = (
    LakeSite("western_facility", (-3252, -1572, -2150, -603), .79),
    LakeSite("western_pond", (-2182, -1746, -1980, -1590), .71),
    LakeSite("northwest_lakes", (-1806, -2200, -680, -1752), 1.00),
    LakeSite("north_pond", (-305, -1806, -194, -1689), .57),
    LakeSite("central_ponds", (920, -1828, 1574, -1715), .60),
    LakeSite("northeast_brook", (2064, -2112, 2392, -1800), .44),
    LakeSite("northeast_headwaters", (2588, -2408, 2864, -2026), .65),
    LakeSite("east_shelf", (2762, -1862, 3154, -1792), .57),
    LakeSite("eastern_pools", (3300, -2200, 3540, -2021), .58),
)
LEVEL = 62
PADDING = 96


def read_survey(surveys, bounds):
    x0, z0, x1, z1 = bounds
    shape = z1-z0, x1-x0
    data = {"k": np.zeros(shape, "B"), "h": np.full(shape, -32768, np.int16),
            "r": np.zeros(shape, bool)}
    for rx in range(x0//512, (x1-1)//512+1):
        for rz in range(z0//512, (z1-1)//512+1):
            path = surveys/f"r.{rx}.{rz}.npz"
            if not path.is_file():
                continue
            ox, oz = 512*rx, 512*rz
            xa, xb = max(x0, ox), min(x1, ox+512)
            za, zb = max(z0, oz), min(z1, oz+512)
            tile = np.s_[za-oz:zb-oz, xa-ox:xb-ox]
            local = np.s_[za-z0:zb-z0, xa-x0:xb-x0]
            with np.load(path) as region:
                for key in data:
                    source_key = "v" if key == "r" and "r" not in region else key
                    data[key][local] = region[source_key][tile]
    return data


def straight_edges(water, dry):
    """Find the two endpoints of each axis-aligned cut facing natural land."""
    for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        facing = water & np.roll(dry, (-dz, -dx), axis=(0, 1))
        # Small notches in an otherwise clipped waterline should not turn one
        # lake bay into a string of identical short scallops.
        kernel = (1, 7) if dz else (7, 1)
        joined = nd.binary_closing(facing, structure=np.ones(kernel, bool))
        rows = joined if dz else joined.T
        for row in np.flatnonzero(rows.sum(axis=1) >= 13):
            line = rows[row]
            starts = np.flatnonzero(line & ~np.r_[False, line[:-1]])
            ends = np.flatnonzero(line & ~np.r_[line[1:], False])
            for start, end in zip(starts, ends):
                length = int(end-start+1)
                if length < 13:
                    continue
                mid = (start+end)/2
                yield (mid, row, dx, dz, length) if dz else (row, mid, dx, dz, length)


def bay_scores(water, dry, site, ox, oz):
    scores = np.full(water.shape, -100, np.float32)
    for cx, cz, dx, dz, length in straight_edges(water, dry):
        wx, wz = ox+cx, oz+cz
        phase = np.sin(wx/81+wz/113)
        depth = min(76, (4+length*.27)*site.reach*(1+.16*phase))
        along = length*.58+min(22, depth*.47)
        extent = int(np.ceil(max(depth, along)*1.4+8))
        xa, za = max(0, int(cx)-extent), max(0, int(cz)-extent)
        xb, zb = min(water.shape[1], int(cx)+extent+1), min(water.shape[0], int(cz)+extent+1)
        zz, xx = np.ogrid[za:zb, xa:xb]
        tangent = ((xx-cx) if dz else (zz-cz))/along
        normal = (xx-cx)*dx+(zz-cz)*dz
        # Taper into the old banks and vary the deepest part of each cove
        # along shore. Irregular offsets follow the world, including tile edges.
        curved = depth*np.sqrt(np.maximum(0, 1-tangent*tangent))
        curved = curved * (1+.17*np.sin(3*tangent+phase)+.12*np.sin((xx+ox)/29+(zz+oz)/37))
        signed = np.where(np.abs(tangent)<1, curved-np.abs(normal+depth*.03), -100)
        scores[za:zb, xa:xb] = np.maximum(scores[za:zb, xa:xb], signed)
    return scores


def northern_shoulder(scores, water, dry, site, ox, oz):
    # Several parts of the same west-basin shore stop on the same survey
    # line. Carry a shallow continuous margin around the headlands between
    # their bays. Distance-to-water preserves separate inlets and islands.
    bands = {"western_facility": (-3248, -2436, -1568, -1536),
             "northwest_lakes": (-1380, -1050, -2140, -2126)}
    if site.name not in bands:
        return scores
    left, right, north, south = bands[site.name]
    z, x = np.ogrid[oz:oz+water.shape[0], ox:ox+water.shape[1]]
    exposed = water & np.roll(dry, 1, axis=0)
    seeds = exposed & (x >= left) & (x <= right) & (z >= north) & (z <= south)
    if not seeds.any():
        return scores
    distance = nd.distance_transform_edt(~seeds)
    shoulder = 16 + 6*np.sin(x/51.0+z/143.0) + 5*np.sin(x/97.0-z/83.0)
    return np.maximum(scores, shoulder-distance)


def plan(site, surveys, out):
    x0, z0, x1, z1 = site.bounds
    bounds = (x0 - PADDING, z0 - PADDING, x1 + PADDING, z1 + PADDING)
    survey = read_survey(surveys, bounds)
    ground = survey["h"].astype(np.float32)
    kind = survey["k"]
    dry = kind == 3
    all_water = (kind == 4) & (ground == LEVEL)
    water = np.zeros_like(dry)
    interior = np.s_[PADDING:-PADDING, PADDING:-PADDING]
    water[interior] = all_water[interior]
    scores = bay_scores(water, dry, site, bounds[0], bounds[1])
    scores = northern_shoulder(scores, water, dry, site, bounds[0], bounds[1])

    # A concave corner can run between two separate straight shoreline runs.
    # Limit the rounding to the immediate margin of the measured water.
    distance = nd.distance_transform_edt(~water).astype(np.float32)
    sigma = 9 * site.reach
    wet_fraction = nd.gaussian_filter(water.astype(np.float32), sigma)
    corner = (wet_fraction - 0.43) * sigma * 3
    scores = np.maximum(scores, np.where(distance < sigma * 2.5, corner, -100))
    clearance = nd.distance_transform_edt((kind != 5) & (kind != 0))

    # Higher shoulders steer the new shore towards low spots. Existing roots
    # and the setbacks around structures stay dry.
    height_penalty = (np.maximum(0, ground - LEVEL - 2) * 1.45
                      + np.maximum(0, LEVEL - 18 - ground) * 0.85)
    eligible = (dry & (clearance > 18) & ~survey["r"]
                & (ground >= LEVEL - 56) & (ground <= LEVEL + 15))
    proposed = eligible & (scores > height_penalty)
    # Round the joins between overlapping coves and keep the result attached
    # to an actual same-level lake through face-connected blocks.
    shoreline = nd.gaussian_filter((proposed | all_water).astype(np.float32), 3.1)
    proposed = eligible & (shoreline > 0.5)
    connected = nd.binary_propagation(water, mask=proposed | all_water)
    mask = connected & proposed
    components, count = nd.label(mask)
    sizes = np.bincount(components.ravel(), minlength=count + 1)
    mask &= sizes[components] >= 5

    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / (site.name + ".npz"), x0=bounds[0], z0=bounds[1], water=mask)
    contacts = mask & nd.binary_dilation(all_water)
    return dict(id=site.name, bounds=bounds, level=LEVEL, original=int(water.sum()),
                new=int(mask.sum()), shore_contacts=int(contacts.sum()),
                max_extension=round(float(distance[mask].max()), 1) if mask.any() else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surveys", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    reports = [plan(site, args.surveys, args.out) for site in SITES]
    (args.out / "sites.json").write_text(json.dumps(reports, indent=2), encoding="utf8")
    print(json.dumps(reports))


if __name__ == "__main__":
    main()
