"""World-space architecture for the main shaft, Terminal Dogma and the three Ritsuko tour rooms."""
import math

import numpy as np

AIR = 'minecraft:air'
FLOOR = 'projectseele:nerv_floor_panel'
WALL = 'projectseele:nerv_structural_panel'
SHAFT = 'projectseele:nerv_shaft_panel'
ARMOR = 'projectseele:nerv_launch_armor'
EDGE = 'minecraft:polished_deepslate'
DARK = 'minecraft:deepslate_tiles'
IRON = 'minecraft:iron_block'
RED = 'minecraft:red_concrete'
LIGHT = 'minecraft:sea_lantern'
LCL = 'projectseele:lcl[level=0]'
LOW, HIGH = -1265, -1052


class Design:
    """Sparse whole sections, with zero meaning leave the prior block untouched."""
    def __init__(self):
        self.sections = {}
        self.names = [None]
        self.ids = {}
        self.signs = {}

    def box(self, x0, y0, z0, x1, y1, z1, block):
        if not (x0 <= x1 and y0 <= y1 and z0 <= z1):
            raise ValueError((x0, y0, z0, x1, y1, z1))
        if block not in self.ids:
            self.ids[block] = len(self.names)
            self.names.append(block)
        for cx in range(x0 >> 4, (x1 >> 4) + 1):
            for cz in range(z0 >> 4, (z1 >> 4) + 1):
                for cy in range(y0 >> 4, (y1 >> 4) + 1):
                    key = cx, cz, cy
                    if key not in self.sections:
                        self.sections[key] = np.zeros((16, 16, 16), np.uint8)
                    x,y,z=cx*16,cy*16,cz*16
                    self.sections[key][max(0,y0-y):min(16,y1-y+1),
                                       max(0,z0-z):min(16,z1-z+1),
                                       max(0,x0-x):min(16,x1-x+1)] = self.ids[block]

    def block(self, x, y, z, block):
        self.box(x,y,z,x,y,z,block)

    def room(self, x0, y0, z0, x1, y1, z1, walls=WALL, floor=FLOOR):
        self.box(x0,y0,z0,x1,y1,z1,walls)
        self.box(x0+1,y0+1,z0+1,x1-1,y1-1,z1-1,AIR)
        self.box(x0+1,y0,z0+1,x1-1,y0,z1-1,floor)

    def sign(self,x,y,z,face,*lines):
        name=f'minecraft:warped_wall_sign[facing={face},waterlogged=false]'
        self.block(x,y,z,name)
        self.signs[(x,y,z)] = {'pos':[x,y,z],'front':list(lines),'color':'white','glow':True}


def main_shaft(d):
    # Select the clear east lane for the full 17 x 60 chassis. Platforms and
    # recessed emergency leaves are on its opposite side, never across that lane.
    d.room(102,LOW,224,146,-987,262,SHAFT)
    d.box(104,LOW+1,226,144,-989,260,AIR)
    d.box(145,LOW,225,146,HIGH,261,SHAFT)
    for y in range(-1256,-1052,8):
        d.box(145,y,228,145,y,258,EDGE)
        for z in (231,255):
            d.block(145,y,z,LIGHT)
    for y in (-1231,-1196,-1161,-1126,-1091):
        for z in (225,261):
            d.box(103,y,z,145,y+1,z,ARMOR)
        d.box(103,y,226,105,y+1,260,ARMOR)
        d.box(145,y,226,145,y+1,260,ARMOR)
    for i,y in enumerate((-1238,-1180,-1122,-1064)):
        z=226 if i%2==0 else 247
        d.box(104,y-2,z,116,y,z+12,EDGE)
        d.box(104,y,z,116,y,z+12,FLOOR)
        d.block(115,y,z+6,LIGHT)
    for i,y in enumerate(range(-1249,-1056,16)):
        z=229 if i%2 else 251
        d.box(104,y,z,108,y+1,z+5,ARMOR)

    # EVA heading out of a released cage can use the existing hangar hall.
    # The new apron crosses only the eastern edge of that hall, away from cage machinery.
    d.box(79,HIGH,231,144,HIGH,254,FLOOR)
    d.box(79,HIGH+1,231,144,HIGH+62,254,AIR)
    d.box(104,HIGH,231,144,HIGH,254,AIR)  # open mouth of the vertical shaft
    d.box(103,HIGH-4,231,103,HIGH-1,254,EDGE)
    d.box(103,HIGH-1,234,103,HIGH-1,250,LIGHT)
    # An independent lower collar and a level 23-wide turning bay.
    d.room(18,LOW,224,105,LOW+66,256,SHAFT)
    d.box(20,LOW+1,231,144,LOW+63,253,AIR)
    d.box(20,LOW,231,145,LOW,253,FLOOR)
    d.box(19,LOW+1,239,42,-1202,257,AIR)
    d.box(19,LOW,239,42,LOW,257,FLOOR)
    # Reconnect the upper personnel passage from B via a west-side catwalk.
    d.box(15,-1230,245,20,-1226,247,AIR)
    d.box(16,-1231,244,20,-1231,257,FLOOR)
    d.box(17,-1230,244,20,-1224,257,AIR)
    d.box(18,-1231,257,20,-1231,257,EDGE)
    for x in (104,144):
        d.block(x,LOW,242,LIGHT)
    # The head of the climbing wall opens onto a real landing. From there
    # the level north gallery leads back around the open well to the hangar.
    d.room(144,HIGH,207,166,HIGH+63,256,SHAFT)
    d.room(94,HIGH,205,166,HIGH+63,228,SHAFT)
    d.box(145,HIGH+1,228,164,HIGH+61,253,AIR)
    d.box(145,HIGH,228,164,HIGH,253,FLOOR)
    d.box(145,HIGH+1,212,164,HIGH+61,236,AIR)
    d.box(94,HIGH+1,212,164,HIGH+61,225,AIR)
    d.box(94,HIGH,212,164,HIGH,225,FLOOR)
    d.box(79,HIGH,209,105,HIGH,229,FLOOR)
    d.box(79,HIGH+1,209,105,HIGH+61,229,AIR)
    d.box(79,HIGH,225,103,HIGH,247,FLOOR)
    d.box(79,HIGH+1,225,103,HIGH+61,247,AIR)
    d.box(138,HIGH,231,144,HIGH+61,254,AIR)
    d.block(146,-1054,242,'minecraft:chiseled_polished_blackstone')
    d.block(111,-1038,261,ARMOR)
    d.sign(111,-1038,260,'north','CENTRAL DOGMA','主軸 / 中央主轴','TERMINAL ↓','EAST WALL GRIP')


def door_block(x,y,z,opening):
    left=30-(opening+1)//2
    right=31+opening//2
    if left<x<right:
        return AIR
    column=x+26-left if x<=left else x+34-right
    if column in (26,34):
        return RED
    if -1249<=y<=-1247 or -1217<=y<=-1215:
        return 'minecraft:black_concrete'
    if z in (258,260) and y in (-1261,-1241,-1227,-1206) and column in (20,24,36,40):
        return IRON
    return WALL


def outlet_to_hangar(d, original):
    # Original underground sorties end on three carrier hatches at y=-466.
    # The shaft's upper stage starts beyond those hatches and never edits them.
    # It joins the very same apron as the hangar at y=-1052.
    for x in range(-21,148):
        for z in range(140,175):
            for y in range(-466,-429):
                b=original.get(x,y,z) or ''
                if any(part in b for part in ('_leaves','_log','_wood','sapling','vine')):
                    d.block(x,y,z,AIR)
    d.room(116,HIGH,172,151,-468,202,SHAFT)
    d.box(118,HIGH+1,174,149,-467,200,AIR)
    d.box(150,HIGH+1,174,151,-467,200,SHAFT)
    for y in range(HIGH+8,-468,8):
        d.box(150,y,176,150,y,198,EDGE)
        for z in (178,197): d.block(150,y,z,LIGHT)
    for y in range(HIGH+35,-470,35):
        d.box(117,y,173,149,y+1,173,ARMOR)
        d.box(117,y,201,149,y+1,201,ARMOR)
        d.box(117,y,174,119,y+1,200,ARMOR)
    d.box(117,-467,173,150,-467,201,EDGE)
    d.box(118,-467,174,149,-467,200,AIR)
    d.box(150,-467,175,162,-467,200,FLOOR)
    d.box(150,-466,175,162,-405,200,AIR)
    d.block(151,-469,188,'minecraft:chiseled_polished_blackstone')
    for z in (174,182,194,200):
        d.block(162,-467,z,'minecraft:yellow_concrete')
    for x in range(120,151,5): d.block(x,-467,173,'minecraft:yellow_concrete')
    d.block(157,-465,203,ARMOR)
    d.sign(157,-465,202,'north','CENTRAL DOGMA','主軸 / 中央主轴','EVA ↓','EAST WALL GRIP')
    d.box(121,HIGH,187,146,HIGH,218,FLOOR)
    d.box(121,HIGH+1,187,146,HIGH+61,218,AIR)
    d.box(126,HIGH+1,207,144,HIGH+61,225,AIR)


def chamber(d, original, opening):
    # Old upper leaves and lintel are retained. The extended door includes a
    # three-wide personnel bridge in its west pocket, outside the 19-wide EVA lane.
    for x in range(16,45):
        for z in range(258,261):
            for y in range(LOW+1,-1230):
                state=FLOOR if y==-1231 and 18<=x<=20 else door_block(x,y,z,opening)
                d.block(x,y,z,state)
            d.block(x,LOW,z,'minecraft:polished_blackstone_bricks')
    d.block(16,LOW,258,'minecraft:chiseled_polished_blackstone')
    # Narrow remaining section of the old central balcony: a continuous pedestrian
    # walkway leaves the door to the west. The cleared central portal frames the lake.
    d.box(21,LOW+1,261,40,-1203,307,AIR)
    d.box(16,-1231,261,19,-1231,288,EDGE)
    d.box(18,-1231,261,20,-1231,262,FLOOR)
    for z in range(264,289,4):
        d.block(16,-1230,z,'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]')
    # Descend from the older high service gallery to the lake-side reveal.
    # From here the viewer stands below the cross, facing the mask upwards.
    d.box(5,-1231,272,17,-1231,274,EDGE)
    d.box(5,-1230,272,17,-1227,274,AIR)
    for i in range(1,26):
        z=274+i
        y=-1231-i
        d.box(5,y+1,z,9,-1228,z,AIR)
        d.box(5,y-1,z,9,y-1,z,DARK)
        d.box(5,y,z,9,y,z,'minecraft:polished_deepslate_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
        d.block(5,y+1,z,'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]')
        if i%6==0: d.block(9,y-1,z,LIGHT)
    d.box(5,-1256,300,12,-1256,315,EDGE)
    d.box(5,-1255,300,12,-1252,315,AIR)
    for z in (302,313):
        for x in (5,12): d.box(x,LOW,z,x,-1257,z,DARK)
    for z in range(301,316):
        d.block(5,-1255,z,'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]')
    for x in range(5,13):
        d.block(x,-1255,315,'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]')
    # The submerged ramp puts the standing machine in increasingly deep LCL, up
    # to its waist on the approach to Lilith. Its top never breaks the lake surface.
    for z in range(261,343):
        for x in range(20,42):
            y=LOW-1-min(26,max(0,z-264)//3)
            d.block(x,y,z,DARK)
            for h in range(y+1,LOW+1):
                d.block(x,h,z,LCL)
    # Set back the far bulkhead into deep round red ports. Seen through the door
    # their dark bell mouths flank the white figure above its uninterrupted lake.
    def port(cx,cy,cz,r,side):
        for u in range(-r-2,r+3):
            for v in range(-r-2,r+3):
                rad=math.hypot(u,v)
                if rad>r+2: continue
                for depth in range(6):
                    if rad>r:
                        state='minecraft:polished_blackstone' if rad>r+1 else 'minecraft:nether_bricks'
                    elif depth<2 and rad>=r-1:
                        state='minecraft:red_nether_bricks'
                    elif depth==5:
                        state='minecraft:black_concrete' if rad<r*.62 else 'minecraft:nether_wart_block'
                    elif depth==4 and (abs(v+u*.32)<.60 or abs(v+u*.32-4)<.62 or abs(v+u*.32+4)<.62):
                        state='minecraft:polished_blackstone'
                    else:
                        state=AIR
                    if side==0: d.block(cx+u,cy+v,cz+depth,state)
                    else: d.block(cx+side*depth,cy+v,cz+u,state)
        if side==0:d.block(cx,cy-2,cz+3,'minecraft:light[level=8,waterlogged=false]')
        else:d.block(cx+side*3,cy-2,cz,'minecraft:light[level=8,waterlogged=false]')
    for x in (-11,72): port(x,-1226,391,12,0)
    for x,side in ((-34,-1),(94,1)):
        for z in (303,363): port(x,-1223,z,10,side)
    # Black ribs and small practical lamps stay at the periphery of the 130-wide hall.
    # Pairs of red beacons mark the entrance back, the long axis remains dark.
    for x in (-34,94):
        for z in range(274,390,15):
            d.box(x,-1264,z,x,-1199,z+1,DARK)
            d.block(x,-1242,z,'minecraft:redstone_block')
            d.block(x,-1241,z,'minecraft:redstone_lamp[lit=true]')
            d.block(x,-1202,z,LIGHT)
    # Kiki's mesh stays in place. Shift the entire block crucifix, including its
    # submerged footing. The two bolts reach from the mesh's own nails into the beam.
    cross={'minecraft:red_concrete','minecraft:gray_concrete'}
    members={}
    for x in range(-4,65):
        for z in range(352,356):
            for y in range(-1310,-1198):
                before=original.get(x,y,z)
                if before in cross and (27<=x<=33 or (-1227<=y<=-1222) or 25<=x<=35):
                    members[x,y,z]=before
    for x,y,z in members:
        d.block(x,y,z,AIR if y>LOW else LCL)
    for (x,y,z),state in members.items():
        d.block(x,y,z+3,state)
    for x in (1,60):
        d.box(x,-1225,353,x,-1225,355,'minecraft:polished_blackstone')

    # Reduce the frontal institutional lighting. The axis ends on the face, palms
    # and vermilion cross. The same local light can illuminate the LCL reflection.
    for x in (3,57):
        d.block(x,-1223,350,'minecraft:light[level=12,waterlogged=false]')
    for x in (8,52):
        d.block(x,-1257,352,'minecraft:light[level=8,waterlogged=false]')
    d.block(16,-1228,249,WALL)
    d.sign(17,-1228,249,'east','HEAVEN’S DOOR','封印区 →','中央主軸 ↑','実験棟 ←')


def tour(d):
    # On the existing unrestricted side of Heaven's Door. The old B lift and its
    # controls remain in their original shaft. The walk follows the order of episode 23.
    y=-1231
    d.room(-15,y,187,-7,y+6,246,DARK)
    d.box(-13,y+1,244,-9,y+4,247,AIR)
    d.box(-13,y,244,-9,y,247,FLOOR)
    for z in range(190,244,9):
        d.block(-11,y+5,z,LIGHT)
    d.room(-33,y,186,-6,y+9,208,'minecraft:light_gray_concrete','minecraft:smooth_stone')
    d.box(-13,y+1,207,-9,y+4,209,AIR)
    # Rough wall panels, an examination cot, pillow, table, bare overhead fixture,
    # and a narrow illuminated band opposite the bed.
    for x in range(-31,-7,4):
        d.box(x,y+1,187,x,y+7,187,'minecraft:gray_concrete')
    d.box(-28,y+1,193,-24,y+1,194,IRON)
    d.box(-28,y+2,193,-25,y+2,194,'minecraft:white_wool')
    d.box(-24,y+2,193,-24,y+2,194,'minecraft:smooth_quartz')
    for x in (-28,-24):
        for z in (193,194):
            d.block(x,y+1,z,'minecraft:polished_andesite')
    d.box(-29,y+1,198,-29,y+2,199,EDGE)
    d.block(-29,y+3,198,'minecraft:flower_pot')
    d.block(-27,y+1,202,'minecraft:water_cauldron[level=3]')
    d.block(-24,y+1,199,'minecraft:polished_andesite_slab[type=bottom,waterlogged=false]')
    for z in range(192,205,4):
        d.box(-7,y+4,z,-7,y+5,z+1,'minecraft:tinted_glass')
    d.block(-20,y+8,198,LIGHT)
    # Chalk from the research notes on the wall and floor in episode 23.
    for dx,dy in ((0,0),(1,1),(2,2),(3,1),(4,0),(1,0),(2,0),(3,0),
                  (7,1),(8,1),(9,1),(7,3),(8,3),(9,3)):
        d.block(-28+dx,y+3+dy,187,'minecraft:white_terracotta')
    for dx,dz in ((0,0),(1,0),(2,0),(1,1),(1,2),(2,3),(3,3),(4,3)):
        d.block(-22+dx,y,198+dz,'minecraft:gray_terracotta')
    d.sign(-8,y+3,207,'north','第１区画','旧実験室','REI / 01')

    # Deep failed-prototype pit. Natural variations in pose, exposed ribs, collapsed
    # necks and eye sockets read from the high grated observation passage.
    d.room(-84,y-17,122,-29,y+12,190,DARK,'minecraft:polished_basalt[axis=y]')
    d.box(-33,y+1,188,-30,y+4,192,AIR)
    d.box(-33,y,187,-30,y,192,FLOOR)
    d.box(-35,y,123,-30,y,189,'minecraft:iron_block')
    d.box(-82,y,122,-30,y,126,EDGE)
    for z in range(127,187):
        d.block(-35,y+1,z,'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]')
    for z in range(132,184,10):
        d.block(-32,y,z,LIGHT)
    for i,(cx,cz) in enumerate([(-68,139),(-48,143),(-71,162),(-50,170),(-64,178)]):
        base=y-15+(i%3)
        bone='minecraft:bone_block[axis=z]'
        d.box(cx-1,base,cz-7,cx+1,base+1,cz+5,bone)
        for t in (-5,-2,1,4):
            width=4+(t in (-2,1))
            for side in (-1,1):
                for j in range(1,width+1):
                    d.block(cx+side*j,base+round(2*math.sin(j*math.pi/width)),cz+t,bone)
        d.box(cx-3,base+1,cz-12,cx+3,base+5,cz-7,'minecraft:smooth_sandstone')
        for dx in (-2,1):
            d.box(cx+dx,base+3,cz-12,cx+dx+1,base+4,cz-11,'minecraft:black_concrete')
        d.box(cx-2,base+1,cz-13,cx+2,base+2,cz-11,bone)
        for side in (-1,1):
            d.box(cx+min(side*7,side*2),base,cz+4,cx+max(side*7,side*2),base+1,cz+5,bone)
        d.block(cx,base-1,cz,LIGHT)
    d.sign(-30,y+3,181,'west','実験体廃棄場','EVA GRAVEYARD')

    # Dummy Plant: a dark, flooded arcuate bank seen through amber glass from one
    # continuous dry observation gallery. Pale blue-haired figures float at varied depths.
    d.room(-38,y,95,20,y+16,126,EDGE,'minecraft:polished_deepslate')
    d.box(-34,y+1,124,-30,y+4,126,AIR)
    d.box(-34,y,123,-30,y,126,FLOOR)
    for x in range(-29,18):
        curve=102+round(7*((x+6)/24)**2)
        d.box(x,y+1,97,x,y+12,curve,LCL)
        d.box(x,y+1,curve+1,x,y+12,curve+1,'minecraft:orange_stained_glass')
        d.box(x,y+13,97,x,y+13,curve+1,EDGE)
        d.box(x,y,97,x,y,curve,'minecraft:ochre_froglight[axis=y]')
    for i,x in enumerate(range(-25,17,5)):
        z=102+round(7*((x+6)/24)**2)
        for row in range(2):
            sx=x+(1 if row else 0)
            d.block(sx,y+2+(i*3)%4+row*5,z-1-row,
                    'projectseele:dummy_tank_figure[facing='+('west' if i%5==2 and row else 'south')+']')
    d.sign(-36,y+3,125,'north','第２区画','DUMMY PLANT','模擬人格・複製槽')
    # Central core and linked plug housings sit on a raised service plinth.
    d.box(7,y+1,115,16,y+1,122,EDGE)
    for x in (9,12,15):
        d.box(x,y+2,116,x,y+5,121,'minecraft:quartz_pillar[axis=z]')
        d.block(x,y+4,115,'minecraft:red_concrete')
        d.block(x,y+5,121,'minecraft:redstone_block')
    d.box(1,y+1,116,4,y+6,119,'minecraft:gray_concrete')
    d.box(2,y+3,119,3,y+5,119,'minecraft:red_stained_glass')
    d.block(2,y+4,118,LIGHT)
    for x in range(-24,15,4):
        d.block(x,y+14,113,'minecraft:light[level=6,waterlogged=false]')
    d.sign(3,y+2,120,'south','ダミーシステム','DUMMY CORE')
    return d


def build(original,opening):
    d=Design()
    main_shaft(d)
    outlet_to_hangar(d,original)
    chamber(d,original,opening)
    tour(d)
    return d
