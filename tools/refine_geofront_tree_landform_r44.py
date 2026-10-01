"""Remove the terrain crater caused by treating one native tree as infrastructure.

Measures and relocates the complete natural oak component, retaining every
block state and an exact inverse. No world writes. Infrastructure stays fixed.
"""
from pathlib import Path
from collections import deque
import argparse,gzip,json,hashlib
import numpy as np
from scipy.ndimage import distance_transform_edt
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
BASE=ROOT/'artifacts/rebuild_r44/city_expansion/tv_geofront_continuous_range_v1'
PLANTS={'minecraft:'+n for n in ['grass','tall_grass','fern','large_fern','poppy','dandelion','cornflower','snow']}


def smooth(t):
    t=np.clip(t,0,1);return t*t*(3-2*t)


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    d=np.load(BASE/'whole_heightfield.npz');ox,oz=map(int,d['origin']);before=d['before'].copy();shape=before.shape
    w=MeasuredWorld(WORLD);w.box((ox,-530,oz),(ox+shape[1]-1,-350,oz+shape[0]-1));w.load()
    soil_recovered=[]
    for zz,xx in zip(*np.where(before<=-32768)):
        x,z=int(xx+ox),int(zz+oz)
        bearing=[y for y in range(-530,-350) if (w.block((x,y,z)) or '').split('[')[0] in {'minecraft:grass_block','minecraft:dirt','minecraft:stone','minecraft:coarse_dirt','minecraft:rooted_dirt'}]
        assert bearing,('Missing actual soil must not become a terrain mask',x,z)
        before[zz,xx]=max(bearing);soil_recovered.append(dict(pos=[x,z],bearing=max(bearing)))
    X,Z=np.meshgrid(np.arange(shape[1])+ox,np.arange(shape[0])+oz);edge=np.minimum.reduce([X-ox,ox+shape[1]-1-X,Z-oz,oz+shape[0]-1-Z]);t=(X-ox)/(shape[1]-1)
    radial=np.hypot(X-30,Z-296);fixed=d['foreign']|d['protection']|(radial<650)|(before<=-32768)
    # A natural tree belongs to decoration after the landform, not the
    # immovable-infrastructure distance field. Preserve true fixed masks.
    distance=distance_transform_edt(~fixed)
    north=630+.42*(X-ox)+18*np.sin((X-ox)/90);south=850+.10*(X-ox)+12*np.sin((X+35)/75)
    rise=np.maximum((24+44*t)*np.exp(-((Z-north)/82)**2),(18+32*t)*np.exp(-((Z-south)/70)**2))*smooth(edge/100)*smooth((distance-16)/40)
    proposed=np.minimum(before+np.rint(rise).astype(np.int16),d['ceilings'].astype(np.int16)-24)
    old=np.where(d['eligible'],d['after'],before);target=np.maximum(old,proposed);changed=(target!=old)&(~fixed)
    for z in range(oz,oz+shape[0]):
        for x in range(ox,ox+shape[1]):assert w.status[(x//16,z//16)]=='full'
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(ox,-530,oz),(ox+shape[1]-1,-350,oz+shape[0]-1),selected_chunks=set(w.selected)))
    trees={}
    for zz,xx in zip(*np.where(d['wood'])):
        x,z=int(xx+ox),int(zz+oz)
        for y in range(-530,-350):
            q=(x,y,z);s=w.block(q)
            if s and s.split('[')[0] in {'minecraft:oak_log','minecraft:oak_leaves'}:trees[q]=s
    assert len(trees)==62,'Reclassify a changed tree component instead of guessing'
    logs={q for q,s in trees.items() if s.startswith('minecraft:oak_log')};assert len({(q[0],q[2]) for q in logs})==1
    root=min(logs,key=lambda q:q[1]);assert root not in tags
    assert all('persistent=false' in s for s in trees.values() if 'leaves' in s),'Not the diagnosed natural tree'
    todo=deque([root]);connected={root}
    while todo:
        q=todo.popleft()
        for dx in [-1,0,1]:
            for dy in [-1,0,1]:
                for dz in [-1,0,1]:
                    n=q[0]+dx,q[1]+dy,q[2]+dz
                    if n in trees and n not in connected:connected.add(n);todo.append(n)
    assert connected==set(trees),'The complete connected component is required'
    # One-cell shell proves this is the whole measured log/leaf component.
    for q in trees:
        for dx,dy,dz in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
            n=q[0]+dx,q[1]+dy,q[2]+dz;s=w.block(n) or ''
            if s.split('[')[0].endswith(('_log','_leaves')):assert n in trees
    shift=int(target[root[2]-oz,root[0]-ox])+1-root[1];assert 0<shift<80
    desired={};columns=[];plants={}
    for zz,xx in zip(*np.where(changed)):
        x,z=int(xx+ox),int(zz+oz);low=int(old[zz,xx]);high=int(target[zz,xx]);assert high-low<80
        for y in range(low+1,low+4):
            q=x,y,z;s=w.block(q)
            if s and s.split('[')[0] in PLANTS:plants[q]=(s,high-low)
        for y in range(low,high+1):
            q=x,y,z;s=w.block(q);assert q not in tags
            assert s in AIR or s.split('[')[0] in {'minecraft:stone','minecraft:dirt','minecraft:grass_block'}|PLANTS or q in trees,(q,s)
            desired[q]='minecraft:grass_block[snowy=false]' if y==high else 'minecraft:dirt' if y>=high-3 else 'minecraft:stone'
        columns.append(dict(pos=[x,z],before=low,after=high))
    for q,s in trees.items():
        desired.setdefault(q,'minecraft:air');dest=q[0],q[1]+shift,q[2]
        assert dest not in tags and w.block(dest) in AIR,(dest,w.block(dest))
        assert dest[1]>target[dest[2]-oz,dest[0]-ox],('Tree would be buried by local slope',dest)
        desired[dest]=s
    for q,(s,offset) in plants.items():
        desired.setdefault(q,'minecraft:air');dest=q[0],q[1]+offset,q[2]
        assert dest not in desired or desired[dest] in AIR,('Plant relocation overlaps another component',dest)
        assert dest not in tags and w.block(dest) in AIR,(dest,w.block(dest))
        desired[dest]=s
    rows=[]
    for q,after in sorted(desired.items()):
        before_state=w.block(q)
        if before_state!=after:rows.append(dict(pos=q,before=before_state,after=after,before_nbt=None,after_nbt=None,owner='r44/geofront/east_range_whole_tree_regrade',reason='Continuous natural ridge field, with the complete diagnosed native oak moved to the new soil surface; no broad log/leaf deletion'))
    for name,inv in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
            for r in rows:
                b=dict(r)
                if inv:b['before'],b['after']=r['after'],r['before']
                f.write(json.dumps(b)+'\n')
    eligible=(target>before)&(~fixed);cols=[[int(xx+ox),int(zz+oz),int(target[zz,xx])] for zz,xx in zip(*np.where(eligible))]
    with gzip.open(a.output/'absolute_eligible_heightfield.json.gz','wt',encoding='utf8') as f:json.dump(dict(format='r44_absolute_eligible_ground_v1',bounds=[ox,oz,ox+shape[1]-1,oz+shape[0]-1],columns=cols),f)
    np.savez_compressed(a.output/'corrected_heightfield.npz',origin=d['origin'],before=before,installed=old,after=target,eligible=eligible,changed=changed)
    report=dict(changed_cells=len(rows),changed_columns=len(columns),moved_small_vegetation=[dict(pos=q,state=s,dy=dy) for q,(s,dy) in sorted(plants.items())],soil_columns_missed_by_grass_only_reader=soil_recovered,whole_tree_before=[dict(pos=q,state=s) for q,s in sorted(trees.items())],tree_vertical_shift=shift,old_tree_root=root,source_tree_classification='Single complete connected oak with native distance-state leaves persistent=false, soil root, no block entity or mixed authored material; exact before/inverse retained',fixed_infrastructure_masks_preserved=True,world_written=False,native_passed=False,visual_passed=False,root_apply_ready=False,future_heightfield_columns=len(cols),producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),columns=columns)
    (a.output/'report.json').write_text(json.dumps(report,indent=2),'utf8');print('Regrade',len(rows),'cells',len(columns),'columns; whole62-block natural tree rises',shift,'NO WRITE',flush=True)


if __name__=='__main__':main()
