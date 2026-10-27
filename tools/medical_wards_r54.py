"""Original three-room medical wing in the explicitly assigned R04 medical room.

Pure geometry recipe shared by the exact measured migration and old room authoring.
The outer pyramid shell, old equipment and circulation outside this room are not inputs.
"""
ROOM_ID='r04/pyramid/435/06'
ROOMS=[('101',-48,-36,-42),('102',-34,-22,-28),('103',-20,-8,-14)]

def layout(floor):
    cells={}; tags={}; rooms=[]
    def put(x,y,z,s):cells[x,y,z]=s
    def fill(x,y,z,X,Y,Z,s):
        for yy in range(y,Y+1):
            for zz in range(z,Z+1):
                for xx in range(x,X+1):put(xx,yy,zz,s)
    for x in range(-48,-7):
        for z in range(378,407):
            put(x,floor,z,'minecraft:smooth_quartz' if z>=387 else 'minecraft:smooth_stone')
            grid=(x+48)%4==0 or (z-378)%4==0
            put(x,floor+5,z,'minecraft:light_gray_concrete' if grid else 'minecraft:white_concrete')
    for x in (-35,-21):fill(x,floor+1,387,x,floor+4,406,'minecraft:white_concrete')
    fill(-48,floor+1,387,-8,floor+4,387,'minecraft:white_concrete')
    for x in (-35,-21):fill(x,floor+2,388,x,floor+2,406,'minecraft:cyan_terracotta')
    for num,a,b,c in ROOMS:
        for x,hinge in ((c-1,'left'),(c,'right')):
            for y,half in ((floor+1,'lower'),(floor+2,'upper')):
                put(x,y,387,f'projectseele:city_personnel_door[facing=north,half={half},hinge={hinge},open=false,powered=false]')
        for z in (391,397,403):
            for x in (c-2,c-1,c,c+1):put(x,floor+5,z,'projectseele:nerv_strip_light[lit=true]')
        for x in range(c-3,c+4):
            put(x,floor+1,400,'minecraft:smooth_quartz')
            put(x,floor+2,400,'minecraft:cyan_terracotta')
        put(c+2,floor+2,399,'projectseele:nerv_medical_panel[facing=south]')
        put(c+2,floor+1,399,'minecraft:smooth_quartz')
        for z,part in ((402,'foot'),(401,'head')):
            p=(c,floor+1,z);put(*p,f'minecraft:white_bed[facing=north,occupied=false,part={part}]');tags[p]=('minecraft:bed',None)
        for z in (391,392):put(b-1,floor+1,z,'minecraft:quartz_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]')
        tags[c,floor+3,386]=('minecraft:sign',['病房 '+num,'NERV 医疗翼','静养 / RECOVERY',''])
        put(c,floor+3,386,'minecraft:birch_wall_sign[facing=north,waterlogged=false]')
        rooms.append(dict(id=ROOM_ID+'/ward_'+num,label='医疗翼 '+num+' 独立病房',purpose='MEDICAL_RECOVERY',bounds=[a,b,388,406],floor=floor,entry=[c,floor+1,387],door_width=2,ceiling=floor+5,bed=[c,floor+1,401]))
    for x in (-42,-28,-14):
        for z in (380,384):put(x,floor+5,z,'projectseele:nerv_strip_light[lit=true]')
    put(-25,floor+3,378,'minecraft:birch_wall_sign[facing=south,waterlogged=false]')
    tags[-25,floor+3,378]=('minecraft:sign',['NERV 医疗翼','101  102  103','独立静养病房','前方 / AHEAD'])
    return cells,tags,rooms


def make_tag(pos,kind,lines=None):
    import nbtlib,json
    t=nbtlib.Compound({'id':nbtlib.String(kind),**{k:nbtlib.Int(v) for k,v in zip(('x','y','z'),pos)}})
    if lines is not None:
        def side():return nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':v},ensure_ascii=False)) for v in lines]),'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
        t.update(front_text=side(),back_text=side(),is_waxed=nbtlib.Byte(1))
    return t


def author_legacy(p,floor,owner):
    cells,tags,rooms=layout(floor)
    for pos,s in cells.items():p.put(*pos,s,owner+'/private_wards_r54','new')
    for pos,(kind,lines) in tags.items():p.block_entities[pos]=make_tag(pos,kind,lines)
    p.meta.setdefault('medical_wards_r54',[]).extend(rooms)

