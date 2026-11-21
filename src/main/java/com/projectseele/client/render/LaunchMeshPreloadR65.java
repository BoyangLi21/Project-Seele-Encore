package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Joining a world starts the background parse of the large launch machinery meshes (R65). */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class LaunchMeshPreloadR65
{
    @SubscribeEvent public static void joined(ClientPlayerNetworkEvent.LoggingIn event)
    {
        TvFacilityMeshes.preloadR65();
        TvCageEnclosureR44.preloadR65();
    }
    private LaunchMeshPreloadR65() {}
}
