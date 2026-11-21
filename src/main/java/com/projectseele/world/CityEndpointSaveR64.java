package com.projectseele.world;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import com.projectseele.mixin.CityChunkMapAccessor;
import net.minecraft.server.level.ChunkHolder;
import net.minecraft.server.level.ChunkMap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.storage.IOWorker;
import net.minecraftforge.fml.util.ObfuscationReflectionHelper;

/** Spread native chunk serialization over the FLUSH phase before its final level save. */
final class CityEndpointSaveR64
{
    private static final Method SAVE_CHUNK = ObfuscationReflectionHelper.findMethod(
            ChunkMap.class, "m_140258_", ChunkAccess.class);
    private final ServerLevel level;
    private final List<ChunkPos> chunks;
    private final CityEntitySaveFence fence;
    private int cursor;
    private List<ChunkHolder> others;
    private int otherCursor;
    private CompletableFuture<Void> writes;

    CityEndpointSaveR64(ServerLevel level, List<ChunkPos> chunks)
    {
        this.level = level;
        this.fence = new CityEntitySaveFence(level);
        this.chunks = chunks;
    }

    boolean drain(long deadline) throws ReflectiveOperationException
    {
        var source = level.getChunkSource();
        while (cursor < chunks.size())
        {
            ChunkPos pos = chunks.get(cursor++);
            var chunk = source.getChunkNow(pos.x, pos.z);
            if (chunk != null && chunk.isUnsaved())
            {
                try {
                    if (!((boolean) SAVE_CHUNK.invoke(source.chunkMap, chunk)))
                        throw new IllegalStateException("Could not queue city chunk save at " + pos);
                } catch (ReflectiveOperationException | RuntimeException error) {
                    chunk.setUnsaved(true);
                    throw error;
                }
            }
            if (System.nanoTime() >= deadline) return false;
        }
        // Every other loaded chunk with unsaved changes, under the same deadline: the full level save below
        // would otherwise serialize them all on the server thread in one tick (R65).
        if (others == null)
        {
            others = new ArrayList<>();
            for (ChunkHolder holder : ((CityChunkMapAccessor) source.chunkMap).seele$chunksR65()) others.add(holder);
        }
        while (otherCursor < others.size())
        {
            ChunkAccess chunk = others.get(otherCursor++).getChunkToSave().getNow(null);
            if (chunk != null && chunk.isUnsaved())
            {
                try {
                    SAVE_CHUNK.invoke(source.chunkMap, chunk);
                } catch (ReflectiveOperationException | RuntimeException error) {
                    chunk.setUnsaved(true);
                    throw error;
                }
            }
            if (System.nanoTime() >= deadline) return false;
        }
        // The native writer owns the I/O. All live chunk/NBT access stays on the server thread.
        // The caller still runs the full level barrier for entities, saved data and later edits.
        if (source.chunkMap.chunkScanner() instanceof IOWorker worker)
        {
            if (writes == null) writes = worker.synchronize(true);
            if (!writes.isDone()) return false;
            writes.join();
        }
        return fence.advance();
    }
}
