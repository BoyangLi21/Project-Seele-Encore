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
                    "在第三新东京市地表迎击夏姆榭尔。光鞭能切开大楼，也会缠住机体甩出去，脐带会被扯断，之后只剩内部电源。步枪打不穿A.T.力场；贴近后用刀削弱力场，把它打到残血，再持刀抵住核心，直到核心熄灭。"),
            new Chapter("rain", "04", "雨中的间奏", "", 0, false, "城际列车与山间步行叙事尚在制作。"),
            new Chapter("ramiel", "05–06", "屋岛作战", "拉米尔", 5, true, "前往箱根阵地。初号机负责阳电子炮，零号机持盾掩护。接通阵地三路电网，初号机停在炮位、看向炮身并右键接入。充能后瞄准核心，在拉米尔发射光束时开火；打中外壳无效。"),
            new Chapter("jet_alone", "07", "反应堆事故", "J.A.", 0, false, "非使徒章节；待制作事故处置流程。"),
            new Chapter("gaghiel", "08", "海上迎击", "迦基尔", 6, true, "迦基尔在深水湖区袭击船队。派二号机出击：运输机把它送到港区，二号机下水走到拦截点。迦基尔咬上来时会把机体衔进嘴里拖走，蹲下、空手、双手撑住上下颚，把嘴撑开；脐带缆要接着，A.T.力场要开着。舰桥接通电源后，两门舰炮在六秒内先后打进张开的嘴里，命中核心才算数。"),
            new Chapter("israfel", "09", "同步作战", "伊斯拉斐尔", 7, true, "伊斯拉斐尔从地面向第三新东京市进攻。派两台机体出击（初号机和二号机最合适）：用刀削掉它的A.T.力场，它被砍到一半时会分成两个，各带一个核心。只打倒一个没有用，另一个会把它修好；两台机体要各对付一个，在大约一秒之内同时把两个都打倒。"),
            new Chapter("sandalphon", "10", "火山行动", "圣德芬", 8, false, "待制作耐热装备与火山救援。"),
            new Chapter("matarael", "11", "停电迎击", "雨天使", 9, true, "总部和全城停电，脐带缆接不上，机体只能靠内部电源作战，时间有限。雨天使走到总部上方，从身体下面的眼睛滴下强酸，会溶穿地表装甲板，也会腐蚀机体。它的A.T.力场很弱，但只有从它身体正下方打上去才有效：避开酸液，钻到它下面，用步枪或近战打核心。"),
            new Chapter("sahaquiel", "12", "空中拦截", "空天使", 10, true, "撒哈奎尔在城市上空，要整个砸向总部。派三台机体出击：第一台机体到达地表后它开始坠落，先投下两块试投碎片，地上的红圈会慢慢收窄到预测落点。所有机体赶到圈中心，在它落地前接住；一台撑不了多久，两台慢慢往下沉，三台才撑得住。接住后它的下面露出核心，从下方攻击。"),
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
    {return "";}
    private TvCampaignCatalog() {}
}
