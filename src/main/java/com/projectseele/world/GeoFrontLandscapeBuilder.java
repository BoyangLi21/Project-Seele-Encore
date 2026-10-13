package com.projectseele.world;

import java.util.Locale;

import com.projectseele.registry.ModFluids;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LadderBlock;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Adds the inhabited landscape between the NERV pyramid and the cavern wall.
 *
 * <p>The builder intentionally owns only the outer GeoFront ring.  The centre
 * pyramid, operations centre, command bridge and the three continuous EVA
 * shafts remain owned by their dedicated builders.  This makes the landscape
 * safe to rebuild without damaging an active sortie route.</p>
 */
public final class GeoFrontLandscapeBuilder
{
    private static final int SHORE_INNER_RADIUS = 73;
    private static final int SHORE_OUTER_RADIUS = 78;
    private static final int SERVICE_ROAD_INNER_RADIUS = 176;
    private static final int SERVICE_ROAD_OUTER_RADIUS = 182;
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;

    private static final BlockPos PUMP_CENTRE = new BlockPos(84, 0, 28);
    private static final BlockPos MAINTENANCE_CENTRE = new BlockPos(-78, 0, 52);
    private static final BlockPos[] BLAST_BUNKERS = {
            new BlockPos(-98, 0, -22),
            new BlockPos(98, 0, -22)
    };
    private static final BlockPos ARBORETUM_CENTRE =
            new BlockPos(-202, 0, 74);
    private static final BlockPos STAFF_CAMPUS_CENTRE =
            new BlockPos(198, 0, 58);
    private static final BlockPos RESEARCH_CAMPUS_CENTRE =
            new BlockPos(0, 0, -242);
    private static final int[][] FOREST_CENTRES = {
            {-185, -130}, {-160, -80}, {-150, -20}, {-135, 55},
            {185, -130}, {160, -80}, {150, -20}, {135, 55},
            {-90, -250}, {0, -270}, {90, -250},
            {-105, 80}, {105, 80}
    };

    private GeoFrontLandscapeBuilder() {}

    public static LandscapeAudit build(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level);
        return build(level, IntegratedNervMapBuilder.GEOFRONT_ORIGIN);
    }

    public static LandscapeAudit build(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level, origin);
        PerformanceCounters.recordBuilderCall();
        buildLclShore(level, origin);
        buildServiceRoad(level, origin);
        buildDocks(level, origin);
        buildPumpingStation(level, origin);
        buildMaintenanceTerrace(level, origin);
        buildBlastBunkers(level, origin);
        enrichForest(level, origin);
        buildInhabitedCampus(level, origin);
        return inspect(level, origin);
    }

    /** Bounded upgrade path for old saves; never rebuilds the 640-block shell. */
    public static LandscapeAudit ensure(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level, origin);
        LandscapeAudit audit = inspect(level, origin);
        if (!audit.valid())
        {
            audit = build(level, origin);
        }
        return audit;
    }

    public static LandscapeAudit inspect(ServerLevel level)
    {
        return inspect(level, IntegratedNervMapBuilder.GEOFRONT_ORIGIN);
    }

    public static LandscapeAudit inspect(ServerLevel level, BlockPos origin)
    {
        boolean shore = level.getBlockState(origin.offset(75, 2, 0))
                .is(Blocks.CHISELED_DEEPSLATE);

        int docks = 0;
        for (int x : new int[] {-55, 55})
        {
            if (level.getBlockState(origin.offset(x, 2, 12))
                    .is(Blocks.SMOOTH_STONE))
            {
                docks++;
            }
        }

        boolean pumpHouse = level.getBlockState(origin.offset(
                PUMP_CENTRE.getX(), 8, PUMP_CENTRE.getZ()))
                .is(Blocks.LODESTONE);
        boolean lclIntake = level.getFluidState(origin.offset(72, 1, 28))
                .getFluidType() == ModFluids.LCL_TYPE.get()
                && level.getFluidState(origin.offset(
                PUMP_CENTRE.getX(), 2, PUMP_CENTRE.getZ()))
                .getFluidType() == ModFluids.LCL_TYPE.get();
        boolean serviceRoad = isServiceRoad(level.getBlockState(
                origin.offset(20, 0, GeoFrontBuilder.CAVERN_CENTRE_Z - 180)));
        boolean maintenance = level.getBlockState(origin.offset(
                MAINTENANCE_CENTRE.getX(), 9, MAINTENANCE_CENTRE.getZ()))
                .is(Blocks.LODESTONE);

        int bunkers = 0;
        for (BlockPos centre : BLAST_BUNKERS)
        {
            if (level.getBlockState(origin.offset(
                    centre.getX(), 7, centre.getZ())).is(Blocks.LODESTONE))
            {
                bunkers++;
            }
        }

        int forestGroves = 0;
        for (int[] centre : FOREST_CENTRES)
        {
            int groundY = forestGroundY(level, origin, centre[0], centre[1]);
            if (level.getBlockState(origin.offset(
                    centre[0], groundY + 1, centre[1]))
                    .is(Blocks.STRIPPED_DARK_OAK_LOG))
            {
                forestGroves++;
            }
        }

        int lclLakeSamples = 0;
        for (int[] sample : new int[][] {
                {60, 0}, {-60, 0}, {-42, -42}, {42, -42}})
        {
            if (level.getFluidState(origin.offset(sample[0], 1, sample[1]))
                    .getFluidType() == ModFluids.LCL_TYPE.get())
            {
                lclLakeSamples++;
            }
        }

        boolean protectedSites = level.getBlockState(origin.offset(
                        0, GeoFrontBuilder.PYRAMID_APEX_Y + 1,
                        GeoFrontBuilder.PYRAMID_CENTRE_Z)).is(Blocks.BEACON)
                && level.getBlockState(origin.offset(0, 2, 70))
                .is(Blocks.IRON_BLOCK);
        for (int x : IntegratedNervMapBuilder.LIFT_X)
        {
            protectedSites &= level.getBlockState(origin.offset(x, 1, -76))
                    .is(Blocks.LODESTONE);
        }

        int campusFacilities = 0;
        for (BlockPos centre : new BlockPos[] {
                STAFF_CAMPUS_CENTRE, RESEARCH_CAMPUS_CENTRE
        })
        {
            if (level.getBlockState(origin.offset(
                            centre.getX(), 9, centre.getZ()))
                    .is(Blocks.LODESTONE))
            {
                campusFacilities++;
            }
        }
        boolean arboretum = level.getBlockState(origin.offset(
                        ARBORETUM_CENTRE.getX(), 1,
                        ARBORETUM_CENTRE.getZ()))
                .is(Blocks.FLOWERING_AZALEA_LEAVES)
                && level.getBlockState(origin.offset(
                        ARBORETUM_CENTRE.getX(), 0,
                        ARBORETUM_CENTRE.getZ() - 14))
                .is(Blocks.MOSS_BLOCK);
        boolean transitNetwork = isCampusPath(level.getBlockState(
                        origin.offset(-160, 0, 48)))
                && isCampusPath(level.getBlockState(
                        origin.offset(160, 0, 44)))
                && isCampusPath(level.getBlockState(
                        origin.offset(0, 0, -205)));

        boolean valid = shore && docks == 2 && pumpHouse && lclIntake
                && serviceRoad && maintenance && bunkers == BLAST_BUNKERS.length
                && forestGroves >= 10 && lclLakeSamples == 4 && protectedSites;
        valid &= campusFacilities == 2 && arboretum && transitNetwork;
        return new LandscapeAudit(valid, shore, docks, pumpHouse, lclIntake,
                serviceRoad, maintenance, bunkers, forestGroves,
                lclLakeSamples, protectedSites, campusFacilities,
                arboretum, transitNetwork);
    }

    /** Raised retaining wall and a dry promenade around the five-block lake. */
    private static void buildLclShore(ServerLevel level, BlockPos origin)
    {
        int innerSqr = SHORE_INNER_RADIUS * SHORE_INNER_RADIUS;
        int outerSqr = SHORE_OUTER_RADIUS * SHORE_OUTER_RADIUS;
        for (int x = -SHORE_OUTER_RADIUS; x <= SHORE_OUTER_RADIUS; x++)
        {
            for (int z = -SHORE_OUTER_RADIUS; z <= SHORE_OUTER_RADIUS; z++)
            {
                int distanceSqr = x * x + z * z;
                if (distanceSqr < innerSqr || distanceSqr > outerSqr
                        || isProtected(x, z))
                {
                    continue;
                }

                double distance = Math.sqrt(distanceSqr);
                if (distance < SHORE_INNER_RADIUS + 1.6D)
                {
                    for (int y = -3; y <= 1; y++)
                    {
                        set(level, origin.offset(x, y, z), y == 1
                                ? Blocks.POLISHED_BASALT.defaultBlockState()
                                : Blocks.DEEPSLATE_BRICKS.defaultBlockState());
                    }
                }

                BlockState deck = Math.floorMod(x * 11 + z * 17, 19) == 0
                        ? Blocks.CHISELED_DEEPSLATE.defaultBlockState()
                        : Blocks.POLISHED_DEEPSLATE.defaultBlockState();
                set(level, origin.offset(x, 2, z), deck);
                clear(level, origin.offset(x, 3, z));
                clear(level, origin.offset(x, 4, z));

                if (distance > SHORE_OUTER_RADIUS - 0.8D
                        && Math.floorMod(x * 5 + z * 7, 11) == 0)
                {
                    set(level, origin.offset(x, 3, z),
                            Blocks.IRON_BARS.defaultBlockState());
                    set(level, origin.offset(x, 4, z),
                            Blocks.SEA_LANTERN.defaultBlockState());
                }
            }
        }

        // Stable signature kept outside every reserved route.
        set(level, origin.offset(75, 2, 0),
                Blocks.CHISELED_DEEPSLATE.defaultBlockState());
    }

    private static void buildServiceRoad(ServerLevel level, BlockPos origin)
    {
        int innerSqr = SERVICE_ROAD_INNER_RADIUS * SERVICE_ROAD_INNER_RADIUS;
        int outerSqr = SERVICE_ROAD_OUTER_RADIUS * SERVICE_ROAD_OUTER_RADIUS;
        for (int x = -SERVICE_ROAD_OUTER_RADIUS; x <= SERVICE_ROAD_OUTER_RADIUS; x++)
        {
            for (int centredZ = -SERVICE_ROAD_OUTER_RADIUS;
                 centredZ <= SERVICE_ROAD_OUTER_RADIUS; centredZ++)
            {
                int z = GeoFrontBuilder.CAVERN_CENTRE_Z + centredZ;
                int distanceSqr = x * x + centredZ * centredZ;
                if (distanceSqr < innerSqr || distanceSqr > outerSqr
                        || isProtected(x, z))
                {
                    continue;
                }
                BlockState road = Math.floorMod(x + z, 9) == 0
                        ? Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState()
                        : Blocks.BLACK_CONCRETE.defaultBlockState();
                set(level, origin.offset(x, 0, z), road);
                clearHeadroom(level, origin.offset(x, 1, z), 4);
            }
        }

        buildRoadSpur(level, origin, 75, 96, 25, 31);
        buildRoadSpur(level, origin, -94, -67, 49, 55);
    }

    private static void buildRoadSpur(ServerLevel level, BlockPos origin,
                                      int minX, int maxX, int minZ, int maxZ)
    {
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                if (isProtected(x, z))
                {
                    continue;
                }
                boolean edge = x == minX || x == maxX || z == minZ || z == maxZ;
                set(level, origin.offset(x, 0, z), edge
                        ? Blocks.YELLOW_CONCRETE.defaultBlockState()
                        : Blocks.BLACK_CONCRETE.defaultBlockState());
                clearHeadroom(level, origin.offset(x, 1, z), 4);
            }
        }
    }

    private static void buildDocks(ServerLevel level, BlockPos origin)
    {
        buildDock(level, origin, 1);
        buildDock(level, origin, -1);
    }

    private static void buildDock(ServerLevel level, BlockPos origin, int side)
    {
        for (int distance = 52; distance <= 77; distance++)
        {
            int x = side * distance;
            for (int z = 10; z <= 14; z++)
            {
                set(level, origin.offset(x, 2, z),
                        Blocks.SMOOTH_STONE.defaultBlockState());
                clear(level, origin.offset(x, 3, z));
                clear(level, origin.offset(x, 4, z));
            }
            for (int z : new int[] {9, 15})
            {
                set(level, origin.offset(x, 3, z),
                        distance % 5 == 0 ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.IRON_BARS.defaultBlockState());
            }
        }
        int endX = side * 52;
        for (int z : new int[] {10, 14})
        {
            for (int y = -2; y <= 2; y++)
            {
                set(level, origin.offset(endX, y, z),
                        Blocks.POLISHED_BASALT.defaultBlockState());
            }
            set(level, origin.offset(endX, 3, z),
                    Blocks.CHAIN.defaultBlockState());
        }
    }

    private static void buildPumpingStation(ServerLevel level, BlockPos origin)
    {
        int centreX = PUMP_CENTRE.getX();
        int centreZ = PUMP_CENTRE.getZ();

        // A covered source channel visibly joins the lake to the pump house.
        for (int x = 55; x <= 77; x++)
        {
            set(level, origin.offset(x, 0, centreZ),
                    Blocks.IRON_BLOCK.defaultBlockState());
            set(level, origin.offset(x, 1, centreZ),
                    ModFluids.LCL_SOURCE.get().defaultFluidState()
                            .createLegacyBlock());
            set(level, origin.offset(x, 1, centreZ - 1),
                    Blocks.POLISHED_DEEPSLATE.defaultBlockState());
            set(level, origin.offset(x, 1, centreZ + 1),
                    Blocks.POLISHED_DEEPSLATE.defaultBlockState());
            set(level, origin.offset(x, 2, centreZ),
                    Blocks.ORANGE_STAINED_GLASS.defaultBlockState());
        }

        for (int x = -8; x <= 8; x++)
        {
            for (int z = -9; z <= 9; z++)
            {
                set(level, origin.offset(centreX + x, 1, centreZ + z),
                        Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int y = 2; y <= 7; y++)
                {
                    clear(level, origin.offset(centreX + x, y, centreZ + z));
                }
                set(level, origin.offset(centreX + x, 8, centreZ + z),
                        Math.floorMod(x + z, 5) == 0
                                ? Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState()
                                : Blocks.GRAY_CONCRETE.defaultBlockState());
            }
        }

        for (int y = 2; y <= 7; y++)
        {
            for (int x = -8; x <= 8; x++)
            {
                setPumpWall(level, origin.offset(centreX + x, y, centreZ - 9),
                        x, y);
                setPumpWall(level, origin.offset(centreX + x, y, centreZ + 9),
                        x, y);
            }
            for (int z = -8; z <= 8; z++)
            {
                setPumpWall(level, origin.offset(centreX - 8, y, centreZ + z),
                        z, y);
                setPumpWall(level, origin.offset(centreX + 8, y, centreZ + z),
                        z, y);
            }
        }

        // The west wall faces the lake and remains a traversable pressure gate.
        for (int y = 2; y <= 5; y++)
        {
            for (int z = -2; z <= 2; z++)
            {
                clear(level, origin.offset(centreX - 8, y, centreZ + z));
            }
        }

        buildLclHeaderTank(level, origin, centreX, centreZ);
        buildPumpMachinery(level, origin, centreX, centreZ);
        set(level, origin.offset(centreX, 8, centreZ),
                Blocks.LODESTONE.defaultBlockState());
    }

    private static void setPumpWall(ServerLevel level, BlockPos position,
                                    int span, int y)
    {
        BlockState wall = y >= 4 && y <= 6 && Math.floorMod(span, 5) <= 1
                ? Blocks.ORANGE_STAINED_GLASS.defaultBlockState()
                : (y == 2 || y == 7
                ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                : Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
        set(level, position, wall);
    }

    private static void buildLclHeaderTank(ServerLevel level, BlockPos origin,
                                           int centreX, int centreZ)
    {
        for (int x = -2; x <= 2; x++)
        {
            for (int z = -2; z <= 2; z++)
            {
                set(level, origin.offset(centreX + x, 1, centreZ + z),
                        Blocks.ORANGE_CONCRETE.defaultBlockState());
                if (Math.abs(x) == 2 || Math.abs(z) == 2)
                {
                    set(level, origin.offset(centreX + x, 2, centreZ + z),
                            Blocks.ORANGE_STAINED_GLASS.defaultBlockState());
                    set(level, origin.offset(centreX + x, 3, centreZ + z),
                            Blocks.IRON_BARS.defaultBlockState());
                }
                else
                {
                    set(level, origin.offset(centreX + x, 2, centreZ + z),
                            ModFluids.LCL_SOURCE.get().defaultFluidState()
                                    .createLegacyBlock());
                }
            }
        }
    }

    private static void buildPumpMachinery(ServerLevel level, BlockPos origin,
                                           int centreX, int centreZ)
    {
        for (int z : new int[] {-6, 6})
        {
            for (int x = -5; x <= 5; x += 5)
            {
                set(level, origin.offset(centreX + x, 2, centreZ + z),
                        Blocks.PISTON.defaultBlockState());
                set(level, origin.offset(centreX + x, 3, centreZ + z),
                        Blocks.OBSERVER.defaultBlockState());
                set(level, origin.offset(centreX + x, 4, centreZ + z),
                        Blocks.IRON_BLOCK.defaultBlockState());
            }
        }
    }

    private static void buildMaintenanceTerrace(ServerLevel level, BlockPos origin)
    {
        int centreX = MAINTENANCE_CENTRE.getX();
        int centreZ = MAINTENANCE_CENTRE.getZ();
        for (int x = -9; x <= 9; x++)
        {
            for (int z = -7; z <= 7; z++)
            {
                set(level, origin.offset(centreX + x, 1, centreZ + z),
                        Math.floorMod(x + z, 6) == 0
                                ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                                : Blocks.SMOOTH_STONE.defaultBlockState());
                clear(level, origin.offset(centreX + x, 2, centreZ + z));
                clear(level, origin.offset(centreX + x, 3, centreZ + z));
            }
        }

        for (int x : new int[] {-9, 9})
        {
            for (int z = -7; z <= 7; z++)
            {
                set(level, origin.offset(centreX + x, 2, centreZ + z),
                        Blocks.IRON_BARS.defaultBlockState());
            }
        }
        for (int z : new int[] {-7, 7})
        {
            for (int x = -9; x <= 9; x++)
            {
                set(level, origin.offset(centreX + x, 2, centreZ + z),
                        Blocks.IRON_BARS.defaultBlockState());
            }
        }

        // Four narrow pylons support an elevated cavern observation deck.
        for (int x : new int[] {-6, 6})
        {
            for (int z : new int[] {-4, 4})
            {
                for (int y = 2; y <= 9; y++)
                {
                    set(level, origin.offset(centreX + x, y, centreZ + z),
                            Blocks.IRON_BLOCK.defaultBlockState());
                }
            }
        }
        for (int x = -7; x <= 7; x++)
        {
            for (int z = -5; z <= 5; z++)
            {
                set(level, origin.offset(centreX + x, 9, centreZ + z),
                        Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState());
            }
        }
        for (int y = 2; y <= 9; y++)
        {
            set(level, origin.offset(centreX - 7, y, centreZ - 4),
                    Blocks.LADDER.defaultBlockState()
                            .setValue(LadderBlock.FACING, Direction.WEST));
        }
        for (int x = -7; x <= 7; x++)
        {
            set(level, origin.offset(centreX + x, 10, centreZ - 5),
                    Blocks.IRON_BARS.defaultBlockState());
            set(level, origin.offset(centreX + x, 10, centreZ + 5),
                    Blocks.IRON_BARS.defaultBlockState());
        }
        set(level, origin.offset(centreX, 9, centreZ),
                Blocks.LODESTONE.defaultBlockState());
    }

    private static void buildBlastBunkers(ServerLevel level, BlockPos origin)
    {
        for (BlockPos centre : BLAST_BUNKERS)
        {
            buildBlastBunker(level, origin, centre);
        }
    }

    private static void buildBlastBunker(ServerLevel level, BlockPos origin,
                                         BlockPos centre)
    {
        int inward = centre.getX() < 0 ? 1 : -1;
        for (int x = -7; x <= 7; x++)
        {
            for (int z = -5; z <= 5; z++)
            {
                set(level, origin.offset(centre.getX() + x, 1,
                                centre.getZ() + z),
                        com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                for (int y = 2; y <= 6; y++)
                {
                    clear(level, origin.offset(centre.getX() + x, y,
                            centre.getZ() + z));
                }
                set(level, origin.offset(centre.getX() + x, 7,
                                centre.getZ() + z),
                        Blocks.BLACK_CONCRETE.defaultBlockState());
            }
        }
        for (int y = 2; y <= 6; y++)
        {
            for (int x = -7; x <= 7; x++)
            {
                set(level, origin.offset(centre.getX() + x, y,
                                centre.getZ() - 5),
                        y == 4 && Math.floorMod(x, 4) == 0
                                ? Blocks.RED_STAINED_GLASS.defaultBlockState()
                                : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                set(level, origin.offset(centre.getX() + x, y,
                                centre.getZ() + 5),
                        com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
            }
            for (int z = -4; z <= 4; z++)
            {
                set(level, origin.offset(centre.getX() - 7, y,
                                centre.getZ() + z),
                        com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                set(level, origin.offset(centre.getX() + 7, y,
                                centre.getZ() + z),
                        com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
            }
        }

        int entranceX = centre.getX() + inward * 7;
        for (int y = 2; y <= 5; y++)
        {
            for (int z = -2; z <= 2; z++)
            {
                clear(level, origin.offset(entranceX, y, centre.getZ() + z));
            }
        }
        for (int z = -4; z <= 4; z++)
        {
            set(level, origin.offset(centre.getX(), 2, centre.getZ() + z),
                    z % 2 == 0 ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                            : Blocks.IRON_BLOCK.defaultBlockState());
        }
        set(level, origin.offset(centre.getX(), 7, centre.getZ()),
                Blocks.LODESTONE.defaultBlockState());
    }

    /**
     * Expands the cavern into an inhabited underground campus: the TV
     * GeoFront reads as a landscape containing a headquarters, not as a
     * pyramid dropped onto an empty lawn.
     */
    private static void buildInhabitedCampus(ServerLevel level,
                                             BlockPos origin)
    {
        buildCampusPaths(level, origin);
        buildArboretum(level, origin);
        buildCampusBuilding(level, origin, STAFF_CAMPUS_CENTRE,
                19, 15, Blocks.LIGHT_BLUE_CONCRETE.defaultBlockState(),
                CampusStyle.STAFF);
        buildCampusBuilding(level, origin, RESEARCH_CAMPUS_CENTRE,
                21, 16, Blocks.PURPLE_CONCRETE.defaultBlockState(),
                CampusStyle.RESEARCH);
        buildServiceRail(level, origin);
        buildPerimeterPortal(level, origin, -238,
                GeoFrontBuilder.CAVERN_CENTRE_Z, Direction.EAST);
        buildPerimeterPortal(level, origin, 238,
                GeoFrontBuilder.CAVERN_CENTRE_Z, Direction.WEST);
        buildPerimeterPortal(level, origin, 0, -286, Direction.SOUTH);
    }

    private static void buildCampusPaths(ServerLevel level, BlockPos origin)
    {
        // West arboretum branch.
        paintPathLineX(level, origin, -202, -134, 48,
                Blocks.MOSSY_STONE_BRICKS.defaultBlockState());
        paintPathLineZ(level, origin, -202, 48, 74,
                Blocks.MOSSY_STONE_BRICKS.defaultBlockState());
        paintPathLineZ(level, origin, -134, 48, 108,
                Blocks.MOSSY_STONE_BRICKS.defaultBlockState());

        // East staff/medical campus branch.
        paintPathLineX(level, origin, 134, 198, 44,
                Blocks.SMOOTH_STONE.defaultBlockState());
        paintPathLineZ(level, origin, 198, 44, 58,
                Blocks.SMOOTH_STONE.defaultBlockState());
        paintPathLineZ(level, origin, 134, 44, 108,
                Blocks.SMOOTH_STONE.defaultBlockState());

        // Northern research branch deliberately bends around the three EVA
        // launch corridors instead of crossing their 31x31 clear volumes.
        paintPathLineZ(level, origin, 0, -242, -205,
                Blocks.POLISHED_ANDESITE.defaultBlockState());
        paintPathLineX(level, origin, 0, 142, -205,
                Blocks.POLISHED_ANDESITE.defaultBlockState());
        paintPathLineZ(level, origin, 142, -205, -112,
                Blocks.POLISHED_ANDESITE.defaultBlockState());
        paintPathLineX(level, origin, 134, 142, -112,
                Blocks.POLISHED_ANDESITE.defaultBlockState());

        // Garden promenade joins the public GeoFront station at Z=190 to the
        // west campus without cutting across the pyramid's service apron.
        paintPathLineX(level, origin, -108, 0, 178,
                Blocks.CUT_COPPER.defaultBlockState());
        paintPathLineZ(level, origin, -108, 108, 178,
                Blocks.CUT_COPPER.defaultBlockState());
        paintPathLineX(level, origin, -160, -108, 108,
                Blocks.CUT_COPPER.defaultBlockState());
        paintPathLineZ(level, origin, -160, 74, 108,
                Blocks.CUT_COPPER.defaultBlockState());
    }

    private static void paintPathLineX(ServerLevel level, BlockPos origin,
                                       int minimumX, int maximumX, int z,
                                       BlockState centre)
    {
        for (int x = Math.min(minimumX, maximumX);
            x <= Math.max(minimumX, maximumX); x++)
        {
            paintPathCell(level, origin, x, z, centre,
                    Math.floorMod(x, 14) == 0, true);
        }
    }

    private static void paintPathLineZ(ServerLevel level, BlockPos origin,
                                       int x, int minimumZ, int maximumZ,
                                       BlockState centre)
    {
        for (int z = Math.min(minimumZ, maximumZ);
            z <= Math.max(minimumZ, maximumZ); z++)
        {
            paintPathCell(level, origin, x, z, centre,
                    Math.floorMod(z, 14) == 0, false);
        }
    }

    private static void paintPathCell(ServerLevel level, BlockPos origin,
                                      int centreX, int centreZ,
                                      BlockState centre, boolean lit,
                                      boolean runsAlongX)
    {
        for (int lateral = -2; lateral <= 2; lateral++)
        {
            int x = centreX + (runsAlongX ? 0 : lateral);
            int z = centreZ + (runsAlongX ? lateral : 0);
            BlockPos floor = origin.offset(x, 0, z);
            set(level, floor, lateral == 0 ? centre
                    : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
            if (level.getBlockState(floor.below()).isAir())
            {
                set(level, floor.below(),
                        Blocks.DEEPSLATE_BRICKS.defaultBlockState());
            }
            clearHeadroom(level, floor.above(), 5);
        }
        if (lit)
        {
            int firstX = centreX + (runsAlongX ? 0 : -3);
            int firstZ = centreZ + (runsAlongX ? -3 : 0);
            int secondX = centreX + (runsAlongX ? 0 : 3);
            int secondZ = centreZ + (runsAlongX ? 3 : 0);
            set(level, origin.offset(firstX, 1, firstZ),
                    Blocks.IRON_BARS.defaultBlockState());
            set(level, origin.offset(firstX, 2, firstZ),
                    Blocks.SEA_LANTERN.defaultBlockState());
            set(level, origin.offset(secondX, 1, secondZ),
                    Blocks.IRON_BARS.defaultBlockState());
            set(level, origin.offset(secondX, 2, secondZ),
                    Blocks.SEA_LANTERN.defaultBlockState());
        }
    }

    private static void buildArboretum(ServerLevel level, BlockPos origin)
    {
        int centreX = ARBORETUM_CENTRE.getX();
        int centreZ = ARBORETUM_CENTRE.getZ();
        for (int x = -28; x <= 28; x++)
        {
            for (int z = -22; z <= 22; z++)
            {
                boolean path = Math.abs(x) <= 2 || Math.abs(z) <= 2;
                boolean border = Math.abs(x) == 28 || Math.abs(z) == 22;
                BlockState ground = path
                        ? Blocks.MOSSY_STONE_BRICKS.defaultBlockState()
                        : Math.floorMod(x * 7 + z * 11, 9) == 0
                                ? Blocks.MOSS_BLOCK.defaultBlockState()
                                : Blocks.GRASS_BLOCK.defaultBlockState();
                set(level, origin.offset(centreX + x, 0, centreZ + z),
                        ground);
                clearHeadroom(level,
                        origin.offset(centreX + x, 1, centreZ + z), 7);
                if (border)
                {
                    set(level, origin.offset(centreX + x, 1,
                                    centreZ + z),
                            Blocks.AZALEA_LEAVES.defaultBlockState());
                    if (Math.floorMod(x + z, 6) == 0)
                    {
                        set(level, origin.offset(centreX + x, 2,
                                        centreZ + z),
                                Blocks.SEA_LANTERN.defaultBlockState());
                    }
                }
                else if (!path && Math.floorMod(x * 13 + z * 17, 29) == 0)
                {
                    BlockState flower = Math.floorMod(x - z, 4) == 0
                            ? Blocks.ALLIUM.defaultBlockState()
                            : Math.floorMod(x - z, 4) == 1
                                    ? Blocks.OXEYE_DAISY.defaultBlockState()
                                    : Math.floorMod(x - z, 4) == 2
                                            ? Blocks.PINK_TULIP
                                            .defaultBlockState()
                                            : Blocks.AZURE_BLUET
                                            .defaultBlockState();
                    set(level, origin.offset(centreX + x, 1,
                            centreZ + z), flower);
                }
            }
        }

        // Reflecting pond and four deliberately framed specimen trees.
        for (int x = -8; x <= 8; x++)
        {
            for (int z = -6; z <= 6; z++)
            {
                if (x * x * 36 + z * z * 64 <= 2304)
                {
                    set(level, origin.offset(centreX + x, -1,
                                    centreZ + z),
                            Blocks.CLAY.defaultBlockState());
                    set(level, origin.offset(centreX + x, 0,
                                    centreZ + z),
                            net.minecraft.world.level.material.Fluids.WATER
                                    .defaultFluidState().createLegacyBlock());
                }
            }
        }
        for (int[] tree : new int[][] {
                {-17, -12}, {17, -12}, {-17, 12}, {17, 12}
        })
        {
            buildGardenTree(level, origin, centreX + tree[0],
                    centreZ + tree[1]);
        }
        set(level, origin.offset(centreX, 0, centreZ - 14),
                Blocks.MOSS_BLOCK.defaultBlockState());
        set(level, origin.offset(centreX, 1, centreZ),
                Blocks.FLOWERING_AZALEA_LEAVES.defaultBlockState());
    }

    private static void buildGardenTree(ServerLevel level, BlockPos origin,
                                        int x, int z)
    {
        for (int y = 1; y <= 7; y++)
        {
            set(level, origin.offset(x, y, z),
                    Blocks.CHERRY_LOG.defaultBlockState());
        }
        for (int dx = -3; dx <= 3; dx++)
        {
            for (int dz = -3; dz <= 3; dz++)
            {
                for (int dy = -1; dy <= 2; dy++)
                {
                    if (dx * dx + dz * dz + dy * dy <= 11)
                    {
                        set(level, origin.offset(x + dx, 7 + dy, z + dz),
                                Blocks.CHERRY_LEAVES.defaultBlockState());
                    }
                }
            }
        }
    }

    private static void buildCampusBuilding(ServerLevel level,
                                            BlockPos origin,
                                            BlockPos centre,
                                            int halfX, int halfZ,
                                            BlockState accent,
                                            CampusStyle style)
    {
        for (int x = -halfX; x <= halfX; x++)
        {
            for (int z = -halfZ; z <= halfZ; z++)
            {
                boolean boundary = Math.abs(x) == halfX
                        || Math.abs(z) == halfZ;
                set(level, origin.offset(centre.getX() + x, 0,
                                centre.getZ() + z),
                        Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int y = 1; y <= 8; y++)
                {
                    BlockState state;
                    if (!boundary)
                    {
                        state = Blocks.AIR.defaultBlockState();
                    }
                    else if (y >= 3 && y <= 6
                            && Math.floorMod(x + z, 5) <= 2)
                    {
                        state = Blocks.GRAY_STAINED_GLASS.defaultBlockState();
                    }
                    else
                    {
                        state = y == 1 || y == 8 ? accent
                                : Blocks.LIGHT_GRAY_CONCRETE
                                .defaultBlockState();
                    }
                    set(level, origin.offset(centre.getX() + x, y,
                            centre.getZ() + z), state);
                }
                set(level, origin.offset(centre.getX() + x, 9,
                                centre.getZ() + z),
                        Math.floorMod(x + z, 8) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE_BRICKS
                                .defaultBlockState());
            }
        }

        // South-facing seven-wide pressure entrance.
        for (int x = -3; x <= 3; x++)
        {
            for (int y = 1; y <= 5; y++)
            {
                clear(level, origin.offset(centre.getX() + x, y,
                        centre.getZ() + halfZ));
            }
        }
        if (style == CampusStyle.STAFF)
        {
            furnishStaffCampus(level, origin, centre, halfX, halfZ);
        }
        else
        {
            furnishResearchCampus(level, origin, centre, halfX, halfZ);
        }
        set(level, origin.offset(centre.getX(), 9, centre.getZ()),
                Blocks.LODESTONE.defaultBlockState());
    }

    private static void furnishStaffCampus(ServerLevel level, BlockPos origin,
                                           BlockPos centre,
                                           int halfX, int halfZ)
    {
        for (int z = -halfZ + 5; z <= halfZ - 6; z += 7)
        {
            for (int x = -halfX + 5; x <= halfX - 5; x += 7)
            {
                set(level, origin.offset(centre.getX() + x, 1,
                                centre.getZ() + z),
                        Blocks.SMOOTH_QUARTZ_SLAB.defaultBlockState());
                set(level, origin.offset(centre.getX() + x - 1, 1,
                                centre.getZ() + z),
                        Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                                .defaultBlockState()
                                .setValue(
                                        net.minecraft.world.level.block.StairBlock.FACING,
                                        Direction.EAST));
                set(level, origin.offset(centre.getX() + x + 1, 1,
                                centre.getZ() + z),
                        Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                                .defaultBlockState()
                                .setValue(
                                        net.minecraft.world.level.block.StairBlock.FACING,
                                        Direction.WEST));
            }
        }
    }

    private static void furnishResearchCampus(ServerLevel level,
                                              BlockPos origin,
                                              BlockPos centre,
                                              int halfX, int halfZ)
    {
        for (int x = -halfX + 5; x <= halfX - 5; x += 8)
        {
            for (int z = -halfZ + 5; z <= halfZ - 5; z += 8)
            {
                set(level, origin.offset(centre.getX() + x, 1,
                                centre.getZ() + z),
                        Blocks.IRON_BLOCK.defaultBlockState());
                set(level, origin.offset(centre.getX() + x, 2,
                                centre.getZ() + z),
                        Blocks.PURPLE_STAINED_GLASS.defaultBlockState());
                set(level, origin.offset(centre.getX() + x, 3,
                                centre.getZ() + z),
                        Blocks.AMETHYST_BLOCK.defaultBlockState());
                set(level, origin.offset(centre.getX() + x, 4,
                                centre.getZ() + z),
                        Blocks.PURPLE_STAINED_GLASS.defaultBlockState());
            }
        }
    }

    private static void buildServiceRail(ServerLevel level, BlockPos origin)
    {
        final int z = -178;
        for (int x = -184; x <= 184; x++)
        {
            set(level, origin.offset(x, 8, z),
                    Blocks.IRON_BLOCK.defaultBlockState());
            set(level, origin.offset(x, 9, z),
                    Math.floorMod(x, 12) == 0
                            ? Blocks.POWERED_RAIL.defaultBlockState()
                            : Blocks.RAIL.defaultBlockState());
            if (Math.floorMod(x, 16) == 0)
            {
                for (int y = 0; y <= 7; y++)
                {
                    set(level, origin.offset(x, y, z),
                            y == 4 ? Blocks.SEA_LANTERN.defaultBlockState()
                                    : Blocks.DEEPSLATE_BRICKS
                                    .defaultBlockState());
                }
            }
        }
        for (int x : new int[] {-184, 0, 184})
        {
            for (int dx = -6; dx <= 6; dx++)
            {
                for (int dz = -3; dz <= 3; dz++)
                {
                    set(level, origin.offset(x + dx, 8, z + dz),
                            Blocks.SMOOTH_STONE.defaultBlockState());
                    if (Math.abs(dx) == 6)
                    {
                        set(level, origin.offset(x + dx, 9, z + dz),
                                Blocks.IRON_BARS.defaultBlockState());
                    }
                }
            }
            set(level, origin.offset(x, 8, z),
                    Blocks.LODESTONE.defaultBlockState());
        }
    }

    private static void buildPerimeterPortal(ServerLevel level,
                                             BlockPos origin,
                                             int centreX, int centreZ,
                                             Direction inward)
    {
        Direction lateral = inward.getClockWise();
        for (int depth = 0; depth <= 7; depth++)
        {
            for (int side = -6; side <= 6; side++)
            {
                for (int y = 0; y <= 8; y++)
                {
                    int x = centreX + inward.getStepX() * depth
                            + lateral.getStepX() * side;
                    int z = centreZ + inward.getStepZ() * depth
                            + lateral.getStepZ() * side;
                    boolean shell = Math.abs(side) >= 5 || y == 0 || y == 8;
                    set(level, origin.offset(x, y, z), shell
                            ? y == 4 && Math.abs(side) == 6
                                    ? Blocks.ORANGE_CONCRETE
                                    .defaultBlockState()
                                    : com.projectseele.world.NervMaterials.structuralBlock()
                                    .defaultBlockState()
                            : Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    private static void enrichForest(ServerLevel level, BlockPos origin)
    {
        for (int index = 0; index < FOREST_CENTRES.length; index++)
        {
            int x = FOREST_CENTRES[index][0];
            int z = FOREST_CENTRES[index][1];
            if (isProtected(x, z) || inServiceRoad(x, z))
            {
                continue;
            }
            buildTreeGrove(level, origin, x, z, 6 + Math.floorMod(index, 4));
        }
    }

    private static void buildTreeGrove(ServerLevel level, BlockPos origin,
                                       int centreX, int centreZ, int height)
    {
        int groundY = forestGroundY(level, origin, centreX, centreZ);
        for (int x = -3; x <= 3; x++)
        {
            for (int z = -3; z <= 3; z++)
            {
                if (x * x + z * z <= 10)
                {
                    set(level, origin.offset(centreX + x, groundY, centreZ + z),
                            Math.floorMod(x * 3 + z * 5, 7) == 0
                                    ? Blocks.MOSS_BLOCK.defaultBlockState()
                                    : Blocks.GRASS_BLOCK.defaultBlockState());
                }
            }
        }
        for (int y = 1; y <= height; y++)
        {
            set(level, origin.offset(centreX, groundY + y, centreZ),
                    Blocks.STRIPPED_DARK_OAK_LOG.defaultBlockState());
            if (y <= 3)
            {
                set(level, origin.offset(centreX + 1, groundY + y, centreZ),
                        Blocks.DARK_OAK_LOG.defaultBlockState());
            }
        }
        for (int x = -3; x <= 3; x++)
        {
                for (int y = -2; y <= 2; y++)
            {
                for (int z = -3; z <= 3; z++)
                {
                    if (x * x + y * y + z * z <= 11)
                    {
                    set(level, origin.offset(centreX + x,
                                    groundY + height + y,
                                        centreZ + z),
                                Math.floorMod(x * 7 + y * 11 + z * 13, 9) == 0
                                        ? Blocks.FLOWERING_AZALEA_LEAVES.defaultBlockState()
                                        : Blocks.AZALEA_LEAVES.defaultBlockState());
                    }
                }
            }
        }
        set(level, origin.offset(centreX, groundY + height + 1, centreZ),
                Blocks.DARK_OAK_LOG.defaultBlockState());
    }

    private static int forestGroundY(ServerLevel level, BlockPos origin,
                                     int x, int z)
    {
        for (int y = 4; y >= -4; y--)
        {
            BlockState state = level.getBlockState(origin.offset(x, y, z));
            if (state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.MOSS_BLOCK)
                    || state.is(Blocks.DIRT) || state.is(Blocks.STONE))
            {
                return y;
            }
        }
        return 0;
    }

    /** Hard exclusions shared by every surface pass in this builder. */
    private static boolean isProtected(int x, int z)
    {
        if (Math.abs(x) <= 45 && z >= -170 && z <= -34)
        {
            return true;
        }
        if (GeoFrontBuilder.isWithinPyramidServiceApron(x, z)
                || GeoFrontBuilder.isWithinPyramidPublicAccess(x, z))
        {
            return true;
        }
        if (Math.abs(x) <= 40 && Math.abs(z) <= 40)
        {
            return true;
        }
        if (Math.abs(x) <= 10 && z >= 30)
        {
            return true;
        }
        if (Math.abs(x) <= 12 && z >= 88)
        {
            return true;
        }
        if (Math.abs(x) <= 6 && z <= -98)
        {
            return true;
        }
        for (int liftX : IntegratedNervMapBuilder.LIFT_X)
        {
            if (Math.abs(x - liftX) <= 9 && z >= -86 && z <= -34)
            {
                return true;
            }
        }
        return false;
    }

    private static boolean inServiceRoad(int x, int z)
    {
        int centredZ = z - GeoFrontBuilder.CAVERN_CENTRE_Z;
        int distanceSqr = x * x + centredZ * centredZ;
        return distanceSqr >= SERVICE_ROAD_INNER_RADIUS * SERVICE_ROAD_INNER_RADIUS
                && distanceSqr <= SERVICE_ROAD_OUTER_RADIUS * SERVICE_ROAD_OUTER_RADIUS;
    }

    private static boolean isServiceRoad(BlockState state)
    {
        return state.is(Blocks.BLACK_CONCRETE)
                || state.is(Blocks.LIGHT_GRAY_CONCRETE)
                || state.is(Blocks.YELLOW_CONCRETE);
    }

    private static boolean isCampusPath(BlockState state)
    {
        return state.is(Blocks.MOSSY_STONE_BRICKS)
                || state.is(Blocks.SMOOTH_STONE)
                || state.is(Blocks.POLISHED_ANDESITE)
                || state.is(Blocks.CUT_COPPER)
                || state.is(Blocks.POLISHED_DEEPSLATE);
    }

    private static void clearHeadroom(ServerLevel level, BlockPos feet, int height)
    {
        for (int y = 0; y < height; y++)
        {
            clear(level, feet.above(y));
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
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, UPDATE_CLIENTS);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    private enum CampusStyle
    {
        STAFF,
        RESEARCH
    }

    public record LandscapeAudit(boolean valid, boolean shore, int docks,
                                 boolean pumpHouse, boolean lclIntake,
                                 boolean serviceRoad, boolean maintenance,
                                 int bunkers, int forestGroves,
                                 int lclLakeSamples, boolean protectedSites,
                                 int campusFacilities, boolean arboretum,
                                 boolean transitNetwork)
    {
        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s shore=%s docks=%d/2 pumpHouse=%s lclIntake=%s "
                            + "serviceRoad=%s maintenance=%s bunkers=%d/2 "
                            + "forestGroves=%d/%d lclLake=%d/4 protectedSites=%s "
                            + "campus=%d/2 arboretum=%s transit=%s",
                    this.valid, this.shore, this.docks, this.pumpHouse,
                    this.lclIntake, this.serviceRoad, this.maintenance,
                    this.bunkers, this.forestGroves, FOREST_CENTRES.length,
                    this.lclLakeSamples, this.protectedSites,
                    this.campusFacilities, this.arboretum,
                    this.transitNetwork);
        }
    }
}
