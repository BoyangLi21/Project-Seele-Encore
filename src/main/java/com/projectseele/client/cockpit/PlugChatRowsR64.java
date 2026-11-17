package com.projectseele.client.cockpit;

import java.util.ArrayList;
import java.util.List;
import java.util.function.IntUnaryOperator;

/**
 * R64: how one line of the pilot's chat panel is laid on its rows. What is said begins on the tag's own row and
 * runs on under it, a few rows at most; what does not fit is cut (the chat's history has all of it).
 * <p>
 * Broken here and not by the game's splitter: that one knows spaces only, and sends a whole sentence without
 * spaces to the next row and a comma to a row's head. Here a row ends where it is full; not inside a word where
 * the script has words (the row gives the word up whole), and never so that the next row begins with a mark that
 * closes what stood before it. Pure text and widths: PlugChatRowsR64Test lays lines out without the game.
 */
public final class PlugChatRowsR64
{
    /** Marks that close what stands before them: a row does not begin with one. */
    private static final String CLOSING = "，。、；：！？）」』”’》】…,.;:!?)";

    private PlugChatRowsR64() {}

    /**
     * @param lead    the width the tag takes at the head of the first row
     * @param width   a row's width
     * @param most    the rows there are
     * @param advance a character's width
     * @return the rows' text, the first of them beside the tag (empty where the tag leaves no room)
     */
    public static List<String> split(String body, int lead, int width, int most, IntUnaryOperator advance)
    {
        String rest = body.replace('\n', ' ').strip();
        List<String> rows = new ArrayList<>();
        for (int row = 0; row < most; row++)
        {
            int room = row == 0 ? Math.max(0, width - lead) : width;
            int cut = fit(rest, room, advance);
            String part;
            if (cut == rest.length())
            {
                part = rest;
                rest = "";
            }
            else if (row == most - 1)
            {
                // The last row there is: what is left over is cut.
                part = rest.substring(0, fit(rest, Math.max(0, room - advance.applyAsInt('…')), advance)).stripTrailing() + "…";
                rest = "";
            }
            else
            {
                if (cut > 0 && word(rest.charAt(cut - 1)) && word(rest.charAt(cut)))
                {
                    // Inside a word: the row ends where the word begins. A word as long as the row is broken
                    // where the row is full (beside the tag it goes to the next row whole).
                    int start = cut;
                    while (start > 0 && word(rest.charAt(start - 1))) start--;
                    if (start > 0 || row == 0) cut = start;
                }
                else if (cut > 1 && CLOSING.indexOf(rest.charAt(cut)) >= 0) cut--;
                // A row under the tag's always takes something, or the line would never end.
                if (cut == 0 && row > 0) cut = 1;
                part = rest.substring(0, cut);
                rest = rest.substring(cut).stripLeading();
            }
            rows.add(part.strip());
            if (rest.isEmpty()) break;
        }
        return rows;
    }

    /** How many characters from the head of the text fit the room. */
    private static int fit(String text, int room, IntUnaryOperator advance)
    {
        int taken = 0, count = 0;
        while (count < text.length())
        {
            taken += advance.applyAsInt(text.charAt(count));
            if (taken > room) break;
            count++;
        }
        return count;
    }

    /** A letter or a digit of a script written in words (not a Chinese character, a kana, a full-width sign). */
    private static boolean word(char sign)
    {
        return sign < 0x2E80 && Character.isLetterOrDigit(sign);
    }
}
