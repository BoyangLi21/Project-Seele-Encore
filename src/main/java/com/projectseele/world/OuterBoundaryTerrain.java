package com.projectseele.world;

import java.util.Locale;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.synth.SimplexNoise;

/**
 * F1/F2 design prototype: terrain beyond the surveyed GSI rectangle. Seaward of
 * the Sagami Bay coastline the sea never ends; everywhere else rolling high
 * mountains rise out of the surveyed edge. Off unless the JVM is started with
 * -Dprojectseele.outerBoundary=sea=beach|rocky,mountain=ridged|rolling|layered,
 * so a world opened without it keeps the existing exterior.
 */
public final class OuterBoundaryTerrain
{
    /** Surveyed GSI rectangle (geography.json bounds at 1:4). */
    public static final int DEM_X0 = -1982, DEM_Z0 = -1548, DEM_X1 = 4386, DEM_Z1 = 3720;

    private static final String SEA = sea(), MOUNTAIN = mountain();
    private static final SimplexNoise A = noise(1), B = noise(2), C = noise(3), D = noise(4), E = noise(5);

    /**
     * Approximate coastline, west to east, land on the left: the Izu east coast
     * from Irozaki to Atami, the surveyed coast's two exits, then Shonan to
     * Jogashima. Placeholder points from public coordinates; the design replaces
     * them with the GSI coastline before anything is written.
     */
    private static final double[][] COAST = {
            {-100000, 18699}, {-3572, 18699}, {-1299, 16618}, {859, 13845}, {3018, 10377},
            {2904, 9129}, {2177, 8547}, {1882, 7326}, {1950, 6356}, {1655, 4941},
            {2360, 3720}, {4386, 78}, {4654, -52}, {5631, -607}, {6926, -856}, {7790, -1217},
            {9040, -1189}, {10744, -718}, {12334, -856}, {12902, -412}, {13130, 392},
            {13879, 3942}, {100000, 3942}};

    private static final Edge EDGE = Edge.load();

    private OuterBoundaryTerrain() {}

    /** Offline grid: blocks to the nearest known column and that column's ground. */
    private record Edge(int x, int z, int step, int width, int depth, short[] distance, short[] height)
    {
        static Edge load()
        {
            try (var in = new java.io.DataInputStream(new java.io.BufferedInputStream(new java.util.zip.GZIPInputStream(
                    OuterBoundaryTerrain.class.getResourceAsStream("/data/projectseele/worldgen/outer_edge.bin.gz")))))
            {
                if (in.readInt() != 0x484B4531) throw new java.io.IOException("Invalid outer edge grid");
                int x = in.readInt(), z = in.readInt(), step = in.readInt(), width = in.readInt(), depth = in.readInt();
                short[] distance = new short[width * depth], height = new short[width * depth];
                for (int i = 0; i < distance.length; i++) distance[i] = in.readShort();
                for (int i = 0; i < height.length; i++) height[i] = in.readShort();
                return new Edge(x, z, step, width, depth, distance, height);
            }
            catch (Exception exception)
            {
                throw new IllegalStateException("Outer boundary prototype needs outer_edge.bin.gz", exception);
            }
        }

        double[] sample(int bx, int bz)
        {
            int i = clamp(Math.round((bx - x) / (float) step), 0, width - 1), j = clamp(Math.round((bz - z) / (float) step), 0, depth - 1);
            double beyond = Math.hypot(bx - (x + i * step), bz - (z + j * step));
            int k = j * width + i;
            return new double[]{distance[k] + beyond, height[k]};
        }
    }

    public static boolean enabled()
    {
        return SEA != null;
    }

    /** True beyond both the surveyed rectangle and every saved chunk. */
    static boolean unknown(int x, int z)
    {
        return EDGE.sample(x, z)[0] > 0;
    }

    public static boolean outsideSurvey(int x, int z)
    {
        return x < DEM_X0 || x > DEM_X1 || z < DEM_Z0 || z > DEM_Z1;
    }

    /** Ground and water for one exterior column. */
    static HakoneSurfaceField.Surface surface(int x, int z)
    {
        // Distance to, and height of, the nearest saved or surveyed column: the
        // new terrain rises from whatever ground the map already ends on.
        double[] known = EDGE.sample(x, z);
        double away = known[0], edge = known[1];
        double target = ground(x, z, away);
        double height = edge + (target - edge) * smooth(away / 900);
        int ground = (int) Math.round(Math.max(-120, Math.min(300, height)));
        return new HakoneSurfaceField.Surface(ground, HakoneSurfaceField.SEA_Y);
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

    /** 0 default, 1 sand, 2 snow, 3 stone; kept free of block classes for offline previews. */
    static int cover(int x, int z, int ground)
    {
        boolean beach = "beach".equals(SEA);
        if (ground < HakoneSurfaceField.SEA_Y - 1) return coast(x, z) < 60 && beach ? 1 : 0;
        double steep = Math.max(Math.abs(surface(x + 2, z).ground() - surface(x - 2, z).ground()),
                Math.abs(surface(x, z + 2).ground() - surface(x, z - 2).ground())) / 4.0;
        double snow = 228 + 10 * A.getValue(x / 90.0, z / 90.0);
        if (ground >= snow && steep < 1.4) return 2;
        if (steep >= 1.4 || ground > snow + 14) return 3;
        if (ground <= HakoneSurfaceField.SEA_Y + 2 && coast(x, z) > -40) return beach ? 1 : 3;
        return 0;
    }

    private static double ground(int x, int z, double away)
    {
        double s = coast(x, z);
        boolean rocky = "rocky".equals(SEA);
        if (s > 0)
        {
            // Shelf, then the bay floor. Rocky coasts drop faster and keep stacks.
            double depth = rocky ? 6 + s / 12 : 2 + s / 30;
            double bed = HakoneSurfaceField.SEA_Y - Math.min(38, depth) + 2 * B.getValue(x / 70.0, z / 70.0);
            if (rocky && s < 260)
            {
                double stack = C.getValue(x / 70.0, z / 70.0);
                if (stack > 0.74) bed = Math.max(bed, HakoneSurfaceField.SEA_Y + 3 + 60 * (stack - 0.74));
            }
            return bed;
        }
        double inland = -s;
        double peak = mountain(x, z, away);
        // Beaches leave a coastal plain; rocky coasts let the ridges reach the sea.
        double plain = rocky ? 180 : 340;
        double shore = HakoneSurfaceField.SEA_Y + (rocky ? 6 : 2);
        return shore + (peak - shore) * smooth(inland / plain);
    }

    private static double mountain(int x, int z, double away)
    {
        // Massifs and broad valleys several kilometres across, so no two stretches of the
        // horizon carry the same ridge pattern at the same height.
        double massif = 0.55 + 0.45 * smooth(0.5 + 0.9 * fbm(E, x / 5200.0, z / 5200.0, 3));
        return 72 + (shape(x, z, away) - 72) * massif;
    }

    private static double shape(int x, int z, double away)
    {
        double wx = x + 700 * A.getValue(x / 2300.0, z / 2300.0) + 160 * B.getValue(x / 600.0, z / 600.0);
        double wz = z + 700 * B.getValue(x / 2300.0 + 31, z / 2300.0 - 17) + 160 * A.getValue(x / 600.0 - 5, z / 600.0 + 9);
        switch (MOUNTAIN)
        {
            case "rolling":
                return 90 + 230 * Math.pow(Math.max(0, 0.5 + 0.7 * fbm(C, wx / 1300, wz / 1300, 5)), 1.3) + 14 * fbm(D, x / 210.0, z / 210.0, 3);
            case "layered":
            {
                // Foothills at the survey edge, the high ranges further out.
                double amplitude = 60 + 200 * smooth((away - 200) / 1800);
                double rx = wx * 0.8 + wz * 0.6, rz = (-wx * 0.6 + wz * 0.8) * 1.9;
                return 85 + amplitude * ridged(C, rx / 1300, rz / 1300, 5) + 12 * fbm(D, x / 230.0, z / 230.0, 3);
            }
            default:
                return 85 + 200 * Math.pow(ridged(C, wx / 1500, wz / 1500, 6), 1.1) + 14 * fbm(D, x / 240.0, z / 240.0, 3);
        }
    }

    /** Signed distance to the coastline: positive at sea, negative on land. */
    static double coast(int x, int z)
    {
        double best = Double.MAX_VALUE;
        for (int i = 0; i + 1 < COAST.length; i++)
        {
            double ax = COAST[i][0], az = COAST[i][1], bx = COAST[i + 1][0], bz = COAST[i + 1][1];
            double dx = bx - ax, dz = bz - az, t = ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz);
            t = Math.max(0, Math.min(1, t));
            best = Math.min(best, Math.hypot(x - ax - t * dx, z - az - t * dz));
        }
        return land(x, z) ? -best : best;
    }

    /** Land lies north of the coastline: the line closed through the far north. */
    private static boolean land(double x, double z)
    {
        boolean inside = false;
        int n = COAST.length;
        for (int i = 0, j = n + 1; i < n + 2; j = i++)
        {
            double[] a = vertex(i), b = vertex(j);
            if ((a[1] > z) != (b[1] > z) && x < (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
        }
        return inside;
    }

    private static double[] vertex(int i)
    {
        int n = COAST.length;
        return i < n ? COAST[i] : i == n ? new double[]{100000, -100000} : new double[]{-100000, -100000};
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

    private static int clamp(int v, int lo, int hi)
    {
        return Math.max(lo, Math.min(hi, v));
    }

    private static double smooth(double value)
    {
        double t = Math.max(0, Math.min(1, value));
        return t * t * (3 - 2 * t);
    }

    private static String option(String key)
    {
        String spec = System.getProperty("projectseele.outerBoundary");
        if (spec == null || spec.isBlank()) return null;
        for (String part : spec.toLowerCase(Locale.ROOT).split(","))
        {
            String[] kv = part.trim().split("=");
            if (kv.length == 2 && kv[0].equals(key)) return kv[1];
        }
        return "";
    }

    private static String sea()
    {
        String value = option("sea");
        return value == null ? null : value.equals("rocky") ? "rocky" : "beach";
    }

    private static String mountain()
    {
        String value = option("mountain");
        return value == null ? "ridged" : value.equals("rolling") || value.equals("layered") ? value : "ridged";
    }
}
