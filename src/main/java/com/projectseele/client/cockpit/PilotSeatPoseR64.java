package com.projectseele.client.cockpit;

import org.joml.Matrix4f;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.List;

/**
 * R64: how the pilot lies in the plug's seat.
 * <p>
 * Up to R63 the pilot was the standing figure leant back 51 degrees about its middle: 1.8 blocks of straight body
 * across a plug 1.6 blocks wide, so the feet came out through the plug's underside (seen in the hangar while the
 * crane carries the plug). The original has the pilot half lying in a seat that runs along the plug, legs towards
 * the insertion tip, a control yoke in each hand. Here the figure is laid along the plug: the trunk raised
 * {@link #TORSO} above the plug's axis with the head at the capsule's eye marker, the legs carried forward along
 * the seat, the arms reaching forward to the yokes, the head brought down to look along the plug.
 * <p>
 * Plug frame P as everywhere else: +X right, +Y hatch, +Z from the insertion tip to the tail, blocks. The figure is
 * the game's ordinary player model (rigid limbs); only its pose and place are set. No game classes here, so that
 * the check (PilotSeatPoseR64Test) can prove the fit without the game.
 */
public final class PilotSeatPoseR64
{
    /** The trunk above the plug's axis, the legs and the arms above it the other way, the head brought down (radians). */
    public static final float TORSO = rad(20), LEGS = rad(10), ARMS = rad(27), HEAD = rad(35);
    /** The arms a little out from the body, to the yokes at the seat's sides. */
    public static final float ARM_OUT = .07F;
    /** How far the middle of the head lies over the capsule's eye marker (blocks): the eye is in the face, not the crown. */
    public static final float HEAD_RAISE = .06F;
    /** One model pixel in blocks: the player model is drawn at 15/16. */
    public static final float PIXEL = .9375F / 16;
    /** The model's hip joint over its feet, the neck over the hip, and half the head (blocks). */
    public static final float HIP = 12 * PIXEL, TRUNK = 12 * PIXEL, HALF_HEAD = 4 * PIXEL;

    private PilotSeatPoseR64() {}

    private static float rad(float degrees) { return (float) Math.toRadians(degrees); }

    /** The angle the standing figure is leant back about the plug's X axis, towards the tail. */
    public static float recline() { return (float) (Math.PI / 2) - TORSO; }
    /** Model angles: the legs and arms swung forward from the trunk, the head down. */
    public static float legPitch() { return -(TORSO + LEGS); }
    public static float armPitch() { return -(TORSO + ARMS); }
    public static float headPitch() { return HEAD; }

    /** Where the model's hip joint lies in the plug, given the capsule's eye marker (both in P, blocks). */
    public static Vector3f hip(float eyeX, float eyeY, float eyeZ)
    {
        float lean = recline() - HEAD;
        // The head's own up, leant with the trunk and brought down by the head's pitch.
        float neckY = eyeY + HEAD_RAISE - HALF_HEAD * (float) Math.cos(lean), neckZ = eyeZ - HALF_HEAD * (float) Math.sin(lean);
        return new Vector3f(eyeX, neckY - TRUNK * (float) Math.sin(TORSO), neckZ - TRUNK * (float) Math.cos(TORSO));
    }

    /**
     * Every corner of the posed figure in the plug's frame, for the check. The boxes and joints are the player
     * model's (arms four pixels wide: the wider of the two models).
     */
    public static List<Vector3f> corners(float eyeX, float eyeY, float eyeZ)
    {
        Vector3f hip = hip(eyeX, eyeY, eyeZ);
        // From model pixels to the plug: the renderer's own flip and scale, the hip brought to its place, the lean.
        Matrix4f toPlug = new Matrix4f().translate(hip).rotateX(recline()).translate(0, -HIP, 0)
                .scale(-1, -1, 1).scale(.9375F).translate(0, -1.501F, 0).scale(1 / 16F);
        List<Vector3f> out = new ArrayList<>();
        box(out, toPlug, 0, 0, 0, headPitch(), 0, -4, -8, -4, 4, 0, 4);
        box(out, toPlug, 0, 0, 0, 0, 0, -4, 0, -2, 4, 12, 2);
        box(out, toPlug, -5, 2, 0, armPitch(), ARM_OUT, -3, -2, -2, 1, 10, 2);
        box(out, toPlug, 5, 2, 0, armPitch(), -ARM_OUT, -1, -2, -2, 3, 10, 2);
        box(out, toPlug, -1.9F, 12, 0, legPitch(), 0, -2, 0, -2, 2, 12, 2);
        box(out, toPlug, 1.9F, 12, 0, legPitch(), 0, -2, 0, -2, 2, 12, 2);
        return out;
    }

    private static void box(List<Vector3f> out, Matrix4f toPlug, float px, float py, float pz, float xRot, float zRot,
                            float x0, float y0, float z0, float x1, float y1, float z1)
    {
        // A model part: moved to its joint, then turned about Z and X, as the game does.
        Matrix4f part = new Matrix4f(toPlug).translate(px, py, pz).rotateZ(zRot).rotateX(xRot);
        for (int i = 0; i < 8; i++)
            out.add(part.transformPosition(new Vector3f((i & 1) == 0 ? x0 : x1, (i & 2) == 0 ? y0 : y1, (i & 4) == 0 ? z0 : z1)));
    }
}
