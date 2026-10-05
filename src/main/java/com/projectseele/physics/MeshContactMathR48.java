package com.projectseele.physics;

import com.projectseele.combat.BladeSweepClipR45;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Surface math for actual triangles; radius is the existing weapon thickness. */
public final class MeshContactMathR48
{
    public record Hit(double time, Vec3 point) {}
    private record Pair(Vec3 first, Vec3 second) {}
    private MeshContactMathR48() {}

    private static double clamp(double value) { return Math.max(0, Math.min(1, value)); }

    private static Vec3 closestSegment(Vec3 point, Vec3 a, Vec3 b)
    {
        Vec3 edge = b.subtract(a); double squared = edge.lengthSqr();
        return squared < 1e-18 ? a : a.add(edge.scale(clamp(point.subtract(a).dot(edge) / squared)));
    }

    public static Vec3 closestTriangle(Vec3 point, Vec3 a, Vec3 b, Vec3 c)
    {
        Vec3 ab = b.subtract(a), ac = c.subtract(a);
        if (ab.cross(ac).lengthSqr() < 1e-20)
        {
            Vec3 first = closestSegment(point, a, b), second = closestSegment(point, b, c), third = closestSegment(point, c, a);
            Vec3 best = first.distanceToSqr(point) < second.distanceToSqr(point) ? first : second;
            return best.distanceToSqr(point) < third.distanceToSqr(point) ? best : third;
        }
        Vec3 ap = point.subtract(a); double d1 = ab.dot(ap), d2 = ac.dot(ap);
        if (d1 <= 0 && d2 <= 0) return a;
        Vec3 bp = point.subtract(b); double d3 = ab.dot(bp), d4 = ac.dot(bp);
        if (d3 >= 0 && d4 <= d3) return b;
        double vc = d1 * d4 - d3 * d2;
        if (vc <= 0 && d1 >= 0 && d3 <= 0) return a.add(ab.scale(d1 / (d1 - d3)));
        Vec3 cp = point.subtract(c); double d5 = ab.dot(cp), d6 = ac.dot(cp);
        if (d6 >= 0 && d5 <= d6) return c;
        double vb = d5 * d2 - d1 * d6;
        if (vb <= 0 && d2 >= 0 && d6 <= 0) return a.add(ac.scale(d2 / (d2 - d6)));
        double va = d3 * d6 - d5 * d4;
        if (va <= 0 && d4 - d3 >= 0 && d5 - d6 >= 0) return b.add(c.subtract(b).scale((d4 - d3) / ((d4 - d3) + (d5 - d6))));
        double inverse = 1 / (va + vb + vc);
        return a.add(ab.scale(vb * inverse)).add(ac.scale(vc * inverse));
    }

    private static Hit segmentTriangle(Vec3 from, Vec3 to, Vec3 a, Vec3 b, Vec3 c)
    {
        Vec3 direction = to.subtract(from), edge1 = b.subtract(a), edge2 = c.subtract(a), cross = direction.cross(edge2);
        double determinant = edge1.dot(cross); if (Math.abs(determinant) < 1e-14) return null;
        Vec3 offset = from.subtract(a); double u = offset.dot(cross) / determinant;
        if (u < -1e-9 || u > 1 + 1e-9) return null;
        Vec3 q = offset.cross(edge1); double v = direction.dot(q) / determinant;
        if (v < -1e-9 || u + v > 1 + 1e-9) return null;
        double time = edge2.dot(q) / determinant;
        return time < -1e-9 || time > 1 + 1e-9 ? null : new Hit(clamp(time), from.lerp(to, clamp(time)));
    }

    private static Hit earlier(Hit a, Hit b) { return b != null && (a == null || b.time() < a.time()) ? b : a; }

    private static Hit sphere(Vec3 from, Vec3 to, Vec3 centre, double radius)
    {
        Vec3 direction = to.subtract(from), offset = from.subtract(centre); double a = direction.lengthSqr();
        if (a < 1e-20) return null;
        double b = offset.dot(direction), c = offset.lengthSqr() - radius * radius, discriminant = b * b - a * c;
        if (discriminant < 0) return null;
        double time = (-b - Math.sqrt(discriminant)) / a;
        return time >= 0 && time <= 1 ? new Hit(time, centre) : null;
    }

    private static Hit edgeCapsule(Vec3 from, Vec3 to, Vec3 a, Vec3 b, double radius)
    {
        Vec3 edge = b.subtract(a), direction = to.subtract(from), offset = from.subtract(a);
        double length = edge.lengthSqr(), speed = direction.lengthSqr(), er = edge.dot(direction), eo = edge.dot(offset);
        double aa = length * speed - er * er, bb = length * direction.dot(offset) - eo * er;
        double cc = length * offset.lengthSqr() - eo * eo - radius * radius * length;
        Hit result = earlier(sphere(from, to, a, radius), sphere(from, to, b, radius));
        double discriminant = bb * bb - aa * cc;
        if (aa > 1e-20 && discriminant >= 0)
        {
            double time = (-bb - Math.sqrt(discriminant)) / aa, along = eo + time * er;
            if (time >= 0 && time <= 1 && along >= 0 && along <= length)
                result = earlier(result, new Hit(time, a.add(edge.scale(along / length))));
        }
        return result;
    }

    /** Swept sphere versus the face, its three edges and its three corners. */
    public static Hit sweepTriangle(Vec3 from, Vec3 to, Vec3 a, Vec3 b, Vec3 c, double radius)
    {
        Vec3 start = closestTriangle(from, a, b, c);
        if (start.distanceToSqr(from) <= radius * radius + 1e-14) return new Hit(0, start);
        Hit result = segmentTriangle(from, to, a, b, c);
        if (radius <= 0) return result;
        Vec3 normal = b.subtract(a).cross(c.subtract(a)); double squared = normal.lengthSqr();
        if (squared > 1e-20)
        {
            normal = normal.scale(1 / Math.sqrt(squared));
            double distance = from.subtract(a).dot(normal), velocity = to.subtract(from).dot(normal);
            if (Math.abs(velocity) > 1e-14) for (int side : new int[]{-1, 1})
            {
                double time = (side * radius - distance) / velocity;
                if (time >= 0 && time <= 1)
                {
                    Vec3 projected = from.lerp(to, time).subtract(normal.scale(side * radius));
                    if (closestTriangle(projected, a, b, c).distanceToSqr(projected) < 1e-12)
                        result = earlier(result, new Hit(time, projected));
                }
            }
        }
        result = earlier(result, edgeCapsule(from, to, a, b, radius));
        result = earlier(result, edgeCapsule(from, to, b, c, radius));
        return earlier(result, edgeCapsule(from, to, c, a, radius));
    }

    public static boolean triangleBox(Vec3 a, Vec3 b, Vec3 c, AABB box)
    {
        double[][] planes = {{1,0,0,-box.maxX},{-1,0,0,box.minX},{0,1,0,-box.maxY},
                {0,-1,0,box.minY},{0,0,1,-box.maxZ},{0,0,-1,box.minZ}};
        return BladeSweepClipR45.triangle(new double[][]{{a.x,a.y,a.z},{b.x,b.y,b.z},{c.x,c.y,c.z}}, planes) != null;
    }

    private static Pair segments(Vec3 a, Vec3 b, Vec3 c, Vec3 d)
    {
        Vec3 first = b.subtract(a), second = d.subtract(c), offset = a.subtract(c);
        double x = first.lengthSqr(), y = second.lengthSqr(), q = second.dot(offset), s, t;
        if (x < 1e-20 && y < 1e-20) return new Pair(a, c);
        if (x < 1e-20) { s = 0; t = clamp(q / y); }
        else
        {
            double p = first.dot(offset);
            if (y < 1e-20) { t = 0; s = clamp(-p / x); }
            else
            {
                double xy = first.dot(second), denominator = x * y - xy * xy;
                s = Math.abs(denominator) > 1e-20 ? clamp((xy * q - p * y) / denominator) : 0;
                t = (xy * s + q) / y;
                if (t < 0) { t = 0; s = clamp(-p / x); }
                else if (t > 1) { t = 1; s = clamp((xy - p) / x); }
            }
        }
        return new Pair(a.lerp(b, s), c.lerp(d, t));
    }

    /** Contact is returned on the actual target triangle, including coplanar blade strips. */
    public static Vec3 triangles(Vec3 a, Vec3 b, Vec3 c, Vec3 x, Vec3 y, Vec3 z, double radius)
    {
        Vec3[] weapon = {a, b, c}, target = {x, y, z}; double squared = radius * radius + 1e-14;
        for (int i = 0; i < 3; i++)
        {
            Hit hit = segmentTriangle(weapon[i], weapon[(i + 1) % 3], x, y, z); if (hit != null) return hit.point();
            hit = segmentTriangle(target[i], target[(i + 1) % 3], a, b, c); if (hit != null) return hit.point();
            Vec3 closest = closestTriangle(weapon[i], x, y, z); if (closest.distanceToSqr(weapon[i]) <= squared) return closest;
            if (closestTriangle(target[i], a, b, c).distanceToSqr(target[i]) <= squared) return target[i];
            for (int j = 0; j < 3; j++)
            {
                Pair pair = segments(weapon[i], weapon[(i + 1) % 3], target[j], target[(j + 1) % 3]);
                if (pair.first().distanceToSqr(pair.second()) <= squared) return pair.second();
            }
        }
        return null;
    }

    public static double boxDistance(AABB box, Vec3 point)
    {
        double x = point.x - Math.max(box.minX, Math.min(box.maxX, point.x));
        double y = point.y - Math.max(box.minY, Math.min(box.maxY, point.y));
        double z = point.z - Math.max(box.minZ, Math.min(box.maxZ, point.z));
        return x * x + y * y + z * z;
    }

    public static double solidAngle(Vec3 point, Vec3 a, Vec3 b, Vec3 c)
    {
        Vec3 x = a.subtract(point), y = b.subtract(point), z = c.subtract(point);
        double lx = x.length(), ly = y.length(), lz = z.length();
        return 2 * Math.atan2(x.dot(y.cross(z)), lx * ly * lz + x.dot(y) * lz + y.dot(z) * lx + z.dot(x) * ly);
    }
}
