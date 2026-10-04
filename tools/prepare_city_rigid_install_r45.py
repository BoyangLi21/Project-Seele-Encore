"""Freeze exact current archive/marker migration and portable installer inputs.

No world writes, no runtime/build/install. Static block replay is a separate
Root operation with its own native receipt; metadata cannot claim it happened.
"""
from pathlib import Path
import argparse,hashlib,json,shutil
import nbtlib

ROOT=Path(__file__).resolve().parents[1]
DATA=Path('dimensions/projectseele/geofront/data')
SOURCES=[
 'src/main/java/com/projectseele/world/CityCreateCargoR45.java',
 'src/main/java/com/projectseele/world/CityCreateBridgeR45.java',
 'src/main/java/com/projectseele/world/CityCreateDistrictR45.java',
 'src/main/java/com/projectseele/world/CityRigidTopologyR45.java',
 'src/main/java/com/projectseele/world/CityRigidGenerationR45.java',
 'src/main/java/com/projectseele/world/CityRigidQualityR45.java',
 'src/main/java/com/projectseele/world/GeoFrontBoundedChunkGenerator.java',
 'src/main/java/com/projectseele/world/Tokyo3RetractionDirector.java',
 'src/main/java/com/projectseele/world/ThirdTokyoSurfaceBuilder.java',
 'src/main/java/com/projectseele/world/LocalMapAssetLoader.java']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--world',type=Path,default=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW')
    parser.add_argument('--topology',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/whole_topology_v2')
    parser.add_argument('--generation',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/generation_v1')
    parser.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/install_bundle_v1');args=parser.parse_args()
    world=args.world.resolve();topology=args.topology.resolve();generation=args.generation.resolve();out=args.out.resolve()
    assert world.name=='SEELE_FIELD_R45_REVIEW' and not out.exists()
    manifest=json.loads((topology/'manifest.json').read_text('utf8'));assert manifest['objects']==96 and manifest['full_be']==1471
    identity_file=world/DATA/'projectseele_tokyo3_building_world_id_r44.dat';identity=str(nbtlib.load(identity_file)['data']['WorldUUID'])
    assert manifest['world_id']==identity
    retract_file=world/DATA/'projectseele_tokyo3_retraction.dat';district=nbtlib.load(retract_file)['data']['Districts'][0]
    assert int(district['Depth'])==int(district['TargetDepth'])==312 and int(district['Cursor'])==int(district['VoxelCursor'])==0 and not str(district['Fault'])
    assert len(list((world/DATA).glob('projectseele_tokyo3_building_archive_r44_*.dat')))==93
    out.mkdir(parents=True);(out/'payload').mkdir();(out/'baseline').mkdir();(out/'source_epoch').mkdir()
    operations=[];differences=[];total_be=0
    for row in manifest['records']:
        candidate=Path(row['cargo']);assert sha(candidate)==row['sha256'];after_file=nbtlib.load(candidate);after=after_file['data']['Buildings'][0]
        target=DATA/candidate.name;actual=world/target
        before_sha=sha(actual)if actual.exists()else None
        if row['index']<93:
            assert before_sha==row['source']['source_archive_sha256'],'Actual archive epoch changed; remeasure/migrate explicitly'
            before_file=nbtlib.load(actual);before=before_file['data']['Buildings'][0]
            assert str(before_file['data']['WorldUUID'])==identity and 'Transaction'not in before
            cells_before={int(c['Pos']):c for c in before['Cargo']};cells_after={int(c['Pos']):c for c in after['Cargo']}
            assert all(cells_after.get(pos)==cell for pos,cell in cells_before.items()),'Original full cargo/BE metadata changed'
            extra=set(cells_after)-set(cells_before);was_core=bool(before['FixedStreetCore'])
            assert extra==({0}if was_core else set()) and not bool(after['FixedStreetCore'])
            assert int(after['Origin'])==int(before['Origin']) and int(after['Centre'])==int(before['Centre'])
            assert int(after['Height'])==int(before['Height']) and int(after['Half'])==int(before['Half'])
            changes={k:dict(before=before[k].snbt()if k in before else None,after=after[k].snbt()if k in after else None)
                for k in before.keys()|after.keys()if k!='Cargo'and (before[k].snbt()if k in before else None)!=(after[k].snbt()if k in after else None)}
            allowed={'FixedStreetCore','NegativeDomeAnchorMask','R45OriginalFixedStreetCore','R45FixedControllerPos','R45RigidTopologyVersion'}
            assert set(changes)<=allowed
            differences.append(dict(index=row['index'],file=candidate.name,extra_moving_floor_cells=len(extra),original_cells=len(cells_before),preserved_full_be=sum('NBT'in c for c in before['Cargo']),fields=changes))
            shutil.copyfile(actual,out/'baseline'/candidate.name)
        else:assert before_sha is None,'Do not silently overwrite an existing private cargo journal'
        total_be+=sum('NBT'in c for c in after['Cargo'])
        payload=out/'payload'/candidate.name;shutil.copyfile(candidate,payload)
        operations.append(dict(kind='archive',source='payload/'+candidate.name,target=target.as_posix(),before_sha256=before_sha,after_sha256=sha(payload),index=row['index']))
    assert total_be==1471
    for path in sorted(generation.rglob('*.dat')):
        relative=path.relative_to(generation);dest=out/'payload/generation'/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        target=DATA/'city_rigid_generation_r45'/relative;assert not (world/target).exists(),'Existing generation recipe requires a backed-up named upgrade'
        operations.append(dict(kind='generation',source=dest.relative_to(out).as_posix(),target=target.as_posix(),before_sha256=None,after_sha256=sha(dest)))
    marker=Path(manifest['authority']);assert sha(marker)==manifest['authority_sha256'];target=DATA/marker.name
    assert not (world/target).exists(),'Existing ownership marker must resume its original migration WAL'
    for stage in ('INSTALLING','INSTALLED'):
        value=nbtlib.load(marker);value['data']['Stage']=nbtlib.String(stage);value['data']['RuntimeEnabled']=nbtlib.Byte(0)
        value['data']['NativeStructurePassed']=nbtlib.Byte(0);value['data']['ExactCargoMigrationPassed']=nbtlib.Byte(0)
        dest=out/'payload'/f'{stage.lower()}.marker.dat';value.save(dest,gzipped=True)
    sources=[]
    for relative in SOURCES:
        source=ROOT/relative;dest=out/'source_epoch'/source.name;shutil.copyfile(source,dest);sources.append(dict(repository_path=relative,sha256=sha(source),frozen_copy=dest.relative_to(out).as_posix()))
    baseline=[]
    for file in (identity_file,retract_file):
        dest=out/'baseline'/file.name;shutil.copyfile(file,dest);baseline.append(dict(target=file.relative_to(world).as_posix(),sha256=sha(file),copy=dest.relative_to(out).as_posix(),write_allowed=False))
    receipt_template=dict(schema='projectseele.city-rigid-root-static-proof-r45.v1',world_id=identity,
        topology_forward_sha256=manifest['forward_sha256'],topology_inverse_sha256=manifest['inverse_sha256'],
        exact_static_forward_applied=False,complete_static_inverse_durable=False,native_structure_port_bearing_passed=False,
        original1471_full_be_preserved=False,root_structure_art_review_passed=False)
    (out/'required_root_static_proof_TEMPLATE.json').write_text(json.dumps(receipt_template,indent=2),'utf8')
    result=dict(schema='projectseele.city-rigid-install-bundle-r45.v1',world_selector=dict(name=world.name,world_id=identity,
        seed=int(nbtlib.load(world/'level.dat')['Data']['WorldGenSettings']['seed']),dimension='projectseele:geofront',origin=int(district['Origin'])),
        world_written=False,root_only=True,default_runtime_enabled=False,full_be=total_be,archive_objects=96,
        static_topology_manifest_sha256=sha(topology/'manifest.json'),static_forward_sha256=manifest['forward_sha256'],static_inverse_sha256=manifest['inverse_sha256'],
        marker_target=target.as_posix(),installing_marker='payload/installing.marker.dat',installed_marker='payload/installed.marker.dat',
        operations=operations,immutable_baseline=baseline,source_epoch=sources,archive_field_differences=differences,
        wal_protocol=['cold/exclusive guard','freeze exact original file bytes and absence','durable file-WAL','INSTALLING marker gates legacy','Root exact static replay/native proof','atomic archive+recipe replacement','full readback','INSTALLED marker RuntimeEnabled=false','Root separate promotion after complete native suite'])
    (out/'manifest.json').write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps({k:v for k,v in result.items()if k not in('operations','immutable_baseline','source_epoch','archive_field_differences','wal_protocol')},indent=2));print('finite operations',len(operations))


if __name__=='__main__':main()
