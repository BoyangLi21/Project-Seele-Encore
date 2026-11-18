package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.client.HangarCoolantVisualR52;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.renderer.layer.GeoRenderLayer;

import java.util.Set;

/** Small rivulets advance downhill within actual triangles of the newly exposed armour. */
final class HangarLclRunoff extends GeoRenderLayer<EvaUnit01Entity>
{
    private static final Set<String> ARMOUR = Set.of("head", "torso_upper", "torso_lower",
            "arm_l", "arm_r", "forearm_l", "forearm_r", "leg_l", "leg_r", "shin_l", "shin_r", "foot_l", "foot_r");
    private final EvaUnit01Renderer renderer;
    private final Vector3f[] points = {new Vector3f(), new Vector3f(), new Vector3f()};
    private final org.joml.Matrix3f localFromWorld = new org.joml.Matrix3f();
    private final Vector3f fall = new Vector3f();
    private final Vector3f top = new Vector3f(), bottom = new Vector3f(), across = new Vector3f(), normal = new Vector3f();

    HangarLclRunoff(EvaUnit01Renderer renderer)
    {
        super(renderer);
        this.renderer = renderer;
    }

    @Override public void renderForBone(PoseStack poses, EvaUnit01Entity eva, GeoBone bone, RenderType type,
                                        MultiBufferSource buffers, VertexConsumer ignored, float partial, int light, int overlay)
    {
        var tank = HangarCoolantVisualR52.tank(eva.getUnitVariant());
        if (tank == null || !tank.draining() || eva.isExperimentalUnit() || bone.isHidden() || !ARMOUR.contains(bone.getName())
                || Math.abs(eva.getX() - tank.gantry.getX()) > 7 || Math.abs(eva.getZ() - tank.gantry.getZ()) > 8
                || Math.abs(eva.getY() - tank.bounds.floor()) > 50 || ShaderShadowPassR44.active()) return;
        var mesh = LocalTriangleMeshLayer.partView(EvaUnit01Renderer.meshResourceForEntity(eva), bone.getName());
        if (mesh == null) return;
        var pose = poses.last();
        var world = renderer.renderedMeshTransform(pose.pose(), eva, partial);
        float surface = tank.surface(partial), ceiling = tank.wetCeiling();
        localFromWorld.set(world).invert().transform(fall.set(0, -1, 0));
        int triangles = mesh.count() / 3, step = Math.max(1, triangles / 30);
        VertexConsumer out = null;
        for (int tri = step / 2; tri < triangles; tri += step)
        {
            for (int j = 0; j < 3; j++)
            {
                int v = tri * 3 + j;
                points[j].set(mesh.x(v), mesh.y(v), mesh.z(v));
            }
            int high = 0, low = 0;
            for (int j = 1; j < 3; j++)
            {
                if (height(world, points[j]) > height(world, points[high])) high = j;
                if (height(world, points[j]) < height(world, points[low])) low = j;
            }
            float exposed = height(world, points[high]) - surface;
            if (high == low || exposed < .1F || exposed > 9 || height(world, points[low]) > ceiling) continue;
            float span = height(world, points[high]) - height(world, points[low]);
            if (span < .08F) continue;
            // Stay inside the face as the head advances. Offset along its authored normal to clear the armour.
            int mid = 3 - high - low, vertex = tri * 3 * mesh.stride();
            float[] values = mesh.vertices();
            normal.set(-values[vertex + 5], values[vertex + 6], values[vertex + 7]);
            float phase = Mth.frac((eva.tickCount + partial) * .045F + tri * .381966F);
            float head = .15F + phase * .72F;
            float tail = Math.max(.04F, head - Math.min(.57F, .85F / span));
            top.set(points[high]).lerp(points[low], tail).lerp(points[mid], .17F).fma(.012F, normal);
            bottom.set(points[high]).lerp(points[low], head).lerp(points[mid], .17F).fma(.012F, normal);
            across.set(points[mid]).sub(top);
            across.mul(Math.min(.09F, .038F / Math.max(.001F, across.length())));
            int alpha = (int)(185 * (1 - exposed / 9) * Mth.sin(phase * Mth.PI));
            if (alpha < 6) continue;
            if (out == null) out = buffers.getBuffer(HangarLclSurface.MATERIAL);
            vertex(out, pose, top, -1F, alpha / 3, light);
            vertex(out, pose, top, 1F, alpha / 3, light);
            vertex(out, pose, bottom, .55F, alpha, light);
            vertex(out, pose, bottom, -.55F, alpha, light);
            if ((tri / step) % 4 == 0)
            {
                // A bead spills from the lower edge. The free tail follows world gravity even on
                // inclined shoulder plates, stops at the waterline, and is hidden by intervening armour.
                top.set(points[low]).lerp(points[mid], .10F).fma(.015F, normal);
                float drop = Math.min(height(world, top) - surface, .25F + 1.65F * phase);
                if (drop < .12F) continue;
                bottom.set(top).fma(drop, fall);
                vertex(out, pose, top, -.8F, alpha, light);
                vertex(out, pose, top, .8F, alpha, light);
                vertex(out, pose, bottom, .20F, alpha / 2, light);
                vertex(out, pose, bottom, -.20F, alpha / 2, light);
            }
        }
    }

    private static float height(Matrix4f transform, Vector3f p)
    {
        return transform.m01() * p.x + transform.m11() * p.y + transform.m21() * p.z + transform.m31();
    }

    private void vertex(VertexConsumer out, PoseStack.Pose pose, Vector3f p, float side, int alpha, int light)
    {
        out.vertex(pose.pose(), p.x + across.x * side, p.y + across.y * side, p.z + across.z * side)
                .color(249, 164, 74, alpha).uv(.5F, .5F).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light)
                .normal(pose.normal(), normal.x, normal.y, normal.z).endVertex();
    }
}