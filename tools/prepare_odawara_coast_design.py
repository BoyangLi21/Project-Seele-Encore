"""Plan a finite Miyukinohama promenade from current blocks and GSI shoreline.

Existing downtown blocks remain owned by their installed district. The future
coastal bypass gets explicit pedestrian crossing volumes for the civil stage;
its absence is not reported as a completed road or bridge.
"""
import argparse,copy,gzip,heapq,json,math
from pathlib import Path
import nbtlib
import numpy as np
from scipy.ndimage import binary_dilation,distance_transform_edt
from scipy.spatial import cKDTree
from shapely import contains_xy
from shapely.geometry import LineString,Point,box,mapping,shape
from shapely.ops import unary_union
from author_hakone_lakefront import Editor
from install_r53_carrier_trays import stopped_world
from map_pipeline.corridors import alignment
from query_blocks import iter_block_entities

def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')

def restore_vacated_ground(survey,rows,before_source,bounds):
    """Reclaim former foundation cuts using the measured pre-building soil."""
    x,z,X,Z=bounds
    with np.load(before_source/'measured.npz')as f:bx,bz,bX,bZ=map(int,f['bounds']);before=f['top'];full=f['full']
    with np.load(survey/'surface.npz')as f:d={k:f[k]for k in f.files}
    for row in rows:
        a,_,b,c,_,e=row['payload_bounds'];a,b,c,e=a-3,b-3,c+3,e+3
        if not(bx<=a<=c<=bX and bz<=b<=e<=bZ):raise ValueError('Incomplete pre-building ground capture')
        src=np.s_[b-bz:e-bz+1,a-bx:c-bx+1]
        if not full[src].all():raise ValueError('Unknown pre-building soil')
        d['surveyed'][b-z:e-z+1,a-x:c-x+1]=before[src]
    np.savez_compressed(survey/'surface.npz',**d)

def pathfind(start,goal,blocked,cost):
    queue=[(0,0,start)];best={start:0};previous={}
    while queue:
        _,d,p=heapq.heappop(queue)
        if d!=best[p]:continue
        if p==goal:
            result=[p]
            while p!=start:p=previous[p];result.append(p)
            return result[::-1]
        j,i=p
        for dj,di in ((0,1),(0,-1),(1,0),(-1,0)):
            q=(j+dj,i+di)
            if not(0<=q[0]<blocked.shape[0]and 0<=q[1]<blocked.shape[1])or blocked[q]:continue
            v=d+float(cost[q])
            if v>=best.get(q,math.inf):continue
            best[q]=v;previous[q]=p;heapq.heappush(queue,(v+abs(q[0]-goal[0])+abs(q[1]-goal[1]),v,q))
    raise ValueError(('No coast access',start,goal))

def set_back_coastal_parcels(catalog,oldwalk,oldgrade,ground,highest,wet,sea,bypass,rails,bounds,tags):
    """Move only complete newly authored parcels out of the reserved bypass.

    Keep their orientation, interiors, device NBT and entrance relationship.
    Destinations must be bare measured land next to an existing city street.
    """
    x,z,X,Z=bounds;zz,xx=np.mgrid[z:Z+1,x:X+1]
    moving=[r for r in catalog if r['id'].startswith('odawara-core/')and
            box(r['occupied_bounds'][0],r['occupied_bounds'][2],r['occupied_bounds'][3],r['occupied_bounds'][5]).intersects(bypass.buffer(6))]
    occupied=unary_union([box(r['occupied_bounds'][0]-3,r['occupied_bounds'][2]-3,r['occupied_bounds'][3]+3,r['occupied_bounds'][5]+3)
                         for r in catalog if r['occupied_bounds'][0]<=X and r['occupied_bounds'][3]>=x and r['occupied_bounds'][2]<=Z and r['occupied_bounds'][5]>=z])
    forbidden=binary_dilation(oldwalk,iterations=2)|wet|(highest>ground+2)
    reserved=unary_union([bypass.buffer(9),sea.buffer(17),rails.buffer(2)])
    js,is_=np.where(oldwalk);coords=np.column_stack([is_+x,js+z]);tree=cKDTree(coords)
    rows=[];offsets={};floors={};footways=[];revised=copy.deepcopy(catalog)
    for row in moving:
        b=row['occupied_bounds'];cx,cz=row['site']['centre'];best=None
        facing=np.asarray(row['approach'])[[0,2]]-np.asarray([cx,cz]);facing=facing/np.linalg.norm(facing)
        for dx in sorted(range(-140,142,2),key=abs):
            for dz in sorted(range(-140,142,2),key=abs):
                if dx*dx+dz*dz<400:continue
                if best is not None and dx*dx+dz*dz>=best[0]:continue
                l,t,R,B=b[0]+dx,b[2]+dz,b[3]+dx,b[5]+dz
                if not(3340<=l<R<=3695 and 440<=t<B<=788):continue
                area=np.s_[t-z:B-z+1,l-x:R-x+1]
                if np.any(forbidden[area]):continue
                polygon=box(l,t,R,B)
                if polygon.intersects(occupied)or polygon.intersects(reserved):continue
                approach=np.asarray(row['approach'])[[0,2]]+[dx,dz]
                distances,indices=tree.query(approach,k=48)
                for dist,index in zip(distances,indices):
                    if not 2<=dist<=32:continue
                    endpoint=coords[index];direction=endpoint-approach
                    if np.dot(direction,facing)<1:continue
                    line=LineString([approach,endpoint]);corridor=line.buffer(1.5)
                    # Frontage fixtures can extend the complete payload beyond
                    # its central landing. The copied landing may therefore be
                    # inside this payload; the outward-facing path exits it.
                    if corridor.intersects(occupied)or corridor.intersects(reserved):continue
                    h=int(round(float(oldgrade[js[index],is_[index]])/2))
                    score=dx*dx+dz*dz+dist*dist*4+(h-row['site']['floor'])**2*100
                    if best is None or score<best[0]:best=(score,dx,dz,h,endpoint.tolist(),polygon,corridor)
                    break
        if best is None:raise ValueError(('No complete inland replacement plot',row['id']))
        _,dx,dz,h,end,polygon,corridor=best;dy=h-row['site']['floor']
        r=copy.deepcopy(row);r.update(payload_bounds=b,surveyed_floor=h,use=row.get('use',''),devices=[list(p)for p in tags if all(b[k]<=p[k]<=b[k+3]for k in range(3))])
        rows.append(r);offsets[r['id']]=[dx,dz];floors[r['id']]=h
        approach=[r['approach'][0]+dx,h+1,r['approach'][2]+dz]
        footways.append(dict(parcel=r['id'],points=[approach,[end[0],float(oldgrade[end[1]-z,end[0]-x])/2+1,end[1]]]))
        updated=next(q for q in revised if q['id']==r['id']);updated['occupied_bounds']=[v+[dx,dy,dz][k%3]for k,v in enumerate(b)]
        occupied=unary_union([occupied,polygon.buffer(3),corridor.buffer(1)])
        print('Reserved coastal roadway by relocating complete parcel',r['id'],[dx,dy,dz],flush=True)
    return rows,offsets,floors,footways,revised

def prepare(a):
    a.out.mkdir(parents=True,exist_ok=False);survey=a.out/'survey';survey.mkdir()
    cap=json.loads((a.source/'capture.json').read_text('utf8'));bounds=cap['bounds_xz'];x,z,X,Z=bounds
    if cap['unavailable_chunks']or cap['actors']:raise ValueError('Complete unoccupied coastal source required')
    with np.load(a.source/'measured.npz')as f:ground=f['top'];full=f['full'];highest=f['highest']
    if not full.all():raise ValueError('Unknown coast blocks')
    np.savez_compressed(survey/'surface.npz',bounds=bounds,old_ground=ground,surveyed=ground.astype(float))
    save(survey/'buildings.json',[])
    with stopped_world(Path(cap['world'])):tags={p:copy.deepcopy(t)for p,t in iter_block_entities(Path(cap['world']),'projectseele:geofront',(x,-128,z),(X,319,Z))}
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(tags.values()))}).save(survey/'captured-devices.dat',gzipped=True)
    with np.load(a.authority/'network.npz')as f:
        ax,az,_,_=map(int,f['bounds']);sl=np.s_[z-az:Z-az+1,x-ax:X-ax+1];oldwalk=f['walk'][sl];oldgrade=f['grade2'][sl]
    fs=json.load(gzip.open(a.geography/'features.world.geojson.gz','rt',encoding='utf8'))['features']
    water=unary_union([shape(f['geometry'])for f in fs if f['properties']['source_layer']=='WA'])
    sea=unary_union([shape(f['geometry'])for f in fs if f['properties']['source_layer']=='WA'and f['properties']['vt_code']==5100])
    rails=unary_union([shape(f['geometry'])for f in fs if f['properties']['source_layer']=='RailCL']).buffer(3)
    bypass=unary_union([shape(f['geometry'])for f in fs if f['properties']['source_layer']=='RdCL'and f['properties'].get('vt_tollsect')=='有料'])
    zz,xx=np.mgrid[z:Z+1,x:X+1];wet=contains_xy(water,xx,zz);sea_mask=contains_xy(sea,xx,zz);railmask=contains_xy(rails,xx,zz)
    e=Editor(a.source);actualwater=np.zeros(ground.shape,bool);waterlevel=np.full(ground.shape,-129,np.int16)
    for f in (a.source/'source').glob('*.npz'):
        with np.load(f)as v:coords=v['coordinates'];blocks=v['blocks'];names=list(map(str,v['palette']))
        waterids=np.asarray([n.split('[')[0]=='minecraft:water'for n in names])
        for (cx,cz),v in zip(coords,blocks):
            area=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16]
            top=np.where(waterids[v],np.arange(-128,320)[:,None,None],-129).max(0)
            actualwater[area]=(top>-129)&(top>=ground[area])
            waterlevel[area]=top
    wet|=actualwater
    sea_levels=waterlevel[sea_mask&actualwater]
    if not len(sea_levels)or len(np.unique(sea_levels))!=1:raise ValueError('Coastal water datum is not uniform')
    sea_level=int(sea_levels[0])
    anchor_surface=ground.copy();anchor_surface[actualwater]=waterlevel[actualwater];anchor_surface[sea_mask&~actualwater]=sea_level
    np.savez_compressed(a.out/'water-surface-levels.npz',bounds=bounds,levels=anchor_surface)
    beach=(distance_transform_edt(~sea_mask)<18)&~wet&(zz>=573)&(zz<=814)
    surveyed=ground.astype(float);surveyed[beach]=np.maximum(surveyed[beach],sea_level)
    np.savez_compressed(survey/'surface.npz',bounds=bounds,old_ground=ground,surveyed=surveyed)
    np.savez_compressed(a.out/'geographic-water.npz',bounds=bounds,wet=wet)
    np.savez_compressed(a.out/'geographic-rail.npz',bounds=bounds,blocked=railmask)
    catalog=json.loads((a.authority/'catalog.json').read_text('utf8'))
    moved,offsets,floors,footways,catalog=set_back_coastal_parcels(catalog,oldwalk,oldgrade,ground,highest,wet,sea,bypass,rails,bounds,tags)
    save(survey/'buildings.json',moved);save(a.out/'coastal-parcel-setbacks.json',[dict(id=r['id'],offset=offsets[r['id']],floor=floors[r['id']],old_bounds=r['occupied_bounds'])for r in moved])
    restore_vacated_ground(survey,moved,a.before_downtown_source,bounds)
    parcels=np.zeros(ground.shape,bool)
    for r in catalog:
        A,_,B,C,_,D=r['occupied_bounds'];l,t,R,S=max(x,A-3),max(z,B-3),min(X,C+3),min(Z,D+3)
        if l<=R and t<=S:parcels[t-z:S-z+1,l-x:R-x+1]=True
    blocked=binary_dilation(wet|railmask,iterations=3)|parcels
    blocked[[0,-1]]=True;blocked[:,[0,-1]]=True
    # The dry shore is measured at every row. Keep a six-metre perpendicular
    # setback even where the native water mask is wider than reference geometry.
    coast=[]
    for pz in range(585,802,12):
        candidates=np.flatnonzero((sea_mask|actualwater)[pz-z]&(xx[pz-z]>=3400))
        if not len(candidates):raise ValueError(('No measured coast',pz))
        wanted=int(candidates[0]+x-10)
        usable=[px for px in range(wanted-12,wanted+9)if not blocked[pz-z,px-x]]
        if not usable:raise ValueError(('No dry coastal width between water and retained buildings',wanted,pz))
        px=min(usable,key=lambda v:abs(v-wanted))
        coast.append([px,-79.,pz])
    promenade=dict(id='miyukinohama-hamacho-promenade',points=coast,width=4,maximum_grade=.12,arc_length_grade=True,linear_grade=True)
    curve,along=alignment(promenade)
    centre=LineString(curve[:,[0,2]])
    if centre.buffer(2.4).intersects(water):raise ValueError('Promenade buffer enters reference water')
    paths=[promenade];access=[]
    highway=contains_xy(bypass.buffer(5),xx,zz);cost=np.ones(ground.shape,float);cost[highway]=3
    for key,anchor,pz in [('miyukinohama',[3494,746],755),('hamacho',[3582,643],655),('hamacho-north',[3665,572],595)]:
        candidates=np.argwhere(oldwalk&~parcels)
        d=np.linalg.norm(candidates-np.asarray([anchor[1]-z,anchor[0]-x]),axis=1);start=tuple(map(int,candidates[int(d.argmin())]))
        if d.min()>8:raise ValueError(('No measured city endpoint',key))
        goalxz=np.asarray(centre.interpolate(centre.project(Point(float(coast[min(range(len(coast)),key=lambda i:abs(coast[i][2]-pz))][0]),pz))).coords[0])
        goal=(int(round(goalxz[1]))-z,int(round(goalxz[0]))-x)
        allowed=blocked.copy();allowed[oldwalk&~parcels]=False
        route=pathfind(start,goal,allowed,cost)
        # Simplify a grid route only inside its clear buffer; no corner cutting.
        line=LineString([(i+x,j+z)for j,i in route]);simplified=line.simplify(1.25)
        for q in simplified.coords:
            if blocked[round(q[1])-z,round(q[0])-x]:raise ValueError(('Simplified route obstructed',key,q))
        pos=list(simplified.coords);length=simplified.length;starty=float(oldgrade[start])/2+1
        if abs(starty+79)/length>.14:raise ValueError(('Coast access needs a longer ramp',key,starty,length))
        points=[];distance=0
        for k,(px,pz0)in enumerate(pos):
            if k:distance+=math.dist(pos[k-1],pos[k])
            points.append([px,starty+(-79-starty)*distance/length,pz0])
        spec=dict(id='coast-access-'+key,points=points,width=3,maximum_grade=.18,arc_length_grade=True,linear_grade=True)
        cc,aa=alignment(spec);buffer=LineString(cc[:,[0,2]]).buffer(1.8)
        if buffer.intersects(water|rails):raise ValueError(('Access crosses water or rail',key))
        for r in catalog:
            A,_,B,C,_,D=r['occupied_bounds']
            if buffer.intersects(box(A-1,B-1,C+1,D+1)):raise ValueError(('Access crosses building',key,r['id']))
        paths.append(spec)
        crossing=LineString(cc[:,[0,2]]).intersection(bypass.buffer(5))
        access.append(dict(id=key,start=points[0],end=points[-1],length=float(aa[-1]),future_bypass_crossing=mapping(crossing),
                           future_civil_stage=3,required_clearance_above_pavement=4,existing_bridge_constructed=False))
    np.savez_compressed(a.out/'retirement.npz',bounds=bounds,retired=np.zeros(ground.shape,bool))
    spec=dict(name='Odawara Miyukinohama and Hamacho coastal promenade',togendai_forecourt=False,surface_water_guard=True,
              geographic_water_mask=str(a.out/'geographic-water.npz'),geographic_rail_mask=str(a.out/'geographic-rail.npz'),
              water_surface_levels=str(a.out/'water-surface-levels.npz'),
              core=[3475,790,3480,795],earthwork_blend_distance=12,streets=[],new_frontages=[],footways=footways,public_paths=paths,
              retained_ports=[],parcel_floors=floors,parcel_offsets_xz=offsets,restore_vacated_parcels=True,
              preserve_entrance_aprons=[r['id']for r in moved],
              before_downtown_ground_source=str(a.before_downtown_source),
              additional_core_areas=[[r['payload_bounds'][0]-4,r['payload_bounds'][2]-4,r['payload_bounds'][3]+4,r['payload_bounds'][5]+4]for r in moved],
              retained_soil_areas=[],protected_volumes=[],preserve_train_corridors=True,
              retained_public_surfaces=[str(a.authority/'network.npz')],preserve_all_existing_public=True,
              retired_public_mask=str(a.out/'retirement.npz'),connectivity_seed=[3395,510],un_relocation_allowed=False)
    np.savez_compressed(a.out/'coastal-masks.npz',bounds=bounds,wet=wet,actual_water=actualwater,sea=sea_mask,parcels=parcels,
                        beach=(distance_transform_edt(~sea_mask)<12)&~wet&(zz>=573)&(zz<=814))
    save(a.out/'authored-design.json',spec);save(a.out/'coastal-access.json',access)
    save(a.out/'coastal-summary.json',dict(bounds=bounds,promenade_length=float(along[-1]),access=access,retained_device_tags=len(tags),phase_1_complete=False))
    print('Coast design:',round(float(along[-1]),1),'metres promenade;',len(access),'city access ramps;',len(tags),'retained devices',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','authority','geography','before-downtown-source','out'):p.add_argument('--'+name,type=Path,required=True)
    prepare(p.parse_args())
