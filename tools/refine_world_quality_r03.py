"""Measured repairs and authored TV-inspired detailing in the existing world.

No terrain regeneration or transport recreation. Mechanical blocks and floor
levels remain governed by their actual saved states and native tests.
"""
from pathlib import Path
import argparse,json,math,gzip
import copy
import nbtlib
import regional_voxels as vox
from quality_structures import Builder,Station
from regional_architecture import AIR,WALL,WHITE,GLASS,FLOOR,DARK,LIGHT,STEEL,RED,bench

ROOT=vox.ROOT;OUT=ROOT/'artifacts/world_quality_r03';R02=ROOT/'artifacts/world_quality_r02';OLD=ROOT/'artifacts/world_expansion_20260907'
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
CROPPED={'tokyo_south/13-05':152,'tokyo_south/13-06':152}
GRAY='minecraft:gray_concrete';BLACK='minecraft:black_concrete';PALE='minecraft:smooth_quartz';YELLOW='minecraft:yellow_terracotta'
BAR='minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]'

def current_plots():
    result=load(R02/'surface_layout.json')['kept_plots']
    if (vox.WORLD/'regional_quality_r03_structures.json').exists():
        for b in result:
            if b['id'] in CROPPED:b['bounds'][1]=CROPPED[b['id']]
    return result

def sign(p,x,y,z,lines,owner,facing='north'):
    p.sign(x,y,z,lines,owner,facing)
    # A different block from old oak labels also ensures text NBT is committed
    # by the shared state-delta writer when an old position is reused.
    p.put(x,y,z,f'minecraft:birch_wall_sign[facing={facing},waterlogged=false]',owner)

def structure(p):
    plots=load(R02/'surface_layout.json')['kept_plots']
    for b in plots:
        if b['id'] not in CROPPED:continue
        x0,x1,z0,z1=b['bounds'];f=b['floor'];n=b['storeys'];edge=CROPPED[b['id']];o=b['id']+'/east_facade_repair'
        p.fill(edge+1,f+1,z0,x1,f+n*5+5,z1,AIR,o)
        p.fill(edge,f,z0,edge,f+n*5,z1,WALL,o)
        for level in range(n):
            y=f+level*5
            p.fill(edge-1,y,z0,edge,y,z1,FLOOR,o)
            for z in range(z0+3,z1-2,5):p.fill(edge,y+2,z,edge,y+3,min(z+2,z1-2),GLASS,o)
            p.fill(edge,y+4,z0,edge,y+4,z1,WHITE,o)
        p.fill(edge-1,f+n*5,z0,edge,f+n*5,z1,DARK,o)
        p.fill(edge,f+n*5+1,z0,edge,f+n*5+1,z1,WALL,o)
        p.meta['landmarks'].append(dict(id=b['id'],before_bounds=b['bounds'],bounds=[x0,edge,z0,z1],floor=f,storeys=n))

def fittings(p):
    from query_blocks import iter_block_entities,read_box
    source=Path(load(OUT/'source_manifest.json')['backup']);moved=[]
    for b in load(R02/'surface_layout.json')['kept_plots']:
        if b['id'] not in CROPPED:continue
        x0,x1,z0,z1=b['bounds'];f=b['floor'];n=b['storeys'];edge=CROPPED[b['id']];o=b['id']+'/retained_fittings'
        for pos,be in iter_block_entities(source,vox.DIM,(edge+1,f,z0),(x1,f+n*5+5,z1)):
            target=(pos[0]-7,pos[1],pos[2]);state=read_box(source,vox.DIM,pos,pos)[pos]
            p.put(*target,state,o);tag=copy.deepcopy(be);tag['x']=nbtlib.Int(target[0]);p.block_entities[target]=tag
            moved.append(dict(before=pos,after=target,id=str(be['id']),snbt=tag.snbt()))
        if b['style']=='residential':
            for level in range(n):
                y=f+level*5
                p.match((151,y+1,z1-3,151,y+1,z1-3),'minecraft:smooth_quartz',AIR,o)
                p.fill(144,y+1,z1-3,150,y+1,z1-3,PALE,o)
                p.put(146,y+1,z1-3,'minecraft:water_cauldron[level=3]',o)
                p.put(150,y+1,z1-2,'minecraft:crafting_table',o)
    p.meta['moved_fittings']=moved

GLYPHS={
 'N':['101','111','111','111','101'],'E':['111','100','110','100','111'],
 'R':['110','101','110','101','101'],'V':['101','101','101','101','010'],
 'C':['111','100','100','100','111'],'U':['101','101','101','101','111'],
 'A':['010','101','111','101','101'],'S':['111','100','111','001','111'],
 'F':['111','100','110','100','100'],'T':['111','010','010','010','010'],
 '0':['111','101','101','101','111'],'1':['010','110','010','010','111'],
 '2':['110','001','010','100','111'],'3':['110','001','010','001','110'],
 '4':['101','101','111','001','001'],'5':['111','100','110','001','110'],
 '6':['011','100','111','101','111'],'7':['111','001','010','010','010'],
 '8':['111','101','111','101','111'],'9':['111','101','111','001','110']}

def letters(p,text,x,y,z,owner,color=WHITE,axis='x'):
    for c,char in enumerate(text):
        for row,bits in enumerate(GLYPHS[char]):
            for col,on in enumerate(bits):
                if on=='1':p.put(x+(c*4+col if axis=='x' else 0),y+4-row,z+(c*4+col if axis=='z' else 0),color,owner)

def seats(p,x,z,f,o,facing='north',length=3):
    for i in range(length):
        h='single' if length==1 else 'left' if i==0 else 'right' if i==length-1 else 'middle'
        p.put(x+i,f+1,z,f'another_furniture:dark_oak_bench[facing={facing},back=true,horizontal_1={h},horizontal_2={h}]',o)

def replace_seats(p,box,o):
    for facing in ('north','south','east','west'):
        p.match(box,f'minecraft:dark_oak_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]',
                f'another_furniture:dark_oak_chair[facing={facing},tucked=false,variant=1]',o)

def stations(p):
    from quality_structures import ground_ports
    data=[d for d in load(OLD/'transit_plan.json')['platforms'] if d.get('mode')!='AIRPLANE']+load(R02/'extension_plan.json')['transit']['platforms']
    for d in data:
        s=Station(p,d);f=s.y;h=s.half;o=s.owner+'/detail';side=10 if d.get('compact') else 15
        lo=s.xyz(-h,f+1,-side);hi=s.xyz(h,f+12,side)
        box=tuple(min(lo[i],hi[i]) for i in range(3))+tuple(max(lo[i],hi[i]) for i in range(3))
        replace_seats(p,box,o)
        for v0,v1 in [(-side,-4),(4,side)]:
            a=s.xyz(-h,f+11,v0);b=s.xyz(h,f+11,v1);p.match((*a,*b),DARK,GRAY,o+'/roof_panels')
        for v in (-side,side):
            # Existing solid lintels receive a quieter metal face. Open ports stay open.
            a=s.xyz(-h,f+8,v);b=s.xyz(h,f+8,v);p.match((*a,*b),WALL,WHITE,o+'/lintel')
            for u in range(-h+7,h-6,16):
                if abs(u)<8:continue
                s.fill(u,f+9,v-(-1 if v>0 else 1),u+3,f+9,v-(-1 if v>0 else 1),GRAY)
            # Signs face passengers inside, and use a consistent route colour.
            if h>=35:
                u=23;vinside=v-(1 if v>0 else -1);facing=('north' if v>0 else 'south') if s.horizontal else ('west' if v>0 else 'east')
                s.fill(u-4,f+3,v,u+5,f+8,v,BLACK)
                x,y,z=s.xyz(u-3,f+4,vinside);letters(p,d['line'][:2],x,y,z,o,WHITE,'x' if s.horizontal else 'z')
                x,y,z=s.xyz(u+1,f+2,vinside);sign(p,x,y,z,[d['name'],d['line'],'のりば / PLATFORM','← 乗換  EXIT →'],o,facing)
            # Fluted ventilation slots stay high above every footbridge.
            for u in range(-h+8,h-7,12):
                for k in range(4):
                    x,y,z=s.xyz(u+k,f+10,v-(1 if v>0 else -1))
                    p.put(x,y,z,'minecraft:iron_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]',o)
        # Flush paving distinguishes the waiting strip; native MTR edges remain intact.
        for v in (-5,5):
            a=s.xyz(-h+4,f,v);b=s.xyz(h-4,f,v);p.match((*a,*b),FLOOR,PALE,o+'/paving')
        for u in (-h+12,h-12):
            if -25<=u<=5:continue
            for v in (-(side-3),side-3):
                x,y,z=s.xyz(u,f+1,v);p.put(x,y,z,GRAY,o);p.put(x,y+1,z,'minecraft:iron_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]',o)
                # Low refuse bins and utility cabinets are kept out of walking lanes.
                x,y,z=s.xyz(u+3,f+1,v);p.fill(x,y,z,x,y+1,z,WALL,o)
                facing=('north' if v>0 else 'south') if s.horizontal else ('west' if v>0 else 'east')
                sign(p,x,y+2,z,['案内 / HELP',d['line'],'時刻表 / GUIDE',''],o,facing)
        p.meta['landmarks'].append(dict(id=o,center=d['center'],programme='seating, signage, ceiling, vents, platform paving'))

def corridor_detail(p,x0,x1,z0,z1,f,h,o):
    horizontal=(x1-x0)>(z1-z0)
    p.match((x0-1,f+h+1,z0-1,x1+1,f+h+1,z1+1),DARK,GRAY,o+'/ceiling')
    # Side-wall seams and kick plates only replace measured concrete. They
    # cannot close existing doorways or replace a retained native mechanism.
    for edge in ((z0-1,z1+1) if horizontal else (x0-1,x1+1)):
        wall=(x0,f+1,edge,x1,f+1,edge) if horizontal else (edge,f+1,z0,edge,f+1,z1)
        p.match(wall,WALL,GRAY,o+'/kickplate')
        for t in range((x0 if horizontal else z0)+5,(x1 if horizontal else z1),10):
            box=(t,f+1,edge,t,f+h,edge) if horizontal else (edge,f+1,t,edge,f+h,t)
            for before in (WALL,RED):p.match(box,before,PALE,o+'/panel_seam')
    for t in range((x0 if horizontal else z0)+5,(x1 if horizontal else z1)-2,10):
        box=(t,f+h,z0,t,f+h,z1) if horizontal else (x0,f+h,t,x1,f+h,t)
        # A continuous lighting cassette replaces the isolated cube rhythm.
        p.fill(*box,'minecraft:smooth_stone_slab[type=top,waterlogged=false]',o+'/ceiling_batten','air')
        mx=(x0+x1)//2;mz=(z0+z1)//2
        if horizontal:p.put(t,f+h,mz,LIGHT,o+'/fluorescent','air')
        else:p.fill(mx-1,f+h,t,mx+1,f+h,t,LIGHT,o+'/fluorescent','air')

def underground(p):
    # Long moving walkway and all established gallery spines.
    corridors=[(114,122,-14,242,-443,5,'hangar'),(-32,-28,271,399,-462,5,'west_lower'),(87,91,271,399,-462,5,'east_lower'),
               (-32,-28,271,399,-449,5,'west_upper'),(87,91,271,399,-449,5,'east_upper'),(194,198,410,537,-461,4,'science_bridge'),
               (326,330,447,608,-467,4,'laboratories'),(273,277,556,679,-467,4,'sigma'),(257,261,100,267,-467,4,'services'),
               (-311,-307,733,768,-467,5,'arrival'),(26,34,445,472,-467,5,'hq_approach')]
    for x0,x1,z0,z1,f,h,key in corridors:corridor_detail(p,x0,x1,z0,z1,f,h,'nerv/detail/'+key)
    # Portal frames and legible sector signs are spaced along the long route.
    for index,z in enumerate((10,70,130,190,232)):
        o='nerv/hangar_marker/'+str(index)
        for x in (113,123):
            p.match((x,-442,z,x,-438,z),WALL,GRAY,o)
            p.match((x,-442,z,x,-438,z),RED,YELLOW,o)
        p.fill(116,-439,z-1,120,-439,z-1,GRAY,o,'air')
        sign(p,118,-439,z,['EVA ケイジ ↑','発令所 ↓','CAGE / LAUNCH','B-40  '+str(index+1).zfill(2)],o,'south')
        p.fill(117,-438,z-1,119,-438,z-1,GRAY,o,'air')
    # Lower arrival hall: information wall, staff desk and waiting bays.
    o='hq/arrival/detail';f=-462
    p.match((-33,f+10,394,93,f+10,429),LIGHT,AIR,o+'/retire_cube_lights')
    p.match((-34,f+11,393,94,f+11,430),DARK,GRAY,o+'/ceiling')
    p.fill(0,f+2,393,61,f+9,393,BLACK,o)
    letters(p,'NERV',22,f+4,394,o)
    p.fill(1,f+2,393,60,f+2,393,RED,o)
    for x in (-20,0,20,40,60,80):
        p.fill(x,f+10,398,x+1,f+10,419,PALE,o)
        p.fill(x+4,f+10,404,x+12,f+10,404,LIGHT,o)
        p.fill(x+4,f+10,417,x+12,f+10,417,LIGHT,o)
    for x0 in (-20,63):
        p.fill(x0,f,400,x0+16,f,418,'minecraft:polished_andesite',o)
        for z in (409,416):seats(p,x0+4,z,f,o,'north',8)
        p.fill(x0+1,f+1,403,x0+2,f+1,404,GRAY,o)
        p.put(x0+1,f+2,403,'minecraft:flower_pot',o)
    p.fill(-18,f+1,398,-5,f+1,400,WALL,o)
    for x in (-15,-9):
        p.put(x,f+2,399,BLACK,o);p.put(x,f+2,400,'minecraft:green_stained_glass',o)
    sign(p,-10,f+4,394,['総合案内','INFORMATION','職員証をご提示下さい','NERV HQ'],o,'south')
    sign(p,74,f+4,394,['EVA ケイジ →','研究区 →','← 医療 / 職員施設','U1 / U2 ↓'],o,'south')
    for x in (-30,89):
        p.fill(x-3,f,405,x-3,f,422,GRAY,o);p.fill(x+3,f,405,x+3,f,422,GRAY,o)
    # All twenty-two furnished rooms retain their doors and functional contents.
    rooms=load(R02/'circulation_repair/places.json')['rooms']+[r for r in load(OLD/'geometry_all/places.json')['rooms'] if not r['id'].startswith('hq/')]
    for r in rooms:
        x0,x1,z0,z1=r['bounds'];f=r['floor'];o=r['id']+'/detail';short=(r['id'].startswith('hq/east') and r['id'].endswith('/1') and f==-449);h=5 if short else 9
        replace_seats(p,(x0+1,f+1,z0+1,x1-1,f+1,z1-1),o)
        p.match((x0+1,f+h-1,z0+1,x1-1,f+h-1,z1-1),LIGHT,AIR,o+'/retire_cube_lights')
        p.match((x0,f+h,z0,x1,f+h,z1),DARK,GRAY,o+'/ceiling')
        for x in range(x0+5,x1-3,8):p.fill(x,f+h-1,z0+4,x+2,f+h-1,z1-4,LIGHT,o+'/light_strip','air')
        for z in (z0,z1):
            p.match((x0+1,f+1,z,x1-1,f+1,z),WALL,GRAY,o+'/base')
            for x in range(x0+5,x1-2,8):p.match((x,f+2,z,x,f+h-1,z),WALL,PALE,o+'/wall_joint')
        x,y,z=r['entry'];direction='east' if '/west/' in r['id'] or r['id'].startswith('logistics/') else 'west'
        sign(p,x+(1 if direction=='east' else -1),f+3,z+2,[r['label'],r['purpose'],'NERV  '+str(f+1),''],o,direction)
        # Wiring and equipment are flush in the back wall, outside room aisles.
        rear=x0 if direction=='east' else x1
        for z in range(z0+4,z1-3,12):
            p.match((rear,f+2,z,rear,f+4,z+2),WALL,GRAY,o+'/service_panel')
    # Calm the busy checkerboard at the preserved upper cage gallery.
    for state in (STEEL,'minecraft:white_concrete','minecraft:red_concrete'):
        p.match((-44,-395,-80,89,-395,-73),state,FLOOR,'cage/detail/deck')
    for x,color in [(-12,'yellow'),(30,'purple'),(72,'red')]:
        p.match((x-10,-395,-73,x+10,-395,-73),FLOOR,'minecraft:'+color+'_terracotta','cage/detail/unit_edge')
    p.meta['room_details']=len(rooms);p.meta['gallery_details']=len(corridors)

def airports(p):
    for key,sx,gx,rz in [('bay',740,650,1430),('hakone',-1670,-1610,-20)]:
        x0,x1,z0,z1=sx-100,sx+100,rz-380,rz-305;f=80;o='airport/'+key+'/detail'
        replace_seats(p,(x0+1,81,z0+1,x1-1,81,z1-1),o)
        p.match((x0+1,99,z0+1,x1-1,99,z1-1),LIGHT,AIR,o+'/retire_cube_lights')
        p.match((x0,100,z0,x1,100,z1),DARK,WALL,o+'/ceiling')
        # Two service wings leave a sixteen-metre central departure axis.
        for side in (-1,1):
            a,b=sorted((sx+side*18,sx+side*90))
            p.fill(a,80,z0+9,b,80,z0+25,'minecraft:polished_andesite',o+'/checkin_zone')
            for c in range(3):
                cx=sx+side*(27+c*24)
                p.fill(cx-8,81,z0+12,cx+8,82,z0+14,AIR,o+'/counter_reset')
                p.fill(cx-8,81,z0+13,cx+7,81,z0+14,GRAY,o+'/checkin_counter')
                p.fill(cx-8,82,z0+13,cx+7,82,z0+13,'minecraft:heavy_weighted_pressure_plate[power=0]',o)
                for dx in (-4,3):
                    p.put(cx+dx,82,z0+14,BLACK,o);p.put(cx+dx,82,z0+15,'minecraft:green_stained_glass',o)
                    p.put(cx+dx,81,z0+11,'another_furniture:dark_oak_chair[facing=south,tucked=false,variant=1]',o)
                p.fill(cx-6,88,z0+14,cx+6,90,z0+14,BLACK,o+'/counter_header')
                p.put(cx,91,z0+14,'minecraft:chain[axis=y,waterlogged=false]',o)
                p.fill(cx,92,z0+14,cx,97,z0+14,'minecraft:chain[axis=y,waterlogged=false]',o)
                sign(p,cx,89,z0+15,[f'{c+1 if side<0 else c+4:02d}  CHECK-IN','搭乗手続き','F1 / REGIONAL AIR','手荷物 / BAGGAGE'],o,'south')
                for z in (z0+19,z0+23):p.fill(cx-6,80,z,cx+6,80,z,WHITE,o+'/queue_inlay')
            # Side lounge furniture and a planted divider; aisles are six metres wide.
            for z in (z0+34,z0+48,z0+61):
                for center in (sx+side*37,sx+side*69):
                    seats(p,center-4,z,80,o,'north',9)
                    seats(p,center-4,z+2,80,o,'south',9)
                    p.fill(center-3,80,z-3,center+3,80,z+5,'minecraft:polished_andesite',o)
            # A service wall gives the otherwise empty end bay a purpose.
            edge=sx+side*94
            for z in range(z0+33,z1-5,9):
                p.fill(edge-1,81,z,edge+1,84,z+2,WALL,o+'/service_cabinet')
                p.put(edge,83,z-1,'minecraft:black_stained_glass',o)
                sign(p,edge,82,z-1,['SERVICE','飲料 / 案内','',''],o)
        # Main information board and a large terminal number, with clear sightlines.
        p.fill(sx-11,90,z0+30,sx+11,96,z0+30,BLACK,o+'/departures_board')
        letters(p,'F1',sx-3,91,z0+29,o,'minecraft:orange_terracotta')
        for dx in (-9,9):p.fill(sx+dx,97,z0+30,sx+dx,99,z0+30,GRAY,o+'/board_hanger')
        sign(p,sx,89,z0+29,['出発 / DEPARTURES','F1 新箱根 ⇄ 箱根湾','乗換 / RAIL ↓','搭乗口 / GATE 01'],o)
        # Ceiling coffers and recessed light strips replace repeated hanging cubes.
        for x in range(x0+6,x1-5,16):
            p.fill(x,98,z0+4,x+2,98,z1-4,WALL,o+'/ceiling_fin')
            for z in (z0+26,z0+53):p.fill(x+4,98,z,x+11,98,z,LIGHT,o+'/light_strip')
        # Entrance canopy fascia and structural soffit.
        for x in range(x0+7,x1-6,24):
            p.fill(x,88,z0-9,x+1,88,z0+2,GRAY,o+'/canopy_rib')
        sign(p,sx-5,86,z0-1,['出発 DEPARTURES','F1 / GATE 01','鉄道 RAIL ↓',''],o)
        sign(p,sx+5,86,z0-1,['到着 ARRIVALS','案内 INFORMATION','出口 EXIT ↑',''],o)
        sz=1190 if key=='bay' else -265
        corridor_detail(p,sx-2,sx+2,z1+8,sz,71,4,o+'/rail_transfer')
        for x,z,heading in [(sx,sz-22,'north'),(gx,sz-22,'north'),(gx,rz-218,'north')]:
            sign(p,x,75 if z<rz-230 else 85,z,['GATE 01 →','F1 / AIR SERVICE','← 鉄道 / TERMINAL',''],o,heading)
        # Real maintenance hangars: side equipment only, keeping aircraft doors clear.
        ox=480 if key=='bay' else -2160
        for number in range(2):
            hx=ox+335+number*105;hz=rz-230
            p.fill(hx-37,81,hz-14,hx-23,82,hz-12,GRAY,o+'/maintenance_bench')
            for x in range(hx-35,hx-23,4):p.put(x,83,hz-13,'minecraft:anvil[facing=north]',o)
            for x in (hx-34,hx+34):
                p.fill(x,81,hz+5,x+5,83,hz+11,GRAY,o+'/service_cart')
                p.fill(x,84,hz+5,x+5,84,hz+11,'minecraft:iron_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]',o)
            p.fill(hx-17,99,hz+20,hx+17,106,hz+20,GRAY,o+'/hangar_number_panel')
            letters(p,'0'+str(number+1),hx-3,100,hz+21,o)
            sign(p,hx-18,82,hz+21,['航空整備庫','MAINTENANCE','AUTHORIZED','PERSONNEL'],o,'south')
        p.meta['landmarks'].append(dict(id=o,programme='six check-in counters, lounges, departures board, service wall, hangar details'))

def surface(p):
    count=0
    for b in current_plots():
        if 'storeys' not in b:continue
        x0,x1,z0,z1=b['bounds'];f=b['floor'];n=b['storeys'];o=b['id']+'/facade_detail';cx=b['entry'][0];count+=1
        # Existing wall cells receive a base course and restrained corner joints.
        for wall in (WHITE,WALL,'minecraft:smooth_sandstone',GRAY):
            for box in [(x0,f+1,z0,x1,f+1,z0),(x0,f+1,z1,x1,f+1,z1),(x0,f+1,z0,x0,f+1,z1),(x1,f+1,z0,x1,f+1,z1)]:p.match(box,wall,GRAY,o)
            for xx in (x0,x1):p.match((xx,f+2,z0,xx,f+n*5-1,z0),wall,PALE,o)
        p.fill(cx-3,f+4,z1+1,cx+3,f+4,z1+2,'minecraft:smooth_stone_slab[type=top,waterlogged=false]',o+'/entry_canopy','air')
        p.put(cx,f+3,z1+1,'another_furniture:white_lamp[facing=south,base=true,lit=true]',o+'/entry_light','air')
        sign(p,cx+3,f+3,z1+1,[b['id'].split('/')[1],'住宅 / RESIDENCE' if b['style'] in ('residential','regional_city') else 'OFFICE / 業務棟','入口 / ENTRY',''],o,'south')
        replace_seats(p,(x0+1,f+1,z0+1,x1-1,f+(n-1)*5+1,z1-1),o)
    p.meta['facades_detailed']=count

def finish(p):
    from query_blocks import iter_selected_sections
    labels=[]
    def text_label(key,pos,text,yaw=0,scale=2,color='#e7e8dc'):
        labels.append(dict(id=key,position=pos,yaw=yaw,scale=scale,text=dict(text=text,color=color)))
    # Recess new lamps into their ceilings, behind shallow metal diffusers.
    for part in ('underground','airports'):
        with gzip.open(OUT/(part+'_details')/'ops.json.gz','rt',encoding='utf-8') as fp:ops=json.load(fp)
        for op in ops:
            if op['state']!=LIGHT or op['box'][1]!=op['box'][4]:continue
            if not (op['owner'].endswith(('/fluorescent','/light_strip')) or op['owner']=='hq/arrival/detail' and op['box'][1]==-452):continue
            x0,y,z0,x1,_,z1=op['box'];rise=2 if part=='airports' and y==98 else 1;o='finish/recessed_lighting'
            p.match(tuple(op['box']),LIGHT,AIR,o)
            p.fill(x0,y+rise,z0,x1,y+rise,z1,LIGHT,o)
            p.fill(x0,y+rise-1,z0,x1,y+rise-1,z1,'minecraft:iron_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]',o)
    # Replace coarse voxel letters with crisp physical text displays.
    p.fill(22,-458,394,37,-454,394,AIR,'finish/hq_wordmark')
    text_label('hq_wordmark',[30.5,-458.2,394.02],'N E R V',0,17)
    text_label('hq_subtitle',[30.5,-459.5,394.02],'CENTRAL OPERATIONS  /  総合案内',0,1.8,'#b7b8af')
    for x in (7,46):
        p.fill(x-2,-462,402,x+11,-462,419,'minecraft:polished_andesite','finish/hq_waiting')
        for z in (406,414):seats(p,x,z,-462,'finish/hq_waiting','north',9)
        p.fill(x+10,-461,408,x+11,-461,412,WALL,'finish/hq_waiting')
        p.fill(x+10,-460,408,x+11,-460,412,'minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]','finish/hq_waiting')
    for i,z in enumerate((10,70,130,190,232)):
        p.match((118,-439,z,118,-439,z),'minecraft:birch_wall_sign[facing=south,waterlogged=false]',AIR,'finish/signs')
        text_label('hangar_way/'+str(i),[118.5,-438.7,z+.01],'EVA CAGES  ↑   /   発令所  ↓',0,1.15)
    data=[d for d in load(OLD/'transit_plan.json')['platforms'] if d.get('mode')!='AIRPLANE']+load(R02/'extension_plan.json')['transit']['platforms']
    for d in data:
        s=Station(p,d);side=10 if d.get('compact') else 15
        for v in (-side,side):
            if s.horizontal:x,y,z=s.x+23.5,s.y+3.2,s.z+v+(-.025 if v>0 else 1.025)
            else:x,y,z=s.x+v+(-.025 if v>0 else 1.025),s.y+3.2,s.z+23.5
            yaw=(180 if v>0 else 0) if s.horizontal else (90 if v>0 else -90)
            # Route code remains in relief above; the actual station name reads at eye level.
            text_label(d['id']+'/'+str(v),[x,y,z],d['name']+'\n'+d['line']+'  /  乗換・出口',yaw,1.7)
    for key,sx,gx,rz in [('bay',740,650,1430),('hakone',-1670,-1610,-20)]:
        x0,x1,z0,z1=sx-100,sx+100,rz-380,rz-305;o='finish/airport/'+key
        # Retire old furniture and counter fragments that predate the new plan.
        selected={(cx,cz):{5} for cx in range(x0//16,x1//16+1) for cz in range(z0//16,z1//16+1)}
        for cx,cz,sy,pal,idx in iter_selected_sections(vox.WORLD,vox.DIM,selected):
            import numpy as np
            states=np.asarray(pal)[idx].reshape(16,16,16)
            for ly,lz,lx in np.argwhere(np.char.startswith(states,'another_furniture:dark_oak_chair')):
                x,y,z=cx*16+int(lx),sy*16+int(ly),cz*16+int(lz)
                if x0<x<x1 and z0+25<z<z1 and y==81:p.match((x,y,z,x,y,z),str(states[ly,lz,lx]),AIR,o+'/old_chairs')
        p.match((x0+1,81,z0+13,x1-1,82,z0+14),DARK,AIR,o+'/old_counters')
        for side in (-1,1):
            a,b=sorted((sx+side*18,sx+side*94));p.match((a,81,z0+13,b,82,z0+14),DARK,AIR,o+'/old_counters')
            for z in (z0+29,z0+43,z0+56):
                for x in (sx+side*30+3,sx+side*55+3,sx+side*80+3):
                    p.match((x,81,z,x,81,z),WALL,AIR,o+'/old_planters');p.match((x,82,z,x,82,z),'minecraft:flower_pot',AIR,o+'/old_planters')
            for c in range(3):
                cx=sx+side*(27+c*24);num=c+1 if side<0 else c+4
                p.match((cx,89,z0+15,cx,89,z0+15),'minecraft:birch_wall_sign[facing=south,waterlogged=false]',AIR,o+'/sign')
                text_label(key+'/checkin/'+str(num),[cx+.5,88.7,z0+15.03],f'{num:02d}   CHECK-IN\n搭乗手続き  /  F1',0,2.4)
        p.fill(sx-3,91,z0+29,sx+3,95,z0+29,AIR,o+'/departures_relief')
        p.match((sx,89,z0+29,sx,89,z0+29),'minecraft:birch_wall_sign[facing=north,waterlogged=false]',AIR,o+'/sign')
        text_label(key+'/departures',[sx+.5,92,z0+29.98],'DEPARTURES  /  出発\nF1  新箱根 ⇄ 箱根湾\nGATE 01   /   鉄道乗換 ↓',180,3)
        text_label(key+'/terminal',[sx+.5,92,z0-1.03],('箱根湾空港' if key=='bay' else '新箱根飛行場')+'\nTERMINAL 01',180,3.5)
    # Published labels use room names and useful level designations, not raw block Y.
    rooms=load(R02/'circulation_repair/places.json')['rooms']
    for r in rooms:
        x,y,z=r['entry'];east='/west/' in r['id']
        p.match((x+(1 if east else -1),y+2,z+2,x+(1 if east else -1),y+2,z+2),f'minecraft:birch_wall_sign[facing={"east" if east else "west"},waterlogged=false]',AIR,'finish/room_sign')
        text_label(r['id']+'/room',[x+(1.02 if east else -.02),y+2.4,z+2.5],r['label']+'\n'+r['purpose'], -90 if east else 90,1.2)
    p.meta['wayfinding_labels']=len(labels)
    (OUT/'wayfinding.json').write_text(json.dumps(labels,ensure_ascii=False,indent=2),encoding='utf-8')

def airport_cleanup(p):
    for sx,z0 in ((740,1050),(-1670,-400)):
        p.match((sx-99,81,z0+13,sx+99,82,z0+14),DARK,AIR,'finish/remaining_counter_fragments')

def access_repairs(p):
    from query_blocks import read_box
    source=Path(load(OUT/'source_manifest.json')['backup'])
    for b in current_plots():
        if not b['id'].startswith('airport/hakone/') or 'storeys' not in b:continue
        x0,x1,z0,z1=b['bounds'];f=b['floor']
        lo=(x0+1,f+1,z0+2);hi=(x0+9,f+b['storeys']*5-1,z0+10)
        before=read_box(source,vox.DIM,lo,hi);current=read_box(vox.WORLD,vox.DIM,lo,hi)
        for pos,state in before.items():
            if current[pos]!=state:p.match((*pos,*pos),current[pos],state,'hakone_tower/restore_verified_stair')
        p.meta['landmarks'].append(dict(id=b['id']+'/stair_restore',bounds=[lo,hi],source=str(source)))
    from quality_circulation import Network
    from regional_architecture import opening
    p.protect((89,-450,-58,97,-430,-46),'retained_cage_lift')
    net=Network(p)
    net.line((101,-50),(112,-50),-443,'hangar/formal_west_exit',5,4)
    net.line((101,-50),(101,-43),-443,'hangar/lift_return',5,4)
    net.line((93,-43),(112,-43),-443,'hangar/existing_lift_lobby',5,4,False)
    net.finish()
    # A three-metre portal in the former platform end guard is offset from
    # the track. A supported return reaches the existing south-facing lift.
    opening(p,108,-50,-443,'hangar/west_portal','west',3,4)
    p.fill(99,-445,-52,111,-444,-47,DARK,'hangar/cantilever_support')
    p.fill(98,-445,-50,104,-444,-42,DARK,'hangar/return_support')
    for z in (-52,-48):p.fill(108,-442,z,108,-439,z,GRAY,'hangar/portal_frame')
    p.fill(108,-438,-52,108,-438,-48,GRAY,'hangar/portal_frame')
    sign(p,109,-440,-48,['EVA ケイジ','エレベーター ←','LAUNCH OBSERVATION','B-40'], 'hangar/portal_sign','east')
    p.meta['landmarks'].append(dict(id='hangar/formal_west_exit',entry=[108,-442,-50],width=3))

def grade_edges(p):
    from collections import defaultdict,Counter
    from query_blocks import iter_selected_sections
    columns=load(OUT/'surface_grade_classification.json')['repair_columns'];selected=defaultdict(set)
    for x,y,z in columns:selected[x//16,z//16].update(range((y-16)//16,y//16+1))
    measured={(cx,cz,sy):(pal,idx) for cx,cz,sy,pal,idx in iter_selected_sections(vox.WORLD,vox.DIM,selected)}
    def state(x,y,z):
        pal,idx=measured[x//16,z//16,y//16];return pal[idx[((y&15)<<8)|((z&15)<<4)|(x&15)]]
    depths=Counter()
    for x,y,z in columns:
        if state(x,y,z) not in vox.AIR:continue
        base=next((yy for yy in range(y-1,y-17,-1) if state(x,yy,z) not in vox.AIR),None)
        if base is None:raise RuntimeError('Unbounded grade gap '+str((x,y,z)))
        depths[y-base]+=1
        for yy in range(base+1,y+1):
            desired='minecraft:grass_block[snowy=false]' if yy==y else 'minecraft:dirt' if yy>=y-3 else 'minecraft:stone'
            p.match((x,yy,z,x,yy,z),state(x,yy,z),desired,'ground/restore_measured_grade_edge')
    p.meta['grade_edge_columns']=columns;p.meta['depths']=dict(depths)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--part',choices=['structure','fittings','stations','underground','airports','surface','finish','airport_cleanup','access_repairs','grade_edges'],default='structure');ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    vox.OUT=OUT;p=Builder();globals()[a.part](p)
    if a.part in ('airports','finish'):
        for b in current_plots():
            if not b['id'].startswith('airport/hakone/') or 'storeys' not in b:continue
            x0,x1,z0,z1=b['bounds'];f=b['floor']
            p.protect((x0,f+1,z0,x1,f+b['storeys']*5+5,z1),'retained_hakone_tower')
    if a.apply:
        from query_blocks import iter_block_entities
        if p.ops:
            lo=tuple(min(o.box[i] for o in p.ops) for i in range(3));hi=tuple(max(o.box[i+3] for o in p.ops) for i in range(3))
            for pos,be in iter_block_entities(vox.WORLD,vox.DIM,lo,hi,selected_chunks=p.by_chunk):
                if str(be['id']) not in ('minecraft:sign','minecraft:hanging_sign'):p.protect((*pos,*pos),'retained/'+str(be['id']))
        receipt=p.apply(a.part+'_details' if a.part!='structure' else 'structure_repairs')
        if a.part=='structure':(vox.WORLD/'regional_quality_r03_structures.json').write_text(json.dumps(dict(cropped=CROPPED,receipt=receipt),indent=2),encoding='utf-8')
        if a.part=='finish':(vox.WORLD/'regional_wayfinding.json').write_bytes((OUT/'wayfinding.json').read_bytes())
    else:p.save_plan(a.part+'_details')

if __name__=='__main__':main()
