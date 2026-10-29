"""Compose the cross-city components with streets, entrances and retired-lot roofs.

Offline authoring only. Native progress, actors and transport files are preserved.
The compact surface recipes describe complete assigned spans, independently of
the parked cargo, so later city movement cannot resurrect an old street layout.
"""
from __future__ import annotations
import argparse, copy, gzip, heapq, json, math, shutil
from collections import defaultdict, deque
from pathlib import Path
import nbtlib
import numpy as np
from PIL import Image, ImageFilter
from query_blocks import AIR, chunk_statuses, iter_selected_sections, iter_block_entities, dimension_dir
from install_r53_carrier_trays import stopped_world
from apply_s20_approved_semantic_repairs import parse_state
from plan_hakone_relocations import unpack
from prepare_hakone_city_cross import packed, contains
from prepare_hakone_main_terrain import sample_grid
from transplant_s22_authority import read_region, parse_chunk
from author_hakone_corner_blocks import retire_old_lots,build_parcels,parcel_mask
from author_hakone_maintenance import author as author_maintenance
from author_hakone_street_connections import grade_retired_edges,connect as connect_retained_streets

DIM='projectseele:geofront';DATA=Path('dimensions/projectseele/geofront/data')
X0,Z0,X1,Z1=-352,-128,415,591
Y0,Y1=-128,208
SHAPE=(Y1-Y0,Z1-Z0+1,X1-X0+1)


def expand(mask,radius):
    return np.array(Image.fromarray(mask).filter(ImageFilter.MaxFilter(radius*2+1)),dtype=bool,copy=True)


class Canvas:
    def __init__(self):
        self.x0=X0;self.z0=Z0
        self.palette=['minecraft:air'];self.ids={self.palette[0]:0}
        self.before=np.zeros(SHAPE,np.uint16);self.blocks=None
        self.assigned=np.zeros(SHAPE,bool);self.keep=np.zeros(SHAPE,bool)
        self.be={};self.original_be={};self.new_be={}
    def code(self,state):
        if state not in self.ids:self.ids[state]=len(self.palette);self.palette.append(state)
        return self.ids[state]
    def capture(self,world,snapshot=None):
        if snapshot and (snapshot/'blocks.npz').exists():
            with np.load(snapshot/'blocks.npz')as saved:
                self.palette=list(map(str,saved['palette']));self.ids={s:i for i,s in enumerate(self.palette)}
                self.before=saved['blocks'];self.blocks=self.before.copy()
            self.original_be={tuple(int(t[k])for k in ('x','y','z')):t for t in nbtlib.load(snapshot/'devices.dat')['BlockEntities']}
            self.be=copy.deepcopy(self.original_be)
            print('Using the explicit stopped-world authoring snapshot; installation still requires current before states',flush=True)
            return
        selected={(x,z):set(range(Y0//16,Y1//16))for x in range(X0//16,X1//16+1)for z in range(Z0//16,Z1//16+1)}
        status=chunk_statuses(world,DIM,selected)
        if any(v!='full'for v in status.values()):raise ValueError('City surface source has unfinished chunks')
        for cx,cz,sy,pal,ids in iter_selected_sections(world,DIM,selected):
            code=np.asarray([self.code(s)for s in pal],np.uint16)
            self.before[sy*16-Y0:sy*16-Y0+16,cz*16-Z0:cz*16-Z0+16,cx*16-X0:cx*16-X0+16]=code[ids].reshape(16,16,16)
        self.blocks=self.before.copy()
        self.original_be=dict(iter_block_entities(world,DIM,(X0,Y0,Z0),(X1,Y1-1,Z1),selected_chunks=set(selected)))
        self.be=copy.deepcopy(self.original_be)
        if snapshot:
            snapshot.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(snapshot/'blocks.npz',blocks=self.before,palette=np.asarray(self.palette))
            nbtlib.File({'BlockEntities':nbtlib.List[nbtlib.Compound](list(self.original_be.values()))}).save(snapshot/'devices.dat',gzipped=True)
        print(f'Captured {len(selected)} FULL city chunks',flush=True)
    def overlay_city(self,folder):
        for file in sorted((folder/'delta').glob('*.npz')):
            with np.load(file)as data:
                p=data['positions'];code=np.asarray([self.code(str(s))for s in data['palette']],np.uint16)
                iy,iz,ix=p[:,1]-Y0,p[:,2]-Z0,p[:,0]-X0
                if np.any(self.before[iy,iz,ix]!=code[data['before']]):raise ValueError('Current world changed since the component candidate')
                self.blocks[iy,iz,ix]=code[data['after']]
        for row in nbtlib.load(folder/'block-entities.dat')['Changes']:
            pos=tuple(unpack(row['Pos']));old=self.original_be.get(pos)
            if old!=row.get('Before'):raise ValueError(f'Current inventory changed at {pos}')
            self.be.pop(pos,None)
            if 'After'in row:self.be[pos]=copy.deepcopy(row['After'])
    def put(self,x,y,z,state):
        if not(X0<=x<=X1 and Z0<=z<=Z1 and Y0<=y<Y1):raise ValueError((x,y,z))
        if self.keep[y-Y0,z-Z0,x-X0]:return
        if (x,y,z)in self.be:raise ValueError(f'Unassigned device at {(x,y,z)}')
        self.blocks[y-Y0,z-Z0,x-X0]=self.code(state);self.assigned[y-Y0,z-Z0,x-X0]=True
    def fill(self,x0,y0,z0,x1,y1,z1,state):
        for p in self.be:
            if x0<=p[0]<=x1 and y0<=p[1]<=y1 and z0<=p[2]<=z1:raise ValueError(f'Unassigned device at {p}')
        s=np.s_[y0-Y0:y1-Y0+1,z0-Z0:z1-Z0+1,x0-X0:x1-X0+1]
        writable=~self.keep[s]
        self.blocks[s][writable]=self.code(state);self.assigned[s][writable]=True
    def layer(self,y,mask,state):
        mask=mask&~self.keep[y-Y0]
        for x,yy,z in self.be:
            if yy==y and mask[z-Z0,x-X0]:raise ValueError(f'Unassigned device at {(x,y,z)}')
        self.blocks[y-Y0][mask]=self.code(state);self.assigned[y-Y0][mask]=True


def preserve_transit(canvas,world):
    """Keep the sampled native rail deck, air envelope and existing piers.

    This offline authoring mask never changes train IDs, schedules or routes.
    Ground streets may pass under the elevated deck beside its actual piers.
    """
    transit=json.loads((world/'native_transit_r28.json').read_text(encoding='utf-8'))
    footprints=np.zeros(SHAPE[1:],bool);deck_min=np.full(SHAPE[1:],Y1,np.int16);segments=0
    def reserve(points,radius):
        nonlocal segments
        touched=False
        for px,py,pz in points:
            x,y,z=map(round,(px,py,pz))
            if not(X0-radius<=x<=X1+radius and Z0-radius<=z<=Z1+radius and 24<=y<Y1):continue
            a,b=max(X0,x-radius)-X0,min(X1,x+radius)-X0+1
            c,d=max(Z0,z-radius)-Z0,min(Z1,z+radius)-Z0+1
            lo,hi=max(Y0,y-4)-Y0,min(Y1,y+9)-Y0
            canvas.keep[lo:hi,c:d,a:b]=True;footprints[c:d,a:b]=True
            deck_min[c:d,a:b]=np.minimum(deck_min[c:d,a:b],y-6);touched=True
        segments+=int(touched)
    for curve in transit['curves']:
        if curve['mode']=='TRAIN':reserve(curve['points'],4)
    for platform in transit['platforms']:
        if platform['transportMode']!='TRAIN':continue
        a=np.array([platform['position1'][k]for k in ('x','y','z')],float)
        b=np.array([platform['position2'][k]for k in ('x','y','z')],float)
        reserve(np.linspace(a,b,max(2,int(np.linalg.norm(b-a))+1)),9)
    # Protect observed support material, rather than inventing solid columns
    # all the way down through the existing underground facility.
    natural={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone',
             'minecraft:dirt','minecraft:grass_block','minecraft:water'}
    structure=np.array([p.split('[')[0]not in natural for p in canvas.palette])
    support=np.zeros(SHAPE[1:],bool)
    for y in range(81,145):support|=structure[canvas.blocks[y-Y0]]&footprints&(y<deck_min)
    for y in range(24,145):canvas.keep[y-Y0]|=support&structure[canvas.blocks[y-Y0]]
    return support,footprints,segments


def topology_masks(top):
    zz,xx=np.mgrid[Z0:Z1+1,X0:X1+1]
    footprint=np.zeros(xx.shape,bool);frame=footprint.copy();cores=footprint.copy();rows=[]
    for index,t in enumerate(top['Towers']):
        x,y,z=unpack(t['Centre']);half=int(t['Half']);f=t.get('Footprint',{})
        a,b,c,d=[int(f.get(k,v))for k,v in [('MinX',-half),('MaxX',half),('MinZ',-half),('MaxZ',half)]]
        footprint|=(xx>=x+a)&(xx<=x+b)&(zz>=z+c)&(zz<=z+d)
        frame|=(xx>=x+a-4)&(xx<=x+b+4)&(zz>=z+c-4)&(zz<=z+d+5)
        if 'FixedCorePos'in t:
            cx,_,cz=unpack(t['FixedCorePos']);cores|=(abs(xx-cx)<=1)&(abs(zz-cz)<=1)
        rows.append(dict(index=index,x=x,y=y,z=z,half=half,base=int(t['RetractedBaseY']),kind=str(t['Kind'])))
    return xx,zz,footprint,frame,cores,rows


def point_path(start,goal,allowed):
    """Bounded offline two-dimensional footpath routing; never runs in game."""
    queue=[(0,0,start)];cost={start:0};parents={}
    while queue:
        _,g,p=heapq.heappop(queue)
        if g!=cost[p]:continue
        if goal[p[1]-Z0,p[0]-X0]:
            path=[p]
            while p in parents:p=parents[p];path.append(p)
            return path[::-1]
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            q=p[0]+dx,p[1]+dz
            if not(X0<=q[0]<=X1 and Z0<=q[1]<=Z1)or not allowed[q[1]-Z0,q[0]-X0]:continue
            ng=g+1
            if ng<cost.get(q,10**9):cost[q]=ng;parents[q]=p;heapq.heappush(queue,(ng,ng,q))
        if len(cost)>30000:break
    return None


def road_network(cross,blocked):
    nodes={};edges=[];centre=np.zeros(cross.shape,bool);direction=np.zeros(cross.shape,np.uint8)
    def valid(x,z,r=4):
        return X0+r<=x<=X1-r and Z0+r<=z<=Z1-r and np.all(cross[z-Z0-r:z-Z0+r+1,x-X0-r:x-X0+r+1])and not np.any(blocked[z-Z0-r:z-Z0+r+1,x-X0-r:x-X0+r+1])
    for x in range(-310,371,40):
        for z in range(0,561,40):
            if valid(x,z):nodes[x,z]=set()
    for p in list(nodes):
        for q in ((p[0]+40,p[1]),(p[0],p[1]+40)):
            if q not in nodes:continue
            line=[(round(p[0]+(q[0]-p[0])*i/40),round(p[1]+(q[1]-p[1])*i/40))for i in range(41)]
            if all(valid(x,z)for x,z in line):nodes[p].add(q);nodes[q].add(p)
    # Closed blocks stay connected around larger original private buildings;
    # no abandoned road stub terminates against their wall.
    changed=True
    while changed:
        leaves=[p for p,n in nodes.items()if len(n)<2];changed=bool(leaves)
        for p in leaves:
            for q in nodes[p]:nodes[q].discard(p)
            del nodes[p]
    if not nodes:raise ValueError('No city road network')
    seen=set();queue=deque([next(iter(nodes))])
    while queue:
        p=queue.popleft()
        if p in seen:continue
        seen.add(p);queue.extend(nodes[p]-seen)
    if len(seen)!=len(nodes):raise ValueError('Disconnected street district')
    for p,neighbors in nodes.items():
        for q in neighbors:
            if q<p:continue
            edges.append([list(p),list(q)])
            for i in range(41):
                x=round(p[0]+(q[0]-p[0])*i/40);z=round(p[1]+(q[1]-p[1])*i/40)
                centre[z-Z0,x-X0]=True;direction[z-Z0,x-X0]|=1 if p[1]==q[1]else 2
    return nodes,edges,centre,direction


def protected_actors(world):
    mask=np.zeros(SHAPE[1:],bool);actors=[]
    folder=dimension_dir(world,DIM)/'entities'
    for rx in range(X0//512,X1//512+1):
        for rz in range(Z0//512,Z1//512+1):
            file=folder/f'r.{rx}.{rz}.mca'
            if not file.exists()or not file.stat().st_size:continue
            _,records=read_region(file)
            for raw in records:
                if raw is None:continue
                for e in parse_chunk(raw).get('Entities',[]):
                    p=list(map(float,e.get('Pos',[])))
                    if len(p)!=3 or not(X0+4<=p[0]<=X1-4 and Z0+4<=p[2]<=Z1-4 and 24<=p[1]<Y1):continue
                    x,z=math.floor(p[0]),math.floor(p[2]);mask[z-Z0-3:z-Z0+4,x-X0-3:x-X0+4]=True
                    actors.append(dict(id=str(e.get('id','')),pos=p,uuid=list(map(int,e.get('UUID',[])))))
    return mask,actors


def export(canvas,out,world,base,world_id,report):
    for stage in ('before','after'):shutil.copytree(base/stage,out/stage)
    shutil.copytree(base/'preserved',out/'preserved')
    (out/'delta').mkdir();files=[];changed=0;spans_count=0
    grouped=defaultdict(list)
    for cz in range(Z0//16,Z1//16+1):
        for cx in range(X0//16,X1//16+1):grouped[cx//32,cz//32].append((cx,cz))
    for region,chunks in grouped.items():
        coords=[];ranges=[0];indices=[];before=[];after=[]
        for cx,cz in chunks:
            s=np.s_[:,cz*16-Z0:cz*16-Z0+16,cx*16-X0:cx*16-X0+16]
            a=canvas.before[s].reshape(-1);b=canvas.blocks[s].reshape(-1);at=np.flatnonzero(a!=b)
            if len(at):
                coords.append((cx,cz));indices.append(at.astype(np.uint32));before.append(a[at]);after.append(b[at]);ranges.append(ranges[-1]+len(at));changed+=len(at)
            used=canvas.assigned[s];values=canvas.blocks[s];spans=[]
            for z in range(16):
                for x in range(16):
                    ys=np.flatnonzero(used[:,z,x]);i=0
                    while i<len(ys):
                        start=end=int(ys[i]);state=int(values[start,z,x]);i+=1
                        while i<len(ys)and int(ys[i])==end+1 and int(values[int(ys[i]),z,x])==state:end=int(ys[i]);i+=1
                        spans.append(nbtlib.IntArray([cx*16+x,cz*16+z,Y0+start,Y0+end,state]))
            if spans:
                relative=DATA/'city_rigid_generation_r45/surface'/f'{cx}_{cz}.dat'
                file=out/'after'/relative;file.parent.mkdir(parents=True,exist_ok=True)
                prior=world/relative
                if prior.exists():
                    before_file=out/'before'/relative;before_file.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(prior,before_file)
                nbtlib.File({'Version':nbtlib.Int(1),'WorldUUID':copy.deepcopy(world_id),
                    'Palette':nbtlib.List[nbtlib.Compound]([parse_state(p)for p in canvas.palette]),
                    'Spans':nbtlib.List[nbtlib.IntArray](spans),
                    'BlockEntities':nbtlib.List[nbtlib.Compound]([
                        nbtlib.Compound({'Pos':nbtlib.Long(packed(p)),
                            'StateId':nbtlib.Int(int(canvas.blocks[p[1]-Y0,p[2]-Z0,p[0]-X0])),
                            'NBT':copy.deepcopy(t)})for p,t in canvas.be.items()
                        if p[0]//16==cx and p[2]//16==cz and canvas.assigned[p[1]-Y0,p[2]-Z0,p[0]-X0]])}).save(file,gzipped=True)
                spans_count+=len(spans)
        if coords:
            name=f'delta/r.{region[0]}.{region[1]}.npz'
            np.savez_compressed(out/name,coordinates=np.asarray(coords,np.int32),ranges=np.asarray(ranges,np.int64),
                indices=np.concatenate(indices),before=np.concatenate(before),after=np.concatenate(after),palette=np.asarray(canvas.palette))
            files.append(name)
        print(f'Exported city street region {region}',flush=True)
    devices=[]
    for p in canvas.original_be.keys()|canvas.be.keys():
        before,after=canvas.original_be.get(p),canvas.be.get(p)
        if before==after:continue
        row=nbtlib.Compound({'Pos':nbtlib.Long(packed(p))})
        if before is not None:row['Before']=copy.deepcopy(before)
        if after is not None:row['After']=copy.deepcopy(after)
        devices.append(row)
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](devices)}).save(out/'block-entities.dat',gzipped=True)
    report.update(world=str(world),world_written=False,shape=list(SHAPE),minimum_y=Y0,maximum_y_exclusive=Y1,
                  changed_blocks=changed,delta_files=files,surface_spans=spans_count,block_entity_changes=len(devices),metadata_files=len(list((out/'after').rglob('*.dat'))))
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


def prepare(args):
    if args.out.exists():raise ValueError('Choose a fresh output directory')
    args.out.mkdir(parents=True)
    topo_file=next((args.city/'after'/DATA).glob('projectseele_city_rigid_topology_r45_*.dat'))
    top=nbtlib.load(topo_file)['data']
    source_plan=Path(json.loads((args.city/'manifest.json').read_text(encoding='utf-8'))['source_plan'])
    plan=json.loads(source_plan.read_text(encoding='utf-8'))
    canvas=Canvas();canvas.capture(args.world,args.source_snapshot);canvas.overlay_city(args.city)
    piers,rail_footprint,rail_segments=preserve_transit(canvas,args.world)
    old_lots=retire_old_lots(canvas,args.gis/'displaced-city-lots')
    xx,zz,footprint,frame,cores,towers=topology_masks(top)
    cross=np.zeros(xx.shape,bool)
    for a,b,c,d in plan['cross_rectangles_xz']:cross|=(xx>=a)&(xx<=c)&(zz>=b)&(zz<=d)
    reserve=(xx>=-80)&(xx<=140)&(zz>=-100)&(zz<=8)
    device=np.zeros(xx.shape,bool)
    for x,y,z in canvas.be:
        if y>=24:device[z-Z0,x-X0]=True
    device=expand(device,2);actors,actor_rows=protected_actors(args.world)
    protected=reserve|device|actors|cores|piers
    nodes,edges,centre,direction=road_network(cross,footprint|protected)
    carriage=expand(centre,2);paved=expand(centre,4);walk=paved&~carriage
    paths=np.zeros(xx.shape,bool);entrances=[];allowed=cross&~expand(footprint|protected,1)
    np.savez_compressed(args.out/'routing.npz',cross=cross,footprint=footprint,frame=frame,piers=piers,
        rail_footprint=rail_footprint,device=device,actors=actors,cores=cores,protected=protected,paved=paved,allowed=allowed)
    for t in towers:
        if t['kind']!='generated':continue
        x,z=t['x'],t['z']+t['half']+3
        path=point_path((x,z),paved,allowed)
        if not path:raise ValueError(f'No street approach for building {t["index"]}')
        for px,pz in path:paths[pz-Z0,px-X0]=True
        paths[t['z']+t['half']+1-Z0:z-Z0+1,x-X0:x-X0+2]=True
        entrances.append(dict(index=t['index'],door=[t['x']+.5,81,t['z']+t['half']],approach=path))
    paths=expand(paths,1)&~footprint&~protected;paved|=paths;walk=paved&~carriage
    active=cross&~frame&~protected
    # Cross platform is a deliberate engineered datum. Existing moving frames
    # and all devices remain distinct from the ordinary load-bearing substrate.
    for y in range(25,80):canvas.layer(y,active,'minecraft:stone')
    surface=cross&~footprint&~protected
    canvas.layer(80,surface,'minecraft:grass_block[snowy=false]')
    for y in range(81,145):canvas.layer(y,surface,'minecraft:air')
    canvas.layer(80,paved,'minecraft:smooth_stone')
    canvas.layer(80,carriage,'minecraft:gray_concrete')
    dashes=centre&(((xx+zz)%12)<5);canvas.layer(80,dashes,'minecraft:white_concrete')
    # Tactile strips remain outside the clear two-way carriageway.
    tactile=walk&((abs(xx-10)%40==3)|(abs(zz)%40==3))&~paths
    canvas.layer(80,tactile,'minecraft:yellow_terracotta')
    crossings=[]
    for (x,z),neighbors in nodes.items():
        if len(neighbors)<3:continue
        for q in neighbors:
            dx=int(np.sign(q[0]-x));dz=int(np.sign(q[1]-z))
            for i in (6,8,10):
                for lane in range(-2,3):canvas.put(x+dx*i-dz*lane,80,z+dz*i+dx*lane,'minecraft:white_concrete')
        crossings.append([x,80,z])
    # Restore the actual flat GeoFront roof (Y24 within its 600-block disk),
    # then grade retired shaft lots to the already sampled geographic relief.
    with np.load(args.gis/'terrain-design.npz')as saved:grid={k:saved[k]for k in ('x','z','height_y')}
    height=np.rint(sample_grid(grid,'height_y',xx,zz)).astype(np.int16)
    retired=np.zeros(xx.shape,bool)
    for r in plan['towers']:
        if not any(r['delta']):continue
        x,_,z=r['source_centre'];t=top['Towers'][r['index']];h=int(t['Half'])
        retired|=(abs(xx-x)<=h+4)&(zz>=z-h-4)&(zz<=z+h+5)
    retired&=~frame&~protected&~cross
    canvas.layer(24,retired,'projectseele:nerv_structural_panel')
    if np.any(retired&(height>=Y1)):raise ValueError('Retired lot exceeds measured height range')
    for y in range(25,Y1):
        canvas.layer(y,retired&(height>y+3),'minecraft:stone')
        canvas.layer(y,retired&(height>y)&(height<=y+3),'minecraft:dirt')
        canvas.layer(y,retired&(height==y),'minecraft:grass_block[snowy=false]')
        canvas.layer(y,retired&(height<y),'minecraft:air')
    grade_retired_edges(canvas,old_lots,cross,protected|rail_footprint,frame,height)
    neighbourhood,neighbourhood_footprint=build_parcels(canvas,old_lots,protected|frame|rail_footprint)
    approach_height=np.full(xx.shape,80,np.int16);approach_goal=paved.copy()
    neighbourhood_paths=[]
    allowed_neighbourhood=~expand(footprint|neighbourhood_footprint|protected,1)
    for row in neighbourhood:
        start=tuple(row['approach_start']);path=point_path(start,approach_goal,allowed_neighbourhood)
        if not path:raise ValueError(f'No public footway for replacement {row["id"]}')
        final=path[-1];end_y=int(approach_height[final[1]-Z0,final[0]-X0]);start_y=row['centre'][1]
        levels=np.rint(np.linspace(start_y,end_y,len(path))).astype(int)
        if np.any(abs(np.diff(levels))>1):raise ValueError(f'Terraced footway needs a longer alignment: {row["id"]}')
        cells={};path_index={p:i for i,p in enumerate(path)};distance={}
        for i,((x,z),y)in enumerate(zip(path,levels)):
            for dz in range(-1,2):
                for dx in range(-1,2):
                    q=(x+dx,z+dz)
                    if not allowed_neighbourhood[q[1]-Z0,q[0]-X0]:continue
                    d=abs(dx)+abs(dz)
                    if q in path_index:cells[q]=int(levels[path_index[q]])
                    elif d<distance.get(q,99):cells[q]=int(y);distance[q]=d
                    if approach_goal[q[1]-Z0,q[0]-X0]:cells[q]=int(approach_height[q[1]-Z0,q[0]-X0])
        for (x,z),y in cells.items():
            canvas.fill(x,25,z,x,int(y)-1,z,'minecraft:stone')
            canvas.put(x,int(y),z,'minecraft:smooth_stone')
            canvas.fill(x,int(y)+1,z,x,int(y)+3,z,'minecraft:air')
            approach_goal[z-Z0,x-X0]=True;approach_height[z-Z0,x-X0]=y
        for i in range(1,len(path)):
            if levels[i]==levels[i-1]:continue
            high=i if levels[i]>levels[i-1]else i-1;low=i-1 if high==i else i
            x,z=path[high];dx=x-path[low][0];dz=z-path[low][1];facing={(1,0):'east',(-1,0):'west',(0,1):'south',(0,-1):'north'}[dx,dz]
            for side in (-1,0,1):
                q=x-dz*side,z+dx*side
                if q in cells and cells[q]==levels[high]and(q not in path_index or path_index[q]==high):
                    canvas.put(q[0],int(levels[high]),q[1],f'minecraft:stone_brick_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]')
        x,_,z=row['door'];f=row['centre'][1]
        canvas.fill(x-1,f,z+1,x+2,f,z+3,'minecraft:smooth_stone')
        row['footway']=[[x,int(y)+1,z]for (x,z),y in zip(path,levels)]
        neighbourhood_paths.append(path)
    # Keep street furnishings off door approaches, machinery and traffic lanes.
    free=surface&~expand(frame|paved|protected|rail_footprint|approach_goal,3);trees=[]
    for z in range(17,Z1-6,23):
        for x in range(X0+13,X1-6,29):
            if not free[z-Z0,x-X0]:continue
            trunk=4+(x+z)%2
            canvas.fill(x,81,z,x,80+trunk,z,'minecraft:oak_log[axis=y]')
            for dy,r in [(trunk-1,2),(trunk,2),(trunk+1,1)]:
                for dz in range(-r,r+1):
                    for dx in range(-r,r+1):
                        if abs(dx)+abs(dz)<=r+1 and (dx or dz or dy>trunk):canvas.put(x+dx,80+dy,z+dz,'minecraft:oak_leaves[distance=7,persistent=true,waterlogged=false]')
            trees.append([x,80,z])
    lamps=[]
    for p,q in edges:
        dx=int(np.sign(q[0]-p[0]));dz=int(np.sign(q[1]-p[1]));x=(p[0]+q[0])//2-dz*6;z=(p[1]+q[1])//2+dx*6
        if not(X0+2<=x<=X1-2 and Z0+2<=z<=Z1-2)or np.any((frame|protected|paths|rail_footprint)[z-Z0-1:z-Z0+2,x-X0-1:x-X0+2]):continue
        canvas.put(x,80,z,'minecraft:polished_andesite');canvas.fill(x,81,z,x,84,z,'minecraft:polished_basalt[axis=y]')
        canvas.put(x,85,z,'minecraft:sea_lantern');canvas.put(x,86,z,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]');lamps.append([x,80,z])
    street_connections=connect_retained_streets(canvas,protected|neighbourhood_footprint)
    (args.out/'street-connections.json').write_text(json.dumps(street_connections,ensure_ascii=False,indent=2),encoding='utf-8')
    maintenance=author_maintenance(canvas,towers)
    (args.out/'maintenance.json').write_text(json.dumps(maintenance,ensure_ascii=False,indent=2),encoding='utf-8')
    report=dict(schema='projectseele.hakone-city-streets.v1',status='candidate; pending geographic perimeter integration',
        source_city=str(args.city),source_plan=str(source_plan),native_traffic_unchanged=True,protected_actors=actor_rows,
        preserved_rail_segments=rail_segments,rail_support_columns=int(piers.sum()),
        road_nodes=len(nodes),road_edges=len(edges),carriage_width=5,sidewalk_width=2,traffic_side='left',
        connected_entrances=len(entrances),crosswalk_junctions=len(crossings),trees=len(trees),lamps=len(lamps),
        retired_surface_columns=int(retired.sum()),replacement_buildings=sum(r['kind']=='building'for r in neighbourhood),replacement_parks=sum(r['kind']=='park'for r in neighbourhood),preserved_parcel_devices=sum(len(r['devices'])for r in neighbourhood),installation_ready=False,
        connected_lower_doors=maintenance['connected_lower_doors'],
        retained_street_connections=len(street_connections),
        remaining=['Blend new perimeter into rebuilt surrounding districts',
                   'Route real streams and trunk-road handoffs around the fictional lift structure','Cold install and changed LOD refresh'])
    (args.out/'streets.json').write_text(json.dumps(dict(nodes=[list(p)for p in nodes],edges=edges,entrances=entrances,crossings=crossings,trees=trees,lamps=lamps),ensure_ascii=False,indent=2),encoding='utf-8')
    (args.out/'neighbourhood.json').write_text(json.dumps(neighbourhood,ensure_ascii=False,indent=2),encoding='utf-8')
    np.savez_compressed(args.out/'surface.npz',bounds=np.array([X0,Z0,X1,Z1]),cross=cross,frame=frame,protected=protected,
                        carriage=carriage,paved=paved,paths=paths,retired=retired,height=height)
    export(canvas,args.out,args.world,args.city,top['WorldUUID'],report)
    print(json.dumps({k:v for k,v in report.items()if k!='protected_actors'},ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--gis',type=Path,required=True)
    p.add_argument('--city',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--source-snapshot',type=Path,help='Explicit reusable authoring snapshot; never used to overwrite current progress');args=p.parse_args()
    with stopped_world(args.world):prepare(args)


if __name__=='__main__':main()
