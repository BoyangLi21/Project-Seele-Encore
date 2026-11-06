"""Offline surface ownership: finite solids, mandatory air, then terrain.

The current save is the source, never a previous repair candidate. This tool
does not touch actors, inventories or runtime movement. A connected component
report is evidence, not permission to delete architectural members.
"""
import argparse, gzip, json, os, struct
import shutil
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
from scipy.ndimage import grey_opening, maximum_filter, distance_transform_edt
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid, sampled
from prepare_hakone_main_terrain import sample_grid
from plan_ashi_landscape_r54 import SOIL, PLANTS
from query_blocks import AIR
from hakone_earthworks import min_slope_envelope

AIRPORTS = [(500,80,1050,1220,1500),(-2150,80,-320,-1450,80)]

def contracts(base, tunnels):
    boxes=[r['occupied_bounds'] for r in json.loads((base/'catalog.json').read_text('utf8'))]
    boxes+=json.loads((base/'station-volumes.json').read_text('utf8'))
    bychunk=defaultdict(list)
    for x,y,z,X,Y,Z in boxes:
        box=[x-1,y-2,z-1,X+1,Y+2,Z+1]
        for cx in range(box[0]//16,box[3]//16+1):
            for cz in range(box[2]//16,box[5]//16+1):bychunk[cx,cz].append(box)
    rails=defaultdict(set)
    for row in json.loads((base/'native-curves.json').read_text('utf8'))['trains']:
        for p in row['points']:
            x,y,z=map(int,np.floor(p))
            if not -120<y<310:continue
            for X in range(x-2,x+3):
                for Z in range(z-2,z+3):rails[X//16,Z//16].add((X,y,Z))
    layers=defaultdict(lambda:defaultdict(set))
    for x,y,z in json.loads(tunnels.read_text('utf8'))['points']:
        layers[x//16,z//16][x,z].add(y)
    return boxes,bychunk,rails,layers

def prepare_plan(a):
    a.plan.mkdir(parents=True,exist_ok=False)
    p=load_grid(a.field);h=p['height_y'].astype(np.float32)
    zz,xx=np.meshgrid(p['z'],p['x'],indexing='ij')
    active=(xx>=-3000)&(xx<2600)&(zz>=-800)&(zz<1800)
    # Existing terrain already provides the broad geographical field. Remove
    # thin positive remnants rather than re-smoothing the real mountain system.
    opened=grey_opening(h,size=(7,7));spikes=(h-opened>=10)&active
    h[spikes]=opened[spikes]
    airports=np.zeros(h.shape,bool)
    for x,y,z,X,Z in AIRPORTS:
        footprint=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)
        distance=distance_transform_edt(~footprint)*2
        # A cut meets the surrounding mountain by a bounded exterior slope;
        # the runway itself is fixed to its observed saved elevation.
        use=(distance<=160)&active&(p['water']==-32768)
        h[use]=np.minimum(h[use],y+distance[use]*.75)
        h[footprint]=y;airports|=footprint
    d=load_grid(a.base/'network.npz')
    walk=sampled(d,'walk',xx,zz).astype(bool)
    grade=sampled(d,'grade2',xx,zz)/2
    # Keep public streets at their installed grade; no new street is invented.
    h[walk&~airports]=np.minimum(h[walk&~airports],grade[walk&~airports])
    # A previous conflicting pin may itself be a knife wall. Solve slopes
    # against the whole field, then support retained ground streets/buildings
    # with a broad earthwork cone; elevated railway/station decks are not pins.
    shaped=min_slope_envelope(h,1.5)
    groundwalk=walk&~sampled(d,'tunnel',xx,zz).astype(bool)
    pins=np.where(groundwalk,grade,-np.inf)
    for row in json.loads((a.base/'catalog.json').read_text('utf8')):
        x,y,z,X,Y,Z=row['occupied_bounds'];inside=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)
        pins[inside]=np.maximum(pins[inside],y)
    for x,y,z,X,Z in AIRPORTS:
        inside=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z);pins[inside]=y
    support=-min_slope_envelope(-pins,1.5)
    fitted=np.maximum(shaped,support)
    blend=np.clip(distance_transform_edt(active)*2/64,0,1);blend=blend*blend*(3-2*blend)
    dry=p['water']==-32768
    h[dry]=h[dry]+(fitted[dry]-h[dry])*blend[dry]
    p['height_y']=np.rint(h).astype(np.int16);p['repair_active']=active;p['airports']=airports
    np.savez_compressed(a.plan/'surface.npz',**p)
    (a.plan/'plan.json').write_text(json.dumps(dict(source=str(a.field),spike_samples=int(spikes.sum()),airports=AIRPORTS,
        authority_order=['retained finite structure','recorded transport and airport air','geographical soil'],runtime_scans=False),indent=2),'utf8')

def classify(a,boxes):
    report=json.loads((a.scan/'floating-components.json').read_text('utf8'));selected=defaultdict(set);rows=[]
    for c in report['components']:
        x,y,z,X,Y,Z=c['bounds'];m={s.split('[')[0] for s in c['materials']}
        overlaps=any(x<=b[3] and X>=b[0] and z<=b[5] and Z>=b[2] and y<=b[4]+2 and Y>=b[1]-2 for b in boxes)
        action='retain-architectural-or-unclassified'
        # Entirely geological islands cannot be a bridge, sign, station canopy
        # or inventory. Underground and incomplete-boundary objects are retained.
        if c['unknown']:action='unknown-neighbor-retained'
        elif y<32:action='underground-retained'
        elif m<=SOIL|PLANTS and not overlaps:action='remove-floating-geology'
        if action.startswith('remove'):
            for rx,rz,i in c['parts']:selected[rx,rz].add(i)
        rows.append(dict(id=c['id'],cells=c['cells'],bounds=c['bounds'],action=action))
    (a.plan/'floating-decisions.json').write_text(json.dumps(dict(counts=dict(Counter(r['action'] for r in rows)),components=rows),indent=2),'utf8')
    return selected

def compose(a):
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    for f in (a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    for f in (a.source/'delta').glob('*.npz'):shutil.copy2(f,a.out/'delta'/f.name)
    p=load_grid(a.plan/'surface.npz');d=load_grid(a.base/'network.npz')
    boxes,bychunk,rails,layers=contracts(a.base,a.tunnels)
    selected=classify(a,boxes) if a.scan else {}
    e=Editor(a.out);yy=np.arange(-128,320)[:,None,None];counts=Counter();changed=[]
    for f in sorted((a.source/'source').glob('*.npz')):
        rx,rz=map(int,f.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        def code(s):
            if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
            return r['ids'][s]
        air,stone,dirt,grass=[code(s) for s in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]')]
        bare=[s.split('[')[0] for s in r['names']]
        geological=np.array([s in SOIL|PLANTS for s in bare]);empty=np.array([s in AIR for s in bare]);wet=np.array([s=='minecraft:water' for s in bare])
        fragments=defaultdict(list)
        if selected.get((rx,rz)):
            with np.load(a.scan/f.name) as data:
                at=data['indices'][np.isin(data['labels'],list(selected[rx,rz]))].astype(np.int64)
            px=at%512+rx*512;pz=(at//512)%512+rz*512;py=at//(512*512)-128
            for x,y,z in zip(px.astype(int),py.astype(int),pz.astype(int)):fragments[x//16,z//16].append((x,y,z))
        for q,b,v in zip(r['coords'],r['before'],r['after']):
            cx,cz=map(int,q);key=cx,cz;zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
            active=sample_grid(p,'repair_active',xx,zz,True)
            if not active.any() and key not in rails and key not in fragments:continue
            radius=np.hypot(xx-30,zz-296);t=np.clip((radius-600)/1200,0,1)
            bottom=np.where(radius<1800,np.maximum(-128,-478+np.floor(502*np.sqrt(np.maximum(0,1-t*t)))+18),-128).astype(int)
            h=np.maximum(bottom,np.rint(sample_grid(p,'height_y',xx,zz)).astype(int))
            protect=np.zeros(v.shape,bool)
            for x,y,z,X,Y,Z in bychunk[key]:protect|=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)&(yy>=y)&(yy<=Y)
            # Only actual retained tunnel layers protect their finite walls and
            # roof; a whole mountain rectangle no longer freezes stray soil.
            for (x,z),heights in layers[key].items():
                for y in heights:protect[max(0,y-2+128):min(448,y+7+128),z%16,x%16]=True
            water_level=sample_grid(p,'water',xx,zz,True)
            water=water_level!=-32768
            cut=active&~water&(yy>h)&(yy>=bottom)&(geological[v]|wet[v])&~protect
            counts['excess_soil_removed']+=int(cut.sum());v[cut]=air
            # Retained underground is below its measured dome cap. Above it,
            # earthwork fills support the new surface, while finite interiors
            # and the original launch passage AIR keep their identity.
            passage=((xx>=-110)&(xx<=225)&(zz>=-155)&(zz<=15)&(yy>=25)&(yy<=180))|((xx>=-425)&(xx<=-285)&(zz>=690)&(zz<=830)&(yy>=20)&(yy<=180))
            fill=active&~water&(yy<=h)&(yy>=bottom)&empty[v]&~protect&~(passage&empty[b])
            counts['surface_support_filled']+=int(fill.sum());v[fill]=stone
            street=sampled(d,'walk',xx,zz).astype(bool)
            street_y=np.ceil(sampled(d,'grade2',xx,zz)/2).astype(int)
            clearance=street&(yy>street_y)&(yy<=street_y+4)&geological[v]&~protect
            counts['street_soil_removed']+=int(clearance.sum());v[clearance]=air
            # Existing airfield/apron is an explicit open-air use. A soil lid
            # is not protected by the airport's large reservation rectangle.
            for x,y,z,X,Z in AIRPORTS:
                footprint=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)
                apron=np.isin(v[y+128],[i for i,s in enumerate(bare) if s in {'minecraft:gray_concrete','minecraft:black_concrete','minecraft:yellow_concrete','minecraft:white_concrete'}])
                footprint|=apron&(xx>=x-16)&(xx<=X+16)&(zz>=z-16)&(zz<=Z+16)
                cut=footprint&(yy>y)&geological[v]&~protect
                counts['airport_soil_removed']+=int(cut.sum());v[cut]=air
            # Rail clearance wins over terrain even in a station reservation.
            # Native deck and all device blocks remain exactly as captured.
            for x,y,z in rails[key]:
                c=v[y+128:y+134,z%16,x%16];bad=geological[c]
                counts['rail_soil_removed']+=int(bad.sum());c[bad]=air
            # Distinct road/tunnel floors can share XZ. Clear each headroom
            # separately and stop below the next recorded floor.
            for (x,z),heights in layers[key].items():
                ys=sorted(heights)
                for i,y in enumerate(ys):
                    hi=min(y+4,ys[i+1]-1 if i+1<len(ys) else y+4)
                    c=v[y+129:hi+129,z%16,x%16];bad=geological[c]
                    counts['tunnel_soil_removed']+=int(bad.sum());c[bad]=air
            for x,y,z in fragments[key]:
                if y<bottom[z%16,x%16] or protect[y+128,z%16,x%16]:continue
                if geological[v[y+128,z%16,x%16]]:v[y+128,z%16,x%16]=air;counts['floating_soil_removed']+=1
            # New exposed soil gets its surface cap, but carved rail/airport
            # air is never filled back by this operation.
            iz,ix=np.nonzero(active&~water&(h<320))
            iy=h[iz,ix]+128
            valid=geological[v[iy,iz,ix]]&~protect[iy,iz,ix]
            iz,ix,iy=iz[valid],ix[valid],iy[valid]
            v[iy,iz,ix]=grass
            for dy in range(1,4):
                use=(iy-dy>=bottom[iz,ix]+128)&geological[v[iy-dy,iz,ix]]&~protect[iy-dy,iz,ix]
                v[iy[use]-dy,iz[use],ix[use]]=dirt
            if np.any(v!=b):changed.append([cx,cz])
        e.save();e.regions.clear()
        print('Volume ownership',f.name,'changed chunks',len(changed),flush=True)
    rows=e.save();prior=json.loads((a.source/'manifest.json').read_text('utf8'))
    prior.update(regions=rows,cells=sum(r['cells'] for r in rows),world_written=False,repair_counts=dict(counts))
    (a.out/'manifest.json').write_text(json.dumps(prior,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=[],visual_verified=False,progress_records_written=False,repair_counts=dict(counts)),indent=2),'utf8')
    (a.out/'transport-changed-chunks.json').write_text(json.dumps(changed),'utf8')
    print('COMPOSED',prior['cells'],dict(counts),flush=True)

def field(a):
    p=load_grid(a.plan/'surface.npz');a.out.mkdir(parents=True,exist_ok=True)
    with gzip.open(a.out/'hakone_surface.bin.gz','wb') as f:
        f.write(struct.pack('>6i',0x484B3535,int(p['x'][0]),int(p['z'][0]),2,len(p['x']),len(p['z'])))
        f.write((p['height_y']*16).astype('>i2').tobytes());f.write(p['water'].astype('>i2').tobytes())

if __name__=='__main__':
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--phase',choices=['plan','compose','field'],required=True)
    for key in ['base','field','plan','tunnels','source','out','scan']:ap.add_argument('--'+key,type=Path)
    a=ap.parse_args();{'plan':prepare_plan,'compose':compose,'field':field}[a.phase](a)
