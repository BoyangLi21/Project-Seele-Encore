package com.projectseele.client.cockpit;

import com.projectseele.entity.EntryPlugCarrierEntity;
import net.minecraft.ChatFormatting;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.network.chat.Component;
import net.minecraft.util.Mth;

/**
 * R64: the cabin sequence as the plug shows it: the lock, the LCL, the nerve connection, the synchronisation.
 * <p>
 * Up to R63 this was a flat orange rectangle rising up the screen, a black frame and a progress bar in the middle
 * of the picture. The LCL is now the liquid itself (PilotLclR64, drawn with the plug's inside); what is left here
 * is what the plug's wall says while it happens: one line and a thin bar in the upper part of the view, the
 * connection's bands of colour running over the wall, and the wall coming on as the Unit's eyes open.
 * The steps and their timing are the server's, unchanged.
 */
public final class PilotSequenceDisplayR64
{
    private static final int ORANGE = 0xFFFF7A00, PALE = 0xFFE8D2B8, GREY = 0xFF8A8178;
    /** The connection's bands: the colours of a spectrum, one after another. */
    private static final int[] SPECTRUM = {0xE8483C, 0xF08A2C, 0xE8D03C, 0x6CC858, 0x48B8D8, 0x4C6CE0, 0xA050D0};

    private PilotSequenceDisplayR64() {}

    /** The capsule is on its way out of its Unit or already out of it: none of the insertion's steps is running. */
    private static boolean leaving(EntryPlugCarrierEntity plug)
    {
        int stage = plug.getInsertionStage();
        return stage == EntryPlugCarrierEntity.STAGE_EJECTING || stage == EntryPlugCarrierEntity.STAGE_FIELD_EJECTING
                || stage == EntryPlugCarrierEntity.STAGE_FIELD_LANDED;
    }

    public static void render(Font font, GuiGraphics g, LocalPlayer player, float partial, int width, int height)
    {
        float progress = PilotCockpitR64.sequence(player, partial);
        if (progress < 0) return;
        EntryPlugCarrierEntity plug = player.getVehicle() instanceof EntryPlugCarrierEntity carrier ? carrier : null;
        int top = Math.max(26, height / 5);
        if (plug != null && plug.getCabinStage() == EntryPlugCarrierEntity.CABIN_SEALED_DARK)
        {
            // Sealed and waiting for the order: the plug's own lamps, and the wall still dark.
            g.drawCenteredString(font, Component.translatable("hud.projectseele.plug_sealed").withStyle(ChatFormatting.GOLD), width / 2, top, ORANGE);
            g.drawCenteredString(font, Component.translatable("hud.projectseele.await_prepare").withStyle(ChatFormatting.DARK_GRAY), width / 2, top + 12, GREY);
            return;
        }
        if (plug != null && leaving(plug))
        {
            // Drawn out by the crane or thrown clear: the capsule says so while its LCL runs out, and nothing after.
            if (PilotLclR64.fill() > 0)
                g.drawCenteredString(font, Component.translatable("hud.projectseele.plug_released").withStyle(ChatFormatting.BOLD), width / 2, top, ORANGE);
            return;
        }
        float fade = progress > .80F ? Mth.clamp(1 - (progress - .80F) / .20F, 0, 1) : 1;
        if (progress > PilotCockpitR64.STEP_NERVE)
        {
            // The nerve connection: bands of colour climb the wall, wider, closer and quicker as it takes, then
            // thin out as the wall comes on. Soft-edged, and never more than a third opaque: the cabin shows through.
            float take = Mth.clamp((progress - PilotCockpitR64.STEP_NERVE) / (PilotCockpitR64.STEP_SYNC - PilotCockpitR64.STEP_NERVE), 0, 1), time = (System.currentTimeMillis() % 100000L) / 1000F;
            int bands = 6 + Math.round(take * 8), half = 1 + Math.round(3 * take);
            for (int i = 0; i < bands; i++)
            {
                float at = ((float) i / bands + time * (.10F + .22F * take)) % 1F;
                int y = height - Math.round(at * height);
                int alpha = Math.round((26 + 60 * take) * fade * (1 - Math.abs(at - .5F) * 1.2F));
                if (alpha <= 2) continue;
                int colour = SPECTRUM[i % SPECTRUM.length];
                for (int k = -half; k <= half; k++)
                {
                    int soft = Math.round(alpha * (1 - Math.abs(k) / (half + 1F)));
                    if (soft > 2) g.fill(0, y + k, width, y + k + 1, soft << 24 | colour);
                }
            }
        }
        if (progress > PilotCockpitR64.STEP_SYNC)
        {
            // The wall comes on: a line of light opens from the middle of the view to its edges and is gone.
            float open = Mth.clamp((progress - PilotCockpitR64.STEP_SYNC) / .12F, 0, 1);
            int half = Math.round(open * open * height * .5F), alpha = Math.round(70 * (1 - open));
            if (alpha > 2) g.fill(0, height / 2 - half - 1, width, height / 2 + half + 1, alpha << 24 | 0xFFF1DC);
        }
        // On its way to the socket the capsule only says that it is being inserted; the lock, the LCL, the nerve
        // connection and the synchronisation follow once it is seated, in the original's order.
        boolean carried = plug != null && !plug.isLockedToEva() && progress <= PilotCockpitR64.STEP_INSERTED + .001F;
        String key = carried ? "hud.projectseele.plug_inserting"
                : progress < PilotCockpitR64.STEP_LCL ? "hud.projectseele.plug_lock"
                : progress < PilotCockpitR64.STEP_NERVE ? "hud.projectseele.lcl_pressurize"
                : progress < PilotCockpitR64.STEP_SYNC ? "hud.projectseele.a10_connect"
                : "hud.projectseele.synch_start";
        int textAlpha = Mth.clamp(Math.round(255 * fade), 0, 255);
        if (textAlpha < 12) return;
        g.drawCenteredString(font, Component.translatable(key).withStyle(ChatFormatting.BOLD), width / 2, top, textAlpha << 24 | ORANGE & 0xFFFFFF);
        // A thin bar with the four steps marked on it.
        int bar = Math.min(200, width / 2), x = width / 2 - bar / 2, y = top + 12;
        g.fill(x, y, x + bar, y + 2, Math.round(110 * fade) << 24 | 0x202020);
        g.fill(x, y, x + Math.round(bar * progress), y + 2, textAlpha << 24 | ORANGE & 0xFFFFFF);
        for (float mark : new float[]{PilotCockpitR64.STEP_LCL, PilotCockpitR64.STEP_NERVE, PilotCockpitR64.STEP_SYNC})
            g.fill(x + Math.round(bar * mark), y - 1, x + Math.round(bar * mark) + 1, y + 3, textAlpha << 24 | PALE & 0xFFFFFF);
        g.drawCenteredString(font, String.format(java.util.Locale.ROOT, "%03d%%", Math.round(progress * 100)), width / 2, y + 6, textAlpha << 24 | PALE & 0xFFFFFF);
    }
}
