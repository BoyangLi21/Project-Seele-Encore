"""Retire the complete obsolete belt inside UN00's widened pressure cell.

Keep the wet-cell boundary closed. Place the replacement pair of belts in the
measured dry service aisle, with full two-cell widths and stationary landings.
"""
from pathlib import Path
import argparse,copy,json,nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43'
WORLD=ROOT/'run/saves/SEELE_FIELD_R43_REVIEW';OUT=ART/'moving_devices/wet_cell_retirement'
FLOOR='projectseele:nerv_floor_panel'

def main(apply=False):
    OUT.mkdir(parents=True,exist_ok=True)
    if apply:
        from release_combat_r36 import guard
        guard()
    assert not list(OUT.glob('complete_device_move/applied_*/receipt.json')),'Never reapply a migrated component'
    parts=json.loads((ART/'moving_devices/wet_cell_components.json').read_text('utf8'))
    assert len(parts)==10 and all(c['kind']=='moving_walks' for c in parts)
    w=MeasuredWorld(WORLD);w.box((6380,74,-6242),(6424,83,-6130));w.load()
    tags=dict(iter_block_entities(WORLD,v.DIM,(6380,74,-6242),(6424,83,-6130)))
    changes={}
    def put(q,after,reason,allowed):
        before=w.block(q);assert before is not None and q not in tags,(q,'unmeasured or existing device NBT')
        assert before in allowed,(q,before,reason)
        if before!=after:changes[q]=(after,reason)
    for c in parts:
        for x,y,z,s,*rest in c['raw_cells']:
            assert y==76 and s.startswith('mtr:escalator_step[') and 'orientation=flat' in s
            put((x,y,z),FLOOR,'retire obsolete complete pressure-floor belt',{s})
    # The R41 generic walk repair cut this actual pressure-cell rear wall.
    for x in range(6418,6423):
        for y in range(77,80):put((x,y,-6227),'minecraft:gray_concrete','restore pressure boundary',AIR)
    runs=[(-6222,-6196),(-6188,-6162)];new_steps=[]
    for start,end in runs:
        for z in range(start,end+1):
            for first,direction in ((6392,True),(6395,False)):
                for x,side in ((first,'left'),(first+1,'right')):
                    assert all(w.get(x,y,z) in AIR for y in (77,78,79)),(x,z,'occupied pedestrian clearance')
                    assert w.get(x,75,z) not in AIR,(x,z,'missing measured bearing')
                    state=f'mtr:escalator_step[direction={str(direction).lower()},facing=north,orientation=flat,side={side},status=true]'
                    put((x,76,z),state,'complete paired belt in dry service aisle',{FLOOR});new_steps.append([x,76,z])
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
    for q,(after,why) in sorted(changes.items()):p.match((*q,*q),w.block(q),after,'r43/un_dry_service/'+why)
    # Mounted to the restored wall, outside the liquid volume and above feet.
    q=(6420,78,-6228);assert w.block(q) in AIR
    for x in range(6419,6422):
        for y in (78,79,80):assert w.get(x,y,-6227) in {'minecraft:gray_concrete','minecraft:air'}
    state='projectseele:station_departure_board[facing=north,wayfinding=true]'
    p.match((*q,*q),w.block(q),state,'r43/pressure_boundary_staff_direction')
    p.block_entities[q]=nbtlib.Compound(dict(id=nbtlib.String('projectseele:station_departure_board'),x=nbtlib.Int(q[0]),y=nbtlib.Int(q[1]),z=nbtlib.Int(q[2]),Wayfinding=nbtlib.Byte(1),Station=nbtlib.String('联合国试验机库'),Route=nbtlib.String('湿舱区域'),Row0=nbtlib.String('→ 西侧人员走廊'),Row1=nbtlib.String('登机请走外侧通道'),Row2=nbtlib.String('注液期间禁止进入')))
    cases=[]
    def case(name,path):cases.append(dict(id='r43/un_dry_service/'+name,path=path))
    for x in (6392.5,6393.5):case('north/'+str(x),[[x,77,-6159.5],[x,77,-6225.5]])
    for x in (6395.5,6396.5):case('south/'+str(x),[[x,77,-6225.5],[x,77,-6159.5]])
    for z in (-6225.5,-6192.5,-6159.5):
        case('cross/'+str(z),[[6386.5,77,z],[6398.5,77,z]])
        case('cross_return/'+str(z),[[6398.5,77,z],[6386.5,77,z]])
    case('west_bypass',[[6386.5,77,-6232.5],[6386.5,77,-6218.5]])
    case('west_bypass_return',[[6386.5,77,-6218.5],[6386.5,77,-6232.5]])
    p.meta.update(retired_components=[c['id'] for c in parts],retired_step_cells=sum(len(c['raw_cells']) for c in parts),new_step_cells=len(new_steps),wet_volume=[[6418,77,-6226],[6466,120,-6137]],dry_belt_runs=runs,
        replacement='West dry service aisle outside both the wet-cell wall and EVA transport envelope; retain original staff entrance/stair destination',
        route_retirement='Eight R41 un_through_port probes crossed the pressure wall and are retired, never counted as current passes',
        generators_fixed=['widen_un_hangars_r31.py','repair_spatial_interfaces_r41.py','prepare_spatial_native_r41.py'],walk_cases=cases,
        validation='Measured complete device/component plan; native movement, pressure states and visual checks pending')
    p.save_plan('complete_device_move');(OUT/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),'utf8')
    if apply:
        p.apply('complete_device_move')
        path=WORLD/'quality_walk_cases.json';original=path.read_bytes();(OUT/'quality_walk_cases.before.json').write_bytes(original)
        rows=json.loads(original);retired=[r for r in rows if r['id'].startswith('r41/un_through_port/')]
        assert len(retired)==8,'Explicit route retirement changed'
        rows=[r for r in rows if not r['id'].startswith('r41/un_through_port/')]+cases
        path.write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')),'utf8')
        (OUT/'retired_routes.json').write_text(json.dumps(retired,ensure_ascii=False,indent=2),'utf8')
        (WORLD/'r43_walk_cases.json').write_text(json.dumps(cases,ensure_ascii=False),'utf8')
        (WORLD/'retired_wet_cell_walks_r43.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')
    print('Complete components',len(parts),'retired cells',p.meta['retired_step_cells'],'new dry steps',len(new_steps),'native cases pending',len(cases),flush=True)

def finish_approach(apply=False):
    """Complete the old route's upstream assembly, not just its wet-cell parts."""
    out=OUT/'north_approach';out.mkdir(parents=True,exist_ok=True)
    assert not list(out.glob('complete_old_route/applied_*/receipt.json')),'Already migrated this approach'
    if apply:
        from release_combat_r36 import guard
        guard()
    w=MeasuredWorld(WORLD);w.box((6384,75,-6247),(6425,82,-6226));w.load()
    v.WORLD=WORLD;v.OUT=out;p=v.Painter()
    for x in (6418,6419,6421,6422):
        for z in range(-6239,-6228):
            q=(x,76,z);s=w.block(q);assert s.startswith('mtr:escalator_step[') and 'orientation=flat' in s
            p.match((*q,*q),s,FLOOR,'r43/retire_entire_old_staff_to_plug_route_approach')
    q=(6420,78,-6228);before=dict(iter_block_entities(WORLD,v.DIM,q,q))[q];after=copy.deepcopy(before)
    after['Row0']=nbtlib.String('↓ 北侧联络厅');after['Row1']=nbtlib.String('登机请循楼梯标识')
    p.update_block_entity(q,w.block(q),before,after,'r43/pressure_wall_returns_to_real_junction')
    board=(6416,79,-6242)
    for x in (6415,6417):
        for y in (77,78):
            q=(x,y,-6242);assert w.block(q) in AIR;p.match((*q,*q),w.block(q),'projectseele:nerv_sign_post','r43/north_junction_fixed_sign_posts')
    for x in range(6415,6418):
        for y in (79,80):assert w.get(x,y,-6242) in AIR
    state='projectseele:station_departure_board[facing=north,wayfinding=true]'
    p.match((*board,*board),w.block(board),state,'r43/north_junction_destinations')
    p.block_entities[board]=nbtlib.Compound(dict(id=nbtlib.String('projectseele:station_departure_board'),x=nbtlib.Int(board[0]),y=nbtlib.Int(board[1]),z=nbtlib.Int(board[2]),Wayfinding=nbtlib.Byte(1),Station=nbtlib.String('联合国试验机库'),Route=nbtlib.String('北侧联络厅'),Row0=nbtlib.String('← 登机楼梯'),Row1=nbtlib.String('→ 人员出口 · 双向步道'),Row2=nbtlib.String('湿舱不作人员通道')))
    paths=[dict(id='r43/un_dry_service/north_connection',path=[[6420.5,77,-6239.5],[6394.5,77,-6239.5],[6394.5,77,-6225.5]]),
           dict(id='r43/un_dry_service/north_sign_reader',path=[[6416.5,77,-6245.5],[6416.5,77,-6243.5]],readingBoard=list(board),readingWayfinding=True)]
    paths.append(dict(id=paths[0]['id']+'/return',path=paths[0]['path'][::-1]))
    catalogue=json.loads((WORLD/'quality_walk_cases.json').read_text('utf8'))
    staff=next(r for r in catalogue if r['id']=='r31/un00/staff_to_plug')
    paths.extend([dict(id='r43/un_dry_service/full_staff_to_plug',path=staff['path']),dict(id='r43/un_dry_service/full_staff_to_plug_return',path=staff['path'][::-1])])
    p.meta.update(retired_upstream_cells=44,reference='R22 original_mtr_walkways route r07/secret/continuous_staff_to_plug, including upstream -6239..-6229 run',
        reason='First after-photo showed a still-powered upstream belt pointing at the restored pressure wall; this is not an accepted endpoint',
        sign_directions='North-facing sign: screen-left = world east to retained boarding stair; screen-right = world west to dry staff exit',walk_cases=paths)
    p.save_plan('complete_old_route');(out/'cases.json').write_text(json.dumps(paths,ensure_ascii=False,indent=2),'utf8')
    if apply:
        (out/'quality_walk_cases.before.json').write_bytes((WORLD/'quality_walk_cases.json').read_bytes())
        (out/'r43_walk_cases.before.json').write_bytes((WORLD/'r43_walk_cases.json').read_bytes())
        p.apply('complete_old_route')
        catalogue.extend(paths);(WORLD/'quality_walk_cases.json').write_text(json.dumps(catalogue,ensure_ascii=False,separators=(',',':')),'utf8')
        (WORLD/'r43_walk_cases.json').write_text(json.dumps(paths,ensure_ascii=False),'utf8')
        (out/'metadata_before.json').write_text(json.dumps(staff,ensure_ascii=False,indent=2),'utf8')
    print('Retired upstream belt 44 cells; real junction sign and full staff route checks',len(paths),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--approach',action='store_true');a=p.parse_args();(finish_approach if a.approach else main)(a.apply)
