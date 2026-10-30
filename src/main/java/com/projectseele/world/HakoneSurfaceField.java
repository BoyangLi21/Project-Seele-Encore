package com.projectseele.world;

import java.io.DataInputStream;
import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.zip.GZIPInputStream;
import org.slf4j.Logger;
import com.mojang.logging.LogUtils;

/** Cached geographic surface only; never performs per-tick terrain checks. */
public final class HakoneSurfaceField
{
    private static final Logger LOGGER = LogUtils.getLogger();
    private static final Field FIELD = load();
    public static final int NO_WATER = -32768;
    public static final int SEA_Y = -82;

    private HakoneSurfaceField() {}

    private record Field(int x, int z, int step, int width, int depth,
                         short[] heights, short[] waters) {}

    public record Surface(int ground, int water) {}

    private static Field load()
    {
        try (InputStream raw = HakoneSurfaceField.class.getResourceAsStream(
                    "/data/projectseele/worldgen/hakone_surface.bin.gz"))
        {
            if (raw == null) throw new IOException("Missing Hakone surface resource");
            try (DataInputStream in = new DataInputStream(new BufferedInputStream(new GZIPInputStream(raw), 65536)))
            {
                if (in.readInt() != 0x484B3535) throw new IOException("Invalid surface format");
                int x = in.readInt(), z = in.readInt(), step = in.readInt();
                int width = in.readInt(), depth = in.readInt();
                if (step < 1 || width < 2 || depth < 2 || (long) width * depth > 10000000)
                    throw new IOException("Invalid surface dimensions");
                short[] heights = new short[width * depth], waters = new short[width * depth];
                for (int i = 0; i < heights.length; i++) heights[i] = in.readShort();
                for (int i = 0; i < waters.length; i++) waters[i] = in.readShort();
                return new Field(x, z, step, width, depth, heights, waters);
            }
        }
        catch (IOException exception)
        {
            // An absent optional map resource must not stop an existing game.
            LOGGER.error("Unable to load the Hakone geographic surface", exception);
            return null;
        }
    }

    public static Surface sample(int x, int z, int nativeGround)
    {
        Field f = FIELD;
        if (f == null) return null;
        double fx = Math.max(0, Math.min(f.width - 1, (x - (double) f.x) / f.step));
        double fz = Math.max(0, Math.min(f.depth - 1, (z - (double) f.z) / f.step));
        int ix = (int) fx, iz = (int) fz, jx = Math.min(ix + 1, f.width - 1), jz = Math.min(iz + 1, f.depth - 1);
        double dx = fx - ix, dz = fz - iz;
        double height = ((f.heights[iz * f.width + ix] * (1 - dx) + f.heights[iz * f.width + jx] * dx) * (1 - dz)
                + (f.heights[jz * f.width + ix] * (1 - dx) + f.heights[jz * f.width + jx] * dx) * dz) / 16.0;
        int water = f.waters[(int) Math.round(fz) * f.width + (int) Math.round(fx)];
        // Beyond the surveyed rectangle, meet native relief at the same sea
        // datum over 256 blocks instead of reintroducing the old Y=62 ocean.
        double distance = Math.max(Math.max(f.x - x, x - (f.x + (f.width - 1) * f.step)),
                Math.max(f.z - z, z - (f.z + (f.depth - 1) * f.step)));
        if (distance > 0)
        {
            double t = Math.min(1, distance / 256.0);
            t = t * t * (3 - 2 * t);
            height = height * (1 - t) + Math.max(-120, nativeGround - 144) * t;
            water = height < SEA_Y ? SEA_Y : NO_WATER;
        }
        return new Surface((int) Math.round(height), water);
    }
}
