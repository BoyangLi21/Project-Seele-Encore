"""Compose real-road districts from measured chunks and preserved parcel contents.

This prepares exact reversible arrays outside the save. Unknown structures,
existing actors, the lift city and the underground complex are never rebuilt.
"""
import argparse,copy,heapq,json,math
from collections import defaultdict,deque
from pathlib import Path
import nbtlib
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from author_hakone_district_blocks import author
from plan_hakone_main_districts import ROAD_MATERIALS
from plan_ashi_landscape_r54 import NATURAL
from prepare_hakone_main_terrain import sample_grid
from hakone_earthworks import grade_ground,grade_development,edge_defects


def line(a,b):
    n=max(abs(a[0]-b[0]),abs(a[1]-b[1]))
    return [tuple(map(int,p))for p in np.rint(np.linspace(a,b,n+1))]


def route(start,goal,blocked,bounds,limit=30000):
    x0,z0,x1,z1=bounds;queue=[(0,0,start)];cost={start:0};parent={}
    while queue:
        _,g,p=heapq.heappop(queue)
        if g!=cost[p]:continue
        if p==goal:
            points=[p]
            while p in parent:p=parent[p];points.append(p)
            return points[::-1]
        for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
            q=(p[0]+dx,p[1]+dz)
            if not(x0<=q[0]<=x1 and z0<=q[1]<=z1)or(blocked[q[1]-z0,q[0]-x0]and q!=goal):continue
            ng=g+1
            if ng<cost.get(q,10**12):
                cost[q]=ng;parent[q]=p;heapq.heappush(queue,(ng+abs(q[0]-goal[0])+abs(q[1]-goal[1]),ng,q))
        if len(cost)>limit:return None


def prepare(a):
    (a.candidate/'functional-check.json').write_text(json.dumps(dict(errors=['Candidate preparation has not completed'])),'utf8')
    plan=json.loads((a.candidate/'district-plan.json').read_text('utf8'));bounds=plan['bounds_xz'];x0,z0,x1,z1=bounds
    with np.load(a.candidate/'district-plan.npz')as file:d={k:file[k]for k in file.files}
    with np.load(a.candidate/'measured.npz')as file:m={k:file[k]for k in file.files}
    rows={r['id']:r for r in json.loads((a.parcels/'manifest.json').read_text('utf8'))['plots']}
    shape=d['target'].shape;target=d['target'].copy();oldlot=np.zeros(shape,bool);owned=defaultdict(list)
    retained_station_file=a.candidate/'retained-station-ground.json'
    station_ground=json.loads(retained_station_file.read_text('utf8'))if retained_station_file.exists()else[]
    def below_station_soil(x,y,z):
        # An old native deck below the new hillside is a separate vertical
        # layer. Treating it as a soil anchor cut the mountain beneath Owakudani
        # by almost ninety blocks. Its physical volume remains preserved.
        return any(height-y>max(left-x,0,x-right)+max(top-z,0,z-bottom)
                   for left,top,right,bottom,height in station_ground)
    zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    with np.load(a.candidate.parent/'lake-basin-mask.npz')as f:lake_grid={k:f[k]for k in('x','z','lake')}
    lake=sample_grid(lake_grid,'lake',xx,zz,True)
    # Coarse GSI inland-water pixels also cover river ribbons. Keeping the
    # previous world's soil height under all those pixels left scattered old
    # ridges beside the new streets. Only the installed lake is immutable;
    # rivers are authored below as channels in the same terrain surface.
    released_water=d['water']&~lake
    with np.load(a.candidate.parent/'terrain-design.npz')as f:grid={k:f[k]for k in('x','z','height_y')}
    surveyed=np.rint(sample_grid(grid,'height_y',xx,zz)).astype(np.int16)
    target[released_water]=surveyed[released_water];d['water']=lake
    for row in rows.values():
        b=row['source_bounds_xyz'];oldlot[b[2]-z0:b[5]-z0+1,b[0]-x0:b[3]-x0+1]=True
        for cx in range(b[0]//16,b[3]//16+1):
            for cz in range(b[2]//16,b[5]//16+1):owned[cx,cz].append(b)
    # Surface roads follow real vectors. Existing bridges can be crossed below
    # their deck; their actual supports are retained and reported separately.
    road_image=Image.new('L',(shape[1],shape[0]));walk_image=road_image.copy()
    for street in plan['streets']:
        if street['tunnel']:continue
        points=[(round(x-x0),round(z-z0))for x,z in street['points']]
        if street['width']:ImageDraw.Draw(road_image).line(points,fill=1,width=street['width'])
        ImageDraw.Draw(walk_image).line(points,fill=1,width=street['width']+4 if street['width']else 3)
    road=np.asarray(road_image,bool)&~d['fixed']&~d['water'];walk=np.asarray(walk_image,bool)&~d['fixed']&~d['water']
    detour_file=a.candidate/'road-detours.json'
    port_file=a.candidate/'retained-port-profiles.json'
    port_profiles=json.loads(port_file.read_text('utf8'))if port_file.exists()else[]
    subsurface_ports=[p for p in port_profiles if any(below_station_soil(x,y,z)for x,y,z in p['points'])]
    port_profiles=[p for p in port_profiles if p not in subsurface_ports]
    prior_port_walk=walk.copy()
    if detour_file.exists():
        retained=np.load(a.candidate/'road-retained-interfaces.npy');road&=~retained;walk&=~retained
        road_image=Image.fromarray(road.astype(np.uint8));walk_image=Image.fromarray(walk.astype(np.uint8))
        for path in json.loads(detour_file.read_text('utf8'))['paths']:
            points=[(x-x0,z-z0)for x,z in path['points']]
            ImageDraw.Draw(road_image).line(points,fill=1,width=path['width'])
            ImageDraw.Draw(walk_image).line(points,fill=1,width=path['width']+4)
        prior_port_walk=np.asarray(walk_image,bool).copy()
        for path in port_profiles:
            if not path['points']:raise ValueError('Unresolved retained street interface')
            points=[(x-x0,z-z0)for x,y,z in path['points']]
            ImageDraw.Draw(road_image).line(points,fill=1,width=path['width'])
            ImageDraw.Draw(walk_image).line(points,fill=1,width=path['walk_width'])
        road=np.asarray(road_image,bool);walk=np.asarray(walk_image,bool)
    # Acute vector joins can rasterize a narrow stroke a pixel beyond a wider
    # one. Every carriageway cell must participate in grading and construction.
    walk|=road
    # Streets follow surveyed relief rather than inherited flat railway
    # terraces. Old native rail remains below overpasses where appropriate.
    zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    # Roads and soil must start from the SAME terrain surface, including the
    # interfaces with the retained city. Raw DEM road heights over blended old
    # soil previously produced vertical roadside walls of more than 30 blocks.
    roadheight=target.copy()
    roadheight=np.clip(roadheight,32,290)
    for _ in range(32):
        for dst,src in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),(np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])]:
            active=walk[dst]&walk[src]
            roadheight[dst][active]=np.minimum(roadheight[dst][active],roadheight[src][active]+1)
    # Join vector fragments at tile seams before setting a tunnel profile;
    # the tunnel's road follows its portals, not the mountain surface above it.
    tunnels=[list(map(tuple,s['points']))for s in plan['streets']if s['tunnel']]
    joined=True
    while joined:
        joined=False
        for i in range(len(tunnels)):
            for j in range(i+1,len(tunnels)):
                hit=False
                for reverse_a in (False,True):
                    for reverse_b in (False,True):
                        left=tunnels[i][::-1]if reverse_a else tunnels[i];right=tunnels[j][::-1]if reverse_b else tunnels[j]
                        if math.dist(left[-1],right[0])<=2:
                            tunnels[i]=left+right;tunnels.pop(j);joined=True;hit=True;break
                    if hit:break
                if hit:break
            if joined:break
    tunnel=np.zeros(shape,bool);tunnel_operations=[];tunnel_walk=[];tunnel_specs=[]
    tunnel_floor=np.full(shape,-32768,np.int16);tunnel_distance=np.full(shape,1e9,np.float32)
    for points in tunnels:
        samples=[]
        for p,q in zip(points,points[1:]):samples.extend(line(tuple(map(round,p)),tuple(map(round,q))))
        if not samples or any(not(x0+6<=x<=x1-6 and z0+6<=z<=z1-6)for x,z in samples):continue
        tunnel_specs.append(samples)
        first,last=samples[0],samples[-1];y0=int(roadheight[first[1]-z0,first[0]-x0]);y1=int(roadheight[last[1]-z0,last[0]-x0])
        for i,(x,z)in enumerate(samples):
            y=round(y0+(y1-y0)*i/max(1,len(samples)-1))
            for dx in range(-5,6):
                for dz in range(-5,6):
                    iz,ix=z+dz-z0,x+dx-x0
                    if d['fixed'][iz,ix]:continue
                    tunnel[iz,ix]=True
                    distance=dx*dx+dz*dz
                    if distance<tunnel_distance[iz,ix]:tunnel_floor[iz,ix]=y;tunnel_distance[iz,ix]=distance
            tunnel_walk.append([x,y+1,z])
    for iz,ix in np.argwhere(tunnel):
        x,z,y=int(ix+x0),int(iz+z0),int(tunnel_floor[iz,ix])
        material='minecraft:black_concrete'if tunnel_distance[iz,ix]<=9 else'minecraft:smooth_stone'
        tunnel_operations.extend([[x,y-1,z,x,y-1,z,'minecraft:stone_bricks'],[x,y,z,x,y,z,material],
                                  [x,y+1,z,x,y+5,z,'minecraft:air'],[x,y+6,z,x,y+6,z,'minecraft:stone_bricks']])
    for point in tunnel_walk:point[1]=int(tunnel_floor[point[2]-z0,point[0]-x0])+1
    bridge=d['river']&walk&~tunnel
    ramp=np.asarray(Image.fromarray(bridge.astype(np.uint8)).filter(ImageFilter.MaxFilter(13)),bool)&walk&~tunnel
    inner=np.asarray(Image.fromarray(bridge.astype(np.uint8)).filter(ImageFilter.MaxFilter(5)),bool)&walk&~tunnel
    roadheight[ramp]+=1;roadheight[inner]+=1;roadheight[bridge]+=1
    target[walk]=roadheight[walk];street_height=roadheight.copy()
    footprint=np.zeros(shape,bool)
    for site in plan['parcels']:
        x,z=site['centre'];hx,hz=site['half'];rx,rz=(hx,hz)if site['rotation']%2==0 else(hz,hx)
        footprint[z-rz-z0-2:z+rz-z0+3,x-rx-x0-2:x+rx-x0+3]=True
    operations=[];reports=[];devices=[];walkpoints=[];doors=[];footways=[];components=[]
    tunnel_border=np.asarray(Image.fromarray(tunnel).filter(ImageFilter.MaxFilter(3)),bool)
    path_blocked=d['held']|d['rail']|d['water']|footprint|tunnel_border
    prior_paths=np.zeros(shape,bool)
    for site in plan['parcels']:
        px,pz=site['street'];site=copy.deepcopy(site);site['floor']=int(street_height[pz-z0,px-x0])+1
        row=rows[site['source_id']];c,report=author(site,row,a.parcels)
        x,z=site['centre'];hx,hz=site['half'];rx,rz=(hx,hz)if site['rotation']%2==0 else(hz,hx)
        area=np.s_[z-rz-z0-2:z+rz-z0+3,x-rx-x0-2:x+rx-x0+3]
        target[area]=site['floor'];road[area]=False;walk[area]=False
        start=(report['approach'][0],report['approach'][2]);goal=(px,pz)
        blocked=path_blocked|(prior_paths&(np.abs(target-site['floor'])>1))
        # The public porch extends three blocks beyond its own footprint.
        path=route(start,goal,blocked,bounds)
        if not path:raise ValueError('No public entrance path for '+row['id'])
        if len(path)>120:raise ValueError('Unexpected frontage detour for '+row['id'])
        f=site['floor'];points=[]
        for i,(xx,zz)in enumerate(path):
            floor=round(f+(street_height[pz-z0,px-x0]-f)*i/max(1,len(path)-1))
            # Two walking lanes beside a low curb. Public paths meet the
            # existing carriageway grade without an inaccessible final ledge.
            for dx,dz in [(0,0),(1,0),(-1,0),(0,1),(0,-1)]:
                qz,qx=zz+dz-z0,xx+dx-x0
                if d['fixed'][qz,qx]or d['protected'][qz,qx]or d['water'][qz,qx]:
                    if(dx,dz)==(0,0):raise ValueError('Entrance meets retained structure')
                    continue
                target[qz,qx]=floor;walk[qz,qx]=True
                prior_paths[qz,qx]=True
            points.append([xx,floor+1,zz])
        report['footway']=points;report['devices']=[{k:v for k,v in r.items()if k in ('source','target')}for r in c.devices]
        operations.extend(c.operations);devices.extend(c.devices);walkpoints.extend(c.walk);doors.extend(c.doors);footways.extend(points);reports.append(report);components.append((c,report))
    # Preserve original street interfaces at the installed city boundary.
    # Their route and final terrain are included in the same reversible delta.
    links=[];street_pixels=np.argwhere(road&~d['held'])
    previous_obstacles=np.zeros(shape,bool)
    surface_file=a.candidate/'district-surface.npz'
    if surface_file.exists():
        with np.load(surface_file)as old:
            if 'ground_obstruction'in old:previous_obstacles=np.asarray(Image.fromarray(old['ground_obstruction']).filter(ImageFilter.MaxFilter(7)),bool)
    # The north access terminates at the retained launch apron, not an outer
    # public road. Keep that access untouched; west and south join the city.
    for sx,sy,sz in [(-344,84,232),(30,80,688)]:
        candidates=street_pixels[np.argsort((street_pixels[:,1]+x0-sx)**2+(street_pixels[:,0]+z0-sz)**2)[:18000]]
        wide_fixed=np.asarray(Image.fromarray(d['fixed']).filter(ImageFilter.MaxFilter(9)),bool)
        blocked=d['held']|footprint|d['water']|prior_paths|wide_fixed|previous_obstacles
        blocked=blocked.copy()
        # Original paved interfaces are an explicit retained public route.
        blocked[d['legacy']&~footprint&~d['water']&~prior_paths&~wide_fixed&~previous_obstacles]=False
        lead=line((sx,sz),(sx-6,sz)if sx<0 else(sx,sz+6))
        for qx,qz in lead:blocked[qz-z0,qx-x0]=False
        found=None
        for gz,gx in candidates[::30]:
            goal=(int(gx+x0),int(gz+z0));path=route(lead[-1],goal,blocked,bounds)
            if path:path=lead[:-1]+path
            if path and abs(int(street_height[gz,gx])-sy)<=len(path)//2:found=(goal,path);break
        if not found:raise ValueError(f'No district connection from {(sx,sz)}')
        goal,path=found;ey=int(street_height[goal[1]-z0,goal[0]-x0]);points=[]
        if abs(ey-sy)>len(path)//2:raise ValueError('Steep city street connection')
        for i,(xx,zz)in enumerate(path):
            floor=round(sy+(ey-sy)*i/max(1,len(path)-1))
            for dx in range(-2,3):
                for dz in range(-2,3):
                    qz,qx=zz+dz-z0,xx+dx-x0
                    if footprint[qz,qx]or(d['held'][qz,qx]and not d['legacy'][qz,qx]):continue
                    target[qz,qx]=floor;walk[qz,qx]=True
                    if abs(dx)<=1 and abs(dz)<=1:road[qz,qx]=True
            points.append([xx,floor+1,zz])
        links.append(dict(start=[sx,sy+1,sz],end=[*goal],points=points));walkpoints.extend(points)
    # Solve the joined surface street grades before placing building floors.
    # Tunnels are separate 3D corridors; their low floor must not tear a deep
    # crack through an unrelated surface road at the same X/Z crossing.
    for iteration in range(384):
        changed=0
        for dst,src in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),(np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])]:
            active=walk[dst]&walk[src]&(target[dst]>target[src]+1)
            changed+=int(active.sum());target[dst][active]=target[src][active]+1
        if not changed:break
    else:raise ValueError('Street grade propagation did not converge')
    plot_areas=[]
    for c,report in components:
        x,z=c.site['centre'];hx,hz=c.site['half'];rx,rz=(hx,hz)if c.site['rotation']%2==0 else(hz,hx)
        plot_areas.append(np.s_[z-rz-z0-2:z+rz-z0+3,x-rx-x0-2:x+rx-x0+3])
    # Treat the original city streets as real ports with measured heights.
    # A later junction solve must not silently lift their first step.
    fixed_grades=np.zeros(shape,bool)
    city=json.loads((a.candidate.parent/'city-south-layout-preserved/plan.json').read_text('utf8'))
    for left,top,right,bottom in city['cross_rectangles_xz']:
        area=np.s_[max(0,top-z0):min(shape[0],bottom-z0+1),max(0,left-x0):min(shape[1],right-x0+1)]
        target[area]=80;fixed_grades[area]=True
    target[lake]=99;fixed_grades|=lake
    if station_ground:
        for left,top,right,bottom,y in station_ground:
            area=np.s_[max(0,top-z0):min(shape[0],bottom-z0+1),max(0,left-x0):min(shape[1],right-x0+1)]
            land=~lake[area];target[area][land]=y;fixed_grades[area]|=land
    for sx,sy,sz in[(-344,84,232),(30,80,688)]:
        area=np.s_[sz-z0-2:sz-z0+3,sx-x0-2:sx-x0+3]
        target[area]=sy;fixed_grades[area]=True
    retained_grades=a.candidate/'retained-road-grades.json'
    if retained_grades.exists():
        for row in json.loads(retained_grades.read_text('utf8'))['anchors']:
            x,y,z=row['point']
            if prior_port_walk[z-z0,x-x0]and not below_station_soil(x,y,z):target[z-z0,x-x0]=y;fixed_grades[z-z0,x-x0]=True
    for profile in port_profiles:
        for x,y,z in profile['points']:
            target[z-z0,x-x0]=y;fixed_grades[z-z0,x-x0]=True
    port_surfaces=a.candidate/'retained-port-surface-grades.json'
    if port_surfaces.exists():
        for x,y,z in json.loads(port_surfaces.read_text('utf8')):
            if walk[z-z0,x-x0]and not below_station_soil(x,y,z):target[z-z0,x-x0]=y;fixed_grades[z-z0,x-x0]=True
    try:target=grade_development(target,walk|footprint,plot_areas,fixed=fixed_grades)
    except ValueError:
        np.savez_compressed(a.candidate/'failed-grade-constraints.npz',bounds=bounds,target=target,fixed=fixed_grades)
        raise
    for (c,report),plot_area in zip(components,plot_areas):
        floor=int(target[plot_area][0,0]);dy=floor-c.site['floor'];c.site['floor']=floor
        if dy:
            for op in c.operations:op[1]+=dy;op[4]+=dy
            for point in c.walk+c.doors:point[1]+=dy
            report['door'][1]+=dy;report['approach'][1]+=dy
            for item in c.devices:
                item['target'][1]+=dy;item['after']['y']=nbtlib.Int(int(item['after']['y'])+dy)
        x,z=c.site['centre'];hx,hz=c.site['half'];rx,rz=(hx,hz)if c.site['rotation']%2==0 else(hz,hx)
        target[z-rz-z0-2:z+rz-z0+3,x-rx-x0-2:x+rx-x0+3]=floor
    # Portal grades follow the now-connected street, including city approach
    # ramps. Reusing pre-junction heights would leave a step at tunnel mouths.
    tunnel_floor.fill(-32768);tunnel_operations=[]
    pending=set(map(tuple,np.argwhere(tunnel)));centres={(z-z0,x-x0)for x,_,z in tunnel_walk}
    while pending:
        seed=next(iter(pending));pending.remove(seed);queue=deque([seed]);component=[seed]
        while queue:
            z,x=queue.popleft()
            for dz,dx in [(1,0),(-1,0),(0,1),(0,-1)]:
                q=(z+dz,x+dx)
                if q in pending:pending.remove(q);component.append(q);queue.append(q)
        centre=np.asarray([q for q in component if q in centres],float)
        if not len(centre):raise ValueError('Tunnel mask lacks centreline')
        axis=centre.max(0)-centre.min(0);axis/=max(1,float(np.linalg.norm(axis)))
        # The sign of each coordinate follows the measured end-to-end trend.
        covariance=np.cov(centre.T)
        if covariance.shape==(2,2)and covariance[0,1]<0:axis[1]*=-1
        projection=centre@axis;first=centre[projection.argmin()].astype(int);last=centre[projection.argmax()].astype(int)
        y0=int(target[tuple(first)]if walk[tuple(first)]else roadheight[tuple(first)])
        y1=int(target[tuple(last)]if walk[tuple(last)]else roadheight[tuple(last)])
        lo,hi=float(projection.min()),float(projection.max())
        for z,x in component:
            fraction=np.clip((np.dot([z,x],axis)-lo)/max(1,hi-lo),0,1)
            y=round(y0+(y1-y0)*float(fraction))
            if walk[z,x]and abs(int(target[z,x])-y)<=3:y=int(target[z,x])
            elif walk[z,x]and 3<int(target[z,x])-y<6:y=int(target[z,x])-6
            tunnel_floor[z,x]=y
    # A surface footway crossing over a shallow tunnel owns its own level.
    # Keep the ceiling at or below that floor, then grade the tunnel approach.
    for _ in range(128):
        changed=False
        for dst,src in[(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),(np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])]:
            use=tunnel[dst]&tunnel[src]&(tunnel_floor[dst]>tunnel_floor[src]+1)
            if use.any():tunnel_floor[dst][use]=tunnel_floor[src][use]+1;changed=True
        if not changed:break
    for iz,ix in np.argwhere(tunnel):
        x,z,y=int(ix+x0),int(iz+z0),int(tunnel_floor[iz,ix]);material='minecraft:black_concrete'if tunnel_distance[iz,ix]<=9 else'minecraft:smooth_stone'
        tunnel_operations.extend([[x,y-1,z,x,y-1,z,'minecraft:stone_bricks'],[x,y,z,x,y,z,material],
                                  [x,y+1,z,x,y+5,z,'minecraft:air'],[x,y+6,z,x,y+6,z,'minecraft:stone_bricks']])
    for point in tunnel_walk:point[1]=int(tunnel_floor[point[2]-z0,point[0]-x0])+1
    tunnel_structures={id(op)for op in tunnel_operations if op[-1]=='minecraft:stone_bricks'}
    tunnel_geometry={id(op)for op in tunnel_operations}
    operations.extend(tunnel_operations);walkpoints.extend(tunnel_walk)
    soil_anchors=(walk|footprint|fixed_grades)&~tunnel&~ramp
    graded,conflicts=grade_ground(target,soil_anchors,target)
    if getattr(a,'surface_only',False):
        active=~d['fixed']&~d['water']
        final_ground=np.where(active,graded,m['top'])
        final_ground[walk|footprint]=target[walk|footprint]
        edges=edge_defects(final_ground,soil_anchors)
        np.savez_compressed(a.candidate/'coupled-grading.npz',bounds=bounds,target=target,graded=graded,
            anchors=soil_anchors,conflicts=conflicts,walk=walk,road=road,footprint=footprint,tunnel=tunnel,ramp=ramp,final_ground=final_ground)
        (a.candidate/'ground-interface-errors.json').write_text(json.dumps([[x+x0,z+z0,axis,height]for x,z,axis,height in edges]),'utf8')
        (a.candidate/'neighbourhood-design.json').write_text(json.dumps(reports,ensure_ascii=False),'utf8')
        print('Offline surface design:',int(conflicts.sum()),'contradictory grade cells; no block patch emitted',flush=True)
        return
    if conflicts.any():
        raise ValueError('Conflicting district terrace grades: '+str(int(conflicts.sum())))
    flexible=~d['fixed']&~d['water']&~tunnel&~ramp
    target[flexible]=graded[flexible]
    # Adjacent path widths share one surface. Reconcile their centre elevations
    # after all junctions, before emitting walking evidence or block arrays.
    for report in reports:
        for point in report['footway']:
            iz,ix=point[2]-z0,point[0]-x0;floor=int(target[iz,ix])
            if tunnel[iz,ix]and abs(int(tunnel_floor[iz,ix])-floor)<=3:floor=int(tunnel_floor[iz,ix])
            point[1]=floor+1
    footways=[p for r in reports for p in r['footway']]
    for link in links:
        for point in link['points']:point[1]=int(target[point[2]-z0,point[0]-x0])+1
    # Register cuboids by touched chunk, preserving their authoring order.
    op_by_chunk=defaultdict(list)
    for op in operations:
        for cx in range(op[0]//16,op[3]//16+1):
            for cz in range(op[2]//16,op[5]//16+1):op_by_chunk[cx,cz].append(op)
    sources=sorted((a.candidate/'source').glob('*.npz'));yy=np.arange(-128,320)[:,None,None]
    total=0;regions=[];obstructed=[];ground_obstruction=np.zeros(shape,bool);check_points=defaultdict(list);check_devices=defaultdict(list);errors=[]
    for report in reports:
        for p,q in zip(report['footway'],report['footway'][1:]):
            if abs(p[1]-q[1])>1:errors.append(['path-grade',report['id'],p,q])
    for dst,src in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:,1:],np.s_[:,:-1])]:
        bad=(np.abs(target[dst]-target[src])>1)&road[dst]&road[src]
        if bad.any():errors.append(['road-grade',int(bad.sum())])
    for point in walkpoints+footways:check_points[point[0]//16,point[2]//16].append(point)
    for point in doors:check_devices[point[0]//16,point[2]//16].append(('door',point))
    for item in devices:check_devices[item['target'][0]//16,item['target'][2]//16].append(('device',item['target']))
    surface_top=m['highest'].copy();surface_ids=np.zeros(shape,np.uint16);surface_palette=['minecraft:air'];surface_lookup={'minecraft:air':0}
    for num,file in enumerate(sources):
        with np.load(file)as data:coords=data['coordinates'];blocks=data['blocks'];palette=list(map(str,data['palette']))
        lookup={s:i for i,s in enumerate(palette)}
        def code(state):
            if state not in lookup:lookup[state]=len(palette);palette.append(state)
            return lookup[state]
        air,stone,dirt,grass,asphalt,paving,stripe,gravel,water=[code(s)for s in (
            'minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]',
            'minecraft:black_concrete','minecraft:smooth_stone','minecraft:white_concrete','minecraft:gravel','minecraft:water[level=0]')]
        for op in operations:code(op[-1])
        natural=np.asarray([s.split('[')[0]in NATURAL for s in palette]);paved=np.asarray([s.split('[')[0]in ROAD_MATERIALS for s in palette])
        changes=[];ranges=[0];offsets=[];priors=[];afters=[]
        for i,(cx,cz)in enumerate(coords):
            area=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16];old=blocks[i];new=old.copy()
            allow=natural[old].copy();lot=np.zeros(old.shape,bool)
            for b in owned[cx,cz]:
                lo=np.maximum([cx*16,-128,cz*16],b[:3]);hi=np.minimum([cx*16+16,320,cz*16+16],np.array(b[3:])+1)
                lot[lo[1]+128:hi[1]+128,lo[2]-cz*16:hi[2]-cz*16,lo[0]-cx*16:hi[0]-cx*16]=True
            allow|=lot
            oldroads=paved[old]&d['legacy'][area]&(yy>=d['legacy_y'][area]-2)&(yy<=d['legacy_y'][area]+8)
            allow|=oldroads
            h=target[area];land_h=np.where(tunnel[area]|ramp[area],d['target'][area],h)
            # An overhead rail beam must not freeze a whole 448-block soil
            # column into a mesa. Preserve its complete vertical structure and
            # air volume while grading the surrounding natural ground.
            foreign=~allow
            structure_low=np.where(foreign,yy,320).min(0)-1
            structure_high=np.where(foreign,yy,-129).max(0)+6
            structure_volume=(yy>=structure_low)&(yy<=structure_high)
            active=~d['fixed'][area]&~d['water'][area]
            lower=np.maximum(32,np.minimum(m['top'][area],land_h)-3);upper=np.maximum(m['highest'][area],land_h+6)
            band=active&(yy>=lower)&(yy<=upper)&allow&~structure_volume
            proposed=np.where(yy>land_h,air,np.where(yy==land_h,grass,np.where(yy>=land_h-3,dirt,stone))).astype(np.uint16)
            new[band]=proposed[band]
            # Old component shells can extend beyond soil-level grading bands.
            retired=lot&~d['fixed'][area]&(yy>=h+1);new[retired]=air
            # Rivers have open banks and a shallow, continuous water bed. At a
            # carriageway crossing the road deck stays above the waterway.
            wet=d['river'][area]&active&~footprint[area]
            for dy,material in [(-2,gravel),(-1,water),(0,water)]:
                mask=wet&(yy==land_h+dy)&allow;new[mask]=material
            rw=walk[area]&~d['water'][area];rh=target[area]
            surface_band=rw&(yy>=rh-1)&(yy<=rh+5)
            ground_obstruction[area]=((yy>rh)&(yy<=rh+5)&~allow).any(0)
            collision=ground_obstruction[area]&rw
            if collision.any():
                for zz,xx in np.argwhere(collision):obstructed.append([int(cx*16+xx),int(rh[zz,xx]),int(cz*16+zz)])
            rw&=~collision
            clear=rw&(yy>rh)&(yy<=rh+5);new[clear]=air
            new[rw&(yy==rh-1)&allow]=stone
            material=np.where(road[area],asphalt,paving)
            zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
            material=np.where(road[area]&d['centre'][area]&((xx+zz)%9<5),stripe,material)
            mask=rw&(yy==rh)&allow;new[mask]=np.broadcast_to(material,new.shape)[mask]
            for op in op_by_chunk[cx,cz]:
                lo=np.maximum([cx*16,-128,cz*16],op[:3]);hi=np.minimum([cx*16+16,320,cz*16+16],np.array(op[3:6])+1)
                s=np.s_[lo[1]+128:hi[1]+128,lo[2]-cz*16:hi[2]-cz*16,lo[0]-cx*16:hi[0]-cx*16]
                if not allow[s].all():
                    # A tunnel ceiling may meet the underside of an existing
                    # concrete railway deck. Keep that load-bearing block;
                    # it already closes the roof and has no device to replace.
                    if id(op)in tunnel_structures:
                        new[s][allow[s]]=code(op[-1]);continue
                    local=np.argwhere(~allow[s])[0];pos=[int(lo[0]+local[2]),int(lo[1]+local[0]),int(lo[2]+local[1])]
                    if id(op)in tunnel_geometry:
                        if op[-1]=='minecraft:air':errors.append(['tunnel-retained-crossing',pos,op])
                        new[s][allow[s]]=code(op[-1]);continue
                    raise ValueError(f'Authored geometry {op} intersects retained {palette[old[tuple(local+np.array([lo[1]+128,lo[2]-cz*16,lo[0]-cx*16]))]]} at {pos}')
                new[s]=code(op[-1])
            def state(p):return palette[new[p[1]+128,p[2]-cz*16,p[0]-cx*16]]
            for point in check_points[cx,cz]:
                x,y,z=point;body=state(point);head=state([x,y+1,z]);below=state([x,y-1,z])
                if body.split('[')[0]not in ('minecraft:air','minecraft:cave_air')or head.split('[')[0]not in ('minecraft:air','minecraft:cave_air'):errors.append(['path-headroom',point,body,head])
                if below.split('[')[0]in ('minecraft:air','minecraft:cave_air','minecraft:water'):errors.append(['path-floor',point,below])
            for kind,point in check_devices[cx,cz]:
                if(kind=='door'and 'door'not in state(point))or(kind=='device'and state(point).split('[')[0]=='minecraft:air'):errors.append([kind,point,state(point)])
            present=new!=air;top=np.where(present,yy,-129).max(0).astype(np.int16);surface_top[area]=top
            topid=np.take_along_axis(new,np.maximum(0,top+128)[None,:,:],axis=0)[0]
            for value in np.unique(topid):
                name=palette[value]
                if name not in surface_lookup:surface_lookup[name]=len(surface_palette);surface_palette.append(name)
                surface_ids[area][topid==value]=surface_lookup[name]
            at=np.flatnonzero((old!=new).ravel()).astype(np.uint32)
            if len(at):
                changes.append((cx,cz));offsets.append(at);priors.append(old.ravel()[at]);afters.append(new.ravel()[at]);ranges.append(ranges[-1]+len(at))
        if changes:
            name='delta/'+file.name
            np.savez_compressed(a.candidate/name,coordinates=np.asarray(changes,np.int32),ranges=np.asarray(ranges,np.int64),indices=np.concatenate(offsets),before=np.concatenate(priors),after=np.concatenate(afters),palette=np.asarray(palette))
            total+=ranges[-1];regions.append(dict(path=name,cells=ranges[-1]))
        print(f'District blocks {num+1}/{len(sources)}; {total:,} edits',flush=True)
    if len({tuple(r['target'])for r in devices})!=len(devices):errors.append(['overlapping-devices'])
    changes={}
    for item in devices:
        changes.setdefault(tuple(item['source']),nbtlib.Compound())['Before']=item['before']
        changes.setdefault(tuple(item['target']),nbtlib.Compound())['After']=item['after']
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changes.values())}).save(a.candidate/'block-entities.dat',gzipped=True)
    report=dict(schema='projectseele.hakone-districts.v1',world=plan['world'],world_written=False,cells=total,regions=regions,
                bounds_xz=bounds,parcel_count=len(reports),devices=len(devices),progress_files_written=[],
                source='Cached GSI road centre lines, building distribution and DEM; adapted fictional street uses')
    (a.candidate/'manifest.json').write_text(json.dumps(report,indent=2),'utf8')
    (a.candidate/'neighbourhood.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),'utf8')
    (a.candidate/'street-connections.json').write_text(json.dumps(links,indent=2),'utf8')
    np.savez_compressed(a.candidate/'district-surface.npz',bounds=bounds,target=target,road=road,walk=walk,ground_obstruction=ground_obstruction,top=surface_top,palette=np.asarray(surface_palette),states=surface_ids)
    result=dict(errors=errors,road_conflicts=obstructed,subsurface_ports_pending=subsurface_ports,parcels=len(reports),preserved_devices=len(devices),walk_points=len(walkpoints)+len(footways),visual_verified=False)
    (a.candidate/'functional-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Prepared districts:',len(reports),'functional path issues:',len(errors),'road interfaces:',len(obstructed),flush=True)
    if errors:raise ValueError('Resolve authored path errors before installing')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--surface-only',action='store_true',help='Produce an offline grading design without authoring block arrays')
    for name in ('candidate','parcels'):p.add_argument('--'+name,type=Path,required=True)
    prepare(p.parse_args())
