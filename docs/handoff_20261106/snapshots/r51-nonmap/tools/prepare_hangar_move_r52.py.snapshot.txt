"""Migrate Root's complete original hangar/incline and lower first launch bank.

Requires the frozen ownership mask and an empty measured destination. Changes
remain a construction world: launch junctions and runtime bindings follow.
"""
import argparse,copy,json,msvcrt
import nbtlib
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE,HANGAR
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from prepare_pyramid_move_r52 import encoded
from facility_frame_nbt_r52 import state_in_frame,block_entity_in_frame,unpack_position
from query_blocks import iter_block_entities
from move_component_actors_r52 import prepare_actor_files,descendants,identity
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace

WORLD=BASE/'WORLD_R52'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    world=WORLD;out=BASE/'hangar_move'
    source=np.load(BASE/'survey/original_hangar_transfer_launch.npz')
    mask=np.load(BASE/'hangar_component/owner_mask.npz')
    move,retire=mask['move'],mask['retire'];lo=tuple(map(int,source['origin']));shape=source['states'].shape
    hi=(lo[0]+shape[2]-1,lo[1]+shape[0]-1,lo[2]+shape[1]-1)
    dl,dh=HANGAR.box(lo,hi);current,cp=measure(lo,hi);destination,dp=measure(dl,dh)
    sp=list(map(str,source['palette']));rotated=[state_in_frame(s,HANGAR) for s in sp]
    names=list(dict.fromkeys(cp+dp+sp+rotated+['minecraft:air','minecraft:stone','minecraft:grass_block[snowy=false]']))
    ids={s:i for i,s in enumerate(names)}
    remap=lambda a,p:np.asarray([ids[s] for s in p],np.uint16)[a]
    before=remap(current,cp);original=remap(source['states'],sp)
    assert np.array_equal(before[move|retire],original[move|retire]),'Original owned component changed'
    before_dest=remap(destination,dp);target=before_dest.copy();target_mask=move[:,::-1,::-1]
    allowed={'minecraft:stone','minecraft:deepslate[axis=y]','minecraft:deepslate','minecraft:air','minecraft:cave_air','minecraft:bedrock'}
    occupants={names[int(v)]:int(n) for v,n in zip(*np.unique(before_dest[target_mask],return_counts=True))}
    assert set(occupants)<=allowed,('Authored occupant in destination',occupants)
    bedrock_y=np.nonzero((before_dest==ids.get('minecraft:bedrock',-1))&target_mask)[0]+dl[1]
    assert np.all((bedrock_y>=-672)&(bedrock_y<=-668)),'Only the former natural dimension bottom may be excavated'
    target[target_mask]=remap(source['states'],rotated)[:,::-1,::-1][target_mask]
    after=before.copy();ys=np.arange(shape[0])[:,None,None]+lo[1]
    fill=np.broadcast_to(np.where(ys>-467,ids['minecraft:air'],np.where(ys==-467,ids['minecraft:grass_block[snowy=false]'],ids['minecraft:stone'])),shape)
    after[retire]=fill[retire]
    owned=json.loads((BASE/'hangar_component/devices_and_actors.json').read_text('utf8'))
    current_tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    dest_tags=dict(iter_block_entities(world,'projectseele:geofront',dl,dh))
    references={tuple(r['pos']):HANGAR.block(r['pos']) for r in owned['devices'] if r['id']=='movingelevators:elevator_tile'}
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-960,320))
    source_cells=runs(painter,lo,before,after,names,'R52_retire_original_hangar_and_transfer')
    target_cells=runs(painter,dl,before_dest,target,names,'R52_original_hangar_incline_rigid_half_turn')
    for row in owned['devices']:
        tag=nbtlib.parse_nbt(row['nbt']);point=tuple(row['pos'])
        assert current_tags[point].snbt()==tag.snbt()
        shifted=block_entity_in_frame(tag,HANGAR,reference_positions=references)
        # The old lab stays in place. This relocated lift's bottom stop serves
        # the wet-vessel engineering level, not that separate old laboratory.
        if row['id']=='movingelevators:elevator_tile' and point[1]==-468:
            shifted['data']['name']=nbtlib.String('机库整备维护层')
        new=tuple(int(shifted[k]) for k in ('x','y','z'))
        assert new not in dest_tags
        painter.block_entities[new]=shifted
        ix,iy,iz=new[0]-dl[0],new[1]-dl[1],new[2]-dl[2]
        if target[iy,iz,ix]==before_dest[iy,iz,ix]:
            painter.update_block_entity(new,names[int(target[iy,iz,ix])],None,shifted,'R52_original_hangar_typed_device')
    painter.meta.update(root_author=True,original_interior_shape_preserved=True,frame=HANGAR.__dict__,
        preserve_original_upper_wells=True,preserve_experimental_lab=True,preserve_compact_lift=True,playable=False)
    folder=painter.save_plan('complete_hangar_incline_translation')
    report=dict(world_written=False,playable=False,source_changed_cells=source_cells,target_changed_cells=target_cells,
        original_devices=len(owned['devices']),original_actor_members=len(owned['actors']),destination_previous_states=occupants,
        pending=['bank 2/3 and junctions','both original main lift connections','old lab interface finishing','all runtime coordinates/rail models'])
    (folder/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
    if not args.apply:return
    assert not list(folder.glob('applied_*')),'Inspect existing receipt instead of replay'
    lock=acquire_world_lock();backups={};geometry=None
    try:
        passenger_ids=set()
        for row in owned['actors']:
            tag=nbtlib.parse_nbt(row['snbt']);passenger_ids.update(identity(t) for t in list(descendants(tag))[1:])
        roots=[r for r in owned['actors'] if r['uuid'] not in passenger_ids]
        pending,actors_receipt=prepare_actor_files(world,{r['uuid']:HANGAR for r in roots},{r['uuid']:r['snbt'] for r in roots})
        caps_path=world/'dimensions/projectseele/geofront/data/capabilities.dat';caps=nbtlib.load(caps_path)
        groups=caps['data']['movingelevators:elevator_groups'];old=groups['-26;-278'];group=copy.deepcopy(old)
        assert not bool(group['group']['isMoving']) and list(map(int,group['group']['floors']))==[-468,-394,-367]
        group['pos']['x']=nbtlib.Int(86);group['pos']['z']=nbtlib.Int(366);group['pos']['facing']=nbtlib.Int(3)
        group['group']['floors']=nbtlib.IntArray([-704,-630,-603]);group['group']['floorData'][0]['name']=nbtlib.String('机库整备维护层')
        assert '86;366' not in groups;del groups['-26;-278'];groups['86;366']=group;pending[caps_path]=encoded(caps)
        roster_path=world/'nerv_staff_r15.json';roster=json.loads(roster_path.read_text('utf8'))
        moved_staff={str(nbtlib.parse_nbt(r['snbt'])['StaffId']) for r in roots if r['id']=='projectseele:nerv_staff'}
        for station in roster['stations']:
            if station['id'] in moved_staff:
                station['feet']=list(HANGAR.block(station['feet']))
                if 'yaw' in station:station['yaw']=(float(station['yaw'])+360)%360-180
        pending[roster_path]=(json.dumps(roster,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        def owns(p):
            x,y,z=np.floor(p).astype(int)-np.asarray(lo)
            return 0<=y<shape[0] and 0<=z<shape[1] and 0<=x<shape[2] and bool(move[y,z,x])
        def shift_player(t):
            if str(t.get('Dimension',''))!='projectseele:geofront' or not owns(list(map(float,t['Pos']))):return False
            assert 'RootVehicle' not in t
            t['Pos']=nbtlib.List[nbtlib.Double]([nbtlib.Double(v) for v in HANGAR.point(list(map(float,t['Pos'])))])
            t['Rotation'][0]=nbtlib.Float((float(t['Rotation'][0])+360)%360-180)
            return True
        players=[]
        for path in (world/'playerdata').glob('*.dat'):
            tag=nbtlib.load(path)
            if shift_player(tag):pending[path]=encoded(tag);players.append(str(path.relative_to(world)))
        path=world/'level.dat';level=nbtlib.load(path)
        if 'Player' in level['Data'] and shift_player(level['Data']['Player']):pending[path]=encoded(level);players.append('level.dat#Player')
        backup=folder/'metadata_before';backup.mkdir()
        for path in pending:
            backups[path]=path.read_bytes() if path.exists() else None
            if backups[path] is not None:
                f=backup/path.relative_to(world);f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(backups[path])
        geometry=painter.apply('complete_hangar_incline_translation',session_lock=lock)
        for path,raw in pending.items():
            assert (path.read_bytes() if path.exists() else None)==backups[path]
            atomic_replace(path,raw)
        from verify_main_r20 import entities
        tags=entities(world);assert len(tags)==678
        for row in owned['actors']:
            tag=next(t for t in tags.values() if identity(t)==row['uuid'])
            assert list(map(float,tag['Pos']))==list(HANGAR.point(row['pos']))
        report.update(world_written=True,geometry=geometry,actors=actors_receipt,players=players,
            all_678_original_ids_preserved=True,native_lift_group={'before':'-26;-278','after':'86;366','floors':[-704,-630,-603]})
        (folder/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    except BaseException:
        for path,raw in backups.items():
            if raw is not None:atomic_replace(path,raw)
        if geometry is not None:
            applications=list(folder.glob('applied_*'));assert len(applications)==1
            for f in (applications[0]/'before').glob('r.*.mca'):atomic_replace(world/'dimensions/projectseele/geofront/region'/f.name,f.read_bytes())
            (applications[0]/'ROLLED_BACK.json').write_text('{"reason":"metadata stage failed"}','utf8')
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
