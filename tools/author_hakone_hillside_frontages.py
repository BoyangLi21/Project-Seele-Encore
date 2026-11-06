"""Build complete low-rise hillside frontages on explicitly graded new plots.

New houses and shops have entrances, usable stairs, rooms and fresh device NBT.
No original inventory, entity, transport member or model asset is copied.
Only a fresh candidate is edited; publication remains a separate cold step.
"""
import argparse,copy,json,os,shutil
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from author_hakone_district_blocks import Frontage
from author_hakone_togendai import Station
from detail_hakone_nerv_streets import preservation_mask
from map_pipeline.launch_protection import load,check_candidate
from plan_ashi_landscape_r54 import SOIL,PLANTS
from prepare_hakone_togendai_neighbourhood import save_json
from prepare_hakone_city_cross import packed
from query_blocks import AIR

EMPTY=AIR|PLANTS|{'minecraft:light'}


def build(row):
    site=row['site'];c=Frontage(site);hx,hz=site['half'];levels=site['floors'];v=site['variant'];programme=row['programme']
    timber=programme=='inn';commercial=programme in ('shop','cafe','inn')
    wall=['minecraft:white_terracotta','minecraft:smooth_sandstone','minecraft:light_gray_terracotta','minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:terracotta'][v%6]
    frame='minecraft:dark_oak_planks'if timber or v%2 else'minecraft:spruce_planks'
    floor='minecraft:spruce_planks'if programme in ('house','inn')else'minecraft:smooth_stone'
    devices=[];goals=[];stairs=[]
    def tag(kind,p,extra=None):
        pos=c.point(*p);t=nbtlib.Compound({'id':nbtlib.String(kind),**{k:nbtlib.Int(a)for k,a in zip(('x','y','z'),pos)}})
        if extra:t.update(extra)
        devices.append(nbtlib.Compound({'Pos':nbtlib.Long(packed(pos)),'After':t}))
    c.fill(-hx-2,-2,-hz-2,hx+2,-1,hz+3,'minecraft:stone_bricks')
    c.fill(-hx-2,0,-hz-2,hx+2,0,hz+3,'minecraft:smooth_stone')
    c.fill(-hx-2,1,-hz-2,hx+2,levels*5+7,hz+3,'minecraft:air')
    for level in range(levels):
        y=level*5;c.fill(-hx,y,-hz,hx,y,hz,floor)
        for z in (-hz,hz):c.fill(-hx,y+1,z,hx,y+4,z,wall)
        for x in (-hx,hx):c.fill(x,y+1,-hz,x,y+4,hz,wall)
        for x in (-hx,hx):
            for z in (-hz,hz):c.fill(x,y+1,z,x,y+4,z,frame)
        for x in range(-hx+2,hx-1,4):
            for z in (-hz,hz):
                c.fill(x,y+2,z,min(x+1,hx-1),y+3,z,'minecraft:light_gray_stained_glass')
                c.fill(x,y+1,z,min(x+1,hx-1),y+1,z,frame)
        for z in range(-hz+2,hz-1,4):
            for x in (-hx,hx):c.fill(x,y+2,z,x,y+3,min(z+1,hz-1),'minecraft:light_gray_stained_glass')
        c.fill(-hx,y+4,hz,hx,y+4,hz,frame)
        c.put(0,y+4,0,'minecraft:sea_lantern')
        goals.append(dict(kind='room',feet=c.point(0,y+1,0)))
        # Furnish the side away from the stair and the entrance aisle.
        if programme in ('house','inn')and (level>0 or levels==1):
            bx,bz=hx-2,-hz+2
            for dz,part in [(0,'foot'),(-1,'head')]:
                c.put(bx,y+1,bz+dz,f'minecraft:white_bed[facing=north,occupied=false,part={part}]');tag('minecraft:bed',(bx,y+1,bz+dz))
            c.put(hx-2,y+1,0,'minecraft:chest[facing=west,type=single,waterlogged=false]');tag('minecraft:chest',(hx-2,y+1,0),{'Items':nbtlib.List[nbtlib.Compound]()})
            c.fill(1,y+1,-hz+1,1,y+3,-hz+1,frame)
        elif programme in ('cafe','inn'):
            for bx,bz in [(2,0),(hx-2,hz-2)]:
                c.put(bx,y+1,bz,'minecraft:oak_fence[east=false,north=false,south=false,waterlogged=false,west=false]')
                c.put(bx,y+2,bz,'minecraft:oak_pressure_plate[powered=false]')
                c.put(bx,y+1,bz+1,'minecraft:dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
            c.fill(2,y+1,-hz+2,hx-1,y+1,-hz+2,'minecraft:smooth_quartz')
        elif programme=='shop':
            c.fill(2,y+1,-hz+2,hx-2,y+2,-hz+2,'minecraft:bookshelf')
            c.fill(hx-2,y+1,-1,hx-2,y+1,hz-2,frame)
        else:
            c.fill(2,y+1,-hz+2,hx-1,y+1,-hz+2,'minecraft:smooth_quartz')
            c.put(hx-2,y+1,1,'minecraft:dark_oak_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]')
    for level in range(levels-1):
        y=level*5
        # Start beside the front vestibule and climb towards a clear rear landing.
        c.fill(-hx+1,y+5,hz-7,-hx+2,y+5,hz-3,'minecraft:air')
        for step in range(5):
            sz=hz-3-step;sy=y+1+step
            c.fill(-hx+1,sy,sz,-hx+2,sy,sz,'minecraft:oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
            for sx in (-hx+1,-hx+2):stairs.append(dict(block=c.point(sx,sy,sz),head=[c.point(sx,sy+1,sz),c.point(sx,sy+2,sz)]))
        c.fill(-hx+1,y+5,hz-8,-hx+2,y+5,hz-8,floor)
        goals.extend([dict(kind='stair lower landing',feet=c.point(-hx+2,y+1,hz-2)),dict(kind='stair upper landing',feet=c.point(-hx+2,y+6,hz-8))])
    # A lower-pitch tile roof has closed gables and thin overhanging eaves.
    roof=levels*5;c.fill(-hx,roof,-hz,hx,roof,hz,frame)
    if row.get('roof_style','gable')=='flat':
        c.fill(-hx,roof,-hz,hx,roof,hz,'minecraft:smooth_stone')
        for pz in (-hz,hz):c.fill(-hx,roof+1,pz,hx,roof+1,pz,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
        for px in (-hx,hx):c.fill(px,roof+1,-hz,px,roof+1,hz,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
        c.fill(hx-3,roof+1,-hz+2,hx-2,roof+1,-hz+3,'minecraft:polished_andesite')
        c.fill(hx-3,roof+2,-hz+2,hx-2,roof+2,-hz+3,'minecraft:iron_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]')
    else:
        for pz in range(-hz-1,hz+2):
            rise=hz+1-abs(pz);py=roof+1+rise//2
            for px in (-hx,hx):
                if abs(pz)<=hz:c.fill(px,roof+1,pz,px,py,pz,wall)
            material='minecraft:deepslate_tile_slab[type=bottom,waterlogged=false]'if rise%2==0 else'minecraft:deepslate_tiles'
            c.fill(-hx-1,py,pz,hx+1,py,pz,material)
    for px,hinge in [(-1,'left'),(0,'right')]:
        for py,half in [(1,'lower'),(2,'upper')]:c.put(px,py,hz,f'minecraft:dark_oak_door[facing=south,half={half},hinge={hinge},open=false,powered=false]')
    c.fill(-1,3,hz,0,3,hz,'minecraft:glass')
    c.fill(-2,0,hz+1,2,0,hz+3,'minecraft:stone_bricks')
    if commercial:
        c.fill(2,1,hz,hx-1,3,hz,'minecraft:glass')
        c.fill(-hx+1,4,hz+1,hx-1,4,hz+2,'minecraft:dark_oak_slab[type=bottom,waterlogged=false]')
        if programme=='inn':
            for px in (-2,1):c.put(px,3,hz+1,'minecraft:blue_wool')
    else:c.fill(-2,4,hz+1,1,4,hz+2,'minecraft:dark_oak_slab[type=bottom,waterlogged=false]')
    # A modest planting strip, drain and outdoor service unit give each plot depth.
    for pz in range(-hz,hz+1):c.put(hx+1,0,pz,'minecraft:gravel')
    for px in (-hx-1,hx+1):
        c.put(px,0,hz+2,'minecraft:dirt');c.put(px,1,hz+2,'minecraft:azalea'if v%2 else'minecraft:flowering_azalea')
    c.fill(hx-2,1,-hz-1,hx-1,1,-hz-1,'minecraft:polished_andesite')
    c.fill(hx-2,2,-hz-1,hx-1,2,-hz-1,'minecraft:iron_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]')
    return c,devices,goals,stairs


def author(source,out):
    for name in ('functional-check.json','independent-check.json'):
        if json.loads((source/name).read_text('utf8'))['errors']:raise ValueError('Unverified street candidate '+name)
    out.mkdir(parents=True,exist_ok=False);(out/'source').mkdir()
    for file in(source/'source').glob('*.npz'):os.link(file,out/'source'/file.name)
    for file in source.iterdir():
        if file.name=='source':continue
        if file.is_dir():shutil.copytree(file,out/file.name)
        else:shutil.copy2(file,out/file.name)
    rows=json.loads((out/'plan/new-frontages.json').read_text('utf8'));spec=json.loads((out/'plan/authored-design.json').read_text('utf8'));e=Editor(out);preserved=preservation_mask(out,spec)
    manifest=json.loads((out/'manifest.json').read_text('utf8'));guard=load(Path(manifest['world']));guards={};changes=list(nbtlib.load(out/'block-entities.dat')['Changes']);added=[];all_goals=[];all_stairs=[]
    for row in rows:
        box=row['occupied_bounds'];site=row['site'];fy=site['floor'];c,devices,goals,stairs=build(row)
        for px in range(box[0],box[3]+1):
            for pz in range(box[2],box[5]+1):
                key=px//16,pz//16
                if key not in guards:guards[key]=guard.chunk_mask(*key)
                for py in range(box[1],box[4]+1):
                    if preserved((px,py,pz))or guards[key][py+128,pz%16,px%16]:raise ValueError(('New frontage enters native geometry',row['id'],px,py,pz))
                    if e.state(px,py,pz).split('[')[0]not in SOIL|EMPTY:raise ValueError(('New frontage enters an existing construction',row['id'],px,py,pz,e.state(px,py,pz)))
        for op in c.operations:
            if any(op[k]<box[k]or op[k+3]>box[k+3]for k in range(3)):raise ValueError(('Frontage operation outside owned plot',row['id'],op))
            e.fill(*op)
        station=Station(e);face=['south','west','north','east'][site['rotation']]
        station.sign(*c.point(3,3,site['half'][1]+1),[row['label']],face)
        devices+=station.devices
        for item in devices:
            pos=tuple(int(item['After'][k])for k in ('x','y','z'));item['Pos']=nbtlib.Long(packed(pos));changes.append(item)
        # The outside doorstep joins the explicitly graded public approach.
        ax,ay,az=row['approach'];e.put(ax,ay-1,az,'minecraft:smooth_stone')
        added.append(dict(**row,devices=[dict(pos=[int(t['After'][k])for k in ('x','y','z')],id=str(t['After']['id']))for t in devices]))
        all_goals.extend(dict(parcel=row['id'],**g)for g in goals);all_stairs.extend(dict(parcel=row['id'],**s)for s in stairs)
    patches=e.save();nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changes)}).save(out/'block-entities.dat',gzipped=True)
    save_json(out/'new-frontages.json',dict(buildings=added,room_goals=all_goals,stairs=all_stairs,new_device_tags=sum(len(r['devices'])for r in added)))
    manifest.update(regions=patches,cells=sum(r['cells']for r in patches),new_frontages=len(rows));save_json(out/'manifest.json',manifest)
    save_json(out/'launch-protection.json',check_candidate(guard,out));print('Authored',len(rows),'complete frontages;',sum(len(r['devices'])for r in added),'new device tags',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();author(a.source,a.out)
