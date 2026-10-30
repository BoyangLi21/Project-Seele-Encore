"""Combine station arrays and native ropeway fixtures without rebuilding saves."""
import argparse,json,math,shutil
from pathlib import Path
from types import SimpleNamespace
import nbtlib
import numpy as np
from author_hakone_lakefront import Editor
from author_hakone_mountain_stations import reachable
from install_hakone_array_patch import Palette,compose

ANGLES=['E','SEE','SE','SSE','S','SSW','SW','SWW','W','NWW','NW','NNW','N','NNE','NE','NEE']


def prepare(a):
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'source').mkdir(exist_ok=True);(a.out/'delta').mkdir(exist_ok=True)
    (a.out/'functional-check.json').write_text(json.dumps({'errors':['Composition incomplete']}),'utf8')
    gis=a.source.parent;native=gis/'ropeway-native';receipt=json.loads((native/'validated/native_transit_receipt.json').read_text())
    if not receipt['passed']:raise ValueError('Native services have not passed commissioning')
    capture=json.loads((a.source/'capture.json').read_text());candidates=[gis/'togendai-candidate',gis/'mountain-stations-candidate']
    for rel in capture['source_files']:
        target=a.out/rel
        if not target.exists():shutil.copy2(a.source/rel,target)
        files=[p/'delta'/Path(rel).name for p in candidates if(p/'delta'/Path(rel).name).exists()]
        patch=a.out/'delta'/Path(rel).name
        if not files:patch.unlink(missing_ok=True);continue
        pal=Palette();rows=compose(files,pal);points=[];ranges=[0];at=[];old=[];new=[]
        for p,(i,b,v)in rows.items():points.append(p);ranges.append(ranges[-1]+len(i));at.append(i);old.append(b);new.append(v)
        np.savez_compressed(patch,coordinates=np.asarray(points),ranges=ranges,indices=np.concatenate(at),before=np.concatenate(old),after=np.concatenate(new),palette=np.asarray(pal.names))
    e=Editor(a.out);plan=json.loads((native/'plan.json').read_text());samples=json.loads((native/'validated/track_samples.json').read_text())
    with np.load(a.source/'measured.npz')as d:top=d['highest'];protected=d['protected'];x0,z0,*_=d['bounds']
    def station(x,z):return any(s['min'][0]<=x<=s['max'][0]and s['min'][2]<=z<=s['max'][2]for s in plan['stations'])
    cabin={};outside=[]
    for r in samples:
        for xx,yy,zz in r['points']:
            x,y,z=round(xx),round(yy),round(zz)
            for dx in (-1,0,1):
                for dz in (-1,0,1):cabin.setdefault((x+dx,z+dz),[]).append((y-5,y-1))
            if not station(x,z)and int(top[z-z0,x-x0])>yy-7:outside.append([r['id'],x,y,z])
    if outside:raise ValueError('Support profile still contacts external terrain: '+str(outside[:6]))
    # At the station, open the actual cabin envelope. In the landscape, only
    # add pylons: terrain and buildings are never carved into a cable trench.
    for (x,z),spans in cabin.items():
        if station(x,z):
            for low,high in spans:e.fill(x,low,z,x,high,z,'minecraft:air')
    nodes={}
    for r in plan['rails']:
        for key,angle in [('from','from_angle'),('to','to_angle')]:
            p=tuple(r[key]);nodes.setdefault(p,dict(angle=r[angle],platform=False));nodes[p]['platform']|=r['kind']=='platform'
    poles=[];errors=[]
    for (x,y,z),row in nodes.items():
        index=ANGLES.index(row['angle']);angle=index*math.pi/8
        if not station(x,z):
            choices=[]
            offsets=[(distance,along)for distance in (5,-5,7,-7,10,-10,14,-14,20,-20,28,-28,36,-36)for along in (0,-8,8,-16,16)]
            for distance,along in offsets:
                bx,bz=round(x-math.sin(angle)*distance+math.cos(angle)*along),round(z+math.cos(angle)*distance+math.sin(angle)*along)
                if protected[bz-z0,bx-x0]or station(bx,bz):continue
                ground=int(top[bz-z0,bx-x0])
                if ground>=y-7:continue
                if any(lo<=y+1 and hi>=ground for lo,hi in cabin.get((bx,bz),[])):continue
                choices.append((bx,ground,bz));break
            if not choices:errors.append(['no-pylon-footing',[x,y,z]]);continue
            bx,ground,bz=choices[0]
            e.fill(bx,ground,bz,bx,y+1,bz,'minecraft:gray_concrete')
            count=max(abs(bx-x),abs(bz-z))
            for px,pz in np.rint(np.linspace((bx,bz),(x,z),count+1)).astype(int):e.put(int(px),y+1,int(pz),'minecraft:iron_block')
            e.put(bx,ground,bz,'minecraft:stone_bricks')
            poles.append(dict(node=[x,y,z],foot=[bx,ground,bz]))
        # Continuous node models use the nearest 45-degree orientation; native
        # rail tangents retain their full 22.5-degree path geometry in MTR data.
        quadr=round(index/2)%4;facing='true'if quadr<2 else'false';diagonal='true'if quadr%2 else'false'
        kind='station'if row['platform']else'upper'
        e.put(x,y,z,f'mtr:cable_car_node_{kind}[facing={facing},is_22_5=false,is_45={diagonal},is_connected=true,waterlogged=false]')
    devices=[]
    for candidate in candidates:
        devices.extend(nbtlib.load(candidate/'block-entities.dat')['Changes'])
    for row in devices:
        tag=row['After'];p=tuple(int(tag[k])for k in ('x','y','z'))
        if 'sign'not in e.state(*p):errors.append(['sign-removed-by-ropeway',p])
    mountain=json.loads((candidates[1]/'functional-check.json').read_text())
    tog=json.loads((candidates[0]/'functional-check.json').read_text())
    public=[SimpleNamespace(goals=r['goals'],bounds=r['bounds'])for r in mountain['stations']]
    public.append(SimpleNamespace(goals=tog['public_goals'],bounds=(-331,100,978,-244,119,1082)))
    for b in public:
        issues,_=reachable(e,b);errors.extend(issues)
    # Every newly added pole stays outside original inhabited plot volumes.
    neighbours=json.loads((gis/'main-district-candidate/neighbourhood.json').read_text('utf8'))
    for pole in poles:
        bx,ground,bz=pole['foot']
        for r in neighbours:
            site=r['site'];cx,cz=site['centre'];hx,hz=site['half']
            if site['rotation']%2:hx,hz=hz,hx
            if abs(bx-cx)<=hx+2 and abs(bz-cz)<=hz+2:errors.append(['pole-on-original-parcel',r['id'],pole])
    regions=e.save();nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](devices)}).save(a.out/'block-entities.dat',gzipped=True)
    manifest=dict(world=capture['world'],bounds_xz=capture['bounds_xz'],regions=regions,cells=sum(r['cells']for r in regions),progress_files_written=[],world_written=False,
                  station_count=5,native_receipt=str(native/'validated/native_transit_receipt.json'),pylons=poles)
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    report=dict(errors=errors,stations=5,pylons=len(poles),nodes=len(nodes),native_services=receipt['validation'],native_installed=False,visual_verified=False)
    (a.out/'functional-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise ValueError('Station/ropeway composition is incomplete')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','out'):p.add_argument('--'+name,type=Path,required=True)
    prepare(p.parse_args())
