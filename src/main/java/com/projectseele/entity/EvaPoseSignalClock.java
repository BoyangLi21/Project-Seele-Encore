package com.projectseele.entity;

/** Continuous packet-to-render interpolation; a new packet starts at the value actually reached. */
public final class EvaPoseSignalClock
{
    private float from,to,raw;
    private long start;
    private boolean initialized;
    public void snap(float value){from=to=raw=value;start=System.nanoTime();initialized=true;}
    public float sample(long now)
    {
        float t=Math.max(0,Math.min(1,(now-start)/50_000_000F));
        return from+(to-from)*t;
    }
    public void accept(float value,boolean cyclic,boolean restartOnBackward)
    {
        long now=System.nanoTime();
        if(!initialized||restartOnBackward&&value<raw-.05F)
        {from=to=value;raw=value;start=now;initialized=true;return;}
        float current=sample(now),target=value;
        // Accepted packet endpoints own travelled phase. Measuring from the
        // lagging rendered value reverses forward bursts crossing half a cycle.
        if(cyclic){float d=value-raw;d-=Math.round(d);target=to+d;}
        from=current;to=target;raw=value;start=now;
    }
}
