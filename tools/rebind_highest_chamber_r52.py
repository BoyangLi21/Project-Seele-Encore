"""Translate the complete inherited chamber authority after checking its actual moved images."""
import argparse,copy,hashlib,json,msvcrt
from pathlib import Path
import nbtlib
from facility_frame_nbt_r52 import pack_position,unpack_position,block_entity_in_frame
from r52_spatial_plan import BASE,PYRAMID
from query_blocks import read_box,iter_block_entities
from regional_voxels import canonical_state
from prepare_pyramid_move_r52 import encoded
from apply_s20_approved_semantic_repairs import atomic_replace

SOURCE=(BASE/'WORLD_R52').resolve()
QA=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game/saves/SEELE_R52_REVIEW').resolve()
NAME='dimensions/projectseele/geofront/data/projectseele_dead_sea_chamber_r45.dat'


def state(tag):
    name=str(tag['Name']);props=tag.get('Properties',{})
    return canonical_state(name+('['+','.join(str(k)+'='+str(v)for k,v in props.items())+']'if props else''))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,default=SOURCE);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=args.world.resolve();assert world in(SOURCE,QA)
    path=world/NAME;before=path.read_bytes();document=nbtlib.load(path);old=document['data'];d=copy.deepcopy(old)
    assert int(d.get('FrameOffsetYR52',0))==0 and unpack_position(d['Gate'])==(32,-329,340)
    assert str(d['ChamberId'])=='r45/dead_sea/highest_tree_chamber' and len(d['Images'])==10 and len(d['Readers'])==2
    assert str(d['Mode'])=='CLOSED'or(str(d['Mode'])=='FAULT'and str(d.get('Fault',''))=='java.lang.IllegalStateException: Highest-room reader binding/clearance changed')
    d['Gate']=pack_position(PYRAMID.block(unpack_position(d['Gate'])));d['FrameOffsetYR52']=nbtlib.Int(-93)
    checks=[]
    for image in d['Images']:
        q=PYRAMID.block(unpack_position(image['Pos']));image['Pos']=pack_position(q)
        actual=read_box(world,'projectseele:geofront',q,q)[q];assert actual==state(image['State']),(q,actual,state(image['State']))
        bes=dict(iter_block_entities(world,'projectseele:geofront',q,q))
        if 'NBT'in image:
            image['NBT']=block_entity_in_frame(image['NBT'],PYRAMID)
            assert q in bes
            current=copy.deepcopy(bes[q]);expected=copy.deepcopy(image['NBT'])
            # Region packing is the sole permitted serialization envelope.
            for tag in(current,expected):
                if int(tag.get('keepPacked',0))==0:tag.pop('keepPacked',None)
            assert current==expected,('Full artwork image changed',q,current,expected)
        else:assert not bes
        checks.append(dict(position=q,state=actual,complete_NBT_matched=True))
    for reader in d['Readers']:
        q=PYRAMID.block(unpack_position(reader['Pos']));reader['Pos']=pack_position(q)
        actual=read_box(world,'projectseele:geofront',q,q)[q];t=dict(iter_block_entities(world,'projectseele:geofront',q,q))[q]
        assert 'facing='+str(reader['Facing'])in actual and str(t['ChamberRole'])==str(reader['Role'])
        assert t['Gate']==d['Gate']and int(t['Exit'])==0 and int(t['Width'])==int(t['Height'])==3 and int(t['Clearance'])==3 and bool(t['AlongX'])and bool(t['Linked'])
    d['Mode']=nbtlib.String('CLOSED');d['Fault']=nbtlib.String('');d['OpenUntil']=nbtlib.Long(0);d['SafetyHeld']=nbtlib.Byte(0)
    document['data']=d;after=encoded(document);out=BASE/'highest_chamber_rebind'/('source'if world==SOURCE else'used_qa')
    out.mkdir(parents=True,exist_ok=True);assert not(out/'APPLIED.json').exists()
    (out/'before.dat').write_bytes(before);(out/'candidate.dat').write_bytes(after)
    report=dict(world=str(world),world_written=False,translated_images=10,original_two_readers_preserved=True,frame_offset_y=-93,
        complete_image_checks=checks,before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(after).hexdigest(),
        previous_mode=str(old['Mode']),fault_reset_only_after_all_images_and_readers_match=True,native_verified=False)
    if args.apply:
        lock=(world/'session.lock').open('r+b');msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            assert path.read_bytes()==before;atomic_replace(path,after);assert path.read_bytes()==after
            actual=nbtlib.load(path)['data'];assert actual==d
            report['world_written']=True
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (out/('APPLIED.json'if args.apply else'PLAN.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k!='complete_image_checks'},ensure_ascii=False))


if __name__=='__main__':main()
