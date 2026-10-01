"""Ground whole-facility production cards in existing exact object identities.

No world reads/writes, dispatch, compilation or acceptance promotion. Cards
retain every native platform, three-dimensional walk obligation and original
bay identity while tying architectural decisions to real interface locations.
"""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json, math

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/rebuild_r44/facility_transit_r44"
OUT = ART / "facility_workpieces_v1"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def source(path):
    return {"path": str(Path(path).resolve()), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def main(out=OUT):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    catalogue_path = ROOT / "artifacts/repair_r43/facility_catalogue/catalogue.json"
    transit_path = ART / "native_transit_cases/cases.json"
    walks_path = ART / "station_walk_cases_v2/station_walk_cases.json"
    lifts_path = ART / "measured_interfaces_v3/lifts.json"
    frame_path = ART / "hangar_tv_calibration_v2/semantic_frame.json"
    catalogue, transit, walks, lifts, frame = map(read, (catalogue_path, transit_path, walks_path, lifts_path, frame_path))
    assert len(catalogue["stations"]) == 20 and len(transit["cases"]) == 38 and len(walks) == 501
    platform_cases = {case["source_platform"]: case for case in transit["cases"]}
    station_cards = []
    for station in catalogue["stations"]:
        lo, hi = station["bounds"]
        platform_ids = {platform["id"] for platform in station["platforms"]}
        relevant = []
        for case in walks:
            # Existing authored IDs and measured path volumes attach these
            # obligations; a station rectangle is not a construction mask.
            named = case.get("station_id") == station["id"] or any(f"/{pid}/" in case["id"] for pid in platform_ids)
            within = any(all(lo[i] - 4 <= point[i] <= hi[i] + 4 for i in range(3)) for point in case["path"])
            if named or within:
                relevant.append({"id": case["id"], "points": len(case["path"]), "first": case["path"][0], "last": case["path"][-1],
                                 "height_range": [min(q[1] for q in case["path"]), max(q[1] for q in case["path"])],
                                 "source_platform": case.get("source_platform"), "requires_actual_stairs": any(abs(a[1] - b[1]) > .1 for a, b in zip(case["path"], case["path"][1:]))})
        interfaces = [platform_cases[pid] for pid in platform_ids if pid in platform_cases]
        has_air = any(platform["mode"] == "AIRPLANE" for platform in station["platforms"])
        if not interfaces:
            kind = "unresolved_native_station_service"
            construction = ["按原站名、全区域和周围实际铁路查明本区域当前用途；保留已建公共入口和人行连接。", "本目录无任何原生站台身份，不能伪造车次或把尚未查清的区域计成已验收车站。"]
        elif has_air:
            kind = "airport_terminal_and_interchange"
            construction = ["以原终端入口—站厅—列车层—登机梯的真实高差组织导视；到达与出发各自留出完整步行带。", "已有顶棚、立柱、候机座位和服务窗口组成一座终端，暖灰地面、奶油色站名牌和真实时刻板形成清楚层级。", "两格原生步道贯通长联络廊，平段无扶手，固定旁通和落脚缓冲延续到真实登机梯。"]
        elif hi[1] < 0:
            kind = "enclosed_underground_station"
            construction = ["站厅、所有铁路口、楼梯和电梯前室使用连续屋面、外围墙和实际支承；人与车的运行体积保持独立。", "蓝灰围护、灰绿设备面、侧向荧光照明和薄金属牌组成NERV年代语汇；每处真正决策口指向下一段实际通路。", "两格原生步道用于完整长联络廊，站内固定旁通能到全部列车门和出口，不把围栏后的机械面算公共楼面。"]
        elif len(platform_ids) >= 3:
            kind = "regional_interchange"
            construction = ["按原站台身份和实际楼层拆分换乘路径；分层楼梯的上下口、过桥转角和每个站台入口各有方向牌。", "结构柱、雨棚、侧候车区和简洁站务窗口形成完整站房；原生盲道、排水和站台门整条保留。", "色带用于真实线路区分，所有站序与下一站由同版原生线路定义；乘客能在进站时确认方向。"]
        else:
            kind = "period_surface_station"
            construction = ["以原街道入口、站房口、长梯和完整站台雨棚为一组建筑；坡地站的桥柱和山体收口都要落到真实支撑。", "浅灰矿物地面、细立柱、克制奶油色站名牌、茶色侧座和原有纸质公告形成九十年代公共设施细节。", "完整楼梯和固定旁通保持直接；候车陈设占据侧湾，真实发车板和门侧全线图从全部乘车口读得到。"]
        station_cards.append({"station_id": station["id"], "name": station["name"], "measured_identity_bounds": station["bounds"],
            "architecture": kind, "build_decisions": construction, "platforms": station["platforms"],
            "actual_origin_next_stop_interfaces": [{"source_platform": c["source_platform"], "destination_platform": c["destination_platform"],
                "mode": c["mode"], "service": c["service"], "source_staging": c["source"]["staging"],
                "whole_source_exit_path": c["source"]["exit_path"], "destination_station": c["destination"]["station_name"]} for c in interfaces],
            "authored_three_dimensional_journeys": relevant,
            "public_gate": {"policy": "existing_free_public_service", "architecture": "原生MTR自动开闭的双向人员闸口，在实际入口阈口组织；NERV权限卡读卡器独立。",
                            "native32_shapes": "root下一原生窗口导出后，逐站按完整入口/出口/占用空间生成exact候选。", "state": "NOT_INSTALLED_UNVERIFIED"},
            "sources": ["docs/ART_DIRECTION_R24.md:1990新宿站务与茶饮柜台、1989田园调布站；本轮沿用既有已观看参考，不声称重新看过全档案。",
                        "docs/TV_NERV_ARCHITECTURE_REFERENCE.md sections6/8:机库与人员路线分离；各车站平面为D级项目工程解释。"],
            "finish": "完整入口至自然登车、另一端自然下车、真实换乘与所有楼层走出；正反原生全景和冷重登通过后才计入完成。",
            "status": "PRODUCTION_CARD only; scene, native operation, all journeys and user visual approval pending"})
    (out / "station_cards.json").write_text(json.dumps(station_cards, ensure_ascii=False, indent=2), encoding="utf8")

    stages = [
        ("wet_standby", "PARKED", "LCL中三原机，双侧拘束接触实际肩面；连续工作廊与真实门外呼梯入口可见。", "侧照明显示蓝灰壳/液面/绿色机械；pa_standby只来自真实状态切换。"),
        ("crew_boarding_and_bridge", "PARKED→BRIDGE_RETRACTING", "从原工作层沿固定侧廊抵达后颈可收桥和原canonical插栓；无人/占用/取消状态各有真实安全通路。", "人员层照明和薄边缘护栏便于看清胶囊入口；收桥后真正让出载台体积。"),
        ("plug_alignment_and_insertion", "PLUG_INSERTING", "吊轨、四索、万向夹具与颈口使用同一canonical轴，倾斜对准、插入、夹具脱离连贯发生。", "局部检修光照出圆口与接触面；pa_insert与原生机械声跟随真实插入阶段。"),
        ("socket_lock_and_drain", "PLUG_LOCKING→DRAINING", "颈盖闭合、插栓锁定后排液；肩部拘束先脱离表面再收回，透明液面连续下降。", "pa_lock/pa_drain与门锁声同步；不能仅换颜色或瞬移液面。"),
        ("transfer_ramp", "TO_SILO", "运输门全高打开，载台与背靠板/原机一体进入连续共用绿机械大厅，长坡导槽和承重接触连续。", "门侧警示与走廊灯按实际门开闭变化，pa_transfer来自真实进程；人员通路独立。"),
        ("silo_ready_and_launch", "SILO_READY→DEPLOYED", "发射床锁定、真实任务许可、井内隔层与地表盖互锁后弹射；保31×31净芯和原机/栓关系。", "pa_ready/pa_3/pa_2/pa_1/pa_launch按真实时间推进；观测者能从安全层看到完整出库。"),
        ("recovery_and_return", "DESCENDING→TO_HANGAR", "原UUID损毁/停机状态通过真实空运或自主返程到回收床；井盖、支撑、倾转和地面接应顺序正确。", "pa_recover/pa_return跟实际回收阶段，单次落地声和现场警示保存重登一致。"),
        ("refill_and_restrain", "FILLING→PARKED", "原载台回床、肩垫接触、桥/栓回泊、LCL重注、维修反馈形成完整返回体验。", "pa_fill/pa_standby、液面和机械落锁同步；停机后的世界保战斗后果。")]
    hangars = [{"variant": bay["variant"], "original_eva_uuid": bay["eva_uuid"], "actual_bed": bay["bed"],
                "frame": bay, "eight_continuous_states": [{"id": ident, "actual_phase": phase, "construction_and_motion": motion, "lighting_and_sound": light} for ident, phase, motion, light in stages],
                "status": "Complete all3 machinery/crew/lighting/sound/transfer/recovery workpiece; no fresh native or visual pass inferred"} for bay in frame["bays"]]
    (out / "hangar_cards.json").write_text(json.dumps(hangars, ensure_ascii=False, indent=2), encoding="utf8")
    report = {"sources": [source(p) for p in (catalogue_path, transit_path, walks_path, lifts_path, frame_path)],
        "whole_station_areas": 20, "whole_station_journeys": 501, "native_train_air_interfaces": 38,
        "station_architecture_profiles": dict(Counter(c["architecture"] for c in station_cards)),
        "original_bays": len(hangars), "mechanical_experience_states_per_bay": len(stages), "actual_lift_groups": len(lifts),
        "actual_lift_landings": sum(len(lift["landings"]) for lift in lifts), "all_lift_interfaces": lifts,
        "execution": ["root稳定停止世界后审查并施工178格六面墙缝与1041格完整人员组件候选，复核同一3rig/6接触mesh、真实LCL/门/灯/声与三套完整往返。",
            "root下一次原生导出publicgate32states；逐站完整阈口、原通路/转角/楼梯/站台门负体积和双向占用验证后施工原生公共闸机。",
            "全部25真实乘梯病例fresh及cold；同版v3手交接接口重新导出全宽楼面图，安装图与最近电梯表回读一致SHA。",
            "38真实交通接口与501独立站内三维路径都执行；机场/技术中心北平台的过桥及现场控制不能压缩为门口到达。",
            "完整每层/入口/设备组件的旧设计退役与生成器封禁要落同一receipt，393分类清单不计为已通过。",
            "原生shader的全部站房、总部楼层、三机库全景与完整自然往返体验复核；最后安装副本冷重登与原UUID/NBT/交通身份回读。"],
        "status": "Grounded production cards and exact existing obligations only; no whole-facility completion, user approval or native pass"}
    (out / "contract.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print("Grounded facility workpieces:", len(station_cards), "whole stations;", len(hangars), "original bays ×", len(stages), "continuous states; no world mutation", flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, default=OUT)
    main(parser.parse_args().out)
