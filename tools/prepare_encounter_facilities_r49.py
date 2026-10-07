"""Measured Yashima ridge and harbour recovery civil candidates; Root alone writes world."""
from pathlib import Path
import argparse,copy,gzip,json,math,hashlib
import nbtlib
from prepare_facilities_r48 import Author,DIM
from query_blocks import AIR
ROOT=Path(__file__).resolve().parents[1]
NATURAL={'minecraft:grass_block','minecraft:dirt','minecraft:stone','minecraft:gravel','minecraft:sand','minecraft:grass','minecraft:short_grass','minecraft:tall_grass','minecraft:oak_leaves','minecraft:oak_log'}
HERO=(-230.5,112,260.5);COVER=(-195.5,108,260.5);ANGEL=(-110.5,110,260.5)
FLOOR='projectseele:nerv_floor_panel';ROCK='minecraft:stone'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r49/encounter_facilities/civil_candidate');args=ap.parse_args()
    a=Author(args.world.resolve(),args.out.resolve());a.out.mkdir(parents=True,exist_ok=True)
    owners=json.loads((ROOT/'artifacts/rebuild_r49/encounter_facilities/west_ridge_survey.json').read_text('utf8'))['city100_owners']
    def owner_at(q):
        x,y,z=q
        return [r['index']for r in owners if r['sweep_xz'][0]<=x<=r['sweep_xz'][1]and r['sweep_xz'][2]<=z<=r['sweep_xz'][3]]
    a.read((-268,75,232),(-176,179,289));d={};protected={};tops={}
    def old_service_walk(x,z,y):return -196<=x<=-193 and 238<=z<=282 and 81<=y<=86
    def put(q,state,reason,tag=None):
        assert not owner_at(q),('City100 movable horizontal footprint is forbidden',q,owner_at(q))
        assert q not in a.t,('Original complete device NBT must remain',q)
        before=a.s[q];name=before.split('[')[0]
        if name not in AIR|NATURAL|{'minecraft:water'} and before!=state:
            raise ValueError(('Original constructed component cannot be overwritten',q,before,state))
        d[q]=(state,reason,tag)
    for x in range(-260,-179):
        for z in range(238,283):
            constructed=[(y,a.s[x,y,z])for y in range(75,100)if a.s[x,y,z].split('[')[0]not in AIR|NATURAL]
            if constructed:
                protected[x,z]=constructed
                # The surveyed continuous X-195 lower-half slab and its X-194
                # buried backing are an existing thin service walk. Preserve
                # both full states and a four-wide, six-high covered passage.
                if not(-196<=x<=-193 and all(y<=80 and (s.startswith('minecraft:smooth_stone_slab[')or s in {'minecraft:deepslate_bricks','minecraft:smooth_stone'})for y,s in constructed)):continue
            ground=max((y for y in range(75,86)if a.s[x,y,z].split('[')[0] in {'minecraft:grass_block','minecraft:dirt','minecraft:stone'}),default=80)
            top=ground
            for cx,cy,cz in (HERO,COVER):
                # Two complete 31m crowns; the rocky shoulders follow uneven
                # falloff outside the crown rather than a rectangular air shelf.
                radius=max(abs(x-(cx-.5))/15,abs(z-(cz-.5))/15)
                if radius<=1:height=cy-1
                else:
                    shoulder=max(0,1-(radius-1)/.65)
                    height=ground+(cy-1-ground)*shoulder*shoulder*(3-2*shoulder)
                    if shoulder>0:height+=.7*math.sin(x*.41+z*.27)+.35*math.sin(z*.8-x*.18)
                top=max(top,math.floor(height))
            tops[x,z]=top
            for y in range(ground+1,top+1):
                if old_service_walk(x,z,y):continue
                if a.s[x,y,z].split('[')[0] not in AIR|NATURAL:continue
                state='minecraft:grass_block[snowy=false]' if y==top else 'minecraft:dirt' if y>=top-2 else 'minecraft:andesite' if (x*7+y*3+z)%23==0 else ROCK
                put((x,y,z),state,'Original natural grass slope reconstructed as an original soil/rock ridge; original constructed columns retained')
    pad_boxes=[]
    for role,(cx,cy,cz) in [('hero',HERO),('cover',COVER)]:
        x0=int(cx)-15;z0=int(cz)-15
        # Python int negative centres rounds towards0; explicitly use the
        # surveyed block datum corresponding to the .5 world centre.
        x0=math.floor(cx)-15;z0=math.floor(cz)-15
        box=[[x0,int(cy)-1,z0],[x0+30,int(cy)-1,z0+30]];pad_boxes.append(dict(role=role,box=box,feet=list((cx,cy,cz))))
        for x in range(x0,x0+31):
            for z in range(z0,z0+31):
                assert (x,z) not in protected or (-196<=x<=-193 and all(y<=80 and (s.startswith('minecraft:smooth_stone_slab[')or s in {'minecraft:deepslate_bricks','minecraft:smooth_stone'})for y,s in protected[x,z])),('A full EVA pad would bury an original road/fixture',role,x,z,protected.get((x,z)))
                for y in range(81,int(cy)-1):
                    if old_service_walk(x,z,y):continue
                    if a.s[x,y,z].split('[')[0] in AIR|NATURAL:put((x,y,z),ROCK,'Full mountain mass supports the complete EVA crown from original natural ground')
                put((x,int(cy)-1,z),FLOOR,'Complete31x31 safe firing/cover crown, not two standable centre cells')
                for y in range(int(cy),int(cy)+61):
                    q=x,y,z
                    if a.s[q].split('[')[0] not in AIR:put(q,'minecraft:air','Full EVA head/body clearance above the commissioned crown')
    # Independent rear equipment/crew apron, clear of the two EVA footprints.
    for x in range(-240,-218):
        for z in range(277,283):
            assert (x,z) not in protected
            for y in range(81,111):put((x,y,z),ROCK,'Rock-backed service apron; no unsupported command/stock island')
            put((x,111,z),FLOOR,'Yashima real service apron behind the firing crown')
    # Native MTR up/down lanes and a manual stair strip use the established
    # native slope/transition recipe and physically connect the old south road.
    escalators=[];walk=[]
    low,high,start_z=80,111,281
    for n in range(high-low+3):
        y=low+max(0,min(high-low,n-1));z=start_z-n
        orient='landing_bottom' if n==0 else 'transition_bottom' if n==1 else 'slope' if n<=high-low else 'transition_top' if n==high-low+1 else 'landing_top'
        for base,forward in [(-247,True),(-243,False)]:
            for lane in (0,1):
                x=base+lane;side='left' if lane==0 else 'right'
                for yy in range(81,y):put((x,yy,z),ROCK,'Real rock bearing under the inclined access device')
                put((x,y,z),f'mtr:escalator_step[direction={str(forward).lower()},facing=north,orientation={orient},side={side},status=true]','Complete two-cell native fast stair lane with original factory states')
                for yy in range(y+1,y+5):put((x,yy,z),'minecraft:air','Measured full device headroom; a terrace cannot plug its own stair')
                put((x,y+1,z),f'mtr:escalator_side[facing=north,orientation={orient},side={side}]','Native edge-matched inclined handrail')
        x=-245
        for yy in range(81,y):put((x,yy,z),ROCK,'Continuous supported manual stair beside both fast lanes')
        put((x,y,z),f'minecraft:polished_andesite_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]' if 2<=n<=high-low+1 else FLOOR,'Manual walk stair has real half-height native treads')
        for yy in range(y+1,y+5):put((x,yy,z),'minecraft:air','Manual stair complete body/head clearance')
        walk.append([x+.5,y+1,z+.5])
    escalators=[dict(start=[x,80,281],top=[x,111,248],width=2,direction='up' if flag else 'down')for x,flag in[(-247,True),(-243,False)]]
    # Join actual old road foot81 atZ284 to lower landing, and top to crown.
    for z in range(282,285):
        for x in range(-247,-241):
            q=x,80,z
            if a.s[q].split('[')[0] in AIR|NATURAL:put(q,FLOOR,'Short supported approach joins the original south street, whose pavement is retained')
            for y in range(81,84):
                if a.s[x,y,z].split('[')[0] in AIR|NATURAL:put((x,y,z),'minecraft:air','Approach headroom joins the preserved road')
    for x in range(-247,-239):
        for z in range(247,249):
            for y in range(81,111):
                if a.s[x,y,z].split('[')[0] in AIR|NATURAL:put((x,y,z),ROCK,'Rock-backed upper stair landing connects to complete hero crown')
            put((x,111,z),FLOOR,'Full-width upper landing; no dead stair end')
    # Only short pylon/lever hardware: these are actual registered block BEs.
    a.read((-12,81,3),(-12,81,3));prototype=a.t[-12,81,3]
    pylons=[];switches=[]
    for x in(-239,-231,-223):
        for y in(112,113):put((x,y,280),'minecraft:iron_block','Grid relay pedestal is supported by the equipment apron')
        q=x,114,280;tag=copy.deepcopy(prototype)
        for k,n in zip(('x','y','z'),q):tag[k]=nbtlib.Int(n)
        put(q,'projectseele:umbilical_pylon','Real native external-power socket; complete factory NBT with new coordinates',tag);pylons.append(list(q))
        switch=x,113,279;put(switch,'minecraft:lever[face=wall,facing=north,powered=false]','Actual wall-supported independent grid switch; campaign controller must consume actual powered state');switches.append(list(switch))
    buttons=[]
    for x,purpose in[(-236,'coolant'),(-228,'reload')]:
        put((x,112,280),'minecraft:iron_block','Real console support, separate from inventory/actor identity')
        q=x,112,279;put(q,'minecraft:stone_button[face=wall,facing=north,powered=false]','Actual '+purpose+' console button; no fake UI-only readiness');buttons.append(dict(role=purpose,pos=list(q)))
    # Coarse protected lead is in a visible rock-backed trench along the rear
    # apron. It is original block-built cable casing, not a model rewrite.
    for x in range(-241,-222):put((x,112,282),'minecraft:black_concrete','Continuous coarse protected electrical trunk between all three real grid pylons')
    a.emit('Y01_ridge_crowns_grid_access',d,dict(site_role='Original compact playable highland at city west edge; current natural ground was a grass slope, not a pre-existing high mountain',hero=list(HERO),cover=list(COVER),angel=list(ANGEL),pad_boxes=pad_boxes,city100_movable_owners_untouched=True,original_constructed_columns_retained=[dict(x=x,z=z,cells=cells)for(x,z),cells in protected.items()],escalators=escalators,manual_stair=walk,grid_switches=switches,power_pylons=pylons,console_buttons=buttons,original_actor_and_inventory_untouched=True,full_field_geometry_native_verified=False))
    # Original stationary ship hulls are outside this new western recovery pad.
    a.read((1400,38,578),(1436,131,628));d={};bearing=[]
    def marine_put(q,state,reason):
        assert q not in a.t and not owner_at(q)
        old=a.s[q];assert old.split('[')[0] in AIR|NATURAL|{'minecraft:water','minecraft:gray_concrete','minecraft:smooth_stone','projectseele:nerv_floor_panel'} or old==state,('Unknown original harbour component',q,old)
        d[q]=(state,reason,None)
    for x in range(1403,1434):
        for z in range(593,624):
            marine_put((x,63,z),'projectseele:nerv_structural_panel','Complete naval recovery pad underside, outside fish turning basin and original hulls')
            marine_put((x,64,z),FLOOR,'Complete31x31 real EVA shore/deck handover pad; foot65')
    for x in range(1412,1425):
        for z in range(588,593):
            marine_put((x,63,z),'projectseele:nerv_structural_panel','Full supported connection from the original quay tail')
            marine_put((x,64,z),FLOOR,'Thirteen-wide link from original quay to new marine recovery crown')
    for x in(1405,1418,1431):
        for z in(595,608,621):
            solid=[y for y in range(38,63)if a.s[x,y,z].split('[')[0] in {'minecraft:stone','minecraft:gravel','minecraft:sand','minecraft:dirt','minecraft:grass_block'}]
            assert solid,('No measured pile bearing',x,z)
            y0=max(solid)
            for y in range(y0+1,64):marine_put((x,y,z),'projectseele:nerv_structural_panel','Complete marine pile bears on the measured native seabed')
            bearing.append(dict(x=x,z=z,seabed_y=y0,top_y=63))
    # Retain full vehicle/airlift access along west/north; perimeter protection
    # is outside the central EVA soles and does not create a phantom passage.
    for x in range(1403,1434):
        for z in(593,623):
            if z==593 and 1412<=x<=1424:continue
            marine_put((x,65,z),'projectseele:nerv_edge_rail[east=false,north='+str(z==593).lower()+',south='+str(z==623).lower()+',west=false]','Complete exposed pad edge guard with the north link kept open')
    for z in range(594,623):
        for x in(1403,1433):marine_put((x,65,z),'projectseele:nerv_edge_rail[east='+str(x==1433).lower()+',north=false,south=false,west='+str(x==1403).lower()+']','Original recovery pad lateral protection outside moving fish envelope')
    a.emit('M01_harbour_recovery_pad',d,dict(hero=[1418.5,65,608.5],pad=[[1403,63,593],[1433,64,623]],link=[[1412,63,588],[1424,64,592]],all_original_ship_blocks_BEs_actors_unchanged=True,measured_pile_bearing=bearing,marine_boss_basin_stays_east_of1450=True,requires_original_cannon_line_or_explicit_identity_preserving_relocation=True,native_game_verified=False))
    # Preserve original city static shard NBT, with both complete components.
    a.recipe()
    marker=dict(schema=49,dimension=DIM,installed=False,source_world=str(a.world),world_written=False,
                yashima=dict(hero=list(HERO),cover=list(COVER),angel=list(ANGEL),yaw=-90,requires_retracted_city=True,visibility='native_tracking',attack_range=160,primary_unit=1,geometry_native_verified=False,pad_boxes=pad_boxes,grid_switches=switches,power_pylons=pylons,console_buttons=buttons,
                supply_racks=[dict(unit=0,uuid='e9fd32e9-b3a3-5dc6-8d9f-21ce267a848e',cargo_uuid='3ea20e4d-37bf-5c8c-90b6-26316d2b4911',position=[-237.5,112,279.5],new_once_only=True),dict(unit=1,uuid='749cf141-0e2f-59ef-9e9b-d08346d5ea8d',cargo_uuid='58eab304-0fb0-5f44-b500-4fed8824db08',position=[-225.5,112,279.5],new_once_only=True)],
                source_cannon_inventory_untouched=True,stock_commissioned=False),
                marine=dict(recovery=[1418.5,65,608.5],crew_wait_ports=[[1436.5,69,402.5],[1486.5,69,402.5]],original_ship_boarding_ports=[[1436.5,69,420.5],[1486.5,69,420.5]],model_scale_suggestion=.5,boss_centre=[1485,55.5,621],surface_y=63,all_yaw_turning_radius=26.2488094968,source_geometry_validated_not_native=True,original_cannon_UUIDs=['a2f5ffe8-278c-4fd2-8edd-2a4f378fca5f','4e33b3e4-051f-46de-8935-673c7afabe49'],original_power=[1330,69,474],original_cannons_must_not_fire_through_ships=True))
    (a.out/'r49_encounter_civil.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),'utf8')
    path=a.world/'r49_encounter_civil.json';before=json.loads(path.read_text('utf8'))if path.exists()else None
    (a.out/'metadata_patch.json').write_text(json.dumps(dict(schema=49,operations=[dict(relative_target='r49_encounter_civil.json',before=before,after=marker)],world_written=False),ensure_ascii=False,indent=2),'utf8')
    for p in a.out.glob('*/contract.json'):
        doc=json.loads(p.read_text('utf8'));doc['schema']='projectseele.r49.encounter-civil-candidate.v1';doc['authorization']='Root relayed current playable Yashima ridge and harbour facilities scope';p.write_text(json.dumps(doc,ensure_ascii=False,indent=2),'utf8')
    (a.out/'manifest.json').write_text(json.dumps(dict(schema=49,world=str(a.world),components=a.components,changed_cells=len(a.all),world_written=False,new_supply_stock_commissioned=False,original_city100_ships_people_inventory_unchanged=True,native_verified=False,visual_verified=False),ensure_ascii=False,indent=2),'utf8')
    print('R49 encounter civil candidate',len(a.all),'cells; no world/actor/inventory writes; new stock not yet commissioned')
if __name__=='__main__':main()
