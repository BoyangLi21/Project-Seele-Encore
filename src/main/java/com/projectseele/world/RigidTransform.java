package com.projectseele.world;

import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/**
 * Immutable rigid transform used by the entry-plug, weapon and socket rigs.
 *
 * <p>The quaternion is normalized on construction and stored with
 * {@code w >= 0}. That removes the q/-q ambiguity from persistent data and
 * keeps interpolation deterministic across server/client reloads.</p>
 */
public record RigidTransform(Vec3 translation,
                             float qx, float qy, float qz, float qw)
{
    private static final float EPSILON = 1.0E-7F;

    public RigidTransform
    {
        if (translation == null)
        {
            throw new IllegalArgumentException("translation is required");
        }
        float length = Mth.sqrt(qx * qx + qy * qy + qz * qz + qw * qw);
        if (!Float.isFinite(length) || length < EPSILON)
        {
            qx = 0.0F;
            qy = 0.0F;
            qz = 0.0F;
            qw = 1.0F;
        }
        else
        {
            float inverse = 1.0F / length;
            qx *= inverse;
            qy *= inverse;
            qz *= inverse;
            qw *= inverse;
            if (qw < 0.0F)
            {
                qx = -qx;
                qy = -qy;
                qz = -qz;
                qw = -qw;
            }
        }
    }

    public static RigidTransform identity()
    {
        return new RigidTransform(Vec3.ZERO,
                0.0F, 0.0F, 0.0F, 1.0F);
    }

    public static RigidTransform of(Vec3 translation,
                                    Quaternionf rotation)
    {
        return new RigidTransform(translation,
                rotation.x, rotation.y, rotation.z, rotation.w);
    }

    /**
     * Creates a transform whose local axes are the supplied world vectors.
     * Axes are columns of the rotation matrix: right, up, outward.
     */
    public static RigidTransform fromAxes(Vec3 translation,
                                          Vec3 right,
                                          Vec3 up,
                                          Vec3 outward)
    {
        Vec3 z = safeNormal(outward, new Vec3(0.0D, 0.0D, 1.0D));
        Vec3 x = right.subtract(z.scale(right.dot(z)));
        x = safeNormal(x, up.cross(z));
        Vec3 y = safeNormal(z.cross(x), up);
        x = safeNormal(y.cross(z), x);

        double m00 = x.x;
        double m01 = y.x;
        double m02 = z.x;
        double m10 = x.y;
        double m11 = y.y;
        double m12 = z.y;
        double m20 = x.z;
        double m21 = y.z;
        double m22 = z.z;
        double trace = m00 + m11 + m22;
        double qx;
        double qy;
        double qz;
        double qw;
        if (trace > 0.0D)
        {
            double s = Math.sqrt(trace + 1.0D) * 2.0D;
            qw = 0.25D * s;
            qx = (m21 - m12) / s;
            qy = (m02 - m20) / s;
            qz = (m10 - m01) / s;
        }
        else if (m00 > m11 && m00 > m22)
        {
            double s = Math.sqrt(1.0D + m00 - m11 - m22) * 2.0D;
            qw = (m21 - m12) / s;
            qx = 0.25D * s;
            qy = (m01 + m10) / s;
            qz = (m02 + m20) / s;
        }
        else if (m11 > m22)
        {
            double s = Math.sqrt(1.0D + m11 - m00 - m22) * 2.0D;
            qw = (m02 - m20) / s;
            qx = (m01 + m10) / s;
            qy = 0.25D * s;
            qz = (m12 + m21) / s;
        }
        else
        {
            double s = Math.sqrt(1.0D + m22 - m00 - m11) * 2.0D;
            qw = (m10 - m01) / s;
            qx = (m02 + m20) / s;
            qy = (m12 + m21) / s;
            qz = 0.25D * s;
        }
        return new RigidTransform(translation,
                (float) qx, (float) qy, (float) qz, (float) qw);
    }

    public Quaternionf rotation()
    {
        return new Quaternionf(this.qx, this.qy, this.qz, this.qw);
    }

    /** Returns {@code this * local}. */
    public RigidTransform compose(RigidTransform local)
    {
        Vec3 position = this.transformPoint(local.translation);
        float x = this.qw * local.qx + this.qx * local.qw
                + this.qy * local.qz - this.qz * local.qy;
        float y = this.qw * local.qy - this.qx * local.qz
                + this.qy * local.qw + this.qz * local.qx;
        float z = this.qw * local.qz + this.qx * local.qy
                - this.qy * local.qx + this.qz * local.qw;
        float w = this.qw * local.qw - this.qx * local.qx
                - this.qy * local.qy - this.qz * local.qz;
        return new RigidTransform(position, x, y, z, w);
    }

    public RigidTransform inverse()
    {
        RigidTransform inverseRotation = new RigidTransform(Vec3.ZERO,
                -this.qx, -this.qy, -this.qz, this.qw);
        return new RigidTransform(
                inverseRotation.transformVector(this.translation.scale(-1.0D)),
                -this.qx, -this.qy, -this.qz, this.qw);
    }

    public Vec3 transformPoint(Vec3 point)
    {
        return this.transformVector(point).add(this.translation);
    }

    public Vec3 transformVector(Vec3 vector)
    {
        Vec3 q = new Vec3(this.qx, this.qy, this.qz);
        Vec3 twiceCross = q.cross(vector).scale(2.0D);
        return vector.add(twiceCross.scale(this.qw))
                .add(q.cross(twiceCross));
    }

    public RigidTransform interpolate(RigidTransform target, double amount)
    {
        float alpha = (float) Mth.clamp(amount, 0.0D, 1.0D);
        Quaternionf rotation = this.rotation()
                .slerp(target.rotation(), alpha)
                .normalize();
        return RigidTransform.of(
                this.translation.lerp(target.translation, alpha), rotation);
    }

    public double rotationErrorDegrees(RigidTransform other)
    {
        // Quaternion components are stored as floats. Even a quaternion
        // compared with itself can have a dot slightly below one, inventing
        // a 0.04-degree change and repeatedly restarting capsule interpolation.
        double dot = Math.abs((double)this.qx * other.qx + (double)this.qy * other.qy
                + (double)this.qz * other.qz + (double)this.qw * other.qw);
        double a=(double)this.qx*this.qx+(double)this.qy*this.qy+(double)this.qz*this.qz+(double)this.qw*this.qw;
        double b=(double)other.qx*other.qx+(double)other.qy*other.qy+(double)other.qz*other.qz+(double)other.qw*other.qw;
        dot/=Math.sqrt(a*b);
        return Math.toDegrees(2.0D
                * Math.acos(Mth.clamp(dot, -1.0D, 1.0D)));
    }

    private static Vec3 safeNormal(Vec3 value, Vec3 fallback)
    {
        if (value.lengthSqr() < 1.0E-10D)
        {
            return fallback.normalize();
        }
        return value.normalize();
    }
}
