"""Compose current port payloads at the measured coast; never install templates.

Current full inventories and actor UUIDs travel unchanged. Historical authored
ownership is used only to repair the ship's terrain-eroded passive hull cells.
The active inland station and the newly commissioned approach stay in place.
"""
import argparse,copy,gzip,json,os,shutil,struct
from pathlib import Path
from collections import Counter
import numpy as np
import nbtlib
from scipy.ndimage import distance_transform_edt,binary_fill_holes
from author_hakone_lakefront import Editor
from query_blocks import AIR
from plan_ashi_landscape_r54 import NATURAL,SOIL,PLANTS
from prepare_hakone_main_terrain import sample_grid
from prepare_hakone_city_cross import packed
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.launch_earthworks import ground
from map_pipeline.install.entity_moves import translated
from install_r53_carrier_trays import stopped_world

DATA=Path('dimensions/projectseele/geofront/data')


def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf8')


def field(path):
    with gzip.open(path,'rb')as f:
        _,x,z,step,w,h=struct.unpack('>6i',f.read(24))
        height=np.frombuffer(f.read(w*h*2),'>i2').reshape(h,w).astype(float)/16
    return dict(x=x+np.arange(w)*step,z=z+np.arange(h)*step,height=height)


def run(a):
    plan=json.loads(a.plan.read_text('utf8'));box=plan['source_bounds'];shift=np.array(plan['delta']);x,y,z,X,Y,Z=box
    if shift.tolist()!=[1824,-144,640]:raise ValueError('Port plan requires a newly surveyed destination')
    O=a.out;O.mkdir(parents=True,exist_ok=False)
    for name in ('source','delta','plan'):(O/name).mkdir()
    folders=[a.source,a.coast]+([a.approach]if a.approach else[])
    captures=[json.loads((p/'capture.json').read_text('utf8'))for p in folders]
    world=Path(captures[0]['world'])
    if any(Path(c['world'])!=world for c in captures):raise ValueError('Different source worlds')
    bounds=[min(c['bounds_xz'][0]for c in captures),min(c['bounds_xz'][1]for c in captures),max(c['bounds_xz'][2]for c in captures),max(c['bounds_xz'][3]for c in captures)]
    grouped={}
    for folder in folders:
        for p in (folder/'source').glob('*.npz'):grouped.setdefault(p.name,[]).append(p)
    for name,files in grouped.items():
        if len(files)==1:os.link(files[0],O/'source'/name);continue
        names=[];codes={};chunks={}
        for p in files:
            with np.load(p)as f:
                remap=[]
                for s in map(str,f['palette']):
                    if s not in codes:codes[s]=len(names);names.append(s)
                    remap.append(codes[s])
                remap=np.asarray(remap,np.uint16)
                for pos,v in zip(f['coordinates'],f['blocks']):
                    key=tuple(map(int,pos));data=remap[v]
                    if key in chunks and not np.array_equal(chunks[key],data):raise ValueError(('Captures disagree',key))
                    chunks[key]=data
        keys=sorted(chunks)
        np.savez_compressed(O/'source'/name,coordinates=np.asarray(keys,np.int32),blocks=np.asarray([chunks[k]for k in keys]),palette=names)
    capture=dict(world=str(world),bounds_xz=bounds,actors=sum((c['actors']for c in captures),[]),source_files=[str(p.relative_to(O))for p in (O/'source').glob('*.npz')])
    write(O/'capture.json',capture);write(O/'plan/relocation.json',plan)
    e=Editor(O);hfield=field(a.terrain);launch=load(world);masks={};protected=plan['preserve_source_volumes']
    with np.load(a.north/'plan/network.npz')as f:road={k:f[k]for k in ('bounds','walk','grade2')}
    def keep(px,py,pz):
        if any(q[0]<=px<=q[3]and q[1]<=py<=q[4]and q[2]<=pz<=q[5]for q in protected):return True
        bx,bz,bX,bZ=map(int,road['bounds'])
        if bx<=px<=bX and bz<=pz<=bZ and road['walk'][pz-bz,px-bx]:
            h=int(np.ceil(road['grade2'][pz-bz,px-bx]/2))
            if h-4<=py<=h+8:return True
        return False
    def put(px,py,pz,state):
        old=e.state(px,py,pz)
        if old==state:return
        key=px//16,pz//16
        if key not in masks:masks[key]=launch.chunk_mask(*key)
        if masks[key][py+128,pz%16,px%16]:raise ValueError(('Launch cell in port edit',px,py,pz))
        e.put(px,py,pz,state)
    # Expected hull ownership after the original boarding openings were cut.
    shape=(Y-y+1,Z-z+1,X-x+1);expected=np.zeros(shape,np.uint16);hull=np.zeros(shape,bool);pal=['minecraft:air'];ids={pal[0]:0}
    for op in json.load(gzip.open(a.ship_ownership,'rt',encoding='utf8')):
        l,b,t,r,T,B=op['box'];l,b,t,r,T,B=max(l,x),max(b,y),max(t,z),min(r,X),min(T,Y),min(B,Z)
        if l>r or b>T or t>B:continue
        state=op['state']
        if state not in ids:ids[state]=len(pal);pal.append(state)
        area=np.s_[b-y:T-y+1,t-z:B-z+1,l-x:r-x+1];expected[area]=ids[state];hull[area]='/dd6_'in op['owner']
    payload={};recovered=[];materials=Counter();natural_codes={}
    for px in range(x,X+1):
        for pz in range(z,Z+1):
            r=e.region(px,pz);v=r['before'][r['index'][px//16,pz//16],y+128:Y+129,pz%16,px%16]
            if r['name']not in natural_codes:natural_codes[r['name']]=np.array([s.split('[')[0]in NATURAL|{'minecraft:light','minecraft:barrier','minecraft:structure_void'}for s in r['names']])
            eligible=~natural_codes[r['name']][v]|hull[:,pz-z,px-x]
            for k in np.flatnonzero(eligible):
                code=v[k];k=int(k)
                py=y+k
                if keep(px,py,pz):continue
                state=r['names'][code];bare=state.split('[')[0];original=pal[int(expected[k,pz-z,px-x])]
                owned=hull[k,pz-z,px-x] and original.split('[')[0]not in AIR|{'minecraft:water','minecraft:barrier'}
                if owned and bare in NATURAL and original!=state:
                    # Passive shape only: current signs, bells and inventories
                    # always come from their exact current saved NBT.
                    if any(w in original for w in ('chest','sign','bell','shulker')):raise ValueError('Missing functional hull block needs original NBT')
                    recovered.append(dict(pos=[px,py,pz],before=state,after=original));state=original;bare=state.split('[')[0]
                if bare not in NATURAL|{'minecraft:light','minecraft:barrier','minecraft:structure_void'} or owned:
                    payload[px,py,pz]=state;materials[bare]+=1
        if (px-x)%64==0:print('Captured current port columns',px-x+1,'/',X-x+1,flush=True)
    payload_palette=sorted(set(payload.values()));payload_codes={s:i for i,s in enumerate(payload_palette)}
    np.savez_compressed(O/'current-payload.npz',coordinates=np.asarray(list(payload),np.int32),states=np.asarray([payload_codes[s]for s in payload.values()],np.uint16),palette=payload_palette,delta=shift)
    write(O/'hull-recovery.json',recovered)
    tags=nbtlib.load(a.components/'block-entities.nbt')['BlockEntities'];moves=[];retained=[]
    for tag in tags:
        p=tuple(int(tag[k])for k in ('x','y','z'))
        if keep(*p):retained.append(tag);continue
        if p not in payload:raise ValueError(('Device is outside the actual port payload',p))
        target=tuple(int(p[i]+shift[i])for i in range(3));new=copy.deepcopy(tag)
        for k,v in zip(('x','y','z'),target):new[k]=nbtlib.Int(v)
        moves.extend([nbtlib.Compound(Pos=nbtlib.Long(packed(p)),Before=copy.deepcopy(tag)),nbtlib.Compound(Pos=nbtlib.Long(packed(target)),After=new)])
    # Restore the complete old footprint to the real terrain field. Native
    # station volumes and commissioned road cells are finite exceptions.
    for px in range(x,X+1):
        for pz in range(z,Z+1):
            h=int(np.rint(sample_grid(hfield,'height',np.array(px),np.array(pz))))
            ys=np.arange(y,max(Y,h+1)+1);r=e.region(px,pz);idx=r['index'][px//16,pz//16]
            protected_col=np.zeros(len(ys),bool)
            for q in protected:
                if q[0]<=px<=q[3]and q[2]<=pz<=q[5]:protected_col|=(ys>=q[1])&(ys<=q[4])
            bx,bz,bX,bZ=map(int,road['bounds'])
            if bx<=px<=bX and bz<=pz<=bZ and road['walk'][pz-bz,px-bx]:
                level=int(np.ceil(road['grade2'][pz-bz,px-bx]/2));protected_col|=(ys>=level-4)&(ys<=level+8)
                h=min(h,level-1)
            codes=[]
            for state in ('minecraft:air','minecraft:grass_block[snowy=false]','minecraft:dirt','minecraft:stone'):
                if state not in r['ids']:r['ids'][state]=len(r['names']);r['names'].append(state)
                codes.append(r['ids'][state])
            values=np.where(ys>h,codes[0],np.where(ys==h,codes[1],np.where(ys>=h-3,codes[2],codes[3]))).astype(np.uint16)
            column=r['after'][idx,ys+128,pz%16,px%16];changed=(column!=values)&~protected_col
            for j in np.flatnonzero(changed&(ys>Y)):
                if r['names'][column[j]].split('[')[0]not in NATURAL|{'minecraft:light'}:raise ValueError(('Unclassified high port object',px,int(ys[j]),pz))
            key=px//16,pz//16
            if key not in masks:masks[key]=launch.chunk_mask(*key)
            if np.any(changed&masks[key][ys+128,pz%16,px%16]):raise ValueError('Port healing enters native mechanism')
            r['after'][idx,ys[changed]+128,pz%16,px%16]=values[changed]
        if (px-x)%64==0:print('Restored inland port columns',px-x+1,'/',X-x+1,flush=True)
    e.save();e.regions.clear();print('Old port footprint restored in candidate; current payload',len(payload),'recovered hull',len(recovered),flush=True)
    # The reclaimed apron has a continuous earth foundation; the berth has
    # real water depth and the piers retain their current complete piles.
    cb=captures[1]['bounds_xz'];cx,cz,cX,cZ=cb
    with np.load(a.coast/'measured.npz')as f:old_ground=f['top']
    zz,xx=np.mgrid[cz:cZ+1,cx:cX+1]
    yard=(xx>=3048)&(xx<=3223)&(zz>=960)&(zz<=1208)
    edge=distance_transform_edt(~yard);target=np.clip(old_ground,np.ceil(-80-edge*.6),np.floor(-80+edge*.6)).astype(np.int16)
    target[yard]=-80
    basin=(xx>=3249)&(xx<=3348)&(zz>=952)&(zz<=1248);target[basin]=np.minimum(old_ground[basin],-95)
    if any(np.any(a)for a in((target-old_ground)[0],(target-old_ground)[-1],(target-old_ground)[:,0],(target-old_ground)[:,-1])):raise ValueError('Port earthwork reaches capture boundary')
    for j,i in zip(*np.nonzero((target!=old_ground)|yard|basin)):
        px,pz=int(i+cx),int(j+cz);h=int(target[j,i]);g=int(old_ground[j,i])
        top=max(g,h,-75 if yard[j,i]else -81)
        for py in range(min(g,h)-2,top+2):
            old=e.state(px,py,pz);bare=old.split('[')[0]
            if bare not in NATURAL|{'minecraft:light'}:raise ValueError(('Unknown coast object',px,py,pz,old))
            state='minecraft:air'if py>h else'minecraft:stone'
            if py>h and py<=-82 and not yard[j,i]:state='minecraft:water[level=0]'
            if py==h and not basin[j,i]and not yard[j,i]:state='minecraft:grass_block[snowy=false]'if h>=-82 else'minecraft:gravel'
            put(px,py,pz,state)
    dry_hull=[]
    for py in range(y,63):
        skin=np.zeros((Z-z+1,X-x+1),bool)
        for px in range(1428,1512):
            for pz in range(324,578):
                if (px,py,pz)in payload and hull[py-y,pz-z,px-x]:skin[pz-z,px-x]=True
        interior=binary_fill_holes(skin)&~skin
        for j,i in zip(*np.nonzero(interior)):
            p=(int(i+x),py,int(j+z));q=tuple(int(p[k]+shift[k])for k in range(3))
            if p not in payload:put(*q,'minecraft:air');dry_hull.append(list(q))
    for p,state in payload.items():
        q=tuple(int(p[i]+shift[i])for i in range(3));old=e.state(*q)
        if old.split('[')[0]not in NATURAL|{'minecraft:light'}:raise ValueError(('Port payload destination collision',q,old))
        put(*q,state)
    # The inland station and commissioned inland road are deliberately not
    # duplicated. Their former overlap must still leave a continuous coastal
    # apron, rather than a four-block trench in the translated yard.
    apron_completion=[]
    for px in range(3048,3224):
        for pz in range(960,1209):
            for py in range(-79,-75):
                source=tuple(int(v-d)for v,d in zip((px,py,pz),shift))
                if source in payload:continue
                old=e.state(px,py,pz)
                if old.split('[')[0]not in NATURAL:raise ValueError(('Unexpected apron insert',px,py,pz,old))
                state='projectseele:nerv_floor_panel'if py==-76 else'minecraft:gray_concrete'
                put(px,py,pz,state);apron_completion.append([px,py,pz])
    regions=e.save();e.regions.clear()
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](moves)}).save(O/'block-entities.dat',gzipped=True)
    actor_moves=[]
    for row in nbtlib.load(a.components/'entities.nbt')['Records']:
        old=row['Entity'];actor_moves.append(nbtlib.Compound(Before=copy.deepcopy(old),After=translated(old,shift),Delta=nbtlib.IntArray(shift)))
    nbtlib.File({'Moves':nbtlib.List[nbtlib.Compound](actor_moves)}).save(O/'entity-moves.dat',gzipped=True)
    # The runtime reads these destination coordinates directly; the separate
    # facility offset moves its hard-coded power/control reference frame.
    rel=Path('r07_installations.json');prior=a.components/'baseline'/rel;meta=json.loads(prior.read_text('utf8'));changed=0
    for row in meta['entities']:
        if row['key'].startswith('vehicle/fleet/'):
            row['position']=[v+int(d)for v,d in zip(row['position'],shift)];changed+=1
    for name in ('before','after'):(O/name).mkdir()
    shutil.copy2(prior,O/'before'/rel);write(O/'after'/rel,meta)
    rel=DATA/'projectseele_facility_sites.dat';prior=a.components/'baseline'/rel
    if prior.exists():
        saved=nbtlib.load(prior);(O/'before'/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(prior,O/'before'/rel)
    else:saved=nbtlib.File({'DataVersion':nbtlib.Int(3465),'data':nbtlib.Compound()})
    offsets=saved['data'].setdefault('Offsets',nbtlib.Compound())
    if any(map(int,offsets.get('PORT',[0,0,0]))):raise ValueError('Port was already relocated')
    offsets['PORT']=nbtlib.IntArray(shift);dest=O/'after'/rel;dest.parent.mkdir(parents=True,exist_ok=True);saved.save(dest,gzipped=True)
    with stopped_world(world):shutil.copytree(world/'mtr',O/'preserved-native')
    write(O/'hull-recovery.json',recovered)
    write(O/'dry-hull-interiors.json',dry_hull)
    write(O/'apron-completion.json',apron_completion)
    write(O/'current-payload.json',dict(cells=len(payload),materials=dict(materials),recovered_hull_cells=len(recovered),moved_devices=len(moves)//2,retained_station_devices=len(retained),actors=len(actor_moves),fleet_metadata_positions=changed))
    manifest=dict(world=str(world),bounds_xz=bounds,regions=regions,cells=sum(r['cells']for r in regions),entity_moves='entity-moves.dat',json_metadata=['r07_installations.json'],preserve_native_members=True,world_written=False)
    write(O/'manifest.json',manifest);write(O/'launch-protection.json',check_candidate(launch,O))
    # Deliberately not publishable until the complete access, ship clearance,
    # source healing and independent inventory/identity checks are finished.
    write(O/'functional-check.json',dict(errors=[['pending port access and 3D acceptance']],world_written=False))
    print('Port physical candidate composed; not installed',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','coast','components','plan','terrain','north','ship-ownership','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--approach',type=Path)
    run(p.parse_args())
