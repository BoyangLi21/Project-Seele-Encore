"""Reconcile saved street levels and exterior terrain as one offline surface.

The source consists exclusively of current FULL chunks. Finite building,
tunnel and railway volumes remain untouched; exact voxel deltas carry the
inverse. No gameplay scan, entity migration or progress replacement is used.
"""
import argparse, gzip, json, os, struct
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.ndimage import maximum_filter, gaussian_filter, distance_transform_edt, binary_fill_holes
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid, sampled
from prepare_hakone_main_terrain import sample_grid
from hakone_earthworks import min_slope_envelope
from plan_ashi_landscape_r54 import SOIL, NATURAL
from query_blocks import AIR
from scipy.ndimage import gaussian_filter1d
from PIL import Image, ImageDraw


def combine(a):
    a.out.mkdir(exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    sources=[a.source,a.extra];grids=[load_grid(p/'measured.npz')for p in sources]
    bounds=[min(g['bounds'][0]for g in grids),min(g['bounds'][1]for g in grids),max(g['bounds'][2]for g in grids),max(g['bounds'][3]for g in grids)]
    shape=(bounds[3]-bounds[1]+1,bounds[2]-bounds[0]+1)
    result={k:np.full(shape,-129 if k in ('top','highest')else False,dtype=g.dtype)for k,g in grids[0].items()if k!='bounds'}
    for g in grids:
        x,z,X,Z=g['bounds'];area=np.s_[z-bounds[1]:Z-bounds[1]+1,x-bounds[0]:X-bounds[0]+1]
        for k in result:result[k][area][g['full']]=g[k][g['full']]
    np.savez_compressed(a.out/'measured.npz',bounds=bounds,**result)
    names=sorted({f.name for p in sources for f in(p/'source').glob('*.npz')})
    for name in names:
        files=[p/'source'/name for p in sources if(p/'source'/name).exists()]
        if len(files)==1:os.link(files[0],a.out/'source'/name);continue
        ids={};palette=[];chunks={}
        for file in files:
            with np.load(file)as d:
                remap=[]
                for s in map(str,d['palette']):
                    if s not in ids:ids[s]=len(palette);palette.append(s)
                    remap.append(ids[s])
                remap=np.array(remap,np.uint16)
                for q,v in zip(d['coordinates'],d['blocks']):
                    if tuple(q)in chunks:raise ValueError('Overlapping current captures')
                    chunks[tuple(q)]=remap[v]
        keys=sorted(chunks);np.savez_compressed(a.out/'source'/name,coordinates=keys,blocks=np.array([chunks[k]for k in keys]),palette=palette)
    (a.out/'capture.json').write_text(json.dumps(dict(sources=list(map(str,sources)),bounds_xz=list(map(int,bounds)),full_chunks=int(result['full'].sum()//256),world_written=False),indent=2),'utf8')


def plan(a):
    a.out.mkdir(exist_ok=False)
    m=load_grid(a.source/'measured.npz');d=load_grid(a.base/'network.npz');s=load_grid(a.survey/'measured-3d.npz')
    bounds=m['bounds'];x0,z0,X,Z=map(int,bounds);xs=np.arange(x0,X+1,2);zs=np.arange(z0,Z+1,2);zz,xx=np.meshgrid(zs,xs,indexing='ij')
    with gzip.open(a.resource,'rb')as f:
        _,fx,fz,step,w,h=struct.unpack('>6i',f.read(24));old=np.frombuffer(f.read(w*h*2),'>i2').reshape(h,w).astype(np.float32)/16;water=np.frombuffer(f.read(w*h*2),'>i2').reshape(h,w)
    field=dict(x=np.arange(w)*step+fx,z=np.arange(h)*step+fz,height_y=old,water=water)
    original=sample_grid(field,'height_y',xx,zz).astype(np.float32);wet=sample_grid(field,'water',xx,zz,True)
    known=m['full'][::2,::2];soil=m['top'][::2,::2];oldheight=original.copy();oldheight[known]=soil[known]
    if a.proto:
        proto=load_grid(a.proto/'measured.npz');use=proto['full'][::2,::2]&~known
        oldheight[use]=proto['top'][::2,::2][use];known|=use
    outside=(xx<fx)|(zz<fz)|(xx>field['x'][-1])|(zz>field['z'][-1]);wet[outside]=-32768
    # The field is authoritative only near edited surfaces. Existing remote
    # facilities and the external datum are fixed, not globally flattened.
    active=(xx>=-3000)&(zz>=-800)&(xx<2600)&(zz<1800)
    fixed=~active;values=oldheight.copy()
    core=sampled(d,'core',xx,zz).astype(bool);fixed|=core;values[core]=80
    roadfloor=sampled(s,'floor2',xx,zz,-32768).astype(float)/2-1
    commissioned=sampled(d,'walk',xx,zz).astype(bool)
    if 'previous_grade2'in d:roadfloor[commissioned]=sampled(d,'grade2',xx,zz)[commissioned]/2
    tunnel=sampled(d,'tunnel',xx,zz).astype(bool)
    # Use recorded road layers. Upper bridges and tunnel interiors are never
    # ground pins. Old western streets are retained functional streets.
    roads=(roadfloor>-128)&(commissioned|((xx<-1100)&(xx>=-2240)))&~tunnel
    roads&=(abs(roadfloor-soil)<9)|((xx<-1100)&(zz>280)&(zz<1040))
    fixed|=roads;values[roads]=roadfloor[roads]
    catalog=json.loads((a.base/'catalog.json').read_text('utf8'))
    boxes=[r['occupied_bounds']for r in catalog]+json.loads((a.base/'station-volumes.json').read_text('utf8'))
    for x,y,z,R,Y,B in boxes:
        plot=(xx>=x-2)&(xx<=R+2)&(zz>=z-2)&(zz<=B+2)&active
        fixed|=plot;values[plot]=y
    # An entire original urban block shares its streets' grade. This removes
    # deep trenches between the old grid, not just a narrow curb strip.
    for row in json.loads((a.gis.parent/'world_quality_r02/surface_layout.json').read_text('utf8'))['kept_plots']:
        if not row['id'].startswith('new_hakone/'):continue
        x,R,z,B=row['bounds'];plot=(xx>=x-3)&(xx<=R+3)&(zz>=z-3)&(zz<=B+3)&active
        fixed|=plot;values[plot]=row['floor']
    oldmesh=sampled(s,'legacy',xx,zz).astype(bool)&(xx>=-1930)&(xx<=-1114)&(zz>=294)&(zz<=1026)
    blocks=binary_fill_holes(oldmesh)&active
    fixed|=blocks;values[blocks]=104
    # Real lakes keep their bed and level. Water is not a terrain crest.
    fixed|=wet!=-32768;values[wet!=-32768]=oldheight[wet!=-32768]
    # Remove narrow numerical ridges/cuts with symmetric slope envelopes.
    slope=2.0 # one terrain block per horizontal block, sampled every two
    lower_shape=min_slope_envelope(oldheight,slope)
    upper_shape=-min_slope_envelope(-oldheight,slope)
    shaped=(lower_shape+upper_shape)*.5
    upper=min_slope_envelope(np.where(fixed,values,np.inf),slope)
    lower=-min_slope_envelope(np.where(fixed,-values,np.inf),slope)
    conflict=lower>upper+.01
    # Existing nearby fixed structures can require retaining faces. Preserve
    # their actual surrounding ground rather than average incompatible pins.
    conflict=maximum_filter(conflict,size=5)
    fitted=np.clip(shaped,lower,upper);fitted[fixed]=values[fixed];fitted[conflict]=oldheight[conflict]
    fitted=np.rint(fitted).astype(np.int16)
    # Smooth finite outer interfaces without altering untouched unknown chunks.
    distance=distance_transform_edt(active&~conflict);blend=np.clip(distance/24,0,1);blend=blend*blend*(3-2*blend)
    fitted=np.rint(oldheight+(fitted-oldheight)*blend).astype(np.int16)
    fitted[fixed&active&~conflict]=np.rint(values[fixed&active&~conflict])
    np.savez_compressed(a.out/'surface.npz',x=xs,z=zs,height_y=fitted,old_height=oldheight,water=wet,active=active,conflict=conflict)
    (a.out/'plan.json').write_text(json.dumps(dict(bounds=[int(xs[0]),int(zs[0]),int(xs[-1]),int(zs[-1])],changed_samples=int((fitted!=oldheight).sum()),retained_constraint_samples=int((conflict&active).sum()),finite_structures=len(boxes),road_anchors=int(roads.sum())),indent=2),'utf8')
    print((a.out/'plan.json').read_text(),flush=True)


def connector(a):
    """Restore the separated old and commissioned town networks with a road."""
    from prepare_hakone_main_districts import line
    s=load_grid(a.survey/'measured-3d.npz');m=load_grid(a.source/'measured.npz');p=load_grid(a.plan/'surface.npz')
    base=load_grid(a.base/'network.npz')
    start=(-1114,306);end=(-839,338);points=list(line(start,end));q=np.array(points);x,z,X,Z=-1140,275,-810,370
    b=[x,z,X,Z];shape=(Z-z+1,X-x+1);iz,ix=q[:,1]-s['bounds'][1],q[:,0]-s['bounds'][0]
    endpoints=s['floor2'][iz[[0,-1]],ix[[0,-1]]]/2-1
    endpoints[-1]=base['grade2'][end[1]-base['bounds'][1],end[0]-base['bounds'][0]]/2
    if np.any(endpoints<-128):raise ValueError('Connector endpoints need actual retained paving')
    old=m['top'][q[:,1]-m['bounds'][1],q[:,0]-m['bounds'][0]].astype(float)
    profile=gaussian_filter1d(old,12);length=len(profile);dist=np.arange(length)
    low=np.maximum(endpoints[0]-.25*dist,endpoints[1]-.25*(length-1-dist));high=np.minimum(endpoints[0]+.25*dist,endpoints[1]+.25*(length-1-dist))
    profile=min_slope_envelope(np.clip(profile,low,high),.25);profile=np.maximum(profile,low);profile[0],profile[-1]=endpoints
    grade=np.rint(profile*2).astype(np.int16)
    im=Image.new('L',(shape[1],shape[0]));dr=ImageDraw.Draw(im);local=[(int(X-x),int(Z-z))for X,Z in q]
    dr.line(local,fill=1,width=11,joint='curve');walk=np.asarray(im,bool)
    im=Image.new('L',(shape[1],shape[0]));ImageDraw.Draw(im).line(local,fill=1,width=7,joint='curve');road=np.asarray(im,bool)
    from scipy.spatial import cKDTree
    zz,xx=np.mgrid[z:Z+1,x:X+1];_,at=cKDTree(q).query(np.column_stack((xx.ravel(),zz.ravel())));grade2=grade[at].reshape(shape)
    marking=np.zeros(shape,bool)
    for i,(xx,zz)in enumerate(points):
        if i%12<5:marking[zz-z,xx-x]=True
    # A junction is one shared surface across the full road width. Merge and
    # regrade its neighbouring approaches instead of stamping a new road over
    # lower side streets, which would replace a disconnection with a wall.
    from plan_hakone_network_repair import network_grade
    bx,bz,_,_=map(int,base['bounds']);ar=np.s_[z-bz:Z-bz+1,x-bx:X-bx+1]
    base['walk'][ar]|=walk;base['road'][ar]|=road;base['marking'][ar][walk]=marking[walk];base['grade2'][ar][walk]=grade2[walk]
    left,top,right,bottom=x-64,z-64,X+64,Z+64;area=np.s_[top-bz:bottom-bz+1,left-bx:right-bx+1]
    localwalk=base['walk'][area];target=base['grade2'][area].copy();pins=np.full(target.shape,np.nan,np.float32)
    pins[0]=target[0];pins[-1]=target[-1];pins[:,0]=target[:,0];pins[:,-1]=target[:,-1]
    for i,(px,pz)in enumerate(points):pins[pz-top,px-left]=grade[i]
    target=network_grade(target,localwalk,np.zeros_like(localwalk),pins)
    base['grade2'][area]=target;base['regraded_walk']=base['walk']&(base['grade2']!=base['previous_grade2'])
    np.savez_compressed(a.base/'network.npz',**base)
    grade2=base['grade2'][ar].copy()
    np.savez_compressed(a.plan/'connector.npz',bounds=b,walk=walk,road=road,grade2=grade2,marking=marking)
    # Couple its complete width to the same terrain surface, with broad cuts
    # and fills instead of a standalone raised asphalt ribbon.
    zz,xx=np.meshgrid(p['z'],p['x'],indexing='ij');pins=sampled(dict(bounds=b,walk=walk),'walk',xx,zz).astype(bool)
    values=sampled(dict(bounds=b,grade2=grade2),'grade2',xx,zz)/2
    upper=min_slope_envelope(np.where(pins,values,np.inf),2.0);lower=-min_slope_envelope(np.where(pins,-values,np.inf),2.0)
    p['height_y']=np.rint(np.clip(p['height_y'],lower,upper)).astype(np.int16)
    np.savez_compressed(a.plan/'surface.npz',**p)
    (a.plan/'connector.json').write_text(json.dumps(dict(start=list(start),end=list(end),retained_floor_y=endpoints.tolist(),length=len(points),carriage_width=7,complete_width=11,maximum_design_grade=.25),indent=2),'utf8')
    print((a.plan/'connector.json').read_text(),flush=True)


def compose(a):
    a.out.mkdir(exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    for f in(a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    m=load_grid(a.source/'measured.npz');d=load_grid(a.base/'network.npz');plan=load_grid(a.plan/'surface.npz')
    boxes=[r['occupied_bounds']for r in json.loads((a.base/'catalog.json').read_text('utf8'))]+json.loads((a.base/'station-volumes.json').read_text('utf8'))
    boxes += [[-110,25,-155,225,180,15],[-425,20,690,-285,180,830],[350,63,-177,1350,123,86]]
    bychunk=defaultdict(list)
    for x,y,z,X,Y,Z in boxes:
        box=[x-3,y-2,z-3,X+3,Y+9,Z+3]
        for cx in range(box[0]//16,box[3]//16+1):
            for cz in range(box[2]//16,box[5]//16+1):bychunk[cx,cz].append(box)
    tunnels=defaultdict(list)
    for x,y,z in json.loads(a.tunnels.read_text('utf8'))['points']:tunnels[x//16,z//16].append((x,y,z))
    rails=defaultdict(set)
    for row in json.loads((a.base/'native-curves.json').read_text('utf8'))['trains']:
        for point in row['points']:
            x,y,z=map(int,np.floor(point))
            if not -120<y<310:continue
            for X in range(x-2,x+3):
                for Z in range(z-2,z+3):rails[X//16,Z//16].add((X,y,Z))
    connect=load_grid(a.plan/'connector.npz')
    e=Editor(a.out);yy=np.arange(-128,320)[:,None,None];changed=[];errors=[];columns=0
    for f in sorted((a.source/'source').glob('*.npz')):
        rx,rz=map(int,f.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        def code(s):
            if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
            return r['ids'][s]
        air,stone,dirt,grass=[code(s)for s in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]')]
        materials=[code(s)for s in ('minecraft:black_concrete','minecraft:smooth_stone','minecraft:white_concrete','projectseele:road_asphalt_slab[type=bottom,waterlogged=false]','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]','projectseele:road_marking_slab[type=bottom,waterlogged=false]')]
        bare=[s.split('[')[0]for s in r['names']];soil=np.array([s in SOIL for s in bare]);empty=np.array([s in AIR for s in bare]);natural=np.array([s in SOIL|AIR|{'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}for s in bare]);wet=np.array([s=='minecraft:water'for s in bare])
        for q,b,v in zip(r['coords'],r['before'],r['after']):
            cx,cz=map(int,q);zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
            top=np.where(soil[v],yy,-129).max(0);h=np.rint(sample_grid(plan,'height_y',xx,zz)).astype(np.int16)
            radius=np.hypot(xx-30,zz-296);t=np.clip((radius-600)/1200,0,1)
            bottom=np.where(radius<1800,np.maximum(-128,-478+np.floor(502*np.sqrt(np.maximum(0,1-t*t)))+18),-128).astype(int)
            h=np.maximum(h,bottom);active=sample_grid(plan,'active',xx,zz,True)&(h!=top)&~wet[v].any(0)
            original_walk=sampled(d,'regraded_walk',xx,zz).astype(bool)if 'regraded_walk'in d else np.zeros((16,16),bool)
            linkwalk=sampled(connect,'walk',xx,zz).astype(bool);walk=linkwalk|original_walk
            if not active.any()and not walk.any():continue
            protect=np.zeros(v.shape,bool)
            for x,y,z,X,Y,Z in bychunk[cx,cz]:protect|=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)&(yy>=y)&(yy<=Y)
            for x,y,z in tunnels[cx,cz]:protect[max(0,y-2+128):min(448,y+7+128),z%16,x%16]=True
            for x,y,z in rails[cx,cz]:
                lo,hi=max(0,y-3+128),min(448,y+9+128)
                protect[lo:hi,z%16,x%16]|=~soil[v[lo:hi,z%16,x%16]]
            # Preserve every non-geological block. Nearby voids and foundations
            # get a local buffer; no unbounded top-to-bottom soil columns.
            foreign=~natural[v]&~wet[v];guard=foreign.copy()
            for dy in range(1,5):guard[dy:]|=foreign[:-dy];guard[:-dy]|=foreign[dy:]
            band=active&natural[v]&(yy>=np.maximum(bottom,np.minimum(h,top)-3))&~protect&~guard
            target=np.where(yy>h,air,np.where(yy==h,grass,np.where(yy>=h-3,dirt,stone))).astype(np.uint16)
            v[band]=np.broadcast_to(target,v.shape)[band]
            if walk.any():
                from verify_hakone_network_candidate import PAVEMENT
                from hakone_earthworks import road_blocks
                grade=sampled(d,'grade2',xx,zz);grade[linkwalk]=sampled(connect,'grade2',xx,zz)[linkwalk]
                rh,slab=road_blocks(grade);pave=np.array([s in PAVEMENT|{'minecraft:iron_bars','minecraft:sea_lantern','minecraft:light'} for s in bare])
                road=sampled(d,'road',xx,zz).astype(bool);mark=sampled(d,'marking',xx,zz).astype(bool)
                road[linkwalk]=sampled(connect,'road',xx,zz)[linkwalk];mark[linkwalk]=sampled(connect,'marking',xx,zz)[linkwalk]
                for iz,ix in np.argwhere(walk):
                    y=int(rh[iz,ix]);oldroad=int((sampled(d,'previous_grade2',xx,zz)[iz,ix]+1)//2)if original_walk[iz,ix]else y
                    lo=max(int(bottom[iz,ix]),min(int(top[iz,ix]),y)-3);hi=max(int(top[iz,ix]),oldroad+3,y+3)
                    states=v[lo+128:hi+129,iz,ix];allowed=natural[states]|pave[states]
                    if protect[y+128:y+132,iz,ix].any()or not(natural[v[y+128:y+132,iz,ix]]|pave[v[y+128:y+132,iz,ix]]).all():
                        errors.append(['connector-object',int(xx[iz,ix]),y,int(zz[iz,ix])]);continue
                    ys=np.arange(lo,hi+1);states[allowed&(ys<y)]=stone;states[allowed&(ys>y)]=air
                    index=2 if mark[iz,ix]else 0 if road[iz,ix]else 1
                    v[y+128,iz,ix]=materials[index+3*bool(slab[iz,ix])]
            # Close exterior voids directly under a newly graded surface. The
            # original dome cover and finite room/tunnel AIR stay protected.
            for iz,ix in np.argwhere(active&~walk):
                y=int(h[iz,ix])-1
                while y>=bottom[iz,ix] and empty[b[y+128,iz,ix]]:
                    if protect[y+128,iz,ix]or guard[y+128,iz,ix]:break
                    v[y+128,iz,ix]=stone;y-=1
            if np.any(v!=b):changed.append([cx,cz]);columns+=int((v!=b).any(0).sum())
        e.save();e.regions.clear();print('Landform composed',f.name,len(changed),'chunks',flush=True)
    rows=e.save();manifest=dict(world=str(a.world),regions=rows,cells=sum(r['cells']for r in rows),bounds_xz=list(map(int,m['bounds'])),world_written=False,terrain_columns=columns)
    prior=a.source/'manifest.json'
    if prior.exists():
        status=json.loads(prior.read_text('utf8')).get('preserved_generation_statuses')
        if status:manifest['preserved_generation_statuses']=status
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=errors,visual_verified=False,progress_records_written=False),indent=2),'utf8')
    (a.out/'transport-changed-chunks.json').write_text(json.dumps(changed),'utf8')
    print('Prepared terrain',manifest['cells'],flush=True)


def field(a):
    p=load_grid(a.plan/'surface.npz');xs,zs=p['x'],p['z'];height=p['height_y'];water=p['water']
    if height.size>12000000:raise ValueError('Surface exceeds the bounded native field')
    a.out.mkdir(exist_ok=False)
    with gzip.open(a.out/'hakone_surface.bin.gz','wb')as f:
        f.write(struct.pack('>6i',0x484B3535,int(xs[0]),int(zs[0]),2,len(xs),len(zs)))
        f.write((height*16).astype('>i2').tobytes());f.write(water.astype('>i2').tobytes())
    (a.out/'field.json').write_text(json.dumps(dict(plan=str(a.plan),samples=int(height.size),shared_saved_and_future_surface=True,runtime_scans=False),indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--phase',choices=('combine','plan','connector','compose','field'),required=True)
    for n in ('source','extra','out','gis','base','survey','resource','plan','world','tunnels','proto'):p.add_argument('--'+n,type=Path)
    a=p.parse_args();globals()[a.phase](a)
