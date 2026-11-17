package com.projectseele.client.cockpit;

import org.joml.Vector3f;

/**
 * The seated pilot stays inside the plug: every corner of the posed figure lies within the shell's least inner
 * radius and between the cabin's two bulkheads, and above the seat's floor. (Up to R63 the feet were 0.35 blocks
 * outside the shell.)
 */
public final class PilotSeatPoseR64Test
{
    /** The capsule's eye marker (EntryPlugKinematics.PILOT_EYE_P: model 0, 0.8, 34.5 at 0.2 blocks a unit). */
    private static final float EYE_Y = .16F, EYE_Z = 6.9F;
    /**
     * The plug, in blocks, read off the high-detail local mesh: the shell's least inner radius over the cabin, the
     * bulkheads before and behind the seat, and the cabin's floor. The public box model is wider than all of these.
     */
    private static final float RADIUS = .66F, TIP_BULKHEAD = 3.03F, TAIL_BULKHEAD = 7.32F, FLOOR = -.57F;

    private static void check(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args)
    {
        float most = 0, low = 9, high = -9, front = 99, back = -99, wide = 0;
        for (Vector3f p : PilotSeatPoseR64.corners(0, EYE_Y, EYE_Z))
        {
            most = Math.max(most, (float) Math.hypot(p.x, p.y));
            low = Math.min(low, p.y); high = Math.max(high, p.y);
            front = Math.min(front, p.z); back = Math.max(back, p.z);
            wide = Math.max(wide, Math.abs(p.x));
        }
        System.out.printf("seated pilot: furthest from the axis %.3f (shell %.2f), y %.3f..%.3f, z %.3f..%.3f, half width %.3f%n",
                most, RADIUS, low, high, front, back, wide);
        check(most <= RADIUS - .03F, "the figure reaches " + most + " blocks from the plug's axis; the shell's inside is at " + RADIUS);
        check(low >= FLOOR, "the figure reaches below the cabin floor: " + low);
        check(front >= TIP_BULKHEAD + .1F && back <= TAIL_BULKHEAD - .05F, "the figure reaches a bulkhead: z " + front + ".." + back);
        // The head stays where the capsule's eye marker is: the first-person eye is inside the drawn head.
        Vector3f hip = PilotSeatPoseR64.hip(0, EYE_Y, EYE_Z);
        check(hip.y < EYE_Y && hip.z < EYE_Z, "the hips lie below and tipwards of the eye");
        // The old pose, for the record: a straight figure leant 51.3 degrees about its middle at the seat marker.
        double lean = Math.atan2(3.5, 2.8), feetY = -.4 - .9 * Math.cos(lean), feetZ = 6.2 - .9 * Math.sin(lean);
        check(Math.hypot(.25, feetY - .117 * Math.sin(lean)) > .8, "the old pose's feet were outside the shell (the fault this replaces)");
        System.out.printf("old pose: feet centre at y %.3f z %.3f, sole corner %.3f from the axis (shell outside 0.80)%n",
                feetY, feetZ, Math.hypot(.25, feetY - .117 * Math.sin(lean)));
    }
}
