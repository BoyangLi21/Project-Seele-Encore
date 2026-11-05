package com.projectseele.client.render;

import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.GeoBone;

/**
 * Two-bone limb IK whose twist is fixed by anatomy.
 *
 * <p>Placing the middle joint toward a pole fixes where the knee or elbow
 * is, but not which way the limb faces: the same joint positions are reached
 * with the thigh and shin turned half round their own length, kneecap to
 * the back. The shared solver keeps whichever turn the incoming pose had,
 * which is right for gameplay poses and wrong for an authored clip whose
 * limbs were already turned. Here the turn is chosen so that a stated side of
 * the upper bone - the kneecap for a leg, the point of the elbow for an arm -
 * faces the way the joint bends.
 */
final class AnatomicalLimbR58
{
    private AnatomicalLimbR58() {}

    /**
     * @param centre    the middle joint in the upper bone's rest frame (model blocks), e.g. the knee socket
     * @param facing    model-space direction of the side that must face the bend at rest
     * @return distance left between the end bone's pivot and the target
     */
    static double solve(GeoBone upper, GeoBone lower, GeoBone wrist, GeoBone end, Vector3f centre,
                        Vector3f target, Vector3f pole, Matrix4f root, Vector3f facing)
    {
        Vector3f shoulder = EvaRigTransforms.point(upper, EvaRigTransforms.pivot(upper), root);
        float scale = root.getScale(new Vector3f()).y;
        Vector3f u = new Vector3f(centre).sub(EvaRigTransforms.pivot(upper));
        Vector3f v = EvaRigTransforms.pivot(end).sub(centre);
        float a = u.length() * scale, b = v.length() * scale;
        Vector3f direction = new Vector3f(target).sub(shoulder);
        float length = direction.length();
        if (length < 1e-6F) direction.set(0, -1, 0); else direction.div(length);
        float distance = Math.max(Math.abs(a - b) + .001F, Math.min(a + b - .001F, length));
        float along = (a * a - b * b + distance * distance) / (2 * distance);
        float height = (float) Math.sqrt(Math.max(0, a * a - along * along));
        Vector3f bend = new Vector3f(pole).sub(new Vector3f(direction).mul(pole.dot(direction)));
        if (bend.lengthSquared() < 1e-8F) bend.set(0, 0, 1).sub(new Vector3f(direction).mul(direction.z));
        bend.normalize();
        Vector3f joint = new Vector3f(shoulder).fma(along, direction).fma(height, bend);
        Vector3f du = new Vector3f(joint).sub(shoulder), dl = new Vector3f(target).sub(joint);
        Vector3f axis = new Vector3f(du).cross(dl);
        if (axis.lengthSquared() < 1e-8F) axis.set(du).cross(bend);
        axis.normalize();
        Vector3f restAxis = new Vector3f(1, 0, 0);

        for (GeoBone bone : new GeoBone[] {lower, wrist, end}) { bone.setPosX(0); bone.setPosY(0); bone.setPosZ(0); }
        if (wrist != end) { wrist.setRotX(0); wrist.setRotY(0); wrist.setRotZ(0); }

        // The two turns that reach the same joints differ by half a turn about
        // the limb; keep the one whose stated side faces the bend.
        Quaternionf world = frameRotation(du, axis, u, restAxis);
        if (world.transform(new Vector3f(facing)).dot(bend) < 0)
        {
            axis.negate();
            world = frameRotation(du, axis, u, restAxis);
        }
        EvaRigTransforms.rotate(upper, EvaRigTransforms.rotation(EvaRigTransforms.parent(upper, root)).invert().mul(world));
        Vector3f actual = EvaRigTransforms.parent(lower, root).transformPosition(new Vector3f(centre));
        Quaternionf lowerWorld = frameRotation(new Vector3f(target).sub(actual), axis, v, restAxis);
        EvaRigTransforms.rotate(lower, EvaRigTransforms.rotation(EvaRigTransforms.parent(lower, root)).invert().mul(lowerWorld));
        EvaRigTransforms.hinge(lower, centre);
        return EvaRigTransforms.point(end, EvaRigTransforms.pivot(end), root).distance(target);
    }

    /** World rotation taking a bone's rest direction and hinge axis onto the solved ones. */
    private static Quaternionf frameRotation(Vector3f direction, Vector3f axis, Vector3f rest, Vector3f restAxis)
    {
        return new Quaternionf().setFromNormalized(frame(direction, axis).mul(frame(rest, restAxis).transpose()));
    }

    private static Matrix3f frame(Vector3f direction, Vector3f axis)
    {
        Vector3f y = new Vector3f(direction).normalize();
        Vector3f x = new Vector3f(axis).sub(new Vector3f(y).mul(axis.dot(y))).normalize();
        return new Matrix3f().setColumn(0, x).setColumn(1, y).setColumn(2, new Vector3f(x).cross(y));
    }

    /** Model-space forward of a body whose renderer matrix is {@code root}, given the way it faces in the world. */
    static Vector3f modelForward(Matrix4f root, Vector3f worldFacing)
    {
        return EvaRigTransforms.rotation(root).invert().transform(new Vector3f(worldFacing)).normalize();
    }

    /**
     * How well a bone's stated side faces the bend of its joint, -1..1:
     * negative means the limb is turned the wrong way round.
     */
    static float facingScore(GeoBone upper, GeoBone lower, GeoBone end, Matrix4f root, Vector3f facing, Vector3f centre)
    {
        Vector3f hip = EvaRigTransforms.point(upper, EvaRigTransforms.pivot(upper), root);
        Vector3f knee = EvaRigTransforms.point(upper, centre, root);
        Vector3f ankle = EvaRigTransforms.point(end, EvaRigTransforms.pivot(end), root);
        Vector3f line = new Vector3f(ankle).sub(hip);
        float t = line.lengthSquared() < 1e-6F ? 0 : new Vector3f(knee).sub(hip).dot(line) / line.lengthSquared();
        Vector3f bend = new Vector3f(knee).sub(new Vector3f(hip).fma(t, line));
        if (bend.length() < .8F) return 1;
        bend.normalize();
        Vector3f side = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(upper))).transform(new Vector3f(facing)).normalize();
        return side.dot(bend);
    }
}
