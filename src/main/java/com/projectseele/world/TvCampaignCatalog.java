package com.projectseele.world;

import java.util.List;

/** TV 1995 ordering. A dossier entry is never advertised as a playable mission. */
public final class TvCampaignCatalog
{
    public record Chapter(String id, String episode, String title, String target, int angel, boolean playable, String briefing) {}
    public static final List<Chapter> CHAPTERS = List.of(
            new Chapter("sachiel", "01–02", "首次出击", "萨基尔", 3, true,
                    "驾驶初号机，经机库整备与发射流程前往东北迎击大道。近战削弱目标后，满足站姿、距离和场地条件时进入自主行动演出。"),
            new Chapter("shamshel", "03", "第二次迎击", "夏姆榭尔", 4, true,
                    "初号机前往东北迎击大道。观察光鞭蓄势，横向闪避后以渐进刀近身。保留供电与撤回余量；本次不会用自动演出代替作战。"),
            new Chapter("rain", "04", "雨中的间奏", "", 0, false, "城际列车与山间步行叙事尚在制作。"),
            new Chapter("ramiel", "05–06", "屋岛作战", "雷米尔", 5, true, "接受指令时拉米尔已在城市上方钻进。初号机与零号机按原整备、发射流程出动，真实领用阳电子炮与防护盾。阵地三路供电开关全部接通后充能，零号机用实际盾面挡住回击射线；每炮后操作冷却和装填按钮，再等待炮体冷却完成。内置电池不能代替炮位电网。"),
            new Chapter("jet_alone", "07", "反应堆事故", "J.A.", 0, false, "非使徒章节；待制作事故处置流程。"),
            new Chapter("gaghiel", "08", "海上迎击", "迦基尔", 6, true, "TV08港区迁址演习。接受指令后迦基尔已在近海游弋，二号机按原整备流程出動并经原机空运到接应冠，再实际进入水中打击域。舰桥接通真实外部电源，双炮各需4秒校准与10秒装填。驾驶二号机在张口阶段以两只实际手掌接触口部、空手蹲伏且保持电缆，稳定1秒后由舰桥在6秒内完成两座原舰炮射击。可以近战削弱目标；10分钟时限只判未及时击破，离线暂停倒计时，失败后按正常流程回收再重试。本章尚无原舰航行或沉舰，不把远处原舰与货物写成受到实际攻击。"),
            new Chapter("israfel", "09", "同步作战", "伊斯拉斐尔", 7, false, "待制作双机协调与双核心同步判定。"),
            new Chapter("sandalphon", "10", "火山行动", "圣德芬", 8, false, "待制作耐热装备与火山救援。"),
            new Chapter("matarael", "11", "停电迎击", "雨天使", 9, false, "待制作总部停电与人工出动。"),
            new Chapter("sahaquiel", "12", "空中拦截", "空天使", 10, false, "待制作三机协同接敌。"),
            new Chapter("ireul", "13", "系统侵入", "恐怖天使", 11, false, "待制作设施隔离与 MAGI 应对。"),
            new Chapter("compatibility", "14–15", "交叉测试与调查", "", 0, false, "待制作同步测试与总部调查间奏。"),
            new Chapter("leliel", "16", "虚数空间", "夜天使", 12, false, "待制作空间规则与救援。"),
            new Chapter("fourth_child", "17", "第四适格者", "", 0, false, "待制作转运与起动试验准备。"),
            new Chapter("bardiel", "18", "起动试验", "霰天使", 13, false, "待制作寄生机体与指挥冲突。"),
            new Chapter("zeruel", "19", "总部防卫", "力天使", 14, false, "待制作总部入侵战。"),
            new Chapter("recovery", "20–21", "回收与往事", "", 0, false, "待制作回收过程与回忆间奏。"),
            new Chapter("arael", "22", "轨道威胁", "鸟天使", 15, false, "待制作轨道目标与精神接触。"),
            new Chapter("armisael", "23", "侵蚀", "子宫天使", 16, false, "待制作融合侵蚀与撤离。"),
            new Chapter("tabris", "24", "最后的来访者", "渚薰", 17, false, "待制作终极教条流程。"),
            new Chapter("instrumentality", "25–26", "TV 结局", "", 0, false, "保留 TV 内心叙事；不以剧场版战役替换。"));

    public static Chapter at(int index) { return CHAPTERS.get(Math.max(0, Math.min(index, CHAPTERS.size() - 1))); }
    public static java.util.Optional<Chapter> find(String id){return CHAPTERS.stream().filter(c->c.id().equals(id)).findFirst();}
    private TvCampaignCatalog() {}
}
