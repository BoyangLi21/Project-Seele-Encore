package com.projectseele.world;

import java.io.IOException;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public final class NervSourcePreparationR53Test
{
    private static int checks;
    private static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception
    {
        var count=new AtomicInteger();var selection=new Object();
        var prepared=NervSourcePreparationR52.beforeServerLoadR53("startup",()->{count.incrementAndGet();return selection;});
        var ready=NervSourcePreparationR52.poll("startup",()->{throw new AssertionError("Live world must reuse its completed startup selection");});
        check(prepared==selection&&ready.value()==selection&&count.get()==1,"Startup and live paths share one immutable result");
        var started=new CountDownLatch(1);var release=new CountDownLatch(1);
        var pending=NervSourcePreparationR52.poll("live",()->{started.countDown();release.await();return selection;});
        check(!pending.ready()&&started.await(3,TimeUnit.SECONDS),"Live caller returns while its worker is still preparing");
        check(!NervSourcePreparationR52.poll("live",()->new Object()).ready(),"Repeated live polling never waits for unfinished source data");
        release.countDown();check(NervSourcePreparationR52.beforeServerLoadR53("live",()->new Object())==selection,"Startup join retains the existing selection identity");
        try{NervSourcePreparationR52.beforeServerLoadR53("failed",()->{throw new IOException("fixture failure");});throw new AssertionError("Failure must remain visible");}
        catch(IOException expected){check(expected.getMessage().equals("fixture failure"),"Startup preserves the original source failure");}
        check(!NervSourcePreparationR52.poll("failed",()->selection).ready(),"Live restore does not silently replace failed source data");
        check(NervSourcePreparationR52.retryFailedR52("failed"),"Explicit same-selection retry can clear the failure");
        check(NervSourcePreparationR52.beforeServerLoadR53("failed",()->selection)==selection,"Explicit retry can prepare the source again");
        System.out.println("PASS startup/live immutable resource handoff checks: "+checks);
    }
}
