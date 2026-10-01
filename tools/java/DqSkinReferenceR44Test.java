package com.projectseele.client.render;

import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Padding/permutation must not change one weighted large-fold deformation. */
public final class DqSkinReferenceR44Test
{
    private static Vector3f deform(int[] ids, float[] weights,
                                  Quaternionf[] rotations, Vector3f[] positions,
                                  boolean candidate)
    {
        int reference = candidate
                ? DqSkinReferenceR44.referenceBone(ids, weights, 0, ids.length)
                : ids[0];
        Quaternionf q = new Quaternionf(0, 0, 0, 0);
        Quaternionf d = new Quaternionf(0, 0, 0, 0);
        for (int slot = 0; slot < ids.length; slot++)
        {
            if (weights[slot] == 0) continue;
            int bone = ids[slot];
            float weight = weights[slot];
            if (rotations[reference].dot(rotations[bone]) < 0) weight = -weight;
            Quaternionf dual = new Quaternionf(positions[bone].x,
                    positions[bone].y, positions[bone].z, 0)
                    .mul(rotations[bone]).mul(.5F);
            q.add(new Quaternionf(rotations[bone]).mul(weight));
            d.add(dual.mul(weight));
        }
        float inv = 1 / (float)Math.sqrt(q.lengthSquared());
        q.mul(inv); d.mul(inv);
        float dot = q.dot(d);
        d.x -= q.x * dot; d.y -= q.y * dot;
        d.z -= q.z * dot; d.w -= q.w * dot;
        Quaternionf translation = d.mul(new Quaternionf(q).conjugate());
        return q.transform(new Vector3f(13.86363F, 34.98271F, -13.97312F))
                .add(2 * translation.x, 2 * translation.y, 2 * translation.z);
    }

    public static void main(String[] args)
    {
        int checks = 0; float maximum = 0, oldFailure = 0;
        int[][] orders = {{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
        int[] effective = {1,2,3}; float[] weights = {.424011F,.424011F,.151978F};
        for (int pose = 0; pose < 32; pose++)
        {
            Quaternionf[] q = {new Quaternionf(),
                    new Quaternionf().rotationXYZ(.3F, .8F + pose * .07F, 2.7F),
                    new Quaternionf().rotationXYZ(-.8F, -2.6F, 1.7F + pose * .04F),
                    new Quaternionf().rotationXYZ(2.4F, .3F, -.9F)};
            Vector3f[] p = {new Vector3f(), new Vector3f(3,6,-4),
                    new Vector3f(-7,4,2), new Vector3f(1,-2,8)};
            Vector3f expected = deform(effective, weights, q, p, true);
            for (int[] order : orders)
            {
                for (int padding = 0; padding < 4; padding++)
                {
                    int[] ids = new int[4]; float[] ws = new float[4]; int k = 0;
                    for (int slot = 0; slot < 4; slot++)
                    {
                        if (slot == padding) { ids[slot] = 0; ws[slot] = 0; }
                        else { ids[slot] = effective[order[k]]; ws[slot] = weights[order[k++]]; }
                    }
                    if (DqSkinReferenceR44.referenceBone(ids, ws, 0, 4) != 1)
                        throw new AssertionError("Padding/permutation changed tie owner");
                    float[][] columns = {{ws[0]}, {ws[1]}, {ws[2]}, {ws[3]}};
                    if (ids[DqSkinReferenceR44.referenceSlot(ids, columns, 0)] != 1)
                        throw new AssertionError("Palette reference disagrees with flat skin");
                    float error = deform(ids, ws, q, p, true).distance(expected);
                    maximum = Math.max(maximum, error);
                    oldFailure = Math.max(oldFailure, deform(ids, ws, q, p, false).distance(expected));
                    if (error > .0001F) throw new AssertionError("Changed deformation " + error);
                    checks++;
                }
            }
        }
        if (oldFailure < 1) throw new AssertionError("First-slot failure was not detected");
        System.out.println("{\"checks\":" + checks + ",\"maximum_candidate_error\":"
                + maximum + ",\"maximum_first_slot_error\":" + oldFailure
                + ",\"scope\":\"Standalone production reference helper with JOML DQ large-fold padding/permutation; renderer dispatch/native pixels untested\"}");
    }
}
