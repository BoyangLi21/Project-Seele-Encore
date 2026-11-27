"""Build the sub-terminal, shelter approaches and furnished residential rooms against a stopped R65 world."""
import argparse
import json
import math
from pathlib import Path

from map_buildings.mca import AIR, World
from map_pipeline.city_protection import load as city_guard
from map_pipeline.launch_protection import load as launch_guard
from map_pipeline.lift_protection import load as lift_guard

REGION = 'dimensions/projectseele/geofront/region'


def state(name):
    return name if ':' in name else 'minecraft:' + name


def stair(wood, direction):
    return f'{wood}_stairs[facing={direction},half=bottom,shape=straight,waterlogged=false]'


def slab(material):
    return f'{material}_slab[type=bottom,waterlogged=false]'


class Plan:
    def __init__(self, world):
        self.reader = World(world / REGION)
        self.cells = {}
        self.entities = {}
        self.signs = []
        self.beds = []
        self.apartments = []
        self.shelters = []

    def get(self, x, y, z):
        return self.cells.get((x, y, z)) or self.reader.get(x, y, z)

    def put(self, x, y, z, name):
        self.cells[x, y, z] = state(name)

    def box(self, x, y, z, X, Y, Z, name):
        for i in range(x, X + 1):
            for h in range(y, Y + 1):
                for k in range(z, Z + 1):
                    self.put(i, h, k, name)

    def sign(self, x, y, z, facing, *lines):
        self.put(x, y, z, f'oak_wall_sign[facing={facing},waterlogged=false]')
        self.signs.append(dict(pos=[x, y, z], front=list(lines), color='white', glow=True))

    def new_bed(self, x, y, z, colour):
        for offset, part in enumerate(('foot', 'head')):
            self.put(x, y, z + offset, f'{colour}_bed[facing=south,occupied=false,part={part}]')
            self.entities[x, y, z + offset] = {'id': 'minecraft:bed', 'snbt': '{}'}

    def validate_bed(self, x, y, z):
        for dz, part in enumerate(('foot', 'head')):
            bed = self.get(x, y, z + dz)
            assert '_bed[' in bed and f'part={part}' in bed and 'facing=south' in bed, (x,y,z,bed)
            assert self.get(x, y + 1, z + dz) in AIR, (x,y,z,'over bed')
        clear = any(all(self.get(x+dx, y+h, z+dz) in AIR for h in (0,1))
                    and self.get(x+dx, y-1, z+dz) not in AIR
                    for dx, dz in ((-1,0), (1,0), (-1,1), (1,1), (0,2), (0,-1)))
        assert clear, ('no dismount beside bed', x, y, z)
        self.beds.append([x, y, z])


def fix_old_housing(p):
    frames = [(117,2044,'polished_deepslate'), (155,2044,'spruce_planks'),
              (194,2044,'white_concrete')]
    frames += [(x,2018,'light_gray_concrete') for x in (124,161,198)]
    for x, z, material in frames:
        for dx in (-1,0):
            assert '_door[' in p.get(x+dx,-475,z)
            p.put(x+dx,-474,z,material)
    # Lift the Gendo library niche clear of his pillow and give the bookcase a finished end.
    for x in range(111,114):
        for y in (-475,-474):
            if p.get(x,y,2056) == state('bookshelf'):
                p.put(x,y,2056,'air')
    beds = [(x, -476, 2056) for x in (112,150,189)]
    beds += [(x+dx, -476+5*k, 1997+dz)
             for x in (112,149,186) for k in range(3) for dz in (3,9,15)
             for dx in (3,7,18,21)]
    for x,y,z in beds:
        for offset in (0,1):
            above = p.get(x,y+1,z+offset)
            if above not in AIR:
                assert above in (state('bookshelf'),state('birch_planks')), (x,y,z,above)
                p.put(x,y+1,z+offset,'air')
        p.validate_bed(x,y,z)


def furnish_comfort(p):
    for k in range(1,14):
        y = 133 + 3*k
        for unit,(left,right) in enumerate(((-65,-59),(-57,-47),(-36,-28),(-26,-18))):
            if (k,unit)==(10,1):
                continue
            # Skip occupied/customised flats, including any furniture with a block entity.
            if any(p.get(x,h,z) not in AIR for x in range(left,right+1)
                   for z in range(770,778) for h in (y,y+1)):
                continue
            variant = (k+unit)%3
            wood = ('oak','birch','spruce')[variant]
            bedside = left if variant!=1 else right
            p.new_bed(bedside,y,770,('blue','gray','green','cyan')[(k+unit)%4])
            table = right if bedside==left else left
            p.put(table,y,771,slab(wood))
            p.put(table,y,772,stair(wood,'south'))
            p.put(table,y,776,'bookshelf')
            p.put(bedside,y,775,'smooth_quartz')
            p.put(bedside,y,776,'water_cauldron[level=2]')
            if right-left>7:
                p.put(table,y,774,stair(wood,'west' if table==right else 'east'))
            # Old iron doors otherwise have no way for a resident to open them.
            doorx = left+2
            if 'iron_door[' in p.get(doorx,y,778):
                for z,face in ((777,'north'),(779,'south')):
                    if p.get(doorx-1,y+1,z) in AIR:
                        p.put(doorx-1,y+1,z,f'stone_button[face=wall,facing={face},powered=false]')
            p.validate_bed(bedside,y,770)
            p.apartments.append([k+1,unit+1])
    assert p.reader.get(-40,162,776) == p.get(-40,162,776)


def maintenance(p):
    for x,z in ((10,286),(10,298)):
        assert p.get(x,-481,z)==state('black_concrete')
        assert p.get(x,-482,z) in (state('gray_carpet'),state('black_concrete'))
        assert p.get(x,-483,z)==state('projectseele:nerv_floor_panel')
        p.put(x,-482,z,'black_concrete')
    for x in (-332,-331):
        flat=p.get(x,-467,762)
        assert 'mtr:escalator_step[' in flat and 'orientation=flat' in flat
        for z in range(763,767):
            p.put(x,-467,z,flat)


def second_command(p):
    # The south entrance looks along the command room towards the north screen.
    # The headquarters drawing places the narrow sail on the far side of the plaza.
    floor = -467
    for x in range(135,174):
        for z in range(312,366):
            chamfer = max(0, 4-min(z-312,365-z))
            if x < 135+chamfer or x > 173-chamfer:
                continue
            p.put(x,floor,z,'polished_andesite')
    for x in range(138,172):
        for z in range(316,359):
            cut = max(0,4-min(z-316,358-z))
            if not 138+cut<=x<=171-cut:
                continue
            edge = x in (138+cut,171-cut) or z in (316,358)
            p.put(x,floor,z,'polished_deepslate' if edge else 'smooth_stone')
            for h in range(1,13):
                if edge and not (z==358 and 150<=x<=156 and h<=5):
                    window = z not in (316,358) and 4<=h<=8 and z%8 in (2,3,4)
                    mat = 'gray_stained_glass' if window else 'light_gray_concrete'
                    if h in (1,10) or (z%9==0 and not window):
                        mat = 'polished_andesite'
                    p.put(x,floor+h,z,mat)
            p.put(x,floor+13,z,'smooth_quartz' if edge else 'smooth_stone')
    # Elevated source-style bridge, three controller tiers stepped towards the screen.
    for x in range(139,171):
        for z in range(317,358):
            for h in range(1,13):
                if any(tag in p.get(x,floor+h,z) for tag in ('_leaves','_log')):
                    p.put(x,floor+h,z,'air')
    for row,z in enumerate((329,337,345)):
        h = row+1
        for x in range(143,167):
            if x in (153,154,155):
                continue
            p.box(x,floor+1,z,x,floor+h,z+3,'polished_deepslate')
            p.put(x,floor+h+1,z,'stripped_dark_oak_wood[axis=x]')
            if x%4!=0:
                p.put(x,floor+h+2,z,'cyan_terracotta' if x%3 else 'light_gray_stained_glass')
            if x%3 == 0:
                p.put(x,floor+h+1,z+2,stair('dark_oak','south'))
        for step in range(h):
            for x in (142,167):
                p.put(x,floor+step+1,z+3+step-h,stair('stone_brick','south'))
    p.box(142,floor+3,317,167,floor+10,317,'polished_blackstone')
    p.box(143,floor+4,317,166,floor+9,317,'gray_concrete')
    for x in range(144,166):
        for h in range(4,10):
            band = (x+h)%13==0 or (x-144)//4==abs(h-7)
            if band:
                p.put(x,floor+h,317,'cyan_terracotta' if x%5 else 'ochre_froglight[axis=y]')
    for z in range(321,353,8):
        for x in (140,169):
            p.box(x,floor+1,z,x,floor+11,z,'polished_basalt[axis=y]')
            p.put(x,floor+11,z+1,'ochre_froglight[axis=y]')
        p.box(140,floor+12,z,169,floor+12,z,'polished_andesite')
    for x in (147,159):
        p.put(x,floor+2,357,'polished_deepslate')
    p.sign(147,floor+2,358,'south','NERV','第二発令所','司令部予備指揮所','SUB TERMINAL')
    # Rising crescent shell. Its projecting lower tongue shades the plaza. An
    # eastern vertical spine and a receding curved western face give the profile.
    for h in range(14,59):
        t = (h-14)/44
        outer = 171-round(3*t*t)
        inner = 140+round(23*math.sqrt(t))
        half = round(18-11*t)
        for x in range(inner,outer+1):
            end = half - max(0, 2-min(x-inner,outer-x))
            for z in range(336-end,337+end):
                side = x in (inner,outer) or abs(z-336)>=end-1
                if side or h in (14,58):
                    mat = 'smooth_quartz'
                    if x==inner and h%10 in (4,5):
                        mat='light_blue_stained_glass'
                    elif x>=outer-1 or (z in (332,340) and x==inner):
                        mat='light_gray_concrete'
                    p.put(x,floor+h,z,mat)
    # A transverse service walk leads out of the south forecourt; it skirts the
    # eastern face where the pyramid is exposed, never carving into its panels.
    pts=[(53,392),(88,392),(103,387),(124,377),(140,368),(153,364),(153,359)]
    for (x0,z0),(x1,z1) in zip(pts,pts[1:]):
        steps=max(abs(x1-x0),abs(z1-z0))
        for i in range(steps+1):
            x,z=round(x0+(x1-x0)*i/steps),round(z0+(z1-z0)*i/steps)
            for a in range(x-2,x+3):
                for b in range(z-2,z+3):
                    if p.get(a,floor,b) in (state('grass_block[snowy=false]'),state('dirt'),state('polished_andesite')):
                        p.put(a,floor,b,'smooth_stone')
    for x in (141,166):
        for z in (360,364):
            p.put(x,floor,z,'ochre_froglight[axis=y]')


def shelter(p,x,z):
    # Descend along the inside of the sidewalk. Only the top four stairs
    # break ground. The lower gallery turns under the road, clear of its deck.
    for n in range(1,9):
        h=80-min(n-1,7)
        step='smooth_stone' if n in (1,8) else stair('stone_brick','south')
        p.put(x,h,z-n,step)
        p.box(x,h+1,z-n,x,h+3,z-n,'air')
        for dx in (-1,1):
            for yy in range(h,h+4):
                p.put(x+dx,yy,z-n,'light_gray_concrete')
        p.put(x,h+4,z-n,'smooth_stone')
        if n==4:
            p.put(x,h+4,z-n,'sea_lantern')
    # An independent ceiling keeps the roadway at Y80 exactly as surveyed.
    for dx in range(-10,2):
        for dz in range(-15,-8):
            for y in range(72,78):
                edge = dx in (-10,1) or dz in (-15,-9)
                door = dx==0 and dz==-9 and 73<=y<=75
                mat = 'smooth_stone' if y in (72,77) else 'light_gray_concrete' if edge and not door else 'air'
                if y==76 and edge:
                    mat='green_terracotta'
                p.put(x+dx,y,z+dz,mat)
    for dx in range(-8,-2):
        for dz,face in ((-14,'north'),(-10,'south')):
            p.put(x+dx,73,z+dz,stair('spruce',face))
    for dx in (-8,-3):
        p.put(x+dx,77,z-12,'sea_lantern')
    p.put(x-9,73,z-11,'water_cauldron[level=3]')
    for dz in (0,1,2):
        p.put(x,80,z+dz,'smooth_stone')
        if p.get(x,79,z+dz) in AIR | {state('water[level=0]')}:
            p.put(x,79,z+dz,'stone_bricks')
    for dz in (-1,1):
        p.put(x,81,z+dz,'stone_pressure_plate[powered=false]')
    p.shelters.append([x,81,z])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('world',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    p=Plan(args.world)
    fix_old_housing(p)
    furnish_comfort(p)
    maintenance(p)
    second_command(p)
    bf=json.loads((args.world/'battlefield_r21.json').read_bytes())
    doors=[(x,z) for x,y,z,*rest in bf['cells'] if y==81 and 'iron_door[' in rest[0]
           and any(v[:3]==[x,83,z+1] and 'SHELTER' in str(v[3:]) for v in bf['cells'])]
    if not doors:
        doors=[(x,z) for x,y,z in bf['permanent_shelters_r66']]
    assert len(doors)==len(set(doors))==38
    bf['permanent_shelters_r66']=[[x,81,z] for x,z in doors]
    # Preserve the city's existing street overlay state machine. Kiosks are
    # emergency fixtures and remain available through both endpoints.
    kiosk_cells={(x+dx,y,z+dz) for x,z in doors for dx in (-1,0,1) for dz in (0,1,2) for y in range(81,85)}
    keep=[]
    for entry in bf['cells']:
        x,y,z,raised,lowered,*extra=entry
        if (x,y,z) in kiosk_cells and raised!=lowered:
            assert lowered=='minecraft:air' and raised.split('[')[0] in {
                state(n) for n in ('birch_wall_sign','smooth_stone_slab','light_gray_concrete','iron_door')},entry
            if p.get(x,y,z)==lowered:
                p.put(x,y,z,raised)
                if 'wall_sign' in raised:
                    p.signs.append(dict(pos=[x,y,z],front=['避難所','SHELTER','',''],color='green'))
        else:
            keep.append(entry)
    bf['cells']=keep
    for x,z in doors:
        shelter(p,x,z)
    rows=[]
    for pos,after in sorted(p.cells.items()):
        before=p.reader.get(*pos)
        if before is None:
            raise ValueError(('unpopulated chunk',pos))
        if before==after:
            continue
        if p.reader.block_entity(*pos):
            raise ValueError(('unexpected block entity',pos,before))
        row=[*pos,before,after]
        if pos in p.entities:
            row.append(p.entities[pos])
        rows.append(row)
    positions=[r[:3] for r in rows]
    for load in (city_guard,lift_guard,launch_guard):
        load(args.world).assert_positions(positions)
    for filename,obj in [('rows',rows),('signs',p.signs),('battlefield_r21',bf),('survey',dict(beds=p.beds,flats=p.apartments,shelters=p.shelters,rows=len(rows),overlay=len(keep)))]:
        (args.output/(filename+'.json')).write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':')),'utf8')
    print(len(rows),'cells;',len(p.beds),'beds;',len(p.apartments),'flats;',len(doors),'shelters')


if __name__=='__main__':
    main()
