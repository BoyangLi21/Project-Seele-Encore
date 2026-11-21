package com.projectseele.client.map;

import java.awt.image.BufferedImage;
import java.util.BitSet;
import java.util.List;
import net.minecraft.resources.ResourceLocation;

/** All baked bounds are block edges, half-open; texture columns increase east and rows increase south. */
public record AreaMapLayer(String id, String label, Bounds bounds, int priority, ResourceLocation texture,
        ResourceLocation preview, Mask mask, Heights bottom, Heights ceiling, Heights ground, Integer floorY, List<Bounds> zones)
{
    public record Bounds(int minX, int minY, int minZ, int maxX, int maxY, int maxZ)
    {
        public Bounds
        {
            if (maxX <= minX || maxY <= minY || maxZ <= minZ) throw new IllegalArgumentException("Empty map bounds");
        }

        public int width() { return maxX - minX; }
        public int depth() { return maxZ - minZ; }
        public double centerX() { return minX + width() * 0.5; }
        public double centerZ() { return minZ + depth() * 0.5; }
        public boolean contains(double x, double y, double z)
        {
            return x >= minX && x < maxX && y >= minY && y < maxY && z >= minZ && z < maxZ;
        }

        int pixel(double x, double z, int w, int h)
        {
            return Math.min(h - 1, (int)((z - minZ) / depth() * h)) * w
                    + Math.min(w - 1, (int)((x - minX) / width() * w));
        }
    }

    public record Mask(int width, int height, BitSet bits)
    {
        static Mask from(BufferedImage image)
        {
            int w = image.getWidth(), h = image.getHeight();
            BitSet result = new BitSet(w * h);
            int[] row = new int[w];
            for (int z = 0; z < h; z++)
            {
                image.getRGB(0, z, w, 1, row, 0, w);
                for (int x = 0; x < w; x++) if ((row[x] >>> 24) != 0) result.set(z * w + x);
            }
            return new Mask(w, h, result);
        }
    }

    public record Heights(int width, int height, short[] values)
    {
        static Heights from(BufferedImage image)
        {
            int w = image.getWidth(), h = image.getHeight();
            short[] result = new short[w * h];
            int[] row = new int[w];
            for (int z = 0; z < h; z++)
            {
                image.getRGB(0, z, w, 1, row, 0, w);
                for (int x = 0; x < w; x++) result[z * w + x] = (short)(((row[x] >>> 8) & 65535) - 32768);
            }
            return new Heights(w, h, result);
        }

        private int at(Bounds b, double x, double z) { return values[b.pixel(x, z, width, height)]; }
    }

    public boolean selects(double x, double y, double z)
    {
        if (!bounds.contains(x, y, z)) return false;
        if (!zones.isEmpty() && zones.stream().noneMatch(zone -> zone.contains(x, y, z))) return false;
        if (mask != null && !mask.bits.get(bounds.pixel(x, z, mask.width, mask.height))) return false;
        if (bottom != null)
        {
            int threshold = bottom.at(bounds, x, z);
            if (threshold == Short.MIN_VALUE || y < threshold) return false;
        }
        return ceiling == null || y < ceiling.at(bounds, x, z);
    }

    public boolean overlapsView(double cx, double cz, double halfWidth, double halfDepth)
    {
        return cx + halfWidth > bounds.minX && cx - halfWidth < bounds.maxX
                && cz + halfDepth > bounds.minZ && cz - halfDepth < bounds.maxZ;
    }

    /** Xaero uses Short.MAX_VALUE for an unknown cursor Y. Do not place underground waypoints on surface roofs. */
    public int cursorHeight(double x, double z)
    {
        if (x < bounds.minX || x >= bounds.maxX || z < bounds.minZ || z >= bounds.maxZ) return Short.MAX_VALUE;
        int y = ground != null ? ground.at(bounds, x, z) : floorY != null ? floorY : Short.MAX_VALUE;
        return y != Short.MIN_VALUE && y != Short.MAX_VALUE && selects(x, y, z) ? y : Short.MAX_VALUE;
    }

    /** The last strip of the surface atlas gives the HUD back to normal player-centred navigation. */
    public boolean nearSurfaceEdge(double x, double z)
    {
        if (!id.equals("surface")) return false;
        double edge = Math.min(128, Math.min(bounds.width(), bounds.depth()) * 0.025);
        return x - bounds.minX < edge || bounds.maxX - x <= edge || z - bounds.minZ < edge || bounds.maxZ - z <= edge;
    }

    public double fit(double w, double h) { return Math.min(w / bounds.width(), h / bounds.depth()); }
}
