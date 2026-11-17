package com.projectseele.client;

import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.network.chat.Component;
import net.minecraft.util.Mth;
import java.util.Locale;

/** TV-inspired optical panorama; game telemetry stays at the display margin. */
public final class EvaPilotDisplayR45
{
    private static final int AMBER = 0xFFE8A058, WHITE = 0xFFE2E7DF;
    private static final int MUTED = 0xFFBCC8C4, RED = 0xFFF16B51, GREEN = 0xFFA6C49A;

    public static void render(GuiGraphics g, Font font, EvaUnit01Entity eva, float partial, int width, int height)
    {
        if (width < 120 || height < 80) return;
        if (com.projectseele.client.cockpit.PilotCockpitR64.ON) { windows(g, font, eva, partial, width, height); return; }
        tiles(g, font, eva, partial, width, height);
    }

    /**
     * R64: the same readings as floating windows on the wall of the plug, as the original shows them: the internal
     * power counted down in large figures at the top, the synchronisation and condition of the unit at the left of
     * the pilot, the weapon at the right. The lower corners belong to the yokes and the hands on them.
     */
    private static void windows(GuiGraphics g, Font font, EvaUnit01Entity eva, float partial, int width, int height)
    {
        int margin = Math.max(8, Math.min(16, width / 45));
        int panel = Math.min(132, width / 2 - margin * 2);
        float hull = Mth.clamp(eva.getHealth() / Math.max(1, eva.getMaxHealth()), 0, 1);
        boolean stopped = EvaShutdownR30.disabled(eva) || !eva.isPoweredOn();
        boolean external = eva.isUmbilicalConnected();
        int ticks = Math.max(0, eva.getPowerTicks()), seconds = ticks / 20;
        boolean low = !external && seconds <= 60;
        int powerColour = stopped || low ? RED : external ? GREEN : AMBER;

        // Power: the five minutes the original counts down once the cable is gone, to the hundredth of a second.
        // At the top of the view, in the middle: the corners are the minimap's and other mods'.
        // The cannon's scope writes its range at the top of the view, in the middle: the countdown stands aside for it.
        int px = ClientForgeEvents.isCannonScopeActive(eva) ? width - margin - 104 : (width - 104) / 2, py = Math.max(4, margin - 4);
        window(g, px, py, 104, 40, powerColour);
        line(g, font, stopped ? "电源停止  OFFLINE" : external ? "外部电源  EXTERNAL" : "内部电源  INTERNAL", px + 5, py + 4, 96, powerColour);
        if (stopped) figures(g, px + 6, py + 15, -1, -1, -1, RED);
        else if (external)
        {
            line(g, font, "脐带缆  CONNECTED", px + 5, py + 16, 96, WHITE);
            gauge(g, px + 5, py + 31, 94, 1, GREEN);
        }
        else
        {
            // The last ten seconds blink, as an alarm does.
            boolean lit = seconds > 10 || (System.currentTimeMillis() / 250 & 1) == 0;
            float within = Mth.clamp(1 - partial, 0, 1);
            int hundredths = ticks <= 0 ? 0 : Mth.clamp(ticks % 20 * 5 - 5 + Math.round(within * 5), 0, 99);
            figures(g, px + 6, py + 15, seconds / 60, seconds % 60, hundredths, lit ? powerColour : 0x40F16B51);
            gauge(g, px + 5, py + 31, 94, Mth.clamp(ticks / (float) Math.max(1, eva.getPowerCapacityTicks()), 0, 1), powerColour);
        }

        // The unit: which one, how well the pilot is synchronised with it, what is left of the body and the field.
        int ly = Math.max(py + 46, height * 2 / 5 - 20);
        window(g, margin, ly, panel, 50, AMBER);
        float synchro = eva.getSynchronizationRatio(partial);
        line(g, font, String.format(Locale.ROOT, "EVA-%02d", eva.getUnitVariant()), margin + 5, ly + 4, 40, WHITE);
        String ratio = String.format(Locale.ROOT, "SYNCHRO %.1f%%", synchro);
        line(g, font, ratio, margin + panel - 5 - font.width(ratio), ly + 4, panel - 10, synchro < 25 ? RED : WHITE);
        harmonics(g, margin + 5, ly + 15, panel - 10, 9, synchro, eva.tickCount + partial);
        String body = String.format(Locale.ROOT, "机体 %03d%%", Math.round(hull * 100));
        line(g, font, body, margin + 5, ly + 27, 52, hull <= .34F ? RED : MUTED);
        gauge(g, margin + 58, ly + 30, panel - 63, hull, hull <= .34F ? RED : GREEN);
        String field = String.format(Locale.ROOT, "AT %03d", Math.round(eva.getAtFieldEnergy()));
        line(g, font, field, margin + 5, ly + 38, 52, eva.isAtFieldOn() ? GREEN : MUTED);
        gauge(g, margin + 58, ly + 41, panel - 63, Mth.clamp(eva.getAtFieldEnergy() / 200F, 0, 1), eva.isAtFieldOn() ? GREEN : AMBER);

        int rx = width - margin - panel;
        window(g, rx, ly, panel, 29, eva.isAtFieldOn() ? GREEN : AMBER);
        line(g, font, Component.translatable(eva.getWeaponTranslationKey()).getString(), rx + 5, ly + 4, panel - 10, WHITE);
        String stance = eva.isPilotProne() ? "趴伏" : eva.isPilotCrouching() ? "下蹲" : eva.isPilotSprinting() ? "冲刺" : "常规操纵";
        String radio = Keybinds.COMMAND_RADIO.getTranslatedKeyMessage().getString() + " 指挥通信";
        line(g, font, stance + "  /  " + radio, rx + 5, ly + 16, panel - 10, MUTED);
        // What is said to the pilot has its own window in the corner above (PilotChatPanelR64).

        alerts(g, font, eva, partial, width, height, py + 18, hull, stopped);
    }

    /** A window on the wall: a faint pane, a bright edge at its left and a notch at its top. */
    private static void window(GuiGraphics g, int x, int y, int width, int height, int colour)
    {
        g.fill(x, y, x + width, y + height, 0x5A0C1416);
        g.fill(x, y, x + 1, y + height, colour);
        g.fill(x + 1, y, x + Math.min(30, width), y + 1, colour);
        g.fill(x + width - 6, y + height - 1, x + width, y + height, colour & 0x00FFFFFF | 0x80000000);
    }

    /** A bar of ten cells. */
    private static void gauge(GuiGraphics g, int x, int y, int width, float value, int colour)
    {
        int cells = 10, cell = Math.max(2, width / cells), lit = Math.round(Mth.clamp(value, 0, 1) * cells);
        for (int i = 0; i < cells; i++)
            g.fill(x + i * cell, y, x + i * cell + cell - 1, y + 3, i < lit ? colour : 0x38BCC8C4);
    }

    /** Two waves that fall into step as the synchronisation rises. */
    private static void harmonics(GuiGraphics g, int x, int y, int width, int height, float synchro, float time)
    {
        g.fill(x, y + height / 2, x + width, y + height / 2 + 1, 0x24BCC8C4);
        float apart = (1 - Mth.clamp(synchro / 100F, 0, 1)) * Mth.PI, amplitude = (height - 1) * .5F;
        for (int i = 0; i < width; i++)
        {
            float at = i * .32F - time * .22F;
            int a = Math.round(y + amplitude - Mth.sin(at) * amplitude), b = Math.round(y + amplitude - Mth.sin(at + apart) * amplitude);
            g.fill(x + i, b, x + i + 1, b + 1, 0xB0A6C49A);
            g.fill(x + i, a, x + i + 1, a + 1, 0xFFE8A058);
        }
    }

    private static final int[] SEGMENTS = {0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F};

    /** minutes : seconds : hundredths in seven-segment figures; negative values draw dashes. */
    private static void figures(GuiGraphics g, int x, int y, int minutes, int seconds, int hundredths, int colour)
    {
        int at = x;
        at = figure(g, at, y, minutes < 0 ? -1 : minutes % 10, colour);
        at = colon(g, at, y, colour);
        at = figure(g, at, y, seconds < 0 ? -1 : seconds / 10, colour);
        at = figure(g, at, y, seconds < 0 ? -1 : seconds % 10, colour);
        at = colon(g, at, y, colour);
        at = figure(g, at, y, hundredths < 0 ? -1 : hundredths / 10, colour);
        figure(g, at, y, hundredths < 0 ? -1 : hundredths % 10, colour);
    }

    private static int figure(GuiGraphics g, int x, int y, int digit, int colour)
    {
        int lit = digit < 0 ? 0x40 : SEGMENTS[digit], ghost = colour & 0x00FFFFFF | 0x20000000;
        int w = 8, h = 13, t = 2, half = h / 2;
        int[][] bars = {{t, 0, w - t, t}, {w - t, t - 1, w, half}, {w - t, half + 1, w, h - t + 1}, {t, h - t, w - t, h},
                {0, half + 1, t, h - t + 1}, {0, t - 1, t, half}, {t, half - 1, w - t, half + 1}};
        for (int i = 0; i < 7; i++)
            g.fill(x + bars[i][0], y + bars[i][1], x + bars[i][2], y + bars[i][3], (lit >> i & 1) != 0 ? colour : ghost);
        return x + w + 3;
    }

    private static int colon(GuiGraphics g, int x, int y, int colour)
    {
        g.fill(x, y + 3, x + 2, y + 5, colour); g.fill(x, y + 8, x + 2, y + 10, colour);
        return x + 5;
    }

    private static void alerts(GuiGraphics g, Font font, EvaUnit01Entity eva, float partial, int width, int height, int top, float hull, boolean stopped)
    {
        if (eva.isLaunchSequenceActive())
        {
            String key = switch (eva.getLaunchPhase())
            {
                case EvaUnit01Entity.LAUNCH_LOCKED -> "hud.projectseele.launch_interlock";
                case EvaUnit01Entity.LAUNCH_ASCENT -> "hud.projectseele.launch_ascent";
                default -> "hud.projectseele.launch_surface_clear";
            };
            centred(g, font, Component.translatable(key).getString(), width, top + 30, RED);
            if (eva.getLaunchPhase() == EvaUnit01Entity.LAUNCH_LOCKED)
                centred(g, font, Component.translatable("hud.projectseele.self_launch_hint", Keybinds.SELF_LAUNCH.getTranslatedKeyMessage()).getString(), width, top + 42, AMBER);
        }
        else if (stopped)
            centred(g, font, EvaShutdownR30.wreck(eva) ? "机体损伤 / 等待回收" : "操纵系统停止", width, top + 30, RED);
        else if (hull <= .34F)
            centred(g, font, "机体损伤 / DAMAGE", width, top + 30, RED);

        float damage = ClientForgeEvents.damageFlash(partial);
        if (damage > 0)
        {
            int alpha = Mth.clamp(Math.round(120 * damage), 0, 120), edge = Math.max(3, height / 65);
            int colour = alpha << 24 | 0x00C4412C;
            g.fill(0, 0, width, edge, colour); g.fill(0, height - edge, width, height, colour);
            g.fill(0, edge, edge, height - edge, colour); g.fill(width - edge, edge, width, height - edge, colour);
        }
        if (eva.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE && !ClientForgeEvents.isRifleSightActive(eva))
        {
            int x = width / 2, y = height / 2;
            g.fill(x - 7, y, x - 3, y + 1, 0xB8DDD7C3); g.fill(x + 4, y, x + 8, y + 1, 0xB8DDD7C3);
        }
    }

    /** The tiles of R45 to R63, kept for -Dprojectseele.cockpitR64=false. */
    private static void tiles(GuiGraphics g, Font font, EvaUnit01Entity eva, float partial, int width, int height)
    {
        int margin = Math.max(8, Math.min(16, width / 45));
        int panel = Math.min(146, width / 2 - margin * 2);
        int left = margin, bottom = height - margin - 29;
        float hull = Mth.clamp(eva.getHealth() / Math.max(1, eva.getMaxHealth()), 0, 1);
        boolean stopped = EvaShutdownR30.disabled(eva) || !eva.isPoweredOn();
        boolean external = eva.isUmbilicalConnected();
        int seconds = Math.max(0, eva.getPowerTicks() / 20);
        int powerColour = stopped || !external && seconds <= 60 ? RED : external ? GREEN : AMBER;

        // TV 08 activation and TV 09 communications use the surrounding
        // optical field. These compact telemetry tiles are a game adaptation,
        // not a claim that the TV camera carried a fixed aircraft HUD.
        tile(g, left, margin, 108, 29, powerColour);
        line(g, font, stopped ? "电源停止 / OFFLINE" : external ? "外部电源 / EXTERNAL" : "内部电源 / INTERNAL",
                left + 5, margin + 4, 98, powerColour);
        String power = stopped ? "--:--" : external ? "CONNECTED" : String.format(Locale.ROOT, "%02d:%02d", seconds / 60, seconds % 60);
        line(g, font, power, left + 5, margin + 16, 98, WHITE);

        tile(g, left, bottom, panel, 29, AMBER);
        String identity = String.format(Locale.ROOT, "EVA-%02d  /  SYNCHRO %.1f%%", eva.getUnitVariant(), eva.getSynchronizationRatio(partial));
        line(g, font, identity, left + 5, bottom + 4, panel - 10, WHITE);
        String condition = String.format(Locale.ROOT, "机体 %03d%%    AT %03d", Math.round(hull * 100), Math.round(eva.getAtFieldEnergy()));
        line(g, font, condition, left + 5, bottom + 16, panel - 10, hull <= .34F ? RED : MUTED);

        int right = width - margin - panel;
        tile(g, right, bottom, panel, 29, eva.isAtFieldOn() ? GREEN : AMBER);
        line(g, font, Component.translatable(eva.getWeaponTranslationKey()).getString(), right + 5, bottom + 4, panel - 10, WHITE);
        String stance = eva.isPilotProne() ? "趴伏" : eva.isPilotCrouching() ? "下蹲" : eva.isPilotSprinting() ? "冲刺" : "常规操纵";
        String radio = Keybinds.COMMAND_RADIO.getTranslatedKeyMessage().getString() + " 指挥通信";
        line(g, font, stance + "  /  " + radio, right + 5, bottom + 16, panel - 10, MUTED);

        if (eva.isLaunchSequenceActive())
        {
            String key = switch (eva.getLaunchPhase())
            {
                case EvaUnit01Entity.LAUNCH_LOCKED -> "hud.projectseele.launch_interlock";
                case EvaUnit01Entity.LAUNCH_ASCENT -> "hud.projectseele.launch_ascent";
                default -> "hud.projectseele.launch_surface_clear";
            };
            centred(g, font, Component.translatable(key).getString(), width, margin + 38, RED);
            if (eva.getLaunchPhase() == EvaUnit01Entity.LAUNCH_LOCKED)
                centred(g, font, Component.translatable("hud.projectseele.self_launch_hint", Keybinds.SELF_LAUNCH.getTranslatedKeyMessage()).getString(), width, margin + 50, AMBER);
        }
        else if (stopped)
            centred(g, font, EvaShutdownR30.wreck(eva) ? "机体损伤 / 等待回收" : "操纵系统停止", width, margin + 38, RED);
        else if (hull <= .34F)
            centred(g, font, "机体损伤 / DAMAGE", width, margin + 38, RED);

        float damage = ClientForgeEvents.damageFlash(partial);
        if (damage > 0)
        {
            int alpha = Mth.clamp(Math.round(120 * damage), 0, 120), edge = Math.max(3, height / 65);
            int colour = alpha << 24 | 0x00C4412C;
            g.fill(0, 0, width, edge, colour); g.fill(0, height - edge, width, height, colour);
            g.fill(0, edge, edge, height - edge, colour); g.fill(width - edge, edge, width, height - edge, colour);
        }
        if (eva.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE && !ClientForgeEvents.isRifleSightActive(eva))
        {
            int x = width / 2, y = height / 2;
            g.fill(x - 7, y, x - 3, y + 1, 0xB8DDD7C3); g.fill(x + 4, y, x + 8, y + 1, 0xB8DDD7C3);
        }
    }

    private static void tile(GuiGraphics g, int x, int y, int width, int height, int colour)
    {
        g.fill(x, y, x + width, y + height, 0x80101818);
        g.fill(x, y, x + 1, y + height, colour);
        g.fill(x + 1, y, x + Math.min(26, width), y + 1, colour);
    }
    private static void line(GuiGraphics g, Font font, String text, int x, int y, int width, int colour)
    {
        g.drawString(font, font.plainSubstrByWidth(text, Math.max(0, width)), x, y, colour, false);
    }
    private static void centred(GuiGraphics g, Font font, String text, int width, int y, int colour)
    {
        String fitted = font.plainSubstrByWidth(text, width - 24);
        g.drawString(font, fitted, (width - font.width(fitted)) / 2, y, colour, true);
    }
    private EvaPilotDisplayR45() {}
}
