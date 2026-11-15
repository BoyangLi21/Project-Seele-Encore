package com.projectseele.client;

import java.util.ArrayDeque;
import java.util.Comparator;
import java.util.Iterator;

import com.mojang.logging.LogUtils;
import com.projectseele.ProjectSeele;
import com.projectseele.visual.GeoFrontCommands;
import net.minecraft.client.Minecraft;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
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
 * After the surface it converts one cave layer, the one Xaero uses everywhere in the dimension when its cave
 * mode type is 2 ("full"), and writes that type into dimension_config.txt.
 * tools/package_r60.py installs the result (xaero/world-map/WORLD/projectseele$geofront) for the server.
 *
 * The outer ring was never saved as chunks, so Xaero has nothing to convert there. A run with
 * -Dprojectseele.xaeroBakePregen=x0,z0,x1,z1 (block bounds) generates and saves every chunk in the bounds
 * instead, then quits; only ever on the bake copy. It is a separate run because Xaero lists the world's
 * region files once, when the dimension opens.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class XaeroMapBake
{
    private static final Logger LOGGER = LogUtils.getLogger();
    private static final boolean ENABLED = Boolean.getBoolean("projectseele.xaeroBake");
    private static final String PREGEN = System.getProperty("projectseele.xaeroBakePregen");
    /** Chunks waiting on generation at once; the generator works on all of them in parallel. */
    private static final int PREGEN_WINDOW = Integer.getInteger("projectseele.xaeroBakePregenWindow", 256);
    private static final int SURFACE_LAYER = Integer.MAX_VALUE;
    /** Xaero's single cave layer for cave mode type 2: its cave start, and so its layer, is Integer.MIN_VALUE. */
    private static final int FULL_CAVE_LAYER = Integer.MIN_VALUE;
    private static final int FULL_CAVE_MODE_TYPE = 2;
    // Xaero lists the world's region files some time after the dimension opens.
    private static final int DETECTION_TICKS = 400;
    private static final int FLUSH_TICKS = 200;
    private static final TicketType<ChunkPos> PREGEN_TICKET = TicketType.create(
            "projectseele_xaero_pregen", Comparator.comparingLong(ChunkPos::toLong));

    private static boolean moved;
    private static int layerPass;
    private static int detection;
    private static int flush;

    private static int chunkX0, chunkZ0, width;
    private static long total, cursor, done;
    private static final ArrayDeque<ChunkPos> outstanding = new ArrayDeque<>();
    private static volatile boolean serverStepQueued;
    private static volatile boolean pregenFinished;
    private static boolean pregenReported;
    private static long pregenStarted;
    private static int reportTicks;

    private XaeroMapBake() { }

    @SubscribeEvent
    public static void clientTick(TickEvent.ClientTickEvent event)
    {
        if ((!ENABLED && PREGEN == null) || event.phase != TickEvent.Phase.END) return;
        var mc = Minecraft.getInstance();
        if (mc.level == null || mc.player == null || mc.getSingleplayerServer() == null) return;
        try
        {
            if (PREGEN != null) pregen(mc);
            else step(mc);
        }
        catch (ReflectiveOperationException | RuntimeException failure)
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
        if (layerPass == 0)
        {
            startReload(dimension, processor, SURFACE_LAYER);
            layerPass = 1;
            LOGGER.info("Xaero map bake started");
            return;
        }
        if (dimension.getClass().getMethod("getFullReloader").invoke(dimension) != null || flush++ < FLUSH_TICKS) return;
        if (layerPass == 1)
        {
            // Cave regions are built from the layer's cave start; a layer made here would start at 0.
            Object layers = dimension.getClass().getMethod("getLayeredMapRegions").invoke(dimension);
            Object layer = layers.getClass().getMethod("getLayer", int.class).invoke(layers, FULL_CAVE_LAYER);
            layer.getClass().getMethod("setCaveStart", int.class).invoke(layer, FULL_CAVE_LAYER);
            startReload(dimension, processor, FULL_CAVE_LAYER);
            layerPass = 2;
            flush = 0;
            LOGGER.info("Xaero map bake surface finished, full cave layer started");
            return;
        }
        var caveModeType = dimension.getClass().getDeclaredField("caveModeType");
        caveModeType.setAccessible(true);
        caveModeType.setInt(dimension, FULL_CAVE_MODE_TYPE);
        dimension.getClass().getMethod("saveConfigUnsynced").invoke(dimension);
        LOGGER.info("Xaero map bake finished");
        mc.stop();
    }

    private static void startReload(Object dimension, Object processor, int layer) throws ReflectiveOperationException
    {
        dimension.getClass().getMethod("startFullMapReload", int.class, boolean.class, processor.getClass())
                .invoke(dimension, layer, true, processor);
    }

    private static void pregen(Minecraft mc)
    {
        var server = mc.getSingleplayerServer();
        if (pregenFinished)
        {
            if (!pregenReported)
            {
                pregenReported = true;
                LOGGER.info("Xaero bake pregeneration finished: {} chunks in {} s", done, (System.nanoTime() - pregenStarted) / 1_000_000_000L);
                mc.stop();
            }
            return;
        }
        if (total == 0)
        {
            String[] bounds = PREGEN.split(",");
            chunkX0 = Integer.parseInt(bounds[0].trim()) >> 4;
            chunkZ0 = Integer.parseInt(bounds[1].trim()) >> 4;
            width = (Integer.parseInt(bounds[2].trim()) >> 4) - chunkX0 + 1;
            total = (long) width * ((Integer.parseInt(bounds[3].trim()) >> 4) - chunkZ0 + 1);
            pregenStarted = System.nanoTime();
            LOGGER.info("Xaero bake pregeneration of {} chunks from chunk {},{} ({} wide)", total, chunkX0, chunkZ0, width);
        }
        if (++reportTicks % 1200 == 0)
        {
            long seconds = Math.max(1, (System.nanoTime() - pregenStarted) / 1_000_000_000L);
            LOGGER.info("Xaero bake pregeneration {} of {} chunks, {} per second", done, total, done / seconds);
        }
        if (serverStepQueued) return;
        serverStepQueued = true;
        server.execute(() ->
        {
            try
            {
                pregenStep(server.getLevel(GeoFrontCommands.GEOFRONT));
            }
            finally
            {
                serverStepQueued = false;
            }
        });
    }

    /** Server thread: keep a window of chunk tickets open, closing each once its chunk is full; unloading saves it. */
    private static void pregenStep(ServerLevel level)
    {
        var chunks = level.getChunkSource();
        for (Iterator<ChunkPos> it = outstanding.iterator(); it.hasNext(); )
        {
            ChunkPos pos = it.next();
            // hasChunk only asks whether the ticket level reached FULL, not whether generation finished.
            if (chunks.getChunkNow(pos.x, pos.z) == null) continue;
            chunks.removeRegionTicket(PREGEN_TICKET, pos, 0, pos);
            it.remove();
            done++;
        }
        while (outstanding.size() < PREGEN_WINDOW && cursor < total)
        {
            ChunkPos pos = new ChunkPos(chunkX0 + (int) (cursor % width), chunkZ0 + (int) (cursor / width));
            cursor++;
            chunks.addRegionTicket(PREGEN_TICKET, pos, 0, pos);
            outstanding.add(pos);
        }
        if (cursor >= total && outstanding.isEmpty() && !pregenFinished)
        {
            level.getServer().saveEverything(false, true, true);
            pregenFinished = true;
        }
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
