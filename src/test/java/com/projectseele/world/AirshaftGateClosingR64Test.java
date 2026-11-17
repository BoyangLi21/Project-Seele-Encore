package com.projectseele.world;

/** A shaft gate keeps its chunks until it has closed, and not for ever if it never does. */
public final class AirshaftGateClosingR64Test
{
    private static int checks;
    private static void check(boolean value, String why)
    {
        checks++;
        if (!value) throw new AssertionError(why);
    }

    public static void main(String[] args)
    {
        var closing = new AirshaftGateClosingR64();
        check(!closing.keepLoaded("remote_airshaft_surface", 100), "A gate nobody used is left alone");

        // A passage holds the gate for forty ticks, then moves on.
        for (long tick = 100; tick < 140; tick++) closing.noted("remote_airshaft_surface", tick);
        check(closing.pending() == 1, "One gate is owed its closing stroke");
        // The closing stroke of 160 ticks, and well past the 100 ticks the passage's own tickets last.
        for (long tick = 140; tick < 300; tick++)
            check(closing.keepLoaded("remote_airshaft_surface", tick), "The gate stays loaded through its closing stroke, tick " + tick);
        check(!closing.keepLoaded("remote_airshaft_south", 200), "Another gate is not kept by this one");

        closing.closed("remote_airshaft_surface");
        check(!closing.keepLoaded("remote_airshaft_surface", 301) && closing.pending() == 0, "A closed gate lets its chunks go");

        // A door that cannot close is given up after the allowance, counted from its last lease.
        closing.noted("bank_1_upper_lane_2", 1000);
        closing.noted("bank_1_upper_lane_2", 1040);
        check(closing.keepLoaded("bank_1_upper_lane_2", 1040 + AirshaftGateClosingR64.ALLOWANCE_TICKS), "The allowance runs from the last lease");
        check(!closing.keepLoaded("bank_1_upper_lane_2", 1041 + AirshaftGateClosingR64.ALLOWANCE_TICKS), "After the allowance the chunks are released");
        check(closing.pending() == 0, "A gate that ran out is forgotten");

        // A world whose clock was set back must not pin the gate.
        closing.noted("remote_airshaft_south", 5000);
        check(!closing.keepLoaded("remote_airshaft_south", 4000) && closing.pending() == 0, "A clock set back releases the gate");
        System.out.println("Shaft gate closing checks passed: " + checks);
    }
}
