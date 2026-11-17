package com.projectseele.client.cockpit;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.Util;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.network.chat.Component;
import net.minecraft.util.FormattedCharSequence;
import net.minecraft.util.Mth;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientChatReceivedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.util.List;

/**
 * R64: what the command post says to a pilot comes up as a window on the plug's wall, sound only, as the original
 * shows a voice link: who is speaking and what they say, for as long as it takes to read. Up to R63 these lines
 * went to the chat, across the lower left of the view. Only while a Unit is piloted in first person with the
 * cockpit's windows on; anywhere else the line goes to the chat as before.
 * <p>
 * The lines are the server's ordinary system messages of the form 「speaker」 text (NervStaffDialogue.say and the
 * combat command brief); nothing new is sent.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class PilotCommWindowR64
{
    private static final int ORANGE = 0xFFE8A058, WHITE = 0xFFE2E7DF, CYAN = 0xFF75BDC5, RED = 0xFFF16B51;
    private static String speaker = "", body = "";
    private static long shownAt = Long.MIN_VALUE, shownFor;

    private PilotCommWindowR64() {}

    private static boolean windowsOn(Minecraft mc)
    {
        if (!PilotCockpitR64.ON || mc.player == null || !mc.options.getCameraType().isFirstPerson() || mc.getCameraEntity() != mc.player) return false;
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(mc.player);
        // The UN units keep their own display, and the cabin sequence has the wall to itself.
        return eva != null && !eva.isExperimentalUnit() && !eva.isActivationCinematicActive() && !mc.options.hideGui;
    }

    @SubscribeEvent
    public static void heard(ClientChatReceivedEvent.System event)
    {
        if (event.isOverlay() || !windowsOn(Minecraft.getInstance())) return;
        String text = event.getMessage().getString();
        int end = text.indexOf('」');
        if (!text.startsWith("「") || end < 2 || end + 1 >= text.length()) return;
        speaker = text.substring(1, end);
        body = text.substring(end + 1).trim();
        shownAt = Util.getMillis();
        // Long enough to read: three seconds and a tenth of a second a character, nine at most.
        shownFor = Math.max(3500L, Math.min(9000L, 3000L + body.length() * 100L));
        event.setCanceled(true);
    }

    /** The window, under the weapon's: nothing while nobody speaks. Returns the height it took. */
    public static int render(GuiGraphics g, Font font, int x, int y, int width)
    {
        long age = Util.getMillis() - shownAt;
        if (shownAt == Long.MIN_VALUE || age < 0 || age > shownFor) return 0;
        float in = Mth.clamp(age / 180F, 0, 1), out = Mth.clamp((shownFor - age) / 400F, 0, 1);
        int alpha = Math.round(255 * Math.min(in, out));
        if (alpha < 16) return 0;
        List<FormattedCharSequence> lines = font.split(Component.literal(body), width - 10);
        int shown = Math.min(3, lines.size()), height = 27 + shown * 10;
        g.fill(x, y, x + width, y + height, Math.round(alpha * .35F) << 24 | 0x0C1416);
        g.fill(x, y, x + 1, y + height, alpha << 24 | RED & 0xFFFFFF);
        g.fill(x + 1, y, x + Math.min(30, width), y + 1, alpha << 24 | RED & 0xFFFFFF);
        g.drawString(font, "SOUND ONLY", x + 5, y + 4, alpha << 24 | RED & 0xFFFFFF, false);
        // The voice's level: a few bars that move while the line is up.
        for (int i = 0; i < 7; i++)
        {
            int level = 2 + Math.round(3 * Math.abs(Mth.sin(age * .012F + i * 1.7F)));
            g.fill(x + width - 8 - i * 3, y + 11 - level, x + width - 6 - i * 3, y + 11, alpha << 24 | ORANGE & 0xFFFFFF);
        }
        g.drawString(font, font.plainSubstrByWidth(speaker, width - 10), x + 5, y + 15, alpha << 24 | CYAN & 0xFFFFFF, false);
        for (int i = 0; i < shown; i++) g.drawString(font, lines.get(i), x + 5, y + 26 + i * 10, alpha << 24 | WHITE & 0xFFFFFF, false);
        return height + 4;
    }
}
