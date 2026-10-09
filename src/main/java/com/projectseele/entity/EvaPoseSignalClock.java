package com.projectseele.entity;

/** Continuous packet-to-render interpolation; a new packet starts at the value actually reached. */
public final class EvaPoseSignalClock
{
    private float from,to,raw;
    private long start,lastAccepted,window;
    private final long minimumWindow,maximumWindow;
    private boolean initialized;
    public EvaPoseSignalClock(){this(50_000_000L,100_000_000L);}
    public EvaPoseSignalClock(long fixedWindow){this(fixedWindow,fixedWindow);}
    private EvaPoseSignalClock(long minimum,long maximum)
    {if(minimum<=0||maximum<minimum)throw new IllegalArgumentException("Invalid pose interpolation window");minimumWindow=minimum;maximumWindow=maximum;window=minimum;}
    public void snap(float value){snapAt(value,System.nanoTime());}
    void snapAt(float value,long now){from=to=raw=value;start=lastAccepted=now;window=minimumWindow;initialized=true;}
    public float sample(long now)
    {
        float t=(float)Math.max(0,Math.min(1,(now-start)/(double)window));
        return from+(to-from)*t;
    }
    public void accept(float value,boolean cyclic,boolean restartOnBackward)
    {
        acceptAt(value,cyclic,restartOnBackward,System.nanoTime());
    }
    void acceptAt(float value,boolean cyclic,boolean restartOnBackward,long now)
    {
        if(!initialized||restartOnBackward&&value<raw-.05F)
        {snapAt(value,now);return;}
        // Redirect from the old window's actual value before changing cadence.
        // This never predicts beyond an accepted endpoint and stops after at
        // most two normal ticks when the packet stream goes silent.
        float current=sample(now),target=value;
        // Accepted packet endpoints own travelled phase. Measuring from the
        // lagging rendered value reverses forward bursts crossing half a cycle.
        if(cyclic){float d=value-raw;d-=Math.round(d);target=to+d;}
        window=Math.max(minimumWindow,Math.min(maximumWindow,now-lastAccepted));
        from=current;to=target;raw=value;start=lastAccepted=now;
    }
}
