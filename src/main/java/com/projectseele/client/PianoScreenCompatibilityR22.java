package com.projectseele.client;

import com.projectseele.client.screen.ScreenGuiScale;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Keep the optional piano's fixed 420x270 panel within the current window. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class PianoScreenCompatibilityR22
{
    private static boolean fitted;
    public static boolean piano(Object screen){return screen!=null&&screen.getClass().getName().equals("com.solvane.grandpiano.client.gui.PianoPlayScreen");}
    public static boolean playTab(Object screen)
    {
        if(!piano(screen))return false;
        try{var f=screen.getClass().getDeclaredField("activeTab");f.setAccessible(true);return String.valueOf(f.get(screen)).equals("PLAY");}
        catch(ReflectiveOperationException e){return false;}
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent e)
    {
        if(e.phase!=TickEvent.Phase.END)return;var mc=Minecraft.getInstance();var window=mc.getWindow();
        if(piano(mc.screen)&&!fitted)
        {
            fitted=true;int fit=Math.max(1,Math.min(window.getWidth()/444,window.getHeight()/294));
            if((window.getGuiScaledWidth()<444||window.getGuiScaledHeight()<294)&&ScreenGuiScale.set(mc,fit))
                mc.screen.resize(mc,window.getGuiScaledWidth(),window.getGuiScaledHeight());
        }
        else if(!piano(mc.screen)&&fitted)
        {
            fitted=false;
            if(ScreenGuiScale.set(mc,ScreenGuiScale.normal(mc))&&mc.screen!=null)mc.screen.resize(mc,window.getGuiScaledWidth(),window.getGuiScaledHeight());
        }
    }
    private PianoScreenCompatibilityR22(){}
}
