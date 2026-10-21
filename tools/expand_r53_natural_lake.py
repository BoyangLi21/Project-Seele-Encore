"""Enlarge the existing far natural lake from its frozen actual-world survey.

Keep the artificial lake, dome armor, original beehive and declared routes.
Only natural terrain is authored. This is separate from the headquarters lake.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import label, generate_binary_structure, distance_transform_cdt

from query_blocks import iter_block_entities, iter_selected_sections, chunk_statuses
from regional_voxels import natural

DIM = 'projectseele:geofront'
WATER_Y = -473


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def footprint(origin, shape):
    z, x = np.ogrid[origin[2]:origin[2]+shape[1], origin[0]:origin[0]+shape[2]]
    angle = np.arctan2((z - 600) / 950, (x + 1130) / 530)
    r = np.hypot((x + 1130) / 530, (z - 600) / 950)
    r /= 1 + .025*np.sin(3*angle) + .018*np.sin(5*angle + .7)
    # Keep a real land buffer to the authored armored cavern and an intact
    # wooded island around the original occupied hive. No hive NBT is moved.
    r = np.maximum(r, 1 + (np.hypot(x - 30, z - 296) - 1660) / 130)
    r = np.maximum(r, 1 + (44 - np.hypot(x + 833, z - 597)) / 60)
    return r


def verify_envelope(world, origin, expected, names):
    """Compare full measured sections, retaining unknown columns as unknown."""
    hi = (origin[0]+expected.shape[2]-1, origin[1]+expected.shape[0]-1,
          origin[2]+expected.shape[1]-1)
    selected = {(cx,cz):set(range(origin[1]//16,hi[1]//16+1))
                for cx in range(origin[0]//16,hi[0]//16+1)
                for cz in range(origin[2]//16,hi[2]//16+1)}
    statuses = chunk_statuses(world,DIM,selected)
    ids = {n:i for i,n in enumerate(names)}
    valid = {}; seen = set()
    for (cx,cz),ys in selected.items():
        x,z=cx*16,cz*16
        sample=expected[:,max(z,origin[2])-origin[2]:min(z+16,hi[2]+1)-origin[2],
                        max(x,origin[0])-origin[0]:min(x+16,hi[0]+1)-origin[0]]
        if statuses.get((cx,cz)) == 'full':
            assert np.all(sample != ids['UNMEASURED']), ('Newly generated column',cx,cz)
            valid[cx,cz]=ys
        else:
            assert np.all(sample == ids['UNMEASURED']), ('Lost measured column',cx,cz)
    def slices(cx,cz,sy):
        x,y,z=cx*16,sy*16,cz*16
        lo=(max(x,origin[0]),max(y,origin[1]),max(z,origin[2]))
        up=(min(x+16,hi[0]+1),min(y+16,hi[1]+1),min(z+16,hi[2]+1))
        a=tuple(slice(lo[k]-origin[k],up[k]-origin[k]) for k in (1,2,0))
        b=tuple(slice(lo[k]-(x,y,z)[k],up[k]-(x,y,z)[k]) for k in (1,2,0))
        return a,b
    for cx,cz,sy,palette,indices in iter_selected_sections(world,DIM,valid):
        assert all(n in ids for n in palette), ('Changed palette',cx,cz,sy)
        values=np.asarray([ids[n] for n in palette],np.uint16)[indices].reshape(16,16,16)
        a,b=slices(cx,cz,sy)
        assert np.array_equal(expected[a],values[b]), ('Full envelope differs',cx,cz,sy)
        seen.add((cx,cz,sy))
    for (cx,cz),ys in valid.items():
        for sy in ys:
            if (cx,cz,sy) not in seen:
                a,_=slices(cx,cz,sy)
                assert np.all(expected[a] == ids['minecraft:air']), ('Absent nonempty section',cx,cz,sy)
    return len(seen)


def install(world, output):
    import msvcrt
    import shutil
    import nbtlib
    import regional_voxels as vox
    from prepare_terminal_move_r52 import runs
    from apply_s20_approved_semantic_repairs import parse_state, atomic_replace

    assert not (output/'INSTALLED.json').exists(), 'Inspect the existing installation'
    assert not list((output/'natural_lake').glob('applied_*')), 'Inspect partial application before retrying'
    data=np.load(output/'EXACT_BEFORE_AFTER.npz')
    before,after=data['before'],data['after']; names=data['palette'].tolist(); origin=data['origin'].tolist()
    report=json.loads((output/'PLAN.json').read_text('utf8'))
    assert Path(report['world']).resolve()==world.resolve()
    vox.WORLD=world;vox.OUT=output;vox.DIM=DIM
    painter=vox.Painter(vertical_bounds=(-1440,320))
    count=runs(painter,origin,before,after,names,'R53_fivefold_natural_lake')
    assert count==report['changed_cells']
    print('Prepared strict operations',len(painter.ops),'cells',count,flush=True)
    # Persistent geometry maintenance must not reconstruct the former lake.
    directory=world/'dimensions/projectseele/geofront/data'
    headers=list(directory.glob('projectseele_city_rigid_topology_r45_*.dat'))
    assert len(headers)==1
    folder=directory/str(nbtlib.load(headers[0])['data']['GenerationFolder'])/'chunks'
    caches={}; cache_cells=0
    for cx,cz in painter.by_chunk:
        path=folder/f'{cx}_{cz}.dat'
        if not path.exists():continue
        doc=nbtlib.load(path); palette=doc['Palette']; lookup={n.snbt():i for i,n in enumerate(palette)}
        dirty=False
        for entry in doc['Static']:
            v=int(entry['Pos']);x=v>>38;y=v&4095;z=(v>>12)&67108863
            if y>=2048:y-=4096
            if z>=33554432:z-=67108864
            q=(y-origin[1],z-origin[2],x-origin[0])
            if not all(0<=q[i]<before.shape[i] for i in range(3)) or before[q]==after[q]:continue
            assert palette[int(entry['StateId'])]==parse_state(names[int(before[q])]), ('Changed static cache',x,y,z)
            state=parse_state(names[int(after[q])]); key=state.snbt()
            if key not in lookup:lookup[key]=len(palette);palette.append(state)
            entry['StateId']=nbtlib.Int(lookup[key]);cache_cells+=1;dirty=True
        if dirty:caches[path]=doc
    protected={p for p in world.iterdir() if p.is_file() and p.name!='session.lock'}
    for d in (world/'playerdata',world/'entities',world/'data',world/'dimensions/projectseele/geofront/entities'):
        protected.update(p for p in d.rglob('*') if p.is_file())
    protected.update(p for p in directory.iterdir() if p.is_file())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    progress={str(p.relative_to(world)):digest(p) for p in protected}
    (output/'PROGRESS_BEFORE.json').write_text(json.dumps(progress,indent=2),'utf8')
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        verify_envelope(world,origin,before,names)
        original_tags={str(p):t.snbt() for p,t in iter_block_entities(world,DIM,tuple(origin),tuple(report['bounds'][1]))}
        assert original_tags==report['preserved_devices']
        for path in caches:
            backup=output/'cache-before'/path.relative_to(world)
            backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,backup)
        try:
            receipt=painter.apply('natural_lake',session_lock=lock)
            for path,doc in caches.items():
                tmp=path.with_suffix('.lake.tmp');doc.save(tmp,gzipped=True);tmp.replace(path)
                assert nbtlib.load(path)==doc
            sections=verify_envelope(world,origin,after,names)
            tags={str(p):t.snbt() for p,t in iter_block_entities(world,DIM,tuple(origin),tuple(report['bounds'][1]))}
            assert tags==original_tags, 'Full device NBT changed'
            assert progress=={str(p.relative_to(world)):digest(p) for p in protected}, 'Player/task/navigation files changed'
        except BaseException:
            for backup in (output/'natural_lake').glob('applied_*/before/*.mca'):
                atomic_replace(world/'dimensions/projectseele/geofront/region'/backup.name,backup.read_bytes())
            for path in caches:
                atomic_replace(path,(output/'cache-before'/path.relative_to(world)).read_bytes())
            raise
    result=dict(world=str(world),cells=count,exact_full_envelope_readback=True,sections_verified=sections,
                full_device_nbt_unchanged=True,progress_files_unchanged=len(progress),derived_static_cells=cache_cells,
                navigation_unchanged=True,native_visual='pending',lod_refresh='pending',receipt=receipt)
    (output/'INSTALLED.json').write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps(result),flush=True)


def plan(frozen, source, world, output):
    assert not (output/'EXACT_BEFORE_AFTER.npz').exists(), 'Preserve the existing candidate'
    data = np.load(source)
    before = data['states']; names = data['palette'].tolist(); origin = data['origin'].tolist()
    hi = (origin[0]+before.shape[2]-1, origin[1]+before.shape[0]-1, origin[2]+before.shape[1]-1)
    r = footprint(origin, before.shape)
    claimed = r <= 1.12
    assert not any(np.any(v) for v in (claimed[0], claimed[-1], claimed[:,0], claimed[:,-1])), 'Survey margin required'
    for n in ('minecraft:air', 'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block[snowy=false]',
              'minecraft:gravel', 'minecraft:sand', 'minecraft:water[level=0]'):
        if n not in names: names.append(n)
    ids = {n:i for i,n in enumerate(names)}
    blocked = [names[int(i)] for i in np.unique(before[:,claimed]) if not natural(names[int(i)])]
    assert not blocked, ('Preserve authored/unknown terrain', blocked)
    tags = dict(iter_block_entities(frozen, DIM, tuple(origin), hi))
    assert all(not claimed[p[2]-origin[2], p[0]-origin[0]] for p in tags)
    old_water = np.isin(before[WATER_Y-origin[1]], [i for i,n in enumerate(names) if n.startswith('minecraft:water')])
    assert not np.any(old_water & (r >= 1)), 'Preserve the existing lake extent'

    ground_names = {'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block', 'minecraft:gravel',
                    'minecraft:sand', 'minecraft:clay', 'minecraft:coarse_dirt', 'minecraft:tuff', 'minecraft:podzol'}
    ground_ids = [i for i,n in enumerate(names) if n.split('[')[0] in ground_names]
    old_ground = np.full(before.shape[1:], origin[1]-1, dtype=np.int16)
    for iy, layer in enumerate(before): old_ground[np.isin(layer, ground_ids)] = origin[1]+iy
    assert np.all(old_ground[claimed] > origin[1]+4)
    bottom = np.floor(-568 + 95*smooth((r-.18)/.82)).astype(np.int16)
    mix = smooth((r-1)/.12)
    shore = np.floor(-472*(1-mix) + old_ground*mix).astype(np.int16)
    target = np.where(r < 1, bottom, shore)

    # Attribute touching crowns to connected original trunks, as in the prior
    # far-lake repair; never delete an entire forest merely because leaves touch.
    tree_ids = [i for i,n in enumerate(names) if n.split('[')[0].endswith(('_log','_leaves'))]
    trees = np.isin(before, tree_ids)
    occupied = np.flatnonzero(trees.any(axis=(1,2)))
    low, high = int(occupied.min()), int(occupied.max())+1
    logs = np.isin(before[low:high], [i for i,n in enumerate(names) if n.split('[')[0].endswith('_log')])
    trunks, _ = label(logs, generate_binary_structure(3,1))
    nearest = distance_transform_cdt(~logs, return_distances=False, return_indices=True)
    owners = trunks[tuple(nearest)]; owners[~trees[low:high]] = 0
    touched = np.unique(owners[:,claimed]); touched = touched[touched != 0]
    cleared = np.zeros_like(trees)
    cleared[low:high] = np.isin(owners,touched) & trees[low:high]
    margins = dict(zip(('bottom','top','north','south','west','east'),
        (int(v.sum()) for v in (cleared[0],cleared[-1],cleared[:,0],cleared[:,-1],cleared[:,:,0],cleared[:,:,-1]))))
    assert not any(margins.values()), ('Extend frozen tree survey before authoring', margins)
    for x,y,z in tags:
        for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            assert not cleared[y+dy-origin[1],z+dz-origin[2],x+dx-origin[0]], 'Preserve the occupied hive support'
    del trees, logs, trunks, nearest, owners
    after = before.copy(); after[cleared] = ids['minecraft:air']
    for iy,y in enumerate(range(origin[1],origin[1]+before.shape[0])):
        values = np.where(y > target,
            np.where((r<1)&(y<=WATER_Y),ids['minecraft:water[level=0]'],ids['minecraft:air']),
            np.where(y==target,np.where(r<1,ids['minecraft:gravel'],ids['minecraft:grass_block[snowy=false]']),
            np.where(y>=target-3,np.where(r<1,ids['minecraft:sand'],ids['minecraft:dirt']),ids['minecraft:stone'])))
        after[iy,claimed] = values[claimed]
    air = np.array([n in ('minecraft:air','minecraft:cave_air','minecraft:void_air') for n in names])
    for iy,layer in enumerate(after):
        water = (layer == ids['minecraft:water[level=0]']) & claimed
        if not water.any(): continue
        assert iy > 0 and not np.any(water & air[after[iy-1]])
        assert not np.any(water[1:] & air[layer[:-1]]) and not np.any(water[:-1] & air[layer[1:]])
        assert not np.any(water[:,1:] & air[layer[:,:-1]]) and not np.any(water[:,:-1] & air[layer[:,1:]])
    for x,y,z in tags: assert before[y-origin[1],z-origin[2],x-origin[0]] == after[y-origin[1],z-origin[2],x-origin[0]]
    graph = json.loads(gzip.decompress((world/'nerv_routes_r24.json.gz').read_bytes()))
    changed_nav = []
    for node in graph['nodes']:
        x,y,z = node[:3]
        for dy in (-1,0,1):
            q=(y+dy-origin[1],z-origin[2],x-origin[0])
            if all(0<=q[k]<before.shape[k] for k in range(3)) and before[q]!=after[q]:
                changed_nav.append(node[:3]); break
    assert not changed_nav, ('Preserve declared personnel routes', changed_nav[:10])
    output.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(output/'EXACT_BEFORE_AFTER.npz',before=before,after=after,palette=names,origin=origin,owned_columns=claimed)
    report = dict(world=str(world),frozen=str(frozen),bounds=[origin,hi],centre=[-1130,600],
                  nominal_size=[1060,1900],water_y=WATER_Y,old_water_area=int(old_water.sum()),
                  new_water_area=int((r<1).sum()),area_ratio=float((r<1).sum()/old_water.sum()),
                  old_max_depth=75,new_max_depth=95,changed_cells=int(np.count_nonzero(before!=after)),
                  removed_trunks=len(touched),removed_tree_cells=int(cleared.sum()),
                  preserved_devices={str(p):t.snbt() for p,t in tags.items()},
                  basin_watertight=True,declared_navigation_nodes_affected=0,world_written=False)
    (output/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True);p.add_argument('--frozen',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    if a.apply:install(a.world,a.output)
    else:plan(a.frozen,a.source,a.world,a.output)
