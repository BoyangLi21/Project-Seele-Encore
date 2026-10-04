"""Original TV-inspired architectural vocabulary, with usable rooms and stairs."""
from math import sin,cos,pi

AIR='minecraft:air';DARK='minecraft:polished_deepslate';WALL='minecraft:light_gray_concrete'
WHITE='minecraft:white_concrete';GLASS='minecraft:gray_stained_glass';FLOOR='minecraft:smooth_stone'
LIGHT='minecraft:sea_lantern';STEEL='minecraft:iron_block';RED='minecraft:red_terracotta'


def box_room(p,b,floor,height,owner,wall=WALL,mode='new'):
    x0,x1,z0,z1=b
    p.fill(x0+1,floor+1,z0+1,x1-1,floor+height-1,z1-1,AIR,owner,mode)
    p.fill(x0,floor,z0,x1,floor,z1,FLOOR,owner,mode)
    p.fill(x0,floor+height,z0,x1,floor+height,z1,DARK,owner,mode)
    for x in (x0,x1):p.fill(x,floor+1,z0,x,floor+height-1,z1,wall,owner,mode)
    for z in (z0,z1):p.fill(x0,floor+1,z,x1,floor+height-1,z,wall,owner,mode)
    for x in range(x0+4,x1,8):
        for z in range(z0+4,z1,8):p.put(x,floor+height-1,z,LIGHT,owner,mode)


def opening(p,x,z,floor,owner,facing='south',width=3,height=3,mode='owned'):
    dx,dz=(1,0) if facing in ('north','south') else (0,1)
    p.fill(x-dx*(width//2),floor+1,z-dz*(width//2),x+dx*(width//2),floor+height,z+dz*(width//2),AIR,owner,mode)


def door(p,x,z,floor,owner,facing='south',iron=False,mode='new'):
    for dy,half in ((1,'lower'),(2,'upper')):
        name='projectseele:city_personnel_door' if iron else 'minecraft:oak_door'
        p.put(x,floor+dy,z,f"{name}[facing={facing},half={half},hinge=left,open=false,powered=false]",owner,mode)



def headquarters_arrival_stair_sides_r46(p):
    """Finite real HQ stair sides; preserve all seven treads and clear lanes."""
    for x in (26,34):
        for z in range(437,442):
            top=-460-(z-437)
            p.fill(x,-465,z,x,top,z,'projectseele:clear_glass',
                   'hq/arrival_stair/complete_side_screen_r46','air')

def stairs(p,x,z,floor,rise,heading,owner,width=3,mode='new'):
    dx,dz={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}[heading]
    sx,sz=(-dz,dx)
    for i in range(rise):
        yy=floor+i+1;xx=x+dx*i;zz=z+dz*i
        for lane in range(-(width//2),width//2+1):
            a,b=xx+sx*lane,zz+sz*lane
            p.fill(a,yy+1,b,a,yy+4,b,AIR,owner,mode)
            p.put(a,yy,b,f'minecraft:polished_deepslate_stairs[facing={heading},half=bottom,shape=straight,waterlogged=false]',owner,mode)
            p.fill(a,floor,b,a,yy-1,b,DARK,owner,mode)
    return x+dx*rise,z+dz*rise,floor+rise


def street_light(p,x,z,floor,owner):
    p.put(x,floor,z,DARK,owner);p.fill(x,floor+1,z,x,floor+5,z,'minecraft:polished_basalt[axis=y]',owner)
    p.put(x,floor+6,z,LIGHT,owner);p.put(x,floor+7,z,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]',owner)


def bench(p,x,z,floor,owner,facing='south'):
    for xx in range(x-1,x+2):p.put(xx,floor+1,z,f'minecraft:dark_oak_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]',owner)


def building(p,b,floor,storeys,owner,style='residential',variant=0):
    x0,x1,z0,z1=b;cx=(x0+x1)//2
    if owner in ('tokyo_south/13-05','tokyo_south/13-06'):
        x1=152;b=(x0,x1,z0,z1)
    wall=['minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:smooth_sandstone','minecraft:gray_concrete'][variant%4]
    p.grade(x0-3,z0-3,x1+3,z1+5,floor,owner,margin=8)
    p.fill(x0,floor+1,z0,x1,floor+storeys*5,z1,AIR,owner)
    for level in range(storeys):
        y=floor+level*5
        p.fill(x0,y,z0,x1,y,z1,FLOOR,owner)
        for x in (x0,x1):p.fill(x,y+1,z0,x,y+4,z1,wall,owner)
        for z in (z0,z1):p.fill(x0,y+1,z,x1,y+4,z,wall,owner)
        for z in (z0,z1):
            for x in range(x0+3,x1-2,5):p.fill(x,y+2,z,min(x+2,x1-2),y+3,z,GLASS,owner)
        for x in (x0,x1):
            for z in range(z0+3,z1-2,5):p.fill(x,y+2,z,x,y+3,min(z+2,z1-2),GLASS,owner)
        if style in ('residential','regional_city'):
            for x in (x0+10,x1-3):
                if x<x1-1:p.bed(x,y+1,z0+5,owner)
            p.chest(x1-2,y+1,z0+8,[('minecraft:bread',8),('minecraft:book',3)],owner,'west')
            p.fill(x1-6,y+1,z1-3,x1-2,y+1,z1-3,'minecraft:smooth_quartz',owner)
            p.put(x1-5,y+1,z1-3,'minecraft:water_cauldron[level=3]',owner)
            p.put(x1-2,y+1,z1-2,'minecraft:crafting_table',owner)
            p.fill(cx,y+1,z0+12,cx,y+3,z1-2,wall,owner)
            opening(p,cx,z0+15,y,owner,'east',1,2,mode='new')
        else:
            for x in range(x0+11,x1-2,6):
                for z in range(z0+5,z1-3,7):
                    p.fill(x,y+1,z,x+2,y+1,z,'minecraft:smooth_quartz',owner)
                    p.put(x+1,y+2,z,'minecraft:black_stained_glass',owner)
                    p.put(x+1,y+1,z+1,'minecraft:dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]',owner)
            p.chest(x1-2,y+1,z0+2,[('minecraft:paper',24),('minecraft:book',8)],owner)
    roof=floor+storeys*5
    p.fill(x0,roof,z0,x1,roof,z1,DARK,owner)
    p.fill(x0+2,roof+1,z0+3,x0+7,roof+3,z0+8,'minecraft:iron_block',owner)
    p.fill(x0+2,roof+4,z0+3,x0+7,roof+4,z0+8,'minecraft:stone_slab[type=bottom,waterlogged=false]',owner)
    for x in (x0,x1):p.fill(x,roof+1,z0,x,roof+1,z1,wall,owner)
    for z in (z0,z1):p.fill(x0,roof+1,z,x1,roof+1,z,wall,owner)
    # Build every landing before the flights; a later floor must not recap an
    # earlier flight's headroom. This is the R02/R43 verified stair-core layout.
    p.fill(x0+1,floor+1,z0+2,x0+9,roof-1,z0+10,AIR,owner)
    flights=[]
    for level in range(storeys):
        y=floor+level*5
        for za,zb in ((z0+2,z0+4),(z0+8,z0+10)):
            p.fill(x0+1,y,za,x0+9,y,zb,FLOOR,owner)
        p.fill(x0+9,y,z0+2,x0+9,y,z0+10,FLOOR,owner)
        for xx in (x0+1,x0+5,x0+9):
            p.fill(xx,y+1,z0+5,xx,y+2,z0+7,'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]',owner)
        p.put(x0+1,y+4,z0+3,LIGHT,owner)
        if level<storeys-1:
            north=level%2==0
            flights.append((x0+(3 if north else 7),z0+(9 if north else 3),y,'north' if north else 'south'))
    for x,z,y,heading in flights:stairs(p,x,z,y,5,heading,owner,3)
    opening(p,cx,z1,floor,owner,width=3,mode='new');door(p,cx,z1,floor,owner)
    p.fill(cx-3,floor,z1+1,cx+3,floor,z1+5,DARK,owner)
    # Low-rise Japanese streets combine residential lobbies, small shops and
    # offices. These original fronts are deliberately distinct from an EVA set.
    fronts=[('町内事务所','minecraft:light_gray_concrete','minecraft:stone_brick_slab'),
            ('街角书店','minecraft:brown_terracotta','minecraft:smooth_stone_slab'),
            ('社区诊所','minecraft:white_concrete','minecraft:quartz_slab'),
            ('喫茶店','minecraft:green_terracotta','minecraft:dark_oak_slab'),
            ('日用品商店','minecraft:light_gray_terracotta','minecraft:smooth_stone_slab'),
            ('办公楼入口','minecraft:gray_concrete','minecraft:stone_brick_slab'),
            ('住宅入口','minecraft:light_gray_concrete','minecraft:smooth_stone_slab'),
            ('街角商店','minecraft:orange_terracotta','minecraft:smooth_stone_slab')]
    index=variant%len(fronts)
    if style in ('residential','regional_city') and index in (0,2,5):index=6
    label,accent,canopy=fronts[index]
    for x in range(x0+2,x1-1):
        if abs(x-cx)>2:p.put(x,floor+4,z1,accent,owner)
    p.fill(cx-4,floor+4,z1+1,cx+4,floor+4,z1+1,canopy+'[type=top,waterlogged=false]',owner)
    p.sign(cx+3,floor+3,z1+1,[label,'入口 / 出口','人员通行',owner.split('/')[-1]],owner)
    p.meta['landmarks'].append(dict(id=owner,bounds=b,floor=floor,storeys=storeys,entry=[cx,floor+1,z1+1],style=style))


def park(p,b,floor,owner):
    x0,x1,z0,z1=b;cx=(x0+x1)//2;cz=(z0+z1)//2
    p.grade(x0,z0,x1,z1,floor,owner,8)
    p.fill(cx-2,floor,z0,cx+2,floor,z1,'minecraft:gravel',owner)
    p.fill(x0,floor,cz-2,x1,floor,cz+2,'minecraft:gravel',owner)
    for x,z in [(x0+7,z0+7),(x1-7,z0+7),(x0+7,z1-7),(x1-7,z1-7)]:
        tree(p,x,z,floor,owner)
    for x in (cx-8,cx+8):bench(p,x,cz+5,floor,owner)
    p.meta['landmarks'].append(dict(id=owner,bounds=b,floor=floor,style='park'))


def tree(p,x,z,floor,owner):
    p.fill(x,floor+1,z,x,floor+7,z,'minecraft:oak_log[axis=y]',owner)
    for y,r in [(floor+5,3),(floor+7,4),(floor+9,2)]:
        p.fill(x-r,y,z-r,x+r,y+1,z+r,'minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]',owner)


def furnished_room(p,b,floor,owner,label,purpose,wall=WALL,exit_side='east'):
    box_room(p,b,floor,9,owner,wall,'air');x0,x1,z0,z1=b;cx=(x0+x1)//2
    # Rooms stand on the measured pyramid foundation, without removing it.
    if floor>-465:
        for x in (x0,x1):
            for z in (z0,z1):p.fill(x,-465,z,x,floor-1,z,DARK,owner,'air')
    ex=x1 if exit_side=='east' else x0
    opening(p,ex,(z0+z1)//2,floor,owner,exit_side,3,3)
    p.sign(ex+(1 if exit_side=='east' else -1),floor+3,(z0+z1)//2+2,[label,purpose,'NERV',''],owner,exit_side)
    if purpose in ('MEDICAL','QUARTERS'):
        for x in range(x0+4,x1-2,5):
            for z in range(z0+5,z1-2,7):
                p.bed(x,floor+1,z,owner)
                p.put(x+1,floor+1,z,'minecraft:light_gray_concrete',owner)
                p.put(x+1,floor+2,z,'minecraft:flower_pot',owner)
        p.chest(x0+2,floor+1,z1-2,[('minecraft:bread',16),('minecraft:glass_bottle',16)],owner)
    elif purpose=='BRIEFING':
        p.fill(x0+3,floor+2,z0+1,x1-3,floor+5,z0+1,'minecraft:black_concrete',owner)
        for z in range(z0+6,z1-2,4):
            for x in range(x0+4,x1-2,5):bench(p,x,z,floor,owner,'north')
    elif purpose=='CAFETERIA':
        for x in range(x0+5,x1-3,6):
            for z in range(z0+5,z1-3,7):
                p.fill(x-1,floor+1,z,x+1,floor+1,z,'minecraft:smooth_quartz',owner)
                bench(p,x,z+1,floor,owner,'north');bench(p,x,z-1,floor,owner)
        p.chest(x0+2,floor+1,z0+2,[('minecraft:bread',32),('minecraft:cooked_beef',16),('minecraft:apple',16)],owner)
    elif purpose=='ARCHIVE':
        for x in range(x0+3,x1-3,4):p.fill(x,floor+1,z0+3,x,floor+4,z1-3,'minecraft:bookshelf',owner)
        p.chest(x1-2,floor+1,z1-2,[('minecraft:book',32),('minecraft:paper',32)],owner)
    elif purpose=='SEELE LINK':
        p.fill(x0+1,floor,z0+1,x1-1,floor,z1-1,'minecraft:black_concrete',owner)
        colors=['white','yellow','lime','light_blue','red','white']
        centers=[(cx,z0+5),(cx-7,z0+11),(cx+7,z0+11),(cx-7,z1-10),(cx+7,z1-10),(cx,z1-4)]
        for color,(x,z) in zip(colors,centers):
            p.fill(x-1,floor+1,z,x+1,floor+1,z,LIGHT,owner)
            p.fill(x-1,floor+2,z,x+1,floor+2,z,f'minecraft:{color}_stained_glass',owner)
            bench(p,x,z+1,floor,owner,'north')
    elif purpose in ('LOCKERS','SUPPLIES'):
        for z in range(z0+3,z1-2,4):p.chest(x0+2,floor+1,z,[('minecraft:iron_ingot',8),('minecraft:leather',8),('minecraft:torch',16)],owner,'east')
        for x in range(x0+6,x1-3,6):p.fill(x,floor+1,z0+2,x+2,floor+3,z0+4,STEEL,owner)
    else:
        for x in range(x0+5,x1-3,6):
            for z in range(z0+5,z1-3,7):
                p.fill(x-1,floor+1,z,x+1,floor+1,z,WHITE,owner)
                p.put(x,floor+2,z,'minecraft:black_stained_glass',owner);bench(p,x,z+1,floor,owner,'north')
    p.meta['rooms'].append(dict(id=owner,label=label,purpose=purpose,bounds=b,floor=floor,entry=[ex,floor+1,(z0+z1)//2]))
