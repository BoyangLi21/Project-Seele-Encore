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
                         short[] heights, short[] waters, byte[] blend) {}

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
                if (step < 1 || width < 2 || depth < 2 || (long) width * depth > 16000000)
                    throw new IOException("Invalid surface dimensions");
                short[] heights = new short[width * depth], waters = new short[width * depth];
                for (int i = 0; i < heights.length; i++) heights[i] = in.readShort();
                for (int i = 0; i < waters.length; i++) waters[i] = in.readShort();
                byte[] blend = new byte[heights.length];
                try (InputStream weights = HakoneSurfaceField.class.getResourceAsStream(
                        "/data/projectseele/worldgen/hakone_surface_blend.bin.gz"))
                {
                    if (weights != null)
                    {
                        try (DataInputStream data = new DataInputStream(new BufferedInputStream(new GZIPInputStream(weights))))
                        {
                            if (data.readInt() != 0x484B4231 || data.readInt() != x || data.readInt() != z
                                    || data.readInt() != step || data.readInt() != width || data.readInt() != depth)
                                throw new IOException("Surface blend dimensions differ");
                            data.readFully(blend);
                            if (data.read() != -1) throw new IOException("Unexpected surface blend payload");
                        }
                    }
                }
                return new Field(x, z, step, width, depth, heights, waters, blend);
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
        double weight = ((Byte.toUnsignedInt(f.blend[iz * f.width + ix]) * (1-dx)
                + Byte.toUnsignedInt(f.blend[iz * f.width + jx]) * dx) * (1-dz)
                + (Byte.toUnsignedInt(f.blend[jz * f.width + ix]) * (1-dx)
                + Byte.toUnsignedInt(f.blend[jz * f.width + jx]) * dx) * dz) / 255.0;
        // Surveyed and saved columns stay fixed. Unsaved holes gradually
        // recover native relief instead of inheriting a clamped row forever.
        double distance = Math.max(Math.max(f.x - x, x - (f.x + (f.width - 1) * f.step)),
                Math.max(f.z - z, z - (f.z + (f.depth - 1) * f.step)));
        if (distance > 0) weight = 1 - (1-weight) * (1-smooth(distance/256));
        if (weight == 0) return new Surface((int) Math.round(height), water);
        var outer = exterior(x, z, nativeGround);
        double result = height * (1-weight) + outer.ground * weight;
        if (water != outer.water)
        {
            // Two water datums meet across dry land, never across an exposed
            // vertical fluid face. The dry crest also contains a retained
            // high lake beside the lower surveyed plain.
            int crest = Math.max(water, outer.water) + 2;
            if (crest > NO_WATER + 2)
                result = Math.max(result, weight <= .5
                        ? height + (crest-height) * smooth(weight*2)
                        : crest + (outer.ground-crest) * smooth(weight*2-1));
        }
        int ground = (int) Math.round(result);
        int level = weight < .5 ? water : outer.water;
        return new Surface(ground, ground < level ? level : NO_WATER);
    }

    private static double smooth(double value)
    {
        double t = Math.max(0, Math.min(1, value));
        return t*t*(3-2*t);
    }

    /** Native N/W continent; lower E/S coast. The remote UN strip stays on
     * its original datum. Unbuilt corner watersheds separate both oceans. */
    static Surface exterior(int x, int z, int nativeGround)
    {
        double coast = Math.max(Math.max(0, x-4386.0), Math.max(0, z-3720.0));
        double inland = Math.max(Math.max(0, -1982.0-x), Math.max(0, -1548.0-z));
        double offset = coast == 0 ? 0 : inland == 0 ? 1
                : smooth((coast/(coast+inland)-.5)*4);
        double height = Math.max(-120, nativeGround-144*offset);
        if (offset > 0 && offset < 1)
        {
            double crest = 74 + Math.max(0, nativeGround-70)*.2;
            double bank = offset <= .35 ? nativeGround + (crest-nativeGround)*smooth(offset/.35)
                    : crest + (Math.max(-120,nativeGround-144)-crest)*smooth((offset-.35)/.65);
            height = Math.max(height, bank);
        }
        // Keep the potential sea level even on land. Otherwise the crest
        // would jump when native noise crosses its shoreline by one block.
        return new Surface((int)Math.round(height), offset < .35 ? 62 : SEA_Y);
    }
}
