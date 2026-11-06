"""Root explicit creation of two additional NERV airframes on measured stands."""
import json,uuid,hashlib,copy,msvcrt,time,argparse
from pathlib import Path
import nbtlib
from r52_spatial_plan import BASE
from transplant_s22_authority import read_region,parse_chunk,build_region
from apply_s20_approved_semantic_repairs import atomic_replace,chunk_blob
from extend_world_depth_r52 import acquire_world_lock


def key(tag):
    a=tag.get('UUID')
    if a is None:return None
    return str(uuid.UUID(bytes=b''.join((int(x)&0xffffffff).to_bytes(4,'big')for x in a)))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';out=BASE/'underground_airport_expansion/aircraft';out.mkdir(exist_ok=True)
    assert not(out/'APPLIED.json').exists(),'Additional aircraft already installed'
    civil=BASE/'underground_airport_expansion/three_original_style_stands/PLAN.json';receipt=json.loads(civil.read_text('utf8'));assert receipt['world_written']and receipt['whole_apron_exact_readback']
    planes=[]
    for serial,x in ((52,-640),(53,-840)):
        uid=uuid.uuid5(uuid.NAMESPACE_URL,f'projectseele:r52:underground-aircraft:serial:{serial}');chunks=[int.from_bytes(uid.bytes[i:i+4],'big',signed=True)for i in range(0,16,4)]
        tag=nbtlib.Compound(id=nbtlib.String('projectseele:un_transport'),UUID=nbtlib.IntArray(chunks),
            Pos=nbtlib.List[nbtlib.Double]([x,-464,-270]),Motion=nbtlib.List[nbtlib.Double]([0,0,0]),Rotation=nbtlib.List[nbtlib.Float]([0,0]),
            NoGravity=nbtlib.Byte(1),Invulnerable=nbtlib.Byte(1),Air=nbtlib.Short(300),Fire=nbtlib.Short(-1),FallDistance=nbtlib.Float(0),PortalCooldown=nbtlib.Int(0),OnGround=nbtlib.Byte(0),
            NervAircraft=nbtlib.Byte(1),UNSerial=nbtlib.Int(serial),Cargo=nbtlib.Byte(0),Kind=nbtlib.Int(0),Deploy=nbtlib.Float(0),HoistDistance=nbtlib.Float(112),
            ForgeData=nbtlib.Compound(R52RootAircraftCivilSHA256=nbtlib.String(hashlib.sha256(civil.read_bytes()).hexdigest())))
        planes.append(dict(uuid=str(uid),serial=serial,stand=[x,-464,-270],nbt=tag))
    ids={row['uuid']for row in planes};assert len(ids)==2;existing=0
    entity_dir=world/'dimensions/projectseele/geofront/entities'
    for path in entity_dir.glob('r.*.mca'):
        if not path.stat().st_size:continue
        for blob in read_region(path)[1]:
            if blob is None:continue
            for tag in parse_chunk(blob).get('Entities',[]):assert key(tag)not in ids,'Additional identity already exists';existing+=1
    path=entity_dir/'r.-2.-1.mca';before=path.read_bytes()if path.is_file()else None
    assert before is None or len(before)==0 or len(before)>=8192,'Truncated nonempty entity region'
    stamps,blobs=read_region(path)if before else(bytes(4096),[None]*1024);stamps=bytearray(stamps);previous=list(blobs);touched=set()
    for row in planes:
        cx=int(row['stand'][0]//16);cz=-270//16;index=cx%32+32*(cz%32);touched.add(index)
        tag=parse_chunk(blobs[index])if blobs[index]is not None else nbtlib.File(dict(DataVersion=nbtlib.Int(3465),Position=nbtlib.IntArray([cx,cz]),Entities=nbtlib.List[nbtlib.Compound]()))
        assert list(map(int,tag['Position']))==[cx,cz];original=[x.snbt()for x in tag['Entities']];tag['Entities'].append(row['nbt'])
        assert[x.snbt()for x in tag['Entities'][:-1]]==original
        blobs[index]=chunk_blob(tag)
        decoded=parse_chunk(blobs[index]);assert decoded.snbt()==tag.snbt(),'Native entity root encoding differs'
        stamps[index*4:index*4+4]=int(time.time()).to_bytes(4,'big')
    after=build_region(bytes(stamps),blobs)
    report=dict(world_written=False,original_geofront_entities_count=existing,new_aircraft=2,original_entities_retained=True,source_civil=str(civil),
        aircraft=[dict(uuid=r['uuid'],serial=r['serial'],stand=r['stand'],yaw=0,type='projectseele:un_transport',nerv=True,nbt=r['nbt'].snbt())for r in planes],
        before_region_sha256=None if before is None else hashlib.sha256(before).hexdigest(),after_region_sha256=hashlib.sha256(after).hexdigest(),
        region=str(path.relative_to(world)),flight_commissioned=False)
    (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items()if k!='aircraft'}),flush=True)
    if args.apply:
        lock=acquire_world_lock()
        try:
            assert(path.read_bytes()if path.is_file()else None)==before
            if before is not None:(out/'entity_region_before.mca').write_bytes(before)
            path.parent.mkdir(parents=True,exist_ok=True);atomic_replace(path,after)
            actual=read_region(path)[1];found=[]
            for i in range(1024):
                if i not in touched:assert actual[i]==previous[i]
                elif actual[i]is not None:found.extend(key(t)for t in parse_chunk(actual[i])['Entities']if key(t)in ids)
            assert set(found)==ids and len(found)==2
            report.update(world_written=True,actual_uuid_readback=True);(out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8')
        except BaseException:
            if path.is_file()and hashlib.sha256(path.read_bytes()).hexdigest()==hashlib.sha256(after).hexdigest():
                atomic_replace(path,before if before is not None else b'')
            raise
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
