"""Review current three-port walking and native stopped-boat interfaces offline.

Never edits water, piers, boats or native traffic. The cached native stop evidence
is joined to an exact later cold native snapshot, and unknown blocks are retained
as unresolved. This does not replace a live passenger boarding test.
"""
import argparse,json,math
from collections import deque
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,box
import audit_mountain_station_access as walk
from check_hakone_boat_clearance import swept_columns
from plan_hakone_station_inventory import Reader

def differences(a,b,path=''):
    if type(a)!=type(b):return [dict(path=path,before=a,after=b)]
    if isinstance(a,dict):
        result=[]
        for key in a.keys()|b.keys():
            if key not in a or key not in b:result.append(dict(path=path+'/'+key,kind='member_added_or_removed'))
            else:result+=differences(a[key],b[key],path+'/'+key)
        return result
    if isinstance(a,list):
        if len(a)!=len(b):return [dict(path=path,kind='list_length_changed')]
        return [r for i,(x,y)in enumerate(zip(a,b))for r in differences(x,y,path+'/'+str(i))]
    return []if a==b else[dict(path=path,before=a,after=b)]

def reachable(nav,start):
    q=nav.nearest_goal(start);seen={q}if q else set();queue=deque(seen)
    while queue:
        a=queue.popleft()
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            for b in nav.column.get((a[0]+dx,a[2]+dz),[]):
                if b not in seen and nav.edge(a,b):seen.add(b);queue.append(b)
    return seen

def run(a):
    a.out.mkdir(parents=True,exist_ok=True)
    reader=walk.SupplementedSections(a.source,a.supplement)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    # SlabBlock collision is material-independent. Explicitly record this alias
    # rather than assuming the unexported spruce state is empty.
    spruce='minecraft:spruce_slab[type=bottom,waterlogged=false]'
    smooth='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
    shapes[spruce]=shapes[smooth];walk.FLOORS=walk.FLOORS|{'minecraft:spruce_slab'}
    installed=json.loads((a.installed/'manifest.json').read_text('utf8'))
    circuit=json.loads((a.installed/'native-circuit.json').read_text('utf8'))
    model=json.loads(a.model.read_text('utf8'));samples=json.loads(a.samples.read_text('utf8'))
    native_rows=[]
    for file in sorted((a.installed/'after/mtr').rglob('*')):
        if not file.is_file():continue
        relative=file.relative_to(a.installed/'after/mtr');current=a.native/relative
        exact=current.is_file()and current.read_bytes()==file.read_bytes();changes=[]
        if not exact:
            if not current.is_file():raise ValueError('Missing retained boat native member')
            changes=differences(Reader(file.read_bytes()).read(),Reader(current.read_bytes()).read())
            allowed={'/vehicles/0/elapsedDwellTime','/vehicles/0/railProgress','/vehicles/0/speed'}
            if relative.parts[2]!='sidings' or any(r['path']not in allowed for r in changes):
                raise ValueError('Retained boat geometry or service changed')
        native_rows.append(dict(member=relative.as_posix(),exact=exact,allowed_running_state_changes=changes))
    if not native_rows:raise ValueError('No retained boat native evidence')
    specs=[
        dict(id='motohakone',name='元箱根港',bounds=[475,95,1998,568,116,2059],start='ticket_hall',
             goals={'ticket_hall':[531,101,2029],'landward_entrance':[537,101,2030],
                    'forecourt':[553,101,2029],'street':[560,102,2033],
                    'bus_north':[540,101,1998],'bus_middle':[540,101,2015],'bus_south':[540,101,2032],
                    'main_pier':[500,101,2018],'low_boarding_landing':[493,100,2018]}),
        dict(id='hakonemachi',name='箱根町港',bounds=[350,95,2280,436,117,2399],start='ticket_hall',
             goals={'ticket_hall':[402,101,2342],'landward_entrance':[401,101,2348],
                    'forecourt':[407,101,2366],'street':[405,101,2367],
                    'bus_north':[417,101,2356],'bus_middle':[417,101,2373],
                    'bus_south':[417,101,2390],'main_pier':[398,101,2297],'low_boarding_landing':[391,100,2292]}),
        dict(id='togendai',name='桃源台港',bounds=[-323,95,1017,-249,107,1100],start='boat_hall',
             goals={'boat_hall':[-286,101,1025],'gangway':[-286,101,1045],
                    'main_pier':[-286,101,1078],'low_boarding_landing':[-303,100,1084]})]
    rows=[]
    for spec in specs:
        nav=walk.Nav(reader,spec['bounds'],shapes,True);routes,count=nav.routes(spec['goals'],spec['start'])
        seen=reachable(nav,spec['goals'][spec['start']]);low_deck=[(x,z)for x,y,z in seen if y==200]
        stops=[]
        for stop in circuit['stops']:
            centre=np.asarray(stop['bogies']).mean((0,1))
            key='togendai'if centre[0]<0 else'motohakone'if centre[0]>450 else'hakonemachi'
            if key!=spec['id']:continue
            bogies=np.asarray(stop['bogies'][0]);forward=(bogies[0]-bogies[1])[[0,2]];forward/=np.linalg.norm(forward)
            normal=np.asarray([-forward[1],forward[0]]);c=centre[[0,2]]
            contacts=[]
            for sign in(-1,1):
                doorway=Polygon([c+normal*sign*w+forward*l for w,l in((1.125,-1),(1.5,-1),(1.5,1),(1.125,1))])
                choices=[(doorway.distance(box(x,z,x+1,z+1)),x,z)for x,z in low_deck]
                contacts.append(min(choices)if choices else None)
            valid=[r for r in contacts if r is not None];best=min(valid)if valid else None
            stops.append(dict(centre=centre.tolist(),doorway_y=float(centre[1]+1),
                connected_deck_height=100,door_to_current_connected_deck_gap=best[0]if best else None,
                nearest_connected_deck=[best[1],100,best[2]]if best else None,
                geometric_contact_verified=bool(best and best[0]<=.15),live_boarding_verified=False))
        platform=[r for r in samples if r['id']==spec['id']+'-boat']
        if len(platform)!=1:raise ValueError('Missing exact platform sample')
        checked=[];obstructions=[];unknown=[]
        lo=math.floor(99+model['visual_bounds'][0][1])
        hi=math.ceil(99+max(model['visual_bounds'][1][1],max(p['hi'][1]for p in model['parts']if p['kind']=='FLOOR')+1.8))-1
        for _,columns in swept_columns(platform,model['half_width'],model['half_length']):
            for x,z in sorted(columns):
                checked.append([x,z])
                for y in range(lo,hi+1):
                    state=reader.state(x,y,z)
                    if state is None:unknown.append([x,y,z]);continue
                    if state.split('[')[0]not in('minecraft:air','minecraft:cave_air','minecraft:water'):
                        obstructions.append([x,y,z,state])
        old_walk=next(r for r in installed['boarding_walks']if r['port']==spec['id'])
        retained_path=[]
        for x,y,z in old_walk['path']:
            q=(x,round(y*2),z);retained_path.append(dict(pos=[x,y,z],known_walkable=q in nav.nodes,reachable_from_hall=q in seen))
        rows.append(dict(**spec,current_paths=routes,reachable_paved_nodes=count,
            native_stopped_boat_contacts=stops,retained_boarding_path=retained_path,
            platform_hull_sweep=dict(columns=len(checked),checked_y=[lo,hi],obstructions=obstructions,unknown=unknown,
                model_source=str(a.model),visual_half_width=model['half_width'],visual_half_length=model['half_length'],
                full_line_clearance_claimed=False,current_model_resource_recheck_pending=True),
            unknown_block_queries=dict(nav.unknown),ordinary_wooden_doors_assumed_open=True,
            native_gates_bypassed=False,whole_station_accepted=False))
        print(spec['id'],'paths',[(r['name'],r['reachable'])for r in routes],
              'native platform hull',len(obstructions),'obstructions',len(unknown),'unknown',
              'door gaps',[s['door_to_current_connected_deck_gap']for s in stops],flush=True)
    report=dict(ports=rows,port_count=len(rows),world_written=False,water_modified=False,native_modified=False,
        retained_boat_native_members=len(native_rows),retained_native_members_exact=all(r['exact']for r in native_rows),
        exact_native_members=sum(r['exact']for r in native_rows),native_geometry_and_service_preserved=True,
        changed_running_state_only=[r for r in native_rows if not r['exact']],
        native_snapshot=str(a.native),current_geometry_source=str(a.source),supplement=str(a.supplement),
        vanilla_material_shape_equivalences={spruce:smooth},historical_collision_export=str(a.metadata),
        current_native_model_and_collision_validation_pending=True,live_passenger_boarding_pending=True)
    (a.out/'port-access-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('source','supplement','metadata','installed','native','model','samples','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
