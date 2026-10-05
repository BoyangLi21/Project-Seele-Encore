"""NERV arrival chain and TV facility programmes, in the approved regional frame.

The original TV names describe programmes, not a claimed official floor plan.
Existing command/MAGI/Dogma rooms remain in place; the new circulation lands
at measured wall openings outside their furniture and operating equipment.
"""
from regional_architecture import *


def hall(p,b,floor,name,height=7,doors=(),mode='new'):
    box_room(p,b,floor,height,name,WALL,mode)
    x0,x1,z0,z1=b
    if floor<-466:p.fill(x0,-490,z0,x1,floor-1,z1,'minecraft:deepslate_bricks',name,'air')
    elif floor<0:
        for x in (x0,x1):
            for z in sorted(set([z0,z1]+list(range(z0,z1,16)))):
                p.fill(x,-490,z,x,floor-1,z,'minecraft:deepslate_bricks',name,'air')
    for x,z,side,width in doors:opening(p,x,z,floor,name,side,width,4,mode)
    p.meta['walk_nodes'].append(dict(id=name,bounds=b,floor=floor))


def corridor(p,a,b,floor,name,width=7,height=6,mode='air'):
    x,z=a;xx,zz=b;r=width//2
    bounds=(min(x,xx)-r,max(x,xx)+r,min(z,zz)-r,max(z,zz)+r)
    hall(p,bounds,floor,name,height,mode=mode)
    if x==xx:
        for end in (min(z,zz)-r,max(z,zz)+r):opening(p,x,end,floor,name,'north',width-2,height-1,mode)
    else:
        for end in (min(x,xx)-r,max(x,xx)+r):opening(p,end,z,floor,name,'east',width-2,height-1,mode)
    return bounds


def walkway(p,x,z0,z1,floor,name):
    corridor(p,(x,z0),(x,z1),floor,name,11,7)
    for z in range(min(z0,z1)+1,max(z0,z1)):
        for xx,reverse in [(x-2,False),(x+2,True)]:
            for lane,side in [(0,'left'),(1,'right')]:
                p.put(xx+lane,floor,z,'mtr:escalator_step[direction='+str(reverse).lower()+',facing=north,orientation=flat,side='+side+',status=true]',name)
    for z in range(min(z0,z1)+12,max(z0,z1)-10,32):
        p.fill(x-5,floor+2,z,x-5,floor+4,z+10,GLASS,name)
        p.fill(x+5,floor+2,z,x+5,floor+4,z+10,GLASS,name)
    p.meta['landmarks'].append(dict(id=name,style='native_moving_walkway',from_pos=[x,floor+1,z0],to=[x,floor+1,z1]))


def gateway(p):
    name='nerv/gateway';p.grade(-420,695,-292,819,80,name,18)
    # Heavy entrance massing, red datum stripe and a sheltered public forecourt.
    hall(p,(-411,-300,700,733),80,name+'/public',15,[(-360,700,'north',15)])
    hall(p,(-389,-329,733,778),80,name+'/secure',16,[(-360,733,'north',9)])
    p.fill(-411,90,700,-300,91,700,RED,name)
    p.fill(-393,96,707,-327,100,714,DARK,name)
    for x in (-400,-310):p.fill(x,81,702,x,95,730,'minecraft:polished_basalt[axis=y]',name)
    p.sign(-360,94,699,['NERV','第３新東京市','GEOFRONT ACCESS','CENTRAL GATE'],name)
    for x in (-402,-393,-321,-312):bench(p,x,711,80,name)
    # Reception issues the already existing employee card; no new duplicate item.
    p.fill(-407,81,722,-395,82,722,DARK,name)
    p.chest(-406,81,725,[('projectseele:nerv_employee_card',1),('projectseele:nerv_employee_card',1),('minecraft:bread',16)],name)
    p.sign(-401,84,721,['受付 / RECEPTION','職員証の受取','EMPLOYEE CARD',''],name)
    p.fill(-368,81,733,-352,86,733,'minecraft:gray_stained_glass',name)
    p.put(-354,82,732,'minecraft:polished_blackstone_button[face=wall,facing=north,powered=false]',name)
    p.sign(-354,84,732,['入場 / SWIPE','職員証を手に持つ','HOLD STAFF CARD',''],name)
    p.put(-354,82,734,'minecraft:polished_blackstone_button[face=wall,facing=south,powered=false]',name)
    # Shaft lining is outside the complete 15 x 15 capture footprint.
    p.fill(-369,-472,741,-351,97,759,'minecraft:deepslate_tiles',name)
    p.fill(-368,-468,742,-352,94,758,AIR,name)
    for y in (-466,81):
        p.fill(-381,y-1,735,-339,y-1,742,FLOOR,name)
        p.fill(-366,y,739,-354,y+5,742,AIR,name)
        p.fill(-363,y,741,-357,y+4,741,'minecraft:gray_stained_glass',name)
        p.put(-355,y+1,740,'minecraft:polished_blackstone_button[face=wall,facing=north,powered=false]',name)
        p.sign(-355,y+3,740,['直梯 / 呼出','NERV 地面入口' if y==81 else '地下都市 · 到达厅','本层呼梯 · 轿厢内选层',''],name)
        # Real controller BEs are installed and configured by the commissioner.
        p.put(-368,y,750,AIR,name)
    # Exactly one physical car, initially on the surface.
    box_room(p,(-367,-353,743,757),80,8,name+'/car','projectseele:nerv_machine_panel')
    # TV12 utility-cabin panel hierarchy, within the unchanged native box.
    # Roof-grid/lamp detail is a separate original root-owned model overlay.
    for x in (-367,-353):p.fill(x,83,743,x,83,757,'projectseele:nerv_structural_panel',name+'/car')
    for z in (743,757):p.fill(-367,83,z,-353,83,z,'projectseele:nerv_structural_panel',name+'/car')
    opening(p,-360,743,80,name+'/car','north',7,5,'new')
    for z in (747,750):
        p.put(-366,82,z,'minecraft:polished_blackstone_button[face=wall,facing=east,powered=false]',name)
        p.sign(-366,84,z,['GEOFRONT' if z==747 else 'TOKYO-3','','',''],name,'east')
    p.meta['landmarks'].append(dict(id=name,style='secure_native_elevator',axis=[-360,750],stops=[-466,81],size=[15,9,15],entry=[-360,81,700]))
    # The lower lobby is on the same walking datum as the rail platforms.
    hall(p,(-403,-315,710,741),-467,'nerv/arrival_lobby',14,[(-360,741,'south',9),(-315,726,'east',9)])
    corridor(p,(-309,726),(-309,766),-467,'nerv/arrival_platform_access',9,7,'new')
    corridor(p,(-309,768),(-330,768),-467,'nerv/arrival_platform_join',9,7,'new')
    opening(p,-330,770,-467,name,'south',7,5)
    p.sign(-346,-462,735,['地下到着ロビー','U1 : NERV 本部','本部・実験棟方面',''],name)
    surface_entry_checkpoint_r47(p)


def surface_entry_checkpoint_r47(p):
    """Complete real outer opening, not an isolated pair in an open hall."""
    import nbtlib,zlib
    from install_access_r44 import packed
    owner='nerv/gateway/complete_outer_checkpoint_r47'
    for x in range(-368,-351):
        for y in range(81,95):
            state='minecraft:barrier' if -363<=x<=-357 and y<=85 else 'projectseele:nerv_machine_edge' if x in(-368,-364,-356,-352) or y in(81,86,94) else 'projectseele:clear_glass'
            p.put(x,y,701,state,owner)
    reader=(-355,82,700);release=(-355,82,702);label='NERV · 地面入口闸门'
    p.put(*reader,'projectseele:nerv_access_reader[facing=north]',owner)
    p.put(*release,'minecraft:stone_button[face=wall,facing=south,powered=false]',owner)
    p.block_entities[reader]=nbtlib.Compound(dict(id=nbtlib.String('projectseele:nerv_access_reader'),x=nbtlib.Int(reader[0]),y=nbtlib.Int(reader[1]),z=nbtlib.Int(reader[2]),Gate=nbtlib.Long(packed((-363,81,701))),Exit=nbtlib.Long(packed(release)),Width=nbtlib.Int(7),Height=nbtlib.Int(5),Clearance=nbtlib.Int(1),Style=nbtlib.Int(1),DoorId=nbtlib.Int(zlib.crc32(label.encode())&0x7fffffff),AlongX=nbtlib.Byte(1),Linked=nbtlib.Byte(1),Label=nbtlib.String(label),OpenUntil=nbtlib.Long(0),SwipeAt=nbtlib.Long(-1),IndicateUntil=nbtlib.Long(0),Presented=nbtlib.Int(0),Status=nbtlib.Int(0),OffHand=nbtlib.Byte(0)))


def pyramid(p):
    # Base-level arrival hall connects the station to both populated wings.
    hall(p,(-34,94,393,430),-462,'hq/arrival_hall',11,[(-29,393,'north',5),(89,393,'north',5),(30,430,'south',9)],mode='air')
    for x in (-20,80):p.fill(x,-461,402,x,-453,422,'minecraft:polished_basalt[axis=y]','hq/arrival_hall','air')
    p.sign(30,-455,429,['NERV 本部','中央到着ホール','COMMAND / MEDICAL','RESEARCH / DOGMA'],'hq/arrival_hall','south')
    # Station floor -467 -> pyramid hall floor -462, outside the accepted rooms.
    corridor(p,(30,446),(30,475),-467,'hq/station_approach',11,9,'new')
    stairs(p,30,441,-467,5,'north','hq/arrival_stair',7,'owned')
    p.fill(26,-462,430,34,-462,437,FLOOR,'hq/arrival_stair','owned')
    p.fill(26,-461,430,34,-457,437,AIR,'hq/arrival_stair','owned')
    from regional_architecture import headquarters_arrival_stair_sides_r46
    headquarters_arrival_stair_sides_r46(p)
    opening(p,30,430,-462,'hq/hall_south_port','south',9,5)
    opening(p,30,475,-467,'hq/station_north_port','north',7,5)
    programmes=[('医療室','MEDICAL'),('職員休憩室','QUARTERS'),('記録保管室','ARCHIVE'),('食堂','CAFETERIA')]
    right=[('作戦会議室','BRIEFING'),('解析作業室','ANALYSIS'),('通信審議室','SEELE LINK'),('補給準備室','SUPPLIES')]
    for floor in (-462,-449):
        suffix='B2' if floor==-462 else 'B1'
        for side,x0,x1,rooms,exit_side in [('west',-67,-34,programmes,'east'),('east',94,127,right,'west')]:
            for i,(label,purpose) in enumerate(rooms):
                z0=263+i*32
                furnished_room(p,(x0,x1,z0,z0+27),floor,f'hq/{side}/{suffix}/{i+1}',label,purpose,exit_side=exit_side)
        for x in (-29,89):corridor(p,(x,271),(x,400),floor,f'hq/{suffix}/wing_{x}',9,7,'air')
        for i in range(4):
            z=276+i*32
            for a,b in [(-34,-32),(92,94)]:
                p.fill(a,floor,z-1,b,floor,z+1,FLOOR,'hq/room_threshold','owned')
                p.fill(a,floor+1,z-1,b,floor+3,z+1,AIR,'hq/room_threshold','owned')
    # Each wing has a return stair and exact handoff into an existing TV room.
    for x in (-29,89):
        stairs(p,x,380,-462,13,'north',f'hq/wing_stair_{x}',5,'owned')
        p.fill(x-2,-449,365,x+2,-449,368,FLOOR,'hq/stair_landing','owned')
        p.fill(x-2,-448,365,x+2,-444,368,AIR,'hq/stair_landing','owned')
    for x in (-26,82):
        p.fill(x-1,-448,287,x+1,-445,291,AIR,'hq/measured_existing_wing_port','owned')
        p.fill(x-1,-449,287,x+1,-449,291,FLOOR,'hq/measured_existing_wing_port','owned')
    # East wing transfer links the retained public lift and the new hangar walk.
    corridor(p,(89,254),(112,254),-449,'hq/east_transfer_lower',7,7,'air')
    stairs(p,112,254,-449,6,'north','hq/east_transfer_stair',5,'owned')
    corridor(p,(112,247),(123,247),-443,'hq/east_transfer_upper',9,7,'air')
    corridor(p,(123,247),(123,273),-443,'hq/public_lift_join',7,7,'air')
    p.fill(121,-442,271,124,-439,275,AIR,'hq/public_lift_measured_handoff','owned')
    walkway(p,118,-27,247,-443,'hq/hangar_moving_walkway')
    # Only these explicitly planned wall ports cut the pyramid shell.
    p.fill(114,-442,219,122,-437,238,AIR,'hq/hangar_shell_port','owned')
    p.fill(114,-443,219,122,-443,238,DARK,'hq/hangar_shell_port','owned')
    corridor(p,(118,-27),(140,-27),-443,'hangar/station_walk_join',9,7,'air')
    opening(p,118,-23,-443,'hangar/walkway_junction','south',7,5)
    p.fill(146,-442,-25,154,-438,-24,AIR,'hangar/platform_south_port','owned')


def labs_and_logistics(p):
    # Laboratory district: Pribnow/Sigma programme, isolated cells and a gallery.
    name='science/sigma';hall(p,(213,288,453,547),-467,name,24,[(250,547,'south',9)])
    p.sign(250,-448,548,['SIGMA UNIT','PRIBNOW BOX','SIMULATION / BIO-TEST','AUTHORIZED PERSONNEL'],name,'south')
    for i,z in enumerate((470,496,522)):
        box_room(p,(223,266,z-9,z+9),-467,16,name+f'/cell{i+1}',WHITE)
        p.fill(224,-464,z+9,265,-453,z+9,'minecraft:light_gray_stained_glass',name)
        # Abstract instrumented body-shaped test rigs, not additional live EVAs.
        p.fill(240,-466,z-5,248,-465,z+5,STEEL,name)
        p.fill(243,-464,z-1,245,-455,z+1,'minecraft:white_terracotta',name)
        p.fill(241,-455,z-2,247,-454,z+2,'minecraft:white_terracotta',name)
        p.fill(243,-453,z-1,245,-451,z+1,'minecraft:red_stained_glass',name)
        p.put(270,-465,z,'minecraft:iron_block',name);p.put(270,-464,z,'minecraft:black_stained_glass',name)
        opening(p,266,z,-467,name,'east',3,3,'new')
    corridor(p,(275,443),(275,552),-467,'science/cell_control_corridor',9,7,'new')
    corridor(p,(275,552),(292,552),-467,'science/station_link',9,7,'new')
    for i,(label,purpose) in enumerate([('同期解析室','ANALYSIS'),('隔離診察室','MEDICAL'),('資料保管庫','ARCHIVE')]):
        z=440+i*55
        furnished_room(p,(334,372,z,z+45),-467,'science/'+str(i),label,purpose,exit_side='west')
        p.fill(334,-490,z,372,-468,z+45,'minecraft:deepslate_bricks','science/foundation','air')
    corridor(p,(328,447),(328,608),-467,'science/east_corridor',9,7,'new')
    for z in (462,517,572):
        p.fill(331,-467,z-1,334,-467,z+1,FLOOR,'science/lab_threshold','owned')
        p.fill(331,-466,z-1,334,-463,z+1,AIR,'science/lab_threshold','owned')
    opening(p,295,565,-467,'science/platform_west','west',7,5)
    opening(p,325,565,-467,'science/platform_east','east',7,5)
    corridor(p,(89,399),(196,399),-462,'hq/science_link',9,7,'air')
    stairs(p,196,409,-467,5,'north','science/hq_access',5,'new')
    corridor(p,(196,410),(196,552),-467,'science/west_walk',9,7,'new')
    corridor(p,(196,552),(275,552),-467,'science/reception_walk',9,7,'new')
    # Technical services are a separate district, with accessible galleries.
    for i,(b,label,purpose) in enumerate([((181,248,93,139),'LCL 管理室','ANALYSIS'),((181,248,158,206),'資材保管庫','SUPPLIES'),((181,248,225,267),'電力管理室','ANALYSIS')]):
        furnished_room(p,b,-467,f'logistics/{i}',label,purpose)
        p.fill(b[0],-490,b[2],b[1],-468,b[3],'minecraft:deepslate_bricks','logistics/foundation','air')
    corridor(p,(259,100),(259,267),-467,'logistics/service_gallery',9,7,'new')
    for z in (116,182,246):
        p.fill(248,-467,z-1,256,-467,z+1,FLOOR,'logistics/room_threshold','owned')
        p.fill(248,-466,z-1,256,-463,z+1,AIR,'logistics/room_threshold','owned')
    corridor(p,(259,180),(282,180),-467,'logistics/station_walk',9,7,'new')
    opening(p,285,180,-467,'logistics/platform_west','west',7,5)
    for cx in (192,223):
        for z in (105,125):
            p.fill(cx-4,-466,z-4,cx+4,-458,z+4,STEEL,'logistics/lcl_tanks')
            p.fill(cx-3,-465,z-3,cx+3,-459,z+3,'minecraft:orange_stained_glass','logistics/lcl_tanks')
            p.fill(cx-2,-464,z-2,cx+2,-460,z+2,'minecraft:water[level=0]','logistics/lcl_tanks')
    p.meta['landmarks'].extend([dict(id='science/sigma',style='tv_programme_playable_interpretation',entry=[250,-466,548]),dict(id='logistics/service_gallery',entry=[259,-466,180])])


def build_underground(p):
    gateway(p);pyramid(p);labs_and_logistics(p)
