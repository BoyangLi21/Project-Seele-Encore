package com.projectseele.client.cockpit;

import java.util.List;
import java.util.function.IntUnaryOperator;

/**
 * The pilot's chat panel lays a line on its rows: what is said begins beside the tag, no row is wider than the
 * panel, no word of a script with words is cut where it can be given up whole, no row begins with a closing mark,
 * nothing is lost unless the rows run out, and then the last row says so.
 */
public final class PlugChatRowsR64Test
{
    /** The game's font, near enough: nine to a Chinese character or a full-width sign, six to the rest. */
    private static final IntUnaryOperator ADVANCE = sign -> sign < 0x2E80 ? 6 : 9;
    private static int checked;

    private static void that(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
        checked++;
    }

    private static int width(String text)
    {
        int width = 0;
        for (int i = 0; i < text.length(); i++) width += ADVANCE.applyAsInt(text.charAt(i));
        return width;
    }

    private static List<String> laid(String body, int lead, int width, int most)
    {
        List<String> rows = PlugChatRowsR64.split(body, lead, width, most, ADVANCE);
        that(!rows.isEmpty() && rows.size() <= most, body + ": " + rows.size() + " rows of " + most);
        for (int i = 0; i < rows.size(); i++)
        {
            that(width(rows.get(i)) <= (i == 0 ? Math.max(0, width - lead) : width), body + ": row " + i + " is wider than its room: " + rows.get(i));
            that(i == 0 || rows.get(i).isEmpty() || "，。、；：！？）」』”’》】,.;:!?)".indexOf(rows.get(i).charAt(0)) < 0, body + ": row " + i + " begins with a closing mark: " + rows.get(i));
        }
        return rows;
    }

    public static void main(String[] args)
    {
        // What is said begins beside the tag; the English word after the Chinese goes to the next row whole.
        // (2026-11-17: this line left its first row to the tag alone, for the L of LCL that still fitted it.)
        List<String> rows = laid("同步率稳定。LCL 电荷正常。", 77, 137, 2);
        that(rows.equals(List.of("同步率稳定。", "LCL 电荷正常。")), "Chinese, then an English word: " + rows);
        rows = laid("同步率稳定。LCL 电荷正常。", 49, 137, 3);
        that(rows.get(0).startsWith("同步率稳定。LCL"), "the word stays on the tag's row where it fits: " + rows);

        // No comma at a row's head.
        rows = laid("EVA-01：等待状态确认，机体未加载", 49, 137, 3);
        that(String.join("", rows).equals("EVA-01：等待状态确认，机体未加载"), "nothing lost: " + rows);
        rows = laid("目标已确认消失。先别急着动，检查供电和机体状态，我们准备接你回来。", 58, 137, 3);
        that(String.join("", rows).equals("目标已确认消失。先别急着动，检查供电和机体状态，我们准备接你回来。"), "nothing lost: " + rows);

        // A script with words breaks at its spaces.
        rows = laid("the quick brown fox jumps over the lazy dog and runs on", 40, 137, 3);
        for (String row : rows) for (String word : row.split(" "))
            that(" the quick brown fox jumps over the lazy dog and runs on ".contains(" " + word + " "), "a word was cut: " + word + " in " + rows);
        that(String.join(" ", rows).equals("the quick brown fox jumps over the lazy dog and runs on"), "nothing lost: " + rows);

        // The rows run out: the last one says so.
        rows = laid("目标已确认消失。先别急着动，检查供电和机体状态，我们准备接你回来。", 58, 137, 2);
        that(rows.size() == 2 && rows.get(1).endsWith("…"), "cut at the last row: " + rows);
        rows = laid("了解", 58, 137, 3);
        that(rows.equals(List.of("了解")), "a short line is one row: " + rows);

        // A tag as wide as the panel: the line begins under it. A word as long as a row is broken where the row is full.
        rows = laid("收到，准备出击", 140, 137, 3);
        that(rows.get(0).isEmpty() && rows.get(1).equals("收到，准备出击"), "under a wide tag: " + rows);
        rows = laid("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 40, 137, 3);
        that(rows.size() == 3 && !rows.get(1).isEmpty() && !rows.get(2).isEmpty(), "one long word: " + rows);
        rows = laid("line one\nline two", 40, 137, 3);
        that(String.join(" ", rows).equals("line one line two"), "a line break is a space: " + rows);
        System.out.println("Plug chat row checks passed: " + checked);
    }
}
