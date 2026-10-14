"""Translate only the complete original HQ station and entrance by -93 Y.

The original three platforms, native gates, displays and guard remain the same
objects. MTR graph/vehicle files are deliberately a separate reviewed stage.
"""
import argparse,json,msvcrt
import nbtlib
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE,PYRAMID
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities
from facility_frame_nbt_r52 import block_entity_in_frame
from extend_world_depth_r52 import acquire_world_lock
from move_component_actors_r52 import prepare_actor_files
from apply_s20_approved_semantic_repairs import atomic_replace

WORLD=BASE/'WORLD_R52'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=WORLD;component=BASE/'hq_station_component'
    source=np.load(component/'SOURCE.npz');owner=np.load(component/'OWNERSHIP.npz')['owned']
    origin=tuple(map(int,source['origin']));shape=source['states'].shape
    lo=(origin[0],origin[1]-93,origin[2]);hi=(origin[0]+shape[2]-1,origin[1]+shape[0]-1,origin[2]+shape[1]-1)
    actual,apalette=measure(lo,hi);names=list(dict.fromkeys(apalette+list(map(str,source['palette']))+['minecraft:grass_block[snowy=false]','minecraft:stone','minecraft:air']))
    ids={v:i for i,v in enumerate(names)};before=np.asarray([ids[s]for s in apalette],np.uint16)[actual]
    original=np.asarray([ids[str(s)]for s in source['palette']],np.uint16)[source['states']]
    # These shared first entrance cells were already carried by the complete
    # pyramid component. Require the exact translated source at the new end.
    pyr=np.load(BASE/'pyramid_component/owner_mask.npz');po=pyr['origin'];pm=pyr['owned'];shared=np.zeros_like(owner)
    for iy,iz,ix in zip(*np.nonzero(owner)):
        x,y,z=origin[0]+ix,origin[1]+iy,origin[2]+iz;px,py,pz=x-po[0],y-po[1],z-po[2]
        if 0<=py<pm.shape[0] and 0<=pz<pm.shape[1] and 0<=px<pm.shape[2]:shared[iy,iz,ix]=pm[py,pz,px]
    old=before[93:93+shape[0]];unmoved=owner&~shared
    bad=np.argwhere(unmoved&(old!=original))
    if len(bad):
        iy,iz,ix=bad[0];raise AssertionError(('Original station source changed',len(bad),(int(ix+origin[0]),int(iy+origin[1]),int(iz+origin[2])),names[int(original[iy,iz,ix])],names[int(old[iy,iz,ix])]))
    target=before[:shape[0]]
    assert np.array_equal(target[shared],original[shared]),'Already moved entrance differs from original component'
    natural={'minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]'}
    unexpected=[names[int(v)]for v in np.unique(target[unmoved])if names[int(v)]not in natural]
    assert not unexpected,('Unexpected new station occupant',unexpected)
    after=before.copy();yy=np.arange(shape[0])[:,None,None]+origin[1]
    fill=np.broadcast_to(np.where(yy>-467,ids['minecraft:air'],np.where(yy==-467,ids['minecraft:grass_block[snowy=false]'],ids['minecraft:stone'])),shape)
    after[93:93+shape[0]][unmoved]=fill[unmoved];after[:shape[0]][owner]=original[owner]
    devices=json.loads((component/'SOURCE_DEVICES.json').read_text('utf8'));references={(30,-467,z):(30,-560,z)for z in (486,494,522)}
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));additions={};moving=[]
    for row in devices:
        pos=tuple(row['pos']);ix,iy,iz=pos[0]-origin[0],pos[1]-origin[1],pos[2]-origin[2]
        if not owner[iy,iz,ix]:continue
        original_tag=nbtlib.parse_nbt(row['snbt']);t=block_entity_in_frame(original_tag,PYRAMID,reference_positions=references)
        dest=tuple(int(t[k])for k in ('x','y','z'))
        if shared[iy,iz,ix]:assert tags[dest].snbt()==t.snbt();continue
        assert tags[pos].snbt()==original_tag.snbt(),('Original station device changed',pos)
        assert dest not in tags,('New station device already occupied',dest)
        additions[dest]=t;moving.append(row)
    vox.WORLD=world;vox.OUT=BASE/'hq_station_move';vox.DIM='projectseele:geofront'
    p=vox.Painter(vertical_bounds=(-960,320));count=runs(p,lo,before,after,names,'R52_original_HQ_station_vertical_translation')
    p.block_entities.update(additions)
    p.meta.update(root_author=True,original_station_id='7F36F8DC34907D9B',source_shift=[0,-93,0],
        original_platform_ids=['910C703E8C195E14','5F8F651005220016','7503CEFA3D9A08FC'],
        original_station_architecture_unchanged=True,other_stations_untouched=True,playable=False)
    folder=p.save_plan('complete_original_HQ_station_translation')
    report=dict(world_written=False,playable=False,changed_cells=count,source_component_cells=int(owner.sum()),
        shared_already_moved_cells=int(shared.sum()),newly_moved_devices=len(moving),original_device_total=len(devices),
        entry=[31,-560,447],pending=['native MTR approach graph/tunnel migration','native passenger and train checks'])
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if not args.apply:return
    assert not list(folder.glob('applied_*')),'Existing station application must not be replayed'
    lock=acquire_world_lock();backups={};geometry=None
    try:
        actors=json.loads((component/'OWNERSHIP.json').read_text('utf8'))['actors']
        actor_files,actor_receipt=prepare_actor_files(world,{r['uuid']:PYRAMID for r in actors},{r['uuid']:r['snbt']for r in actors})
        pending=dict(actor_files);roster_path=world/'nerv_staff_r15.json';roster=json.loads(roster_path.read_text('utf8'))
        staff_ids={str(nbtlib.parse_nbt(r['snbt'])['StaffId'])for r in actors}
        for row in roster['stations']:
            if row['id']in staff_ids:row['feet']=list(PYRAMID.block(row['feet']))
        pending[roster_path]=(json.dumps(roster,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        b=folder/'metadata_before';b.mkdir()
        for f in pending:
            backups[f]=f.read_bytes();dest=b/f.relative_to(world);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(backups[f])
        geometry=p.apply('complete_original_HQ_station_translation',session_lock=lock)
        for f,raw in pending.items():assert f.read_bytes()==backups[f];atomic_replace(f,raw)
        final=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
        assert all(final[q].snbt()==t.snbt()for q,t in additions.items())
        assert all(tuple(r['pos'])not in final for r in moving)
        from verify_main_r20 import entities
        assert len(entities(world))==678
        report.update(world_written=True,receipt=geometry,actor_receipt=actor_receipt,all_original_native_gate_nbt_preserved=True)
        (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    except BaseException:
        for f,raw in backups.items():atomic_replace(f,raw)
        if geometry is not None:
            app=list(folder.glob('applied_*'));assert len(app)==1
            for f in (app[0]/'before').glob('r.*.mca'):atomic_replace(world/'dimensions/projectseele/geofront/region'/f.name,f.read_bytes())
            (app[0]/'ROLLED_BACK.json').write_text('{"reason":"HQ station metadata/readback failed"}','utf8')
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
