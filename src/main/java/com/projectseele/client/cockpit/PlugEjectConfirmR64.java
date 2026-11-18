package com.projectseele.client.cockpit;

import com.projectseele.client.Keybinds;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.resources.language.I18n;
import net.minecraft.util.Mth;

/**
 * R64: the entry plug is not thrown out by one touch of a key. The eject key first puts a warning on the plug's
 * wall; the same key again, while the warning stands, ejects; the cancel key takes the warning down, and it goes
 * by itself after {@link #WINDOW} ticks. Nothing of this is the server's: it still gets the one eject request it
 * always got, only later (an ejection out in the field costs the pilot half the maximum health, so a slip of the
 * finger was dear).
 */
public final class PlugEjectConfirmR64
{
    /** The warning stands this many client ticks. */
    public static final int WINDOW = 120;
    private static final int RED = 0xFFF16B51, WHITE = 0xFFE2E7DF, MUTED = 0xFFBCC8C4, AMBER = 0xFFE8A058;
    private static int left, unit = -1;

    private PlugEjectConfirmR64() {}

    /** The eject key in the Unit with this entity id: true when the ejection is to be asked of the server now. */
    public static boolean pressed(int entity)
    {
        if (left > 0 && unit == entity) { left = 0; return true; }
        left = WINDOW; unit = entity;
        return false;
    }

    /** The cancel key: true when there was a warning to take down. */
    public static boolean cancelled()
    {
        if (left <= 0) return false;
        left = 0;
        return true;
    }

    /** Once a client tick, with the id of the Unit the player pilots (-1: none): the warning runs out, and goes at once outside that Unit. */
    public static void tick(int entity)
    {
        if (left <= 0) return;
        if (entity != unit) left = 0;
        else left--;
    }

    /** The warning stands. */
    public static boolean asking()
    {
        return left > 0;
    }

    /**
     * The warning, as one of the plug's windows: a red-edged plate in the upper middle of the view, hazard bands
     * above and below, what the key will do in plain words, and the time it still stands. What the ejection costs
     * is written in the lines the language file breaks it into, so that the plate stays narrow: between the plug's
     * side panels where the view is wide enough, and over their inner edges where it is not.
     */
    public static void render(GuiGraphics g, int width, int height)
    {
        if (left <= 0) return;
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null || mc.options.hideGui || width < 160 || height < 100) return;
        Font font = mc.font;
        String title = I18n.get("hud.projectseele.eject.title");
        String[] cost = I18n.get("hud.projectseele.eject.cost").split("\n");
        String confirm = I18n.get("hud.projectseele.eject.confirm", Keybinds.EXIT_EVA.getTranslatedKeyMessage().getString());
        String cancel = I18n.get("hud.projectseele.eject.cancel", Keybinds.EJECT_CANCEL.getTranslatedKeyMessage().getString());
        int text = Math.max(font.width(title), Math.max(font.width(confirm), font.width(cancel)));
        for (String row : cost) text = Math.max(text, font.width(row));
        int w = Math.min(width - 16, Math.max(140, text + 20)), h = 60 + 10 * cost.length;
        int x = (width - w) / 2, y = Math.max(46, Math.round(height * .24F));
        // Nearly solid: where the plate lies over the plug's side panels their text must not read through its own.
        g.fill(x, y, x + w, y + h, 0xF00C1416);
        g.fill(x, y, x + 1, y + h, RED); g.fill(x + w - 1, y, x + w, y + h, RED);
        bands(g, x + 1, y, w - 2); bands(g, x + 1, y + h - 5, w - 2);
        // The heading blinks twice a second, as the plug's alarms do; it is red in both beats.
        boolean lit = (System.currentTimeMillis() / 250 & 1) == 0;
        g.drawString(font, title, x + (w - font.width(title)) / 2, y + 10, lit ? 0xFFFF8A70 : RED, false);
        int line = y + 23;
        for (String row : cost) { fitted(g, font, row, x, line, w, MUTED); line += 10; }
        fitted(g, font, confirm, x, line + 4, w, WHITE);
        fitted(g, font, cancel, x, line + 15, w, AMBER);
        // The time the warning still stands, running out from both ends.
        int run = Math.round((w - 20) * Mth.clamp(left / (float) WINDOW, 0, 1) / 2);
        g.fill(x + w / 2 - run, y + h - 9, x + w / 2 + run, y + h - 8, RED);
    }

    /** A band of slanted red and dark stripes, five pixels high. */
    private static void bands(GuiGraphics g, int x, int y, int width)
    {
        for (int row = 0; row < 5; row++)
            for (int column = 0; column < width; column++)
                if (Math.floorMod(column + row, 10) < 5) g.fill(x + column, y + row, x + column + 1, y + row + 1, 0xD8F16B51);
    }

    private static void fitted(GuiGraphics g, Font font, String text, int x, int y, int width, int colour)
    {
        String shown = font.plainSubstrByWidth(text, width - 12);
        g.drawString(font, shown, x + (width - font.width(shown)) / 2, y, colour, false);
    }
}
