"""Close-out inventory/protection bytes from frozen artifacts only; no live-world read."""
from pathlib import Path
from collections import Counter
import json,gzip,hashlib,shutil
from prepare_city_ecology_protection_r44 import compress_columns

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44';CITY=ART/'city_expansion'
OUT=CITY/'manual_review_closeout_20261001_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assert not OUT.exists();OUT.mkdir()
    names=[('箱根西侧生活区','hakone_west_complete_service_landing_v17',307),
           ('第三东京北侧新街区','tokyo_supported_continuous_roofs_v16',1383),
           ('霧里新团地及服务区','kirisato_whole_joined_shores_v35',3133),
           ('美里住宅结构与户内','tv_misato_full_sealed_warm_finish_v13',334),
           ('TV式学校与体育馆','tv_school_connected_current_tokyo_campus_v22',629)]
    districts=[];files=[];reservations=[]
    for label,name,native in names:
        folder=CITY/name;d=json.loads((folder/'new_district.json').read_text('utf8'))
        contracts=list(folder.glob('construction_contract_refrozen_v*.json'));contract=max(contracts,key=lambda p:int(p.stem.rsplit('_v',1)[1]))
        receipts=[p for p in (folder/'root_install').rglob('receipt.json')if p.parent.name.startswith('applied_')and json.loads(p.read_text('utf8')).get('verified')]
        assert receipts,(name,'Actual verified installation required');receipt=max(receipts,key=lambda p:p.parent.name)
        buildings=[]
        for b in d['buildings']:
            buildings.append(dict(id=b['id'],label=b.get('label',b['id'].split('/')[-1]),kind=b['kind'],bounds_xz=b['bounds'],floor_feet=b.get('floor_feet',[b['floor']+1]),
                entry=b['entry'],door=b['door'],street_handoff=b['actual_street_handoff'],roof_y=b['roof']))
        districts.append(dict(label=label,installed_latest=name,dimension='projectseele:geofront',bounds=d['bounds'],buildings=buildings,
            operating_station=d.get('station'),operating_platform_id=d.get('operating_platform'),existing_buildings=len(buildings),
            complete_floor_planes=len(d['floors']),native_walk_obligations=native,actual_native_passed=True,human_art_acceptance=False,
            contract=str(contract.resolve()),receipt=str(receipt.resolve()),receipt_sha256=sha(receipt)))
        reservation=folder/'ecology_reservations.json';reservations+=json.loads(reservation.read_text('utf8'))['reservations']
        for p in [contract,receipt,folder/'new_district.json',folder/'ecology_reservations.json',folder/'forward.jsonl.gz',folder/'inverse.jsonl.gz']:
            files.append(dict(path=str(p.resolve()),sha256=sha(p)))
    # Both before provider files are already frozen from the 552-volume epoch.
    # Never read or modify the active construction save during close-out.
    provider_base=ART/'ecology/installed_t27_k14_w6_school_misato_protection_v2'
    combined=compress_columns(reservations);additional={tuple(r['bounds'])for r in combined};provider_plan=[]
    for index,target in enumerate([ROOT/'src/main/resources/data/projectseele/dimension/geofront.json',ROOT/'run/saves/SEELE_FIELD_R44_REVIEW/datapacks/tv_world_preview/data/projectseele/dimension/geofront.json']):
        before=provider_base/f'provider_{index:02d}.before.json';data=json.loads(before.read_bytes());provider=data['generator']['biome_source'];old=list(provider['protected_volumes']);old_set=set(map(tuple,old))
        add=sorted(additional-old_set);provider['protected_volumes']=old+[list(r)for r in add];assert provider['protected_volumes'][:len(old)]==old
        backup=OUT/f'provider_{index:02d}.before.json';after=OUT/f'provider_{index:02d}.after.json';shutil.copy2(before,backup);after.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
        provider_plan.append(dict(target=str(target),before=str(backup.resolve()),expected_sha256=sha(backup),bytes_from=str(after.resolve()),after_sha256=sha(after),
            inverse=dict(target=str(target),expected_sha256=sha(after),bytes_from=str(backup.resolve())),existing_prefix_volumes=len(old),added_exact_volumes=len(add),total_volumes=len(old)+len(add)))
    (OUT/'installed_geometry_protection_only_plan.json').write_text(json.dumps(dict(forward=provider_plan,root_current_hash_check_required=True,
        source_provider_written=False,world_provider_written=False,live_world_read=False,root_only_install=True,native_future_generation_verified=False,
        scope='Minimum additive exact 3D protection for the actually installed five city/landmark groups, including K35 supports and real public pavement. Original552 prefix preserved; natural lawn transitions not blanket reserved. No vegetation author queue or terrain generation is started.'),indent=2),'utf8')
    geof=dict(dimension='projectseele:geofront',bounds=[720,-530,560,1080,-350,940],two_continuous_ridges_and_valley_installed=True,
        first_whole_landform_cells=2095463,followup_v5_write_cells=176661,write_counts_overlap_not_unique_cells=True,old_whole_tree_cells_moved=62,small_native_plants_moved=316,
        applied_base=str((CITY/'tv_geofront_continuous_range_v1/frozen_whole_geometry_v2/root_install/whole_landform_progress.json').resolve()),
        applied_v5=str((CITY/'geofront_tree_integrated_range_v5/root_install/replay_continuous_range_and_whole_native_tree/continuous_range_and_whole_native_tree/applied_20261001_151536_795385/receipt.json').resolve()),
        compiled_ground_columns_verified=116039,compiled_proof=str((CITY/'geofront_tree_integrated_range_v5/root_composed_compiled_generator_v1/result.json').resolve()),
        actual_native_photos=str((ART/'space_photos/hills_v5_and_compact_misato_visible_features_v2/20261001_170059').resolve()),
        native_new_chunk_generation_verified=False,art_passed=False,manual_focus='从谷地/山脊看连贯坡形、实际石壳和总部视锥；当前偏暗且几乎裸山。没有用假天空或无形灯棋盘遮掩。')
    runtime_files=[ROOT/'src/main/java/com/projectseele/world/TvAuthoredTerrainR44.java',ROOT/'src/main/java/com/projectseele/world/TvWorldPreviewTerrain.java',
        ROOT/'src/main/resources/data/projectseele/worldgen/authored/geofront_east_ranges_r44.json.gz',
        ROOT/'src/main/java/com/projectseele/world/CityPersonnelDoorR44.java',ROOT/'src/main/java/com/projectseele/world/CityRainPipeR44.java',ROOT/'src/main/java/com/projectseele/world/CityRainGutterR44.java']
    for p in runtime_files:assert p.exists();files.append(dict(path=str(p.resolve()),sha256=sha(p)))
    future_surface=CITY/'kirisato_whole_joined_shores_v35/exact_natural_surface_targets.json.gz'
    files.append(dict(path=str(future_surface.resolve()),sha256=sha(future_surface),installed_in_generator=False))
    manifest=dict(user_scope='立即停止新制作；六包半成品供人工验收；未完成下轮继续',source_repo=str(ROOT),construction_world='SEELE_FIELD_R44_REVIEW',
        worker_world_writes=False,live_world_read=False,art_approval=False,districts=districts,geofront=geof,
        applied_new_building_total=50,counts='West6 + Tokyo27 + Kirisato14 + Misato1 + School2. K35 is landscape repair of K13, not another14 buildings.',
        runtime_minimum=['Project SEELE current compiled jar/resources and existing full dependency set must be preserved.','AnotherFurniture1.20.1-3.0.4 is required by actual installed dining table/chair/sofa states.','MTR4.0.5 and existing Moving Elevators/runtime dependencies remain; this list does not authorize removing other source-world mods.',
            'GeoFront exact authored heightfield gzip and its compiled reader are mandatory; no new world generation or ecology author dispatch.'],
        pure_client='第六包保留Forge/模组/模组内置模型贴图及存档兼容依赖，禁用外置材质包和光影。不能把纯净版做成丢失AnotherFurniture或ProjectSEELE方块注册的原版客户端。',
        exclude_uninstalled=['kirisato_private_source_street_life_v36 (four source-only lamps, never applied)','tv_misato_matte_plaster_v14 (713 cells, source candidate only)','All rejected/earlier uninstalled city/school/Misato variants','Full remaining46177 ecology361batches and cavity daylight implementation (not executed/implemented)'],
        unresolved=['城市立面重复、空街景、大片灰岸；新增完整景观/灯/电线/绿化生活设施未完成。','学校庭院/岸线/操场细节和全场地艺术仍未通过。','美里家仍是v13高反射石英；独立哑光材候选未施装；厨房/家具质感仍待完善。','GeoFront当前BLOCK/SKY/raw0，sapling生长>=9条件失败；22点只证明存活/支持与光照，不证明自然生长。','全部生态仅30个校准origins已装；46177剩余/361批未跑；旧执行epoch不能派发。','GeoFront116039列仅实际compiled ground读取一致，未证明新chunk生成；K35 114591自然地表列future surface loader未接入。','未来生成新3D保护需要Root核哈希安装本closeout候选并验证；本worker未装provider。','原193楼/93升降中心楼/675树/799道路等全工程覆盖、美术和实际交通生命周期由Root总清单继续，不因本清单功能数关闭。'],
        files=files)
    (OUT/'installed_city_landform_delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
    text=['# R44 城市与地下地形：半成品人工验收清单','','这是已施装清单，不是全域完成或美术通过。第六客户端保留必要模组与内置资源，仅去掉外置材质/光影。','','| 地点 | 已装范围 | 直接到访站立点（维度 projectseele:geofront） | 人工重点 |','|---|---|---|---|']
    focus={'箱根西侧生活区':'住宅/旅馆入口、店铺封闭橱窗与侧后勤门、完整小庭院、与原路标高衔接；街景仍空。','第三东京北侧新街区':'27栋的屋面连续性、店铺11前庭承重、真实门/楼梯/全部楼层与接站步行；多类生活街景未完成。','霧里新团地及服务区':'14栋外廊/院子、173岸段/木跨、水面保留、整片坡地和所有原入口；灰岸与重复立面待美术。','美里住宅结构与户内':'三层玄关→厨房餐桌→客厅/电视→短厅卧室/湿区/阳台；2.5m净高与封顶；当前石英镜面、粗家具仍未通过。','TV式学校与体育馆':'双扇校门/鞋柜、两翼教室/楼梯/屋顶、体育馆宽前庭、操场及校场岸线；功能过，美术未过。'}
    for d in districts:
        b=d['buildings'][0];x,y,z=b['street_handoff'];pose=f'({x+.5:g}, {y:g}, {z+.5:g})'
        text.append('| '+d['label']+' | '+str(d['existing_buildings'])+'建筑 / '+str(d['complete_floor_planes'])+'已占用楼面 | '+pose+' | '+focus[d['label']]+' |')
    text+=['','每栋的精确边界、门、入口、全部楼层和接街点见 installed_city_landform_delivery_manifest.json；原生步行不等于真实闸机/列车/机场完整生命周期。','','GeoFront 新连续双脊/谷地范围 X720..1080、Z560..940、地下约Y−482..−421。实际光影照片路径和安装收据见manifest。现有裸山/暗景不是最终景观；不要把地下client ambient .62当服务器日光。','','未施装街景灯、哑光住宅和整域植被均不装入当前存档。新3D保护最小候选见 installed_geometry_protection_only_plan.json，Root核当前文件SHA后才可安装；它不运行生态。','','原作依据边界：美里屋内关系来自亲看的fan TV平面图，房间米制/楼层/选址是推演；学校参考含官方活动中的二级模型，不冒称TV原设定。地形参照TV帧与Chronicle截面，缩尺是推演。研究截图/官方图不进发布assets。','','以上供人工体验和指出问题，所有未完成项列在manifest，下一轮继续。']
    (OUT/'城市地形_人工验收.md').write_text('\n'.join(text)+'\n','utf8')
    snapshots=OUT/'source_inputs';snapshots.mkdir();shutil.copy2(Path(__file__),snapshots/Path(__file__).name)
    print('Close-out:',sum(d['existing_buildings']for d in districts),'actually installed buildings;',len(files),'frozen/runtime references;',[(p['existing_prefix_volumes'],p['added_exact_volumes'],p['total_volumes'])for p in provider_plan],'; no world/source writes',flush=True)

if __name__=='__main__':main()
