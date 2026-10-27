package com.projectseele.world;

import java.util.ArrayList;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.BooleanSupplier;
import java.util.function.Supplier;
import net.minecraftforge.event.server.ServerStoppingEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Bounded pure-source work; no world or actor may be captured by a task. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class NervGeometryWorkR53
{
    private static final AtomicLong GENERATION=new AtomicLong();
    private static final ThreadLocal<Work<?>> ACTIVE=new ThreadLocal<>();
    private static final ThreadPoolExecutor EXECUTOR=new ThreadPoolExecutor(2,2,0,TimeUnit.MILLISECONDS,
            new ArrayBlockingQueue<>(8),r->{var thread=new Thread(r,"SEELE immutable geometry");thread.setDaemon(true);return thread;},
            new ThreadPoolExecutor.AbortPolicy());
    private static final class Work<T> implements Runnable
    {
        final long generation=GENERATION.get();
        final BooleanSupplier sourceValid;
        final Supplier<T> calculation;
        final CompletableFuture<T> result=new CompletableFuture<>();
        Work(BooleanSupplier sourceValid,Supplier<T> calculation){this.sourceValid=sourceValid;this.calculation=calculation;}
        boolean current(){return generation==GENERATION.get()&&!result.isDone()&&sourceValid.getAsBoolean();}
        @Override public void run()
        {
            ACTIVE.set(this);
            try{check();var value=calculation.get();check();result.complete(value);}
            catch(Throwable failure){result.completeExceptionally(failure);}
            finally{ACTIVE.remove();}
        }
    }
    /** sourceValid must read only the captured source's cancellation flag. */
    public static <T> CompletableFuture<T> submit(BooleanSupplier sourceValid,Supplier<T> calculation)
    {
        java.util.Objects.requireNonNull(sourceValid);java.util.Objects.requireNonNull(calculation);
        var work=new Work<T>(sourceValid,calculation);
        EXECUTOR.execute(work);
        return work.result;
    }
    /** Synchronous server-side geometry has no worker token and is unchanged. */
    public static void check()
    {
        var work=ACTIVE.get();
        if(work!=null&&!work.current())throw new CancellationException("Original geometry work invalidated");
    }
    static void invalidateGenerationR53()
    {
        GENERATION.incrementAndGet();
        var queued=new ArrayList<Runnable>();EXECUTOR.getQueue().drainTo(queued);
        for(var task:queued)if(task instanceof Work<?> work)
            work.result.completeExceptionally(new CancellationException("Original server geometry generation stopped"));
    }
    @SubscribeEvent public static void stopping(ServerStoppingEvent event){invalidateGenerationR53();}
    private NervGeometryWorkR53(){}
}
