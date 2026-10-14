"""Measure only Root's adopted early-curve change, reusing fixed body slices.

No WORLD writes. The unchanged body binaries are never decoded or reswept.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import argparse
import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from build_current_launch_height_hulls import read_mesh, cones, clipped, merge, bands
from measure_upright_bores_r52 import make_parts
from plan_bank3_exact_geometry_r52 import contains
from query_blocks import chunk_statuses, iter_selected_sections


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')


def current_hull(a, old, new):
    cache = a.source
    fixed = json.loads((cache/'ACTUAL_FIXED_ASSEMBLY_HEIGHT_SLICES.json').read_text('utf8'))
    dynamic = json.loads((cache/'CURRENT_HEAD_CONTINUOUS_HEIGHT_SLICES.json').read_text('utf8'))
    prior = json.loads((cache/'CURRENT_COMPLETE_NINE_ASCENT_HEIGHT_HULLS.json').read_text('utf8'))
    export = json.loads((cache/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json').read_text('utf8'))
    cone_source = json.loads((cache/'CURRENT_HEAD_CONTINUOUS_TANGENT_CONES.json').read_text('utf8'))
    production = json.loads((cache/'CURRENT_PRODUCTION_HEAD_EXPORT.json').read_text('utf8'))
    assert prior['root_design_sha256'] == sha(a.previous)
    model = a.root/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json'
    head = model.with_name('outer_head_transfer_r53.json')
    assert export['head_source_sha256'] == sha(head)
    templates = {p['name']: p for p in export['head_templates']}
    moving = {-1: [], 1: []}
    for name, (_, mesh) in read_mesh(cache/'ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz').items():
        frame = templates[name]['frame']
        if frame != 'ROOT':
            moving[-1 if frame == 'RUNNER_NEG' else 1].append(mesh)
    moving = {s: np.concatenate(rows) for s, rows in moving.items()}
    merged = {int(b['height_band_m'][0]): np.array(b['actual_clipped_XZ_convex_hull_m'])
              for b in dynamic['height_slices_1m']}
    added = []
    for leg in new['legs']:
        if leg['id'].endswith('/reverse') or '/exit3/' not in leg['id']:
            continue
        for i in (1, 2):
            added.extend(cones(np.array(leg['centre_curve']['segments'][i]['controls']),
                cone_source['actual_vertex_coefficients'], cone_source['frame_roundoff_m'], leg['id'], i))
    unique = {}
    for row in added:
        key = tuple(round(x, 10) for x in row['direction'])
        if key not in unique or row['position_error_m'] > unique[key]['position_error_m']:
            unique[key] = row
    balls = {int(k): np.array(v) for k, v in production['world_yaw180_mounts'].items()}
    for number, row in enumerate(unique.values(), 1):
        d = np.array(row['direction']); u = np.array([-1., 0, 0]); x = u-d*np.dot(u, d)
        x /= np.linalg.norm(x); y = np.cross(d, x)
        for side, mesh in moving.items():
            posed = mesh[:, :, 0, None]*x+mesh[:, :, 1, None]*y+mesh[:, :, 2, None]*d+balls[side]-.35*y
            merge(merged, clipped(posed, row['position_error_m']+1e-8))
        if number % 500 == 0:
            print('new early head cones', number, '/', len(unique), flush=True)
    result = copy.deepcopy(prior)
    result['root_design_sha256'] = sha(a.directory)
    result['directory_fingerprint'] = None
    result['directory_fingerprint_requires_current_production_parser'] = True
    result['variants'] = []
    for v in range(3):
        rows = {int(b['height_band_m'][0]): np.array(b['actual_clipped_XZ_convex_hull_m'])
                for b in fixed['variants'][v]['height_slices_1m']}
        offset = export['variants'][v]['root_relative_to_actual_foot_midpoint']['translation']['z']
        merge(rows, {y: points+np.array([0., offset]) for y, points in merged.items()})
        variant = copy.deepcopy(prior['variants'][v]); variant['height_slices_1m'] = bands(rows)
        points = np.concatenate(list(rows.values()))
        variant['conservative_complete_xyz_bounds_m'] = [float(points[:, 0].min()), min(rows),
            float(points[:, 1].min()), float(points[:, 0].max()), max(rows)+1, float(points[:, 1].max())]
        result['variants'].append(variant)
    result['current_early_direction_rebind'] = dict(previous_hull_sha256=sha(cache/'CURRENT_COMPLETE_NINE_ASCENT_HEIGHT_HULLS.json'),
        new_early_direction_cones=len(added), unique_new_early_direction_cones=len(unique),
        cached_fixed_slice_sha256=sha(cache/'ACTUAL_FIXED_ASSEMBLY_HEIGHT_SLICES.json'),
        cached_head_template_sha256=sha(cache/'ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz'),
        original_body_binaries_read=False, retained_prior_direction_union=True,
        old_source_hashes_preserved_as_provenance=True, root_spatial_plan_sha256=sha(a.base/'ROOT_SPATIAL_PLAN.json'))
    result['source_sha256'] = {str(p): sha(p) for p in (a.directory, a.previous,
        cache/'ACTUAL_FIXED_ASSEMBLY_HEIGHT_SLICES.json', cache/'CURRENT_HEAD_CONTINUOUS_HEIGHT_SLICES.json',
        cache/'ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz', model, head, Path(__file__))}
    write(a.output/'CURRENT_COMPLETE_NINE_ASCENT_HEIGHT_HULLS.json', result)
    write(a.output/'ADDED_EARLY_HEAD_TANGENT_CONES.json', dict(root_design_sha256=sha(a.directory), cones=added))
    return result


def docs(old, new):
    old_changed = copy.deepcopy(old); old_changed['legs'] = []
    new_changed = copy.deepcopy(new); new_changed['legs'] = []
    retained = copy.deepcopy(new); retained['legs'] = []
    old_legs = {l['id']: l for l in old['legs']}
    for leg in new['legs']:
        if leg['id'].endswith('/reverse') or 'centre_curve' not in leg:
            continue
        if '/exit3/' in leg['id']:
            old_leg = copy.deepcopy(old_legs[leg['id']]); segments = old_leg['centre_curve']['segments']
            join = leg['centre_curve']['segments'][3]['controls'][0]
            prefix = dict(type='LINE', controls=[segments[4]['controls'][0], join])
            old_leg['centre_curve']['segments'] = segments[1:4]+[prefix]
            old_changed['legs'].append(old_leg)
            fresh = copy.deepcopy(leg); fresh['centre_curve']['segments'] = leg['centre_curve']['segments'][1:3]
            new_changed['legs'].append(fresh)
            kept = copy.deepcopy(leg); kept['centre_curve']['segments'] = [leg['centre_curve']['segments'][0], *leg['centre_curve']['segments'][3:]]
            retained['legs'].append(kept)
        else:
            retained['legs'].append(copy.deepcopy(leg))
    return old_changed, new_changed, retained


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'directory', 'previous', 'source', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); a.root = Path(__file__).resolve().parents[1]
    assert not a.output.exists(); a.output.mkdir(parents=True)
    old, new = [json.loads(path.read_text('utf8')) for path in (a.previous, a.directory)]
    hull = current_hull(a, old, new)
    old_doc, new_doc, retained_doc = docs(old, new)
    changed_old, changed_new = [make_parts(doc, hull) for doc in (old_doc, new_doc)]
    low = np.min([part['bounds'][0] for part in changed_old+changed_new], axis=0)-3
    high = np.max([part['bounds'][1] for part in changed_old+changed_new], axis=0)+3
    retained_parts = [part for part in make_parts(retained_doc, hull)
                      if np.all(np.array(part['bounds'][0]) <= high) and np.all(np.array(part['bounds'][1]) >= low)]
    groups = (changed_old, changed_new, retained_parts)
    members = defaultdict(lambda: [[], [], []]); selected = defaultdict(set)
    for group, parts in enumerate(groups):
        for number, part in enumerate(parts):
            lo, hi = [np.floor((np.array(v)+(-2.01 if i == 0 else 2.01))/16).astype(int)
                      for i, v in enumerate(part['bounds'])]
            grid = np.indices(tuple(hi-lo+1)).reshape(3, -1).T+lo
            centres = grid*16+8; eq = part['equations']
            active = np.arange(len(grid))
            for start in range(0, len(eq), 16):
                rows = eq[start:start+16]
                active = active[np.all(centres[active]@rows[:, :3].T+rows[:, 3] <= 3.1+8*np.abs(rows[:, :3]).sum(1), axis=1)]
                if not len(active): break
            for cx, sy, cz in grid[active]:
                key = int(cx), int(cz), int(sy)
                if group < 2:
                    selected[key[:2]].add(key[2])
                members[key][group].append(number)
    statuses = chunk_statuses(a.base/'WORLD', 'projectseele:geofront', selected)
    assert all(status == 'full' for status in statuses.values()), 'All local early chunks must be FULL'
    palette = ['minecraft:air']; codes = {palette[0]: 0}; rows = []
    local = np.indices((16, 16, 16)).reshape(3, -1).T[:, [2, 0, 1]]+.5
    for number, (cx, cz, sy, pal, before) in enumerate(iter_selected_sections(a.base/'WORLD', 'projectseele:geofront', selected), 1):
        mapping = []
        for state in pal:
            if state not in codes: codes[state] = len(palette); palette.append(state)
            mapping.append(codes[state])
        xyz = local+[cx*16, sy*16, cz*16]; masks = []
        for group, parts in enumerate(groups):
            core, shell = np.zeros(4096, bool), np.zeros(4096, bool)
            for index in members[cx, cz, sy][group]:
                core |= contains(parts[index], xyz)
                shell |= contains(parts[index], xyz, 2)
            masks.extend((core, shell))
        rows.append(((cx, cz, sy), np.array(mapping, np.uint16)[before], *masks))
        if number % 200 == 0: print('local early sections', number, flush=True)
    names = ('old_core', 'old_shell', 'new_core', 'new_shell', 'retained_core', 'retained_shell')
    np.savez_compressed(a.output/'MEASURED_SOURCE.npz', section_keys=np.array([r[0] for r in rows], np.int32),
        before=np.array([r[1] for r in rows], np.uint16), palette=palette,
        **{name: np.array([r[j+2] for r in rows]) for j, name in enumerate(names)})
    report = dict(world_written=False, clearance_passed=False, root_design_sha256=sha(a.directory),
        previous_design_sha256=sha(a.previous), hulls_sha256=sha(a.output/'CURRENT_COMPLETE_NINE_ASCENT_HEIGHT_HULLS.json'),
        root_spatial_plan_sha256=sha(a.base/'ROOT_SPATIAL_PLAN.json'), measured_legs='ONLY_THREE_CHANGED_EARLY_SEGMENTS_AND_OLD_MAIN_PREFIX',
        unchanged_routes_measured_only_where_intersecting_change_sections=True, original_body_source_reswept=False,
        sections=len(rows), chunks=len(selected), changed_old_parts=len(changed_old), changed_new_parts=len(changed_new),
        retained_intersection_parts=len(retained_parts), source_sha256=sha(a.output/'MEASURED_SOURCE.npz'),
        old_new_shape_bounds=[low.tolist(), high.tolist()])
    write(a.output/'MEASURED_REPORT.json', report); print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
