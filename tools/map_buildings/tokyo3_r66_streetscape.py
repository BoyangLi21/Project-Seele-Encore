"""Derive old-town shopfront and hillside infill changes from the parked world's actual buildings."""
import argparse,gzip,json,math
from pathlib import Path
from collections import Counter
from mca import World
from city_body_sync import topology
from tokyo3_r66_design import AIR

AXIS=[(-333,8),(-290,34),(-255,12),(-209,-4),(-164,8),(-119,28)]
PALETTES=[('white_terracotta','brown_terracotta','deepslate_tiles'),('smooth_sandstone','stripped_spruce_wood[axis=y]','polished_andesite'),
          ('light_gray_concrete','gray_terracotta','polished_deepslate'),('white_concrete','cyan_terracotta','stone_bricks')]
N=lambda s:'minecraft:'+s
def open_(s):return s is not None and s in {AIR,'minecraft:cave_air','minecraft:grass','minecraft:tall_grass[half=upper]','minecraft:tall_grass[half=lower]','minecraft:fern','minecraft:dandelion','minecraft:poppy'}
def earth(s):return bool(s) and s.split('[')[0] in {'minecraft:grass_block','minecraft:dirt','minecraft:coarse_dirt','minecraft:podzol'}
def nearest(x,z,corners):
    best=9999.
    for (x0,z0),(x1,z1) in zip(corners,corners[1:]):
        dx,dz=x1-x0,z1-z0;t=min(1,max(0,((x-x0)*dx+(z-z0)*dz)/(dx*dx+dz*dz)))
        best=min(best,math.hypot(x-(x0+t*dx),z-(z0+t*dz)))
    return best

def build_shops(w,changes,protected,other):
    placed=[];occupied=set()
    for seg,((x0,z0),(x1,z1)) in enumerate(zip(AXIS,AXIS[1:])):
        dx,dz=x1-x0,z1-z0;length=math.hypot(dx,dz);vx,vz=dx/length,dz/length
        for fraction in (.20,.68,.43,.91,.06,.31,.56,.79):
          for side in (-1,1):
           for offset in (15,19,24,29,34):
            cx,cz=round(x0+dx*fraction-vz*offset*side),round(z0+dz*fraction+vx*offset*side)
            typ=(seg+side+round(fraction*8))%4;half=(5 if typ%2 else 4);depth=(3 if typ%2 else 4)
            def uv(x,z):return ((x-cx)*vx+(z-cz)*vz, (-(x-cx)*vz+(z-cz)*vx)*side)
            cells={(x,z) for x in range(cx-13,cx+14) for z in range(cz-13,cz+14) if (lambda u,v:abs(u)<=half and abs(v)<=depth and u-v<half+depth-1)(*uv(x,z))}
            if any(protected(x,z) or (x,z) in occupied or nearest(x,z,AXIS)<9 for x,z in cells):continue
            grade={};bad=False
            for x,z in cells:
                for y in range(143,62,-1):
                    s=w.get(x,y,z)
                    if open_(s):continue
                    if earth(s):grade[x,z]=y
                    else:bad=True
                    break
                if bad or (x,z) not in grade:bad=True;break
            if bad or max(grade.values())-min(grade.values())>4:continue
            base=max(grade.values());wall,trim,roof=map(N,PALETTES[typ]);floors=2+(typ==1)+(typ==2)
            storey=4;high=storey*floors;local={}
            for p,g in grade.items():
                x,z=p;u,v=uv(x,z)
                border=any((x+a,z+b) not in cells for a,b in ((1,0),(-1,0),(0,1),(0,-1)))
                for y in range(g+1,base+high+1):
                    i=y-base
                    if i<=0:state=N('stone_bricks')
                    elif i%storey==0:state=N('spruce_planks') if not border else trim
                    elif not border:continue
                    elif v < -depth+1.4 and abs(u)<1.55 and i in (1,2,3):continue
                    elif i%storey in (2,3) and round(u if abs(v)>depth-1.5 else v)%6 in (1,2,3,4):state=N('light_gray_stained_glass') if i>3 else N('glass')
                    else:state=wall
                    local[x,y,z]=state
                if typ%2==0:
                    ridge=int((depth-abs(v))/2)
                    for i in range(max(0,ridge-1),ridge+1):local[x,base+high+1+i,z]=roof
                else:
                    local[x,base+high+1,z]=N('smooth_stone_slab[type=bottom,waterlogged=false]') if border else roof
                    if 1<u<4 and 0<v<3:local[x,base+high+2,z]=N('smooth_stone')
                if v < -depth+1.6 and abs(u)>2 and (round(u)+typ)%4==0:local[x,base+3,z]=N('ochre_froglight[axis=y]')
            if any(not open_(w.get(*p)) or w.block_entity(*p) or (other and (other.get(*p)!=w.get(*p) or other.block_entity(*p))) for p in local):continue
            if other and any(other.get(x,y,z)!=w.get(x,y,z) for (x,z),y in grade.items()):continue
            for p,s in local.items():changes[p]=(w.get(*p),s)
            for x,z in cells:
                for a in range(-4,5):
                    for b in range(-4,5):occupied.add((x+a,z+b))
            placed.append(dict(x=cx,z=cz,base=base,floors=floors,angle=round(math.degrees(math.atan2(dz,dx)),1),voxels=len(local),segment=seg));break
    return placed

def main():
    a=argparse.ArgumentParser();a.add_argument('region',type=Path);a.add_argument('authority',type=Path);a.add_argument('out',type=Path);a.add_argument('--other-regions',type=Path);args=a.parse_args()
    w=World(args.region);ts=topology(args.authority);boxes=[]
    for t in ts.values():
        cx,_,cz=t['centre'];f=t['fp'];boxes.append((cx+f[0]-2,cz+f[2]-2,cx+f[1]+2,cz+f[3]+2))
    for x,z in [(-210,180),(270,420),(270,380),(30,140),(30,300),(110,220)]:boxes.append((x-17,z-17,x+17,z+17))
    boxes.extend([(-48,151,94,282),(-215,488,-125,557),(-81,752,4,816)])
    def protected(x,z):return any(x0<=x<=x1 and z0<=z<=z1 for x0,z0,x1,z1 in boxes)
    other=World(args.other_regions) if args.other_regions else None
    changes={};placed=build_shops(w,changes,protected,other)
    targets={'minecraft:glass','minecraft:light_blue_stained_glass','minecraft:light_gray_stained_glass','minecraft:white_stained_glass'}
    frames={N(v) for v in ('white_concrete','light_gray_concrete','smooth_quartz','smooth_stone','white_terracotta','polished_andesite')}
    counts=Counter()
    # Grid intersections and transit corridor remain open. Scan only the interiors of private blocks,
    # then accept exterior window bands supported by an uninterrupted row of architectural cladding.
    for cz in range(-20,662,40):
      for cx in range(-330,312,40):
        if protected(cx,cz):continue
        for x in range(cx-13,cx+14):
          for z in range(cz-13,cz+14):
            if protected(x,z):continue
            surface=w.get(x,80,z)
            for y in range(85,145):
                s=w.get(x,y,z)
                if s not in targets or w.get(x,y-1,z) not in frames:continue
                # The front is the side with open air; require two adjoining panes and exterior
                # depth to distinguish a shop window from a single service aperture or mechanism.
                tangent=None
                for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                    if not open_(w.get(x+dx,y,z+dz)) or not open_(w.get(x+2*dx,y,z+2*dz)):continue
                    if w.get(x+dz,y,z+dx) not in targets and w.get(x-dz,y,z-dx) not in targets:continue
                    tangent=(dx,dz);break
                if not tangent:continue
                old=abs(cx-10)>180 or cz>420 or cz<60
                family=(cx//40+2*(cz//40))%4
                if y<93 and old:
                    new=N(('white_terracotta','brown_terracotta','stripped_spruce_wood[axis=y]','cyan_terracotta')[family])
                    pos=(x,y-1,z)
                elif (y//4+family)%3==0:
                    new=N(('light_gray_stained_glass','gray_stained_glass','light_blue_stained_glass','glass')[family]);pos=(x,y,z)
                elif y%4==1 and (x+z+family)%5 in (0,1):
                    new=N('smooth_quartz' if not old else 'smooth_sandstone');pos=(x,y-1,z)
                else:continue
                before=w.get(*pos)
                if before!=new and not w.block_entity(*pos) and (not other or other.get(*pos)==before):
                    changes[pos]=(before,new);counts[cx,cz]+=1
    # The five civil zones are surveyed in the original regional plan. Read voxel sections rather
    # than a city-grid assumption; old Hakone shops have off-grid foundations and sloping streets.
    import numpy as np
    zones=[r for r in json.loads((args.authority/'regional_plan.json').read_text('utf8'))['zones']
           if r['id'] in {'tokyo_west','tokyo_north','tokyo_south','harbour_ward','new_hakone'}]
    targets |= {N('gray_stained_glass'),N('black_stained_glass')}
    regional=Counter();seen=set()
    for zone in zones:
        x0,x1,z0,z1=map(int,zone['bounds'])
        for kx in range(x0>>4,(x1>>4)+1):
          for kz in range(z0>>4,(z1>>4)+1):
            if (kx,kz) in seen:continue
            seen.add((kx,kz))
            if len(w.chunks)>100:w.chunks.clear()
            ch=w.chunk(kx,kz)
            if ch is None:continue
            for sy,(ids,palette) in ch[0].items():
                if sy<4 or sy>13:continue
                glazing=[i for i,s in enumerate(palette) if s in targets]
                if not glazing:continue
                for index in np.flatnonzero(np.isin(ids,glazing)):
                    index=int(index);x=kx*16+(index&15);z=kz*16+((index>>4)&15);y=sy*16+(index>>8)
                    if not(x0<=x<=x1 and z0<=z<=z1) or (-343<=x<=324 and -33<=z<=636) or protected(x,z):continue
                    if y<zone['floor']+3 or (x+y+z)%3==0:continue
                    sill=w.get(x,y-1,z)
                    if sill not in frames:continue
                    exterior=any(open_(w.get(x+dx,y,z+dz)) and open_(w.get(x+dx*2,y,z+dz*2))
                        and (w.get(x+dz,y,z+dx) in targets or w.get(x-dz,y,z-dx) in targets)
                        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)))
                    if not exterior:continue
                    family=(kx//2+kz//3)%4
                    if (y-zone['floor'])<14:
                        p=(x,y-1,z);new=N(('white_terracotta','smooth_sandstone','polished_andesite','light_gray_concrete')[family])
                    else:
                        p=(x,y,z);new=N(('light_gray_stained_glass','light_blue_stained_glass','glass','gray_stained_glass')[family])
                    old=w.get(*p)
                    if p not in changes and old!=new and not w.block_entity(*p) and (not other or other.get(*p)==old):
                        changes[p]=(old,new);regional[zone['id']]+=1
    args.out.mkdir(parents=True,exist_ok=True)
    with gzip.open(args.out/'streetscape.tsv.gz','wt',encoding='utf8')as out:
        for (x,y,z),(before,after) in sorted(changes.items()):out.write(f'{x}\t{y}\t{z}\t{before}\t{after}\n')
    result={'new_shop_houses':placed,'existing_blocks':[dict(cx=x,cz=z,edits=n) for (x,z),n in sorted(counts.items())],'regional_facade_cells':dict(regional),'total_edits':len(changes)}
    (args.out/'streetscape.json').write_text(json.dumps(result,indent=1),'utf8');print(len(placed),len(counts),len(changes),flush=True)
if __name__=='__main__':main()
