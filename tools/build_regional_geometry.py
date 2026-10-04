"""Construct the commissioned regional world from measured terrain and native MTR geometry."""
from pathlib import Path
import argparse,json,math
import numpy as np
from regional_voxels import Painter,ROOT,WORLD,OUT
from regional_architecture import *


def load(name):return json.loads((OUT/name).read_text(encoding='utf-8'))


def rail_space(samples):
    occupied=set()
    for rail in samples:
        for x,y,z in rail['points'][::3]:
            if y<0:continue
            cx,cz=round(x)//8,round(z)//8
            occupied.update((cx+dx,cz+dz) for dx in range(-2,3) for dz in range(-2,3))
    return occupied


def street(p,a,b,width,owner):
    ax,ay,az=a;bx,by,bz=b;n=max(abs(bx-ax),abs(bz-az))
    # Shape a supported road bench locally, including roads outside building plots.
    for start in range(0,n+1,32):
        stop=min(n,start+31)
        xa=round(ax+(bx-ax)*start/max(1,n));za=round(az+(bz-az)*start/max(1,n))
        xb=round(ax+(bx-ax)*stop/max(1,n));zb=round(az+(bz-az)*stop/max(1,n))
        yy=round(ay+(by-ay)*(start+stop)/2/max(1,n))
        p.grade(min(xa,xb)-width//2,min(za,zb)-width//2,max(xa,xb)+width//2,max(za,zb)+width//2,yy,owner,3)
    for i in range(n+1):
        x=round(ax+(bx-ax)*i/max(1,n));y=round(ay+(by-ay)*i/max(1,n));z=round(az+(bz-az)*i/max(1,n))
        x0,x1=(x-width//2,x+width//2) if ax==bx else (x,x)
        z0,z1=(z-width//2,z+width//2) if az==bz else (z,z)
        p.fill(x0,y-4,z0,x1,y-1,z1,'minecraft:stone',owner)
        p.fill(x0,y,z0,x1,y,z1,'minecraft:black_concrete',owner)
        p.fill(x0,y+1,z0,x1,y+6,z1,AIR,owner)
        if i%10<5:p.put(x,y,z,'minecraft:white_concrete',owner)
        if i%48==0:street_light(p,x0-2 if ax==bx else x,z0 if ax==bx else z0-2,y,owner)


def districts(p,plan,samples):
    occupied=rail_space(samples);survey=np.asarray(load('native_surface_survey.json')['native_heights'])
    def native(x,z):
        index=np.argmin((survey[:,0]-x)**2+(survey[:,2]-z)**2);return int(survey[index,1])-1
    reserves=[(-445,-260,685,835),(-975,-780,110,205),(440,1250,1030,1540),(-2190,-1410,-350,110),(-65,175,-175,90)]
    count=0
    for zone in plan['zones']:
        if zone['kind']!='district':continue
        x0,x1,z0,z1=zone['bounds'];step=zone['spacing'];base=zone['floor'];name=zone['id']
        def fy(x):return round(80+16*max(0,min(1,(-230-x)/490))) if name=='tokyo_west' else base
        xs=list(range(x0+step//2,x1-step//2+1,step));zs=list(range(z0+step//2,z1-step//2+1,step))
        for gx,x in enumerate(xs):
            for gz,z in enumerate(zs):
                floor=fy(x);owner=f'{name}/{gx+1:02d}-{gz+1:02d}';half=17 if step==56 else 21
                if any(a-26<=x<=b+26 and c-26<=z<=d+26 for a,b,c,d in reserves):continue
                if any((xx//8,zz//8) in occupied for xx in (x-half,x,x+half) for zz in (z-half,z,z+half)):continue
                h=native(x,z)
                if h>floor+24 or h<floor-22:continue
                code=(gx*31+gz*17+len(name))%23
                b=(x-half,x+half,z-half,z+half)
                if code in (0,9,19):park(p,b,floor,owner);continue
                style='residential' if code%4<2 else 'office'
                levels=3+code%5 if name!='new_hakone' else 3+code%7
                if name=='tokyo_north' and code%7==0:levels=10+code%3
                building(p,b,floor,levels,owner,style,code);count+=1
        for x in range(x0,x1+1,step):street(p,(x,fy(x),z0),(x,fy(x),z1),9,name+'/street')
        for z in range(z0,z1+1,step):street(p,(x0,fy(x0),z),(x1,fy(x1),z),9,name+'/street')
    # Arterials tie the new wards into measured gaps between the existing moving lots.
    street(p,(-110,80,-520),(-110,80,-4),13,'regional/north_arterial')
    street(p,(-760,96,200),(-230,80,200),13,'regional/west_arterial')
    street(p,(-230,80,200),(-194,80,200),11,'regional/west_core_join')
    street(p,(-360,80,680),(-360,80,700),13,'regional/nerv_approach')
    p.meta['city_buildings']=count


def tracks_and_stations(p,transit,samples):
    if (WORLD/'native_transit_r22.json').is_file():
        raise RuntimeError('The installed R22 through-service layout retired C1 and its full original pier components; legacy regional transit geometry is not admitted. Use the current native rail/civil recipe.')
    for rail in samples:
        if rail['mode']!='TRAIN':continue
        owner='rail/'+rail['id'];cells={tuple(map(round,point)) for point in rail['points']}
        for x,y,z in cells:
            mode='owned' if x>=111 and z<20 and y<0 else 'new'
            p.fill(x-3,y-2,z-3,x+3,y-1,z+3,DARK,owner)
            p.fill(x-2,y,z-2,x+2,y+6,z+2,AIR,owner,mode)
            if x%16==0 and z%4==0:
                bottom=-489 if y<0 else 38
                p.fill(x,y-3,z,x,y-3,z,STEEL,owner)
                # Slender engineered bridge piers, confined to each railway.
                p.fill(x,bottom,z,x,y-3,z,'minecraft:polished_basalt[axis=y]',owner,'air')
    for platform in transit['platforms']:
        if platform.get('mode')=='AIRPLANE':continue
        x,y,z=platform['center'];length=platform['length'];axis=platform['heading'];owner='station/'+platform['id']
        horizontal=axis in ('E','W');half=length//2+10
        b=(x-half,x+half,z-15,z+15) if horizontal else (x-15,x+15,z-half,z+half)
        x0,x1,z0,z1=b
        if y>=75:p.grade(x0,z0,x1,z1,y,owner,12)
        elif y>=0:p.fill(x0,y-3,z0,x1,y-1,z1,DARK,owner)
        else:p.fill(x0,-490,z0,x1,y-1,z1,'minecraft:deepslate_bricks',owner,'new')
        mode='owned' if platform['id']=='U2_hangar' else 'new'
        box_room(p,b,y,11,owner,WHITE,mode)
        # Track trench remains open; platform tops are one metre above rail bed.
        if horizontal:
            p.fill(x0,y,z-2,x1,y+7,z+2,AIR,owner,mode)
            p.fill(x0,y-1,z-2,x1,y-1,z+2,DARK,owner)
            for zz in (z-4,z+4):p.fill(x0+2,y,zz,x1-2,y,zz,'minecraft:yellow_terracotta',owner)
            for xx in range(x0+8,x1-7,12):bench(p,xx,z-8,y,owner);bench(p,xx,z+8,y,owner,'north')
            opening(p,x,z0,y,owner,'north',7,5,mode='new');opening(p,x,z1,y,owner,'south',7,5,mode='new')
            p.sign(x,y+5,z0-1,[platform['name'],platform['line'],'改札 / CONCOURSE',''],owner,'north')
            # Passenger footbridge keeps cross-platform circulation off the tracks.
            p.fill(x-3,y+6,z0+2,x+3,y+6,z1-2,FLOOR,owner)
            stairs(p,x,z0+3,y,6,'south',owner,3)
            stairs(p,x,z1-3,y,6,'north',owner,3)
        else:
            p.fill(x-2,y,z0,x+2,y+7,z1,AIR,owner,mode)
            p.fill(x-2,y-1,z0,x+2,y-1,z1,DARK,owner)
            for xx in (x-4,x+4):p.fill(xx,y,z0+2,xx,y,z1-2,'minecraft:yellow_terracotta',owner)
            for zz in range(z0+8,z1-7,12):bench(p,x-8,zz,y,owner,'east');bench(p,x+8,zz,y,owner,'west')
            opening(p,x0,z,y,owner,'west',7,5,mode='new');opening(p,x1,z,y,owner,'east',7,5,mode='new')
            p.sign(x0-1,y+5,z,[platform['name'],platform['line'],'改札 / CONCOURSE',''],owner,'west')
            p.fill(x0+2,y+6,z-3,x1-2,y+6,z+3,FLOOR,owner)
            stairs(p,x0+3,z,y,6,'east',owner,3);stairs(p,x1-3,z,y,6,'west',owner,3)
        p.meta['landmarks'].append(dict(id=owner,bounds=b,floor=y,style='station',platform=platform))
    # Shared surface concourses and the two underground headquarters platforms.
    for x,y,z0,z1 in [(-120,80,-200,-136),(30,-467,490,522)]:
        owner=f'interchange/{x}/{y}'
        p.fill(x-8,y+6,z0-10,x+8,y+6,z1+10,FLOOR,owner)
        p.fill(x-8,y+7,z0-10,x+8,y+11,z1+10,AIR,owner)
        for xx in (x-9,x+9):p.fill(xx,y+7,z0-10,xx,y+8,z1+10,GLASS,owner)
    # Open the underground terminal passages after the station walls are authored.
    for sx,gate_x,join_z,end_z in [(740,650,1180,1190),(-1670,-1610,-270,-265)]:
        owner='airport/rail_transfer'
        p.fill(min(sx,gate_x)-3,71,join_z-3,max(sx,gate_x)+3,71,join_z+3,FLOOR,owner)
        p.fill(min(sx,gate_x)-3,72,join_z-3,max(sx,gate_x)+3,75,join_z+3,AIR,owner)
        p.fill(sx-3,71,min(join_z,end_z),sx+3,71,max(join_z,end_z),FLOOR,owner)
        p.fill(sx-3,72,min(join_z,end_z),sx+3,75,max(join_z,end_z),AIR,owner)


def airports(p,transit):
    for key,ox,rz,mirror,label in [('bay',480,1430,False,'箱根湾空港'),('hakone',-2160,-20,True,'新箱根飛行場')]:
        owner='airport/'+key;floor=80
        p.grade(ox-20,rz-310,ox+740,rz+100,floor,owner,48)
        p.fill(ox-10,floor,rz-300,ox+730,floor,rz+95,'minecraft:gray_concrete',owner)
        for z in (rz,rz+60):
            p.fill(ox+25,floor,z-18,ox+655,floor,z+18,'minecraft:black_concrete',owner)
            for x in range(ox+35,ox+650,24):p.fill(x,floor,z-1,x+10,floor,z+1,WHITE,owner)
            for x in (ox+42,ox+630):
                for zz in range(z-14,z+15,4):p.fill(x-2,floor,zz,x+8,floor,zz+1,WHITE,owner)
            for x in range(ox+25,ox+656,32):
                for zz in (z-20,z+20):p.put(x,floor+1,zz,LIGHT,owner)
        gate_x=ox+(550 if mirror else 170)
        sx,sy,sz=(740,65,1190) if key=='bay' else (-1670,65,-265)
        terminal=(sx-100,sx+100,rz-380,rz-305)
        p.grade(terminal[0]-6,terminal[2]-6,terminal[1]+6,terminal[3]+6,floor,owner+'/terminal',16)
        box_room(p,terminal,floor,20,owner+'/terminal',WHITE)
        x0,x1,z0,z1=terminal
        for z in (z0,z1):p.fill(x0+3,floor+3,z,x1-3,floor+15,z,'minecraft:light_gray_stained_glass',owner)
        for x in range(x0+8,x1-7,16):
            p.fill(x,floor+1,z0+13,x+8,floor+2,z0+13,DARK,owner)
            bench(p,x+4,z0+40,floor,owner);bench(p,x+4,z0+55,floor,owner,'north')
        opening(p,(x0+x1)//2,z0,floor,owner,'north',13,7,mode='new')
        # Passenger underpasses cross taxiways below ground; fixed structures
        # never occupy the swept wing volume of a taxiing A320.
        opening(p,sx,z1,floor,owner,'south',7,5,mode='new')
        p.fill(sx-3,71,z1-2,sx+3,71,sz,FLOOR,owner)
        p.fill(sx-3,72,z1-2,sx+3,75,sz,AIR,owner)
        stairs(p,sx,z1+6,71,9,'north',owner+'/terminal_access',5)
        join_z=rz-250
        p.fill(min(sx,gate_x)-3,71,join_z-3,max(sx,gate_x)+3,71,join_z+3,FLOOR,owner)
        p.fill(min(sx,gate_x)-3,72,join_z-3,max(sx,gate_x)+3,75,join_z+3,AIR,owner)
        p.fill(gate_x-3,71,join_z,gate_x+3,71,rz-234,FLOOR,owner)
        p.fill(gate_x-3,72,join_z,gate_x+3,76,rz-234,AIR,owner)
        stairs(p,gate_x,rz-234,71,9,'south',owner+'/apron_access',5)
        p.fill(gate_x-3,80,rz-225,gate_x+3,80,rz-192,FLOOR,owner)
        p.sign(gate_x,floor+7,z0-1,[label,'TERMINAL 1','到着 / 出発','RAIL / AIR'],owner)
        p.chest(x0+5,floor+1,z0+5,[('minecraft:bread',32),('minecraft:paper',32)],owner)
        # Operations tower, hangars and cargo servicing are separate buildings.
        tower_x=ox+575;tower_z=rz-330
        building(p,(tower_x-10,tower_x+10,tower_z-12,tower_z+12),floor,8,owner+'/管制塔','office',3)
        for n in range(2):
            hx=ox+335+n*105;hz=rz-230
            box_room(p,(hx-42,hx+42,hz-20,hz+20),floor,30,owner+f'/整備庫{n+1}',WALL)
            opening(p,hx,hz+20,floor,owner,'south',31,16,mode='new')
            p.chest(hx-36,floor+1,hz-14,[('minecraft:iron_ingot',32),('minecraft:redstone',32)],owner)
        p.meta['landmarks'].append(dict(id=owner,bounds=[ox-20,ox+740,rz-310,rz+100],floor=floor,style='airport',gate=[gate_x,81,rz-190]))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--part',choices=['surface','transit','airports','underground','all'],default='all');parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    plan=load('regional_plan.json');transit=load('transit_plan.json');samples=load('transit2/track_samples.json');p=Painter()
    if args.part in ('surface','all'):districts(p,plan,samples)
    if args.part in ('airports','all'):airports(p,transit)
    if args.part in ('transit','all'):tracks_and_stations(p,transit,samples)
    if args.part in ('underground','all'):
        from build_regional_underground import build_underground
        build_underground(p)
    name='geometry_'+args.part
    p.apply(name) if args.apply else p.save_plan(name)

if __name__=='__main__':main()
