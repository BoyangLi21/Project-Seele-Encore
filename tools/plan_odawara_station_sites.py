"""Measure five southeastern station sites using immutable offline snapshots.

Produces construction inputs, not a world patch or a claim of completed access.
GSI centre lines describe corridors; they do not establish real platform counts.
"""
import argparse, collections, gzip, heapq, json, math
from pathlib import Path
import numpy as np
import nbtlib
from shapely.geometry import shape, Point, LineString, Polygon, mapping, box
from shapely.ops import unary_union
from map_pipeline.station_sections import StationSections
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR

NATURAL = SOIL | AIR | {'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:light'}
NAMES = {'kamonomiya':'鴨宮駅','odawara':'小田原駅','midoricho':'緑町駅','hayakawa':'早川駅','itabashi':'箱根板橋駅'}

def json_write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')

def basis(points):
    u = np.asarray(points[-1],float)-points[0]; u/=np.linalg.norm(u)
    if u[0]<0 or (abs(u[0])<1e-8 and u[1]<0): u=-u
    return u, np.asarray([-u[1],u[0]])

def rectangle(c,u,n,a,b,d,e):
    return Polygon([c+u*a+n*d,c+u*b+n*d,c+u*b+n*e,c+u*a+n*e])

def raster(poly,x,z,X,Z):
    from shapely import contains_xy
    zz,xx=np.mgrid[z:Z+1,x:X+1]
    return contains_xy(poly.buffer(.001),xx+.5,zz+.5)

def run(a):
    a.out.mkdir(parents=True,exist_ok=True)
    stations=json.loads((a.geography/'stations.json').read_text('utf8'))
    programme=json.loads((a.programme/'district-programme.json').read_text('utf8'))
    features=json.loads(gzip.decompress((a.features/'features.world.geojson.gz').read_bytes()))['features']
    rails=[(i,f,shape(f['geometry'])) for i,f in enumerate(features) if f['properties'].get('source_layer')=='RailCL']
    waters=[(i,f,shape(f['geometry'])) for i,f in enumerate(features) if f['properties'].get('source_layer') in ('WA','RvrCL','WStrL')]
    reader=StationSections(a.source,cache_regions=5)
    cap=reader.report
    devices=[dict(x=int(d['x']),y=int(d['y']),z=int(d['z']),id=str(d['id'])) for d in nbtlib.load(a.source/'devices.dat')['Devices']]
    with np.load(a.authority/'network.npz') as f:
        ax,az,aX,aZ=map(int,f['bounds']); network={k:f[k] for k in ('walk','grade2','ground','held')}
    output=[]
    for slug,name in NAMES.items():
        station=next(s for s in stations if s['name']==name)
        site=next(s for s in cap['sites'] if s['name']==name and s['kind']=='geographic')
        x,_,z,X,_,Z=site['bounds']; low,high=-112,-40
        data,palette=reader.box([x,low,z,X,high,Z]); names=[s.split('[')[0] for s in palette]
        natural=np.asarray([s in NATURAL for s in names]); soil=np.asarray([s in SOIL for s in names]); air=np.asarray([s in AIR or s=='minecraft:light' for s in names]); water=np.asarray([s=='minecraft:water' for s in names])
        yy=np.arange(low,high+1)[:,None,None]
        ground=np.where(soil[data],yy,low-1).max(0); unknown=(data==0).any(0)
        public=network['walk'][z-az:Z-az+1,x-ax:X-ax+1]; grades=network['grade2'][z-az:Z-az+1,x-ax:X-ax+1]
        cc=np.asarray(station['track_centre_xz']); u,n=basis(station['station_track']); ref=LineString(station['station_track'])
        nearby=[(i,f,g) for i,f,g in rails if g.distance(Point(cc))<100]
        station_lines=[(i,f,g) for i,f,g in nearby if f['properties'].get('vt_sngldbl')=='駅部分' and g.distance(Point(cc))<45]
        evidence=[]
        for i,f,g in sorted(nearby,key=lambda r:r[2].distance(Point(cc))):
            evidence.append(dict(feature_index=i,properties=f['properties'],geometry=mapping(g),distance=round(g.distance(Point(cc)),3)))
        scope=next(s for s in programme['stations'] if s['name']==name)
        reservation=shape(scope['geometry'])
        public_points=np.argwhere(public)[:,::-1]+np.asarray([x,z])
        def public_distance(c,side):
            allowed=public_points[((public_points-cc)@n)*side>9]
            return float(np.linalg.norm(allowed-c,axis=1).min()) if len(allowed) else 1000
        def parallel_conflicts(poly):
            result=[]
            for i,f,g in nearby:
                if not g.intersects(poly.buffer(2)):continue
                clipped=g.intersection(poly.buffer(6))
                lines=list(clipped.geoms) if clipped.geom_type=='MultiLineString' else [clipped]
                points=[np.asarray(q.coords) for q in lines if q.geom_type=='LineString']
                if not points:continue
                offsets=(np.concatenate(points)-cc)@n
                # A tile-fragment continuation along the same axis is not a
                # parallel railway. Preserve separate corridors >4 blocks away.
                if float(np.median(np.abs(offsets)))>4:result.append(i)
            return result
        def measure(poly,level):
            mask=raster(poly,x,z,X,Z)
            band=(yy>=level-3)&(yy<=level+10)
            conflict=(~natural[data])&band&mask[None,:,:]
            counts=collections.Counter(palette[int(v)] for v in data[conflict])
            out=dict(columns=int(mask.sum()),unknown_columns=int((mask&unknown).sum()),water_cells=int((water[data]&band&mask[None,:,:]).sum()),protected_cells=int(conflict.sum()),protected_states=dict(counts),public_columns=int((mask&public).sum()))
            if mask.any():
                values=ground[mask];out.update(ground_min=int(values.min()),ground_max=int(values.max()),max_fill=int(max(0,(level-values).max())),max_cut=int(max(0,(values-level).max())),outside_reserved_columns=int((mask&~raster(reservation,x,z,X,Z)).sum()))
            out['device_coordinates']=[[d['x'],d['y'],d['z']] for d in devices if level-3<=d['y']<=level+10 and poly.covers(Point(d['x']+.5,d['z']+.5))]
            out['outside_capture_area']=float(poly.difference(box(x,z,X+1,Z+1)).area)
            where=np.argwhere(conflict)
            out['protected_examples']=[[int(j[2]+x),int(j[0]+low),int(j[1]+z),palette[int(data[tuple(j)])]] for j in where[:30]]
            return out,mask
        # A two-track footprint is a design decision for mapped double-track
        # corridors, not a claim that GSI tells us the exact real station layout.
        tracks=1 if slug in ('midoricho','itabashi') else 2
        length=48 if tracks==1 else 128
        possibilities=[]
        for shift in (-8,-4,0,4,8):
            centre=cc+u*shift
            if tracks==1:
                for side in (-1,1):
                    core=rectangle(centre,u,n,-length/2-3,length/2+3,-2 if side>0 else -9,9 if side>0 else 2)
                    mask=raster(core,x,z,X,Z); level=int(round(float(np.median(ground[mask]))))+1
                    m,_=measure(core,level); score=m['protected_cells']*100+m['public_columns']*20+m['unknown_columns']*1000+len(parallel_conflicts(core))*3000+(m['max_fill']+m['max_cut'])*10+abs(shift)+public_distance(centre+n*side*18,side)
                    possibilities.append((score,centre,side,core,level,m))
            else:
                core=rectangle(centre,u,n,-length/2-3,length/2+3,-7,7)
                mask=raster(core,x,z,X,Z); level=int(round(float(np.median(ground[mask]))))+1
                m,_=measure(core,level); score=m['protected_cells']*100+m['public_columns']*20+m['unknown_columns']*1000+(m['max_fill']+m['max_cut'])*10+abs(shift)
                possibilities.append((score,centre,0,core,level,m))
        best=min(possibilities,key=lambda p:p[0]);_,centre,side,core,level,measurement=best
        # Hall stays on one side of the line and is scored against measured
        # protected blocks and existing public ground, never cleared blindly.
        halls=[]
        for hall_side in ((side,) if tracks==1 else (-1,1)):
            for along in (-12,0,12):
                for offset in (17,23,29):
                    hc=centre+u*along+n*offset*hall_side
                    hall=rectangle(hc,u,n,-9,9,-7,7)
                    hm,hmask=measure(hall,level)
                    if not hmask.any():continue
                    # Also protect parallel rail corridors of a different operator.
                    other=parallel_conflicts(hall.buffer(1))
                    score=hm['protected_cells']*100+hm['public_columns']*20+hm['unknown_columns']*1000+len(other)*3000+(hm['max_fill']+hm['max_cut'])*10+offset+public_distance(hc,hall_side)*2
                    halls.append((score,hall_side,hc,hall,hm,other))
        hall_choice=min(halls,key=lambda p:p[0]);_,hall_side,hc,hall,hm,other=hall_choice
        # Verify actual destination sidewalk blocks and body space before calling
        # a target suitable; no guessed height from a stale surface map.
        street=[]
        for iz,ix in np.argwhere(public):
            wx,wz=int(ix+x),int(iz+z); g2=int(grades[iz,ix]); by=(g2+1)//2
            if not low<=by<=high-3:continue
            state=palette[int(data[by-low,iz,ix])]
            bottom_slab='slab[' in state and 'type=bottom' in state
            floor_ok=(g2%2==0 and state.split('[')[0] in {'minecraft:smooth_stone','minecraft:stone_bricks','minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:white_concrete','minecraft:black_concrete','minecraft:polished_andesite','minecraft:andesite'}) or (g2%2!=0 and bottom_slab)
            if not floor_ok or not air[data[by-low+1:by-low+4,iz,ix]].all():continue
            if np.dot(np.asarray([wx,wz])-centre,n)*hall_side<9:continue
            dist=float(np.linalg.norm(np.asarray([wx,wz])-hc))
            street.append((dist,wx,wz,g2,state))
        street.sort(); targets=[]
        for dist,wx,wz,g2,state in street:
            if all(math.hypot(wx-t['xyz'][0],wz-t['xyz'][2])>=10 for t in targets):
                targets.append(dict(xyz=[wx,g2/2+1,wz],floor_grade2=g2,floor_state=state,distance_from_hall=round(dist,2),headroom_blocks_checked=3))
            if len(targets)==8:break
        access=None
        if targets:
            # Four-connected 3-wide corridor in a single planned floor band.
            # Grade assignment and final voxel geometry remain a release gate.
            passable=np.ones(ground.shape,bool)
            band=(yy>=level-3)&(yy<=level+4)
            bad=((~natural[data])&band).any(0)|unknown
            bad&=~public
            for dz in (-1,0,1):
                for dx in (-1,0,1):
                    dest=np.s_[max(0,dz):min(bad.shape[0],bad.shape[0]+dz),max(0,dx):min(bad.shape[1],bad.shape[1]+dx)]
                    src=np.s_[max(0,-dz):min(bad.shape[0],bad.shape[0]-dz),max(0,-dx):min(bad.shape[1],bad.shape[1]-dx)]
                    passable[dest]&=~bad[src]
            # Paths must remain on the entrance side and outside railway beds.
            zz,xx=np.mgrid[z:Z+1,x:X+1]
            passable&=(((xx+.5-centre[0])*n[0]+(zz+.5-centre[1])*n[1])*hall_side>8)
            passable&=(np.abs(ground-level)<=4)|public
            starts=[]
            for forward in range(8,12):
                p=hc+n*hall_side*forward; q=(int(round(p[0]))-x,int(round(p[1]))-z)
                if 0<=q[0]<=X-x and 0<=q[1]<=Z-z and passable[q[1],q[0]]:starts.append(q)
            ends={(t['xyz'][0]-x,t['xyz'][2]-z):t for t in targets}
            heap=[];cost={};prev={}
            for q in starts:heapq.heappush(heap,(0,q));cost[q]=0;prev[q]=None
            goal=None
            while heap:
                value,q=heapq.heappop(heap)
                if value!=cost[q]:continue
                if q in ends:goal=q;break
                for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                    Q=q[0]+dx,q[1]+dz
                    if not(1<=Q[0]<X-x and 1<=Q[1]<Z-z) or not passable[Q[1],Q[0]]:continue
                    v=value+1+.2*abs(int(ground[Q[1],Q[0]])-level)
                    if v<cost.get(Q,1e30):cost[Q]=v;prev[Q]=q;heapq.heappush(heap,(v,Q))
            if goal is not None:
                path=[];q=goal
                while q is not None:path.append([q[0]+x,q[1]+z]);q=prev[q]
                path.reverse();access=dict(centreline_xz=path,width=3,target=ends[goal],planar_corridor_clear=True,final_grade_and_body_sweep_verified=False)
        rail_offsets=[0] if tracks==1 else [-4.5,4.5]
        track_lines=[dict(centreline=[list(np.round(centre+u*t+n*offset,3)) for t in(-length/2,length/2)],rail_y=level,offset=offset,length=length,bed_floor_y=level-1,reserved_width=3,reserved_height=6) for offset in rail_offsets]
        platforms=[dict(geometry=mapping(rectangle(centre,u,n,-length/2,length/2,side*2 if side>0 else -9,9 if side>0 else -2)),floor_y=level)] if tracks==1 else [dict(geometry=mapping(rectangle(centre,u,n,-length/2,length/2,-3,3)),floor_y=level,boarding_faces=2)]
        blockers=[]
        for label,m in [('core',measurement),('hall',hm)]:
            for field in ('unknown_columns','protected_cells','public_columns','water_cells'):
                if m[field]:blockers.append(f'{label}: {field}={m[field]}')
            if m['max_fill']>4 or m['max_cut']>3:blockers.append(f'{label}: terrain support/cut exceeds simple foundation')
            if m['device_coordinates']:blockers.append(f'{label}: existing devices')
            if m['outside_capture_area']>.01:blockers.append(f'{label}: footprint extends beyond the measured capture')
        core_rail_conflicts=parallel_conflicts(core)
        if other:blockers.append('hall overlaps another cached railway corridor')
        if core_rail_conflicts:blockers.append('core overlaps another cached railway corridor')
        if not access:blockers.append('no measured three-wide entrance-side street corridor found')
        if tracks==2:blockers.append('island platform requires designed grade-separated bridge/stairs to hall')
        if slug=='odawara':blockers.append('four distinct cached station corridors require complete multilevel hub plan; generic selected core is only a probe')
        row=dict(id=slug,name=name,reference=station,captured_bounds=[x,low,z,X,high,Z],axis_degrees=round(math.degrees(math.atan2(u[1],u[0]))%180,3),axis_u=u.tolist(),axis_n=n.tolist(),candidate_centre_xz=centre.tolist(),planned_rail_y=level,rail_lines=track_lines,platforms=platforms,core_geometry=mapping(core),core_measurement=measurement,hall_geometry=mapping(hall),hall_centre_xz=hc.tolist(),hall_side=hall_side,hall_measurement=hm,nearby_railway_conflicts=other,core_railway_conflicts=core_rail_conflicts,street_targets=targets,access_corridor=access,cached_rail_evidence=evidence,station_corridor_evidence_count=len(station_lines),blockers=blockers,physical_authoring_may_begin=not blockers,world_written=False,exact_real_platform_layout_verified=False,stage_three_native_vehicle_sweep_required=True)
        # Keep every conflicting cell for a later precise redesign. These cells
        # are protected evidence, never a removal list.
        active=raster(unary_union([core,hall]),x,z,X,Z)
        conflicts=(~natural[data])&(yy>=level-3)&(yy<=level+10)&active[None,:,:]
        where=np.argwhere(conflicts)
        conflict_rows=[[int(j[2]+x),int(j[0]+low),int(j[1]+z),palette[int(data[tuple(j)])]] for j in where]
        json_write(a.out/(slug+'-protected-cells.json'),dict(protected_do_not_remove=True,columns=conflict_rows))
        row['protected_cells_file']=slug+'-protected-cells.json'
        # Odawara is four corridor families, with independently retained axes
        # and endpoints. Layer order is not converted to an invented elevation.
        if slug=='odawara':
            row['hub_corridors']=[dict(feature_index=i,properties=f['properties'],geometry=mapping(g),axis_degrees=round(math.degrees(math.atan2(*(basis(list(g.coords))[0][::-1])))%180,3),platform_count_unverified=True,relative_layer=f['properties'].get('vt_lvorder'),absolute_native_rail_y_unassigned=True) for i,f,g in station_lines]
            row['hub_design_requirements']=['retain all four corridors, including the short non-JR terminus','two-sided city access with one common paid/unpaid transfer concourse','independent stair/step-free connection to every boarding group','preserve separation at crossings; GIS relative layer does not specify metre height','extend native geometry/vehicle sweep before platform voxel authoring','keep bridge/river boundary interfaces explicitly assigned to stage 3']
        local_water=[]
        search=box(x,z,X,Z)
        for i,f,g in waters:
            if g.intersects(search):local_water.append(dict(feature_index=i,properties=f['properties'],geometry=mapping(g.intersection(search))))
        row['nearby_water_interfaces']=local_water
        json_write(a.out/(slug+'.json'),row);output.append(row)
        np.savez_compressed(a.out/(slug+'-measurement.npz'),bounds=[x,z,X,Z],ground=ground,public=public,grade2=grades,unknown=unknown,protected=((~natural[data])&(yy>=level-3)&(yy<=level+10)).any(0))
        render_plan(a.out,slug,row,ground,public,unknown,data,palette,low)
        print(name, 'level',level,'core conflicts',measurement['protected_cells'],'hall conflicts',hm['protected_cells'],'street path',len(access['centreline_xz']) if access else 0,'blockers',len(blockers),flush=True)
    declared=[s['name'] for s in programme['stations'] if '国府津' in s['name']]
    json_write(a.out/'review.json',dict(stations_reviewed=len(output),site_inputs=[r['id']+'.json' for r in output],construction_complete=0,physical_authoring_ready=sum(r['physical_authoring_may_begin'] for r in output),new_station_layouts_are_designs_not_measured_real_platform_counts=True,source=str(a.source),authority=str(a.authority),geography=str(a.features),kozudirection=dict(declared_station_names=declared,new_station_created=False,note='Use existing eastern regional interface; no undeclared station is added.'),world_written=False,un_relocation_allowed=False))

def render_plan(out,slug,row,ground,public,unknown,data,palette,low):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    x,_,z,X,_,Z=row['captured_bounds'];fig,ax=plt.subplots(figsize=(10,10),dpi=130)
    ax.imshow(ground,extent=(x,X+1,Z+1,z),cmap='Greys',vmin=row['planned_rail_y']-8,vmax=row['planned_rail_y']+5)
    overlay=np.zeros((*ground.shape,4));overlay[public]=[.1,.7,.9,.85];overlay[unknown]=[.9,.1,.7,.7]
    ax.imshow(overlay,extent=(x,X+1,Z+1,z))
    def geo(g,color,lw):
        q=shape(g)
        if q.geom_type=='Polygon':xx,zz=q.exterior.xy;ax.plot(xx,zz,color=color,linewidth=lw)
        elif q.geom_type=='LineString':xx,zz=q.xy;ax.plot(xx,zz,color=color,linewidth=lw)
    for v in row['cached_rail_evidence']:geo(v['geometry'],'#8b5b2b',1)
    geo(row['core_geometry'],'#ef651e',2);geo(row['hall_geometry'],'#2050f0',2)
    for p in row['platforms']:geo(p['geometry'],'#f0d000',2)
    for line in row['rail_lines']:
        q=np.asarray(line['centreline']);ax.plot(q[:,0],q[:,1],color='#000000',linewidth=2)
    if row['access_corridor']:
        q=np.asarray(row['access_corridor']['centreline_xz']);ax.plot(q[:,0],q[:,1],color='#30bc40',linewidth=3)
    for t in row['street_targets']:ax.plot(t['xyz'][0],t['xyz'][2],'co',markersize=3)
    ax.set_xlim(x,X);ax.set_ylim(Z,z);ax.set_aspect('equal');ax.set_title(slug+' | measured ground + candidate footprint\ncyan existing public, brown GIS rail, green candidate access, orange core')
    ax.set_xlabel('world X');ax.set_ylabel('world Z');fig.tight_layout();fig.savefig(out/(slug+'-plan.png'));plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in ('source','authority','geography','programme','features','out'):p.add_argument('--'+k,type=Path,required=True)
    run(p.parse_args())
