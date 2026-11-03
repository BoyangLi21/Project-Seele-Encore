"""Stage actual changed surface pixels and all Xaero zoom levels, offline.

Keep native map colours learned from matching current block/height samples.
Keep every unchanged pixel and opaque native metadata. This does not delete
maps, waypoints or exploration, and never writes the live client's cache.
"""
import argparse,collections,json,shutil,struct
from pathlib import Path
import numpy as np
from PIL import Image
from author_hakone_lakefront import Editor
from query_blocks import AIR
from xaero_cache_codec import Cache,unpack_heights

INVISIBLE=AIR|{'minecraft:barrier','minecraft:structure_void','minecraft:light'}

def prepare(a):
    a.out.mkdir(parents=True,exist_ok=False)
    records={};tile_refs={};colours=collections.defaultdict(list);updates={};missing=[];visible_changes=0
    def cache(level,rx,rz):
        key=level,rx,rz
        if key not in records:
            rel=Path('cache_1'if level==0 else f'cache/{level}')/f'{rx}_{rz}.xwmc';file=a.cache/rel
            if not file.exists():return None
            records[key]=dict(cache=Cache.open(file,leaf=level==0),rel=rel,file=file)
        return records[key]
    def tile(level,tx,tz):
        key=level,tx,tz
        if key not in tile_refs:
            rec=cache(level,tx//8,tz//8);k=(tx%8)*16+tz%8
            if rec is None or k not in rec['cache'].tiles:return None
            t=rec['cache'].tiles[k]
            tile_refs[key]=dict(tile=t,rec=rec,rgba=np.array(t.image()),height=unpack_heights(t.heights),top=unpack_heights(t.top_heights),version=rec['cache'].versions[k])
        return tile_refs[key]
    changes={}
    for folder in a.candidate:
        report=json.loads((folder/'functional-check.json').read_text('utf8'))
        if report['errors']:raise ValueError('Unverified surface candidate')
        e=Editor(folder)
        for f in (folder/'delta').glob('*.npz'):
            rx,rz=map(int,f.stem.split('.')[1:]);r=e.region(rx*512,rz*512);names=r['names'];bases=[s.split('[')[0]for s in names];visible=np.array([s not in INVISIBLE for s in bases])
            for (cx,cz),before,after in zip(r['coords'],r['before'],r['after']):
                cx,cz=int(cx),int(cz);h0=np.where(visible[before],np.arange(448)[:,None,None],0).max(0);h1=np.where(visible[after],np.arange(448)[:,None,None],0).max(0)
                s0=np.take_along_axis(before,h0[None],0)[0];s1=np.take_along_axis(after,h1[None],0)[0]
                t=tile(0,cx//4,cz//4)
                if t is None:
                    if ((h0!=h1)|(s0!=s1)).any():missing.append([cx,cz])
                    continue
                iz,ix=(cz%4)*16,(cx%4)*16;area=np.s_[iz:iz+16,ix:ix+16];rgba=t['rgba'][area];native_h=t['height'][area]
                matches=abs(native_h-(h0-128))<=1
                for state in np.unique(s0[matches]):
                    name=bases[state];samples=rgba[:,:,:3][matches&(s0==state)]
                    if samples.size:colours[name].extend(samples[::max(1,len(samples)//30)].tolist())
                for dz,dx in zip(*np.nonzero((h0!=h1)|(s0!=s1))):
                    pos=(cx*16+int(dx),cz*16+int(dz));value=(int(h1[dz,dx])-128,bases[s1[dz,dx]])
                    if pos in changes and changes[pos]!=value:raise ValueError(('Conflicting candidate map pixels',pos))
                    changes[pos]=value
            e.regions.clear()
    if missing:raise ValueError(('Changed chunks need a complete native base map',missing[:12]))
    palette={k:np.rint(np.median(v,axis=0)).astype(np.uint8).tolist()for k,v in colours.items()if v}
    # New stone half-slabs use the sampled colour of the matching stone.
    aliases={'minecraft:stone_brick_slab':'minecraft:stone_bricks','minecraft:gray_concrete':'minecraft:light_gray_concrete','minecraft:dirt':'minecraft:grass_block'}
    unresolved=sorted({state for _,state in changes.values()}-palette.keys())
    for name in unresolved:
        alias=aliases.get(name)
        if alias in palette:palette[name]=palette[alias]
    unresolved=sorted({state for _,state in changes.values()}-palette.keys())
    if unresolved:raise ValueError(('No measured native map colour',unresolved))
    changed_tiles=set()
    for (px,pz),(height,name)in changes.items():
        key=0,px//64,pz//64;t=tile(*key);dz,dx=pz%64,px%64;t['rgba'][dz,dx,:3]=palette[name];t['rgba'][dz,dx,3]=0;t['height'][dz,dx]=height;t['top'][dz,dx]=height;changed_tiles.add(key)
    leaf_count=len(changed_tiles)
    levels=sorted(int(p.name)for p in (a.cache/'cache').iterdir()if p.is_dir()and p.name.isdigit())
    for level in levels:
        if level<1:continue
        parents={(level,tx//2,tz//2)for l,tx,tz in changed_tiles if l==level-1}
        for key in parents:
            _,tx,tz=key;p=tile(*key)
            if p is None:raise ValueError(('Missing native overview tile',key))
            versions=[]
            for dz in range(2):
                for dx in range(2):
                    ck=(level-1,tx*2+dx,tz*2+dz);child=tile(*ck)
                    if child is None:versions.append(-1);continue
                    versions.append(child['version']+(1 if ck in changed_tiles else 0))
                    if ck not in changed_tiles:continue
                    area=np.s_[dz*32:dz*32+32,dx*32:dx*32+32]
                    # Average the four native channels separately: the fourth
                    # is light, so RGBA premultiplied-alpha resizing is wrong.
                    p['rgba'][area]=np.rint(child['rgba'].reshape(32,2,32,2,4).mean((1,3))).astype(np.uint8)
                    for name in ('height','top'):p[name][area]=child[name].reshape(32,2,32,2).max((1,3))
            p['children']=struct.pack('>4i',*versions)
            changed_tiles.add(key)
    for key in changed_tiles:
        t=tile_refs[key];raw=t['tile'].replaced(Image.fromarray(t['rgba'],'RGBA'),t['height'],t['top'])
        if 'children'in t:raw=raw[:-16]+t['children']
        updates.setdefault(t['rec']['rel'],{})[t['tile'].key]=raw
    files=[]
    for rec in records.values():
        rel=rec['rel']
        if rel not in updates:continue
        before=a.out/'before'/rel;after=a.out/'after'/rel;before.parent.mkdir(parents=True,exist_ok=True);after.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(rec['file'],before);rec['cache'].write(after,updates[rel])
        # Read every updated height and pixel back through the native layout.
        checked=Cache.open(after,leaf=rec['cache'].leaf)
        for k in updates[rel]:
            ref=next(t for t in tile_refs.values()if t['rec']is rec and t['tile'].key==k)
            assert np.array_equal(np.asarray(checked.tiles[k].image()),ref['rgba'])
            assert np.array_equal(unpack_heights(checked.tiles[k].heights),ref['height'])
        files.append(rel.as_posix())
    result=dict(cache_root=str(a.cache),candidates=[str(c)for c in a.candidate],files=files,pixels=len(changes),leaf_tiles=leaf_count,all_zoom_tiles=len(changed_tiles),levels=levels,native_palette=palette,errors=[],live_cache_written=False)
    (a.out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in result.items()if k not in ('native_palette','files')}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('cache','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--candidate',type=Path,action='append',required=True)
    prepare(p.parse_args())
