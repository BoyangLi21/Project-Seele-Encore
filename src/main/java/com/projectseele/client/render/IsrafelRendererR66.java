package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import com.projectseele.entity.IsrafelEntity;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import org.joml.Vector3f;

/**
 * R66: the Seventh Angel drawn from original geometry only (the private rig is never read). Units are blocks, feet at
 * the origin, front toward -z, about 60 tall like the hitbox: long thin legs, a narrow waist, a chest that widens into
 * broad shoulder plates, long arms ending in three claws, and a small head carrying a flat white mask face. The core
 * sits in the chest.
 * <p>
 * Episode 9's two-tone look: whole, the left side is ochre and the right side silver; after the split one half is
 * ochre and the other silver, so the two are told apart at a glance. A downed half lies on its back until it rises.
 */
public final class IsrafelRendererR66 extends EntityRenderer<IsrafelEntity>
{
    private static final float[] OCHRE = AngelMeshR66.rgb(.78F, .52F, .20F);
    private static final float[] OCHRE_DARK = AngelMeshR66.rgb(.55F, .33F, .12F);
    private static final float[] SILVER = AngelMeshR66.rgb(.74F, .76F, .80F);
    private static final float[] SILVER_DARK = AngelMeshR66.rgb(.48F, .50F, .56F);
    private static final float[] MASK = AngelMeshR66.rgb(.94F, .93F, .90F);
    private static final float[] MARK = AngelMeshR66.rgb(.06F, .05F, .06F);
    private static final float[] SOCKET = AngelMeshR66.rgb(.25F, .05F, .07F);
    private static final float[] CORE = AngelMeshR66.rgb(.96F, .10F, .10F);

    public IsrafelRendererR66(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 6;
    }

    @Override
    public ResourceLocation getTextureLocation(IsrafelEntity entity)
    {
        return AngelMeshR66.WHITE;
    }

    @Override
    public void render(IsrafelEntity actor, float yaw, float partial, PoseStack pose, MultiBufferSource buffers, int light)
    {
        float bodyYaw = Mth.rotLerp(partial, actor.yBodyRotO, actor.yBodyRot);
        float walk = actor.walkAnimation.position(partial), stride = Mth.clamp(actor.walkAnimation.speed(partial), 0, 1);
        float swing = actor.getAttackAnim(partial), time = actor.tickCount + partial;
        int half = actor.halfR66();
        float[] left = half == 2 ? SILVER : OCHRE, right = half == 1 ? OCHRE : SILVER;
        float[] leftDark = half == 2 ? SILVER_DARK : OCHRE_DARK, rightDark = half == 1 ? OCHRE_DARK : SILVER_DARK;

        VertexConsumer solid = buffers.getBuffer(RenderType.entityCutoutNoCull(AngelMeshR66.WHITE));
        pose.pushPose();
        pose.mulPose(Axis.YP.rotationDegrees(180 - bodyYaw));
        if (actor.downedR66())
        {
            // fallen on its back, the feet where they stood
            pose.translate(0, 2.5F, 0);
            pose.mulPose(Axis.XP.rotationDegrees(-78));
        }
        float breathe = Mth.sin(time * .06F) * .35F;

        // legs: hip, knee, ankle; the stride swings each leg about its hip
        for (int side : new int[]{-1, 1})
        {
            float[] colour = side < 0 ? left : right, dark = side < 0 ? leftDark : rightDark;
            float phase = walk * .32F + (side < 0 ? 0 : Mth.PI);
            float thigh = Mth.sin(phase) * .45F * stride, shin = Math.max(0, -Mth.cos(phase)) * .55F * stride;
            Vector3f hip = new Vector3f(side * 3.6F, 26, 0);
            Vector3f knee = offset(hip, 12.5F, thigh, side * .25F);
            Vector3f ankle = offset(knee, 11.5F, thigh - shin, 0);
            AngelMeshR66.loft(pose, solid, new AngelMeshR66.Ring[]{
                    new AngelMeshR66.Ring(hip, 2.6F, 2.6F, colour),
                    new AngelMeshR66.Ring(knee, 1.7F, 1.7F, dark),
                    new AngelMeshR66.Ring(ankle, 1.2F, 1.2F, colour)}, 10, light, true);
            // narrow pointed foot
            AngelMeshR66.ellipsoid(pose, solid, new Vector3f(ankle.x, ankle.y - 1.2F, ankle.z - 2.2F), 1.5F, 1F, 3.6F, dark, light, 6);
        }
        // pelvis, waist, chest and shoulder yoke, split in colour down the middle
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(-1.6F, 27.5F, 0), 4.2F, 3F, 3.4F, leftDark, light, 8);
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(1.6F, 27.5F, 0), 4.2F, 3F, 3.4F, rightDark, light, 8);
        for (int side : new int[]{-1, 1})
        {
            float[] colour = side < 0 ? left : right;
            AngelMeshR66.loft(pose, solid, new AngelMeshR66.Ring[]{
                    new AngelMeshR66.Ring(new Vector3f(side * 1.6F, 29, 0), 2F, 2.4F, colour),
                    new AngelMeshR66.Ring(new Vector3f(side * 2.6F, 37, -.3F), 3.4F, 3.6F + breathe * .2F, colour),
                    new AngelMeshR66.Ring(new Vector3f(side * 3.8F, 44, 0), 4.6F, 3.8F, colour),
                    new AngelMeshR66.Ring(new Vector3f(side * 3.2F, 47.5F, .3F), 3.2F, 2.6F, colour)}, 10, light, true);
            // broad shoulder plate with a raised fin
            AngelMeshR66.ellipsoid(pose, solid, new Vector3f(side * 10.5F, 46.5F + breathe, 0), 5.2F, 2.6F, 4.6F, side < 0 ? leftDark : rightDark, light, 8);
            AngelMeshR66.plate(pose, solid, new Vector3f(side * 8.5F, 48, -2.5F), new Vector3f(side * 13.5F, 53.5F + breathe, -.5F),
                    new Vector3f(side * 14, 52 + breathe, 2.5F), new Vector3f(side * 9, 48, 2.5F), colour, light);
            drawArm(pose, solid, light, side, colour, side < 0 ? leftDark : rightDark, swing, walk, stride, breathe);
        }
        // neck and head with the flat mask face
        AngelMeshR66.loft(pose, solid, new AngelMeshR66.Ring[]{
                new AngelMeshR66.Ring(new Vector3f(0, 47.5F, .3F), 1.6F, 1.6F, left),
                new AngelMeshR66.Ring(new Vector3f(0, 50.5F, .2F), 1.4F, 1.4F, right)}, 8, light, false);
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(-.9F, 54, .4F), 3.4F, 4.6F, 3.4F, left, light, 8);
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(.9F, 54, .4F), 3.4F, 4.6F, 3.4F, right, light, 8);
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(0, 54, -2.9F), 3.9F, 4.8F, .9F, MASK, light, 10);
        for (int side : new int[]{-1, 1})
            AngelMeshR66.ellipsoid(pose, solid, new Vector3f(side * 1.5F, 55.2F, -3.7F), .75F, 1.1F, .3F, MARK, light, 6);
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(0, 52.2F, -3.75F), 1.2F, .35F, .25F, MARK, light, 6);
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(0, 37, -3.2F), 2.9F, 2.9F, 1.4F, SOCKET, light, 8);

        VertexConsumer glow = buffers.getBuffer(RenderType.entityTranslucentEmissive(AngelMeshR66.WHITE));
        float pulse = actor.isDeadOrDying() ? .1F : actor.downedR66() ? .25F + .2F * Mth.sin(time * .9F) : .8F + .2F * Mth.sin(time * .16F);
        AngelMeshR66.ellipsoid(pose, glow, new Vector3f(0, 37, -3.9F), 2.2F, 2.2F, 1.6F, AngelMeshR66.mix(SOCKET, CORE, pulse),
                LightTexture.FULL_BRIGHT, 8);
        pose.popPose();
        super.render(actor, yaw, partial, pose, buffers, light);
    }

    /** One arm from the shoulder; the swing of an attack raises it forward and brings it down, claws first. */
    private static void drawArm(PoseStack pose, VertexConsumer out, int light, int side, float[] colour, float[] dark,
                                float swing, float walk, float stride, float breathe)
    {
        float strike = Mth.sin(swing * Mth.PI) * 1.6F;
        float sway = Mth.sin(walk * .32F + (side < 0 ? Mth.PI : 0)) * .25F * stride;
        Vector3f shoulder = new Vector3f(side * 11.5F, 45.5F + breathe, 0);
        Vector3f elbow = offset(shoulder, 12, sway + strike, side * .18F);
        Vector3f wrist = offset(elbow, 11, sway + strike * 1.15F + .12F, side * .05F);
        AngelMeshR66.loft(pose, out, new AngelMeshR66.Ring[]{
                new AngelMeshR66.Ring(shoulder, 1.9F, 1.9F, colour),
                new AngelMeshR66.Ring(elbow, 1.3F, 1.3F, dark),
                new AngelMeshR66.Ring(wrist, 1.1F, 1.1F, colour)}, 8, light, true);
        Vector3f down = new Vector3f(wrist).sub(elbow).normalize();
        for (int claw = -1; claw <= 1; claw++)
        {
            Vector3f base = new Vector3f(wrist).add(claw * .7F, 0, claw * .45F);
            Vector3f tip = new Vector3f(base).add(new Vector3f(down).mul(4.5F)).add(claw * .9F, 0, -.6F);
            AngelMeshR66.plate(pose, out,new Vector3f(base).add(-.35F, 0, 0), new Vector3f(base).add(.35F, 0, 0),
                    tip, tip, dark, light);
        }
    }

    /**
     * The point a limb segment of the given length reaches below its joint, turned forward by pitch (radians; positive
     * swings toward -z, the front) and outward by roll.
     */
    private static Vector3f offset(Vector3f joint, float length, float pitch, float roll)
    {
        float y = -Mth.cos(pitch) * Mth.cos(roll) * length;
        float z = -Mth.sin(pitch) * length;
        float x = Mth.sin(roll) * length;
        return new Vector3f(joint).add(x, y, z);
    }
}
