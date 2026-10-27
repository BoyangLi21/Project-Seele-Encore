package com.projectseele.client.render;

import java.util.Arrays;
import java.util.Random;

/** Compare the production sparse path with the previous dense DQ accumulator. */
public final class AuthoredInfluencesR53Test
{
    public static void main(String[] args)
    {
        var random = new Random(531020);
        int vertices = 4096, palette = 48;
        float[][] weights = new float[palette][vertices], transforms = new float[palette][8];
        for (int v = 0; v < vertices; v++)
        {
            int count = 1 + random.nextInt(9);
            for (int i = 0; i < count; i++) weights[random.nextInt(palette)][v] += 1 + random.nextInt(4);
            float sum = 0;
            for (float[] row : weights) sum += row[v];
            for (float[] row : weights) row[v] /= sum;
        }
        // Ties, signed zero and very small positive weights must keep their exact ordering.
        for (float[] row : weights) { row[0] = 0; row[1] = -0.0F; }
        weights[7][0] = weights[31][0] = .5F;
        weights[0][1] = Float.MIN_NORMAL; weights[47][1] = 1F;
        var sparse = new AuthoredInfluencesR53(Arrays.asList(weights));
        for (int frame = 0; frame < 32; frame++)
        {
            for (float[] transform : transforms)
                for (int i = 0; i < transform.length; i++) transform[i] = random.nextFloat() * 2 - 1;
            for (int v = 0; v < vertices; v++)
            {
                int dominant = 0;
                for (int slot = 1; slot < palette; slot++)
                    if (weights[slot][v] > weights[dominant][v]) dominant = slot;
                if (dominant != sparse.dominant[v]) throw new AssertionError("Hemisphere reference changed");
                float[] expected = new float[8], actual = new float[8], reference = transforms[dominant];
                for (int slot = 0; slot < palette; slot++)
                    if (weights[slot][v] != 0) accumulate(expected, transforms[slot], reference, weights[slot][v]);
                for (int at = sparse.offsets[v]; at < sparse.offsets[v + 1]; at++)
                    accumulate(actual, transforms[sparse.slots[at]], reference, sparse.weights[at]);
                for (int i = 0; i < 8; i++)
                    if (Float.floatToRawIntBits(expected[i]) != Float.floatToRawIntBits(actual[i]))
                        throw new AssertionError("Dual quaternion sum changed at " + v + "/" + i);
            }
        }
        System.out.println("131072 dense/sparse DQ samples are bit-exact; all nonzero weights retained.");
    }

    private static void accumulate(float[] out, float[] transform, float[] reference, float weight)
    {
        if (transform[0]*reference[0] + transform[1]*reference[1]
                + transform[2]*reference[2] + transform[3]*reference[3] < 0) weight = -weight;
        for (int i = 0; i < out.length; i++) out[i] += transform[i] * weight;
    }
}
