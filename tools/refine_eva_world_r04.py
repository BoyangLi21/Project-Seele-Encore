"""Current-save R04 facilities: measured, reversible additions and repairs."""
from pathlib import Path
from collections import defaultdict
import argparse,json,math
import regional_voxels as vox
from quality_structures import Builder,walk,CASES
from regional_architecture import AIR,DARK,WALL,WHITE,GLASS,FLOOR,LIGHT,STEEL,RED,stairs,box_room,opening,furnished_room
from query_blocks import iter_block_entities

ROOT=vox.ROOT;OUT=ROOT/'artifacts/world_motion_r04';load=lambda p:json.loads(p.read_text(encoding='utf-8'))
GRAY='minecraft:gray_concrete';BLACK='minecraft:black_concrete'

def roof(p):
    o='r04/hangar_roof'
    p.protect((88,-450,-59,99,-361,-45),'retained_cage_lift')
    # The new lid sits above the original crane rails and upper personnel deck.
    p.fill(-46,-355,-142,110,-354,-56,GRAY,o)
    p.fill(-46,-353,-142,110,-353,-142,DARK,o)
    p.fill(-46,-353,-56,110,-353,-56,DARK,o)
    for x in (-46,110):
        p.fill(x,-365,-142,x,-354,-56,WALL,o+'/perimeter')
    for z in (-142,-56):
        p.fill(-46,-365,z,110,-356,z,WALL,o+'/perimeter')
        p.fill(-43,-362,z,107,-359,z,GLASS,o+'/clerestory')
    for x in (-44,-33,8,10,50,52,93,108):
        for z in (-139,-57):p.fill(x,-443,z,x+1,-356,z+1,'minecraft:polished_basalt[axis=y]',o+'/structural_pier')
    for z in range(-137,-59,13):
        p.fill(-44,-357,z,108,-356,z+1,STEEL,o+'/roof_beam')
        for x in (-20,21,63):p.fill(x,-356,z+4,x+15,-356,z+4,LIGHT,o+'/recessed_light')
    for x in (-12,30,72):
        p.fill(x-7,-353,-110,x+7,-351,-96,WALL,o+'/ventilation')
        for z in range(-108,-97,2):p.fill(x-5,-350,z,x+5,-350,z,'minecraft:iron_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]',o+'/ventilation')
    p.meta['roof']=dict(bounds=[-46,-355,-142,110,-354,-56],covers=['three wet cages','upper boarding/crane volume'],lowest_new_ceiling=-357)

def pyramid(p):
    from quality_circulation import Network
    # Existing command equipment, old rooms and all elevator axes remain in place.
    p.protect((-2,-444,244,60,-389,366),'original_command_module')
    p.protect((-32,-466,260,88,-437,340),'accepted_lower_tv_rooms')
    p.protect((5,-351,297,55,-311,344),'commander_office')
    for x,z,lo,hi in [(12,253,-567,-403),(28,321,-391,-334),(130,273,-450,90),(72,273,-570,-438)]:p.protect((x-5,lo,z-5,x+5,hi,z+5),'retained_lift')
    old=load(ROOT/'artifacts/world_quality_r02/circulation_repair/places.json')
    for r in old['rooms']:
        a,b,c,d=r['bounds'];f=r['floor'];p.protect((a,f,c,b,f+9,d),'accepted_room/'+r['id'])
    programmes=[('計算機運用室','ANALYSIS'),('技術記録室','ARCHIVE'),('交替勤務室','QUARTERS'),('作戦資料室','BRIEFING'),('通信管制室','ANALYSIS'),('医療支援室','MEDICAL'),('機材整備室','SUPPLIES'),('職員食堂','CAFETERIA')]
    tiers=[(-435,-54,112,407),(-421,-43,104,400),(-407,-35,95,394),(-393,-25,None,384)]
    net=Network(p);n=0
    def room(bounds,f,side):
        nonlocal n
        label,purpose=programmes[n%len(programmes)];n+=1;o=f'r04/pyramid/{-f}/{n:02d}'
        furnished_room(p,bounds,f,o,label,purpose,exit_side=side)
        x0,x1,z0,z1=bounds;ez=(z0+z1)//2;ex=x1 if side=='east' else x0
        gallery=-5 if side=='east' else 76
        if side in ('east','west'):
            net.line((ex-2 if side=='east' else ex+2,ez),(gallery,ez),f,o+'/door',3,3,False)
        walk(o+'/threshold',[ex+(-2.5 if side=='east' else 2.5),f+1,ez+.5],[gallery+.5,f+1,ez+.5])
    for f,left,right,south in tiers:
        for z0,z1 in [(268,293),(301,326),(334,359)]:room((left,-8,z0,z1),f,'east')
        if right is not None:
            for z0,z1 in [(272,296),(304,330)]:room((80,right,z0,z1),f,'west')
        for x0,x1 in [(left+5,-7),(2,42)]:
            # Southern programme rooms use a northern opening to the rear concourse.
            label,purpose=programmes[n%len(programmes)];n+=1;o=f'r04/pyramid/{-f}/{n:02d}'
            furnished_room(p,(x0,x1,377,south),f,o,label,purpose,exit_side='east')
            p.fill(x1,f+1,(377+south)//2-1,x1,f+3,(377+south)//2+1,WALL,o+'/retire_side_door')
            cx=(x0+x1)//2;opening(p,cx,377,f,o,'north',3,3)
            p.meta['rooms'][-1]['entry']=[cx,f+1,377]
            net.line((cx,379),(cx,371),f,o+'/north_entry',3,3,False)
        net.line((-5,274),(-5,371),f,f'r04/pyramid/{f}/west_gallery',3,4)
        net.line((-5,371),(76,371),f,f'r04/pyramid/{f}/rear_gallery',5,4)
        net.line((76,282),(76,371),f,f'r04/pyramid/{f}/east_gallery',3,4)
        net.line((69,367),(76,367),f,f'r04/pyramid/{f}/stair_exit',3,3,False)
    for f in (-379,-365):
        west=-15 if f==-379 else -5
        # Upper rings fit the narrowing shell, clear of the office and its lift.
        defs=[((west,6,302,332),'機関監視室','ANALYSIS'),((2,23,348,364),'通信中継室','ANALYSIS'),((31,52,348,364),'当直準備室','QUARTERS'),((10,50,286,298),'光学監視室','ANALYSIS')]
        for (x0,x1,z0,z1),label,purpose in defs:
            n+=1;o=f'r04/pyramid/{-f}/{n:02d}';furnished_room(p,(x0,x1,z0,z1),f,o,label,purpose,exit_side='east')
            # Door to a small clear edge aisle, away from the room furniture.
            if z0==348:
                ez=(z0+z1)//2;p.fill(x1,f+1,ez-1,x1,f+3,ez+1,WALL,o+'/retire_side_door')
                cx=(x0+x1)//2;opening(p,cx,z1,f,o,'south',3,3);p.meta['rooms'][-1]['entry']=[cx,f+1,z1]
                net.line((cx,z1-2),(cx,367),f,o+'/entry',3,3,False)
            elif z0==286:
                ez=(z0+z1)//2;p.fill(x1,f+1,ez-1,x1,f+3,ez+1,WALL,o+'/retire_side_door')
                opening(p,10,z1-3,f,o,'west',3,3);p.meta['rooms'][-1]['entry']=[10,f+1,z1-3]
                net.line((12,z1-3),(10,z1-3),f,o+'/entry',3,3,False)
            else:net.line((4,317),(10,317),f,o+'/entry',3,3,False)
        net.line((10,295),(10,344),f,f'r04/pyramid/{f}/upper_west_gallery',3,4)
        net.line((10,344),(-1,344),f,f'r04/pyramid/{f}/upper_turn',3,4)
        net.line((-1,344),(-1,367),f,f'r04/pyramid/{f}/upper_return',3,4)
        net.line((-1,367),(69,367),f,f'r04/pyramid/{f}/upper_south_gallery',3,4)
    # Complete all slabs before cutting the switchback stairs through them.
    for f in range(-449,-364,14):
        p.fill(62,f,350,72,f,368,FLOOR,'r04/pyramid/stair_core')
        h=8 if f==-365 else 12
        for x in (61,73):p.fill(x,f+1,350,x,f+h,368,WALL,'r04/pyramid/stair_wall')
        p.fill(62,f+1,349,72,f+h,349,WALL,'r04/pyramid/stair_wall')
        p.fill(62,f+1,369,72,f+h,369,WALL,'r04/pyramid/stair_wall')
    net.line((69,375),(69,367),-449,'r04/pyramid/existing_upper_handoff',3,3)
    net.finish()
    for f in range(-449,-365,14):
        p.fill(62,f+7,354,72,f+7,357,FLOOR,'r04/pyramid/mid_landing')
        p.fill(62,f+8,354,72,f+11,357,AIR,'r04/pyramid/mid_landing')
        stairs(p,64,364,f,7,'north','r04/pyramid/flight_a',3,'owned')
        stairs(p,69,357,f+7,7,'south','r04/pyramid/flight_b',3,'owned')
        p.fill(62,f+14,364,72,f+14,368,FLOOR,'r04/pyramid/top_landing')
        p.fill(62,f+15,364,72,f+18,368,AIR,'r04/pyramid/top_landing')
        walk(f'r04/flight/{f}/a',[64.5,f+1,366.5],[64.5,f+8,356.5])
        walk(f'r04/flight/{f}/mid',[64.5,f+8,355.5],[69.5,f+8,355.5])
        walk(f'r04/flight/{f}/b',[69.5,f+8,355.5],[69.5,f+15,365.5])
    p.fill(62,-356,350,72,-356,368,DARK,'r04/pyramid/stair_roof')
    # R43: the retained under-stair floors are now service vestibules, linked
    # to the stationary crossing in the east gallery rather than orphaned.
    for f in (-435,-421,-407,-393):
        p.fill(72,f+1,355,72,f+3,356,AIR,'r43/pyramid/east_stair_vestibule_port')
    p.meta['new_rooms']=n;p.meta['new_floor_walk_levels']=[-434,-420,-406,-392,-378,-364]

def dogma(p):
    from quality_circulation import Network
    o='r04/terminal_dogma';p.protect((6,-574,242,18,-557,267),'retained_secure_lift_landing')
    p.protect((66,-630,266,79,-529,281),'retained_central_dogma_shaft')
    # Large dark containment chamber: the entry gallery overlooks open LCL.
    p.fill(-38,-630,265,98,-529,403,'minecraft:deepslate_tiles',o+'/pressure_shell')
    p.fill(-35,-627,268,95,-533,400,AIR,o+'/chamber')
    p.fill(-35,-532,268,95,-532,400,BLACK,o+'/ceiling')
    p.fill(-35,-627,268,95,-603,400,'minecraft:deepslate',o+'/bed')
    p.fill(-34,-602,269,94,-601,399,'projectseele:lcl[level=0]',o+'/LCL_lake')
    for x in (-35,95):
        for z in range(274,398,12):
            p.fill(x,-600,z,x,-534,z+1,GRAY,o+'/wall_rib')
            p.put(x,-576,z,'minecraft:light[level=9,waterlogged=false]',o+'/indirect_light')
    for z in (268,400):
        for x in range(-30,94,14):p.fill(x,-600,z,x+1,-534,z,GRAY,o+'/wall_rib')
    # A freestanding deep-red crucifix, positioned at the model's actual nail plane.
    p.fill(27,-623,359,33,-548,362,RED,o+'/cross_stem')
    p.fill(-2,-569,359,62,-564,362,RED,o+'/cross_arm')
    for x in (26,34):p.fill(x,-623,360,x,-548,361,GRAY,o+'/cross_backbone')
    # Main front gallery is shallow, so it does not conceal Lilith's lower body.
    p.fill(-34,-569,269,94,-567,294,DARK,o+'/arrival_gallery')
    p.fill(-34,-566,269,94,-559,294,AIR,o+'/arrival_clearance')
    for x0,x1 in [(-28,18),(42,88)]:p.fill(x0,-566,295,x1,-565,295,'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]',o+'/front_guard')
    # Narrow observation tongue and side maintenance perimeter leave the lake open.
    p.fill(23,-568,294,37,-567,305,DARK,o+'/viewing_platform')
    for x in (22,38):p.fill(x,-566,296,x,-565,306,'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]',o+'/view_guard')
    p.fill(23,-566,306,37,-565,306,'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]',o+'/view_guard')
    for x0,x1 in [(-34,-29),(89,94)]:
        p.fill(x0,-570,285,x1,-567,393,DARK,o+'/side_gallery')
        xx=x1+1 if x0<0 else x0-1;p.fill(xx,-566,296,xx,-565,393,'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]',o+'/side_guard')
    p.fill(-34,-569,388,94,-567,396,DARK,o+'/rear_gallery')
    for x in range(-28,90,16):
        p.put(x,-566,273,'minecraft:light[level=10,waterlogged=false]',o+'/gallery_light')
        p.put(x,-566,391,'minecraft:light[level=7,waterlogged=false]',o+'/gallery_light')
    # Controlled entry retains its existing lift datum and a deliberate sequence of gates.
    net=Network(p);net.line((12,258),(12,280),-567,o+'/lift_entry',5,5)
    net.line((12,280),(30,280),-567,o+'/vestibule',7,5)
    net.finish()
    for z in (268,275):
        for x in (8,16):p.fill(x,-566,z,x,-562,z,STEEL,o+'/pressure_frame')
        p.fill(8,-561,z,16,-561,z,STEEL,o+'/pressure_frame')
    p.sign(10,-563,279,['TERMINAL DOGMA','最終教義','最高機密 / LCL','NERV'],o,'south')
    for name,a,b in [('front',[12.5,-566,270.5],[12.5,-566,280.5]),('turn',[12.5,-566,280.5],[30.5,-566,280.5]),('view',[30.5,-566,280.5],[30.5,-566,303.5]),('west',[-30.5,-566,291.5],[-30.5,-566,391.5]),('east',[91.5,-566,291.5],[91.5,-566,391.5]),('rear',[-30.5,-566,392.5],[91.5,-566,392.5])]:walk(o+'/'+name,a,b)
    p.meta['dogma']=dict(bounds=[-38,-630,265,98,-529,403],lcl_y=-601,specimen_anchor=[30,-600,355],specimen_scale=1.65,front_gallery_y=-566)

def junctions(p):
    # Measured furniture edges and a retired wall, not the retained gate at Z=257.
    for f,z in [(-407,313),(-407,346),(-393,280)]:
        p.fill(-13,f+1,z-1,-7,f+3,z+1,AIR,'r04/clear_room_door_aisle')
    # This movable bed was protected as a block entity in the initial pass.
    p.put(-11,-392,279,AIR,'r04/relocate_entry_bed')
    p.put(-11,-392,280,AIR,'r04/relocate_entry_bed')
    p.bed(-17,-392,280,'r04/relocate_entry_bed',color='light_gray')
    p.fill(10,-569,264,14,-567,267,DARK,'r04/dogma_entry_support')
    p.fill(10,-566,264,14,-562,267,AIR,'r04/dogma_entry_opening')
    p.fill(28,-566,284,32,-562,286,AIR,'r04/dogma_view_opening')
    for x in (-28,88):
        p.fill(x,-566,389,x,-565,395,AIR,'r04/dogma_rear_guard_return')
    p.meta['fixes']=['three room entry aisles','supported Dogma entry south of retained gate','observation door','rear perimeter junctions']

def details(p):
    from quality_structures import Station
    from refine_world_quality_r03 import corridor_detail,replace_seats
    old=ROOT/'artifacts/world_expansion_20260907';r02=ROOT/'artifacts/world_quality_r02'
    platforms=[d for d in load(old/'transit_plan.json')['platforms'] if d.get('mode')!='AIRPLANE']+load(r02/'extension_plan.json')['transit']['platforms']
    labels=[];plates=[]
    colors={'C1':'#61b88a','R1':'#e1b260','A1':'#6baad6','S1':'#b391ca','U1':'#ecb349','U2':'#df755d'}
    for d in platforms:
        s=Station(p,d);f=s.y;h=s.half;side=10 if d.get('compact') else 15;o=s.owner+'/r04'
        for v in (-4,4):
            a=s.xyz(-h+5,f,v);b=s.xyz(h-5,f,v)
            for state in (FLOOR,'minecraft:smooth_quartz'):p.match((*a,*b),state,'minecraft:yellow_terracotta',o+'/tactile_edge')
        for v in (-side,side):
            facing=('north' if v>0 else 'south') if s.horizontal else ('west' if v>0 else 'east');yaw={'south':0,'north':180,'west':90,'east':270}[facing]
            inside=v-(1 if v>0 else -1)
            for u in (-h+18,h-18):
                if -27<u<12:continue
                # Flush wall panels keep all platform circulation and train clearance.
                a=s.xyz(u-7,f+3,v);b=s.xyz(u+7,f+6,v)
                for state in (WALL,GLASS,WHITE):p.match((*a,*b),state,WHITE,o+'/enamel_sign_back')
                pos=list(s.xyz(u+.5,f+4.3,v+.5));pos[2 if s.horizontal else 0]+=(-.515 if v>0 else .515)
                labels.append(dict(id=o+f'/{u}/{v}',position=pos,yaw=yaw,scale=1.7,lineWidth=400,text=[dict(text=d['line']+'   '+d['name']+'\n',color=colors.get(d['line'],'#9ac19a'),bold=True),dict(text='← 乗換 Transfer     出口 Exit →',color='#242a30')]))
            # Slim suspended emergency wayfinding above, clear of bridge users.
            for u in (-h+10,h-10):
                x,y,z=s.xyz(u,f+7,inside)
                p.sign(x,y,z,['非常口 / EXIT','避難方向 →','線路内立入禁止','STAFF / HELP'],o,facing)
        p.meta['landmarks'].append(dict(id=o,center=d['center'],style='Japanese enamel route boards, tactile platform edge, emergency wayfinding'))
    for r in load(OUT/'pyramid/places.json')['rooms']:
        x0,x1,z0,z1=r['bounds'];f=r['floor'];o=r['id']+'/r04_detail'
        replace_seats(p,(x0+1,f+1,z0+1,x1-1,f+1,z1-1),o)
        for z in (z0,z1):
            p.match((x0+1,f+1,z,x1-1,f+1,z),WALL,GRAY,o+'/skirting')
            for x in range(x0+5,x1-2,8):p.match((x,f+2,z,x,f+6,z),WALL,'minecraft:smooth_quartz',o+'/panel_joint')
        cx=x0+4
        p.match((cx-1,f+4,z0,cx+1,f+6,z0),WALL,WHITE,o+'/plaque_back')
        plates.append(dict(id=o,position=[cx+.5,f+5.5,z0+1.015],yaw=0,size=2.5))
        labels.append(dict(id=o+'/room_label',position=[(x0+x1)/2+.5,f+7,z0+1.025],yaw=0,scale=1.3,lineWidth=300,text=dict(text=r['label']+' / '+r['purpose'],color='#e5d6bd')))
    for f in (-435,-421,-407,-393):
        for x in (-5,76):corridor_detail(p,x-1,x+1,282,371,f,4,f'r04/pyramid/gallery/{f}/{x}')
        corridor_detail(p,-5,76,369,373,f,4,f'r04/pyramid/rear/{f}')
    for ident,sx,rz,destination in [('bay',740,1430,'新箱根 SHIN-HAKONE'),('hakone',-1670,-20,'箱根湾 HAKONE BAY')]:
        z0=rz-380;o='r04/airport/'+ident
        labels.append(dict(id=o+'/departures',position=[sx+.5,93.6,z0+29.98],yaw=180,scale=2.0,lineWidth=430,text=[dict(text='出発 DEPARTURES\n',color='#f1c45d',bold=True),dict(text='F1   '+destination+'\n搭乗口 GATE 01',color='#eeeeea')]))
        for xoff in (-82,82):
            labels.append(dict(id=o+f'/services/{xoff}',position=[sx+xoff,85.5,z0+1.02],yaw=0,scale=1.25,lineWidth=340,text=dict(text='案内 Information  •  手荷物 Baggage\n鉄道 Rail  ↓   出口 Exit  ↓',color='#34424c')))
        # Flush, coloured route inlays sit on the existing terminal datum.
        for xoff in (-8,8):
            for state in (FLOOR,'minecraft:polished_andesite'):
                p.match((sx+xoff,80,z0+4,sx+xoff,80,z0+63),state,'minecraft:blue_terracotta',o+'/rail_wayfinding')
    # Existing entrance and arrival feature walls receive restrained square plaques.
    for ident,x,y,z,size,yaw in [('public_gate',-391,87,699.98,6,180),('public_security',-383,89,732.985,5,180),('secure_lobby',-383,89,734.02,4,0),('arrival',-381,-460,711.02,4,0),('pyramid_lobby',4,-456,394.02,4,0)]:
        plates.append(dict(id=ident,position=[x,y,z],size=size,yaw=yaw))
    p.meta['labels']=labels;p.meta['plates']=plates

def support_repair(p):
    from query_blocks import read_box
    import gzip
    with gzip.open(OUT/'pyramid/ops.json.gz','rt',encoding='utf-8') as fp:ops=json.load(fp)
    points=set()
    for d in ops:
        x,y,z,xx,yy,zz=d['box']
        if d['state']==DARK and d['mode']=='air' and x==xx and z==zz and y==-465:
            points.update((x,v,z) for v in range(y,min(yy,-436)+1))
    source=Path(load(OUT/'source_manifest.json')['backup'])
    lo=tuple(min(q[i] for q in points) for i in range(3));hi=tuple(max(q[i] for q in points) for i in range(3))
    original=read_box(source,vox.DIM,lo,hi);current=read_box(vox.WORLD,vox.DIM,lo,hi)
    restored=[]
    for q in sorted(points):
        before=original.get(q,AIR)
        if current.get(q)==DARK and before in (AIR,'minecraft:cave_air','minecraft:void_air'):
            p.put(*q,before,'r04/retire_pier_below_existing_ceiling');restored.append(q)
    # New lower rooms bear on shallow transfer beams above the old Y=-440 ceilings.
    for r in load(OUT/'pyramid/places.json')['rooms']:
        if r['floor']!=-435:continue
        x0,x1,z0,z1=r['bounds'];o=r['id']+'/transfer_beam'
        for z in (z0,z1):p.fill(x0,-438,z,x1,-436,z,STEEL,o,'air')
        for x in (x0,x1):p.fill(x,-438,z0,x,-436,z1,STEEL,o,'air')
    # Open both sides of the T where the added core meets the existing upper return.
    p.fill(67,-448,373,72,-445,377,AIR,'r04/old_new_stair_T_junction')
    p.fill(67,-449,373,72,-449,377,FLOOR,'r04/old_new_stair_T_junction')
    p.meta['restored_new_pier_cells']=len(restored)

def visual_finish(p):
    # Human-eye sight lines over a one-metre rail, with quiet TV-style surfaces.
    for state in ['minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]','minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]']:
        p.match((-34,-565,269,94,-565,396),state,AIR,'r04/dogma/sightline_rail')
    p.match((-34,-567,269,94,-567,396),DARK,GRAY,'r04/dogma/matte_gallery')
    for x in (-36,-35,95,96):p.match((x,-600,268,x,-533,400),'minecraft:deepslate_tiles',BLACK,'r04/dogma/quiet_wall')
    for z in (267,268,400,401):p.match((-35,-600,z,95,-533,z),'minecraft:deepslate_tiles',BLACK,'r04/dogma/quiet_wall')
    p.match((-2,-623,359,62,-548,362),RED,'minecraft:red_concrete','r04/dogma/crucifix')
    for r in load(OUT/'pyramid/places.json')['rooms']:
        x0,x1,z0,z1=r['bounds'];f=r['floor'];o=r['id']+'/inset_lighting'
        p.match((x0+1,f+8,z0+1,x1-1,f+8,z1-1),LIGHT,AIR,o)
        p.match((x0,f+9,z0,x1,f+9,z1),DARK,GRAY,o)
        for x in range(x0+5,x1-3,9):
            p.match((x,f+9,z0+4,x,f+9,z1-4),DARK,LIGHT,o)
            p.match((x,f+9,z0+4,x,f+9,z1-4),GRAY,LIGHT,o)
    p.meta['finish']='lower Dogma rails, matte surfaces, inset room lighting, merged airport departure boards'

def workstations(p):
    rooms=load(OUT/'pyramid/places.json')['rooms']+load(ROOT/'artifacts/world_quality_r02/circulation_repair/places.json')['rooms']
    for r in rooms:
        if r['purpose'] in ('MEDICAL','QUARTERS','BRIEFING','CAFETERIA','ARCHIVE','SEELE LINK','LOCKERS','SUPPLIES'):continue
        x0,x1,z0,z1=r['bounds'];f=r['floor']
        for x in range(x0+5,x1-3,6):
            for z in range(z0+5,z1-3,7):p.match((x,f+2,z,x,f+2,z),'minecraft:black_stained_glass','projectseele:nerv_workstation[facing=south]',r['id']+'/CRT')
    for sx,rz in [(740,1430),(-1670,-20)]:
        for side in (-1,1):
            for c in range(3):
                cx=sx+side*(27+c*24)
                for dx in (-4,3):p.match((cx+dx,82,rz-365,cx+dx,82,rz-365),'minecraft:green_stained_glass','projectseele:nerv_workstation[facing=north]','r04/airport/CRT')
    p.meta['programme']='solid CRT cabinets with original monochrome screen texture, replacing exact placeholder glass blocks'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('part',choices=['roof','pyramid','dogma','junctions','details','support_repair','visual_finish','workstations']);ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    vox.OUT=OUT;p=Builder();globals()[a.part](p)
    if p.ops:
        lo=tuple(min(o.box[i] for o in p.ops) for i in range(3));hi=tuple(max(o.box[i+3] for o in p.ops) for i in range(3))
        for pos,be in iter_block_entities(vox.WORLD,vox.DIM,lo,hi,selected_chunks=p.by_chunk):
            if a.part=='junctions' and pos in [(-11,-392,279),(-11,-392,280),(-17,-392,279),(-17,-392,280)] and str(be['id'])=='minecraft:bed':continue
            p.protect((*pos,*pos),'retained_equipment/'+str(be['id']))
    p.apply(a.part) if a.apply else p.save_plan(a.part)
    if a.apply and a.part=='dogma':(vox.WORLD/'regional_tv_detail_r04.json').write_text(json.dumps(dict(schema=1,dogma_complete=True,source='world_motion_r04')),encoding='utf-8')
    if a.apply and a.part=='details':
        target=vox.WORLD/'regional_wayfinding.json';labels=load(target);ids={d['id'] for d in p.meta['labels']};labels=[d for d in labels if d['id'] not in ids]+p.meta['labels'];target.write_text(json.dumps(labels,ensure_ascii=False),encoding='utf-8')
        (ROOT/'run/projectseele-local-maps/r04_wall_plates.json').write_text(json.dumps(p.meta['plates']),encoding='utf-8')
    if a.apply and a.part=='visual_finish':
        target=vox.WORLD/'regional_wayfinding.json';labels=load(target)
        for d in labels:
            if d['id'] in ('bay/departures','hakone/departures'):
                name='新箱根 SHIN-HAKONE' if d['id'].startswith('bay') else '箱根湾 HAKONE BAY'
                d['position'][1]=92;d['scale']=3;d['lineWidth']=430
                d['text']=[dict(text='出発  DEPARTURES\n',color='#f1c45d',bold=True),dict(text='F1   '+name+'\nGATE 01   /   鉄道乗換 ↓',color='#eeeeea')]
        labels=[d for d in labels if d['id'] not in ('r04/airport/bay/departures','r04/airport/hakone/departures')]
        target.write_text(json.dumps(labels,ensure_ascii=False),encoding='utf-8')
    if CASES:(OUT/(a.part+'_walk_cases.json')).write_text(json.dumps(CASES,ensure_ascii=False),encoding='utf-8')

if __name__=='__main__':main()
