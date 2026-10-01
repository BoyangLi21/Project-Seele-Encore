package com.projectseele.client.render;

/** Candidate hemisphere owner; zero padding cannot choose a quaternion. */
final class DqSkinReferenceR44
{
    static final boolean REVIEW = Boolean.getBoolean("projectseele.r44DominantSkinReview");
    static final boolean RUNNING = Boolean.getBoolean("projectseele.r44RunningSkinReview");

    static
    {
        if (REVIEW && RUNNING) throw new IllegalStateException("Select one R44 skin reference candidate");
    }

    static int referenceBone(int[] bones, float[] weights, int at, int count)
    {
        int chosen = -1;
        float maximum = 0;
        for (int slot = at; slot < at + count; slot++)
        {
            float weight = weights[slot];
            if (weight > maximum || weight == maximum && weight > 0
                    && (chosen < 0 || bones[slot] < chosen))
            {
                maximum = weight;
                chosen = bones[slot];
            }
        }
        if (chosen < 0)
        {
            throw new IllegalArgumentException("Skin vertex has no positive influence");
        }
        return chosen;
    }

    static int referenceSlot(int[] stableBones, float[][] weights, int vertex)
    {
        int chosen = -1;
        float maximum = 0;
        for (int slot = 0; slot < weights.length; slot++)
        {
            float weight = weights[slot][vertex];
            if (weight > maximum || weight == maximum && weight > 0
                    && (chosen < 0 || stableBones[slot] < stableBones[chosen]))
            {
                maximum = weight;
                chosen = slot;
            }
        }
        if (chosen < 0)
        {
            throw new IllegalArgumentException("Skin vertex has no positive influence");
        }
        return chosen;
    }

    private DqSkinReferenceR44() {}
}
