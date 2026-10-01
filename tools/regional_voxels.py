"""Measured region patch engine for the explicitly authorized regional build.

Shape authoring is independent of Anvil IO. The only block reader is
query_blocks; the existing palette writer is reused with per-region backups,
compressed before/after arrays, precondition checks and exact readback.
"""
from collections import defaultdict,Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import gzip,json,shutil,msvcrt,time,copy
import nbtlib
import numpy as np
from query_blocks import iter_selected_sections,iter_block_entities,dimension_dir,AIR
from transplant_s22_authority import read_region,parse_chunk,build_region,decoded_sections,flush_decoded,chunk_blob
from apply_s20_approved_semantic_repairs import parse_state,atomic_replace

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_TV_WORLD_PREVIEW_20260906'
OUT=ROOT/'artifacts/world_expansion_20260907'
DIM='projectseele:geofront'
NATURAL={'stone','dirt','grass_block','gravel','sand','sandstone','bedrock','clay','coarse_dirt','rooted_dirt','podzol','mud','water'}

def canonical_state(state):
    """Use the same sorted property representation as query_blocks readback."""
    if '[' not in state:return state
    name,properties=state.split('[',1)
    return name+'['+','.join(sorted(properties[:-1].split(',')))+']'


def natural(state):
    name=state.split('[')[0]
    plants={'short_grass','grass','tall_grass','fern','large_fern','dead_bush','seagrass','tall_seagrass','kelp','kelp_plant',
            'dandelion','poppy','blue_orchid','allium','azure_bluet','oxeye_daisy','cornflower','lily_of_the_valley','sunflower','lilac','rose_bush','peony','snow','snow_block'}
    return name in AIR or name=='minecraft:light' or name.startswith('minecraft:') and (name[10:] in NATURAL|plants
        or name.endswith(('_log','_leaves','_sapling','_tulip')))


@dataclass(frozen=True)
class Op:
    box:tuple
    state:str
    owner:str
    mode:str='new'
    extra:tuple=()


class Painter:
    def __init__(self):
        self.ops=[];self.by_chunk=defaultdict(list);self.block_entities={};self.keep_boxes=[];self.entity_updates={}
        self.meta={'rooms':[],'landmarks':[],'doors':[],'walk_nodes':[]}
    def fill(self,x0,y0,z0,x1,y1,z1,state,owner,mode='new'):
        state=canonical_state(state)
        x0,x1=sorted((int(x0),int(x1)));y0,y1=sorted((int(y0),int(y1)));z0,z1=sorted((int(z0),int(z1)))
        if y0<-672 or y1>=320:raise ValueError((owner,y0,y1))
        op=Op((x0,y0,z0,x1,y1,z1),state,owner,mode);i=len(self.ops);self.ops.append(op)
        for cx in range(x0//16,x1//16+1):
            for cz in range(z0//16,z1//16+1):self.by_chunk[cx,cz].append(i)
    def put(self,x,y,z,state,owner,mode='new'):self.fill(x,y,z,x,y,z,state,owner,mode)
    def protect(self,box,owner,modes=()):
        self.keep_boxes.append(dict(box=tuple(box),owner=owner,modes=tuple(modes)))
    def match(self,box,before,after,owner):
        self.fill(*box,after,owner,'match')
        self.ops[-1]=Op(self.ops[-1].box,canonical_state(after),owner,'match',(canonical_state(before),))
    def update_block_entity(self,pos,state,before,after,owner):
        """Explicit NBT-only edit with measured state/tag preconditions and inverse."""
        pos=tuple(map(int,pos));self.match((*pos,*pos),state,state,owner)
        self.block_entities[pos]=copy.deepcopy(after)
        self.entity_updates[pos]=(canonical_state(state),copy.deepcopy(before),copy.deepcopy(after),owner)
    def heightfield(self,cx,cz,heights,active,owner,clear_vegetation=None):
        if clear_vegetation is None:clear_vegetation=np.ones((16,16),dtype=bool)
        op=Op((cx*16,32,cz*16,cx*16+15,255,cz*16+15),'minecraft:grass_block[snowy=false]',owner,'heightfield',
              (np.asarray(heights,dtype=int).tolist(),np.asarray(active,dtype=bool).tolist(),np.asarray(clear_vegetation,dtype=bool).tolist()))
        self.by_chunk[cx,cz].append(len(self.ops));self.ops.append(op)
    def grade(self,x0,z0,x1,z1,floor,owner,margin=12):
        op=Op((x0-margin,-32,z0-margin,x1+margin,255,z1+margin),'minecraft:stone',owner,'grade',(x0,z0,x1,z1,floor,margin))
        i=len(self.ops);self.ops.append(op)
        for cx in range((x0-margin)//16,(x1+margin)//16+1):
            for cz in range((z0-margin)//16,(z1+margin)//16+1):self.by_chunk[cx,cz].append(i)
    def sign(self,x,y,z,lines,owner,facing='north'):
        self.put(x,y,z,f'minecraft:oak_wall_sign[facing={facing},waterlogged=false]',owner)
        front=nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':str(t)},ensure_ascii=False)) for t in (list(lines)+['']*4)[:4]]),
            'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
        self.block_entities[x,y,z]=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(x),'y':nbtlib.Int(y),'z':nbtlib.Int(z),
            'front_text':front,'back_text':nbtlib.Compound(front),'is_waxed':nbtlib.Byte(1)})
    def chest(self,x,y,z,items,owner,facing='north'):
        self.put(x,y,z,f'minecraft:chest[facing={facing},type=single,waterlogged=false]',owner)
        entries=[]
        for slot,(item,count) in enumerate(items[:27]):
            entries.append(nbtlib.Compound({'Slot':nbtlib.Byte(slot),'id':nbtlib.String(item),'Count':nbtlib.Byte(count)}))
        self.block_entities[x,y,z]=nbtlib.Compound({'id':nbtlib.String('minecraft:chest'),'x':nbtlib.Int(x),'y':nbtlib.Int(y),'z':nbtlib.Int(z),'Items':nbtlib.List[nbtlib.Compound](entries)})
    def bed(self,x,y,z,owner,color='white'):
        for zz,part in [(z,'foot'),(z-1,'head')]:
            self.put(x,y,zz,f'minecraft:{color}_bed[facing=north,occupied=false,part={part}]',owner)
            self.block_entities[x,y,zz]=nbtlib.Compound({'id':nbtlib.String('minecraft:bed'),'x':nbtlib.Int(x),'y':nbtlib.Int(y),'z':nbtlib.Int(zz)})
    def save_plan(self,name):
        folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
        with gzip.open(folder/'ops.json.gz','wt',encoding='utf-8') as f:json.dump([o.__dict__ for o in self.ops],f,ensure_ascii=False)
        (folder/'places.json').write_text(json.dumps(self.meta,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'chunks.json').write_text(json.dumps(sorted(self.by_chunk)),encoding='utf-8')
        (folder/'states.json').write_text(json.dumps(sorted({o.state for o in self.ops})),encoding='utf-8')
        (folder/'protected.json').write_text(json.dumps(self.keep_boxes,ensure_ascii=False),encoding='utf-8')
        (folder/'block_entities.json').write_text(json.dumps([{'pos':p,'snbt':v.snbt()} for p,v in self.block_entities.items()],ensure_ascii=False),encoding='utf-8')
        print(name,'operations',len(self.ops),'chunks',len(self.by_chunk),'block entities',len(self.block_entities),flush=True)
        return folder
    def apply(self,name,session_lock=None):
        folder=self.save_plan(name)
        own_lock=session_lock is None
        lock=(WORLD/'session.lock').open('r+b') if own_lock else session_lock
        if own_lock:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:assert not lock.closed and Path(lock.name).resolve()==(WORLD/'session.lock').resolve(),'Wrong externally held world lock'
        report_dir=folder/('applied_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));(report_dir/'before').mkdir(parents=True);(report_dir/'delta').mkdir()
        groups=defaultdict(dict)
        for (cx,cz),ops in self.by_chunk.items():groups[cx//32,cz//32][cx,cz]=ops
        additions_by_chunk=defaultdict(set)
        protected_by_chunk=defaultdict(list)
        for protection in self.keep_boxes:
            x0,y0,z0,x1,y1,z1=protection['box']
            # Only edited chunks can consume a protection mask. A broad
            # keep-out box must not allocate an entry for every world chunk.
            for cx,cz in self.by_chunk:
                if x0//16<=cx<=x1//16 and z0//16<=cz<=z1//16:
                    protected_by_chunk[cx,cz].append(protection)
        for p in self.block_entities:additions_by_chunk[p[0]//16,p[2]//16].add(p)
        touched=[];counts=Counter();protected=Counter();start=time.monotonic();entity_deltas=[]
        try:
            from information_fixture_guard_r44 import retained_faces,check_retained_faces
            information_faces=retained_faces(self,WORLD,DIM)
            for number,((rx,rz),chunks_ops) in enumerate(sorted(groups.items())):
                selected={p:{sy for i in ops for sy in range(self.ops[i].box[1]//16,self.ops[i].box[4]//16+1)} for p,ops in chunks_ops.items()}
                measured={(cx,cz,sy):(pal,idx) for cx,cz,sy,pal,idx in iter_selected_sections(WORLD,DIM,selected)}
                missing=[(cx,cz,sy) for (cx,cz),ys in selected.items() for sy in ys if (cx,cz,sy) not in measured]
                if missing:raise RuntimeError(f'Unmeasured sections: {missing[:5]}')
                path=dimension_dir(WORLD,DIM)/f'region/r.{rx}.{rz}.mca';backup=report_dir/'before'/path.name;shutil.copy2(path,backup)
                stamps,blobs=read_region(path);dirty=False;expected_entities={}
                for (cx,cz),op_indices in chunks_ops.items():
                    slot=(cx&31)+(cz&31)*32;root=parse_chunk(blobs[slot]);decoded=decoded_sections(root)
                    minimum=min(selected[cx,cz]);maximum=max(selected[cx,cz]);palettes=[];lookup={}
                    def code(state):
                        if state not in lookup:lookup[state]=len(palettes);palettes.append(state)
                        return lookup[state]
                    before=np.full(((maximum-minimum+1)*16,16,16),65535,dtype=np.uint16)
                    for sy in selected[cx,cz]:
                        pal,idx=measured[cx,cz,sy];mapping=np.asarray([code(s) for s in pal],dtype=np.uint16)
                        before[(sy-minimum)*16:(sy-minimum+1)*16]=mapping[idx].reshape(16,16,16)
                    after=before.copy();entity_positions={tuple(int(t[k]) for k in ('x','y','z')) for t in root.get('block_entities',[])}
                    protection_cache={}
                    def protected_cells(mode):
                        if mode not in protection_cache:
                            held=np.zeros(before.shape,dtype=bool)
                            for protection in protected_by_chunk[cx,cz]:
                                if protection['modes'] and mode not in protection['modes']:continue
                                x0,y0,z0,x1,y1,z1=protection['box']
                                y0=max(y0,minimum*16);y1=min(y1,(maximum+1)*16-1)
                                if y0>y1:continue
                                held[y0-minimum*16:y1-minimum*16+1,max(z0-cz*16,0):min(z1-cz*16+1,16),max(x0-cx*16,0):min(x1-cx*16+1,16)]=True
                            protection_cache[mode]=held
                        return protection_cache[mode]
                    for i in op_indices:
                        op=self.ops[i];x0,y0,z0,x1,y1,z1=op.box
                        ax=max(x0,cx*16)-cx*16;bx=min(x1,cx*16+15)-cx*16+1
                        az=max(z0,cz*16)-cz*16;bz=min(z1,cz*16+15)-cz*16+1
                        ay=y0-minimum*16;by=y1-minimum*16+1
                        target=code(op.state);src=before[ay:by,az:bz,ax:bx];view=after[ay:by,az:bz,ax:bx]
                        if np.any(src==65535):raise RuntimeError(f'Unknown voxel in {op.owner}')
                        if op.mode=='heightfield':
                            heights=np.asarray(op.extra[0],dtype=int);active=np.asarray(op.extra[1],dtype=bool)[None,:,:]
                            yy=np.arange(y0,y1+1)[:,None,None];target_heights=heights[None,:,:]
                            stone=code('minecraft:stone');soil=code('minecraft:dirt');grass=code('minecraft:grass_block[snowy=false]');air=code('minecraft:air')
                            allowed=np.asarray([natural(s) for s in palettes],dtype=bool)
                            # Earlier retirement operations are part of this staged surface pass.
                            editable=allowed[view] & active & ~protected_cells(op.mode)[ay:by,az:bz,ax:bx]
                            vegetation=np.asarray([s.split('[')[0].endswith(('_log','_leaves')) for s in palettes],dtype=bool)[view]
                            editable &= ~((yy>target_heights)&vegetation&~np.asarray(op.extra[2],dtype=bool)[None,:,:])
                            values=np.where(yy>target_heights,air,np.where(yy==target_heights,grass,np.where(yy>=target_heights-3,soil,stone)))
                            view[editable]=np.broadcast_to(values,view.shape)[editable]
                            continue
                        if op.mode=='grade':
                            import math
                            gx0,gz0,gx1,gz1,desired,margin=op.extra
                            natural_mask=np.asarray([natural(s) for s in palettes],dtype=bool)
                            ground_mask=np.asarray([s.split('[')[0].removeprefix('minecraft:') in NATURAL-{'water'} for s in palettes],dtype=bool)
                            soil=code('minecraft:dirt');grass=code('minecraft:grass_block[snowy=false]');stone=code('minecraft:stone');air=code('minecraft:air')
                            for zz in range(az,bz):
                                for xx in range(ax,bx):
                                    original=before[ay:by,zz,xx];ys=np.flatnonzero(ground_mask[original])
                                    if not len(ys):raise RuntimeError(f'No measured ground for {op.owner} at {cx*16+xx,cz*16+zz}')
                                    old_y=y0+int(ys[-1]);x=cx*16+xx;z=cz*16+zz
                                    distance=math.hypot(max(gx0-x,0,x-gx1),max(gz0-z,0,z-gz1))
                                    if distance>=margin:continue
                                    mix=min(1,distance/max(1,margin));mix=mix*mix*(3-2*mix)
                                    new_y=round(desired*(1-mix)+old_y*mix)
                                    authored=~natural_mask[original]
                                    if np.any(authored[max(0,old_y-y0-3):]):
                                        protected[op.owner]+=1;continue
                                    column=after[:,zz,xx]
                                    for yy in range(max(y0,min(old_y,new_y)-3),256):
                                        iy=yy-minimum*16
                                        if yy<=new_y:column[iy]=grass if yy==new_y else soil if yy>=new_y-3 else stone
                                        else:column[iy]=air
                            continue
                        if op.mode in ('owned','retire'):mask=np.ones(src.shape,dtype=bool)
                        elif op.mode=='ground_clear':mask=np.asarray([s.split('[')[0].removeprefix('minecraft:') in NATURAL-{'water'} for s in palettes],dtype=bool)[src]
                        elif op.mode=='match':
                            mask=np.asarray([s==op.extra[0] for s in palettes],dtype=bool)[src]
                            # A measured single-cell delta is an assertion,
                            # not a bulk palette filter. Previously a stale
                            # state silently disappeared from the applied
                            # subset and still received a verified receipt.
                            # Legacy multi-cell palette selections keep their
                            # filtering semantics; exact candidates fail and
                            # roll back instead of quietly losing a member.
                            if op.box[:3]==op.box[3:] and not bool(mask.all()):
                                actual=palettes[int(src.reshape(-1)[0])]
                                raise RuntimeError(f'Exact cell precondition changed: {op.box[:3]} expected {op.extra[0]}, actual {actual}, owner {op.owner}')
                        else:
                            allowed=np.asarray([natural(s) or s==op.state for s in palettes],dtype=bool)
                            if op.mode=='air':allowed=np.asarray([s.split('[')[0] in AIR or s.startswith('minecraft:light[') or s==op.state for s in palettes],dtype=bool)
                            mask=allowed[src]
                            protected[op.owner]+=int((~mask & (view!=target)).sum())
                        mask &= ~protected_cells(op.mode)[ay:by,az:bz,ax:bx]
                        view[mask]=target
                    check_retained_faces(information_faces,(cx,cz),before,after,palettes,minimum)
                    diff=(before!=after)&(before!=65535)
                    old_entities={tuple(int(t[k]) for k in ('x','y','z')):t for t in root.get('block_entities',[])}
                    nbt_changes=set()
                    for pos,(expected_state,expected_tag,new_tag,owner) in self.entity_updates.items():
                        if (pos[0]//16,pos[2]//16)!=(cx,cz):continue
                        yy,zz,xx=pos[1]-minimum*16,pos[2]&15,pos[0]&15
                        if protected_cells('match')[yy,zz,xx]:raise RuntimeError(f'Protected NBT update: {pos} {owner}')
                        if palettes[int(before[yy,zz,xx])]!=expected_state or palettes[int(after[yy,zz,xx])]!=expected_state:
                            raise RuntimeError(f'NBT block-state precondition changed: {pos}')
                        original=old_entities.get(pos)
                        actual=None if original is None else original.snbt()
                        expected=None if expected_tag is None else expected_tag.snbt()
                        if actual!=expected:raise RuntimeError(f'NBT precondition changed: {pos}')
                        if actual!=new_tag.snbt():
                            nbt_changes.add(pos);entity_deltas.append(dict(position=pos,owner=owner,state=expected_state,before=actual,after=new_tag.snbt()))
                    if not diff.any() and not nbt_changes:continue
                    offsets=np.flatnonzero(diff).astype(np.uint32);old_values=before.reshape(-1)[offsets];new_values=after.reshape(-1)[offsets]
                    np.savez_compressed(report_dir/'delta'/f'c.{cx}.{cz}.npz',minimum=np.int32(minimum*16),offsets=offsets,palette=np.asarray(palettes),before=old_values,after=new_values)
                    changed_positions=set(nbt_changes)
                    for sy in selected[cx,cz]:
                        block_slice=slice((sy-minimum)*16,(sy-minimum+1)*16);mask=diff[block_slice].reshape(-1)
                        if not mask.any():continue
                        item=decoded.get(sy)
                        if item is None:raise RuntimeError(f'Writer section absent {cx,cz,sy}')
                        writer_palette,writer_indices,writer_lookup=item
                        # Check the writer against the independent measured reader before changing indices.
                        current_names=[str(t['Name'])+('['+','.join(f'{k}={v}' for k,v in sorted(t.get('Properties',{}).items()))+']' if t.get('Properties') else '') for t in writer_palette]
                        old_pal,old_idx=measured[cx,cz,sy]
                        if not np.array_equal(np.asarray(current_names)[writer_indices[mask]],np.asarray(old_pal)[old_idx[mask]]):
                            raise RuntimeError(f'Changed precondition {cx,cz,sy}')
                        mapping={s:n for n,s in enumerate(current_names)}
                        values=after[block_slice].reshape(-1)
                        for value in np.unique(values[mask]):
                            state=palettes[int(value)]
                            if state not in mapping:
                                mapping[state]=len(writer_palette);writer_palette.append(parse_state(state));writer_lookup[state]=mapping[state]
                            writer_indices[mask & (values==value)]=mapping[state]
                        for p in entity_positions|additions_by_chunk[cx,cz]:
                            if p[1]//16==sy and mask[((p[1]&15)<<8)|((p[2]&15)<<4)|(p[0]&15)]:changed_positions.add(p)
                    existing=[t for t in root.get('block_entities',[]) if tuple(int(t[k]) for k in ('x','y','z')) not in changed_positions]
                    existing += [self.block_entities[p] for p in changed_positions if p in self.block_entities]
                    root['block_entities']=nbtlib.List[nbtlib.Compound](existing)
                    # New/retired doors, signs, beds and inventories need the
                    # same complete NBT readback as state-preserving updates.
                    # The old witness checked only self.entity_updates.
                    for p in changed_positions:
                        expected_entities[p]=self.block_entities.get(p)
                    if diff.any():
                        flush_decoded(root,decoded);root['isLightOn']=nbtlib.Byte(0);root.pop('Heightmaps',None)
                        for section in root.get('sections',[]):section.pop('BlockLight',None);section.pop('SkyLight',None)
                    blobs[slot]=chunk_blob(root);dirty=True;counts['cells']+=len(offsets);counts['chunks']+=1;counts['block_entities']+=len(nbt_changes)
                if dirty:
                    atomic_replace(path,build_region(stamps,blobs));touched.append((path,backup))
                    for cx,cz,sy,pal,idx in iter_selected_sections(WORLD,DIM,selected):
                        payload=report_dir/'delta'/f'c.{cx}.{cz}.npz'
                        if not payload.exists():continue
                        with np.load(payload) as d:
                            low=int(d['minimum']);offsets=d['offsets'];ys=offsets.astype(np.int64)//256+low;keep=(ys//16)==sy
                            if keep.any():
                                expected=d['palette'][d['after'][keep]];actual=np.asarray(pal)[idx[(offsets[keep]%4096).astype(int)]]
                                if not np.array_equal(actual,expected):raise RuntimeError(f'Readback mismatch {cx,cz,sy}')
                    if expected_entities:
                        lo=tuple(min(p[i] for p in expected_entities) for i in range(3));hi=tuple(max(p[i] for p in expected_entities) for i in range(3))
                        current=dict(iter_block_entities(WORLD,DIM,lo,hi,selected_chunks=set(chunks_ops)))
                        for p,expected in expected_entities.items():
                            actual=current.get(p)
                            if (None if actual is None else actual.snbt())!=(None if expected is None else expected.snbt()):
                                raise RuntimeError(f'Full created/retired/updated NBT readback mismatch: {p}')
                        counts['block_entity_records_verified']+=len(expected_entities)
                print(f'{name}: regions {number+1}/{len(groups)}, cells {counts["cells"]}, {time.monotonic()-start:.1f}s',flush=True)
        except Exception:
            for path,backup in touched:atomic_replace(path,backup.read_bytes())
            raise
        finally:
            if own_lock:lock.close()
        (report_dir/'block_entity_deltas.json').write_text(json.dumps(entity_deltas,ensure_ascii=False,indent=2),encoding='utf8')
        receipt=dict(world=str(WORLD),dimension=DIM,counts=counts,kept_existing_cells=dict(protected),verified=True,elapsed=round(time.monotonic()-start,2))
        (report_dir/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        print('VERIFIED',report_dir,flush=True)
        return receipt
