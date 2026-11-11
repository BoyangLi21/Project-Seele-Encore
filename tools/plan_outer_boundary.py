"""Resources for the outer boundary terrain (F1 sea, F2 mountains) of the GeoFront generator.

outer_edge.bin.gz: on the surface-field grid every 8 blocks, the distance to the
nearest known column (surveyed rectangle or saved chunk), that column's ground,
and whether the cell is a saved chunk. outer_coast.bin.gz: every 16 blocks over
the Sagami Bay region, the signed distance to the coastline, positive at sea.
Inside the surveyed rectangle the coast is the surface field's own sea; outside
it comes from GSI DEM tiles (sea is the tiles' no-data value) or, without them,
from a coarse hand-placed line. The actual world is never opened: saved chunks
are read from a copy's region headers.
"""
import argparse
import gzip
import json
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

DEM = (-1982, -1548, 4386, 3720)
ANCHOR = dict(lon=139.0085, lat=35.2662, x=30, z=220, metres_per_block=4.0)
COAST_BOUNDS = (-12000, -10000, 20000, 24000)
COAST_STEP = 16
# Coarse fallback, west to east with land on the left (Irozaki ... Atami, the surveyed
# coast's exits, Kozu ... Jogashima). Used only where no GSI tile covers a cell.
FALLBACK = [(-100000, 18699), (-3572, 18699), (-1299, 16618), (859, 13845), (3018, 10377), (2904, 9129), (2177, 8547),
            (1882, 7326), (1950, 6356), (1655, 4941), (2360, 3720), (4386, 78), (4654, -52), (5631, -607), (6926, -856),
            (7790, -1217), (9040, -1189), (10744, -718), (12334, -856), (12902, -412), (13130, 392), (13879, 3942), (100000, 3942)]


def metres_per_degree():
    a, e2, lat = 6378137.0, 0.00669437999014, math.radians(ANCHOR['lat'])
    w = 1 - e2 * math.sin(lat) ** 2
    return a / math.sqrt(w) * math.cos(lat) * math.pi / 180, a * (1 - e2) / w ** 1.5 * math.pi / 180


def world_of(lon, lat):
    mx, mz = metres_per_degree()
    s = ANCHOR['metres_per_block']
    return ANCHOR['x'] + (lon - ANCHOR['lon']) * mx / s, ANCHOR['z'] - (lat - ANCHOR['lat']) * mz / s


def lonlat_of(x, z):
    mx, mz = metres_per_degree()
    s = ANCHOR['metres_per_block']
    return ANCHOR['lon'] + (x - ANCHOR['x']) * s / mx, ANCHOR['lat'] - (z - ANCHOR['z']) * s / mz


def read_field(path):
    raw = gzip.decompress(Path(path).read_bytes())
    magic, x0, z0, step, w, d = struct.unpack('>6i', raw[:24])
    heights = np.frombuffer(raw[24:24 + w * d * 2], '>i2').reshape(d, w)
    waters = np.frombuffer(raw[24 + w * d * 2:], '>i2').reshape(d, w)
    return (x0, z0, step, w, d), heights, waters


def saved_chunks(region_dir, drop):
    chunks = set()
    for path in Path(region_dir).glob('r.*.mca'):
        rx, rz = map(int, path.stem.split('.')[1:3])
        header = path.read_bytes()[:4096]
        if len(header) < 4096:
            continue
        for i in range(1024):
            if struct.unpack('>I', header[i * 4:i * 4 + 4])[0]:
                chunks.add((rx * 32 + (i & 31), rz * 32 + (i >> 5)))
    return chunks - drop


def gsi_sea(tile_dir, xs, zs):
    """True where a GSI z12 DEM pixel is no-data (sea), None where no tile was fetched."""
    lon, lat = lonlat_of(xs, zs)
    n = 2 ** 12
    fx = (lon + 180) / 360 * n
    lat_r = np.radians(lat)
    fy = (1 - np.log(np.tan(lat_r) + 1 / np.cos(lat_r)) / math.pi) / 2 * n
    tx, ty = fx.astype(int), fy.astype(int)
    px, py = ((fx - tx) * 256).astype(int).clip(0, 255), ((fy - ty) * 256).astype(int).clip(0, 255)
    sea = np.full(xs.shape, -1, np.int8)
    manifest = json.loads((Path(tile_dir) / 'manifest.json').read_text('utf8'))
    for key, state in manifest['tiles'].items():
        x, y = map(int, key.split('/'))
        mask = (tx == x) & (ty == y)
        if not mask.any():
            continue
        if state == 'sea':
            sea[mask] = 1
            continue
        rgb = np.asarray(Image.open(Path(tile_dir) / f'{x}' / f'{y}.png').convert('RGB')).astype(np.int64)
        value = rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]
        sea[mask] = (value[py[mask], px[mask]] == 2 ** 23).astype(np.int8)
    return sea


def fallback_land(xs, zs):
    inside = np.zeros(xs.shape, bool)
    poly = FALLBACK + [(100000, -100000), (-100000, -100000)]
    for (ax, az), (bx, bz) in zip(poly, poly[1:] + poly[:1]):
        cross = (az > zs) != (bz > zs)
        with np.errstate(divide='ignore', invalid='ignore'):
            at = (bx - ax) * (zs - az) / (bz - az) + ax
        inside ^= cross & (xs < at)
    return inside


def build(a):
    (fx0, fz0, fstep, fw, fd), heights, waters = read_field(a.field)
    drop = {tuple(c) for c in json.loads(Path(a.drop).read_text('utf8'))['chunks']} if a.drop else set()
    saved = saved_chunks(a.region_dir, drop)

    # outer_edge: known = surveyed rectangle or saved chunk, on the field grid every 8 blocks.
    k = 8 // fstep
    xs = fx0 + np.arange(0, fw, k) * fstep
    zs = fz0 + np.arange(0, fd, k) * fstep
    X, Z = np.meshgrid(xs, zs)
    dem = (X >= DEM[0]) & (X <= DEM[2]) & (Z >= DEM[1]) & (Z <= DEM[3])
    have = np.array([[(int(x) >> 4, int(z) >> 4) in saved for x in xs] for z in zs])
    known = dem | have
    ground = np.round(heights[::k, ::k] / 16.0).astype(np.int32)
    dist, (iz, ix) = ndimage.distance_transform_edt(~known, return_indices=True)
    edge = struct.pack('>6i', 0x484B4532, fx0, fz0, 8, known.shape[1], known.shape[0])
    edge += np.clip(np.round(dist * 8), 0, 32767).astype('>i2').tobytes() + ground[iz, ix].astype('>i2').tobytes()
    edge += have.astype(np.uint8).tobytes()
    (Path(a.out) / 'outer_edge.bin.gz').write_bytes(gzip.compress(edge, 9))

    # outer_coast: sea mask, then a signed distance clipped to +-2048 blocks.
    cx0, cz0, cx1, cz1 = COAST_BOUNDS
    gx = np.arange(cx0, cx1 + 1, COAST_STEP)
    gz = np.arange(cz0, cz1 + 1, COAST_STEP)
    GX, GZ = np.meshgrid(gx, gz)
    sea = np.where(fallback_land(GX.astype(float), GZ.astype(float)), 0, 1).astype(np.int8)
    source = np.full(sea.shape, 'fallback', object)
    if a.gsi:
        gsea = gsi_sea(a.gsi, GX.astype(float), GZ.astype(float))
        sea = np.where(gsea >= 0, gsea, sea)
    inside = (GX >= DEM[0]) & (GX <= DEM[2]) & (GZ >= DEM[1]) & (GZ <= DEM[3])
    fi = np.clip((GZ - fz0) // fstep, 0, fd - 1)
    fj = np.clip((GX - fx0) // fstep, 0, fw - 1)
    sea = np.where(inside, (waters[fi, fj] == -82).astype(np.int8), sea)
    seab = sea.astype(bool)
    signed = ndimage.distance_transform_edt(seab) - ndimage.distance_transform_edt(~seab)
    signed = np.clip(np.round(signed * COAST_STEP), -2048, 2048).astype('>i2')
    coast = struct.pack('>5i', 0x484B4331, cx0, cz0, COAST_STEP, len(gx)) + struct.pack('>i', len(gz)) + signed.tobytes()
    (Path(a.out) / 'outer_coast.bin.gz').write_bytes(gzip.compress(coast, 9))
    report = dict(saved_chunks=len(saved), dropped=len(drop), known_cells=int(known.sum()), coast_cells=int(sea.size),
                  sea_cells=int(sea.sum()), gsi=bool(a.gsi), world_written=False)
    print(json.dumps(report))


def fetch(a):
    """Download the listed GSI z12 DEM tiles once; 404 tiles are recorded as all-sea."""
    import urllib.request
    import urllib.error
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tiles = json.loads(Path(a.tiles).read_text('utf8'))
    manifest = dict(source='https://cyberjapandata.gsi.go.jp/xyz/dem_png/12/{x}/{y}.png', attribution='出典：国土地理院', tiles={})
    total = 0
    for x, y in tiles:
        url = manifest['source'].format(x=x, y=y)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'ProjectSEELE-map-tools'}), timeout=30) as r:
                data = r.read()
            (out / str(x)).mkdir(exist_ok=True)
            (out / str(x) / f'{y}.png').write_bytes(data)
            manifest['tiles'][f'{x}/{y}'] = 'png'
            total += len(data)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            manifest['tiles'][f'{x}/{y}'] = 'sea'
    manifest['bytes'] = total
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(dict(tiles=len(tiles), png=sum(v == 'png' for v in manifest['tiles'].values()), bytes=total)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('build', 'fetch'))
    parser.add_argument('--field', help='hakone_surface.bin.gz')
    parser.add_argument('--region-dir', help='region folder of a copy of the GeoFront dimension')
    parser.add_argument('--drop', help='JSON {"chunks": [[cx, cz], ...]} treated as deleted')
    parser.add_argument('--gsi', help='folder written by fetch')
    parser.add_argument('--tiles', help='fetch: JSON list of [x, y] z12 tiles')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    globals()[args.mode](args)
