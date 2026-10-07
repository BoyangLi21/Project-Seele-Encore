package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;
import java.util.Arrays;

/** Cached rigid geometry emitted through the ordinary entity material and shadow pass. */
final class RigidMachineryPartR44
{
    private static final ResourceLocation PAINT = new ResourceLocation("projectseele", "textures/entity/machinery_paint_r44.png");
    private static final int STRIDE = 11;
    private final float[] vertices;
    private final float[] bounds;
    private final ResourceLocation texture;

    private RigidMachineryPartR44(float[] vertices, float[] bounds)
    {
        this(vertices, bounds, PAINT);
    }

    private RigidMachineryPartR44(float[] vertices, float[] bounds, ResourceLocation texture)
    {
        this.vertices = vertices;
        this.bounds = bounds;
        this.texture = texture;
    }

    /** Imported rigid triangles keep their original UVs and smooth vertex normals. */
    static RigidMachineryPartR44 textured(JsonArray encoded, ResourceLocation texture)
    {
        if (encoded.size() % 24 != 0) throw new IllegalArgumentException("Triangle XYZ/UV/normal layout required");
        float[] vertices = new float[encoded.size() / 24 * 44];
        float[] bounds = {Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY,
                Float.NEGATIVE_INFINITY, Float.NEGATIVE_INFINITY, Float.NEGATIVE_INFINITY};
        int cursor = 0;
        for (int triangle = 0; triangle < encoded.size(); triangle += 24)
        {
            for (int corner : new int[] {0, 1, 2, 2})
            {
                int offset = triangle + corner * 8;
                float[] source = new float[8];
                for (int i = 0; i < 8; i++)
                {
                    source[i] = encoded.get(offset + i).getAsFloat();
                    if (!Float.isFinite(source[i])) throw new IllegalArgumentException("Non-finite imported machinery");
                }
                for (int axis = 0; axis < 3; axis++)
                {
                    bounds[axis] = Math.min(bounds[axis], source[axis]);
                    bounds[axis + 3] = Math.max(bounds[axis + 3], source[axis]);
                }
                for (float value : new float[] {source[0], source[1], source[2], 1, 1, 1,
                        source[5], source[6], source[7], source[3], source[4]}) vertices[cursor++] = value;
            }
        }
        return new RigidMachineryPartR44(vertices, bounds, texture);
    }

    static RigidMachineryPartR44 triangles(JsonArray encoded)
    {
        if (encoded.size() % 18 != 0) throw new IllegalArgumentException("Triangle RGB layout required");
        Builder builder = new Builder();
        for (int i = 0; i < encoded.size(); i += 18)
        {
            Vec3 a = point(encoded, i), b = point(encoded, i + 6), c = point(encoded, i + 12);
            Vec3 normal = b.subtract(a).cross(c.subtract(a));
            if (normal.lengthSqr() < 1e-12) continue;
            normal = normal.normalize();
            builder.vertex(a, normal, encoded, i, 0, 0);
            builder.vertex(b, normal, encoded, i + 6, 1, 0);
            builder.vertex(c, normal, encoded, i + 12, 1, 1);
            builder.vertex(c, normal, encoded, i + 12, 1, 1);
        }
        return builder.finish();
    }

    private static Vec3 point(JsonArray data, int index)
    {
        return new Vec3(data.get(index).getAsDouble(), data.get(index + 1).getAsDouble(), data.get(index + 2).getAsDouble());
    }

    float[] bounds()
    {
        return bounds.clone();
    }

    void draw(PoseStack poses, MultiBufferSource buffers, int light)
    {
        TvCraneMeshWitnessR44.part(vertices,poses);
        if (RigidMachineryGpuR44.draw(this, vertices, texture, poses, buffers, light)) return;
        VertexConsumer out = buffers.getBuffer(ModelRenderTypesR49.solid(texture));
        var frame = poses.last();
        boolean reflected = frame.pose().determinant() < 0;
        Vector3f normal = new Vector3f();
        for (int quad = 0; quad < vertices.length; quad += STRIDE * 4)
        {
            for (int j = 0; j < 4; j++)
            {
                int index = quad + (reflected ? 3 - j : j) * STRIDE;
                normal.set(vertices[index + 6], vertices[index + 7], vertices[index + 8]);
                normal.mul(frame.normal()).normalize();
                out.vertex(frame.pose(), vertices[index], vertices[index + 1], vertices[index + 2])
                        .color(vertices[index + 3], vertices[index + 4], vertices[index + 5], 1)
                        .uv(vertices[index + 9], vertices[index + 10])
                        .overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light)
                        .normal(normal.x, normal.y, normal.z).endVertex();
            }
        }
    }

    static final class Builder
    {
        private float[] data = new float[4096];
        private int size;
        private final float[] box = {Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY,
                Float.NEGATIVE_INFINITY, Float.NEGATIVE_INFINITY, Float.NEGATIVE_INFINITY};

        void quad(Vec3 a, Vec3 b, Vec3 c, Vec3 d, int color)
        {
            Vec3 normal = b.subtract(a).cross(c.subtract(a));
            if (normal.lengthSqr() < 1e-12) return;
            normal = normal.normalize();
            float red = ((color >> 16) & 255) / 255F;
            float green = ((color >> 8) & 255) / 255F;
            float blue = (color & 255) / 255F;
            vertex(a, normal, red, green, blue, 0, 0);
            vertex(b, normal, red, green, blue, 1, 0);
            vertex(c, normal, red, green, blue, 1, 1);
            vertex(d, normal, red, green, blue, 0, 1);
        }

        private void vertex(Vec3 p, Vec3 normal, JsonArray source, int index, float u, float v)
        {
            vertex(p, normal, source.get(index + 3).getAsFloat() / 255,
                    source.get(index + 4).getAsFloat() / 255, source.get(index + 5).getAsFloat() / 255, u, v);
        }

        private void vertex(Vec3 p, Vec3 n, float red, float green, float blue, float u, float v)
        {
            if (size + STRIDE > data.length) data = Arrays.copyOf(data, data.length * 2);
            float[] values = {(float)p.x, (float)p.y, (float)p.z, red, green, blue, (float)n.x, (float)n.y, (float)n.z, u, v};
            for (int i = 0; i < values.length; i++)
            {
                if (!Float.isFinite(values[i])) throw new IllegalArgumentException("Non-finite machinery vertex");
                data[size++] = values[i];
            }
            box[0] = Math.min(box[0], (float)p.x); box[3] = Math.max(box[3], (float)p.x);
            box[1] = Math.min(box[1], (float)p.y); box[4] = Math.max(box[4], (float)p.y);
            box[2] = Math.min(box[2], (float)p.z); box[5] = Math.max(box[5], (float)p.z);
        }

        RigidMachineryPartR44 finish()
        {
            if (size == 0) Arrays.fill(box, 0);
            return new RigidMachineryPartR44(Arrays.copyOf(data, size), box.clone());
        }
    }
}
