package com.projectseele.client;

import com.mojang.logging.LogUtils;
import com.projectseele.ProjectSeele;
import com.projectseele.visual.GeoFrontCommands;
import net.minecraft.client.Minecraft;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.GameType;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.slf4j.Logger;

/**
 * Release build step, off unless the game runs with -Dprojectseele.xaeroBake=true on a singleplayer copy
 * of the final world: Xaero converts every saved GeoFront region into its own map files, then the game quits.
 * A multiplayer client only lists a region that has a file like these, so tile caches alone never show.
 * tools/package_r60.py installs the result (xaero/world-map/WORLD/projectseele$geofront) for the server.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class XaeroMapBake
{
    private static final Logger LOGGER = LogUtils.getLogger();
    private static final boolean ENABLED = Boolean.getBoolean("projectseele.xaeroBake");
    private static final int SURFACE_LAYER = Integer.MAX_VALUE;
    // Xaero lists the world's region files some time after the dimension opens.
    private static final int DETECTION_TICKS = 400;
    private static final int FLUSH_TICKS = 200;

    private static boolean moved;
    private static boolean converting;
    private static int detection;
    private static int flush;

    private XaeroMapBake() { }

    @SubscribeEvent
    public static void clientTick(TickEvent.ClientTickEvent event)
    {
        if (!ENABLED || event.phase != TickEvent.Phase.END) return;
        var mc = Minecraft.getInstance();
        if (mc.level == null || mc.player == null || mc.getSingleplayerServer() == null) return;
        try
        {
            step(mc);
        }
        catch (ReflectiveOperationException failure)
        {
            LOGGER.error("Xaero map bake failed", failure);
            mc.stop();
        }
    }

    private static void step(Minecraft mc) throws ReflectiveOperationException
    {
        if (mc.level.dimension() != GeoFrontCommands.GEOFRONT)
        {
            if (!moved) moveToGeoFront(mc);
            return;
        }
        if (detection++ < DETECTION_TICKS) return;
        Class<?> sessionType = Class.forName("xaero.map.WorldMapSession");
        Object session = sessionType.getMethod("getCurrentSession").invoke(null);
        if (session == null) return;
        Object processor = sessionType.getMethod("getMapProcessor").invoke(session);
        Object world = processor.getClass().getMethod("getMapWorld").invoke(processor);
        Object dimension = world.getClass().getMethod("getCurrentDimension").invoke(world);
        if (!converting)
        {
            dimension.getClass().getMethod("startFullMapReload", int.class, boolean.class, processor.getClass())
                    .invoke(dimension, SURFACE_LAYER, true, processor);
            converting = true;
            LOGGER.info("Xaero map bake started");
            return;
        }
        if (dimension.getClass().getMethod("getFullReloader").invoke(dimension) != null || flush++ < FLUSH_TICKS) return;
        LOGGER.info("Xaero map bake finished");
        mc.stop();
    }

    private static void moveToGeoFront(Minecraft mc)
    {
        moved = true;
        var server = mc.getSingleplayerServer();
        server.execute(() ->
        {
            ServerLevel geoFront = server.getLevel(GeoFrontCommands.GEOFRONT);
            var player = server.getPlayerList().getPlayers().get(0);
            player.setGameMode(GameType.SPECTATOR);
            player.teleportTo(geoFront, 0.5, 320.0, 0.5, 0.0F, 0.0F);
        });
    }
}
