package com.projectseele.client.cockpit;

/**
 * R64: the arithmetic of the pilot's steadier view (PilotViewSteadyR64), with no game classes so that it can be
 * checked by itself (ViewSteadyMathR64Test).
 * <p>
 * Everything is in the body's own frame: to its right, up, forward, in blocks, measured from the Unit's feet. The
 * head's optical point comes in every drawn frame; what comes out is how far from the head the eye stands.
 */
public final class ViewSteadyMathR64
{
    /** How fast the eye follows where the head settles (1/seconds): a posture change is taken in about half a second. */
    public static final double FOLLOW = 5.0;
    /** The share of the head's quick movement the eye takes: sideways, up and down, fore and aft. */
    public static final double SHARE_SIDE = .18, SHARE_UP = .30, SHARE_FORE = .18;
    /** In the air and for half a second after a landing: the tuck of the jump and the sink of the landing are the pilot's too. */
    public static final double SHARE_AIR = .50, AIR_IN = .12, AIR_OUT = .55;
    /**
     * The most the eye is ever away from the head (blocks): to either side and before it; above it, where there is
     * nothing of the Unit (a landing folds the body 19 blocks down in a fifth of a second, and the eye is let down
     * after it); and under it and behind it, towards the shoulders and the back. In the pilot's view the Unit's head,
     * neck, trunk and pylons are not drawn at all, so none of this can show the body from inside; the reach is what
     * keeps the arms where a pilot expects them. A blow swings the head a dozen blocks in a fifth of a second: with
     * one small reach all round (2.6, the first trial) the eye was dragged along with most of that.
     */
    public static final double REACH_SIDE = 4.5, REACH_OVER = 9.0, REACH_AHEAD = 4.5, REACH_UNDER = 3.0, REACH_BEHIND = 3.5;
    /** Seconds over which the steadying comes in and goes out (a sight raised or lowered). */
    public static final double BLEND = .10;

    private double x, y, z, vx, vy, vz, air, strength;
    /** The eye against the head after the last step: to the right, up, forward. */
    public double offsetX, offsetY, offsetZ;

    /** The head is here and has been: nothing to follow yet. */
    public void reset(double headX, double headY, double headZ)
    {
        x = headX; y = headY; z = headZ;
        vx = vy = vz = 0; air = 0; strength = 0;
        offsetX = offsetY = offsetZ = 0;
    }

    /**
     * One drawn frame.
     *
     * @param dt       seconds since the last
     * @param airborne the Unit is off the ground (a jump or a fall, not a step)
     * @param wanted   how much steadying is asked for, 0..1: the setting, or 0 behind a sight
     */
    public void step(double headX, double headY, double headZ, double dt, boolean airborne, double wanted)
    {
        air += ((airborne ? 1 : 0) - air) * (1 - Math.exp(-dt / (airborne ? AIR_IN : AIR_OUT)));
        strength += (wanted - strength) * (1 - Math.exp(-dt / BLEND));
        // A sight is an exact ray: once it is up the eye is the head's, to the last fraction.
        if (wanted <= 0 && strength < .02) strength = 0;
        // Where the head settles: a spring without overshoot, each axis by itself.
        double decay = Math.exp(-FOLLOW * dt), step;
        step = (vx + FOLLOW * (x - headX)) * dt; vx = (vx - FOLLOW * step) * decay; x = headX + (x - headX + step) * decay;
        step = (vy + FOLLOW * (y - headY)) * dt; vy = (vy - FOLLOW * step) * decay; y = headY + (y - headY + step) * decay;
        step = (vz + FOLLOW * (z - headZ)) * dt; vz = (vz - FOLLOW * step) * decay; z = headZ + (z - headZ + step) * decay;
        // The eye's distance from the head: what is left of the difference, bent over towards the reach.
        double ox = (x - headX) * (1 - lerp(air, SHARE_SIDE, SHARE_AIR)), oy = (y - headY) * (1 - lerp(air, SHARE_UP, SHARE_AIR)),
                oz = (z - headZ) * (1 - lerp(air, SHARE_FORE, SHARE_AIR));
        offsetX = bend(ox, REACH_SIDE) * strength;
        offsetY = bend(oy, oy > 0 ? REACH_OVER : REACH_UNDER) * strength;
        offsetZ = bend(oz, oz > 0 ? REACH_AHEAD : REACH_BEHIND) * strength;
    }

    private static double lerp(double t, double from, double to)
    {
        return from + (to - from) * t;
    }

    /** Plain up to half the reach, bent over towards the reach past it. */
    static double bend(double value, double reach)
    {
        double plain = reach * .5, size = Math.abs(value);
        return size <= plain ? value : Math.copySign(plain + (reach - plain) * Math.tanh((size - plain) / (reach - plain)), value);
    }
}
