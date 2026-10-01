"""Current full-width road structure, terrain edges, interfaces and virtual rails.

Road authority is the measured R20/R02 contracts, not discovered air. Complete
station and railway volumes remain separate owners. No world is written.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,json,time,math,hashlib
import numpy as np
from scipy.spatial import cKDTree
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/surface_network'
CONTRACTS=[ROOT/'artifacts/world_rebuild_r20/road_actual/extension_contract_final.npz',ROOT/'artifacts/world_rebuild_r20/road_actual/road_contract_final.npz']
FLOORS={'minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone','minecraft:polished_blackstone_slab','minecraft:quartz_slab','minecraft:smooth_stone_slab','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}

def catalogue(revisions=(),additional=()):
    cells={};sources=[]
    for p in CONTRACTS:
        a=np.load(p);ox,oz=map(int,a['origin']);mask=a['mask'];heights=a['height2'];carriage=a['carriage'];name=str(p)
        sources.append(dict(path=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),columns=int(mask.sum()),origin=[ox,oz]))
        for iz,ix in zip(*np.nonzero(mask)):
            cells[int(ix+ox),int(iz+oz)]=(int(heights[iz,ix]),bool(carriage[iz,ix]),name)
    for manifest in additional:
        path=Path(manifest);data=json.loads(path.read_text('utf8'))
        for row in data['columns']:cells[tuple(row['pos'])]=(row['height2'],row['carriage'],row['source_id'],row.get('native_feet'))
        sources.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),columns=len(data['columns']),role='Explicit authored later road surfaces; native physical comparison remains required'))
    for revision in revisions:
        path=Path(revision);delta=json.loads(path.read_text('utf8'))
        for row in delta['columns']:
            key=tuple(row['pos']);old=cells[key]
            if old[0]!=row['before_height2']:raise RuntimeError('Road authority revision does not match its frozen predecessor: '+str(row))
            cells[key]=(row['after_height2'],old[1],str(path))
        sources.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),columns=len(delta['columns']),role='Explicit complete-component authority successor; physical comparison still required'))
    return cells,sources

def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=0);p.add_argument('--out',type=Path,default=OUT/'road_structure_vehicle_before.json');p.add_argument('--road-revision',type=Path,action='append',default=[]);p.add_argument('--bounds',type=int,nargs=4);p.add_argument('--additional-authority',type=Path,action='append',default=[]);args=p.parse_args();args.out.parent.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    roads,sources=catalogue(args.road_revision,args.additional_authority);keys=sorted(roads)
    if args.bounds:
        x0,z0,x1,z1=args.bounds;keys=[q for q in keys if x0<=q[0]<=x1 and z0<=q[1]<=z1]
    print('Whole road authority catalogue',len(keys),'columns',flush=True)
    if args.limit:keys=keys[:args.limit]
    shapes={canonical_state(k):v for k,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    native=json.loads((ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json').read_text('utf8'))
    rails=np.asarray([q for curve in native['curves'] if curve['mode']=='TRAIN' for q in curve['points'] if q[1]>=0],float)
    railtree=cKDTree(np.floor(rails[:,[0,2]]))
    regions=defaultdict(list)
    for x,z in keys:regions[x//512,z//512].append((x,z))
    unknown=Counter();issues=[];crossings=[];edges=[];heights={};counts=Counter()
    coordinates=np.empty((len(keys),2),np.int32);expected_height2=np.empty(len(keys),np.int16)
    actual_feet=np.full(len(keys),np.nan,np.float32);column_flags=np.zeros(len(keys),np.uint16)
    def boxes(state):
        if state is None:return None
        if state.partition('[')[0] in AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:dandelion','minecraft:poppy','minecraft:cornflower'}:return []
        result=shapes.get(state)
        if result is None:unknown[state]+=1
        return result
    for region,points in sorted(regions.items()):
        print('Loading complete road region',region,'columns',len(points),flush=True)
        w=MeasuredWorld(WORLD)
        for x,z in points:
            y=(roads[x,z][0]-1)//2;w.box((x-1,y-16,z-1),(x+1,y+8,z+1))
        w.load()
        print('Native road sections loaded',len(w.tiles),'for',region,flush=True)
        def bearing(x,z,feet):
            for y in range(math.floor(feet),math.floor(feet)-18,-1):
                shape=boxes(w.get(x,y,z))
                if shape is None:return None
                tops=[y+b[4] for b in shape if b[0]<=.5<=b[3] and b[2]<=.5<=b[5] and y+b[4]<=feet+.001]
                if tops:return max(tops)
            return feet-18
        def clear_at(x,z,feet,height=1.8):
            for y in range(math.floor(feet),math.ceil(feet+height)):
                shape=boxes(w.get(x,y,z))
                if shape is None:return None
                if any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and y+b[1]<feet+height and y+b[4]>feet+.001 for b in shape):return False
            return True
        for x,z in points:
            feet=roads[x,z][3] if len(roads[x,z])>3 and roads[x,z][3] is not None else roads[x,z][0]/2;y=math.floor(feet-.001);state=w.get(x,y,z);counts['road_columns']+=1
            profile_index=counts['road_columns']-1;coordinates[profile_index]=x,z;expected_height2[profile_index]=roads[x,z][0]
            if roads[x,z][1]:column_flags[profile_index]|=16
            if counts['road_columns']%4096==0:print('Physical column',counts['road_columns'],'/',len(keys),flush=True)
            actual=bearing(x,z,feet)
            # A later named station plinth can stand half a block above the
            # obsolete road pin. Measure its native paving top, rather than
            # calling the lower cube face a floor and its upper half a roof.
            paving=boxes(state) if state and (state.partition('[')[0] in FLOORS or (len(roads[x,z])>3 and roads[x,z][3] is not None)) else []
            near=[y+b[4] for b in paving or [] if b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(y+b[4]-feet)<=.501]
            if near:
                actual=min(near,key=lambda value:abs(value-feet))
                if abs(actual-feet)>.01:counts['native_near_paving_top_refinements']+=1
            heights[x,z]=actual
            if actual is None or state is None:
                issues.append(dict(kind='UNMEASURED',pos=[x,feet,z],state=state));counts['unmeasured']+=1;continue
            actual_feet[profile_index]=actual;column_flags[profile_index]|=1
            if abs(actual-feet)<=.01:column_flags[profile_index]|=2
            if abs(actual-feet)>.01:
                issues.append(dict(kind='ROAD_FLOOR_DATUM',pos=[x,feet,z],actual=actual,source=roads[x,z][2],floor=state));counts['floor_datum']+=1
            physical_feet=actual if actual is not None and abs(actual-feet)<=.501 else feet
            clearance=clear_at(x,z,physical_feet)
            if clearance is True:column_flags[profile_index]|=4
            if clearance is not True:
                issues.append(dict(kind='HEAD_CLEARANCE' if clearance is False else 'UNKNOWN_CLEARANCE',pos=[x,feet,z],native_near_paving_feet=physical_feet,states=[w.get(x,yy,z) for yy in range(math.floor(physical_feet),math.ceil(physical_feet+1.8))]));counts['clearance']+=1
            if roads[x,z][1]:
                vehicle=clear_at(x,z,physical_feet,6)
                if vehicle is True:column_flags[profile_index]|=8
                counts['carriage_columns']+=1
                if vehicle is not True:
                    issues.append(dict(kind='VEHICLE_CLEARANCE' if vehicle is False else 'UNKNOWN_VEHICLE_CLEARANCE',pos=[x,feet,z],native_near_paving_feet=physical_feet,required=6,states=[w.get(x,yy,z) for yy in range(math.floor(physical_feet),math.ceil(physical_feet+6))]));counts['vehicle_clearance']+=1
            # Separate paving from the supporting component underneath it.
            below=bearing(x,z,y+.001)
            if below is not None and below<y-.01:
                column_flags[profile_index]|=32
                issues.append(dict(kind='DECK_SUPPORT_REVIEW',pos=[x,feet,z],underside_gap=y-below,state=state,interpretation='Bridge/cantilever or unsupported road; explicit component/pier purpose must decide, never fill blindly'));counts['support_review']+=1
            close=railtree.query_ball_point([x,z],4.25)
            exact=[i for i in close if abs(math.floor(rails[i,0])-x)<=3 and abs(math.floor(rails[i,2])-z)<=3]
            if exact:
                low=float(rails[exact,1].min());high=float(rails[exact,1].max());body=6 if roads[x,z][1] else 1.8
                conflicts=[i for i in exact if rails[i,1]-3<feet+body-.001 and rails[i,1]+8>feet-1]
                if conflicts:column_flags[profile_index]|=256
                crossings.append(dict(pos=[x,feet,z],rail_y=[low,high],clear_above=low-3-feet,road_kind='carriage' if roads[x,z][1] else 'pedestrian',required_clearance=body,
                    status='RAILWAY_ROAD_SWEPT_ENVELOPE_REVIEW' if conflicts else 'SEPARATED_NATIVE_CURVE_HEIGHT',
                    envelope_policy='R23 measured bridge underside railY-3; virtual train body to railY+8; complete 7x7 sampled floor footprint'))
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                if (x+dx,z+dz) in roads:continue
                neighbour=bearing(x+dx,z+dz,feet)
                if neighbour is None:edges.append(dict(pos=[x,feet,z],normal=[dx,0,dz],status='UNMEASURED_EDGE'));continue
                if neighbour<feet-.6:
                    column_flags[profile_index]|=64
                    protected=clear_at(x+dx,z+dz,feet) is False
                    if not protected:column_flags[profile_index]|=128
                    edges.append(dict(pos=[x,feet,z],normal=[dx,0,dz],drop=feet-neighbour,side_state=w.get(x+dx,math.floor(feet),z+dz),
                        status='EXISTING_EDGE_BARRIER_COMPONENT_REVIEW' if protected else 'OPEN_ROAD_TERRAIN_DROP',interpretation='Roadside slope/bank/shore/bridge edge; whole section required'))
        print('Road region',region,'measured',counts['road_columns'],'/',len(keys),flush=True)
    jumps=[]
    for x,z in keys:
        a=heights.get((x,z))
        if a is None:continue
        for dx,dz in ((1,0),(0,1),(1,1),(1,-1)):
            b=heights.get((x+dx,z+dz))
            if b is not None and abs(a-b)>.501:jumps.append(dict(from_pos=[x,a,z],to_pos=[x+dx,b,z+dz],rise=abs(a-b)))
    profile_path=args.out.with_suffix('.columns.npz')
    np.savez_compressed(profile_path,coordinates=coordinates,expected_height2=expected_height2,actual_feet=actual_feet,flags=column_flags)
    report=dict(world=str(WORLD),authority_sources=sources,measured_columns=len(keys),full_authority_columns=len(roads),
        exact_measured_column_profiles=str(profile_path),column_profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        profile_flags={'measured_floor':1,'exact_authored_datum':2,'native_player_clear':4,'native_six_metre_vehicle_clear':8,'authored_carriage':16,'support_component_pending':32,'exterior_drop':64,'unguarded_drop':128,'virtual_rail_sweep_conflict':256},
        inherited_native_curve_source='R43 resolved installed MTR curves; virtual rails are not block absence',counts=dict(counts),unknown_shapes=dict(unknown),
        physical_floor_issues=issues,all_width_height_jumps=jumps,road_terrain_edges=edges,road_rail_interfaces=crossings,
        station_port_scope='Current named station entrance/foyer/boarding contract belongs to transit reviewer; road-side ports must be reconciled next',
        world_changed=False,native_player_and_vehicle_passed=False,visual_passed=False,seconds=time.monotonic()-started,
        scope='All road-mask widths, actual collision headroom, actual support below paving, all four exterior edges, eight-neighbour grades and virtual 3D railway curves; review is not repair/approval')
    args.out.write_text(json.dumps(report,ensure_ascii=False),'utf8')
    print({k:v if k not in ('physical_floor_issues','all_width_height_jumps','road_terrain_edges','road_rail_interfaces') else len(v) for k,v in report.items() if k not in ('authority_sources','scope','unknown_shapes')},flush=True)

if __name__=='__main__':main()
