package com.projectseele.client.render;

import java.util.Collection;

/** Static nonzero weights in their original palette order; no influence is pruned. */
final class AuthoredInfluencesR53
{
    final float[][] paletteWeights;
    final int[] offsets, slots, dominant;
    final float[] weights;
    private int[] leaders;
    private float[] spins;

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

    private record Corner(float x, float y, float z) {}

    /**
     * For each corner, the first corner at the same rest position with the
     * same weights. The meshes are unindexed triangle lists, so every
     * surface point repeats about six times; its blend is evaluated once.
     */
    int[] leaders(float[] rest, int stride)
    {
        if (this.leaders != null) return this.leaders;
        int count = rest.length / stride;
        int[] result = new int[count];
        var first = new java.util.HashMap<Corner, Integer>(count);
        for (int vertex = 0; vertex < count; vertex++)
        {
            int i = vertex * stride;
            Integer seen = first.putIfAbsent(new Corner(rest[i], rest[i + 1], rest[i + 2]), vertex);
            result[vertex] = seen != null && sameWeights(seen, vertex) ? seen : vertex;
        }
        this.spins = new float[count * 4];
        return this.leaders = result;
    }

    /** Scratch for one blended rotation per leading corner (x, y, z, w). */
    float[] spins() { return this.spins; }

    private boolean sameWeights(int a, int b)
    {
        int length = this.offsets[a + 1] - this.offsets[a];
        if (length != this.offsets[b + 1] - this.offsets[b]) return false;
        for (int k = 0; k < length; k++)
            if (this.slots[this.offsets[a] + k] != this.slots[this.offsets[b] + k]
                    || this.weights[this.offsets[a] + k] != this.weights[this.offsets[b] + k]) return false;
        return true;
    }
}
