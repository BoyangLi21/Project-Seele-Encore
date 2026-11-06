"""Replace measured NERV wooden labels with existing compact metal nameplates.

Preserve every text line, location, facing and wall attachment. Interactive
or distinct rear-faced signs are rejected rather than losing their behaviour.
"""
import argparse,json,msvcrt,nbtlib
import regional_voxels as vox
from r52_spatial_plan import BASE
from query_blocks import read_box,iter_block_entities
from extend_world_depth_r52 import acquire_world_lock


def literal(raw):
    text=json.loads(raw)
    if isinstance(text,str):return text
    assert isinstance(text,dict) and set(text)<= {'text','color','bold','italic','underlined','strikethrough','obfuscated'},'Do not discard interactive/styled component semantics'
    return text.get('text','')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';out=BASE/'final_map_audit/tv_nameplates'
    inventory=json.loads((out/'WOOD_SIGN_INVENTORY.json').read_text('utf8'))
    assert len(inventory)==43
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320));rows=[];retained=[]
    for row in inventory:
        q=tuple(row['position']);state=read_box(world,vox.DIM,q,q)[q]
        tags=dict(iter_block_entities(world,vox.DIM,q,q));old=nbtlib.parse_nbt(row['nbt'])
        assert state==row['state'] and tags[q]==old
        front=[literal(s) for s in row['front']];rear=[literal(s) for s in row['back']]
        assert not any(rear) or rear==front,'Distinct rear text needs a two-sided component'
        lines=[line for line in front if line]
        if not lines:
            retained.append(dict(position=q,reason='Unlabelled sign may be original furniture trim; not a room nameplate. Keep complete component for separate visual review.'))
            continue
        assert len(lines)<=4
        props=dict(v.split('=',1) for v in state[:-1].split('[',1)[1].split(','));face=props['facing']
        normal={'north':(0,0,-1),'south':(0,0,1),'east':(1,0,0),'west':(-1,0,0)}[face]
        backing=tuple(v-n for v,n in zip(q,normal));support=read_box(world,vox.DIM,backing,backing)[backing]
        assert support.split('[')[0] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:water'),('Floating original label requires separate repair',q)
        desired=f'projectseele:nerv_direction_panel[facing={face},wayfinding=true]'
        tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),
            'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),
            'Wayfinding':nbtlib.Byte(1),'RoomPlaqueR52':nbtlib.Byte(1),
            'Station':nbtlib.String(lines[0]),'Route':nbtlib.String('房间入口'),'PlatformCentre':nbtlib.Long(0)})
        for i,text in enumerate((lines[1:]+['']*3)[:3]):tag['Row'+str(i)]=nbtlib.String(text)
        encoded=[str(tag['Station'])]+[str(tag['Row'+str(i)]) for i in range(3)]
        assert [s for s in encoded if s]==lines
        p.exact((*q,*q),state,desired,'R52_NERV_industrial_room_nameplate');p.block_entities[q]=tag
        rows.append(dict(position=q,zone=row['zone'],facing=face,all_text=lines,backing_state=support,
            before_state=state,after_state=desired,before_nbt=row['nbt'],after_nbt=tag.snbt()))
    p.meta.update(root_author=True,component='NERV room labels only',room_entrance_type_excluded_from_automatic_wayfinding=True,
        label_count=len(rows),all_original_text_and_facing_preserved=True,interactive_controls_unchanged=True)
    stage=p.save_plan('metal_room_nameplates');report=dict(world_written=False,nameplates=rows,retained_unlabelled_components=retained,
        all_original_text_preserved=True,original_NERV_volume_and_doors_unchanged=True,
        reference='Original TV industrial control-room/console materials; user-directed NERV game room names retained.',native_art_accepted=False)
    if args.apply:
        assert not list(stage.glob('applied_*')),'Do not replay'
        lock=acquire_world_lock()
        try:report.update(world_written=True,receipt=p.apply('metal_room_nameplates',session_lock=lock))
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
        for row in rows:
            q=tuple(row['position']);assert read_box(world,vox.DIM,q,q)[q]==row['after_state']
            assert dict(iter_block_entities(world,vox.DIM,q,q))[q]==nbtlib.parse_nbt(row['after_nbt'])
    (stage/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='nameplates'}),'count',len(rows),flush=True)


if __name__=='__main__':main()
