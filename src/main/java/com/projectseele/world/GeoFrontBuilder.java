package com.projectseele.world;

import java.util.Locale;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.registry.ModBlocks;
import com.projectseele.registry.ModFluids;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.util.Mth;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LadderBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.material.Fluids;

/** Full underground GeoFront sphere and its NERV command pyramid. */
public final class GeoFrontBuilder
{
    public static final int CAVERN_RADIUS = 320;
    /** Structures occupy the inner disc, so it stays perfectly level. */
    public static final int TERRAIN_FLAT_RADIUS = 170;
    private static final int TERRAIN_CELL = 24;
    private static final int TERRAIN_AMPLITUDE = 4;
    private static final int TERRAIN_BLEND = 40;
    private static final int NO_SURFACE = Integer.MIN_VALUE;
    /** Sphere centre relative to the NERV floor origin. */
    public static final int CAVERN_CENTRE_Y = 112;
    public static final int CAVERN_CENTRE_Z = -76;
    public static final int CAVERN_TOP_Y = CAVERN_CENTRE_Y + CAVERN_RADIUS;
    public static final int CAVERN_BOTTOM_Y = CAVERN_CENTRE_Y - CAVERN_RADIUS;
    /** Ground-access overlook south of the pyramid, reached by the public stair. */
    public static final int OBSERVATION_Z = 190;
    public static final int OBSERVATION_Y = 24;
    public static final int[] LIFT_X = {-42, 0, 42};

    // The downloaded command module occupies X=-28..27, Y=-21..55 and
    // Z=-33..95. The NERV shell deliberately encloses that complete volume
    // instead of treating the command centre as an exterior annex.
    public static final int PYRAMID_BASE_CENTRE_Z = 31;
    public static final int PYRAMID_CENTRE_Z = 31;
    public static final int PYRAMID_BASE_Y = -22;
    public static final int PYRAMID_APEX_Y = 150;
    public static final int PYRAMID_BASE_HALF_X = 120;
    public static final int PYRAMID_BASE_HALF_Z = 120;
    private static final int PYRAMID_APEX_HALF = 0;
    private static final int PYRAMID_AUDIT_Y = 57;
    public static final int PYRAMID_APRON_MARGIN = 14;
    private static final int PYRAMID_APRON_MARKER_INSET = 4;
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;

    private GeoFrontBuilder() {}

    public static void build(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        build(level, origin, false);
    }

    /** Builds the playable NERV facilities inside the complete buried sphere. */
    public static void build(ServerLevel level, BlockPos origin,
                             boolean preservePrivateShell)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "GeoFrontBuilder.build");
        PerformanceCounters.recordBuilderCall();
        if (!SeeleConfig.rescueMode()
                && SeeleConfig.TRANSPARENT_GEOFRONT_SHELL.get())
        {
            buildSkyweaveSphere(level, origin);
        }
        buildCavernFloor(level, origin);
        logFloorContinuity(level, origin);
        clearLegacyArtificialSun(level, origin);
        buildNaturalLake(level, origin);
        buildLclLake(level, origin);
        buildNervPyramid(level, origin);
        NervOperationsCentreBuilder.build(level, origin);
        MagiDeepLabBuilder.build(level, origin);
        TerminalDogmaBuilder.build(level, origin);
        NervOperationsCentreBuilder.linkFacilities(level, origin);
        buildEvaLiftTerminals(level, origin);
        buildCommandBridge(level, origin);
        buildForestRing(level, origin);
        buildObservationDeck(level, origin);
        buildObservationAccess(level, origin);
        repairCavernLighting(level, origin);
    }

    public static GeoFrontAudit inspect(ServerLevel level, BlockPos origin)
    {
        // Terrain continuity is reported by logFloorContinuity right after the
        // floor is laid, not asserted here. Gating the whole map on it put the
        // server in a rebuild loop: every login failed the audit, rebuilt for
        // thirty seconds, and failed again.
        boolean floor = level.getBlockState(origin.offset(150, 0,
                CAVERN_CENTRE_Z)).is(Blocks.GRASS_BLOCK);
        BlockPos sphereCentre = cavernCentre(origin);
        BlockState expectedSky = skyweaveState();
        boolean skySphere = level.getBlockState(sphereCentre.offset(
                CAVERN_RADIUS, 0, 0)).is(expectedSky.getBlock())
                && level.getBlockState(sphereCentre.offset(
                -CAVERN_RADIUS, 0, 0)).is(expectedSky.getBlock())
                // The three audited launch shafts deliberately pierce the
                // absolute north pole. Sample the intact upper shoulder.
                && level.getBlockState(sphereCentre.offset(
                64, 248, 0)).is(expectedSky.getBlock())
                && level.getBlockState(sphereCentre.offset(
                0, -CAVERN_RADIUS, 0)).is(expectedSky.getBlock())
                && level.getBlockState(sphereCentre.offset(
                0, 0, CAVERN_RADIUS)).is(expectedSky.getBlock())
                && level.getBlockState(sphereCentre.offset(
                0, 0, -CAVERN_RADIUS)).is(expectedSky.getBlock());
        boolean lake = level.getFluidState(origin.offset(48, 1, 0))
                .getFluidType() == ModFluids.LCL_TYPE.get();
        boolean naturalLake = level.getFluidState(origin.offset(-125, 0, -125))
                .is(Fluids.WATER);
        boolean pyramid = level.getBlockState(origin.offset(
                        -PYRAMID_BASE_HALF_X, PYRAMID_BASE_Y,
                        PYRAMID_BASE_CENTRE_Z - PYRAMID_BASE_HALF_Z))
                .is(Blocks.CHISELED_DEEPSLATE)
                && level.getBlockState(origin.offset(
                        pyramidHalfXAt(PYRAMID_AUDIT_Y), PYRAMID_AUDIT_Y,
                        PYRAMID_CENTRE_Z
                                + pyramidHalfZAt(PYRAMID_AUDIT_Y)))
                .is(Blocks.CRYING_OBSIDIAN)
                && level.getBlockState(origin.offset(
                        0, PYRAMID_APEX_Y + 1, PYRAMID_CENTRE_Z))
                .is(Blocks.BEACON);
        boolean legacyInnerPyramidGone =
                level.getBlockState(origin.offset(34, 2, 0)).isAir()
                        && level.getBlockState(origin.offset(0, 2, -34)).isAir();
        boolean realSky = expectedSky.getBlock()
                == ModBlocks.GEOFRONT_SKYWEAVE.get();
        boolean cavernLighting = level.getBlockState(origin.offset(
                200, 0, CAVERN_CENTRE_Z)).is(Blocks.SEA_LANTERN)
                && level.getBlockState(origin.offset(216, 24, CAVERN_CENTRE_Z)).is(Blocks.LIGHT);
        int lifts = 0;
        int gantries = 0;
        for (int x : LIFT_X)
        {
            if (level.getBlockState(origin.offset(x, 1, -76)).is(Blocks.LODESTONE))
            {
                lifts++;
            }
            // buildLiftGantry anchors its dry access ladder 17 blocks behind
            // the -76 carrier bed, with the suspension frame one block farther
            // back. The old -63/-70 samples described a removed prototype and
            // rejected all three intact current gantries.
            if (level.getBlockState(origin.offset(x, 27, -59))
                    .is(Blocks.LADDER)
                    && level.getBlockState(origin.offset(x, 27, -58))
                    .is(Blocks.IRON_BLOCK))
            {
                gantries++;
            }
        }
        boolean bridge = pyramidGroundAccessPresent(level, origin);
        boolean observation = level.getBlockState(
                origin.offset(0, OBSERVATION_Y, OBSERVATION_Z)).is(Blocks.LODESTONE);
        NervOperationsCentreBuilder.OperationsAudit operations =
                NervOperationsCentreBuilder.inspect(level, origin);
        MagiDeepLabBuilder.MagiAudit magi =
                MagiDeepLabBuilder.inspect(level, origin);
        TerminalDogmaBuilder.TerminalDogmaAudit terminalDogma =
                TerminalDogmaBuilder.inspect(level, origin);
        int vanillaLavaSamples = countVanillaLavaSamples(level, origin);
        boolean valid = floor && skySphere && lake && naturalLake
                && pyramid && legacyInnerPyramidGone && lifts == 3
                && cavernLighting && gantries == 3
                && bridge && observation && operations.runtimePhysicalValid()
                && magi.runtimePhysicalValid()
                && terminalDogma.valid() && vanillaLavaSamples == 0;
        return new GeoFrontAudit(valid, floor, skySphere, lake, naturalLake,
                pyramid, legacyInnerPyramidGone, realSky, cavernLighting,
                lifts, gantries, bridge, observation, operations,
                magi, terminalDogma, vanillaLavaSamples);
    }

    /**
     * Samples the full inhabited volume instead of scanning seventy million
     * interior blocks. A fresh dimension generates air below the surface, so
     * any vanilla lava at these distributed points proves stale/contaminated
     * chunks and rejects the map before a player is sent underground.
     */
    public static int countVanillaLavaSamples(ServerLevel level, BlockPos origin)
    {
        BlockPos centre = cavernCentre(origin);
        int[] horizontal = {-192, -128, -64, 0, 64, 128, 192};
        int[] vertical = {-224, -160, -104, -64, 0, 64, 128, 192};
        int safeRadius = CAVERN_RADIUS - 20;
        int safeRadiusSqr = safeRadius * safeRadius;
        int lava = 0;
        for (int x : horizontal)
        {
            for (int y : vertical)
            {
                for (int z : horizontal)
                {
                    if (x * x + y * y + z * z > safeRadiusSqr)
                    {
                        continue;
                    }
                    if (level.getFluidState(centre.offset(x, y, z))
                            .is(FluidTags.LAVA))
                    {
                        lava++;
                    }
                }
            }
        }
        return lava;
    }

    /**
     * Measures cavern-floor continuity and logs it.
     *
     * <p>Diagnostic, not a gate. Two earlier revisions asserted this and both
     * were wrong about what the finished floor looks like — the first demanded
     * bare ground where roads and groves sit, the second still failed for
     * reasons the audit could not report. Run this right after the floor is
     * laid and before anything is built on it, so the numbers describe the
     * terrain itself, and print them instead of guessing again.
     */
    private static void logFloorContinuity(ServerLevel level, BlockPos origin)
    {
        BlockPos centre = cavernCentre(origin);
        int floorDeltaY = origin.getY() - centre.getY();
        int floorRadius = (int) Math.floor(Math.sqrt(
                CAVERN_RADIUS * CAVERN_RADIUS - floorDeltaY * floorDeltaY)) - 8;
        int compared = 0;
        int missing = 0;
        int worstStep = 0;
        String worstAt = "none";
        for (int radius = TERRAIN_FLAT_RADIUS + 6;
             radius <= floorRadius - 6; radius += 17)
        {
            for (int degrees = 0; degrees < 360; degrees += 15)
            {
                double angle = Math.toRadians(degrees);
                int x = (int) Math.round(Math.cos(angle) * radius);
                int z = (int) Math.round(Math.sin(angle) * radius);
                int here = surfaceOffsetY(level, centre, origin.getY(), x, z);
                if (here == NO_SURFACE)
                {
                    missing++;
                    continue;
                }
                for (int[] step : new int[][] {{1, 0}, {0, 1}})
                {
                    int next = surfaceOffsetY(level, centre, origin.getY(),
                            x + step[0], z + step[1]);
                    if (next == NO_SURFACE)
                    {
                        missing++;
                        continue;
                    }
                    compared++;
                    int delta = Math.abs(next - here);
                    if (delta > worstStep)
                    {
                        worstStep = delta;
                        worstAt = x + "," + z + " -> " + (x + step[0])
                                + "," + (z + step[1])
                                + " (" + here + " -> " + next + ")";
                    }
                }
            }
        }
        ProjectSeele.LOGGER.info(
                "GeoFront floor continuity: compared={} noSurface={} worstStep={} at {}",
                compared, missing, worstStep, worstAt);
    }

    /** Grass/stone surface height of one column, relative to the NERV floor. */
    private static int surfaceOffsetY(ServerLevel level, BlockPos centre,
                                       int baseY, int x, int z)
    {
        for (int y = TERRAIN_AMPLITUDE + 2; y >= -TERRAIN_AMPLITUDE - 2; y--)
        {
            BlockState state = level.getBlockState(
                    new BlockPos(centre.getX() + x, baseY + y, centre.getZ() + z));
            if (state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.STONE)
                    || state.is(Blocks.MOSS_BLOCK))
            {
                return y;
            }
        }
        return NO_SURFACE;
    }

    /**
     * Continuous cavern-floor height.
     *
     * <p>The predecessor evaluated {@code floorMod(x * 31 + z * 17, 5) - 2}
     * per block. That is a hash, not a height field: stepping one block in x
     * moved it by one level and one block in z by two, so every column stood
     * at a different height from its neighbours and two thirds of the floor
     * read as a lattice of one-block pillars. Control points are therefore
     * sampled once per {@link #TERRAIN_CELL} and blended, which bounds the
     * slope between orthogonal neighbours to a single block.
     */
    private static int terrainHeight(int x, int z, int distance)
    {
        if (distance <= TERRAIN_FLAT_RADIUS)
        {
            return 0;
        }
        int cellX = Math.floorDiv(x, TERRAIN_CELL);
        int cellZ = Math.floorDiv(z, TERRAIN_CELL);
        float withinX = smoothStep((x - cellX * TERRAIN_CELL) / (float) TERRAIN_CELL);
        float withinZ = smoothStep((z - cellZ * TERRAIN_CELL) / (float) TERRAIN_CELL);
        float near = Mth.lerp(withinX, controlHeight(cellX, cellZ),
                controlHeight(cellX + 1, cellZ));
        float far = Mth.lerp(withinX, controlHeight(cellX, cellZ + 1),
                controlHeight(cellX + 1, cellZ + 1));
        // Ramp in from the flat inner disc so the two regions meet without a
        // step at the seam.
        float ramp = Mth.clamp((distance - TERRAIN_FLAT_RADIUS)
                / (float) TERRAIN_BLEND, 0.0F, 1.0F);
        return Math.round(Mth.lerp(withinZ, near, far)
                * TERRAIN_AMPLITUDE * ramp);
    }

    /** Deterministic -1..1 control value for one terrain lattice corner. */
    private static float controlHeight(int cellX, int cellZ)
    {
        int hash = cellX * 374761393 + cellZ * 668265263;
        hash = (hash ^ (hash >>> 13)) * 1274126177;
        hash ^= hash >>> 16;
        return Math.floorMod(hash, 2001) / 1000.0F - 1.0F;
    }

    private static float smoothStep(float value)
    {
        return value * value * (3.0F - 2.0F * value);
    }

    private static void buildCavernFloor(ServerLevel level, BlockPos origin)
    {
        BlockPos centre = cavernCentre(origin);
        int floorDeltaY = origin.getY() - centre.getY();
        int floorRadius = (int) Math.floor(Math.sqrt(
                CAVERN_RADIUS * CAVERN_RADIUS - floorDeltaY * floorDeltaY)) - 8;
        int radiusSqr = floorRadius * floorRadius;
        for (int x = -floorRadius; x <= floorRadius; x++)
        {
            for (int z = -floorRadius; z <= floorRadius; z++)
            {
                int distanceSqr = x * x + z * z;
                if (distanceSqr > radiusSqr)
                {
                    continue;
                }
                int distance = (int) Math.sqrt(distanceSqr);
                int terrainY = terrainHeight(x, z, distance);
                BlockPos column = new BlockPos(
                        centre.getX() + x, origin.getY(), centre.getZ() + z);
                // Track the surface downwards, otherwise a dipped column ends
                // its dirt below the fixed old base and opens a hole.
                for (int y = Math.min(-5, terrainY - 3); y <= terrainY - 3; y++)
                {
                    set(level, column.offset(0, y, 0),
                            Blocks.STONE.defaultBlockState());
                }
                set(level, column.offset(0, terrainY - 2, 0),
                        Blocks.DIRT.defaultBlockState());
                set(level, column.offset(0, terrainY - 1, 0),
                        Blocks.DIRT.defaultBlockState());
                set(level, column.offset(0, terrainY, 0),
                        distance >= floorRadius - 3
                                ? Blocks.STONE.defaultBlockState()
                                : Blocks.GRASS_BLOCK.defaultBlockState());
                // Older terrain formulas left dirt/grass/stone towers because a
                // later rebuild wrote the new top but never cleared the old
                // one. The old ceiling of 24 missed remnants that a much taller
                // formula stranded higher up (the thin stone columns hanging in
                // the cavern), so sweep the whole lower hemisphere. Only natural
                // terrain is removed; authored structures use non-terrain blocks
                // and are rebuilt later, so they stay untouched.
                for (int y = terrainY + 1; y <= CAVERN_CENTRE_Y; y++)
                {
                    BlockPos stale = column.offset(0, y, 0);
                    if (isNaturalTerrain(level.getBlockState(stale)))
                    {
                        set(level, stale, Blocks.AIR.defaultBlockState());
                    }
                }
            }
        }
    }

    private static void buildSkyweaveSphere(ServerLevel level, BlockPos origin)
    {
        BlockPos centre = cavernCentre(origin);
        BlockState sky = skyweaveState();
        int radiusSqr = CAVERN_RADIUS * CAVERN_RADIUS;
        for (int y = -CAVERN_RADIUS; y <= CAVERN_RADIUS; y++)
        {
            int horizontalRadius = (int) Math.round(Math.sqrt(
                    Math.max(0, radiusSqr - y * y)));
            int poleStep = Math.min(CAVERN_RADIUS, Math.abs(y) + 1);
            int nextRadius = (int) Math.round(Math.sqrt(
                    Math.max(0, radiusSqr - poleStep * poleStep)));
            int innerRadius = Math.max(0, nextRadius - 1);
            // Carve the annulus band by rows, not by angular samples. The old
            // raster rounded adjacent angles onto the same voxel and skipped
            // its neighbour, so where the shell is steep the misses stacked
            // across layers into thin stone columns hanging from the ceiling.
            int outerSqr = horizontalRadius * horizontalRadius;
            int innerSqr = innerRadius * innerRadius;
            for (int x = -horizontalRadius; x <= horizontalRadius; x++)
            {
                int xSqr = x * x;
                if (xSqr > outerSqr)
                {
                    continue;
                }
                int zOuter = (int) Math.floor(Math.sqrt(outerSqr - xSqr));
                int zInner = xSqr >= innerSqr ? 0
                        : (int) Math.ceil(Math.sqrt(innerSqr - xSqr));
                for (int z = zInner; z <= zOuter; z++)
                {
                    set(level, centre.offset(x, y, z), sky);
                    if (z != 0)
                    {
                        set(level, centre.offset(x, y, -z), sky);
                    }
                }
            }
        }
        // Exact cardinal blocks are both visual seams and deterministic audit
        // markers; the annular raster above may otherwise choose an adjacent
        // rounded voxel at a pole.
        set(level, centre.offset(CAVERN_RADIUS, 0, 0), sky);
        set(level, centre.offset(-CAVERN_RADIUS, 0, 0), sky);
        set(level, centre.offset(0, CAVERN_RADIUS, 0), sky);
        set(level, centre.offset(64, 248, 0), sky);
        set(level, centre.offset(0, -CAVERN_RADIUS, 0), sky);
        set(level, centre.offset(0, 0, CAVERN_RADIUS), sky);
        set(level, centre.offset(0, 0, -CAVERN_RADIUS), sky);
    }

    public static BlockPos cavernCentre(BlockPos origin)
    {
        return origin.offset(0, CAVERN_CENTRE_Y, CAVERN_CENTRE_Z);
    }

    public static boolean skyweaveAvailable()
    {
        return true;
    }

    private static BlockState skyweaveState()
    {
        return ModBlocks.GEOFRONT_SKYWEAVE.get().defaultBlockState();
    }

    private static void clearLegacyArtificialSun(ServerLevel level,
                                                  BlockPos origin)
    {
        for (int x = -11; x <= 11; x++)
        {
            for (int z = -11; z <= 11; z++)
            {
                for (int y = 79; y <= 92; y++)
                {
                    BlockPos position = origin.offset(x, y, z);
                    BlockState state = level.getBlockState(position);
                    if (state.is(Blocks.SEA_LANTERN)
                            || state.is(Blocks.YELLOW_STAINED_GLASS)
                            || state.is(Blocks.LIGHT))
                    {
                        set(level, position, Blocks.AIR.defaultBlockState());
                    }
                }
            }
        }
    }

    private static void buildLclLake(ServerLevel level, BlockPos origin)
    {
        int outer = 72;
        int inner = 40;
        for (int x = -outer; x <= outer; x++)
        {
            for (int z = -outer; z <= outer; z++)
            {
                int distanceSqr = x * x + z * z;
                if (distanceSqr > outer * outer || distanceSqr < inner * inner)
                {
                    continue;
                }
                BlockState bed = Math.floorMod(x * 17 + z * 31, 37) == 0
                        ? Blocks.SEA_LANTERN.defaultBlockState()
                        : Blocks.POLISHED_BASALT.defaultBlockState();
                set(level, origin.offset(x, -4, z), bed);
                for (int y = -3; y <= 1; y++)
                {
                    set(level, origin.offset(x, y, z),
                            ModFluids.LCL_SOURCE.get().defaultFluidState()
                                    .createLegacyBlock());
                }
            }
        }
    }

    /** A separate freshwater lake makes the Skyweave interior a real biome. */
    private static void buildNaturalLake(ServerLevel level, BlockPos origin)
    {
        BlockPos centre = origin.offset(-125, 0, -125);
        final int radiusX = 52;
        final int radiusZ = 34;
        for (int x = -58; x <= 58; x++)
        {
            for (int z = -40; z <= 40; z++)
            {
                double distance = square(x / (double) radiusX)
                        + square(z / (double) radiusZ);
                if (distance <= 1.0D)
                {
                    for (int y = -9; y <= -6; y++)
                    {
                        set(level, centre.offset(x, y, z),
                                Blocks.STONE.defaultBlockState());
                    }
                    BlockState bed = Math.floorMod(x * 19 + z * 23, 19) == 0
                            ? Blocks.GRAVEL.defaultBlockState()
                            : Blocks.CLAY.defaultBlockState();
                    set(level, centre.offset(x, -5, z), bed);
                    for (int y = -4; y <= 0; y++)
                    {
                        set(level, centre.offset(x, y, z),
                                Fluids.WATER.defaultFluidState().createLegacyBlock());
                    }
                    for (int y = 1; y <= 4; y++)
                    {
                        set(level, centre.offset(x, y, z),
                                Blocks.AIR.defaultBlockState());
                    }
                }
                else if (distance <= 1.20D)
                {
                    int pattern = Math.floorMod(x * 31 + z * 17, 11);
                    set(level, centre.offset(x, 0, z), pattern <= 1
                            ? Blocks.GRAVEL.defaultBlockState()
                            : pattern == 2
                            ? Blocks.CLAY.defaultBlockState()
                            : Blocks.GRASS_BLOCK.defaultBlockState());
                }
            }
        }
    }

    /**
     * Bounded exterior migration. Besides the shell markers, validate the
     * traversable ground route and the actual apron surface: old saves often
     * retained revision markers while later landscape passes restored grass
     * or an imported wall cut the public passage in half.
     */
    public static boolean ensurePyramidRevision(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return false;
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "GeoFrontBuilder.ensurePyramidRevision");
        BlockPos baseMarker = origin.offset(-PYRAMID_BASE_HALF_X,
                PYRAMID_BASE_Y,
                PYRAMID_BASE_CENTRE_Z - PYRAMID_BASE_HALF_Z);
        BlockPos middleMarker = origin.offset(pyramidHalfXAt(PYRAMID_AUDIT_Y),
                PYRAMID_AUDIT_Y,
                PYRAMID_CENTRE_Z + pyramidHalfZAt(PYRAMID_AUDIT_Y));
        BlockPos apexMarker = origin.offset(0, PYRAMID_APEX_Y + 1,
                PYRAMID_CENTRE_Z);
        boolean shellValid = level.getBlockState(baseMarker)
                .is(Blocks.CHISELED_DEEPSLATE)
                && level.getBlockState(middleMarker).is(Blocks.CRYING_OBSIDIAN)
                && level.getBlockState(apexMarker).is(Blocks.BEACON);
        boolean preserveCommandAsset =
                LocalMapAssetLoader.commandMarkersPresent(level, origin);
        boolean repaired = false;
        if (!shellValid)
        {
            buildNervPyramid(level, origin);
            ProjectSeele.LOGGER.info(
                    "NERV pyramid upgraded to the square black v18 envelope at {}",
                    origin.toShortString());
            repaired = true;
        }
        if (!pyramidApronMarkersPresent(level, origin)
                || !pyramidApronSurfacePresent(level, origin))
        {
            buildPyramidApron(level, origin, preserveCommandAsset);
            writePyramidApronMarkers(level, origin);
            ProjectSeele.LOGGER.info(
                    "NERV pyramid service apron repaired at {}",
                    origin.toShortString());
            repaired = true;
        }
        if (!pyramidGroundAccessPresent(level, origin))
        {
            clearLegacyObservationDeck(level, origin);
            buildCommandBridge(level, origin);
            buildObservationDeck(level, origin);
            buildObservationAccess(level, origin);
            ProjectSeele.LOGGER.info(
                    "NERV pyramid public passage and ground overlook repaired at {}",
                    origin.toShortString());
            repaired = true;
        }
        return repaired;
    }

    private static void buildNervPyramid(ServerLevel level, BlockPos origin)
    {
        boolean preserveCommandAsset =
                LocalMapAssetLoader.commandMarkersPresent(level, origin);
        clearTallEnvelopePyramid(level, origin, preserveCommandAsset);
        clearBentEnvelopePyramid(level, origin, preserveCommandAsset);
        clearPreviousEnvelopePyramid(level, origin, preserveCommandAsset);
        clearLegacyNervPyramid(level, origin, preserveCommandAsset);

        fillPyramidRectangle(level, origin, PYRAMID_BASE_Y,
                PYRAMID_BASE_CENTRE_Z, PYRAMID_BASE_HALF_X,
                PYRAMID_BASE_HALF_Z,
                Blocks.POLISHED_DEEPSLATE.defaultBlockState(),
                preserveCommandAsset);

        for (int y = PYRAMID_BASE_Y + 1; y <= PYRAMID_APEX_Y; y++)
        {
            int halfX = pyramidHalfXAt(y);
            int halfZ = pyramidHalfZAt(y);
            int centreZ = pyramidCentreZAt(y);
            int nextHalfX = y == PYRAMID_APEX_Y ? 0 : pyramidHalfXAt(y + 1);
            int nextHalfZ = y == PYRAMID_APEX_Y ? 0 : pyramidHalfZAt(y + 1);
            int nextCentreZ = y == PYRAMID_APEX_Y
                    ? centreZ : pyramidCentreZAt(y + 1);
            rectangularPyramidShellLayer(level, origin, y,
                    centreZ, halfX, halfZ, nextCentreZ,
                    nextHalfX, nextHalfZ,
                    pyramidShellState(y), preserveCommandAsset);

            // Continuous dark corner ribs and orange cardinal ribs make the
            // huge envelope read as one NERV pyramid from cavern distance.
            BlockState corner = Blocks.BLACK_CONCRETE.defaultBlockState();
            BlockState accent = Blocks.ORANGE_CONCRETE.defaultBlockState();
            pyramidSet(level, origin, -halfX, y,
                    centreZ - halfZ, corner, preserveCommandAsset);
            pyramidSet(level, origin, halfX, y,
                    centreZ - halfZ, corner, preserveCommandAsset);
            pyramidSet(level, origin, -halfX, y,
                    centreZ + halfZ, corner, preserveCommandAsset);
            pyramidSet(level, origin, halfX, y,
                    centreZ + halfZ, corner, preserveCommandAsset);
            pyramidSet(level, origin, 0, y,
                    centreZ - halfZ, accent, preserveCommandAsset);
            pyramidSet(level, origin, 0, y,
                    centreZ + halfZ, accent, preserveCommandAsset);
            pyramidSet(level, origin, -halfX, y,
                    centreZ, accent, preserveCommandAsset);
            pyramidSet(level, origin, halfX, y,
                    centreZ, accent, preserveCommandAsset);
        }

        // Version-specific structural markers keep old, undersized shells from
        // passing the audit merely because a command-module marker exists.
        set(level, origin.offset(-PYRAMID_BASE_HALF_X, PYRAMID_BASE_Y,
                        PYRAMID_BASE_CENTRE_Z - PYRAMID_BASE_HALF_Z),
                Blocks.CHISELED_DEEPSLATE.defaultBlockState());
        set(level, origin.offset(pyramidHalfXAt(PYRAMID_AUDIT_Y),
                        PYRAMID_AUDIT_Y,
                        PYRAMID_CENTRE_Z + pyramidHalfZAt(PYRAMID_AUDIT_Y)),
                Blocks.CRYING_OBSIDIAN.defaultBlockState());
        set(level, origin.offset(0, PYRAMID_APEX_Y, PYRAMID_CENTRE_Z),
                Blocks.REDSTONE_BLOCK.defaultBlockState());
        set(level, origin.offset(0, PYRAMID_APEX_Y + 1, PYRAMID_CENTRE_Z),
                Blocks.BEACON.defaultBlockState());
        set(level, origin.offset(0, PYRAMID_APEX_Y + 2, PYRAMID_CENTRE_Z),
                Blocks.RED_STAINED_GLASS.defaultBlockState());
        buildPyramidApron(level, origin, preserveCommandAsset);
        writePyramidApronMarkers(level, origin);
    }

    /**
     * Replaces the irregular grass/plant fringe around NERV with a level,
     * illuminated service apron. The pyramid interior, LCL and imported
     * command module are never overwritten.
     */
    private static void buildPyramidApron(ServerLevel level, BlockPos origin,
                                          boolean preserveCommandAsset)
    {
        for (int x = -PYRAMID_BASE_HALF_X - PYRAMID_APRON_MARGIN;
             x <= PYRAMID_BASE_HALF_X + PYRAMID_APRON_MARGIN; x++)
        {
            for (int z = PYRAMID_BASE_CENTRE_Z - PYRAMID_BASE_HALF_Z
                         - PYRAMID_APRON_MARGIN;
                 z <= PYRAMID_BASE_CENTRE_Z + PYRAMID_BASE_HALF_Z
                         + PYRAMID_APRON_MARGIN; z++)
            {
                int centredZ = z - PYRAMID_BASE_CENTRE_Z;
                // Preserve authored command-module blocks, not the natural
                // dirt columns between them. Skipping this complete projected
                // envelope was the source of the grass pillars in old saves.
                boolean commandColumn = preserveCommandAsset
                        && LocalMapAssetLoader.commandEnvelopeContains(x, 0, z);
                BlockPos position = origin.offset(x, 0, z);
                if (!level.getFluidState(position).isEmpty()
                        || !level.getFluidState(position.above()).isEmpty())
                {
                    continue;
                }
                BlockState state = level.getBlockState(position);
                clearStaleNaturalColumn(level, position, 1, 32,
                        !commandColumn);
                clearStaleApronSuperstructure(level, origin, x, z,
                        commandColumn);
                if (commandColumn && !isNaturalTerrain(state))
                {
                    if (state.isAir())
                    {
                        set(level, position, pyramidApronState(x, centredZ));
                    }
                    continue;
                }
                if (!state.is(Blocks.GRASS_BLOCK) && !state.is(Blocks.DIRT)
                        && !state.is(Blocks.MOSS_BLOCK) && !state.is(Blocks.STONE)
                        && !state.is(Blocks.GRAVEL) && !state.is(Blocks.SAND)
                        && !state.is(Blocks.COARSE_DIRT) && !state.is(Blocks.ROOTED_DIRT)
                        && !state.is(Blocks.PODZOL) && !state.is(Blocks.MYCELIUM)
                        && !state.is(Blocks.MUD) && !state.is(Blocks.CLAY)
                        && !state.is(Blocks.POLISHED_DEEPSLATE)
                        && !state.is(Blocks.LIGHT_GRAY_CONCRETE)
                        && !state.isAir())
                {
                    continue;
                }
                boolean guide = Math.floorMod(x, 16) <= 1
                        || Math.floorMod(centredZ, 16) <= 1;
                set(level, position, pyramidApronState(x, centredZ));

                if (guide && Math.floorMod(x * 7 + centredZ * 11, 31) == 0)
                {
                    set(level, position.above(), Blocks.LIGHT.defaultBlockState());
                }
            }
        }
    }

    private static BlockState pyramidApronState(int x, int centredZ)
    {
        boolean border = Math.abs(x)
                == PYRAMID_BASE_HALF_X + PYRAMID_APRON_MARGIN
                || Math.abs(centredZ)
                == PYRAMID_BASE_HALF_Z + PYRAMID_APRON_MARGIN;
        boolean guide = Math.floorMod(x, 16) <= 1
                || Math.floorMod(centredZ, 16) <= 1;
        return border
                ? Blocks.CHISELED_POLISHED_BLACKSTONE.defaultBlockState()
                : guide
                        ? Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState()
                        : Blocks.POLISHED_DEEPSLATE.defaultBlockState();
    }
    private static void writePyramidApronMarkers(ServerLevel level,
                                                   BlockPos origin)
    {
        int x = PYRAMID_BASE_HALF_X + PYRAMID_APRON_MARGIN
                - PYRAMID_APRON_MARKER_INSET;
        int z = PYRAMID_BASE_HALF_Z + PYRAMID_APRON_MARGIN
                - PYRAMID_APRON_MARKER_INSET;
        for (int signX : new int[] {-1, 1})
        {
            for (int signZ : new int[] {-1, 1})
            {
                set(level, origin.offset(signX * x, 0,
                                PYRAMID_BASE_CENTRE_Z + signZ * z),
                        Blocks.CHISELED_POLISHED_BLACKSTONE.defaultBlockState());
            }
        }
        set(level, origin.offset(x, 1, PYRAMID_BASE_CENTRE_Z + z),
                Blocks.CRYING_OBSIDIAN.defaultBlockState());
        set(level, origin.offset(-x, 1, PYRAMID_BASE_CENTRE_Z + z),
                Blocks.LODESTONE.defaultBlockState());
    }

    private static boolean pyramidApronMarkersPresent(ServerLevel level,
                                                        BlockPos origin)
    {
        int x = PYRAMID_BASE_HALF_X + PYRAMID_APRON_MARGIN
                - PYRAMID_APRON_MARKER_INSET;
        int z = PYRAMID_BASE_HALF_Z + PYRAMID_APRON_MARGIN
                - PYRAMID_APRON_MARKER_INSET;
        for (int signX : new int[] {-1, 1})
        {
            for (int signZ : new int[] {-1, 1})
            {
                if (!level.getBlockState(origin.offset(signX * x, 0,
                                PYRAMID_BASE_CENTRE_Z + signZ * z))
                        .is(Blocks.CHISELED_POLISHED_BLACKSTONE))
                {
                    return false;
                }
            }
        }
        return level.getBlockState(origin.offset(x, 1,
                        PYRAMID_BASE_CENTRE_Z + z)).is(Blocks.CRYING_OBSIDIAN)
                && level.getBlockState(origin.offset(-x, 1,
                        PYRAMID_BASE_CENTRE_Z + z)).is(Blocks.LODESTONE);
    }
    /**
     * Samples the visible apron instead of trusting migration markers. This
     * catches old worlds where a later terrain pass painted grass back over
     * an otherwise current pyramid.
     */
    private static boolean pyramidApronSurfacePresent(ServerLevel level,
                                                       BlockPos origin)
    {
        int[][] samples = {
                {-96, -112}, {-48, -112}, {48, -112}, {96, -112},
                {-96, 112}, {-48, 112}, {48, 112}, {96, 112},
                {-128, -64}, {-128, 0}, {-128, 64},
                {128, -64}, {128, 0}, {128, 64}
        };
        for (int[] sample : samples)
        {
            BlockState state = level.getBlockState(origin.offset(sample[0], 0,
                    PYRAMID_BASE_CENTRE_Z + sample[1]));
            if (!state.is(Blocks.POLISHED_DEEPSLATE)
                    && !state.is(Blocks.LIGHT_GRAY_CONCRETE)
                    && !state.is(Blocks.CHISELED_POLISHED_BLACKSTONE))
            {
                return false;
            }
            for (int y = 2; y <= 8; y++)
            {
                BlockState above = level.getBlockState(origin.offset(
                        sample[0], y,
                        PYRAMID_BASE_CENTRE_Z + sample[1]));
                if (!above.isAir() && !above.is(Blocks.LIGHT))
                {
                    return false;
                }
            }
        }
        return true;
    }
    /** Removes the rejected v17 tall, rectangular grey envelope. */
    private static void clearTallEnvelopePyramid(ServerLevel level,
                                                  BlockPos origin,
                                                  boolean preserveCommandAsset)
    {
        final int oldBaseY = -22;
        final int oldApexY = 200;
        final int oldHalfX = 70;
        final int oldHalfZ = 100;
        final int oldCentreZ = 31;
        BlockPos baseMarker = origin.offset(-oldHalfX, oldBaseY,
                oldCentreZ - oldHalfZ);
        BlockPos sideMarker = origin.offset(45, 57, 95);
        if (!level.getBlockState(baseMarker).is(Blocks.CHISELED_DEEPSLATE)
                || !level.getBlockState(sideMarker).is(Blocks.CRYING_OBSIDIAN))
        {
            return;
        }
        for (int x = -oldHalfX; x <= oldHalfX; x++)
        {
            for (int z = -oldHalfZ; z <= oldHalfZ; z++)
            {
                clearLegacyPyramidBlock(level, origin, x, oldBaseY,
                        oldCentreZ + z, preserveCommandAsset);
            }
        }
        int height = oldApexY - oldBaseY;
        for (int y = oldBaseY + 1; y <= oldApexY; y++)
        {
            int halfX = steppedLerp(oldHalfX, 0, y - oldBaseY, height);
            int halfZ = steppedLerp(oldHalfZ, 0, y - oldBaseY, height);
            int nextHalfX = y == oldApexY ? 0
                    : steppedLerp(oldHalfX, 0, y + 1 - oldBaseY, height);
            int nextHalfZ = y == oldApexY ? 0
                    : steppedLerp(oldHalfZ, 0, y + 1 - oldBaseY, height);
            for (int x = -halfX; x <= halfX; x++)
            {
                for (int z = -halfZ; z <= halfZ; z++)
                {
                    if (Math.abs(x) >= nextHalfX || Math.abs(z) >= nextHalfZ)
                    {
                        clearLegacyPyramidBlock(level, origin, x, y,
                                oldCentreZ + z, preserveCommandAsset);
                    }
                }
            }
        }
        clearLegacyPyramidBlock(level, origin, 0, oldApexY + 1,
                oldCentreZ, preserveCommandAsset);
        clearLegacyPyramidBlock(level, origin, 0, oldApexY + 2,
                oldCentreZ, preserveCommandAsset);
    }
    /**
     * Removes the v15 two-stage, drifting envelope. Its shoulder kink and
     * moving centre made the lower half read wider and unrelated to the top.
     */
    private static void clearBentEnvelopePyramid(ServerLevel level,
                                                 BlockPos origin,
                                                 boolean preserveCommandAsset)
    {
        BlockPos baseMarker = origin.offset(-70, -22, -100);
        BlockPos shoulderMarker = origin.offset(46, 57, 93);
        if (!level.getBlockState(baseMarker).is(Blocks.CHISELED_DEEPSLATE)
                || !level.getBlockState(shoulderMarker)
                .is(Blocks.CRYING_OBSIDIAN))
        {
            return;
        }
        for (int x = -70; x <= 70; x++)
        {
            for (int z = -100; z <= 100; z++)
            {
                clearLegacyPyramidBlock(level, origin, x, -22, z,
                        preserveCommandAsset);
            }
        }
        for (int y = -21; y <= 84; y++)
        {
            int halfX = y <= 57
                    ? steppedLerp(70, 46, y + 22, 79)
                    : steppedLerp(46, 5, y - 57, 27);
            int halfZ = y <= 57
                    ? steppedLerp(100, 62, y + 22, 79)
                    : steppedLerp(62, 5, y - 57, 27);
            int centreZ = y <= 57
                    ? steppedLerp(0, 31, y + 22, 79) : 31;
            int nextHalfX = y == 84 ? 0 : (y + 1 <= 57
                    ? steppedLerp(70, 46, y + 23, 79)
                    : steppedLerp(46, 5, y + 1 - 57, 27));
            int nextHalfZ = y == 84 ? 0 : (y + 1 <= 57
                    ? steppedLerp(100, 62, y + 23, 79)
                    : steppedLerp(62, 5, y + 1 - 57, 27));
            int nextCentreZ = y == 84 ? centreZ : (y + 1 <= 57
                    ? steppedLerp(0, 31, y + 23, 79) : 31);
            int minZ = centreZ - halfZ;
            int maxZ = centreZ + halfZ;
            int nextMinZ = nextCentreZ - nextHalfZ;
            int nextMaxZ = nextCentreZ + nextHalfZ;
            for (int x = -halfX; x <= halfX; x++)
            {
                for (int z = minZ; z <= maxZ; z++)
                {
                    if (Math.abs(x) >= nextHalfX
                            || z <= nextMinZ || z >= nextMaxZ)
                    {
                        clearLegacyPyramidBlock(level, origin, x, y, z,
                                preserveCommandAsset);
                    }
                }
            }
        }
        clearLegacyPyramidBlock(level, origin, 0, 85, 31,
                preserveCommandAsset);
        clearLegacyPyramidBlock(level, origin, 0, 86, 31,
                preserveCommandAsset);
    }

    /** Removes the rejected v10 near-vertical envelope without touching its NBT interior. */
    private static void clearPreviousEnvelopePyramid(ServerLevel level,
                                                      BlockPos origin,
                                                      boolean preserveCommandAsset)
    {
        BlockPos previousMarker = origin.offset(34, 57, 99);
        BlockPos previousBaseMarker = origin.offset(-46, -22, -43);
        if (!level.getBlockState(previousMarker).is(Blocks.CRYING_OBSIDIAN)
                || !level.getBlockState(previousBaseMarker)
                .is(Blocks.CHISELED_DEEPSLATE))
        {
            return;
        }
        for (int x = -46; x <= 46; x++)
        {
            for (int z = -74; z <= 74; z++)
            {
                clearLegacyPyramidBlock(level, origin, x, -22, 31 + z,
                        preserveCommandAsset);
            }
        }
        for (int y = -21; y <= 84; y++)
        {
            int halfX = y <= 57
                    ? steppedLerp(46, 34, y + 22, 79)
                    : steppedLerp(34, 2, y - 57, 27);
            int halfZ = y <= 57
                    ? steppedLerp(74, 68, y + 22, 79)
                    : steppedLerp(68, 2, y - 57, 27);
            int nextHalfX = y == 84 ? 0 : (y + 1 <= 57
                    ? steppedLerp(46, 34, y + 23, 79)
                    : steppedLerp(34, 2, y + 1 - 57, 27));
            int nextHalfZ = y == 84 ? 0 : (y + 1 <= 57
                    ? steppedLerp(74, 68, y + 23, 79)
                    : steppedLerp(68, 2, y + 1 - 57, 27));
            for (int x = -halfX; x <= halfX; x++)
            {
                for (int z = -halfZ; z <= halfZ; z++)
                {
                    if (Math.abs(x) >= nextHalfX || Math.abs(z) >= nextHalfZ)
                    {
                        clearLegacyPyramidBlock(level, origin, x, y, 31 + z,
                                preserveCommandAsset);
                    }
                }
            }
        }
        clearLegacyPyramidBlock(level, origin, 0, 85, 31,
                preserveCommandAsset);
        clearLegacyPyramidBlock(level, origin, 0, 86, 31,
                preserveCommandAsset);
    }

    private static void clearLegacyNervPyramid(ServerLevel level,
                                                BlockPos origin,
                                                boolean preserveCommandAsset)
    {
        for (int x = -35; x <= 35; x++)
        {
            for (int z = -35; z <= 35; z++)
            {
                clearLegacyPyramidBlock(level, origin, x, 1, z,
                        preserveCommandAsset);
            }
        }
        for (int y = 2; y <= 28; y++)
        {
            int half = Math.max(4, 36 - y);
            for (int i = -half; i <= half; i++)
            {
                clearLegacyPyramidBlock(level, origin, -half, y, i,
                        preserveCommandAsset);
                clearLegacyPyramidBlock(level, origin, half, y, i,
                        preserveCommandAsset);
                clearLegacyPyramidBlock(level, origin, i, y, -half,
                        preserveCommandAsset);
                clearLegacyPyramidBlock(level, origin, i, y, half,
                        preserveCommandAsset);
            }
            if (y % 7 == 0)
            {
                for (int x = -half + 1; x < half; x++)
                {
                    for (int z = -half + 1; z < half; z++)
                    {
                        clearLegacyPyramidBlock(level, origin, x, y, z,
                                preserveCommandAsset);
                    }
                }
            }
        }
        for (int depth = 1; depth <= 20; depth++)
        {
            int y = -2 - depth;
            int half = Math.max(1, 22 - depth);
            for (int i = -half; i <= half; i++)
            {
                clearLegacyPyramidBlock(level, origin, -half, y, i,
                        preserveCommandAsset);
                clearLegacyPyramidBlock(level, origin, half, y, i,
                        preserveCommandAsset);
                clearLegacyPyramidBlock(level, origin, i, y, -half,
                        preserveCommandAsset);
                clearLegacyPyramidBlock(level, origin, i, y, half,
                        preserveCommandAsset);
            }
        }
        for (int y = 28; y <= 30; y++)
        {
            clearLegacyPyramidBlock(level, origin, 0, y, 0,
                    preserveCommandAsset);
        }
    }

    private static void clearLegacyPyramidBlock(ServerLevel level,
                                                 BlockPos origin,
                                                 int x, int y, int z,
                                                 boolean preserveCommandAsset)
    {
        if (preserveCommandAsset
                && (LocalMapAssetLoader.commandEnvelopeContains(x, y, z)
                    || LocalMapAssetLoader.isCommandMarkerOffset(x, y, z)))
        {
            return;
        }
        set(level, origin.offset(x, y, z), Blocks.AIR.defaultBlockState());
    }

    private static int pyramidHalfXAt(int y)
    {
        return steppedLerp(PYRAMID_BASE_HALF_X, PYRAMID_APEX_HALF,
                y - PYRAMID_BASE_Y,
                PYRAMID_APEX_Y - PYRAMID_BASE_Y);
    }

    private static int pyramidCentreZAt(int y)
    {
        return PYRAMID_CENTRE_Z;
    }

    /** Keeps later landscape passes outside the complete command-pyramid island. */
    public static boolean isWithinPyramidFootprint(int relativeX,
                                                   int relativeZ,
                                                   int margin)
    {
        return Math.abs(relativeX) <= PYRAMID_BASE_HALF_X + margin
                && relativeZ >= PYRAMID_BASE_CENTRE_Z
                        - PYRAMID_BASE_HALF_Z - margin
                && relativeZ <= PYRAMID_BASE_CENTRE_Z
                        + PYRAMID_BASE_HALF_Z + margin;
    }

    /** Full rectangular service apron that later terrain passes must preserve. */
    public static boolean isWithinPyramidServiceApron(int relativeX,
                                                       int relativeZ)
    {
        return isWithinPyramidFootprint(relativeX, relativeZ,
                PYRAMID_APRON_MARGIN);
    }

    /** Ground stair and overlook south of the pyramid. */
    public static boolean isWithinPyramidPublicAccess(int relativeX,
                                                       int relativeZ)
    {
        int southFace = PYRAMID_BASE_CENTRE_Z + PYRAMID_BASE_HALF_Z - 2;
        return Math.abs(relativeX) <= 10
                && relativeZ >= southFace
                && relativeZ <= OBSERVATION_Z + 9;
    }
    private static int pyramidHalfZAt(int y)
    {
        return steppedLerp(PYRAMID_BASE_HALF_Z, PYRAMID_APEX_HALF,
                y - PYRAMID_BASE_Y,
                PYRAMID_APEX_Y - PYRAMID_BASE_Y);
    }

    private static int steppedLerp(int start, int end,
                                   int numerator, int denominator)
    {
        float progress = Math.max(0.0F, Math.min(1.0F,
                numerator / (float) denominator));
        return Math.round(start + (end - start) * progress);
    }

    private static BlockState pyramidShellState(int y)
    {
        int band = Math.floorMod(y - PYRAMID_BASE_Y, 14);
        if (band <= 1)
        {
            return Blocks.ORANGE_CONCRETE.defaultBlockState();
        }
        if (y > 72 && band <= 4)
        {
            return Blocks.SMOOTH_QUARTZ.defaultBlockState();
        }
        return band % 4 <= 1 ? Blocks.BLACK_CONCRETE.defaultBlockState()
                : Blocks.POLISHED_BLACKSTONE.defaultBlockState();
    }

    private static void fillPyramidRectangle(ServerLevel level,
                                              BlockPos origin, int y,
                                              int centreZ, int halfX, int halfZ,
                                              BlockState state,
                                              boolean preserveCommandAsset)
    {
        for (int x = -halfX; x <= halfX; x++)
        {
            for (int z = -halfZ; z <= halfZ; z++)
            {
                pyramidSet(level, origin, x, y, centreZ + z,
                        state, preserveCommandAsset);
            }
        }
    }

    private static void rectangularPyramidShellLayer(ServerLevel level,
                                                      BlockPos origin, int y,
                                                      int centreZ,
                                                      int halfX, int halfZ,
                                                      int nextCentreZ,
                                                      int nextHalfX,
                                                      int nextHalfZ,
                                                      BlockState state,
                                                      boolean preserveCommandAsset)
    {
        int minZ = centreZ - halfZ;
        int maxZ = centreZ + halfZ;
        int nextMinZ = nextCentreZ - nextHalfZ;
        int nextMaxZ = nextCentreZ + nextHalfZ;
        for (int x = -halfX; x <= halfX; x++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                if (Math.abs(x) >= nextHalfX
                        || z <= nextMinZ || z >= nextMaxZ)
                {
                    pyramidSet(level, origin, x, y, z, state,
                            preserveCommandAsset);
                }
            }
        }
    }

    private static void pyramidSet(ServerLevel level, BlockPos origin,
                                   int x, int y, int z, BlockState state,
                                   boolean preserveCommandAsset)
    {
        if (preserveCommandAsset
                && LocalMapAssetLoader.isCommandMarkerOffset(x, y, z))
        {
            return;
        }
        set(level, origin.offset(x, y, z), state);
    }

    private static void buildEvaLiftTerminals(ServerLevel level, BlockPos origin)
    {
        for (int x : LIFT_X)
        {
            BlockPos centre = origin.offset(x, 0, -76);
            clearLiftCorridor(level, centre);
            BlockState accent = x < 0 ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                    : x > 0 ? Blocks.RED_CONCRETE.defaultBlockState()
                    : Blocks.PURPLE_CONCRETE.defaultBlockState();
            fillSquare(level, centre, 0, 7,
                    Blocks.POLISHED_DEEPSLATE.defaultBlockState());
            set(level, centre.above(), Blocks.LODESTONE.defaultBlockState());
            for (int y = 1; y <= 20; y++)
            {
                set(level, centre.offset(-7, y, 0), Blocks.IRON_BLOCK.defaultBlockState());
                set(level, centre.offset(7, y, 0), Blocks.IRON_BLOCK.defaultBlockState());
            }
            for (int span = -7; span <= 7; span++)
            {
                set(level, centre.offset(span, 20, 0), span % 4 == 0
                        ? Blocks.REDSTONE_LAMP.defaultBlockState()
                        : Blocks.BLACK_CONCRETE.defaultBlockState());
            }
            for (int z = -75; z <= -36; z++)
            {
                for (int width = -3; width <= 3; width++)
                {
                    set(level, origin.offset(x + width, 1, z),
                            width == 0 && Math.floorMod(z, 6) < 3
                                    ? Blocks.YELLOW_CONCRETE.defaultBlockState()
                                    : Blocks.GRAY_CONCRETE.defaultBlockState());
                }
            }
            buildLiftGantry(level, centre, accent);
        }
    }

    /** Removes only carrier residue inside the three audited 15x15 lift paths. */
    private static void clearLiftCorridor(ServerLevel level, BlockPos centre)
    {
        for (int y = 2; y <= 50; y++)
        {
            for (int x = -IntegratedNervMapBuilder.SHAFT_CLEAR_RADIUS;
                 x <= IntegratedNervMapBuilder.SHAFT_CLEAR_RADIUS; x++)
            {
                for (int z = -IntegratedNervMapBuilder.SHAFT_CLEAR_RADIUS;
                     z <= IntegratedNervMapBuilder.SHAFT_CLEAR_RADIUS; z++)
                {
                    set(level, centre.offset(x, y, z), Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    /** Reachable rear service deck aligned with the real EVA entry-plug socket. */
    private static void buildLiftGantry(ServerLevel level, BlockPos centre,
                                         BlockState accent)
    {
        BlockState frame = Blocks.IRON_BLOCK.defaultBlockState();
        BlockState dark = Blocks.BLACK_CONCRETE.defaultBlockState();
        BlockState light = Blocks.SEA_LANTERN.defaultBlockState();
        BlockState ladder = Blocks.LADDER.defaultBlockState()
                .setValue(LadderBlock.FACING, Direction.NORTH);
        int gantryY = 40;

        for (int y = 2; y <= gantryY; y++)
        {
            set(level, centre.offset(0, y, 18), frame);
            set(level, centre.offset(0, y, 17), ladder);
            if (y % 4 == 0)
            {
                set(level, centre.offset(1, y, 18), light);
            }
        }
        for (int z = 8; z <= 18; z++)
        {
            for (int x = -4; x <= 4; x++)
            {
                BlockState deck = x == 0 && z == 17
                        ? ladder : (x == 0 && z % 3 == 0 ? accent : dark);
                set(level, centre.offset(x, gantryY, z), deck);
                if (Math.abs(x) == 4)
                {
                    set(level, centre.offset(x, gantryY + 1, z),
                            Blocks.IRON_BARS.defaultBlockState());
                    set(level, centre.offset(x, gantryY + 3, z), frame);
                }
            }
            set(level, centre.offset(0, gantryY + 4, z),
                    z % 3 == 0 ? light : frame);
        }
    }

    private static void buildCommandBridge(ServerLevel level, BlockPos origin)
    {
        int exteriorZ = PYRAMID_BASE_CENTRE_Z
                + PYRAMID_BASE_HALF_Z + 8;
        int pressureGateZ = PYRAMID_CENTRE_Z
                + pyramidHalfZAt(7) - 1;
        for (int z = 35; z <= exteriorZ; z++)
        {
            for (int x = -4; x <= 4; x++)
            {
                set(level, origin.offset(x, 2, z), x == 0 && z % 8 < 4
                        ? Blocks.SEA_LANTERN.defaultBlockState()
                        : Blocks.IRON_BLOCK.defaultBlockState());
                // Clear the whole authored-module-to-exterior route. The old
                // code opened headroom only at the pyramid face, so imported
                // command-room walls left every apparent passage as a dead end.
                for (int y = 3; y <= 7; y++)
                {
                    set(level, origin.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
            }
            for (int y = 3; y <= 5; y++)
            {
                set(level, origin.offset(-5, y, z),
                        Blocks.IRON_BARS.defaultBlockState());
                set(level, origin.offset(5, y, z),
                        Blocks.IRON_BARS.defaultBlockState());
            }
        }

        // Open pressure frames mark the imported module boundary and the real
        // pyramid shell without introducing another blocking door.
        for (int gateZ : new int[] {96, pressureGateZ})
        {
            for (int x = -5; x <= 5; x++)
            {
                set(level, origin.offset(x, 8, gateZ),
                        Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState());
            }
            for (int y = 3; y <= 8; y++)
            {
                set(level, origin.offset(-5, y, gateZ),
                        Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState());
                set(level, origin.offset(5, y, gateZ),
                        Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState());
            }
        }
    }
    private static void removeArtificialSun(ServerLevel level, BlockPos origin)
    {
        clearLegacyArtificialSun(level, origin);
    }

    private static void buildForestRing(ServerLevel level, BlockPos origin)
    {
        BlockPos sphereCentre = cavernCentre(origin);
        for (int x = -205; x <= 205; x += 9)
        {
            for (int z = -205; z <= 205; z += 9)
            {
                int distanceSqr = x * x + z * z;
                int localX = sphereCentre.getX() + x - origin.getX();
                int localZ = sphereCentre.getZ() + z - origin.getZ();
                boolean naturalLake = square((localX + 125) / 58.0D)
                        + square((localZ + 125) / 40.0D) <= 1.25D;
                if (distanceSqr < 92 * 92 || distanceSqr > 205 * 205
                        || Math.floorMod(x * 13 + z * 19, 7) > 1
                        || naturalLake
                        || isWithinPyramidFootprint(localX, localZ, 16)
                        || Math.abs(localZ + 76) <= 12)
                {
                    continue;
                }
                BlockPos ground = findGrassSurface(level,
                        new BlockPos(sphereCentre.getX() + x,
                                origin.getY(), sphereCentre.getZ() + z));
                if (ground == null)
                {
                    continue;
                }
                int height = 4 + Math.floorMod(x * 7 + z * 11, 4);
                for (int y = 1; y <= height; y++)
                {
                    set(level, ground.offset(0, y, 0),
                            Blocks.DARK_OAK_LOG.defaultBlockState());
                }
                for (int dx = -2; dx <= 2; dx++)
                {
                    for (int dz = -2; dz <= 2; dz++)
                    {
                        if (Math.abs(dx) + Math.abs(dz) <= 3)
                        {
                            set(level, ground.offset(dx, height + 1, dz),
                                    Blocks.DARK_OAK_LEAVES.defaultBlockState());
                        }
                    }
                }
            }
        }
    }

    private static BlockPos findGrassSurface(ServerLevel level, BlockPos column)
    {
        for (int y = 4; y >= -4; y--)
        {
            BlockPos candidate = column.offset(0, y, 0);
            if (level.getBlockState(candidate).is(Blocks.GRASS_BLOCK))
            {
                return candidate;
            }
        }
        return null;
    }

    private static double square(double value)
    {
        return value * value;
    }

    /**
     * Lights the playable volume without a visible ceiling of lamps. The
     * dimension supplies broad reflected daylight; a tight ground plane keeps
     * paths mob-safe while a sparse 3-D lattice preserves local contrast.
     */
    public static void repairCavernLighting(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "GeoFrontBuilder.repairCavernLighting");
        int floorDeltaY = origin.getY() - cavernCentre(origin).getY();
        int floorRadius = (int) Math.floor(Math.sqrt(
                CAVERN_RADIUS * CAVERN_RADIUS - floorDeltaY * floorDeltaY)) - 14;
        int floorRadiusSqr = floorRadius * floorRadius;

        for (int x = -floorRadius; x <= floorRadius; x += 20)
        {
            for (int z = -floorRadius; z <= floorRadius; z += 20)
            {
                if (x * x + z * z > floorRadiusSqr
                        || lightingExclusion(x, 0, z))
                {
                    continue;
                }
                BlockPos floor = origin.offset(x, 0, CAVERN_CENTRE_Z + z);
                BlockState state = level.getBlockState(floor);
                if (state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.STONE)
                        || state.is(Blocks.DIRT) || state.is(Blocks.SAND)
                        || state.is(Blocks.GRAVEL) || state.is(Blocks.MOSS_BLOCK))
                {
                    set(level, floor, Blocks.SEA_LANTERN.defaultBlockState());
                }
            }
        }

        // A fourteen-block plane gives every walkable gap real block light;
        // ambient dimension light alone would look bright but still permit
        // zero-light hostile spawns.
        for (int x = -floorRadius; x <= floorRadius; x += 14)
        {
            for (int z = -floorRadius; z <= floorRadius; z += 14)
            {
                if (x * x + z * z > floorRadiusSqr
                        || lightingExclusion(x, 4, z))
                {
                    continue;
                }
                BlockPos position = origin.offset(x, 4, CAVERN_CENTRE_Z + z);
                if (level.getBlockState(position).isAir())
                {
                    set(level, position, Blocks.LIGHT.defaultBlockState());
                }
            }
        }

        for (int relativeY = 32; relativeY <= CAVERN_TOP_Y - 28;
             relativeY += 32)
        {
            int sphereY = relativeY - CAVERN_CENTRE_Y;
            int horizontalRadius = (int) Math.floor(Math.sqrt(Math.max(0,
                    CAVERN_RADIUS * CAVERN_RADIUS - sphereY * sphereY))) - 18;
            int horizontalRadiusSqr = horizontalRadius * horizontalRadius;
            for (int x = -horizontalRadius; x <= horizontalRadius; x += 32)
            {
                for (int z = -horizontalRadius; z <= horizontalRadius; z += 32)
                {
                    if (x * x + z * z > horizontalRadiusSqr
                            || lightingExclusion(x, relativeY, z))
                    {
                        continue;
                    }
                    BlockPos position = origin.offset(x, relativeY,
                            CAVERN_CENTRE_Z + z);
                    if (level.getBlockState(position).isAir())
                    {
                        set(level, position, Blocks.LIGHT.defaultBlockState());
                    }
                }
            }
        }

        // Stable audit lights remain well outside every facility footprint.
        set(level, origin.offset(200, 0, CAVERN_CENTRE_Z),
                Blocks.SEA_LANTERN.defaultBlockState());
        set(level, origin.offset(216, 24, CAVERN_CENTRE_Z),
                Blocks.LIGHT.defaultBlockState());
    }

    private static boolean lightingExclusion(int x, int y, int centredZ)
    {
        int relativeZ = CAVERN_CENTRE_Z + centredZ;
        if (y <= PYRAMID_APEX_Y + 16
                && isWithinPyramidFootprint(x, relativeZ, 18))
        {
            return true;
        }
        for (int liftX : LIFT_X)
        {
            if (Math.abs(x - liftX) <= 12
                    && Math.abs(relativeZ - CAVERN_CENTRE_Z) <= 22)
            {
                return true;
            }
        }
        return false;
    }

    private static void buildObservationDeck(ServerLevel level, BlockPos origin)
    {
        BlockPos centre = origin.offset(0, 0, OBSERVATION_Z);
        for (int y = 1; y <= OBSERVATION_Y; y++)
        {
            for (int x : new int[] {-5, 5})
            {
                for (int z : new int[] {-5, 5})
                {
                    set(level, centre.offset(x, y, z), Blocks.IRON_BLOCK.defaultBlockState());
                }
            }
        }
        fillSquare(level, centre, OBSERVATION_Y, 8,
                Blocks.SMOOTH_STONE.defaultBlockState());
        for (int i = -8; i <= 8; i++)
        {
            set(level, centre.offset(-8, OBSERVATION_Y + 1, i),
                    Blocks.IRON_BARS.defaultBlockState());
            set(level, centre.offset(8, OBSERVATION_Y + 1, i),
                    Blocks.IRON_BARS.defaultBlockState());
            if (Math.abs(i) > 3)
            {
                set(level, centre.offset(i, OBSERVATION_Y + 1, -8),
                        Blocks.IRON_BARS.defaultBlockState());
            }
            set(level, centre.offset(i, OBSERVATION_Y + 1, 8),
                    Blocks.IRON_BARS.defaultBlockState());
        }
        set(level, centre.offset(0, OBSERVATION_Y, 0),
                Blocks.LODESTONE.defaultBlockState());
    }

    /**
     * A real supported stair joins the ground-level command passage to the
     * overlook. No teleport or isolated floating deck is involved.
     */
    private static void buildObservationAccess(ServerLevel level,
                                                BlockPos origin)
    {
        int firstZ = PYRAMID_BASE_CENTRE_Z + PYRAMID_BASE_HALF_Z + 9;
        int finalZ = OBSERVATION_Z - 9;
        for (int z = firstZ; z <= finalZ; z++)
        {
            int stepY = 3 + z - firstZ;
            for (int x = -3; x <= 3; x++)
            {
                set(level, origin.offset(x, stepY, z),
                        Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                                .defaultBlockState()
                                .setValue(net.minecraft.world.level.block.StairBlock.FACING,
                                        Direction.SOUTH));
                for (int y = 0; y < stepY; y++)
                {
                    if (Math.abs(x) == 3)
                    {
                        set(level, origin.offset(x, y, z),
                                Blocks.POLISHED_BLACKSTONE_BRICKS
                                        .defaultBlockState());
                    }
                }
            }
            for (int side : new int[] {-4, 4})
            {
                set(level, origin.offset(side, stepY, z),
                        Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState());
                set(level, origin.offset(side, stepY + 1, z),
                        Blocks.IRON_BARS.defaultBlockState());
            }
        }
    }

    private static boolean pyramidGroundAccessPresent(ServerLevel level,
                                                       BlockPos origin)
    {
        int firstZ = PYRAMID_BASE_CENTRE_Z + PYRAMID_BASE_HALF_Z + 9;
        int finalZ = OBSERVATION_Z - 9;
        return level.getBlockState(origin.offset(0, 2, 70))
                        .is(Blocks.IRON_BLOCK)
                && level.getBlockState(origin.offset(0, 4, 70)).isAir()
                && level.getBlockState(origin.offset(0, 2, firstZ - 1))
                        .is(Blocks.IRON_BLOCK)
                && level.getBlockState(origin.offset(0, 3, firstZ))
                        .is(Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS)
                && level.getBlockState(origin.offset(0,
                        3 + finalZ - firstZ, finalZ))
                        .is(Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS)
                && level.getBlockState(origin.offset(0,
                        OBSERVATION_Y, OBSERVATION_Z)).is(Blocks.LODESTONE);
    }

    /** Removes the superseded floating v18 overlook at Z=100. */
    private static void clearLegacyObservationDeck(ServerLevel level,
                                                    BlockPos origin)
    {
        final int oldZ = 100;
        BlockPos centre = origin.offset(0, 0, oldZ);
        if (!level.getBlockState(centre.offset(0, OBSERVATION_Y, 0))
                .is(Blocks.LODESTONE))
        {
            return;
        }
        for (int y = 1; y <= OBSERVATION_Y; y++)
        {
            for (int x : new int[] {-5, 5})
            {
                for (int z : new int[] {-5, 5})
                {
                    BlockPos support = centre.offset(x, y, z);
                    if (level.getBlockState(support).is(Blocks.IRON_BLOCK))
                    {
                        set(level, support, Blocks.AIR.defaultBlockState());
                    }
                }
            }
        }
        for (int x = -8; x <= 8; x++)
        {
            for (int z = -8; z <= 8; z++)
            {
                BlockPos floor = centre.offset(x, OBSERVATION_Y, z);
                if (level.getBlockState(floor).is(Blocks.SMOOTH_STONE)
                        || level.getBlockState(floor).is(Blocks.LODESTONE))
                {
                    set(level, floor, Blocks.AIR.defaultBlockState());
                }
            }
            for (BlockPos rail : new BlockPos[] {
                    centre.offset(-8, OBSERVATION_Y + 1, x),
                    centre.offset(8, OBSERVATION_Y + 1, x),
                    centre.offset(x, OBSERVATION_Y + 1, -8),
                    centre.offset(x, OBSERVATION_Y + 1, 8)})
            {
                if (level.getBlockState(rail).is(Blocks.IRON_BARS))
                {
                    set(level, rail, Blocks.AIR.defaultBlockState());
                }
            }
        }
    }
    private static boolean isCavernStone(BlockState state)
    {
        return state.is(Blocks.DEEPSLATE) || state.is(Blocks.CALCITE)
                || state.is(Blocks.POLISHED_BASALT);
    }

    private static void squarePerimeter(ServerLevel level, BlockPos centre,
                                        int y, int half, BlockState state)
    {
        for (int i = -half; i <= half; i++)
        {
            set(level, centre.offset(-half, y, i), state);
            set(level, centre.offset(half, y, i), state);
            set(level, centre.offset(i, y, -half), state);
            set(level, centre.offset(i, y, half), state);
        }
    }

    private static void fillSquare(ServerLevel level, BlockPos centre, int y,
                                   int half, BlockState state)
    {
        for (int x = -half; x <= half; x++)
        {
            for (int z = -half; z <= half; z++)
            {
                set(level, centre.offset(x, y, z), state);
            }
        }
    }

    /**
     * Removes rejected pyramid/apron revisions which left artificial stone
     * terraces standing above the current service plane.
     *
     * <p>Only cells outside the current sloping shell are eligible. The three
     * EVA terminals and the southern public approach are explicit exclusions,
     * so an installed world's real circulation architecture is never treated
     * as debris.</p>
     */
    private static void clearStaleApronSuperstructure(ServerLevel level,
                                                       BlockPos origin,
                                                       int relativeX,
                                                       int relativeZ,
                                                       boolean commandColumn)
    {
        if (commandColumn
                || isWithinPyramidPublicAccess(relativeX, relativeZ)
                || isWithinEvaLiftTerminal(relativeX, relativeZ))
        {
            return;
        }
        for (int y = 1; y <= 32; y++)
        {
            int halfX = pyramidHalfXAt(y);
            int halfZ = pyramidHalfZAt(y);
            if (Math.abs(relativeX) <= halfX
                    && Math.abs(relativeZ - pyramidCentreZAt(y)) <= halfZ)
            {
                continue;
            }
            BlockPos stale = origin.offset(relativeX, y, relativeZ);
            BlockState state = level.getBlockState(stale);
            if (isRejectedApronMaterial(state))
            {
                set(level, stale, Blocks.AIR.defaultBlockState());
            }
        }
    }

    private static boolean isWithinEvaLiftTerminal(int relativeX,
                                                    int relativeZ)
    {
        for (int liftX : LIFT_X)
        {
            if (Math.abs(relativeX - liftX) <= 10
                    && relativeZ >= -90 && relativeZ <= -34)
            {
                return true;
            }
        }
        return false;
    }

    private static boolean isRejectedApronMaterial(BlockState state)
    {
        return state.is(Blocks.COBBLED_DEEPSLATE)
                || state.is(Blocks.COBBLED_DEEPSLATE_STAIRS)
                || state.is(Blocks.COBBLED_DEEPSLATE_SLAB)
                || state.is(Blocks.COBBLED_DEEPSLATE_WALL)
                || state.is(Blocks.POLISHED_DEEPSLATE)
                || state.is(Blocks.POLISHED_DEEPSLATE_STAIRS)
                || state.is(Blocks.POLISHED_DEEPSLATE_SLAB)
                || state.is(Blocks.POLISHED_DEEPSLATE_WALL)
                || state.is(Blocks.DEEPSLATE_BRICKS)
                || state.is(Blocks.DEEPSLATE_BRICK_STAIRS)
                || state.is(Blocks.DEEPSLATE_BRICK_SLAB)
                || state.is(Blocks.DEEPSLATE_BRICK_WALL)
                || state.is(Blocks.CRACKED_DEEPSLATE_BRICKS)
                || state.is(Blocks.DEEPSLATE_TILES)
                || state.is(Blocks.DEEPSLATE_TILE_STAIRS)
                || state.is(Blocks.DEEPSLATE_TILE_SLAB)
                || state.is(Blocks.DEEPSLATE_TILE_WALL)
                || state.is(Blocks.CRACKED_DEEPSLATE_TILES)
                || state.is(Blocks.CHISELED_DEEPSLATE)
                || state.is(Blocks.POLISHED_BLACKSTONE)
                || state.is(Blocks.POLISHED_BLACKSTONE_BRICKS)
                || state.is(Blocks.CRACKED_POLISHED_BLACKSTONE_BRICKS)
                || state.is(Blocks.SMOOTH_STONE)
                || state.is(Blocks.LIGHT_GRAY_CONCRETE)
                || state.is(Blocks.GRAY_CONCRETE);
    }

    private static void clearStaleNaturalColumn(ServerLevel level,
                                                BlockPos base,
                                                int minimumY, int maximumY,
                                                boolean clearTrees)
    {
        for (int y = minimumY; y <= maximumY; y++)
        {
            BlockPos stale = base.above(y);
            BlockState above = level.getBlockState(stale);
            if (isNaturalTerrain(above)
                    || above.is(Blocks.GRASS)
                    || above.is(Blocks.TALL_GRASS)
                    || above.is(Blocks.FERN)
                    || above.is(Blocks.LARGE_FERN)
                    || above.is(Blocks.SNOW)
                    || above.is(Blocks.DANDELION)
                    || above.is(Blocks.POPPY)
                    || above.is(Blocks.BLUE_ORCHID)
                    || above.is(Blocks.ALLIUM)
                    || above.is(Blocks.AZURE_BLUET)
                    || above.is(Blocks.OXEYE_DAISY)
                    || above.is(Blocks.CORNFLOWER)
                    || above.is(Blocks.LILY_OF_THE_VALLEY)
                    || (clearTrees && (above.is(BlockTags.LOGS)
                            || above.is(BlockTags.LEAVES)
                            || above.is(Blocks.VINE)
                            || above.is(Blocks.AZALEA)
                            || above.is(Blocks.FLOWERING_AZALEA))))
            {
                set(level, stale, Blocks.AIR.defaultBlockState());
            }
        }
    }
    private static boolean isNaturalTerrain(BlockState state)
    {
        return state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.DIRT)
                || state.is(Blocks.MOSS_BLOCK) || state.is(Blocks.STONE)
                || state.is(Blocks.GRAVEL) || state.is(Blocks.SAND)
                || state.is(Blocks.COARSE_DIRT)
                || state.is(Blocks.ROOTED_DIRT)
                || state.is(Blocks.PODZOL) || state.is(Blocks.MYCELIUM)
                || state.is(Blocks.MUD) || state.is(Blocks.CLAY);
    }

    private static void set(ServerLevel level, BlockPos position, BlockState state)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, UPDATE_CLIENTS);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    public record GeoFrontAudit(boolean valid, boolean floor, boolean skySphere,
                                boolean lake, boolean naturalLake,
                                boolean pyramid, boolean legacyInnerPyramidGone,
                                boolean realSky, boolean cavernLighting,
                                int lifts, int gantries, boolean bridge,
                                boolean observation,
                                NervOperationsCentreBuilder.OperationsAudit operations,
                                MagiDeepLabBuilder.MagiAudit magi,
                                TerminalDogmaBuilder.TerminalDogmaAudit terminalDogma,
                                int vanillaLavaSamples)
    {
        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s floor=%s skySphere=%s lclLake=%s naturalLake=%s "
                            + "nervPyramid=%s legacyInnerGone=%s realSky=%s lighting=%s "
                            + "lifts=%d/3 gantries=%d/3 "
                            + "commandBridge=%s observation=%s operations={%s} "
                            + "magi={%s} terminalDogma={%s} vanillaLavaSamples=%d/0",
                    this.valid, this.floor, this.skySphere, this.lake,
                    this.naturalLake, this.pyramid,
                    this.legacyInnerPyramidGone, this.realSky, this.cavernLighting,
                    this.lifts, this.gantries, this.bridge,
                    this.observation, this.operations.summary(), this.magi.summary(),
                    this.terminalDogma.summary(), this.vanillaLavaSamples);
        }
    }
}
