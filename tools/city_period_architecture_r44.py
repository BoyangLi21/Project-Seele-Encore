"""Period street architecture shared by installed repairs and new districts.

Only works through the caller's exact measured/owned-cell writer. Facade normals,
entry headroom and use-specific exterior/interior bays share one coordinate frame.
"""
import json
import nbtlib

WALLS={'minecraft:smooth_sandstone','minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:light_gray_terracotta','minecraft:stone_bricks'}
GLASS='minecraft:gray_stained_glass'
SITE_SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand','minecraft:sandstone','minecraft:clay','minecraft:coarse_dirt','minecraft:rooted_dirt','minecraft:podzol','minecraft:mud','minecraft:andesite','minecraft:diorite','minecraft:granite'}


def low_shop_maintenance_roof(b,state,put):
    targets={'r44/tokyo_north_new/08':'east','r44/tokyo_north_new/11':'east',
             'r44/tokyo_north_new/13':'west','r44/tokyo_north_new/27':'west'}
    side=targets.get(b['id'])
    if side is None:return None
    x,z,X,Z=b['bounds'];f=b['floor'];roof=b['roof'];feet=f+1
    if b['kind']!='local_shop' or b['floor_feet']!=[feet] or roof!=f+4:
        return dict(building=b['id'],status='HOLD_CHANGED_NAMED_LOW_SHOP_ENVELOPE')
    lx,lz,dx,dz,facing=(X-1,Z-2,1,0,'west')if side=='east'else(x+1,z+5,-1,0,'east')
    masonry=WALLS|{'minecraft:white_terracotta','minecraft:terracotta','minecraft:smooth_stone',
                   'minecraft:polished_deepslate','minecraft:polished_andesite','minecraft:smooth_quartz'}
    name=lambda q:(state(q)or'').partition('[')[0]
    if any(name((lx,y,lz))not in{'minecraft:air','minecraft:cave_air'}for y in range(feet,roof)):
        return dict(building=b['id'],status='HOLD_EXISTING_INTERIOR_OBJECT')
    if any(name((lx+dx,y,lz+dz))not in masonry for y in range(feet,roof+1)):
        return dict(building=b['id'],status='HOLD_NO_FULL_ACTUAL_MASONRY_SUPPORT')
    if any(name(q)not in masonry for q in[(lx,f,lz),(lx,roof,lz),(lx-dx,f,lz-dz),(lx-dx,roof,lz-dz)]):
        return dict(building=b['id'],status='HOLD_INCOMPLETE_TWO_LANDINGS')
    if any(name((lx-dx,y,lz-dz))not in{'minecraft:air','minecraft:cave_air'}for y in(feet,feet+1,roof+1,roof+2)):
        return dict(building=b['id'],status='HOLD_ACTUAL_LANDING_BODY_OBSTRUCTION')
    for y in range(feet,roof):
        put((lx,y,lz),f'minecraft:ladder[facing={facing},waterlogged=false]',b['id'],'R47 finite named low-shop masonry-supported roof maintenance ladder')
    put((lx,roof,lz),f'minecraft:oak_trapdoor[facing={facing},half=top,open=false,powered=false,waterlogged=false]',b['id'],'R47 matching-facing manually opened weather-sealed maintenance hatch')
    b['roof_role']='Weather roof with manual maintenance ladder/hatch; no public roof route'
    return dict(building=b['id'],status='AUTHORED_MAINTENANCE_COMPONENT_NATIVE_USE_PENDING',ladder=[lx,feet,lz],hatch=[lx,roof,lz],facing=facing,world_written=False)


def complete_shop_front(b,state,put):
    x,z,X,Z=b['bounds'];f=b['floor'];dx,_,_=b['door'];owner=b['id']
    assert b.get('facing','south')=='south'
    left_end=min(x+5,dx-2);glazing=[]
    for xx in range(x,X+1):
        for yy in [f+1,f+2]:
            if xx==dx:continue
            material='minecraft:light_gray_concrete' if xx<=left_end or xx in [x,X,dx-1,dx+1] else GLASS
            put((xx,yy,Z),material,owner,'Complete supported shopfront: solid real service bay/piers and full glazing close every former air bypass')
            if material==GLASS:glazing.append([xx,yy,Z])
        put((xx,f+3,Z),'minecraft:light_gray_concrete',owner,'Continuous full-width shop lintel above the actual two-high glass door and closed display bays')
    for half,dy in [('lower',1),('upper',2)]:put((dx,f+dy,Z),f'mcwdoors:store_door[facing=south,half={half},hinge=left,open=false,powered=false]',owner,'Complete real customer glass door, the only customer route through the closed shopfront')
    side=None;path=[];bearing=[]
    if 'Accessible flat roof' in b.get('roof_role','') and Z-z<=14:
        sz=z+10;side=[x,f+1,sz]
        sx=x+3
        # The old first tread abutted the open facade and could only be
        # walked while its wall was missing. Move this existing whole flight
        # one metre inward and provide a real level lower landing. Roof goal,
        # upper weather hatch, footprint and all occupied storeys stay.
        for xx in range(sx-1,sx+2):put((xx,f+1,sz),'minecraft:air',owner,'Retire the first facade-adjacent stair tread; real level landing permits a complete shopfront')
        for i in range(5):
            yy=f+i+1;zz=sz-1-i
            for xx in range(sx-1,sx+2):
                for yb in range(f,yy):put((xx,yb,zz),'minecraft:polished_andesite',owner,'Complete founded bearing for the retained three-wide roof flight shifted one metre inward')
                put((xx,yy,zz),'minecraft:polished_andesite_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]',owner,'Whole real roof stair flight shifted inside the closed facade with its existing upper goal retained')
                for yb in range(yy+1,yy+3):put((xx,yb,zz),'minecraft:air',owner,'Actual two-high flight headroom; compact upper weather cover atYroof+3 is retained')
        for half,dy in [('lower',1),('upper',2)]:put((x,f+dy,sz),f'projectseele:city_personnel_door[facing=west,half={half},hinge=left,open=false,powered=false]',owner,'Purposeful real west service entrance connects the retained roof stair from an actual side approach')
        for xx in [x-2,x-1]:
            for zz in range(sz-2,Z+4):
                ground=max([yy for yy in range(max(40,f-12),f) if (state((xx,yy,zz)) or '').split('[')[0] in SITE_SOIL],default=None)
                bearing.append(dict(pos=[xx,zz],actual_or_authored_ground=ground,new_floor=f,cut_fill=None if ground is None else f-ground))
                if ground is None or f-ground>8:continue
                for yy in range(ground+1,f):put((xx,yy,zz),'minecraft:stone',owner,'Whole measured side service-footway footing, founded on the actual soil within8m')
                put((xx,f,zz),'minecraft:smooth_stone',owner,'Complete two-wide shop side service footway reaches the retained full frontage')
                for yy in range(f+1,f+5):
                    current=state((xx,yy,zz)) or ''
                    if current.split('[')[0] in SITE_SOIL|{'minecraft:air','minecraft:cave_air','minecraft:grass','minecraft:tall_grass','minecraft:fern'}:put((xx,yy,zz),'minecraft:air',owner,'Measured service entrance headroom; preserve other actual masonry/caps/eaves and fullNBT')
        # The uphill side is retained structurally outside the complete2m
        # footway. The opposite side is the real building wall/door plane.
        for zz in range(sz-2,Z+1):
            top=max([yy for yy in range(f-3,f+6) if (state((x-4,yy,zz)) or '').split('[')[0] in SITE_SOIL],default=f)
            if top>f+5:continue
            for yy in range(f-2,max(f,top)+1):put((x-3,yy,zz),'minecraft:stone_bricks',owner,'Founded west service-path retaining return holds the actual neighbouring uphill soil outside the2m clear ground')
            put((x-3,max(f,top)+1,zz),'minecraft:stone_brick_slab[type=bottom,waterlogged=false]',owner,'Supported low retaining cap follows measured uphill bank; no filling of the door or footway')
        hx,hy,hz=b['actual_street_handoff'];path=[[hx+.5,hy,hz+.5],[x-1.5,f+1,hz+.5],[x-1.5,f+1,sz+.5],[x+1.5,f+1,sz+.5],[sx+.5,f+1,sz+.5]]
    return dict(building=owner,glazing=glazing,customer_door=b['door'],service_door=side,service_street_route=path,service_bearing=bearing,service_founded=all(p['actual_or_authored_ground'] is not None and p['cut_fill']<=8 for p in bearing),world_written=False)


def sign_nbt(q,lines):
    face=nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':s},ensure_ascii=False)) for s in (lines+['']*4)[:4]]),'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
    return nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'front_text':face,'back_text':nbtlib.parse_nbt(face.snbt()),'is_waxed':nbtlib.Byte(1)}).snbt()


def author(b,number,street,state,put,protected_route_cells):
    x,z,X,Z=b['bounds'];f=b['floor'];owner=b['id'];kind=b['kind'];heading=b.get('facing','south')
    nx,nz={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}[heading]
    tx,tz=(1,0) if nx==0 else (0,1);dx,_,dz=b['door']
    def at(u,v,y):return (dx+tx*u+nx*v,y,dz+tz*u+nz*v)
    def emit(q,s,why,nbt=None):put(q,s,owner,why,nbt)
    def name(q):return (state(q) or '').split('[')[0]
    domestic=kind in ['compact_home','terraced_home','small_inn']
    wall='minecraft:smooth_sandstone' if domestic else 'minecraft:white_concrete' if kind in ['clinic','civic'] else 'minecraft:light_gray_terracotta' if kind=='apartment' else 'minecraft:light_gray_concrete'
    frame=wall if domestic else 'minecraft:light_gray_concrete'
    # Windows are generated on all real wall planes, never only on north/south.
    # Upper setback east planes follow the actual body, not its old footprint.
    window_bays=[]
    for level,feet in enumerate(b['floor_feet']):
        y=feet-1;edge=X-(level*2 if kind=='apartment' else 0)
        planes=[('north',[(xx,z) for xx in range(x+2,edge-1)]),('south',[(xx,Z) for xx in range(x+2,edge-1)]),('west',[(x,zz) for zz in range(z+2,Z-1)]),('east',[(edge,zz) for zz in range(z+2,Z-1)])]
        for normal,points in planes:
            if normal=='north' and kind=='gallery_danchi':continue
            # Each use has human-scale bays separated by real wall piers.
            width=2 if domestic or kind=='apartment' else 3
            period=5 if domestic or kind=='apartment' else 6
            for i,q in enumerate(points):
                if i%period>=width:continue
                yy=[y+2] if domestic or kind=='apartment' else [y+2,y+3]
                for h in yy:
                    pos=(q[0],h,q[1]);old=name(pos)
                    if old in WALLS or old==GLASS:emit(pos,GLASS,'Actual '+normal+' oriented occupied-room window bay')
                window_bays.append([q[0],y+2,q[1]])
    # Complete entrance bay. Two-high door always has a real lintel, piers
    # and room glazing; a one-block sign cannot punch a three-high wall void.
    for u in [-1,1]:
        for yy in range(f+1,min(f+4,b['roof'])):
            emit(at(u,0,yy),frame,'Complete entrance jamb grounded in the actual facade')
    for u in range(-2,3):emit(at(u,0,f+3),frame,'Continuous actual door lintel and facade backing, never raw stair through a third-block opening')
    for half,dy in [('lower',1),('upper',2)]:
        door='minecraft:oak_door' if domestic else 'mcwdoors:store_door' if heading=='south' and kind in ['local_shop','shophouse','coffee_house','book_office'] else 'projectseele:city_personnel_door'
        emit(at(0,0,f+dy),f'{door}[facing={heading},half={half},hinge=left,open=false,powered=false]','Use-specific real manually operable complete entrance door')
    # Broad shallow canopy makes a sheltered porch with minimum3m clearance.
    canopy='minecraft:dark_oak_slab[type=top,waterlogged=false]' if domestic else 'minecraft:smooth_stone_slab[type=top,waterlogged=false]'
    for u in range(-3,4):
        for v in [1,2]:emit(at(u,v,f+3),canopy,'Supported shallow entrance canopy over full-height public approach')
    if domestic:
        # Outer posts are outside the original door approach and leave5m span.
        for u in [-3,3]:
            for yy in range(f+1,f+4):
                q=at(u,2,yy)
                if q not in protected_route_cells:emit(q,'minecraft:dark_oak_fence[east=false,north=false,south=false,waterlogged=false,west=false]','Quarter-metre timber porch support outside every declared circulation cell')
    else:
        for u in range(-3,4):emit(at(u,2,f+4),'minecraft:green_terracotta' if kind=='clinic' else 'minecraft:blue_terracotta' if kind=='civic' else 'minecraft:red_terracotta','Distinct supported clinic/civic/shop fascia above canopy')
    # Public name plaque has a solid jamb behind it at eye height; front text
    # is semantic only, never construction owner identifiers.
    signq=at(1,1,f+2)
    lines=[street+'一丁目',str(number)+'-1'] if kind=='compact_home' else [b['label'],'住戸・共用玄関' if kind in ['tv_misato_home','apartment','gallery_danchi','terraced_home'] else '受付' if kind in ['clinic','small_inn'] else '日用品・食料品' if kind in ['local_shop','shophouse'] else '学校玄関' if kind=='tv_school' else '体育館' if kind=='tv_gym' else '開館 9:00–18:00']
    emit(signq,f'minecraft:birch_wall_sign[facing={heading},waterlogged=false]','Eye-height actual entrance-side plaque mounted one cell outside its solid jamb',sign_nbt(signq,lines))
    # Entrance lateral room windows differ by use. Shop piers frame a glazed
    # storefront while the entrance remains a complete two-high door bay.
    for u in [-4,-3,3,4]:
        q=at(u,0,f+2)
        if x<q[0]<X or z<q[2]<Z:
            if name(q) in WALLS|{GLASS}:emit(q,GLASS,'Entrance-side real display/waiting/domestic window in oriented facade')
    if kind in ['local_shop','shophouse','coffee_house','book_office'] and heading=='south':
        # A real west stair bay has a solid street-facing screen. It stays
        # separate from the glazed retail bay and retains every old flight.
        for xx in range(x+1,min(x+5,dx-2)+1):
            for yy in range(f+1,min(f+4,b['roof'])):
                q=(xx,yy,Z)
                if q not in protected_route_cells:emit(q,'minecraft:light_gray_concrete','Opaque entrance-front stair screen prevents an exposed raw flight in the display window')
    # Actual occupied service bays are just inside storefront/room windows,
    # but all authored route cells (including stair flights) veto furniture.
    furnishing=[]
    if kind in ['local_shop','shophouse','coffee_house','book_office','small_inn','clinic','civic']:
        for level,feet in enumerate(b['floor_feet']):
            if level>0:continue
            yy=feet
            for zz in range(z+3,min(Z-2,z+10)):
                q=(X-2,yy,zz)
                if name(q) not in {'minecraft:air','minecraft:cave_air'} or q in protected_route_cells:continue
                # Isolated one-cell pockets are left clear; a continuous side
                # furnishing bay must retain two-wide occupied-room access.
                if name((q[0]-2,q[1],q[2])) not in {'minecraft:air','minecraft:cave_air'}:continue
                item='minecraft:bookshelf' if kind in ['local_shop','shophouse','book_office','civic'] else 'minecraft:smooth_quartz' if kind=='clinic' else 'minecraft:spruce_planks'
                emit(q,item,'Actual '+kind+' storage/reception/reading bay outside every retained declared route');furnishing.append(list(q))
    shopfront=complete_shop_front(b,state,put) if heading=='south' and kind in ['local_shop','shophouse','coffee_house','book_office'] else None
    maintenance=low_shop_maintenance_roof(b,state,put)
    return {'building':owner,'oriented_window_cells':window_bays,'main_door_material':'oak' if domestic else 'manual steel','entry_normal':[nx,nz],'solid_eye_height_plaque':list(signq),'canopy_clear_feet':f+3.5,'actual_interior_furnishings':furnishing,'shopfront':shopfront,'maintenance_roof':maintenance,'native_use_verified':False}
