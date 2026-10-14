"""Native five-stop personnel lift joining HQ, hangar and full Terminal layer.

Copies the verified original Moving Elevators car, retaining complete typed
button/display state. Every gallery ends on a measured original floor.
"""
import argparse,copy,json,msvcrt
import nbtlib
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE,Frame
from facility_frame_nbt_r52 import state_in_frame,block_entity_in_frame
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from prepare_pyramid_move_r52 import encoded
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace
from query_blocks import iter_block_entities

STOPS=[(-766,'中央教条 · 莉莉丝层'),(-704,'机库整备维护层'),(-630,'机库登机层'),(-603,'三机观察廊'),(-554,'NERV 总部入口层')]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';lo=(84,-769,372);hi=(113,-548,412)
    actual,palette=measure(lo,hi);names=list(palette)
    source=np.load(BASE/'survey/original_hangar_transfer_launch.npz');o=source['origin'];sp=list(map(str,source['palette']))
    frame=Frame(90,-170,-160,436)
    names=list(dict.fromkeys(names+[state_in_frame(s,frame) for s in sp]+['projectseele:nerv_structural_panel',
        'projectseele:nerv_wall_panel','projectseele:nerv_floor_panel','projectseele:nerv_strip_light',
        'minecraft:air','minecraft:gray_stained_glass','movingelevators:elevator_block[facing=north]',
        'movingelevators:button_block','movingelevators:display_block']))
    ids={s:i for i,s in enumerate(names)};before=np.asarray([ids[s] for s in palette],np.uint16)[actual];after=before.copy()
    def sl(b):
        x,y,z,X,Y,Z=b;assert lo[0]<=x<=X<=hi[0] and lo[1]<=y<=Y<=hi[1] and lo[2]<=z<=Z<=hi[2],b
        return np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]
    def fill(b,state):after[sl(b)]=ids[state]
    floor='projectseele:nerv_floor_panel';wall='projectseele:nerv_wall_panel';struct='projectseele:nerv_structural_panel'
    fill((104,-768,403,112,-548,411),struct);fill((105,-767,404,111,-549,410),'minecraft:air')
    # Author four bounded galleries; the top landing uses the existing HQ
    # corridor and escalator without replacing either.
    for feet,_ in STOPS[:-1]:
        end=391 if feet==-766 else 374
        centre=94 if feet==-704 else 88
        # Leave the last original floor row intact, only opening its wall.
        old_floor=before[feet-1-lo[1],end-lo[2],centre-lo[0]]
        assert names[int(old_floor)] in {floor,'minecraft:gray_concrete'}
        boxes=[(105,feet-1,396,111,feet+4,403),(centre-3,feet-1,396,111,feet+4,402),(centre-3,feet-1,end,centre+3,feet+4,402)]
        for b in boxes:fill(b,wall)
        for b in boxes:fill((b[0],feet-1,b[2],b[3],feet-1,b[5]),floor)
        for b in [(106,feet,397,110,feet+3,403),(centre-2,feet,397,110,feet+3,401),(centre-2,feet,end,centre+2,feet+3,401)]:fill(b,'minecraft:air')
        for z in range(end+4,400,8):fill((centre,feet+4,z,centre,feet+4,z+1),'projectseele:nerv_strip_light')
        fill((96,feet+4,399,97,feet+4,399),'projectseele:nerv_strip_light')
    # Original car source geometry is [Y,Z,X]. A +90 yaw transposes X/Z and
    # reverses the new X index; it does not change floor size or machinery.
    src=source['states'][-395-o[1]:-389-o[1]+1,-280-o[2]:-276-o[2]+1,-31-o[0]:-27-o[0]+1]
    car=np.asarray([ids[state_in_frame(s,frame)] for s in sp],np.uint16)[src].transpose(0,2,1)[:,:,::-1]
    after[sl((106,-555,405,110,-549,409))]=car
    devices=json.loads((BASE/'survey/original_hangar_transfer_launch_devices.json').read_text('utf8'))
    button=nbtlib.parse_nbt(next(r['nbt'] for r in devices if r['pos']==[-27,-393,-278]))
    display=nbtlib.parse_nbt(next(r['nbt'] for r in devices if r['pos']==[-27,-392,-278]))
    controller=nbtlib.parse_nbt(next(r['nbt'] for r in devices if r['pos']==[-26,-394,-278]))
    additions={}
    for original in (button,display):
        t=block_entity_in_frame(original,frame,reference_positions={(-26,-468,-278):(108,-766,410)})
        additions[tuple(int(t[k]) for k in ('x','y','z'))]=t
    for feet,title in STOPS:
        # Five-wide landing leaf, three-wide cabin leaf and permanent
        # thresholds. Native cage alignment owns which landing can open.
        fill((106,feet-1,403,110,feet-1,404),floor)
        fill((106,feet,403,110,feet+2,403),'minecraft:air' if feet==-554 else 'minecraft:gray_stained_glass')
        fill((108,feet,410,108,feet,410),'movingelevators:elevator_block[facing=north]')
        t=copy.deepcopy(controller)
        for key,value in zip(('x','y','z'),(108,feet,410)):t[key]=nbtlib.Int(value)
        t['data']['facing']=nbtlib.Int(2);t['data']['name']=nbtlib.String(title);t['data']['color']=nbtlib.Int(1 if feet==-766 else 3)
        additions[(108,feet,410)]=t
        for proto,dy,state in ((button,1,'movingelevators:button_block'),(display,2,'movingelevators:display_block')):
            point=(111,feet+dy,403);fill((*point,*point),state);t=copy.deepcopy(proto)
            for key,value in zip(('x','y','z'),point):t[key]=nbtlib.Int(value)
            if proto is button:
                for key,value in {'facing':2,'controllerFacing':2,'controllerX':108,'controllerY':feet,'controllerZ':410}.items():t['data'][key]=nbtlib.Int(value)
            additions[point]=t
    current=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    for point,tag in current.items():
        x,y,z=point;assert before[y-lo[1],z-lo[2],x-lo[0]]==after[y-lo[1],z-lo[2],x-lo[0]],('Existing device touched',point)
    vox.WORLD=world;vox.OUT=BASE/'shared_deep_lift';vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-960,320))
    count=runs(painter,lo,before,after,names,'R52_shared_native_deep_lift')
    painter.block_entities.update(additions)
    painter.meta.update(root_author=True,cabin_original_geometry=True,native_controller=[108,410],floors=STOPS,
        whole_terminal_below_hangar=True,existing_hq_escalator_preserved=True,playable=False)
    folder=painter.save_plan('native_shared_deep_lift')
    report=dict(world_written=False,playable=False,changed_cells=count,typed_devices=len(additions),floors=STOPS,
        cabin_centre=[108,-554,407],facing='north',controller_xz=[108,410],
        gallery_endpoints=[[94 if y==-704 else 88,y,391 if y==-766 else 374] for y,_ in STOPS[:-1]],
        pending=['live S20 spec registration/landing-door interlock','native call/ride all floors','whole floor loop inspection'])
    (folder/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
    if not args.apply:return
    assert not list(folder.glob('applied_*'))
    lock=acquire_world_lock();caps_path=world/'dimensions/projectseele/geofront/data/capabilities.dat';raw=caps_path.read_bytes();geometry=None
    try:
        caps=nbtlib.load(caps_path);groups=caps['data']['movingelevators:elevator_groups'];assert '108;410' not in groups
        group=copy.deepcopy(groups['86;366']);group['pos']['x']=nbtlib.Int(108);group['pos']['z']=nbtlib.Int(410);group['pos']['facing']=nbtlib.Int(2)
        group['group']['floors']=nbtlib.IntArray([y for y,_ in STOPS])
        group['group']['floorData']=nbtlib.List[nbtlib.Compound]([nbtlib.Compound({'color':nbtlib.Int(1 if y==-766 else 3),'name':nbtlib.String(title),'isCageAvailable':nbtlib.Byte(y==-554)}) for y,title in STOPS])
        groups['108;410']=group
        (folder/'capabilities_before.dat').write_bytes(raw)
        geometry=painter.apply('native_shared_deep_lift',session_lock=lock)
        assert caps_path.read_bytes()==raw;atomic_replace(caps_path,encoded(caps))
        check=nbtlib.load(caps_path)['data']['movingelevators:elevator_groups']['108;410']
        assert list(map(int,check['group']['floors']))==[y for y,_ in STOPS]
        report.update(world_written=True,receipt=geometry,native_group_installed=True)
        (folder/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    except BaseException:
        atomic_replace(caps_path,raw)
        if geometry is not None:
            app=list(folder.glob('applied_*'));assert len(app)==1
            for f in (app[0]/'before').glob('r.*.mca'):atomic_replace(world/'dimensions/projectseele/geofront/region'/f.name,f.read_bytes())
            (app[0]/'ROLLED_BACK.json').write_text('{"reason":"native group install failed"}','utf8')
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
