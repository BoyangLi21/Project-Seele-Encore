package com.projectseele.entity;

/** Delayed frames must not reverse several forward packets received together. */
public final class EvaPoseSignalClockTest
{
    public static void main(String[] args)
    {
        var clock=new EvaPoseSignalClock();clock.snap(0);
        clock.accept(.25F,true,false);clock.accept(.5F,true,false);clock.accept(.75F,true,false);
        float forward=clock.sample(System.nanoTime()+60_000_000L);
        if(Math.abs(forward-.75F)>.001F)throw new AssertionError("Forward packet burst reversed its cycle: "+forward);
        clock.accept(0F,true,false);clock.accept(.25F,true,false);
        float wrapped=clock.sample(System.nanoTime()+60_000_000L);
        if(Math.abs(wrapped-1.25F)>.001F)throw new AssertionError("Cycle seam lost accepted travel: "+wrapped);
        clock.accept(0F,true,false);clock.accept(.75F,true,false);
        float reverse=clock.sample(System.nanoTime()+60_000_000L);
        if(Math.abs(reverse-.75F)>.001F)throw new AssertionError("Backward packets cannot reverse: "+reverse);
        System.out.println("Pose clock: delayed forward bursts, cycle seam and deliberate reversal PASS");
    }
}
