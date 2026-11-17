package com.projectseele.client.cockpit;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * R64: who is speaking in a line of chat, read off the line itself, for the pilot's chat panel.
 * <p>
 * Nothing on the server marks its messages by source, and there are some three hundred places that send one. They
 * are written in a handful of shapes, though, and the shape tells the source: 「name · channel」 text for the staff
 * and the pilots, [post] text for the control rooms, a few name：text lines, and everything else is the system's
 * (command replies, a Unit's own notices, the game's messages). A player's chat arrives as such and is never
 * guessed at, whatever the player wrote: nobody types their way into the command post's voice.
 * Pure text in, pure text out: PlugChatSourceR64Test holds a line of each shape.
 */
public final class PlugChatSourceR64
{
    public enum Kind { PLAYER, PERSON, COMMAND, SYSTEM }

    /** A line for the panel: who says it (the tag) and what is said. */
    public record Line(Kind kind, String tag, String body) {}

    public static final String SYSTEM = "系统", COMMAND = "指挥";
    public static final String KEY_SYSTEM = "hud.projectseele.chat.system", KEY_COMMAND = "hud.projectseele.chat.command",
            KEY_PLAYER = "hud.projectseele.chat.player", KEY_HEADER = "hud.projectseele.chat.header", KEY_NAME = "hud.projectseele.chat.name.";

    /**
     * Who speaks in the mod's lines: an id (the language key's end), the full name the tag shows, the name as an
     * English reader has it (for the names a player may not pass for), and the other ways the lines write it.
     */
    private record Person(String id, String name, String english, String... also) {}

    private static final Person[] PEOPLE = {
            new Person("misato", "葛城美里", "Misato Katsuragi", "美里", "葛城"),
            new Person("ritsuko", "赤木律子", "Ritsuko Akagi", "律子", "赤木"),
            new Person("maya", "伊吹摩耶", "Maya Ibuki", "摩耶", "伊吹"),
            new Person("fuyutsuki", "冬月耕造", "Kozo Fuyutsuki", "冬月", "冬月司令", "冬月副司令"),
            new Person("gendo", "碇源堂", "Gendo Ikari", "源堂", "碇司令"),
            new Person("hyuga", "日向诚", "Makoto Hyuga", "日向"),
            new Person("aoba", "青叶茂", "Shigeru Aoba", "青叶"),
            new Person("kaji", "加持良治", "Ryoji Kaji", "加持"),
            new Person("shinji", "碇真嗣", "Shinji Ikari", "真嗣"),
            new Person("rei", "绫波丽", "Rei Ayanami", "绫波", "丽"),
            new Person("asuka", "惣流·明日香·兰格雷", "Asuka Langley Soryu", "明日香", "惣流明日香", "惣流"),
            new Person("kaworu", "渚薰", "Kaworu Nagisa", "薰"),
    };
    /** Every way a line writes a name, to the full name; the full name to its id; what a player may not be taken for. */
    private static final Map<String, String> FULL = new HashMap<>(), ID = new HashMap<>();
    private static final Set<String> TAKEN = new HashSet<>();
    /** What marks a post or a control room, not a person, in a speaker's place. */
    private static final String[] POSTS = {"NERV", "UN", "管制", "联络", "机库", "休息室"};

    static
    {
        for (String label : new String[]{SYSTEM, COMMAND, "system", "command", "comm", "sound only", "nerv", "magi"}) TAKEN.add(label);
        for (Person person : PEOPLE)
        {
            FULL.put(person.name, person.name);
            ID.put(person.name, person.id);
            TAKEN.add(person.name);
            for (String other : person.also) { FULL.put(other, person.name); TAKEN.add(other); }
            // An English reader's tag is the English name; its parts alone would pass for it as well.
            String english = person.english.toLowerCase(Locale.ROOT);
            TAKEN.add(english);
            TAKEN.add(english.replace(" ", ""));
            for (String part : english.split(" ")) TAKEN.add(part);
        }
    }

    private PlugChatSourceR64() {}

    /** A player's chat: the game says who sent it, and nothing in what they wrote changes that. */
    public static Line player(String name, String text)
    {
        return new Line(Kind.PLAYER, name.strip(), text.strip());
    }

    /**
     * A player whose name reads like one of the panel's own tags (the system, the command post, somebody of the
     * staff, in either language): the panel says "player" before such a name.
     */
    public static boolean taken(String name)
    {
        String plain = name.strip().toLowerCase(Locale.ROOT).replace('_', ' ').replace('-', ' ').replaceAll("\\s+", " ");
        return TAKEN.contains(plain) || TAKEN.contains(plain.replace(" ", ""));
    }

    /** The language key the panel says a tag with, or null where the tag is shown as it stands (a player, a name not on the list). */
    public static String key(Line line)
    {
        return switch (line.kind())
        {
            case SYSTEM -> KEY_SYSTEM;
            case COMMAND -> KEY_COMMAND;
            case PERSON -> ID.containsKey(line.tag()) ? KEY_NAME + ID.get(line.tag()) : null;
            case PLAYER -> null;
        };
    }

    /** Every language key the panel may ask for: the check holds both language files to it. */
    public static List<String> keys()
    {
        List<String> keys = new ArrayList<>(List.of(KEY_SYSTEM, KEY_COMMAND, KEY_PLAYER, KEY_HEADER));
        for (Person person : PEOPLE) keys.add(KEY_NAME + person.id);
        return keys;
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
            if (FULL.containsKey(head)) return new Line(Kind.PERSON, FULL.get(head), rest);
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
        return new Line(Kind.PERSON, FULL.getOrDefault(name, name), body);
    }
}
