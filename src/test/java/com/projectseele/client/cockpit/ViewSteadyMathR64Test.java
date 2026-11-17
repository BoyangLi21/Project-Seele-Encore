package com.projectseele.client.cockpit;

/**
 * The steadier view does what it says: a still head leaves the eye on it, a walk's bob reaches the eye much
 * reduced, the eye stays within its reach of the head whatever the head does (least of all under and behind it), a
 * change of posture is followed, a sight takes the steadying away entirely, and the frame rate does not matter.
 */
public final class ViewSteadyMathR64Test
{
    private static void check(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
    }

    /** The eye's and the head's swing (half of peak to peak) over the last two seconds of a bob on one axis. */
    private static double[] bob(int axis, double hertz, double amplitude, double fps)
    {
        ViewSteadyMathR64 m = new ViewSteadyMathR64();
        m.reset(0, 50, 2);
        double dt = 1 / fps, low = 1e9, high = -1e9;
        for (int i = 1; i <= fps * 6; i++)
        {
            double t = i * dt, swing = amplitude * Math.sin(2 * Math.PI * hertz * t);
            double hx = axis == 0 ? swing : 0, hy = 50 + (axis == 1 ? swing : 0), hz = 2 + (axis == 2 ? swing : 0);
            m.step(hx, hy, hz, dt, false, 1);
            double eye = axis == 0 ? hx + m.offsetX : axis == 1 ? hy + m.offsetY - 50 : hz + m.offsetZ - 2;
            if (t > 4) { low = Math.min(low, eye); high = Math.max(high, eye); }
        }
        return new double[]{(high - low) / 2, amplitude};
    }

    public static void main(String[] args)
    {
        // A still head: the eye is on it.
        ViewSteadyMathR64 m = new ViewSteadyMathR64();
        m.reset(1, 50, 2);
        for (int i = 0; i < 300; i++) m.step(1, 50, 2, 1 / 60.0, false, 1);
        check(Math.abs(m.offsetX) + Math.abs(m.offsetY) + Math.abs(m.offsetZ) < 1e-9, "a still head leaves the eye on it");

        // The walk and the run, as measured in the game (2026-11-17): about 1.2 Hz and 1.7 blocks up and down, 2 to
        // the sides at a walk; 2.4 Hz and 4.4 to the sides at a run.
        double[] up = bob(1, 1.2, 1.7, 60), side = bob(0, 1.2, 2.0, 60), run = bob(0, 2.4, 4.4, 60);
        System.out.printf("walk bob up: head %.2f, eye %.2f (%.0f%% less); to the side: head %.2f, eye %.2f (%.0f%% less); run to the side: head %.2f, eye %.2f (%.0f%% less)%n",
                up[1], up[0], 100 - 100 * up[0] / up[1], side[1], side[0], 100 - 100 * side[0] / side[1], run[1], run[0], 100 - 100 * run[0] / run[1]);
        check(up[0] < up[1] * .45, "the walk's bob up and down is more than halved: " + up[0]);
        check(side[0] < side[1] * .35, "the walk's sway is cut to a third: " + side[0]);
        check(run[0] < run[1] * .45, "the run's sway is more than halved: " + run[0]);
        check(up[0] > up[1] * .15, "the walk is still felt: " + up[0]);

        // Whatever the head does, the eye stays within its reach of it, and nearest under and behind it.
        java.util.Random random = new java.util.Random(64);
        m.reset(0, 50, 2);
        double hx = 0, hy = 50, hz = 2, most = 0;
        for (int i = 0; i < 20000; i++)
        {
            if (random.nextInt(40) == 0) { hx += random.nextGaussian() * 9; hy += random.nextGaussian() * 9; hz += random.nextGaussian() * 9; }
            m.step(hx, hy, hz, 1 / 60.0, random.nextInt(200) < 30, 1);
            check(Math.abs(m.offsetX) <= ViewSteadyMathR64.REACH_SIDE + 1e-9, "to the side within reach");
            check(m.offsetY <= ViewSteadyMathR64.REACH_OVER + 1e-9 && m.offsetY >= -ViewSteadyMathR64.REACH_UNDER - 1e-9, "over and under within reach: " + m.offsetY);
            check(m.offsetZ <= ViewSteadyMathR64.REACH_AHEAD + 1e-9 && m.offsetZ >= -ViewSteadyMathR64.REACH_BEHIND - 1e-9, "ahead and behind within reach: " + m.offsetZ);
            most = Math.max(most, Math.max(-m.offsetY, -m.offsetZ));
        }
        check(most > 1.2, "the reach under and behind was reached in the trial: " + most);

        // A change of posture (the head ten blocks lower, as in a crouch) is followed: within a quarter of a block
        // after a second and a half.
        m.reset(0, 50, 2);
        for (int i = 0; i < 90; i++) m.step(0, 40, 2, 1 / 60.0, false, 1);
        check(Math.abs(m.offsetY) < .25, "a crouch is followed within a second and a half: " + m.offsetY);

        // Behind a sight the eye is the head's exactly, within half a second of raising it.
        m.reset(0, 50, 2);
        for (int i = 0; i < 120; i++) m.step(Math.sin(i * .2) * 2, 50, 2, 1 / 60.0, false, 1);
        check(Math.abs(m.offsetX) > .2, "steadying before the sight is raised");
        for (int i = 120; i < 150; i++) m.step(Math.sin(i * .2) * 2, 50, 2, 1 / 60.0, false, 0);
        check(m.offsetX == 0 && m.offsetY == 0 && m.offsetZ == 0, "a sight takes the steadying away entirely");

        // The frame rate does not change what the eye does.
        double slow = bob(1, 1.2, 1.7, 30)[0], fast = bob(1, 1.2, 1.7, 144)[0];
        check(Math.abs(slow - fast) < .05, "the same at 30 and at 144 frames a second: " + slow + " and " + fast);
    }
}
