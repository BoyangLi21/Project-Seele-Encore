package com.projectseele.client.cockpit;

import java.util.Map;

/**
 * R64: who is speaking in a line of chat, read off the line itself, for the pilot's chat panel.
 * <p>
 * Nothing on the server marks its messages by source, and there are some three hundred places that send one. They
 * are written in a handful of shapes, though, and the shape tells the source: 「name · channel」 text for the staff
 * and the pilots, [post] text for the control rooms, a few name：text lines, and everything else is the system's
 * (command replies, a Unit's own notices, the game's messages). A player's chat arrives as such and is never
 * guessed at. Pure text in, pure text out: PlugChatSourceR64Test holds a line of each shape.
 */
public final class PlugChatSourceR64
{
    public enum Kind { PLAYER, PERSON, COMMAND, SYSTEM }

    /** A line for the panel: who says it (the tag) and what is said. */
    public record Line(Kind kind, String tag, String body) {}

    public static final String SYSTEM = "系统", COMMAND = "指挥";
    /** The short names a few lines are written with, and whose they are. */
    private static final Map<String, String> SHORT = Map.of("律子", "赤木律子", "美里", "葛城美里", "摩耶", "伊吹摩耶", "冬月", "冬月");
    /** What marks a post or a control room, not a person, in a speaker's place. */
    private static final String[] POSTS = {"NERV", "UN", "管制", "联络", "机库", "休息室"};

    private PlugChatSourceR64() {}

    /** A player's chat: the game says who sent it. */
    public static Line player(String name, String text)
    {
        return new Line(Kind.PLAYER, name.strip(), text.strip());
    }

    /** Any other line that reaches the chat. */
    public static Line system(String text)
    {
        String line = text.strip();
        // 「name · channel」 text: every line of the staff's and the pilots' dialogue.
        Line spoken = bracketed(line, '「', '」', true);
        if (spoken != null) return spoken;
        // [post] text for the control rooms, [name] text for a guard or a technician answering.
        spoken = bracketed(line, '[', ']', false);
        if (spoken != null) return spoken;
        int colon = line.indexOf('：');
        if (colon > 0 && colon + 1 < line.length())
        {
            String head = line.substring(0, colon), rest = line.substring(colon + 1).strip();
            if (SHORT.containsKey(head)) return new Line(Kind.PERSON, SHORT.get(head), rest);
            if (head.equals("作战命令")) return new Line(Kind.COMMAND, COMMAND, rest);
        }
        return new Line(Kind.SYSTEM, SYSTEM, line);
    }

    private static Line bracketed(String line, char open, char close, boolean always)
    {
        if (line.isEmpty() || line.charAt(0) != open) return null;
        int end = line.indexOf(close);
        if (end < 2 || end + 1 >= line.length()) return null;
        String speaker = line.substring(1, end), body = line.substring(end + 1).strip();
        // The channel after the name (作战通信, 机体监视, 驾驶员通信 ...) is not part of who speaks.
        int dot = speaker.indexOf(" · ");
        String name = (dot > 0 ? speaker.substring(0, dot) : speaker).strip();
        if (body.isEmpty() || name.isEmpty()) return null;
        for (String post : POSTS) if (name.contains(post)) return new Line(Kind.COMMAND, COMMAND, body);
        // Square brackets are everybody's: only a short single word between them is taken for a name.
        if (!always && (name.length() > 16 || name.indexOf(' ') >= 0)) return null;
        return new Line(Kind.PERSON, SHORT.getOrDefault(name, name), body);
    }
}
