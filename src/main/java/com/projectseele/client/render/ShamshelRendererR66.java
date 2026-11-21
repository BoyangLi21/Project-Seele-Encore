package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.entity.ShamshelEntity;
import com.projectseele.entity.ShamshelWhipMotion;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;

import java.util.List;

/**
 * R66: the Fourth Angel drawn from original geometry only. The body is authored in the whip rig's own units
 * (pixels, divided by 16, scaled by five) and placed with {@link ShamshelWhipMotion#bodyMatrix}, so the body
 * pitches and turns exactly as the whips and the server's whip contacts do. Nothing reads a model file.
 * <p>
 * The shape follows the episode-3 silhouette: an upright, banded arthropod body that tapers to a point below, a
 * broad shoulder yoke carrying the two whip roots, a hooded head with a dark visor and four eye marks, short
 * paired legs on the belly and the red core half buried in the chest.
 */
public final class ShamshelRendererR66 extends EntityRenderer<ShamshelEntity>
{
    private static final float[] BODY = AngelMeshR66.rgb(.52F, .16F, .30F);
    private static final float[] BAND = AngelMeshR66.rgb(.74F, .40F, .48F);
    private static final float[] HOOD = AngelMeshR66.rgb(.60F, .21F, .36F);
    private static final float[] VISOR = AngelMeshR66.rgb(.10F, .05F, .08F);
    private static final float[] EYE = AngelMeshR66.rgb(.02F, .02F, .02F);
    private static final float[] SOCKET = AngelMeshR66.rgb(.28F, .07F, .12F);
    private static final float[] CORE = AngelMeshR66.rgb(.95F, .08F, .10F);
    private static final float[] WHIP = AngelMeshR66.rgb(.96F, .72F, .96F);

    public ShamshelRendererR66(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 4.5F;
    }

    @Override
    public boolean shouldRender(ShamshelEntity entity, Frustum frustum, double x, double y, double z)
    {
        if (!entity.shouldRender(x, y, z)) return false;
        // The whips reach about 26 blocks from the shoulders.
        AABB box = entity.getBoundingBox().inflate(30, 6, 30);
        return frustum.isVisible(box);
    }

    @Override
    public void render(ShamshelEntity actor, float yaw, float partial, PoseStack pose, MultiBufferSource buffers, int light)
    {
        float age = actor.sweepAge(partial);
        Vec3 origin = actor.getPosition(partial);
        Matrix4f body = ShamshelWhipMotion.bodyMatrix(actor, age, partial);
        Matrix4f local = new Matrix4f().translation((float) -origin.x, (float) -origin.y, (float) -origin.z).mul(body);

        VertexConsumer solid = buffers.getBuffer(RenderType.entityCutoutNoCull(AngelMeshR66.WHITE));
        pose.pushPose();
        pose.mulPoseMatrix(local);
        pose.scale(1 / 16F, 1 / 16F, 1 / 16F);
        float time = actor.tickCount + partial;
        drawBody(pose, solid, light, time);
        VertexConsumer glow = buffers.getBuffer(RenderType.entityTranslucentEmissive(AngelMeshR66.WHITE));
        float pulse = .85F + .15F * Mth.sin(time * .18F);
        // under the knife the core flickers and darkens toward the end of the hold
        float pin = actor.pinProgressR66();
        if (pin > 0) pulse = (1 - pin) * (.55F + .45F * Mth.sin(time * 2.1F)) + .05F;
        float[] core = AngelMeshR66.mix(SOCKET, CORE, actor.isDeadOrDying() ? .1F : pulse);
        AngelMeshR66.ellipsoid(pose, glow, new Vector3f(0, 128, -31), 9.5F, 9.5F, 8.5F, core, LightTexture.FULL_BRIGHT, 8);
        pose.popPose();

        drawWhips(actor, age, partial, origin, pose, glow);
        ShamshelWhipLight.render(actor, partial, pose, buffers);
        super.render(actor, yaw, partial, pose, buffers, light);
    }

    private static void drawBody(PoseStack pose, VertexConsumer out, int light, float time)
    {
        // banded trunk, tail point at the bottom, forward lean at the top
        float[][] trunk = {{6, 6, 6, 6}, {25, 14, 12, 4}, {45, 22, 17, 2}, {65, 27, 20, 0}, {85, 29, 21, -1},
                {105, 31, 22, -2}, {125, 36, 24, -3}, {145, 44, 26, -5}, {156, 46, 26, -6}};
        AngelMeshR66.Ring[] rings = new AngelMeshR66.Ring[trunk.length];
        for (int i = 0; i < trunk.length; i++)
        {
            float sway = Mth.sin(time * .045F - i * .5F) * .8F * (1 - i / (float) trunk.length);
            rings[i] = new AngelMeshR66.Ring(new Vector3f(sway, trunk[i][0], trunk[i][3]), trunk[i][1], trunk[i][2], i % 2 == 0 ? BAND : BODY);
        }
        AngelMeshR66.loft(pose, out, rings, 14, light, true);
        // shoulder yoke and the two whip roots (the rig's measured pivots sit at x ±52, y 155.6, z -11.7)
        AngelMeshR66.ellipsoid(pose, out, new Vector3f(0, 153, -8), 58, 15, 27, BODY, light, 8);
        for (int side : new int[]{-1, 1})
            AngelMeshR66.ellipsoid(pose, out, new Vector3f(side * 52, 155.6F, -11.7F), 11, 11, 11, BAND, light, 6);
        // hooded head with the dark visor across its front
        AngelMeshR66.ellipsoid(pose, out, new Vector3f(0, 178, -14), 40, 23, 31, HOOD, light, 10);
        AngelMeshR66.ellipsoid(pose, out, new Vector3f(0, 170, -38), 31, 13, 7, VISOR, light, 8);
        for (int side : new int[]{-1, 1})
        {
            AngelMeshR66.ellipsoid(pose, out, new Vector3f(side * 10, 176, -44.5F), 3.8F, 3.8F, 2F, EYE, light, 5);
            AngelMeshR66.ellipsoid(pose, out, new Vector3f(side * 22, 167, -42.5F), 3.2F, 3.2F, 2F, EYE, light, 5);
        }
        // the socket the core sits in
        AngelMeshR66.ellipsoid(pose, out, new Vector3f(0, 128, -24), 14, 14, 9, SOCKET, light, 8);
        // short paired legs down the belly
        for (int pair = 0; pair < 5; pair++)
        {
            float y = 112 - pair * 15;
            float bend = Mth.sin(time * .09F + pair) * 2;
            for (int side : new int[]{-1, 1})
            {
                AngelMeshR66.Ring[] leg = {
                        new AngelMeshR66.Ring(new Vector3f(side * 17, y, -14), 3.4F, 3.4F, BODY),
                        new AngelMeshR66.Ring(new Vector3f(side * 26, y - 9 + bend, -25), 2.8F, 2.8F, BAND),
                        new AngelMeshR66.Ring(new Vector3f(side * 23, y - 22 + bend, -31), 1.8F, 1.8F, BODY)};
                AngelMeshR66.loft(pose, out, leg, 6, light, true);
            }
        }
    }

    private static void drawWhips(ShamshelEntity actor, float age, float partial, Vec3 origin, PoseStack pose, VertexConsumer out)
    {
        for (int side : new int[]{-1, 1})
        {
            List<Vec3> chain = ShamshelWhipMotion.points(actor, side, age, partial);
            Vector3f[] path = new Vector3f[chain.size()];
            for (int i = 0; i < path.length; i++) path[i] = chain.get(i).subtract(origin).toVector3f();
            boolean active = actor.isSweeping() && side == actor.sweepSide();
            float[] colour = active ? WHIP : AngelMeshR66.mix(WHIP, AngelMeshR66.rgb(.62F, .30F, .55F), .45F);
            AngelMeshR66.ribbon(pose, out, path, active ? .85F : .6F, new Vector3f(0, 1, 0), colour, LightTexture.FULL_BRIGHT);
            AngelMeshR66.ribbon(pose, out, path, active ? .85F : .6F, new Vector3f(1, 0, 0), colour, LightTexture.FULL_BRIGHT);
            if (side == actor.sweepSide() && actor.level().getEntity(actor.wrapTargetIdR66()) instanceof net.minecraft.world.entity.LivingEntity held)
                drawWrap(path[path.length - 1], held, partial, origin, pose, out, actor.tickCount + partial);
        }
    }

    /** The whip runs from its tip to the held unit and coils twice round its lower leg. */
    private static void drawWrap(Vector3f tip, net.minecraft.world.entity.LivingEntity held, float partial, Vec3 origin, PoseStack pose, VertexConsumer out, float time)
    {
        Vec3 at = held.getPosition(partial).subtract(origin);
        float r = held.getBbWidth() * .22F;
        Vector3f[] coil = new Vector3f[26];
        coil[0] = tip;
        for (int i = 1; i < coil.length; i++)
        {
            double a = i * .55 + time * .05;
            coil[i] = new Vector3f((float) (at.x + Math.cos(a) * r), (float) (at.y + 3 + i * .35), (float) (at.z + Math.sin(a) * r));
        }
        AngelMeshR66.ribbon(pose, out, coil, .7F, new Vector3f(0, 1, 0), WHIP, LightTexture.FULL_BRIGHT);
        AngelMeshR66.ribbon(pose, out, coil, .7F, new Vector3f(1, 0, 0), WHIP, LightTexture.FULL_BRIGHT);
    }

    @Override
    public ResourceLocation getTextureLocation(ShamshelEntity entity)
    {
        return AngelMeshR66.WHITE;
    }
}
