"""Architecture of the R66 Tokyo-3 skyline, in the local frame of rigid-city owners."""
from collections import Counter

AIR = 'minecraft:air'
WHITE = 'minecraft:white_concrete'
STONE = 'minecraft:smooth_stone'
FINS = 'minecraft:smooth_quartz'
GREY = 'minecraft:light_gray_concrete'
BASE = 'minecraft:polished_andesite'
BLUE = 'minecraft:light_blue_stained_glass'
SMOKE = 'minecraft:gray_stained_glass'
GLASS = 'minecraft:light_gray_stained_glass'
GLOW = 'minecraft:ochre_froglight[axis=y]'
COOL = 'minecraft:sea_lantern'
DARK = 'minecraft:gray_concrete'
COPING = 'minecraft:smooth_quartz_slab[type=bottom,waterlogged=false]'
# Distinct secondary buildings stand on compartmentalised lift platforms. The same
# persisted tower owns both moving houses, precisely as it owns its former office.
PAIRED = {9, 15, 47, 60}
LANDMARK = {37, 43}
CIVIC = {3, 4, 8, 12, 17, 21, 26, 32, 33, 39, 48, 53, 54, 59, 63}
HOUSING = {0, 1, 5, 13, 24, 30, 31, 34, 36, 41, 50, 55, 61, 64, 68, 72, 73, 74, 76, 79, 81, 85, 87, 91, 92}
OWNERS = sorted(PAIRED | LANDMARK | CIVIC | HOUSING)


def section(owner, h, y, r):
    """Occupied plan polygons at this storey. Three/four cell chamfers are visible at street scale."""
    if owner in PAIRED:
        # Asymmetric twin shafts and independent flat crowns. A clear three-block alley
        # reaches the parapet of the shared podium; both towers land on the same rigid lift.
        first = (lambda x,z: -r+1 <= x <= -2 and -r+2 <= z <= r-1 and abs(z)+abs(x+6) <= r+1)
        second = (lambda x,z: 2 <= x <= r-1 and -r+1 <= z <= r-3 and abs(z)+abs(x-5) <= r)
        return [first] + ([second] if y <= h-9-(owner%3)*3 else [])
    if owner in LANDMARK:
        # Pair facing Hakone: light vertical cores, dark slit, faceted shoulder, flat crown.
        off = int(y > h-7)
        return [lambda x,z: abs(x)<=r-2-off and -r+2+off<=z<=r-1-off and abs(x)+abs(z)<=2*r-7-off]
    if owner in CIVIC:
        inset = int(y > h*.47) + int(y > h*.76)
        return [lambda x,z: -r+1+inset<=x<=r-1 and -r+1<=z<=r-1-inset and
                            x-z<=2*r-8-2*inset and z-x<=2*r-5-inset]
    setback = (y//max(9,h//3)) if owner%3 else int(y > h*.72)*2
    return [lambda x,z: -r+2<=x<=r-1-setback and -r+1+setback<=z<=r-2 and
                        x+z<=2*r-8-setback and -x-z<=2*r-7-setback]


def model(owner, h, r, original):
    """Retain the occupied lobby, all functional machinery and BE-bearing pieces."""
    keep = {p:s for p,s in original.items() if p[1]<=8 or s.startswith('projectseele:') or
            s.startswith(('minecraft:iron_block','minecraft:redstone_lamp','minecraft:barrel',
                          'minecraft:chest','minecraft:trapped_chest','minecraft:spawner')) or '_bed[' in s or 'sign[' in s}
    voxels = dict(keep)
    squares = {(x,z) for x in range(-r,r+1) for z in range(-r,r+1)}
    old_floor = {(x,z) for x,y,z in keep if y==8}
    previous = old_floor
    for y in range(9,h+2):
        polys = section(owner,h,y,r)
        floor = {p for p in squares if any(poly(*p) for poly in polys)} if y<=h else set()
        for x,z in previous-floor:
            if y==9: continue
            voxels[x,y-1,z] = COPING if (x+z)%7==0 else STONE
        for x,z in sorted(floor):
            outside = [(a,b) for a,b in ((1,0),(-1,0),(0,1),(0,-1)) if (x+a,z+b) not in floor]
            if not outside:
                if y in (9,h) or (y%4==0 and any((x+2*a,z+2*b) not in floor for a,b in ((1,0),(-1,0),(0,1),(0,-1)))):
                    voxels[x,y,z] = STONE
                continue
            # Use opaque fins adjacent to pale blue-grey ribbon glazing. A separately lit
            # backing one cell inside the glass gives actual window light at night.
            u = z if outside[0][0] else x
            corner = len(outside)>1
            if owner in LANDMARK:
                state = FINS if corner or abs(u)==5 or abs(u)==6 else WHITE if y>=h-3 or y%12==0 else SMOKE if abs(u)<=1 else (GREY if y%4==0 else BLUE)
            elif owner in PAIRED:
                state = WHITE if corner or y in (h,h-1) else STONE if y%5==0 else FINS if u%6==0 else GLASS
            elif owner in CIVIC:
                state = FINS if corner else WHITE if y%5<=1 else GREY if u%7==0 else BLUE if owner%2 else GLASS
            else:
                state = WHITE if y%4==0 or corner else GREY if y%4==1 or u%6 in (0,1) else GLASS
            voxels[x,y,z] = state
            if state in (GLASS,BLUE,SMOKE) and y%4==2 and (u//3+y//4+owner)%4 in (0,1):
                dx,dz=outside[0]
                if (x-dx,z-dz) in floor:
                    voxels[x-dx,y,z-dz] = GLOW if (owner+y//4)%5 else COOL
        previous=floor
    for p,s in keep.items():
        voxels[p]=s
    # The central marker is linked to its own podium roof, including split buildings.
    for x,y,z in list(keep):
        if y>=h and (x,y-1,z) not in voxels:
            for a in range(y-1,8,-1):
                if (x,a,z) in voxels:break
                voxels[x,a,z]=GREY
    return voxels
