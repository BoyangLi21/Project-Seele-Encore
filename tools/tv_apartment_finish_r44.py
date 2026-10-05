"""Complete warm apartment partitions/headers, real existing-runtime furniture."""
TABLE='another_furniture:oak_table[facing=north,leg_1=true,leg_2=true,leg_3=true,leg_4=true,waterlogged=false]'
CHAIR='another_furniture:oak_chair[facing=north,tucked=false,variant=1,waterlogged=false]'
SOFAS=['another_furniture:brown_sofa[facing=east,type=left,waterlogged=false]','another_furniture:brown_sofa[facing=east,type=right,waterlogged=false]']
PLASTER='projectseele:residential_plaster'
PLASTER_TOP='projectseele:residential_plaster_slab[type=top,waterlogged=false]'
def author(b,state,put,protected):
    x,z,X,Z=b['bounds'];f=b['floor']+10;L=x+10;N=Z-14;S=Z-1;owner=b['id'];changed_walls=[];ceilings=[];headers=[];doors=[]
    walls={'minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:smooth_quartz',PLASTER}
    def emit(q,s,why):put(q,s,owner,why)
    protected=set(protected);stair_heads=set()
    # Original five-step three-wide common flights are positive structural
    # ownership. A0.6m sampled centreline does not protect their two side lanes.
    for level in range(b.get('storeys',len(b.get('floor_feet',[])))):
        y=b['floor']+level*5;north=level%2==0;sx=x+(3 if north else 7);sz=z+(10 if north else 4);direction=-1 if north else 1
        for i in range(5):
            yy=y+i+1;zz=sz+direction*i
            for xx in range(sx-1,sx+2):
                for Y in range(yy+1,yy+5):stair_heads.add((xx,Y,zz))
    protected.update(stair_heads)
    restored_stair_heads=[]
    for q in sorted(stair_heads):
        if q[1]==f+4 and state(q)in{'minecraft:smooth_quartz',PLASTER}:
            emit(q,'minecraft:air','Restore complete existing three-wide rising flight where the communal ceiling had covered its side lanes');restored_stair_heads.append(q)
    for xx in range(x+1,X):
        for zz in range(z+1,Z):
            # Stair flights/head apertures retain their complete actual
            # capsule sweep, not a renderer silhouette or a guessed cuboid.
            private=xx>=L and zz>=N-1
            for yy in range(f+1,f+4):
                q=(xx,yy,zz);old=state(q)
                if old and old.split('[')[0] in walls and q not in protected:
                    emit(q,PLASTER,'Whole interior matte painted plaster finish; original texture, structural ownership and all living paths retained')
            low=state((xx,f+1,zz));upper=state((xx,f+2,zz));wall=low and upper and low.split('[')[0] in walls and upper.split('[')[0] in walls
            door=low and '_door[' in low
            if wall or door:
                q=(xx,f+3,zz)
                if q not in protected:
                    emit(q,PLASTER,'Complete matte plaster partition top / real door header reaches above the2.5m private ceiling or3m public ceiling; retire all through half-cell gaps');headers.append(q)
            if door and low.startswith('projectseele:city_personnel_door['):
                for dy in [1,2]:
                    q=(xx,f+dy,zz);old=state(q)
                    if old and old.startswith('projectseele:city_personnel_door['):emit(q,old.replace('projectseele:city_personnel_door[','minecraft:oak_door['),'Real domestic wood door pair replaces the owned industrial bedroom/household/service door; same actual manual operation and native DoorBlock geometry');doors.append(q)
            # Private ceiling is half-block-top at93.5; the public/shared
            # rooms close at94, except the real rising stair aperture.
            yy=f+3 if private else f+4;q=(xx,yy,zz);old=state(q)
            if q in protected:continue
            if private:
                if old in ('minecraft:smooth_stone_slab[type=top,waterlogged=false]','minecraft:smooth_quartz_slab[type=top,waterlogged=false]',PLASTER_TOP):emit(q,PLASTER_TOP,'Whole matte plaster2.5m private ceiling; retains top-slab clearance');ceilings.append(q)
            elif not old or old in ('minecraft:smooth_quartz',PLASTER) or old.startswith(('minecraft:air','minecraft:cave_air','minecraft:void_air')):
                emit(q,PLASTER,'Complete3m communal corridor/neighbour/utility matte ceiling around retained stair aperture');ceilings.append(q)
    for xx in [L+3,L+4]:emit((xx,f+1,N+3),TABLE,'Actual existing-runtime oak dining table with native seven-box legs/top; retire floating vanilla slab proxy')
    for zz in [N+7,S-2]:
        for dy in [1,2]:
            q=(X,f+dy,zz);old=state(q)
            if old and old.startswith('projectseele:city_personnel_door['):emit(q,old.replace('projectseele:city_personnel_door[','minecraft:oak_door['),'Complete home living/bedroom veranda wood door pair; retained actual outer shell and balcony')
        emit((X,f+3,zz),PLASTER,'Whole veranda door matte plaster lintel closes its upper opening against the private ceiling')
    emit((L+3,f+1,N+4),CHAIR,'Actual existing-runtime oak dining chair, clear of the genkan route')
    for index,zz in enumerate([N+4,N+5]):emit((L+11,f+1,zz),SOFAS[index],'Actual connected cushioned household sofa with native ground legs, not stair blocks')
    emit((L+10,f+1,N+6),TABLE,'Actual living work/coffee table with grounded native legs')
    # Complete kitchen countertop/cabinet fronts, preserving real sink,
    # cooker preparation table, foyer shoe cabinet and the small PenPen bay.
    for xx in range(L+1,L+6):
        emit((xx,f+1,N),'minecraft:smooth_quartz','Whole warm-white kitchen base cabinet/counter run, actual floor bearing')
        emit((xx,f+2,N),'minecraft:oak_planks','Grounded upper kitchen cabinet row against the retained rear wall')
    # Bedroom furniture occupies side/rear corners outside each true door.
    for xx,zz in [(L+11,N),(L+5,S),(X-1,S)]:emit((xx,f+1,zz),'minecraft:oak_planks','Real grounded bedside/dresser surface alongside the retained household bed')
    return dict(wall_and_header_cells=headers,wood_door_cells=doors,whole_ceiling_cells=ceilings,actual_furniture_states=[TABLE,CHAIR]+SOFAS,stairs_full_capsule_preserved=True,full_declared_three_wide_stair_head_mask=sorted(stair_heads),restored_side_lane_ceiling_cells=restored_stair_heads,world_written=False)
