"""Independently check a regional station's saved cells and pedestrian goals."""
import argparse,json
from collections import deque
from pathlib import Path
import nbtlib
import numpy as np
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT
from plan_hakone_station_inventory import Reader
from map_pipeline.station_validation import station_preflight

def verify(candidate,authority,write=True,mode='registered'):
    if mode not in ('offline-preflight','registered'):raise ValueError('Unknown station validation mode')
    m=json.loads((candidate/'manifest.json').read_text('utf8'));d=json.loads((candidate/'station-design.json').read_text('utf8'))
    e=Editor(candidate);errors=[];cells=0;changed_public=0;changed_water=0;outside=0;foreign=[]
    source_allowed=SOIL|AIR|{'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:light'}
    boxes=[r['bounds']for r in d['parts']if 'bounds'in r];columns={}
    for r in d['parts']:
        for x,z,g in r.get('columns',[]):columns[x,z]=((g+1)//2-2,(g+1)//2+3)
    with np.load(authority/'network.npz')as f:
        ax,az,aX,aZ=map(int,f['bounds']);oldwalk=f['walk'];oldgrade=f['grade2']
    protected={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(candidate/'captured-devices.dat')['Devices']}
    changed_devices=[]
    for file in sorted((candidate/'source').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        for(cx,cz),before,after in zip(r['coords'],r['before'],r['after']):
            for iy,iz,ix in np.argwhere(before!=after):
                x,y,z=int(cx)*16+int(ix),int(iy)-128,int(cz)*16+int(iz);cells+=1
                b=r['names'][int(before[iy,iz,ix])];a=r['names'][int(after[iy,iz,ix])]
                if b.split('[')[0]not in source_allowed:foreign.append([x,y,z,b])
                if(x,y,z)in protected:changed_devices.append([x,y,z])
                if ax<=x<=aX and az<=z<=aZ and oldwalk[z-az,x-ax]:changed_public+=1
                if b.startswith('minecraft:water')or a.startswith('minecraft:water'):changed_water+=1
                in_box=any(q[0]<=x<=q[3]and q[1]<=y<=q[4]and q[2]<=z<=q[5]for q in boxes)
                if not in_box and not((x,z)in columns and columns[x,z][0]<=y<=columns[x,z][1]):outside+=1
        e.regions.clear()
    if cells!=m['cells']:errors.append(['manifest-cell-count',cells,m['cells']])
    for label,value in [('original-public-columns-modified',changed_public),('water-modified',changed_water),('outside-declared-station-volume',outside),('original-device-modified',len(changed_devices)),('unowned-source-material',len(foreign))]:
        if value:errors.append([label,value])
    floors=PAVEMENT|{'projectseele:station_tactile_warning','projectseele:station_tactile_path','projectseele:period_station_floor'}
    nodes={};floor_errors=[];head_errors=[]
    for x,z,grade in d['public_columns']:
        y=(grade+1)//2;floor=e.state(x,y,z);name=floor.split('[')[0]
        expected_slab=grade%2!=0
        if name not in floors or name.endswith('_stairs')or expected_slab!=('type=bottom'in floor):
            floor_errors.append([x,y,z,grade,floor]);continue
        body=[e.state(x,Y,z)for Y in(y+1,y+2)]
        if any(s.split('[')[0]not in AIR|{'minecraft:light'}for s in body):head_errors.append([x,y,z,body]);continue
        nodes[x,grade+2,z]=None
    if floor_errors:errors.append(['public-floor-height',len(floor_errors)])
    if head_errors:errors.append(['public-headroom',len(head_errors)])
    start=tuple(int(round(v*2))if i==1 else int(v)for i,v in enumerate(d['retained_street_anchor']))
    parents={start:None}if start in nodes else{};queue=deque(parents)
    while queue:
        x,y,z=queue.popleft()
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            for dy in(0,1,-1):
                q=x+dx,y+dy,z+dz
                if q in nodes and q not in parents:parents[q]=(x,y,z);queue.append(q)
    if len(parents)!=len(nodes):errors.append(['unreachable-public-columns',len(nodes)-len(parents)])
    routes=[]
    for name,p in d['goals'].items():
        goal=(int(p[0]),round(p[1]*2),int(p[2]));path=[];q=goal
        if q not in parents:errors.append(['unreachable-station-goal',name,p])
        else:
            while q is not None:path.append([q[0]+.5,q[1]/2,q[2]+.5]);q=parents[q]
            path.reverse()
        routes.append(dict(name=name,reachable=bool(path),path=path))
    plan=json.loads((candidate/'native-station-plan.json').read_text('utf8'))
    preflight=station_preflight(candidate,d,plan);errors.extend(preflight['errors'])
    clearance=preflight['rail_clearance_bounds']
    rail_obstacles=[]
    if clearance is not None:
        for x in range(clearance[0],clearance[3]+1):
            for z in range(clearance[2],clearance[5]+1):
                for y in range(clearance[1],clearance[4]+1):
                    state=e.state(x,y,z)
                    if state.split('[')[0]not in AIR|{'minecraft:light'}:rail_obstacles.append([x,y,z,state])
    if rail_obstacles:errors.append(['station-track-clearance',len(rail_obstacles)])
    expected_signs={tuple(r['pos']):r['title']for r in d['expected_signs']}if 'expected_signs'in d else{(2526,-68,-1181):'和田河原駅',(2519,-69,-1174):'きっぷ',(2540,-69,-1163):'和田河原'}
    if len(expected_signs)!=3 or d['station']not in expected_signs.values():errors.append(['station-sign-design'])
    actual_signs={}
    for row in nbtlib.load(candidate/'block-entities.dat')['Changes']:
        tag=row.get('After');pos=tuple(int(tag[k])for k in('x','y','z'))if tag else None
        if pos in actual_signs:errors.append(['duplicate-station-sign',pos]);continue
        actual_signs[pos]=tag
    if set(actual_signs)!=set(expected_signs):errors.append(['station-sign-payload-set'])
    for pos,title in expected_signs.items():
        tag=actual_signs.get(pos)
        if tag is None:continue
        state=e.state(*pos)
        text=json.loads(str(tag['front_text']['messages'][0])).get('text')
        if str(tag['id'])!='minecraft:sign'or not state.startswith('minecraft:oak_wall_sign[')or text!=title:
            errors.append(['station-sign-payload',list(pos)])
    native=candidate/'native-station/native-station-proof.json';native_ok=False
    if native.exists()and len(plan.get('rails',[]))==1:
        pa,pb=plan['rails'][0]['from'],plan['rails'][0]['to']
        proof=json.loads(native.read_text('utf8'))
        native_ok=proof['existing_loaded_objects_exact']and abs(proof['platform_length']-48)<1e-7 and len(proof['members'])==3
        if set(proof['members'])!=set(m.get('native_additions',[])):native_ok=False
        decoded={Path(name).parts[3]:Reader((candidate/'after'/name).read_bytes()).read()for name in proof['members']}
        if decoded['stations']['name']!=d['station']or decoded['platforms']['name']!='1':native_ok=False
        if decoded['rails']['position1']!=dict(zip(('x','y','z'),pa))or decoded['rails']['position2']!=dict(zip(('x','y','z'),pb)):native_ok=False
        if any(decoded['platforms'][k]!=decoded['rails'][k]for k in('position1','position2')):native_ok=False
    pending=[]if native_ok else['native-station-registration']
    if not native_ok and mode=='registered':errors.append(['native-station-registration-unverified'])
    report=dict(errors=errors,changed_cells=cells,public_columns=len(nodes),reachable_public_columns=len(parents),
        floor_errors=floor_errors,head_errors=head_errors,destinations=routes,changed_original_public_cells=changed_public,
        original_device_cells_changed=changed_devices,unowned_material_examples=foreign[:20],
        changed_water_cells=changed_water,rail_obstacles=rail_obstacles,native_station_registration_verified=native_ok,
        validation_mode=mode,pending=pending,preflight=preflight,
        offline_preflight_passed=not any(row[0]!='native-station-registration-unverified'for row in errors),
        registered_validation_passed=mode=='registered'and not errors and native_ok,
        planned_maximum_consist_length=d.get('planned_maximum_consist_length',40),native_platform_length=preflight['platform_length'],maximum_pedestrian_step=.5,
        through_service_complete=False,world_written=False,game_ui_verified=False)
    if write:
        output='station-preflight-check.json'if mode=='offline-preflight'else'station-independent-check.json'
        (candidate/output).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
        if mode=='registered':
            (candidate/'functional-check.json').write_text(json.dumps(dict(errors=errors,station=d['station'],world_written=False),ensure_ascii=False,indent=2),'utf8')
    print('Independent station:',cells,'changes;',len(nodes),'public columns;',len(parents),'reachable; errors',errors,flush=True)
    return report

def require_verified(candidate):
    m=json.loads((candidate/'manifest.json').read_text('utf8'))
    if m.get('kind')!='measured-regional-station':return
    check=json.loads((candidate/'station-independent-check.json').read_text('utf8'))
    release=json.loads((candidate/'station-release-check.json').read_text('utf8'))
    if check.get('validation_mode','registered')!='registered'or check.get('native_station_registration_verified')is not True or check['errors']or check['changed_cells']!=m['cells']or check['reachable_public_columns']!=check['public_columns']:
        raise ValueError('Unverified station geometry')
    required=('production_recipe_replay_passed','identity_snapshot_ready','native_station_registration_verified',
        'exact_voxel_views_reviewed','negative_fault_checks_passed','no_new_floating_components','current_native_source_exact')
    if not all(release.get(k)is True for k in required):raise ValueError('Station release requirements incomplete')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--authority',type=Path,required=True)
    p.add_argument('--mode',choices=('offline-preflight','registered'),default='registered')
    p.add_argument('--no-write',action='store_true',help='Inspect offline files without replacing saved reports')
    a=p.parse_args()
    if verify(a.candidate,a.authority,write=not a.no_write,mode=a.mode)['errors']:raise SystemExit(1)
