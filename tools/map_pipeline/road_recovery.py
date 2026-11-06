"""Classify observed road layers, retire obsolete decks, clear retained roads.

Only existing registered roads grant editing authority. All other material
candidates remain in the discovery report instead of being silently deleted.
"""
import argparse,json
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled
from plan_ashi_landscape_r54 import SOIL,PLANTS
from query_blocks import AIR


def classify(a):
    f=np.load(a.survey/'observed.npz');v=f['points'];chunks=f['chunks']
    d=load_grid(a.plan/'network.npz')
    current=sampled(d,'walk',v[:,0],v[:,2]).astype(bool)&(abs(v[:,3]-sampled(d,'grade2',v[:,0],v[:,2])-2)<=2)
    legacy=np.zeros(len(v),bool)
    for name in ('road_contract_final.npz','extension_contract_final.npz'):
        q=load_grid(a.gis.parent/'world_rebuild_r20/road_actual'/name);x,z=map(int,q['origin'])
        q['bounds']=[x,z,x+q['mask'].shape[1]-1,z+q['mask'].shape[0]-1]
        legacy|=sampled(q,'mask',v[:,0],v[:,2]).astype(bool)&(abs(sampled(q,'height2',v[:,0],v[:,2])-v[:,3])<=1)
    x,y,z=v[:,:3].T
    replaced=((x>=-1050)&(x<=1350)&(z>=-800)&(z<=1400))|((x>=896)&(x<=2431)&(z>=512)&(z<=1407))
    facility=((x>=350)&(x<=1350)&(z>=-177)&(z<=125))|((x>=400)&(x<=1350)&(z>=1400))
    boxes=[r['occupied_bounds']for r in json.loads((a.plan/'catalog.json').read_text('utf8'))]
    boxes+=json.loads((a.plan/'station-volumes.json').read_text('utf8'))
    inside=np.zeros(len(v),bool)
    for bx,by,bz,bX,bY,bZ in boxes:
        inside|=(x>=bx)&(x<=bX)&(z>=bz)&(z<=bZ)&(y>=by)&(y<=bY)
    # Existing tunnel layers are retained at their own elevation, even if a
    # surface street occupies the same plan coordinate.
    tunnels=json.loads(a.tunnels.read_text('utf8'))['points']
    from map_pipeline.roads import keys
    tk=np.sort(keys(np.array([p[0]for p in tunnels]),np.array([p[2]for p in tunnels]),np.array([2*p[1]+2 for p in tunnels])))
    vk=keys(x,z,v[:,3]);at=np.searchsorted(tk,vk);hit=at<len(tk);hit[hit]&=tk[at[hit]]==vk[hit]
    retain=(current|hit|(legacy&(~replaced|facility)))&~inside
    retire=legacy&replaced&~facility&~current&~hit&~inside
    result=dict(current=int(current.sum()),registered_legacy=int(legacy.sum()),retained_road_layers=int(retain.sum()),
                obsolete_road_layers=int(retire.sum()),unclassified_material_layers=int((~retain&~retire).sum()),
                blocked_retained_layers=int((retain&(v[:,5]>0)).sum()),
                observed_layers=len(v),unknown_full_chunks_not_fabricated=True)
    np.savez_compressed(a.out/'classification.npz',points=v,retain=retain,retire=retire,chunks=chunks)
    (a.out/'classification.json').write_text(json.dumps(result,indent=2),'utf8')
    print(result,flush=True)


def compose(a):
    f=np.load(a.out/'classification.npz');v=f['points'];retain=f['retain'];retire=f['retire']
    tasks=defaultdict(list)
    for p in v[retain|retire]:tasks[int(p[0])//512,int(p[2])//512].append(p)
    chosen={tuple(map(int,p[:3])):bool(r)for p,r in zip(v[retain|retire],retire[retain|retire])}
    e=Editor(a.candidate);counts=Counter();conflicts=[];kept=[]
    catalog=json.loads((a.plan/'catalog.json').read_text('utf8'))
    boxes=[r['occupied_bounds']for r in catalog]+json.loads((a.plan/'station-volumes.json').read_text('utf8'))
    rails=defaultdict(set)
    for row in json.loads((a.plan/'native-curves.json').read_text('utf8'))['trains']:
        for p in row['points']:
            x,y,z=map(int,np.floor(p))
            for X in range(x-2,x+3):
                for Z in range(z-2,z+3):rails[X,Z].add(y)
    for key,ps in sorted(tasks.items()):
        r=e.region(key[0]*512,key[1]*512)
        local_boxes=[b for b in boxes if b[0]<(key[0]+1)*512 and b[3]>=key[0]*512 and b[2]<(key[1]+1)*512 and b[5]>=key[1]*512]
        for s in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'):
            if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
        air,stone,dirt,grass=[r['ids'][s]for s in('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]')]
        bare=[s.split('[')[0]for s in r['names']];soil=np.array([s in SOIL|PLANTS for s in bare]);empty=np.array([s in AIR|PLANTS|{'minecraft:light'} for s in bare])
        road_material=np.array([s in {'minecraft:black_concrete','minecraft:white_concrete','minecraft:gray_concrete','minecraft:smooth_stone','minecraft:smooth_stone_slab','minecraft:yellow_concrete','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}for s in bare])
        for p in ps:
            x,y,z=map(int,p[:3]);c=r['after'][r['index'][x//16,z//16],:,z%16,x%16];cy=y+128
            if chosen[x,y,z]:
                if any(ry-3<=y<=ry+8 for ry in rails[x,z]):counts['retired_candidates_under_native_transport_retained']+=1;continue
                # Replace only the measured road stack (up to three blocks),
                # never its entire column or unrelated lamps/unknown devices.
                supported=(cy>2 and soil[c[cy-3]])
                for dy in range(3):
                    i=cy-dy
                    if i<0 or not road_material[c[i]]:break
                    c[i]=grass if dy==0 and supported else dirt if supported else air
                    counts['obsolete_paving_cells_removed']+=1
                continue
            hi=min(448,cy+4)
            protected=np.zeros(max(0,hi-cy-1),bool)
            for bx,by,bz,bX,bY,bZ in local_boxes:
                if bx<=x<=bX and bz<=z<=bZ:protected|=(np.arange(y+1,y+1+len(protected))>=by)&(np.arange(y+1,y+1+len(protected))<=bY)
            for ry in rails[x,z]:protected|=(np.arange(y+1,y+1+len(protected))>=ry-3)&(np.arange(y+1,y+1+len(protected))<=ry+8)
            head=c[cy+1:hi];bad=soil[head]&~protected
            counts['road_soil_cells_removed']+=int(bad.sum());head[bad]=air
            if soil[head].any():conflicts.append([x,y,z,'retained structure/rail contact'])
            if (~empty[head]&~soil[head]).any():kept.append([x,y,z,sorted(set(bare[i]for i in head[~empty[head]&~soil[head]]))])
        e.save();e.regions.clear()
        print('Recovered road region',key,dict(counts),flush=True)
    rows=e.save();m=json.loads((a.candidate/'manifest.json').read_text('utf8'));m.update(regions=rows,cells=sum(r['cells']for r in rows))
    (a.candidate/'manifest.json').write_text(json.dumps(m,indent=2),'utf8')
    result=dict(counts=dict(counts),protected_contacts=conflicts,other_objects=kept,
                note='Unknown structures are retained, not counted as cleared. Road endpoint classification is a separate output.')
    (a.out/'recovery.json').write_text(json.dumps(result,indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('phase',choices=['classify','compose'])
    for k in('survey','plan','gis','out','tunnels','candidate'):p.add_argument('--'+k,type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    {'classify':classify,'compose':compose}[a.phase](a)
