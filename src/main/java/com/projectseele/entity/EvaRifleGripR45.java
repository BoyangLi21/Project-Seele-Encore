package com.projectseele.entity;

import net.minecraft.world.phys.Vec3;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Measured weapon contacts shared by carry geometry and the final arm solve. */
public final class EvaRifleGripR45
{
    public record Contact(Vector3f wrist, Quaternionf rotation) {}
    public record Pair(Contact left, Contact right) {}

    public static Pair contacts(EvaUnit01Entity eva, EvaBodyPose.Sample body,
                                Vec3 grip, Vec3 right, Vec3 forward, Vec3 up)
    {
        if (!EvaAnatomicalHandsR45.enabled(eva) || EvaBodyPose.hasOwnUnRig(eva)) return null;
        var frames = EvaAnatomicalHandsR45.rig(eva.getUnitVariant()).grips();
        if (!frames.containsKey("l") || !frames.containsKey("r")) return null;
        Vector3f r = right.toVector3f(), f = forward.toVector3f(), u = up.toVector3f();
        var along = new Vector3f(f).fma(-.56F, u).normalize();
        var across = new Vector3f(u).fma(.56F, f).normalize();
        // Contacts measured on the imported grip and lower fore-end. These
        // are the SAME contact frames the final rendered arms must consume.
        var dominant = contact(frames.get("r"), body.rig.get("hand_r").pivot(),
                frame(along, across), grip.toVector3f().fma(.573097F, r).fma(-.324F, u).fma(-1.584F, f));
        var supporting = contact(frames.get("l"), body.rig.get("hand_l").pivot(),
                frame(r, f), grip.toVector3f().fma(4.536F, f).fma(.170421F, u));
        return new Pair(supporting, dominant);
    }

    private static Contact contact(EvaAnatomicalHandsR45.Grip grip, Vector3f wrist,
                                    Matrix3f desiredFrame, Vector3f pad)
    {
        var rotation = new Quaternionf().setFromNormalized(desiredFrame.mul(frame(grip.along(), grip.across()).transpose()));
        pad.add(new Quaternionf(rotation).transform(new Vector3f(grip.poseTranslation())).mul(EvaScale.RENDER_SCALE));
        rotation.mul(grip.poseRotation());
        var target = pad.sub(new Quaternionf(rotation).transform(new Vector3f(grip.palm()).sub(wrist).mul(EvaScale.RENDER_SCALE)));
        return new Contact(target, rotation);
    }

    /** Fit an already measured hand frame to a separately authored weapon pad. */
    public static Contact fitPalm(EvaAnatomicalHandsR45.Grip grip, Vector3f wrist,
                                  Vector3f along, Vector3f across, Vector3f pad)
    {
        return contact(grip,wrist,frame(along,across),new Vector3f(pad));
    }

    private static Matrix3f frame(Vector3f along, Vector3f across)
    {
        var y = new Vector3f(along).normalize();
        var x = new Vector3f(across).fma(-across.dot(y), y).normalize();
        return new Matrix3f().setColumn(0, x).setColumn(1, y).setColumn(2, new Vector3f(x).cross(y));
    }

    /** Minimum upward carry correction that leaves both measured wrists reachable.
     * A two-bone arm solver clamps length, so silently sending it an unreachable
     * palm target displaces the hand through the weapon even with correct skin.
     */
    public static double reachLift(Pair contacts, EvaBodyPose.Sample body, Matrix4f world)
    {
        if (contacts == null) return 0;
        double lift = 0;
        float scale = world.getScale(new Vector3f()).y;
        for (String side : new String[]{"l", "r"})
        {
            var arm = body.rig.get("arm_" + side);
            var hand = body.rig.get("hand_" + side);
            var socket = body.rig.get("r30_elbow_socket_" + side);
            var elbow = socket != null ? socket.pivot()
                    : new Vector3f(side.equals("l") ? -23.489652F : 23.489652F, 123.435069F, 7.737214F).div(16);
            double reach = (arm.pivot().distance(elbow) + elbow.distance(hand.pivot())) * scale - .08;
            var shoulder = new Matrix4f(world).mul(body.matrix(arm.name())).transformPosition(new Vector3f(arm.pivot()));
            var target = side.equals("l") ? contacts.left().wrist() : contacts.right().wrist();
            double dx = target.x - shoulder.x, dz = target.z - shoulder.z;
            double remaining = reach * reach - dx * dx - dz * dz;
            // A vertical correction cannot resolve a horizontal reach failure.
            // Do not fabricate a valid solution by stretching the arm.
            if (remaining > 0)
                lift = Math.max(lift, shoulder.y - Math.sqrt(remaining) - target.y);
        }
        return lift;
    }

    private EvaRifleGripR45() {}
}
