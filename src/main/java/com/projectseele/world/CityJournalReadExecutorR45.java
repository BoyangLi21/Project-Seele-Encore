package com.projectseele.world;

import java.util.Set;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;

/** One bounded daemon reader per city context; no disk work runs on a caller or the common pool. */
public final class CityJournalReadExecutorR45 implements AutoCloseable
{
    private static final AtomicInteger IDS = new AtomicInteger();
    private final String threadName = "seele-city-journal-reader-" + IDS.incrementAndGet();
    private final Set<CompletableFuture<?>> pending = ConcurrentHashMap.newKeySet();
    private final ThreadPoolExecutor executor = new ThreadPoolExecutor(1, 1, 0, TimeUnit.MILLISECONDS,
            new ArrayBlockingQueue<>(1), task ->
            {
                Thread thread = new Thread(task, threadName);
                thread.setDaemon(true); thread.setPriority(Thread.NORM_PRIORITY - 1); return thread;
            }, new ThreadPoolExecutor.AbortPolicy());
    private boolean closed;

    public synchronized <T> CompletableFuture<T> submit(Supplier<T> supplier)
    {
        CompletableFuture<T> result = new CompletableFuture<>();
        if (closed)
        {
            result.completeExceptionally(new IllegalStateException("City journal reader is closed")); return result;
        }
        pending.add(result); result.whenComplete((value, failure) -> pending.remove(result));
        try
        {
            executor.execute(() ->
            {
                if (result.isDone()) return;
                try { result.complete(supplier.get()); }
                catch (Throwable failure) { result.completeExceptionally(failure); }
            });
        }
        catch (java.util.concurrent.RejectedExecutionException failure) { result.completeExceptionally(failure); }
        return result;
    }

    public String threadName() { return threadName; }
    public int queuedTasks() { return executor.getQueue().size(); }
    public int activeTasks() { return executor.getActiveCount(); }
    public int pendingTasks() { return pending.size(); }
    public boolean isClosed() { return executor.isShutdown(); }
    public boolean isTerminated() { return executor.isTerminated(); }

    @Override
    public synchronized void close()
    {
        if (closed) return;
        closed = true;
        for (CompletableFuture<?> future : pending) future.cancel(false);
        executor.shutdownNow(); pending.clear();
    }
}
