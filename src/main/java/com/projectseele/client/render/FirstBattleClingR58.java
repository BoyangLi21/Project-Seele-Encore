package com.projectseele.client.render;

import com.projectseele.entity.FirstBattleClip;
import com.projectseele.entity.FirstBattleSignals;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

/**
 * Sachiel's last act in the first battle, solved against Unit-01's real body
 * instead of replaying angles authored for another mesh: from the ground it
 * springs onto Unit-01's chest, its arms close round the back of the
 * shoulders and its legs lock round the waist, and it squeezes harder,
 * shaking, until the cross. Unit-01's back socket and eye curves of the clip
 * give the body it holds; two-bone IK places every limb on it.
 */
final class FirstBattleClingR58
{
    static final float RISE = 17.0F, HOLD = 17.7F, END = 18.7F;
    private static final String[] BONES = {"root", "torso_lower", "torso_upper", "neck", "head",
            "arm_l", "forearm_l", "hand_l", "leg_l", "shin_l", "foot_l",
            "arm_r", "forearm_r", "hand_r", "leg_r", "shin_r", "foot_r"};

    private FirstBattleClingR58() {}

    static boolean active(float time) { return time >= RISE && time <= END; }

    static void apply(Entity angel, BakedGeoModel model, FirstBattleSignals.Spec spec, float time, float partial)
    {
        GeoBone[] bones = new GeoBone[BONES.length];
        for (int i = 0; i < BONES.length; i++)
        {
            bones[i] = model.getBone(BONES[i]).orElse(null);
            if (bones[i] == null) return;
        }
        // The clip's own pose at this instant, for the spring out of it.
        float[][] clip = new float[BONES.length][6];
        for (int i = 0; i < BONES.length; i++) clip[i] = read(bones[i]);

        Vec3 origin = new Vec3(Mth.lerp(partial, angel.xOld, angel.getX()), Mth.lerp(partial, angel.yOld, angel.getY()),
                Mth.lerp(partial, angel.zOld, angel.getZ())).add(FirstBattleClip.renderOffset(angel, partial));
        float yaw = FirstBattleClip.yaw(spec, false, time);
        Matrix4f root = new Matrix4f().translate((float) origin.x, (float) origin.y, (float) origin.z)
                .rotateY((float) Math.toRadians(180 - yaw)).scale(5);

        Vec3 socket = FirstBattleClip.point(spec, true, "socket_blocks", time);
        float evaYaw = FirstBattleClip.yaw(spec, true, time);
        Vec3 front = Vec3.directionFromRotation(0, evaYaw).multiply(1, 0, 1).normalize();
        Vec3 side = new Vec3(-front.z, 0, front.x);
        Vec3 evaRoot = FirstBattleClip.point(spec, true, "root_blocks", time);

        float hold = Mth.clamp((time - HOLD) / (END - HOLD), 0, 1);
        // Squeeze: the grip closes and the body presses in as the core fails.
        float squeeze = hold * hold;
        float shake = hold * .35F * Mth.sin(time * 44F) + hold * .2F * Mth.sin(time * 71F);

        // Trunk upright and leaning into Unit-01; limbs reset before solving.
        for (int i = 1; i < BONES.length; i++) zero(bones[i]);
        zero(bones[0]);
        Vector3f lean = new Vector3f(0, 1, 0).fma(.28F + .1F * squeeze, toF(front.scale(-1))).normalize();
        Quaternionf world = new Quaternionf().rotationTo(new Vector3f(0, 1, 0), lean).mul(EvaRigTransforms.rotation(root));
        EvaRigTransforms.rotate(bones[0], EvaRigTransforms.rotation(root).invert().mul(world));
        bones[2].setRotX(.12F); // chest curls over the shoulders it holds
        bones[4].setRotX(.35F); // mask pressed down against Unit-01

        // Body: the waist of Sachiel's chest a body's depth in front of Unit-01's chest.
        Vec3 chest = socket.add(front.scale(12.5 - 1.5 * squeeze)).add(0, -21 + shake, 0).add(side.scale(shake * .6));
        Vector3f now = EvaRigTransforms.point(bones[2], EvaRigTransforms.pivot(bones[2]), root);
        Vector3f move = toF(chest).sub(now);
        Vector3f local = EvaRigTransforms.rotation(root).invert().transform(new Vector3f(move)).div(root.getScale(new Vector3f()).y);
        bones[0].setPosX(-local.x * 16); bones[0].setPosY(local.y * 16); bones[0].setPosZ(local.z * 16);

        for (int s = 0; s < 2; s++)
        {
            String n = s == 0 ? "l" : "r";
            int arm = s == 0 ? 5 : 11;
            // Each limb goes to the side of Unit-01 it is already on.
            Vector3f shoulder = EvaRigTransforms.point(bones[arm], EvaRigTransforms.pivot(bones[arm]), root);
            double sign = Math.signum(new Vec3(shoulder.x, shoulder.y, shoulder.z).subtract(socket).dot(side));
            if (sign == 0) sign = s == 0 ? 1 : -1;
            Vec3 hand = socket.add(side.scale(sign * (8.5 - 2.5 * squeeze))).add(0, -7.5, 0).add(front.scale(-2.5 - squeeze));
            Vec3 foot = evaRoot.add(side.scale(sign * (8.5 - 2 * squeeze))).add(0, 17, 0).add(front.scale(-2.5));
            Vector3f armPole = toF(side.scale(sign).add(0, .45, 0).add(front.scale(.3)));
            Vector3f legPole = toF(side.scale(sign).add(0, .7, 0).add(front.scale(.6)));
            EvaRigTransforms.solveGenericArm(bones[arm], bones[arm + 1], bones[arm + 2], toF(hand),
                    EvaRigTransforms.rotation(root), armPole, root);
            // Claws curl into Unit-01's back.
            bones[arm + 2].setRotX(.5F); bones[arm + 2].setRotY(0); bones[arm + 2].setRotZ(0);
            EvaRigTransforms.solveGenericArm(bones[arm + 3], bones[arm + 4], bones[arm + 5], toF(foot),
                    EvaRigTransforms.rotation(root), legPole, root);
            bones[arm + 5].setRotX(-.6F); bones[arm + 5].setRotY(0); bones[arm + 5].setRotZ(0);
        }

        // The spring: from the clip's pose on the ground into the hold.
        float rise = Mth.clamp((time - RISE) / (HOLD - RISE), 0, 1);
        float w = rise * rise * (3 - 2 * rise);
        if (w < 1)
            for (int i = 0; i < BONES.length; i++)
            {
                float[] solved = read(bones[i]);
                var a = new Quaternionf().rotationZYX(clip[i][2], clip[i][1], clip[i][0]);
                var b = new Quaternionf().rotationZYX(solved[2], solved[1], solved[0]);
                EvaRigTransforms.rotate(bones[i], a.slerp(b, w));
                bones[i].setPosX(Mth.lerp(w, clip[i][3], solved[3]));
                bones[i].setPosY(Mth.lerp(w, clip[i][4], solved[4]));
                bones[i].setPosZ(Mth.lerp(w, clip[i][5], solved[5]));
            }
    }

    static final float GRAB_IN = 5.6F, GRAB_FULL = 6.1F, YANK = 8.4F, GRAB_OUT = 9.1F, GRAB_END = 9.5F;

    static boolean grabbing(float time) { return time >= GRAB_IN && time <= GRAB_END; }

    /**
     * Unit-01 seizes Sachiel by the arm: that arm goes into Unit-01's gripping
     * hand and is drawn out straight when the hand hauls on it, the free arm
     * claws at Unit-01's shoulder, and the trunk leans back against the pull
     * until the yank jerks it forward into the throw. Outside the window the
     * clip's own pose returns through the same blend.
     */
    static void grab(Entity angel, BakedGeoModel model, FirstBattleSignals.Spec spec, float time, float partial)
    {
        GeoBone[] bones = new GeoBone[BONES.length];
        for (int i = 0; i < BONES.length; i++)
        {
            bones[i] = model.getBone(BONES[i]).orElse(null);
            if (bones[i] == null) return;
        }
        float[][] clip = new float[BONES.length][6];
        for (int i = 0; i < BONES.length; i++) clip[i] = read(bones[i]);
        Vec3 origin = new Vec3(Mth.lerp(partial, angel.xOld, angel.getX()), Mth.lerp(partial, angel.yOld, angel.getY()),
                Mth.lerp(partial, angel.zOld, angel.getZ())).add(FirstBattleClip.renderOffset(angel, partial));
        float yaw = FirstBattleClip.yaw(spec, false, time);
        Matrix4f root = new Matrix4f().translate((float) origin.x, (float) origin.y, (float) origin.z)
                .rotateY((float) Math.toRadians(180 - yaw)).scale(5);
        Vec3 grip = FirstBattleClip.point(spec, true, "hand_r_blocks", time);
        Vec3 socket = FirstBattleClip.point(spec, true, "socket_blocks", time);
        Vec3 eva = FirstBattleClip.point(spec, true, "root_blocks", time);
        Vec3 toward = eva.subtract(origin).multiply(1, 0, 1);
        toward = toward.lengthSqr() < 1e-4 ? Vec3.directionFromRotation(0, yaw + 180) : toward.normalize();
        Vec3 side = new Vec3(-toward.z, 0, toward.x);

        // Trunk: back against the pull, then thrown forward by the yank.
        float yank = Mth.clamp((time - YANK) / (GRAB_OUT - YANK), 0, 1);
        yank = yank * yank * (3 - 2 * yank);
        float back = -.22F + .62F * yank;
        Vector3f lean = new Vector3f(0, 1, 0).fma(back, toF(toward)).normalize();
        Quaternionf world = new Quaternionf().rotationTo(new Vector3f(0, 1, 0), lean).mul(EvaRigTransforms.rotation(root));
        EvaRigTransforms.rotate(bones[0], EvaRigTransforms.rotation(root).invert().mul(world));
        bones[1].setRotX(0); bones[1].setRotY(0); bones[1].setRotZ(0);
        bones[2].setRotX(0); bones[2].setRotY(0); bones[2].setRotZ(0);

        int held = -1;
        double nearest = Double.MAX_VALUE;
        for (int arm : new int[] {5, 11})
        {
            Vector3f s = EvaRigTransforms.point(bones[arm], EvaRigTransforms.pivot(bones[arm]), root);
            double d = grip.distanceToSqr(s.x, s.y, s.z);
            if (d < nearest) { nearest = d; held = arm; }
        }
        for (int arm : new int[] {5, 11})
        {
            Vector3f shoulder = EvaRigTransforms.point(bones[arm], EvaRigTransforms.pivot(bones[arm]), root);
            double sign = Math.signum(new Vec3(shoulder.x, shoulder.y, shoulder.z).subtract(origin).dot(side));
            Vec3 target;
            Vector3f pole;
            if (arm == held)
            {
                // The wrist a little past the gripping hand: the forearm lies in its grip.
                Vec3 along = grip.subtract(shoulder.x, shoulder.y, shoulder.z).normalize();
                target = grip.add(along.scale(5));
                pole = toF(side.scale(sign).add(0, -.6, 0));
            }
            else
            {
                target = socket.add(toward.scale(-7)).add(0, -9, 0).add(side.scale(sign * 6));
                pole = toF(side.scale(sign).add(0, .5, 0).add(toward.scale(-.4)));
            }
            EvaRigTransforms.solveGenericArm(bones[arm], bones[arm + 1], bones[arm + 2], toF(target),
                    EvaRigTransforms.rotation(root), pole, root);
            bones[arm + 2].setRotX(arm == held ? .2F : .6F); bones[arm + 2].setRotY(0); bones[arm + 2].setRotZ(0);
        }

        float in = Mth.clamp((time - GRAB_IN) / (GRAB_FULL - GRAB_IN), 0, 1);
        float out = Mth.clamp((GRAB_END - time) / (GRAB_END - GRAB_OUT), 0, 1);
        float w = Math.min(in * in * (3 - 2 * in), out * out * (3 - 2 * out));
        if (w < 1)
            for (int i = 0; i < BONES.length; i++)
            {
                float[] solved = read(bones[i]);
                var a = new Quaternionf().rotationZYX(clip[i][2], clip[i][1], clip[i][0]);
                var b = new Quaternionf().rotationZYX(solved[2], solved[1], solved[0]);
                EvaRigTransforms.rotate(bones[i], a.slerp(b, w));
                bones[i].setPosX(Mth.lerp(w, clip[i][3], solved[3]));
                bones[i].setPosY(Mth.lerp(w, clip[i][4], solved[4]));
                bones[i].setPosZ(Mth.lerp(w, clip[i][5], solved[5]));
            }
    }

    private static float[] read(GeoBone b)
    {
        return new float[] {b.getRotX(), b.getRotY(), b.getRotZ(), b.getPosX(), b.getPosY(), b.getPosZ()};
    }

    private static void zero(GeoBone b)
    {
        b.setRotX(0); b.setRotY(0); b.setRotZ(0); b.setPosX(0); b.setPosY(0); b.setPosZ(0);
    }

    private static Vector3f toF(Vec3 v) { return new Vector3f((float) v.x, (float) v.y, (float) v.z); }
}
