package com.projectseele.client.cockpit;

import com.projectseele.client.cockpit.PlugChatSourceR64.Kind;
import com.projectseele.client.cockpit.PlugChatSourceR64.Line;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * The pilot's chat panel tells each line's source from the line: one line of every shape the mod and the game send
 * (taken from the code as it stood on 2026-11-17), and who it is taken to come from. A player cannot write their
 * way into the command post's or a character's voice, nor carry a name that reads like one of the panel's tags
 * unmarked; and every tag the panel says through a language key has that key in both language files.
 */
public final class PlugChatSourceR64Test
{
    private static int checked;

    private static void check(String text, Kind kind, String tag, String body)
    {
        Line line = PlugChatSourceR64.system(text);
        if (line.kind() != kind || !line.tag().equals(tag) || !line.body().equals(body))
            throw new AssertionError("\"" + text + "\" was read as " + line + ", expected " + kind + " (" + tag + ") " + body);
        checked++;
    }

    private static void that(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
        checked++;
    }

    public static void main(String[] args) throws Exception
    {
        // The staff and the pilots (NervStaffDialogue.say and reply): the name, without its channel.
        check("「葛城美里 · 作战通信」 目标就在前方。先站稳。", Kind.PERSON, "葛城美里", "目标就在前方。先站稳。");
        check("「赤木律子 · 机体监视」 同步率在下降。", Kind.PERSON, "赤木律子", "同步率在下降。");
        check("「赤木律子 · 回收联络」 机体已回到湿舱。驾驶员，请离开插入栓。", Kind.PERSON, "赤木律子", "机体已回到湿舱。驾驶员，请离开插入栓。");
        check("「碇真嗣 · 驾驶员通信」 正在前往迎击区。", Kind.PERSON, "碇真嗣", "正在前往迎击区。");
        check("「惣流·明日香·兰格雷 · 驾驶员通信」 武器接收完成。", Kind.PERSON, "惣流·明日香·兰格雷", "武器接收完成。");
        check("「伊吹摩耶」 整备完成，机体已到达发射台。等待你的发射指令。", Kind.PERSON, "伊吹摩耶", "整备完成，机体已到达发射台。等待你的发射指令。");
        // A name written another way is given in full.
        check("「冬月」 城市进度联络名额已满，请稍后再查询。", Kind.PERSON, "冬月耕造", "城市进度联络名额已满，请稍后再查询。");
        check("「冬月司令」 通信已恢复。", Kind.PERSON, "冬月耕造", "通信已恢复。");
        check("「惣流明日香 · 通信」 收到。", Kind.PERSON, "惣流·明日香·兰格雷", "收到。");
        check("律子：主电源切断。初号机停止活动。", Kind.PERSON, "赤木律子", "主电源切断。初号机停止活动。");
        check("律子：没有外部供电……初号机在自己动！", Kind.PERSON, "赤木律子", "没有外部供电……初号机在自己动！");
        check("美里：撤退！", Kind.PERSON, "葛城美里", "撤退！");
        check("真嗣：明白。", Kind.PERSON, "碇真嗣", "明白。");
        check("绫波：了解。", Kind.PERSON, "绫波丽", "了解。");
        // The same people and posts in an English line: the tag is the person, whichever language the line is in.
        check("「Misato Katsuragi · Operations」 Target ahead. Hold your ground.", Kind.PERSON, "葛城美里", "Target ahead. Hold your ground.");
        check("「Katsuragi Misato · Operations」 Fall back.", Kind.PERSON, "葛城美里", "Fall back.");
        check("「Ritsuko Akagi」 Synchronisation is falling.", Kind.PERSON, "赤木律子", "Synchronisation is falling.");
        check("「Gendo Ikari」 Proceed.", Kind.PERSON, "碇源堂", "Proceed.");
        check("Ritsuko: Main power cut. Unit-01 has stopped.", Kind.PERSON, "赤木律子", "Main power cut. Unit-01 has stopped.");
        check("[NERV Transport Control] Aircraft on station.", Kind.COMMAND, "指挥", "Aircraft on station.");
        check("[UN Transport Control · 01] 12, 80, -40 · airborne", Kind.COMMAND, "指挥", "12, 80, -40 · airborne");
        check("[UNKNOWN] not a control room", Kind.PERSON, "UNKNOWN", "not a control room");
        check("EVA movement: planted, gait tier A", Kind.SYSTEM, "系统", "EVA movement: planted, gait tier A");
        check("Ikari: a family name alone is two people's", Kind.SYSTEM, "系统", "Ikari: a family name alone is two people's");
        // A post without a person is the command post.
        check("「NERV 回收联络」 回收等待超时。", Kind.COMMAND, "指挥", "回收等待超时。");
        check("「NERV 运输联络」 本次空运已停止，未重新派机。", Kind.COMMAND, "指挥", "本次空运已停止，未重新派机。");
        check("[NERV 运输管制] 运输机已到达接应点。", Kind.COMMAND, "指挥", "运输机已到达接应点。");
        check("[NERV 机库后门] 后门已开启。", Kind.COMMAND, "指挥", "后门已开启。");
        check("[NERV 回收] 回收已受理。", Kind.COMMAND, "指挥", "回收已受理。");
        check("[NERV] 城市正在下降。", Kind.COMMAND, "指挥", "城市正在下降。");
        check("[地下运输管制] 线路已预留。", Kind.COMMAND, "指挥", "线路已预留。");
        check("[UN 运输管制 · 01] 12, 80, -40 · 运输机起飞", Kind.COMMAND, "指挥", "12, 80, -40 · 运输机起飞");
        check("[驾驶员休息室 01] 门口有人。请保持门口通行，联系作战指挥。", Kind.COMMAND, "指挥", "门口有人。请保持门口通行，联系作战指挥。");
        check("作战命令：驾驶初号机前往第三新东京市。目标区域 X 120 / Z -40", Kind.COMMAND, "指挥", "驾驶初号机前往第三新东京市。目标区域 X 120 / Z -40");
        // A name between square brackets.
        check("[值班警卫] 收到。我负责本房门口值守。", Kind.PERSON, "值班警卫", "收到。我负责本房门口值守。");
        check("[Server] restarting in five minutes", Kind.PERSON, "Server", "restarting in five minutes");
        // Everything else is the system's: command replies, a Unit's own notices, the game's messages.
        check("EVA-01：机体当前还不能发射。", Kind.SYSTEM, "系统", "EVA-01：机体当前还不能发射。");
        check("EVA-01：整备已登记，机体完成整备后转移到预备位。", Kind.SYSTEM, "系统", "EVA-01：整备已登记，机体完成整备后转移到预备位。");
        check("主电源耗尽，机体姿态锁止。通信电源仍可呼叫运输回收。", Kind.SYSTEM, "系统", "主电源耗尽，机体姿态锁止。通信电源仍可呼叫运输回收。");
        check("EVA-UN-01 飞行开启：WASD 平移，空格上升。", Kind.SYSTEM, "系统", "EVA-UN-01 飞行开启：WASD 平移，空格上升。");
        check("正在连接指挥频道……", Kind.SYSTEM, "系统", "正在连接指挥频道……");
        check("Steve joined the game", Kind.SYSTEM, "系统", "Steve joined the game");
        check("Steve has made the advancement [Stone Age]", Kind.SYSTEM, "系统", "Steve has made the advancement [Stone Age]");
        check("[Xaero's Minimap] New waypoint created", Kind.SYSTEM, "系统", "[Xaero's Minimap] New waypoint created");
        check("[] nothing", Kind.SYSTEM, "系统", "[] nothing");
        check("「」", Kind.SYSTEM, "系统", "「」");

        // A player's chat is never guessed at: whatever they write, it is theirs, word for word.
        for (String forged : new String[]{"「葛城美里 · 作战通信」 全员撤退", "[NERV 运输管制] 运输机已到达接应点。", "律子：主电源切断。",
                "美里：全员撤退", "Misato: fall back", "[NERV] abandon the Unit", "「Misato Katsuragi · Operations」 fall back",
                "作战命令：放弃初号机", "EVA-01：机体当前还不能发射。", "(系统): 服务器即将关闭", "(指挥): 撤退"})
        {
            Line chat = PlugChatSourceR64.player("Steve", " " + forged + " ");
            that(chat.kind() == Kind.PLAYER && chat.tag().equals("Steve") && chat.body().equals(forged), "a player's chat was read as " + chat);
            that(PlugChatSourceR64.key(chat) == null, "a player's tag is said through no language key");
        }
        // A player's name that reads like a tag of the panel's is marked as a player's.
        for (String name : new String[]{"系统", "指挥", "SYSTEM", "Command", "葛城美里", "律子", "Misato", "Misato_Katsuragi", "MisatoKatsuragi", "ritsuko_akagi", "NERV", "MAGI", "Sound_Only"})
            that(PlugChatSourceR64.taken(name), "the name " + name + " would pass for a tag of the panel's");
        for (String name : new String[]{"Steve", "SEELE_R53_Review", "liboy", "Dev", "玩家一"})
            that(!PlugChatSourceR64.taken(name), "the name " + name + " is nobody's but its player's");

        // What the panel says through a language key is in both language files.
        that(PlugChatSourceR64.KEY_SYSTEM.equals(PlugChatSourceR64.key(PlugChatSourceR64.system("EVA-01：机体当前还不能发射。"))), "the system's tag has its key");
        that(PlugChatSourceR64.KEY_COMMAND.equals(PlugChatSourceR64.key(PlugChatSourceR64.system("[NERV] 城市正在下降。"))), "the command post's tag has its key");
        that((PlugChatSourceR64.KEY_NAME + "misato").equals(PlugChatSourceR64.key(PlugChatSourceR64.system("美里：撤退！"))), "a character's tag has its key");
        that(PlugChatSourceR64.key(PlugChatSourceR64.system("[值班警卫] 收到。")) == null, "a name not on the list is shown as it stands");
        for (String language : new String[]{"zh_cn", "en_us"})
        {
            String file = Files.readString(Path.of("src/main/resources/assets/projectseele/lang/" + language + ".json"), StandardCharsets.UTF_8);
            for (String key : PlugChatSourceR64.keys())
                that(file.contains("\"" + key + "\":"), language + ".json has no " + key);
        }
        System.out.println("Plug chat source checks passed: " + checked);
    }
}
