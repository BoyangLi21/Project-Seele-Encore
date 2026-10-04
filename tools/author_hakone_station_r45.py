"""Complete existing Hakone station architectural candidate; never writes saves.

Uses the official Hakone-Yumoto public/paid/service program as a reference.
The existing R1/S1 elevated alignments and all native IDs stay in place. This
is a whole-station game adaptation, explicitly not a three-track 1:1 replica.
"""
from pathlib import Path
import argparse
import json
import math

from query_blocks import AIR
from school_hakone_patch_r45 import Candidate, ROOT, ART, sha

SID='6131386888082811228'
PLATFORMS=['-3388587481325067738','2113004979025593751','3559976582378878399','1700974792440530138']
CIVIL=ROOT/'artifacts/access_r22/transit/civil/station_contract.json'
TRANSIT=ROOT/'artifacts/rebuild_r44/facility_transit_r44/native_transit_cases/cases.json'


def protect_body(c, points, radius=1.2):
    for a,b in zip(points,points[1:]):
        n=max(1,math.ceil(math.dist(a,b)*2))
        for i in range(n+1):
            q=[a[k]+(b[k]-a[k])*i/n for k in range(3)]
            if not all(c.lo[k]-3<=q[k]<=c.hi[k]+3 for k in range(3)):continue
            for x in range(math.floor(q[0]-radius),math.floor(q[0]+radius)+1):
                for z in range(math.floor(q[2]-radius),math.floor(q[2]+radius)+1):
                    for y in range(math.floor(q[1]),math.ceil(q[1]+2.4)):
                        c.hard.add((x,y,z))


def protect_existing(c,native,cases):
    # Current native virtual-track curves, not old terrain or straight guesses.
    for curve in native['curves']:
        if curve.get('mode')!='TRAIN':continue
        for x,y,z in curve.get('points',[]):
            if not c.lo[0]-4<=x<=c.hi[0]+4 or not c.lo[2]-4<=z<=c.hi[2]+4 or not c.lo[1]-8<=y<=c.hi[1]:continue
            for X in range(math.floor(x)-2,math.floor(x)+3):
                for Z in range(math.floor(z)-2,math.floor(z)+3):
                    for Y in range(math.floor(y),math.floor(y)+7):c.hard.add((X,Y,Z))
    for case in cases:
        points=case.get('path') or [case.get('start'),case.get('end')]
        if points and points[0] is not None and any(all(c.lo[k]<=q[k]<=c.hi[k] for k in range(3)) for q in points):
            protect_body(c,points)
    for q,tag in c.tags.items():
        st=c.measured.block(q)
        for x in range(q[0]-2,q[0]+3):
            for z in range(q[2]-1,q[2]+2):
                for y in range(q[1]-1,q[1]+3):c.hard.add((x,y,z))
    # Keep every actual MTR cell and all tactile strips, even if not catalogued.
    for (cx,sy,cz),(palette,ids) in c.measured.tiles.items():
        keep={i for i,s in enumerate(palette) if s.startswith('mtr:') or s.startswith('projectseele:station_tactile') or s.startswith('projectseele:period_fixture')}
        if not keep:continue
        for i,pid in enumerate(ids):
            if int(pid) in keep:
                q=(cx*16+(i&15),sy*16+(i>>8),cz*16+((i>>4)&15))
                c.hard.add(q)
                if palette[int(pid)].startswith('mtr:escalator_step['):
                    for X in range(q[0]-1,q[0]+2):
                        for Z in range(q[2]-1,q[2]+2):
                            for Y in range(q[1]+1,q[1]+5):c.hard.add((X,Y,Z))


def service_room(c,label,rect,facing='south',kind='ticket_information'):
    x,z,X,Z=rect;g=104
    # These are declared existing lower-station bays, with measured plinth and
    # no independent building/fixture. An unresolved room is not emitted.
    blockers=[]
    for xx in range(x,X+1):
        for zz in range(z,Z+1):
            floor=c.measured.get(xx,g,zz)
            if floor not in ['projectseele:period_station_floor','minecraft:smooth_stone']:
                blockers.append([xx,g,zz,floor])
            for y in range(g+1,g+5):
                st=c.measured.get(xx,y,zz)
                if st.partition('[')[0] not in AIR|{'projectseele:nerv_storage_panel','projectseele:station_seat'} or (xx,y,zz) in c.hard:
                    blockers.append([xx,y,zz,st,'protected' if (xx,y,zz) in c.hard else 'occupied'])
    if blockers:
        return dict(id=label,bounds=[x,g,z,X,g+5,Z],status='NOT_EMITTED',blockers=blockers)
    c.fill((x,g,z,X,g,Z),'minecraft:brown_terracotta','Whole named station '+kind+' floor, on measured existing bearing')
    c.fill((x+1,g+1,z+1,X-1,g+4,Z-1),'minecraft:air','Whole explicitly named existing service bay retires the prior inert NERV-style storage-panels and repeated station seats before purpose-specific original station furniture')
    for xx in [x,X]:c.fill((xx,g+1,z,xx,g+4,Z),'projectseele:residential_plaster','Full named station service-room side wall')
    for zz in [z,Z]:c.fill((x,g+1,zz,X,g+4,zz),'projectseele:residential_plaster','Full named station service-room frontage/back wall')
    c.fill((x,g+5,z,X,g+5,Z),'minecraft:oak_planks','Whole named station service-room weather/interior ceiling')
    front=Z if facing=='south' else z
    dx=(x+X)//2
    for xx in range(x+1,X):
        c.fill((xx,g+2,front,xx,g+3,front),'projectseele:clear_glass','Real ticket/service frontage glazing')
    for xx,h in [(dx-1,'left'),(dx,'right')]:c.door((xx,g+1,front),facing,h,label=label+'/leaf'+str(xx-dx+2))
    inside=front-1 if facing=='south' else front+1
    outside=front+2 if facing=='south' else front-2
    c.path(label+'/whole_public_entry',[[dx+.5,g+1,outside+.5],[dx+.5,g+1,inside+.5],[x+2.5,g+1,inside+.5],[X-1.5,g+1,inside+.5]],door=[dx,g+1,front])
    if kind in ['ticket_information','luggage_service']:
        back=z+1 if facing=='south' else Z-1
        for xx in range(x+1,X):c.fixture((xx,g+1,back),'cafe_counter','旅行・乗車案内' if kind=='ticket_information' else '手荷物受付',facing=facing)
        if kind=='luggage_service':
            for zz in range(z+1,Z):c.empty_container((x+1,g+1,zz),'minecraft:barrel[facing=east,open=false]','barrel')
    elif kind=='souvenir_shop':
        for xx in range(x+1,X):c.fill((xx,g+1,z+1,xx,g+2,z+1),'minecraft:bookshelf','Original compact souvenir display shelving; no vendor trademark texture')
        for xx in [x+2,X-2]:c.fixture((xx,g+1,z+3),'cafe_counter','地域物産売店',facing=facing)
    elif kind=='waiting_room':
        for xx in range(x+2,X-1,2):
            for zz in [z+2,z+4]:c.put((xx,g+1,zz),'projectseele:station_seat[facing=south]','Whole waiting room with grounded passenger seats and a free front aisle')
    elif kind=='toilets':
        for xx in range(x+2,X-1,3):
            c.fill((xx-1,g+1,z+1,xx-1,g+3,z+3),'projectseele:residential_plaster','Complete station WC privacy cubicle')
            c.put((xx,g+1,z+1),'minecraft:water_cauldron[level=3]','Original voxel sanitary pan; not a custom functional toilet')
            c.door((xx,g+1,z+3),'south',label=label+'/cubicle_'+str(xx))
        c.fixture((X-1,g+1,Z-1),'drinking_fountain','手洗い',facing='west')
    elif kind=='staff_office':
        for xx in range(x+2,X-1,3):
            c.fixture((xx,g+1,z+2),'cafe_table','駅係員机')
            c.put((xx,g+1,z+3),'projectseele:residential_chair[facing=north]','Complete station staff office seating')
    for xx in [x+2,X-2]:c.put((xx,g+4,z+2),'minecraft:sea_lantern','Visible room luminaire attached to the entire roof')
    c.sign((dx+2,g+3,front+(1 if facing=='south' else -1)),[label,'駅内サービス'],facing)
    c.rooms.append(dict(id='r45/hakone/'+label,kind=kind,bounds=[x+1,g+1,z+1,X-1,g+4,Z-1],level='lower_station_hall',canon_exact_layout=False))
    c.components.append(dict(id='r45/hakone/'+label,kind=kind,bounds=[x,g,z,X,g+5,Z],metre_layout='original engineering bay inside the existing station plinth'))
    c.floors.append(dict(id='r45/hakone/'+label,feet=g+1,bounds=[x+1,z+1,X-1,Z-1]))
    c.camera(label+'/inside',[dx+.5,g+1,inside+.5],[dx+.5,g+2,(z+Z)/2],[label,'all_furniture','door','wall','ceiling'])
    return dict(id=label,bounds=[x,g,z,X,g+5,Z],status='EMITTED')


def canopy(c,s):
    x,y,z=s['center'];h=s['half'];edge=y+11
    # Retire only the complete old authored flat canopy; columns, equipment,
    # native tracks, overbridges and all station door interfaces remain.
    for xx in range(x-h,x+h+1):
        for zz in range(z-15,z+16):
            for yy in [edge,edge+1]:
                old=c.measured.get(xx,yy,zz)
                if old in ['minecraft:light_gray_concrete','projectseele:clear_glass','minecraft:light_gray_stained_glass','minecraft:glass']:
                    c.put((xx,yy,zz),'minecraft:air','Entire superseded authored flat station canopy retired before the complete roof profile')
    for zz in range(z-15,z+16):
        top=edge+round(4*(1-abs(zz-z)/15))
        c.fill((x-h,top,zz,x+h,top,zz),'minecraft:gray_concrete','Whole low-pitched matte metal station roof; profile is engineering adaptation, not official measured geometry')
        if zz in [z-15,z+15]:
            c.fill((x-h,top-1,zz,x+h,top-1,zz),'minecraft:dark_oak_planks','Continuous roof edge/soffit carried by the real retained station columns')
    # Close the gables as a whole, leaving all end/native interfaces intact.
    for xx in [x-h,x+h]:
        for zz in range(z-15,z+16):
            top=edge+round(4*(1-abs(zz-z)/15))
            c.fill((xx,edge,zz,xx,top-1,zz),'projectseele:residential_plaster','Complete founded station roof gable between retained eaves and ridge')
    # Full lower hall ceiling is suspended from the existing platform frame.
    for xx in range(x-h+1,x+h):
        for zz in range(z-14,z+15):
            old=c.measured.get(xx,111,zz)
            if old in AIR:c.put((xx,111,zz),'minecraft:oak_planks','Whole fitted lower station hall ceiling; all native stair and moving-walk envelopes protected')
    for xx in range(x-h+12,x+h-9,12):
        for zz in [z-6,z+6]:c.put((xx,110,zz),'minecraft:sea_lantern','Visible human-scale station hall luminaire below the complete fitted ceiling')
    # Entire extant vertical columns receive an even, finite cladding update.
    for zz in [z-15,z+15]:
        for xx in range(x-h,x+h+1):
            for yy in range(105,edge):
                if c.measured.get(xx,yy,zz)=='minecraft:light_gray_concrete':
                    c.put((xx,yy,zz),'projectseele:residential_plaster','Whole real station frame finish; no fictional wall inferred from air')
    c.components.append(dict(id='r45/hakone/'+s['line']+'_complete_station',kind='full_retained_operating_station_building',bounds=[x-h,104,z-15,x+h,edge+4,z+15],whole_roof=True,whole_lower_ceiling=True,platform_ids=[str(i) for i in s['platform_ids']],feet=[105,y+1,y+8],all_native_vertical_connections_retained=True))
    c.floors.extend([dict(id='r45/hakone/'+s['line']+'/lower_hall',feet=105,bounds=[x-h+1,z-14,x+h-1,z+14],native_moving_walks_and_columns_classified_separately=True),dict(id='r45/hakone/'+s['line']+'/north_platform',feet=y+1,bounds=[x-h+1,z-14,x+h-1,z-5]),dict(id='r45/hakone/'+s['line']+'/south_platform',feet=y+1,bounds=[x-h+1,z+5,x+h-1,z+14])])
    c.camera(s['line']+'/whole_platform',[x-h+36.5,y+1,z-11.5],[x+h-12.5,y+3,z+2.5],[s['line'],'full_platform_length','roof','both_platform_edges','all_departure_boards'])
    c.camera(s['line']+'/whole_lower_hall',[x-h+40.5,105,z+.5],[x+h-13.5,108,z+.5],[s['line'],'full_concourse','room_frontages','all_ceiling_luminaires','original_moving_walks'])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--world',type=Path,default=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW')
    p.add_argument('--out',type=Path,default=ART/'hakone_v1')
    p.add_argument('--repair-current',action='store_true',help='Use current R45 lifecycle repair; do not replay the whole R22/R45 station geometry')
    a=p.parse_args()
    installed=list((ROOT/'artifacts/rebuild_r45/component_installations').glob('*hakone*/installation.json'))
    if a.repair_current or a.world.name=='SEELE_FIELD_R45_REVIEW' and installed or (a.world/'r45_school_hakone_components.json').exists():
        from prepare_school_hakone_lifecycle_r45 import prepare
        output=ART/'lifecycle_repair_current' if a.out==ART/'hakone_v1' else a.out
        prepare(a.world,output)
        return
    c=Candidate(a.world,[-1560,90,610,-1396,151,770],'r45/hakone')
    native=json.loads((a.world/'native_transit_r28.json').read_text('utf8'))
    cases=json.loads((a.world/'quality_walk_cases.json').read_text('utf8'))
    stations=[s for s in json.loads(CIVIL.read_text('utf8'))['stations'] if s['station']=='新箱根中央']
    protect_existing(c,native,cases)
    inherited=[case for case in cases if any('/'+pid+'/' in case['id'] for pid in PLATFORMS) or '/transfer/hakone' in case['id']]
    c.cases.extend(inherited)
    room_requests=[('旅行・乗車案内',(-1518,623,-1505,630),'south','ticket_information'),('地域物産売店',(-1475,625,-1462,630),'south','souvenir_shop'),('待合室',(-1518,642,-1505,649),'north','waiting_room'),('手荷物受付',(-1511,663,-1493,670),'south','luggage_service'),('駅内トイレ',(-1469,665,-1455,670),'south','toilets'),('駅事務室',(-1460,683,-1447,690),'north','staff_office')]
    emitted=[service_room(c,*req) for req in room_requests]
    for s in stations:canopy(c,s)
    gates=[g for g in json.loads((a.world/'r44_public_station_gates.json').read_text('utf8'))['gates'] if g['station_id']==SID]
    for i,g in enumerate(gates):
        c.ports.append(dict(id='r45/hakone/gate/'+str(i),kind='original_native_ticket_gate',position=g['position'],station_id=SID,closed_state=g['closed_state'],open_state=g['open_state'],preserved=True,native_open_close_verified=False))
    transit=json.loads(TRANSIT.read_text('utf8'))
    interfaces=[x for x in transit['cases'] if x.get('source_platform') in PLATFORMS]
    for item in interfaces:
        source=item['source'];pid=item['source_platform']
        c.ports.append(dict(id='r45/hakone/platform/'+pid,kind='complete_existing_boarding_interface',platform_id=pid,station_id=SID,staging=source['staging'],platform_lo=source['platform_lo'],platform_hi=source['platform_hi'],actual_APG_pairs=source['actual_APG_pairs'],all_actual_door_approaches=source['all_actual_door_approaches'],snapshot_sha256=sha(TRANSIT),live_boarding_verified=False))
        for i,q in enumerate(source['all_actual_door_approaches']):
            # A finite apron survey covers every real pair; actual train door
            # opening, collision and boarding remain root's native test.
            outside=q[2]+(-1 if q[2]<source['staging'][2] else 1)
            c.path('boarding/'+pid+'/'+str(i),[[q[0]+.5,q[1],outside+.5],[q[0]+.5,q[1],q[2]+.5]],native_platform_id=pid,requires_actual_APG_open=True)
    replacements=[]
    for case in inherited:
        if case['id'].startswith('r40/platform/') and any('/'+pid+'/' in case['id'] for pid in PLATFORMS):
            first,last=case['path'];y=first[1];z=first[2]
            corrected=[first,[-1484.5,y,z],[-1484.5,y,z-1],[-1478.5,y,z-1],[-1478.5,y,z],last]
            replacements.append(dict(id=case['id'],before_path=case['path'],after_path=corrected,reason='Full old island-platform centreline crosses the complete existing NERV sign-post at X-1481. Retain its actual identity/backing and both original endpoints; use the already authored R43 north-side clear apron for a full-width detour.',delete_case=False,fixture_preserved=True))
            case['path']=corrected
        if case['id']=='r28/map_approach/r25/station_map/3559976582378878399/-1':
            corrected=[[ -1534.5,105,659.5],[-1532.5,105,659.5],[-1532.5,105,660.5],[-1526.5,105,660.5]]
            replacements.append(dict(id=case['id'],before_path=case['path'],after_path=corrected,reason='Original source starts inside the closed north S1 ticket barrier at Z661; the real public north entrance begins outside at Z659 and reaches the same actual map-reading point',delete_case=False,gate_preserved=True))
            case['path']=corrected
    for i,g in enumerate(gates[::2]):
        x,y,z=g['position'];dz=-1 if 'facing=south' in g['closed_state'] else 1
        c.camera('public_gate_'+str(i),[x+1.5,y,z+dz*3+.5],[x+.5,y+1,z+.5],['original_gate_bank','public_approach','native_fare_interaction'])
    c.camera('whole_station',[-1378.5,155,709.5],[-1480,125,651],['R1_complete_station','S1_complete_station','four_platforms','all_vertical_connections','whole_service_floor','interchange'])
    unresolved=[x for x in emitted if x['status']!='EMITTED']
    out=c.export(a.out,dict(title='R45 entire existing Hakone interchange / Hakone-Yumoto program adaptation',producer=str(Path(__file__).resolve()),station_id=SID,native_platform_ids=PLATFORMS,official_sources=['https://www.odakyu.jp/station/hakone_yumoto/','https://www.odakyu.jp/station/hakone_yumoto/homeview/','https://www.hakonenavi.jp/transportation/station/hakone-yumoto/'],reference_facts=['Official Hakone-Yumoto: ground platforms have Romancecar / Odawara local / Gora mountain-rail functions','Official station has upper-floor ticket gates, public travel centre/cafe/souvenir program and public deck to opposite-side bus/taxi access','Official railway platform access includes stairs, escalators and elevators'],adaptation_differences=['Existing R1/S1 routes, four directional native platform identities and feet119/131 retained; real three-platform ground configuration is not copied','Existing four lower gate banks and lower hall105 remain; this is not an exact upper-gate layout replica','Roof profile, materials, room dimensions and bay positions are original voxel engineering','Native lift availability is absent in current native transit snapshot; no decorative shaft is represented as a working elevator','No unsupported cosmetic bus vehicles or non-operating bus stops are claimed as live transport'],service_room_requests=emitted,unresolved_service_rooms=unresolved,traffic_files_modified=False,all_existing_BE_immutable=True,hard_native_envelope_cells=len(c.hard),unverified=['all actual MTR gates with real card interaction','all 368 observed APG door approaches plus live train boarding in four directions','native end-to-end R1/S1 transfer and original vertical connection states','all room entries and entire floor geometry after native load','complete current-shader native photography','actual final installation readback and user approval']))
    (out/'path_replacements.json').write_text(json.dumps(replacements,indent=2),'utf8')
    (out/'boarding_interfaces.json').write_text(json.dumps(interfaces,ensure_ascii=False,indent=2),'utf8')
    (out/'protected_native_coordinates.json').write_text(json.dumps(sorted(c.hard)),'utf8')
    (out/'road_authority.json').write_text(json.dumps(dict(columns=[],scope='No roadway changes in this station patch; full original public street/forecourt retained')),'utf8')
    (out/'new_district.json').write_text(json.dumps(dict(id='r45_hakone_station',bounds=[-1560,-1396,610,700],buildings=[dict(id='r45/hakone/'+s['line'],bounds=[s['center'][0]-s['half'],s['center'][2]-15,s['center'][0]+s['half'],s['center'][2]+15],floor=104,storeys=3,roof=s['center'][1]+15,kind='station',door=[s['center'][0]-s['half']+4,105,s['center'][2]-15]) for s in stations],rooms=c.rooms,reference='Official current Hakone-Yumoto spatial program; full current R1/S1 elevated station adaptation, not 1:1'),ensure_ascii=False,indent=2),'utf8')
    print('whole service rooms emitted',len(emitted)-len(unresolved),'of',len(emitted),'protected unresolved',[(x['id'].encode('unicode_escape').decode(),len(x['blockers'])) for x in unresolved],flush=True)


if __name__=='__main__':
    main()
