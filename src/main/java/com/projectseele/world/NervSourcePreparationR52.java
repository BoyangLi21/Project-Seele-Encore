package com.projectseele.world;

import java.util.*;
import java.util.concurrent.*;

/** One bounded CPU/byte-source worker. Live callers poll without waiting.
 * Tasks must capture only immutable source data, never a Level or Entity. */
public final class NervSourcePreparationR52 {
    public record Poll<T>(T value,String hold) { public boolean ready(){return value!=null;} }
    private static final ThreadPoolExecutor WORKER=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(1),task->{var thread=new Thread(task,"R52 immutable source preparation");thread.setDaemon(true);return thread;},new ThreadPoolExecutor.AbortPolicy());
    private static final Map<String,CompletableFuture<?>> JOBS=new LinkedHashMap<>();
    private static final int MAX_SELECTIONS=8;

    /** Only an explicit same-authority retry may discard a failed result.
     * Successful selections and running immutable reads remain shared. */
    public static synchronized boolean retryFailedR52(String key)
    {
        var existing=JOBS.get(key);if(existing==null||!existing.isCompletedExceptionally())return false;
        JOBS.remove(key);return true;
    }

    public static synchronized <T> Poll<T> poll(String key,Callable<T> loader) {
        @SuppressWarnings("unchecked") var existing=(CompletableFuture<T>)JOBS.get(key);
        if(existing==null){
            if(JOBS.size()>=MAX_SELECTIONS)return new Poll<>(null,"bounded source selection capacity exhausted");
            existing=new CompletableFuture<>();var target=existing;
            try{WORKER.execute(()->{try{target.complete(Objects.requireNonNull(loader.call(),"Source preparation returned no value"));}catch(Throwable failure){target.completeExceptionally(failure);}});}
            catch(RejectedExecutionException busy){return new Poll<>(null,"source preparation worker busy");}
            JOBS.put(key,existing);
        }
        if(!existing.isDone())return new Poll<>(null,"immutable sources still preparing");
        try{return new Poll<>(existing.getNow(null),"");}
        catch(CompletionException failure){var cause=failure.getCause();return new Poll<>(null,"immutable source preparation failed: "+cause.getClass().getSimpleName()+": "+cause.getMessage());}
    }
    /** Only the ServerAboutToStart lifecycle may await this result, before
     * world simulation or entity deserialization. Live polling reuses it. */
    public static <T> T beforeServerLoadR53(String key,Callable<T> loader)throws Exception
    {
        CompletableFuture<T> future;
        synchronized(NervSourcePreparationR52.class)
        {
            Poll<T> ready=poll(key,loader);if(ready.ready())return ready.value();
            @SuppressWarnings("unchecked") var pending=(CompletableFuture<T>)JOBS.get(key);
            if(pending==null)throw new IllegalStateException(ready.hold());future=pending;
        }
        try{return future.get();}
        catch(ExecutionException failure)
        {
            var cause=failure.getCause();if(cause instanceof Exception exception)throw exception;
            if(cause instanceof Error error)throw error;throw new IllegalStateException(cause);
        }
        catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw interrupted;}
    }
    private NervSourcePreparationR52(){}
}
