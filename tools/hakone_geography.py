"""Offline Hakone GIS inputs and a single geographic frame for map authoring.

This command never opens a Minecraft world for writing. GSI numeric DEM and
vector data stay cached outside the source tree; no maps or animation images
become game textures. Geometry retains its source tile and feature attributes.
Dependencies: numpy, Pillow, mapbox-vector-tile (and matplotlib for plot).
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path
import urllib.error
import urllib.request

import numpy as np
from PIL import Image


CONFIG = Path(__file__).parent / "templates/hakone/geography.json"


class Frame:
    def __init__(self, config):
        self.config = config
        anchor = config["anchor"]
        self.scale = float(config["metres_per_block"])
        self.origin = np.asarray(anchor["world_xyz"], dtype=float)
        self.altitude = float(anchor["elevation_m"])
        self.lon, self.lat = float(anchor["longitude"]), float(anchor["latitude"])
        latitude = math.radians(self.lat)
        flattening = 1 / 298.257223563
        eccentricity2 = flattening * (2-flattening)
        q = 1 - eccentricity2 * math.sin(latitude)**2
        self.east_per_degree = math.pi/180 * 6378137 / math.sqrt(q) * math.cos(latitude)
        self.north_per_degree = math.pi/180 * 6378137 * (1-eccentricity2) / q**1.5

    def world(self, lon, lat):
        east = (np.asarray(lon)-self.lon) * self.east_per_degree
        north = (np.asarray(lat)-self.lat) * self.north_per_degree
        return self.origin[0] + east / self.scale, self.origin[2] - north / self.scale

    def geographic(self, x, z):
        return (self.lon + (np.asarray(x)-self.origin[0])*self.scale/self.east_per_degree,
                self.lat - (np.asarray(z)-self.origin[2])*self.scale/self.north_per_degree)

    def height(self, metres):
        return self.origin[1] + (np.asarray(metres) - self.altitude) / self.scale


def tile_xy(lon, lat, zoom):
    n = 2 ** zoom
    return ((np.asarray(lon) + 180) / 360 * n,
            (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n)


def tile_bounds(config, zoom):
    west, south, east, north = config["geographic_bounds_wsen"]
    x0, y0 = tile_xy(west, north, zoom)
    x1, y1 = tile_xy(east, south, zoom)
    return tuple(map(math.floor, (x0, y0, x1, y1)))


def fetch_tile(out, layer, zoom, x, y, extension):
    path = out / "tiles" / layer / str(zoom) / str(x) / f"{y}.{extension}"
    if path.exists():
        return path, "cached"
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://cyberjapandata.gsi.go.jp/xyz/{layer}/{zoom}/{x}/{y}.{extension}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return path, "absent"
        raise
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(data)
    temporary.replace(path)
    return path, "downloaded"


def fetch(config, out):
    jobs = []
    for layer, zoom, extension in [("dem_png", config["dem_zoom"], "png"),
                                    ("optimal_bvmap-v1", config["vector_zoom"], "pbf")]:
        x0, y0, x1, y1 = tile_bounds(config, zoom)
        jobs.extend((out, layer, zoom, x, y, extension)
                    for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
    counts, absent = Counter(), []
    with ThreadPoolExecutor(max_workers=4) as executor:
        pending = {executor.submit(fetch_tile, *args): args for args in jobs}
        for i, future in enumerate(as_completed(pending), 1):
            path, state = future.result()
            counts[state] += 1
            if state == "absent":
                absent.append(str(path.relative_to(out)))
            if i % 40 == 0 or i == len(jobs):
                print(f"GIS tiles {i}/{len(jobs)} {dict(counts)}", flush=True)
    receipt = dict(retrieved_utc=datetime.now(timezone.utc).isoformat(),
                   counts=counts, absent=absent, sources=config["source_urls"])
    (out / "sources.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")


def decode_dem(path):
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.int32)
    value = (rgb[:, :, 0] << 16) | (rgb[:, :, 1] << 8) | rgb[:, :, 2]
    invalid = value == 2 ** 23
    elevation = np.where(value > 2 ** 23, value - 2 ** 24, value).astype(np.float32) * .01
    elevation[invalid] = np.nan
    return elevation


def dem_mosaic(config, out):
    zoom = config["dem_zoom"]
    x0, y0, x1, y1 = tile_bounds(config, zoom)
    dem = np.full(((y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256), np.nan, dtype=np.float32)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            path = out / f"tiles/dem_png/{zoom}/{x}/{y}.png"
            if path.exists():
                dem[(y-y0)*256:(y-y0+1)*256, (x-x0)*256:(x-x0+1)*256] = decode_dem(path)
    np.savez_compressed(out / "dem.npz", elevation_m=dem, tile_origin=[x0, y0], zoom=zoom)
    return dem, x0, y0, zoom


def sample_dem(mosaic, lon, lat):
    dem, tx, ty, zoom = mosaic
    x, y = tile_xy(lon, lat, zoom)
    # Numeric samples are located at tile pixel coordinates per the GSI spec.
    px, py = (x-tx)*256, (y-ty)*256
    ix, iy = np.floor(px).astype(int), np.floor(py).astype(int)
    good = (ix >= 0) & (iy >= 0) & (ix < dem.shape[1]-1) & (iy < dem.shape[0]-1)
    ix, iy = np.clip(ix, 0, dem.shape[1]-2), np.clip(iy, 0, dem.shape[0]-2)
    fx, fy = px-ix, py-iy
    value = ((1-fx)*(1-fy)*dem[iy, ix] + fx*(1-fy)*dem[iy, ix+1]
             + (1-fx)*fy*dem[iy+1, ix] + fx*fy*dem[iy+1, ix+1])
    return np.where(good, value, np.nan)


def vectors(config, out, frame):
    import mapbox_vector_tile
    zoom = config["vector_zoom"]
    wanted = {"Anno", "RdCL", "RailCL", "RvrCL", "WA", "WStrL", "TpgphArea"}
    features, counts = [], Counter()
    for path in sorted((out / f"tiles/optimal_bvmap-v1/{zoom}").glob("*/*.pbf")):
        tx, ty = int(path.parent.name), int(path.stem)
        layers = mapbox_vector_tile.decode(path.read_bytes(), default_options={"y_coord_down": True})
        for layer_name, layer in layers.items():
            if layer_name not in wanted:
                continue
            extent = layer["extent"]

            def convert(coords):
                if isinstance(coords[0], (int, float)):
                    gx, gy = (tx+coords[0]/extent)/2**zoom, (ty+coords[1]/extent)/2**zoom
                    lon, lat = gx*360-180, math.degrees(math.atan(math.sinh(math.pi*(1-2*gy))))
                    x, z = frame.world(lon, lat)
                    return [round(float(x), 3), round(float(z), 3)]
                return [convert(child) for child in coords]

            for feature in layer["features"]:
                if not feature["geometry"].get("coordinates"):
                    continue
                properties = dict(feature["properties"], source_layer=layer_name,
                                  source_tile=[zoom, tx, ty])
                features.append(dict(type="Feature", properties=properties,
                                     geometry=dict(type=feature["geometry"]["type"],
                                                   coordinates=convert(feature["geometry"]["coordinates"]))))
                counts[layer_name] += 1
    with gzip.open(out / "features.world.geojson.gz", "wt", encoding="utf-8") as stream:
        json.dump(dict(type="FeatureCollection", coordinate_system="Project SEELE X/Z blocks; see geography.json",
                       attribution=config["source_urls"]["attribution"], features=features), stream, ensure_ascii=False)
    print("GIS feature counts", dict(counts), flush=True)
    return features, counts


def build(config, out):
    frame = Frame(config)
    mosaic = dem_mosaic(config, out)
    features, counts = vectors(config, out, frame)
    labels = []
    names = ("仙石", "金時", "明神", "大涌", "神山", "駒ヶ岳", "二子", "芦ノ湖", "芦ノ", "桃源", "箱根町港", "元箱根",
             "箱根湯本", "はこねゆもと", "とうのさわ", "おおひらだい", "みやのした", "こわきだに", "ちょうこくのもり",
             "ごうら", "そううんざん", "おおわくだに", "うばこ", "とうげんだい", "小田原漁港", "はやかわ", "おだわら")
    seen = set()
    for feature in features:
        props = feature["properties"]
        text = props.get("vt_text", "")
        if props["source_layer"] != "Anno" or not any(name in text for name in names):
            continue
        if feature["geometry"]["type"] != "Point":
            continue
        x, z = feature["geometry"]["coordinates"]
        key = (text, round(x), round(z))
        if key in seen:
            continue
        seen.add(key)
        lon, lat = frame.geographic(x, z)
        height = float(sample_dem(mosaic, lon, lat))
        labels.append(dict(name=text, label_position_xz=[x, z], longitude=float(lon), latitude=float(lat),
                           terrain_height_m=height if math.isfinite(height) else None,
                           terrain_world_y=float(frame.height(height)) if math.isfinite(height) else None,
                           code=props.get("vt_code"), source_tile=props["source_tile"],
                           caution="Cartographic label anchor; station entrances and mountain summits must use their actual geometry, not the label offset."))
    (out / "landmark_labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "geography.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = dict(status="GIS design data only; not installed into a world", feature_counts=counts,
                 source_elevation_range_m=[float(np.nanmin(mosaic[0])), float(np.nanmax(mosaic[0]))],
                 world_elevation_range_y=list(map(float, frame.height([np.nanmin(mosaic[0]), np.nanmax(mosaic[0])]))),
                 sea_level_world_y=float(frame.height(0)), landmark_label_count=len(labels))
    (out / "design.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["fetch", "build"])
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    (fetch if args.action == "fetch" else build)(config, args.out)


if __name__ == "__main__":
    main()
