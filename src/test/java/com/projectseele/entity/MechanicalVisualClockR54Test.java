package com.projectseele.entity;

public final class MechanicalVisualClockR54Test
{
    public static void main(String[] args)
    {
        equal(100, MechanicalVisualClockR54.presentationTime(20, .25F, 100));
        equal(200, MechanicalVisualClockR54.presentationTime(20, 1, 200));
        equal(100, MechanicalVisualClockR54.presentationTime(20, .25F, 300));
        equal(400, MechanicalVisualClockR54.presentationTime(21, .25F, 400));
        equal(500, MechanicalVisualClockR54.presentationTime(19, .25F, 500));
        // The packet arrives at partial .7; it must start at the curve origin.
        long arrived = 150_000_000;
        equal(0, MechanicalVisualClockR54.receivedTickFraction(arrived,
                MechanicalVisualClockR54.presentationTime(30, .7F, arrived)));
        equal(.1, MechanicalVisualClockR54.receivedTickFraction(arrived,
                MechanicalVisualClockR54.presentationTime(30, .8F, arrived + 5_000_000)));
        // An entity tick boundary cannot advance a 20 ms-old packet to its endpoint.
        equal(.4, MechanicalVisualClockR54.receivedTickFraction(arrived,
                MechanicalVisualClockR54.presentationTime(31, .1F, arrived + 20_000_000)));
        equal(1, MechanicalVisualClockR54.receivedTickFraction(arrived, arrived + 500_000_000));
        equal(0, MechanicalVisualClockR54.receivedTickFraction(arrived, arrived - 1));
        var clock = new MechanicalVisualClockR54();
        clock.receive(100_000, 0);
        equal(1, clock.fraction(0));
        // The remote server stamp has no relationship to local elapsed time.
        clock.receive(100_001, 50_000_000);
        equal(0, clock.fraction(50_000_000));
        equal(.5, clock.fraction(75_000_000));
        clock.receive(100_001, 80_000_000);
        equal(1, clock.fraction(100_000_000));

        var liquid = new MechanicalVisualClockR54.Value();
        liquid.receive(44, 0);
        liquid.receive(43, 50_000_000);
        equal(43.5, liquid.sample(75_000_000));
        // A batched newer packet starts at the value already on screen.
        liquid.receive(42, 75_000_000);
        equal(43.5, liquid.sample(75_000_000));
        equal(42.75, liquid.sample(100_000_000));
        equal(42, liquid.sample(125_000_000));
        // A stalled server cannot make presentation predict drained liquid.
        equal(42, liquid.sample(5_000_000_000L));
        liquid.receive(40, 5_000_000_000L);
        equal(42, liquid.sample(5_000_000_000L));
        equal(41, liquid.sample(5_075_000_000L));
        equal(40, liquid.sample(5_150_000_000L));
        System.out.println("Mechanical visual arrival, batching, stall and endpoint checks passed");
    }

    private static void equal(double expected, double actual)
    {
        if (Math.abs(expected - actual) > 1e-9)
            throw new AssertionError("Expected " + expected + ", got " + actual);
    }
}
