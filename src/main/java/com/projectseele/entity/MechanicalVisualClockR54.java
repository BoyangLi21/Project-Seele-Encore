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

    /** Replays per-tick samples on one steady clock a little behind the newest
     *  stamp: packet timing and a slow server change the lead, not the motion. */
    public static final class TickPlayback<T>
    {
        public interface Mix<T> { T mix(T from, T to, double fraction); }
        private record Sample<T>(long tick, T value) {}

        private static final double MIN_LEAD = 1.25D, MAX_LEAD = 6.0D, GAIN = .35D, MAX_TRIM = .45D;
        private static final int STALL_TICKS = 12, RETAINED_TICKS = 48;

        private final java.util.ArrayDeque<Sample<T>> samples = new java.util.ArrayDeque<>();
        private final Mix<T> mix;
        private double head, velocity, lead = MIN_LEAD, rate = 20D, jitter;
        private long anchor, lastArrival, windowStart;
        private int windowTicks;

        public TickPlayback(Mix<T> mix) { this.mix = mix; }

        /** Pure in time between packets: every reader of a frame gets the same pose. */
        private double headAt(long now)
        {
            double at = head + velocity * Math.max(0D, (now - anchor) / 1.0E9D);
            return Math.min(at, samples.peekLast().tick());
        }

        public void receive(long tick, T value, long now)
        {
            var newest = samples.peekLast();
            if (newest == null || tick < newest.tick() - 200L)
            {
                samples.clear();
                samples.add(new Sample<>(tick, value));
                head = tick;
                velocity = 0D;
                anchor = lastArrival = windowStart = now;
                windowTicks = 0;
                return;
            }
            if (tick <= newest.tick())
            {
                if (tick == newest.tick() && !value.equals(newest.value()))
                {
                    samples.removeLast();
                    samples.add(new Sample<>(tick, value));
                }
                return;
            }
            double current = headAt(now);
            long elapsed = now - lastArrival;
            lastArrival = now;
            int ticks = (int) Math.min(100L, tick - newest.tick());
            if (ticks > STALL_TICKS || elapsed > 500_000_000L)
            {
                // A long stop is not motion: hold the last pose until just
                // before this new sample and restart the lead from there.
                samples.clear();
                samples.add(new Sample<>(tick - 1L, newest.value()));
                samples.add(new Sample<>(tick, value));
                head = tick - 1L - lead;
                velocity = rate;
                anchor = windowStart = now;
                windowTicks = 0;
                return;
            }
            windowTicks += ticks;
            if (now - windowStart >= 400_000_000L)
            {
                double measured = windowTicks / ((now - windowStart) / 1.0E9D);
                rate += (Math.max(4D, Math.min(30D, measured)) - rate) * .5D;
                windowStart = now;
                windowTicks = 0;
            }
            // Deviation from the steady arrival, in ticks. TCP batching shows
            // up here as well, so bunched samples widen the safety lead.
            double expected = ticks / rate, deviation = Math.abs(elapsed / 1.0E9D - expected) * rate;
            jitter = deviation > jitter ? jitter + (deviation - jitter) * .25D : jitter + (deviation - jitter) * .02D;
            lead = Math.max(MIN_LEAD, Math.min(MAX_LEAD, MIN_LEAD + jitter * 1.8D));
            samples.add(new Sample<>(tick, value));
            while (samples.size() > 2 && samples.peekFirst().tick() < tick - RETAINED_TICKS)
                samples.removeFirst();
            // Only a packet changes the speed, always from the drawn position.
            double error = tick - lead - current;
            head = Math.abs(error) > 40D ? tick - lead : current;
            velocity = rate * (1D + Math.max(-MAX_TRIM, Math.min(MAX_TRIM, error * GAIN)));
            anchor = now;
        }

        public T sample(long now)
        {
            if (samples.isEmpty()) throw new IllegalStateException("Playback sampled before its first sample");
            double position = headAt(now);
            Sample<T> before = null, after = null;
            for (var sample : samples)
            {
                if (sample.tick() <= position) before = sample;
                else { after = sample; break; }
            }
            if (before == null) return samples.peekFirst().value();
            if (after == null) return before.value();
            double fraction = (position - before.tick()) / (double) (after.tick() - before.tick());
            return mix.mix(before.value(), after.value(), Math.max(0D, Math.min(1D, fraction)));
        }
    }

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
