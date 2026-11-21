package com.projectseele.world;

import java.util.concurrent.CompletableFuture;
import com.projectseele.mixin.ServiceAircraftSectionsR32Accessor;
import com.projectseele.mixin.ServiceAircraftWorldR32Accessor;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.thread.ProcessorMailbox;
import net.minecraft.world.level.chunk.storage.IOWorker;
import net.minecraftforge.event.level.LevelEvent;
import net.minecraftforge.eventbus.api.Event;
import net.minecraftforge.eventbus.api.IEventBus;

/** The endpoint journal waits across ticks for the native entity and chunk writers' final disk barriers. */
public final class CityEntitySaveFence
{
    private static final ThreadLocal<CityEntitySaveFence> ACTIVE = new ThreadLocal<>();
    private final ServerLevel level;
    private final Object storage;
    private final Object chunks;
    private CompletableFuture<Void> writes;
    private CompletableFuture<Void> chunkWrites;
    private ProcessorMailbox<Runnable> mailbox;
    private Runnable announce;
    private boolean started;

    CityEntitySaveFence(ServerLevel level)
    {
        this.level = level;
        var manager = ((ServiceAircraftWorldR32Accessor) level).seele$entityManagerR32();
        storage = ((ServiceAircraftSectionsR32Accessor) manager).seele$storageR65();
        chunks = level.getChunkSource().chunkMap;
    }

    public static boolean deferFinalFlush(Object source, IOWorker worker, ProcessorMailbox<Runnable> queue)
    {
        var fence = ACTIVE.get();
        if (fence == null || source != fence.storage || fence.writes != null) return false;
        fence.writes = worker.synchronize(true);
        fence.mailbox = queue;
        return true;
    }

    /** The full level save ends with a blocking flush of the region writer; the endpoint polls it instead (R65). */
    public static boolean deferChunkFlush(Object source, IOWorker worker)
    {
        var fence = ACTIVE.get();
        if (fence == null || source != fence.chunks || fence.chunkWrites != null) return false;
        fence.chunkWrites = worker.synchronize(true);
        return true;
    }

    public static boolean postWhenDurable(IEventBus bus, Event event)
    {
        var fence = ACTIVE.get();
        if (fence == null || fence.writes == null && fence.chunkWrites == null || !(event instanceof LevelEvent.Save save)
                || save.getLevel() != fence.level) return bus.post(event);
        fence.announce = () -> bus.post(event);
        return false;
    }

    boolean advance()
    {
        if (!started)
        {
            started = true;
            ACTIVE.set(this);
            try { level.save(null, true, false); }
            finally { ACTIVE.remove(); }
        }
        if (writes != null && !writes.isDone() || chunkWrites != null && !chunkWrites.isDone()) return false;
        if (chunkWrites != null) chunkWrites.join();
        if (writes != null)
        {
            writes.join();
            mailbox.runAll();
        }
        if (announce != null) announce.run();
        return true;
    }
}
