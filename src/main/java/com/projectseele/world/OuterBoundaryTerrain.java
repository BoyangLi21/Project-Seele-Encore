package com.projectseele.world;

import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.util.zip.GZIPInputStream;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.LevelChunkSection;
import net.minecraft.world.level.chunk.PalettedContainer;
import net.minecraft.world.level.levelgen.synth.SimplexNoise;

/**
 * Terrain beyond the surveyed rectangle and the saved chunks (F1/F2). Seaward of the
 * Sagami Bay coastline the sea never ends: sand from Odawara east, rocks and stacks
 * from Manazuru south. Everywhere else mountains rise from the nearest known ground,
 * low beside the map and higher further out. Both resources are built offline by
 * tools/plan_outer_boundary.py. -Dprojectseele.outerBoundary=off restores the old
 * exterior.
 */
public final class OuterBoundaryTerrain
{
    public static final int DEM_X0 = -1982, DEM_Z0 = -1548, DEM_X1 = 4386, DEM_Z1 = 3720;

    private static final boolean ENABLED = !"off".equalsIgnoreCase(System.getProperty("projectseele.outerBoundary", ""));
    private static final SimplexNoise A = noise(1), B = noise(2), C = noise(3), D = noise(4), E = noise(5);
    private static final Edge EDGE = Edge.load();
    private static final Coast COAST = Coast.load();

    /** Fallback coastline beyond the coast grid only, west to east with land on the left. */
    private static final double[][] FALLBACK = {
            {-100000, 18699}, {-3572, 18699}, {-1299, 16618}, {859, 13845}, {3018, 10377},
            {2904, 9129}, {2177, 8547}, {1882, 7326}, {1950, 6356}, {1655, 4941},
            {2360, 3720}, {4386, 78}, {4654, -52}, {5631, -607}, {6926, -856}, {7790, -1217},
            {9040, -1189}, {10744, -718}, {12334, -856}, {12902, -412}, {13130, 392},
            {13879, 3942}, {100000, 3942}};

    private OuterBoundaryTerrain() {}

    public static boolean enabled()
    {
        return ENABLED && EDGE != null;
    }

    /** True beyond both the surveyed rectangle and every saved chunk. */
    public static boolean unknown(int x, int z)
    {
        return EDGE.distance(x, z) > 0;
    }

    /** A chunk with no known column anywhere in it: the native noise can be skipped. */
    public static boolean wholeChunkUnknown(ChunkPos chunk)
    {
        return EDGE.distance(chunk.getMiddleBlockX(), chunk.getMiddleBlockZ()) > 24;
    }

    /** Ground and water for one exterior column. */
    static HakoneSurfaceField.Surface surface(int x, int z)
    {
        double away = EDGE.distance(x, z), edge = EDGE.ground(x, z);
        double target = ground(x, z, away);
        double height = edge + (target - edge) * smooth(away / 900);
        int ground = (int) Math.round(Math.max(-120, Math.min(300, height)));
        return new HakoneSurfaceField.Surface(ground, HakoneSurfaceField.SEA_Y);
    }

    /**
     * Unsaved surveyed sea from Manazuru to Yugawara keeps the field's coast and depth,
     * with rock stacks added near the shore.
     */
    static HakoneSurfaceField.Surface surveyedSea(int x, int z, HakoneSurfaceField.Surface field)
    {
        if (field.water() != HakoneSurfaceField.SEA_Y || field.ground() >= HakoneSurfaceField.SEA_Y || EDGE.saved(x, z)) return field;
        double s = coast(x, z);
        if (s <= 0 || s > 120 || rocky(z) < 0.5) return field;
        int top = stack(x, z, field.ground());
        return top == field.ground() ? field : new HakoneSurfaceField.Surface(top, HakoneSurfaceField.SEA_Y);
    }

    /** Material for the top block, or null to keep the default grass or gravel. */
    public static BlockState top(int x, int z, int ground)
    {
        return switch (cover(x, z, ground))
        {
            case 1 -> Blocks.SAND.defaultBlockState();
            case 2 -> Blocks.SNOW_BLOCK.defaultBlockState();
            case 3 -> Blocks.STONE.defaultBlockState();
            default -> null;
        };
    }

    /** 0 default, 1 sand, 2 snow, 3 stone; free of block classes for offline previews. */
    static int cover(int x, int z, int ground)
    {
        boolean beach = rocky(z) < 0.5;
        if (ground < HakoneSurfaceField.SEA_Y - 1) return coast(x, z) < 60 && beach ? 1 : 0;
        double steep = Math.max(Math.abs(surface(x + 2, z).ground() - surface(x - 2, z).ground()),
                Math.abs(surface(x, z + 2).ground() - surface(x, z - 2).ground())) / 4.0;
        double snow = 228 + 10 * A.getValue(x / 90.0, z / 90.0);
        if (ground >= snow && steep < 1.4) return 2;
        if (steep >= 1.4 || ground > snow + 14) return 3;
        if (ground <= HakoneSurfaceField.SEA_Y + 2 && coast(x, z) > -40) return beach ? 1 : 3;
        return 0;
    }

    /** Stone below -128 in a chunk whose surface the outer terrain writes anyway. */
    public static void fillDeep(ChunkAccess chunk)
    {
        int from = Math.max(GeoFrontHeightR52.LEGACY_MIN_Y, chunk.getMinBuildHeight()), to = -128;
        var sections = chunk.getSections();
        BlockState stone = Blocks.STONE.defaultBlockState();
        for (int y = from; y < to; y += 16)
        {
            int index = chunk.getSectionIndex(y);
            var states = new PalettedContainer<>(Block.BLOCK_STATE_REGISTRY, stone, PalettedContainer.Strategy.SECTION_STATES);
            sections[index] = new LevelChunkSection(states, sections[index].getBiomes());
        }
        for (var entry : chunk.getHeightmaps())
            for (int z = 0; z < 16; z++)
                for (int x = 0; x < 16; x++)
                    entry.getValue().update(x, to - 1, z, stone);
        chunk.setUnsaved(true);
    }

    /** Rocks from Manazuru south, sand from Odawara east. */
    private static double rocky(int z)
    {
        return smooth((z - 1800) / 500.0);
    }

    private static double ground(int x, int z, double away)
    {
        double s = coast(x, z), r = rocky(z);
        if (s > 0)
        {
            double depth = (2 + s / 30) * (1 - r) + (6 + s / 12) * r;
            double bed = HakoneSurfaceField.SEA_Y - Math.min(38, depth) + 2 * B.getValue(x / 70.0, z / 70.0);
            return r >= 0.5 && s < 120 ? stack(x, z, (int) Math.round(bed)) : bed;
        }
        double peak = mountain(x, z, away);
        double plain = 340 * (1 - r) + 180 * r;
        double shore = HakoneSurfaceField.SEA_Y + 2 + 4 * r;
        return shore + (peak - shore) * smooth(-s / plain);
    }

    private static int stack(int x, int z, int bed)
    {
        double rock = C.getValue(x / 70.0, z / 70.0);
        return rock > 0.8 ? Math.max(bed, (int) Math.round(HakoneSurfaceField.SEA_Y + 3 + 70 * (rock - 0.8))) : bed;
    }

    /**
     * Low hills beside the map, the high ranges further out. Ridges come from one warped,
     * isotropic ridged noise mixed with rounded noise, so no row of identical spires forms;
     * massifs several kilometres across vary the height along the horizon.
     */
    private static double mountain(int x, int z, double away)
    {
        double wx = x + 700 * A.getValue(x / 2300.0, z / 2300.0) + 160 * B.getValue(x / 600.0, z / 600.0);
        double wz = z + 700 * B.getValue(x / 2300.0 + 31, z / 2300.0 - 17) + 160 * A.getValue(x / 600.0 - 5, z / 600.0 + 9);
        double ridges = 0.65 * Math.pow(ridged(C, wx / 1800, wz / 1800, 6), 1.05) + 0.35 * (0.5 + 0.5 * fbm(D, wx / 800, wz / 800, 4));
        double amplitude = 70 + 175 * smooth((away - 200) / 1800);
        double massif = 0.55 + 0.45 * smooth(0.5 + 0.9 * fbm(E, x / 5200.0, z / 5200.0, 3));
        return 85 + amplitude * massif * ridges + 12 * fbm(D, x / 230.0, z / 230.0, 3);
    }

    /** Signed distance to the coastline: positive at sea, negative on land. */
    static double coast(int x, int z)
    {
        if (COAST != null && COAST.covers(x, z)) return COAST.sample(x, z);
        double best = Double.MAX_VALUE;
        for (int i = 0; i + 1 < FALLBACK.length; i++)
        {
            double ax = FALLBACK[i][0], az = FALLBACK[i][1], bx = FALLBACK[i + 1][0], bz = FALLBACK[i + 1][1];
            double dx = bx - ax, dz = bz - az, t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)));
            best = Math.min(best, Math.hypot(x - ax - t * dx, z - az - t * dz));
        }
        return land(x, z) ? -best : best;
    }

    private static boolean land(double x, double z)
    {
        boolean inside = false;
        int n = FALLBACK.length;
        for (int i = 0, j = n + 1; i < n + 2; j = i++)
        {
            double[] a = vertex(i), b = vertex(j);
            if ((a[1] > z) != (b[1] > z) && x < (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
        }
        return inside;
    }

    private static double[] vertex(int i)
    {
        int n = FALLBACK.length;
        return i < n ? FALLBACK[i] : i == n ? new double[]{100000, -100000} : new double[]{-100000, -100000};
    }

    private static double ridged(SimplexNoise n, double x, double z, int octaves)
    {
        double sum = 0, amplitude = 0.5, weight = 1, frequency = 1;
        for (int i = 0; i < octaves; i++)
        {
            double r = 1 - Math.abs(n.getValue(x * frequency + i * 17.3, z * frequency - i * 9.1));
            r *= r * weight;
            weight = Math.max(0, Math.min(1, r * 1.6));
            sum += r * amplitude;
            amplitude *= 0.5;
            frequency *= 2.03;
        }
        return Math.min(1, sum * 1.05);
    }

    private static double fbm(SimplexNoise n, double x, double z, int octaves)
    {
        double sum = 0, amplitude = 0.5, frequency = 1;
        for (int i = 0; i < octaves; i++)
        {
            sum += amplitude * n.getValue(x * frequency + i * 11.7, z * frequency + i * 5.3);
            amplitude *= 0.5;
            frequency *= 2.01;
        }
        return sum;
    }

    private static SimplexNoise noise(long salt)
    {
        return new SimplexNoise(RandomSource.create(0x5EE1EF12L * 31 + salt));
    }

    private static double smooth(double value)
    {
        double t = Math.max(0, Math.min(1, value));
        return t * t * (3 - 2 * t);
    }

    private static DataInputStream open(String name) throws IOException
    {
        var raw = OuterBoundaryTerrain.class.getResourceAsStream("/data/projectseele/worldgen/" + name);
        if (raw == null) throw new IOException("Missing " + name);
        return new DataInputStream(new BufferedInputStream(new GZIPInputStream(raw), 65536));
    }

    /** Every 8 blocks: distance to the nearest known column, its ground, and saved chunks. */
    private record Edge(int x, int z, int step, int width, int depth, short[] distance, short[] ground, byte[] saved)
    {
        static Edge load()
        {
            try (var in = open("outer_edge.bin.gz"))
            {
                if (in.readInt() != 0x484B4532) throw new IOException("Unexpected outer edge format");
                int x = in.readInt(), z = in.readInt(), step = in.readInt(), width = in.readInt(), depth = in.readInt();
                short[] distance = new short[width * depth], ground = new short[width * depth];
                byte[] saved = new byte[width * depth];
                for (int i = 0; i < distance.length; i++) distance[i] = in.readShort();
                for (int i = 0; i < ground.length; i++) ground[i] = in.readShort();
                in.readFully(saved);
                return new Edge(x, z, step, width, depth, distance, ground, saved);
            }
            catch (IOException exception)
            {
                // Without the grid the generator keeps the previous exterior.
                return null;
            }
        }

        private boolean outside(int bx, int bz)
        {
            return bx < x || bz < z || bx > x + (width - 1) * step || bz > z + (depth - 1) * step;
        }

        private int index(int bx, int bz)
        {
            int i = Math.max(0, Math.min(width - 1, Math.round((bx - x) / (float) step)));
            int j = Math.max(0, Math.min(depth - 1, Math.round((bz - z) / (float) step)));
            return j * width + i;
        }

        double distance(int bx, int bz)
        {
            int k = index(bx, bz);
            if (!outside(bx, bz)) return distance[k];
            int i = k % width, j = k / width;
            return distance[k] + Math.hypot(bx - (x + i * step), bz - (z + j * step));
        }

        double ground(int bx, int bz)
        {
            return ground[index(bx, bz)];
        }

        boolean saved(int bx, int bz)
        {
            return !outside(bx, bz) && saved[index(bx, bz)] != 0;
        }
    }

    /** Every 16 blocks over Sagami Bay: signed distance to the coast, positive at sea. */
    private record Coast(int x, int z, int step, int width, int depth, short[] signed)
    {
        static Coast load()
        {
            try (var in = open("outer_coast.bin.gz"))
            {
                if (in.readInt() != 0x484B4331) throw new IOException("Unexpected coast format");
                int x = in.readInt(), z = in.readInt(), step = in.readInt(), width = in.readInt(), depth = in.readInt();
                short[] signed = new short[width * depth];
                for (int i = 0; i < signed.length; i++) signed[i] = in.readShort();
                return new Coast(x, z, step, width, depth, signed);
            }
            catch (IOException exception)
            {
                return null;
            }
        }

        boolean covers(int bx, int bz)
        {
            return bx >= x && bz >= z && bx < x + (width - 1) * step && bz < z + (depth - 1) * step;
        }

        double sample(int bx, int bz)
        {
            double fx = (bx - x) / (double) step, fz = (bz - z) / (double) step;
            int i = (int) fx, j = (int) fz;
            double dx = fx - i, dz = fz - j;
            return (signed[j * width + i] * (1 - dx) + signed[j * width + i + 1] * dx) * (1 - dz)
                    + (signed[(j + 1) * width + i] * (1 - dx) + signed[(j + 1) * width + i + 1] * dx) * dz;
        }
    }
}
