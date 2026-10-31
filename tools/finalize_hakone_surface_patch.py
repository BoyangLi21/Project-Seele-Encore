"""Compose current surface fixes, ground live supports and update future recipes."""
import argparse,copy,json,os,shutil
from pathlib import Path
from collections import defaultdict
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from install_hakone_array_patch import Palette,compose
from query_blocks import iter_block_entities,AIR
from plan_ashi_landscape_r54 import SOIL
from apply_s20_approved_semantic_repairs import parse_state
from hakone_earthworks import road_blocks

DATA=Path('dimensions/projectseele/geofront/data')

def finalize_proto(a):
    a.out.mkdir(exist_ok=False);(a.out/'delta').mkdir()
    errors=[];count=0
    for file in(a.terrain/'delta').glob('*.npz'):
        os.link(file,a.out/'delta'/file.name)
        rx,rz=map(int,file.stem.split('.')[1:])
        with np.load(file)as f:coords=f['coordinates'];ranges=f['ranges'];at=f['indices']
        selected={tuple(map(int,q)):i for i,q in enumerate(coords)}
        for p,tag in iter_block_entities(a.frozen,'projectseele:geofront',(rx*512,-128,rz*512),(rx*512+511,319,rz*512+511),selected_chunks=set(selected)):
            count+=1;i=selected[p[0]//16,p[2]//16];offset=(p[1]+128)*256+(p[2]%16)*16+p[0]%16;l,r=ranges[i:i+2]
            j=np.searchsorted(at[l:r],offset)
            if j<r-l and at[l+j]==offset:errors.append(['proto-device-touched',*p])
    original=json.loads((a.terrain/'functional-check.json').read_text('utf8'))['errors']
    errors=[e for e in original if e[0]!='pending']+errors
    manifest=json.loads((a.terrain/'manifest.json').read_text('utf8'));manifest['world']=str(a.world)
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=errors,devices_checked=count,generation_stages_preserved=True,visual_verified=False),indent=2),'utf8')
    print('Proto composition',len(manifest['preserved_generation_statuses']),'chunks; issues',len(errors),flush=True)

def finalize(a):
    a.out.mkdir(exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    for source in(a.terrain,a.stations):
        for f in(source/'source').glob('*.npz'):
            dest=a.out/'source'/f.name
            if not dest.exists():os.link(f,dest)
    files=defaultdict(list)
    for source in(a.terrain,a.stations):
        for f in(source/'delta').glob('*.npz'):files[f.name].append(f)
    for name,paths in files.items():
        p=Palette();chunks=compose(paths,p);coords=[];ranges=[0];indices=[];old=[];new=[]
        for q,(at,b,v)in chunks.items():
            if not len(at):continue
            coords.append(q);ranges.append(ranges[-1]+len(at));indices.append(at);old.append(b);new.append(v)
        if coords:np.savez_compressed(a.out/'delta'/name,coordinates=coords,ranges=ranges,indices=np.concatenate(indices),before=np.concatenate(old),after=np.concatenate(new),palette=p.names)
    editor=Editor(a.out);errors=[];supports=[]
    terrain_manifest=json.loads((a.terrain/'manifest.json').read_text('utf8'))
    # Building stone, gravel and timber must not be mistaken for geology.
    # Preserve the complete occupied envelope, including its original AIR.
    occupied=defaultdict(list)
    retained_boxes=list(json.loads((Path(terrain_manifest['terrain_atlas'])/'retained-parcels.json').read_text('utf8')).values())
    retained_boxes.append([-110,32,-120,225,160,15])
    for box in retained_boxes:
        x,y,z,X,Y,Z=box
        for rx in range(x//512,X//512+1):
            for rz in range(z//512,Z//512+1):occupied[rx,rz].append(box)
    restored_building_cells=0
    for (rx,rz),boxes in occupied.items():
        if not(a.out/'source'/f'r.{rx}.{rz}.npz').exists():continue
        r=editor.region(rx*512,rz*512);station_changes=defaultdict(set)
        file=a.stations/'delta'/f'r.{rx}.{rz}.npz'
        if file.exists():
            with np.load(file)as f:
                co,ra,at=f['coordinates'],f['ranges'],f['indices']
                for i,q in enumerate(co):station_changes[tuple(q)]=set(map(int,at[ra[i]:ra[i+1]]))
        for (cx,cz),before,after in zip(r['coords'],r['before'],r['after']):
            for x,y,z,X,Y,Z in boxes:
                lx,lz=max(x,cx*16),max(z,cz*16);hx,hz=min(X,cx*16+15),min(Z,cz*16+15)
                if lx>hx or lz>hz:continue
                area=np.s_[max(-128,y)+128:min(319,Y)+129,lz-cz*16:hz-cz*16+1,lx-cx*16:hx-cx*16+1]
                mask=np.zeros(before.shape,bool);mask[area]=True
                if station_changes[cx,cz]:mask.ravel()[list(station_changes[cx,cz])]=False
                mask&=after!=before;restored_building_cells+=int(mask.sum());after[mask]=before[mask]
        editor.save();editor.regions.clear()
    seam_files=[a.terrain.parent/'seams-v1/gora-seam.npz',Path(terrain_manifest['terrain_atlas'])/'shore-seam.npz']
    markings=0
    for seam_file in seam_files:
        with np.load(seam_file)as d:
            x0,z0,_,_=map(int,d['bounds']);mask=d['road']&~d['plots'];grades=d['grade2'];old=d['old_target']
        for iz,ix in np.argwhere(mask):
            x,z=int(ix+x0),int(iz+z0);y,slab=map(int,road_blocks(np.array(grades[iz,ix])));previous=int(round(old[iz,ix]))
            if editor.state(x,y,z).split('[')[0]not in {'minecraft:black_concrete','projectseele:road_asphalt_slab'}:continue
            if any(editor.state(x,Y,z,original=True).split('[')[0]in {'minecraft:white_concrete','projectseele:road_marking_slab'}for Y in range(previous-1,previous+2)):
                editor.put(x,y,z,'projectseele:road_marking_slab[type=bottom,waterlogged=false]'if slab else'minecraft:white_concrete');markings+=1
        editor.save();editor.regions.clear()
    poles=json.loads((a.gis/'station-corridor-ready/manifest.json').read_text('utf8'))['pylons']
    pending=defaultdict(list)
    for r in poles:
        x,y,z=map(int,r['foot']);pending[x//512,z//512].append(('ropeway',x,int(r['node'][1]),z))
    piers=json.loads((a.gis.parent/'world_rebuild_r20/transit/civil/viaduct_stations_and_streets/places.json').read_text('utf8'))['piers']
    for x,y,z in piers:
        if not(a.out/'source'/f'r.{x//512}.{z//512}.npz').exists():continue
        for dx in(-1,0,1):
            for dz in(-1,0,1):pending[(x+dx)//512,(z+dz)//512].append(('viaduct',x+dx,y-4,z+dz))
    materials={'minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:stone_bricks'}
    for region,rows in pending.items():
        for kind,x,head,z in rows:
            r=editor.region(x,z)
            if(x//16,z//16)not in r['index']:continue
            start=head
            if kind=='ropeway':
                # The cable node is not a post block; find its supporting stem.
                while start>=head-8 and editor.state(x,start,z).split('[')[0]not in materials:start-=1
            if editor.state(x,start,z).split('[')[0]not in materials:continue
            if kind=='viaduct' and editor.state(x,start+1,z).split('[')[0]not in materials:continue
            foot=start
            while foot>-127 and editor.state(x,foot-1,z).split('[')[0]in materials:foot-=1
            # Old pier catalogs also intersect later station decks. A two-layer
            # slab is a horizontal deck, not a vertical post to extend through
            # the occupied concourse below it.
            if kind=='viaduct' and start-foot+1<4:continue
            ground=foot-1
            while ground>-128 and editor.state(x,ground,z).split('[')[0]in AIR|{'minecraft:water','minecraft:grass','minecraft:tall_grass'}:ground-=1
            if ground>=foot-1:continue
            base=editor.state(x,ground,z).split('[')[0]
            if base not in SOIL|materials:errors.append(['support-bearing',kind,x,ground,z,base]);continue
            material='minecraft:gray_concrete'if kind=='ropeway'else'minecraft:light_gray_concrete'
            editor.fill(x,ground+1,z,x,foot-1,z,material);supports.append([kind,x,ground,z,foot])
        editor.save();editor.regions.clear()
    regions=editor.save();changed_devices=0;devices_checked=0;recipe_count=0
    for file in sorted((a.out/'delta').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:])
        with np.load(file)as f:coords=f['coordinates'];ranges=f['ranges'];at=f['indices'];after=f['after'];before=f['before'];names=list(map(str,f['palette']))
        selected={tuple(map(int,p))for p in coords};positions=defaultdict(dict)
        for p,tag in iter_block_entities(a.frozen,'projectseele:geofront',(rx*512,-128,rz*512),(rx*512+511,319,rz*512+511),selected_chunks=selected):
            positions[p[0]//16,p[2]//16][(p[1]+128)*256+(p[2]%16)*16+p[0]%16]=p
        for i,q in enumerate(coords):
            q=tuple(map(int,q));l,r=ranges[i:i+2];offsets=at[l:r];values=after[l:r]
            for offset,p in positions[q].items():
                devices_checked+=1;j=np.searchsorted(offsets,offset)
                if j<len(offsets)and offsets[j]==offset:errors.append(['persistent-device-touched',*p]);changed_devices+=1
            relative=DATA/'city_rigid_generation_r45/surface'/f'{q[0]}_{q[1]}.dat';original=a.frozen/relative
            if not original.exists():continue
            data=nbtlib.load(original);oldpalette=data['Palette'];lookup={str(s['Name'])+str(s.get('Properties',{})):j for j,s in enumerate(oldpalette)}
            remap={}
            for value in np.unique(values):
                state=parse_state(names[int(value)]);key=str(state['Name'])+str(state.get('Properties',{}))
                if key not in lookup:lookup[key]=len(oldpalette);oldpalette.append(state)
                remap[int(value)]=lookup[key]
            bycolumn=defaultdict(list)
            for offset,value in zip(offsets,values):bycolumn[int(offset)%256].append((int(offset)//256-128,remap[int(value)]))
            for column,rows in bycolumn.items():
                rows.sort();start=end=rows[0][0];state=rows[0][1]
                for y,value in rows[1:]+[(9999,-1)]:
                    if y==end+1 and value==state:end=y;continue
                    data['Spans'].append(nbtlib.IntArray([q[0]*16+column%16,q[1]*16+column//16,start,end,state]));start=end=y;state=value
            prior=a.out/'before'/relative;target=a.out/'after'/relative;prior.parent.mkdir(parents=True,exist_ok=True);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original,prior);data.save(target,gzipped=True);recipe_count+=1
        print('Composed devices/recipes',file.name,flush=True)
    prior=json.loads((a.terrain/'functional-check.json').read_text('utf8'))['errors']
    errors=[r for r in prior if r[0]!='pending']+errors
    manifest=json.loads((a.terrain/'manifest.json').read_text('utf8'));manifest.update(regions=regions,cells=sum(r['cells']for r in regions),support_extensions=supports,updated_surface_recipes=recipe_count,stations=str(a.stations),road_markings_preserved=markings,restored_building_cells=restored_building_cells)
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=errors,devices_checked=devices_checked,changed_devices=changed_devices,updated_recipes=recipe_count,visual_verified=False),indent=2),'utf8')
    print('Final composition',manifest['cells'],'cells;',len(errors),'issues;',recipe_count,'recipes',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('terrain','stations','gis','frozen','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--proto',action='store_true');p.add_argument('--world',type=Path)
    a=p.parse_args()
    if a.proto:
        if a.world is None:p.error('An explicit installation target is required')
        finalize_proto(a)
    else:finalize(a)
