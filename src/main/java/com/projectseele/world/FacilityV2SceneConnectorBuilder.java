package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModFluids;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LightBlock;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Final physical joins between the authored civil scene and the retained
 * three-line EVA plant.
 *
 * <p>This deliberately runs after the exterior fabric has completed.  It owns
 * only narrow, player-visible joins which are absent from both authorities:
 * the pyramid front promenade, lower-silo service spurs, carrier observation
 * galleries and the surface recovery boulevard.  No teleport or diagonal
 * corridor participates.</p>
 */
public final class FacilityV2SceneConnectorBuilder
{
    private static final int REVISION = 6;
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    private static BlockState structuralStructure()
    {
        return com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
    }
    private static final BlockState FLOOR =
            Blocks.POLISHED_DEEPSLATE.defaultBlockState();
    private static final BlockState ROAD =
            Blocks.GRAY_CONCRETE.defaultBlockState();
    private static final BlockState ROAD_EDGE =
            Blocks.ORANGE_CONCRETE.defaultBlockState();
    private static final BlockState GLASS =
            Blocks.GRAY_STAINED_GLASS.defaultBlockState();
    private static final BlockState LIGHT =
            Blocks.SEA_LANTERN.defaultBlockState();

    private FacilityV2SceneConnectorBuilder() {}

    public static boolean ensure(ServerLevel level,
                                 FacilitySchemaV2.ResolvedManifest manifest)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return installed(level, manifest);
        BlockPos centre = manifest.centre();
        if (installed(level, manifest))
        {
            return true;
        }
        PerformanceCounters.recordBuilderCall();
        buildPyramidPromenade(level, centre);
        buildLowerSiloRoads(level, centre);
        buildCarrierObservationGalleries(level);
        buildMechanicalObservationNetwork(level, centre);
        buildSurfaceRecoveryBoulevard(level, manifest);
        buildSurfaceRecoveryPads(level, manifest);
        restoreLclLake(level, centre);
        buildLclLakePromenade(level, centre);
        buildLclProcessingScene(level, centre);
        BlockPos marker = marker(centre);
        set(level, marker, Blocks.NETHERITE_BLOCK.defaultBlockState());
        set(level, marker.east(REVISION),
                Blocks.LODESTONE.defaultBlockState());
        boolean complete = installed(level, manifest);
        ProjectSeele.LOGGER.info(
                "Facility rescue scene connectors built: revision={} complete={} "
                        + "joins=pyramid-promenade,lower-silo-roads,"
                        + "carrier-galleries,mechanical-observation-network,"
                        + "surface-recovery-boulevard,recovery-pads,"
                        + "real-lcl-lake,lcl-lake-promenade,lcl-intakes",
                REVISION, complete);
        return complete;
    }

    private static boolean installed(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest)
    {
        BlockPos centre = manifest.centre();
        BlockPos unit01Bed = EvaHangarBuilder.hangarBed(
                IntegratedNervMapBuilder.GEOFRONT_ORIGIN, 1);
        return level.getBlockState(marker(centre))
                .is(Blocks.NETHERITE_BLOCK)
                && level.getBlockState(marker(centre).east(REVISION))
                .is(Blocks.LODESTONE)
                && !level.getBlockState(centre.offset(
                        0, -361, 250)).isAir()
                && !level.getBlockState(new BlockPos(
                        centre.getX(), manifest.surfaceY(),
                        centre.getZ() + 100)).isAir()
                && !level.getBlockState(unit01Bed.offset(
                        20, 48, 35)).isAir()
                && level.getBlockState(unit01Bed.offset(
                        17, 52, 35)).is(GLASS.getBlock())
                && !level.getBlockState(centre.offset(
                        54, -395, -115)).isAir()
                && !level.getBlockState(centre.offset(
                        0, -361, -208)).isAir()
                && level.getFluidState(centre.offset(
                        0, -361, -260)).getFluidType()
                        == ModFluids.LCL_TYPE.get()
                && !level.getBlockState(centre.offset(
                        18, manifest.surfaceY(), -76)).isAir()
                && !level.getBlockState(centre.offset(
                        36, -360, -220)).isAir();
    }

    /**
     * H-01 foyer at Y=-356 exits through the south pyramid face. A broad,
     * sealed hall crosses the shell; five straight landings descend to the
     * plaza and continue to its road ring.
     */
    private static void buildPyramidPromenade(ServerLevel level,
                                               BlockPos centre)
    {
        int floorY = -356;
        for (int z = 180; z <= 220; z++)
        {
            for (int x = -10; x <= 10; x++)
            {
                set(level, centre.offset(x, floorY - 1, z),
                        Math.floorMod(x + z, 8) == 0 ? LIGHT : structuralStructure());
                set(level, centre.offset(x, floorY, z),
                        Math.abs(x) >= 8 ? ROAD_EDGE : FLOOR);
                for (int y = floorY + 1; y <= floorY + 7; y++)
                {
                    boolean wall = Math.abs(x) == 10;
                    set(level, centre.offset(x, y, z),
                            wall ? (y >= floorY + 2
                                    && y <= floorY + 5 ? GLASS : structuralStructure())
                                    : Blocks.AIR.defaultBlockState());
                }
                set(level, centre.offset(x, floorY + 8, z),
                        Math.floorMod(x + z, 9) == 0 ? LIGHT : structuralStructure());
            }
        }

        // Keep the registered foyer port and the plaza end visibly open.
        openDoor(level, centre, floorY, 180);
        openDoor(level, centre, floorY, 220);

        BlockState downSouth = Blocks.POLISHED_DEEPSLATE_STAIRS
                .defaultBlockState()
                .setValue(StairBlock.FACING, Direction.NORTH);
        for (int step = 0; step < 5; step++)
        {
            int stepY = floorY - step;
            int zMin = 220 + step * 4;
            int zMax = zMin + 3;
            for (int z = zMin; z <= zMax; z++)
            {
                for (int x = -10; x <= 10; x++)
                {
                    BlockState deck = z == zMax && step < 4
                            ? downSouth
                            : Math.abs(x) >= 8 ? ROAD_EDGE : FLOOR;
                    set(level, centre.offset(x, stepY, z), deck);
                    for (int y = stepY + 1; y <= stepY + 7; y++)
                    {
                        set(level, centre.offset(x, y, z),
                                Blocks.AIR.defaultBlockState());
                    }
                    for (int support = -369; support < stepY; support++)
                    {
                        set(level, centre.offset(x, support, z), structuralStructure());
                    }
                }
            }
        }
        buildUndergroundRoad(level, centre, 0, 240, 0, 260, 18);
    }

    private static void openDoor(ServerLevel level, BlockPos centre,
                                 int floorY, int relativeZ)
    {
        for (int x = -4; x <= 4; x++)
        {
            for (int y = floorY + 1; y <= floorY + 7; y++)
            {
                set(level, centre.offset(x, y, relativeZ),
                        Blocks.AIR.defaultBlockState());
            }
        }
    }

    /**
     * Three paved service spurs meet the north road ring and terminate at
     * readable recovery decks around the real launch columns.
     */
    private static void buildLowerSiloRoads(ServerLevel level,
                                             BlockPos centre)
    {
        // One real network: the LCL promenade feeds a north/south trunk,
        // which meets a transverse distribution road before splitting into
        // the three silo approaches.  The former three isolated strips looked
        // like roads but could not be reached from one another.
        buildUndergroundRoad(level, centre,
                0, -205, 0, -176, 18);
        buildUndergroundRoad(level, centre,
                -64, -176, 64, -176, 18);
        for (int relativeX : IntegratedNervMapBuilder.LIFT_X)
        {
            buildUndergroundRoad(level, centre,
                    relativeX, -176, relativeX, -100, 12);
            buildRecoveryDeck(level, centre, relativeX, -76);
        }
    }

    private static void buildUndergroundRoad(ServerLevel level,
                                              BlockPos centre,
                                              int x1, int z1,
                                              int x2, int z2,
                                              int width)
    {
        int steps = Math.max(Math.abs(x2 - x1), Math.abs(z2 - z1)) + 1;
        for (int along = 0; along < steps; along++)
        {
            double t = steps == 1 ? 0.0D
                    : along / (double) (steps - 1);
            int baseX = (int) Math.round(x1 + (x2 - x1) * t);
            int baseZ = (int) Math.round(z1 + (z2 - z1) * t);
            boolean xMajor = Math.abs(x2 - x1) >= Math.abs(z2 - z1);
            for (int lane = -width / 2; lane <= width / 2; lane++)
            {
                int x = baseX + (xMajor ? 0 : lane);
                int z = baseZ + (xMajor ? lane : 0);
                for (int y = -369; y < -361; y++)
                {
                    set(level, centre.offset(x, y, z), structuralStructure());
                }
                boolean edge = Math.abs(lane) >= width / 2 - 1;
                boolean line = Math.abs(lane) <= 1
                        && Math.floorMod(along, 14) < 7;
                set(level, centre.offset(x, -361, z),
                        edge || line ? ROAD_EDGE : ROAD);
                for (int y = -360; y <= -350; y++)
                {
                    set(level, centre.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
                if (edge && Math.floorMod(along, 16) == 0)
                {
                    set(level, centre.offset(x, -354, z),
                            Blocks.LIGHT.defaultBlockState()
                                    .setValue(LightBlock.LEVEL, 15));
                }
            }
        }
    }

    private static void buildRecoveryDeck(ServerLevel level, BlockPos centre,
                                          int relativeX, int relativeZ)
    {
        int inner = IntegratedNervMapBuilder.SHAFT_OUTER_RADIUS + 1;
        int outer = inner + 6;
        for (int x = -outer; x <= outer; x++)
        {
            for (int z = -outer; z <= outer; z++)
            {
                int edge = Math.max(Math.abs(x), Math.abs(z));
                if (edge < inner)
                {
                    continue;
                }
                BlockState deck = edge == inner || edge == outer
                        ? ROAD_EDGE : Blocks.SMOOTH_STONE.defaultBlockState();
                set(level, centre.offset(relativeX + x, -361,
                        relativeZ + z), deck);
                for (int y = -360; y <= -350; y++)
                {
                    set(level, centre.offset(relativeX + x, y,
                            relativeZ + z), Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    /**
     * A glazed side gallery lets operators follow each carrier from the wet
     * cage gate to the launch-column mouth instead of watching it disappear
     * behind a wall.
     */
    private static void buildCarrierObservationGalleries(ServerLevel level)
    {
        BlockPos origin = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
        for (int variant = 0; variant < 3; variant++)
        {
            BlockPos bed = EvaHangarBuilder.hangarBed(origin, variant);
            int floorY = bed.getY() + 48;
            int startZ = bed.getZ() + 26;
            int endZ = IntegratedNervMapBuilder.lowerLiftBed(variant).getZ()
                    - IntegratedNervMapBuilder.SHAFT_OUTER_RADIUS - 1;
            for (int z = startZ; z <= endZ; z++)
            {
                for (int x = 18; x <= 23; x++)
                {
                    BlockPos floor = new BlockPos(
                            bed.getX() + x, floorY, z);
                    set(level, floor, Math.floorMod(z, 7) == 0
                            ? LIGHT : FLOOR);
                    for (int y = 1; y <= 6; y++)
                    {
                        boolean outerWall = x == 23;
                        set(level, floor.above(y),
                                outerWall ? (y >= 2 && y <= 5
                                        ? GLASS : structuralStructure())
                                        : Blocks.AIR.defaultBlockState());
                    }
                    set(level, floor.above(7), structuralStructure());
                }
                // Replace a narrow part of the carrier-tunnel wall with a
                // pressure-rated window at the operator's eye level.
                for (int y = 50; y <= 55; y++)
                {
                    set(level, new BlockPos(
                            bed.getX() + 17, bed.getY() + y, z), GLASS);
                }
            }
            // Seal the shaft end while preserving the view into its lower bay.
            for (int x = 18; x <= 23; x++)
            {
                for (int y = floorY + 1; y <= floorY + 7; y++)
                {
                    set(level, new BlockPos(
                            bed.getX() + x, y, endZ + 1),
                            y >= floorY + 2 && y <= floorY + 5
                                    ? GLASS : structuralStructure());
                }
            }
        }
    }

    /**
     * Gives the lower carrier galleries a real pedestrian route.
     *
     * <p>The wet-cage observation concourse is at Y=-386, while the carrier
     * side galleries are at Y=-395.  A straight north/south stair descends
     * outside every EVA swept volume, then reaches a transverse pressure
     * corridor immediately before the three carrier tunnels begin.  Only
     * short side branches enter the already-safe gallery lanes; no public
     * floor crosses a carrier centreline after the transport gate.</p>
     */
    private static void buildMechanicalObservationNetwork(
            ServerLevel level, BlockPos centre)
    {
        int upperFloorY = IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getY()
                + EvaHangarBuilder.OBSERVATION_FLOOR_Y;
        int lowerFloorY = upperFloorY - 9;

        // Level approach from the permanent staff-lift/wet-cage spine.
        buildSealedWalkwayZ(level, centre, 50, 58,
                -168, -143, upperFloorY);

        // Nine conventional one-block flights with three-block landings.
        // The route is axis-aligned; there is no diagonal rescue staircase.
        for (int z = -142; z <= -115; z++)
        {
            int drop = Math.min(9, (z + 142 + 2) / 3);
            int floorY = upperFloorY - drop;
            boolean transition = z > -142
                    && Math.min(9, (z + 142 + 2) / 3)
                    != Math.min(9, (z + 141) / 3);
            BlockState tread = transition
                    ? Blocks.POLISHED_DEEPSLATE_STAIRS.defaultBlockState()
                    .setValue(StairBlock.FACING, Direction.NORTH)
                    : FLOOR;
            for (int x = 50; x <= 58; x++)
            {
                for (int supportY = lowerFloorY - 2;
                     supportY < floorY; supportY++)
                {
                    set(level, centre.offset(x, supportY, z), structuralStructure());
                }
                set(level, centre.offset(x, floorY, z),
                        x == 50 || x == 58 ? ROAD_EDGE : tread);
                for (int y = floorY + 1; y <= floorY + 6; y++)
                {
                    boolean wall = x == 50 || x == 58;
                    set(level, centre.offset(x, y, z),
                            wall && y >= floorY + 2 && y <= floorY + 4
                                    ? GLASS
                                    : wall ? structuralStructure()
                                    : Blocks.AIR.defaultBlockState());
                }
                set(level, centre.offset(x, floorY + 7, z),
                        Math.floorMod(x + z, 9) == 0 ? LIGHT : structuralStructure());
            }
        }

        // Safe transverse concourse ends before the mechanical tunnel mouths.
        buildSealedWalkwayX(level, centre, -26, 66,
                -117, -112, lowerFloorY);

        // Three short pressure necks line up with the existing side galleries.
        for (int variant = 0; variant < 3; variant++)
        {
            int galleryMinX = IntegratedNervMapBuilder.LIFT_X[variant] + 18;
            int galleryMaxX = galleryMinX + 5;
            BlockState accent = switch (variant)
            {
                case 0 -> Blocks.ORANGE_CONCRETE.defaultBlockState();
                case 2 -> Blocks.RED_CONCRETE.defaultBlockState();
                default -> Blocks.PURPLE_CONCRETE.defaultBlockState();
            };
            for (int z = -112; z <= -110; z++)
            {
                for (int x = galleryMinX; x <= galleryMaxX; x++)
                {
                    set(level, centre.offset(x, lowerFloorY, z),
                            x == galleryMinX || x == galleryMaxX
                                    ? accent : FLOOR);
                    for (int y = lowerFloorY + 1;
                         y <= lowerFloorY + 6; y++)
                    {
                        boolean wall = x == galleryMinX
                                || x == galleryMaxX;
                        set(level, centre.offset(x, y, z),
                                wall && y >= lowerFloorY + 2
                                        && y <= lowerFloorY + 5
                                        ? GLASS
                                        : wall ? structuralStructure()
                                        : Blocks.AIR.defaultBlockState());
                    }
                    set(level, centre.offset(x, lowerFloorY + 7, z),
                            accent);
                }
            }
        }
    }

    /**
     * Surface heads feed a shared recovery crossbar and one broad boulevard
     * to the authored Tokyo-3 H-01 station boundary at relative Z=244.
     * The station owns Z >= 244, so this exterior join stops at 243 instead
     * of clearing the lift doors and lights inside another facility owner.
     */
    private static void buildSurfaceRecoveryBoulevard(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest)
    {
        BlockPos centre = manifest.centre();
        int surfaceY = manifest.surfaceY();
        // One orthogonal crossbar replaces the former shallow diagonal. Each
        // silo branch now meets it at a visible T-junction.
        buildSurfaceRoad(level, centre, -70, -52, 70, -52,
                surfaceY, true);
        buildSurfaceRoad(level, centre, -42, -58, -42, -52,
                surfaceY, false);
        buildSurfaceRoad(level, centre, 0, -58, 0, -52,
                surfaceY, false);
        buildSurfaceRoad(level, centre, 42, -58, 42, -52,
                surfaceY, false);
        buildSurfaceRoad(level, centre, 0, -52, 0, 243,
                surfaceY, false);

        // The station deck is one block lower. This broad threshold makes the
        // final transition a normal step rather than a hidden collision lip.
        for (int z = 236; z <= 243; z++)
        {
            int deckY = z >= 241 ? surfaceY - 1 : surfaceY;
            for (int x = -12; x <= 12; x++)
            {
                set(level, centre.offset(x, deckY, z),
                        Math.abs(x) >= 10 ? ROAD_EDGE : ROAD);
                for (int y = deckY + 1; y <= deckY + 9; y++)
                {
                    set(level, centre.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    /**
     * Permanent, readable recovery aprons around all three surface heads.
     * The clear 35x35 launch core remains untouched; the apron begins one
     * block outside its pressure shell and joins the shared road naturally.
     */
    private static void buildSurfaceRecoveryPads(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest)
    {
        BlockPos centre = manifest.centre();
        int surfaceY = manifest.surfaceY();
        int inner = IntegratedNervMapBuilder.SHAFT_OUTER_RADIUS + 1;
        int outer = inner + 8;
        for (int variant = 0; variant < 3; variant++)
        {
            int centreX = IntegratedNervMapBuilder.LIFT_X[variant];
            BlockState accent = switch (variant)
            {
                case 0 -> Blocks.ORANGE_CONCRETE.defaultBlockState();
                case 2 -> Blocks.RED_CONCRETE.defaultBlockState();
                default -> Blocks.PURPLE_CONCRETE.defaultBlockState();
            };
            for (int dx = -outer; dx <= outer; dx++)
            {
                for (int dz = -outer; dz <= outer; dz++)
                {
                    int edge = Math.max(Math.abs(dx), Math.abs(dz));
                    if (edge < inner || edge > outer)
                    {
                        continue;
                    }
                    BlockState deck = edge == inner || edge == outer
                            ? accent
                            : Math.floorMod(dx + dz, 11) == 0
                            ? LIGHT
                            : Blocks.SMOOTH_STONE.defaultBlockState();
                    set(level, centre.offset(centreX + dx, surfaceY,
                            -76 + dz), deck);
                    for (int y = surfaceY + 1; y <= surfaceY + 8; y++)
                    {
                        set(level, centre.offset(centreX + dx, y,
                                -76 + dz), Blocks.AIR.defaultBlockState());
                    }
                }
            }
            for (int dx : new int[] {-outer, outer})
            {
                for (int dz : new int[] {-outer, outer})
                {
                    BlockPos pylon = centre.offset(centreX + dx,
                            surfaceY + 1, -76 + dz);
                    set(level, pylon, structuralStructure());
                    set(level, pylon.above(), accent);
                    set(level, pylon.above(2), Blocks.BEACON
                            .defaultBlockState());
                }
            }
        }
    }

    /**
     * A lit, railed public edge for the real custom-fluid LCL lake. The road
     * ring already reaches the south shore; this turns that endpoint into a
     * deliberate scene and leaves one broad opening for immersion/testing.
     */
    private static void buildLclLakePromenade(ServerLevel level,
                                               BlockPos centre)
    {
        int floorY = -361;
        for (int x = -56; x <= 56; x++)
        {
            for (int z = -211; z <= -205; z++)
            {
                BlockState deck = Math.floorMod(x + z, 9) == 0
                        ? LIGHT : Blocks.SMOOTH_STONE.defaultBlockState();
                if (Math.abs(x) >= 53)
                {
                    deck = ROAD_EDGE;
                }
                set(level, centre.offset(x, floorY, z), deck);
                for (int y = floorY + 1; y <= floorY + 5; y++)
                {
                    set(level, centre.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
            }
            if (Math.abs(x) > 5)
            {
                set(level, centre.offset(x, floorY + 1, -211),
                        Blocks.ORANGE_STAINED_GLASS.defaultBlockState());
            }
        }
        for (int z = -211; z <= -205; z++)
        {
            set(level, centre.offset(-57, floorY + 1, z),
                    Blocks.IRON_BARS.defaultBlockState());
            set(level, centre.offset(57, floorY + 1, z),
                    Blocks.IRON_BARS.defaultBlockState());
        }
    }

    /**
     * Two compact pump/intake piers make the lake part of NERV rather than an
     * isolated orange pool.  All liquid cells remain the breathable custom
     * fluid; orange blocks are confined to safety markings above the surface.
     */
    private static void buildLclProcessingScene(ServerLevel level,
                                                BlockPos centre)
    {
        for (int intakeX : new int[] {-36, 36})
        {
            for (int z = -224; z <= -212; z++)
            {
                for (int x = intakeX - 3; x <= intakeX + 3; x++)
                {
                    set(level, centre.offset(x, -360, z),
                            Math.abs(x - intakeX) == 3
                                    ? ROAD_EDGE
                                    : Blocks.IRON_BLOCK.defaultBlockState());
                    if (Math.abs(x - intakeX) == 3)
                    {
                        set(level, centre.offset(x, -359, z),
                                Blocks.IRON_BARS.defaultBlockState());
                    }
                }
            }
            for (int y = -367; y <= -357; y++)
            {
                set(level, centre.offset(intakeX, y, -222),
                        y == -357 ? LIGHT
                                : Blocks.CUT_COPPER.defaultBlockState());
                set(level, centre.offset(intakeX + 1, y, -222),
                        Blocks.CUT_COPPER.defaultBlockState());
            }
            for (int x = intakeX - 2; x <= intakeX + 2; x++)
            {
                for (int z = -211; z <= -207; z++)
                {
                    set(level, centre.offset(x, -359, z),
                            Math.floorMod(x + z, 5) == 0
                                    ? LIGHT : structuralStructure());
                    for (int y = -358; y <= -354; y++)
                    {
                        boolean wall = Math.abs(x - intakeX) == 2
                                || z == -207;
                        set(level, centre.offset(x, y, z),
                                wall ? GLASS
                                        : Blocks.AIR.defaultBlockState());
                    }
                    set(level, centre.offset(x, -353, z), structuralStructure());
                }
            }
        }
    }

    /**
     * Replaces the retired orange block mock-up with the actual breathable
     * LCL fluid. This is intentionally a narrow one-time rescue migration:
     * the lake is isolated from Facility owners and its southern promenade.
     */
    private static void restoreLclLake(ServerLevel level, BlockPos centre)
    {
        for (int x = -84; x <= 84; x++)
        {
            for (int z = -312; z <= -208; z++)
            {
                double nx = x / 80.0D;
                double nz = (z + 260) / 48.0D;
                double distance = nx * nx + nz * nz;
                if (distance > 1.0D)
                {
                    // A three-to-four block pressure rim prevents source LCL
                    // from finding a diagonal air gap and flooding the entire
                    // cavern after the one-time migration.
                    if (distance <= 1.14D)
                    {
                        for (int y = -372; y <= -360; y++)
                        {
                            set(level, centre.offset(x, y, z),
                                    y == -360
                                            ? Blocks.POLISHED_DEEPSLATE
                                            .defaultBlockState()
                                            : Blocks.DEEPSLATE
                                            .defaultBlockState());
                        }
                    }
                    continue;
                }
                for (int y = -372; y <= -348; y++)
                {
                    BlockState state;
                    if (y <= -368)
                    {
                        state = Math.floorMod(x * 17 + z * 31, 23) == 0
                                ? LIGHT
                                : y == -368
                                ? Blocks.CLAY.defaultBlockState()
                                : Blocks.DEEPSLATE.defaultBlockState();
                    }
                    else if (y <= -361)
                    {
                        state = ModFluids.LCL_SOURCE.get()
                                .defaultFluidState().createLegacyBlock();
                    }
                    else
                    {
                        state = Blocks.AIR.defaultBlockState();
                    }
                    set(level, centre.offset(x, y, z), state);
                }
            }
        }
    }

    private static void buildSurfaceRoad(ServerLevel level, BlockPos centre,
                                         int x1, int z1, int x2, int z2,
                                         int surfaceY, boolean broad)
    {
        int width = broad ? 8 : 22;
        int steps = Math.max(Math.abs(x2 - x1), Math.abs(z2 - z1)) + 1;
        for (int along = 0; along < steps; along++)
        {
            double t = steps == 1 ? 0.0D
                    : along / (double) (steps - 1);
            int baseX = (int) Math.round(x1 + (x2 - x1) * t);
            int baseZ = (int) Math.round(z1 + (z2 - z1) * t);
            boolean xMajor = Math.abs(x2 - x1) >= Math.abs(z2 - z1);
            for (int lane = -width / 2; lane <= width / 2; lane++)
            {
                int x = baseX + (xMajor ? 0 : lane);
                int z = baseZ + (xMajor ? lane : 0);
                for (int y = surfaceY - 4; y < surfaceY; y++)
                {
                    set(level, centre.offset(x, y, z),
                            com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                }
                boolean edge = Math.abs(lane) >= width / 2 - 1;
                boolean centreLine = Math.abs(lane) <= 1
                        && Math.floorMod(along, 16) < 8;
                set(level, centre.offset(x, surfaceY, z),
                        edge || centreLine ? Blocks.WHITE_CONCRETE
                                .defaultBlockState()
                                : Blocks.GRAY_CONCRETE.defaultBlockState());
                for (int y = surfaceY + 1;
                     y <= surfaceY
                             + FacilitySchemaV2.EVA_SURFACE_SWEEP_HEIGHT;
                     y++)
                {
                    set(level, centre.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
                if (edge && Math.floorMod(along, 20) == 0)
                {
                    set(level, centre.offset(x, surfaceY + 8, z),
                            Blocks.LIGHT.defaultBlockState()
                                    .setValue(LightBlock.LEVEL, 15));
                }
            }
        }
    }

    private static void buildSealedWalkwayX(
            ServerLevel level, BlockPos centre,
            int minX, int maxX, int minZ, int maxZ, int floorY)
    {
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                set(level, centre.offset(x, floorY, z),
                        Math.floorMod(x + z, 11) == 0 ? LIGHT : FLOOR);
                for (int y = floorY + 1; y <= floorY + 6; y++)
                {
                    boolean wall = z == minZ || z == maxZ;
                    set(level, centre.offset(x, y, z),
                            wall && y >= floorY + 2 && y <= floorY + 5
                                    ? GLASS
                                    : wall ? structuralStructure()
                                    : Blocks.AIR.defaultBlockState());
                }
                set(level, centre.offset(x, floorY + 7, z),
                        Math.floorMod(x - z, 13) == 0 ? LIGHT : structuralStructure());
            }
        }
    }

    private static void buildSealedWalkwayZ(
            ServerLevel level, BlockPos centre,
            int minX, int maxX, int minZ, int maxZ, int floorY)
    {
        for (int z = minZ; z <= maxZ; z++)
        {
            for (int x = minX; x <= maxX; x++)
            {
                set(level, centre.offset(x, floorY, z),
                        Math.floorMod(x + z, 11) == 0 ? LIGHT : FLOOR);
                for (int y = floorY + 1; y <= floorY + 6; y++)
                {
                    boolean wall = x == minX || x == maxX;
                    set(level, centre.offset(x, y, z),
                            wall && y >= floorY + 2 && y <= floorY + 5
                                    ? GLASS
                                    : wall ? structuralStructure()
                                    : Blocks.AIR.defaultBlockState());
                }
                set(level, centre.offset(x, floorY + 7, z),
                        Math.floorMod(x - z, 13) == 0 ? LIGHT : structuralStructure());
            }
        }
    }

    private static BlockPos marker(BlockPos centre)
    {
        return new BlockPos(centre.getX() + 140, -378,
                centre.getZ() + 230);
    }

    private static void set(ServerLevel level, BlockPos position,
                            BlockState state)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, UPDATE_CLIENTS);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }
}
