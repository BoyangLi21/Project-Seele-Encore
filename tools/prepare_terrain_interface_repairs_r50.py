"""Finite measured natural shoulder regrading; candidate and source only.

The old coarse-sample steep-interface test is not a geology classifier. This
script explicitly retains water, does not treat elevated track ballast as
ground, and cannot write an Anvil world. Root owns installation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math

import numpy as np
from scipy.ndimage import gaussian_filter

from prepare_facilities_r48 import Author, DIM
from prepare_battle_civil_r50 import complete_recipe
from query_blocks import AIR

ROOT = Path(__file__).resolve().parents[1]
NATURAL = AIR | {'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block', 'minecraft:water'}
SPECS = [(6, 'T01_west_shoulder_south', -392, -248),
         (7, 'T02_west_shoulder_north', -104, 8)]


def source_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def overlap(a, b):
    return all(a[0][k] <= b[1][k] and b[0][k] <= a[1][k] for k in range(3))


def build(world, out):
    out.mkdir(parents=True, exist_ok=True)
    authored = Author(world, out)
    full_desired = {}
    results = []
    protected = []
    inventory_path = ROOT/'artifacts/rebuild_r49/surface_r50/surface_object_inventory.json'
    inv = json.loads(inventory_path.read_text('utf8'))
    objects = inv['objects'] if isinstance(inv, dict) else inv
    for obj in objects:
        box = obj.get('bounds')
        if not isinstance(box, list):
            continue
        if len(box) == 4 and all(isinstance(v, (float, int)) for v in box):
            box = [[box[0], 0, box[2]], [box[1], 255, box[3]]]
        if len(box) == 6 and all(isinstance(v, (float, int)) for v in box):
            box = [box[:3], box[3:]]
        if len(box) == 2 and all(isinstance(v, list) and len(v) == 3 for v in box):
            protected.append((obj.get('id'), box))
    frozen = [([[-95, 72, 435], [155, 194, 534]], 'Y01'),
              ([[25, 19, 351], [42, 87, 360]], 'A01'),
              ([[1326, 15, 588], [1750, 125, 806]], 'M01'),
              ([[8, -441, -240], [10, -441, -240]], 'Y02')]
    for interface_id, name, z0, z1 in SPECS:
        # Twelve metres of actual readback halo; no interpolated terrain input.
        lo = (-2340, 48, z0-12)
        hi = (-2268, 155, z1+12)
        authored.read(lo, hi)
        nx, nz = hi[0]-lo[0]+1, hi[2]-lo[2]+1
        heights = np.empty((nz, nx), dtype=np.int16)
        wet = np.zeros_like(heights, dtype=bool)
        for j, z in enumerate(range(lo[2], hi[2]+1)):
            for i, x in enumerate(range(lo[0], hi[0]+1)):
                col = [authored.s[x, y, z] for y in range(48, 156)]
                assert all(s.split('[')[0] in NATURAL for s in col), (name, x, z, 'constructed cell')
                assert all((x, y, z) not in authored.t for y in range(48, 156)), (name, x, z, 'BE')
                top = max(y for y in range(48, 156) if authored.s[x, y, z].split('[')[0]
                          in {'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block'})
                assert all(authored.s[x, y, z] in AIR or authored.s[x, y, z].startswith('minecraft:water')
                           for y in range(top+1, 156)), (name, x, z, 'overhead object')
                heights[j, i] = top
                wet[j, i] = any(s.startswith('minecraft:water') for s in col)
        smooth = gaussian_filter(heights.astype(float), sigma=(3, 6), mode='nearest')
        target = heights.copy()
        desired = {}
        box = [[-2328, 48, z0], [-2280, 155, z1]]
        owners = [k for k, b in protected if overlap(box, b)]
        assert not owners, (name, 'catalogued live geometry', owners)
        assert not any(overlap(box, b) for b, k in frozen), name
        wet_count = 0
        cavity_columns_retained = 0
        for z in range(z0, z1+1):
            j = z-lo[2]
            end = min(z-z0, z1-z)
            zw = min(1., end/16.)
            zw = zw*zw*(3-2*zw)
            for x in range(-2328, -2279):
                i = x-lo[0]
                v = max(0., 1-abs(x+2304)/24.)
                xw = v*v*(3-2*v)
                w = xw*zw
                old_top = int(heights[j, i])
                new_top = old_top if wet[j, i] else int(np.rint(old_top*(1-w)+smooth[j, i]*w))
                if new_top != old_top and any(authored.s[x, y, z].split('[')[0]
                        not in {'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block'}
                        for y in range(min(old_top, new_top)-3, old_top+1)):
                    # A measured shallow natural cavity is retained as a whole
                    # column rather than sealed or exposed by the contour pass.
                    new_top = old_top
                    cavity_columns_retained += 1
                wet_count += int(wet[j, i])
                target[j, i] = new_top
                for y in range(48, 156):
                    p = (x, y, z)
                    # Preserve the complete original column where no height is
                    # changed, including every source water state and air cell.
                    if new_top == old_top or y < min(old_top, new_top)-3:
                        state = authored.s[p]
                    else:
                        state = ('minecraft:grass_block[snowy=false]' if y == new_top else
                                 'minecraft:dirt' if new_top-3 <= y < new_top else
                                 'minecraft:stone' if y < new_top else 'minecraft:air')
                    desired[p] = (state, 'Measured finite west shoulder contour; continuous soil/rock bearing and unchanged waterbank, not a rectangular mountain replacement', None)
        ix = -2305-lo[0]
        js = slice(z0-lo[2], z1-lo[2]+1)
        before_edge = abs(heights[js, ix+1]-heights[js, ix])
        after_edge = abs(target[js, ix+1]-target[js, ix])
        changed_columns = int(np.count_nonzero(target != heights))
        result = dict(interface_id=interface_id, name=name, complete_bounds=box,
                      measured_bounds=[list(lo), list(hi)], changed_columns=changed_columns,
                      original_and_result_peak=[int(heights.max()), int(target.max())],
                      original_and_result_min=[int(heights.min()), int(target.min())],
                      frame_edge_before_max=int(before_edge.max()), frame_edge_after_max=int(after_edge.max()),
                      frame_edge_before_ge8=int((before_edge >= 8).sum()), frame_edge_after_ge8=int((after_edge >= 8).sum()),
                      water_columns_retained=wet_count, shallow_cavity_columns_retained=cavity_columns_retained,
                      deeper_actual_cave_cells_retained=True, live_catalogue_overlap=owners,
                      measured_materials_only=['stone', 'dirt', 'grass_block', 'water', 'air'],
                      purpose='Authorized current contour improvement; historical generator causation not proven',
                      all_traffic_building_NBT_entity_and_new_battle_components_retained=True)
        authored.emit(name, desired, result)
        full_desired.update(desired)
        np.savez_compressed(out/(name+'_heightfield.npz'), origin=np.array([lo[0], lo[2]]),
                            before=heights, after=target, wet=wet,
                            declared=np.array(box), complete=True)
        results.append(result)
        print(result, flush=True)
    authored.full_desired = full_desired
    complete_recipe(authored)
    for p in out.glob('*/contract.json'):
        d = json.loads(p.read_text('utf8'))
        d.update(schema='projectseele.r50.terrain-interface-candidate.v1',
                 authorization='Root-relayed user global natural terrain reconstruction, item40',
                 geological_cliffs_not_globally_smoothed=True)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), 'utf8')
    authored.components = [json.loads((out/r['name']/'contract.json').read_text('utf8')) for r in results]
    manifest = dict(schema=50, source_world=str(world), components=authored.components,
                    changed_cells=len(authored.all), complete_generation_cells=len(full_desired),
                    inventory_source=str(inventory_path), inventory_sha256=source_digest(inventory_path),
                    frozen_four_battle_components_disjoint=True, results=results,
                    full_actual_state_NBT_inverse_mask=True, world_written=False,
                    native_verified=False, visual_verified=False,
                    metadata_operations=[], all_actor_identity_inventory_and_progress_files_untouched=True)
    (out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf8')
    (out/'metadata_patch.json').write_text(json.dumps(dict(schema=50, operations=[], world_written=False), indent=2), 'utf8')
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=ROOT/'artifacts/rebuild_r49/surface_r50/terrain_interface_repairs/candidate')
    args = ap.parse_args()
    build(args.world.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
