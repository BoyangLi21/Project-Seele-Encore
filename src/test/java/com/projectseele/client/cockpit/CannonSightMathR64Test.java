package com.projectseele.client.cockpit;

/**
 * The positron cannon's sight: a direction is put on the picture where it is seen, the field of view narrows with the
 * visor and then with the charge, and the shot is on only when the barrel has settled, the charge is full and the
 * bore's ray is through an open core.
 */
public final class CannonSightMathR64Test
{
    private static int checked;

    private static void that(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
        checked++;
    }

    private static boolean near(double a, double b, double within) { return Math.abs(a - b) <= within; }

    public static void main(String[] args)
    {
        double[] forward = {0, 0, 1}, up = {0, 1, 0}, right = {-1, 0, 0};

        // Straight ahead is the middle of the picture, at any field of view.
        double[] at = CannonSightMathR64.onPicture(0, 0, 50, forward, up, right, 70);
        that(near(at[0], 0, 1e-9) && near(at[1], 0, 1e-9), "straight ahead is the middle: " + at[0] + ", " + at[1]);

        // Half the field of view upwards is the picture's upper edge: one half height above the middle.
        double half = Math.toRadians(35);
        at = CannonSightMathR64.onPicture(0, Math.sin(half), Math.cos(half), forward, up, right, 70);
        that(near(at[0], 0, 1e-9) && near(at[1], -1, 1e-9), "half the field upwards is the upper edge: " + at[1]);

        // To the right of the view is to the right on the picture, and the narrower field throws it further out.
        double[] wide = CannonSightMathR64.onPicture(-1, 0, 20, forward, up, right, 70);
        double[] narrow = CannonSightMathR64.onPicture(-1, 0, 20, forward, up, right, 70 * .16);
        that(wide[0] > 0 && narrow[0] > wide[0] * 5, "the narrow field magnifies: " + wide[0] + " to " + narrow[0]);

        // Nothing behind the eye is drawn.
        that(CannonSightMathR64.onPicture(0, 0, -5, forward, up, right, 70) == null, "behind the eye there is no place on the picture");

        // Angles.
        that(near(CannonSightMathR64.apart(0, 0, 1, 0, 0, 3), 0, 1e-6), "the same direction is no angle apart");
        that(near(CannonSightMathR64.apart(0, 0, 1, 1, 0, 0), 90, 1e-6), "a right angle");
        that(near(CannonSightMathR64.apart(0, 0, 1, 0, Math.tan(Math.toRadians(8)), 1), 8, 1e-6), "eight degrees up");
        that(CannonSightMathR64.apart(0, 0, 0, 0, 0, 1) == 180, "no direction counts as wholly off");

        // How far a ray passes from a point.
        that(near(CannonSightMathR64.missBy(0, 0, 0, 0, 0, 1, 0, 0, 80), 0, 1e-9), "through the point");
        that(near(CannonSightMathR64.missBy(0, 0, 0, 0, 0, 1, 3, 4, 80), 5, 1e-9), "five to the side");
        that(near(CannonSightMathR64.missBy(0, 0, 0, 0, 0, 1, 0, 3, -4), 5, 1e-9), "a point behind the muzzle is measured from the muzzle");

        // The field of view: plain with the visor up, .35 with it down, .16 with the charge full, never widening on the way.
        that(CannonSightMathR64.field(0, 0) == 1 && CannonSightMathR64.field(0, 1) == 1, "the visor up leaves the field alone");
        that(near(CannonSightMathR64.field(1, 0), .35, 1e-6), "the visor down: " + CannonSightMathR64.field(1, 0));
        that(near(CannonSightMathR64.field(1, 1), .16, 1e-6), "the charge full: " + CannonSightMathR64.field(1, 1));
        float before = 1;
        for (int i = 0; i <= 100; i++)
        {
            float now = CannonSightMathR64.field(Math.min(1, i / 30F), Math.max(0, (i - 30) / 70F));
            that(now <= before + 1e-6, "the field never widens as the visor comes down and the charge rises: step " + i);
            before = now;
        }
        that(near(CannonSightMathR64.field(2, 3), .16, 1e-6) && CannonSightMathR64.field(-1, -1) == 1, "out of range is held to the range");

        // The shot is on only with all three.
        that(CannonSightMathR64.on(.1, 1, true, true, true, true), "settled, full, through the open core");
        that(!CannonSightMathR64.on(2, 1, true, true, true, true), "the barrel is still moving");
        that(!CannonSightMathR64.on(.1, .98F, true, true, true, true), "the charge is not full");
        that(!CannonSightMathR64.on(.1, 1, true, false, true, true), "the core is shut behind the field");
        that(!CannonSightMathR64.on(.1, 1, true, true, false, true), "the ray passes the core by");
        that(CannonSightMathR64.on(.1, 1, false, false, false, true), "no core in play: the ray reaches something");
        that(!CannonSightMathR64.on(.1, 1, false, false, false, false), "no core in play and nothing reached");

        // The closing tone follows the furthest of the three.
        that(CannonSightMathR64.closing(.1, 1, true, 0, 4.25, true) == 1, "all together");
        that(near(CannonSightMathR64.closing(.1, .5F, true, 0, 4.25, true), .5, 1e-6), "held back by the charge");
        that(CannonSightMathR64.closing(12, 1, true, 0, 4.25, true) == 0, "held back by the barrel");
        float nearCore = CannonSightMathR64.closing(.1, 1, true, 6, 4.25, true), farCore = CannonSightMathR64.closing(.1, 1, true, 15, 4.25, true);
        that(nearCore > farCore && nearCore < 1 && CannonSightMathR64.closing(.1, 1, true, 40, 4.25, true) == 0, "nearer the core is nearer on: " + nearCore + ", " + farCore);

        System.out.println("CannonSightMathR64Test: " + checked + " checks passed.");
    }
}
