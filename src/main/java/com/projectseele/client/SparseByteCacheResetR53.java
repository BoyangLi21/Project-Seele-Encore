package com.projectseele.client;

import java.util.Arrays;

/** Worker-owned dirty pages retain the original packed occlusion-cache values. */
public final class SparseByteCacheResetR53
{
    private static final int SHIFT = 12;
    private final boolean[] dirty;
    private final int[] pages;
    private int count;

    public SparseByteCacheResetR53(int bytes)
    {
        dirty = new boolean[(bytes + (1 << SHIFT) - 1) >> SHIFT];
        pages = new int[dirty.length];
    }

    public void mark(int byteIndex)
    {
        int page = byteIndex >> SHIFT;
        if (!dirty[page])
        {
            dirty[page] = true;
            pages[count++] = page;
        }
    }

    public void clear(byte[] cache)
    {
        for (int i = 0; i < count; i++)
        {
            int page = pages[i], start = page << SHIFT;
            Arrays.fill(cache, start, Math.min(start + (1 << SHIFT), cache.length), (byte) 0);
            dirty[page] = false;
        }
        count = 0;
    }
}
