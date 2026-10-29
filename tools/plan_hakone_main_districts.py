"""Lay out complete mixed-use districts along the cached real Hakone roads.

The fictional lift city, native infrastructure and existing actors are explicit
constraints. Original parcel IDs and contents are assigned to new frontages;
the plan never claims these fictional shops are surveyed Japanese businesses.
"""
import argparse,gzip,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from prepare_hakone_main_terrain import sample_grid,smooth
from prepare_hakone_lake_basin import distance_from
from plan_ashi_landscape_r54 import NATURAL


ROAD_MATERIALS={'minecraft:black_concrete','minecraft:white_concrete','minecraft:gray_concrete',
    'minecraft:smooth_stone','minecraft:smooth_stone_slab','minecraft:polished_andesite',
    'minecraft:stone_bricks','minecraft:stone_brick_slab','minecraft:stone_brick_stairs',
    'minecraft:polished_blackstone_slab','minecraft:polished_blackstone_stairs',
    'minecraft:yellow_concrete','minecraft:yellow_terracotta','minecraft:iron_bars',
    'minecraft:stone_brick_wall','minecraft:sea_lantern','minecraft:light','minecraft:light_gray_concrete',
    'projectseele:road_asphalt_slab','projectseele:road_marking_slab',
    'projectseele:station_tactile_warning','projectseele:nerv_ceiling_light'}


def draw_line(image,coords,x0,z0,width,value=1):
    ImageDraw.Draw(image).line([(round(x-x0),round(z-z0))for x,z in coords],fill=value,width=width,joint='curve')


def plan(a):
    capture=json.loads((a.candidate/'capture.json').read_text('utf8'))
    x0,z0,x1,z1=capture['bounds_xz'];shape=(z1-z0+1,x1-x0+1)
    with np.load(a.candidate/'measured.npz')as data:m={k:data[k]for k in data.files}
    rows=json.loads((a.parcels/'manifest.json').read_text('utf8'))['plots']
    owned=defaultdict(list)
    for row in rows:
        b=row['source_bounds_xyz']
        for cx in range(b[0]//16,b[3]//16+1):
            for cz in range(b[2]//16,b[5]//16+1):owned[cx,cz].append(b)
    with np.load(a.legacy_roads)as data:
        origin=data['origin'];oldmask=data['mask'];oldheight=data['height2']
    legacy=np.zeros(shape,bool);legacy_y=np.full(shape,80,np.int16)
    left,top=max(x0,int(origin[0])),max(z0,int(origin[1]));right,bottom=min(x1+1,int(origin[0])+oldmask.shape[1]),min(z1+1,int(origin[1])+oldmask.shape[0])
    src=np.s_[top-origin[1]:bottom-origin[1],left-origin[0]:right-origin[0]];dst=np.s_[top-z0:bottom-z0,left-x0:right-x0]
    legacy[dst]=oldmask[src];legacy_y[dst]=oldheight[src]//2-1
    # Identify obsolete ordinary road construction by its recorded footprint
    # and measured material. Native objects and other authored columns remain.
    protected=np.zeros(shape,bool);yy=np.arange(-128,320)[:,None,None]
    retained_cache=a.candidate/'retained-infrastructure.npy'
    source_files=[] if retained_cache.exists() else sorted((a.candidate/'source').glob('*.npz'))
    if retained_cache.exists():protected=np.load(retained_cache)
    for file in source_files:
        with np.load(file)as data:coords=data['coordinates'];blocks=data['blocks'];names=list(map(str,data['palette']))
        natural=np.asarray([s.split('[')[0]in NATURAL for s in names]);road=np.asarray([s.split('[')[0]in ROAD_MATERIALS for s in names])
        for i,(cx,cz)in enumerate(coords):
            area=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16]
            allowed=natural[blocks[i]]
            allowed|=road[blocks[i]]&legacy[area][None,:,:]&(yy>=legacy_y[area]-2)&(yy<=legacy_y[area]+8)
            for b in owned[cx,cz]:
                lo=np.maximum([cx*16,-128,cz*16],b[:3]);hi=np.minimum([cx*16+16,320,cz*16+16],np.array(b[3:])+1)
                allowed[lo[1]+128:hi[1]+128,lo[2]-cz*16:hi[2]-cz*16,lo[0]-cx*16:hi[0]-cx*16]=True
            protected[area]=(~allowed[160:]).any(0)
        print('Classified retained infrastructure',file.name,flush=True)
    if source_files:np.save(retained_cache,protected)
    fixed=np.zeros(shape,bool)
    def reserve(box,margin=0):
        x,z,X,Z=box
        fixed[max(0,z-z0-margin):min(shape[0],Z-z0+margin+1),max(0,x-x0-margin):min(shape[1],X-x0+margin+1)]=True
    city=json.loads((a.gis/'city-south-layout-preserved/plan.json').read_text('utf8'))
    for box in city['cross_rectangles_xz']:reserve(box,3)
    reserve([-110,-155,225,15],8)
    reserve([-425,690,-285,830],12) # Existing named surface gateway and shaft.
    for name in ('city-south-streets-v3/neighbourhood.json','city-south-streets-v3/retained-neighbourhood.json'):
        for row in json.loads((a.gis/name).read_text('utf8')):
            b=row['bounds'];reserve([b[0],b[2],b[3],b[5]],5)
            for x,y,z in row.get('footway',[]):reserve([x,z,x,z],2)
    reserve([-497,863,-455,905],5)
    for row in capture['actors']:
        x,y,z=row['pos'];radius=32 if row['id']in ('superbwarfare:ac_130h','superbwarfare:j_16')else 8
        reserve([math.floor(x),math.floor(z),math.ceil(x),math.ceil(z)],radius)
    held=np.asarray(Image.fromarray(protected|fixed|~m['full']).filter(ImageFilter.MaxFilter(7)),bool)
    zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    with np.load(a.gis/'terrain-design.npz')as data:grid={k:data[k]for k in ('x','z','height_y','inland_water')}
    height=sample_grid(grid,'height_y',xx,zz);water=sample_grid(grid,'inland_water',xx,zz,True)
    border=np.minimum.reduce([xx-x0,x1-xx,zz-z0,z1-zz]);distance=distance_from(held,48)
    target=np.rint(m['top']+(height-m['top'])*smooth(np.minimum(distance,border)/48)).astype(np.int16)
    target=np.clip(target,32,300);target[water]=m['top'][water]
    features=json.load(gzip.open(a.gis/'features.world.geojson.gz','rt',encoding='utf8'))['features']
    streets=[];roadimg=Image.new('L',(shape[1],shape[0]));walkimg=roadimg.copy();centreimg=roadimg.copy();rivers=roadimg.copy();railmask=roadimg.copy()
    for f in features:
        kind=f['properties']['source_layer'];geom=f['geometry'];props=f['properties']
        if kind not in ('RdCL','RvrCL')or geom['type']!='LineString':continue
        points=geom['coordinates']
        if not any(x0-30<=x<=x1+30 and z0-30<=z<=z1+30 for x,z in points):continue
        if kind=='RvrCL':draw_line(rivers,points,x0,z0,3);continue
        code=int(props['vt_code']);pedestrian=code in (2721,2731);tunnel=code in (2704,2714)
        carriage=3 if code in (2711,2713)else 7
        if pedestrian:carriage=0
        draw_line(walkimg,points,x0,z0,3 if pedestrian else carriage+4)
        if carriage:draw_line(roadimg,points,x0,z0,carriage)
        draw_line(centreimg,points,x0,z0,1)
        streets.append(dict(points=points,width=carriage,kind=props.get('vt_rdctg',''),code=code,tunnel=tunnel,source_tile=props['source_tile']))
    transit=json.loads((a.world/'native_transit_r28.json').read_text('utf8'))
    for curve in transit['curves']:
        if curve['mode']=='TRAIN':draw_line(railmask,[(p[0],p[2])for p in curve['points']],x0,z0,19)
    road=np.asarray(roadimg,bool)&~fixed;walk=np.asarray(walkimg,bool)&~fixed;centre=np.asarray(centreimg,bool)&~fixed
    river=np.asarray(rivers,bool)&~fixed;rail=np.asarray(railmask,bool)
    # Preserve the already installed lake and all native station/rail corridors.
    blocked=held|water|rail|np.asarray(Image.fromarray(np.asarray(walkimg)).filter(ImageFilter.MaxFilter(7)),bool)
    occupied=blocked.copy();built=np.zeros(shape,bool);locations=[];used=set()
    np.savez_compressed(a.candidate/'district-plan.npz',bounds=[x0,z0,x1,z1],target=target,protected=protected,fixed=fixed,
        held=held,legacy=legacy,legacy_y=legacy_y,road=road,walk=walk,centre=centre,river=river,water=water,rail=rail)
    print('Surface counts',dict(held=int(held.sum()),blocked=int(blocked.sum()),roads=int(road.sum()),full=int(m['full'].sum())),flush=True)
    def fits(cx,cz,hx,hz):
        if not(x0+8+hx<=cx<=x1-8-hx and z0+8+hz<=cz<=z1-8-hz):return False
        q=np.s_[cz-hz-z0-3:cz+hz-z0+4,cx-hx-x0-3:cx+hx-x0+4]
        return not occupied[q].any() and float(height[q].max()-height[q].min())<=12
    # Frontage candidates sample real curves and point their doors toward the
    # actual street, not toward a fabricated north/south rectangular grid.
    for street in streets:
        if not street['width']or street['tunnel']:continue
        points=np.asarray(street['points']);distance_along=0.
        for p,q in zip(points,points[1:]):
            length=float(np.linalg.norm(q-p))
            if length<1:continue
            tangent=(q-p)/length;normal=np.array([-tangent[1],tangent[0]])
            for d in np.arange(2,length,10):
                point=p+tangent*d
                for sign in (-1,1):
                    offset=normal*sign;axis=0 if abs(offset[0])>abs(offset[1])else 1
                    # Canonical facade faces south (rotation 0).
                    face=('west'if offset[0]>0 else'east')if axis==0 else('north'if offset[1]>0 else'south')
                    rotation={'south':0,'west':1,'north':2,'east':3}[face]
                    for setback in (22,30,42):
                        pos=np.rint(point+offset*(street['width']/2+setback)).astype(int);cx,cz=map(int,pos)
                        key=(round(cx/5),round(cz/5),rotation)
                        if key in used:continue
                        used.add(key)
                        if not(x0<=cx<=x1 and z0<=cz<=z1):continue
                        locations.append(dict(centre=[cx,cz],rotation=rotation,street=[round(float(v))for v in point],road_width=street['width'],code=street['code']))
    # Existing content identity determines the programme; higher blocks stay
    # close to the engineered city, smaller uses continue along outer roads.
    building_features=json.load(gzip.open(a.gis/'buildings.world.geojson.gz','rt',encoding='utf8'))['features']
    building_centres=[]
    for feature in building_features:
        if feature['properties']['source_layer']!='BldA':continue
        geometry=feature['geometry'];rings=geometry['coordinates']
        if geometry['type']=='Polygon':rings=[rings]
        if geometry['type']not in ('Polygon','MultiPolygon'):continue
        for polygon in rings:
            points=np.asarray(polygon[0]);point=points.mean(0)
            if x0<=point[0]<=x1 and z0<=point[1]<=z1:building_centres.append(point)
    building_centres=np.asarray(building_centres)
    for site in locations:
        site['surveyed_building_distance']=round(float(np.linalg.norm(building_centres-site['centre'],axis=1).min()),1)if len(building_centres)else None
    assignments=[]
    print('Frontage candidates',len(locations),flush=True)
    for number,row in enumerate(sorted(rows,key=lambda r:(-r.get('storeys',0),r['id']))):
        floors=row.get('storeys',0);hx=9 if floors>=8 else 8;hz=10
        sx=(row['bounds'][0]+row['bounds'][1])/2;sz=(row['bounds'][2]+row['bounds'][3])/2
        def score(site):
            x,z=site['centre'];dist=(x-sx)**2+(z-sz)**2
            density=min(180,site['surveyed_building_distance']or 0)**2*.3
            return dist+density+max(0,math.hypot(x-30,z-340)-450)**2*(4 if floors>=8 else .3)
        picked=None
        for site in sorted(locations,key=score):
            cx,cz=site['centre'];rx,rz=(hx,hz)if site['rotation']%2==0 else(hz,hx)
            if not fits(cx,cz,rx,rz):continue
            px,pz=site['street']
            if not(x0<=px<=x1 and z0<=pz<=z1)or fixed[pz-z0,px-x0]:continue
            floor=int(target[pz-z0,px-x0])+1
            if floor+max(1,floors)*5+7>=319:continue
            # Reject a disconnected corner frontage; its approach must not
            # cross another original object or a neighbouring building.
            vector=np.asarray([px-cx,pz-cz]);length=max(abs(vector))
            approach=np.rint(np.linspace([cx,cz],[px,pz],int(length)+1)).astype(int)
            segment=approach[max(rx,rz)+2:]
            if any(held[z-z0,x-x0]or rail[z-z0,x-x0]or water[z-z0,x-x0]or built[z-z0,x-x0]for x,z in segment):continue
            picked=dict(site,source_id=row['id'],half=[hx,hz],floor=floor,floors=floors,source_floor=row['floor'],style=row.get('style','park'))
            occupied[cz-rz-z0-5:cz+rz-z0+6,cx-rx-x0-5:cx+rx-x0+6]=True
            built[cz-rz-z0-3:cz+rz-z0+4,cx-rx-x0-3:cx+rx-x0+4]=True
            break
        if picked is None:raise ValueError(f'No complete frontage for {row["id"]}; placed {len(assignments)}')
        assignments.append(picked)
    np.savez_compressed(a.candidate/'district-plan.npz',bounds=[x0,z0,x1,z1],target=target,protected=protected,fixed=fixed,
        held=held,legacy=legacy,legacy_y=legacy_y,road=road,walk=walk,centre=centre,river=river,water=water,rail=rail)
    result=dict(status='authored layout; not installed',world=str(a.world),source_parcels=str(a.parcels),
        bounds_xz=[x0,z0,x1,z1],streets=streets,parcels=assignments,
        original_devices=sum(r['block_entities']for r in rows),native_transport_ids_unchanged=True,
        geographic_source='cached GSI DEM and road vectors; building uses and playable sizes are Project SEELE adaptations')
    (a.candidate/'district-plan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Complete district frontages:',len(assignments),'Real road segments:',len(streets),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('world','gis','candidate','parcels','legacy-roads'):p.add_argument('--'+name,type=Path,required=True)
    plan(p.parse_args())
