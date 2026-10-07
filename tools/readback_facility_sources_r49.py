"""Read final construction door/BE and migrated static sources only; never control a game."""
from pathlib import Path
import argparse,copy,gzip,json
import nbtlib
from query_blocks import read_box,iter_block_entities,palette_state
ROOT=Path(__file__).resolve().parents[1];DIM='projectseele:geofront'
def packed(q):
    x,y,z=q;n=((x&67108863)<<38)|((z&67108863)<<12)|(y&4095)
    return n-(1<<64) if n>=1<<63 else n
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r49/facilities/final_construction_readback.json');args=ap.parse_args()
    w=args.world.resolve();states={};bes={}
    for lo,hi in [((25,-365,314),(32,-356,317))]+[((x-2,-395,-224),(x+1,-393,-221)) for x in (7,49,91)]+[((x-2,-395,-224),(x+2,-393,-222)) for x in(-12,30,72)]:
        states.update(read_box(w,DIM,lo,hi));bes.update(iter_block_entities(w,DIM,lo,hi))
    components=[ROOT/'artifacts/rebuild_r49/facilities/F01_guard_facing_pilot_doors',ROOT/'artifacts/rebuild_r49/facilities/F02_closed_seele_vestibule_gate',ROOT/'artifacts/rebuild_r49/bridge_topology/R49_through_side_bridge_and_stairs']
    rows={}
    for c in components:
        with gzip.open(c/'forward.jsonl.gz','rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);q=tuple(r['pos']);assert q not in rows;rows[q]=r
    door_positions=[(x,y,-223) for x in(7,49,91) for y in(-394,-393)]+[(x,y,315) for x in(28,29) for y in(-364,-363)]
    reader_positions=[(27,-363,z) for z in(314,316)]
    door_proof=[]
    for q in door_positions+reader_positions:
        r=rows[q];tag=None if r['after_nbt'] is None else nbtlib.parse_nbt(r['after_nbt'])
        assert states[q]==r['after'] and bes.get(q)==tag,('Final door/BE differs',q,states[q],r['after'])
        door_proof.append(dict(pos=list(q),state=states[q],full_NBT_matches_installed_candidate=True,nbt=None if tag is None else tag.snbt()))
    old_reader=(31,-363,316)
    baseline=ROOT/'artifacts/rebuild_r48/construction/SEELE_R48_WORLD'
    old=dict(iter_block_entities(baseline,DIM,old_reader,old_reader))[old_reader]
    assert bes[old_reader]==old
    bridge_marker=json.loads((w/'r48_entry_plug_bridge.json').read_text('utf8'))
    assert bridge_marker['stair_z']==17 and bridge_marker['half_step_z']==18 and bridge_marker['landing_z']==[16] and bridge_marker['all_stairs_retract_before_plug_motion'] is True
    stair_proof=[]
    for cx in(-12,30,72):
        for side in(-2,2):
            cells=[]
            for z in(16,17,18):
                q=cx+side,-394,-240+z;assert states[q]==rows[q]['after'];cells.append(dict(pos=list(q),state=states[q]))
            assert 'entry_plug_bridge_deck' in cells[0]['state'] and 'andesite_stairs' in cells[1]['state'] and 'andesite_slab[type=bottom' in cells[2]['state']
            stair_proof.append(dict(bed_x=cx,side=side,cells=cells,node_foot_heights=[-393,-393,-393.5],maximum_entry_step=.5))
    patch=json.loads((ROOT/'artifacts/rebuild_r49/combined_generation/generation_recipe/file_patch.json').read_text('utf8'))
    sources={};source_files=[]
    for op in patch['operations']:
        actual=nbtlib.load(w/op['relative_target']);expected=nbtlib.load(op['after_file']);assert actual==expected,('Final static shard differs',op['relative_target'])
        source_files.append(dict(path=op['relative_target'],whole_original_and_new_NBT_equal_to_payload=True))
        for cell in actual['Static']:sources[int(cell['Pos'])]=(palette_state(actual['Palette'][int(cell['StateId'])]),cell.get('NBT'))
        if op['before_file']:
            previous=nbtlib.load(op['before_file'])
            assert all(actual[k]==v for k,v in previous.items() if k not in('Palette','Static'))
            assert list(actual['Palette'][:len(previous['Palette'])])==list(previous['Palette'])
            unchanged={int(c['Pos']):c for c in previous['Static'] if int(c['Pos']) not in {packed(q) for q in rows}}
            current={int(c['Pos']):c for c in actual['Static']}
            assert all(current[p]==v for p,v in unchanged.items())
    for q,r in rows.items():
        desired=None if r['after_nbt'] is None else nbtlib.parse_nbt(r['after_nbt'])
        assert sources[packed(q)]==(r['after'],desired),('Migrated Static cell/complete NBT differs',q)
    with gzip.open(ROOT/'artifacts/rebuild_r49/bridge_topology/full_extension_states.json.gz','rt',encoding='utf8') as f:phases=json.load(f)
    phase_fields=[]
    for phase in phases:
        cx=-12+42*phase['variant'];amount=phase['extension'];cells={tuple(q):s for q,s in phase['cells']}
        for side in(-2,2):
            for z in(16,17,18):
                s=cells[cx+side,-394,-240+z]
                if amount==9:assert s==states[cx+side,-394,-240+z]
                else:assert 'stairs' not in s and 'slab' not in s and 'entry_plug_bridge_deck' not in s
        phase_fields.append(dict(variant=phase['variant'],extension=amount,stairs_match_full_9_or_retract_before_motion=True))
    conference=json.loads((w/'r47_seele_conference.json').read_text('utf8'));lighting=json.loads((w/'r48_seele_lighting.json').read_text('utf8'))
    assert conference['access_policy']['middle_egress_without_card'] is False
    assert lighting['meeting_all_block_lights_zero_r49'] is True and len(lighting['ambient'])+len(lighting['table'])==23
    tasks=json.loads((ROOT/'artifacts/rebuild_r49/TASKS.json').read_text('utf8'))
    evidence={
        '5':dict(evidence='三间北门6个上下半门完整状态；原桥门、电话和座席位置保持',native='三名原NPC原椅/原栓往返已由root完成；真人卫兵门点击未测',steps=['带NERV权限从卫兵侧接近(7/49/91,-394,-223)，右键门并走入原休息室。','从屋内再次开门离开，门口停人时确认不会夹关；离开后观察五秒关闭。']),
        '15':dict(evidence='六座完整底半板18/阶梯17/平台16现场与Static匹配，30阶段阶梯字段匹配',native='原NPC旧登机点往返通过，真人踏步、占用收桥、全回收原生仍未测',steps=['从三床两侧固定环前接臂Z14..15进入贯穿桥，走至后接臂Z24绕房后返回。','沿相对X±2，先Z18半板、Z17阶梯、Z16上舱平台接近原舱口；正常点入原栓。','用正常整备/回收观察先撤踏步再收桥；有人仍站在桥/梯时，应暂停撤收。']),
        '16':dict(evidence='两面读卡器完整工厂BE均Linked=false/Clearance3，房门两扇四半完整，原电梯reader NBT保留；静态源906项全部吻合',native='最高卡真实点击、电梯真人出入与占用联锁未测；GameEvents吞首次MID刷卡的source缺陷已修，更新jar原生未验证',steps=['从电梯侧在(27,-363,316)持最高卡刷卡并保持0.3秒，双门应开六秒。','屋内(27,-363,314)同样必须最高卡；空手/低卡两面均拒绝，直接点门不会开启。','测试最高卡在副手、刷卡0.3秒内换掉卡或走远、门口站人、重新进入世界，确认拒绝/占用延迟关门。','在原(31,-363,316)最高卡首次刷卡应有真实读卡反馈并能叫梯，不能被通用控制先吞掉。']),
        '17':dict(evidence='会议metadata指定23个旧方块泛光全0，日常14；桌柔光/红字由root renderer负责',native='光影和无光影画面均待玩家验收，没有视觉通过',steps=['右键(17,-363,312)在日常/会议之间切换；会议应整房黑，仅顶部重点照桌，桌不刺眼、碑字红光。','分别用原光影与无光影检查门缝、桌表面、碑字和下照束；保存退出再登录验证灯态保持。'])}
    report=dict(schema=49,world=str(w),world_written=False,game_controlled=False,door_and_reader_actual_readback=door_proof,original_MID_reader_full_NBT_preserved=True,
                final_static_files=source_files,all_906_migrated_Static_states_and_complete_NBT_match=True,all_old_unmodified_Static_palette_and_Ground_preserved=True,
                final_stairs_actual_readback=stair_proof,phase_stair_fields=phase_fields,
                all_twenty_task_status_snapshot={k:dict(goal=v['goal'],state=v['state']) for k,v in tasks['items'].items()},task_item_evidence=evidence,
                event_source_fix='GameEvents first returns for finite conference/R49 readers and R49 doors; registration order cannot route them into generic lift call/seat handlers',
                source_fix_updated_jar_native_verified=False,visual_verified=False)
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(door_half_cells=10,reader_full_BEs=2,original_reader_NBT_preserved=True,static_shards=len(source_files),static_cells_checked=len(rows),stairs=6,phase_stair_fields=len(phase_fields),world_written=False,visual_verified=False),ensure_ascii=False))
if __name__=='__main__':main()
