"""Prepare original actor moves as complete typed entity-region replacements.

No duplicate actors, UUID assignment, world writes, or inferred owner selection.
The caller owns the world lock and commits these files with its geometry stage.
"""
from pathlib import Path
import copy,math,uuid
import nbtlib
from transplant_s22_authority import read_region,parse_chunk,build_region,chunk_blob
from facility_frame_nbt_r52 import actor_in_frame


def identity(tag):
    return str(uuid.UUID(bytes=b''.join((int(v)&0xffffffff).to_bytes(4,'big') for v in tag['UUID'])))


def descendants(tag):
    yield tag
    for child in tag.get('Passengers',[]):yield from descendants(child)


def prepare_actor_files(world,mapping,expected):
    """mapping is exact original root UUID -> authored Frame; expected is SNBT."""
    folder=Path(world)/'dimensions/projectseele/geofront/entities'
    files={};locations={};all_ids=set()
    for path in folder.glob('r.*.mca'):
        if path.stat().st_size==0:continue
        assert not path.is_symlink() and not path.is_junction()
        stamps,blobs=read_region(path);roots={}
        for slot,blob in enumerate(blobs):
            if blob is None:continue
            root=parse_chunk(blob);roots[slot]=root
            for tag in root.get('Entities',[]):
                key=identity(tag)
                for member in descendants(tag):
                    uid=identity(member);assert uid not in all_ids,('Existing duplicate',uid);all_ids.add(uid)
                    if uid in mapping and uid!=key:raise ValueError('Move the complete root/passenger graph, not a detached passenger')
                if key in mapping:
                    assert key not in locations
                    assert tag.snbt()==expected[key],('Original actor state changed',key)
                    locations[key]=(path,slot,tag)
        files[path]=(stamps,blobs,roots)
    assert set(locations)==set(mapping),('Missing original roots',set(mapping)-set(locations))
    dirty=set();moves=[]
    for key,frame in mapping.items():
        path,slot,old=locations[key];new=actor_in_frame(old,frame)
        assert identity(new)==key
        cx,cz=math.floor(float(new['Pos'][0]))//16,math.floor(float(new['Pos'][2]))//16
        target=folder/f'r.{cx//32}.{cz//32}.mca';new_slot=(cx&31)+(cz&31)*32
        if target not in files:
            assert not target.exists() or target.stat().st_size==0
            files[target]=(bytes(4096),[None]*1024,{})
        source_root=files[path][2][slot]
        dest_roots=files[target][2]
        if new_slot not in dest_roots:
            assert set(source_root)<={'DataVersion','Entities','Position'},'Unknown entity chunk fields require explicit migration'
            dest_roots[new_slot]=nbtlib.File({'DataVersion':copy.deepcopy(source_root['DataVersion']),
                'Position':nbtlib.IntArray([cx,cz]),'Entities':nbtlib.List[nbtlib.Compound]()})
        source_root['Entities']=nbtlib.List[nbtlib.Compound]([tag for tag in source_root['Entities'] if identity(tag)!=key])
        # A valid, empty native chunk may encode the list with TAG_End.
        # Appending a Compound requires a typed list, without changing actors.
        dest_roots[new_slot]['Entities']=nbtlib.List[nbtlib.Compound]([*dest_roots[new_slot].get('Entities',[]),new])
        dirty.update(((path,slot),(target,new_slot)))
        changed={name for name in old if old[name].snbt()!=new[name].snbt()}
        assert changed<={'Pos','Rotation','Motion','StaffStation','StaffStationYaw','Passengers',
            'SeeleNervLogisticsYaw','PoseQX','PoseQY','PoseQZ','PoseQW'},changed
        moves.append(dict(uuid=key,type=str(old['id']),before=list(map(float,old['Pos'])),after=list(map(float,new['Pos'])),changed_keys=sorted(changed)))
    result={}
    for path in {path for path,slot in dirty}:
        stamps,blobs,roots=files[path]
        for p,slot in dirty:
            if p==path:blobs[slot]=chunk_blob(roots[slot])
        result[path]=build_region(stamps,blobs)
    after_ids=[]
    for path,(stamps,blobs,roots) in files.items():
        for root in roots.values():
            for tag in root.get('Entities',[]):
                after_ids.extend(identity(member) for member in descendants(tag))
    assert len(after_ids)==len(set(after_ids)) and set(after_ids)==all_ids
    return result,dict(moves=moves,original_id_count=len(all_ids),final_id_count=len(after_ids),all_original_uuids_preserved=True)
