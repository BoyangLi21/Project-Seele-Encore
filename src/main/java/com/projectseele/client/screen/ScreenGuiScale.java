package com.projectseele.client.screen;

import net.minecraft.client.Minecraft;

/**
 * A GUI scale for one screen. Only the window is touched, never the stored option:
 * with Distant Horizons installed, Oculus reloads the whole shader pack as soon as
 * the guiScale option differs from the value it last saw, and that froze the game
 * for seconds each time such a screen opened or closed.
 */
public final class ScreenGuiScale
{
    /** The scale the stored option gives this window. */
    public static int normal(Minecraft mc)
    {
        return mc.getWindow().calculateScale(mc.options.guiScale().get(), mc.isEnforceUnicode());
    }

    /** True when the window's scale changed, so the caller has to lay its widgets out again. */
    public static boolean set(Minecraft mc, int scale)
    {
        var window = mc.getWindow();
        if ((int) window.getGuiScale() == scale) return false;
        window.setGuiScale(scale);
        return true;
    }

    private ScreenGuiScale()
    {
    }
}
