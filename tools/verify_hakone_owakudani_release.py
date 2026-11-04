"""Independent readback gates for the finite two-level Owakudani station."""
import argparse,itertools,json,math,subprocess,zipfile
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from author_hakone_lakefront import Editor
from map_pipeline.native_geometry_patch import expected,decode
from map_pipeline.rail_civil_geometry import block_top
from verify_hakone_cable_station import CabinReserve,journeys
from verify_hakone_network_candidate import PAVEMENT
from query_blocks import AIR


def floating(folder):
    report=json.loads((folder/'floating-components.json').read_text('utf8'));cells=set()
    with np.load(folder/'r.0.1.npz')as f:indices=f['indices'].astype(np.int64);labels=f['labels']
    for row in report['components']:
        if row['unknown']:continue
        ids=[k for rx,rz,k in row['parts']if(rx,rz)==(0,1)]
        at=indices[np.isin(labels,ids)]
        cells.update(zip((at%512).tolist(),(at//262144-128).tolist(),((at//512)%512+512).tolist()))
    return cells,sum(r['unknown']for r in report['components'])


def verify(a):
    c=a.candidate;e=Editor(c);final,native=expected(c)
    design=json.loads((c/'station-design.json').read_text('utf8'))
    curves=json.loads((c/'plan/native-curves.json').read_text('utf8'))
    previous=json.loads((a.previous/'native-curves.json').read_text('utf8'))
    if curves['trains']!=previous['trains']or len(curves['ropeway'])!=len(previous['ropeway']):raise ValueError('Unrelated native curves changed')
    changed=[i for i,(p,q)in enumerate(zip(previous['ropeway'],curves['ropeway']))if p!=q]
    if changed!=[65,66,67,100,101,102,103,104,105]:raise ValueError('Unexpected cable curve changes')
    edits=json.loads((c/'station-edits.json').read_text('utf8'))
    for row in edits:
        p=row['pos']
        if e.state(*p)!=row['after']or e.state(*p,original=True)!=row['before']:raise ValueError(('Edited voxel readback',p))
    reserve=CabinReserve(curves,[250,804,300,854]);x,y,z,X,Y,Z=design['clearance_box'];checked=0
    for px in range(x,X+1):
        for pz in range(z,Z+1):
            for h in range(y,Y+1):
                s=e.state(px,h,pz);checked+=1
                if s.split('[')[0]in AIR|{'minecraft:light'}or s.startswith('mtr:'):continue
                if reserve.block((px,h,pz),s):raise ValueError(('Readback cabin obstruction',px,h,pz,s))
    access=journeys(e,reserve,design['goals'],[256,174,806,296,198,861])
    if access['errors']or len(access['journeys'])!=6:raise ValueError('Final passenger connection failed')
    # Boarding is checked against static blocks with a stopped car. Holding
    # areas and public circulation above remain outside the moving-car sweep.
    boarding=[]
    for name,target in [('west north platform',825),('west south platform',833),('east north platform',823),('east south platform',831)]:
        px,foot,pz=design['goals'][name];last=foot;route=[]
        for zz in range(pz,target+(1 if target>=pz else -1),1 if target>=pz else -1):
            options=[]
            for h in range(math.floor(foot)-2,math.ceil(foot)+1):
                s=e.state(px,h,zz)
                if s.split('[')[0]not in PAVEMENT:continue
                f=block_top(h,s)
                if abs(f-last)>.5:continue
                if any(e.state(px,q,zz).split('[')[0]not in AIR|{'minecraft:light'}for q in range(h+1,math.ceil(f+1.8))):continue
                options.append(f)
            if not options:raise ValueError(('Static boarding gap or obstruction',name,px,zz))
            last=min(options,key=lambda f:abs(f-last));route.append([px,last,zz])
        if abs(last-foot)>.5:raise ValueError('Boarding floor differs from car floor')
        boarding.append(dict(name=name,static_path=route,car_floor=foot,step_to_car=abs(last-foot)))
    old,old_unknown=floating(a.baseline_components);new,new_unknown=floating(a.components)
    if new-old or new_unknown!=old_unknown:raise ValueError('New floating component or changed unknown coverage')
    owners=[]
    for name,raw in final.items():
        if '/sidings/'not in name:continue
        row=decode(raw)[0].value
        if row.get('transportMode')!='CABLE_CAR':continue
        ids=[r['vehicleId']for r in row['vehicleCars']]
        if ids!=['ngong_ping_360_normal_red_lht']:raise ValueError('Assigned cabin model differs')
        owners.append(row['name'])
    if len(owners)!=2:raise ValueError('Expected two original cable services')
    measured=[]
    with zipfile.ZipFile(a.mtr)as jar:
        for model,offset in [('ngong_ping_360',-5.),('cable_car_grip',.5)]:
            prop=json.loads(jar.read('assets/mtr/properties/vehicle/'+model+'_lht.json'))
            if prop['modelYOffset']!=offset:raise ValueError('Model offset changed')
            padding=max([abs(r.get('doorZMultiplier',0))/16 for r in prop['parts']]+[0])
            data=json.loads(jar.read('assets/mtr/models/vehicle/'+model+'.bbmodel'))
            for part in data['elements']:
                corners=np.array(list(itertools.product(*zip(part['from'],part['to']))),float)
                origin=np.array(part.get('origin',[0,0,0]));angle=part.get('rotation',[0,0,0]);vertices=[]
                for order in itertools.permutations('xyz'):
                    v=(Rotation.from_euler(''.join(order),[angle['xyz'.index(k)]for k in order],degrees=True).apply(corners-origin)+origin)/16
                    v[:,1]+=offset
                    for dz in(-padding,padding):
                        vv=v.copy();vv[:,2]+=dz;vertices.extend(vv)
                v=np.array(vertices);low,high=float(v[:,1].min()),float(v[:,1].max());radius=float(np.linalg.norm(v[:,[0,2]],axis=1).max())
                if low<reserve.TIERS[0][0]or high>reserve.TIERS[-1][1]:raise ValueError('Cabin vertical envelope exceeded')
                for bottom,top,r in reserve.TIERS:
                    if low<top and high>bottom and radius>r:raise ValueError(('Cabin radial envelope exceeded',part['name']))
                measured.append(dict(model=model,part=part['name'],low=low,high=high,radius=radius))
    subprocess.run([str(a.java),'-cp',str(a.mtr),str(a.repo/'tools/java/InspectCableMode.java')],check=True)
    report=dict(errors=[],edited_cells_read_back=len(edits),clearance_cells_checked=checked,changed_native_curves=changed,native=native,passenger_destinations=6,boarding=boarding,
                floating_cells_before=len(old),floating_cells_after=len(new),new_floating_cells=0,unknown_components=new_unknown,models=measured,owners=owners,game_ui_verification=False)
    (c/'cable-station-independent-check.json').write_text(json.dumps(report,indent=2),'utf8')
    manifest=json.loads((c/'manifest.json').read_text('utf8'));manifest['cable_station_verification']={'passenger_destinations':6,'boarding_edges':4}
    (c/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k not in('models','boarding','native')}),flush=True)


def require_verified(candidate):
    manifest=json.loads((candidate/'manifest.json').read_text('utf8'))
    operation=candidate/'native-geometry/operations.json'
    station_migration=operation.exists()and json.loads(operation.read_text('utf8')).get('migration_kind')=='cable_station_vertical'
    if 'cable_station_verification'not in manifest and not station_migration:return
    r=json.loads((candidate/'cable-station-independent-check.json').read_text('utf8'))
    if r['errors']or r['passenger_destinations']!=6 or len(r['boarding'])!=4 or r['new_floating_cells']:raise ValueError('Unverified cable station')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('candidate','previous','baseline-components','components','mtr','java','repo'):p.add_argument('--'+n,type=Path,required=True)
    verify(p.parse_args())
