"""Whole new street blocks with exact old-state/NBT inverse; no world write entry."""
from pathlib import Path
from collections import Counter,deque
import argparse,gzip,json,math,hashlib
import numpy as np
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from regional_voxels import canonical_state
from city_period_architecture_r44 import author as period_author
from tv_landmark_architecture_r44 import school as tv_school,gym as tv_gym,misato_home as tv_misato_home,school_entrance
from city_roof_r44 import compact_roof
from compact_tv_household_r44 import author as compact_tv_household
from tv_apartment_finish_r44 import author as finish_tv_apartment

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';ART=ROOT/'artifacts/rebuild_r44'
SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand','minecraft:sandstone','minecraft:clay','minecraft:coarse_dirt','minecraft:rooted_dirt','minecraft:podzol','minecraft:mud','minecraft:andesite','minecraft:diorite','minecraft:granite'}
SMALL={'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:poppy','minecraft:dandelion','minecraft:cornflower','minecraft:snow'}
PAVING={'minecraft:smooth_stone','minecraft:black_concrete','minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:polished_blackstone_slab','minecraft:smooth_stone_slab','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}


def design(name):
    if name=='hakone_west':
        # This replacement site follows the measured level west street, not
        # the rejected south cliff. Each body has a distinct use and volume.
        buildings=[
            dict(id='r44/hakone_west_new/home',kind='compact_home',label='西町住宅',storeys=2,bounds=[-1936,483,-1928,495]),
            dict(id='r44/hakone_west_new/shop',kind='local_shop',label='西町生活店',storeys=1,bounds=[-1922,484,-1910,495]),
            dict(id='r44/hakone_west_new/clinic',kind='clinic',label='西町診療所',storeys=2,bounds=[-1904,478,-1888,495]),
            dict(id='r44/hakone_west_new/inn',kind='small_inn',label='西坂旅館',storeys=2,bounds=[-1967,483,-1952,499],facing='east'),
            dict(id='r44/hakone_west_new/apartment',kind='apartment',label='西坂共同住宅',storeys=3,bounds=[-1960,509,-1952,523],facing='east'),
            dict(id='r44/hakone_west_new/civic',kind='civic',label='西町集会所',storeys=1,bounds=[-1904,528,-1888,540],facing='north')]
        # Narrow apartment uses its own compact circulation plan. Its stepped
        # body is widened westward only where the full survey gives <=5m fill.
        buildings[4]['bounds']=[-1962,509,-1952,520]
        return dict(id=name,bounds=[-1980,-1870,466,554],buildings=buildings,
            road_lines=[[-1944,504,-1880,504],[-1944,520,-1880,520],[-1944,504,-1944,520]],
            anchors=[[-1880,504],[-1880,520]],fixed_road_feet=105,
            operating_platform='3559976582378878399',station='新箱根中央 S1 / R1',
            reference='Measured level western street pocket; original compact home, narrow shop, courtyard clinic, tiled inn, stepped apartment and low civic hall. Source south-cliff candidate remains rejected.')
    if name=='tokyo_north':
        buildings=[]
        types=[('shophouse',3,'社区商住'),('book_office',3,'街角书店 / 事务所'),('clinic',2,'北町诊所'),('civic',2,'北町公民会馆'),
               ('terraced_home',2,'北町住宅'),('apartment',4,'北町共同住宅'),('coffee_house',2,'街角喫茶'),('local_shop',2,'生活用品店')]
        for n,(kind,floors,label) in enumerate(types):
            x=-208+(n%4)*48;z=-614+(n//4)*48;buildings.append(dict(id=f'r44/tokyo_north_new/{n+1:02d}',kind=kind,label=label,storeys=floors,bounds=[x,z,x+28,z+24]))
        buildings[0]['bounds']=[-200,-614,-172,-590]
        buildings[0]['bounds']=[-200,-614,-182,-598];buildings[0]['storeys']=2
        buildings[1]['bounds']=[-160,-614,-138,-590]
        buildings[3]['bounds']=[-64,-606,-32,-597];buildings[3]['storeys']=1
        buildings[4]['kind']='compact_home';buildings[4]['bounds']=[-208,-566,-200,-555]
        buildings[5]['bounds']=[-164,-566,-132,-548]
        buildings[6]['bounds']=[-112,-566,-92,-550];buildings[6]['storeys']=1
        buildings[7]['bounds']=[-64,-566,-46,-551];buildings[7]['storeys']=1
        buildings.append(dict(id='r44/tokyo_north_new/09',kind='compact_home',label='北町住宅二号',storeys=2,bounds=[-196,-566,-188,-555]))
        for b in buildings[4:]:b['facing']='north'
        return dict(id=name,bounds=[-232,156,-636,-516],buildings=buildings,road_lines=[[-224,-580,-16,-580],[-16,-580,-16,-536],[-16,-536,140,-536],[140,-536,140,-520]],
            engineered_street='Lower neighbourhood streetY71..73 follows the real valley. New156m east connector climbs8m at5.1% to the actualY81 existing city port. North ridge is retained.',
            anchors=[[140,-520]],operating_platform='-7008638758418776874',station='第三新东京中央',reference='1989 Shibuya Center-gai narrow storefront rhythm; old Tokyo station forecourts; original mixed street-block plan')
    if name=='hakone_south':
        types=[('terraced_home',2,'南坂住宅'),('small_inn',3,'南坂旅馆'),('local_shop',2,'地方商店'),('civic',2,'南坂集会所'),('terraced_home',2,'山麓住宅'),('book_office',3,'地方事务所')]
        buildings=[]
        for n,(kind,floors,label) in enumerate(types):
            x=-1744+(n%2)*60;z=1058+(n//2)*34;buildings.append(dict(id=f'r44/hakone_south_new/{n+1:02d}',kind=kind,label=label,storeys=floors,bounds=[x,z,x+28,z+24]))
        for i in [0,4]:buildings[i]['kind']='compact_home';x,z,X,Z=buildings[i]['bounds'];buildings[i]['bounds']=[x+10,z,x+18,z+11]
        buildings[1]['bounds']=[-1684,1058,-1662,1076]
        buildings[2]['bounds']=[-1744,1092,-1726,1107];buildings[2]['storeys']=1
        buildings[3]['bounds']=[-1684,1092,-1652,1108];buildings[3]['storeys']=1
        buildings[5]['bounds']=[-1684,1126,-1662,1142];buildings[5]['storeys']=2
        return dict(id=name,bounds=[-1760,-1640,1008,1172],buildings=buildings,road_lines=[[-1752,1050,-1648,1050],[-1752,1160,-1648,1160],[-1752,1050,-1752,1160],[-1648,1050,-1648,1160],[-1752,1084,-1648,1084],[-1752,1118,-1648,1118],[-1696,1050,-1696,1016]],
            anchors=[[-1694,1016]],operating_platform='3559976582378878399',station='新箱根中央 S1 / R1',reference='1991 Hakone-Yumoto storefront covered footway; hillside town with planted separations rather than copied skyscrapers')
    if name=='kirisato_north':
        buildings=[dict(id='r44/kirisato_north_new/G',kind='gallery_danchi',label='霧里北 G棟',storeys=4,bounds=[-2888,-1288,-2844,-1264]),
            dict(id='r44/kirisato_north_new/H',kind='gallery_danchi',label='霧里北 H棟',storeys=4,bounds=[-2888,-1224,-2844,-1200]),
            dict(id='r44/kirisato_north_new/shop',kind='local_shop',label='団地生活店',storeys=2,bounds=[-2872,-1182,-2858,-1168],facing='north'),
            dict(id='r44/kirisato_north_new/clinic',kind='clinic',label='団地診疗所',storeys=2,bounds=[-2854,-1182,-2838,-1168])]
        return dict(id=name,bounds=[-2920,-2812,-1320,-1128],buildings=buildings,road_lines=[[-2904,-1308,-2828,-1308],[-2904,-1308,-2904,-1164],[-2828,-1308,-2828,-1152],[-2904,-1256,-2828,-1256],[-2904,-1192,-2828,-1192],[-2828,-1152,-2840,-1152],[-2840,-1152,-2840,-1136]],
            engineered_street='North streetY75; west street rises2m/144m while east street descends4m/144m to the realY71 housing-city port. All cross streets interpolate the complete same datum field.',
            anchors=[[-2840,-1136]],operating_platform='9030722757170331109',station='霧里住宅区',reference='Original TV-inspired gallery residences; UR1989 Tama-daira horizontal bands and1994 Hanamigawa curved low streets are separate environmental references, not Rei room prototypes')
    raise ValueError(name)


def main():
    p=argparse.ArgumentParser();p.add_argument('district',choices=['tokyo_north','hakone_south','hakone_west','kirisato_north']);p.add_argument('output',type=Path);p.add_argument('--baseline-plan',type=Path);p.add_argument('--design-file',type=Path);a=p.parse_args();assert not a.output.exists()
    d=json.loads(a.design_file.read_text('utf8')) if a.design_file else design(a.district);x0,x1,z0,z1=d['bounds'];w=MeasuredWorld(WORLD);w.box((x0-12,40,z0-12),(x1+12,220,z1+12));w.load()
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x0-12,40,z0-12),(x1+12,220,z1+12),selected_chunks=set(w.selected)))
    if a.baseline_plan:
        baseline=[json.loads(line) for line in gzip.open(a.baseline_plan/'forward.jsonl.gz','rt',encoding='utf8')]
        original={tuple(r['pos']):r['before'] for r in baseline};actual_get=w.get
        def original_get(x,y,z):return original.get((math.floor(x),math.floor(y),math.floor(z)),actual_get(x,y,z))
        w.get=original_get
        for r in baseline:
            if r.get('before_nbt') is None:tags.pop(tuple(r['pos']),None)
    raw=np.load(ART/'surface_network/road_complete_authority_stage3.columns.npz');oldroads={tuple(map(int,q)):(float(f),int(g)) for q,f,g in zip(raw['coordinates'],raw['actual_feet'],raw['flags'])}
    if a.district=='hakone_south':d['road_lines'][-1]=[-1694,1050,-1694,1016]
    proposed={};newtags={};held=[];cases=[];rooms=[];flights=[];floors=[];ground_cache={};wet_cache={};culverts=[];approaches={}
    original_ownership=json.loads((ART/'city_buildings/actual_authored_ownership.json').read_text('utf8'))['buildings'];original_boxes={}
    for old_building in original_ownership:
        lo,hi=old_building['planned_bounds']
        for cx in range(lo[0]//32,hi[0]//32+1):
            for cz in range(lo[2]//32,hi[2]//32+1):original_boxes.setdefault((cx,cz),[]).append((lo,hi,old_building['id']))
    declared_port_repairs={tuple(q[:2]):round(q[2]*2) for q in d.get('native_port_half_step_repairs',[])}
    def ground(x,z):
        if (x,z) not in ground_cache:
            ys=[y for y in range(40,191) if (w.get(x,y,z) or '').split('[')[0] in SOIL];ground_cache[x,z]=max(ys) if ys else None
            watery=[y for y in range(40,191) if (w.get(x,y,z) or '').split('[')[0]=='minecraft:water'];wet_cache[x,z]=max(watery) if watery else None
        return ground_cache[x,z]
    def put(q,state,owner,reason):
        q=tuple(map(int,q));old=w.block(q)
        for lo,hi,identity in original_boxes.get((q[0]//32,q[2]//32),[]):
            if all(lo[k]<=q[k]<=hi[k] for k in range(3)):
                held.append(dict(pos=q,state=old,original_owner=identity,reason='Original authored building full3D ownership is HARD; material/paving class never grants a new parcel permission'));return
        if old is None or q in tags or old.split('[')[0] not in SOIL|SMALL|PAVING|AIR:
            held.append(dict(pos=q,state=old,full_nbt=tags[q].snbt() if q in tags else None,owner=owner,reason=reason));return
        if math.hypot(q[0]-32,q[2]-217)<250:held.append(dict(pos=q,reason='Protected central settled combat core'));return
        state=canonical_state(state)
        if not any(st in state for st in ['_sign','_bed','minecraft:chest']):newtags.pop(q,None)
        if state==old:proposed.pop(q,None)
        else:proposed[q]=(state,owner,reason)
    def fill(box,state,owner,reason):
        x,y,z,X,Y,Z=box
        for yy in range(y,Y+1):
            for zz in range(z,Z+1):
                for xx in range(x,X+1):put((xx,yy,zz),state,owner,reason)
    def sign(q,text,owner,facing='south'):
        put(q,f'minecraft:birch_wall_sign[facing={facing},waterlogged=false]',owner,'Supported original public sign')
        face=nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':s},ensure_ascii=False)) for s in (text,'入口 / 出口','公共通路',owner.split('/')[-1])]),'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
        newtags[tuple(q)]=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'front_text':face,'back_text':nbtlib.parse_nbt(face.snbt()),'is_waxed':nbtlib.Byte(1)}).snbt()
    def door(x,y,z,owner,facing='south'):
        for dy,half in [(1,'lower'),(2,'upper')]:put((x,y+dy,z),f'projectseele:city_personnel_door[facing={facing},half={half},hinge=left,open=false,powered=false]',owner,'Complete manual public personnel door pair')
    def bed(x,y,z,owner):
        for zz,part in [(z,'foot'),(z-1,'head')]:
            put((x,y,zz),f'minecraft:white_bed[facing=north,occupied=false,part={part}]',owner,'Complete usable domestic bed, separate from public circulation')
            newtags[x,y,zz]=nbtlib.Compound({'id':nbtlib.String('minecraft:bed'),'x':nbtlib.Int(x),'y':nbtlib.Int(y),'z':nbtlib.Int(zz)}).snbt()
    def pavement(x,z,h2,carriage,owner):
        if owner!=('r44/'+a.district+'/complete_new_streets'):approaches[x,z]=(h2,owner)
        if owner!=('r44/'+a.district+'/complete_new_streets') and (x,z) in columns:return
        y=(h2-1)//2;g=ground(x,z)
        previous=oldroads.get((x,z))
        if previous and previous[1]&7==7 and (x,z) not in declared_port_repairs:
            if abs(previous[0]-h2/2)>.001:held.append(dict(pos=[x,h2/2,z],old_public_feet=previous[0],reason='New complete street datum must preserve the effective old port'))
            return
        if g is None:held.append(dict(pos=[x,y,z],owner=owner,reason='No whole measured natural grass bearing; no wetland filling or inferred street'));return
        water=wet_cache.get((x,z))
        if water is not None and water>=g:
            if y-1<=water:held.append(dict(pos=[x,y,z],owner=owner,reason='Wetland crossing needs complete raised culvert clearance, not filling'));return
            put((x,y-1,z),'minecraft:iron_block',owner,'Continuous full-width founded culvert deck preserves the measured shallow water channel below')
            culverts.append(dict(pos=[x,z],water_y=water,bearing_y=g,deck_y=y-1,water_preserved=True))
        else:
            for yy in range(min(g+1,y-2),y):put((x,yy,z),'minecraft:stone',owner,'Full natural bearing formation, never a floating street')
        if h2%2:state=('minecraft:polished_blackstone_slab' if carriage else 'minecraft:smooth_stone_slab')+'[type=bottom,waterlogged=false]'
        else:state='minecraft:black_concrete' if carriage else 'minecraft:smooth_stone'
        put((x,y,z),state,owner,'Whole-width carriageway or continuous public footway')
        for yy in range(y+1,y+7):put((x,yy,z),'minecraft:air',owner,'Preserve full route clearance with actual existing component guards')
    centres={}
    for x,z,X,Z in d['road_lines']:
        length=max(abs(X-x),abs(Z-z))
        for i in range(length+1):centres[round(x+(X-x)*i/max(1,length)),round(z+(Z-z)*i/max(1,length))]=None
    heights={q:round((ground(*q)+1)*2) if ground(*q) is not None else None for q in centres}
    for x,z in centres:
        water=[]
        for dx,dz in [(i,0) for i in range(-6,7)]+[(0,i) for i in range(-6,7)]:
            ground(x+dx,z+dz);wy=wet_cache.get((x+dx,z+dz))
            if wy is not None:water.append(wy)
        if heights[x,z] is not None and water:heights[x,z]=max(heights[x,z],2*(max(water)+3))
    for q in map(tuple,d['anchors']):
        assert q in oldroads and oldroads[q][1]&7==7,(q,'Actual old public street anchor missing/blocked');heights[q]=round(oldroads[q][0]*2)
    locked=set(map(tuple,d['anchors']))
    for q in centres:
        previous=oldroads.get(q)
        if previous and previous[1]&7==7:heights[q]=round(previous[0]*2);locked.add(q)
    if 'fixed_road_feet' in d:
        for q in heights:
            if q not in locked:heights[q]=round(d['fixed_road_feet']*2)
    if a.district=='tokyo_north':
        for x,z in heights:
            if (x,z) not in locked:
                feet=71+2*min(1,max(0,(x+224)/208)) if z<-536 else 73+8*min(1,max(0,(x+16)/156))
                if d.get('east_valley_expansion') and x>=32 and z<-536:
                    # Only the west collector climbs to the old elevated
                    # port. The east valley loops keep their real low datum,
                    # rather than lifting every eastern parcel by13m.
                    west=68+7.5*min(1,max(0,(z+712)/176));valley=68+4*min(1,max(0,(z+712)/156));blend=min(1,max(0,(76-x)/44));feet=valley+(west-valley)*blend
                heights[x,z]=round(feet*2)
    if a.district=='kirisato_north':
        for x,z in heights:
            if (x,z) not in locked:
                t=min(1,max(0,(z+1308)/144));west=min(1,max(0,(-2828-x)/76))
                feet=75+t*(2*west-4*(1-west));heights[x,z]=round(feet*2)
                if d.get('housing_east_expansion') and x>-2828:
                    blend=min(1,max(0,(-2728-x)/100));valley=69-1*t;feet=valley+((75-4*t)-valley)*blend;heights[x,z]=round(feet*2)
                if d.get('housing_dryland_expansion') and x>-2828:
                    feet=71+3*min(1,max(0,(-2828-x)/(-452))) if z>=-1140 else 74;heights[x,z]=round(feet*2)
    # A complete street graph, with half-block maximum adjacent datum change.
    for iteration in range(512):
        changed=False
        for q,h in list(heights.items()):
            if h is None:continue
            for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
                other=q[0]+dx,q[1]+dz;k=heights.get(other)
                if k is None or abs(h-k)<=1:continue
                if other not in locked:heights[other]=h+1 if k>h else h-1;changed=True
        if not changed:break
    columns={}
    for (x,z),h2 in heights.items():
        if h2 is None:held.append(dict(pos=[x,z],reason='Unmeasured natural street centre'));continue
        for dx in range(-6,7):
            for dz in range(-6,7):
                # Full13-column width for each actual cardinal road line.
                horizontal=any(z==b and min(a,c)<=x<=max(a,c) for a,b,c,e in d['road_lines'] if b==e)
                vertical=any(x==a and min(b,e)<=z<=max(b,e) for a,b,c,e in d['road_lines'] if a==c)
                if (horizontal and dx==0) or (vertical and dz==0):
                    q=x+dx,z+dz;distance=abs(dz) if horizontal and dx==0 else abs(dx)
                    if q not in columns or distance<columns[q][2]:
                        previous=oldroads.get(q)
                        columns[q]=(round(previous[0]*2),bool(previous[1]&16),distance) if previous and previous[1]&7==7 else (h2,distance<=4,distance)
    owner='r44/'+a.district+'/complete_new_streets'
    for q,h2 in declared_port_repairs.items():
        assert q in columns and (q not in oldroads or oldroads[q][1]&7==7)
        h,c,dist=columns[q];assert abs(h-h2)==1,'Only an explicit measured half-block road-port seam correction is allowed'
        columns[q]=(h2,c,dist)
    if d.get('east_valley_expansion') or d.get('housing_east_expansion') or d.get('housing_dryland_expansion') or d.get('generic_complete_column_smoothing'):
        fixed={q for q in columns if q in oldroads and oldroads[q][1]&7==7}
        for iteration in range(1024):
            changed=False
            for q in list(columns):
                h,carriage,distance=columns[q]
                for step in [(1,0),(0,1),(-1,0),(0,-1)]:
                    other=q[0]+step[0],q[1]+step[1]
                    if other not in columns:continue
                    k,c,distance2=columns[other]
                    if abs(h-k)<=1:continue
                    if other not in fixed:
                        columns[other]=(max(h-1,min(h+1,k)),c,distance2);changed=True
                    elif q not in fixed:
                        h=max(k-1,min(k+1,h));columns[q]=(h,carriage,distance);changed=True
            if not changed:break
    for (x,z),(h2,carriage,distance) in columns.items():pavement(x,z,h2,carriage,owner)
    if d.get('sports_field'):
        field=d['sports_field'];sx,sz,SX,SZ=field['bounds'];level=field['floor'];sport_owner='r44/tv_school/sports_field';profiles=[]
        for xx in range(sx-18,SX+19):
            for zz in range(sz-18,SZ+19):
                if (xx,zz) in columns:continue
                g=ground(xx,zz)
                dist=max(sx-xx,xx-SX,sz-zz,zz-SZ,0)
                if g is None or (wet_cache.get((xx,zz)) is not None and wet_cache[xx,zz]>=g):
                    if dist==0:held.append(dict(pos=[xx,level,zz],owner=sport_owner,reason='Bare sports field must use actual dry founded land, not fill water'))
                    continue
                blend=max(0,1-dist/18);new=round(g+(level-g)*blend)
                if abs(level-g)>8 and dist==0:held.append(dict(pos=[xx,level,zz],ground=g,reason='School sports floor exceeds bounded8m actual formation'));continue
                for yy in range(g+1,new):put((xx,yy,zz),'minecraft:stone',sport_owner,'Whole sports-field formation reaches the actual measured soil')
                put((xx,new,zz),'minecraft:coarse_dirt' if dist==0 else 'minecraft:grass_block[snowy=false]',sport_owner,'Bare school exercise field with actual18m planted transition back to the measured relief')
                for yy in range(new+1,max(new+3,g+2)):put((xx,yy,zz),'minecraft:air',sport_owner,'Whole graded sports-field headroom, never a floating bare rectangle')
                profiles.append(dict(pos=[xx,zz],ground=g,after_ground=new))
        d['sports_field']['actual_profiles']=profiles
    if d.get('school_sports_path'):
        owner='r44/tv_school/sports_access';points=d['school_sports_path'];foot=73
        for first,last in zip(points,points[1:]):
            length=max(abs(last[0]-first[0]),abs(last[1]-first[1]))
            for i in range(length+1):
                xx=round(first[0]+(last[0]-first[0])*i/max(1,length));zz=round(first[1]+(last[1]-first[1])*i/max(1,length))
                for side in [-1,0,1]:pavement(xx+(side if first[0]==last[0] else 0),zz+(side if first[1]==last[1] else 0),round(foot*2),False,owner)
    for b in d['buildings']:
        x,z,X,Z=b['bounds'];cx=(x+X)//2;cz=(z+Z)//2;facing=b.get('facing','south')
        entry_x,entry_z=(X+1,cz) if facing=='east' else (cx,z-1) if facing=='north' else (cx,Z+1)
        door_x,door_z=(X,cz) if facing=='east' else (cx,z) if facing=='north' else (cx,Z)
        if b['kind']=='gallery_danchi':
            facing='north';entry_x,entry_z=x+6,z-1;door_x,door_z=x+6,z;b['facing']='north'
        front_columns=[q for q in columns if (q[1]<=entry_z if facing=='north' else q[1]>=entry_z if facing=='south' else q[0]>=entry_x if facing=='east' else q[0]<=entry_x)]
        assert front_columns,(b['id'],'Declared entrance has no real street column in its outward half-space')
        nearest=min(front_columns,key=lambda q:(q[0]-entry_x)**2+(q[1]-entry_z)**2);roadFeet=columns[nearest][0]
        if roadFeet is None:continue
        f=math.ceil(roadFeet/2)-1;b['floor']=f;b['floor_feet']=[f+i*5+1 for i in range(b['storeys'])];roof=f+b['storeys']*5;b['roof']=roof
        material='minecraft:light_gray_concrete' if b['kind']=='gallery_danchi' else 'minecraft:smooth_sandstone' if b['kind'] in ['small_inn','terraced_home'] else 'minecraft:white_concrete'
        for xx in range(x,X+1):
            for zz in range(z,Z+1):
                g=ground(xx,zz)
                if g is None:held.append(dict(pos=[xx,f,zz],owner=b['id'],reason='Full building bearing not measured natural ground'));continue
                for yy in range(min(g+1,f-3),f):put((xx,yy,zz),'minecraft:stone',b['id'],'Complete new building footing reaches measured natural bearing')
        def entry_and_approach():
            for yy in range(f+1,f+3):put((door_x,yy,door_z),'minecraft:air',b['id'],'Actual complete ground entrance opening')
            door(door_x,f,door_z,b['id'],facing)
            sign((door_x+(0 if facing=='east' else 2),f+3,door_z+(1 if facing=='east' else -1 if facing=='north' else 1)),b['label'],b['id'],facing)
            route=[];qx,qz=entry_x,entry_z
            # A whole supported public footway reaches the measured street,
            # including east and north frontages. It never ends at a label.
            step=1 if nearest[0]>=qx else -1
            route.extend((xx,qz) for xx in range(qx,nearest[0]+step,step))
            step=1 if nearest[1]>=qz else -1
            route.extend((nearest[0],zz) for zz in range(qz,nearest[1]+step,step))
            for xx,zz in route:
                if facing=='east':
                    for dd in (-1,0,1):pavement(xx,zz+dd,2*(f+1),False,b['id'])
                else:
                    for dd in (-1,0,1):pavement(xx+dd,zz,2*(f+1),False,b['id'])
            b['entry']=[entry_x,f+1,entry_z];b['actual_street_handoff']=[nearest[0],roadFeet/2,nearest[1]]
            b['door']=[door_x,f+1,door_z];b['approach_columns']=[list(q) for q in route]
            normal={'south':(0,1),'north':(0,-1),'east':(1,0)}[facing]
            path=[]
            for xx,zz in route[::-1]:
                point=[xx+.5,columns[xx,zz][0]/2 if (xx,zz) in columns else f+1,zz+.5]
                if not path or point!=path[-1]:path.append(point)
            path.append([door_x-normal[0]+.5,f+1,door_z-normal[1]+.5])
            for suffix,pth in [('',path),('/return',path[::-1])]:cases.append(dict(id=b['id']+'/public_entry'+suffix,path=pth,door=b['door'],native_passed=False))
        if b['storeys']==1 and a.district=='tokyo_north':
            roof=f+4;b['roof']=roof;b['floor_feet']=[f+1]
            fill((x,f+1,z,X,roof+5,Z),'minecraft:air',b['id'],'Low independent public hall/shop envelope; one occupied storey has no invented public roof stair')
            fill((x,f,z,X,f,Z),'minecraft:smooth_stone',b['id'],'Continuous complete ground public room')
            fill((x,roof,z,X,roof,Z),'minecraft:smooth_stone',b['id'],'Supported low weather roof')
            for xx in [x,X]:fill((xx,f+1,z,xx,f+3,Z),material,b['id'],'Separate low public side wall')
            for zz in [z,Z]:fill((x,f+1,zz,X,f+3,zz),material,b['id'],'Thin low period shop/hall front')
            for zz in [z,Z]:fill((x+2,f+2,zz,X-2,f+2,zz),'minecraft:gray_stained_glass',b['id'],'Long low period public-room window band')
            if b['kind'] in ['civic','coffee_house']:
                for offset in range((Z-z)//2+1):
                    yy=roof+1+offset//2
                    for zz,heading in [(z+offset,'south'),(Z-offset,'north')]:fill((x-1,yy,zz,X+1,yy,zz),f'minecraft:brick_stairs[facing={heading},half=bottom,shape=straight,waterlogged=false]',b['id'],'Low long gable weather roof with real horizontal eaves')
                b['architecture']='Long single public hall under a low tiled ridge' if b['kind']=='civic' else 'Independent one-storey cafe with a low tiled gable, small public room and counter'
            else:
                fill((x,roof+1,z,X,roof+1,z),'minecraft:light_gray_concrete',b['id'],'Thin shop fascia above the actual glazed frontage')
                b['architecture']='Narrow one-storey period shopfront / long display window / low flat roof and fascia'
            if b['kind']!='civic':fill((X-2,f+1,z+3,X-2,f+1,Z-3),'minecraft:smooth_quartz',b['id'],'Actual shop/cafe counter kept off the circulation')
            b['roof_role']='Single-storey weather roof; no public roof access'
            b['landing_seed']=[x+3,z+3];rooms.append(dict(id=b['id']+'/floor1',kind=b['kind'],bounds=[x+1,f+1,z+1,X-1,f+3,Z-1],public_floor=True))
            entry_and_approach();floors.append(dict(id=b['id']+'/floor1',feet_y=f+1));continue
        if b['kind']=='compact_home' or (b['kind']=='apartment' and X-x<13):
            roof=f+4*b['storeys'];b['roof']=roof;b['floor_feet']=[f+i*4+1 for i in range(b['storeys'])]
            fill((x,f+1,z,X,roof+4,Z),'minecraft:air',b['id'],'Independent compact house, not a large shared apartment block')
            for level in range(b['storeys']+1):
                y=f+level*4;fill((x,y,z,X,y,Z),'minecraft:smooth_stone',b['id'],'Whole compact floor/roof')
                if level==b['storeys']:continue
                for xx in [x,X]:fill((xx,y+1,z,xx,y+3,Z),'minecraft:smooth_sandstone',b['id'],'Compact domestic side wall')
                for zz in [z,Z]:fill((x,y+1,zz,X,y+3,zz),'minecraft:smooth_sandstone',b['id'],'Compact domestic facade')
                edge=X-(level*2 if b['kind']=='apartment' else 0)
                if edge<X:
                    fill((edge+1,y+1,z,X,y+3,Z),'minecraft:air',b['id'],'True narrow apartment upper body retreats toward the retained west stair')
                    fill((edge,y+1,z,edge,y+3,Z),'minecraft:smooth_sandstone',b['id'],'Actual upper setback return wall')
                    fill((X,y+1,z,X,y+1,Z),'minecraft:light_gray_concrete',b['id'],'Supported low terrace edge outside the upper apartment body')
                    terraceZ=Z-3
                    for yy in range(y+1,y+3):put((edge,yy,terraceZ),'minecraft:air',b['id'],'Actual apartment-to-terrace opening through the setback wall')
                    door(edge,y,terraceZ,b['id'],'east')
                    terracepath=[[edge-.5,y+1,terraceZ+.5],[edge+1.5,y+1,terraceZ+.5]]
                    for suffix,pth in [('',terracepath),('/return',terracepath[::-1])]:cases.append(dict(id=b['id']+f'/terrace{level+1}'+suffix,path=pth,door=[edge,y+1,terraceZ],native_passed=False))
                fill((x+4,y+2,Z,min(x+6,edge-1),y+2,Z),'minecraft:gray_stained_glass',b['id'],'Separate small domestic window')
                bed(edge-2,y+1,z+4,b['id']);put((edge-1,y+1,z+7),'minecraft:water_cauldron[level=3]',b['id'],'Usable domestic wash basin')
                if level>0:fill((x+1,y,z+3,x+2,y,z+6),'minecraft:air',b['id'],'Explicit compact stair aperture with retained upper landing')
                if level<b['storeys']-1:
                    flights.append(dict(id=b['id']+'/private_stairs',from_feet=y+1,to_feet=y+5,width=2,heading='north'))
                    stairpath=[[x+1.5,y+1,z+7.5],[x+1.5,y+5,z+2.5],[x+3.5,y+5,z+2.5]]
                    for suffix,pth in [('',stairpath),('/return',stairpath[::-1])]:cases.append(dict(id=b['id']+f'/private_stairs{level+1}'+suffix,path=pth,native_passed=False))
                rooms.append(dict(id=b['id']+f'/floor{level+1}',kind='compact_home',bounds=[x+1,y+1,z+1,X-1,y+3,Z-1],public_floor=False))
            # Flights come after every upper-floor aperture. The old order
            # erased the final tread at the actual upper-floor plane.
            for level in range(b['storeys']-1):
                y=f+level*4
                for i in range(4):
                    yy=y+i+1;zz=z+6-i
                    fill((x+1,yy+1,zz,x+2,yy+3,zz),'minecraft:air',b['id'],'Whole compact flight headroom after the final upper-floor aperture')
                    fill((x+1,yy,zz,x+2,yy,zz),'minecraft:polished_andesite_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]',b['id'],'Complete four-step compact flight including its retained final tread')
            if b['kind']=='compact_home':
                compact_roof(b,lambda q:proposed[q][0] if q in proposed else w.block(q),put)
                b['architecture']='Independent9x13 home / own front door / planted side court / two-wide private stair / low tiled roof'
                b['roof_role']='Pitched domestic weather roof; no public roof route'
            else:
                b['architecture']='Narrow three-storey apartment / actual upper body setbacks and terraces / east entrance / independent two-wide private stair'
                b['roof_role']='Flat maintenance roof; no public roof route'
            entry_and_approach();b['landing_seed']=[x+3,z+2]
            floors.extend(dict(id=b['id']+f'/floor{n+1}',feet_y=y) for n,y in enumerate(b['floor_feet']));continue
        fill((x,f+1,z,X,roof+4,Z),'minecraft:air',b['id'],'Explicit new building envelope; preserve every existing non-natural state/NBT')
        for level in range(b['storeys']+1):
            y=f+level*5;fill((x,y,z,X,y,Z),'minecraft:smooth_stone',b['id'],'Whole new occupied floor or usable roof')
            if level==b['storeys']:continue
            for xx in [x,X]:fill((xx,y+1,z,xx,y+4,Z),material,b['id'],'Whole side wall')
            for zz in [z,Z]:fill((x,y+1,zz,X,y+4,zz),material,b['id'],'Whole facade wall')
            for xx in range(x+3,X-2,6):
                for zz in [z,Z]:fill((xx,y+2,zz,min(xx+2,X-2),y+3,zz),'minecraft:gray_stained_glass',b['id'],'Supported narrow period windows')
            # Side service strip is distinct from the full public stair core.
            for xx in range(x+13,X-2,8):
                fill((xx,y+1,z+7,xx+2,y+1,z+7),'minecraft:smooth_quartz',b['id'],'Working table or domestic counter outside the main circulation')
                put((xx,y+1,z+8),'minecraft:dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]',b['id'],'Usable side seating with clear approach')
            put((cx,y+4,(z+Z)//2),'minecraft:sea_lantern',b['id'],'Mounted interior luminaire')
            rooms.append(dict(id=b['id']+f'/floor{level+1}',kind=b['kind'],bounds=[x+1,y+1,z+1,X-1,y+4,Z-1],public_floor=True))
        # Complete stair landings are built before flights; no upper floor caps headroom.
        fill((x+1,f+1,z+2,x+9,roof+3,z+12),'minecraft:air',b['id'],'Whole separated public stair core')
        for level in range(b['storeys']+1):
            y=f+level*5
            for za,zb in [(z+2,z+4),(z+10,z+12)]:fill((x+1,y,za,x+9,y,zb),'minecraft:smooth_stone',b['id'],'Full landing at each real floor')
            fill((x+9,y,z+2,x+9,y,z+12),'minecraft:smooth_stone',b['id'],'Landing-to-room side passage')
            if level==b['storeys']:continue
            if level==b['storeys']-1 and b['kind'] in ['terraced_home','small_inn']:
                fill((x+1,roof,z+2,x+9,roof,z+12),'minecraft:smooth_stone',b['id'],'Full weather roof over the occupied public stair; no route into the low pitched attic')
                continue
            north=level%2==0;sx=x+(3 if north else 7);sz=z+(10 if north else 4);direction=-1 if north else 1
            for i in range(5):
                yy=y+i+1;zz=sz+direction*i
                fill((sx-1,yy+1,zz,sx+1,yy+4,zz),'minecraft:air',b['id'],'Whole flight headroom')
                fill((sx-1,y,zz,sx+1,yy-1,zz),'minecraft:polished_andesite',b['id'],'Full stair bearing')
                fill((sx-1,yy,zz,sx+1,yy,zz),f'minecraft:polished_andesite_stairs[facing={"north" if north else "south"},half=bottom,shape=straight,waterlogged=false]',b['id'],'Three-wide real stair flight')
            flights.append(dict(id=b['id']+f'/stairs{level+1}',from_feet=y+1,to_feet=y+6,width=3,heading='north' if north else 'south'))
            end=sz+direction*5
            fill((sx-1,y+5,end,sx+1,y+5,end),'minecraft:smooth_stone',b['id'],'Complete upper-flight transition into the retained floor landing')
            landingZ=z+(3.5 if north else 11.5)
            path=[[sx+.5,y+1,sz-direction+.5],[sx+.5,y+6,sz+direction*5+.5],[sx+.5,y+6,landingZ],[x+9.5,y+6,landingZ]]
            if level==b['storeys']-1 and b['kind']=='clinic' and a.district in ['tokyo_north','hakone_west']:
                path.extend([[x+9.5,y+6,z+12.5],[x+9.5,y+6,z+14.5]])
            elif level==b['storeys']-1 and b['kind'] not in ['terraced_home','small_inn']:
                path.extend([[x+9.5,y+6,z+3.5],[min(X-1,x+12)+.5,y+6,z+3.5]])
            elif b['kind']=='clinic' and a.district in ['tokyo_north','hakone_west']:
                path.append([x+9.5,y+6,z+3.5])
            elif b['kind']=='gallery_danchi':
                path.extend([[x+9.5,y+6,z+2.5],[x+12.5,y+6,z+2.5]])
            else:path.append([min(X-1,x+12)+.5,y+6,landingZ])
            for suffix,pth in [('',path),('/return',path[::-1])]:cases.append(dict(id=b['id']+f'/stairs{level+1}'+suffix,path=pth,native_passed=False))
        # Ground public door has a full supported approach, never a painted opening.
        if b['kind']=='clinic' and a.district in ['tokyo_north','hakone_west']:
            cutX=X-min(11,max(3,X-x-11));cutZ=z+min(8,max(4,Z-z-11))
            fill((cutX,f+1,z,X,roof+4,cutZ),'minecraft:air',b['id'],'Open forecourt removed from the clinic body to create a real L-shaped volume')
            fill((cutX,f,z,X,f,cutZ),'minecraft:smooth_stone',b['id'],'Supported public waiting court inside the clinic setback')
            fill((cutX,f+1,z,cutX,roof,cutZ),material,b['id'],'L-shaped courtyard return wall')
            fill((cutX,f+1,cutZ,X,roof,cutZ),material,b['id'],'L-shaped clinic court facade')
            courtDoor=min(X-1,cutX+1)
            for yy in range(f+1,f+3):put((courtDoor,yy,cutZ),'minecraft:air',b['id'],'Waiting court is connected to the clinic public room by a complete real door')
            door(courtDoor,f,cutZ,b['id'],'north')
            courtPath=[[courtDoor+.5,f+1,cutZ+1.5],[courtDoor+.5,f+1,cutZ-1.5]]
            for suffix,pth in [('',courtPath),('/return',courtPath[::-1])]:cases.append(dict(id=b['id']+'/waiting_court'+suffix,path=pth,door=[courtDoor,f+1,cutZ],native_passed=False))
            b['architecture']='Real L-shaped two-storey clinic / recessed outdoor waiting court / separate rear treatment room'
        if b['kind']=='apartment':
            for level in range(1,b['storeys']):
                y=f+level*5;edge=X-level*2
                fill((edge+1,y+1,z,X,roof+4,Z),'minecraft:air',b['id'],'Actual upper-storey retreat, not facade colour variation')
                fill((edge,y+1,z,edge,y+4,Z),material,b['id'],'Supported new setback facade')
                fill((edge+1,y,z,X,y,Z),'minecraft:smooth_stone',b['id'],'Usable terrace at the actual setback level')
                fill((X,y+1,z,X,y+1,Z),'minecraft:light_gray_concrete',b['id'],'Real supported setback terrace perimeter')
                terraceZ=Z-3
                for yy in range(y+1,y+3):put((edge,yy,terraceZ),'minecraft:air',b['id'],'Full opening connects each actual setback terrace to its apartment')
                door(edge,y,terraceZ,b['id'],'east')
                path=[[edge-.5,y+1,terraceZ+.5],[edge+1.5,y+1,terraceZ+.5]]
                for suffix,pth in [('',path),('/return',path[::-1])]:cases.append(dict(id=b['id']+f'/terrace{level+1}'+suffix,path=pth,door=[edge,y+1,terraceZ],native_passed=False))
            b['architecture']='Four-storey stepped apartment body / independent roof terraces / full retained west stair core'
        if b['kind']=='gallery_danchi':
            for level in range(b['storeys']):
                y=f+level*5
                fill((x+10,y+1,z,X-1,y+4,z+3),'minecraft:air',b['id'],'Continuous north exterior access gallery, not a generic sealed office')
                fill((x+10,y+1,z,X-1,y+1,z),'minecraft:light_gray_concrete',b['id'],'Supported low gallery parapet')
                fill((x+10,y+2,z,X-1,y+2,z),'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]',b['id'],'Fine exterior gallery guard on its actual parapet')
                fill((x+10,y+1,z+4,X-1,y+4,z+4),material,b['id'],'Separate apartment wall behind the full access gallery')
                units=max(1,(X-x-12)//10)
                for unit in range(units):
                    left=x+11+unit*10;right=min(left+9,X-1);entry=left+4
                    fill((left,y+1,z+4,left,y+4,Z-3),material,b['id'],'Individual occupied apartment boundary')
                    for yy in range(y+1,y+3):put((entry,yy,z+4),'minecraft:air',b['id'],'Real gallery-to-apartment opening')
                    door(entry,y,z+4,b['id'],'north');bed(left+2,y+1,Z-6,b['id'])
                    put((right-1,y+1,z+7),'minecraft:water_cauldron[level=3]',b['id'],'Small domestic washing basin in the room')
                    sign((entry+1,y+3,z+3),str((level+1)*100+unit+1),b['id'],'north')
                    path=[[entry+.5,y+1,z+2.5],[entry+.5,y+1,z+6.5]]
                    for suffix,pth in [('',path),('/return',path[::-1])]:cases.append(dict(id=b['id']+f'/unit{level+1}-{unit+1}'+suffix,path=pth,door=[entry,y+1,z+4],native_passed=False))
            b['architecture']='External north galleries / individual apartments / fine low guards / subdued end-wall number; original Rei402 and identity remain elsewhere'
        elif b['kind'] in ['terraced_home','small_inn']:
            # Low tiled gable has separate eaves, unlike flat office roofs.
            span=(X-x)//2
            for offset in range(span+1):
                yy=roof+1+offset//2
                for xx,heading in [(x+offset,'east'),(X-offset,'west')]:
                    fill((xx,yy,z-1,xx,yy,Z+1),f'minecraft:brick_stairs[facing={heading},half=bottom,shape=straight,waterlogged=false]',b['id'],'Original low clay-tile gable and supported eave')
            b['architecture']='Low tiled gable / separate timber-toned domestic and inn rooms'
            for level in range(b['storeys']):bed(X-4,f+level*5+1,Z-5,b['id'])
        elif b['kind'] in ['clinic','civic','book_office']:
            for level in range(b['storeys']):
                y=f+level*5
                roomZ=min(z+13,Z-3);innerX=min(X-3,max(x+12,cx))
                fill((x+10,y+1,roomZ,X-2,y+3,roomZ),'minecraft:light_gray_concrete',b['id'],'Real front waiting/reading room and rear work-room separation')
                door(innerX,y,roomZ,b['id'])
                if b['kind']=='book_office':fill((X-2,y+1,z+3,X-2,y+3,z+10),'minecraft:bookshelf',b['id'],'Actual book/record storage wall')
                elif b['kind']=='clinic' and level>0:bed(X-4,y+1,Z-5,b['id'])
            b['architecture']='Separate front public room / rear work room / explicit inner doors, with original thin frontage'
        else:
            for level in range(1,b['storeys']):
                y=f+level*5
                unitX=max(x+11,cx)
                fill((unitX,y+1,z+5,unitX,y+4,Z-3),material,b['id'],'Two actual upper residential/work units outside the complete common stair core')
                door(unitX,y,min(z+9,Z-3),b['id'],'east');bed(X-4,y+1,Z-5,b['id'])
            b['architecture']='Thin ground shopfront / two real upper units / common full stair core'
        entry_and_approach()
        if b['kind'] not in ['terraced_home','small_inn']:
            for xx in [x,X]:fill((xx,roof+1,z,xx,roof+1,Z),material,b['id'],'Whole usable roof parapet')
            for zz in [z,Z]:fill((x,roof+1,zz,X,roof+1,zz),material,b['id'],'Whole roof perimeter')
            # The actual stair reaches a sheltered roof landing. Its hole
            # does not leave a raw exposed rectangle in an occupied roof.
            headX=min(X-1,x+10);headZ=min(Z-1,z+13)
            for xx in [x+1,headX]:fill((xx,roof+1,z+1,xx,roof+3,headZ),material,b['id'],'Complete roof stair-head side enclosure')
            for zz in [z+1,headZ]:fill((x+1,roof+1,zz,headX,roof+3,zz),material,b['id'],'Complete roof stair-head end enclosure')
            fill((x+1,roof+4,z+1,headX,roof+4,headZ),'minecraft:smooth_stone',b['id'],'Supported stair-head weather roof')
            if b['kind']=='clinic' and a.district in ['tokyo_north','hakone_west']:
                for yy in [roof+1,roof+2]:put((x+9,yy,headZ),'minecraft:air',b['id'],'Roof exit leads south onto the retained actual L-body, never the cut-out forecourt void')
                door(x+9,roof,headZ,b['id'],'south')
            else:
                exitZ=z+3
                for yy in [roof+1,roof+2]:put((headX,yy,exitZ),'minecraft:air',b['id'],'Real roof landing-to-terrace opening')
                door(headX,roof,exitZ,b['id'],'east')
            b['roof_role']='Accessible flat roof with retained public stair, full perimeter guard and flight transition'
        else:b['roof_role']='Low pitched roof over rooms; stair top lands within attic rather than public roof'
        if b['kind']=='gallery_danchi':
            ex=x+6
            entryPath=[[ex+.5,f+1,z-.5],[ex+.5,f+1,z+3.5],[x+9.5,f+1,z+3.5],[x+12.5,f+1,z+2.5]]
            for suffix,pth in [('',entryPath),('/return',entryPath[::-1])]:cases.append(dict(id=b['id']+'/public_stair_entry'+suffix,path=pth,door=[ex,f+1,z],native_passed=False))
        floors.extend(dict(id=b['id']+f'/floor{n+1}',feet_y=y) for n,y in enumerate(b['floor_feet']))
    landmark_components=[]
    for b in d['buildings']:
        if b['kind'] not in ['tv_school','tv_gym','tv_misato_home']:continue
        def landmark_state(q):return proposed[q][0] if q in proposed else w.block(q)
        component=tv_school(b,landmark_state,put,door) if b['kind']=='tv_school' else tv_gym(b,landmark_state,put) if b['kind']=='tv_gym' else tv_misato_home(b,landmark_state,put,door,bed)
        if b['kind']=='tv_misato_home':
            def shoe_storage(q,owner):
                put(q,'minecraft:chest[facing=east,type=single,waterlogged=false]',owner,'Actual manually usable genkan shoe/umbrella cabinet with full source inventory NBT')
                newtags[q]=nbtlib.Compound({'id':nbtlib.String('minecraft:chest'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Items':nbtlib.List[nbtlib.Compound]([])}).snbt()
            refined=compact_tv_household(b,landmark_state,put,bed,shoe_storage)
            component['rooms']=[r for r in component['rooms'] if '/floor3/' not in r['id']]+refined['rooms'];component['cases']=[c for c in component['cases'] if '/floor3/' not in c['id']]+refined['cases'];component['compact_household']=refined
        rooms=[r for r in rooms if not r['id'].startswith(b['id']+'/')]+component['rooms'];cases.extend(component['cases']);landmark_components.append(dict(building=b['id'],**component))
    # The primary producer always authors the oriented period entry/facade
    # design. Calling this script alone must not reproduce the old generic
    # blank east walls, in-wall signs or a3-high hole over a2-high door.
    protected=set()
    for case in cases:
        for first,last in zip(case['path'],case['path'][1:]):
            steps=max(1,math.ceil(math.dist(first,last)*4))
            for i in range(steps+1):
                point=[first[k]+(last[k]-first[k])*i/steps for k in range(3)]
                for xx in range(math.floor(point[0]-.31),math.floor(point[0]+.31)+1):
                    for zz in range(math.floor(point[2]-.31),math.floor(point[2]+.31)+1):
                        for yy in range(math.floor(point[1]),math.ceil(point[1]+1.8)):protected.add((xx,yy,zz))
    def target_state(q):return proposed[q][0] if q in proposed else w.block(q)
    def period_put(q,s,owner,reason,nbt=None):
        put(q,s,owner,reason)
        if nbt is not None:newtags[tuple(q)]=nbt
    for q,nbt in list(newtags.items()):
        if '_wall_sign[' not in target_state(q):continue
        building=next((b for b in d['buildings'] if proposed.get(q,(None,None))[1]==b['id']),None)
        if building is None or (building['kind']=='gallery_danchi' and building['bounds'][1]<q[2]<building['bounds'][3]):continue
        put(q,'minecraft:air',building['id'],'Retire obsolete generic engineering/public facade plaque in the primary producer')
        if building.get('facing')=='east' and q[0]==building['bounds'][2]:put(q,'minecraft:smooth_sandstone',building['id'],'Close the original in-wall sign opening before the actual exterior entrance-side plaque')
    period_components=[];street={'hakone_west':'西町','tokyo_north':'北町','kirisato_north':'霧里北'}.get(a.district,'南町')
    for n,b in enumerate(d['buildings'],1):
        component=period_author(b,n,street,target_state,period_put,protected);period_components.append(component);service=component.get('shopfront')
        if service and not service['service_founded']:held.append(dict(owner=b['id'],reason='Real measured side service footing is not bounded/founded',profiles=service['service_bearing']))
        if service and service['service_door']:
            for c in cases:
                if c['id'] in [b['id']+'/stairs1',b['id']+'/stairs1/return']:
                    forward=c['path'][::-1] if c['id'].endswith('/return') else c['path'];revised=service['service_street_route']+forward[1:];c['retired_before_path']=c['path'];c['path']=revised[::-1] if c['id'].endswith('/return') else revised;c['door']=service['service_door'];c['revision_reason']='Retire old stair start on the glazed facade; preserve the real roof goal through the purposeful west service door'
    for b in d['buildings']:
        if b['kind']=='tv_school':
            component=school_entrance(b,target_state,put);rooms.extend(component['rooms']);cases.extend(component['cases']);landmark_components.append(dict(building=b['id'],**component))
        elif b['kind']=='tv_misato_home':landmark_components.append(dict(building=b['id'],**finish_tv_apartment(b,target_state,put,protected)))
    # Exact installed railway envelopes remain a veto, not a visual guess.
    native=json.loads((ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json').read_text('utf8'));rail_conflicts=[]
    candidates=np.array([q for q,(s,o,r) in proposed.items() if s not in AIR],int)
    if len(candidates):
        from scipy.spatial import cKDTree
        tree=cKDTree(candidates[:,[0,2]])
        for curve in native['curves']:
            if curve['mode']!='TRAIN':continue
            for xx,yy,zz in curve['points']:
                for i in tree.query_ball_point([xx,zz],4.3):
                    q=candidates[i]
                    if abs(q[0]-math.floor(xx))<=3 and abs(q[2]-math.floor(zz))<=3 and yy-3<q[1]+1 and yy+8>q[1]:rail_conflicts.append(dict(pos=q.tolist(),curve=curve['id']))
    a.output.mkdir(parents=True)
    rows=[dict(pos=q,before=w.block(q),after=s,before_nbt=None,after_nbt=newtags.get(q),owner=o,reason=r) for q,(s,o,r) in sorted(proposed.items())]
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as stream:
            for row in rows:
                v=dict(row)
                if inverse:v['before'],v['after']=row['after'],row['before'];v['before_nbt'],v['after_nbt']=row['after_nbt'],row['before_nbt']
                stream.write(json.dumps(v,ensure_ascii=False)+'\n')
    (a.output/'native_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),'utf8')
    (a.output/'architecture_components.json').write_text(json.dumps(dict(components=period_components,primary_producer_integrated=True,source_helper='city_period_architecture_r44.py',world_written=False),ensure_ascii=False,indent=2),'utf8')
    if landmark_components:(a.output/'tv_landmark_components.json').write_text(json.dumps(dict(components=landmark_components,world_written=False),ensure_ascii=False,indent=2),'utf8')
    if a.design_file:d['producer_design_file']=str(a.design_file.resolve())
    (a.output/'new_district.json').write_text(json.dumps(dict(d,rooms=rooms,floors=floors,stair_flights=flights,whole_culvert_deck_columns=culverts),ensure_ascii=False,indent=2),'utf8')
    (a.output/'road_authority.json').write_text(json.dumps(dict(columns=[dict(pos=q,height2=v[0],native_feet=v[0]/2,carriage=v[1],source_id='r44/'+a.district+'/new_streets') for q,v in columns.items()],world_written=False),indent=2),'utf8')
    protections=[dict(bounds=[b['bounds'][0]-3,b['floor']-4,b['bounds'][1]-4,b['bounds'][2]+3,b['roof']+(max(5,(b['bounds'][2]-b['bounds'][0])//4+3) if b['kind'] in ['terraced_home','small_inn'] else 5),b['bounds'][3]+8],owner=b['id'],role='new building/floors/real full roof/door approach') for b in d['buildings'] if 'floor' in b]
    protections.extend(dict(bounds=[x,math.floor(h/2)-3,z,x,math.ceil(h/2)+6,z],owner=owner,role='new full-width street') for (x,z),(h,carriage,distance) in columns.items())
    protections.extend(dict(bounds=[x,math.floor(h/2)-3,z,x,math.ceil(h/2)+3,z],owner=o,role='complete new public building approach') for (x,z),(h,o) in approaches.items())
    if d.get('sports_field'):
        protections.extend(dict(bounds=[p['pos'][0],min(p['ground'],p['after_ground'])-3,p['pos'][1],p['pos'][0],p['after_ground']+6,p['pos'][1]],owner='r44/tv_school/sports_field',role='actual bare exercise field and full measured eighteen-metre graded margin') for p in d['sports_field']['actual_profiles'])
    # Side veranda on the named household layer extends outside the generic
    # south balcony reservation; its real clearance belongs to the city.
    protections.extend(dict(bounds=[b['bounds'][2],b['floor']+7,b['bounds'][1],b['bounds'][2]+3,b['floor']+15,b['bounds'][3]+1],owner=b['id'],role='TV household floor3 whole eastern veranda') for b in d['buildings'] if b['kind']=='tv_misato_home')
    protections.extend(component['protection'] for component in landmark_components if 'protection' in component)
    (a.output/'ecology_reservations.json').write_text(json.dumps(dict(reservations=protections,required_before_native_reseed=True),indent=2),'utf8')
    audit=dict(new_buildings=len(d['buildings']),new_floor_planes=len(floors),old_buildings_rebuilt=0,changed_cells=len(rows),new_street_columns=len(columns),full_nbt_generated=len(newtags),held=held,rail_conflicts=rail_conflicts,
        exact_state_nbt_inverse=True,world_written=False,ready=False,ready_reason='Whole all-direction street/door/floor/roof and actual station successor cases, collision graph, slope/foundation/successor checks and native/visual review required; this is first actual geometry, not a ready release',native_passed=False,visual_passed=False,
        entire_district=d,original_193_buildings_untouched=True,existing_rei402_and_all_uuid_preserved=True,battle_clear_radius250=True)
    (a.output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),'utf8');print('New actual district geometry',a.district,'buildings',len(d['buildings']),'floors',len(floors),'cells',len(rows),'held',len(held),'rail',len(rail_conflicts),'world unchanged',flush=True)


if __name__=='__main__':main()
