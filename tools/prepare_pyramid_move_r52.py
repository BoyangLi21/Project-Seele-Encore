"""Prepare the single Root pyramid move from the measured original component.

The public surface lift is reserved for its own extension; every original
artwork, inventory and access reader is carried with typed NBT. No save write.
"""
import argparse,json,copy,io,gzip,msvcrt
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


def encoded(tag):
    stream=io.BytesIO();tag.write(stream);return gzip.compress(stream.getvalue(),mtime=0)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    world=WORLD
    terminal_receipt=json.loads((BASE/'terminal_move/complete_terminal_translation/PLAN.json').read_text('utf8'))
    assert terminal_receipt['world_written'] and terminal_receipt['original_lilith_and_all_678_actor_ids_preserved']
    data=np.load(BASE/'survey/headquarters_and_original_station.npz')
    owner=np.load(BASE/'pyramid_component/owner_mask.npz')['owned']
    src_lo=tuple(map(int,data['origin']));shape=data['states'].shape
    src_hi=(src_lo[0]+shape[2]-1,src_lo[1]+shape[0]-1,src_lo[2]+shape[1]-1)
    lo=(src_lo[0],src_lo[1]-93,src_lo[2]);hi=src_hi
    current,current_pal=measure(lo,hi)
    names=list(dict.fromkeys(current_pal+list(map(str,data['palette']))+[
        'minecraft:air','minecraft:stone','minecraft:grass_block[snowy=false]']))
    codes={s:i for i,s in enumerate(names)}
    before=np.asarray([codes[s] for s in current_pal],np.uint16)[current]
    source=np.asarray([codes[str(s)] for s in data['palette']],np.uint16)[data['states']]
    old=before[93:93+shape[0]]
    assert np.array_equal(old[owner],source[owner]),'Frozen owned pyramid geometry changed'
    source_ownership=np.zeros(before.shape,dtype=bool)
    source_ownership[93:93+shape[0]]=owner
    new_only=owner & ~source_ownership[:shape[0]]
    natural={'minecraft:air','minecraft:cave_air','minecraft:stone',
             'minecraft:deepslate','minecraft:deepslate[axis=y]',
             'minecraft:grass_block[snowy=false]','minecraft:dirt','minecraft:tuff'}
    occupants={names[int(v)]:int(n) for v,n in zip(*np.unique(before[:shape[0]][new_only],return_counts=True))}
    # The measured old command-to-Dogma shaft continues below the frozen HQ
    # envelope. It belongs to the same two-main-lift migration, and its obsolete
    # portion is replaced with the lowered HQ before the original axis is moved.
    yy,zz,xx=np.ogrid[:shape[0],:shape[1],:shape[2]]
    old_main_shaft=(xx+lo[0]>=9)&(xx+lo[0]<=15)&(zz+lo[2]>=250)&(zz+lo[2]<=256)&(yy+lo[1]>=-515)&(yy+lo[1]<=-486)
    old_shaft_states=np.isin(before[:shape[0]],[codes[s] for s in ('projectseele:nerv_structural_panel','minecraft:sea_lantern') if s in codes])
    expected_old_shaft=new_only & old_main_shaft & old_shaft_states
    assert int(expected_old_shaft.sum())==626,'Old shaft ownership no longer matches exact measured baseline'
    other=np.unique(before[:shape[0]][new_only & ~expected_old_shaft])
    assert {names[int(v)] for v in other}<=natural,('Unrelated authored occupant in pyramid destination',occupants)
    after=before.copy()
    y=np.arange(shape[0])[:,None,None]+src_lo[1]
    fill=np.broadcast_to(np.where(y>-467,codes['minecraft:air'],
         np.where(y==-467,codes['minecraft:grass_block[snowy=false]'],codes['minecraft:stone'])),shape)
    after[93:93+shape[0]][owner]=fill[owner]
    translated=source.copy()
    marking=codes['projectseele:nerv_pyramid_marking'];panel=codes['projectseele:nerv_pyramid_panel']
    translated[translated==marking]=panel
    after[:shape[0]][owner]=translated[owner]
    # Resample the original block emblem and project onto the measured south
    # shell. Do not paint the glazed band or invent a replacement NERV graphic.
    original_logo=np.any(data['states']==list(data['palette']).index('projectseele:nerv_pyramid_marking'),axis=1)
    original_logo=original_logo[-406-src_lo[1]:-335-src_lo[1]+1,-6-src_lo[0]:66-src_lo[0]+1]
    logo=original_logo[np.rint(np.linspace(0,original_logo.shape[0]-1,33)).astype(int)[:,None],
                       np.rint(np.linspace(0,original_logo.shape[1]-1,33)).astype(int)[None,:]]
    logo_cells=[]
    for oy,ox in zip(*np.nonzero(logo)):
        x=14+int(ox);target_y=-462+int(oy);source_y=target_y+93
        row=source[source_y-src_lo[1],:,x-src_lo[0]]
        front=np.flatnonzero((row==panel)|(row==marking))
        assert len(front),'Logo point has no original shell support'
        z=src_lo[2]+int(front[-1]);q=(x,target_y,z)
        assert after[target_y-lo[1],z-lo[2],x-lo[0]]==panel
        after[target_y-lo[1],z-lo[2],x-lo[0]]=marking;logo_cells.append(q)
    current_tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    owned=json.loads((BASE/'pyramid_component/devices_and_actors.json').read_text('utf8'))
    references={(9,-566,253):(9,-541,253)}
    for row in owned['devices']:
        if row['id']=='movingelevators:elevator_tile':references[tuple(row['pos'])]=PYRAMID.block(row['pos'])
    vox.WORLD=world;vox.OUT=BASE/'pyramid_move';vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-960,320));cells=runs(painter,lo,before,after,names,'R52_complete_pyramid_vertical_move')
    for row in owned['devices']:
        old_tag=nbtlib.parse_nbt(row['nbt']);position=tuple(row['pos'])
        assert position in current_tags and current_tags[position].snbt()==old_tag.snbt()
        new=block_entity_in_frame(old_tag,PYRAMID,reference_positions=references)
        point=tuple(int(new[k]) for k in ('x','y','z'))
        painter.block_entities[point]=new
        index=(point[1]-lo[1],point[2]-lo[2],point[0]-lo[0])
        if before[index]==after[index]:
            painter.update_block_entity(point,names[int(after[index])],current_tags.get(point),new,'R52_complete_typed_pyramid_device')
    painter.meta.update(root_author=True,source_shift=[0,-93,0],whole_component=True,
        original_artwork_count=4,original_glazing_count=2344,public_surface_lift_reserved=True,
        original_external_logo_resized_and_raised=True,external_logo_cells=logo_cells,
        pending=['native lift group floor transforms','201 actor/home migrations','respawn reference migration',
                 'public lift lower extension','floor rings/shared lift/HQ station/lake','runtime directory activation'],playable=False)
    folder=painter.save_plan('complete_pyramid_translation')
    report=dict(world_written=False,changed_cells=cells,operations=len(painter.ops),typed_devices=len(owned['devices']),
                original_artworks=4,original_glazing=2344,external_logo_cells=len(logo_cells),source_shift=[0,-93,0],
                public_surface_shaft_not_moved=True,actors_and_runtime_pending=True)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if not args.apply:return
    assert not list(folder.glob('applied_*')),'Existing application requires readback, not replay'
    lock=acquire_world_lock();backups={};geometry_receipt=None
    try:
        actor_files,actor_receipt=prepare_actor_files(world,{r['uuid']:PYRAMID for r in owned['actors']},{r['uuid']:r['snbt'] for r in owned['actors']})
        pending=dict(actor_files)
        caps_path=world/'dimensions/projectseele/geofront/data/capabilities.dat';caps=nbtlib.load(caps_path)
        groups=caps['data']['movingelevators:elevator_groups']
        lift_receipts=[]
        for key in ('9;253','31;321','63;302'):
            group=groups[key]['group'];assert not bool(group['isMoving'])
            floors=list(map(int,group['floors']));assert -566 not in floors,'Retire old Terminal stop first'
            assert len(floors)==len(group['floorData'])
            group['floors']=nbtlib.IntArray([y-93 for y in floors])
            lift_receipts.append(dict(group=key,before=floors,after=list(map(int,group['floors']))))
        pending[caps_path]=encoded(caps)
        roster_path=world/'nerv_staff_r15.json';roster=json.loads(roster_path.read_text('utf8'))
        moved_staff={str(nbtlib.parse_nbt(r['snbt'])['StaffId']) for r in owned['actors'] if r['id']=='projectseele:nerv_staff'}
        for station in roster['stations']:
            if station['id'] in moved_staff:station['feet']=list(PYRAMID.block(station['feet']))
        pending[roster_path]=(json.dumps(roster,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        def owns_point(point):
            x,y,z=map(int,np.floor(point));ix,iy,iz=x-src_lo[0],y-src_lo[1],z-src_lo[2]
            return 0<=iy<shape[0] and 0<=iz<shape[1] and 0<=ix<shape[2] and bool(owner[iy,iz,ix])
        def shift_player(tag):
            changed=[]
            if str(tag.get('Dimension',''))=='projectseele:geofront' and owns_point(tuple(map(float,tag['Pos']))):
                assert 'RootVehicle' not in tag,'Vehicle-bound player needs explicit graph migration'
                tag['Pos']=nbtlib.List[nbtlib.Double]([nbtlib.Double(v) for v in PYRAMID.point(tuple(map(float,tag['Pos'])))])
                changed.append('Pos')
            if str(tag.get('SpawnDimension',''))=='projectseele:geofront' and all(k in tag for k in ('SpawnX','SpawnY','SpawnZ')):
                pos=tuple(int(tag[k]) for k in ('SpawnX','SpawnY','SpawnZ'))
                if owns_point(pos):
                    for k,v in zip(('SpawnX','SpawnY','SpawnZ'),PYRAMID.block(pos)):tag[k]=type(tag[k])(v)
                    changed.append('respawn')
            return changed
        player_receipts=[]
        for path in (world/'playerdata').glob('*.dat'):
            tag=nbtlib.load(path);changed=shift_player(tag)
            if changed:pending[path]=encoded(tag);player_receipts.append(dict(file=str(path.relative_to(world)),fields=changed))
        level_path=world/'level.dat';level=nbtlib.load(level_path)
        if 'Player' in level['Data']:
            changed=shift_player(level['Data']['Player'])
            if changed:pending[level_path]=encoded(level);player_receipts.append(dict(file='level.dat#Player',fields=changed))
        meta_backup=folder/'metadata_before';meta_backup.mkdir()
        for path in pending:
            backups[path]=path.read_bytes();target=meta_backup/path.relative_to(world);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(backups[path])
        geometry_receipt=painter.apply('complete_pyramid_translation',session_lock=lock)
        for path,raw in pending.items():
            assert path.read_bytes()==backups[path];atomic_replace(path,raw)
        from verify_main_r20 import entities
        assert len(entities(world))==678
        report.update(world_written=True,receipt=geometry_receipt,actor_receipt=actor_receipt,
                      native_lift_floors=lift_receipts,player_coordinate_updates=player_receipts,
                      playable=False,pending=['public lift extension','floor loop closure and common deep lift',
                      'station approaches','west lake and natural lake','runtime anchor rebinding'])
        (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    except BaseException:
        for path,raw in backups.items():atomic_replace(path,raw)
        if geometry_receipt is not None:
            applications=list(folder.glob('applied_*'));assert len(applications)==1
            for backup in (applications[0]/'before').glob('r.*.mca'):
                atomic_replace(world/'dimensions/projectseele/geofront/region'/backup.name,backup.read_bytes())
            (applications[0]/'ROLLED_BACK.json').write_text('{"reason":"metadata stage failed"}','utf8')
        raise
    finally:
        msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
