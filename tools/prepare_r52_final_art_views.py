"""Read the current construction save to prepare bounded photo viewpoints.

No game launch, QA copy, or world writes. Migration provenance fields are never
applied as transforms: all coordinates below are current world coordinates.
"""
from pathlib import Path
import argparse, json, math, hashlib, uuid
from query_blocks import read_box, iter_block_entities, iter_box_cells, AIR
from inspect_map_assets import region_chunks
BASE=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')
WORLD=BASE/'WORLD_R52';ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'.codex/r52_final_art_capture/VIEWS_CURRENT_V8.json'
DIM='projectseele:geofront'
GROUND=BASE/'continuous_upright/spread_level_throats/GROUND_CONTINUOUS_DESIGN.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def original_units(world):
    directory=json.loads(GROUND.read_text('utf8'));units={u['eva']:u for u in directory['units']}
    nodes={n['id']:n for n in directory['nodes']};bays={u['eva']:nodes['unit'+str(u['variant'])+'/bay']['foot_frame']['translation'] for u in units.values()}
    selected={(math.floor(p[0])//16,math.floor(p[2])//16)for p in bays.values()};bounds=(min(p[0]for p in selected),max(p[0]for p in selected),min(p[1]for p in selected),max(p[1]for p in selected));found={}
    def descendants(t):
        yield t
        for child in t.get('Passengers',[]):yield from descendants(child)
    for path in (world/'dimensions/projectseele/geofront/entities').glob('r.*.mca'):
        for cx,cz,chunk in region_chunks(path,bounds,selected):
            for root in chunk.get('Entities',[]):
                for t in descendants(root):
                    if 'UUID'not in t:continue
                    uid=str(uuid.UUID(bytes=b''.join((int(n)&0xffffffff).to_bytes(4,'big')for n in t['UUID'])))
                    if uid not in units:continue
                    if uid in found:raise ValueError('Duplicate original EVA: '+uid)
                    variant=units[uid]['variant'];position=list(map(float,t['Pos']));expected_type='projectseele:eva_unit0'+str(variant)
                    if str(t['id'])!=expected_type or math.dist(position,bays[uid])>2:raise ValueError(('Original EVA is not in its current authored wet bay',uid,str(t['id']),position))
                    found[uid]={'uuid':uid,'variant':variant,'source_type':str(t['id']),'expected_position':position,'position_tolerance_m':2.0,'source_entity_chunk':[cx,cz]}
    if set(found)!=set(units):raise ValueError(('Original bay EVA missing in exact selected source entity chunks',set(units)-set(found)))
    return {r['variant']:r for r in found.values()}

def sampled_surface(world,low,high):
    """Exact16m-spaced current columns, only their top non-air surface section.

    This is declared sampled landmark coverage, not proof of the entire box.
    No interpolated terrain or generated section is substituted for source data.
    """
    tops={}
    for q,s in iter_box_cells(world,DIM,low,high,step=(16,1,16),include_air=False,full_chunks_only=True):
        key=(q[0],q[2])
        if key not in tops or q[1]>tops[key][0][1]:tops[key]=(q,s)
    return list(tops.values())

def prepare(output):
    if not output.resolve().is_relative_to(ROOT) or output.exists():raise ValueError('Fresh repository-owned output required')
    units=original_units(WORLD)
    views=[
      ('highest_floor_nerv',[39.5,-415.,337.5],[30.5,-421.,325.5],[[19,-424,310],[41,-408,341]],'structure'),
      ('highest_ceiling_tree',[30.5,-420.,315.5],[30.5,-410.,332.5],[[19,-424,310],[41,-407,341]],'structure'),
      ('seele_bright',[47.5,-457.,306.5],[34.5,-456.,308.5],[[16,-458,300],[51,-449,315]],'structure'),
      ('seele_dark',[47.5,-457.,306.5],[34.5,-456.,308.5],[[16,-458,300],[51,-449,315]],'structure'),
      ('wet_unit00_bridge',[57.5,-622.,305.5],[72.5,-630.,320.5],[[54,-681,302],[92,-599,373]],'structure'),
      ('wet_unit01_bridge',[15.5,-622.,305.5],[30.5,-630.,320.5],[[12,-681,302],[50,-599,373]],'structure'),
      ('wet_unit02_bridge',[-26.5,-622.,305.5],[-11.5,-630.,320.5],[[-30,-681,302],[8,-599,373]],'structure'),
      ('bank1_serial_and_launch',[-24.5,-623.,155.5],[30.5,-632.,124.276],[[-32,-653,87],[94,-575,170]],'guide'),
      ('bank2_serial_and_launch',[-24.5,-623.,-297.5],[30.5,-632.,-328.724],[[-32,-653,-366],[94,-575,-283]],'guide'),
      ('bank3_serial_and_launch',[-24.5,-623.,-750.5],[30.5,-632.,-781.724],[[-32,-653,-819],[94,-575,-736]],'guide'),
      ('far_yashima_ridge',[-1460.,240.,-1510.],[-1240.,174.,-1400.],[[-1620,70,-1780],[-1040,210,-1220]],'surface'),
      ('artificial_lake_corner_inverse',[-160.,-310.,340.],[-90.,-455.,180.],[[-296,-510,18],[100,-382,449]],'lake'),
      ('artificial_lake_inverse_close',[-95.,-430.,210.],[-30.,-480.,265.],[[-110,-510,210],[30,-464,322]],'lake'),
      ('reservoir_inspection_walk',[-86.,-455.,51.],[-105.,-475.,20.],[[-155,-487,12],[-17,-460,137]],'surface'),
      ('retired_old_hangar_recovery',[30.5,-397.,100.5],[30.5,-440.,-80.],[[-48,-470,-170],[115,-335,138]],'surface'),
      ('surface_roads_mountains',[-400.,126.,710.],[-320.,81.,790.],[[-560,60,590],[-220,180,910]],'surface'),
      ('original_surface_station',[-349.5,84.,745.5],[-360.5,82.,730.5],[[-380,70,710],[-330,120,760]],'structure'),
      ('command_bridge',[45.5,-495.,269.5],[30.5,-499.,280.5],[[3,-502,248],[62,-479,309]],'structure'),
      ('headquarters_underground_station',[31.5,-556.,438.5],[31.5,-559.,459.5],[[-5,-563,428],[66,-532,489]],'structure'),
      ('terminal_dogma_below_hangar',[25.5,-841.,302.5],[30.5,-868.,348.5],[[-34,-926,240],[96,-795,400]],'structure'),
      ('airport_road_repaired_intersection',[405.5,139.,169.5],[388.5,78.,105.5],[[337,64,89],[468,94,121]],'surface'),
      ('west_restored_mountain',[-2120.,280.,707.],[-2140.,150.,748.],[[-2304,60,720],[-1969,260,760]],'surface'),
      ('natural_transition_6114',[390.,125.,-272.],[371.,69.,-230.],[[340,50,-268],[415,105,-187]],'surface'),
      ('natural_transition_7670_7849',[363.,155.,882.],[337.,78.,837.],[[295,50,777],[387,145,922]],'surface'),
      ('natural_transition_8169',[371.,150.,1050.],[344.,79.,1014.],[[290,55,991],[405,115,1032]],'surface'),
      ('natural_transition_8801',[94.,170.,1234.],[70.,80.,1273.],[[39,55,1235],[96,155,1305]],'surface'),
      ('natural_transition_9222',[1409.,155.,1327.],[1415.,85.,1350.],[[1390,50,1328],[1438,130,1375]],'surface'),
      ('natural_transition_10621',[288.,150.,1622.],[278.,68.,1642.],[[250,55,1622],[310,130,1665]],'surface')
    ]
    rows=[]
    for name,position,target,bounds,kind in views:
        low,high=map(tuple,bounds)
        if kind in ('structure','guide'):
            cells=list(read_box(WORLD,DIM,low,high,namespace='projectseele').items())
            if not cells:raise ValueError('No actual facility landmark cells: '+name)
        else:cells=sampled_surface(WORLD,low,high)
        sections=sorted({(x//16,y//16,z//16) for (x,y,z),s in cells if max(abs(x-position[0]),abs(z-position[2]))<=352})
        if not sections or len(sections)>8192:raise ValueError((name,'Bounded actual landmark sections required',len(sections)))
        eye=[position[0],position[1]+1.62,position[2]]
        eyeCell=tuple(math.floor(n) for n in eye)
        eyeState=read_box(WORLD,DIM,eyeCell,eyeCell).get(eyeCell,'UNREAD')
        targetCell=tuple(math.floor(n) for n in target)
        # Real floor/wall anchors may be farther than3m from a corridor centre.
        near=read_box(WORLD,DIM,tuple(n-12 for n in targetCell),tuple(n+12 for n in targetCell))
        candidates=[(q,s) for q,s in near.items() if s.split('[')[0] not in AIR]
        if not candidates:candidates=cells
        anchors=[{'position':list(q),'state':s} for q,s in sorted(candidates,key=lambda r:sum((r[0][i]-target[i])**2 for i in range(3)))[:6]]
        if name.startswith('highest'):
            for q,t in iter_block_entities(WORLD,DIM,(15,-438,307),(46,-399,345)):
                if str(t.get('id',''))!='projectseele:wall_artwork':continue
                fields={k:{'type':kind,'value':str(t[k]) if kind=='string' else int(t[k]) if kind in ('int','long') else float(t[k])} for k,kind in [('Artwork','string'),('SurfaceFacing','string'),('Facing','int'),('Tint','int'),('Width','float'),('Height','float')] if k in t}
                anchors.append({'position':list(q),'state':'projectseele:wall_artwork','block_entity_fields':fields})
        row={'name':name,'position':position,'target':target,'eye_cell':list(eyeCell),'source_eye_state':eyeState,'landmark_bounds':bounds,'required_sections':[list(s) for s in sections],'required_blocks':anchors,'native_capture_valid':False,'needs_camera_adjustment':eyeState.split('[')[0] not in AIR,'section_coverage':'All actual facility-material sections inside the declared box' if kind in ('structure','guide') else 'Exact current16m-spaced top-surface columns; unsampled/underwater areas are outside this coverage'}
        if kind=='guide':row['guide_bounds']=[low[0],-650,low[2],high[0],-602,high[2]]
        if name.startswith('wet'):
            row['mechanical_scope']='Original full carrier/gantry and wet bay; new static launch guide is covered by the three bank views'
            row['required_entities']=[units[int(name[len('wet_unit'):len('wet_unit')+2])]]
        if name.startswith('seele'):
            light=json.loads((WORLD/'r48_seele_lighting.json').read_text())
            button=light['button'] # current coordinates; translation is provenance only
            row.update(seele_meeting_mode=name=='seele_dark',seele_button=button,seele_use_stand=[19.5,button[1]-1,button[2]+.5])
            row['required_blocks']=[b for b in anchors if not b['state'].startswith('minecraft:light[')]
            row['dynamic_required_blocks']=[]
            for group in ('ambient','table'):
                for q in light[group]:
                    current=read_box(WORLD,DIM,tuple(q),tuple(q)).get(tuple(q),'UNREAD')
                    if not current.startswith('minecraft:light['):raise ValueError(('Actual lighting circuit cell missing',q,current))
                    level=14 if name=='seele_bright' else 0 if group=='ambient' or light.get('meeting_all_block_lights_zero_r49') else 14 if q[0]==34 else 12
                    import re
                    row['dynamic_required_blocks'].append({'position':q,'state':re.sub(r'level=\d+','level='+str(level),current)})
        if not row['required_blocks']:raise ValueError('Real source anchors required: '+name)
        rows.append(row)
        print(name,len(sections),'sections',eyeState,'anchors',len(row['required_blocks']),flush=True)
    report={'schema':'projectseele.r52.final-art-camera-source.v1','source_world':str(WORLD),'game_started':False,'world_written':False,'client_copied':False,'world_copied':False,'views':rows,'source_inputs':{str(p):sha(p) for p in [WORLD/'r52/headquarters.json',WORLD/'r52/travel.json',WORLD/'r47_seele_conference.json',WORLD/'r48_seele_lighting.json',GROUND]},'final_build_receipt_required':True,'jar_sha256':None,'render_distance_chunks':24,'rule':'Final immutable BUILD_RECEIPT protocol70/current compiled class and asset pins. Source/QA exact block and artwork NBT anchors must match before launch. Original EVA UUID/variant/current bay position must exist on the actual client. No C8 images qualify.','limits':'This is a bounded photo plan. Entity and asset-cache presence cannot prove a complete same-frame EVA model draw; Root must review actual pixels. Native camera/frustum/mesh/GPU readiness and visual review remain pending. Coverage is clipped to352m horizontally from the actual camera. The bank views cover each bank entrance and launch connection, not proof of the entire serial route.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report
def main():
    global GROUND
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=DEFAULT)
    ap.add_argument('--ground',type=Path,default=GROUND,help='Actual final continuous directory; never silently use retired61c9')
    a=ap.parse_args();GROUND=a.ground.resolve()
    prepare(a.output.resolve());print(a.output.resolve())
if __name__=='__main__':main()
