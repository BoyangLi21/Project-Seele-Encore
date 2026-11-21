package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.ProjectSeele;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/**
 * Original direct geometry for the R66 Angels: lofted tubes, ellipsoids and plates with real normals, so the
 * bodies take the world's light. Nothing here reads a model file; every shape is built from numbers in code.
 */
final class AngelMeshR66
{
    /** A flat white image; every colour comes from the vertex. */
    static final ResourceLocation WHITE = new ResourceLocation(ProjectSeele.MODID, "textures/entity/angel_white_r66.png");

    record Ring(Vector3f centre, float rx, float rz, float[] colour) {}

    /**
     * A tube through rings. Each ring lies in the plane perpendicular to the local path direction; rx is the
     * half-width across the path's side axis and rz along its forward axis.
     */
    static void loft(PoseStack pose, VertexConsumer out, Ring[] rings, int sides, int light, boolean capEnds)
    {
        int n = rings.length;
        Vector3f[][] p = new Vector3f[n][sides];
        Vector3f[][] nm = new Vector3f[n][sides];
        Vector3f lastSide = null;
        for (int i = 0; i < n; i++)
        {
            Vector3f prev = rings[Math.max(0, i - 1)].centre(), next = rings[Math.min(n - 1, i + 1)].centre();
            Vector3f axis = new Vector3f(next).sub(prev);
            if (axis.lengthSquared() < 1e-8F) axis.set(0, 1, 0);
            axis.normalize();
            Vector3f side = lastSide == null ? perpendicular(axis) : new Vector3f(lastSide).sub(new Vector3f(axis).mul(lastSide.dot(axis)));
            if (side.lengthSquared() < 1e-8F) side = perpendicular(axis);
            side.normalize();
            lastSide = side;
            Vector3f forward = new Vector3f(axis).cross(side).normalize();
            for (int k = 0; k < sides; k++)
            {
                double a = Math.PI * 2 * k / sides;
                float c = (float) Math.cos(a), s = (float) Math.sin(a);
                Vector3f offset = new Vector3f(side).mul(c * rings[i].rx()).add(new Vector3f(forward).mul(s * rings[i].rz()));
                p[i][k] = new Vector3f(rings[i].centre()).add(offset);
                // an ellipse's normal, not its radius vector
                nm[i][k] = new Vector3f(side).mul(c / Math.max(1e-4F, rings[i].rx())).add(new Vector3f(forward).mul(s / Math.max(1e-4F, rings[i].rz()))).normalize();
            }
        }
        for (int i = 0; i + 1 < n; i++)
            for (int k = 0; k < sides; k++)
            {
                int k1 = (k + 1) % sides;
                quad(pose, out, p[i][k], p[i][k1], p[i + 1][k1], p[i + 1][k], nm[i][k], nm[i][k1], nm[i + 1][k1], nm[i + 1][k],
                        rings[i].colour(), rings[i + 1].colour(), light);
            }
        if (capEnds)
        {
            cap(pose, out, rings[0], p[0], true, light);
            cap(pose, out, rings[n - 1], p[n - 1], false, light);
        }
    }

    private static void cap(PoseStack pose, VertexConsumer out, Ring ring, Vector3f[] edge, boolean start, int light)
    {
        Vector3f centre = ring.centre();
        Vector3f normal = new Vector3f(edge[1]).sub(edge[0]).cross(new Vector3f(edge[2]).sub(edge[0])).normalize();
        if (start) normal.negate();
        for (int k = 0; k < edge.length; k++)
        {
            Vector3f a = edge[k], b = edge[(k + 1) % edge.length];
            if (start) quad(pose, out, centre, b, a, centre, normal, normal, normal, normal, ring.colour(), ring.colour(), light);
            else quad(pose, out, centre, a, b, centre, normal, normal, normal, normal, ring.colour(), ring.colour(), light);
        }
    }

    /** An ellipsoid of half-axes rx, ry, rz around a centre. */
    static void ellipsoid(PoseStack pose, VertexConsumer out, Vector3f centre, float rx, float ry, float rz, float[] colour, int light, int bands)
    {
        int sides = bands * 2;
        for (int i = 0; i < bands; i++)
        {
            double t0 = Math.PI * i / bands - Math.PI / 2, t1 = Math.PI * (i + 1) / bands - Math.PI / 2;
            for (int k = 0; k < sides; k++)
            {
                double a0 = Math.PI * 2 * k / sides, a1 = Math.PI * 2 * (k + 1) / sides;
                Vector3f u00 = unit(t0, a0), u01 = unit(t0, a1), u11 = unit(t1, a1), u10 = unit(t1, a0);
                quad(pose, out, onEllipsoid(centre, u00, rx, ry, rz), onEllipsoid(centre, u10, rx, ry, rz), onEllipsoid(centre, u11, rx, ry, rz), onEllipsoid(centre, u01, rx, ry, rz),
                        normalOf(u00, rx, ry, rz), normalOf(u10, rx, ry, rz), normalOf(u11, rx, ry, rz), normalOf(u01, rx, ry, rz), colour, colour, light);
            }
        }
    }

    /** A thin plate through four corners, drawn on both faces. */
    static void plate(PoseStack pose, VertexConsumer out, Vector3f a, Vector3f b, Vector3f c, Vector3f d, float[] colour, int light)
    {
        Vector3f n = new Vector3f(b).sub(a).cross(new Vector3f(d).sub(a)).normalize();
        Vector3f back = new Vector3f(n).negate();
        quad(pose, out, a, b, c, d, n, n, n, n, colour, colour, light);
        quad(pose, out, a, d, c, b, back, back, back, back, colour, colour, light);
    }

    /** A flat ribbon along a polyline, facing the given up direction, both faces. */
    static void ribbon(PoseStack pose, VertexConsumer out, Vector3f[] path, float halfWidth, Vector3f up, float[] colour, int light)
    {
        for (int i = 0; i + 1 < path.length; i++)
        {
            Vector3f axis = new Vector3f(path[i + 1]).sub(path[i]);
            if (axis.lengthSquared() < 1e-8F) continue;
            Vector3f side = new Vector3f(axis).cross(up);
            if (side.lengthSquared() < 1e-8F) side = perpendicular(axis.normalize());
            side.normalize().mul(halfWidth);
            plate(pose, out, new Vector3f(path[i]).sub(side), new Vector3f(path[i]).add(side), new Vector3f(path[i + 1]).add(side), new Vector3f(path[i + 1]).sub(side), colour, light);
        }
    }

    static float[] rgb(float r, float g, float b) { return new float[]{r, g, b, 1}; }

    static float[] mix(float[] a, float[] b, float t)
    {
        return new float[]{a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t};
    }

    private static Vector3f unit(double lat, double lon)
    {
        return new Vector3f((float) (Math.cos(lat) * Math.cos(lon)), (float) Math.sin(lat), (float) (Math.cos(lat) * Math.sin(lon)));
    }

    private static Vector3f onEllipsoid(Vector3f c, Vector3f u, float rx, float ry, float rz)
    {
        return new Vector3f(c.x + u.x * rx, c.y + u.y * ry, c.z + u.z * rz);
    }

    private static Vector3f normalOf(Vector3f u, float rx, float ry, float rz)
    {
        return new Vector3f(u.x / Math.max(1e-4F, rx), u.y / Math.max(1e-4F, ry), u.z / Math.max(1e-4F, rz)).normalize();
    }

    private static Vector3f perpendicular(Vector3f axis)
    {
        Vector3f helper = Math.abs(axis.y) < .9F ? new Vector3f(0, 1, 0) : new Vector3f(1, 0, 0);
        return new Vector3f(axis).cross(helper).normalize();
    }

    private static void quad(PoseStack pose, VertexConsumer out, Vector3f a, Vector3f b, Vector3f c, Vector3f d,
                             Vector3f na, Vector3f nb, Vector3f nc, Vector3f nd, float[] k0, float[] k1, int light)
    {
        Matrix4f m = pose.last().pose();
        Matrix3f n = pose.last().normal();
        vertex(out, m, n, a, na, k0, 0, 0, light);
        vertex(out, m, n, b, nb, k0, 1, 0, light);
        vertex(out, m, n, c, nc, k1, 1, 1, light);
        vertex(out, m, n, d, nd, k1, 0, 1, light);
    }

    private static void vertex(VertexConsumer out, Matrix4f m, Matrix3f n, Vector3f p, Vector3f normal, float[] k, float u, float v, int light)
    {
        out.vertex(m, p.x, p.y, p.z).color(k[0], k[1], k[2], k[3]).uv(u, v).overlayCoords(OverlayTexture.NO_OVERLAY)
                .uv2(light).normal(n, normal.x, normal.y, normal.z).endVertex();
    }

    private AngelMeshR66() {}
}
