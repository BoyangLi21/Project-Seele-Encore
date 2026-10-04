"""Root-only exact archive/marker migration, separate from static block replay.

Default verify is read-only. Explicit --stage-root / --finish-root / --rollback-root
are for the single Root world writer after cold/exclusive guard. This tool never
edits region, entity, player, quest or transport data, never installs a mod.
"""
from pathlib import Path
import argparse,copy,datetime,hashlib,json,os,shutil,tempfile
import nbtlib
import numpy as np
from release_combat_r36 import guard
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,palette_state
from measure_city_placements_r45 import unpack_pos
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()if path.exists()else None

def same_tag(a,b):
    if a is None or b is None:return a is b
    if type(a)is not type(b):return False
    if isinstance(a,nbtlib.Compound):return set(a)==set(b)and all(same_tag(a[k],b[k])for k in a)
    if isinstance(a,nbtlib.List):return a.subtype==b.subtype and len(a)==len(b)and all(same_tag(x,y)for x,y in zip(a,b))
    if isinstance(a,(nbtlib.ByteArray,nbtlib.IntArray,nbtlib.LongArray)):return np.array_equal(a,b)
    return bool(a==b)


def serialized_be_tag_matches(expected,actual):
    """Compare all BE fields, explicitly accounting for native region packing metadata.

    Vanilla's loaded/unpacked region record can add Byte keepPacked=0 to an
    otherwise identical saveWithFullMetadata image. Preserve the actual tag;
    never discard arbitrary fields, accept packed=1, or coerce another type.
    """
    if same_tag(expected,actual):return True,False
    if expected is None or actual is None or 'keepPacked' in expected:return False,False
    value=actual.get('keepPacked')
    if type(value)is not nbtlib.Byte or int(value)!=0:return False,False
    encoded=copy.deepcopy(expected);encoded['keepPacked']=nbtlib.Byte(0)
    return same_tag(encoded,actual),True


def resolve(base,name):
    value=Path(name);assert not value.is_absolute()and'..'not in value.parts
    result=(base/value).resolve();assert result.is_relative_to(base.resolve());return result


def atomic_bytes(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);fd,pending=tempfile.mkstemp(prefix=path.name+'.',suffix='.pending',dir=path.parent)
    try:
        with os.fdopen(fd,'wb')as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(pending,path)
    finally:
        if Path(pending).exists():Path(pending).unlink()


def atomic_json(path,value):atomic_bytes(path,json.dumps(value,indent=2).encode('utf8'))


def metadata_current_errors(world,manifest):
    errors=[]
    for entry in manifest['immutable_baseline']:
        target=resolve(world,entry['target'])
        if sha(target)!=entry['sha256']:errors.append(dict(target=entry['target'],kind='Immutable UUID/depth baseline changed'))
    for row in manifest['operations']:
        actual=sha(resolve(world,row['target']))
        if actual not in {row['before_sha256'],row['after_sha256']}:
            errors.append(dict(target=row['target'],kind='Unexpected current bytes',actual_sha256=actual))
    return errors


def actual_candidate_check(world,bundle,manifest):
    w=MeasuredWorld(world);cargo={};cores={};anchors={}
    for op in manifest['operations']:
        if op['kind']!='archive':continue
        building=nbtlib.load(resolve(bundle,op['source']))['data']['Buildings'][0]
        cx,cy,cz=unpack_pos(int(building['Centre']));base=19-int(building['Height'])if op['index']<93 else -61
        for cell in building['Cargo']:
            x,y,z=unpack_pos(int(cell['Pos']));point=(cx+x,base+y,cz+z)
            assert point not in cargo,'Two complete cargo owners overlap'
            cargo[point]=cell;w.box(point,point)
        for point in map(unpack_pos,building['NegativeDomeAnchorMask']):anchors[point]='minecraft:iron_block';w.box(point,point)
        if 'R45FixedControllerPos'in building:
            point=unpack_pos(int(building['R45FixedControllerPos']));cores[point]=True;w.box(point,point)
    assert len(cargo)==749242 and len(cores)==64 and len(anchors)==6144
    # The generation recipes contain the exact preserved armed/core state.
    # Checking only the registry-name prefix would miss inventory/control state changes.
    needed={(p[0]//16,p[2]//16)for p in cores};core_states={}
    for op in manifest['operations']:
        if op['kind']!='generation'or '/chunks/'not in op['target']:continue
        chunk=tuple(map(int,Path(op['target']).stem.split('_')))
        if chunk not in needed:continue
        recipe=nbtlib.load(resolve(bundle,op['source']));palette=recipe['Palette']
        for row in recipe['Static']:
            point=unpack_pos(int(row['Pos']))
            if point in cores:core_states[point]=canonical_state(palette_state(palette[int(row['StateId'])]))
    assert set(core_states)==set(cores),'Every fixed controller needs its exact portable recipe state'
    w.load();points=list(cargo)+list(anchors)+list(cores)
    lo=tuple(min(p[i]for p in points)for i in range(3));hi=tuple(max(p[i]for p in points)for i in range(3))
    actual_tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    errors=[];recognized_serialization_fields=0
    for point,cell in cargo.items():
        expected=canonical_state(palette_state(cell['State']));actual=w.block(point)
        tag=cell.get('NBT');actual_tag=actual_tags.get(point)
        if tag is not None:
            tag=copy.deepcopy(tag)
            for key,value in zip(('x','y','z'),point):tag[key]=nbtlib.Int(value)
        nbt_matches,serialized=serialized_be_tag_matches(tag,actual_tag)
        if nbt_matches and serialized:recognized_serialization_fields+=1
        if expected!=actual or not nbt_matches:
            errors.append(dict(pos=point,kind='Complete candidate cargo/current fullNBT differs',expected=expected,actual=actual))
    for point,state in anchors.items():
        if w.block(point)!=state or point in actual_tags:errors.append(dict(pos=point,kind='Relocated negative mask state/NBT differs'))
    for point in cores:
        if w.block(point)!=core_states[point]or point in actual_tags:
            errors.append(dict(pos=point,kind='Fixed operator identity differs'))
    return errors,dict(actual_cargo_cells=len(cargo),actual_cargo_be=sum(p in actual_tags for p in cargo),fixed_cores=len(cores),external_anchor_cells=len(anchors),
        native_serialized_keepPacked_0_records=recognized_serialization_fields,arbitrary_NBT_fields_ignored=0,actual_full_region_NBT_rewritten=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path);parser.add_argument('--world',type=Path,required=True)
    action=parser.add_mutually_exclusive_group();action.add_argument('--stage-root',action='store_true');action.add_argument('--finish-root',action='store_true');action.add_argument('--rollback-root',action='store_true')
    parser.add_argument('--root-proof',type=Path);args=parser.parse_args();bundle=args.bundle.resolve();world=args.world.resolve()
    manifest_file=bundle/'manifest.json';manifest=json.loads(manifest_file.read_text());selector=manifest['world_selector']
    assert world.name==selector['name'] and selector['world_id']==str(nbtlib.load(world/'dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID'])
    assert int(nbtlib.load(world/'level.dat')['Data']['WorldGenSettings']['seed'])==selector['seed']
    for entry in manifest['source_epoch']:
        assert sha(resolve(bundle,entry['frozen_copy']))==entry['sha256']
        assert sha(ROOT/entry['repository_path'])==entry['sha256'],'Source epoch changed; refreeze explicit installer input'
    for op in manifest['operations']:assert sha(resolve(bundle,op['source']))==op['after_sha256']
    wal_file=bundle/'metadata_wal.json';marker=resolve(world,manifest['marker_target'])
    errors=metadata_current_errors(world,manifest)
    if not any((args.stage_root,args.finish_root,args.rollback_root)):
        print(json.dumps(dict(read_only=True,world_written=False,errors=errors,wal_exists=wal_file.exists(),marker_exists=marker.exists()),indent=2));assert not errors;return
    guard();assert not errors,errors[:10]
    if args.stage_root:
        if wal_file.exists():
            wal=json.loads(wal_file.read_text())
            assert wal['manifest_sha256']==sha(manifest_file)and wal['world_id']==selector['world_id']
            assert wal['phase']in ('PREPARED','INSTALLING'),'Resume later migration phases with finish/rollback; never restage'
            for entry,op in zip(wal['entries'],manifest['operations']):
                assert entry['target']==op['target']and entry['before_sha256']==op['before_sha256']and entry['after_sha256']==op['after_sha256']
                assert sha(resolve(world,entry['target']))==entry['before_sha256']
                if entry['backup']:assert sha(resolve(bundle,entry['backup']))==entry['before_sha256']
            assert len(wal['entries'])==len(manifest['operations'])
        else:
            assert not marker.exists(),'Never stage over another ownership marker'
            backup=bundle/'original_file_bytes';backup.mkdir(exist_ok=True);entries=[]
            for i,op in enumerate(manifest['operations']):
                target=resolve(world,op['target']);before=sha(target);assert before==op['before_sha256']
                name=f'{i}.bin';saved=backup/name
                if before is not None:
                    # Exact inverse bytes are forced before publishing the write-ahead journal.
                    atomic_bytes(saved,target.read_bytes());assert sha(saved)==before
                entries.append(dict(target=op['target'],before_sha256=before,after_sha256=op['after_sha256'],backup='original_file_bytes/'+name if before else None))
            wal=dict(schema='projectseele.city-rigid-metadata-wal-r45.v1',manifest_sha256=sha(manifest_file),world_id=selector['world_id'],phase='PREPARED',entries=entries,
                marker_before_absent=True,started=datetime.datetime.now().isoformat(),world_written=False)
            atomic_json(wal_file,wal)
        installing=resolve(bundle,manifest['installing_marker'])
        assert sha(marker)in {None,sha(installing)},'Foreign marker bytes must never be overwritten'
        if not marker.exists():atomic_bytes(marker,installing.read_bytes())
        wal['phase']='INSTALLING';wal['world_written']=True;atomic_json(wal_file,wal)
        print('Root ownership staged; static replay remains separate. RuntimeEnabled=false.');return
    assert wal_file.exists(),'Stage the exact durable metadata WAL first'
    wal=json.loads(wal_file.read_text());assert wal['manifest_sha256']==sha(manifest_file)and wal['world_id']==selector['world_id']
    assert wal['phase']in ('INSTALLING','APPLYING_METADATA','INSTALLED_DISABLED','ROLLING_BACK_METADATA')
    for entry in wal['entries']:
        if entry['backup']:assert sha(resolve(bundle,entry['backup']))==entry['before_sha256'],'Durable inverse bytes changed'
    if marker.exists():
        owner=nbtlib.load(marker)['data']
        assert str(owner['WorldUUID'])==selector['world_id']and int(owner['Origin'])==selector['origin']
        assert str(owner['Stage'])in ('INSTALLING','INSTALLED')and not bool(owner['RuntimeEnabled'])
    else:assert args.rollback_root and wal['phase']=='ROLLING_BACK_METADATA','Ownership marker missing; explicitly resume stage before static replay'
    assert args.root_proof is not None,'Exact static/native Root proof is required; a metadata flag is not evidence'
    proof=json.loads(args.root_proof.read_text());assert proof['schema']=='projectseele.city-rigid-root-static-proof-r45.v1'and proof['world_id']==selector['world_id']
    assert proof['topology_forward_sha256']==manifest['static_forward_sha256']and proof['topology_inverse_sha256']==manifest['static_inverse_sha256']
    if args.finish_root:
        required=('exact_static_forward_applied','complete_static_inverse_durable','native_structure_port_bearing_passed','original1471_full_be_preserved','root_structure_art_review_passed')
        assert all(proof.get(k)is True for k in required),'No implicit native/art pass promotion'
        actual_errors,counts=actual_candidate_check(world,bundle,manifest);assert not actual_errors,actual_errors[:10]
        wal['phase']='APPLYING_METADATA';wal['root_proof_sha256']=sha(args.root_proof);atomic_json(wal_file,wal)
        for op in manifest['operations']:
            target=resolve(world,op['target']);assert sha(target)in {op['before_sha256'],op['after_sha256']}
            if sha(target)!=op['after_sha256']:atomic_bytes(target,resolve(bundle,op['source']).read_bytes())
            assert sha(target)==op['after_sha256']
        marker_tag=nbtlib.load(resolve(bundle,manifest['installed_marker']));marker_tag['data']['NativeStructurePassed']=nbtlib.Byte(1);marker_tag['data']['ExactCargoMigrationPassed']=nbtlib.Byte(1)
        marker_tag['data']['RootStaticProofSHA256']=nbtlib.String(sha(args.root_proof));marker_tag['data']['RuntimeEnabled']=nbtlib.Byte(0)
        import io,gzip
        stream=io.BytesIO();marker_tag.write(stream);atomic_bytes(marker,gzip.compress(stream.getvalue(),compresslevel=1,mtime=0))
        assert str(nbtlib.load(marker)['data']['Stage'])=='INSTALLED'and not bool(nbtlib.load(marker)['data']['RuntimeEnabled'])
        wal['phase']='INSTALLED_DISABLED';wal['actual_native_readback']=counts;wal['marker_after_sha256']=sha(marker);atomic_json(wal_file,wal)
        print(json.dumps(dict(root_metadata_installed=True,runtime_enabled=False,**counts),indent=2));return
    assert proof.get('exact_static_inverse_applied')is True and proof.get('original_static_full_nbt_restored')is True,'Restore the static topology first; never expose new geometry to old generators'
    wal['phase']='ROLLING_BACK_METADATA';atomic_json(wal_file,wal)
    for entry in reversed(wal['entries']):
        target=resolve(world,entry['target']);assert sha(target)in {entry['before_sha256'],entry['after_sha256']}
        if entry['backup']:atomic_bytes(target,resolve(bundle,entry['backup']).read_bytes());assert sha(target)==entry['before_sha256']
        elif target.exists():target.unlink()
    # Only the explicitly named marker is unlinked after native static inverse.
    assert marker.is_relative_to(world);marker.unlink(missing_ok=True);wal['phase']='ROLLED_BACK';atomic_json(wal_file,wal);print('Exact metadata inverse restored; source UUID/depth never replaced.')


if __name__=='__main__':main()
