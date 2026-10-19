"""Move the user-selected obstructing command officer to the side of the same dais.

No blocks, UUIDs, commands or entity positions are changed. The existing officer
walks to the new persisted post on load through the normal return-to-post AI.
"""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,msvcrt
import nbtlib
from query_blocks import read_box
from transplant_s22_authority import read_region,parse_chunk,build_region,chunk_blob
from apply_s20_approved_semantic_repairs import atomic_replace
from facility_frame_nbt_r52 import pack_position,unpack_position
from move_component_actors_r52 import identity,descendants

OLD=(32,-502,287)
NEW=(25,-502,283)
UID='9314a59b-b93c-45da-8aa7-691658deefc3'
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(v):return (json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def runtime_reference(w,old_sha,new_sha):
    p=w/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat';before=p.read_bytes();tag=nbtlib.load(p);old=copy.deepcopy(tag)
    assert str(tag['data']['InstallationBundleSHA'])==old_sha
    assert 'PendingInstallation'not in tag['data']
    tag['data']['InstallationBundleSHA']=nbtlib.String(new_sha)
    inverse=copy.deepcopy(tag);inverse['data']['InstallationBundleSHA']=old['data']['InstallationBundleSHA']
    assert inverse.snbt()==old.snbt()
    stream=io.BytesIO();tag.write(stream)
    return p,before,gzip.compress(stream.getvalue(),mtime=0)

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('world',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--apply',action='store_true');ap.add_argument('--finish-reference',action='store_true');a=ap.parse_args()
    w=a.world;out=a.output
    with(w/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        if a.finish_reference:
            assert (out/'INSTALLED.json').exists()
            p,b,v=runtime_reference(w,sha((out/'before/ROOT_ASSEMBLY_BUNDLE.json').read_bytes()),sha((w/'ROOT_ASSEMBLY_BUNDLE.json').read_bytes()))
            backup=out/'runtime_reference_before.dat';assert not backup.exists();backup.write_bytes(b)
            atomic_replace(p,v);assert p.read_bytes()==v
            (out/'RUNTIME_REFERENCE_INSTALLED.json').write_bytes(enc(dict(path=p.relative_to(w).as_posix(),before=sha(b),after=sha(v),only_bundle_reference_changed=True)))
            print('Saved bundle reference rebound; complete inverse NBT equality verified');return
        assert not out.exists(),'Use a fresh evidence directory'
        out.mkdir();(out/'before').mkdir();(out/'candidate').mkdir()
        # Existing main_command staffing area, explicitly authorized for moving
        # this officer aside. The floor check is clearance, not room inference.
        cells=read_box(w,'projectseele:geofront',(24,-503,282),(26,-500,284))
        assert cells[25,-503,283]=='minecraft:white_concrete'
        assert all(cells[25,y,283]in {'minecraft:air','minecraft:cave_air'}for y in (-502,-501,-500))
        edits=[]
        def add(p,before,after):
            rel=p.relative_to(w);dest=out/'before'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(before)
            dest=out/'candidate'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(after);edits.append((p,before,after))
        roster_path=w/'nerv_staff_r15.json';raw=roster_path.read_bytes();roster=json.loads(raw)
        row=next(r for r in roster['stations']if r['id']=='aoba');assert tuple(row['feet'])==OLD and row['room']=='main_command'
        assert not any(r['feet']==list(NEW)for r in roster['stations'])
        row['feet']=list(NEW);row['yaw']=-90.;add(roster_path,raw,enc(roster))
        owner_path=w/'ROOT_MECHANICAL_OWNER.json';raw=owner_path.read_bytes();old_owner=sha(raw);owner=json.loads(raw)
        row=next(r for r in owner['staff']if r['id']=='aoba');assert tuple(row['feet'])==OLD and row['original_uuid']==UID
        row['feet']=list(NEW);row['yaw']=-90.;row['support']=[dict(position=[25,-503,283],state=cells[25,-503,283])]
        new_owner=enc(owner);add(owner_path,raw,new_owner)
        bundle_path=w/'ROOT_ASSEMBLY_BUNDLE.json';raw=bundle_path.read_bytes();bundle=json.loads(raw)
        assert bundle['mechanical_owner']['sha256']==old_owner
        bundle['mechanical_owner']['sha256']=sha(new_owner);new_bundle=enc(bundle);add(bundle_path,raw,new_bundle)
        add(*runtime_reference(w,sha(raw),sha(new_bundle)))
        # This post and the new post are in the same entity region. Position is
        # deliberately retained so the actor walks instead of teleporting.
        p=w/'dimensions/projectseele/geofront/entities/r.0.0.mca';before=p.read_bytes();ts,blobs=read_region(p);found=0;proof={}
        for i,blob in enumerate(blobs):
            if blob is None:continue
            tag=parse_chunk(blob);oldtag=copy.deepcopy(tag);dirty=False
            for parent in tag.get('Entities',[]):
                for e in descendants(parent):
                    if str(e.get('id'))!='projectseele:nerv_staff'or str(e.get('StaffId'))!='aoba':continue
                    found+=1;assert identity(e)==UID and unpack_position(e['StaffStation'])==OLD
                    original=copy.deepcopy(e);old_yaw=e['StaffStationYaw'];e['StaffStation']=pack_position(NEW);e['StaffStationYaw']=nbtlib.Float(-90.)
                    reverted=copy.deepcopy(e);reverted['StaffStation']=original['StaffStation'];reverted['StaffStationYaw']=old_yaw
                    assert reverted.snbt()==original.snbt()
                    proof=dict(uuid=UID,old_station=OLD,new_station=NEW,entity_position_unchanged=list(map(float,e['Pos'])),all_other_entity_nbt_unchanged=True)
                    dirty=True
            if dirty:
                blobs[i]=chunk_blob(tag);roundtrip=parse_chunk(blobs[i]);assert roundtrip.snbt()==tag.snbt()
        assert found==1
        add(p,before,build_region(ts,blobs))
        report=dict(user_authorized_post_move=True,voxel_changes=0,identity_and_progress_preserved=True,proof=proof,
                    files=[dict(path=p.relative_to(w).as_posix(),before=sha(b),after=sha(v))for p,b,v in edits],
                    native_walk_and_restart_verification_pending=True)
        (out/'PLAN.json').write_bytes(enc(report))
        if a.apply:
            changed=[]
            try:
                for p,b,v in edits:
                    assert p.read_bytes()==b;atomic_replace(p,v);changed.append((p,b));assert p.read_bytes()==v
            except BaseException:
                for p,b in reversed(changed):atomic_replace(p,b)
                raise
            (out/'INSTALLED.json').write_bytes(enc(report|dict(exact_readback=True)))
        print(json.dumps(report['proof']))
if __name__=='__main__':main()
