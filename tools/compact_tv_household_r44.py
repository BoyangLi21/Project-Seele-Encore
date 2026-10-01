"""Door/furniture-scaled TV relational household, preserving outer shell/stairs."""
def author(b,state,put,bed,storage=None):
    x,z,X,Z=b['bounds'];f=b['floor']+10;owner=b['id'];L=x+10;R=X;N=Z-14;S=Z-1;rooms=[];cases=[]
    def fill(box,s,why):
        a,y,c,A,Y,C=box
        for yy in range(y,Y+1):
            for zz in range(c,C+1):
                for xx in range(a,A+1):put((xx,yy,zz),s,owner,why)
    def doorway(xx,zz,heading,name,path):
        for dy,half in [(1,'lower'),(2,'upper')]:put((xx,f+dy,zz),f'projectseele:city_personnel_door[facing={heading},half={half},hinge=left,open=false,powered=false]',owner,'Complete scaled home/private-neighbour/service door pair')
        for suffix,p in [('',path),('/return',path[::-1])]:cases.append(dict(id=owner+'/floor3/'+name+suffix,path=p,door=[xx,f+1,zz],native_passed=False))
    def room(name,kind,box,house='TV_Misato'):
        a,c,A,C=box;rooms.append(dict(id=owner+'/floor3/'+name,kind=kind,household=house,bounds=[a,f+1,c,A,f+3,C],canonical_metres=False,clear_ceiling_metres=2.5 if house=='TV_Misato' else 3))
    # Only the already-authored eastern floor3 area is repartitioned. The
    # retained north/west complete staircase is never swallowed by this unit.
    fill((L+1,f+1,z+1,R-1,f+4,S),'minecraft:air','Retire owned overlarge floor3 partitions/furniture with exact full-NBT inverse before compact household and real neighbour')
    fill((L+1,f,N,R-1,f,S),'minecraft:oak_planks','Warm actual wood household floor; retained structural slab is replaced only within the owned floor3 finish layer')
    fill((L,f+1,z+1,L,f+3,S),'minecraft:white_concrete','Full common-corridor/private-unit boundary remains outside the retained stair')
    fill((L,f+1,N-1,R-1,f+3,N-1),'minecraft:white_concrete','New north neighbour/TV-household boundary compacts the former deep apartment')
    # Compact household ceiling: native TOP slab underside at f+3.5 gives
    # actual2.5m clear height above feet f+1, while the outer storey stays5m.
    fill((L+1,f+3,N,R-1,f+3,S),'minecraft:smooth_stone_slab[type=top,waterlogged=false]','Complete supported2.5m clear home ceiling below the retained next-storey slab')
    # Misato above living; kitchen at left; Shinji and Asuka face short hall.
    fill((L+7,f+1,N,L+7,f+2,N+3),'minecraft:white_concrete','Misato west room/closet boundary')
    fill((L+7,f+1,N+3,R-1,f+2,N+3),'minecraft:white_concrete','Misato room at opposite end of the compact living room')
    fill((L+1,f+1,S-3,L+7,f+2,S-3),'minecraft:white_concrete','Shinji upper room boundary next to the genkan/wet-core side')
    fill((L+7,f+1,S-3,L+7,f+2,S),'minecraft:white_concrete','Shinji side of the actual two-metre short hall')
    fill((L+10,f+1,S-3,R-1,f+2,S-3),'minecraft:white_concrete','Asuka upper room boundary beside living/veranda')
    fill((L+10,f+1,S-3,L+10,f+2,S),'minecraft:white_concrete','Asuka opposite side of the short hall')
    # Wet core with actual separate washing/WC doors and a bath door reached
    # through the washing room, as in the reference relationships.
    fill((L+1,f+1,N+6,L+7,f+2,N+6),'minecraft:light_gray_concrete','Wet-core boundary below compact kitchen/dining')
    fill((L+4,f+1,N+6,L+4,f+2,N+9),'minecraft:light_gray_concrete','Separate bath from washing/WC')
    fill((L+7,f+1,N+6,L+7,f+2,N+9),'minecraft:light_gray_concrete','Separate wet core from actual private hall')
    fill((L+4,f+1,N+8,L+7,f+2,N+8),'minecraft:light_gray_concrete','Separate actual WC and washing compartments')
    for name,xx,zz,heading,path in [
        ('misato_entry',L+10,N+3,'south',[[L+10.5,f+1,N+4.5],[L+10.5,f+1,N+1.5]]),
        ('shinji_entry',L+7,S-1,'east',[[L+8.5,f+1,S-.5],[L+5.5,f+1,S-.5]]),
        ('asuka_entry',L+10,S-2,'west',[[L+9.5,f+1,S-1.5],[L+12.5,f+1,S-1.5]]),
        ('bath_entry',L+4,N+7,'east',[[L+5.5,f+1,N+7.5],[L+2.5,f+1,N+7.5]]),
        ('wash_entry',L+7,N+7,'east',[[L+8.5,f+1,N+7.5],[L+5.5,f+1,N+7.5]]),
        ('wc_entry',L+7,N+9,'east',[[L+8.5,f+1,N+9.5],[L+6.5,f+1,N+9.5]]),
        ('genkan_to_dining',L,N+5,'west',[[L-1.5,f+1,N+5.5],[L+1.5,f+1,N+5.5],[L+8.5,f+1,N+5.5]])]:doorway(xx,zz,heading,name,path)
    bed(L+9,f+1,N+2,owner);bed(L+2,f+1,S-1,owner);bed(L+12,f+1,S,owner)
    room('misato','private_bedroom',[L+8,N,R-1,N+2]);room('shinji','private_bedroom',[L+1,S-2,L+6,S]);room('asuka','private_bedroom',[L+11,S-2,R-1,S])
    room('living','living_with_sofa_tv',[L+8,N+4,R-1,N+9]);room('kitchen_dining','kitchen_with_real_counter_sink_table',[L+1,N,L+6,N+5]);room('bath','wet_room',[L+1,N+7,L+3,N+9]);room('wash','wet_room',[L+5,N+7,L+6,N+7]);room('wc','wet_room',[L+5,N+9,L+6,N+9]);room('short_hall','home_hall',[L+8,S-3,L+9,S])
    # Human-sized original furniture uses native existing states only.
    for xx in range(L+1,L+6):put((xx,f+1,N), 'minecraft:smooth_quartz',owner,'Actual compact kitchen work counter, measured against1m door and2m bed')
    put((L+1,f+1,N+1),'minecraft:water_cauldron[level=3]',owner,'Real kitchen sink in side work bay away from the genkan route')
    put((L+4,f+1,N+1),'minecraft:crafting_table',owner,'Usable kitchen preparation/cooking work surface; original voxel adaptation')
    if storage:storage((L+1,f+1,N+4),owner)
    for xx in [L+3,L+4]:put((xx,f+1,N+3),'minecraft:dark_oak_slab[type=top,waterlogged=false]',owner,'Two-metre family dining table at1m height, not a bare cubic room label')
    put((L+3,f+1,N+4),'minecraft:dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]',owner,'Dining seat faces the real table')
    for zz in [N+4,N+5]:put((L+11,f+1,zz),'minecraft:dark_oak_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]',owner,'Two-metre actual household sofa faces its television and stays outside the wet-core hallway')
    put((R-1,f+1,N+8),'minecraft:smooth_stone_slab[type=top,waterlogged=false]',owner,'Grounded television low stand')
    put((R-1,f+2,N+8),'minecraft:black_concrete',owner,'Original dark television screen/body; no copied TV artwork')
    put((L+10,f+1,N+6),'minecraft:dark_oak_slab[type=top,waterlogged=false]',owner,'Low living-room coffee table separate from the veranda and bedroom door routes')
    put((L+2,f+1,N+9),'minecraft:water_cauldron[level=3]',owner,'Bath fixture beside the actual bath approach, preserving full route')
    put((L+5,f+1,N+9),'minecraft:water_cauldron[level=3]',owner,'Separate actual WC fixture leaves the adjacent real entry cell clear')
    # PenPen has a real small refrigeration bay and manual door at the open
    # kitchen/living side; actual actor identities are not moved or spawned.
    fill((L+6,f+1,N+2,L+6,f+2,N+3),'minecraft:white_concrete','Supported original refrigeration casing at kitchen/living opening')
    fill((L+7,f+1,N+2,L+7,f+2,N+2),'minecraft:white_concrete','Refrigeration bay back casing')
    put((L+7,f,N+3),'minecraft:light_blue_concrete',owner,'Actual blue refrigeration bay floor with a clear1m interior')
    fill((L+7,f+1,N+3,L+7,f+2,N+3),'minecraft:air','Actual clear refrigeration bay cell replaces the former bedroom-corner wall; full side/back casings retained')
    doorway(L+7,N+4,'south','penpen_bay',[[L+7.5,f+1,N+5.5],[L+7.5,f+1,N+3.5]])
    # Restore the retired original veranda door openings to full glass and
    # place actual new living/Asuka doors beside the compact household.
    for zz in [z+9,S-2]:fill((R,f+1,zz,R,f+2,zz),'minecraft:gray_stained_glass','Close obsolete large-unit side veranda doorway before compact actual-room doors')
    for name,zz in [('living_veranda',N+7),('asuka_veranda',S-2)]:doorway(R,zz,'east',name,[[R-1.5,f+1,zz+.5],[R+2.5,f+1,zz+.5]])
    # Public corridor3m wide; neighbouring live unit and utility occupy the
    # former9x22 empty common region. The real stair core remains untouched.
    fill((x+6,f+1,Z-11,x+6,f+2,S),'minecraft:white_concrete','Actual neighbour/utility boundary beside the retained3m public corridor')
    fill((x+1,f+1,Z-5,x+6,f+2,Z-5),'minecraft:white_concrete','Separate small occupied neighbour and communal utility room')
    for name,zz in [('neighbour_entry',Z-9),('utility_entry',S-1)]:doorway(x+6,zz,'east',name,[[x+7.5,f+1,zz+.5],[x+3.5,f+1,zz+.5]])
    bed(x+2,f+1,Z-7,owner);put((x+4,f+1,Z-10),'minecraft:crafting_table',owner,'Real small neighbouring household work/dining table')
    put((x+4,f+1,S),'minecraft:water_cauldron[level=3]',owner,'Actual communal washing/cleaning sink off the3m corridor, leaving its west storage aisle connected')
    for zz in [S-2,S]:put((x+1,f+1,zz),'minecraft:bookshelf',owner,'Real communal supply/book storage off the public corridor')
    doorway(L,N-4,'west','north_neighbour_entry',[[L-.5,f+1,N-3.5],[L+2.5,f+1,N-3.5]])
    bed(L+10,f+1,N-4,owner);put((L+3,f+1,N-6),'minecraft:crafting_table',owner,'Actual neighbouring north unit work/dining bay')
    room('north_neighbour','ordinary_unit',[L+1,z+1,R-1,N-2],'ordinary_unit');room('west_neighbour','ordinary_unit',[x+1,Z-11,x+5,Z-6],'ordinary_unit');room('communal_utility','washing_storage',[x+1,Z-4,x+5,S],'common_area');room('common_corridor','public_corridor',[x+7,Z-11,x+9,S],'common_area')
    # Real warm emitters are visibly recessed through the scaled ceiling;
    # neither hidden minecraft:light cells nor an unlit grey empty room.
    for xx,zz in [(L+3,N+2),(L+10,N+5),(L+10,N+1),(L+3,S-1),(L+12,S-1),(L+5,N+7)]:
        put((xx,f+3,zz),'minecraft:air',owner,'Actual recessed domestic ceiling luminaire opening')
        put((xx,f+4,zz),'minecraft:ochre_froglight[axis=y]',owner,'Visible warm ceiling luminaire in the retained building envelope')
    b['architecture']='Retained five-storey shell and full stair; engineering floor3 compact TV household with2.5m clear ceiling, warm wood floor, actual kitchen/dining/sofa/TV/refrigeration/genkan cabinet and side veranda;3m shared corridor, north/west neighbours and utility. No canonical metres/floor/site asserted.'
    return dict(rooms=rooms,cases=cases,private_bounds=[L,f,N-1,R,f+3,S+1],clear_private_ceiling=2.5,public_corridor_width=3,reference_metres_inferred=True,world_written=False)
