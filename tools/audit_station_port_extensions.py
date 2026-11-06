"""Read-only finite native station-port sweeps from frozen candidate overlays.

The report identifies exact collisions and affected public/device cells. It never
edits an installed package, creates a repair delta, or declares through service.
"""
import argparse
import math
from pathlib import Path

import nbtlib
import numpy as np
from shapely.geometry import LineString, Point, box
from shapely.prepared import prep

from author_hakone_lakefront import Editor
from author_station_layout import collision, read, write
from check_kamonomiya_visible_models import clipped_half_width
from map_pipeline.mtr_vehicle_pose import envelope


def audit(site, out):
    candidate = Path(site['candidate'])
    e = Editor(candidate)
    capture = read(candidate / 'capture.json')
    design = read(candidate / 'station-design.json')
    native = read(Path(site['geometry']))
    by_id = {q['input_rail_id']: q for q in native['rails']}
    nodes = {tuple(q) for q in design['station_multi_level_nodes']}
    edits = {tuple(q['pos']): q for q in read(candidate / 'exact-edits.json')}
    devices = {tuple(int(q[k]) for k in ('x', 'y', 'z'))
               for q in nbtlib.load(candidate / 'captured-devices.dat')['Devices']}
    l, t, r, b = capture['bounds_xz']
    y = design['rail_level']
    rows, hits, unknown = [], {}, set()
    for chain in site['port_chains']:
        points = []
        for segment in chain['segments']:
            q = by_id[segment['id']]
            ps = q['points'][::-1] if segment.get('reverse') else q['points']
            if points and not np.allclose(points[-1], ps[0]):
                raise ValueError('Native finite port is discontinuous')
            points.extend(ps if not points else ps[1:])
        pts = np.asarray(points)
        if not np.allclose(pts[:, 1], y):
            raise ValueError('Only level finite port alignments are supported')
        line = LineString(pts[:, [0, 2]])
        station = by_id[chain['platform']]
        a, z = np.asarray(station['points'])[[0, -1]][:, [0, 2]]
        tangent = (z - a) / np.linalg.norm(z - a)
        for ident in site['models']:
            model = read(Path(site['model_source']) / (ident + '.json'))
            if not model['all_selected_conditions_enclosed']:
                raise ValueError('Incomplete model condition envelope')
            with np.load(Path(site['model_source']) / (ident + '-visible-cubes.npz')) as f:
                cubes, slides = f['cubes'].copy(), f['door_slides'].copy()
            extent = max(abs(model['visible_motion_bounds'][i][2]) for i in (0, 1)) + .03
            tested, model_hits, cache, exact_cache = 0, [], {}, {}
            for h in range(5):
                widths = [v for cube, slide in zip(cubes, slides)
                          if (v := clipped_half_width(cube, slide, h - .03, h + 1.03)) is not None]
                if not widths:
                    continue
                def swept(width):
                    return prep(envelope(line, length=2 * extent, width=2 * width,
                                         bogie1_position=-6, bogie2_position=6,
                                         spacing=.125, directions=(1, -1)))
                band = swept(max(widths) + .03)
                for x in range(math.floor(band.context.bounds[0]), math.ceil(band.context.bounds[2])):
                    for zz in range(math.floor(band.context.bounds[1]), math.ceil(band.context.bounds[3])):
                        if not band.intersects(box(x, zz, x + 1, zz + 1)):
                            continue
                        p = (x, y + h, zz)
                        if not l <= x <= r or not t <= zz <= b:
                            unknown.add(p)
                            continue
                        state = e.state(*p)
                        tested += 1
                        for q in collision(state):
                            key = (h + q[1], h + q[4])
                            if key not in cache:
                                widths = [v for cube, slide in zip(cubes, slides)
                                          if (v := clipped_half_width(cube, slide, key[0] - .03, key[1] + .03)) is not None]
                                cache[key] = swept(max(widths) + .03) if widths else None
                            poly = cache[key]
                            if not poly or not poly.intersects(box(x + q[0], zz + q[2], x + q[3], zz + q[5])):
                                continue
                            if key not in exact_cache:
                                exact_widths = [v for cube, slide in zip(cubes, slides)
                                                if (v := clipped_half_width(cube, slide, key[0] + 1e-7, key[1] - 1e-7)) is not None]
                                exact_cache[key] = envelope(line, length=2 * (extent - .03),
                                    width=2 * max(exact_widths), bogie1_position=-6,
                                    bogie2_position=6, spacing=.125, directions=(1, -1)) if exact_widths else None
                            exact = exact_cache[key]
                            exact_area = (exact.intersection(box(x + q[0], zz + q[2],
                                          x + q[3], zz + q[5])).area if exact is not None else 0)
                            along = float((np.array([x + .5, zz + .5]) - a) @ tangent)
                            end = 'start' if along < 0 else 'end' if along > station['length'] else 'station'
                            before = e.state(*p, original=True)
                            row = hits.setdefault(p, dict(pos=list(p), state=state, original_state=before,
                                changed_by_station_candidate=p in edits and edits[p]['after'] == state,
                                original_device=p in devices,
                                public_floor_nodes=[list(n) for n in nodes
                                                    if n[0] == x and n[2] == zz and (n[1] + 1) // 2 == p[1]],
                                rails=[], models=[], ports=[], actual_visible_models=[],
                                maximum_actual_cross_section_overlap_area=0))
                            if exact_area > 1e-9 and ident not in row['actual_visible_models']:
                                row['actual_visible_models'].append(ident)
                            row['maximum_actual_cross_section_overlap_area'] = max(
                                row['maximum_actual_cross_section_overlap_area'], float(exact_area))
                            for key2, value in [('rails', chain['platform']), ('models', ident), ('ports', end)]:
                                if value not in row[key2]:
                                    row[key2].append(value)
                            model_hits.append(list(p))
                            break
            rows.append(dict(platform=chain['platform'], model=ident, tested_blocks=tested,
                             collision_cells=model_hits, finite_composed_length=line.length,
                             finite_endpoints=[list(line.coords[0]), list(line.coords[-1])]))
    positions = sorted(hits)
    for row in hits.values():
        row['actual_visible_model_intersection'] = bool(row['actual_visible_models'])
        row['safety_margin_only'] = not row['actual_visible_model_intersection']
    bounds = ([min(p[i] for p in positions) for i in range(3)] +
              [max(p[i] for p in positions) for i in range(3)]) if positions else None
    report = dict(station=design['name'], candidate=str(candidate), candidate_overlay_only=True,
                  actual_current_readback_required_before_any_patch=True, world_written=False,
                  native_geometry=str(site['geometry']), native_geometry_only_no_simulator=True,
                  bogie1_position=-6, bogie2_position=6,
                  pose_source='MTR native smoothed bogie samples; map_pipeline.mtr_vehicle_pose',
                  full_model_y_bands=True, exact_saved_collision_boxes=True,
                  directions=[1, -1], sample_spacing=.125, checks=rows,
                  confirmed_collisions=[hits[p] for p in positions], confirmed_collision_count=len(positions),
                  actual_visible_collision_count=sum(q['actual_visible_model_intersection'] for q in hits.values()),
                  safety_margin_only_count=sum(q['safety_margin_only'] for q in hits.values()),
                  collision_bounds=bounds, unknown_cells=[list(p) for p in sorted(unknown)],
                  existing_public_nodes=len(nodes), original_devices=len(devices),
                  stop_platform_contract_retested=False, through_service_complete=False,
                  repair_plan=None, collision_cells_are_not_automatic_deletion_permission=True,
                  remaining_beyond_finite_endpoints_unverified=True)
    out.mkdir(parents=True, exist_ok=False)
    write(out / 'report.json', report)
    print(site['id'], len(positions), 'confirmed cells;', len(unknown), 'unknown cells', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for item in read(args.config)['sites']:
        audit(item, args.out / item['id'])
