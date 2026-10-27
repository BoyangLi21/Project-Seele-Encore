package com.projectseele.entity;

/** Local presentation time for received mechanical samples; never predicts a server target. */
public final class MechanicalVisualClockR54
{
    private record FrameKey(long tick, int partial) {}
    private static final java.util.Map<FrameKey,Long> FRAME_TIMES = new java.util.LinkedHashMap<>();
    private static long latestFrameTick = Long.MIN_VALUE;

    /** All mechanical consumers of one partial frame use one wall-clock sample. */
    public static long presentationTime(long tick, float partial)
    { return presentationTime(tick, partial, System.nanoTime()); }

    static synchronized long presentationTime(long tick, float partial, long now)
    {
        if (tick < latestFrameTick) FRAME_TIMES.clear();
        latestFrameTick = tick;
        var key = new FrameKey(tick, Float.floatToIntBits(partial));
        var known = FRAME_TIMES.get(key);
        if (known != null) return known;
        FRAME_TIMES.put(key, now);
        if (FRAME_TIMES.size() > 64) FRAME_TIMES.remove(FRAME_TIMES.keySet().iterator().next());
        return now;
    }

    private static final long MIN_SPAN = 50_000_000L;
    private static final long MAX_SPAN = 150_000_000L;

    /** A received one-tick curve starts when it arrives, not at the render tick's partial. */
    public static double receivedTickFraction(long received, long now)
    { return Math.max(0, Math.min(1, (now - received) / (double)MIN_SPAN)); }

    private boolean initialized;
    private long stamp, received, span = MIN_SPAN;

    public void receive(long next, long now)
    {
        if (initialized && stamp == next) return;
        if (!initialized)
        {
            initialized = true;
            received = now;
            span = 0;
        }
        else
        {
            span = Math.max(MIN_SPAN, Math.min(MAX_SPAN, now - received));
            received = now;
        }
        stamp = next;
    }

    public double fraction(long now)
    { return span == 0 ? 1 : Math.max(0, Math.min(1, (now - received) / (double)span)); }

    /** Retarget from the currently drawn value when packets are batched or delayed. */
    public static final class Value
    {
        private final MechanicalVisualClockR54 clock = new MechanicalVisualClockR54();
        private boolean initialized;
        private double from, to;

        public void receive(double target, long now)
        {
            if (initialized && Double.compare(to, target) == 0) return;
            from = initialized ? sample(now) : target;
            to = target;
            clock.receive(Double.doubleToLongBits(target), now);
            initialized = true;
        }

        public double sample(long now)
        { return from + (to - from) * clock.fraction(now); }
    }
}
