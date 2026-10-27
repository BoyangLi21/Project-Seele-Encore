package com.projectseele.world;

import java.util.ArrayList;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

public final class NervGeometryWorkR53Test
{
    private static int checks;
    private static void check(boolean value,String reason){checks++;if(!value)throw new AssertionError(reason);}
    private static void await(CountDownLatch latch)
    {try{if(!latch.await(5,TimeUnit.SECONDS))throw new AssertionError("Worker rendezvous expired");}catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new AssertionError(interrupted);}}
    private static boolean failed(CompletableFuture<?> future,Class<? extends Throwable> expected)throws Exception
    {try{future.get(5,TimeUnit.SECONDS);return false;}catch(CancellationException cancelled){return expected.isInstance(cancelled);}catch(ExecutionException failed){return expected.isInstance(failed.getCause());}}
    public static void main(String[] args)throws Exception
    {
        NervGeometryWorkR53.check();
        check(NervGeometryWorkR53.submit(()->true,()->7).get(5,TimeUnit.SECONDS)==7,"Current pure source result completes");
        check(failed(NervGeometryWorkR53.submit(()->false,()->{throw new AssertionError("Invalid source was evaluated");}),CancellationException.class),"Invalid source is rejected before evaluation");
        var live=new AtomicBoolean(true);var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        var changed=NervGeometryWorkR53.submit(live::get,()->{entered.countDown();await(release);NervGeometryWorkR53.check();return 8;});
        await(entered);live.set(false);release.countDown();check(failed(changed,CancellationException.class),"Captured replacement cancels a running computation");
        var busy=new CountDownLatch(2);var finish=new CountDownLatch(1);var running=new ArrayList<CompletableFuture<Integer>>();
        for(int i=0;i<2;i++)running.add(NervGeometryWorkR53.submit(()->true,()->{busy.countDown();await(finish);NervGeometryWorkR53.check();return 9;}));
        await(busy);var queued=new ArrayList<CompletableFuture<Integer>>();
        for(int i=0;i<8;i++)queued.add(NervGeometryWorkR53.submit(()->true,()->10));
        boolean rejected=false;
        try{NervGeometryWorkR53.submit(()->true,()->11);}catch(RejectedExecutionException full){rejected=true;}
        check(rejected,"A full queue throws for transient pending instead of caching a source failure");
        NervGeometryWorkR53.invalidateGenerationR53();finish.countDown();
        for(var task:running)check(failed(task,CancellationException.class),"Server stopping invalidates the running generation");
        for(var task:queued)check(failed(task,CancellationException.class),"Server stopping drains queued work without evaluating it");
        NervGeometryWorkR53.check();
        check(NervGeometryWorkR53.submit(()->true,()->12).get(5,TimeUnit.SECONDS)==12,"A fresh generation runs after stopping without stale thread-local state");
        System.out.println("R53 bounded geometry worker PASS checks="+checks+"; no world or entity access");
    }
}
