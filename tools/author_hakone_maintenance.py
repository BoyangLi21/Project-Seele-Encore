"""Connect the real lower tower aprons to a fixed maintenance gallery and stairs."""
import numpy as np
from PIL import Image,ImageFilter


def author(c,towers):
    floor=-112;paths=np.zeros(c.blocks.shape[1:],bool);connections=[]
    def line(a,b):
        n=max(abs(a[0]-b[0]),abs(a[1]-b[1]))
        for i in range(n+1):
            x=round(a[0]+(b[0]-a[0])*i/max(1,n));z=round(a[1]+(b[1]-a[1])*i/max(1,n))
            paths[z-c.z0,x-c.x0]=True
    line((30,40),(30,548));line((-302,220),(350,220))
    # The stairwell approach goes around its north wall, entering the first
    # flat landing from the west instead of crossing underneath a flight.
    line((30,76),(-194,76));line((-194,76),(-194,84));line((-194,84),(-188,84))
    for t in towers:
        if t['kind']!='generated':continue
        x,z=t['x'],t['z']+t['half']+7;base=t['base']
        if base<floor+5:raise ValueError('Gallery must remain below the deepest retained bearing')
        root=(x,z-1)
        joint=(30,root[1])if abs(x-30)<=abs(root[1]-220)else(x,220)
        line(root,joint)
        connections.append(dict(index=t['index'],door=[x,base+1,t['z']+t['half']],ladder=[x,z],landing=base))
    deck=np.array(Image.fromarray(paths).filter(ImageFilter.MaxFilter(3)),dtype=bool)
    border=np.asarray(Image.fromarray(deck).filter(ImageFilter.MaxFilter(3)),bool)&~deck
    c.layer(floor,deck|border,'minecraft:polished_deepslate')
    for y in range(floor+1,floor+4):c.layer(y,deck,'minecraft:air')
    for iz,ix in zip(*np.nonzero(border)):
        directions={k:0<=iz+dz<border.shape[0]and 0<=ix+dx<border.shape[1]and bool(border[iz+dz,ix+dx])
                    for k,dx,dz in [('east',1,0),('north',0,-1),('south',0,1),('west',-1,0)]}
        state='minecraft:iron_bars['+','.join(k+'='+str(v).lower()for k,v in sorted(directions.items()))+',waterlogged=false]'
        # State properties are canonicalised by the shared serializer.
        c.put(ix+c.x0,floor+1,iz+c.z0,state)
    for row in connections:
        x,z=row['ladder'];base=row['landing']
        c.fill(x-1,base,z-3,x+2,base,z-1,'minecraft:polished_deepslate')
        c.fill(x-1,floor+1,z,x-1,base+2,z,'minecraft:gray_stained_glass')
        c.fill(x+2,floor+1,z,x+2,base+2,z,'minecraft:gray_stained_glass')
        c.fill(x-1,floor+1,z+1,x+2,base+2,z+1,'minecraft:polished_deepslate')
        c.fill(x-1,floor+4,z-1,x+2,base-1,z-1,'minecraft:gray_stained_glass')
        c.fill(x,floor+1,z,x+1,base+1,z,'minecraft:ladder[facing=north,waterlogged=false]')
        c.fill(x,floor+1,z-1,x+1,floor+3,z-1,'minecraft:air')
        c.fill(x,base+1,z-3,x+1,base+3,z-1,'minecraft:air')
        c.put(x-1,base+3,z,'minecraft:sea_lantern')
    # Ordinary stairs provide continuous walking access from the public park.
    # Four short flights and level corners form each turn; the central void
    # and independent floor openings remain clear all the way to the street.
    x0,z0=-190,82;top=82;y=floor;flight=[]
    c.fill(x0-1,floor,z0-1,x0+15,top+4,z0+15,'minecraft:air')
    c.fill(x0-1,floor,z0-1,x0+15,floor,z0+15,'minecraft:polished_deepslate')
    for yy in range(floor+1,top+4):
        material='minecraft:gray_stained_glass'if yy%8 in (3,4,5)else 'minecraft:light_gray_concrete'
        for zz in (z0-1,z0+15):c.fill(x0-1,yy,zz,x0+15,yy,zz,material)
        for xx in (x0-1,x0+15):c.fill(xx,yy,z0-1,xx,yy,z0+15,material)
    c.fill(x0-1,top+4,z0-1,x0+15,top+4,z0+15,'minecraft:smooth_stone')
    sides=[((2,2),(1,0),'east'),((10,2),(0,1),'south'),((10,10),(-1,0),'west'),((2,10),(0,-1),'north')]
    done=False
    while not done:
        for (ox,oz),(dx,dz),face in sides:
            for j in range(8):
                stair=2<=j<=5
                if stair:y+=1
                x,z=x0+ox+dx*j,z0+oz+dz*j
                for side in (-1,0,1):
                    c.put(x-dz*side,y,z+dx*side,
                        f'minecraft:stone_brick_stairs[facing={face},half=bottom,shape=straight,waterlogged=false]'if stair else 'minecraft:polished_deepslate')
                # Inner parapet follows the stair rather than bridging its
                # opening with a floor slab on the next turn.
                c.put(x-dz*2,y+1,z+dx*2,'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]')
                c.put(x+dz*2,y+1,z-dx*2,'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]')
                flight.append([x,y+1,z])
                if y==top:done=True;break
            if done:break
    # Corner parapets must not cross the adjoining flight's three-wide
    # landing. Clear its actual walking volume after all sides are joined.
    for i,(x,y,z)in enumerate(flight):
        q=flight[i+1]if i+1<len(flight)else flight[i-1]
        dx=int(np.sign(q[0]-x));dz=int(np.sign(q[2]-z))
        for side in (-1,0,1):c.fill(x-dz*side,y,z+dx*side,x-dz*side,y+1,z+dx*side,'minecraft:air')
    end=flight[-1];ex=end[0]
    c.fill(x0-1,floor,z0+1,x0+2,floor,z0+3,'minecraft:polished_deepslate')
    c.fill(x0-1,floor+1,z0+1,x0-1,floor+3,z0+3,'minecraft:air')
    c.fill(ex-1,top,z0-4,ex+1,top,z0,'minecraft:smooth_stone')
    c.fill(ex+1,top,z0,ex+2,top,z0+3,'minecraft:smooth_stone')
    c.fill(ex-1,top+1,z0-1,ex+1,top+3,z0+2,'minecraft:air')
    c.fill(ex-1,top,z0-5,-143,top,z0-3,'minecraft:smooth_stone')
    c.fill(-145,top,z0-4,-143,top,z0+3,'minecraft:smooth_stone')
    # The surface porch and park connection are supported, not floating slabs.
    c.fill(ex-1,25,z0-5,-143,top-1,z0-3,'minecraft:stone')
    c.fill(-145,25,z0-4,-143,top-1,z0+3,'minecraft:stone')
    return dict(gallery_floor=floor,connected_lower_doors=len(connections),connections=connections,
                street_access=[ex,top+1,z0-2],stairs=flight)
