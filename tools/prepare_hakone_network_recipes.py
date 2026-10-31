"""Persist final surface authority, keeping current inventories and lift state."""
import argparse,copy,gzip,json,shutil,struct
from pathlib import Path
from collections import defaultdict
import nbtlib
import numpy as np
from author_hakone_lakefront import Editor
from apply_s20_approved_semantic_repairs import parse_state
from repair_hakone_surface_ownership import load_grid,sampled
from query_blocks import iter_block_entities
from prepare_hakone_city_cross import packed
from hakone_earthworks import road_blocks

DATA=Path('dimensions/projectseele/geofront/data')

def run(a):
    e=Editor(a.candidate);check=json.loads((a.candidate/'functional-check.json').read_text('utf8'));errors=list(check['errors'])
    migrations={}
    path=a.candidate/'block-entities.dat'
    if path.exists():
        for row in nbtlib.load(path)['Changes']:
            tag=row.get('Before',row.get('After'));migrations[tuple(int(tag[k])for k in ('x','y','z'))]=row
    root=a.world/DATA/'city_rigid_generation_r45/surface'
    if not a.regions:
        wanted=set()
        for patch in(a.candidate/'delta').glob('*.npz'):
            with np.load(patch)as source:wanted.update(f'{int(x)}_{int(z)}.dat'for x,z in source['coordinates'])
        # A withdrawn edit must also withdraw its prepared future replay.
        # These are derived candidate files only, never current save recipes.
        for side in ('before','after'):
            for prepared in(a.candidate/side/DATA/'city_rigid_generation_r45/surface').glob('*.dat'):
                if prepared.name not in wanted:prepared.unlink()
    example=next(root.glob('*.dat'));identity=nbtlib.load(example)['WorldUUID'];recipes=devices=0;newrecipes=0
    for file in sorted((a.candidate/'delta').glob('*.npz')):
        if a.regions and file.name not in a.regions:continue
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        with np.load(file)as f:coords,ra,at,vs,names=(f[k]for k in('coordinates','ranges','indices','after','palette'))
        chunks={tuple(map(int,q)):i for i,q in enumerate(coords)};tags=defaultdict(dict)
        for pos,tag in iter_block_entities(a.world,'projectseele:geofront',(rx*512,-128,rz*512),(rx*512+511,319,rz*512+511),selected_chunks=set(chunks)):
            tags[pos[0]//16,pos[2]//16][pos]=copy.deepcopy(tag);devices+=1
            i=chunks[pos[0]//16,pos[2]//16];l,h=ra[i:i+2];offset=(pos[1]+128)*256+pos[2]%16*16+pos[0]%16;j=np.searchsorted(at[l:h],offset)
            if j<h-l and at[l+j]==offset and pos not in migrations:errors.append(['unapproved-device-change',*pos])
        for pos,row in migrations.items():
            q=pos[0]//16,pos[2]//16
            if q not in chunks:continue
            if 'Before'in row:
                if tags[q].get(pos)!=row['Before']:errors.append(['moved-device-precondition',*pos])
                tags[q].pop(pos,None)
            if 'After'in row:tags[q][pos]=copy.deepcopy(row['After'])
        for q,i in chunks.items():
            rel=DATA/'city_rigid_generation_r45/surface'/f'{q[0]}_{q[1]}.dat';original=a.world/rel
            exists=original.exists()
            data=nbtlib.load(original)if exists else nbtlib.File({'Version':nbtlib.Int(1),'WorldUUID':copy.deepcopy(identity),'Palette':nbtlib.List[nbtlib.Compound](),'Spans':nbtlib.List[nbtlib.IntArray](),'BlockEntities':nbtlib.List[nbtlib.Compound]()})
            palette=data['Palette'];lookup={str(s['Name'])+str(s.get('Properties',{})):j for j,s in enumerate(palette)}
            codes={}
            def code(name):
                name=str(name)
                if name in codes:return codes[name]
                s=parse_state(name);key=str(s['Name'])+str(s.get('Properties',{}))
                if key not in lookup:lookup[key]=len(palette);palette.append(s)
                codes[name]=lookup[key];return lookup[key]
            l,h=ra[i:i+2];columns=defaultdict(list)
            if exists:
                for offset,value in zip(at[l:h],vs[l:h]):columns[int(offset)%256].append((int(offset)//256-128,code(names[value])))
            else:
                # Complete saved surface, not a sparse change set applied to
                # unrelated future noise. The original underground is excluded.
                v=r['after'][r['index'][q]];x,z=q[0]*16,q[1]*16
                bottoms={}
                for iz in range(16):
                    for ix in range(16):
                        radius=np.hypot(x+ix-30,z+iz-296);t=np.clip((radius-600)/1200,0,1)
                        bottom=int(max(-128,-478+np.floor(502*np.sqrt(max(0,1-t*t)))+18))if radius<1800 else -128
                        bottoms[iz*16+ix]=bottom
                        column=v[bottom+128:,iz,ix];ends=np.r_[0,np.flatnonzero(column[1:]!=column[:-1])+1,len(column)]
                        for lo,hi in zip(ends[:-1],ends[1:]):
                            data['Spans'].append(nbtlib.IntArray([x+ix,z+iz,bottom+int(lo),bottom+int(hi)-1,code(r['names'][column[lo]])]))
                newrecipes+=1
            for col,rows in columns.items():
                rows.sort();lo=hi=rows[0][0];s=rows[0][1]
                for y,value in rows[1:]+[(9999,-1)]:
                    if y==hi+1 and value==s:hi=y;continue
                    data['Spans'].append(nbtlib.IntArray([q[0]*16+col%16,q[1]*16+col//16,lo,hi,s]));lo=hi=y;s=value
            if exists:
                retained=[]
                for cell in data.get('BlockEntities',[]):
                    # Pos follows Minecraft BlockPos packing in existing recipes.
                    if int(cell['Pos'])not in {packed(p)for p in migrations}:retained.append(cell)
                data['BlockEntities']=nbtlib.List[nbtlib.Compound](retained)
                wanted={p:t for p,t in tags[q].items()if p in migrations}
            else:wanted=tags[q]
            for pos,tag in wanted.items():
                if pos[1]<-128:continue
                # Only attach inventories covered by the new complete surface.
                if not exists and pos[1]<bottoms[pos[2]%16*16+pos[0]%16]:continue
                state=e.state(*pos)
                data['BlockEntities'].append(nbtlib.Compound({'Pos':nbtlib.Long(packed(pos)),'StateId':nbtlib.Int(code(state)),'NBT':copy.deepcopy(tag)}))
            prior=a.candidate/'before'/rel;out=a.candidate/'after'/rel;out.parent.mkdir(parents=True,exist_ok=True)
            if exists:prior.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,prior)
            data.save(out,gzipped=True);recipes+=1
        e.regions.clear();print('Prepared current generation recipes',file.name,recipes,flush=True)
    preserve=a.candidate/'preserved';preserve.mkdir(exist_ok=True)
    for f in(a.world/DATA).glob('*control*.dat'):shutil.copy2(f,preserve/f.name)
    check.update(errors=errors)
    if a.regions:check['last_recipe_refresh']=dict(regions=a.regions,recipes=recipes,devices_checked=devices)
    else:
        check.pop('last_recipe_refresh',None)
        check.update(devices_checked=devices,updated_recipes=recipes,new_complete_surface_recipes=newrecipes)
    (a.candidate/'functional-check.json').write_text(json.dumps(check,indent=2),'utf8')
    print('Prepared',recipes,'recipes; devices',devices,'unresolved',len(errors),flush=True)

def field(a):
    d=load_grid(a.plan/'network.npz')
    with gzip.open(a.resource,'rb')as f:
        header=f.read(24);magic,x,z,step,w,h=struct.unpack('>6i',header)
        old=np.frombuffer(f.read(w*h*2),'>i2').reshape(h,w).copy();water=np.frombuffer(f.read(w*h*2),'>i2').reshape(h,w).copy()
    zz,xx=np.meshgrid(np.arange(h)*step+z,np.arange(w)*step+x,indexing='ij');inside=(xx>=d['bounds'][0])&(xx<=d['bounds'][2])&(zz>=d['bounds'][1])&(zz<=d['bounds'][3])
    difference=sampled(d,'ground',xx,zz)-sampled(d,'old_ground',xx,zz)
    # Preserve surveyed lakes/rivers and the already baked external transition.
    use=inside&(difference!=0)&(water==-32768);new=old.copy();new[use]=sampled(d,'ground',xx,zz)[use]*16
    for edge in (difference[0],difference[-1],difference[:,0],difference[:,-1]):
        if np.any(edge):raise ValueError('Network earthworks reach the outer saved-world seam')
    a.out.mkdir(parents=True,exist_ok=True)
    with gzip.open(a.out/'hakone_surface.bin.gz','wb')as f:f.write(header);f.write(new.astype('>i2').tobytes());f.write(water.astype('>i2').tobytes())
    (a.out/'field.json').write_text(json.dumps(dict(changed_pixels=int(use.sum()),water_preserved=True,outer_boundary_preserved=True,source=str(a.resource),plan=str(a.plan)),indent=2),'utf8')
    print('Prepared generation field',int(use.sum()),'pixels',flush=True)


def future(a):
    """Author missing corridor chunks as recipes without inventing FULL chunks."""
    rows=json.loads(a.unfinished.read_text('utf8'));d=load_grid(a.plan/'network.npz')
    root=a.world/DATA/'city_rigid_generation_r45/surface'
    identity=nbtlib.load(next(root.glob('*.dat')))['WorldUUID'];checked=0
    for row in rows:
        if row['status']!='missing':raise ValueError('Future recipe expects genuinely ungenerated chunk')
        cx,cz=row['chunk'];rel=DATA/'city_rigid_generation_r45/surface'/f'{cx}_{cz}.dat'
        if (a.world/rel).exists():raise ValueError('Existing recipe requires explicit merge')
        data=nbtlib.File({'Version':nbtlib.Int(1),'WorldUUID':copy.deepcopy(identity),'Palette':nbtlib.List[nbtlib.Compound](),
            'Spans':nbtlib.List[nbtlib.IntArray](),'BlockEntities':nbtlib.List[nbtlib.Compound]()});codes={}
        def code(name):
            if name not in codes:codes[name]=len(codes);data['Palette'].append(parse_state(name))
            return codes[name]
        def span(x,z,lo,hi,name):
            if lo<=hi:data['Spans'].append(nbtlib.IntArray([x,z,lo,hi,code(name)]))
        for x in range(cx*16,cx*16+16):
            for z in range(cz*16,cz*16+16):
                iz,ix=z-int(d['bounds'][1]),x-int(d['bounds'][0]);ground=int(d['ground'][iz,ix])
                if np.hypot(x-30,z-296)<1800:raise ValueError('Missing corridor unexpectedly enters the retained underground')
                walk=bool(d['walk'][iz,ix]);height,slab=road_blocks(d['grade2'][iz,ix]);height=int(height)
                if walk:
                    road=bool(d['road'][iz,ix]);mark=bool(d['marking'][iz,ix])
                    name=(('projectseele:road_marking_slab'if mark else 'projectseele:road_asphalt_slab'if road else 'minecraft:smooth_stone_slab')+'[type=bottom,waterlogged=false]')if slab else 'minecraft:white_concrete'if mark else 'minecraft:black_concrete'if road else 'minecraft:smooth_stone'
                    span(x,z,-128,height-1,'minecraft:stone');span(x,z,height,height,name);span(x,z,height+1,319,'minecraft:air');checked+=1
                else:
                    span(x,z,-128,ground-4,'minecraft:stone');span(x,z,ground-3,ground-1,'minecraft:dirt');span(x,z,ground,ground,'minecraft:grass_block[snowy=false]');span(x,z,ground+1,319,'minecraft:air')
        out=a.candidate/'after'/rel;out.parent.mkdir(parents=True,exist_ok=True);data.save(out,gzipped=True)
        saved=nbtlib.load(out)
        if len(saved['Spans'])!=len(data['Spans']):raise ValueError('Incomplete future surface recipe')
    check=json.loads((a.candidate/'functional-check.json').read_text('utf8'))
    if checked!=check['not_yet_full_road_columns']:raise ValueError(('Missing future street coverage',checked,check['not_yet_full_road_columns']))
    check.update(future_road_columns=checked,future_missing_chunk_recipes=len(rows))
    (a.candidate/'functional-check.json').write_text(json.dumps(check,indent=2),'utf8')
    print('Future street coverage',checked,'columns in',len(rows),'ungenerated chunks; generation status untouched',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--phase',choices=('recipes','field','future'),required=True)
    for n in('candidate','world','plan','resource','out','unfinished'):p.add_argument('--'+n,type=Path)
    p.add_argument('--regions',nargs='*')
    a=p.parse_args();{'recipes':run,'field':field,'future':future}[a.phase](a)
