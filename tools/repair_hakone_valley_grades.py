"""Regrade installed valley neighbourhoods without replacing their contents.

The native station platforms stay at their operating elevation. Streets, whole
residential plots and connecting paths share one grade calculation. Building
shells are moved from the current captured save, including user-added contents;
only natural earth and the recorded authored road volumes may be reworked.
"""
import argparse,copy,json,os
from collections import defaultdict
from pathlib import Path
import numpy as np
import nbtlib
from PIL import Image,ImageDraw
from hakone_earthworks import grade_development,grade_ground,min_slope_envelope,road_blocks
from prepare_hakone_main_terrain import sample_grid
from author_hakone_lakefront import Editor
from author_hakone_district_blocks import Frontage
from prepare_hakone_roof_repair import gables
from plan_ashi_landscape_r54 import NATURAL
from query_blocks import iter_block_entities
from install_r53_carrier_trays import stopped_world


def rectangle(site,bounds,margin=2):
    x,z=site['centre'];hx,hz=site['half']
    if site['rotation']%2:hx,hz=hz,hx
    x0,z0,x1,z1=bounds
    return np.s_[max(0,z-hz-z0-margin):min(z1-z0+1,z+hz-z0+margin+1),
                 max(0,x-hx-x0-margin):min(x1-x0+1,x+hx-x0+margin+1)]


def design(gis,source,out):
    if out.exists():raise ValueError('Choose a new repair candidate')
    (out/'source').mkdir(parents=True);(out/'delta').mkdir()
    for p in(source/'source').glob('*.npz'):os.link(p,out/'source'/p.name)
    capture=json.loads((source/'capture.json').read_text('utf8'))
    (out/'capture.json').write_text(json.dumps(capture,ensure_ascii=False),'utf8')
    (out/'functional-check.json').write_text(json.dumps(dict(errors=['Valley regrading has not been composed'])),'utf8')
    with np.load(gis/'tozan-valley-candidate-v5/valley-surface.npz')as f:d={k:f[k]for k in f.files}
    layout=json.loads((gis/'tozan-valley-candidate-v5/valley-buildings.json').read_text('utf8'))
    bounds=d['bounds'];x0,z0,x1,z1=map(int,bounds);shape=d['target'].shape
    zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    with np.load(gis/'terrain-design.npz')as f:g={k:f[k]for k in('x','z','height_y')}
    surveyed=sample_grid(g,'height_y',xx,zz)
    target2=np.rint(surveyed*2).astype(np.int16)
    target2[d['walk']]=d['road2'][d['walk']]
    developed=d['walk'].copy();fixed=np.zeros(shape,bool);plots=[]
    rows=copy.deepcopy(layout['buildings'])
    # The fixed station platform connections are the level first path in each
    # station pair. Ordinary street approaches are solved with the street.
    approaches=layout['approaches']
    for i,path in enumerate(approaches):
        for x,y,z in path:
            area=np.s_[z-z0-1:z-z0+2,x-x0-1:x-x0+2]
            target2[area]=y*2;developed[area]=True
            if i<2*len(layout['stations']) and i%2==0:fixed[area]=True
    for row in rows:
        area=rectangle(row['site'],bounds);plots.append(area)
        target2[area]=row['site']['floor']*2;developed[area]=True
        if row.get('kind')=='station':fixed[area]=True
    # Several old street ramps overlapped the platform approach in projection.
    # Give that level connection its actual station height after rasterizing
    # all flexible paths; otherwise the last ramp pixel corrupts a fixed grade.
    for path in approaches[:2*len(layout['stations']):2]:
        for x,y,z in path:target2[z-z0-1:z-z0+2,x-x0-1:x-x0+2]=y*2
    station_plan=json.loads((gis/'tozan-native/plan.json').read_text('utf8'))
    platforms={r['station_id']:r for r in layout['stations']}
    for station in station_plan['station_geometry']:
        if station['id']not in platforms:continue
        row=platforms[station['id']];a,b=np.asarray(station['platform_a']),np.asarray(station['platform_b'])
        direction=np.asarray(station['direction']);normal=np.array([-direction[1],direction[0]])
        if np.dot(np.asarray(row['site']['centre'])-(a+b)/2,normal)<0:normal=-normal
        offset=normal*4;y=row['site']['floor']
        for fraction in np.linspace(0,1,max(2,round(float(np.linalg.norm(b-a))))+1):
            x,z=np.rint(a+(b-a)*fraction+offset).astype(int)
            area=np.s_[z-z0-1:z-z0+2,x-x0-1:x-x0+2]
            target2[area]=y*2;fixed[area]=True;developed[area]=True
    # Retained Gora interchange is outside the altered parcels. Its measured
    # public ground stays with the already commissioned station batch.
    np.savez_compressed(out/'grade-input.npz',bounds=bounds,target2=target2,developed=developed,fixed=fixed)
    fitted=grade_development(target2,developed,plots,fixed,slope=1.0,plot_quantum=2)
    crossing_heights={};base_target=target2.copy();base_fixed=fixed.copy();pedestrian_fixed=fixed.copy()
    tracks=json.loads((gis/'tozan-native/validated-v7/track_samples.json').read_text('utf8'))
    rail_columns={}
    for rail in tracks:
        if rail['id'].startswith('HC'):continue
        for px,py,pz in rail['points']:
            x,y,z=int(np.floor(px)),int(np.floor(py)),int(np.floor(pz))
            for X in range(x-1,x+2):
                for Z in range(z-1,z+2):
                    if x0<=X<=x1 and z0<=Z<=z1:rail_columns[X,Z]=y
    for iteration in range(8):
        added=False
        for (x,z),y in rail_columns.items():
            if developed[z-z0,x-x0] and not base_fixed[z-z0,x-x0]:
                fy=int((fitted[z-z0,x-x0]+1)//2)
                if y-1<fy<y+6 and (x,z)not in crossing_heights:
                    crossing_heights[x,z]=y-1;added=True
        if not added:break
        target2=base_target.copy();fixed=base_fixed.copy();crossing_grid=np.full(shape,np.inf,np.float32)
        for (x,z),y in crossing_heights.items():crossing_grid[z-z0,x-x0]=y*2
        crossing_grade=min_slope_envelope(crossing_grid,2)
        for (x,z),y in crossing_heights.items():
            value=int(crossing_grade[z-z0,x-x0])
            if y*2-value>1:raise ValueError('Rail crossing needs a distinct bridge or underpass')
            target2[z-z0,x-x0]=value;fixed[z-z0,x-x0]=True
        np.savez_compressed(out/'grade-input.npz',bounds=bounds,target2=target2,developed=developed,fixed=fixed)
        # Rasterized native ballast and platforms contain one-block lips.
        # Their retained levels bound this joint solve at the same traversable
        # one-block grade as the main city; ordinary half-slab profiles remain
        # the starting heights. Soil shoulders use the same one-block limit.
        fitted=grade_development(target2,developed,plots,fixed,slope=2.0,plot_quantum=2)
    else:raise ValueError('Valley rail/street grades did not converge')
    ground,conflicts=grade_ground(surveyed,developed,fitted//2,slope=1.0)
    if conflicts.any():raise ValueError('Contradictory valley earthworks')
    shifts=[]
    for old,row,area in zip(layout['buildings'],rows,plots):
        y=int(fitted[area][0,0])//2;dy=y-old['site']['floor'];row['site']['floor']=y
        shifts.append(dict(label=row['label'],centre=row['site']['centre'],before=old['site']['floor'],after=y,dy=dy))
        for key in('entrance','door','approach','upper'):
            if row.get(key):row[key][1]+=dy
        if row.get('road'):
            rx,_,rz=row['road'];row['road'][1]=int((fitted[rz-z0,rx-x0]+1)//2)
    newpaths=[]
    for path in approaches:
        newpaths.append([[x,int((fitted[z-z0,x-x0]+1)//2),z]for x,y,z in path])
    result=dict(buildings=rows,stations=[r for r in rows if r.get('kind')=='station'],approaches=newpaths,
                village_counts=layout['village_counts'],shifts=shifts)
    (out/'valley-buildings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    np.savez_compressed(out/'grading.npz',bounds=bounds,target=ground,grade2=fitted,developed=developed,fixed=fixed,pedestrian_fixed=pedestrian_fixed,**{k:d[k]for k in('walk','road','bridge','wet','water_y','held')})
    print('Valley design:',len(rows),'buildings;',sum(r['dy']!=0 for r in shifts),'vertical moves;',
          'largest move',max(abs(r['dy'])for r in shifts),'blocks',flush=True)
    for r in shifts:
        if abs(r['dy'])>=8:print(r,flush=True)
    return result


def building_box(row):
    site=row['site'];c=Frontage(site);hx,hz=site['half']
    a=c.point(-hx-1,-2,-hz-1);b=c.point(hx+1,site['floors']*5+6,hz+2)
    return [*np.minimum(a,b),*np.maximum(a,b)]


def compose(gis,source,out):
    capture=json.loads((source/'capture.json').read_text('utf8'));world=Path(capture['world'])
    prior=json.loads((gis/'tozan-valley-candidate-v5/valley-buildings.json').read_text('utf8'))
    revised=json.loads((out/'valley-buildings.json').read_text('utf8'))
    with np.load(out/'grading.npz')as f:d={k:f[k]for k in f.files}
    with np.load(gis/'tozan-valley-candidate-v5/valley-surface.npz')as f:oldsurface={k:f[k]for k in('target','road2','walk')}
    with np.load(source/'measured.npz')as f:m={k:f[k]for k in f.files}
    x0,z0,x1,z1=map(int,d['bounds']);shape=d['target'].shape;zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    with stopped_world(world):devices=dict(iter_block_entities(world,'projectseele:geofront',(x0,-128,z0),(x1,319,z1)))
    # Record all exact original contents once. Later installation still compares
    # these complete tags with the then-current world, including inventories.
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](copy.deepcopy(list(devices.values())))}).save(out/'captured-devices.dat',gzipped=True)
    e=Editor(source);payloads=[];oldboxes=[];newboxes=[];moves={};roofops=[]
    for old,row in zip(prior['buildings'],revised['buildings']):
        box=building_box(old);newbox=building_box(row);dy=row['site']['floor']-old['site']['floor']
        if box[0]<1024 and box[2]<=1023:continue  # main-city overlap is composed separately
        for actor in capture['actors']:
            if dy and all(box[i]<=actor['pos'][i]<=box[i+3]for i in range(3)):
                raise ValueError('Move the occupied parcel together with its actor before installation')
        for pos,tag in devices.items():
            if all(box[i]<=pos[i]<=box[i+3]for i in range(3)) and dy:moves[pos]=(pos[0],pos[1]+dy,pos[2])
        saved=[]
        for x in range(box[0],box[3]+1):
            for z in range(box[2],box[5]+1):
                r=e.region(x,z);b=r['before'][r['index'][x//16,z//16],box[1]+128:box[4]+129,z%16,x%16]
                saved.append((x,z,[r['names'][v]for v in b]))
        payloads.append((newbox,saved));oldboxes.append((box,old['site']['floor']))
        newboxes.append(newbox);roofops.extend(gables(row).operations)
        e.regions.clear()
    del e
    bychunk=defaultdict(list);oldowned=defaultdict(list);roofchunks=defaultdict(list)
    for box,saved in payloads:
        for x,z,column in saved:bychunk[x//16,z//16].append((x,z,box[1],column))
    for box,floor in oldboxes:
        for cx in range(box[0]//16,box[3]//16+1):
            for cz in range(box[2]//16,box[5]//16+1):oldowned[cx,cz].append((box,floor))
    for op in roofops:
        for cx in range(op[0]//16,op[3]//16+1):
            for cz in range(op[2]//16,op[5]//16+1):roofchunks[cx,cz].append(op)
    oldpaths=defaultdict(list)
    for path in prior['approaches']:
        for x,y,z in path:
            for X in range(x-1,x+2):
                for Z in range(z-1,z+2):oldpaths[X//16,Z//16].append((X,y,Z))
    pathmask=np.zeros(shape,bool)
    for path in revised['approaches']:
        for x,y,z in path:pathmask[z-z0-1:z-z0+2,x-x0-1:x-x0+2]=True
    plotmask=np.zeros(shape,bool)
    for row in revised['buildings']:plotmask[rectangle(row['site'],d['bounds'],1)]=True
    # Keep the native rail's actual running volume, not its entire soil column.
    railvol=defaultdict(dict)
    tracks=json.loads((gis/'tozan-native/validated-v7/track_samples.json').read_text('utf8'))
    for rail in tracks:
        if rail['id'].startswith('HC'):continue
        for px,py,pz in rail['points']:
            x,y,z=int(np.floor(px)),int(np.floor(py)),int(np.floor(pz))
            for X in range(x-1,x+2):
                for Z in range(z-1,z+2):railvol[X//16,Z//16][X,Z]=y
    yy=np.arange(-128,320)[:,None,None];regions=[];errors=[];roadconflicts=[];plotclear=[]
    active=((xx>=1024)|(zz>=1024))&~m['actors']
    # The old UN quay/ships are a separate final task, never earthwork anchors
    # derived from their roofs or the old sea level.
    active&=~((xx>=1152)&(zz<650))
    paving={'minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone',
        'minecraft:stone_bricks','projectseele:road_asphalt_slab','projectseele:road_marking_slab','minecraft:smooth_stone_slab'}
    total=0
    for file in sorted((source/'source').glob('*.npz')):
        with np.load(file)as f:coords=f['coordinates'];blocks=f['blocks'];palette=list(map(str,f['palette']))
        ids={s:i for i,s in enumerate(palette)}
        def code(s):
            if s not in ids:ids[s]=len(palette);palette.append(s)
            return ids[s]
        for chunk in coords:
            for x,z,y,column in bychunk[tuple(chunk)]:
                for state in column:code(state)
            for op in roofchunks[tuple(chunk)]:code(op[-1])
        air,stone,dirt,grass,water,asphalt,pave,stripe,aslab,pslab,mslab=[code(s)for s in(
            'minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:water[level=0]',
            'minecraft:black_concrete','minecraft:smooth_stone','minecraft:white_concrete',
            'projectseele:road_asphalt_slab[type=bottom,waterlogged=false]','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]',
            'projectseele:road_marking_slab[type=bottom,waterlogged=false]')]
        natural=np.array([s.split('[')[0]in NATURAL for s in palette]);paved=np.array([s.split('[')[0]in paving for s in palette])
        coordinates=[];ranges=[0];atlist=[];before=[];after=[]
        for (cx,cz),old in zip(coords,blocks):
            area=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16];h=d['target'][area];live=active[area]
            if not live.any():continue
            new=old.copy();owned=np.zeros(old.shape,bool)
            oldy=oldsurface['road2'][area]//2
            owned|=oldsurface['walk'][area]&(yy>=oldy-1)&(yy<=oldy+5)&paved[old]
            for x,y,z in oldpaths[cx,cz]:owned[max(0,y-2+128):min(448,y+4+128),z%16,x%16]=True
            for box,floor in oldowned[cx,cz]:
                X,Z=max(box[0],cx*16),max(box[2],cz*16);R,B=min(box[3],cx*16+15),min(box[5],cz*16+15)
                owned[box[1]+128:box[4]+129,Z-cz*16:B-cz*16+1,X-cx*16:R-cx*16+1]=True
                for x in range(X,R+1):
                    for z in range(Z,B+1):
                        bottom=min(int(oldsurface['target'][z-z0,x-x0]),floor-2)
                        owned[max(-128,bottom)+128:floor-2+128,z%16,x%16]|=np.array([palette[v]=='minecraft:stone_bricks'for v in old[max(-128,bottom)+128:floor-2+128,z%16,x%16]],bool)
            allow=natural[old]|owned
            foreign=~allow;low=np.where(foreign,yy,320).min(0)-1;high=np.where(foreign,yy,-129).max(0)+4
            keep=(yy>=low)&(yy<=high)
            for (x,z),y in railvol[cx,cz].items():keep[max(0,y-2+128):min(448,y+6+128),z%16,x%16]=True
            lower=np.maximum(-127,np.minimum(m['top'][area],h)-3);upper=np.maximum(m['highest'][area],h+6)
            band=live&(yy>=lower)&(yy<=upper)&allow&~keep
            proposed=np.where(yy>h,air,np.where(yy==h,grass,np.where(yy>=h-3,dirt,stone))).astype(np.uint16)
            new[band]=proposed[band]
            retired=owned&live&~keep;new[retired]=proposed[retired]
            rw=(d['walk'][area]|pathmask[area]|d['pedestrian_fixed'][area])&live&~plotmask[area]
            y,odd=road_blocks(d['grade2'][area])
            motorroad=d['road'][area]&~d['pedestrian_fixed'][area]
            clearheight=np.where(motorroad,4,3)
            conflict=rw&((yy>y)&(yy<=y+clearheight)&~allow).any(0)
            for z,x in np.argwhere(conflict):roadconflicts.append([int(cx*16+x),int(y[z,x]),int(cz*16+z)])
            rw&=~conflict
            materials=np.where(motorroad,np.where(odd,aslab,asphalt),np.where(odd,pslab,pave))
            # Keep native rail air clear at grade-separated intersections.
            for (x,z),ry in railvol[cx,cz].items():
                if rw[z%16,x%16]and ry-1<int(y[z%16,x%16])<ry+6:
                    roadconflicts.append([int(x),int(y[z%16,x%16]),int(z),'rail']);rw[z%16,x%16]=False
            new[rw&(yy>y)&(yy<=y+clearheight)&allow]=air
            new[rw&(yy==y-1)&allow]=stone
            mask=rw&(yy==y)&allow;new[mask]=np.broadcast_to(materials,new.shape)[mask]
            for x,z,y,column in bychunk[cx,cz]:new[y+128:y+128+len(column),z%16,x%16]=np.array([ids[s]for s in column],np.uint16)
            for op in roofchunks[cx,cz]:
                lo=np.maximum([cx*16,-128,cz*16],op[:3]);hi=np.minimum([cx*16+15,319,cz*16+15],op[3:6]);sl=np.s_[lo[1]+128:hi[1]+129,lo[2]-cz*16:hi[2]-cz*16+1,lo[0]-cx*16:hi[0]-cx*16+1]
                replace=np.isin(new[sl],[air]);new[sl][replace]=ids[op[-1]]
            at=np.flatnonzero((new!=old).ravel()).astype(np.uint32)
            if len(at):coordinates.append((cx,cz));atlist.append(at);before.append(old.ravel()[at]);after.append(new.ravel()[at]);ranges.append(ranges[-1]+len(at))
        if coordinates:
            name='delta/'+file.name;np.savez_compressed(out/name,coordinates=np.asarray(coordinates,np.int32),ranges=np.asarray(ranges,np.int64),indices=np.concatenate(atlist),before=np.concatenate(before),after=np.concatenate(after),palette=np.asarray(palette))
            regions.append(dict(path=name,cells=ranges[-1]));total+=ranges[-1]
        print('Valley integrated',file.name,total,'cells',flush=True)
    changes={}
    for pos,q in moves.items():
        tag=copy.deepcopy(devices[pos]);tag['y']=nbtlib.Int(q[1])
        changes.setdefault(pos,nbtlib.Compound())['Before']=copy.deepcopy(devices[pos]);changes.setdefault(q,nbtlib.Compound())['After']=tag
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changes.values())}).save(out/'block-entities.dat',gzipped=True)
    report=dict(world=str(world),regions=regions,cells=total,bounds_xz=list(map(int,d['bounds'])),world_written=False,
        pending=['road/native interfaces','complete parcel exterior and public paths','western overlap with main city','cold installation and changed-region LOD'],moved_devices=len(moves))
    (out/'manifest.json').write_text(json.dumps(report,indent=2),'utf8')
    (out/'functional-check.json').write_text(json.dumps(dict(errors=errors,road_conflicts=roadconflicts,public_routes_pending=True,visual_verified=False),indent=2),'utf8')
    print('Native/road interfaces requiring closure:',len(roadconflicts),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('gis','source','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--compose',action='store_true')
    a=p.parse_args()
    if a.compose:compose(a.gis,a.source,a.out)
    else:design(a.gis,a.source,a.out)
