"""Restore finite, bank-contained geographic ponds or moat reaches.

Open rivers are deliberately rejected: they require a flow and interface design.
The saved chunk recipes provide the exact one-block water outline; the coarse
regional height field is unchanged. No actual world files are modified here.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_dilation
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL,SOIL
from query_blocks import AIR
from install_r53_carrier_trays import stopped_world
from map_pipeline.launch_protection import load,check_candidate

def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')

def prepare(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world'])
    if cap['actors']or cap['unavailable_chunks']:raise ValueError('Full unoccupied measured source required')
    x,z,X,Z=cap['bounds_xz']
    programme=json.loads((a.programme/'watercourse-programme.json').read_text('utf8'))
    rows=[r for r in programme['components']if r['id']in a.component]
    if len(rows)!=len(set(a.component)):raise ValueError('Unknown or duplicate water component')
    for r in rows:
        l,t,R,B=r['bounds']
        if r['open_regional_interface']or r['reaches_geographic_sea']:raise ValueError('Open river needs a separate flow/interface design')
        if not(x+4<=l<=R<=X-4 and z+4<=t<=B<=Z-4):raise ValueError('Complete closed water body and bank collar required')
    with np.load(a.programme/'watercourse-reference.npz')as f:
        ox,oz,oX,oZ=map(int,f['bounds']);ids=f['labels'][z-oz:Z-oz+1,x-ox:X-ox+1];mask=np.isin(ids,a.component)
    with np.load(a.source/'measured.npz')as f:ground=f['top'];full=f['full']
    if not full.all()or int(mask.sum())!=sum(r['columns']for r in rows):raise ValueError('Incomplete measured water-body footprint')
    if a.depth<2 or a.depth>5:raise ValueError('Finite shallow restoration depth required')
    bank=binary_dilation(mask)&~mask
    if np.any(ground[bank]<a.level):raise ValueError('A water edge lacks a containing bank')
    if np.any(ground[mask]<a.level-a.depth):raise ValueError('Existing deeper bed requires its own preservation design')
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('source','delta'):(a.out/name).mkdir()
    for p in(a.source/'source').glob('*.npz'):os.link(p,a.out/'source'/p.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    with stopped_world(world):shutil.copytree(world/'mtr',a.out/'preserved-native')
    e=Editor(a.out);guard=load(world);yy=np.arange(-128,320)[:,None,None];bed=a.level-a.depth
    for path in sorted((a.out/'source').glob('*.npz')):
        rx,rz=map(int,path.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        for name in ('minecraft:air','minecraft:gravel','minecraft:water[level=0]'):
            if name not in r['ids']:r['ids'][name]=len(r['names']);r['names'].append(name)
        base=[s.split('[')[0]for s in r['names']]
        natural=np.asarray([s in NATURAL for s in base]);air=np.asarray([s in AIR for s in base]);soil=np.asarray([s in SOIL for s in base])
        for (cx,cz),v in zip(r['coords'],r['after']):
            q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];active=mask[q]
            if not active.any():continue
            actual=np.where(soil[v],yy,-129).max(0)
            if np.any(active&(actual!=ground[q])):raise ValueError('Measured soil and saved payload disagree')
            highest=np.where(~air[v],yy,-129).max(0);band=active&(yy>=bed)&(yy<=np.maximum(highest,a.level))
            if np.any(band&(~natural[v]|guard.chunk_mask(int(cx),int(cz)))):raise ValueError('Water restoration intersects retained structure or launch volume')
            target=np.where(yy==bed,r['ids']['minecraft:gravel'],np.where(yy<=a.level,r['ids']['minecraft:water[level=0]'],r['ids']['minecraft:air']))
            v[band]=np.broadcast_to(target,v.shape)[band]
        e.save();e.regions.clear()
    records=e.save();target=ground.copy();target[mask]=bed
    np.savez_compressed(a.out/'water-design.npz',bounds=cap['bounds_xz'],wet=mask,bank=bank,old_ground=ground,ground=target,level=a.level,bed=bed)
    save(a.out/'manifest.json',dict(world=str(world),bounds_xz=cap['bounds_xz'],regions=records,cells=sum(r['cells']for r in records),
        preserve_native_members=True,enclosed_water=dict(programme=str(a.programme),components=a.component,columns=int(mask.sum()),level=a.level,bed=bed,
        exact_future_chunk_recipes_required=True,regional_height_field_unchanged=True),world_written=False))
    save(a.out/'functional-check.json',dict(errors=['Independent enclosed-water verification pending'],visual_verified=False,world_written=False))
    save(a.out/'launch-protection.json',check_candidate(guard,a.out))
    print('Prepared',int(mask.sum()),'water columns;',sum(r['cells']for r in records),'changed cells; no world writes.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','programme','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--component',nargs='+',type=int,required=True);p.add_argument('--level',type=int,required=True);p.add_argument('--depth',type=int,default=2)
    prepare(p.parse_args())
