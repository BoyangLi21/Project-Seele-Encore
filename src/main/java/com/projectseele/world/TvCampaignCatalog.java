package com.projectseele.world;

import java.util.List;

/** TV 1995 ordering. A dossier entry is never advertised as a playable mission. */
public final class TvCampaignCatalog
{
    public record Chapter(String id, String episode, String title, String target, int angel, boolean playable, String briefing) {}
    public static final List<Chapter> CHAPTERS = List.of(
            new Chapter("sachiel", "01–02", "首次出击", "萨基尔", 3, true,
                    "前往东北迎击大道迎击萨基尔。观察目标动作，避开正面攻击，用近战削弱A.T.力场后攻击核心。注意机体损伤与供电。"),
            new Chapter("shamshel", "03", "第二次迎击", "夏姆榭尔", 4, true,
                    "前往东北迎击大道迎击夏姆榭尔。看到光鞭蓄势时横向闪避，趁攻击间隙用渐进刀近身。留意电量，必要时撤回补给。"),
            new Chapter("rain", "04", "雨中的间奏", "", 0, false, "城际列车与山间步行叙事尚在制作。"),
            new Chapter("ramiel", "05–06", "屋岛作战", "拉米尔", 5, true, "前往箱根阵地。初号机负责阳电子炮，零号机持盾掩护。接通阵地三路电网，初号机停在炮位、看向炮身并右键接入。充能后瞄准核心，在拉米尔发射光束时开火；打中外壳无效。"),
            new Chapter("jet_alone", "07", "反应堆事故", "J.A.", 0, false, "非使徒章节；待制作事故处置流程。"),
            new Chapter("gaghiel", "08", "海上迎击", "迦基尔", 6, false, "海上迎击尚未开放。"),
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
    public static String preparationBlockerR52(String id)
    {return switch(id){case "gaghiel"->"海上迎击尚未开放，请选择其他任务。";default->"";};}
    private TvCampaignCatalog() {}
}
