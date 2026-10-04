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
        String radio = Keybinds.COMMAND_RADIO.getTranslatedKeyMessage().getString() + " 通信";
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
