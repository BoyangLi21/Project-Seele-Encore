"""Prepare georeferenced terrain and regional conflicts without changing a save.

The raster is a design input, not an edit permission mask. Existing structures,
entrances, actors and transport must be handled by the measured patch stage.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from hakone_geography import Frame, sample_dem


def lines(feature):
    geometry = feature["geometry"]
    if geometry["type"] == "LineString":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiLineString":
        return geometry["coordinates"]
    return []


def water_raster(features, bounds, spacing):
    x0, z0, x1, z1 = bounds
    shape = ((x1-x0)//spacing+1, (z1-z0)//spacing+1)
    # Separate layers ensure a hole in one buffered tile never erases a
    # neighbouring tile's valid water polygon.
    masks = {code: Image.new("1", shape) for code in (5100, 5200)}
    for feature in features:
        props, geometry = feature["properties"], feature["geometry"]
        code = props.get("vt_code")
        if props["source_layer"] != "WA" or code not in masks:
            continue
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        for polygon in polygons:
            if not polygon:
                continue
            outer = np.asarray(polygon[0], dtype=float)
            left = max(0, int(np.floor((outer[:, 0].min()-x0)/spacing)))
            top = max(0, int(np.floor((outer[:, 1].min()-z0)/spacing)))
            right = min(shape[0], int(np.ceil((outer[:, 0].max()-x0)/spacing))+1)
            bottom = min(shape[1], int(np.ceil((outer[:, 1].max()-z0)/spacing))+1)
            if right <= left or bottom <= top:
                continue
            local = Image.new("1", (right-left, bottom-top))
            draw = ImageDraw.Draw(local)
            for i, ring in enumerate(polygon):
                points = [((x-x0)/spacing-left, (z-z0)/spacing-top) for x, z in ring]
                if len(points) >= 3:
                    draw.polygon(points, fill=1 if i == 0 else 0)
            masks[code].paste(1, (left, top, right, bottom), local)
    return np.asarray(masks[5100], dtype=bool), np.asarray(masks[5200], dtype=bool)


def close_dem_gaps(elevation, sea, iterations=4):
    """Interpolate only short coastal/river gaps; unknown inland remains unknown."""
    values = elevation.copy()
    values[sea] = 0
    count = 0
    for _ in range(iterations):
        valid = np.isfinite(values)
        missing = ~valid
        if not missing.any():
            break
        padded = np.pad(np.where(valid, values, 0), 1)
        weights = np.pad(valid.astype(np.uint8), 1)
        total, number = np.zeros_like(values), np.zeros_like(values, dtype=np.uint8)
        for dz, dx in ((0,1), (1,0), (1,2), (2,1)):
            total += padded[dz:dz+values.shape[0], dx:dx+values.shape[1]]
            number += weights[dz:dz+values.shape[0], dx:dx+values.shape[1]]
        fill = missing & (number > 0)
        values[fill] = total[fill] / number[fill]
        count += int(fill.sum())
    return values, count


def station_geometry(features, frame, mosaic):
    station_lines = [np.asarray(line) for feature in features
                     if feature["properties"]["source_layer"] == "RailCL"
                     and feature["properties"].get("vt_sngldbl") == "駅部分"
                     for line in lines(feature)]
    rows = {}
    for feature in features:
        props, geometry = feature["properties"], feature["geometry"]
        if props["source_layer"] != "Anno" or props.get("vt_code") != 422:
            continue
        name = props.get("vt_text", "")
        points = np.asarray([geometry["coordinates"]] if geometry["type"] == "Point" else geometry["coordinates"])
        if points.ndim != 2:
            continue
        centre = points.mean(axis=0)
        candidates = [(float(np.linalg.norm(line-centre, axis=1).min()), line) for line in station_lines]
        if not candidates:
            continue
        distance, line = min(candidates, key=lambda item: item[0])
        if distance > 100:
            continue
        # A single nearest mapped station track is explicit: no fabricated
        # entrance, platform width or station building is inferred from it.
        point = (line.min(axis=0)+line.max(axis=0))/2
        lon, lat = frame.geographic(*point)
        altitude = float(sample_dem(mosaic, lon, lat))
        row = dict(name=name, track_centre_xz=point.tolist(), longitude=float(lon), latitude=float(lat),
                   terrain_world_y=float(frame.height(altitude)) if np.isfinite(altitude) else None,
                   label_distance_blocks=round(distance, 2), station_track=line.tolist(),
                   status="mapped station track; station building and entrance still require authoring")
        if name not in rows or distance < rows[name]["label_distance_blocks"]:
            rows[name] = row
    return list(rows.values())


def overview(out, config, features, elevations, sea, inland, axes, zones, stations):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import LightSource, LinearSegmentedColormap
    from matplotlib.patches import Rectangle, Patch
    from matplotlib.lines import Line2D

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    xs, zs = axes
    terrain = np.nan_to_num(elevations, nan=0)
    land_colours = LinearSegmentedColormap.from_list("hakone_land", ["#d8e0bb", "#a8bb8c", "#7c9e72", "#c6c29a", "#a7997c", "#eee6cf"])
    rgb = LightSource(azdeg=315, altdeg=45).shade(terrain, cmap=land_colours,
                                               vert_exag=.8, dx=8, dy=8, blend_mode="soft")
    rgb[sea, :3] = [.34, .59, .72]
    rgb[inland, :3] = [.32, .65, .78]
    fig, ax = plt.subplots(figsize=(15, 12), constrained_layout=True)
    ax.imshow(rgb, extent=[xs[0], xs[-1], zs[-1], zs[0]], origin="upper", zorder=0)
    groups = dict(road=[], rail=[])
    for feature in features:
        props = feature["properties"]
        if props["source_layer"] == "RailCL":
            groups["rail"].extend(lines(feature))
        elif props["source_layer"] == "RdCL" and props.get("vt_rdctg") in ("国道", "都道府県道", "高速自動車国道等"):
            groups["road"].extend(lines(feature))
    for key, color, width in (("road", "#f1d28b", .65), ("rail", "#34394b", .7)):
        ax.add_collection(LineCollection(groups[key], colors=color, linewidths=width, zorder=3))
    for row in zones:
        x0, x1, z0, z1 = row["bounds"]
        ax.add_patch(Rectangle((x0,z0),x1-x0,z1-z0,fill=False,ec="#a83e50",lw=1,ls="--",zorder=4))
    x0,z0,x1,z1 = config["retained_city_box_xz"]
    ax.add_patch(Rectangle((x0,z0),x1-x0,z1-z0,fc="#d99926",alpha=.28,ec="#8a4d00",lw=1.5,zorder=5))
    cross_file=out/"city-cross-relocation.json"
    if cross_file.exists():
        for x0,z0,x1,z1 in json.loads(cross_file.read_text("utf8"))["cross_rectangles_xz"]:
            ax.add_patch(Rectangle((x0,z0),x1-x0,z1-z0,fill=False,ec="#5a388e",lw=1.3,zorder=6))
    un_file=out/"un-odawara-relocation.json"
    if un_file.exists():
        x0,_,z0,x1,_,z1=json.loads(un_file.read_text("utf8"))["target_bounds"]
        ax.add_patch(Rectangle((x0,z0),x1-x0,z1-z0,fill=False,ec="#4863a0",lw=1.5,zorder=6))
        ax.text((x0+x1)/2,z0-45,"UN 基地选址",ha="center",fontsize=10,color="#263b71",zorder=7)
    labels = [(30, 220, "保留升降城区\n仙石原盆地"), (-50,-440,"金时山"), (320,1130,"神山"),
              (420,1370,"驹岳"), (-105,1767,"芦之湖"), (3250,1080,"小田原海港"), (3740,2100,"相模湾")]
    requested = {"箱根湯本駅":"箱根汤本", "強羅駅":"强罗", "桃源台駅":"桃源台", "小田原駅":"小田原"}
    for row in stations:
        if row["name"] in requested:
            x,z=row["track_centre_xz"]; labels.append((x,z,requested[row["name"]]))
            ax.scatter([x],[z],s=16,c="#222e46",zorder=7)
    for x,z,label in labels:
        ax.annotate(label,(x,z),xytext=(8,8),textcoords="offset points",fontsize=10,color="#172b33",zorder=8,
                    bbox=dict(boxstyle="round,pad=.22",fc="white",ec="none",alpha=.85))
    ax.set_xlim(xs[0],xs[-1]);ax.set_ylim(zs[-1],zs[0]);ax.set_aspect("equal")
    ax.set_xlabel("游戏 X / 向东");ax.set_ylabel("游戏 Z / 向南")
    ax.set_title("箱根真实地理底图与旧地图布局叠加\n统一地理比例 1:4；设计图，尚未写入存档",loc="left",fontsize=18,pad=14)
    ax.legend(handles=[Patch(facecolor="#d99926",alpha=.5,label="保留升降核心"),
                       Line2D([],[],color="#a83e50",ls="--",label="旧城区／机场边界：需重构"),
                       Line2D([],[],color="#f1d28b",lw=3,label="现实主干公路"),
                       Line2D([],[],color="#34394b",label="现实铁路／索道")],loc="lower left",framealpha=.95,fontsize=10)
    ax.text(.985,.985,"北 ↑",transform=ax.transAxes,ha="right",va="top",fontsize=14)
    fig.text(.012,.006,"来源：国土地理院 DEM、最适化矢量瓦片（传统端点 2023-10）；Project SEELE 加工。旧边界来自当前存档区域目录。",fontsize=9)
    fig.savefig(out / "geography-overview.png",dpi=150)
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,required=True)
    parser.add_argument("--regional-plan",type=Path,required=True)
    parser.add_argument("--spacing",type=int,default=2)
    args=parser.parse_args();out=args.data
    if args.spacing < 1:
        parser.error("spacing must be positive")
    config=json.loads((out/"geography.json").read_text("utf8"));frame=Frame(config)
    d=np.load(out/"dem.npz");mosaic=(d["elevation_m"],*d["tile_origin"],int(d["zoom"]))
    features=json.load(gzip.open(out/"features.world.geojson.gz","rt",encoding="utf8"))["features"]
    west,south,east,north=config["geographic_bounds_wsen"]
    x0,z0=frame.world(west,north);x1,z1=frame.world(east,south)
    spacing=args.spacing
    x0,z0=np.ceil(np.array([x0,z0])/spacing).astype(int)*spacing
    x1,z1=np.floor(np.array([x1,z1])/spacing).astype(int)*spacing
    xs=np.arange(x0,x1+1,spacing);zs=np.arange(z0,z1+1,spacing)
    xx,zz=np.meshgrid(xs,zs);lon,lat=frame.geographic(xx,zz)
    elevation=sample_dem(mosaic,lon,lat).astype(np.float32)
    sea,inland=water_raster(features,[x0,z0,x1,z1],spacing)
    elevation,filled=close_dem_gaps(elevation,sea)
    height=frame.height(elevation).astype(np.float32)
    city=config["retained_city_box_xz"]
    platforms=[city]
    cross_file=out/"city-cross-relocation.json"
    if cross_file.exists():
        platforms=json.loads(cross_file.read_text("utf8"))["cross_rectangles_xz"]
    distance=np.full(xx.shape,np.inf,dtype=np.float32)
    for city in platforms:
        current=np.hypot(np.maximum.reduce([city[0]-xx,np.zeros_like(xx),xx-city[2]]),
                         np.maximum.reduce([city[1]-zz,np.zeros_like(zz),zz-city[3]]))
        distance=np.minimum(distance,current)
    blend=np.clip(distance/config["city_blend_blocks"],0,1);blend=blend*blend*(3-2*blend)
    height=height*blend+config["retained_city_surface_y"]*(1-blend)
    np.savez_compressed(out/"terrain-design.npz",x=xs,z=zs,elevation_m=elevation,height_y=height,
                        sea=sea,inland_water=inland,city_platform=distance==0)
    stations=station_geometry(features,frame,mosaic)
    (out/"stations.json").write_text(json.dumps(stations,ensure_ascii=False,indent=2),encoding="utf8")
    plan=json.loads(args.regional_plan.read_text("utf8"))
    zones=[]
    for row in plan["zones"]:
        if row.get("floor",-999)<0:
            continue
        x0,x1,z0,z1=row["bounds"];sx=np.linspace(x0,x1,17);sz=np.linspace(z0,z1,17)
        px,pz=np.meshgrid(sx,sz);lon,lat=frame.geographic(px,pz)
        target=frame.height(sample_dem(mosaic,lon,lat))
        zones.append(dict(id=row["id"],bounds=row["bounds"],current_floor=row["floor"],
                          target_y_range=[round(float(np.nanmin(target)),1),round(float(np.nanmax(target)),1)],
                          median_height_change=round(float(np.nanmedian(target)-row["floor"]),1),
                          status="requires regional redesign; this table does not authorize erasing structures"))
    report=dict(status="design only; no world changes",raster_shape=list(height.shape),spacing=spacing,
                source_missing_after_coastal_interpolation=int((~np.isfinite(elevation)).sum()),
                short_gap_samples_interpolated=filled,sea_samples=int(sea.sum()),inland_water_samples=int(inland.sum()),
                planned_city_platform_samples=int((distance==0).sum()),stations=len(stations),zones=zones)
    (out/"regional-conflicts.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    overview(out,config,features,elevation,sea,inland,(xs,zs),zones,stations)
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
