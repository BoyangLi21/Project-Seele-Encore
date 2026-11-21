package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import com.projectseele.entity.MataraelEntity;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import org.joml.Vector3f;

/**
 * R66: the Ninth Angel drawn from original geometry only. Units are blocks, feet level at the origin: a round body
 * about 16 across carried 32 up on four long legs whose knees rise above the body, as a harvestman's do; a ring of
 * eye marks round the body and a cluster of them on the underside, where the acid falls from and where the core is.
 * The legs lift in turn as it walks.
 */
public final class MataraelRendererR66 extends EntityRenderer<MataraelEntity>
{
    private static final float[] SHELL = AngelMeshR66.rgb(.24F, .20F, .19F);
    private static final float[] BAND = AngelMeshR66.rgb(.36F, .30F, .26F);
    private static final float[] LEG = AngelMeshR66.rgb(.18F, .15F, .14F);
    private static final float[] JOINT = AngelMeshR66.rgb(.40F, .34F, .28F);
    private static final float[] EYE = AngelMeshR66.rgb(.86F, .82F, .70F);
    private static final float[] PUPIL = AngelMeshR66.rgb(.05F, .04F, .04F);
    private static final float[] SOCKET = AngelMeshR66.rgb(.25F, .05F, .07F);
    private static final float[] CORE = AngelMeshR66.rgb(.96F, .10F, .10F);
    private static final float[] ACID = AngelMeshR66.rgb(.72F, .86F, .18F);

    public MataraelRendererR66(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 8;
    }

    @Override
    public ResourceLocation getTextureLocation(MataraelEntity entity)
    {
        return AngelMeshR66.WHITE;
    }

    @Override
    public boolean shouldRender(MataraelEntity entity, Frustum frustum, double x, double y, double z)
    {
        // the legs reach far outside the box
        return entity.shouldRender(x, y, z) && frustum.isVisible(entity.getBoundingBox().inflate(26, 12, 26));
    }

    @Override
    public void render(MataraelEntity actor, float yaw, float partial, PoseStack pose, MultiBufferSource buffers, int light)
    {
        float bodyYaw = Mth.rotLerp(partial, actor.yBodyRotO, actor.yBodyRot);
        float walk = actor.walkAnimation.position(partial), stride = Mth.clamp(actor.walkAnimation.speed(partial) * 3, 0, 1);
        float time = actor.tickCount + partial, sway = Mth.sin(time * .05F) * .4F;
        VertexConsumer solid = buffers.getBuffer(RenderType.entityCutoutNoCull(AngelMeshR66.WHITE));
        pose.pushPose();
        pose.mulPose(Axis.YP.rotationDegrees(180 - bodyYaw));
        float body = (float) MataraelEntity.BODY_Y + sway;

        // body: a squat sphere in bands, darker on top
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(0, body, 0), 8, 6.2F, 8, SHELL, light, 12);
        AngelMeshR66.loft(pose, solid, new AngelMeshR66.Ring[]{
                new AngelMeshR66.Ring(new Vector3f(0, body - 1.2F, 0), 8.15F, 8.15F, BAND),
                new AngelMeshR66.Ring(new Vector3f(0, body + 1.2F, 0), 8.05F, 8.05F, BAND)}, 20, light, false);
        // the eye ring round the body
        for (int i = 0; i < 8; i++)
        {
            double a = Math.PI * 2 * i / 8;
            float x = (float) Math.cos(a) * 7.7F, z = (float) Math.sin(a) * 7.7F;
            AngelMeshR66.ellipsoid(pose, solid, new Vector3f(x, body + 2.6F, z), 1.4F, 1.1F, 1.4F, EYE, light, 6);
            AngelMeshR66.ellipsoid(pose, solid, new Vector3f(x * 1.04F, body + 2.6F, z * 1.04F), .6F, .6F, .6F, PUPIL, light, 5);
        }
        // underside eyes round the core, where the acid gathers
        for (int i = 0; i < 6; i++)
        {
            double a = Math.PI * 2 * i / 6 + .3;
            float x = (float) Math.cos(a) * 3.4F, z = (float) Math.sin(a) * 3.4F;
            AngelMeshR66.ellipsoid(pose, solid, new Vector3f(x, body - 5.4F, z), 1.1F, .6F, 1.1F, EYE, light, 6);
            float drip = (time * .05F + i * .37F) % 1;
            AngelMeshR66.ellipsoid(pose, solid, new Vector3f(x, body - 6.2F - drip * 1.6F, z), .35F, .5F + drip * .4F, .35F, ACID, LightTexture.FULL_BRIGHT, 4);
        }
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(0, body - 5.6F, 0), 2.6F, 1.1F, 2.6F, SOCKET, light, 8);

        // four long legs: root on the body, knee high above it, foot far out on the ground
        for (int leg = 0; leg < 4; leg++)
        {
            double a = Math.PI * .25 + Math.PI * .5 * leg;
            float c = (float) Math.cos(a), s = (float) Math.sin(a);
            float lift = Math.max(0, Mth.sin(walk * .22F + leg * Mth.HALF_PI)) * 3.5F * stride;
            float reach = 22 + Mth.sin(walk * .22F + leg * Mth.HALF_PI + Mth.HALF_PI) * 1.8F * stride;
            Vector3f root = new Vector3f(c * 6.5F, body + .5F, s * 6.5F);
            Vector3f knee = new Vector3f(c * 14, body + 12 + lift * .4F, s * 14);
            Vector3f ankle = new Vector3f(c * (reach - 2), 6 + lift, s * (reach - 2));
            Vector3f foot = new Vector3f(c * reach, lift, s * reach);
            AngelMeshR66.loft(pose, solid, new AngelMeshR66.Ring[]{
                    new AngelMeshR66.Ring(root, 1.3F, 1.3F, JOINT),
                    new AngelMeshR66.Ring(knee, .95F, .95F, LEG),
                    new AngelMeshR66.Ring(ankle, .7F, .7F, LEG),
                    new AngelMeshR66.Ring(foot, .35F, .35F, JOINT)}, 8, light, true);
            AngelMeshR66.ellipsoid(pose, solid, knee, 1.35F, 1.35F, 1.35F, JOINT, light, 6);
        }

        VertexConsumer glow = buffers.getBuffer(RenderType.entityTranslucentEmissive(AngelMeshR66.WHITE));
        float pulse = actor.isDeadOrDying() ? .1F : .75F + .25F * Mth.sin(time * .15F);
        AngelMeshR66.ellipsoid(pose, glow, new Vector3f(0, (float) MataraelEntity.CORE_Y + sway, 0), 1.9F, 1.1F, 1.9F,
                AngelMeshR66.mix(SOCKET, CORE, pulse), LightTexture.FULL_BRIGHT, 8);
        pose.popPose();
        super.render(actor, yaw, partial, pose, buffers, light);
    }
}
