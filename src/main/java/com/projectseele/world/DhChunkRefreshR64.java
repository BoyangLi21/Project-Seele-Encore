package com.projectseele.world;

import java.lang.reflect.Method;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import com.projectseele.ProjectSeele;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.chunk.LevelChunk;

/**
 * Pushes chunks that changed without being saved into Distant Horizons. DH 2.3.4 only rebuilds a
 * far-view column when the server saves or loads a chunk, so the moving Tokyo-3 towers would hang
 * as stale LODs until the next autosave. overwriteChunkDataAsync takes the same path as DH's own
 * save hook (unchanged chunks are skipped by hash) and the server forwards the result to players.
 * Reflection keeps DH optional: without it every call is a no-op.
 */
public final class DhChunkRefreshR64
{
    /** DH's multiplayer sync is limited to 50 sections a second per player; stay near that. */
    private static final int CHUNKS_PER_TICK = 24;
    private static final Map<ResourceKey<Level>, LinkedHashSet<Long>> QUEUE = new ConcurrentHashMap<>();

    private static boolean resolved;
    private static Object worldProxy;
    private static Object terrainRepo;
    private static Method allLevels;
    private static Method wrappedObject;
    private static Method dimensionName;
    private static Method overwrite;

    private DhChunkRefreshR64() {}

    public static void queue(ServerLevel level, long[] chunks)
    {
        if (!available()) return;
        LinkedHashSet<Long> pending = QUEUE.computeIfAbsent(level.dimension(), key -> new LinkedHashSet<>());
        synchronized (pending)
        {
            for (long chunk : chunks) pending.add(chunk);
            ProjectSeele.LOGGER.info("DH far-view refresh queued {} chunks in {} ({} pending)",
                    chunks.length, level.dimension().location(), pending.size());
        }
    }

    public static void tick(ServerLevel level)
    {
        LinkedHashSet<Long> pending = QUEUE.get(level.dimension());
        if (pending == null) return;
        long[] batch;
        synchronized (pending)
        {
            if (pending.isEmpty()) return;
            batch = new long[Math.min(CHUNKS_PER_TICK, pending.size())];
            Iterator<Long> it = pending.iterator();
            for (int i = 0; i < batch.length; i++)
            {
                batch[i] = it.next();
                it.remove();
            }
            if (pending.isEmpty())
            {
                ProjectSeele.LOGGER.info("DH far-view refresh queue drained in {}", level.dimension().location());
            }
        }
        Object wrapper = levelWrapper(level);
        if (wrapper == null) return;
        try
        {
            for (long packed : batch)
            {
                // Only resident chunks: the travel tickets keep the district loaded, and a remote
                // chunk is never worth a synchronous load here.
                LevelChunk chunk = level.getChunkSource().getChunkNow(ChunkPos.getX(packed), ChunkPos.getZ(packed));
                if (chunk != null) overwrite.invoke(terrainRepo, wrapper, new Object[] {chunk, level});
            }
        }
        catch (ReflectiveOperationException | RuntimeException failure)
        {
            ProjectSeele.LOGGER.warn("Distant Horizons chunk refresh failed; far view updates on the next save", failure);
            QUEUE.clear();
            terrainRepo = null;
        }
    }

    private static boolean available()
    {
        if (!resolved)
        {
            resolved = true;
            try
            {
                var delayed = Class.forName("com.seibel.distanthorizons.api.DhApi$Delayed");
                var proxyType = Class.forName("com.seibel.distanthorizons.api.interfaces.world.IDhApiWorldProxy");
                var levelType = Class.forName("com.seibel.distanthorizons.api.interfaces.world.IDhApiLevelWrapper");
                var repoType = Class.forName("com.seibel.distanthorizons.api.interfaces.data.IDhApiTerrainDataRepo");
                var unsafeType = Class.forName("com.seibel.distanthorizons.api.interfaces.IDhApiUnsafeWrapper");
                allLevels = proxyType.getMethod("getAllLoadedLevelWrappers");
                dimensionName = levelType.getMethod("getDimensionName");
                wrappedObject = unsafeType.getMethod("getWrappedMcObject");
                overwrite = repoType.getMethod("overwriteChunkDataAsync", levelType, Object[].class);
                worldProxy = delayed.getField("worldProxy").get(null);
                terrainRepo = delayed.getField("terrainRepo").get(null);
            }
            catch (ClassNotFoundException absent)
            {
                return false;
            }
            catch (ReflectiveOperationException failure)
            {
                ProjectSeele.LOGGER.warn("Distant Horizons API not usable; city travel will not refresh the far view", failure);
                return false;
            }
        }
        return terrainRepo != null && worldProxy != null;
    }

    private static Object levelWrapper(ServerLevel level)
    {
        try
        {
            Object byName = null;
            String name = level.dimension().location().toString();
            for (Object wrapper : (Iterable<?>) allLevels.invoke(worldProxy))
            {
                if (wrappedObject.invoke(wrapper) == level) return wrapper;
                if (byName == null && name.equals(dimensionName.invoke(wrapper))) byName = wrapper;
            }
            return byName;
        }
        catch (ReflectiveOperationException | RuntimeException notLoaded)
        {
            return null;
        }
    }
}
