"""Plan the R64 southwest foothills from a matching saved-world snapshot and block survey.

Run with --world WORLD --survey SURVEY --gsi projected-grid.npz --out DIRECTORY.
SURVEY contains the full, merged r.X.Z.npz ground/material surveys produced by
survey_r64_playtest_terrain. The GSI raster uses the perimeter baker's h,x0,z0,step
schema. Output plan/r.X.Z.npz uses the existing terrain stager's h,target format.
All scratch data and output are external. The source world is opened read-only.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy import ndimage as nd

from finish_r64_playtest_woodland import d8
from plan_r64_playtest_terrain import smooth
from plant_r64_playtest_woodland import surround
from survey_r64_playtest_terrain import EMPTY, kind
from write_deep_cells import REGION, decode, read_chunk


# Registered southwest window and old surveyed rectangle in GeoFront coordinates.
X0, Z0, X1, Z1 = -3584, 1024, 2048, 5632
WEST_EDGE, SOUTH_EDGE = -1982, 3720
STEP = 8
GRADE_HALO = 48


def region_coordinates(path):
    _, rx, rz = path.stem.split('.')
    return int(rx), int(rz)


def survey_tiles(survey):
    for path in sorted(survey.glob('r.*.*.npz')):
        rx, rz = region_coordinates(path)
        if X0 <= rx * 512 < X1 and Z0 <= rz * 512 < Z1:
            yield path, (rx * 512 - X0) // STEP, (rz * 512 - Z0) // STEP


def sample(field, x, z):
    iz, ix = np.broadcast_arrays((z - Z0 - 3.5) / STEP, (x - X0 - 3.5) / STEP)
    return nd.map_coordinates(field, (iz, ix), order=1, mode='nearest')


def surface_mosaic(survey):
    shape = ((Z1 - Z0) // STEP, (X1 - X0) // STEP)
    height, wet, hard = (np.zeros(shape, np.float32) for _ in range(3))
    valid = np.zeros(shape, bool)
    for path, ix, iz in survey_tiles(survey):
        area = np.s_[iz:iz + 64, ix:ix + 64]
        with np.load(path) as region:
            material = region['k']
            fraction = d8(material > 0)
            height[area] = d8(np.where(material > 0, region['h'], 0)) / np.maximum(.001, fraction)
            wet[area] = d8(material == 4)
            hard[area] = d8(material == 5)
            valid[area] = fraction == 1
    if not valid.any():
        raise ValueError('The supplied block survey has no measured southwest terrain')
    nearest = nd.distance_transform_edt(~valid, return_indices=True, return_distances=False)
    return height[tuple(nearest)], wet, hard, valid


def displacement(survey, gsi):
    height, wet, hard, valid = surface_mosaic(survey)
    z, x = np.mgrid[Z0 + 3.5:Z1:STEP, X0 + 3.5:X1:STEP]
    with np.load(gsi) as grid:
        source = grid['h']
        ix = (x.astype(int) - int(grid['x0'])) // STEP
        iz = (z.astype(int) - int(grid['z0'])) // STEP
        if (int(grid['step']) != STEP or ix.min() < 0 or iz.min() < 0
                or ix.max() >= source.shape[1] or iz.max() >= source.shape[0]):
            raise ValueError('GSI input must cover the southwest survey on its eight-block grid')
        dem = source[iz, ix]
    measured = np.isfinite(dem)
    if not measured.any():
        raise ValueError('The southwest GSI reference has no measured elevations')
    nearest = nd.distance_transform_edt(~measured, return_indices=True, return_distances=False)
    dem = dem[tuple(nearest)]

    distance = np.hypot(np.maximum(WEST_EDGE - x, 0), np.maximum(z - SOUTH_EDGE, 0))
    facing = nd.gaussian_filter(((WEST_EDGE - x) > (z - SOUTH_EDGE)).astype('f'), 68)
    nx, nz = -np.sin(facing * np.pi / 2), np.cos(facing * np.pi / 2)
    envelope = (smooth((distance - 42) / 220) * smooth((1110 - distance) / 310)
                * smooth((z - 1720) / 520) * smooth((820 - x) / 600)
                * smooth(nd.distance_transform_edt(valid) * STEP / 130)
                * smooth(nd.distance_transform_edt(measured) * STEP / 100))

    # Compare the nearby unmodified mountain with its two lateral shoulders at
    # two depths. This carries the actual ridge and side-valley directions into
    # the legacy ramp. A diffuse normal avoids focusing them on the old corner.
    reach = 460 + .19 * (620 - distance)
    source_x, source_z = x + nx * reach, z + nz * reach
    broad = nd.gaussian_filter(height, 12)

    def shoulders(cx, cz, offsets):
        return sum(sample(broad, cx + nz * offset, cz - nx * offset) for offset in offsets) / len(offsets)

    ridge = sample(nd.gaussian_filter(height, 4), source_x, source_z)
    ridge -= shoulders(source_x, source_z, (-350, -210, 210, 350))
    ax, az = x + nx * (reach + 160), z + nz * (reach + 160)
    incidence = sample(broad, ax, az) - shoulders(ax, az, (-415, -260, 260, 415))
    gully = np.clip(dem - nd.gaussian_filter(dem, 16), -14, 14)
    shift = 260 * np.tanh((.70 * ridge + .61 * incidence + .77 * gully) / 25) - 76
    baseline = nd.gaussian_filter(height, 5.5)
    warped = sample(baseline, x + nx * shift, z + nz * shift)
    detail = sample(nd.gaussian_filter(height, 1) - nd.gaussian_filter(height, 6), source_x, source_z)
    raw = warped - baseline + .58 * ridge + .88 * detail
    cap = np.where(raw < 0, 87, 66)
    change = cap * np.tanh(raw / cap) * envelope

    # Retain GSI-matched slopes and stable water and construction. Soften the
    # narrow parallel ribs of the northwest source hill before the lowland.
    change *= smooth((nd.gaussian_filter(np.abs(height - dem), 15) - 7) / 42)
    change *= smooth((nd.distance_transform_edt((wet < .025) & (hard < .025)) * STEP - 10) / 96)
    northwest = np.exp(-.5 * ((x + 2650) / 480) ** 2 - .5 * ((z - 2420) / 510) ** 2)
    change += .90 * northwest * (nd.gaussian_filter(change, 5.8) - change) * envelope
    return change.astype(np.float32)


def write_targets(survey, gsi, raw):
    change = displacement(survey, gsi)
    for path, ix, iz in survey_tiles(survey):
        neighborhood = change[max(0, iz - 1):iz + 65, max(0, ix - 1):ix + 65]
        if np.max(abs(neighborhood)) < .42:
            continue
        rx, rz = region_coordinates(path)
        z, x = np.mgrid[rz * 512:(rz + 1) * 512, rx * 512:(rx + 1) * 512]
        motion = sample(change, x, z)
        with np.load(path) as region:
            ground, material = region['h'], region['k']
        if np.any(material != 3):
            motion *= smooth((nd.distance_transform_edt(material == 3) - 6) / 60) * (material == 3)
        delta = np.rint(motion).astype(np.int16)
        if delta.any():
            np.savez_compressed(raw / path.name, h=ground, target=ground + delta)


def retain_foundations(job):
    world, path, guarded = job
    rx, rz = region_coordinates(path)
    with np.load(path) as plan:
        ground, target = plan['h'], plan['target']
    source = (world / REGION / (path.stem + '.mca')).read_bytes()
    for j, i in zip(*np.nonzero((target < ground).reshape(32, 16, 32, 16).any(axis=(1, 3)))):
        area = np.s_[j * 16:j * 16 + 16, i * 16:i * 16 + 16]
        old = ground[area].astype(int)
        initial = target[area].astype(int)
        lower = initial < old
        low, high = max(-128, int(initial[lower].min()) - 6), int(old[lower].max())
        chunk = read_chunk(source, int(rx * 32 + i), int(rz * 32 + j))[3]
        for section in chunk['sections']:
            bottom = int(section['Y']) * 16
            if bottom + 15 < low or bottom > high:
                continue
            ids, palette = decode(section['block_states'])
            names = [state.partition('[')[0] for state in palette]
            geological = np.array([kind(s) == 3 or s.endswith('_ore') or s in
                                   ('minecraft:cobblestone', 'minecraft:mossy_cobblestone') for s in names])
            if geological.all():
                continue
            y = bottom + np.arange(16)[:, None, None]
            blocked = (~geological[ids.reshape(16, 16, 16)]) & lower & (y <= old) & (y >= initial - 6)
            found = blocked.any(axis=0)
            if found.any():
                # Keep four unexcavated blocks above a cavity, fluid or structure.
                roof = np.minimum(old, bottom + 15 - blocked[::-1].argmax(axis=0) + 5)
                target[area][found] = np.maximum(target[area][found], roof[found])
    np.savez_compressed(guarded / path.name, h=ground, target=target)


def propagate_lower_bound(values, dx, dz):
    for _ in range(GRADE_HALO):
        new = values.copy()
        new[:, 1:] = np.maximum(new[:, 1:], values[:, :-1] - dx)
        new[:, :-1] = np.maximum(new[:, :-1], values[:, 1:] - dx)
        new[1:] = np.maximum(new[1:], values[:-1] - dz)
        new[:-1] = np.maximum(new[:-1], values[1:] - dz)
        if np.array_equal(new, values):
            return new
        values = new
    raise ValueError('Grade constraint reaches beyond the region halo')


def constrain_grade(job):
    survey, path, result = job
    rx, rz = region_coordinates(path)
    ground = surround(survey, rx, rz, 'h', EMPTY, margin=GRADE_HALO).astype(np.int32)
    proposed = surround(path.parent, rx, rz, 'target', EMPTY, margin=GRADE_HALO)
    target = np.where(proposed == EMPTY, ground, proposed)
    dx = np.maximum(2, abs(np.diff(ground, axis=1)))
    dz = np.maximum(2, abs(np.diff(ground, axis=0)))
    # First bound raised surfaces from the unchanged anchors, then relax cut
    # surfaces. No adjacent face becomes taller than two blocks or its old step.
    upper = -propagate_lower_bound(-np.maximum(ground, target), dx, dz)
    safe = propagate_lower_bound(np.minimum(upper, target), dx, dz)
    tile = np.s_[GRADE_HALO:-GRADE_HALO, GRADE_HALO:-GRADE_HALO]
    height, after = ground[tile], safe[tile]
    if np.any((after != height) & (target[tile] == height)):
        raise ValueError(f'Grade escaped the movable footprint in {path.name}')
    np.savez_compressed(result / path.name, h=height.astype(np.int16), target=after.astype(np.int16))
    return int((height != after).sum())


def plan(args):
    args.out.mkdir(exist_ok=True, parents=True)
    dest = args.out / 'plan'
    dest.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=args.out) as scratch:
        scratch = Path(scratch)
        raw, guarded, result = [scratch / name for name in ('raw', 'guarded', 'result')]
        for path in (raw, guarded, result):
            path.mkdir()
        write_targets(args.survey, args.gsi, raw)
        regions = sorted(p.name for p in raw.glob('r.*.*.npz'))
        with ProcessPoolExecutor(args.workers) as pool:
            list(pool.map(retain_foundations, [(args.world, raw / name, guarded) for name in regions]))
            counts = list(pool.map(constrain_grade, [(args.survey, guarded / name, result) for name in regions]))
        marker = args.out / 'southwest-plan.json'
        previous = json.loads(marker.read_bytes())['regions'] if marker.exists() else []
        for name in regions:
            os.replace(result / name, dest / name)
        for name in set(previous) - set(regions):
            if name == Path(name).name and Path(name).match('r.*.*.npz'):
                (dest / name).unlink(missing_ok=True)
        report = {'regions': regions, 'changed_columns': sum(counts)}
        (scratch / 'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        os.replace(scratch / 'manifest.json', marker)
    print(f'Planned {len(regions)} regions, {sum(counts)} measured ground columns in {dest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('world', 'survey', 'gsi', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    plan(parser.parse_args())
