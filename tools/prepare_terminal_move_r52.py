"""Root-owned complete Terminal Dogma move, with strict measured cell runs.

Default prepares a bounded plan only. Actors and native lift group changes are
recorded as pending: never call a partially assembled world ready for play.
"""
from pathlib import Path
import argparse,copy,io,json,msvcrt
import nbtlib
import numpy as np
import regional_voxels as vox
from query_blocks import iter_block_entities
from survey_r52_original_complex import measure
from r52_spatial_plan import BASE,TERMINAL
from extend_world_depth_r52 import acquire_world_lock
from move_component_actors_r52 import prepare_actor_files
from apply_s20_approved_semantic_repairs import atomic_replace

WORLD=BASE/'WORLD_R52'
OUT=BASE/'terminal_move'


def runs(painter,lo,before,after,palette,owner):
    cells=0
    for y in range(before.shape[0]):
        for z in range(before.shape[1]):
            old,new=before[y,z],after[y,z]
            changed=np.flatnonzero(old!=new)
            if not len(changed):continue
            breaks=np.flatnonzero((np.diff(changed)!=1)|(old[changed[1:]]!=old[changed[:-1]])|(new[changed[1:]]!=new[changed[:-1]]))+1
            for row in np.split(changed,breaks):
                a,b=int(row[0]),int(row[-1]);cells+=len(row)
                painter.exact((lo[0]+a,lo[1]+y,lo[2]+z,lo[0]+b,lo[1]+y,lo[2]+z),
                              palette[int(old[a])],palette[int(new[a])],owner)
    return cells


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    assert (BASE/'depth_extension/APPLIED.json').exists(),'Complete new deep section foundation first'
    source=np.load(BASE/'survey/terminal_complete.npz')
    lo=tuple(map(int,source['origin']));shape=source['states'].shape
    hi=(lo[0]+shape[2]-1,lo[1]+shape[0]-1,lo[2]+shape[1]-1)
    dest_lo,dest_hi=TERMINAL.box(lo,hi)
    before,before_pal=measure(dest_lo,dest_hi)
    actual,actual_pal=measure(lo,hi)
    source_pal=list(map(str,source['palette']))
    all_names=list(dict.fromkeys(source_pal+before_pal+actual_pal+['minecraft:stone','minecraft:black_concrete']))
    ids={name:i for i,name in enumerate(all_names)}
    remap=lambda data,pal:np.asarray([ids[s] for s in pal],np.uint16)[data]
    original=remap(source['states'],source_pal)
    current=remap(actual,actual_pal)
    assert np.array_equal(original,current),'Original Terminal component changed after its frozen measurement'
    previous=remap(before,before_pal)
    assert all(before_pal[int(i)] in {'minecraft:deepslate[axis=y]','minecraft:deepslate'} for i in np.unique(before)), 'Unexpected occupant in explicit new deep destination'
    target=original.copy()
    devices=json.loads((BASE/'survey/terminal_complete_devices.json').read_text('utf8'))
    assert len(devices)==1 and devices[0]['id']=='movingelevators:elevator_tile'
    # Preserve the complete gallery. The original command lift is extended on
    # its retained axis; its moved stop is rebuilt at that shaft, not on a third
    # independent lift at this translated controller position.
    px,py,pz=devices[0]['pos']
    target[py-lo[1],pz-lo[2],px-lo[0]]=ids['minecraft:black_concrete']
    retired=np.full_like(current,ids['minecraft:stone'])
    vox.WORLD=WORLD;vox.OUT=OUT;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-960,320))
    count_source=runs(painter,lo,current,retired,all_names,'R52_retire_complete_old_terminal')
    count_target=runs(painter,dest_lo,previous,target,all_names,'R52_move_complete_terminal_below_hangar')
    painter.meta.update(root_author=True,source_envelope=[lo,hi],destination_envelope=[dest_lo,dest_hi],
                        original_controller_retired=devices[0],pending_main_controller=[6,-846,253],
                        pending_lilith_original_uuid='5102dc56-c4e4-4e74-b66b-79f70fde6ced',
                        terminal_frame=TERMINAL.__dict__,playable=False)
    folder=painter.save_plan('complete_terminal_translation')
    report=dict(source_retired_cells=count_source,target_changed_cells=count_target,operations=len(painter.ops),
                full_source_match=True,new_destination_measured=True,source_envelope=[lo,hi],destination_envelope=[dest_lo,dest_hi],
                original_artitecture_copied=True,only_old_controller_removed=True,actors_and_runtime_pending=True,world_written=False)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)
    if args.apply:
        assert not list(folder.glob('applied_*')),'Already has an application receipt; inspect rather than replay'
        actors=json.loads((BASE/'survey/ORIGINAL_ALL_ACTORS.json').read_text('utf8'))['actors']
        lilith=next(r for r in actors if r['id']=='projectseele:lilith')
        lock=acquire_world_lock();before_files={};geometry_receipt=None
        try:
            owned_actors=[r for r in actors if all(lo[i]<=r['pos'][i]<=hi[i] for i in range(3))]
            actor_files,actor_receipt=prepare_actor_files(WORLD,{r['uuid']:TERMINAL for r in owned_actors},{r['uuid']:r['snbt'] for r in owned_actors})
            caps_path=WORLD/'dimensions/projectseele/geofront/data/capabilities.dat'
            caps=nbtlib.load(caps_path);group=caps['data']['movingelevators:elevator_groups']['9;253']['group']
            assert not bool(group['isMoving']) and list(map(int,group['floors']))==[-566,-448,-423,-419,-409]
            assert not bool(group['floorData'][0]['isCageAvailable'])
            group['floors']=nbtlib.IntArray(list(group['floors'])[1:])
            group['floorData']=type(group['floorData'])(list(group['floorData'])[1:])
            pending=dict(actor_files)
            roster_path=WORLD/'nerv_staff_r15.json'
            roster=json.loads(roster_path.read_text('utf8'))
            staff_ids={str(nbtlib.parse_nbt(r['snbt'])['StaffId']) for r in owned_actors if r['id']=='projectseele:nerv_staff'}
            for station in roster['stations']:
                if station['id'] in staff_ids:station['feet']=list(TERMINAL.block(station['feet']))
            pending[roster_path]=(json.dumps(roster,ensure_ascii=False,indent=2)+'\n').encode('utf8')
            stream=io.BytesIO();caps.write(stream)
            import gzip
            pending[caps_path]=gzip.compress(stream.getvalue(),mtime=0)
            # No currently saved player or respawn point belongs to this layer.
            for path in (WORLD/'playerdata').glob('*.dat'):
                player=nbtlib.load(path)
                if str(player.get('Dimension',''))=='projectseele:geofront':
                    position=list(map(float,player.get('Pos',[])))
                    assert not all(lo[i]<=position[i]<=hi[i] for i in range(3)), 'Player requires an explicit same-stage position migration'
                if str(player.get('SpawnDimension',''))=='projectseele:geofront' and 'SpawnY' in player:
                    position=[int(player[k]) for k in ('SpawnX','SpawnY','SpawnZ')]
                    assert not all(lo[i]<=position[i]<=hi[i] for i in range(3)), 'Respawn requires explicit migration'
            for path in pending:before_files[path]=path.read_bytes() if path.exists() else None
            metadata_backup=folder/'metadata_before';metadata_backup.mkdir()
            for path,raw in before_files.items():
                if raw is not None:
                    target=metadata_backup/path.relative_to(WORLD);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            geometry_receipt=painter.apply('complete_terminal_translation',session_lock=lock)
            for path,raw in pending.items():
                assert (path.read_bytes() if path.exists() else None)==before_files[path],'Metadata changed under the exclusive construction lock'
                atomic_replace(path,raw)
            from verify_main_r20 import entities
            current_actors=entities(WORLD)
            assert len(current_actors)==678
            moved=next(tag for tag in current_actors.values() if str(tag['id'])=='projectseele:lilith')
            assert list(map(float,moved['Pos']))==list(TERMINAL.point(lilith['pos']))
            report.update(world_written=True,receipt=geometry_receipt,actor_receipt=actor_receipt,
                          original_lilith_and_all_678_actor_ids_preserved=True,
                          old_dedicated_terminal_lift_stop_retired=True,
                          pending=['original command lift extension and gallery link','runtime destinations/armor target rebind','native visual review'])
        except BaseException:
            for path,raw in before_files.items():
                if raw is not None:atomic_replace(path,raw)
            if geometry_receipt is not None:
                applications=list(folder.glob('applied_*'));assert len(applications)==1
                for backup in (applications[0]/'before').glob('r.*.mca'):
                    atomic_replace(WORLD/'dimensions/projectseele/geofront/region'/backup.name,backup.read_bytes())
                (applications[0]/'ROLLED_BACK.json').write_text('{"reason":"metadata stage failed"}','utf8')
            raise
        finally:
            msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
        (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
