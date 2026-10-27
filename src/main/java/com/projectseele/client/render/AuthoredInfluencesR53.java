package com.projectseele.client.render;

import java.util.Collection;

/** Static nonzero weights in their original palette order; no influence is pruned. */
final class AuthoredInfluencesR53
{
    final float[][] paletteWeights;
    final int[] offsets, slots, dominant;
    final float[] weights;

    AuthoredInfluencesR53(Collection<float[]> palette)
    {
        this.paletteWeights = palette.toArray(float[][]::new);
        int count = this.paletteWeights.length == 0 ? 0 : this.paletteWeights[0].length;
        this.offsets = new int[count + 1];
        this.dominant = new int[count];
        int active = 0;
        for (int vertex = 0; vertex < count; vertex++)
        {
            this.offsets[vertex] = active;
            int reference = 0;
            for (int slot = 0; slot < this.paletteWeights.length; slot++)
            {
                float weight = this.paletteWeights[slot][vertex];
                if (weight != 0) active++;
                if (weight > this.paletteWeights[reference][vertex]) reference = slot;
            }
            this.dominant[vertex] = reference;
        }
        this.offsets[count] = active;
        this.slots = new int[active];
        this.weights = new float[active];
        int at = 0;
        for (int vertex = 0; vertex < count; vertex++)
            for (int slot = 0; slot < this.paletteWeights.length; slot++)
            {
                float weight = this.paletteWeights[slot][vertex];
                if (weight == 0) continue;
                this.slots[at] = slot;
                this.weights[at++] = weight;
            }
    }
}
