package com.projectseele.world;

import java.util.UUID;

/** The MTR rider's speed excuse: only a rider, only up to two ticks at 700 km/h and a margin, in any direction. */
public final class RiderSpeedAllowanceR65Test
{
    private static int checked;

    private static void that(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
        checked++;
    }

    public static void main(String[] args)
    {
        double tick = 700 / 3.6 / 20;
        that(Math.abs(tick - 9.722) < .001, "700 km/h is 9.72 blocks a tick: " + tick);
        that(RiderSpeedAllowanceR65.mtrStep(true, tick, 0, 0), "one tick at 700 km/h is excused");
        that(RiderSpeedAllowanceR65.mtrStep(true, -2 * tick, 0, 0), "two ticks in one packet, after a stall, are excused");
        that(RiderSpeedAllowanceR65.mtrStep(true, 16, -12, 8), "a step along a climbing curve within the margin is excused");
        that(RiderSpeedAllowanceR65.mtrStep(true, 0, 24, 0), "the margin itself is excused");
        that(!RiderSpeedAllowanceR65.mtrStep(true, 0, 24.01, 0), "past the margin is not");
        that(!RiderSpeedAllowanceR65.mtrStep(true, 514, 12, -1654), "a jump across the map is never excused");
        that(!RiderSpeedAllowanceR65.mtrStep(false, tick, 0, 0), "nobody but a rider is excused");
        that(!RiderSpeedAllowanceR65.mtrStep(false, 0, 0, 0), "not even a rider's standing still, if not riding");
        // Without MTR on the classpath (as in this check) nobody is riding, so nothing is excused.
        that(!RiderSpeedAllowanceR65.ridingMtr(UUID.randomUUID()), "without MTR nobody rides");
        that(!RiderSpeedAllowanceR65.ridingMtr(UUID.randomUUID()), "and the failed lookup is not retried into an error");
        System.out.println("RiderSpeedAllowanceR65Test: " + checked + " checks passed");
    }
}
