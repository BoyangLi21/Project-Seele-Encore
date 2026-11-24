package com.projectseele.world;

import com.projectseele.world.AirshaftHoldR65.Step;

/** Run with AllChecks: what the transport plant does with a shaft gate while the phone holds the shaft open (R65). */
public final class AirshaftHoldR65Test
{
    private static int checks;
    private static void check(boolean value, String why)
    {
        checks++;
        if (!value) throw new AssertionError(why);
    }

    public static void main(String[] args)
    {
        String surface = "remote_airshaft_surface", south = "remote_airshaft_south", silo = "bank_3_surface_lane_1";
        check(AirshaftHoldR65.shaftGate(surface) && AirshaftHoldR65.shaftGate(south), "Both doors of the shaft are its gates");
        check(!AirshaftHoldR65.shaftGate(silo), "A launch silo's door is not");

        var hold = new AirshaftHoldR65();
        // No order: every idle gate takes its closing stroke, as before R65.
        check(hold.step(surface, false, false, true, 100) == Step.CLOSE, "Without the order an idle shaft gate closes");
        check(hold.step(silo, false, false, true, 100) == Step.CLOSE, "So does an idle silo door");
        check(hold.step(surface, false, true, true, 100) == Step.LEAVE, "A passage keeps its gate");
        check(hold.step(surface, false, false, false, 100) == Step.LEAVE, "A gate somebody else holds is left alone");

        // The order: the shaft's gates are driven open, a silo door still closes.
        hold.ordered();
        check(hold.step(surface, true, false, true, 200) == Step.OPEN, "On the order the surface gate is driven open");
        check(hold.step(south, true, false, true, 200) == Step.OPEN, "And the underground gate");
        check(hold.step(silo, true, false, true, 200) == Step.CLOSE, "The order does not reach a silo door");
        check(hold.step(surface, true, false, true, 360) == Step.OPEN, "Still driven during the stroke");
        hold.opened(surface);
        check(hold.seenOpen(surface) && !hold.seenOpen(south), "Each gate reports for itself");
        check(hold.step(surface, true, false, true, 361) == Step.REST, "A gate seen open is left open with nothing to load");
        check(hold.step(south, true, false, true, 361) == Step.OPEN, "The other one is still on its way");

        // A passage through the held shaft: left to the passage, looked at again behind it, never closed.
        check(hold.step(surface, true, true, true, 400) == Step.LEAVE, "A passage through the held shaft keeps its gate");
        check(hold.step(surface, true, false, true, 600) == Step.OPEN, "Behind the passage the gate is looked at again");
        hold.opened(surface);
        check(hold.step(surface, true, false, true, 601) == Step.REST, "And rests open again");

        // A door that cannot be found or cannot move does not keep its chunks for ever.
        check(hold.step(south, true, false, true, 200 + AirshaftHoldR65.ALLOWANCE_TICKS) == Step.OPEN, "Inside the allowance the gate is still tried");
        check(hold.step(south, true, false, true, 201 + AirshaftHoldR65.ALLOWANCE_TICKS) == Step.REST, "Past it the chunks are let go");
        check(hold.step(south, true, false, true, 100) == Step.REST, "A clock that ran backwards is not trusted either");

        // The order taken back: both gates go to the closing stroke at once; a new order starts afresh.
        hold.ordered();
        check(hold.step(surface, false, false, true, 5000) == Step.CLOSE, "With the order taken back the surface gate closes");
        check(hold.step(south, false, false, true, 5000) == Step.CLOSE, "And the underground gate");
        check(hold.step(south, true, false, true, 6000) == Step.OPEN, "A new order tries a gate that ran out of allowance again");
        System.out.println("AirshaftHoldR65Test: " + checks + " checks passed");
    }
}
