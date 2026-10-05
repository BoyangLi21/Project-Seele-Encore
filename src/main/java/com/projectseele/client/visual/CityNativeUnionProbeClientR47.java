package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.world.CityNativeUnionProbeR47;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Separate physical client witness of its actual tracked complete city input. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class CityNativeUnionProbeClientR47
{
    private static int ticks;
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||System.getProperty("projectseele.r47CityUnionClientProbe","").isBlank()||++ticks%20!=0)return;
        var mc=net.minecraft.client.Minecraft.getInstance();
        if(mc.level!=null)CityNativeUnionProbeR47.observe(mc.level,mc.level.entitiesForRendering(),"forgeclient","projectseele.r47CityUnionClientProbe");
    }
    private CityNativeUnionProbeClientR47() {}
}
