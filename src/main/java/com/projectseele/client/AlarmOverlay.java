package com.projectseele.client;

import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.util.Mth;
import net.minecraftforge.client.gui.overlay.ForgeGui;
import net.minecraftforge.client.gui.overlay.IGuiOverlay;

/**
 * Pulsing red combat vignette while the Angel alarm is live: three nested
 * translucent frames hugging the screen edges, breathing at siren tempo.
 */
public class AlarmOverlay implements IGuiOverlay
{
    public static final AlarmOverlay INSTANCE = new AlarmOverlay();

    /** Eased 0..1 so the vignette fades in and out instead of popping. */
    private float intensity;
    public void resetConnectionR45(){intensity=0;}

    @Override
    public void render(ForgeGui gui, GuiGraphics guiGraphics, float partialTick, int width, int height)
    {
        if (!com.projectseele.config.SeeleConfig.ALARM_VIGNETTE.get())
        {
            return;
        }
        float target = ClientAlarmState.isActive() ? 1.0F : 0.0F;
        this.intensity += (target - this.intensity) * 0.06F;
        if (this.intensity < 0.01F)
        {
            return;
        }

        float time = (System.currentTimeMillis() % 60000L) / 1000.0F;
        float pulse = 0.75F + 0.25F * Mth.sin(time * (float) Math.PI * 1.1F);
        float strength = this.intensity * pulse;

        int edge = Math.min(width, height);
        drawFrame(guiGraphics, width, height, Math.round(edge * 0.055F), alpha(0.34F * strength));
        drawFrame(guiGraphics, width, height, Math.round(edge * 0.030F), alpha(0.30F * strength));
        drawFrame(guiGraphics, width, height, Math.round(edge * 0.012F), alpha(0.42F * strength));
    }

    private static int alpha(float a)
    {
        return (Math.round(Mth.clamp(a, 0.0F, 1.0F) * 255.0F) << 24) | 0xCC0000;
    }

    /** One hollow rectangle hugging the screen border at the given thickness. */
    private static void drawFrame(GuiGraphics guiGraphics, int width, int height, int thickness, int color)
    {
        guiGraphics.fill(0, 0, width, thickness, color);
        guiGraphics.fill(0, height - thickness, width, height, color);
        guiGraphics.fill(0, thickness, thickness, height - thickness, color);
        guiGraphics.fill(width - thickness, thickness, width, height - thickness, color);
    }
}
