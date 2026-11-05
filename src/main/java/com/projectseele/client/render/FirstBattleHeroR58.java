package com.projectseele.client.render;

import com.projectseele.entity.EvaScale;
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
 * Unit-01's whole body in the first-battle finale.
 *
 * <p>The authored clip's body motion could not be repaired limb by limb: it
 * tipped the body back as if Unit-01 were the one thrown, leapt over Sachiel
 * and squatted in the air. Only its ground path and timing are kept. The
 * trunk follows a table of phases (pelvis drop, lean, chest bend, twist), the
 * feet follow a plan of plants and steps, the hands a target per phase, and
 * every limb is solved with {@link AnatomicalLimbR58} so kneecaps and elbows
 * face the way they bend.
 *
 * <p>Phases: push on the AT field (0-5 s) and tear it (5-5.6); step in and
 * seize Sachiel by the shoulders (5.6-8.4); twist and hurl it (8.4-9.4);
 * follow through and run to it (9.4-11.8); drop to both knees beside it
 * (11.8-12.2); six two-handed blows into its core (12.2-16.75); rise
 * (16.75-17.6) and brace against its embrace until the cross.
 */
final class FirstBattleHeroR58
{
    static final float[] BLOWS = {12.75F, 13.35F, 14.15F, 14.75F, 15.35F, 16.05F};
    static final float POUND_IN = 12.05F, POUND_OUT = 16.75F;
    private static final float WIND = .4F, STRIKE = .11F, HOLD = .1F;
    private static final float TEAR = 5F, STEP = 5.6F, TWIST = 8.4F, LET_GO = 9.4F, RUN = 10F, KNEEL = 11.8F,
            RISE = 16.75F, BRACE = 17.6F;
    /** Pelvis height above the ground when kneeling, blocks. */
    private static final float KNEEL_HIP = 15F;
    private static final float ANKLE_LIMIT = (float) Math.toRadians(35);

    private FirstBattleHeroR58() {}

    private static float standingRootY, standingAnkle = 6, standingHip = 36;
    private static final Quaternionf[] standingAnkleTurn = {new Quaternionf(), new Quaternionf()};
    /** Unit-01's forearms (left, right), published for Sachiel's claws (one frame behind at most). */
    private static final Vec3[] forearms = new Vec3[2];
    private static float forearmsAt = -1;

    static Vec3[] forearms(float time)
    {
        return forearms[0] != null && forearms[1] != null && Math.abs(time - forearmsAt) < .25F ? forearms.clone() : null;
    }

    /** Where Unit-01's fists land: the pinned Sachiel's core. */
    static Vec3 core(FirstBattleSignals.Spec spec, float time)
    {
        return FirstBattleClip.poundCore(spec, time);
    }

    // ------------------------------------------------------------ the body

    private record Body(float drop, float lean, float bend, float twist) {}

    private static Body body(float t)
    {
        if (t < TEAR) return new Body(2.5F, .2F, .1F, 0);
        if (t < STEP) return new Body(2, .12F, .05F, 0);
        if (t < TWIST)
        {
            float u = smooth((t - STEP) / .7F);
            return new Body(2 + 2 * u, .12F + .16F * u, .05F + .1F * u, 0);
        }
        if (t < LET_GO)
        {
            float u = smooth((t - TWIST) / (LET_GO - TWIST));
            return new Body(4 - u, .28F - .1F * u, .15F, -.75F * u);
        }
        if (t < RUN)
        {
            float u = smooth((t - LET_GO) / (RUN - LET_GO));
            return new Body(3 - 1.5F * u, .18F + .05F * u, .15F, -.75F * (1 - u));
        }
        if (t < KNEEL) return new Body(1.5F + .8F * Math.abs(Mth.sin((t - RUN) * Mth.PI / .4F)), .24F, .12F, 0);
        float kneel = standingHip - KNEEL_HIP;
        if (t < POUND_IN + .15F)
        {
            float u = smooth((t - KNEEL) / (POUND_IN + .15F - KNEEL));
            return new Body(Mth.lerp(u, 1.5F, kneel), .24F + .1F * u, .12F + .1F * u, 0);
        }
        if (t < RISE)
        {
            float trunk = trunk(t);
            return new Body(kneel, .34F + .35F * trunk, .22F + .3F * trunk, 0);
        }
        if (t < BRACE)
        {
            float u = smooth((t - RISE) / (BRACE - RISE));
            return new Body(Mth.lerp(u, kneel, 2), Mth.lerp(u, .34F, -.08F), Mth.lerp(u, .22F, 0), 0);
        }
        return new Body(2.5F, -.12F, -.05F, 0);
    }

    // ------------------------------------------------------------ the feet

    /** A foot on the ground from {@code from} to {@code to}, at the path's point at {@code key} plus lead/width. */
    private record Plant(float from, float to, float key, float lead, float width, boolean kneel) {}

    private static final Plant[][] PLANS = {
        { // left: leads in the lunge
            new Plant(-1, 5.7F, .4F, 8, 5, false), new Plant(6F, 8.95F, 6.6F, 9, 5, false), new Plant(9.25F, 10.15F, 9.7F, 7, 5, false),
            new Plant(10.45F, 10.75F, 10.6F, 6, 5, false), new Plant(11.25F, 11.55F, 11.4F, 6, 5, false),
            new Plant(12.1F, 16.9F, 12.5F, -14, 6.5F, true), new Plant(17.45F, 99, 17.6F, 1, 5, false)},
        { // right: trails in the lunge
            new Plant(-1, 5.9F, .4F, -8, 5, false), new Plant(6.2F, 9.1F, 6.6F, -9, 5, false), new Plant(9.4F, 10.35F, 9.9F, -6, 5, false),
            new Plant(10.85F, 11.15F, 11F, 6, 5, false), new Plant(11.65F, 11.85F, 11.8F, 4, 5, false),
            new Plant(12.1F, 16.9F, 12.5F, -14, 6.5F, true), new Plant(17.5F, 99, 17.6F, -3, 5, false)}};

    private static Vec3 plant(FirstBattleSignals.Spec spec, Plant p, int s, Vec3 front, Vec3 left, double ground)
    {
        Vec3 path = FirstBattleClip.point(spec, true, "root_blocks", p.key());
        Vec3 at = path.add(front.scale(p.lead())).add(left.scale((s == 0 ? 1 : -1) * p.width()));
        return new Vec3(at.x, ground + (p.kneel() ? 3 : standingAnkle), at.z);
    }

    /** The foot's pivot target now: planted, kneeling, or on a step between two plants. */
    private static Vec3 foot(FirstBattleSignals.Spec spec, float t, int s, Vec3 front, Vec3 left, double ground)
    {
        Plant[] plan = PLANS[s];
        for (int i = 0; i < plan.length; i++)
        {
            Plant p = plan[i];
            if (t <= p.to())
            {
                if (t >= p.from() || i == 0) return plant(spec, p, s, front, left, ground);
                Plant before = plan[i - 1];
                float u = Mth.clamp((t - before.to()) / (p.from() - before.to()), 0, 1);
                Vec3 a = plant(spec, before, s, front, left, ground), b = plant(spec, p, s, front, left, ground);
                double lift = Math.min(8, .35 * a.distanceTo(b));
                return a.lerp(b, smooth(u)).add(0, lift * 4 * u * (1 - u), 0);
            }
        }
        return plant(spec, plan[plan.length - 1], s, front, left, ground);
    }

    private static boolean kneeling(float t) { return t > 12.1F && t < 16.9F; }

    // ------------------------------------------------------------ the hands

    private static Vector3f hand(FirstBattleSignals.Spec spec, float t, int s, Vector3f shoulder, Vector3f chest,
                                 Vec3 front, Vec3 left, Vec3[] held, Vec3[] sachiel)
    {
        float sign = s == 0 ? 1 : -1;
        Vector3f guard = new Vector3f(chest).fma(11, toF(front)).fma(5 * sign, toF(left)).add(0, -3, 0);
        if (t < TEAR) return toF(FirstBattleClip.point(spec, true, s == 0 ? "hand_l_blocks" : "hand_r_blocks", t));
        if (t < STEP)
        {
            // Tearing the field open: the hands drive apart and down.
            float u = smooth((t - TEAR) / (STEP - TEAR));
            return toF(FirstBattleClip.point(spec, true, s == 0 ? "hand_l_blocks" : "hand_r_blocks", TEAR))
                    .fma(12 * u * sign, toF(left)).add(0, -5 * u, 0);
        }
        if (t < LET_GO + .2F && held != null)
        {
            Vector3f a = toF(held[0]), b = toF(held[1]);
            Vector3f mine = a.distanceSquared(shoulder) < b.distanceSquared(shoulder) ? a : b;
            Vector3f grip = new Vector3f(mine).lerp(new Vector3f(a).add(b).mul(.5F), .25F).add(0, -2, 0);
            float in = smooth((t - STEP) / .6F);
            return new Vector3f(guard).lerp(grip, in);
        }
        if (t < RUN)
        {
            // Follow-through of the throw: both arms swept down and across.
            float u = smooth((t - LET_GO) / (RUN - LET_GO));
            return new Vector3f(guard).add(0, -10 * u, 0).fma(-6 * u * sign, toF(left));
        }
        if (t < KNEEL)
        {
            // Running: arms swing opposite to the legs.
            float swing = Mth.sin((t - RUN) * Mth.PI / .4F) * sign;
            return new Vector3f(shoulder).add(0, -17, 0).fma(7 * swing, toF(front)).fma(5 * sign, toF(left));
        }
        if (t < POUND_IN) return guard;
        if (t < POUND_OUT)
        {
            Vector3f fists = fists(spec, t, shoulder, front).fma(1.3F * sign, toF(left));
            return new Vector3f(guard).lerp(fists, poundWeight(t));
        }
        if (t < BRACE || sachiel == null) return guard;
        // Bracing against the embrace: hands on its shoulders, pushing it off.
        return toF(sachiel[1]).fma(7 * sign, toF(left)).fma(-1.5F, toF(front));
    }

    // ------------------------------------------------------------ solving

    static void apply(Entity eva, BakedGeoModel model, FirstBattleSignals.Spec spec, float time, float partial, Matrix4f root)
    {
        GeoBone rootBone = model.getBone("root").orElse(null), pelvis = model.getBone("torso_lower").orElse(null),
                chestBone = model.getBone("torso_upper").orElse(null);
        if (rootBone == null || pelvis == null || chestBone == null) return;
        double ground = spec.origin().y;
        Vec3 front = Vec3.directionFromRotation(0, FirstBattleClip.yaw(spec, true, time)).multiply(1, 0, 1).normalize();
        Vec3 left = new Vec3(front.z, 0, -front.x);
        Vector3f forward = AnatomicalLimbR58.modelForward(root, toF(front));

        if (time < 1)
        {
            standingRootY = rootBone.getPosY();
            for (int s = 0; s < 2; s++)
            {
                String side = s == 0 ? "l" : "r";
                GeoBone shin = model.getBone("shin_" + side).orElse(null), foot = model.getBone("foot_" + side).orElse(null),
                        thigh = model.getBone("leg_" + side).orElse(null);
                if (shin == null || foot == null || thigh == null) continue;
                standingAnkleTurn[s] = relation(shin, foot, root);
                standingAnkle = (float) Math.max(.5, EvaRigTransforms.point(foot, EvaRigTransforms.pivot(foot), root).y - ground);
                standingHip = (float) (EvaRigTransforms.point(thigh, EvaRigTransforms.pivot(thigh), root).y - ground);
            }
        }

        // The trunk from the phase table.
        Body b = body(time);
        for (GeoBone bone : new GeoBone[] {rootBone, pelvis, chestBone})
        {
            bone.setRotX(0); bone.setRotY(0); bone.setRotZ(0);
        }
        model.getBone("neck").ifPresent(n -> { n.setRotX(0); n.setRotY(0); n.setRotZ(0); });
        model.getBone("head").ifPresent(n -> { n.setRotX(0); n.setRotY(0); n.setRotZ(0); });
        rootBone.setPosX(0); rootBone.setPosZ(0);
        rootBone.setPosY(standingRootY - b.drop() * 16 / EvaScale.RENDER_SCALE);
        turn(rootBone, new Quaternionf().rotationY(b.twist()), root);
        Vector3f leftNow = new Quaternionf().rotationY(b.twist()).transform(toF(left));
        turn(pelvis, new Quaternionf().fromAxisAngleRad(leftNow.x, leftNow.y, leftNow.z, b.lean()), root);
        turn(chestBone, new Quaternionf().fromAxisAngleRad(leftNow.x, leftNow.y, leftNow.z, b.bend()), root);

        // Legs to the foot plan.
        for (int s = 0; s < 2; s++)
        {
            String side = s == 0 ? "l" : "r";
            GeoBone upper = model.getBone("leg_" + side).orElse(null), lower = model.getBone("shin_" + side).orElse(null);
            GeoBone ankle = model.getBone("ankle_" + side).orElse(null), foot = model.getBone("foot_" + side).orElse(null);
            if (upper == null || lower == null || ankle == null || foot == null) continue;
            Vector3f target = toF(foot(spec, time, s, front, left, ground));
            boolean kneel = kneeling(time);
            Vector3f pole = kneel ? toF(front).add(0, -.6F, 0) : toF(front).fma(s == 0 ? .15F : -.15F, toF(left)).add(0, .1F, 0);
            AnatomicalLimbR58.solve(upper, lower, ankle, foot, EvaRigTransforms.knee(lower), target, pole, root, forward);
            Quaternionf shinWorld = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(lower)));
            Quaternionf wanted;
            if (kneel) wanted = new Quaternionf(shinWorld).mul(standingAnkleTurn[s]);
            else
            {
                // Flat on the ground; a foot well behind the hip rises onto its toes.
                Vector3f hip = EvaRigTransforms.point(upper, EvaRigTransforms.pivot(upper), root);
                float behind = -new Vector3f(target).sub(hip).dot(toF(front));
                float lift = (float) Math.toRadians(40) * Mth.clamp((behind - 4) / 14F, 0, 1);
                Vector3f toes = toF(front).mul(Mth.cos(lift)).add(0, -Mth.sin(lift), 0);
                wanted = new Quaternionf().rotationTo(toF(front), toes).mul(EvaRigTransforms.rotation(root))
                        .mul(new Quaternionf().rotationY(b.twist()));
            }
            EvaRigTransforms.rotate(foot, EvaRigTransforms.rotation(EvaRigTransforms.parent(foot, root)).invert().mul(wanted));
            limitAnkle(lower, foot, root, standingAnkleTurn[s]);
        }

        // Arms to the phase's hand targets.
        Vector3f chest = EvaRigTransforms.point(chestBone, EvaRigTransforms.pivot(chestBone), root).add(0, 8, 0);
        Vec3[] held = FirstBattleAngelR58.shoulders(time);
        Vec3[] sachiel = FirstBattleAngelR58.body(time);
        for (int s = 0; s < 2; s++)
        {
            String side = s == 0 ? "l" : "r";
            GeoBone upper = model.getBone("arm_" + side).orElse(null), lower = model.getBone("forearm_" + side).orElse(null);
            GeoBone wrist = model.getBone("wrist_" + side).orElse(null), hand = model.getBone("hand_" + side).orElse(null);
            if (upper == null || lower == null || wrist == null || hand == null) continue;
            Vector3f shoulder = EvaRigTransforms.point(upper, EvaRigTransforms.pivot(upper), root);
            Vector3f target = hand(spec, time, s, shoulder, chest, front, left, held, sachiel);
            Vector3f out = toF(left).mul(s == 0 ? 1 : -1);
            Vector3f pole = target.y > shoulder.y
                    ? new Vector3f(out).mul(.7F).fma(.5F, toF(front)).add(0, .2F, 0)
                    : new Vector3f(out).mul(.8F).add(0, -1, 0).fma(-.3F, toF(front));
            AnatomicalLimbR58.solve(upper, lower, wrist, hand, EvaRigTransforms.elbow(lower, side), target, pole, root,
                    new Vector3f(forward).negate());
            wrist.setRotX(0); wrist.setRotY(0); wrist.setRotZ(0);
            hand.setRotX(0); hand.setRotY(0); hand.setRotZ(0);
            Vector3f elbow = EvaRigTransforms.point(lower, EvaRigTransforms.pivot(lower), root);
            Vector3f palm = EvaRigTransforms.point(hand, EvaRigTransforms.pivot(hand), root);
            Vector3f mid = elbow.lerp(palm, .55F);
            forearms[s] = new Vec3(mid.x, mid.y, mid.z);
        }
        forearmsAt = time;
        log(model, root, time, forward, ground);
    }

    /** Turns a just-zeroed bone by a world rotation about its pivot. */
    private static void turn(GeoBone bone, Quaternionf world, Matrix4f root)
    {
        Quaternionf parent = EvaRigTransforms.rotation(EvaRigTransforms.parent(bone, root));
        EvaRigTransforms.rotate(bone, new Quaternionf(parent).invert().mul(world).mul(parent));
    }

    private static Quaternionf relation(GeoBone shin, GeoBone foot, Matrix4f root)
    {
        Quaternionf shinWorld = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(shin)));
        Quaternionf footWorld = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(foot)));
        return shinWorld.invert().mul(footWorld).normalize();
    }

    /** Keeps the foot within ANKLE_LIMIT of how it sits on the shin when standing. */
    private static void limitAnkle(GeoBone shin, GeoBone foot, Matrix4f root, Quaternionf standing)
    {
        Quaternionf shinWorld = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(shin)));
        Quaternionf away = new Quaternionf(standing).invert().mul(relation(shin, foot, root)).normalize();
        float angle = 2 * (float) Math.acos(Math.min(1, Math.abs(away.w)));
        if (angle <= ANKLE_LIMIT) return;
        Quaternionf wanted = new Quaternionf(shinWorld).mul(standing).mul(new Quaternionf().slerp(away, ANKLE_LIMIT / angle));
        EvaRigTransforms.rotate(foot, EvaRigTransforms.rotation(EvaRigTransforms.parent(foot, root)).invert().mul(wanted));
    }

    // ------------------------------------------------------------ the blows

    static float poundWeight(float time)
    {
        float in = Mth.clamp((time - POUND_IN) / .35F, 0, 1), out = Mth.clamp((POUND_OUT - time) / .45F, 0, 1);
        return smooth(Math.min(in, out));
    }

    /** Phase of the blow sequence: -1 wound up, 0 between, +1 driven down. */
    private static float phase(float time)
    {
        for (float blow : BLOWS)
        {
            if (time < blow - WIND - STRIKE) return 0;
            if (time < blow - STRIKE) return -smooth((time - (blow - WIND - STRIKE)) / WIND);
            if (time < blow) { float s = (time - (blow - STRIKE)) / STRIKE; return -1 + 2 * s * s; }
            if (time < blow + HOLD) return 1;
            if (time < blow + HOLD + .1F) return 1 - .45F * smooth((time - blow - HOLD) / .1F);
        }
        return .55F;
    }

    private static float trunk(float time)
    {
        float p = phase(time);
        return p < 0 ? .7F * p : p;
    }

    private static Vector3f fists(FirstBattleSignals.Spec spec, float time, Vector3f shoulder, Vec3 front)
    {
        Vector3f high = new Vector3f(shoulder).add(0, 17, 0).fma(-3, toF(front));
        Vector3f low = toF(core(spec, time));
        Vector3f rest = new Vector3f(low).add(0, 8, 0);
        float p = phase(time);
        if (p < 0) return new Vector3f(rest).lerp(high, -p);
        if (p < 1) return new Vector3f(high).lerp(low, p);
        return low;
    }

    // ------------------------------------------------------------ review log

    private static final boolean JOINT_LOG = Boolean.getBoolean("projectseele.finaleJointLogR58");
    private static int lastLogged = -1;

    private static void log(BakedGeoModel model, Matrix4f root, float time, Vector3f forward, double ground)
    {
        if (!JOINT_LOG || (int) (time * 20) == lastLogged) return;
        lastLogged = (int) (time * 20);
        StringBuilder row = new StringBuilder(String.format(java.util.Locale.ROOT, "R58 FINALE JOINTS t=%.2f", time));
        for (String side : new String[] {"l", "r"})
        {
            GeoBone thigh = model.getBone("leg_" + side).orElse(null), shin = model.getBone("shin_" + side).orElse(null),
                    foot = model.getBone("foot_" + side).orElse(null), arm = model.getBone("arm_" + side).orElse(null),
                    fore = model.getBone("forearm_" + side).orElse(null), hand = model.getBone("hand_" + side).orElse(null);
            if (thigh == null || shin == null || foot == null || arm == null || fore == null || hand == null) continue;
            Vector3f ankle = EvaRigTransforms.point(foot, EvaRigTransforms.pivot(foot), root);
            Quaternionf d = new Quaternionf(standingAnkleTurn[side.equals("l") ? 0 : 1]).invert().mul(relation(shin, foot, root)).normalize();
            row.append(String.format(java.util.Locale.ROOT, " kneeFace_%s=%.2f elbowFace_%s=%.2f ankle_%s=%.0f footY_%s=%.1f",
                    side, AnatomicalLimbR58.facingScore(thigh, shin, foot, root, forward, EvaRigTransforms.knee(shin)),
                    side, AnatomicalLimbR58.facingScore(arm, fore, hand, root, new Vector3f(forward).negate(), EvaRigTransforms.elbow(fore, side)),
                    side, Math.toDegrees(2 * Math.acos(Math.min(1, Math.abs(d.w)))), side, ankle.y - ground - standingAnkle));
        }
        Vec3[] other = FirstBattleAngelR58.body(time);
        GeoBone chest = model.getBone("torso_upper").orElse(null);
        if (other != null && chest != null)
        {
            Vector3f p = EvaRigTransforms.point(chest, EvaRigTransforms.pivot(chest), root);
            float closest = Float.MAX_VALUE;
            for (Vec3 q : other) closest = Math.min(closest, (float) q.distanceTo(new Vec3(p.x, p.y, p.z)));
            row.append(String.format(java.util.Locale.ROOT, " trunks=%.1f", closest));
        }
        com.projectseele.ProjectSeele.LOGGER.info(row.toString());
    }

    private static float smooth(float t)
    {
        t = Mth.clamp(t, 0, 1);
        return t * t * (3 - 2 * t);
    }

    private static Vector3f toF(Vec3 v) { return new Vector3f((float) v.x, (float) v.y, (float) v.z); }
}
