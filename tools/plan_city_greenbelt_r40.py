"""Measured urban-edge planting plan; no changes to street or terrain elevations.

Uses the immutable pre-work world while native tests run. Application rereads
every proposed cell against the current world after Minecraft closes.
"""
import argparse,json,gzip,math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
from query_blocks import AIR
import regional_voxels as v

OUT=ROOT/'artifacts/world_combat_r40/greenbelt';BASE=ROOT/'artifacts/world_combat_r40/source_world_backup'
ZONES=[('tokyo_west_woodland',(-900,450,-763,840)),('hakone_east_woodland',(-1225,655,-1121,930)),('intercity_woodland',(-1040,685,-925,910))]

def plan():
    OUT.mkdir(parents=True,exist_ok=True);w=MeasuredWorld(BASE)
    for _,(x,z,X,Z) in ZONES:w.box((x-5,45,z-5),(X+5,150,Z+5))
    w.load();native=json.loads((BASE/'native_transit_r28.json').read_text());rail=np.asarray([q for c in native['curves'] if c['mode']=='TRAIN' for q in c['points']]);rail_tree=cKDTree(rail[:,[0,2]])
    paths=[]
    for r in json.loads((BASE/'quality_walk_cases.json').read_text()):
        pts=r.get('path',[r.get('start'),r.get('end')])
        if any(q is None for q in pts):continue
        for a,b in zip(pts,pts[1:]):
            if not 35<min(a[1],b[1])<170:continue
            if max(a[0],b[0])<-1240 or min(a[0],b[0])>-748 or max(a[2],b[2])<430 or min(a[2],b[2])>945:continue
            paths.extend(np.linspace(a,b,max(2,int(np.linalg.norm(np.asarray(a)-b)/2)+1)))
    path_tree=cKDTree(np.asarray(paths)[:,[0,2]]) if paths else None
    natural={'minecraft:grass_block','minecraft:dirt','minecraft:coarse_dirt','minecraft:podzol'};plants={'minecraft:grass','minecraft:short_grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:light'}
    changes={};trees=[];held=0
    def ground(x,z):
        for y in range(140,49,-1):
            s=w.get(x,y,z)
            if s is None:continue
            n=s.partition('[')[0]
            if n in natural:return y
            if n not in AIR|plants and not n.endswith('_leaves'):return None
        return None
    for name,(x0,z0,x1,z1) in ZONES:
        for xbase in range(x0+5,x1-4,13):
            for zbase in range(z0+5,z1-4,13):
                seed=((xbase*73856093)^(zbase*19349663))&0xffffffff
                x=xbase+seed%5-2;z=zbase+(seed//7)%5-2
                if rail_tree.query([x,z])[0]<13 or path_tree is not None and path_tree.query([x,z])[0]<7:held+=1;continue
                y=ground(x,z)
                if y is None:held+=1;continue
                g=[ground(x+dx,z+dz) for dx,dz in ((-3,0),(3,0),(0,-3),(0,3))]
                if any(q is None or abs(q-y)>2 for q in g):held+=1;continue
                height=6+seed%3;need={}
                conifer=seed%3==0;wood='spruce' if conifer else 'oak'
                for dy in range(1,height+1):need[(x,y+dy,z)]=f'minecraft:{wood}_log[axis=y]'
                for dy in range(3,height+2):
                    radius=max(1,int((height+2-dy)/2)) if conifer else (3 if 4<=dy<=height else 2)
                    for dx in range(-radius,radius+1):
                        for dz in range(-radius,radius+1):
                            if dx*dx+dz*dz>radius*radius+1 or dx==0 and dz==0 and dy<=height:continue
                            need[x+dx,y+dy,z+dz]=f'minecraft:{wood}_leaves[distance=1,persistent=true,waterlogged=false]'
                # Complete trunk and crown are checked, not merely the root.
                if any((w.block(q) or '').partition('[')[0] not in AIR|plants or q in changes for q in need):held+=1;continue
                for q,s in need.items():changes[q]=(w.block(q),s,name)
                trees.append(dict(zone=name,root=[x,y+1,z],height=height,species=wood))
    with gzip.open(OUT/'cells.json.gz','wt',encoding='utf8') as f:json.dump([[*q,*s] for q,s in sorted(changes.items())],f,separators=(',',':'))
    report=dict(zones=ZONES,trees=trees,held_sites=held,cells=len(changes),terrain_elevations_changed=False,native_rail_exclusion_metres=13,registered_public_path_exclusion_metres=7,reference='Hakone mountain woodland and urban-edge separation; project interpretation, not a claim of copied canonical geography')
    (OUT/'contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('Greenbelt trees',len(trees),'cells',len(changes),'held',held)

def apply():
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();w=MeasuredWorld()
    with gzip.open(OUT/'cells.json.gz','rt',encoding='utf8') as f:rows=json.load(f)
    for row in rows:w.around(row[:3],0)
    w.load()
    for x,y,z,before,after,owner in rows:
        q=x,y,z
        if w.block(q)!=before:raise RuntimeError(('World changed before planting',q,w.block(q),before))
        p.match((*q,*q),before,after,'r40/'+owner)
    p.meta=json.loads((OUT/'contract.json').read_text());p.apply('urban_edge_woodland')
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');args=a.parse_args();apply() if args.apply else plan()
