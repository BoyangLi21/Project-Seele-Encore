package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.AttachFace;

/**
 * Physical rescue link between the Facility v2 command deck and the proven
 * three-cage mechanical plant.
 *
 * <p>The vertical change is handled only by the permanent staff lift. The
 * command deck and wet-cage observation deck each use a level, enclosed,
 * orthogonal corridor. No teleport, disposable cabin or diagonal staircase
 * participates.</p>
 */
public final class FacilityV2LegacyBridgeBuilder
{
    private static final int REVISION = 3;
    private static BlockState structuralStructure()
    {
        return com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
    }
    private static final BlockState FLOOR =
            Blocks.POLISHED_DEEPSLATE.defaultBlockState();
    private static final BlockState LIGHT =
            Blocks.SEA_LANTERN.defaultBlockState();
    private static final BlockState GLASS =
            Blocks.GRAY_STAINED_GLASS.defaultBlockState();
    private static final BlockState DARK =
            Blocks.BLACK_CONCRETE.defaultBlockState();
    private static final BlockState CYAN =
            Blocks.CYAN_CONCRETE.defaultBlockState();
    private static final BlockState WEST_BUTTON =
            Blocks.STONE_BUTTON.defaultBlockState()
                    .setValue(ButtonBlock.FACE, AttachFace.WALL)
                    .setValue(ButtonBlock.FACING, Direction.EAST);
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;

    private static final int COMMAND_FLOOR_Y = -333;
    private static final int OBSERVATION_FLOOR_Y =
            IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getY()
                    + EvaHangarBuilder.OBSERVATION_FLOOR_Y;
    /** Cabin Y whose deck is flush with the legacy observation floor. */
    public static final int WET_CAGE_LIFT_Y = OBSERVATION_FLOOR_Y + 1;
    private static final int[] STAFF_LANDINGS =
            {-408, WET_CAGE_LIFT_Y, -348, -332};
    private static final BlockPos MARKER_A =
            new BlockPos(59, COMMAND_FLOOR_Y - 1, 64);
    private static final BlockPos MARKER_B =
            new BlockPos(59, OBSERVATION_FLOOR_Y - 1, -164);
    private static final BlockPos REVISION_MARKER =
            new BlockPos(-64, OBSERVATION_FLOOR_Y - 2, -182);

    private FacilityV2LegacyBridgeBuilder() {}

    public static boolean ensure(ServerLevel level, BlockPos facilityCentre)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return installed(level, facilityCentre);
        boolean mechanicalReady =
                FacilityV2RescueDirector.isTargetWorld(level.getServer())
                        ? IntegratedNervMapBuilder.rescueMechanicalReady(level)
                        : IntegratedNervMapBuilder.isInstalled(level);
        if (facilityCentre.getX()
                != IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getX()
                || facilityCentre.getZ()
                != IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getZ()
                || !mechanicalReady)
        {
            return false;
        }
        if (installed(level, facilityCentre))
        {
            return true;
        }
        build(level, facilityCentre);
        return installed(level, facilityCentre);
    }

    private static boolean installed(ServerLevel level, BlockPos centre)
    {
        return level.getBlockState(centre.offset(MARKER_A))
                .is(Blocks.NETHERITE_BLOCK)
                && level.getBlockState(centre.offset(MARKER_B))
                .is(Blocks.LODESTONE)
                && level.getBlockState(centre.offset(
                        30, COMMAND_FLOOR_Y, 32))
                .is(Blocks.POLISHED_DEEPSLATE)
                && level.getBlockState(centre.offset(
                        30, COMMAND_FLOOR_Y + 2, 32)).isAir()
                && (level.getBlockState(centre.offset(
                        54, OBSERVATION_FLOOR_Y, 0))
                .is(Blocks.POLISHED_DEEPSLATE)
                || level.getBlockState(centre.offset(
                        54, OBSERVATION_FLOOR_Y, 0))
                .is(Blocks.SEA_LANTERN))
                && level.getBlockState(centre.offset(
                        54, OBSERVATION_FLOOR_Y + 2, 0)).isAir()
                && level.getBlockState(centre.offset(
                        54, OBSERVATION_FLOOR_Y, -164))
                .is(Blocks.POLISHED_DEEPSLATE)
                && level.getBlockState(centre.offset(
                        58, WET_CAGE_LIFT_Y + 2, 58))
                .is(Blocks.STONE_BUTTON)
                && level.getBlockState(centre.offset(REVISION_MARKER))
                .is(Blocks.RESPAWN_ANCHOR)
                && !level.getBlockState(centre.offset(
                        0, OBSERVATION_FLOOR_Y, -176)).isAir()
                && level.getBlockState(centre.offset(
                        0, OBSERVATION_FLOOR_Y + 2, -170)).isAir();
    }

    private static void build(ServerLevel level, BlockPos centre)
    {
        PerformanceCounters.recordBuilderCall();
        purgeRetiredDiagonalRoute(level, centre);
        buildCommandLiftApproach(level, centre);
        buildWetCageLiftLanding(level, centre);
        buildObservationApproach(level, centre);
        buildWetCageOrientationHall(level, centre);
        buildStaffLiftControls(level, centre);
        set(level, centre.offset(MARKER_A),
                Blocks.NETHERITE_BLOCK.defaultBlockState());
        set(level, centre.offset(MARKER_B),
                Blocks.LODESTONE.defaultBlockState());
        set(level, centre.offset(REVISION_MARKER),
                Blocks.RESPAWN_ANCHOR.defaultBlockState());
    }

    /**
     * Removes only the exact volumes owned by the retired 53-step rescue
     * stair. The replacement is then authored into a disjoint x=50..60 route.
     */
    private static void purgeRetiredDiagonalRoute(ServerLevel level,
                                                   BlockPos centre)
    {
        int oldSteps = COMMAND_FLOOR_Y - OBSERVATION_FLOOR_Y;
        for (int step = 0; step <= oldSteps; step++)
        {
            int z = 32 - step;
            int floorY = COMMAND_FLOOR_Y - step;
            clear(level, centre, 66, 74, floorY, floorY + 7, z, z);
        }
        int stairEndZ = 32 - oldSteps;
        clear(level, centre, 66, 74,
                OBSERVATION_FLOOR_Y, OBSERVATION_FLOOR_Y + 8,
                -168, stairEndZ);
        // x=50..52 belongs to Unit-02's existing observation room.
        clear(level, centre, 53, 74,
                OBSERVATION_FLOOR_Y, OBSERVATION_FLOOR_Y + 8,
                -168, -160);
    }

    private static void buildCommandLiftApproach(ServerLevel level,
                                                  BlockPos centre)
    {
        // East door of the imported command shell to a broad level gallery.
        buildHorizontalX(level, centre, 24, 59, 28, 36,
                COMMAND_FLOOR_Y);
        clear(level, centre, 24, 29, COMMAND_FLOOR_Y + 1,
                COMMAND_FLOOR_Y + 6, 29, 35);

        // One square corner turns north into the staff-lift west landing.
        buildHorizontalZ(level, centre, 54, 59, 32, 68,
                COMMAND_FLOOR_Y);
        clear(level, centre, 58, 60, COMMAND_FLOOR_Y + 1,
                COMMAND_FLOOR_Y + 5, 61, 66);

        for (int x : new int[] {30, 44, 56})
        {
            for (int y = -360; y < COMMAND_FLOOR_Y; y++)
            {
                set(level, centre.offset(x, y, 29),
                        Math.floorMod(y + 360, 8) == 0 ? LIGHT : structuralStructure());
                set(level, centre.offset(x, y, 35),
                        Math.floorMod(y + 360, 8) == 0 ? LIGHT : structuralStructure());
            }
        }
    }

    private static void buildWetCageLiftLanding(ServerLevel level,
                                                 BlockPos centre)
    {
        // Flush deck at y=-386; cabin target is one block higher.
        buildHorizontalX(level, centre, 48, 59, 60, 68,
                OBSERVATION_FLOOR_Y);
        // The runtime director replaces this aperture with interlocked doors.
        for (int z = 61; z <= 66; z++)
        {
            for (int y = WET_CAGE_LIFT_Y;
                 y <= WET_CAGE_LIFT_Y + 4; y++)
            {
                set(level, centre.offset(60, y, z),
                        Blocks.IRON_BLOCK.defaultBlockState());
            }
        }
    }

    private static void buildObservationApproach(ServerLevel level,
                                                  BlockPos centre)
    {
        // Long north-south corridor deliberately stays outside all carrier,
        // crane and launch-silo sweep volumes.
        buildHorizontalZ(level, centre, 50, 58, -168, 64,
                OBSERVATION_FLOOR_Y);
        for (int x = 50; x <= 58; x++)
        {
            for (int z = -168; z <= -160; z++)
            {
                set(level, centre.offset(x, OBSERVATION_FLOOR_Y, z),
                        Math.floorMod(x, 8) == 0
                                && (z == -167 || z == -161)
                                ? LIGHT : FLOOR);
                set(level, centre.offset(
                                x, OBSERVATION_FLOOR_Y + 8, z),
                        Math.floorMod(x + z, 11) == 0 ? LIGHT : structuralStructure());
                for (int y = OBSERVATION_FLOOR_Y + 1;
                     y < OBSERVATION_FLOOR_Y + 8; y++)
                {
                    BlockState state = z == -168 || z == -160
                            ? (y >= OBSERVATION_FLOOR_Y + 3
                            && y <= OBSERVATION_FLOOR_Y + 5
                            ? GLASS : structuralStructure())
                            : Blocks.AIR.defaultBlockState();
                    set(level, centre.offset(x, y, z), state);
                }
            }
        }
        clear(level, centre, 50, 53, OBSERVATION_FLOOR_Y + 1,
                OBSERVATION_FLOOR_Y + 7, -167, -161);
    }

    /**
     * A real lower-lift arrival hall: operators leave the permanent staff
     * elevator into one sealed transverse concourse and can read all three
     * wet-cage entrances at once.  The previous single corridor arrived at
     * Unit-02's side wall, making EVA-00/01 look like unrelated dead ends.
     */
    private static void buildWetCageOrientationHall(ServerLevel level,
                                                     BlockPos centre)
    {
        int minX = -64;
        int maxX = 64;
        int minZ = -182;
        int maxZ = -172;
        int floorY = OBSERVATION_FLOOR_Y;
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                BlockState floor = Math.floorMod(x + z, 11) == 0
                        ? LIGHT : FLOOR;
                for (int cage = 0; cage < 3; cage++)
                {
                    int centreX = IntegratedNervMapBuilder.LIFT_X[cage];
                    if (Math.abs(x - centreX) <= 4)
                    {
                        floor = switch (cage)
                        {
                            case 0 -> Blocks.ORANGE_CONCRETE
                                    .defaultBlockState();
                            case 2 -> Blocks.RED_CONCRETE
                                    .defaultBlockState();
                            default -> Blocks.PURPLE_CONCRETE
                                    .defaultBlockState();
                        };
                    }
                }
                set(level, centre.offset(x, floorY, z), floor);
                set(level, centre.offset(x, floorY + 8, z),
                        Math.floorMod(x - z, 13) == 0 ? LIGHT : structuralStructure());
                for (int y = floorY + 1; y < floorY + 8; y++)
                {
                    boolean boundary = x == minX || x == maxX
                            || z == minZ || z == maxZ;
                    boolean cageDoor = z == maxZ
                            && isCageDoorColumn(x);
                    boolean liftNeck = x >= 50 && x <= 58
                            && z == maxZ;
                    set(level, centre.offset(x, y, z),
                            boundary && !cageDoor && !liftNeck
                                    ? (y >= floorY + 3
                                    && y <= floorY + 5 ? GLASS : structuralStructure())
                                    : Blocks.AIR.defaultBlockState());
                }
            }
        }

        // Three straight, pressure-framed necks enter the existing control
        // rooms.  They cut only the rooms' north walls and never cross the
        // boarding bridge or EVA transport sweep.
        for (int cage = 0; cage < 3; cage++)
        {
            int centreX = IntegratedNervMapBuilder.LIFT_X[cage];
            BlockState accent = switch (cage)
            {
                case 0 -> Blocks.ORANGE_CONCRETE.defaultBlockState();
                case 2 -> Blocks.RED_CONCRETE.defaultBlockState();
                default -> Blocks.PURPLE_CONCRETE.defaultBlockState();
            };
            for (int z = -172; z <= -166; z++)
            {
                for (int x = centreX - 4; x <= centreX + 4; x++)
                {
                    set(level, centre.offset(x, floorY, z),
                            Math.abs(x - centreX) == 4 ? accent : FLOOR);
                    set(level, centre.offset(x, floorY + 7, z),
                            Math.abs(x - centreX) == 4 ? accent : structuralStructure());
                    for (int y = floorY + 1; y < floorY + 7; y++)
                    {
                        boolean wall = Math.abs(x - centreX) == 4;
                        set(level, centre.offset(x, y, z),
                                wall ? (y >= floorY + 2
                                && y <= floorY + 5 ? GLASS : structuralStructure())
                                : Blocks.AIR.defaultBlockState());
                    }
                }
            }
        }

        // Orthogonal neck from the staff-lift corridor into the east end of
        // the concourse.
        buildHorizontalZ(level, centre, 50, 58, -172, -168, floorY);
    }

    private static boolean isCageDoorColumn(int x)
    {
        for (int centreX : IntegratedNervMapBuilder.LIFT_X)
        {
            if (Math.abs(x - centreX) <= 4)
            {
                return true;
            }
        }
        return false;
    }

    /**
     * Four destination buttons at every landing: service, wet cages,
     * technical and command. Back-lit full panels make the controls legible.
     */
    private static void buildStaffLiftControls(ServerLevel level,
                                               BlockPos centre)
    {
        for (int landing : STAFF_LANDINGS)
        {
            int buttonY = landing + 2;
            for (int z = 57; z <= 60; z++)
            {
                set(level, centre.offset(57, buttonY, z),
                        z == 58 ? CYAN : DARK);
                set(level, centre.offset(58, buttonY, z), WEST_BUTTON);
            }
            set(level, centre.offset(57, buttonY + 1, 58), LIGHT);
            set(level, centre.offset(57, buttonY + 1, 59), LIGHT);
        }
    }

    private static void buildHorizontalX(ServerLevel level, BlockPos centre,
                                         int minX, int maxX,
                                         int minZ, int maxZ, int floorY)
    {
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                set(level, centre.offset(x, floorY, z),
                        Math.floorMod(x + z, 9) == 0 ? LIGHT : FLOOR);
                set(level, centre.offset(x, floorY + 8, z),
                        Math.floorMod(x + z, 11) == 0 ? LIGHT : structuralStructure());
                for (int y = floorY + 1; y < floorY + 8; y++)
                {
                    boolean wall = z == minZ || z == maxZ;
                    set(level, centre.offset(x, y, z),
                            wall ? windowedWall(y - floorY) :
                                    Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    private static void buildHorizontalZ(ServerLevel level, BlockPos centre,
                                         int minX, int maxX,
                                         int minZ, int maxZ, int floorY)
    {
        for (int z = minZ; z <= maxZ; z++)
        {
            for (int x = minX; x <= maxX; x++)
            {
                set(level, centre.offset(x, floorY, z),
                        Math.floorMod(x + z, 9) == 0 ? LIGHT : FLOOR);
                set(level, centre.offset(x, floorY + 8, z),
                        Math.floorMod(x + z, 11) == 0 ? LIGHT : structuralStructure());
                for (int y = floorY + 1; y < floorY + 8; y++)
                {
                    boolean wall = x == minX || x == maxX;
                    set(level, centre.offset(x, y, z),
                            wall ? windowedWall(y - floorY) :
                                    Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    private static BlockState windowedWall(int relativeY)
    {
        return relativeY >= 3 && relativeY <= 5 ? GLASS : structuralStructure();
    }

    private static void clear(ServerLevel level, BlockPos centre,
                              int minX, int maxX,
                              int minY, int maxY,
                              int minZ, int maxZ)
    {
        for (int y = minY; y <= maxY; y++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                for (int x = minX; x <= maxX; x++)
                {
                    set(level, centre.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    private static void set(ServerLevel level, BlockPos position,
                            BlockState state)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (!level.getBlockState(position).equals(state)
                && level.setBlock(position, state, UPDATE_CLIENTS))
        {
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }
}
