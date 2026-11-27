"""Apply Central/Terminal Dogma to a stopped staged copy, preserving post-749 player edits.

  python build_r66_dogma.py --world STAGE --reference FROZEN_749 --out RECEIPTS [--apply]

The reference is immutable and may be a minimal world containing just both GeoFront
region files. All changed chunks are prepared and reread privately before replacement.
A partially completed multi-file install can be rerun without replacing newer blocks.
"""
import argparse
import hashlib
import json
import os
import time
from contextlib import nullcontext
from pathlib import Path

import nbtlib
import numpy as np

from install_r53_carrier_trays import stopped_world
from map_buildings.mca import World
from r66_dogma_geometry import AIR, LOW, build
from write_deep_cells import REGION, clear_light, decode, encode, read_chunk, sign_entity, write_chunk


def digest(data):
    return hashlib.sha256(data).hexdigest()


def palette_strings(sec):
    return decode(sec['block_states']) if sec is not None and 'block_states' in sec else (np.zeros(4096,dtype=int),[AIR])


def positions(cx,cy,cz,indices):
    return [(cx*16+int(i%16),cy*16+int(i//256),cz*16+int(i//16%16)) for i in indices]


def root_entities(root):
    return {(int(e['x']),int(e['y']),int(e['z'])):e for e in root.get('block_entities',[])}


def run(world, reference, out, apply):
    lock = stopped_world(world) if apply and (world/'session.lock').exists() else nullcontext()
    with lock:
        return build_stopped(world,reference,out,apply)


def build_stopped(world, reference, out, apply):
    started=time.perf_counter()
    world,reference=world.resolve(),reference.resolve()
    if world==reference:
        raise ValueError('Stage and reference must be independent directories')
    out.mkdir(parents=True,exist_ok=True)
    ref=World(reference/REGION)
    current=World(world/REGION)
    prior_collar=(current.get(146,-1054,242)=='minecraft:chiseled_polished_blackstone'
                  and all(current.get(145,y,z)==AIR for y in range(LOW+1,LOW+64) for z in range(231,254)))
    opening=sum(current.get(x,-1202,258)==AIR for x in range(18,43))
    from r66_dogma_geometry import door_block
    for x in range(16,45):
        if current.get(x,-1202,258)!=door_block(x,-1202,258,opening):
            raise ValueError('Door leaves have a nonstandard pattern; stage was not modified')
    design=build(ref,opening)
    cases={}
    for cx,cz,cy in design.sections:
        cases.setdefault((cx>>5,cz>>5),{}).setdefault((cx,cz),[]).append(cy)
    allowed_air={'minecraft:air','minecraft:cave_air','minecraft:void_air'}
    identifiers={s:i for i,s in enumerate(design.names)}
    def intern(s):
        if s not in identifiers:
            identifiers[s]=len(identifiers)
        return identifiers[s]
    # Treat cave/void air as equivalent only when the requested state is ordinary air.
    air_ids=[intern(s) for s in allowed_air]
    names=design.names
    prepared=[]
    stats={'cells':0,'chunks':0,'signs':0,'conflicts':[],'regions':{},'opening':opening}
    for rk,chunks in sorted(cases.items()):
        filename=f'r.{rk[0]}.{rk[1]}.mca'
        fpath=world/REGION/filename
        before=fpath.read_bytes()
        target=bytearray(before)
        refbuf=(reference/REGION/filename).read_bytes()
        for (cx,cz),section_keys in sorted(chunks.items()):
            index,loc,count,root=read_chunk(target,cx,cz)
            refroot=read_chunk(refbuf,cx,cz)[3]
            secs={int(s['Y']):s for s in root['sections']}
            refsecs={int(s['Y']):s for s in refroot['sections']}
            entities=root_entities(root)
            refentities=root_entities(refroot)
            changed_sections={}
            chunk_signs={}
            for cy in sorted(section_keys):
                mask=design.sections[cx,cz,cy].reshape(-1)
                idx=np.flatnonzero(mask)
                desired=mask[idx].astype(int)
                sid,pal=palette_strings(secs.get(cy));rid,rpal=palette_strings(refsecs.get(cy))
                current_ids=np.array([intern(s) for s in pal])[sid]
                ref_ids=np.array([intern(s) for s in rpal])[rid]
                actual=current_ids[idx]
                dirty=(actual!=desired)&~((desired==identifiers[AIR])&np.isin(actual,air_ids))
                # Record user edits even if the plan would otherwise accept the reference palette.
                bad=dirty&(actual!=ref_ids[idx])
                # The first 750 collar carved exactly this face to ordinary air.
                # Accept only that known former output on an already installed shaft.
                if prior_collar and cx==145>>4 and cz in (231>>4,253>>4):
                    former_gap=((idx%16==145%16)&(cz*16+idx//16%16>=231)&(cz*16+idx//16%16<=253)
                               &(cy*16+idx//256>LOW)&(cy*16+idx//256<=LOW+63))
                    bad &= ~(former_gap & (actual==identifiers[AIR]))
                for at in np.flatnonzero(bad)[:12]:
                    pos=positions(cx,cy,cz,[idx[at]])[0]
                    stats['conflicts'].append([pos,pal[sid[idx[at]]],rpal[rid[idx[at]]],names[desired[at]]])
                sign_positions=[p for p in design.signs if p[0]>>4==cx and p[2]>>4==cz and p[1]>>4==cy]
                for pos in sign_positions:
                    s=design.signs[pos]
                    want=sign_entity(s,'minecraft:warped_wall_sign')
                    if pos in entities and entities[pos]!=want and entities[pos]!=refentities.get(pos):
                        stats['conflicts'].append([pos,'modified sign'])
                    if entities.get(pos)!=want:
                        chunk_signs[pos]=want
                for pos,entity in entities.items():
                    if pos[1]>>4!=cy: continue
                    local=((pos[1]&15)*256+(pos[2]&15)*16+(pos[0]&15))
                    if mask[local] and current_ids[local]!=mask[local] and pos not in design.signs:
                        stats['conflicts'].append([pos,'block entity',str(entity['id']),names[mask[local]]])
                if not np.any(dirty):
                    continue
                if cy not in secs:
                    raise ValueError(f'Missing section {cx},{cy},{cz}')
                changed_idx=idx[dirty]; changed=desired[dirty]
                extended=list(pal)
                local_ids={}
                for wanted in np.unique(changed):
                    state=names[wanted]
                    if state not in extended: extended.append(state)
                    local_ids[wanted]=extended.index(state)
                changed_ids=sid.copy()
                for wanted,pi in local_ids.items(): changed_ids[changed_idx[changed==wanted]]=pi
                encode(secs[cy]['block_states'],changed_ids,extended)
                changed_sections[cy]=np.array([intern(s) for s in extended])[changed_ids]
                stats['cells']+=len(changed_idx)
            if not changed_sections and not chunk_signs: continue
            for pos,tag in chunk_signs.items():
                if pos in entities: root['block_entities'].remove(entities[pos])
                root['block_entities'].append(tag)
                stats['signs']+=1
            clear_light(root)
            write_chunk(target,index,loc,count,root)
            read=read_chunk(target,cx,cz)[3]
            readsecs={int(s['Y']):s for s in read['sections']}
            for cy,expected in changed_sections.items():
                ids,pal=palette_strings(readsecs[cy])
                assert np.array_equal(np.array([intern(s) for s in pal])[ids],expected),(cx,cy,cz)
            verified=root_entities(read)
            assert all(verified.get(p)==t for p,t in chunk_signs.items())
            assert all(verified.get(p)==t for p,t in entities.items() if p not in chunk_signs)
            stats['chunks']+=1
        orig=digest(before)
        if target!=before:
            tmp=out/(filename+'.ready')
            tmp.write_bytes(target)
            assert digest(tmp.read_bytes())==digest(target)
            prepared.append((fpath,tmp,orig))
        stats['regions'][filename]={'before':orig,'after':digest(target)}
    if not stats['conflicts'] and apply:
        # Recheck all inputs together before committing the per-region atomic replacements.
        for path,tmp,orig in prepared:
            if digest(path.read_bytes())!=orig:
                raise RuntimeError(f'Stage changed during preflight: {path}')
        for path,tmp,orig in prepared:
            install=path.with_name(path.name+'.r66-dogma.tmp')
            install.write_bytes(tmp.read_bytes())
            os.replace(install,path)
    stats['seconds']=round(time.perf_counter()-started,2)
    stats['applied']=bool(apply and not stats['conflicts'])
    (out/'installation.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False),'utf8')
    print(json.dumps({**stats,'conflicts':stats['conflicts'][:12]},ensure_ascii=False))
    if stats['conflicts']: raise SystemExit('Conflicts found. Inspect installation.json. No staged region was replaced.')
    return stats


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    run(a.world,a.reference,a.out,a.apply)
