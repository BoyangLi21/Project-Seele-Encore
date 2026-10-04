"""Full school campus R45 candidate. Read-only Minecraft source; no apply mode.

Existing classroom bars, three storeys, links, stairs, roof and gym are reused.
All rooms receive a stated use; the complete 25x10 pool has real water, shallow
end, steps, ladders, deck, guard, changing/shower rooms and founded approach.
All metre choices and school-room assignments are engineering adaptation.
"""
from pathlib import Path
import argparse
import json
import shutil

from school_hakone_patch_r45 import Candidate, ROOT, ART

BASE=ROOT/'artifacts/rebuild_r44/city_expansion/tv_school_connected_current_tokyo_campus_v22'


def room_contents(c,r,kind):
    x,y,z,X,Y,Z=r['bounds'];f=y-1
    c.fill((x,y,z,X,Y,Z),'minecraft:air','Retire generic repeated school workbenches before entire authored '+kind+' interior')
    c.fill((x,f,z,X,f,Z),'minecraft:oak_planks' if kind not in ['toilets','science','home_economics','infirmary'] else 'minecraft:light_gray_concrete','Entire occupied school room floor appropriate to '+kind)
    c.sign((x+1,y+1,Z+2),[r['label'],kind.replace('_',' ')],'south')
    # South-edge circulation remains clear along the entire room width.
    doorway=x+4
    c.path(r['label']+'/complete_room_aisle',[[doorway+.5,y,Z+2.5],[doorway+.5,y,Z+.5],[x+1.5,y,Z+.5],[X-.5,y,Z+.5]],door=[doorway,y,Z+1])
    if kind in ['classroom','science','music','art']:
        c.fill((x+1,y+1,z,x+min(8,X-x-1),y+2,z),'minecraft:green_terracotta','Original classroom chalkboard at real front wall')
        c.fixture((X-1,y,z+1),'cafe_table','教員机')
        c.fixture((x,y+2,z+2),'wall_clock','教室時計',facing='east')
        for xx in range(x+1,X-1,2):
            for zz in [z+1,z+3,z+5]:
                if zz+1>=Z:continue
                c.fixture((xx,y,zz),'cafe_table','生徒机')
                c.put((xx,y,zz+1),'projectseele:residential_chair[facing=north]','Human-scale original school chair facing the real board')
        if kind=='science':
            for basin_ordinal,_ in enumerate(range(x+2,X-1,4)):
                c.put((X,y,z+2+basin_ordinal),'minecraft:water_cauldron[level=3]','Whole right-wall experiment rinse line, with continuous X-1 operation corridor and connected desk aisles')
        if kind=='music':
            for xx in range(x+1,min(X,x+7)):
                c.put((xx,y,z+1),'minecraft:note_block[instrument=harp,note=0,powered=false]','Original playable music-room percussion bench; no official audio')
        if kind=='art':
            c.fill((X,y,z+1,X,y+1,z+4),'minecraft:bookshelf','Art room grounded storage shelving')
    elif kind=='staff_office':
        for xx in range(x+2,X-1,3):
            for zz in [z+2,z+5]:
                c.fixture((xx,y,zz),'cafe_table','職員机')
                c.put((xx,y,zz+1),'projectseele:residential_chair[facing=north]','Original staff seating with continuous south aisle')
        c.fill((X,y,z,X,y+1,z+4),'minecraft:bookshelf','Staffroom records and textbook shelves')
        c.fixture((x,y,z+1),'notice_board','職員室',['校務連絡','避難経路は南側廊下へ'],facing='east')
    elif kind=='infirmary':
        for xx in [x+1,x+5,X-1]:
            c.bed((xx,y,z+3))
        c.fixture((X,y,z+1),'cafe_counter','保健室収納')
        c.put((x,y,z),'minecraft:water_cauldron[level=3]','Infirmary hand basin outside door circulation')
    elif kind=='library':
        for xx in range(x+1,X,4):
            c.fill((xx,y,z+1,xx,y+1,z+4),'minecraft:bookshelf','Complete founded library shelving rows with clear reading aisles')
        for xx in [x+2,X-2]:
            c.fixture((xx,y,z+5),'cafe_table','閲覧机')
            c.put((xx+1,y,z+5),'projectseele:residential_chair[facing=west]','Library reading seat')
    elif kind=='toilets':
        c.fill((x,y,z,X,Y,z),'minecraft:white_concrete','Continuous WC rear plumbing/privacy wall, rather than a one-cell walking pocket behind each sanitary pan')
        for xx in [x+1,x+5,x+9]:
            if xx+1>X:continue
            c.fill((xx-1,y,z,xx-1,y+2,z+3),'minecraft:white_concrete','Complete school sanitary cubicle privacy wall')
            c.fill((xx+1,y,z,xx+1,y+2,z+3),'minecraft:white_concrete','Complete school sanitary cubicle privacy wall')
            c.put((xx,y,z+1),'minecraft:water_cauldron[level=3]','Voxel sanitary pan interpretation, separately identified from native functional WC')
            c.door((xx,y,z+3),'south',label=r['label']+f'/cubicle_{xx}')
        for xx in [x+1,x+7,X]:
            c.fixture((xx,y,Z-1),'drinking_fountain','手洗い設備',facing='south')
    elif kind in ['home_economics','science_prep']:
        for xx in range(x,X+1):
            c.fixture((xx,y,z),'cafe_counter','家庭科調理台' if kind=='home_economics' else '準備室作業台')
        for xx in [x+2,X-2]:
            c.put((xx,y,z),'minecraft:water_cauldron[level=3]','Grounded teaching sink on wet-room work line')
        for xx in range(x+1,X-1,4):
            c.fixture((xx,y,z+3),'cafe_table','実習机')
            c.put((xx,y,z+4),'projectseele:residential_chair[facing=north]','Practical-room seat with full rear circulation')
    for xx in [x+2,X-2]:
        c.put((xx,y+3,z+3),'minecraft:sea_lantern','Visible ceiling luminaire attached to the next floor / complete weather roof')
    c.rooms.append(dict(r,kind=kind,adapted_use=True,canon_exact_layout=False))
    c.camera('room_'+r['label'],[doorway+.5,y,Z+.5],[doorway+.5,y+1,z+2.5],[r['id'],kind])


def pool(c):
    f=72
    c.foundation((264,-747,308,-730),f,'school_pool_and_changing_terrace')
    # Water is 25x10m (five 2m lanes). East shallow end preserves a route out.
    for x in range(280,305):
        floor=71 if x>=300 else 70
        for z in range(-743,-733):
            c.put((x,floor,z),'minecraft:blue_concrete' if z in [-742,-740,-738,-736,-734] else 'minecraft:white_concrete','Whole pool floor / five original lane markings, not official artwork')
            for y in range(floor+1,73):c.put((x,y,z),'minecraft:water[level=0]','Complete contained swimming water volume')
    for z in [-744,-733]:c.fill((279,70,z,305,72,z),'minecraft:white_concrete','Entire swimming basin wall / coping containment')
    for x in [279,305]:c.fill((x,70,-743,x,72,-734),'minecraft:white_concrete','Entire swimming basin end wall / coping containment')
    # Real ladder escape points use backing basin walls, with no floating rail.
    for x in [282,298]:
        for y in [71,72]:c.put((x,y,-743),'minecraft:ladder[facing=south,waterlogged=true]','Swimming ladder attached to the actual north pool wall; native swim exit requires verification')
    for z in [-739,-738]:
        c.put((304,72,z),'minecraft:quartz_stairs[facing=east,half=bottom,shape=straight,waterlogged=true]','Real two-wide shallow-end in-water exit step below the dry deck')
    for z in [-747,-730]:
        for x in range(276,309):c.put((x,73,z),'minecraft:oak_fence[east=true,north=false,south=false,waterlogged=false,west=true]','Entire pool deck edge guard on continuous masonry coping')
    for z in range(-746,-730):c.put((308,73,z),'minecraft:oak_fence[east=false,north=true,south=true,waterlogged=false,west=false]','Entire eastern pool guard; no unprotected terrace edge')
    for x in [277,278]:
        c.put((x,73,-747),'minecraft:oak_fence_gate[facing=north,in_wall=false,open=false,powered=false]','Complete two-wide pupil pool gate')
    # The changing building is a complete roofed service facility, not labels.
    c.fill((264,73,-747,275,75,-730),'minecraft:air','Whole changing/shower building interior clearance')
    for x in [264,275]:c.fill((x,73,-747,x,75,-730),'projectseele:residential_plaster','Complete founded changing-room exterior wall')
    for z in [-747,-739,-730]:c.fill((264,73,z,275,75,z),'projectseele:residential_plaster','Whole changing-room privacy / exterior partition')
    c.fill((264,76,-747,275,76,-730),'minecraft:smooth_stone','Complete continuous changing-room weather roof')
    for label,doorz,a,Z in [('north_changing',-742,-746,-740),('south_changing',-734,-738,-731)]:
        c.door((275,73,doorz),'east',label=label)
        for z in range(a+1,Z):
            c.empty_container((265,73,z),'minecraft:barrel[facing=east,open=false]','barrel')
            c.put((266,73,z),'minecraft:dark_oak_slab[type=bottom,waterlogged=false]','Grounded changing bench below player eye level')
        for z in [a+1,a+3]:
            c.put((272,73,z),'minecraft:water_cauldron[level=3]','Individual shower / rinse basin; water mechanics are explicit Minecraft adaptation')
            c.put((272,75,z),'minecraft:tripwire_hook[attached=false,facing=west,powered=false]','Original attached shower fitting on actual wall bay')
            c.put((273,75,z),'minecraft:white_concrete','Actual backing for the shower fitting')
        c.put((270,75,a+2),'minecraft:sea_lantern','Visible changing-room ceiling light attached to roof')
        c.rooms.append(dict(id='r45/school/'+label,kind='changing_shower_room',bounds=[265,73,a,274,75,Z],floor=1,canon_exact_layout=False))
        c.path(label+'/door',[[278.5,73,doorz+.5],[273.5,73,doorz+.5],[270.5,73,doorz+.5]],door=[275,73,doorz])
        c.sign((276,74,doorz-1),['更衣室・シャワー','プール利用者専用'],'east')
    # The full dry approach joins the actual v22 sport route at X273/Z-750.
    for x in range(272,280):
        for z in range(-751,-747):
            g=max(y for y in range(48,74) if c.measured.get(x,y,z).partition('[')[0] not in {'minecraft:air','minecraft:grass','minecraft:tall_grass'})
            for y in range(g,72):c.put((x,y,z),'minecraft:stone','Whole pool approach has measured dry bearing')
            c.put((x,72,z),'minecraft:smooth_stone','Full three-wide connection to actual sports approach')
            c.fill((x,73,z,x,75,z),'minecraft:air','Complete pupil pool approach width and headroom')
    # The retained north sports link floor is at Z=-750, so its foot centre
    # is -749.5. Z=-750.5 stands on the unbuilt neighbouring Z=-751 row.
    c.path('pool/from_school_north_port',[[233.5,73,-730.5],[233.5,73,-749.5],[277.5,73,-749.5],[277.5,73,-746.5],[277.5,73,-732.5]],interaction='pool_gate',gate=[277,73,-747])
    c.path('pool/full_deck_ring',[[277.5,73,-745.5],[306.5,73,-745.5],[306.5,73,-731.5],[277.5,73,-731.5],[277.5,73,-745.5]])
    c.path('pool/to_retained_sports_field',[[277.5,73,-750.5],[273.5,73,-750.5],[273.5,73,-756.5],[273.5,73,-767.5]])
    # Exact authored fence connectivity includes the actual adjoining terrain
    # and the changing-room wall. Native neighbour updates should not silently
    # change a disconnected corner into a different inverse precondition.
    shapes=json.loads((c.world/'native_collision_shapes.json').read_text('utf8'))
    directions={'east':(1,0),'north':(0,-1),'south':(0,1),'west':(-1,0)}
    for q,row in list(c.target.items()):
        if not row['after'].startswith('minecraft:oak_fence['):continue
        connected={}
        for name,(dx,dz) in directions.items():
            st=c.state((q[0]+dx,q[1],q[2]+dz));base=st.partition('[')[0]
            connected[name]=base.endswith('_fence') or '_fence_gate' in base or any(b==[0.0,0.0,0.0,1.0,1.0,1.0] for b in shapes.get(st,[]))
        props=','.join(name+'='+str(connected[name]).lower() for name in ['east','north','south'])+',waterlogged=false,west='+str(connected['west']).lower()
        c.put(q,'minecraft:oak_fence['+props+']','Complete connected swimming-pool guard including real corners, gates, room walls and adjoining dry terrain')
    c.components.extend([dict(id='r45/school/swimming_pool',kind='complete_swimming_facility',bounds=[276,70,-747,308,74,-730],water_bounds=[280,71,-743,304,72,-734],water_length_m=25,water_width_m=10,lanes=5,deep_end_native_depth_m=1.8889,shallow_end_native_depth_m=.8889,metres_are_engineering=True,swimming_native_verified=False),dict(id='r45/school/changing_building',kind='changing_shower_building',bounds=[264,72,-747,275,76,-730])])
    c.floors.extend([dict(id='r45/school/pool_deck',feet=73,bounds=[276,-747,308,-730],exclusions=[[280,-743,304,-734]],role='dry_deck'),dict(id='r45/school/north_changing',feet=73,bounds=[265,-746,274,-740]),dict(id='r45/school/south_changing',feet=73,bounds=[265,-738,274,-731])])
    c.camera('pool_whole',[318.5,82,-721.5],[289.5,73,-739],[x['id'] for x in c.components if '/swimming_pool' in x['id'] or '/changing_building' in x['id']])
    c.camera('pool_ground',[277.5,73,-745.5],[295.5,72,-738.5],['dry_deck','water','ladder','shallow_exit','edge_guard'])


def gym(c,b):
    x,z,X,Z=b['bounds'];f=b['floor']
    c.fill((x+1,f,z+1,X-1,f,Z-1),'minecraft:birch_planks','Complete sports hall timber playing surface')
    for xx in [292,300]:c.fill((xx,f,-715,xx,f,-698),'minecraft:white_concrete','Complete original volleyball side marking')
    for zz in [-715,-707,-698]:c.fill((292,f,zz,300,f,zz),'minecraft:white_concrete','Original volleyball end / centre marking')
    for zz in [z+1,Z-1]:
        c.fill((295,f+4,zz,299,f+5,zz),'minecraft:white_stained_glass','Grounded wall-supported gym backboard interpretation, above all pupil headroom')
    for xx in [288,306]:
        for zz in range(-715,-698,4):c.put((xx,f+1,zz),'projectseele:residential_chair[facing=east]' if xx==288 else 'projectseele:residential_chair[facing=west]','Full court-side changing/substitute seating outside the marked sports court')
    c.components.append(dict(id='r45/school/gym',kind='complete_retained_sports_hall',bounds=[x,f,z,X,b['roof'],Z],retained_v22_roof=True,official_gym_curve_source='separately labelled SMALL WORLDS secondary reference',court_metres_are_adaptation=True))
    c.floors.append(dict(id='r45/school/gym/full_court',feet=f+1,bounds=[x+1,z+1,X-1,Z-1],role='Entire actual playing hall; seats/backboards are fixtures and roof is not public'))
    c.path('gym/entire_court',[[297.5,73,-695.5],[297.5,73,-697.5],[290.5,73,-697.5],[290.5,73,-716.5],[303.5,73,-716.5],[303.5,73,-697.5],[297.5,73,-697.5]],door=b['door'])
    c.camera('gym_whole_inside',[290.5,73,-696.5],[297.5,76,-708.5],['roof','court','both_end_backboards','all_seating','entry'])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--world',type=Path,default=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW')
    p.add_argument('--out',type=Path,default=ART/'school_v1')
    p.add_argument('--repair-current',action='store_true',help='Measure the installed R45 campus; emit only its remaining finite tail and additive lifecycle metadata')
    a=p.parse_args()
    installed=ROOT/'artifacts/rebuild_r45/component_installations/school_campus_v2/installation.json'
    if a.repair_current or a.world.name=='SEELE_FIELD_R45_REVIEW' and installed.exists() or (a.world/'r45_school_hakone_components.json').exists():
        from prepare_school_hakone_lifecycle_r45 import prepare
        output=ART/'lifecycle_repair_current' if a.out==ART/'school_v1' else a.out
        prepare(a.world,output)
        return
    d=json.loads((BASE/'new_district.json').read_text('utf8'))
    c=Candidate(a.world,[216,48,-790,314,102,-668],'r45/school')
    uses={'1-N1':'staff_office','1-N2':'infirmary','1-N3':'science_prep','1-S1':'library','1-S2':'toilets','1-S3':'home_economics','2-S2':'music','2-S3':'science','3-N3':'art'}
    for r in d['rooms']:
        if '/main/' in r['id'] and r.get('wing'):
            room_contents(c,r,uses.get(r['label'],'classroom'))
    b=next(b for b in d['buildings'] if b['kind']=='tv_school')
    c.components.append(dict(id='r45/school/main',kind='whole_retained_three_storey_school',bounds=[224,72,-728,282,92,-680],classroom_bars=2,storeys=3,retained_links=2,retained_stair_towers=2,retained_genkan=True,retained_roof=True))
    for f in b['floor_feet']:
        c.floors.append(dict(id=f'r45/school/main/floor_{f}',feet=f,bounds=[225,-727,281,-687],retained_v22_geometry=True))
        c.path(f'floor_{f}/north_full_corridor',[[234.5,f,-717.5],[280.5,f,-717.5]])
        c.path(f'floor_{f}/south_full_corridor',[[226.5,f,-687.5],[272.5,f,-687.5]])
        c.camera(f'floor_{f}_north',[235.5,f,-717.5],[276.5,f+1,-717.5],['all_north_doors','floor','ceiling','windows'])
        c.camera(f'floor_{f}_south',[227.5,f,-687.5],[269.5,f+1,-687.5],['all_south_doors','east_stair_port','floor','ceiling'])
    c.cases.extend(json.loads((BASE/'native_cases.json').read_text('utf8')))
    gym(c,next(b for b in d['buildings'] if b['kind']=='tv_gym'))
    pool(c)
    # The original 35x25 field remains usable as a full dry dirt court.
    for x in range(257,290):
        for z in range(-779,-756):
            c.put((x,72,z),'minecraft:coarse_dirt','Whole retained school sports-ground surface, distinct from station or patio paving')
    for x in range(256,291):
        for z in [-780,-756]:
            if z==-756 and 272<=x<=274:continue
            for y in [73,74]:c.put((x,y,z),'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]','Complete sports-ground perimeter wire guard founded on the original field terrace; three-wide actual south entry retained')
    for z in range(-779,-756):
        for x in [256,290]:
            for y in [73,74]:c.put((x,y,z),'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]','Complete sports-ground wire guard on the actual lateral retaining edge')
    for x in [229,276]:
        for z in [-710,-706]:
            c.put((x,73,z),'minecraft:oak_leaves[distance=7,persistent=true,waterlogged=false]','Low original courtyard planting with no fictional trunk dependency, kept below both classroom linking corridors')
            c.put((x+(1 if x==229 else -1),73,z),'projectseele:residential_chair[facing=south]','Actual pupil courtyard seat outside the central full-width linking route')
    shapes=json.loads((c.world/'native_collision_shapes.json').read_text('utf8'))
    for q,row in list(c.target.items()):
        if not row['after'].startswith('minecraft:iron_bars['):continue
        props={}
        for name,(dx,dz) in {'east':(1,0),'north':(0,-1),'south':(0,1),'west':(-1,0)}.items():
            st=c.state((q[0]+dx,q[1],q[2]+dz))
            props[name]=st.partition('[')[0]=='minecraft:iron_bars' or any(b==[0.0,0.0,0.0,1.0,1.0,1.0] for b in shapes.get(st,[]))
        c.put(q,'minecraft:iron_bars['+','.join(n+'='+str(props[n]).lower() for n in ['east','north','south'])+',waterlogged=false,west='+str(props['west']).lower()+']','Complete connected sports-field guard including corners, open south access and actual adjoining terrain')
    c.components.append(dict(id='r45/school/sports_field',kind='retained_complete_sports_ground',bounds=[256,72,-780,290,76,-756]))
    c.floors.append(dict(id='r45/school/sports_field',feet=73,bounds=[257,-779,289,-757]))
    c.camera('whole_campus',[314.5,96,-670.5],[265,77,-719],['all_school_storeys','genkan','gym','sports_field','pool','changing_rooms','real_street'])
    c.camera('roof_and_court',[240.5,88,-696.5],[262,78,-710],['retained_roof_guard','roof_entry','two_links','whole_courtyard'])
    existing_port_keys={tuple(p['position']) for p in c.ports if 'position' in p}
    for case in c.cases:
        if case.get('door') and tuple(case['door']) not in existing_port_keys:
            q=tuple(case['door']);st=c.state(q)
            c.ports.append(dict(id=case['id']+'/actual_door_port',kind='retained_school_door',position=list(q),closed_state=st,open_state=st.replace('open=false','open=true'),states=['closed','open'],native_verified=False))
            existing_port_keys.add(q)
    c.ports.extend([dict(id='r45/school/west_stair_tower',kind='retained_storey_and_roof_connection',feet=[73,78,83,88],source='v22 actual stairs1/2/3 pairs',native_verified=False),dict(id='r45/school/east_stair_tower',kind='retained_storey_connection',feet=[73,78,83],source='v22 actual east_tower_stairs1/2 pairs',native_verified=False),dict(id='r45/school/pool_gate',kind='native_pool_gate_pair',positions=[[277,73,-747],[278,73,-747]],states=['closed','open'],native_verified=False)])
    c.floors.append(dict(id='r45/school/retained_roof',feet=88,bounds=[225,-727,281,-687],role='Guarded original v22 rooftop; courtyard void is classified separately'))
    out=c.export(a.out,dict(title='R45 entire TV-facing school campus with complete pool',producer=str(Path(__file__).resolve()),installed_base=str(BASE.resolve()),no_v22_replay=True,canon='TV-facing school exterior relationship from inherited research; SMALL WORLDS model is a secondary visual reference. 25x10 pool, location, room count, furniture and assigned room uses are original playable engineering.',water_and_marsh_preserved=True,unverified=['new and inherited whole-room native motion','water ladder and shallow-end swimming exit','open/closed school and pool gate states','storage block entities after native load','complete native shader photography','user visual approval','final actual installed-copy readback']))
    (out/'new_district.json').write_text(json.dumps(dict(d,r45_rooms=c.rooms,r45_components=c.components,r45_pool_added=True),ensure_ascii=False,indent=2),'utf8')
    reservations=json.loads((BASE/'ecology_reservations.json').read_text('utf8'))
    reservations['reservations'].extend(dict(bounds=b['bounds'],owner=b['id'],role=b['kind']) for b in c.components)
    for f in c.foundations:
        cols=f['columns'];reservations['reservations'].append(dict(bounds=[min(v['pos'][0] for v in cols),min(v['actual_bearing_y'] for v in cols)-2,min(v['pos'][1] for v in cols),max(v['pos'][0] for v in cols),80,max(v['pos'][1] for v in cols)],owner='r45/school/'+f['component'],role='Entire measured foundation, retaining wall, dry deck, pool and changing-room envelope'))
    (out/'ecology_reservations.json').write_text(json.dumps(reservations,indent=2),'utf8')
    shutil.copy2(BASE/'road_authority.json',out/'road_authority.json')
    shutil.copy2(BASE/'station_journeys.json',out/'inherited_station_journeys.json')


if __name__=='__main__':
    main()
