package com.projectseele.world;

import net.minecraft.world.phys.Vec3;

/** A delivery column set down at a requested place keeps its top at Root's cruise height. */
public final class NervAirDeliveryColumnR64Test
{
    private static int checks;
    private static void check(boolean value, String why)
    {
        checks++;
        if (!value) throw new AssertionError(why);
    }

    public static void main(String[] args)
    {
        // The Hakone column (landing at y 175, top at 294) asked to deliver in the city (landing at y 81).
        Vec3 toCity = new Vec3(1280.5, -94, 1509);
        Vec3 top = NervAirDeliveryTargetR53.columnShift(toCity, true);
        check(top.x == 1280.5 && top.z == 1509, "The top comes over the landing");
        check(top.y == 0, "The top keeps its cruise height over a lower landing");
        check(294 + top.y == 294, "The last cruise leg stays level at 294");
        Vec3 below = NervAirDeliveryTargetR53.columnShift(toCity, false);
        check(below.equals(toCity), "The nodes under the top keep their heights over the landing");
        check(291 + below.y == 197, "The descent from 294 to 197 happens in the column");

        // A landing higher than the template's still lifts the whole column.
        Vec3 uphill = new Vec3(-40, 60, 25);
        check(NervAirDeliveryTargetR53.columnShift(uphill, true).equals(uphill), "A higher landing raises the top with it");
        check(NervAirDeliveryTargetR53.columnShift(uphill, false).equals(uphill), "and the rest of the column");

        // The same height: nothing changes either way.
        Vec3 level = new Vec3(12, 0, -7);
        check(NervAirDeliveryTargetR53.columnShift(level, true).equals(level), "A landing at the template's height moves the top sideways only");
        System.out.println("Delivery column checks passed: " + checks);
    }
}
