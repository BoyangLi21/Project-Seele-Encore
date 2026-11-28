"""Complete the reserve landings, shade its operations room, and open the Sigma laboratory passageways."""

import json
from pathlib import Path

import nbtlib
import numpy as np
from dogma_optics_gallery import FLOOR_Y, GLASS, gallery_footprint
from dogma_recommission import AIR, AIRS, FLOOR, source_entity

SURVEY = Path(__file__).with_name("plans")/"subterminal_geofront.npz"
FIXTURES = Path(__file__).resolve().parents[1]/"src/main/resources/assets/projectseele/command/reserve_power.json"
LIGHT_SWITCH = (231,-461,383)


def complete_landings(b):
    # Front and rear bounds of the three podium tiers differ. Each landing ends at
    # the back of the original blade, not at the narrower east edge of the command desks.
    for floor, lo, hi, wall_top in ((-463,375,415,-453),(-452,380,410,-448)):
        for z in range(lo,hi+1):
            back=next(x for x in range(254,260) if b.get(x,floor,z)=="minecraft:white_concrete")
            for x in range(254,back):
                if x<=256 and 390<=z<=396:
                    continue  # Keep the native lift shaft and moving cabin clear.
                if b.get(x,floor,z) in AIRS:
                    b.put(x,floor,z,FLOOR)
                # Cap the ends of the newly completed east aisle; light from the
                # lower room must not enter the command floor around its outer shell.
                if z in (lo,hi):
                    for y in range(floor+1,wall_top):
                        if b.get(x,y,z) in AIRS:
                            b.put(x,y,z,"smooth_quartz")
                if b.get(x,wall_top,z) in AIRS:
                    b.put(x,wall_top,z,FLOOR)
            for y in range(floor+1,wall_top):
                if b.get(back,y,z) in AIRS:
                    b.put(back,y,z,"white_concrete")


def gallery_caps(b):
    with np.load(SURVEY) as survey:
        floor=gallery_footprint(survey["m"])
    low=min(z for x,z in floor); high=max(z for x,z in floor)
    for x,z in floor:
        if min(z-low,high-z)>=8:
            continue
        for y in range(FLOOR_Y+1,FLOOR_Y+6):
            if b.get(x,y,z)==GLASS:
                b.put(x,y,z,"smooth_quartz")


def open_sigma(b):
    # The R24 enclosed gallery added end walls *behind* the original laboratory
    # doors. Open all three 3-wide handoffs and the 5-wide south vestibule.
    for z in (607,633,659):
        b.box(263,-466,z-1,263,-464,z+1,AIR)
        # In each doorway an old floor lamp occupied the middle of the walking surface.
        if b.get(264,-466,z).startswith("projectseele:nerv_ceiling_light["):
            b.put(264,-466,z,AIR)
            b.put(264,-464,z,"projectseele:nerv_ceiling_light[hanging=true,lit=true]")
    b.box(248,-466,680,252,-463,680,AIR)
    # Connect the east maintenance aisle to the vestibule through the transverse passage.
    for x in (272,278):
        b.box(x,-466,674,x,-463,676,AIR)


def circuit_cells():
    groups=json.loads(FIXTURES.read_text("utf8"))
    for group in groups:
        for x,z,lo,hi in group["columns"]:
            for y in range(lo,hi+1):
                yield (x,y,z), group["on"],group["off"]


def repair(b):
    complete_landings(b)
    # Two front-row fixtures previously replaced the wall on its chamfered corners.
    for z in (380,411):
        old=b.get(225,-454,z)
        if old.startswith("projectseele:nerv_ceiling_light["):
            b.put(225,-454,z,"smooth_quartz")
            b.put(226,-454,z,old)
    gallery_caps(b)
    open_sigma(b)
    powered="powered=true" in b.get(*LIGHT_SWITCH)
    for pos,on,off in circuit_cells():
        state=b.get(*pos)
        if state in (on,off):
            b.put(*pos,on if powered else off)


    stations=json.loads(FIXTURES.with_name("reserve_console.json").read_text("utf8"))
    signs=[(station["x"]-1,-462,station["z"]+offset)
           for station in stations for offset,_ in enumerate(station["keys"],-1)]
    signs.append((247,-459,407))
    for pos in signs:
        tag=b.tags.get(pos) or source_entity(b.reader,pos)
        if tag is None or "front_text" not in tag:
            continue
        if bool(tag["front_text"].get("has_glowing_text",0))!=powered:
            tag["front_text"]["has_glowing_text"]=nbtlib.Byte(powered)
            b.tags[pos]=tag
            b.put(*pos,b.get(*pos))
