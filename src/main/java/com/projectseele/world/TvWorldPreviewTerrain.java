package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LeavesBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.levelgen.Heightmap;

/** Fresh preview chunks only. Authored facilities are transplanted afterwards. */
public final class TvWorldPreviewTerrain
{
    public static final int CENTRE_X = 30, CENTRE_Z = 296;
    public static final int RADIUS = 1800, FLAT_RADIUS = 600;
    public static final int ROOF_Y = 24, FLOOR_Y = -478, LAKE_Y = -473;
    public static final int CITY_WALK_Y = 80;

    private TvWorldPreviewTerrain() {}

    public static boolean active(net.minecraft.server.level.ServerLevel level)
    {
        return level.getChunkSource().getGenerator() instanceof GeoFrontBoundedChunkGenerator generator
                && generator.isTvPreview();
    }

    public static boolean insideDome(ChunkPos chunk)
    {
        return Math.hypot(chunk.getMiddleBlockX() - CENTRE_X,
                chunk.getMiddleBlockZ() - CENTRE_Z) <= RADIUS + 24;
    }

    public static int roof(int x, int z)
    {
        double radius = Math.hypot(x - CENTRE_X, z - CENTRE_Z);
        if (radius <= FLAT_RADIUS) return ROOF_Y;
        double t = Math.min(1, (radius - FLAT_RADIUS) / (RADIUS - FLAT_RADIUS));
        return FLOOR_Y + (int) Math.floor((ROOF_Y - FLOOR_Y)
                * Math.sqrt(Math.max(0, 1 - t * t)));
    }

    public static double lakeDistance(int x, int z)
    {
        double dx = (x + 310.0) / 310.0, dz = (z - 340.0) / 200.0;
        return dx * dx + dz * dz + 0.075 * Math.sin((x + z) / 47.0)
                + 0.045 * Math.cos(z / 37.0);
    }

    public static int ground(int x, int z)
    {
        double lake = lakeDistance(x, z);
        double y = FLOOR_Y + 3.5 * Math.sin(x / 137.0) * Math.cos(z / 193.0)
                + 2.4 * Math.sin((x + z) / 67.0)
                + 29 * gaussian(x, z, 420, 830, 310)
                + 17 * gaussian(x, z, -230, 1030, 390)
                + 11 * gaussian(x, z, 720, 330, 290);
        if (lake < 1.2)
        {
            double shelf = smooth((lake - 0.60) / 0.60);
            y = (LAKE_Y - 11) * (1 - shelf) + (LAKE_Y + 2) * shelf;
        }
        // Retain the actual HQ foundation height and grade the adjacent park.
        double campus = 1 - smooth(rectangleDistance(x, z, -90, 96, 160, 447) / 64);
        return TvAuthoredTerrainR44.ground(x, z, (int) Math.round(y * (1 - campus) - 467 * campus));
    }

    public static void shape(ChunkAccess chunk)
    {
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        int minX = chunk.getPos().getMinBlockX(), minZ = chunk.getPos().getMinBlockZ();
        for (int z = minZ; z < minZ + 16; z++)
        {
            for (int x = minX; x < minX + 16; x++)
            {
                int nativeGround = chunk.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x & 15, z & 15);
                int surfaceTop = nativeGround;
                double cityDistance = rectangleDistance(x, z, -194, -4, 254, 444);
                if (cityDistance < 160)
                {
                    double grade = 1 - smooth(cityDistance / 160);
                    int top = (int) Math.round(nativeGround * (1 - grade) + 79 * grade);
                    surfaceTop = top;
                    for (int y = Math.min(nativeGround, top) - 3; y <= Math.max(nativeGround, top); y++)
                    {
                        BlockState state = y > top ? Blocks.AIR.defaultBlockState()
                                : y == top ? Blocks.GRASS_BLOCK.defaultBlockState()
                                : y >= top - 3 ? Blocks.DIRT.defaultBlockState()
                                : Blocks.STONE.defaultBlockState();
                        chunk.setBlockState(p.set(x, y, z), state, false);
                    }
                }
                // The custom fixed biome has no vanilla surface-rule branch.
                // Give future explored land the same soil as the finished core.
                if (surfaceTop >= 64)
                    for (int d = 0; d < 4; d++)
                        chunk.setBlockState(p.set(x, surfaceTop - d, z),
                                (d == 0 ? Blocks.GRASS_BLOCK : Blocks.DIRT).defaultBlockState(), false);
                if (Math.hypot(x - CENTRE_X, z - CENTRE_Z) >= RADIUS) continue;
                int floor = ground(x, z), ceiling = roof(x, z);
                if (ceiling <= floor + 4) continue;
                boolean lake = lakeDistance(x, z) < 1.1 && floor < LAKE_Y;
                // Retain solid cover even where the natural ocean is deep.
                for (int y = ceiling + 1; y <= ceiling + 16; y++)
                    chunk.setBlockState(p.set(x, y, z), Blocks.STONE.defaultBlockState(), false);
                for (int y = floor + 1; y <= ceiling; y++)
                    chunk.setBlockState(p.set(x, y, z), lake && y <= LAKE_Y
                            ? Blocks.WATER.defaultBlockState() : Blocks.AIR.defaultBlockState(), false);
                for (int y = floor - 7; y <= floor; y++)
                {
                    BlockState material = y < floor - 3 ? Blocks.STONE.defaultBlockState()
                            : lake ? (y == floor ? Blocks.GRAVEL : Blocks.SAND).defaultBlockState()
                            : (y == floor ? Blocks.GRASS_BLOCK : Blocks.DIRT).defaultBlockState();
                    chunk.setBlockState(p.set(x, y, z), material, false);
                }
            }
        }
        // Native placed features run in the decoration stage, after adjacent
        // carved chunks are available. Shape only establishes soil and geology.
        chunk.setUnsaved(true);
    }

    private static void plantForest(ChunkAccess chunk)
    {
        int minX = chunk.getPos().getMinBlockX(), minZ = chunk.getPos().getMinBlockZ();
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        // Jittered world cells with crowns clipped per chunk avoid grid seams.
        for (int gz = Math.floorDiv(minZ - 5, 14); gz <= Math.floorDiv(minZ + 20, 14); gz++)
        {
            for (int gx = Math.floorDiv(minX - 5, 14); gx <= Math.floorDiv(minX + 20, 14); gx++)
            {
                long h = hash(gx, gz);
                int x = gx * 14 + 2 + (int) Math.floorMod(h, 10);
                int z = gz * 14 + 2 + (int) Math.floorMod(h >>> 12, 10);
                if (rectangleDistance(x, z, -85, 75, 190, 425) < 35
                        || lakeDistance(x, z) < 1.28 || roof(x, z) < ground(x, z) + 20) continue;
                double density = Math.max(gaussian(x, z, -520, 810, 420),
                        Math.max(gaussian(x, z, 370, 860, 350), gaussian(x, z, 730, 230, 420)));
                if (Math.floorMod(h >>> 24, 1000) > density * 740) continue;
                int base = ground(x, z), height = 7 + (int) Math.floorMod(h >>> 34, 5);
                BlockState trunk = (Math.floorMod(h, 7) == 0 ? Blocks.BIRCH_LOG : Blocks.OAK_LOG).defaultBlockState();
                BlockState leaves = Blocks.OAK_LEAVES.defaultBlockState().setValue(LeavesBlock.PERSISTENT, true);
                for (int dy = 1; dy <= height + 2; dy++)
                    for (int dz = -4; dz <= 4; dz++)
                        for (int dx = -4; dx <= 4; dx++)
                        {
                            int px = x + dx, pz = z + dz;
                            if (px < minX || px >= minX + 16 || pz < minZ || pz >= minZ + 16) continue;
                            if (dx == 0 && dz == 0 && dy <= height)
                                chunk.setBlockState(p.set(px, base + dy, pz), trunk, false);
                            else if (dy >= height - 4 && (dx * dx + dz * dz) / 16.0
                                    + Math.pow((dy - height + 1) / 3.4, 2) < 1)
                                chunk.setBlockState(p.set(px, base + dy, pz), leaves, false);
                        }
            }
        }
    }

    private static double rectangleDistance(double x, double z, int x0, int z0, int x1, int z1)
    {
        return Math.hypot(Math.max(x0 - x, Math.max(0, x - x1)), Math.max(z0 - z, Math.max(0, z - z1)));
    }

    private static double smooth(double t)
    {
        t = Math.max(0, Math.min(1, t));
        return t * t * (3 - 2 * t);
    }

    private static double gaussian(int x, int z, int cx, int cz, int radius)
    {
        return Math.exp(-((double) (x - cx) * (x - cx) + (double) (z - cz) * (z - cz)) / (radius * radius));
    }

    private static long hash(int x, int z)
    {
        long value = x * 341873128712L ^ z * 132897987541L;
        value = (value ^ (value >>> 33)) * 0xff51afd7ed558ccdL;
        return value ^ (value >>> 33);
    }
}
