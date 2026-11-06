"""Cache and decode a finite GSI district without replacing earlier map inputs.

Coordinates use the project's established 1:4 geographic frame. The output is
reference geometry, not a claim that buildings or roads exist in the save.
Network retrieval is opt-in; previously cached tiles are always reused.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import json
import math
from pathlib import Path

import mapbox_vector_tile
from shapely.geometry import box, shape

from hakone_geography import Frame, fetch_tile, tile_xy


def prepare(a):
    if a.out.exists():
        raise ValueError('Use a fresh district reference directory')
    x, z, X, Z = a.bounds
    if x >= X or z >= Z or X - x > 4096 or Z - z > 4096:
        raise ValueError('Expected a finite district of at most 4096 blocks per axis')
    config = json.loads((a.gis / 'geography.json').read_text('utf8'))
    frame = Frame(config)
    west, north = frame.geographic(x, z)
    east, south = frame.geographic(X, Z)
    tx0, ty0 = map(math.floor, tile_xy(west, north, a.zoom))
    tx1, ty1 = map(math.floor, tile_xy(east, south, a.zoom))
    tiles = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)]
    if len(tiles) > 1024:
        raise ValueError('Too many reference tiles')
    a.out.mkdir(parents=True)
    counts = Counter()
    paths = {}
    if a.fetch:
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {pool.submit(fetch_tile, a.gis, 'optimal_bvmap-v1', a.zoom, tx, ty, 'pbf'): (tx, ty) for tx, ty in tiles}
            for n, job in enumerate(as_completed(jobs), 1):
                path, status = job.result()
                counts[status] += 1
                if path.exists():
                    paths[jobs[job]] = path
                if n % 12 == 0 or n == len(tiles):
                    print('District reference tiles', n, '/', len(tiles), dict(counts), flush=True)
    else:
        for tx, ty in tiles:
            path = a.gis / f'tiles/optimal_bvmap-v1/{a.zoom}/{tx}/{ty}.pbf'
            counts['cached' if path.exists() else 'missing'] += 1
            if path.exists():
                paths[tx, ty] = path
    boundary = box(*a.bounds)
    features = []
    layers = Counter()
    invalid = Counter()
    wanted = {'BldA', 'SpcfArea', 'RdCL', 'RailCL', 'Anno', 'WA', 'RvrCL', 'WStrL', 'TpgphArea'}
    for n, ((tx, ty), path) in enumerate(sorted(paths.items()), 1):
        decoded = mapbox_vector_tile.decode(path.read_bytes(), default_options={'y_coord_down': True})
        for name, layer in decoded.items():
            if name not in wanted:
                continue
            extent = layer['extent']

            def convert(coords):
                if not coords:
                    return coords
                if isinstance(coords[0], (int, float)):
                    gx, gy = (tx + coords[0] / extent) / 2 ** a.zoom, (ty + coords[1] / extent) / 2 ** a.zoom
                    lon = gx * 360 - 180
                    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * gy))))
                    px, pz = frame.world(lon, lat)
                    return [round(float(px), 3), round(float(pz), 3)]
                return [convert(child) for child in coords]

            for index, feature in enumerate(layer['features']):
                raw = feature['geometry']
                if not raw.get('coordinates'):
                    continue
                geometry = dict(type=raw['type'], coordinates=convert(raw['coordinates']))
                obj = shape(geometry)
                if not obj.is_valid:
                    invalid[name] += 1
                    continue
                if obj.is_empty or not obj.intersects(boundary):
                    continue
                props = dict(feature['properties'], source_layer=name, source_tile=[a.zoom, tx, ty], source_feature_index=index)
                features.append(dict(type='Feature', properties=props, geometry=geometry))
                layers[name] += 1
        if n % 12 == 0 or n == len(paths):
            print('Decoded reference tiles', n, '/', len(paths), 'features', len(features), flush=True)
    missing = [list(v) for v in tiles if v not in paths]
    provenance = dict(bounds_xz=a.bounds, zoom=a.zoom, requested_tiles=tiles, tile_results=dict(counts),
                      missing_tiles=missing, complete=not missing, feature_counts=dict(layers), invalid_geometries_skipped=dict(invalid),
                      source='https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/',
                      attribution=config['source_urls']['attribution'], metres_per_block=frame.scale,
                      current_business_names_verified=False, game_world_written=False,
                      geometry_policy='Keep full intersecting features; tile seams and transport levels require explicit downstream reconciliation')
    with gzip.open(a.out / 'features.world.geojson.gz', 'wt', encoding='utf8') as stream:
        json.dump(dict(type='FeatureCollection', coordinate_system='Project SEELE X/Z blocks', provenance=provenance, features=features), stream, ensure_ascii=False)
    (a.out / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2), 'utf8')
    print('District reference ready', json.dumps(dict(features=len(features), complete=not missing, layers=dict(layers))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--gis', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--bounds', type=int, nargs=4, required=True)
    parser.add_argument('--zoom', type=int, choices=(14, 15, 16), default=16)
    parser.add_argument('--fetch', action='store_true')
    prepare(parser.parse_args())
