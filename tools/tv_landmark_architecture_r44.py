"""Original TV landmark geometry; metre grids are playable engineering choices.

School massing follows TV-facing references plus the separately labelled official
SMALL WORLDS model. No official image/audio is incorporated as a game asset.
"""


def school(b,state,put,door):
    x,z,X,Z=b['bounds'];f=b['floor'];roof=b['roof'];owner=b['id'];mid=(x+X)//2
    north_end=z+12;south_start=Z-12;rooms=[];cases=[];bridges=[]
    wall='minecraft:white_concrete';floor='minecraft:smooth_stone';glass='minecraft:gray_stained_glass'
    def emit(q,s,why):put(q,s,owner,why)
    def fill(box,s,why):
        a,y,c,A,Y,C=box
        for yy in range(y,Y+1):
            for zz in range(c,C+1):
                for xx in range(a,A+1):emit((xx,yy,zz),s,why)
    # An actual open court separates the two bars, not a tinted office slab.
    fill((x,f+1,north_end+1,X,roof+4,south_start-1),'minecraft:air','Whole school courtyard open to sky between the real classroom bars')
    fill((x+1,f,north_end+1,X-1,f,south_start-1),'minecraft:grass_block[snowy=false]','Low school courtyard lawn on measured full founded ground')
    fill((mid-2,f,north_end,mid+2,f,south_start),floor,'Real central entrance/courtyard route connects both classroom bars')
    # Classrooms and2m corridors have their own supported walls and doors.
    for level in range(b['storeys']):
        y=f+level*5
        for wing,za,zb in [('north',z,north_end),('south',south_start,Z)]:
            for face in [za,zb]:fill((x,y+1,face,X,y+4,face),wall,'Complete supported classroom-bar facade; former courtyard-border scan cells are actual walls')
            # Preserve the already authored full west stair core in the north
            # bar; classroom furniture never replaces its actual flight.
            room_start=x+11 if wing=='north' else x+2
            fill((room_start,y+1,za+1,X-2,y+3,zb-1),'minecraft:air','Retire generic office/bedroom partitions; authored school rooms replace them')
            corridor_z=zb-3
            fill((room_start,y+1,corridor_z,X-2,y+3,corridor_z),wall,'Real classroom-to-corridor boundary with individually usable doors')
            classroom_end=X-10 if wing=='south' else X-2
            segments=[(xx,min(xx+13,classroom_end)) for xx in range(room_start,classroom_end,14)]
            # A remainder is part of its neighbouring classroom, never a
            # labelled two-metre classroom produced by a range() tail.
            if len(segments)>1 and segments[-1][1]-segments[-1][0]-1<8:
                segments[-2]=(segments[-2][0],segments[-1][1]);segments.pop()
            for xx,end in segments:
                entry=min(end-2,xx+5)
                if xx>room_start:fill((xx,y+1,za+1,xx,y+3,corridor_z),wall,'Supported individual classroom partition')
                door(entry,y,corridor_z,owner,'south')
                number=len([r for r in rooms if r.get('wing')==wing and r.get('floor')==level+1])+1
                label='2-A' if wing=='north' and level==1 and number==1 else f'{level+1}-{wing[0].upper()}{number}'
                rooms.append(dict(id=owner+'/'+label,label=label,wing=wing,floor=level+1,kind='classroom' if level>0 else 'classroom_or_staff',bounds=[xx+1,y+1,za+1,end-1,y+3,corridor_z-1],canonical_metres=False,minimum_clear_width_metres=8))
                # Desks face a real chalkboard, in repeated double-seat bays.
                fill((xx+2,y+2,za+1,min(end-2,xx+10),y+3,za+1),'minecraft:green_terracotta','Original green classroom chalkboard; no copied TV artwork/text')
                for dz in [4,7]:
                    for dx in [3,7,10]:
                        if xx+dx>end-1 or za+dz+1>=corridor_z:continue
                        emit((xx+dx,y+1,za+dz),'minecraft:crafting_table','Usable grounded classroom work desk with free corridor/door circulation; original voxel furniture interpretation')
                        emit((xx+dx,y+1,za+dz+1),'minecraft:dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]','Classroom side seating faces its actual chalkboard')
                p=[[entry+.5,y+1,corridor_z+1.5],[entry+.5,y+1,corridor_z-1.5]]
                for suffix,path in [('',p),('/return',p[::-1])]:cases.append(dict(id=owner+'/'+label+'/door'+suffix,path=path,door=[entry,y+1,corridor_z],native_passed=False))
            for xx in range(room_start+2,X-3,5):fill((xx,y+2,za,min(xx+2,X-2),y+3,za),glass,'Long repeated school classroom window bands, backed by real occupied rooms')
        # Enclosed links across the courtyard occur at each actual storey.
        if level==0:
            for zz,heading in [(north_end,'south'),(south_start,'north')]:door(mid,y,zz,owner,heading)
        if level>0:
            fill((mid-2,y,north_end,mid+2,y,south_start),floor,'Full school linking corridor deck supported by the two classroom bars')
            for xx in [mid-2,mid+2]:fill((xx,y+1,north_end+1,xx,y+3,south_start-1),glass,'Glazed linking corridor side wall, not a floating painted line')
            fill((mid-2,y+4,north_end+1,mid+2,y+4,south_start-1),floor,'Actual linking corridor weather cover')
            for zz in [north_end,south_start]:
                fill((mid-1,y+1,zz,mid+1,y+2,zz),'minecraft:air','Complete classroom-bar/link aperture at the same real storey')
            bridges.append(dict(floor=level+1,bounds=[mid-2,y,north_end,mid+2,y+4,south_start],structural_span_metres=south_start-north_end,metres_inferred=True))
    # Two usable end towers distinguish the school from a generic office.
    # North/west tower uses the retained full original stair and roof hatch.
    # The south/east tower has its own mirrored five-rise flight per storey.
    sx=X-4;za=south_start
    for level in range(b['storeys']):
        y=f+level*5
        fill((X-8,y+1,za+1,X-1,y+4,Z-1),'minecraft:air','Whole south-east school stair tower clearance')
        fill((X-8,y,za+1,X-1,y,za+3),floor,'Full school end stair landing')
        fill((X-8,y,Z-3,X-1,y,Z-1),floor,'Full school end stair return landing')
        if level==b['storeys']-1:continue
        for i in range(5):
            yy=y+i+1;zz=za+4+i
            fill((sx-1,yy,zz,sx+1,yy,zz),'minecraft:polished_andesite_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]','Real three-wide school end stair flight')
            fill((sx-1,yy+1,zz,sx+1,yy+3,zz),'minecraft:air','Actual end stair headroom through the next floor')
        p=[[sx+.5,y+1,za+3.5],[sx+.5,y+6,za+9.5],[X-7.5,y+6,Z-2.5],[X-7.5,y+6,za+2.5]]
        for suffix,path in [('',p),('/return',p[::-1])]:cases.append(dict(id=owner+f'/east_tower_stairs{level+1}'+suffix,path=path,native_passed=False))
    dx,dy,dz=b['door'];door(dx,f,dz,owner,b.get('facing','south'))
    north_entry=x+9;door(north_entry,f,z,owner,'north');p=[[north_entry+.5,f+1,z-1.5],[north_entry+.5,f+1,z+2.5]]
    for suffix,path in [('',p),('/return',p[::-1])]:cases.append(dict(id=owner+'/sports_side_entry'+suffix,path=path,door=[north_entry,f+1,z],native_passed=False))
    # Thin roof metal guards and actual roof doors match the reference logic.
    b['architecture']='Two real three-storey classroom bars / open planted court / glazed links / west and east stair towers /2-A classroom / guarded roof with real north stair hatch'
    return dict(rooms=rooms,cases=cases,bridges=bridges,source_relation='TV-facing massing plus separately labelled official2019 SMALL WORLDS secondary model; dimensions/room count/furniture are engineering adaptation',world_written=False)


def gym(b,state,put):
    x,z,X,Z=b['bounds'];f=b['floor'];owner=b['id'];mid=(x+X)//2;span=max(1,(X-x)/2);b['roof']=f+10;b['roof_role']='Continuous curved gym weather roof; no public roof route'
    for yy in range(f+1,f+11):
        for zz in range(z,Z+1):
            for xx in range(x,X+1):put((xx,yy,zz),'minecraft:air',owner,'Retire generic low commercial ceiling/furniture before the actual gym volume')
    for xx in range(x,X+1):
        rise=round(4*(max(0,1-((xx-mid)/span)**2)**.5));yy=f+6+rise
        for zz in range(z,Z+1):put((xx,yy,zz),'minecraft:smooth_stone',owner,'Continuous original barrel-vault gym weather cover, playable rounded voxel engineering interpretation')
        for zz in [z,Z]:
            for yb in range(f+1,yy):put((xx,yb,zz),'minecraft:white_concrete',owner,'Founded gym end wall supports the whole curved roof profile')
    for xx in [x,X]:
        for zz in range(z,Z+1):
            for yy in range(f+1,f+6):put((xx,yy,zz),'minecraft:white_concrete',owner,'Full gym long wall and roof bearing')
    dx,dy,dz=b['door']
    for half,i in [('lower',0),('upper',1)]:put((dx,dy+i,dz),f'projectseele:city_personnel_door[facing={b.get("facing","south")},half={half},hinge=left,open=false,powered=false]',owner,'Complete real gym entrance after full volume authoring')
    b['architecture']='School gym with continuous barrel-vault weather roof, actual entrance and court floor; curved profile inferred from secondary reference'
    return dict(rooms=[dict(id=owner+'/gym_court',kind='sports_court',bounds=[x+1,f+1,z+1,X-1,f+5,Z-1],canonical_metres=False)],cases=[],world_written=False)


def school_entrance(b,state,put):
    """Wide two-door school genkan, actual sheltered hall and shoe-rack bays."""
    x,z,X,Z=b['bounds'];f=b['floor'];owner=b['id'];centre=(x+X)//2;left=centre-4;right=centre+4;front=Z+5;cases=[]
    def fill(box,s,why):
        a,y,c,A,Y,C=box
        for yy in range(y,Y+1):
            for zz in range(c,C+1):
                for xx in range(a,A+1):put((xx,yy,zz),s,owner,why)
    fill((left,f,Z+1,right,f,front),'minecraft:smooth_stone','Whole founded school entry floor spans the full double-door genkan, not a narrow private-house porch')
    fill((left,f+1,Z+1,right,f+4,front),'minecraft:air','Whole double-door school vestibule clears former domestic canopy/soil/wood plaque remnants')
    for xx in [left,right]:fill((xx,f+1,Z+1,xx,f+4,front),'minecraft:white_concrete','Full supported school vestibule side wall')
    fill((left,f+1,front,right,f+4,front),'minecraft:white_concrete','Full school outer genkan frontage and lintel')
    fill((left-1,f+5,Z,right+1,f+5,front+1),'minecraft:smooth_stone','Wide shallow supported school weather cover and sheltered entrance eaves')
    for xx in [left,right]:fill((xx,f+2,Z+2,xx,f+3,front-1),'minecraft:gray_stained_glass','Real genkan sidelights between full wall posts')
    for boundary,name in [(front,'outer'),(Z,'inner')]:
        for xx,hinge in [(centre-1,'left'),(centre,'right')]:
            for dy,half in [(1,'lower'),(2,'upper')]:put((xx,f+dy,boundary),f'projectseele:city_personnel_door[facing=south,half={half},hinge={hinge},open=false,powered=false]',owner,'Complete independently usable mirrored school double-door pair')
            fill((xx,f+3,boundary,xx,f+4,boundary),'minecraft:white_concrete','Actual full school double-door lintel closes former window above the two real leaves')
            path=[[xx+.5,f+1,boundary+1.5],[xx+.5,f+1,boundary-1.5]]
            for suffix,p in [('',path),('/return',path[::-1])]:cases.append(dict(id=owner+'/genkan/'+name+f'_leaf{xx-centre+2}'+suffix,path=p,door=[xx,f+1,boundary],native_passed=False))
    # Shelves are real half-height wood volumes, with open cubby gaps and
    # a complete two-wide central walking aisle. They are original voxel
    # furniture, not a bookshelf block pretending that its printed books
    # are shoes, and no item-frame/entity is invented by this block plan.
    for xx in [left+1,right-1]:
        for zz in range(Z+2,front):
            for yy in [f+1,f+2,f+3]:put((xx,yy,zz),'minecraft:dark_oak_slab[type=top,waterlogged=false]',owner,'Actual open shoe/umbrella rack shelf bay, clear of the double-door school circulation')
    olddoor=list(b['door']);b['door']=[centre,f+1,front];b['entry']=[centre,f+1,front+1];b['school_genkan_bounds']=[left,f,Z,right,f+5,front+1]
    b['architecture']+=' / broad twin-door genkan with real vestibule, sheltered eaves and open wood shoe-rack bays'
    return dict(rooms=[dict(id=owner+'/school_genkan',kind='shoe_rack_entrance_hall',bounds=[left+1,f+1,Z+1,right-1,f+4,front-1],metres_inferred=True)],cases=cases,old_inner_door=olddoor,protection=dict(bounds=[left-1,f-3,Z-1,right+1,f+8,front+2],owner=owner,role='Whole double-door school vestibule / shoe shelves / eaves / real public approach'),world_written=False)


def misato_home(b,state,put,door,bed):
    x,z,X,Z=b['bounds'];f=b['floor'];owner=b['id'];left=x+10;right=X-1;front=Z-11;back=Z;rooms=[];cases=[]
    def emit(q,s,why):put(q,s,owner,why)
    def fill(box,s,why):
        a,y,c,A,Y,C=box
        for yy in range(y,Y+1):
            for zz in range(c,C+1):
                for xx in range(a,A+1):emit((xx,yy,zz),s,why)
    for level in range(b['storeys']):
        y=f+level*5;home=level==2
        if home:
            # This household occupies the eastern side of this engineering
            # floor. Read the actual reference adjacency rather than assign
            # three TV names to the repeated ordinary-unit bedroom strip.
            # Reference top = local north; veranda = local east. Rotation,
            # floor number and metre grid are explicit adaptation choices.
            L=x+10;R=X;N=z+1;S=Z-1
            fill((x+1,y+1,Z-11,L-1,y+3,S),'minecraft:air','Full common hall connects retained stair landing to the household side genkan')
            fill((L,y+1,N,R,y+3,S),'minecraft:air','Retire whole generic floor3 partitions and furniture before TV relational layout')
            for xx in [L,R]:fill((xx,y+1,N,xx,y+3,Z),'minecraft:white_concrete','Complete household west/east perimeter')
            for zz in [z,Z]:fill((L,y+1,zz,R,y+3,zz),'minecraft:white_concrete','Complete household north/south perimeter')
            # Misato is at the opposite end of the living room; Shinji and
            # Asuka face each other across the short southern hall.
            fill((L+6,y+1,N+5,R-1,y+3,N+5),'minecraft:white_concrete','Misato bedroom at the upper end of the actual living room')
            fill((L+6,y+1,N,L+6,y+3,N+5),'minecraft:white_concrete','Misato west closet/bedroom boundary')
            fill((L+1,y+1,S-6,L+6,y+3,S-6),'minecraft:white_concrete','Shinji bedroom adjoining the entrance/wash side')
            fill((L+6,y+1,S-6,L+6,y+3,S),'minecraft:white_concrete','Shinji side of the two-metre short private hall')
            fill((L+9,y+1,S-6,R-1,y+3,S-6),'minecraft:white_concrete','Asuka bedroom at the lower living-room/veranda end')
            fill((L+9,y+1,S-6,L+9,y+3,S),'minecraft:white_concrete','Asuka side of the short hall opposite Shinji')
            # Left-side bath/wash/WC block, with actual separate doors.
            fill((L+1,y+1,N+11,L+6,y+3,N+11),'minecraft:light_gray_concrete','Wet-core top boundary beside kitchen/living opening')
            fill((L+4,y+1,N+11,L+4,y+3,N+15),'minecraft:light_gray_concrete','Separate bath and wash/WC side boundary')
            fill((L+4,y+1,N+13,L+6,y+3,N+13),'minecraft:light_gray_concrete','Separate washing and WC compartments')
            fill((L+6,y+1,N+11,L+6,y+3,N+15),'minecraft:light_gray_concrete','Wet-core east boundary opens onto the real short hall')
            doors=[('misato',L+9,N+5,'south',[L+7,N,L+11,N+4],[L+10,N+7,L+9,N+3]),
                ('shinji',L+6,S-3,'east',[L+1,S-5,L+5,S],[L+7,S-3,L+4,S-3]),
                ('asuka',L+9,S-3,'west',[L+10,S-5,R-1,S],[L+8,S-3,L+11,S-3]),
                ('bath',L+4,N+12,'east',[L+1,N+12,L+3,N+15],[L+5,N+12,L+2,N+12]),
                ('wash',L+6,N+12,'east',[L+5,N+12,L+5,N+12],[L+7,N+12,L+5,N+12]),
                ('wc',L+6,N+14,'east',[L+5,N+14,L+5,N+15],[L+7,N+14,L+5,N+14])]
            for name,xx,zz,heading,box,leg in doors:
                door(xx,y,zz,owner,heading)
                rooms.append(dict(id=owner+'/floor3/'+name,kind='private_bedroom' if name in ['misato','shinji','asuka'] else 'wet_room',household='TV_Misato',bounds=[box[0],y+1,box[1],box[2],y+3,box[3]],canonical_metres=False))
                ax,az,bx,bz=leg;path=[[ax+.5,y+1,az+.5],[bx+.5,y+1,bz+.5]]
                # A diagonal bedroom route would cross a real partition;
                # approach the Misato doorway along the living-room axis.
                if name=='misato':path=[[xx+.5,y+1,N+7.5],[xx+.5,y+1,N+3.5]]
                for suffix,p in [('',path),('/return',path[::-1])]:cases.append(dict(id=owner+'/floor3/'+name+'/entry'+suffix,path=p,door=[xx,y+1,zz],native_passed=False))
            bed(L+7,y+1,N+3,owner);bed(L+2,y+1,S-1,owner);bed(L+11,y+1,S-1,owner)
            # Genkan must connect through a hall, not through Shinji's room.
            # Its west entry feeds the clear kitchen/wet-core-side corridor.
            entrance_z=N+10;door(L,y,entrance_z,owner,'west')
            path=[[L-1.5,y+1,entrance_z+.5],[L+1.5,y+1,entrance_z+.5],[L+3.5,y+1,entrance_z+.5],[L+5.5,y+1,entrance_z+.5],[L+7.5,y+1,entrance_z+.5],[L+7.5,y+1,N+8.5]]
            for suffix,p in [('',path),('/return',path[::-1])]:cases.append(dict(id=owner+'/floor3/genkan_to_living'+suffix,path=p,door=[L,y+1,entrance_z],native_passed=False))
            # Open kitchen/dining left of living; PenPen provision is at
            # the opening between those two real zones.
            for xx in range(L+1,L+4):emit((xx,y+1,N+6),'minecraft:smooth_quartz','Kitchen counter on left side of the living/dining zone; two-metre gap accesses the upper storage area')
            emit((L+3,y+1,N+8),'minecraft:crafting_table','Actual dining work table with surrounding walkable space')
            emit((L+5,y+1,N+9),'minecraft:light_blue_concrete','PenPen refrigeration bay at kitchen/living opening')
            emit((L+5,y+2,N+9),'minecraft:white_concrete','Supported original refrigeration upper casing')
            for half,dy in [('lower',1),('upper',2)]:emit((L+6,y+dy,N+9),f'projectseele:city_personnel_door[facing=east,half={half},hinge=left,open=false,powered=false]','Actual PenPen refrigeration access at the kitchen/living opening')
            emit((L+2,y+1,N+14),'minecraft:water_cauldron[level=3]','Bath fixture outside the actual door route')
            emit((L+5,y+1,N+15),'minecraft:water_cauldron[level=3]','WC fixture outside the actual door route')
            # Side veranda follows the reference adjacency along living,
            # Misato and Asuka; its geometry is founded into the floor.
            fill((R+1,y,N,R+3,y,Z),'minecraft:smooth_stone','Whole eastern veranda deck supported by the household floor')
            fill((R+3,y+1,N,R+3,y+1,Z),'minecraft:light_gray_concrete','Whole veranda lower guard')
            fill((R+3,y+2,N,R+3,y+2,Z),'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]','Fine veranda outer metal guard')
            for zz in [N,Z]:fill((R+1,y+1,zz,R+3,y+1,zz),'minecraft:light_gray_concrete','Veranda end guards')
            for name,zz in [('living',N+8),('asuka',S-4)]:
                door(R,y,zz,owner,'east');path=[[R-1.5,y+1,zz+.5],[R+2.5,y+1,zz+.5]]
                for suffix,p in [('',path),('/return',path[::-1])]:cases.append(dict(id=owner+'/floor3/'+name+'_veranda'+suffix,path=p,door=[R,y+1,zz],native_passed=False))
            for name,box in [('genkan',[L+1,N+10,L+3,N+10]),('kitchen_dining',[L+1,N+6,L+5,N+10]),('living',[L+7,N+6,R-1,N+14]),('short_hall',[L+7,S-6,L+8,S])]:rooms.append(dict(id=owner+'/floor3/'+name,kind='connected_home_core',household='TV_Misato',bounds=[box[0],y+1,box[1],box[2],y+3,box[3]],canonical_metres=False))
            continue
        fill((left,y+1,z+1,right,y+3,front-1),'minecraft:air','Real common hall from the retained complete stair to each unit; retire obsolete generic upper-unit wall across the landing')
        fill((left,y+1,front,right,y+4,back),'minecraft:air','Replace generic upper units with real residential layout and clear common stair/entry connection')
        for xx in [left,right]:fill((xx,y+1,front,xx,y+3,back),'minecraft:white_concrete','Real apartment outer side wall')
        for zz in [front,back]:fill((left,y+1,zz,right,y+3,zz),'minecraft:white_concrete','Complete unit entrance/balcony facade')
        # Foyer into a2m hall; private bedrooms sit separately along its west.
        fill((left+4,y+1,front+1,left+4,y+3,back-1),'minecraft:white_concrete','TV-household hall/private-room boundary, metre grid inferred for player clearance')
        for n,(name,za,zb) in enumerate([('misato',front+3,front+5),('asuka',front+6,front+8),('shinji',front+9,back-1)]):
            for zz in [za-1,zb+1]:fill((left+1,y+1,zz,left+4,y+3,zz),'minecraft:white_concrete','Separate occupied bedroom boundary')
            door(left+4,y,za+1,owner,'east');bed(left+1,y+1,min(zb,za+1),owner)
            rooms.append(dict(id=owner+f'/floor{level+1}/'+(name if home else 'bedroom'+str(n+1)),kind='private_bedroom',household='TV_Misato' if home else 'ordinary_unit',bounds=[left+1,y+1,za,left+3,y+3,zb],canonical_metres=False))
            p=[[left+5.5,y+1,za+1.5],[left+2.5,y+1,za+1.5]]
            for suffix,path in [('',p),('/return',p[::-1])]:cases.append(dict(id=rooms[-1]['id']+'/entry'+suffix,path=path,door=[left+4,y+1,za+1],native_passed=False))
        entrance=left+6;door(entrance,y,front,owner,'north')
        door(left+4,y,front+1,owner,'east')
        # Front-right wet core/PenPen nook; kitchen/living continues rearward.
        for boundary in [front+3,front+6]:fill((left+7,y+1,boundary,right-1,y+3,boundary),'minecraft:light_gray_concrete','Separate washing/WC/bath and kitchen/living zones')
        for zz in [front+2,front+5]:door(left+7,y,zz,owner,'west')
        emit((right-2,y+1,front+2),'minecraft:water_cauldron[level=3]','Usable washing basin in the actual wet core')
        emit((right-2,y+1,front+5),'minecraft:water_cauldron[level=3]','Separate bath fixture, original voxel adaptation')
        emit((left+8,y+1,front+1),'minecraft:bookshelf','Original storage/utility nook next to the washing space; PenPen refrigerator provision on the named household floor')
        # Original white refrigeration bay beside the kitchen/wet core.
        # Its actual usable door is retained as geometry, without TV logos.
        # Keep the washing basin emitted above. A refrigerator is a cabinet,
        # never a personnel doorway overwritten onto the basin and wet wall.
        for dy in (1,2):
            emit((right-2,y+dy,front+1),'minecraft:air','Complete washing-room service clearance after retiring the original blocked refrigeration casing')
            emit((right-1,y+dy,front+8),'minecraft:smooth_quartz','Supported native closed refrigeration cabinet beside the actual kitchen wall, outside all real door approaches')
            emit((right-2,y+dy,front+8),'minecraft:polished_blackstone_button[face=wall,facing=west,powered=false]','Recessed native cabinet handle, not a personnel door or room entrance')
        for xx in range(left+8,right-1):emit((xx,y+1,front+7),'minecraft:smooth_quartz','Actual kitchen work counter facing the living space')
        emit((left+8,y+1,front+9),'minecraft:crafting_table','Usable living/dining work table in the named unit')
        # Real balcony is outside the building wall; both public/return legs
        # include the actual south door and a complete supported guarded deck.
        balcony_x=left+10;door(balcony_x,y,back,owner,'south')
        fill((left+7,y,Z+1,right,y,Z+3),'minecraft:smooth_stone','Whole balcony deck bearing into the actual unit floor, not a painted facade mark')
        fill((left+7,y+1,Z+3,right,y+1,Z+3),'minecraft:light_gray_concrete','Supported balcony outer low guard')
        fill((left+7,y+2,Z+3,right,y+2,Z+3),'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]','Fine balcony metal guard above the real founded parapet')
        for xx in [left+7,right]:fill((xx,y+1,Z+1,xx,y+1,Z+3),'minecraft:light_gray_concrete','Complete balcony side guards')
        p=[[balcony_x+.5,y+1,back-1.5],[balcony_x+.5,y+1,back+2.5]]
        for suffix,path in [('',p),('/return',p[::-1])]:cases.append(dict(id=owner+f'/floor{level+1}/balcony'+suffix,path=path,door=[balcony_x,y+1,back],native_passed=False))
        p=[[entrance+.5,y+1,front-1.5],[entrance+.5,y+1,front+1.5]]
        for suffix,path in [('',p),('/return',p[::-1])]:cases.append(dict(id=owner+f'/floor{level+1}/unit_entry'+suffix,path=path,door=[entrance,y+1,front],native_passed=False))
        rooms.append(dict(id=owner+f'/floor{level+1}/genkan_hall_kitchen_living',kind='connected_home_core',household='TV_Misato' if home else 'ordinary_unit',bounds=[left+5,y+1,front+1,right-1,y+3,back-1],canonical_metres=False))
    b['architecture']='Real common apartment stair; named TV household on engineering floor3; genkan→2m hall→kitchen/living/balcony; separate Misato/Asuka/Shinji rooms and washing/WC/bath/PenPen nook. Exact TV metre/floor/address is not asserted.'
    return dict(rooms=rooms,cases=cases,canonical_floor_number=False,canonical_metres=False,source_tv_layout='Root inspected fan floorplan/TV-reference room relationships; ~80m² fan tatami estimate is not official dimension. Compass/location disputed; actual city site is an engineering decision.',world_written=False)
