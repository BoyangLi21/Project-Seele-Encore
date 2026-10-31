"""Reconcile modified candidate chunks with existing future-city recipes."""
import argparse,json,shutil
from pathlib import Path
from collections import defaultdict
import nbtlib
import numpy as np
from author_hakone_lakefront import Editor
from apply_s20_approved_semantic_repairs import parse_state
from query_blocks import iter_block_entities
from hakone_earthworks import road_blocks
from plan_hakone_main_districts import ROAD_MATERIALS
from plan_ashi_landscape_r54 import NATURAL

DATA=Path('dimensions/projectseele/geofront/data')


def refresh(a):
    manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    selected=set(map(tuple,json.loads((a.candidate/'transport-changed-chunks.json').read_text('utf8'))))
    check=json.loads((a.candidate/'functional-check.json').read_text('utf8'));errors=[];classified=check.get('classified_decks',[]);editor=Editor(a.candidate)
    for error in check['errors']:
        if a.reapply_interfaces and error[0].startswith('city-interface-'):continue
        if error[0]!='support-bearing':errors.append(error);continue
        _,kind,x,y,z,base=error
        # Verify these entries really were horizontal station decking in the
        # recorded source. Never extend a deck through a hall or footpath.
        stem=[]
        for Y in range(y+1,min(319,y+17)):
            name=editor.state(x,Y,z,original=True).split('[')[0]
            if name=='minecraft:light_gray_concrete':stem.append(Y)
            elif stem:break
        if kind=='viaduct' and 0<len(stem)<4:classified.append(dict(pos=[x,y,z],original_deck=stem,bearing=base))
        else:errors.append(error)
    paths=manifest.get('road_interfaces',[]);checked=0
    for route in paths:
        cells={};dist={};path=route['path'];centre={(x,z):g for x,g,z in path}
        for x,g,z in path:
            for dx in range(-4,5):
                for dz in range(-4,5):
                    q=x+dx,z+dz;d=max(abs(dx),abs(dz))
                    if d<dist.get(q,99):cells[q]=centre.get(q,g);dist[q]=d
        for(x,z),g in cells.items():
            y,slab=map(int,road_blocks(np.array(round(g*2))))
            if a.reapply_interfaces:
                allowed=NATURAL|{'minecraft:gray_concrete','minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone','minecraft:smooth_stone_slab','projectseele:road_asphalt_slab','projectseele:road_marking_slab','minecraft:yellow_concrete','minecraft:yellow_terracotta','minecraft:polished_blackstone_slab','minecraft:stone_brick_stairs'}
                for Y in range(y-1,y+5):
                    s=editor.state(x,Y,z).split('[')[0]
                    if Y<=y and s=='minecraft:light_gray_concrete':continue
                    if s not in allowed:raise ValueError(('Original street handoff now reaches a structure',x,Y,z,s))
                material='minecraft:smooth_stone'if dist[x,z]>2 else'minecraft:gray_concrete'
                if slab:material='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'if dist[x,z]>2 else'projectseele:road_asphalt_slab[type=bottom,waterlogged=false]'
                editor.put(x,y-1,z,'minecraft:stone');editor.put(x,y,z,material)
                for Y in range(y+1,y+5):editor.put(x,Y,z,'minecraft:air')
                selected.add((x//16,z//16))
            floor=editor.state(x,y,z)
            if floor.split('[')[0]not in ROAD_MATERIALS|{'minecraft:gray_concrete','minecraft:smooth_stone_slab'}:errors.append(['city-interface-floor',route['id'],x,y,z,floor])
            for Y in(y+1,y+2):
                s=editor.state(x,Y,z)
                if s not in ('minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light'):errors.append(['city-interface-body',route['id'],x,Y,z,s])
            checked+=1
        if a.reapply_interfaces:
            for i,(x,g,z)in enumerate(path):
                y,slab=map(int,road_blocks(np.array(round(g*2))))
                if i%12<5:editor.put(x,y,z,'projectseele:road_marking_slab[type=bottom,waterlogged=false]'if slab else'minecraft:white_concrete')
    if a.reapply_interfaces:
        regions=editor.save();manifest.update(regions=regions,cells=sum(r['cells']for r in regions))
        (a.candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    editor.regions.clear();devices=0;recipes=0
    for file in sorted((a.candidate/'delta').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:]);local={p for p in selected if p[0]//32==rx and p[1]//32==rz}
        if not local:continue
        with np.load(file)as f:co,ra,at,values,names=(f[k]for k in('coordinates','ranges','indices','after','palette'))
        rows={tuple(map(int,q)):i for i,q in enumerate(co)}
        for pos,tag in iter_block_entities(a.frozen,'projectseele:geofront',(rx*512,-128,rz*512),(rx*512+511,319,rz*512+511),selected_chunks=local):
            devices+=1;q=pos[0]//16,pos[2]//16
            if q not in rows:continue
            i=rows[q];start,end=ra[i:i+2];offset=(pos[1]+128)*256+(pos[2]%16)*16+pos[0]%16
            j=np.searchsorted(at[start:end],offset)
            if j<end-start and at[start+j]==offset:errors.append(['completion-device-touched',*pos])
        for q in local:
            rel=DATA/'city_rigid_generation_r45/surface'/f'{q[0]}_{q[1]}.dat';original=a.frozen/rel
            if not original.exists():continue
            data=nbtlib.load(original);palette=data['Palette'];lookup={str(s['Name'])+str(s.get('Properties',{})):j for j,s in enumerate(palette)}
            if q in rows:
                i=rows[q];start,end=ra[i:i+2];offsets=at[start:end];vs=values[start:end];remap={}
                for v in np.unique(vs):
                    s=parse_state(str(names[v]));k=str(s['Name'])+str(s.get('Properties',{}))
                    if k not in lookup:lookup[k]=len(palette);palette.append(s)
                    remap[int(v)]=lookup[k]
                columns=defaultdict(list)
                for offset,v in zip(offsets,vs):columns[int(offset)%256].append((int(offset)//256-128,remap[int(v)]))
                for col,rs in columns.items():
                    rs.sort();lo=hi=rs[0][0];s=rs[0][1]
                    for y,v in rs[1:]+[(9999,-1)]:
                        if y==hi+1 and v==s:hi=y;continue
                        data['Spans'].append(nbtlib.IntArray([q[0]*16+col%16,q[1]*16+col//16,lo,hi,s]));lo=hi=y;s=v
            prior=a.candidate/'before'/rel;out=a.candidate/'after'/rel
            prior.parent.mkdir(parents=True,exist_ok=True);out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original,prior);data.save(out,gzipped=True);recipes+=1
        print('Refreshed recipe region',file.name,flush=True)
    folder=a.candidate/'preserved';folder.mkdir(exist_ok=True)
    for f in(a.frozen/DATA).glob('*control*.dat'):shutil.copy2(f,folder/f.name)
    check.update(errors=errors,completion_devices_checked=devices,updated_recipes_after_transport=recipes,city_interface_full_width_columns=checked,classified_decks=classified)
    (a.candidate/'functional-check.json').write_text(json.dumps(check,indent=2),'utf8')
    print('Completion checks: devices',devices,'road columns',checked,'recipes',recipes,'errors',len(errors),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('candidate','frozen'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--reapply-interfaces',action='store_true')
    refresh(p.parse_args())
