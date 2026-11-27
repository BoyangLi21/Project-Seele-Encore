"""Bake the R64 GeoFront grass disc and facility floor plans from installed Anvil chunks.

PNG assets and travel/occupancy data are private build products. Run on a cold
world, outside the checkout. All images are north-up, +X right and +Z down.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
import gzip
import json
from multiprocessing import Pool
from pathlib import Path
import math

import numpy as np
from PIL import Image
from scipy import ndimage

from inspect_map_assets import region_chunks

DIM = "projectseele:geofront"
ASSETS = Path("assets/projectseele/area_maps")
# Bounds are half-open and include a margin outside the measured grass rim.
CAVERN = (-1888, -1600, 1952, 2240)
BACKGROUND = (21, 31, 36)
NO_Y = -32768
AIR = 0
ROCK = 1
COLOURS = [BACKGROUND, (75, 78, 82), (113, 150, 85), (67, 114, 75),
           (50, 103, 137), (129, 110, 79), (158, 157, 145), (108, 119, 128),
           (60, 69, 80), (182, 183, 176), (52, 79, 82), (78, 135, 144),
           (182, 116, 55), (149, 70, 65), (219, 199, 133), (88, 110, 135),
           (158, 97, 142), (230, 154, 79), (164, 110, 86), (178, 194, 193),
           (211, 168, 86), (87, 74, 67), (203, 228, 185), (72, 53, 54)]
COLOURS = np.array(COLOURS, dtype=np.uint8)
PLANTS = ("flower", "sapling", "tulip", "fern", "vines", "lily", "carpet", "azalea",
          "dandelion", "poppy", "orchid", "allium", "cornflower", "mushroom",
          "torch", "button", "tripwire", "seagrass", "potted", "seeds")


@lru_cache(maxsize=None)
def material(name):
    """Group actual block ids into a stable cartographic palette."""
    ns, key = name.split(":", 1)
    if key in ("air", "void_air", "cave_air", "light", "barrier", "structure_void"):
        return AIR
    if key in ("stone", "deepslate", "bedrock", "tuff", "calcite") or key.endswith("_ore"):
        return ROCK
    if key in ("grass_block", "moss_block", "podzol", "grass", "tall_grass"):
        return 2
    if key.endswith(("_leaves", "_log")):
        return 3
    if key in ("water", "bubble_column", "ice"):
        return 4
    if key in ("dirt", "gravel", "coarse_dirt", "rooted_dirt", "mud", "sand"):
        return 5
    if "lcl" in key or "lava" in key:
        return 17
    if "door" in key or "gate" in key or "turnstile" in key:
        return 20
    if "rail" in key or "track" in key:
        return 10
    if "light" in key and "light_gray" not in key and "light_blue" not in key or key in ("sea_lantern", "glowstone") or key.endswith("froglight"):
        return 22
    if "pyramid_panel" in key or "black_concrete" in key or "blackstone" in key or "deep" in key:
        return 8
    if any(p in key for p in PLANTS):
        return AIR
    if "glass" in key:
        return 19
    for token, col in (("orange",12), ("red",13), ("marking",13), ("yellow",14), ("blue",15),
                       ("cyan",11), ("magenta",16), ("purple",16), ("pink",16),
                       ("white",9), ("quartz",9), ("tactile",14), ("green",3),
                       ("copper",18), ("brick",18), ("wood",5), ("plank",5)):
        if token in key:
            return col
    if any(p in key for p in ("floor","platform","escalator","andesite","smooth_stone","polished","stair","slab","iron")):
        return 6
    return 7


def chunk_volume(chunk, y0, y1, step):
    size = 16 // step
    volume = np.zeros((y1-y0, size, size), np.uint8)
    for section in chunk.get("sections", ()):
        base = int(section["Y"]) * 16
        start, stop = max(base, y0), min(base+16, y1)
        if start >= stop:
            continue
        states = section.get("block_states", {})
        palette = states.get("palette", ())
        target = volume[start-y0:stop-y0]
        if not palette:
            continue
        codes = np.array([material(str(p["Name"])) for p in palette], np.uint8)
        if len(codes) == 1:
            target[:] = codes[0]
            continue
        bits = max(4, (len(palette)-1).bit_length())
        per = 64 // bits
        words = np.asarray(states["data"], dtype=">i8").astype(np.uint64)
        at = sample_offsets(step)[start-base:stop-base]
        ids = (words[at//per] >> ((at%per)*bits).astype(np.uint64)) & ((1<<bits)-1)
        target[:] = codes[ids]
    return volume


@lru_cache(maxsize=8)
def sample_offsets(step):
    return np.arange(4096, dtype=np.int32).reshape(16,16,16)[:,step//2::step,step//2::step]


def put_height(path, heights):
    packed = (heights.astype(np.int32) + 32768).astype(np.uint16)
    rgba = np.zeros((*packed.shape, 3), np.uint8)
    rgba[:,:,0] = packed >> 8
    rgba[:,:,1] = packed & 255
    Image.fromarray(rgba).save(path)


def cavern_projection(volume):
    y0 = -512
    air = volume == AIR
    # A long free span separates the disc from enclosed foundations and rock.
    # Locate it in the floor band before considering vegetation and buildings.
    clear = air[:175] & air[2:177] & air[5:180] & air[9:184]
    clear[:12] = False
    first = np.argmax(clear, axis=0)
    valid = clear.any(axis=0)
    yy = np.arange(len(volume))[:,None,None]
    # The native liner is generally three blocks thick under solid rock.
    solid = volume == ROCK
    cap = solid[:-5] & solid[2:-3] & solid[5:] & (yy[:-5] > first + 5)
    ceiling = np.where(cap.any(axis=0), np.argmax(cap,axis=0)-3, len(volume)-1)
    # Slice below suspended city blocks while retaining trees, the pyramid skin
    # and other structures rising from the floor. Hide the dome liner itself.
    pick = (~air[:164]) & (yy[:164]<ceiling-3)
    h = np.max(np.where(pick, yy[:164], -1),axis=0)
    valid &= (h >= 0)
    z,x = np.indices(h.shape)
    top = volume[np.maximum(h,0),z,x]
    # The first open span can sit above a tree. Find the surface underneath
    # its canopy so a player walking below the branches stays in the cavern
    # and so the floor map follows the land instead of every treetop.
    land_pick = pick & (volume[:164] != 3)
    land = np.max(np.where(land_pick, yy[:164], -1),axis=0)
    land = np.where((land < 0) | (top != 3), h, land)
    land_id = volume[np.maximum(land,0),z,x]
    ground = np.minimum(np.maximum(0, first-1), np.maximum(0, land))
    # Levels below the disc have independently baked HQ/hangar/terminal plans.
    return np.stack((np.where(valid,top,0), np.where(valid,h+y0,NO_Y),
                     np.where(valid,ground+y0-9,NO_Y),np.where(valid,ceiling+y0,NO_Y),
                     np.where(valid,land_id,0),np.where(valid,land+y0,NO_Y))).astype(np.int16)


def cavern_region(job):
    world, work, rx, rz = job
    out = work / f"ground.{rx}.{rz}.npz"
    if out.exists():
        return out
    path = world / "dimensions/projectseele/geofront/region" / f"r.{rx}.{rz}.mca"
    tile = np.full((6,256,256), NO_Y,np.int16)
    tile[0] = tile[4] = 0
    chunks = 0
    if path.exists():
        bounds = (CAVERN[0]//16, (CAVERN[2]-1)//16, CAVERN[1]//16,(CAVERN[3]-1)//16)
        errors = []
        for cx, cz, chunk in region_chunks(path,bounds,diagnostics=errors):
            if str(chunk.get("Status","")).removeprefix("minecraft:") != "full":
                continue
            tile[:,(cz%32)*8:(cz%32+1)*8,(cx%32)*8:(cx%32+1)*8] = cavern_projection(chunk_volume(chunk,-512,81,2))
            chunks += 1
        if errors:
            raise ValueError(errors[:3])
    np.savez_compressed(out, tile=tile, chunks=chunks)
    return out


def shade(ids, heights, step):
    h = np.where(heights == NO_Y, -476, heights).astype(np.float32)
    dx = (h - np.roll(h,1,axis=1)) / step
    dz = (h - np.roll(h,1,axis=0)) / step
    gain = 1 + np.clip((dx + dz) * .043, -.20, .20)
    rgb = (COLOURS[ids] * gain[:,:,None]).clip(0,255).astype(np.uint8)
    rgb[ids == 0] = BACKGROUND
    return rgb


def layer(id_, label, bounds, y0, y1, priority, **extra):
    x0,z0,x1,z1 = bounds
    return dict(id=id_,label=label,minX=x0,minZ=z0,maxX=x1,maxZ=z1,minY=int(y0),maxY=int(y1),
                priority=priority,texture=f"projectseele:area_maps/{id_}.png",**extra)

def cavern_floor_map(materials, ground):
    """Shaded ground, water and facility roofs from the measured cavern survey."""
    valid = materials != 0
    nearby = ndimage.distance_transform_edt(~valid, return_distances=False, return_indices=True)
    h = ground[tuple(nearby)].astype(np.float32)
    rolling = ndimage.gaussian_filter(h, 5)
    dz, dx = np.gradient(rolling / 2)
    # Show broad, shallow floor relief at overview scale. Retain crisp actual
    # water and building outlines and use the soil beneath surveyed trees.
    light = np.clip(1 - .90 * dx - .68 * dz, .70, 1.22)
    natural = (materials == 2) | (materials == 5)
    tones = COLOURS[materials].astype(np.float32)
    tones[natural] += np.clip((rolling[natural]+477)*.74, -15, 34)[:,None]
    rgb = np.clip(tones * np.where(natural, light, 1)[:,:,None], 0, 255).astype(np.uint8)
    detail = shade(materials,ground,2)
    rgb[~natural] = detail[~natural]
    return rgb


def bake_cavern(world, out, workers):
    work = out / "parts"
    work.mkdir(exist_ok=True)
    x0,z0,x1,z1 = CAVERN
    jobs = [(world,work,rx,rz) for rx in range(x0//512,(x1-1)//512+1) for rz in range(z0//512,(z1-1)//512+1)]
    data = np.full((6,(z1-z0)//2,(x1-x0)//2),NO_Y,np.int16)
    data[0] = data[4] = 0
    chunks=0
    with Pool(workers) as pool:
        for i,path in enumerate(pool.imap_unordered(cavern_region,jobs),1):
            _,rx,rz = path.stem.split(".")
            bx,bz=int(rx)*512,int(rz)*512
            xx,zz=max(x0,bx),max(z0,bz)
            ex,ez=min(x1,bx+512),min(z1,bz+512)
            with np.load(path) as a:
                data[:,(zz-z0)//2:(ez-z0)//2,(xx-x0)//2:(ex-x0)//2]=a["tile"][:,(zz-bz)//2:(ez-bz)//2,(xx-bx)//2:(ex-bx)//2]
                chunks+=int(a["chunks"])
            if i % 8 == 0:
                print(f"GeoFront regions {i}/{len(jobs)}",flush=True)
    ids,heights,bottom,ceil,land_id,land=data
    # The GeoFront is the connected main cavern; unrelated caves outside the
    # real grass rim cannot activate this layer.
    labels,count=ndimage.label(ndimage.binary_closing(ids>0,iterations=2))
    centre = labels[(327-z0)//2,(30-x0)//2]
    if not centre:
        centre = np.bincount(labels.ravel())[1:].argmax()+1
    valid = (labels==centre) & (ids!=0)
    ids[~valid]=land_id[~valid]=0
    heights[~valid]=bottom[~valid]=ceil[~valid]=land[~valid]=NO_Y
    a = out / ASSETS
    Image.fromarray(cavern_floor_map(land_id,land)).save(a/"geofront.png")
    put_height(a/"geofront_bottom.png",bottom)
    put_height(a/"geofront_ceiling.png",ceil)
    put_height(a/"geofront_ground.png",np.where(valid,land+1,NO_Y))
    record = layer("geofront","地下草原",CAVERN,int(bottom[valid].min()),int(ceil[valid].max())+1,10,
                   ground="projectseele:area_maps/geofront_ground.png",bottom="projectseele:area_maps/geofront_bottom.png",ceiling="projectseele:area_maps/geofront_ceiling.png",
                   # R65 owner: Xaero draws the cavern itself (its baked cave map); only here may it switch to cave mode.
                   display="native",caves=True)
    z,x=np.where(valid)
    report = dict(complete_chunks=chunks,valid_texels=int(valid.sum()),resolution=2,
                  observedXZ=[int(x0+x.min()*2),int(z0+z.min()*2),int(x0+x.max()*2+2),int(z0+z.max()*2+2)],
                  grass=int((ids==2).sum()),trees=int((ids==3).sum()),water=int((ids==4).sum()),
                  surfaceY=[int(heights[valid].min()),int(np.median(heights[valid])),int(heights[valid].max())])
    (out/"geofront.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),"utf8")
    (out/"geofront-check.json").write_text(json.dumps(report,indent=2),"utf8")


@dataclass(frozen=True)
class Floor:
    id: str
    label: str
    feet: int


@dataclass(frozen=True)
class Facility:
    key: str
    bounds: tuple
    interval: tuple
    floors: tuple
    scope: str


def catalogue(world):
    def floor(id_, label, y):
        return Floor(id_, label, y)
    pyramid = [
        ("station","总部车站 · 站台",-559), ("b1","总部 B1 · 交通接驳层",-554),
        ("lobby","总部 1F · 总部门厅",-541), ("transit","总部 · 地下交通层",-535),
        ("service","总部 2F · 医疗与勤务层",-527), ("command_doors","指挥中心 · 下层通廊",-522),
        ("command_deck","指挥中心 · 主指挥台",-516), ("research","总部 3F · 科研联络层",-513),
        ("command_gallery","指挥中心 · 观察廊",-502), ("operations","总部 4F · 作战指挥室",-499),
        ("upper_command","总部 5F · 指挥室上层",-485), ("liaison","总部 · 总指挥联络厅",-481),
        ("upper_office","总部 6F · 上部办公层",-471), ("seele","总部 7F · SEELE 会议室",-457),
        ("office","总部 · 司令办公室",-434), ("top","总部 · 顶层",-422)]
    hangar = [("lower","机库 · 底层检修通道",-1088), ("bay","机库 · 机体停放层",-1062),
              ("launch","机库 · 发射区检修廊",-1030), ("boarding","机库 · 登机平台",-1014),
              ("observation","机库 · 上层观察廊",-987)]
    experimental = [("sync","原实验区 · LCL 同步实验层",-468),("station","原实验区 · 车站与接驳",-442)]
    def numbered(prefix,values):
        return tuple(floor(f"{prefix}_{tag}",label,feet) for tag,label,feet in values)
    facilities = [
        Facility("pyramid",(-112,176,177,559),(-566,-406),numbered("pyramid",pyramid),"hq"),
        Facility("hangar",(-76,-16,120,407),(-1110,-967),numbered("hangar",hangar),"deep"),
        Facility("terminal",(-64,219,110,414),(-1280,-1193),(
            floor("terminal_lake","终极教条 · LCL 湖",-1264),floor("terminal_gate","终极教条 · 天堂之门",-1230)),"deep"),
        Facility("experimental",(-58,-307,216,140),(-487,-426),numbered("experimental",experimental),"experimental"),
        Facility("airport",(-540,-361,-334,-177),(-485,-461),
                 (floor("airport_underground","地下运输机场 · 停机坪",-475),),"apron"),
        Facility("spiral",(-763,861,-477,1007),(-478,-456),
                 (floor("spiral_station","GS 螺旋线 · GeoFront 港口站",-467),),"station"),
    ]
    # UN surface ground can be below world zero. Each hangar selector follows
    # its actual building footprint instead of capturing the surrounding base.
    hangars=json.loads((world/"un_hangars_r31.json").read_text("utf8"))["hangars"]
    lo=[min(h["bounds"][0][i] for h in hangars) for i in range(3)]
    hi=[max(h["bounds"][1][i] for h in hangars) for i in range(3)]
    bounds=(lo[0]-4,lo[2]-4,hi[0]+5,hi[2]+5)
    facilities.append(Facility("un",bounds,(lo[1],hi[1]+1),
                      (floor("un_hangars","联合国试验机库 · 人员层",-67),),"un"))
    return facilities


def read_facility(world, facility):
    x0,z0,x1,z1=facility.bounds
    y0=facility.interval[0]-12
    if facility.key=="terminal":
        y0=min(y0,facility.floors[0].feet-64)
    y1=facility.interval[1]+12
    blocks=np.full((y1-y0,z1-z0,x1-x0),ROCK,np.uint8)
    # Use real block names for the thin sloping pyramid shell. This height
    # prevents standing on the roof/grass from selecting an indoor floor.
    shell=np.full((z1-z0,x1-x0),NO_Y,np.int16)
    seen=set()
    cb=(x0//16,(x1-1)//16,z0//16,(z1-1)//16)
    for rx in range(cb[0]//32,cb[1]//32+1):
        for rz in range(cb[2]//32,cb[3]//32+1):
            path=world/"dimensions/projectseele/geofront/region"/f"r.{rx}.{rz}.mca"
            errors=[]
            for cx,cz,chunk in region_chunks(path,cb,diagnostics=errors):
                if str(chunk.get("Status","")).removeprefix("minecraft:")!="full":
                    continue
                seen.add((cx,cz))
                startX,startZ=max(x0,cx*16),max(z0,cz*16)
                endX,endZ=min(x1,cx*16+16),min(z1,cz*16+16)
                dest=(slice(startZ-z0,endZ-z0),slice(startX-x0,endX-x0))
                src=(slice(startZ-cz*16,endZ-cz*16),slice(startX-cx*16,endX-cx*16))
                blocks[(slice(None),*dest)]=chunk_volume(chunk,y0,y1,1)[(slice(None),*src)]
                if facility.scope=="hq":
                    height=np.full((16,16),NO_Y,np.int16)
                    for sec in chunk["sections"]:
                        sy=int(sec["Y"])*16
                        if sy+16<=y0 or sy>=-378:
                            continue
                        s=sec.get("block_states",{})
                        names=[str(v["Name"]) for v in s.get("palette",())]
                        take=np.array(["pyramid_" in n or n=="projectseele:one_way_glass" for n in names])
                        if not take.any():
                            continue
                        if len(names)==1:
                            height=np.maximum(height,sy+15)
                        else:
                            bits=max(4,(len(names)-1).bit_length())
                            idx=sample_offsets(1)
                            words=np.asarray(s["data"],dtype=">i8").astype(np.uint64)
                            ids=(words[idx//(64//bits)]>>((idx%(64//bits))*bits).astype(np.uint64))&((1<<bits)-1)
                            h=np.max(np.where(take[ids],np.arange(sy,sy+16)[:,None,None],NO_Y),axis=0)
                            height=np.maximum(height,h)
                    shell[dest]=height[src]
            if errors:
                raise ValueError(errors[:3])
    expected=(cb[1]-cb[0]+1)*(cb[3]-cb[2]+1)
    if len(seen)!=expected:
        raise ValueError(f"{facility.key}: {len(seen)} of {expected} full chunks")
    return blocks,y0,shell


def feet_interval(facility,i):
    floors=facility.floors
    y=floors[i].feet
    low=(floors[i-1].feet+y+1)//2 if i else facility.interval[0]
    high=(floors[i+1].feet+y+1)//2 if i+1<len(floors) else facility.interval[1]
    return low,high


def support_map(volume,feet):
    valid=lambda y: (volume[y]!=AIR)&(volume[y+1]==AIR)&(volume[y+2]==AIR)
    heights=np.full(volume.shape[1:],-1,np.int16)
    # Prefer the exact floor plane, then stair treads and furniture nearby.
    for offset in (-7,5,-6,4,-5,3,-4,2,-3,1,-2,0,-1):
        y=feet+offset
        if 0<=y and y+2<len(volume):
            heights[valid(y)]=y
    return heights


def data_mask(cols):
    rgba=np.zeros((*cols.shape,4),np.uint8)
    rgba[:,:,0:3]=255
    rgba[:,:,3]=cols.astype(np.uint8)*255
    return Image.fromarray(rgba)


def preview(path):
    target=path.with_stem(path.stem+"_preview")
    with Image.open(path) as im:
        im.thumbnail((384,384),Image.Resampling.LANCZOS)
        im.save(target)
    return "projectseele:area_maps/"+target.name


def render_floor(out, facility, floor, band, blocks, y0, shell, points, landings, doors, un_zones, mechanical):
    x0,z0,x1,z1=facility.bounds
    a=out/ASSETS
    fy=floor.feet-y0
    support=support_map(blocks,fy)
    zz,xx=np.indices(support.shape)
    floor_ids=blocks[np.maximum(support,0),zz,xx]
    air=(blocks[fy+1]==AIR) | (blocks[fy+1]==20)
    near=(support>=0) & (floor_ids!=ROCK) & air
    built=near & ~np.isin(floor_ids,[2,3,4,5])
    graph=np.zeros_like(near)
    matches=points[(points[:,1]>=band[0]) & (points[:,1]<band[1])]
    inside=matches[(matches[:,0]>=x0)&(matches[:,0]<x1)&(matches[:,2]>=z0)&(matches[:,2]<z1)]
    graph[inside[:,2]-z0,inside[:,0]-x0]=True
    # Only verified floor nodes become anchors; stale route metadata cannot
    # turn an empty or refilled room into a selectable map.
    graph &= ndimage.maximum_filter(near,size=3)
    walk=near.copy()
    if facility.scope=="hq":
        # An enclosed room, a current graph node, or the inside of the
        # pyramid skin can anchor a floor. Exterior grass never qualifies.
        ceiling=(blocks[fy+3:min(len(blocks),fy+19)]!=AIR).any(axis=0)
        under_skin=shell>floor.feet+1
        walk=built & (ceiling | under_skin | graph)
        label,count=ndimage.label(walk,np.ones((3,3)))
        # Include enclosed rooms missed by staff routing and isolate the
        # station from detached machinery at the same elevation.
        size=np.bincount(label.ravel())
        good=(size>=20)
        good[0]=False
        walk=good[label]|graph
        if floor.id=="pyramid_station":
            walk&=zz+z0>=426
        if floor.feet>=-481:
            walk &= under_skin | ndimage.maximum_filter(graph,size=5)
    elif facility.scope=="deep":
        walk=built | graph
    elif facility.scope=="un":
        inside_hangar=np.zeros_like(walk)
        for lo,hi in un_zones:
            inside_hangar[(zz+z0>=lo[2])&(zz+z0<=hi[2])&(xx+x0>=lo[0])&(xx+x0<=hi[0])]=True
        walk=(built | graph) & inside_hangar
    else:
        walk=built | graph
    seeds=ndimage.binary_closing(ndimage.binary_dilation(walk,iterations=2),iterations=3)
    labels,n=ndimage.label(seeds)
    areas=np.bincount(labels.ravel())
    keep=(areas>=25);keep[0]=False
    scope=ndimage.binary_fill_holes(keep[labels])
    if facility.scope=="deep":
        # Open EVA bays and the LCL lake remain part of their enclosing halls
        # even where no pedestrian can stand at this exact elevation.
        for dy in range(max(0,fy-40),min(len(blocks),fy+2)):
            wet=(blocks[dy]==17)
            if wet.any():
                scope|=wet
        shell_air=blocks[fy+1]!=ROCK
        scope|=shell_air & ndimage.binary_fill_holes(ndimage.binary_closing(scope,iterations=4))
    # Resolve holes at lift shafts from installed cabin/controller anchors.
    for x,y,z in landings:
        if band[0]<=y<band[1] and x0+4<=x<x1-4 and z0+4<=z<z1-4:
            scope[z-z0-3:z-z0+4,x-x0-3:x-x0+4]=True
    sel=scope.copy()
    if facility.scope=="hq" and floor.feet>=-481:
        sel&=(shell>band[0]) | ndimage.maximum_filter(graph,size=5)
    # Surround the structure with one wall of dark linework. The slice is
    # sampled at head height for doors, walls, dividing glass, rail and columns.
    show=ndimage.binary_dilation(scope,iterations=2)
    pic=np.full((*scope.shape,3),BACKGROUND,np.uint8)
    # Depressed open areas: show actual lower deck / LCL, fading with depth.
    lower=blocks[max(0,fy-54):max(1,fy-4)]
    if len(lower):
        has=lower!=AIR
        idx=(len(lower)-1)-np.argmax(has[::-1],axis=0)
        low_ids=lower[idx,zz,xx]
        low_vis=scope & (~near) & has.any(axis=0) & (low_ids!=ROCK)
        pic[low_vis]=(COLOURS[low_ids[low_vis]]*.56).astype(np.uint8)
    # Open floor colours remain distinct from structural fill, even for
    # opposing decks which use identical grey construction materials.
    pic[show & built]=COLOURS[floor_ids[show & built]]
    wall=show & ~air & (blocks[fy+1]!=ROCK)
    wall_colour=((COLOURS[blocks[fy+1]].astype(np.float32)*.43)+[15,18,19]).clip(0,255).astype(np.uint8)
    pic[wall]=wall_colour[wall]
    if floor.id=="terminal_lake":
        # The pool surface remains level. Its measured contiguous fluid depth distinguishes
        # the shallow sill, the sloped basin and the channels cut into the lake floor.
        liquid=(blocks[:fy][::-1]==17)
        depth=np.logical_and.accumulate(liquid,axis=0).sum(axis=0)
        covered=scope & air & (depth>0)
        shade=np.clip(1.08-depth[covered]/80,.48,1.0)
        pic[covered]=(COLOURS[17]*shade[:,None]).astype(np.uint8)
    divider=wall & ndimage.binary_dilation(walk) & np.isin(blocks[fy+1],[10,19,20])
    pic[divider]=COLOURS[blocks[fy+1][divider]]
    native_doors=(blocks[fy]==20)|(blocks[fy+1]==20)
    pic[show & native_doors]=COLOURS[20]
    for x,y,z in doors:
        if band[0]<=y<band[1] and x0<=x<x1 and z0<=z<z1:
            if show[z-z0,x-x0]:
                pic[z-z0,x-x0]=COLOURS[20]
    for x,y,z in landings:
        if band[0]<=y<band[1] and x0+2<=x<x1-2 and z0+2<=z<z1-2:
            i,j=z-z0,x-x0
            pic[i-2:i+3,j-2:j+3]=(67,179,175)
            pic[i-1:i+2,j-1:j+2]=(32,66,73)
    gate_cells=0
    if facility.key=="hangar":
        for gate in mechanical:
            if gate["kind"]!="HANGAR":
                continue
            x,y,z=gate["frame"]["position"]
            if not y<=floor.feet<y+gate["height"]:
                continue
            # The door frame maps its local leaf-width axis into the world.
            qx,qy,qz,qw=gate["frame"]["quaternion"]
            ux,uz=1-2*(qy*qy+qz*qz),2*(qx*qz-qw*qy)
            half=(gate["width"]-1)/2
            for offset in np.arange(-half,half+1):
                ix,iz=math.floor(x+ux*offset)-x0,math.floor(z+uz*offset)-z0
                if 0<=ix<x1-x0 and 0<=iz<z1-z0:
                    pic[iz,ix]=COLOURS[20]
                    show[iz,ix]=True
                    gate_cells+=1
    if not sel.any():
        raise ValueError("Empty footprint for "+floor.id)
    if floor.id=="spiral_station":
        # The western side is the open port at lake level. Draw its two piers, decks
        # and office from their top blocks; the platform retains its interior floor plan.
        west=xx+x0 < -606
        zone=west & (xx+x0 >= -747) & (zz+z0 >= 910) & (zz+z0 <= 997)
        band_blocks=blocks[max(0,fy-12):min(len(blocks),fy+9)]
        solid=band_blocks!=AIR
        surface_y=len(band_blocks)-1-np.argmax(solid[::-1],axis=0)
        top=band_blocks[surface_y,zz,xx]
        surveyed=solid.any(axis=0)
        visible=surveyed & (~show | west)
        pic[visible]=COLOURS[top[visible]]
        pic[visible & (top==4)]=[53,94,166]
        show|=surveyed
        water_below=band_blocks[np.maximum(surface_y-2,0),zz,xx]==4
        piers=(top==5) & ndimage.maximum_filter(water_below,size=3)
        sel|=zone & surveyed & (piers | ~np.isin(top,[ROCK,2,3,4,5]))
    zs,xs=np.where(show)
    az,bz=max(0,int(zs.min())-5),min(z1-z0,int(zs.max())+6)
    ax,bx=max(0,int(xs.min())-5),min(x1-x0,int(xs.max())+6)
    crop=np.s_[az:bz,ax:bx]
    path=a/(floor.id+".png")
    Image.fromarray(pic[crop]).save(path)
    mask=a/(floor.id+"_mask.png")
    data_mask(sel[crop]).save(mask)
    opts=dict(floorY=floor.feet,mask="projectseele:area_maps/"+mask.name,preview=preview(path))
    if facility.scope=="hq" and floor.feet>=-481:
        top=np.where(shell!=NO_Y,shell,band[1]).astype(np.int16)
        # Actual staff anchors below an open terrace/deck remain selectable.
        topo=np.where(graph & (top<floor.feet+2),np.maximum(top,floor.feet+3),top)
        cap=a/(floor.id+"_ceiling.png")
        put_height(cap,topo[crop]);opts["ceiling"]="projectseele:area_maps/"+cap.name
    bounds=(x0+ax,z0+az,x0+bx,z0+bz)
    entry=layer(floor.id,floor.label,bounds,*band,35 if facility.scope=="hq" else 40,**opts)
    stats=dict(feet=floor.feet,footprint=int(sel.sum()),native_walk_pixels=int((walk & scope).sum()),routing_anchors=int(graph.sum()),
               commissioned_gate_cells=gate_cells,structures=int(wall.sum()),door_blocks=int((show & native_doors).sum()),bounds=bounds)
    return entry,stats


def bake_facilities(world,out):
    walking=json.loads(gzip.decompress((world/"r53_personnel_walking_graph.json.gz").read_bytes()))
    points=np.array(walking["nodes"],np.int32)
    lifts=json.loads((world/"personnel_lifts_r52.json").read_text("utf8"))
    landings=[f["cabin"] for lift in lifts["lifts"] for f in lift["floors"]]
    gates=json.loads((world/"r52/headquarters_command_doors.json").read_text("utf8"))
    doors=[pos for d in gates["doors"] for pos in d["aperture"]]
    un=json.loads((world/"un_hangars_r31.json").read_text("utf8"))
    un_zones=[h["bounds"] for h in un["hangars"]]
    mechanical=json.loads((world/"ROOT_MECHANICAL_OWNER.json").read_text("utf8"))["gates"]
    layers=[];stats={}
    for facility in catalogue(world):
        blocks,y0,shell=read_facility(world,facility)
        for i,floor in enumerate(facility.floors):
            entry,check=render_floor(out,facility,floor,feet_interval(facility,i),blocks,y0,shell,points,landings,doors,un_zones,mechanical)
            layers.append(entry)
            stats[floor.id]=check
            print(f"{floor.id} at Y {floor.feet}: {check['footprint']} mapped cells",flush=True)
    (out/"facility-layers.json").write_text(json.dumps(layers,ensure_ascii=False,indent=2),"utf8")
    (out/"facility-check.json").write_text(json.dumps(stats,indent=2),"utf8")


def merge(out):
    records=json.loads((out/"facility-layers.json").read_text("utf8"))
    grass=json.loads((out/"geofront.json").read_text("utf8"))
    grass["preview"]=preview(out/ASSETS/"geofront.png")
    records.insert(0,grass)
    if (out/"surface.json").exists():
        records.insert(0,json.loads((out/"surface.json").read_text("utf8")))
    for e in records:
        for key in ("texture","preview","mask","bottom","ceiling","ground"):
            if e.get(key):
                path=out/"assets"/e[key].replace(":","/")
                if not path.is_file():
                    raise FileNotFoundError(path)
    (out/ASSETS/"index.json").write_text(json.dumps(dict(schema=1,dimension=DIM,layers=records),ensure_ascii=False,indent=2),"utf8")

if __name__ == "__main__":
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument("world",type=Path)
    parser.add_argument("out",type=Path)
    parser.add_argument("--workers",type=int,default=3)
    parser.add_argument("--mode",choices=("cavern","facilities","merge","all"),default="all")
    args=parser.parse_args()
    (args.out/ASSETS).mkdir(exist_ok=True,parents=True)
    if args.mode in ("all","cavern"):
        bake_cavern(args.world,args.out,args.workers)

    if args.mode in ("all","facilities"):
        bake_facilities(args.world,args.out)
    if args.mode in ("all","merge"):
        merge(args.out)
