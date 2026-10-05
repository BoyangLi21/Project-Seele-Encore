package com.projectseele.world;

import java.util.Locale;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LeavesBlock;
import net.minecraft.world.level.block.state.BlockState;

import net.minecraft.world.level.levelgen.Heightmap;
/**
 * Builds the terrain and civil infrastructure around the compact Tokyo-3
 * district. The mountain basin is deliberately a walkable shell supported by
 * visible retaining strata rather than a solid 400-block-wide stone volume.
 *
 * <p>Call this after {@link ThirdTokyoSurfaceBuilder#buildDistrict} and before
 * the continuous lift shafts are cut by {@link IntegratedNervMapBuilder}.</p>
 */
public final class Tokyo3LandscapeBuilder
{
    public static final int CITY_PLATFORM_HALF_SIZE = 224;
    public static final int OUTER_TERRAIN_RADIUS = 360;
    public static final int RETAINING_DEPTH = 32;
    public static final int HIGHWAY_Z = -196;
    public static final int HIGHWAY_DECK_Y = 22;
    public static final int RAIL_X = 196;
    public static final int RAIL_DECK_Y = 12;
    public static final int ESTIMATED_MAX_BLOCK_WRITES = 760_000;

    private static final int DEEP_GRID_HALF_SIZE = 208;
    private static final int PERIMETER_DEFENCE_RADIUS = 342;
    private static final int TRANSIT_EXTENT = 312;
    private static final int TRANSIT_PORTAL = 280;
    private static final int TRANSIT_SUPPORT_EXTENT = 276;
    private static final int TRANSIT_LIGHT_EXTENT = 264;
    private static final int RAIL_PORTAL = 286;
    private static final int RESCUE_X = -260;
    private static final int RESCUE_Z = 104;
    private static final int LAUNCH_WARNING_INNER_RADIUS = 15;
    private static final int LAUNCH_WARNING_OUTER_RADIUS = 17;
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    private static final int[] LIFT_X = {-42, 0, 42};
    private static final int[][] RIDGE_AUDIT_POINTS = {
            {0, -336}, {336, 0}, {0, 336}, {-336, 0},
    };

    private Tokyo3LandscapeBuilder() {}

    public static LandscapeAudit build(ServerLevel level)
    {
        return build(level, IntegratedNervMapBuilder.TOKYO3_ORIGIN);
    }

    public static LandscapeAudit build(ServerLevel level, BlockPos origin)
    {
        if (CityLegacyOwnershipR48.inhibits(level, origin, "Tokyo3LandscapeBuilder.build"))
            return inspect(level, origin);
        requireBuildHeight(level, origin);
        buildRetainingStructure(level, origin);
        buildOuterTerrainShell(level, origin);
        buildPerimeterDefences(level, origin);
        buildElevatedExpressway(level, origin);
        buildRailwayAndStation(level, origin);
        buildLaunchSafetyDistrict(level, origin);
        buildMunicipalFacilities(level, origin);
        plantMountainForest(level, origin);
        return inspect(level, origin);
    }

    public static LandscapeAudit inspect(ServerLevel level)
    {
        return inspect(level, IntegratedNervMapBuilder.TOKYO3_ORIGIN);
    }

    public static LandscapeAudit inspect(ServerLevel level, BlockPos origin)
    {
        boolean retainingWall = isRetainingMaterial(level.getBlockState(
                origin.offset(CITY_PLATFORM_HALF_SIZE, -12, 72)));
        boolean underDeck = isStructuralMaterial(level.getBlockState(
                origin.offset(120, -1, 120)));
        boolean deepGrid = isStructuralMaterial(level.getBlockState(
                origin.offset(128, -RETAINING_DEPTH, 112)));

        int ridgePoints = 0;
        for (int[] point : RIDGE_AUDIT_POINTS)
        {
            if (terrainSurfacePresent(level, origin, point[0], point[1]))
            {
                ridgePoints++;
            }
        }

        boolean highway = isRoadSurface(level.getBlockState(
                origin.offset(0, HIGHWAY_DECK_Y, HIGHWAY_Z)));
        boolean westPortal = level.getBlockState(origin.offset(-TRANSIT_PORTAL,
                HIGHWAY_DECK_Y + 8, HIGHWAY_Z)).is(Blocks.ORANGE_CONCRETE);
        boolean eastPortal = level.getBlockState(origin.offset(TRANSIT_PORTAL,
                HIGHWAY_DECK_Y + 8, HIGHWAY_Z)).is(Blocks.ORANGE_CONCRETE);
        boolean railway = level.getBlockState(origin.offset(
                RAIL_X - 3, RAIL_DECK_Y + 1, 0)).is(Blocks.RAIL)
                || level.getBlockState(origin.offset(
                        RAIL_X - 3, RAIL_DECK_Y + 1, 0)).is(Blocks.POWERED_RAIL);
        boolean station = level.getBlockState(origin.offset(
                RAIL_X, RAIL_DECK_Y + 1, 0)).is(Blocks.LODESTONE);

        int safetyZones = 0;
        for (int liftX : LIFT_X)
        {
            // The continuous-shaft pass deliberately replaces the outermost
            // warning-ring cell with the iron carrier rim.  Audit both the
            // rim and a deterministic black warning cell one block inside it
            // instead of demanding yellow concrete at a coordinate whose
            // final owner is the shaft head.
            BlockState rim = level.getBlockState(origin.offset(
                    liftX, 0, LAUNCH_WARNING_OUTER_RADIUS));
            BlockState warning = level.getBlockState(origin.offset(
                    liftX + 2, 0, LAUNCH_WARNING_OUTER_RADIUS - 1));
            if (rim.is(Blocks.IRON_BLOCK) && warning.is(Blocks.BLACK_CONCRETE))
            {
                safetyZones++;
            }
        }
        boolean shaftHeadroom = shaftHeadroomClear(level, origin);
        boolean rescueCentre = columnContains(level, origin, RESCUE_X,
                RESCUE_Z, -48, 96, Blocks.BEACON);

        boolean valid = retainingWall && underDeck && deepGrid
                && ridgePoints == RIDGE_AUDIT_POINTS.length
                && highway && westPortal && eastPortal && railway && station
                && safetyZones == LIFT_X.length && shaftHeadroom
                && rescueCentre;
        return new LandscapeAudit(valid, retainingWall, underDeck, deepGrid,
                ridgePoints, highway, westPortal, eastPortal, railway,
                station, safetyZones, shaftHeadroom, rescueCentre);
    }

    private static void buildRetainingStructure(ServerLevel level, BlockPos origin)
    {
        for (int depth = 1; depth <= RETAINING_DEPTH; depth++)
        {
            BlockState state = retainingState(depth);
            for (int span = -CITY_PLATFORM_HALF_SIZE;
                 span <= CITY_PLATFORM_HALF_SIZE; span++)
            {
                set(level, origin.offset(-CITY_PLATFORM_HALF_SIZE, -depth, span), state);
                set(level, origin.offset(CITY_PLATFORM_HALF_SIZE, -depth, span), state);
                set(level, origin.offset(span, -depth, -CITY_PLATFORM_HALF_SIZE), state);
                set(level, origin.offset(span, -depth, CITY_PLATFORM_HALF_SIZE), state);
            }
        }

        // A sparse under-deck lattice reads as a real engineered platform but
        // avoids another complete 241 x 241 layer.
        BlockState beam = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        for (int axis = -152; axis <= 152; axis += 16)
        {
            for (int span = -156; span <= 156; span++)
            {
                setUnlessShaft(level, origin, axis, -1, span, beam);
                setUnlessShaft(level, origin, span, -1, axis, beam);
            }
        }

        buildSquareContour(level, origin, 152, -8,
                Blocks.POLISHED_BASALT.defaultBlockState());
        buildSquareContour(level, origin, 148, -16,
                Blocks.CHISELED_DEEPSLATE.defaultBlockState());

        // The lower service shelf is a grid, not an expensive solid slab.
        for (int x = -DEEP_GRID_HALF_SIZE; x <= DEEP_GRID_HALF_SIZE; x++)
        {
            for (int z = -DEEP_GRID_HALF_SIZE; z <= DEEP_GRID_HALF_SIZE; z++)
            {
                if (Math.floorMod(x, 16) > 1 && Math.floorMod(z, 16) > 1)
                {
                    continue;
                }
                BlockState state = (x + z) % 32 == 0
                        ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                        : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
                setUnlessShaft(level, origin, x, -RETAINING_DEPTH, z, state);
            }
        }

        for (int x = -128; x <= 128; x += 32)
        {
            for (int z = -128; z <= 128; z += 32)
            {
                buildSupportColumn(level, origin, x, z);
            }
        }
    }

    private static void buildSquareContour(ServerLevel level, BlockPos origin,
                                           int halfSize, int y,
                                           BlockState state)
    {
        for (int inset = 0; inset <= 1; inset++)
        {
            int edge = halfSize - inset;
            for (int span = -edge; span <= edge; span++)
            {
                setUnlessShaft(level, origin, -edge, y, span, state);
                setUnlessShaft(level, origin, edge, y, span, state);
                setUnlessShaft(level, origin, span, y, -edge, state);
                setUnlessShaft(level, origin, span, y, edge, state);
            }
        }
    }

    private static void buildSupportColumn(ServerLevel level, BlockPos origin,
                                           int centreX, int centreZ)
    {
        for (int y = -RETAINING_DEPTH + 1; y <= -2; y++)
        {
            BlockState state = y % 8 == 0
                    ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                    : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
            for (int x = -1; x <= 1; x++)
            {
                for (int z = -1; z <= 1; z++)
                {
                    setUnlessShaft(level, origin, centreX + x, y,
                            centreZ + z, state);
                }
            }
        }
    }

    private static void buildOuterTerrainShell(ServerLevel level, BlockPos origin)
    {
        // Preserve the normal-noise continent. Only this 32-block transition
        // band reconciles the level NERV platform with untouched native
        // terrain, so Tokyo-3 is physically part of a landmass instead of a
        // synthetic disc floating above it.
        final int transitionWidth = 32;
        final int transitionEdge = CITY_PLATFORM_HALF_SIZE + transitionWidth;
        for (int x = -transitionEdge; x <= transitionEdge; x++)
        {
            for (int z = -transitionEdge; z <= transitionEdge; z++)
            {
                int maxAxis = Math.max(Math.abs(x), Math.abs(z));
                if (maxAxis <= CITY_PLATFORM_HALF_SIZE
                        || maxAxis >= transitionEdge)
                {
                    continue;
                }

                int nativeOffset = nativeSurfaceOffset(level, origin, x, z);
                double progress = (maxAxis - CITY_PLATFORM_HALF_SIZE)
                        / (double) transitionWidth;
                double smooth = progress * progress
                        * (3.0D - 2.0D * progress);
                int targetOffset = (int) Math.round(nativeOffset * smooth);
                int worldX = origin.getX() + x;
                int worldZ = origin.getZ() + z;

                if (targetOffset < nativeOffset)
                {
                    for (int y = targetOffset + 1; y <= nativeOffset; y++)
                    {
                        clear(level, new BlockPos(worldX,
                                origin.getY() + y, worldZ));
                    }
                }
                else
                {
                    for (int y = nativeOffset + 1; y <= targetOffset; y++)
                    {
                        BlockState fill = y >= targetOffset - 2
                                ? Blocks.DIRT.defaultBlockState()
                                : Blocks.STONE.defaultBlockState();
                        set(level, new BlockPos(worldX,
                                origin.getY() + y, worldZ), fill);
                    }
                }
                set(level, origin.offset(x, targetOffset, z),
                        Blocks.GRASS_BLOCK.defaultBlockState());
            }
        }
    }

    private static void buildPerimeterDefences(ServerLevel level, BlockPos origin)
    {
        for (int step = 0; step < 720; step++)
        {
            double angle = Math.PI * 2.0 * step / 720.0;
            int x = (int) Math.round(Math.cos(angle) * PERIMETER_DEFENCE_RADIUS);
            int z = (int) Math.round(Math.sin(angle) * PERIMETER_DEFENCE_RADIUS);
            if (defenceOpening(x, z))
            {
                continue;
            }
            int ground = nativeSurfaceOffset(level, origin, x, z);
            for (int y = 1; y <= 4; y++)
            {
                BlockState state = y == 4 && step % 8 < 4
                        ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                        : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
                set(level, origin.offset(x, ground + y, z), state);
            }
            if (step % 60 == 0)
            {
                buildDefencePylon(level, origin.offset(x, ground + 1, z));
            }
        }
    }

    private static void buildDefencePylon(ServerLevel level, BlockPos base)
    {
        for (int y = 0; y <= 12; y++)
        {
            BlockState state = y == 8 || y == 12
                    ? Blocks.REDSTONE_LAMP.defaultBlockState()
                    : Blocks.IRON_BLOCK.defaultBlockState();
            set(level, base.above(y), state);
        }
        for (int x = -2; x <= 2; x++)
        {
            set(level, base.offset(x, 9, 0), Blocks.IRON_BARS.defaultBlockState());
        }
    }

    private static void buildElevatedExpressway(ServerLevel level, BlockPos origin)
    {
        for (int x = -TRANSIT_EXTENT; x <= TRANSIT_EXTENT; x++)
        {
            for (int z = -5; z <= 5; z++)
            {
                BlockState deck = Math.abs(z) == 5
                        ? Blocks.POLISHED_DEEPSLATE.defaultBlockState()
                        : Blocks.SMOOTH_STONE.defaultBlockState();
                BlockState road = z == 0
                        ? Blocks.YELLOW_CONCRETE.defaultBlockState()
                        : Math.abs(z) == 4
                                ? Blocks.GRAY_CONCRETE.defaultBlockState()
                                : Blocks.BLACK_CONCRETE.defaultBlockState();
                set(level, origin.offset(x, HIGHWAY_DECK_Y - 1,
                        HIGHWAY_Z + z), deck);
                set(level, origin.offset(x, HIGHWAY_DECK_Y,
                        HIGHWAY_Z + z), road);
            }
            set(level, origin.offset(x, HIGHWAY_DECK_Y + 1, HIGHWAY_Z - 6),
                    Blocks.IRON_BARS.defaultBlockState());
            set(level, origin.offset(x, HIGHWAY_DECK_Y + 1, HIGHWAY_Z + 6),
                    Blocks.IRON_BARS.defaultBlockState());
        }

        for (int x = -TRANSIT_SUPPORT_EXTENT;
             x <= TRANSIT_SUPPORT_EXTENT; x += 24)
        {
            if (Math.abs(x - RAIL_X) <= 10)
            {
                continue;
            }
            int ground = nativeSurfaceOffset(level, origin, x, HIGHWAY_Z);
            for (int y = ground + 1; y < HIGHWAY_DECK_Y - 1; y++)
            {
                for (int dx = -1; dx <= 1; dx++)
                {
                    for (int dz = -1; dz <= 1; dz++)
                    {
                        set(level, origin.offset(x + dx, y,
                                HIGHWAY_Z + dz), Blocks.IRON_BLOCK.defaultBlockState());
                    }
                }
            }
        }

        buildHighwayTunnel(level, origin, -1);
        buildHighwayTunnel(level, origin, 1);
        buildHighwayLighting(level, origin);
    }

    private static void buildHighwayTunnel(ServerLevel level, BlockPos origin,
                                           int direction)
    {
        int start = direction < 0 ? -TRANSIT_EXTENT : TRANSIT_PORTAL;
        int end = direction < 0 ? -TRANSIT_PORTAL : TRANSIT_EXTENT;
        int minimum = Math.min(start, end);
        int maximum = Math.max(start, end);
        for (int x = minimum; x <= maximum; x++)
        {
            for (int z = -6; z <= 6; z++)
            {
                for (int y = 1; y <= 7; y++)
                {
                    BlockPos position = origin.offset(x, HIGHWAY_DECK_Y + y,
                            HIGHWAY_Z + z);
                    if (Math.abs(z) == 6 || y == 7)
                    {
                        set(level, position,
                                com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                    }
                    else
                    {
                        clear(level, position);
                    }
                }
            }
        }

        int portalX = direction < 0 ? -TRANSIT_PORTAL : TRANSIT_PORTAL;
        for (int z = -7; z <= 7; z++)
        {
            set(level, origin.offset(portalX, HIGHWAY_DECK_Y + 8,
                    HIGHWAY_Z + z), Blocks.ORANGE_CONCRETE.defaultBlockState());
        }
        for (int y = 1; y <= 8; y++)
        {
            set(level, origin.offset(portalX, HIGHWAY_DECK_Y + y,
                    HIGHWAY_Z - 7), Blocks.ORANGE_CONCRETE.defaultBlockState());
            set(level, origin.offset(portalX, HIGHWAY_DECK_Y + y,
                    HIGHWAY_Z + 7), Blocks.ORANGE_CONCRETE.defaultBlockState());
        }
    }

    private static void buildHighwayLighting(ServerLevel level, BlockPos origin)
    {
        for (int x = -TRANSIT_LIGHT_EXTENT;
             x <= TRANSIT_LIGHT_EXTENT; x += 24)
        {
            for (int side : new int[] {-7, 7})
            {
                for (int y = 1; y <= 6; y++)
                {
                    set(level, origin.offset(x, HIGHWAY_DECK_Y + y,
                            HIGHWAY_Z + side), Blocks.IRON_BARS.defaultBlockState());
                }
                set(level, origin.offset(x, HIGHWAY_DECK_Y + 6,
                        HIGHWAY_Z + side), Blocks.SEA_LANTERN.defaultBlockState());
            }
        }
    }

    private static void buildRailwayAndStation(ServerLevel level, BlockPos origin)
    {
        for (int z = -TRANSIT_EXTENT; z <= TRANSIT_EXTENT; z++)
        {
            for (int x = -6; x <= 6; x++)
            {
                set(level, origin.offset(RAIL_X + x, RAIL_DECK_Y, z),
                        Math.abs(x) >= 5
                                ? Blocks.POLISHED_DEEPSLATE.defaultBlockState()
                                : Blocks.SMOOTH_STONE.defaultBlockState());
                for (int y = RAIL_DECK_Y + 1; y <= RAIL_DECK_Y + 7; y++)
                {
                    clear(level, origin.offset(RAIL_X + x, y, z));
                }
            }

            for (int trackX : new int[] {RAIL_X - 3, RAIL_X + 3})
            {
                BlockState rail = Math.floorMod(z, 16) == 0
                        ? Blocks.POWERED_RAIL.defaultBlockState()
                        : Blocks.RAIL.defaultBlockState();
                if (rail.is(Blocks.POWERED_RAIL))
                {
                    set(level, origin.offset(trackX, RAIL_DECK_Y, z),
                            Blocks.REDSTONE_BLOCK.defaultBlockState());
                }
                set(level, origin.offset(trackX, RAIL_DECK_Y + 1, z), rail);
            }

            int terrain = nativeSurfaceOffset(level, origin, RAIL_X, z);
            if (terrain > RAIL_DECK_Y + 1)
            {
                int wallTop = Math.min(terrain + 1, RAIL_DECK_Y + 8);
                for (int y = RAIL_DECK_Y + 1; y <= wallTop; y++)
                {
                    set(level, origin.offset(RAIL_X - 7, y, z),
                            Blocks.DEEPSLATE_BRICKS.defaultBlockState());
                    set(level, origin.offset(RAIL_X + 7, y, z),
                            Blocks.DEEPSLATE_BRICKS.defaultBlockState());
                }
                if (terrain >= RAIL_DECK_Y + 7)
                {
                    for (int x = -7; x <= 7; x++)
                    {
                        set(level, origin.offset(RAIL_X + x,
                                RAIL_DECK_Y + 8, z),
                                Blocks.DEEPSLATE_BRICKS.defaultBlockState());
                    }
                }
            }
        }
        buildRailStation(level, origin);
        buildRailPortal(level, origin, -RAIL_PORTAL);
        buildRailPortal(level, origin, RAIL_PORTAL);
    }

    private static void buildRailStation(ServerLevel level, BlockPos origin)
    {
        for (int z = -28; z <= 28; z++)
        {
            for (int x = -1; x <= 1; x++)
            {
                set(level, origin.offset(RAIL_X + x, RAIL_DECK_Y + 1, z),
                        z % 8 == 0
                                ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                                : Blocks.SMOOTH_QUARTZ.defaultBlockState());
            }
            for (int x : new int[] {-8, 8})
            {
                set(level, origin.offset(RAIL_X + x, RAIL_DECK_Y + 1, z),
                        Blocks.SMOOTH_STONE.defaultBlockState());
                if (Math.floorMod(z, 8) == 0)
                {
                    for (int y = 2; y <= 9; y++)
                    {
                        set(level, origin.offset(RAIL_X + x,
                                RAIL_DECK_Y + y, z),
                                Blocks.IRON_BLOCK.defaultBlockState());
                    }
                }
            }
            for (int x = -9; x <= 9; x++)
            {
                set(level, origin.offset(RAIL_X + x, RAIL_DECK_Y + 10, z),
                        Math.floorMod(x + z, 9) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
            }
        }
        set(level, origin.offset(RAIL_X, RAIL_DECK_Y + 1, 0),
                Blocks.LODESTONE.defaultBlockState());
    }

    private static void buildRailPortal(ServerLevel level, BlockPos origin,
                                        int z)
    {
        for (int x = -8; x <= 8; x++)
        {
            set(level, origin.offset(RAIL_X + x, RAIL_DECK_Y + 9, z),
                    Blocks.ORANGE_CONCRETE.defaultBlockState());
        }
        for (int x : new int[] {-8, 8})
        {
            for (int y = 1; y <= 9; y++)
            {
                set(level, origin.offset(RAIL_X + x, RAIL_DECK_Y + y, z),
                        Blocks.ORANGE_CONCRETE.defaultBlockState());
            }
        }
    }

    private static void buildLaunchSafetyDistrict(ServerLevel level,
                                                  BlockPos origin)
    {
        for (int liftX : LIFT_X)
        {
            buildLaunchSafetyZone(level, origin, liftX);
        }
    }

    private static void buildLaunchSafetyZone(ServerLevel level, BlockPos origin,
                                              int liftX)
    {
        for (int x = -LAUNCH_WARNING_OUTER_RADIUS;
             x <= LAUNCH_WARNING_OUTER_RADIUS; x++)
        {
            for (int z = -LAUNCH_WARNING_OUTER_RADIUS;
                 z <= LAUNCH_WARNING_OUTER_RADIUS; z++)
            {
                int edge = Math.max(Math.abs(x), Math.abs(z));
                if (edge < LAUNCH_WARNING_INNER_RADIUS
                        || edge > LAUNCH_WARNING_OUTER_RADIUS)
                {
                    continue;
                }
                BlockState warning = Math.floorMod(x + z, 4) < 2
                        ? Blocks.YELLOW_CONCRETE.defaultBlockState()
                        : Blocks.BLACK_CONCRETE.defaultBlockState();
                set(level, origin.offset(liftX + x, 0, z), warning);
            }
        }

        for (int x : new int[] {-LAUNCH_WARNING_OUTER_RADIUS,
                LAUNCH_WARNING_OUTER_RADIUS})
        {
            for (int z : new int[] {-LAUNCH_WARNING_OUTER_RADIUS,
                    LAUNCH_WARNING_OUTER_RADIUS})
            {
                for (int y = 1; y <= 8; y++)
                {
                    set(level, origin.offset(liftX + x, y, z),
                            y == 4 || y == 8
                                    ? Blocks.REDSTONE_LAMP.defaultBlockState()
                                    : Blocks.IRON_BLOCK.defaultBlockState());
                }
            }
        }
        // The old bunker sat directly in the EVA's forward sortie lane.
        // Keep the observation/control cell behind the carrier opening, where
        // it can watch the shaft without becoming a 60-metre trip hazard.
        buildLaunchControlBunker(level, origin.offset(liftX, 0, -26));
    }

    private static void buildLaunchControlBunker(ServerLevel level,
                                                 BlockPos centre)
    {
        for (int x = -5; x <= 5; x++)
        {
            for (int z = -3; z <= 3; z++)
            {
                set(level, centre.offset(x, 0, z),
                        Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                set(level, centre.offset(x, 5, z),
                        Blocks.SMOOTH_STONE.defaultBlockState());
                for (int y = 1; y <= 4; y++)
                {
                    if (Math.abs(x) == 5 || Math.abs(z) == 3)
                    {
                        BlockState wall = y == 3 && Math.abs(x) < 4
                                ? Blocks.ORANGE_STAINED_GLASS.defaultBlockState()
                                : Blocks.GRAY_CONCRETE.defaultBlockState();
                        set(level, centre.offset(x, y, z), wall);
                    }
                    else
                    {
                        clear(level, centre.offset(x, y, z));
                    }
                }
            }
        }
        for (int y = 1; y <= 3; y++)
        {
            clear(level, centre.offset(0, y, -3));
        }
        set(level, centre.offset(0, 1, 2), Blocks.REDSTONE_LAMP.defaultBlockState());
    }

    private static void buildMunicipalFacilities(ServerLevel level,
                                                 BlockPos origin)
    {
        int rescueX = RESCUE_X;
        int rescueZ = RESCUE_Z;
        int ground = nativeSurfaceOffset(level, origin,
                rescueX, rescueZ);
        BlockPos centre = origin.offset(rescueX, ground, rescueZ);
        for (int x = -10; x <= 10; x++)
        {
            for (int z = -7; z <= 7; z++)
            {
                set(level, centre.offset(x, 0, z),
                        Blocks.SMOOTH_STONE.defaultBlockState());
                set(level, centre.offset(x, 7, z),
                        Math.floorMod(x + z, 7) == 0
                                ? Blocks.REDSTONE_LAMP.defaultBlockState()
                                : Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
                for (int y = 1; y <= 6; y++)
                {
                    if (Math.abs(x) == 10 || Math.abs(z) == 7)
                    {
                        BlockState wall = y >= 3 && y <= 5 && z == -7
                                ? Blocks.RED_STAINED_GLASS.defaultBlockState()
                                : Blocks.WHITE_CONCRETE.defaultBlockState();
                        set(level, centre.offset(x, y, z), wall);
                    }
                    else
                    {
                        clear(level, centre.offset(x, y, z));
                    }
                }
            }
        }
        for (int x = -7; x <= 7; x++)
        {
            set(level, centre.offset(x, 0, -8),
                    Math.floorMod(x, 4) < 2
                            ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                            : Blocks.BLACK_CONCRETE.defaultBlockState());
        }
        set(level, centre.above(), Blocks.BEACON.defaultBlockState());

        buildHelipad(level, origin, -300, 160);
    }

    private static void buildHelipad(ServerLevel level, BlockPos origin,
                                     int centreX, int centreZ)
    {
        int ground = nativeSurfaceOffset(level, origin,
                centreX, centreZ) + 1;
        for (int x = -9; x <= 9; x++)
        {
            for (int z = -9; z <= 9; z++)
            {
                int radiusSquared = x * x + z * z;
                if (radiusSquared > 81)
                {
                    continue;
                }
                BlockState state = Math.abs(x) <= 1
                        || (Math.abs(z) <= 1 && Math.abs(x) <= 6)
                                ? Blocks.WHITE_CONCRETE.defaultBlockState()
                                : radiusSquared >= 64
                                        ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                                        : Blocks.GRAY_CONCRETE.defaultBlockState();
                set(level, origin.offset(centreX + x, ground, centreZ + z), state);
            }
        }
    }

    private static void plantMountainForest(ServerLevel level, BlockPos origin)
    {
        for (int x = -330; x <= 330; x += 11)
        {
            for (int z = -330; z <= 330; z += 11)
            {
                if (!insideOuterTerrain(x, z) || transitOrFacilityCorridor(x, z)
                        || Math.floorMod(hash(x, z), 19) != 0)
                {
                    continue;
                }
                int y = nativeSurfaceOffset(level, origin, x, z);
                if (y < -12 || y > 64)
                {
                    continue;
                }
                buildConifer(level, origin.offset(x, y + 1, z),
                        5 + Math.floorMod(hash(z, x), 4));
            }
        }
    }

    private static void buildConifer(ServerLevel level, BlockPos base,
                                     int height)
    {
        for (int y = 0; y < height; y++)
        {
            set(level, base.above(y), Blocks.SPRUCE_LOG.defaultBlockState());
        }
        BlockState leaves = Blocks.SPRUCE_LEAVES.defaultBlockState()
                .setValue(LeavesBlock.PERSISTENT, true);
        for (int y = 2; y <= height; y++)
        {
            int radius = y >= height - 1 ? 1 : (height - y) % 3 == 0 ? 3 : 2;
            for (int x = -radius; x <= radius; x++)
            {
                for (int z = -radius; z <= radius; z++)
                {
                    if (Math.abs(x) + Math.abs(z) > radius + 1
                            || x == 0 && z == 0 && y < height)
                    {
                        continue;
                    }
                    set(level, base.offset(x, y, z), leaves);
                }
            }
        }
    }

    private static int nativeSurfaceOffset(ServerLevel level, BlockPos origin,
                                           int x, int z)
    {
        int surface = level.getHeight(
                Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                origin.getX() + x, origin.getZ() + z) - 1;
        return Math.max(-48, Math.min(96, surface - origin.getY()));
    }

    /**
     * Audits the native ridge beneath later perimeter details. Heightmaps
     * report the highest motion-blocking block in a column, which can become
     * a defence fitting or another non-terrain detail after the landscape
     * itself has been built. The ridge is still intact in that case, so walk
     * down the bounded surface band instead of treating the decoration as the
     * ground.
     */
    private static boolean terrainSurfacePresent(ServerLevel level,
                                                 BlockPos origin,
                                                 int x, int z)
    {
        int top = nativeSurfaceOffset(level, origin, x, z);
        for (int y = top; y >= -48; y--)
        {
            if (isTerrainSurface(level.getBlockState(
                    origin.offset(x, y, z))))
            {
                return true;
            }
        }
        return false;
    }

    private static BlockState retainingState(int depth)
    {
        // Preserve the six-layer deepslate-brick foundation already owned by
        // ThirdTokyoSurfaceBuilder.  The deeper bands remain visually varied.
        if (depth <= 6)
        {
            return Blocks.DEEPSLATE_BRICKS.defaultBlockState();
        }
        if (depth % 8 == 0)
        {
            return Blocks.ORANGE_CONCRETE.defaultBlockState();
        }
        if (depth % 4 == 0)
        {
            return Blocks.CHISELED_DEEPSLATE.defaultBlockState();
        }
        return Blocks.DEEPSLATE_BRICKS.defaultBlockState();
    }

    private static boolean insideOuterTerrain(int x, int z)
    {
        return Math.max(Math.abs(x), Math.abs(z)) > CITY_PLATFORM_HALF_SIZE
                && x * x + z * z <= OUTER_TERRAIN_RADIUS * OUTER_TERRAIN_RADIUS;
    }

    private static boolean defenceOpening(int x, int z)
    {
        boolean highway = Math.abs(z - HIGHWAY_Z) <= 9 && Math.abs(x) >= 205;
        boolean railway = Math.abs(x - RAIL_X) <= 9 && Math.abs(z) >= 205;
        return highway || railway;
    }

    private static boolean transitOrFacilityCorridor(int x, int z)
    {
        if (Math.abs(z - HIGHWAY_Z) <= 14 || Math.abs(x - RAIL_X) <= 12)
        {
            return true;
        }
        if (Math.abs(x - RESCUE_X) <= 18 && Math.abs(z - RESCUE_Z) <= 15
                || Math.abs(x + 300) <= 12 && Math.abs(z - 160) <= 12)
        {
            return true;
        }
        for (int liftX : LIFT_X)
        {
            if (Math.abs(x - liftX) <= 16 && Math.abs(z) <= 28)
            {
                return true;
            }
        }
        return false;
    }

    private static boolean columnContains(ServerLevel level, BlockPos origin,
                                          int x, int z, int minimumY,
                                          int maximumY, Block block)
    {
        int start = Math.max(minimumY,
                level.getMinBuildHeight() - origin.getY());
        int end = Math.min(maximumY,
                level.getMaxBuildHeight() - origin.getY() - 1);
        BlockPos.MutableBlockPos cursor = new BlockPos.MutableBlockPos();
        for (int y = start; y <= end; y++)
        {
            cursor.set(origin.getX() + x, origin.getY() + y,
                    origin.getZ() + z);
            if (level.getBlockState(cursor).is(block))
            {
                return true;
            }
        }
        return false;
    }

    private static boolean shaftHeadroomClear(ServerLevel level, BlockPos origin)
    {
        for (int liftX : LIFT_X)
        {
            for (int y : new int[] {1, 20, 40})
            {
                if (!level.getBlockState(origin.offset(liftX, y, 0)).isAir())
                {
                    return false;
                }
            }
        }
        return true;
    }

    private static boolean isProtectedShaft(int x, int z)
    {
        for (int liftX : LIFT_X)
        {
            // Runtime landscape repair happens after the 25x25 shaft shells
            // already exist. Protect the complete shell, not only the old
            // 15x15 prototype core, or the Y=79 under-deck lattice cuts all
            // three continuous launch routes in one pass.
            if (Math.abs(x - liftX)
                    <= IntegratedNervMapBuilder.SHAFT_OUTER_RADIUS
                    && Math.abs(z)
                    <= IntegratedNervMapBuilder.SHAFT_OUTER_RADIUS)
            {
                return true;
            }
        }
        return false;
    }

    private static boolean isRetainingMaterial(BlockState state)
    {
        return state.is(Blocks.DEEPSLATE_BRICKS)
                || state.is(Blocks.CHISELED_DEEPSLATE)
                || state.is(Blocks.ORANGE_CONCRETE);
    }

    private static boolean isStructuralMaterial(BlockState state)
    {
        return state.is(Blocks.POLISHED_DEEPSLATE)
                || state.is(com.projectseele.world.NervMaterials.STRUCTURAL_SHELL)
                || state.is(Blocks.ORANGE_CONCRETE);
    }

    private static boolean isTerrainSurface(BlockState state)
    {
        return state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.SNOW)
                || state.is(Blocks.COARSE_DIRT)
                || state.is(Blocks.DIRT) || state.is(Blocks.PODZOL)
                || state.is(Blocks.SAND) || state.is(Blocks.GRAVEL)
                || state.is(Blocks.MOSS_BLOCK) || state.is(Blocks.STONE)
                || state.is(Blocks.ANDESITE) || state.is(Blocks.CALCITE)
                || state.is(Blocks.SNOW_BLOCK);
    }

    private static boolean isRoadSurface(BlockState state)
    {
        return state.is(Blocks.BLACK_CONCRETE) || state.is(Blocks.GRAY_CONCRETE)
                || state.is(Blocks.YELLOW_CONCRETE);
    }

    private static int hash(int x, int z)
    {
        return x * 73_428_767 ^ z * 91_293_191 ^ x * z * 31;
    }

    private static double clamp(double value, double minimum, double maximum)
    {
        return Math.max(minimum, Math.min(maximum, value));
    }

    private static void setUnlessShaft(ServerLevel level, BlockPos origin,
                                       int x, int y, int z, BlockState state)
    {
        if (!isProtectedShaft(x, z))
        {
            set(level, origin.offset(x, y, z), state);
        }
    }

    private static void requireBuildHeight(ServerLevel level, BlockPos origin)
    {
        int requiredMin = origin.getY() - RETAINING_DEPTH;
        int requiredMax = origin.getY() + 48;
        if (requiredMin < level.getMinBuildHeight()
                || requiredMax >= level.getMaxBuildHeight())
        {
            throw new IllegalStateException(String.format(Locale.ROOT,
                    "Tokyo-3 landscape requires Y=%d..%d but dimension provides %d..%d",
                    requiredMin, requiredMax, level.getMinBuildHeight(),
                    level.getMaxBuildHeight() - 1));
        }
    }

    private static void clear(ServerLevel level, BlockPos position)
    {
        if (!level.getBlockState(position).isAir())
        {
            set(level, position, Blocks.AIR.defaultBlockState());
        }
    }

    private static void set(ServerLevel level, BlockPos position, BlockState state)
    {
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, UPDATE_CLIENTS);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    public record LandscapeAudit(boolean valid, boolean retainingWall,
                                 boolean underDeck, boolean deepGrid,
                                 int ridgePoints, boolean highway,
                                 boolean westPortal, boolean eastPortal,
                                 boolean railway, boolean station,
                                 int safetyZones, boolean shaftHeadroom,
                                 boolean rescueCentre)
    {
        public static LandscapeAudit imported()
        {
            return new LandscapeAudit(true, true, true, true, 4,
                    true, true, true, true, true, 3, true, true);
        }

        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s retainingWall=%s underDeck=%s deepGrid=%s "
                            + "ridgePoints=%d/4 highway=%s portals=%s/%s "
                            + "railway=%s station=%s safetyZones=%d/3 "
                            + "shaftHeadroom=%s rescueCentre=%s budget<=%d",
                    this.valid, this.retainingWall, this.underDeck,
                    this.deepGrid, this.ridgePoints, this.highway,
                    this.westPortal, this.eastPortal, this.railway,
                    this.station, this.safetyZones, this.shaftHeadroom,
                    this.rescueCentre, ESTIMATED_MAX_BLOCK_WRITES);
        }
    }
}
