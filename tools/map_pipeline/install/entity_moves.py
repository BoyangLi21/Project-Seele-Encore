"""Stage exact-NBT actor translations for the map installer's rollback journal."""
import copy,math
from pathlib import Path
import nbtlib
from transplant_s22_authority import read_region,parse_chunk,build_region
from apply_s20_approved_semantic_repairs import chunk_blob,atomic_replace

ENTITIES=Path('dimensions/projectseele/geofront/entities')


def identity(tag):
    return tuple(map(int,tag['UUID']))


def identities(tag):
    yield identity(tag)
    for child in tag.get('Passengers',[]):yield from identities(child)


def translated(tag,delta):
    if len(delta)!=3 or any(not math.isfinite(float(d))for d in delta):raise ValueError('Invalid actor translation')
    if len(tag.get('Pos',[]))!=3 or any(not math.isfinite(float(v))for v in tag['Pos']) or len(tag.get('UUID',[]))!=4:
        raise ValueError('Malformed actor position or identity')
    # Active paths/tows need their own explicit coordinate transform; a parked
    # facility migration must not accidentally change an ongoing vehicle trip.
    if tag.get('LoiterActive',0) or tag.get('Radius',0) or tag.get('TowedByUUID','') or tag.get('TowingUUID','') or tag.get('TowingUUIDs',[]):
        raise ValueError('Active vehicle movement needs an explicit migration')
    empty_brain=tag.get('Brain',{}) in ({},{'memories':{}})
    if any(k in tag for k in ('TileX','TileY','TileZ','Leash')) or not empty_brain:
        raise ValueError('Spatial actor metadata needs an explicit migration')
    result=copy.deepcopy(tag)
    result['Pos']=nbtlib.List[nbtlib.Double]([float(v)+float(d)for v,d in zip(tag['Pos'],delta)])
    if 'Passengers'in tag:result['Passengers']=nbtlib.List[nbtlib.Compound]([translated(p,delta)for p in tag['Passengers']])
    return result


def prepare(candidate,world,stage,manifest):
    name=manifest.get('entity_moves')
    if name is None:return [],dict(roots=0,identities=0)
    relative=Path(name)
    if relative.is_absolute()or '..'in relative.parts:raise ValueError('Unsafe actor move packet')
    rows=nbtlib.load(candidate/relative)['Moves'];moves={};wanted=set()
    for row in rows:
        old,new,delta=row['Before'],row['After'],row['Delta'];uid=identity(old)
        if translated(old,delta)!=new:raise ValueError('Actor move changes content beyond its exact translation')
        ids=list(identities(old))
        if len(set(ids))!=len(ids)or wanted.intersection(ids):raise ValueError('Duplicate selected actor identity')
        wanted.update(ids);moves[uid]=(old,new)
    if not moves:raise ValueError('Empty actor move packet')
    regions={};found={};all_ids=set()
    for path in sorted((world/ENTITIES).glob('*.mca')):
        if path.stat().st_size==0:continue
        _,rx,rz=path.stem.split('.');key=int(rx),int(rz);times,raw=read_region(path);regions[key]=[times,raw,{}]
        for slot,blob in enumerate(raw):
            if blob is None:continue
            root=parse_chunk(blob)
            for entity in root.get('Entities',[]):
                ids=list(identities(entity));dupes=all_ids.intersection(ids)
                if dupes or len(ids)!=len(set(ids)):raise ValueError('Existing duplicate actor identity')
                all_ids.update(ids);uid=identity(entity)
                if uid in moves:
                    if entity!=moves[uid][0]:raise ValueError('Current actor changed since capture')
                    found[uid]=(key,slot,root)
    if set(found)!=set(moves):raise ValueError('Selected original actor is missing or is nested under another actor')
    dirty=set()
    def mutable(key,slot,template=None):
        if key not in regions:regions[key]=[bytes(4096),[None]*1024,{}]
        times,raw,changed=regions[key]
        if slot not in changed:
            if raw[slot] is not None:changed[slot]=parse_chunk(raw[slot])
            else:
                cx=key[0]*32+slot%32;cz=key[1]*32+slot//32
                changed[slot]=nbtlib.File({'DataVersion':copy.deepcopy(template['DataVersion']),
                    'Position':nbtlib.IntArray([cx,cz]),'Entities':nbtlib.List[nbtlib.Compound]()})
        dirty.add(key);return changed[slot]
    for uid,(old,new)in moves.items():
        key,slot,template=found[uid];root=mutable(key,slot)
        root['Entities']=nbtlib.List[nbtlib.Compound]([e for e in root['Entities']if identity(e)!=uid])
        cx,cz=math.floor(float(new['Pos'][0]))//16,math.floor(float(new['Pos'][2]))//16
        target=mutable((cx//32,cz//32),(cz%32)*32+cx%32,template)
        target['Entities'].append(copy.deepcopy(new))
    plans=[];after_ids=set();translated_roots={}
    for key,(times,raw,changed)in regions.items():
        for slot,root in changed.items():raw[slot]=chunk_blob(root)
        for blob in raw:
            if blob is None:continue
            for entity in parse_chunk(blob).get('Entities',[]):
                ids=list(identities(entity))
                if after_ids.intersection(ids):raise ValueError('Migration duplicated an actor')
                after_ids.update(ids)
                if identity(entity)in moves:translated_roots[identity(entity)]=entity
        if key in dirty:
            rel=ENTITIES/f'r.{key[0]}.{key[1]}.mca';out=stage/rel;out.parent.mkdir(parents=True,exist_ok=True)
            atomic_replace(out,build_region(times,raw));plans.append((world/rel,out))
    if after_ids!=all_ids or any(translated_roots[k]!=v[1]for k,v in moves.items()):raise ValueError('Actor conservation or full-NBT readback failed')
    return plans,dict(roots=len(moves),identities=len(wanted),all_original_identities_preserved=True,unselected_actor_nbt_preserved=True,regions=len(plans))
