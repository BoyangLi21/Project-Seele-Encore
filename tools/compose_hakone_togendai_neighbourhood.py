"""Compose a finite Togendai candidate while preserving complete parcel contents."""
import argparse,copy,json,os,shutil
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
import nbtlib
from scipy.ndimage import binary_dilation
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.launch_earthworks import ground
from prepare_hakone_togendai_neighbourhood import rect,save_json,PAVE,EMPTY
from prepare_hakone_city_cross import packed
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL,PLANTS,NATURAL
from install_r53_carrier_trays import stopped_world
from map_pipeline.frontage_geometry import entrance_frame
from map_pipeline.payload_exceptions import record_exception

def compose(a):
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('source','delta','payloads','plan'):(a.out/name).mkdir()
    for file in (a.source/'source').glob('*.npz'):os.link(file,a.out/'source'/file.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    for file in a.design.glob('*.json'):shutil.copy2(file,a.out/'plan'/file.name)
    shutil.copy2(a.base_plan/'native-curves.json',a.out/'plan/native-curves.json')
    with np.load(a.design/'design.npz')as f:d={k:f[k]for k in f.files}
    bounds=d['bounds'];x,z,X,Z=map(int,bounds);shape=d['walk'].shape
    bridge=d.get('bridge',np.zeros(shape,bool))
    covered=d.get('covered',np.zeros(shape,bool))
    rows=json.loads((a.design/'buildings.json').read_text('utf8'))
    capture=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(capture['world'])
    devices={tuple(int(t[k])for k in('x','y','z')):t for t in nbtlib.load(a.survey/'captured-devices.dat')['Devices']}
    guard=load(world);e=Editor(a.out);changes={};payloads=[];moved=set();stats=Counter();errors=[]
    # Snapshot EVERY parcel before retiring any old volume. This also handles
    # a destination that overlaps an old floor in the same vertical column.
    for number,row in enumerate(rows):
        box=row['payload_bounds'];dy=row['dy'];shift=row.get('translation',[0,dy,0]);lo=np.asarray(box[:3]);hi=np.asarray(box[3:]);sx,sy,sz=map(int,hi-lo+1)
        if any(all(volume[i]<=actor['pos'][i]<=volume[i+3]for i in range(3))for actor in capture['actors']for volume in (box,row['new_payload_bounds'])):raise ValueError('An occupied parcel or destination requires an explicit actor move')
        names=[];codes={};v=np.empty((sy,sz,sx),np.uint16)
        for px in range(box[0],box[3]+1):
            for pz in range(box[2],box[5]+1):
                r=e.region(px,pz);col=r['before'][r['index'][px//16,pz//16],box[1]+128:box[4]+129,pz%16,px%16]
                remap=[]
                for state in r['names']:
                    if state not in codes:codes[state]=len(names);names.append(state)
                    remap.append(codes[state])
                v[:,pz-box[2],px-box[0]]=np.asarray(remap,np.uint16)[col]
        np.savez_compressed(a.out/'payloads'/f'{number}.npz',bounds=box,dy=dy,translation=shift,blocks=v,palette=names)
        payloads.append((box,shift,v,names));stats['parcel_payload_cells']+=int(v.size)
        for pos,tag in devices.items():
            if not all(box[i]<=pos[i]<=box[i+3]for i in range(3)):continue
            if pos in moved:raise ValueError('Overlapping parcel payloads')
            moved.add(pos);q=tuple(pos[i]+shift[i]for i in range(3));new=copy.deepcopy(tag)
            for k,value in zip(('x','y','z'),q):new[k]=nbtlib.Int(value)
            changes.setdefault(pos,{})['Before']=copy.deepcopy(tag);changes.setdefault(q,{})['After']=new
        for other in rows[:number]:
            for key in ('payload_bounds','new_payload_bounds'):
                b=other[key];q=row[key]
                if all(max(q[i],b[i])<=min(q[i+3],b[i+3])for i in (0,2)):raise ValueError(('Overlapping parcels',key,row['id'],other['id']))
    for p,r in changes.items():
        if 'After'in r and p in devices and p not in moved:raise ValueError(('Destination occupied by retained device',p))
    # Original addresses, schedules, vehicle data and identities remain bytes.
    with stopped_world(world):shutil.copytree(world/'mtr',a.out/'preserved-native')
    shutil.copy2(a.survey/'captured-devices.dat',a.out/'captured-devices.dat')
    design_spec=json.loads((a.design/'authored-design.json').read_text('utf8'))
    removed_vegetation=[]
    for box in design_spec.get('retire_vegetation_volumes',[]):
        for px in range(box[0],box[3]+1):
            for pz in range(box[2],box[5]+1):
                for py in range(box[1],box[4]+1):
                    state=e.state(px,py,pz);mat=state.split('[')[0]
                    if not(mat.endswith('_leaves')or mat.endswith('_log')):continue
                    if (px,py,pz)in devices or guard.chunk_mask(px//16,pz//16)[py+128,pz%16,px%16]:raise ValueError(('Retained device or launch cell in vegetation retirement',px,py,pz))
                    removed_vegetation.append(dict(pos=[px,py,pz],before=state,after='minecraft:air'));e.put(px,py,pz,'minecraft:air')
    save_json(a.out/'retired-vegetation.json',removed_vegetation)
    for remnant in design_spec.get('retire_street_remnants',[]):
        pos=remnant['pos']
        if tuple(pos)in devices or e.state(*pos,original=True)!=remnant['state']:raise ValueError(('Changed street remnant',pos))
        e.put(*pos,remnant.get('after','minecraft:air'));stats['explicit_old_lamp_remnants']+=1
    oldnet=np.load(a.base_plan/'network.npz');bx,bz,_,_=map(int,oldnet['bounds']);area=np.s_[z-bz:Z-bz+1,x-bx:X-bx+1]
    oldwalk=oldnet['walk'][area].copy();oldgrade=oldnet['grade2'][area].copy();oldnet.close()
    for row in rows:
        for px,py,pz in row.get('footway',[]):
            l,t,R,B=max(x,px-1),max(z,pz-1),min(X,px+1),min(Z,pz+1)
            if l<=R and t<=B:oldwalk[t-z:B-z+1,l-x:R-x+1]=True
    oldowned=binary_dilation(oldwalk,iterations=2)
    rebuild=d['core']|binary_dilation(d['walk'],iterations=6)
    for box in design_spec.get('retire_road_areas',[]):rebuild[rect(bounds,box)]=True
    rebuild[d['ports']&~d['walk']]=False
    retired_scope=rebuild&oldowned
    if design_spec.get('togendai_forecourt',True):retired_scope[rect(bounds,[-326,979,-246,996])]=True
    retained=json.loads((a.design/'retained-buildings.json').read_text('utf8'))
    boxes=[[b[0]-2,b[1]-3,b[2]-2,b[3]+2,b[4]+8,b[5]+2]for b in retained]
    boxes += design_spec.get('protected_volumes',[[-316,95,997,-255,135,1048],[-316,90,1049,-255,112,1090],[-328,110,989,-244,125,998]])
    # Native cable cars hang below their guide line. A conservative swept
    # volume protects both movement directions, independently of station boxes.
    cable=defaultdict(list)
    curves=json.loads((a.base_plan/'native-curves.json').read_text('utf8'))
    for row in curves.get('ropeway',curves.get('ropeways',[])):
        for px,py,pz in row['points']:
            px,py,pz=map(int,np.floor([px,py,pz]))
            for Q in range(px-3,px+4):
                for R in range(pz-3,pz+4):cable[Q//16,R//16].append((Q,py,R))
    trains=defaultdict(dict)
    if design_spec.get('preserve_train_corridors',False):
        for row in curves['trains']:
            for px,py,pz in row['points']:
                px,py,pz=map(int,np.floor([px,py,pz]))
                if px<x-8 or px>X+8 or pz<z-8 or pz>Z+8 or py<-100 or py>310:continue
                for Q in range(px-8,px+9):
                    for R in range(pz-8,pz+9):
                        lo,hi=trains[Q//16,R//16].get((Q,R),(320,-129))
                        trains[Q//16,R//16][Q,R]=(min(lo,py-30),max(hi,py+7))
    yy=np.arange(-128,320)[:,None,None];retired=[];protected_chunks={}
    def protected_chunk(cx,cz):
        if (cx,cz)in protected_chunks:return protected_chunks[cx,cz]
        zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16];protect=guard.chunk_mask(cx,cz)
        for q in boxes:
            if q[0]>cx*16+15 or q[3]<cx*16 or q[2]>cz*16+15 or q[5]<cz*16:continue
            protect|=(xx>=q[0])&(xx<=q[3])&(zz>=q[2])&(zz<=q[5])&(yy>=q[1])&(yy<=q[4])
        for Q,Y,R in cable[cx,cz]:protect[max(0,Y-10+128):min(448,Y+7+128),R%16,Q%16]=True
        for (Q,R),(lo,hi)in trains[cx,cz].items():
            lo,hi=max(-128,lo),min(319,hi)
            keep=np.ones(hi-lo+1,bool)
            if design_spec.get('train_underpasses') and x<=Q<=X and z<=R<=Z:
                from map_pipeline.rail_underpasses import editable_underpass_column
                keep&=~editable_underpass_column(e,Q,R,lo,hi,design_spec['train_underpasses'],oldwalk[R-z,Q-x],oldgrade[R-z,Q-x])
            protect[lo+128:hi+129,R%16,Q%16]|=keep
        for pos in devices.keys()-moved:
            if pos[0]//16==cx and pos[2]//16==cz:protect[pos[1]+128,pos[2]%16,pos[0]%16]=True
        protected_chunks[cx,cz]=protect
        return protect
    for box,shift,v,names in payloads:
        for px in range(box[0],box[3]+1):
            for pz in range(box[2],box[5]+1):
                r=e.region(px,pz);idx=r['index'][px//16,pz//16];a0,b0=box[1]+128,box[4]+129
                if 'minecraft:air'not in r['ids']:r['ids']['minecraft:air']=len(r['names']);r['names'].append('minecraft:air')
                preserve=protected_chunk(px//16,pz//16)[a0:b0,pz%16,px%16]
                r['after'][idx,a0:b0,pz%16,px%16][~preserve]=r['ids']['minecraft:air']
    for file in sorted((a.out/'source').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:])
        if rx*512>X or rx*512+511<x or rz*512>Z or rz*512+511<z:continue
        r=e.region(rx*512,rz*512)
        def code(s):
            if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
            return r['ids'][s]
        air,stone,dirt,grass,asphalt,paving,stripe,aslab,pslab,sslab=[code(s)for s in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:black_concrete','minecraft:smooth_stone','minecraft:white_concrete','projectseele:road_asphalt_slab[type=bottom,waterlogged=false]','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]','projectseele:road_marking_slab[type=bottom,waterlogged=false]')]
        natural=np.array([s.split('[')[0]in SOIL|PLANTS for s in r['names']]);empty=np.array([s.split('[')[0]in EMPTY for s in r['names']]);pave=np.array([s.split('[')[0]in PAVE for s in r['names']]);soil=np.array([s.split('[')[0]in SOIL for s in r['names']])
        decor=np.array([s.split('[')[0]in {'minecraft:iron_bars','minecraft:sea_lantern','minecraft:stone_brick_wall','minecraft:polished_andesite','minecraft:polished_deepslate'}for s in r['names']])
        civil=np.array([s.split('[')[0]in set(design_spec.get('retire_civil_materials',[]))for s in r['names']])
        for (cx,cz),before,v in zip(r['coords'],r['before'],r['after']):
            cx,cz=int(cx),int(cz);zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16];inside=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)
            iz=np.clip(zz-z,0,shape[0]-1);ix=np.clip(xx-x,0,shape[1]-1)
            walk=d['walk'][iz,ix]&inside;new=d['ground'][iz,ix];old=d['old_ground'][iz,ix];active=inside&(new!=old)&(old>-129)
            retire=retired_scope[iz,ix]&inside
            explicit=np.zeros((448,16,16),bool)
            for ax,ay,az,bX,bY,bZ in design_spec.get('retire_civil_volumes',[]):
                if ax>cx*16+15 or bX<cx*16 or az>cz*16+15 or bZ<cz*16:continue
                if not(x<=ax<=bX<=X and z<=az<=bZ<=Z and -128<=ay<=bY<320):raise ValueError('Civil retirement exceeds captured scope')
                explicit|=(xx>=ax)&(xx<=bX)&(zz>=az)&(zz<=bZ)&(yy>=ay)&(yy<=bY)
            if not (active|walk|retire).any() and not explicit.any():continue
            protect=protected_chunk(cx,cz)
            owned_civil=explicit&~protect&civil[v]
            replacement=np.where(yy>new,air,np.where(yy==new,grass,np.where(yy>=new-3,dirt,stone)))
            v[owned_civil]=np.broadcast_to(replacement,v.shape)[owned_civil]
            stats['explicit_retired_legacy_civil_cells']+=int(owned_civil.sum())
            own=retire&~protect&(yy>=old-4)&(yy<=np.maximum(old+12,(oldgrade[iz,ix]+1)//2+8))
            retiredmask=own&(pave[v]|decor[v]);stats['retired_pavement_and_details']+=int(retiredmask.sum());v[retiredmask]=air
            # Only the exterior skin is moved. Existing underground voids,
            # equipment and all retained finite room volumes survive.
            band=active&~protect&(yy>=np.minimum(old,new)-3)
            cut=band&(yy>new)&natural[v];v[cut]=air;stats['cut_cells']+=int(cut.sum())
            fill=band&(yy<=new)&(natural[v]|empty[v]);material=np.where(yy==new,grass,np.where(yy>=new-3,dirt,stone));v[fill]=np.broadcast_to(material,v.shape)[fill];stats['filled_or_graded_cells']+=int(fill.sum())
            floor,slab=road_blocks(d['grade2'][iz,ix])
            for j,i in np.argwhere(walk):
                px,pz=int(xx[j,i]),int(zz[j,i]);h=int(floor[j,i]);j0,i0=int(iz[j,i]),int(ix[j,i])
                # Native station floor is retained, not filled through rooms.
                if protect[h+128,j,i]:
                    if not pave[v[h+128,j,i]] and r['names'][v[h+128,j,i]].split('[')[0]not in design_spec.get('retained_pavement_materials',[]):errors.append(['protected road floor',px,h,pz,r['names'][v[h+128,j,i]]])
                    continue
                deck=bool(bridge[j0,i0]or covered[j0,i0])
                for Y in range(h-2 if deck else min(int(old[j,i])-2,h-2),h+(5 if d['road'][j0,i0]or covered[j0,i0]else 4)):
                    if protect[Y+128,j,i]:continue
                    state=int(v[Y+128,j,i]);allowed=natural[state]or empty[state]or (pave[state]and retire[j,i])
                    if not allowed:
                        if Y>=h-1:errors.append(['street obstruction',px,Y,pz,r['names'][state]])
                        continue
                    if Y<h:v[Y+128,j,i]=stone
                    elif Y>h:v[Y+128,j,i]=air
                    else:
                        isroad=bool(d['road'][j0,i0]);ismark=bool(d['marking'][j0,i0])
                        v[Y+128,j,i]=(sslab if ismark else aslab if isroad else pslab)if slab[j,i]else(stripe if ismark else asphalt if isroad else paving)
        e.save();e.regions.clear()
        print('Composed terrain',file.name,'obstructions',len(errors),flush=True)
    save_json(a.out/'composition-obstacles.json',errors)
    # Restore complete translated payloads LAST, preserving interiors including
    # empty room cells. Foundation fill is confined below their copied bases.
    for box,shift,v,names in payloads:
        dx,dy,dz=shift
        for sx in range(box[0],box[3]+1):
            for sz in range(box[2],box[5]+1):
                px,pz=sx+dx,sz+dz
                r=e.region(px,pz);mapped=[]
                for state in names:
                    if state not in r['ids']:r['ids'][state]=len(r['names']);r['names'].append(state)
                    mapped.append(r['ids'][state])
                column=np.asarray(mapped,np.uint16)[v[:,sz-box[2],sx-box[0]]];idx=r['index'][px//16,pz//16];lo=box[1]+dy;hi=box[4]+dy
                dest=r['after'][idx,lo+128:hi+129,pz%16,px%16]
                # Native objects or user content outside the former parcel
                # may not silently disappear beneath a translated building.
                for offset,state in enumerate(dest):
                    mat=r['names'][state].split('[')[0]
                    if mat not in NATURAL|EMPTY|PAVE and not (box[0]<=px<=box[3]and box[1]<=lo+offset<=box[4]and box[2]<=pz<=box[5]):
                        errors.append(['parcel destination obstruction',px,lo+offset,pz,r['names'][state]])
                dest[:]=column
                j,i=pz-z,px-x;h=int(d['ground'][j,i]);oldh=int(d['old_ground'][j,i])
                for Y in range(min(oldh,h),lo):
                    if protected_chunk(px//16,pz//16)[Y+128,pz%16,px%16]:continue
                    mat=e.state(px,Y,pz).split('[')[0]
                    if mat in SOIL|EMPTY:e.put(px,Y,pz,'minecraft:stone')
    # Correct only the OUTDOOR three-wide door aprons: the previous street
    # pass had left several at a different datum from their retained doors.
    outdoor=[]
    for row in rows:
        px,pz,dx,dz=entrance_frame(row);h=row['site']['floor']
        for distance in (1,2,3):
            for side in (-1,0,1):
                Q,R=px+dx*distance-dz*side,pz+dz*distance+dx*side
                for Y in range(h-1,h+4):
                    before=e.state(Q,Y,R);mat=before.split('[')[0];new='minecraft:stone'if Y<h else'minecraft:smooth_stone'if Y==h else'minecraft:air'
                    if before==new:continue
                    if protected_chunk(Q//16,R//16)[Y+128,R%16,Q%16]:
                        if Y<h and mat in SOIL|PAVE and 'type=bottom'not in before and not mat.endswith('_stairs'):continue
                        raise ValueError(('Entrance apron would change retained native volume',row['id'],Q,Y,R,before))
                    if (Q,Y,R)in changes or (Q,Y,R)in devices or mat not in SOIL|EMPTY|PAVE:raise ValueError(('Unowned entrance apron object',row['id'],Q,Y,R,before))
                    outdoor.append(dict(parcel=row['id'],pos=[Q,Y,R],before=before,after=new));e.put(Q,Y,R,new)
    # Small explicitly surveyed outdoor aprons may include an old elevated
    # path inside a parcel's capture collar. Regrade that collar only after
    # restoring the complete payload, never the building's occupied volume.
    for spec in design_spec.get('outdoor_paving_aprons',[]):
        row=next(r for r in rows if r['id']==spec['parcel'])
        ax,az,bx,bz=spec['bounds'];h=int(row['site']['floor'])
        if not(x<=ax<=bx<=X and z<=az<=bz<=Z)or (bx-ax+1)*(bz-az+1)>256:
            raise ValueError(('Exterior apron exceeds finite scope',spec))
        occupied=row['occupied_bounds'];payload=row['new_payload_bounds']
        if row['translation']!=[0,0,0]:raise ValueError('Exterior regrade requires current unmoved parcel')
        if not(payload[0]-3<=ax<=bx<=payload[3]+3 and payload[2]-3<=az<=bz<=payload[5]+3):
            raise ValueError('Exterior apron is not beside its parcel')
        for Q in range(ax,bx+1):
            for R in range(az,bz+1):
                if occupied[0]<=Q<=occupied[3]and occupied[2]<=R<=occupied[5]:
                    raise ValueError(('Exterior apron enters a building',Q,R))
                j,i=R-z,Q-x
                if d['walk'][j,i]and int(d['grade2'][j,i])!=h*2:
                    raise ValueError(('Exterior apron disagrees with designed path',Q,R))
                for Y in range(h-2,h+4):
                    pos=(Q,Y,R);before=e.state(*pos)
                    new='minecraft:stone'if Y<h else'minecraft:smooth_stone'if Y==h else'minecraft:air'
                    if before==new:continue
                    if pos in devices or pos in changes or protected_chunk(Q//16,R//16)[Y+128,R%16,Q%16]:
                        raise ValueError(('Exterior apron meets retained native object',pos))
                    if before.split('[')[0]not in SOIL|EMPTY|PAVE:
                        raise ValueError(('Unowned exterior apron cell',pos,before))
                    record_exception(outdoor,dict(parcel=row['id'],kind='surveyed exterior paving apron',pos=list(pos),before=before,after=new))
                    e.put(*pos,new)
    # Move the original station lamp out of the new sidewalk. It has no block
    # entity; all five original block states are retained at the new position.
    lamp=[]
    if design_spec.get('togendai_forecourt',True):
        lamp_source=[-249,110,997];lamp_target=[-235,0,1004];j,i=lamp_target[2]-z,lamp_target[0]-x;lamp_target[1]=int(d['ground'][j,i])+1
        if d['walk'][j,i]:raise ValueError('Lamp would obstruct commissioned pavement')
        for k in range(5):
            p=(lamp_source[0],lamp_source[1]+k,lamp_source[2]);q=(lamp_target[0],lamp_target[1]+k,lamp_target[2]);state=e.state(*p,original=True)
            if state.split('[')[0]not in {'minecraft:iron_bars','minecraft:lantern'}or e.state(*q).split('[')[0]not in EMPTY:raise ValueError(('Station lamp relocation blocked',p,q))
            lamp.append(dict(before=list(p),after=list(q),state=state));e.put(*p,'minecraft:air');e.put(*q,state)
    save_json(a.out/'outdoor-apron-corrections.json',outdoor);save_json(a.out/'retained-lamp-move.json',lamp)
    patches=e.save();e.regions.clear()
    records=[nbtlib.Compound({'Pos':nbtlib.Long(packed(pos)),**row})for pos,row in sorted(changes.items())]
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](records)}).save(a.out/'block-entities.dat',gzipped=True)
    actualground=ground(Editor(a.out),list(map(int,bounds)))
    np.savez_compressed(a.out/'plan/network.npz',**{**d,'ground':actualground,'tunnel':covered&d['walk']})
    report=dict(errors=errors,world_written=False,visual_verified=False,parcels=len(rows),moved_devices=len(moved),**stats)
    save_json(a.out/'functional-check.json',report)
    manifest=dict(world=str(world),bounds_xz=bounds.tolist(),regions=patches,cells=sum(r['cells']for r in patches),world_written=False,preserve_native_members=True,neighbourhood_verification=dict(public_columns=int(d['walk'].sum()),parcels=len(rows),devices=len(moved)),parcel_moves=[dict(id=r['id'],dy=r['dy'],translation=r.get('translation',[0,r['dy'],0]))for r in rows])
    save_json(a.out/'manifest.json',manifest);save_json(a.out/'launch-protection.json',check_candidate(guard,a.out))
    print(json.dumps({**manifest,'regions':len(patches),'errors':len(errors),'moved_devices':len(moved)},ensure_ascii=False),flush=True)
    if errors:
        print(errors[:20],flush=True)
        raise ValueError('Candidate composition has unresolved obstructions')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','survey','design','base-plan','out'):p.add_argument('--'+name,type=Path,required=True)
    compose(p.parse_args())
