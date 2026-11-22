package com.projectseele.client.sound;

import java.util.Arrays;
import java.util.function.IntUnaryOperator;

/** Run with AllChecks. */
public final class VenueReverbR61Test
{
    private static final int RANGE = 128;

    /** Same x, y, z nesting as the probe, so index maps to direction. */
    private static float[] rays(IntUnaryOperator length)
    {
        var values = new float[26];
        int index = 0;
        for (int x = -1; x <= 1; x++)
        {
            for (int y = -1; y <= 1; y++)
            {
                for (int z = -1; z <= 1; z++)
                {
                    if (x == 0 && y == 0 && z == 0) continue;
                    values[index++] = length.applyAsInt(x == 0 && z == 0 ? 100 + y : y == 0 ? 10 : 20);
                }
            }
        }
        return values;
    }

    private static void check(VenueReverbR61.Venue expected, VenueReverbR61.Venue actual, String name)
    {
        if (expected != actual) throw new AssertionError(name + ": expected " + expected + " but got " + actual);
    }

    public static void main(String[] args)
    {
        float[] open = new float[26];
        Arrays.fill(open, RANGE);
        check(VenueReverbR61.Venue.OPEN, VenueReverbR61.classify(false, true, open, RANGE), "street");
        check(VenueReverbR61.Venue.CAVERN, VenueReverbR61.classify(true, false, open, RANGE), "cavern floor");

        // The ray index is only used through the kind code passed to the lambda.
        float[] shaft = rays(kind -> kind >= 99 ? RANGE : 12);
        check(VenueReverbR61.Venue.SHAFT, VenueReverbR61.classify(true, false, shaft, RANGE), "launch shaft");

        float[] hangar = rays(kind -> 45);
        check(VenueReverbR61.Venue.HANGAR, VenueReverbR61.classify(true, false, hangar, RANGE), "hangar bay");

        float[] corridor = rays(kind -> 6);
        check(VenueReverbR61.Venue.ROOM, VenueReverbR61.classify(true, false, corridor, RANGE), "corridor");

        // A walled street under open sky is still open air, not a room.
        float[] street = rays(kind -> kind >= 99 ? RANGE : kind == 10 ? 30 : RANGE);
        check(VenueReverbR61.Venue.OPEN, VenueReverbR61.classify(false, true, street, RANGE), "walled street");

        // R64: a hangar bay's PA is at least the hangar wherever the listener stands; only the cavern is bigger.
        for (var listener : VenueReverbR61.Venue.values())
            check(listener == VenueReverbR61.Venue.CAVERN ? VenueReverbR61.Venue.CAVERN : VenueReverbR61.Venue.HANGAR,
                    VenueReverbR61.bayVenue(listener), "hangar bay PA heard from " + listener);

        // R65: the dry alarm take sounds like the listener's space; under open sky it is the city's far answer.
        for (var listener : VenueReverbR61.Venue.values())
            check(listener == VenueReverbR61.Venue.OPEN ? VenueReverbR61.Venue.CITY_PA : listener,
                    VenueReverbR61.alarmVenue(listener), "alarm heard from " + listener);

        // Every preset must stay inside OpenAL's EAX reverb ranges, or the effect is rejected and the send goes silent.
        for (var v : VenueReverbR61.Venue.values())
        {
            range(v, "density", v.density, 0, 1);
            range(v, "diffusion", v.diffusion, 0, 1);
            range(v, "gain", v.gain, 0, 1);
            range(v, "gainHf", v.gainHf, 0, 1);
            range(v, "decay", v.decay, .1F, 20);
            range(v, "decayHf", v.decayHf, .1F, 2);
            range(v, "reflections", v.reflections, 0, 3.16F);
            range(v, "reflectionsDelay", v.reflectionsDelay, 0, .3F);
            range(v, "late", v.late, 0, 10);
            range(v, "lateDelay", v.lateDelay, 0, .1F);
            range(v, "echoTime", v.echoTime, .075F, .25F);
            range(v, "echoDepth", v.echoDepth, 0, 1);
        }
    }

    private static void range(VenueReverbR61.Venue venue, String name, float value, float low, float high)
    {
        if (value < low || value > high) throw new AssertionError(venue + "." + name + " = " + value + " outside " + low + ".." + high);
    }

    private VenueReverbR61Test() { }
}
