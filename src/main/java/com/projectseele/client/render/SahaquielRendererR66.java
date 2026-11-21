package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import com.projectseele.entity.SahaquielEntity;
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
 * R66: the Tenth Angel drawn from original geometry only. Units are blocks, the origin at the middle of its underside:
 * a broad flat body with one great eye on the underside, looking down at the city it falls on, the core in the pupil;
 * long membranes spread to both sides and shorter ones fore and aft, ripples running along them; eye marks on the
 * membranes. While it falls, a hot orange glow wraps it.
 */
public final class SahaquielRendererR66 extends EntityRenderer<SahaquielEntity>
{
    private static final float[] SKIN = AngelMeshR66.rgb(.86F, .42F, .20F);
    private static final float[] SKIN_DARK = AngelMeshR66.rgb(.52F, .20F, .12F);
    private static final float[] MEMBRANE = AngelMeshR66.rgb(.92F, .55F, .36F);
    private static final float[] WHITE = AngelMeshR66.rgb(.95F, .93F, .88F);
    private static final float[] BLACK = AngelMeshR66.rgb(.05F, .04F, .04F);
    private static final float[] SOCKET = AngelMeshR66.rgb(.25F, .05F, .07F);
    private static final float[] CORE = AngelMeshR66.rgb(.96F, .10F, .10F);
    private static final float[] HEAT = AngelMeshR66.rgb(1F, .45F, .12F);

    public SahaquielRendererR66(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 0;
    }

    @Override
    public ResourceLocation getTextureLocation(SahaquielEntity entity)
    {
        return AngelMeshR66.WHITE;
    }

    @Override
    public boolean shouldRender(SahaquielEntity entity, Frustum frustum, double x, double y, double z)
    {
        return frustum.isVisible(entity.getBoundingBox().inflate(60, 10, 60));
    }

    @Override
    public void render(SahaquielEntity actor, float yaw, float partial, PoseStack pose, MultiBufferSource buffers, int light)
    {
        float time = actor.tickCount + partial;
        boolean falling = actor.stateR66() == SahaquielEntity.FALL;
        int lit = LightTexture.FULL_BRIGHT;
        VertexConsumer solid = buffers.getBuffer(RenderType.entityCutoutNoCull(AngelMeshR66.WHITE));
        pose.pushPose();
        pose.mulPose(Axis.YP.rotationDegrees(180 - Mth.rotLerp(partial, actor.yRotO, actor.getYRot())));

        // the body: a flat lens, darker toward the rim
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(0, 5, 0), 17, 4.6F, 14, SKIN, lit, 14);
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(0, 6.5F, 0), 11, 3.4F, 9, SKIN_DARK, lit, 10);
        // the great eye on the underside, the core in its pupil
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(0, 1.2F, 0), 9, 1.1F, 6.2F, WHITE, lit, 12);
        AngelMeshR66.ellipsoid(pose, solid, new Vector3f(0, .8F, 0), 3.6F, .9F, 3.6F, BLACK, lit, 10);
        // membranes: two long ones to the sides, two short ones fore and aft
        for (int side : new int[]{-1, 1})
        {
            membrane(pose, solid, lit, side, 0, 60, 9, time);
            membrane(pose, solid, lit, side, 1, 26, 6, time + 20);
        }

        VertexConsumer glow = buffers.getBuffer(RenderType.entityTranslucentEmissive(AngelMeshR66.WHITE));
        float pulse = actor.isDeadOrDying() ? .1F : .75F + .25F * Mth.sin(time * .18F);
        AngelMeshR66.ellipsoid(pose, glow, new Vector3f(0, .4F, 0), 1.9F, .7F, 1.9F, AngelMeshR66.mix(SOCKET, CORE, pulse), lit, 8);
        if (falling)
        {
            float flicker = .55F + .25F * Mth.sin(time * 1.3F);
            AngelMeshR66.ellipsoid(pose, glow, new Vector3f(0, 2, 0), 19, 6, 16, AngelMeshR66.mix(SKIN_DARK, HEAT, flicker), lit, 12);
        }
        pose.popPose();
        super.render(actor, yaw, partial, pose, buffers, light);
    }

    /**
     * One membrane strip as a run of quads out from the rim. axis 0: along x (to the side); 1: along z (fore or aft).
     * A ripple runs out along it; three eye marks sit on its upper face.
     */
    private static void membrane(PoseStack pose, VertexConsumer out, int light, int side, int axis, float length, float width, float time)
    {
        int segments = 8;
        Vector3f[] lead = new Vector3f[segments + 1], trail = new Vector3f[segments + 1];
        for (int i = 0; i <= segments; i++)
        {
            float f = i / (float) segments, along = (axis == 0 ? 14 : 11) + f * length;
            float half = width * (1 - f * .75F), y = 4 + Mth.sin(time * .09F - f * 3) * 2.2F * f - f * f * 3;
            lead[i] = axis == 0 ? new Vector3f(side * along, y, -half) : new Vector3f(-half, y, side * along);
            trail[i] = axis == 0 ? new Vector3f(side * along, y, half) : new Vector3f(half, y, side * along);
        }
        for (int i = 0; i < segments; i++)
            AngelMeshR66.plate(pose, out, lead[i], lead[i + 1], trail[i + 1], trail[i],
                    AngelMeshR66.mix(MEMBRANE, SKIN_DARK, i / (float) segments * .6F), light);
        for (int i = 2; i <= 6; i += 2)
        {
            Vector3f c = new Vector3f(lead[i]).add(trail[i]).mul(.5F).add(0, .4F, 0);
            AngelMeshR66.ellipsoid(pose, out, c, 1.6F, .4F, 1.6F, WHITE, light, 6);
            AngelMeshR66.ellipsoid(pose, out, new Vector3f(c).add(0, .25F, 0), .7F, .3F, .7F, BLACK, light, 5);
        }
    }
}
