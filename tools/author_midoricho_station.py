"""Offline relocated Midoricho platform with retained drains and street access.

The original site cannot fit a usable platform between the old street and JR.
This explicitly documented 69 m shift stays on the same cached non-JR line.
"""
import argparse, copy, json, math, shutil
from pathlib import Path
import numpy as np
import nbtlib
from shapely.geometry import shape, box, LineString, Point, mapping
from shapely.ops import unary_union
from author_hakone_lakefront import Editor
from author_hakone_togendai import Station
from author_kamonomiya_station import ALLOWED, OPEN
from author_itabashi_station import dump
from prepare_hakone_city_cross import packed

BASE=-75


def author(a):
    a.out.mkdir(exist_ok=False);shutil.copytree(a.source/'source',a.out/'source');(a.out/'delta').mkdir()
    for f in('capture.json','measured.npz','captured-devices.dat'):shutil.copy2(a.source/f,a.out/f)
    shutil.copytree(a.native,a.out/'preserved-native');shutil.copytree(a.model,a.out/'vehicle-model')
    cap=json.loads((a.source/'capture.json').read_text('utf8'));l,t,r,b=cap['bounds_xz']
    with np.load(a.source/'measured.npz')as f:ground=f['top'].copy()
    with np.load(a.authority/'network.npz')as f:ax,az,_,_=map(int,f['bounds']);oldwalk=f['walk'];oldgrade=f['grade2']
    devices={tuple(int(q[k])for k in('x','y','z'))for q in nbtlib.load(a.source/'captured-devices.dat')['Devices']}
    references=json.loads(a.reference.read_text('utf8'))
    water=unary_union([shape(q['geometry'])for q in references if q['properties'].get('source_layer')in('WA','RvrCL','WStrL')]);banks=water.buffer(3)
    jr=unary_union([shape(q['geometry'])for q in references if q['properties'].get('source_layer')=='RailCL'and q['properties'].get('vt_rtcode')=='JR'])
    e=Editor(a.out);signs=Station(e);owned=set();public={};underpasses=[];channel_columns=[]
    def put(x,y,z,state):
        if not(l<=x<=r and t<=z<=b and -128<=y<320):raise ValueError(('Unknown source',x,y,z))
        if e.state(x,y,z)==state:return
        before=e.state(x,y,z,True)
        if before.split('[')[0]not in ALLOWED or(x,y,z)in devices:raise ValueError(('Protected original',x,y,z,before))
        if oldwalk[z-az,x-ax]:raise ValueError(('Retained public column',x,y,z))
        if banks.intersects(box(x,z,x+1,z+1)):
            if not(3444<=x<=3453 and 317<=z<=366 and y>=-76):raise ValueError(('Protected water bank',x,y,z))
        e.put(x,y,z,state);owned.add((x,y,z))
    def fill(x,y,z,X,Y,Z,state):
        for xx in range(x,X+1):
            for zz in range(z,Z+1):
                for yy in range(y,Y+1):put(xx,yy,zz,state)
    def floor(x,z,g,declare=True):
        if oldwalk[z-az,x-ax]:
            if declare:public[x,z]=int(oldgrade[z-az,x-ax])
            return
        y=(g+1)//2;bottom=min(y-1,int(ground[z-t,x-l])-1)
        if banks.intersects(box(x,z,x+1,z+1)):
            # Above the retained channel/banks: a bearing deck only, never fill.
            if y<BASE:raise ValueError(('Low floor across water buffer',x,y,z))
            bottom=-76;channel_columns.append([x,z])
        for yy in range(bottom,y):put(x,yy,z,'minecraft:stone_bricks')
        put(x,y,z,'minecraft:smooth_stone'if g%2==0 else'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
        for yy in range(y+1,max(y+4,int(ground[z-t,x-l])+3)):put(x,yy,z,'minecraft:air')
        if declare:public[x,z]=g
    def rect(x,z,X,Z,g):
        for xx in range(x,X+1):
            for zz in range(z,Z+1):floor(xx,zz,g)
    # A 48 m flat north-south boarding track stays on the same cached approach.
    # Railway deck bridges the two small cached drains; all support outside banks.
    for x in range(3444,3448):
        for z in range(316,367):
            if banks.intersects(box(x,z,x+1,z+1)):
                bottom=-76;channel_columns.append([x,z])
            else:bottom=int(ground[z-t,x-l])-1
            for y in range(bottom,-75):put(x,y,z,'minecraft:stone_bricks')
            for y in range(-75,-69):put(x,y,z,'minecraft:air')
    # Extend only the free vehicle envelope; not the physical bed into transitions.
    fill(3444,-75,313,3447,-70,371,'minecraft:air')
    rect(3448,317,3453,366,BASE*2)
    # North end must bear on the measured bank, not cantilever nine metres
    # across the first drain while waiting for the future approach railway.
    for x in range(3448,3454):
        floor(x,316,BASE*2,False);put(x,BASE+1,316,'minecraft:light_gray_stained_glass')
    fill(3448,BASE,317,3448,BASE,366,'projectseele:station_tactile_warning')
    # The whole platform keeps two clear boarding-side columns, including below
    # the short rear stair/service frontage; no crossing of the running track.
    for z in range(317,367):put(3453,BASE+1,z,'minecraft:light_gray_stained_glass')
    # A compact partial canopy avoids an oversized elevated concourse.
    fill(3448,BASE+6,317,3453,BASE+6,338,'minecraft:light_gray_concrete')
    fill(3449,BASE+7,318,3452,BASE+7,337,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    for z in(319,328,337):
        fill(3453,BASE+1,z,3453,BASE+5,z,'minecraft:dark_oak_log[axis=y]')
        fill(3449,BASE+5,z,3453,BASE+5,z,'minecraft:dark_oak_log[axis=x]')
        put(3451,BASE+5,z+1,'minecraft:sea_lantern')
    for z in(324,334,354):
        for zz in range(z,z+3):put(3452,BASE+1,zz,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    # This pedestrian route follows the east side of Daiyuzan and passes below
    # reference JR viaducts (level-order 1). Future JR deck minima are explicit.
    waypoints=[(3451,365),(3462,374),(3462,402),(3472,402),(3472,405)]
    route=[]
    for p,q in zip(waypoints,waypoints[1:]):
        n=max(abs(q[0]-p[0]),abs(q[1]-p[1]))
        for i in range(n+1):
            k=(round(p[0]+(q[0]-p[0])*i/n),round(p[1]+(q[1]-p[1])*i/n))
            if not route or route[-1]!=k:route.append(k)
    columns={}
    for i,(x,z)in enumerate(route):
        g=BASE*2-min(6,max(0,(i-4)//7))
        for dx in(-1,0,1):
            for dz in(-1,0,1):columns[x+dx,z+dz]=g
    for(x,z),g in columns.items():
        if(x,z)in public:g=public[x,z]
        floor(x,z,g)
        if box(x,z,x+1,z+1).distance(jr)<4.5:
            underpasses.append(dict(x=x,z=z,floor_grade2=g,feet_y=g/2+1,minimum_JR_bridge_underside_y=g/2+3,
                                   minimum_future_JR_rail_y=g/2+5,clear_width_metres=3,JR_built=False))
    # Hall remains next to the original street rather than following the shifted
    # platform north. The former public street is not cut, moved or overwritten.
    rect(3464,405,3480,423,-156)
    for z in(405,423):fill(3464,-77,z,3480,-74,z,'minecraft:light_gray_concrete')
    for x in(3464,3480):fill(x,-77,405,x,-74,423,'minecraft:light_gray_concrete')
    for x in(3465,3476):
        for z in(405,423):fill(x,-76,z,x+3,-75,z,'minecraft:light_gray_stained_glass')
    for z in(408,418):
        for x in(3464,3480):fill(x,-76,z,x,-75,z+2,'minecraft:light_gray_stained_glass')
    fill(3470,-77,405,3474,-75,405,'minecraft:air')
    fill(3464,-77,412,3464,-75,416,'minecraft:air')
    fill(3463,-73,404,3481,-73,424,'minecraft:gray_concrete')
    fill(3464,-72,405,3480,-72,423,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    for x in(3468,3476):
        for z in(409,419):put(x,-74,z,'minecraft:sea_lantern')
    fill(3476,-77,412,3478,-77,414,'minecraft:smooth_quartz')
    # Retain the exact slab sidewalk; three half-steps join the hall landing.
    for x in range(3458,3465):
        g=-159+min(3,max(0,x-3460))
        for z in range(413,416):floor(x,z,g)
    expected=[(3463,-75,414,'west',['緑町駅','MIDORICHO','大雄山線 / Daiyuzan','改札 / 入口']),
              (3475,-75,413,'west',['緑町駅','きっぷ / Tickets','小田原・大雄山','1 番線']),
              (3450,-71,329,'west',['緑町駅','MIDORICHO','1 番線','小田原 ← → 大雄山'])]
    for index,(x,y,z,facing,words)in enumerate(expected):
        put(x+1,y,z,'minecraft:gray_concrete')
        if index==1:put(x+1,y-1,z,'minecraft:gray_concrete')
        else:
            top=-73 if index==0 else BASE+6
            for yy in range(y+1,top):put(x+1,yy,z,'minecraft:chain[axis=y,waterlogged=false]')
        put(x,y,z,'minecraft:oak_wall_sign[facing=west,waterlogged=false]');signs.sign(x,y,z,words,facing)
    rows=[]
    for(x,z),g in sorted(public.items()):
        y=(g+1)//2
        if all(e.state(x,yy,z).split('[')[0]in OPEN for yy in(y+1,y+2)):rows.append([x,z,g])
    goals=dict(street=[3459,-78.5,414],entrance=[3465,-77,414],forecourt=[3462,-77.5,414],
               hall=[3472,-77,414],ticket=[3474,-77,413],north_hall=[3472,-77,406],
               platform_south=[3449,-74,364],platform_centre=[3449,-74,342],platform_north=[3449,-74,319])
    regions=e.save();e.regions.clear()
    tags=[]
    for q in signs.devices:
        tag=q['After'];pos=tuple(int(tag[k])for k in('x','y','z'))
        tags.append(nbtlib.Compound({'Pos':nbtlib.Long(packed(pos)),'After':copy.deepcopy(tag)}))
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](tags)}).save(a.out/'block-entities.dat',gzipped=True)
    bounds=[min(q[i]for q in owned)for i in range(3)]+[max(q[i]for q in owned)for i in range(3)]
    native=dict(rails=[dict(id='midoricho-platform-1',**{'from':[3446,BASE,318],'to':[3446,BASE,366]},
                           from_angle='S',to_angle='N',shape='QUADRATIC',vertical_radius=40,mode='TRAIN',kind='platform',platform_name='1')],
                stations=[dict(id='midoricho',name='緑町駅',min=[3443,-82,316],max=[3482,-66,425],color=0x35875C)],lines=[])
    for f in('native-input.json','native-samples.json'):shutil.copy2(a.math/f,a.out/f)
    dump(a.out/'native-station-plan.json',native)
    ground_access=[q for q in rows if q[1]>366 and q[2]/2<=int(ground[q[1]-t,q[0]-l])+1]
    design=dict(station='緑町駅',station_id='midoricho',parts=[dict(kind='relocated side platform, drain spans and original-street hall',bounds=bounds)],
        public_columns=rows,ground_access_columns=ground_access,ground_access_format=['x','z','grade2'],
        station_multi_level_nodes=[[x,g,z]for x,z,g in rows],station_multi_level_node_format=['x','grade2','z'],
        network_single_grade2_update_scope='ground_access_columns only',goals=goals,retained_street_anchor=goals['street'],
        expected_signs=[dict(pos=[x,y,z],facing=f,title=words[0])for x,y,z,f,words in expected],
        source_authority=str(a.authority),source_native=str(a.native),native_math_samples='native-samples.json',
        original_reference_centre=[3446.443,411.8685],actual_station_centre=[3446.5,342.5],
        north_shift_metres=69.36852341821983,geographic_adaptation=True,one_to_one_restoration_claimed=False,
        adaptation_reason='Same-line north shift from a 0.04m pinch point between retained street and JR; entrance stays at original street',
        local_cached_axis_degrees=76.8,native_axis_degrees=90,platform_length=48,planned_maximum_consist_length=18,
        vehicle='e44_mini_cab_3',consist=dict(cars=2,native_car_length=9,native_total_length=18,prototype_real_world_consist_claimed=False),
        full_boarding_edge=dict(axis='z',samples=list(range(318,367)),edge_x=3448,minimum_required_width=2,columns_perpendicular=[3448,3449,3450,3451,3452,3453],floor_y=BASE),
        rail_level=BASE,continuous_boarding_interval=[318.5,366.5],visible_platform_gap=.1875,native_floor_support_gap=.25,
        channel_bridge_columns=sorted(set(map(tuple,channel_columns))),reserved_future_water_surface=-78,
        channel_abutment_rows=[316,326,332,340],channel_abutment_x_range=[3444,3453],
        rail_deck_underside=-76,minimum_water_headroom_under_rail=2,platform_deck_underside=-76,
        water_already_built=False,JR_underpass_interfaces=underpasses,JR_crossing_service_verified=False,
        no_at_grade_passenger_rail_crossing=True,pedestrian_route=route,
        native_registry_pending=True,production_replay_pending=True,physical_scope_complete=False,world_written=False,through_service_complete=False)
    dump(a.out/'station-design.json',design);dump(a.out/'reference-geography.json',references)
    dump(a.out/'manifest.json',dict(world=cap['world'],kind='measured-regional-station',bounds_xz=cap['bounds_xz'],regions=regions,
        cells=sum(q['cells']for q in regions),station_design='station-design.json',native_station_pending=True,world_written=False))
    print('Prepared Midoricho:',sum(q['cells']for q in regions),'cells;',len(rows),'public nodes;',len(underpasses),'JR-underpass interface columns',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('source','authority','native','model','reference','math','out'):p.add_argument('--'+k,type=Path,required=True)
    author(p.parse_args())
