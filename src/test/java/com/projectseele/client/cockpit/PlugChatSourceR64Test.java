package com.projectseele.client.cockpit;

import com.projectseele.client.cockpit.PlugChatSourceR64.Kind;
import com.projectseele.client.cockpit.PlugChatSourceR64.Line;

/**
 * The pilot's chat panel tells each line's source from the line: one line of every shape the mod and the game send
 * (taken from the code as it stood on 2026-11-17), and who it is taken to come from.
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

    public static void main(String[] args)
    {
        // The staff and the pilots (NervStaffDialogue.say and reply): the name, without its channel.
        check("「葛城美里 · 作战通信」 目标就在前方。先站稳。", Kind.PERSON, "葛城美里", "目标就在前方。先站稳。");
        check("「赤木律子 · 机体监视」 同步率在下降。", Kind.PERSON, "赤木律子", "同步率在下降。");
        check("「赤木律子 · 回收联络」 机体已回到湿舱。驾驶员，请离开插入栓。", Kind.PERSON, "赤木律子", "机体已回到湿舱。驾驶员，请离开插入栓。");
        check("「碇真嗣 · 驾驶员通信」 正在前往迎击区。", Kind.PERSON, "碇真嗣", "正在前往迎击区。");
        check("「伊吹摩耶」 整备完成，机体已到达发射台。等待你的发射指令。", Kind.PERSON, "伊吹摩耶", "整备完成，机体已到达发射台。等待你的发射指令。");
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
        // A name written short before a colon, and a name between square brackets.
        check("律子：主电源切断。初号机停止活动。", Kind.PERSON, "赤木律子", "主电源切断。初号机停止活动。");
        check("律子：没有外部供电……初号机在自己动！", Kind.PERSON, "赤木律子", "没有外部供电……初号机在自己动！");
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

        // A player's chat is never guessed at, whatever it looks like.
        Line chat = PlugChatSourceR64.player("Steve", " 「葛城美里」 骗你的 ");
        if (chat.kind() != Kind.PLAYER || !chat.tag().equals("Steve") || !chat.body().equals("「葛城美里」 骗你的"))
            throw new AssertionError("a player's chat was read as " + chat);
        System.out.println("Plug chat source checks passed: " + (checked + 1));
    }
}
