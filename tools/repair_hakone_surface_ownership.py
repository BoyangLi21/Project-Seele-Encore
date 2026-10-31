"""Repair installed city surfaces and footings from explicit authored ownership.

Works on a frozen current capture. It never deletes by material across an
unknown area, edits live game data, or moves transport/actor identities.
"""
import argparse, copy, json
from pathlib import Path
import nbtlib
import numpy as np
from query_blocks import iter_block_entities
from apply_s20_approved_semantic_repairs import parse_state
from prepare_hakone_main_terrain import sample_grid
from plan_ashi_landscape_r54 import SOIL

DATA = Path('dimensions/projectseele/geofront/data')


def load_grid(path):
    with np.load(path) as f:
        return {k:f[k] for k in f.files}


def sampled(d, key, xx, zz, default=0):
    x0,z0,x1,z1 = map(int,d['bounds'])
    valid=(xx>=x0)&(xx<=x1)&(zz>=z0)&(zz<=z1)
    result=np.full(xx.shape,default,dtype=d[key].dtype)
    result[valid]=d[key][zz[valid]-z0,xx[valid]-x0]
    return result


def run(a):
    source=Path(a.source); out=Path(a.out); out.mkdir(exist_ok=False)
    (out/'delta').mkdir(); (out/'source').mkdir()
    city=load_grid(a.gis/'city-south-streets-v3/surface.npz')
    routing=load_grid(a.gis/'city-south-streets-v3/routing.npz'); routing['bounds']=city['bounds']
    main=load_grid(a.gis/'main-district-integration-v1/coupled-grading.npz')
    legacy=load_grid(a.gis/'main-district-integration-v1/district-plan.npz')
    measured=load_grid(source/'measured.npz')
    poles=json.loads((a.gis/'station-corridor-ready/manifest.json').read_text('utf8'))['pylons']
    parcels=[]
    for file in ('neighbourhood.json','retained-neighbourhood.json'):
        parcels+=json.loads((a.gis/'city-south-streets-v3'/file).read_text('utf8'))
    current_parcels=json.loads((a.gis/'main-district-current-ready-v2/neighbourhood.json').read_text('utf8'))
    boxes=[r['bounds'] for r in parcels]
    for r in current_parcels:
        s=r['site'];x,z=s['centre'];hx,hz=s['half'];hx,hz=(hz,hx)if s['rotation']%2 else(hx,hz)
        boxes.append([x-hx-2,s['floor'],z-hz-2,x+hx+2,s['floor']+max(1,s['floors'])*5+8,z+hz+2])
    bounds=measured['bounds']; devices=dict(iter_block_entities(a.frozen,'projectseele:geofront',
        (int(bounds[0]),32,int(bounds[1])),(int(bounds[2]),319,int(bounds[3]))))
    changes=[]; evidence={'removed_city_soil':0,'retired_road_cells':0,'pylons':[], 'devices_preserved':len(devices)}
    yy=np.arange(-128,320)[:,None,None]
    for file in sorted((source/'source').glob('*.npz')):
        with np.load(file) as f:
            coords=f['coordinates']; blocks=f['blocks']; names=list(map(str,f['palette']))
        names+=['minecraft:air','minecraft:grass_block[snowy=false]','minecraft:stone','minecraft:dirt','minecraft:stone_bricks']
        ids={s:i for i,s in enumerate(names)}
        soil=np.array([s.split('[')[0]in SOIL for s in names])
        road=np.array([s.split('[')[0]in {'minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone','minecraft:smooth_stone_slab','minecraft:gray_concrete'}for s in names])
        air=np.array([s.split('[')[0]in {'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:grass','minecraft:tall_grass','minecraft:water'}for s in names])
        bearing=np.array([s.split('[')[0]in SOIL|{'minecraft:stone_bricks','minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:smooth_stone'}for s in names])
        points=[];ranges=[0];indices=[];before=[];after=[]
        for coordinate,old in zip(coords,blocks):
            cx,cz=map(int,coordinate); zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]; new=old.copy()
            cross=sampled(city,'cross',xx,zz).astype(bool)
            frame=sampled(city,'frame',xx,zz).astype(bool)
            paved=sampled(city,'paved',xx,zz).astype(bool)
            owned_plot=np.zeros((16,16),bool)
            for x,y,z,X,Y,Z in boxes:owned_plot|=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)
            # Trees, lamps, functional machinery and the actual raised/lowered
            # cargo are not soil. A stray soil pillar is not a protected pier.
            remove=cross&~owned_plot&(yy>80)&soil[old]
            # Launch mouths and their mountain-side structures retain height.
            remove&=~((xx>=-110)&(xx<=225)&(zz<=15))
            evidence['removed_city_soil']+=int(remove.sum());new[remove]=ids['minecraft:air']
            oldroad=sampled(legacy,'legacy',xx,zz).astype(bool)
            currentwalk=sampled(main,'walk',xx,zz).astype(bool)
            # Known obsolete road paint is retired only inside the engineered
            # city; street openings and entire native stations are kept.
            station=((xx>=294)&(xx<=379)&(zz>=222)&(zz<=378))|((xx>=159)&(xx<=201)&(zz>=682)&(zz<=838))
            retire=cross&oldroad&~paved&~frame&~owned_plot&~station&road[old[208]]
            evidence['retired_road_cells']+=int(retire.sum());new[208][retire]=ids['minecraft:grass_block[snowy=false]']
            # The actual support head and cable node never move. Recompute the
            # footing against the final soil, instead of its historical Y.
            for pole in poles:
                x,previous,z=map(int,pole['foot']);head=int(pole['node'][1])+1
                if x//16!=cx or z//16!=cz:continue
                col=new[:,z%16,x%16];ground=np.flatnonzero(bearing[col]&(np.arange(-128,320)<previous))
                if not len(ground):raise ValueError('No measured pylon bearing '+str(pole))
                ground=int(ground[-1])-128
                if ground>=previous-1:continue
                if names[int(col[previous+128])]!='minecraft:stone_bricks':raise ValueError('Pylon footing changed '+str(pole))
                gap=col[ground+129:previous+128]
                if not air[gap].all():raise ValueError('Pylon extension meets a retained object '+str(pole))
                col[ground+128]=ids['minecraft:stone_bricks'];col[ground+129:previous+129]=ids.get('minecraft:gray_concrete',ids['minecraft:stone_bricks'])
                evidence['pylons'].append(dict(node=pole['node'],old_foot=pole['foot'],new_foot=[x,ground,z]))
            for (x,y,z),tag in devices.items():
                if x//16==cx and z//16==cz and new[y+128,z%16,x%16]!=old[y+128,z%16,x%16]:
                    raise ValueError('Surface operation reaches persistent device '+str((x,y,z)))
            at=np.flatnonzero((new!=old).ravel()).astype(np.uint32)
            if not len(at):continue
            points.append(coordinate);ranges.append(ranges[-1]+len(at));indices.append(at);before.append(old.ravel()[at]);after.append(new.ravel()[at])
        if points:
            np.savez_compressed(out/'delta'/file.name,coordinates=points,ranges=ranges,indices=np.concatenate(indices),before=np.concatenate(before),after=np.concatenate(after),palette=np.array(names))
            # These immutable current blocks are the inverse source, never a
            # whole-world installation payload.
            import os
            os.link(file,out/'source'/file.name)
            changes.append(dict(path='delta/'+file.name,cells=ranges[-1]))
            print(file.name,ranges[-1],flush=True)
    manifest=dict(world=str(a.world),bounds_xz=list(map(int,bounds)),regions=changes,cells=sum(r['cells']for r in changes),world_written=False)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (out/'ownership-evidence.json').write_text(json.dumps(evidence,indent=2),'utf8')
    (out/'functional-check.json').write_text(json.dumps(dict(errors=['Final road/recipe/structure composition pending'],visual_verified=False),indent=2),'utf8')
    print(json.dumps(evidence),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','out','gis','frozen','world'):p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
