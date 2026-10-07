"""R50 measured battle civil components. Candidates only; Root is the world writer."""
from pathlib import Path
import argparse, copy, gzip, json, math
import nbtlib
from prepare_facilities_r48 import Author, DIM
from query_blocks import AIR
from regional_voxels import canonical_state

ROOT = Path(__file__).resolve().parents[1]
NATURAL = AIR | {'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block',
    'minecraft:gravel', 'minecraft:sand', 'minecraft:clay', 'minecraft:deepslate',
    'minecraft:andesite', 'minecraft:diorite', 'minecraft:granite', 'minecraft:tuff',
    'minecraft:grass', 'minecraft:tall_grass', 'minecraft:oak_log', 'minecraft:oak_leaves',
    'minecraft:azalea', 'minecraft:flowering_azalea', 'minecraft:azalea_leaves', 'minecraft:flowering_azalea_leaves',
    'minecraft:birch_log', 'minecraft:birch_leaves', 'minecraft:water',
    'minecraft:seagrass', 'minecraft:tall_seagrass', 'minecraft:kelp', 'minecraft:kelp_plant'}
FLOOR = 'projectseele:nerv_floor_panel'
FRAME = 'projectseele:nerv_structural_panel'

def metadata(a, name, after):
    p = a.world/name
    before = json.loads(p.read_text('utf8')) if p.exists() else None
    (a.out/name).write_text(json.dumps(after, ensure_ascii=False, indent=2), 'utf8')
    return dict(relative_target=name, before=before, after=after)

def armor(a):
    a.read((25,19,351),(42,87,360)); desired = {}
    ranges = [(78,80),(70,72),(62,64),(54,56),(46,48),(38,40),(30,32),(20,24)]
    layers = [dict(id=f'upper_shell_{i+1:02d}',y_min=lo,y_max=hi,hit_points=1200,block=FRAME,
        sensor=[35,hi,355],plate_bounds=[[27,lo,352],[33,hi,358]])
        for i,(lo,hi) in enumerate(ranges)]
    plate_y = {y for lo,hi in ranges for y in range(lo,hi+1)}
    def put(p,state,reason):
        old = a.s[p]; name = old.split('[')[0]
        assert p not in a.t, ('Original device NBT is protected',p)
        assert name in NATURAL or (p[1] in (20,24) and name=='minecraft:iron_block') or (p[1] >= 79 and name in {
            'minecraft:black_concrete','minecraft:gray_concrete',
            'minecraft:light_gray_concrete','minecraft:polished_deepslate'}), (p,old)
        desired[p] = state,reason,None
    for x in range(26,35):
        for z in range(351,360):
            for y in range(20,81):
                edge = x in (26,34) or z in (351,359)
                state = FRAME if edge or y in plate_y else 'minecraft:air'
                put((x,y,z),state,'Explicit Lilith projection upper-shell armor column; eight full independent 7x7 plates and closed outer frame')
    # Enclosed manual inspection shaft east of the movable city owner and
    # independent from the beam aperture; its closed floor stops at Y25.
    for x in range(36,41):
        for z in range(352,359):
            for y in range(25,85):
                edge = x in (36,40) or z in (352,358) or y in (25,84)
                put((x,y,z),FRAME if edge else 'minecraft:air',
                    'Full enclosed personnel maintenance shaft, protected from the beam aperture; continuous support and no GF drop')
    for y in range(26,84):
        put((39,y,355),'minecraft:ladder[facing=west,waterlogged=false]',
            'Actual ladder attached to the complete east backing wall; no imaginary elevator')
    for layer in layers:
        y = layer['y_max']
        put((35,y,355),'projectseele:nerv_circuit_indicator[lit=false]',
            'Independent actual layer sensor with a continuous wall-backed conduit')
        if y>=26:
            for z in range(354,357):
                put((37,y-1,z),FLOOR,'Supported inspection shelf adjacent to the ladder; beam plate remains independent')
            layer['inspection_shelf'] = [[37,y-1,354],[37,y-1,356]]
    for y in range(25,81):
        put((35,y,356),'minecraft:black_concrete','Continuous enclosed layer-sensor electrical trunk')
    for y,half in [(81,'lower'),(82,'upper')]:
        put((38,y,358),f'projectseele:city_personnel_door[facing=south,half={half},hinge=right,open=false,powered=false]',
            'Real surface maintenance entrance with frame, continuous landing and independent manual latch')
    for x in range(37,40):
        for z in range(358,361):
            put((x,80,z),FLOOR,'Full three-wide surface maintenance landing joins the existing city pavement')
    put((39,81,359),'minecraft:stone_button[face=wall,facing=south,powered=false]',
        'Real surface repair command mounted on the closed maintenance wall; runtime owns exact authorized plates only')
    a.full_desired=desired
    a.emit('A01_lilith_projection_upper_shell',desired,dict(layers=layers,
        source_lilith_uuid='5102dc56-c4e4-4e74-b66b-79f70fde6ced',source_lilith=[30.5,-600,355.5],
        retained_below_y=19,original_GF_shell_iron_cells_explicitly_reconstructed=28,city100_owner34=[[21,331],[39,349]],
        after_breach='GeoFront cavity only; retained pyramid/hq and terminal rooms are not removed',
        full_lower_route_created=False,inspection_shaft=[[36,25,352],[40,84,358]]))
    marker = dict(schema=50,id='nerv_lilith_projection_upper_shell_r50',dimension=DIM,installed=False,world_written=False,
        surface=[30.5,80,355.5],layers=layers,hole_bounds=[[27,20,352],[33,80,358]],
        plate_block=FRAME,repair_control=[39,81,359],protected_below_y=19,geofront_entry_y=19,terminal_pos=[30.5,-600,355.5],
        terminal_uuid='5102dc56-c4e4-4e74-b66b-79f70fde6ced',
        first_boundary='upper_shell',breach_enters='geofront_cavity',
        hq_and_terminal_route_created=False,native_verified=False)
    return [metadata(a,'nerv_armor_column_r50.json',marker)]

def yashima(a, cover_y, hero_y):
    a.read((-95,72,435),(155,194,534)); desired={}; tops={}; road_columns={}; clear_to={}
    owners=json.loads((ROOT/'artifacts/rebuild_r49/encounter_facilities/west_ridge_survey.json').read_text('utf8'))['city100_owners']
    def owner(p):
        return any(o['sweep_xz'][0]<=p[0]<=o['sweep_xz'][1] and o['sweep_xz'][2]<=p[2]<=o['sweep_xz'][3] for o in owners)
    def put(p,state,reason,tag=None,hardware=False):
        assert not owner(p) and p not in a.t,('Original moving ownership or BE protected',p)
        old=a.s[p];name=old.split('[')[0]
        assert name in NATURAL or old==state or (hardware and p[1]==80 and name in {'minecraft:smooth_stone','minecraft:black_concrete','minecraft:white_concrete'}),(p,old,state)
        desired[p]=state,reason,tag
    for x in range(-90,151):
        for z in range(437,530):
            constructed=[(y,a.s[x,y,z])for y in range(72,195)if a.s[x,y,z].split('[')[0]not in NATURAL]
            if constructed:
                assert max(y for y,s in constructed)<100,('Fixed building rather than road fixture enters new ridge',x,z,constructed)
                road_columns[x,z]=constructed
                clear_to[x,z]=max(87,max(y for y,s in constructed)+3)
            ground=max((y for y in range(72,85)if a.s[x,y,z].split('[')[0]in {'minecraft:grass_block','minecraft:dirt','minecraft:stone'}),default=79)
            distance=max(0,abs(x-30)-25)/95
            shoulder=max(0,1-distance)
            # Two rounded rock/soil crests. The commissioned grey stance decks
            # have their own explicit supports; no rectangular soil box is
            # hidden underneath a grass skin.
            def lobe(centre,half,peak):
                f=max(0,1-abs(z-centre)/half)
                return (peak-ground)*f*f*(3-2*f)
            rise=max(lobe(458,21,cover_y-1),lobe(486,43,hero_y-1))
            top=math.floor(ground+rise*shoulder*shoulder*(3-2*shoulder))
            if abs(x-30)>26:top+=math.floor(.6*math.sin(x*.24+z*.3)+.5*math.sin(x*.47-z*.11))
            top=max(ground,top);tops[x,z]=top
            for y in range(ground+1,top+1):
                if y<=clear_to.get((x,z),-1000):continue
                state='minecraft:grass_block[snowy=false]'if y==top else 'minecraft:dirt'if y>=top-2 else 'minecraft:andesite'if (x*7+y*3+z)%29==0 else 'minecraft:stone'
                put((x,y,z),state,'Soil/rock south ridge with long east/west graded shoulders; existing streets retain their complete floor and six-high underpass')
    pad_boxes=[]
    for role,x0,x1,z0,z1,feet in [('hero',6,54,467,529,hero_y),('cover',20,40,450,466,cover_y)]:
        for x in range(x0,x1+1):
            for z in range(z0,z1+1):
                put((x,feet-2,z),FRAME,'Explicit reinforced stance-deck underside above the rounded natural ridge; not a grass-coated rock box')
                put((x,feet-1,z),FLOOR,'Complete actual EVA '+role+' stance crown, including the full prone shooter footprint')
                for y in range(feet,feet+61):
                    if a.s[x,y,z]not in AIR:put((x,y,z),'minecraft:air','Complete commissioned EVA body/head envelope clearance')
                    elif (x,y,z)in desired:desired[x,y,z]=('minecraft:air','Actual EVA '+role+' crown body clearance',None)
        pad_boxes.append(dict(role=role,box=[[x0,feet-1,z0],[x1,feet-1,z1]],feet=[30.5,feet,498.5 if role=='hero' else 458.5]))
        xs=range(x0,x1+1,12) if role=='hero' else (20,30,40)
        zs=(467,479,491,503,510) if role=='hero' else (452,464)
        for x in xs:
            for z in zs:
                for xx in range(x,min(x+2,x1+1)):
                    for zz in range(z,min(z+2,z1+1)):
                        assert (xx,zz)not in road_columns,('Stance support cannot block the retained road',xx,zz)
                        for y in range(tops[xx,zz]+1,feet-1):
                            put((xx,y,zz),FRAME,'Complete stance-deck pier rooted in its measured rounded ridge; original road and device volumes avoided')
                if role=='hero' and z==510:
                    for zz in range(511,530):
                        y=min(feet-2,feet-20+(zz-511))
                        for yy in range(y,min(y+2,feet-1)):
                            put((x,yy,zz),FRAME,'Two-thick face-connected rear-deck bracket bridges the original southern street above its complete headroom')
    # Standing EVA approach: 20-wide, one-block rise per two metres, 61-high.
    ramp=[]
    for x in range(-86,7):
        floor_y=79+math.floor((x+86)*(hero_y-1-79)/92)
        for z in range(488,508):
            put((x,floor_y-1,z),FRAME,'Whole broad EVA ramp reinforced underside; natural ridge remains visible below the engineered approach')
            put((x,floor_y,z),FLOOR,'Twenty-wide EVA access ramp; rise never exceeds one block per cell')
            for y in range(floor_y+1,floor_y+62):
                put((x,y,z),'minecraft:air','Full standing EVA approach body envelope; crew stairs are separate')
        ramp.append([x+.5,floor_y+1,498.5])
        if (x+86)%10==0:
            for z in (489,506):
                for y in range(tops[x,z]+1,floor_y):put((x,y,z),FRAME,'Real broad EVA approach piers to the rounded natural bearing ridge')
    # Rear side equipment apron, separate from the shooter bounding footprint.
    for x in range(55,73):
        for z in range(482,514):
            put((x,hero_y-2,z),FRAME,'Explicit service apron deck underside; existing original street remains unobstructed below')
            put((x,hero_y-1,z),FLOOR,'Real eastern service apron outside the shooter/prone footprint')
            for y in range(hero_y,hero_y+61):put((x,y,z),'minecraft:air','Complete service apron crew and42-high physical stock-station clearance')
            if x in (56,64,72) and z in (484,496,508):
                assert (x,z)not in road_columns
                for y in range(tops[x,z]+1,hero_y-2):put((x,y,z),FRAME,'Actual service-apron pier to surveyed rounded rock ridge')
    a.read((-12,81,3),(-12,81,3));prototype=a.t[-12,81,3]
    pylons=[];switches=[];buttons=[]
    for z in (500,505,510):
        for y in range(hero_y,hero_y+12):put((57,y,z),'minecraft:iron_block','Full powered socket mast on the actual equipment apron')
        p=(57,hero_y+12,z);tag=copy.deepcopy(prototype)
        for k,v in zip(('x','y','z'),p):tag[k]=nbtlib.Int(v)
        put(p,'projectseele:umbilical_pylon','Complete native power-pylon BE factory state and coordinates',tag);pylons.append(list(p))
        p=(56,hero_y+1,z);put(p,'minecraft:lever[face=wall,facing=west,powered=false]','Independent actual live grid switch on its original authored mast');switches.append(list(p))
    for z,role in [(502,'coolant'),(508,'reload')]:
        put((58,hero_y,z),'minecraft:iron_block','Actual crew console backing separate from supply actor inventory')
        p=(57,hero_y,z);put(p,'minecraft:stone_button[face=wall,facing=west,powered=false]','Actual '+role+' crew console button');buttons.append(dict(role=role,pos=list(p)))
    for z in range(499,512):put((58,hero_y,z),'minecraft:black_concrete','Continuous protected grid cable trunk joining the three real sockets clear of the shield entry ramp')
    # A rising east branch leaves the shooter's whole prone footprint clear.
    # Shield enters first, obtains the physical item on the crown, then climbs
    # this genuine six-metre interface to the side waiting/centre brace deck.
    side_floors={}
    def deck(x,z,floor_y,reason):
        put((x,floor_y-1,z),FRAME,'Complete side-interface reinforced bearing deck: '+reason)
        put((x,floor_y,z),FLOOR,reason);side_floors[x,z]=floor_y
        if floor_y>hero_y-1:
            for y in range(hero_y-2,floor_y-1):
                if desired.get((x,y,z),(None,))[0]in {FLOOR,FRAME}:
                    put((x,y,z),'minecraft:air','Retire the superseded empty lower apron skin below the new actual side ramp')
        for y in range(floor_y+1,floor_y+62):put((x,y,z),'minecraft:air','Full17-wide standing body and25-wide held-shield side-interface clearance')
    for x in range(55,77):
        floor_y=hero_y-1+math.floor((x-55)*(cover_y-hero_y)/21)
        for z in range(469,490):deck(x,z,floor_y,'Twenty-one-wide actual eastward shield climb, maximum one-block rise per cell')
    for x in range(77,95):
        for z in range(448,490):deck(x,z,cover_y-1,'Continuous supported upper east return for the actual shield route')
    for x in range(20,95):
        for z in range(448,467):deck(x,z,cover_y-1,'Same-height complete centre/side shield footing and actual lateral waiting-to-brace traverse')
    # Full permanentREADY surface supply racks occupy31x31 and11x11,
    # respectively. Their proper footprint is isolated from both live EVAs,
    # all power masts and the two approach lanes, without an underground shaft.
    for x in range(95,130):
        for z in range(446,530):deck(x,z,cover_y-1,'Whole surfaceREADY armament-stock deck and actual seventeen-wide operating apron, inside the160m mission admission envelope')
    for x,z in[(56,470),(56,487),(66,470),(66,487),(76,470),(76,487),(83,450),(83,463),(83,477),(92,450),(92,463),(92,477),(46,450),(46,464),(59,450),(59,464)]:
        assert (x,z)not in road_columns
        floor_y=side_floors[x,z]
        for y in range(tops[x,z]+1,floor_y-1):put((x,y,z),FRAME,'Actual shield-side interface pier to the measured rounded rock/soil ridge')
    for x in(98,110,123,128):
        for z in(451,463,475,487,499,511,523):
            if (x,z)in road_columns:continue
            for y in range(tops[x,z]+1,cover_y-2):put((x,y,z),FRAME,'Complete surface supply deck pier to actual rounded bearing soil; preserved street/fixtures are not used as an obstructed footing')
    def standing_feet(px,pz):
        # Arrival tests use the actual seventeen-wide native sole. A centre
        # floor alone is lower than the leading sole on a ramp and stalls AI.
        highest=71
        for x in range(math.floor(px-8.5+1e-7),math.ceil(px+8.5-1e-7)):
            for z in range(math.floor(pz-8.5+1e-7),math.ceil(pz+8.5-1e-7)):
                for y in range(72,cover_y+16):
                    state=desired.get((x,y,z),(a.s.get((x,y,z),'minecraft:air'),))[0]
                    name=state.split('[')[0]
                    if name not in AIR|{'minecraft:water','projectseele:lcl','minecraft:grass','minecraft:tall_grass','minecraft:lever','minecraft:stone_button','minecraft:light'}:
                        highest=max(highest,y)
        return highest+1
    def sampled_route(keys):
        result=[list(keys[0])]
        for first,last in zip(keys,keys[1:]):
            steps=max(1,math.ceil(math.hypot(last[0]-first[0],last[2]-first[2])/2))
            for n in range(1,steps+1):
                t=n/steps;x=first[0]+(last[0]-first[0])*t;z=first[2]+(last[2]-first[2])*t
                result.append([x,standing_feet(x,z),z])
        return result
    ramp=[[p[0],standing_feet(p[0],p[2]),p[2]]for p in ramp]
    extension=sampled_route([[6.5,hero_y,498.5],[6.5,hero_y,480.5],[47.5,hero_y,480.5],[83.5,cover_y,480.5],[112.5,cover_y,478.5]])
    supply_route=ramp+extension[1:]
    side_route=sampled_route([[112.5,cover_y,478.5],[83.5,cover_y,478.5],[83.5,cover_y,458.5],[48.5,cover_y,458.5]])
    shooter_route=sampled_route([[112.5,cover_y,472.5],[83.5,cover_y,472.5],[83.5,cover_y,480.5],[47.5,hero_y,480.5],[30.5,hero_y,480.5],[30.5,hero_y,498.5]])
    assert all(math.dist(first,last)<=8 and abs(first[1]-last[1])<=1.6 for first,last in zip(supply_route,supply_route[1:])),('Inconsistent full-body access feet',supply_route)
    assert all(math.dist(first,last)<=8 and abs(first[1]-last[1])<=1.6 for first,last in zip(side_route,side_route[1:])),('Inconsistent exact shield route feet',side_route)
    stairs=[]
    rise=hero_y-1-80
    for n in range(rise+3):
        y=80+max(0,min(rise,n-1));z=528-n
        orient='landing_bottom'if n==0 else'transition_bottom'if n==1 else'slope'if n<=rise else'transition_top'if n==rise+1 else'landing_top'
        for base,flag in [(66,True),(70,False)]:
            for lane in (0,1):
                x=base+lane;side='left'if lane==0 else'right'
                for yy in range(88,y):put((x,yy,z),'minecraft:stone','Native crew escalator continuous rock bearing above street clearance')
                put((x,y,z),f'mtr:escalator_step[direction={str(flag).lower()},facing=north,orientation={orient},side={side},status=true]','Complete paired native crew escalator lane; original bottom approach is explicitly remodeled',hardware=True)
                for yy in range(y+1,y+5):put((x,yy,z),'minecraft:air','Complete real crew stair headroom')
                put((x,y+1,z),f'mtr:escalator_side[facing=north,orientation={orient},side={side}]','Native matched complete escalator side')
        x=68
        put((x,y,z),f'minecraft:polished_andesite_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]'if 2<=n<=rise+1 else FLOOR,'Actual supported manual crew stair between the fast lanes',hardware=True)
        for yy in range(y+1,y+5):put((x,yy,z),'minecraft:air','Manual crew stair complete headroom')
        stairs.append([x+.5,y+1,z+.5])
    # Vegetation belongs on the gentler shoulders, outside all firing and walk volumes.
    for x,z in [(-72,461),(-65,515),(-49,477),(-24,455),(101,461),(125,482),(130,513),(108,520)]:
        y=tops[x,z]
        if (x,z)in road_columns:continue
        for yy in range(y+1,y+6):put((x,yy,z),'minecraft:oak_log[axis=y]','Original planted shoulder vegetation, outside the approach and muzzle cone')
        for xx in range(x-2,x+3):
            for zz in range(z-2,z+3):
                for yy in range(y+4,y+7):
                    if xx==x and zz==z and yy<y+6:continue
                    put((xx,yy,zz),'minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]','Complete supported original shoulder tree canopy')
    controls=dict(grid_switches=switches,power_pylons=pylons,console_buttons=buttons,
        supply_racks=[dict(unit=0,uuid='e9fd32e9-b3a3-5dc6-8d9f-21ce267a848e',cargo_uuid='3ea20e4d-37bf-5c8c-90b6-26316d2b4911',position=[112.5,cover_y,502.5],new_once_only=True,surface_READY_forever=True,outer_width=31,payload_height=52,native_height=54,footprint=[[97,cover_y-1,487],[128,cover_y-1,518]],yaw=180),dict(unit=1,uuid='749cf141-0e2f-59ef-9e9b-d08346d5ea8d',cargo_uuid='58eab304-0fb0-5f44-b500-4fed8824db08',position=[112.5,cover_y,452.5],new_once_only=True,surface_READY_forever=True,outer_width=11,payload_height=42,native_height=44,footprint=[[107,cover_y-1,447],[118,cover_y-1,458]],yaw=0)],
        equipment_approach=[dict(unit=0,position=[112.5,cover_y,478.5],original_native_pickup_range=24),dict(unit=1,position=[112.5,cover_y,472.5],original_native_pickup_range=24)],
        recovery_storage=[dict(unit=0,position=[8,-441,-240]),dict(unit=1,position=[10,-441,-240])],stock_commissioned=False)
    marker=dict(schema=50,dimension=DIM,installed=False,hero=[30.5,hero_y,498.5],cover=[30.5,cover_y,458.5],angel=[30.5,144,355.5],yaw=180,
        pad_boxes=pad_boxes,yashima_controls=controls,eva_access_ramp=ramp,max_rise_per_cell=1,ramp_width=20,ramp_clearance_height=61,
        eva_supply_access_route=supply_route,
        cover_access_ramp=side_route,cover_access_width=21,cover_access_rise=cover_y-hero_y,
        cover_after_supply_route=side_route,
        equipment_approach={'0':[112.5,standing_feet(112.5,478.5),478.5],'1':[112.5,standing_feet(112.5,472.5),472.5]},route_arrival_radius=.9,
        stock_native_pickup_range=24,old_NPC21_was_not_station_native_range=True,
        cannon_after_supply_route=shooter_route,
        surface_supply_deck=[[95,cover_y-2,446],[129,cover_y-1,529]],
        waypoint_feet_source='Highest full17x17 native solid sole, not centre-only surface; collision movement remains native-unverified',
        shield_wait_port=[48.5,cover_y,458.5],shield_brace_port=[30.5,cover_y,458.5],
        shield_activity_clearance=[[18,cover_y,443],[62,cover_y+61,466]],
        shield_side_requires_original_walking_route=True,shield_small_crown_not_airlift_ready=True,
        sequential_arrival=[0,1],shield_route_claimed_native_passed=False,
        manual_crew_stair=stairs,all_original_city100_owners_untouched=True,world_written=False,native_verified=False,visual_verified=False,
        northern_crown='Two rounded natural crests and all-direction graded rock/soil slopes; explicit grey engineering decks and piers are separate from the natural mountain',
        full_natural_rock_boxes_under_decks=False,deck_supports_explicit=True,
        shield_height_requires_root_actual_mesh_check=True,requires_retracted_city=True)
    a.full_desired=desired
    a.emit('Y01_south_ridge_power_and_access',desired,marker)
    return [metadata(a,'r50_yashima_civil.json',marker)]

def marine(a):
    a.read((1508,14,564),(1752,85,804)); desired={}; changed_estimate=0
    def put(p,state,reason,tag=None,port=False):
        assert p not in a.t,('Original complete marine device protected',p)
        old=a.s[p];name=old.split('[')[0]
        if name not in NATURAL:
            if port and name in {'minecraft:gray_concrete','minecraft:smooth_stone',FLOOR}:
                state=old
            else:
                assert port and name=='projectseele:nerv_edge_rail',('Original marine constructed component protected',p,old)
        desired[p]=state,reason,tag
    old_bed={};old_surface={}
    for (x,y,z),s in a.s.items():
        if (x-1630)**2+(z-685)**2>118**2:continue
        name=s.split('[')[0]
        assert name in NATURAL,('Dense measured basin includes construction',x,y,z,s)
        if name=='minecraft:water':old_surface[x,z]=max(old_surface.get((x,z),-1),y)
        elif name not in AIR|{'minecraft:seagrass','minecraft:tall_seagrass','minecraft:kelp','minecraft:kelp_plant'}:
            old_bed[x,z]=max(old_bed.get((x,z),-1),y)
    seabed_profile={}
    for x in range(1512,1749):
        for z in range(567,804):
            r=math.hypot(x-1630,z-685)
            if r>118:continue
            assert old_surface[x,z]==62
            original=old_bed[x,z]
            t=max(0,min(1,(r-105)/13));fade=t*t*(3-2*t)
            bed=math.floor(16+(original-16)*fade)
            seabed_profile[x,z]=bed
            for y in range(bed+1,63):
                put((x,y,z),'minecraft:water[level=0]',
                    'Complete separately commissioned deep naval turning basin; original natural seabed only, with graded transition and full jaw attack clearance')
            put((x,bed,z),'minecraft:gravel','Measured natural deep-basin bearing bed, below complete mouth attack sweep')
            if r<=105:
                for y in range(63,86):
                    put((x,y,z),'minecraft:air','Complete dorsal/attack airborne envelope above the water; explicitly retained in future generation')
    # Full original quay tail and the commissioned boardwalk/recovery footprint.
    a.read((1406,25,580),(1428,129,791))
    a.read((1426,25,766),(1540,129,792))
    a.read((1500,25,752),(1548,129,790))
    walkway=set()
    for z in range(588,775):
        for x in range(1415,1422):walkway.add((x,z))
    for x in range(1415,1521):
        for z in range(768,775):walkway.add((x,z))
    pad={(x,z)for x in range(1504,1535)for z in range(756,787)}
    operator_apron={(x,z)for x in range(1535,1547)for z in range(756,781)}
    surface=walkway|pad|operator_apron;piles=[]
    for x,z in sorted(surface):
        put((x,63,z),FRAME,'Complete supported offshore recovery/crew walkway underside; original quay structure retained',port=True)
        put((x,64,z),FLOOR,'Continuous actual marine crew/recovery floor at foot65; original quay floor retained',port=True)
        for y in range(65,126):
            if (x,z)in pad or y<=68:
                put((x,y,z),'minecraft:air','Whole recovery body/head envelope or full seven-wide crew headroom; measured natural vegetation removed completely from this aperture',port=True)
        # Only the real seven-wide tail port loses its old south-facing rail.
        if z==588:
            put((x,65,z),'minecraft:air','Complete explicitly commissioned old quay-tail boarding aperture; original rail-state inverse retained',port=True)
    for x,z in sorted(surface):
        if any((x+dx,z+dz)not in surface for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]):
            if z==588:continue
            flags=dict(east=(x+1,z)not in surface,west=(x-1,z)not in surface,
                north=(x,z-1)not in surface,south=(x,z+1)not in surface)
            state='projectseele:nerv_edge_rail['+','.join(f'{k}={str(flags[k]).lower()}'for k in sorted(flags))+']'
            put((x,65,z),state,'Complete full perimeter protection; actual original quay port and new seven-wide link remain open',port=True)
    pile_centres=[(1418,z)for z in range(596,774,16)]+[(x,771)for x in range(1434,1505,16)]+[(x,z)for x in(1506,1519,1532)for z in(758,771,784)]+[(x,z)for x in(1538,1544)for z in(758,770,778)]
    for x,z in pile_centres:
        levels=[y for y in range(25,63)if a.s[x,y,z].split('[')[0]in {'minecraft:stone','minecraft:gravel','minecraft:sand','minecraft:dirt','minecraft:clay','minecraft:deepslate','minecraft:andesite','minecraft:diorite'}]
        assert levels,('No measured pile bearing',x,z)
        bed=seabed_profile.get((x,z),max(levels))
        for y in range(bed+1,64):put((x,y,z),FRAME,'Full boardwalk pile bears on measured native seabed; no unsupported offshore platform',port=True)
        piles.append(dict(pos=[x,bed,z],top_y=63))
    # Complete native fast walking directions in the separate western crew link.
    for z in range(592,763):
        for base,flag in [(1415,False),(1419,True)]:
            for lane in (0,1):
                p=(base+lane,64,z);side='left'if lane==0 else'right'
                put(p,f'mtr:escalator_step[direction={str(flag).lower()},facing=north,orientation=flat,side={side},status=true]',
                    'Two native paired marine crew moving walks, with the central manual lane and stationary corner buffers retained')
    a.read((-12,81,3),(-12,81,3));prototype=a.t[-12,81,3]
    for y in(65,66):put((1542,y,758),'minecraft:iron_block','Real supported marine umbilical socket pedestal outside the entire recovery/airlift crown')
    p=(1542,67,758);tag=copy.deepcopy(prototype)
    for k,v in zip(('x','y','z'),p):tag[k]=nbtlib.Int(v)
    put(p,'projectseele:umbilical_pylon','Actual native offshore umbilical socket, within existing132m configured lead range',tag)
    power=(1541,66,774);cannons=[(1541,65,770),(1541,65,772)]
    for z in(770,772,774):
        for y in(65,66):put((1542,y,z),'minecraft:iron_block','Actual mission console backing on independent operator apron outside17/29-wide recovery sweeps, separated from original gun inventories')
    put(power,'minecraft:lever[face=wall,facing=west,powered=false]','Actual naval grid switch controlling the native campaign external supply')
    for p in cannons:put(p,'minecraft:stone_button[face=wall,facing=west,powered=false]','Separate real command button for each retained original cannon identity')
    for z in range(758,775):put((1543,65,z),'minecraft:black_concrete','Continuous protected naval grid trunk on independent operator apron outside the entire recovery crown')
    for x in range(1542,1544):put((x,65,758),'minecraft:black_concrete','Continuous protected electrical branch to actual offshore umbilical socket')
    # Native walking/descent continues from the flat landing crown. Higher
    # ramp cells stay outside the complete101.55m fish sweep; it reaches the
    # flat16 seabed before the NPC walks inward toward the cannon-facing jaw.
    a.read((1504,14,695),(1530,129,759))
    underwater=[]
    for z in range(755,699,-1):
        floor_y=64-math.floor((755-z)*48/55)
        for x in range(1505,1528):
            if floor_y>16:assert math.hypot(1528-1630,z-685)>math.hypot(32,64)+30
            bearing=seabed_profile.get((x,z))
            if bearing is None:
                bearing=max(y for y in range(14,63)if a.s[x,y,z].split('[')[0]in {'minecraft:stone','minecraft:dirt','minecraft:gravel','minecraft:sand','minecraft:clay','minecraft:deepslate','minecraft:andesite','minecraft:diorite'})
            for y in range(bearing+1,floor_y):put((x,y,z),FRAME,'Actual whole23-wide underwater access ramp bearing above its measured post-dredge bed')
            put((x,floor_y,z),FLOOR,'Full-width actual naval EVA descending tread; maximum one-block drop per metre, never inside higher fish sweep')
            for y in range(floor_y+1,63):put((x,y,z),'minecraft:water[level=0]','Whole23-wide descent and submersion clearance; old natural seabed alone is excavated')
            for y in range(max(63,floor_y+1),floor_y+62):put((x,y,z),'minecraft:air','Actual above-water head clearance of the underwater entry route')
        underwater.append([1516.5,floor_y+1,z+.5])
    for x in range(1505,1528):put((x,65,756),'minecraft:air','Explicit23-wide original new-crown north gate into the real EVA descent; no rail through its body')
    underwater=[[1519.5,65,771.5],[1516.5,65,771.5],[1516.5,65,764.5],[1516.5,65,758.5]]+underwater
    a.read((1504,14,672),(1569,85,701))
    flat_cells={(x,z)for x in range(1505,1528)for z in range(674,701)}|{(x,z)for x in range(1516,1569)for z in range(674,698)}
    for x,z in sorted(flat_cells):
        put((x,16,z),FLOOR,'Whole23-wide flat naval entry/turn apron continues the descending ramp into the complete16 bed')
        for y in range(17,63):put((x,y,z),'minecraft:water[level=0]','Actual whole-body underwater turn clearance, including measured natural shoulder cells outside the round basin')
        for y in range(63,86):put((x,y,z),'minecraft:air','Whole real underwater EVA standing/head volume over the entry turn remains clear')
    route_keys=[[1516.5,17,700.5],[1516.5,17,685.5],[1556.5,17,685.5],[1605,17,643]]
    for start,end in zip(route_keys,route_keys[1:]):
        steps=math.ceil(math.dist(start,end)/4)
        for n in range(1,steps+1):
            t=n/steps;p=[start[i]+(end[i]-start[i])*t for i in range(3)]
            underwater.append(p)
    # A second real socket keeps the cannon-facing grapple within the retained
    # native132m lead, instead of silently extending the balance constant.
    a.read((1511,25,636),(1519,72,644));nw_bearing=[]
    for x in range(1513,1518):
        for z in range(638,643):
            put((x,63,z),FRAME,'Complete northwestern power-service apron underside outside every fish pose')
            put((x,64,z),FLOOR,'Real supported northwestern external-power service footing')
            if x in(1513,1517)or z in(638,642):
                put((x,65,z),'projectseele:nerv_edge_rail[east='+str(x==1517).lower()+',north='+str(z==638).lower()+',south='+str(z==642).lower()+',west='+str(x==1513).lower()+']','Complete small-service-pier edge protection')
    for x,z in[(1514,639),(1516,641)]:
        bed=max(y for y in range(25,63)if a.s[x,y,z].split('[')[0]in {'minecraft:stone','minecraft:gravel','minecraft:sand','minecraft:dirt','minecraft:clay','minecraft:deepslate','minecraft:andesite','minecraft:diorite'})
        for y in range(bed+1,64):put((x,y,z),FRAME,'Complete NW external-power pier bears on actual unchanged seabed, outside the dredge boundary')
        nw_bearing.append(dict(pos=[x,bed,z],top_y=63))
    put((1515,65,640),'minecraft:iron_block','Actual NW marine socket backing on its supported sea pier')
    p=(1515,66,640);tag=copy.deepcopy(prototype)
    for k,v in zip(('x','y','z'),p):tag[k]=nbtlib.Int(v)
    put(p,'projectseele:umbilical_pylon','Complete native NW power socket for the actual cannon-facing underwater melee route',tag)
    # Buried trunk does not become a solid collision obstruction in the fish's
    # water envelope. It is the game's coarse protected cable route.
    a.read((1515,14,640),(1516,16,756))
    for z in range(640,757):put((1515,15,z),'minecraft:black_concrete','Buried protected naval feeder beneath the actual swept water/collision volume')
    def naval_feet(px,pz):
        highest=13
        for x in range(math.floor(px-8.5+1e-7),math.ceil(px+8.5-1e-7)):
            for z in range(math.floor(pz-8.5+1e-7),math.ceil(pz+8.5-1e-7)):
                for y in range(14,68):
                    state=desired.get((x,y,z),(a.s.get((x,y,z),'minecraft:air'),))[0]
                    name=state.split('[')[0]
                    if name not in AIR|{'minecraft:water','minecraft:seagrass','minecraft:tall_seagrass','minecraft:kelp','minecraft:kelp_plant','minecraft:grass','minecraft:tall_grass','minecraft:lever','minecraft:stone_button'}:
                        highest=max(highest,y)
        return highest+1
    underwater=[[p[0],naval_feet(p[0],p[2]),p[2]]for p in underwater]
    assert all(desired.get((x,y,z),(a.s[x,y,z],))[0]in AIR for x in range(1505,1534)for y in range(65,126)for z in range(757,786)), 'Recovery29x29 body/airlift sweep must remain air after all hardware and route construction'
    marker=dict(schema=50,id='tv_marine_deep_basin_r50',dimension=DIM,installed=False,
        geometry_validated=True,model_ready=True,spawn=[1630,42,685],arena_center=[1630,42,685],
        radius_x=30,radius_z=30,seabed_y=16,water_y=63,model_scale=1,yaw=180,
        model_local_bounds=[[-32,-24,-45],[32,26,64]],idle_local_bounds=[[-32,-13,-45],[32,26,64]],
        swept_horizontal_radius=math.hypot(32,64)+30,inner_basin_radius=105,outer_basin_radius=118,
        power_block=[1330,69,474],power_control=list(power),cannon_controls=[list(p)for p in cannons],
        new_umbilical_pylon=[1542,67,758],escape_point=[1519.5,65,771.5],recovery=[1519.5,65,771.5],
        new_umbilical_pylons=[[1542,67,758],[1515,66,640]],
        eva_underwater_route=dict(installed=False,width=23,waypoints=underwater,max_drop_per_cell=1,
            initial_flat_recovery_kept=True,higher_ramp_excludes_full_fish_sweep=True,
            northwest_base_goal=[1605,17,643],native_verified=False),
        nw_power_service=dict(pylon=[1515,66,640],bearing=nw_bearing,source_native_cable_range_retained=132),
        cargo_health=100,deadline_ticks=12000,all_original_ship_identities_inventory_and_components_untouched=True,
        original_cannon_UUIDs=['a2f5ffe8-278c-4fd2-8edd-2a4f378fca5f','4e33b3e4-051f-46de-8935-673c7afabe49'],
        original_cannon_positions=[[1420.5,65,350.5],[1471.5,65,392.5]],
        cannon_ray_native_verified=False,geometry_validation_source='Dense actual FULL world natural-only basin, complete all-yaw raw bbox plus30 root sweep and jaw localY-24; native water/entity test remains required',
        native_verified=False,visual_verified=False,world_written=False,
        dorsal_fin_may_emerge=True,whole_body_height_required_underwater=False,
        crew_route=dict(from_quay=[1418.5,65,588.5],corner=[1418.5,65,771.5],to_recovery=[1519.5,65,771.5],width=7,manual_lane=1,native_fast_lanes=2),
        eva_arrival_requires_existing_airlift=True,quay_original_width_less_than_EVA_width=True,
        recovery_pad=[[1504,63,756],[1534,64,786]],operator_apron=[[1535,63,756],[1546,64,780]],
        recovery_29x29_body_clearance=[[1505,65,757],[1533,125,785]],measured_piles=piles)
    a.full_desired=desired
    a.emit('M01_full_scale_basin_and_recovery',desired,marker)
    return [metadata(a,'tv_marine_site_r50.json',marker)]

def recovery_storage(a):
    a.read((7,-444,-242),(11,-438,-238));desired={};ports=[]
    for unit,x,face in [(0,8,'east'),(1,10,'west')]:
        p=(x,-441,-240)
        assert a.s[p]=='projectseele:nerv_shaft_panel' and p not in a.t
        assert a.s[x,-442,-240]==FLOOR
        assert a.s[9,-443,-240]==FLOOR and all(a.s[9,y,-240]in AIR for y in(-442,-441,-440))
        tag=nbtlib.Compound({'id':nbtlib.String('minecraft:barrel'),
            'x':nbtlib.Int(x),'y':nbtlib.Int(-441),'z':nbtlib.Int(-240),
            'Items':nbtlib.List[nbtlib.Compound]([]),
            'CustomName':nbtlib.String(json.dumps({'text':('零号机' if unit==0 else '初号机')+' · 屋岛装备回收入库'},ensure_ascii=False))})
        desired[p]=(f'minecraft:barrel[facing={face},open=false]',
            'Empty full-cube receiving cabinet recessed into the actual fixed sealed wet-bay wall; its face uses the original dry maintenance gap, outside the carrier sweep',tag)
        ports.append(dict(unit=unit,position=list(p),facing=face,slots=27,
            initially_empty=True,operation_layer_y=-442,crew_stand_candidate=[9.5,-442,-239.5],
            personnel_route_to_local_dry_gap_verified=False,
            original_parked_eva=[-11.5 if unit==0 else 30.5,-442,-239.5],
            horizontal_reach=19.5 if unit==0 else 20.5,
            fixed_side_wall_retains_full_cube_LCL_seal=True,
            original_machine_edge_frames_and_29_wide_carrier_sweep_untouched=True))
    a.full_desired=desired
    a.emit('Y02_actual_bay_recovery_storage',desired,dict(recovery_storage=ports,
        full_old_states_and_NBT=True,empty_native_containers_only=True,
        new_weapon_items_spawned=False,actual_original_EVA_identity_and_weapon_custody_untouched=True,
        purpose='Root-authorized automatic conserved stock receiving ports beside the parked original units'))
    return [metadata(a,'r50_yashima_recovery_storage.json',dict(schema=50,dimension=DIM,
        installed=False,recovery_storage=ports,world_written=False,native_verified=False))]

def complete_recipe(a):
    changed=a.all;complete={}
    for p,(state,reason,tag) in a.full_desired.items():
        old=a.t.get(p)
        complete[p]=dict(pos=list(p),before=a.s[p],after=canonical_state(state),
            before_nbt=None if old is None else old.snbt(),after_nbt=None if tag is None else tag.snbt(),
            owner='r50_complete_generation',reason=reason)
    with gzip.open(a.out/'complete_generation_source.jsonl.gz','wt',encoding='utf8')as f:
        for p,row in sorted(complete.items()):f.write(json.dumps(row,ensure_ascii=False)+'\n')
    a.all=complete;a.recipe();a.all=changed
    p=a.out/'generation_recipe/file_patch.json';d=json.loads(p.read_text('utf8'))
    d['complete_desired_cells']=len(complete);d['actual_world_changed_cells']=len(changed)
    d['includes_unchanged_declared_air_water_body_clearance']=True
    p.write_text(json.dumps(d,indent=2),'utf8')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--component',choices=['armor','yashima','marine','recovery_storage'],required=True)
    ap.add_argument('--cover-y',type=int,default=110)
    ap.add_argument('--hero-y',type=int,default=104)
    args = ap.parse_args(); a = Author(args.world.resolve(),args.out.resolve())
    a.out.mkdir(parents=True,exist_ok=True)
    operations = armor(a) if args.component=='armor' else yashima(a,args.cover_y,args.hero_y) if args.component=='yashima' else marine(a) if args.component=='marine' else recovery_storage(a)
    complete_recipe(a)
    for path in a.out.glob('*/contract.json'):
        d = json.loads(path.read_text('utf8'))
        d.update(schema='projectseele.r50.battle-civil-candidate.v1',
            authorization='Root-relayed user R50 playable battle civil facilities and Lilith projection upper-shell armor')
        path.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')
    (a.out/'metadata_patch.json').write_text(json.dumps(dict(schema=50,
        operations=operations,world_written=False),ensure_ascii=False,indent=2),'utf8')
    (a.out/'manifest.json').write_text(json.dumps(dict(schema=50,source_world=str(a.world),
        components=a.components,changed_cells=len(a.all),world_written=False,
        complete_states_NBT_and_inverse=True,native_verified=False,visual_verified=False,
        player_entity_inventory_city_motion_and_traffic_progress_untouched=True),ensure_ascii=False,indent=2),'utf8')
    print('R50 candidate',args.component,len(a.all),'cells; no world writes')

if __name__ == '__main__': main()
