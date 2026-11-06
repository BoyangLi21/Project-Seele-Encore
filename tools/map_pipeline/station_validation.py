"""Offline checks shared by cardinal, single-side-platform station candidates.

A measured relocation is a specific recorded design, never a larger global
tolerance. Its cached rail must connect to the original station's cached rail.
This checks local geometry only; native registration and visible vehicle model
checks remain separate requirements.
"""
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point, shape


DEFAULT_STATIONS = Path('F:/eva/artifacts/hakone_geography_20261029/stations.json')


def read_json(path):
    return json.loads(Path(path).read_text('utf8'))


def axis(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180


def axis_error(a, b):
    return abs((a - b + 90) % 180 - 90)


def _close(a, b, tolerance=.001):
    return len(a) == len(b) and math.dist(a, b) <= tolerance


def _finite_values(value):
    if isinstance(value, dict):
        return all(_finite_values(v) for v in value.values())
    if isinstance(value, list):
        return all(_finite_values(v) for v in value)
    return not isinstance(value, float) or math.isfinite(value)


def _measured_geography(candidate, config, design, pa, pb, ref, errors):
    """Bind recorded adaptation to endpoints and independently cached geometry."""
    measured = config['measured_adaptation']
    centre = [(pa[i] + pb[i]) / 2 + .5 for i in (0, 2)]
    original = ref['track_centre_xz']
    delta = [centre[i] - original[i] for i in range(2)]
    if not (measured.get('approved_game_adaptation') is True
            and measured.get('one_to_one_restoration_claimed') is False
            and isinstance(measured.get('reason'), str) and measured['reason'].strip()):
        errors.append(['unrecorded-station-adaptation'])
    for key, actual in [('original_reference_centre', original),
                        ('actual_station_centre', centre), ('translation_xz', delta)]:
        if not _close(measured[key], actual):
            errors.append(['station-adaptation-record-mismatch', key])
    for key in ('original_reference_centre', 'actual_station_centre'):
        if key in design and not _close(design[key], measured[key]):
            errors.append(['station-design-adaptation-mismatch', key])
    if (abs(pa[1] - measured['rail_y']) > .001
            or abs(pa[1] - ref['terrain_world_y'] - measured['elevation_above_reference_terrain']) > .001):
        errors.append(['station-adaptation-record-mismatch', 'rail_y'])
    if abs(math.dist(centre, original) - measured['translation_metres']) > .001:
        errors.append(['station-adaptation-record-mismatch', 'translation_metres'])

    geography = read_json(candidate / config['reference_geography'])
    rails = {row['feature_index']: row for row in geography
             if row.get('properties', {}).get('source_layer') == 'RailCL'}
    selected = measured['local_rail_feature_index']
    source = measured['original_station_rail_feature_index']
    if selected not in rails or source not in rails:
        errors.append(['station-cached-rail-reference-missing'])
        return {'centre_xz': centre, 'translation_xz': delta}
    # Both endpoints of the adaptation must lie on the same non-JR component.
    non_jr = {key: shape(row['geometry']) for key, row in rails.items()
              if row['properties'].get('vt_rtcode') == 'JR以外'
              and row['geometry']['type'] == 'LineString'}
    if selected not in non_jr or source not in non_jr:
        errors.append(['station-cached-rail-is-not-non-JR'])
        return {'centre_xz': centre, 'translation_xz': delta}
    reached = {source}
    queue = [source]
    while queue:
        current = non_jr[queue.pop()]
        for key, line in non_jr.items():
            if key in reached:
                continue
            # End-to-end continuity; a crossing alone is not a connection.
            if min(math.dist(a, b) for a in (current.coords[0], current.coords[-1])
                   for b in (line.coords[0], line.coords[-1])) <= .1:
                reached.add(key)
                queue.append(key)
    if selected not in reached:
        errors.append(['station-relocation-not-on-same-cached-corridor'])
    original_line = LineString(ref['station_track'])
    original_deviation = original_line.hausdorff_distance(non_jr[source])
    if original_deviation > .1:
        errors.append(['station-original-cached-track-mismatch', original_deviation])

    local = non_jr[selected]
    p = Point(centre)
    along = local.project(p)
    a = local.interpolate(max(0, along - .5))
    b = local.interpolate(min(local.length, along + .5))
    local_axis = axis(a.coords[0], b.coords[0])
    native_axis = axis([pa[0], pa[2]], [pb[0], pb[2]])
    # Fixed small centre and angular bounds are independent of the recorded shift.
    distance = local.distance(p)
    if distance > 2 or axis_error(native_axis, local_axis) > 15:
        errors.append(['station-local-cached-rail-adaptation-out-of-bounds'])
    if axis_error(local_axis, measured['local_cached_axis_degrees']) > .1:
        errors.append(['station-local-axis-record-mismatch'])
    native_line = LineString([(pa[0] + .5, pa[2] + .5), (pb[0] + .5, pb[2] + .5)])
    deviation = max(local.distance(native_line.interpolate(i / 96, normalized=True)) for i in range(97))
    # Record the measured maximum rather than granting a free-form corridor width.
    if abs(deviation - measured['maximum_track_to_cached_rail_distance']) > .05:
        errors.append(['station-track-cached-rail-deviation-mismatch'])
    return dict(centre_xz=centre, original_reference_centre=original,
                translation_xz=delta, translation_metres=math.dist(centre, original),
                local_rail_feature_index=selected, original_station_rail_feature_index=source,
                same_non_JR_cached_component=selected in reached,
                original_cached_track_deviation=original_deviation,
                centre_to_cached_rail_distance=distance,
                maximum_track_to_cached_rail_distance=deviation,
                local_cached_axis_degrees=local_axis, native_axis_degrees=native_axis,
                axis_error_degrees=axis_error(native_axis, local_axis), rail_y=pa[1])


def station_preflight(candidate, design=None, plan=None, config=None):
    """Return errors and derived geometry without reading a live world or writing.

    Passing dictionaries permits isolated rejection tests without modifying a
    frozen candidate. Missing authoring-plan.json never disables geography.
    """
    candidate = Path(candidate)
    design = read_json(candidate / 'station-design.json') if design is None else design
    plan = read_json(candidate / 'native-station-plan.json') if plan is None else plan
    config_path = candidate / 'station-verification-config.json'
    config = (read_json(config_path) if config_path.exists() else {}) if config is None else config
    errors = []
    result = dict(errors=errors, rail_clearance_bounds=None, platform_length=None,
                  platform_side=None, geographic_reference_verified=False,
                  configuration='station-verification-config.json' if config else 'legacy-cardinal-defaults')
    if config and (config.get('schema') != 'station-verification-v1'
                   or config.get('station') != design['station'] or not _finite_values(config)):
        errors.append(['station-verification-config-identity'])
        return result
    if len(plan.get('rails', [])) != 1 or len(plan.get('stations', [])) != 1 or plan.get('lines'):
        errors.append(['compact-station-native-scope'])
        return result
    rail = plan['rails'][0]
    pa, pb = rail['from'], rail['to']
    length = design.get('platform_length', 48)
    if (len(pa) != 3 or len(pb) != 3
            or not all(isinstance(n, int) and not isinstance(n, bool) for n in pa + pb)
            or pa[1] != pb[1]
            or sum(pa[i] != pb[i] for i in (0, 2)) != 1
            or sum(abs(pa[i] - pb[i]) for i in (0, 2)) != length or length != 48):
        errors.append(['compact-station-track-geometry'])
        return result
    result['platform_length'] = length
    directions = ('E', 'W') if pb[0] > pa[0] else ('W', 'E') if pb[0] < pa[0] else ('S', 'N') if pb[2] > pa[2] else ('N', 'S')
    if ((rail.get('from_angle'), rail.get('to_angle')) != directions
            or rail.get('mode') != 'TRAIN' or rail.get('kind') != 'platform'):
        errors.append(['compact-station-track-direction'])
    if 'rail_level' in design and design['rail_level'] != pa[1]:
        errors.append(['station-design-rail-level-mismatch'])
    if plan['stations'][0]['name'] != design['station']:
        errors.append(['station-native-plan-name'])
    if not 0 < design.get('planned_maximum_consist_length', 40) <= length:
        errors.append(['station-consist-exceeds-platform'])
    perpendicular = 2 if pa[2] == pb[2] else 0
    sides = ('north', 'south') if perpendicular == 2 else ('west', 'east')
    goals = [p[perpendicular] - pa[perpendicular] for name, p in design['goals'].items()
             if name.startswith('platform')]
    derived_side = sides[0] if goals and max(goals) < 0 else sides[1] if goals and min(goals) > 0 else None
    side = config.get('platform_side', derived_side)
    if side not in sides or side != derived_side:
        errors.append(['station-platform-side-mismatch'])
        return result
    result['platform_side'] = side
    if 'full_boarding_edge' in design:
        edge = design['full_boarding_edge']
        along_index = 0 if perpendicular == 2 else 2
        expected_axis = 'x' if along_index == 0 else 'z'
        edge_coordinate = edge.get('edge_z' if perpendicular == 2 else 'edge_x')
        sign = -1 if side == sides[0] else 1
        if (edge.get('axis') != expected_axis or edge_coordinate is None
                or sign * (edge_coordinate - pa[perpendicular]) <= 0):
            errors.append(['station-boarding-edge-side-mismatch'])
        if (edge.get('floor_y') != pa[1]
                or edge.get('samples') != list(range(min(pa[along_index], pb[along_index]), max(pa[along_index], pb[along_index]) + 1))):
            errors.append(['station-boarding-edge-geometry-mismatch'])
    authoring = candidate / 'authoring-plan.json'
    if authoring.exists() and ('north', 'east', 'south', 'west')[read_json(authoring)['rotation'] % 4] != side:
        errors.append(['station-platform-authoring-rotation-mismatch'])
    low, high = (1, 2) if side == sides[0] else (2, 1)
    if perpendicular == 2:
        clearance = [min(pa[0], pb[0]), pa[1], pa[2] - low, max(pa[0], pb[0]), pa[1] + 4, pa[2] + high]
    else:
        clearance = [pa[0] - low, pa[1], min(pa[2], pb[2]), pa[0] + high, pa[1] + 4, max(pa[2], pb[2])]
    result['rail_clearance_bounds'] = clearance
    if 'rail_clearance_bounds' in design and clearance != design['rail_clearance_bounds']:
        errors.append(['declared-track-envelope-mismatch'])
    try:
        cached = candidate / config['cached_stations'] if config else DEFAULT_STATIONS
        references = [r for r in read_json(cached) if r['name'] == design['station']]
        if len(references) != 1:
            errors.append(['unique-cached-station-reference'])
            return result
        ref = references[0]
        before_geography = len(errors)
        if 'measured_adaptation' in config:
            result['geography'] = _measured_geography(candidate, config, design, pa, pb, ref, errors)
        else:
            centre = [(pa[i] + pb[i]) / 2 for i in (0, 2)]
            track = ref['station_track']
            angle_error = axis_error(axis([pa[0], pa[2]], [pb[0], pb[2]]), axis(track[0], track[-1]))
            offset = math.dist(centre, ref['track_centre_xz'])
            if offset > 2 or angle_error > 15 or abs(pa[1] - ref['terrain_world_y']) > 4:
                errors.append(['station-geographic-adaptation-out-of-bounds'])
            result['geography'] = dict(centre_xz=centre, original_reference_centre=ref['track_centre_xz'],
                                       centre_offset_metres=offset, axis_error_degrees=angle_error,
                                       reference='cached-station-track')
        result['geographic_reference_verified'] = len(errors) == before_geography
    except (OSError, KeyError, TypeError, ValueError, IndexError) as exc:
        errors.append(['station-geographic-reference-invalid', type(exc).__name__])
    return result
