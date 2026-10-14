package com.projectseele.world;

import java.nio.file.Files;
import java.nio.file.Path;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;

/**
 * Compiles the permanent same-world route between Tokyo-3 and GeoFront.
 *
 * <p>The S20 rebuild deliberately keeps this route independent from the
 * command room and all EVA swept volumes. A supported B-40 concourse reaches
 * one sealed vertical shaft, and the upper landing opens into a compact
 * street-level pavilion. The lift itself is installed by
 * {@link S20PhysicalElevatorDirector}; this class owns only the fixed shaft,
 * station and approach geometry.</p>
 */
public final class S20SurfaceTransitDirector
{
    public static final int AXIS_X = 130;
    public static final int AXIS_Z = 273;
    public static final int LOWER_WALK_Y = -442;
    public static final int UPPER_WALK_Y = 81;

    private static final int SHAFT_MIN_Y = LOWER_WALK_Y - 1;
    private static final int SHAFT_MAX_Y = UPPER_WALK_Y + 4;
    private static final int SHAFT_RADIUS = 4;
    private static final int SHAFT_CLEAR_RADIUS = 3;
    private static final int SEGMENT_HEIGHT = 32;
    private static final int SHAFT_SEGMENTS =
            (SHAFT_MAX_Y - SHAFT_MIN_Y + SEGMENT_HEIGHT)
                    / SEGMENT_HEIGHT;
    private static final int PHASES = SHAFT_SEGMENTS + 2;
    private static final int PHASE_INTERVAL_TICKS = 2;
    private static final BlockPos MARKER_BASE =
            new BlockPos(146, -448, 257);
    private static final BlockPos LOWER_REVISION_MARKER =
            new BlockPos(146, -448, 256);
    private static final BlockPos BASE_REVISION_MARKER =
            new BlockPos(146, -448, 255);
    private static final BlockPos LOWER_SHELL_REVISION_MARKER =
            new BlockPos(146, -448, 254);
    private static final int UPDATE =
            Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE;

    private static final BlockState FLOOR =
            Blocks.POLISHED_DEEPSLATE.defaultBlockState();
    private static BlockState structuralStructure()
    {
        return com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
    }
    private static final BlockState WALL =
            Blocks.DEEPSLATE_TILES.defaultBlockState();
    private static final BlockState BLACK =
            Blocks.BLACK_CONCRETE.defaultBlockState();
    private static final BlockState ACCENT =
            Blocks.ORANGE_CONCRETE.defaultBlockState();
    private static final BlockState GLASS =
            Blocks.GRAY_STAINED_GLASS.defaultBlockState();
    private static final BlockState LIGHT =
            Blocks.SEA_LANTERN.defaultBlockState();
    private static final BlockState AIR =
            Blocks.AIR.defaultBlockState();

    private static boolean completeLogged;

    private S20SurfaceTransitDirector() {}

    public static void tick(MinecraftServer server)
    {
        if(NervLegacyGenerationGuardR52.retired(server))return;
        if (!authorised(server)
                || server.getTickCount() % PHASE_INTERVAL_TICKS != 0)
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return;
        }
        if(FacilityLayoutR21.active(level))return;
        if (!shaftBaseInstalled(level))
        {
            level.getChunkAt(new BlockPos(
                    AXIS_X, SHAFT_MIN_Y - 2, AXIS_Z));
            buildShaftBase(level);
            level.setBlock(BASE_REVISION_MARKER,
                    Blocks.STRUCTURE_VOID.defaultBlockState(),
                    Block.UPDATE_CLIENTS);
            ProjectSeele.LOGGER.info(
                    "S20 public-lift lower foundation restored: "
                            + "axis=({}, {}) y=[{},{}]",
                    AXIS_X, AXIS_Z, SHAFT_MIN_Y - 2,
                    SHAFT_MIN_Y - 1);
            return;
        }
        if (!lowerShaftShellInstalled(level))
        {
            level.getChunkAt(new BlockPos(
                    AXIS_X, SHAFT_MIN_Y, AXIS_Z));
            buildLowerShaftShell(level);
            level.setBlock(LOWER_SHELL_REVISION_MARKER,
                    Blocks.STRUCTURE_VOID.defaultBlockState(),
                    Block.UPDATE_CLIENTS);
            ProjectSeele.LOGGER.info(
                    "S20 public-lift lower shaft walls restored: "
                            + "axis=({}, {}) y=[{},{}] interiorPreserved=true",
                    AXIS_X, AXIS_Z, SHAFT_MIN_Y,
                    SHAFT_MIN_Y + 19);
            return;
        }
        if (!lowerConcourseInstalled(level))
        {
            level.getChunkAt(new BlockPos(100, LOWER_WALK_Y, AXIS_Z));
            buildLowerConcourse(level);
            level.setBlock(LOWER_REVISION_MARKER,
                    Blocks.STRUCTURE_VOID.defaultBlockState(),
                    Block.UPDATE_CLIENTS);
            ProjectSeele.LOGGER.info(
                    "S20 B-40 public-lift concourse restored: "
                            + "world=x[78,123] y[-443,-438] z[270,276] "
                            + "receipt=physical-blocks");
            return;
        }
        int phase = firstMissingPhase(level);
        if (phase < 0)
        {
            if (!completeLogged)
            {
                completeLogged = true;
                ProjectSeele.LOGGER.info(
                        "S20 surface transit ready: "
                                + "physicalShaft=true teleport=false "
                                + "axis=({}, {}) walkY={}->{} "
                                + "b40Connected=true streetConnected=true",
                        AXIS_X, AXIS_Z, LOWER_WALK_Y, UPPER_WALK_Y);
            }
            return;
        }

        level.getChunkAt(new BlockPos(
                AXIS_X,
                phase == 0
                        ? LOWER_WALK_Y
                        : Math.min(SHAFT_MAX_Y,
                        SHAFT_MIN_Y
                                + Math.max(0, phase - 1)
                                * SEGMENT_HEIGHT),
                AXIS_Z));
        if (phase == 0)
        {
            buildLowerConcourse(level);
        }
        else if (phase <= SHAFT_SEGMENTS)
        {
            int minY = SHAFT_MIN_Y
                    + (phase - 1) * SEGMENT_HEIGHT;
            int maxY = Math.min(SHAFT_MAX_Y,
                    minY + SEGMENT_HEIGHT - 1);
            buildShaftSegment(level, minY, maxY);
        }
        else
        {
            buildSurfacePavilion(level);
        }
        level.setBlock(marker(phase),
                Blocks.STRUCTURE_VOID.defaultBlockState(),
                Block.UPDATE_CLIENTS);
        ProjectSeele.LOGGER.info(
                "S20 surface transit phase {}/{} installed: {}",
                phase + 1, PHASES, phaseName(phase));
    }

    public static boolean installed(ServerLevel level)
    {
        if(FacilityLayoutR21.active(level))return level.getBlockState(new BlockPos(130,-442,269)).is(com.supermartijn642.movingelevators.MovingElevators.elevator_block)
                &&level.getBlockState(new BlockPos(130,75,269)).is(com.supermartijn642.movingelevators.MovingElevators.elevator_block);
        return shaftBaseInstalled(level)
                && lowerShaftShellInstalled(level)
                && lowerConcourseInstalled(level)
                && firstMissingPhase(level) < 0;
    }

    private static boolean lowerShaftShellInstalled(ServerLevel level)
    {
        if (!level.getBlockState(LOWER_SHELL_REVISION_MARKER)
                .is(Blocks.STRUCTURE_VOID))
        {
            return false;
        }
        for (int y : new int[] {SHAFT_MIN_Y, SHAFT_MIN_Y + 19})
        {
            for (int[] offset : new int[][] {
                    {-SHAFT_RADIUS, 0}, {SHAFT_RADIUS, 0},
                    {0, -SHAFT_RADIUS}, {0, SHAFT_RADIUS}})
            {
                BlockPos sample = new BlockPos(
                        AXIS_X + offset[0], y, AXIS_Z + offset[1]);
                if (!level.getBlockState(sample)
                        .isCollisionShapeFullBlock(level, sample))
                {
                    return false;
                }
            }
        }
        return true;
    }

    private static void buildLowerShaftShell(ServerLevel level)
    {
        for (int y = SHAFT_MIN_Y;
             y <= SHAFT_MIN_Y + 19; y++)
        {
            boolean band = Math.floorMod(y - SHAFT_MIN_Y, 8) == 0;
            for (int dx = -SHAFT_RADIUS;
                 dx <= SHAFT_RADIUS; dx++)
            {
                for (int dz = -SHAFT_RADIUS;
                     dz <= SHAFT_RADIUS; dz++)
                {
                    if (Math.max(Math.abs(dx), Math.abs(dz))
                            <= SHAFT_CLEAR_RADIUS)
                    {
                        continue;
                    }
                    BlockPos position = new BlockPos(
                            AXIS_X + dx, y, AXIS_Z + dz);
                    boolean cardinalLight = (dx == 0 || dz == 0)
                            && Math.floorMod(y - SHAFT_MIN_Y, 8) == 4;
                    set(level, position, cardinalLight ? LIGHT
                            : band ? ACCENT : structuralStructure());
                }
            }
        }
    }

    private static boolean shaftBaseInstalled(ServerLevel level)
    {
        if (!level.getBlockState(BASE_REVISION_MARKER)
                .is(Blocks.STRUCTURE_VOID))
        {
            return false;
        }
        int y = SHAFT_MIN_Y - 1;
        for (int dx : new int[] {-SHAFT_RADIUS, 0, SHAFT_RADIUS})
        {
            for (int dz : new int[] {-SHAFT_RADIUS, 0, SHAFT_RADIUS})
            {
                BlockPos sample = new BlockPos(
                        AXIS_X + dx, y, AXIS_Z + dz);
                if (!level.getBlockState(sample)
                        .isCollisionShapeFullBlock(level, sample))
                {
                    return false;
                }
            }
        }
        return true;
    }

    private static void buildShaftBase(ServerLevel level)
    {
        for (int y = SHAFT_MIN_Y - 2;
             y <= SHAFT_MIN_Y - 1; y++)
        {
            for (int dx = -SHAFT_RADIUS;
                 dx <= SHAFT_RADIUS; dx++)
            {
                for (int dz = -SHAFT_RADIUS;
                     dz <= SHAFT_RADIUS; dz++)
                {
                    boolean beam = y == SHAFT_MIN_Y - 2
                            || dx == 0 || dz == 0;
                    set(level, new BlockPos(
                            AXIS_X + dx, y, AXIS_Z + dz),
                            beam ? structuralStructure() : FLOOR);
                }
            }
        }
    }

    /** Repaints the bounded street pavilion after an overlapping old lot is removed. */
    public static void repairSurfacePavilion(ServerLevel level)
    {
        if(FacilityLayoutR21.active(level))return;
        buildSurfacePavilion(level);
    }

    private static boolean lowerConcourseInstalled(ServerLevel level)
    {
        if (!level.getBlockState(LOWER_REVISION_MARKER)
                .is(Blocks.STRUCTURE_VOID))
        {
            return false;
        }
        for (int x : new int[] {78, 100, AXIS_X - 7})
        {
            BlockPos feet = new BlockPos(x, LOWER_WALK_Y, AXIS_Z);
            if (!level.getBlockState(feet.below())
                    .isCollisionShapeFullBlock(level, feet.below())
                    || !level.getBlockState(feet).isAir()
                    || !level.getBlockState(feet.above()).isAir())
            {
                return false;
            }
        }
        /*
         * The compact-cage branch enters through the north wall at z=270.
         * A previous revision checked only the east-west floor anchors, so
         * the phase marker could remain valid while buildLowerConcourse()
         * had sealed this aperture after the personnel route was compiled.
         */
        BlockPos cageSeam = new BlockPos(108, LOWER_WALK_Y,
                AXIS_Z - 3);
        if (!level.getBlockState(cageSeam.below())
                .isCollisionShapeFullBlock(level, cageSeam.below())
                || !level.getBlockState(cageSeam).isAir()
                || !level.getBlockState(cageSeam.above()).isAir())
        {
            return false;
        }
        return true;
    }

    private static boolean authorised(MinecraftServer server)
    {
        if (!FacilityWorldPolicy.isS20Rebuild(server))
        {
            return false;
        }
        Path root = server.getWorldPath(LevelResource.ROOT);
        return Files.isRegularFile(
                root.resolve(FacilityWorldPolicy.S20_MARKER));
    }

    private static int firstMissingPhase(ServerLevel level)
    {
        for (int phase = 0; phase < PHASES; phase++)
        {
            if (!level.getBlockState(marker(phase))
                    .is(Blocks.STRUCTURE_VOID))
            {
                return phase;
            }
        }
        return -1;
    }

    private static BlockPos marker(int phase)
    {
        return MARKER_BASE.offset(phase, 0, 0);
    }

    private static String phaseName(int phase)
    {
        if (phase == 0)
        {
            return "B-40 PUBLIC-LIFT CONCOURSE";
        }
        if (phase <= SHAFT_SEGMENTS)
        {
            int minY = SHAFT_MIN_Y
                    + (phase - 1) * SEGMENT_HEIGHT;
            int maxY = Math.min(SHAFT_MAX_Y,
                    minY + SEGMENT_HEIGHT - 1);
            return "SEALED SHAFT Y[" + minY + "," + maxY + "]";
        }
        return "TOKYO-3 STREET PAVILION";
    }

    /**
     * Extends the already compiled B-40 bridge straight east. The route is
     * deliberately orthogonal, supported and enclosed; it never enters the
     * command-room owner or an EVA carrier line.
     */
    private static void buildLowerConcourse(ServerLevel level)
    {
        int minX = 78;
        int maxX = AXIS_X - 7;
        int floorY = LOWER_WALK_Y - 1;
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = AXIS_Z - 2; z <= AXIS_Z + 2; z++)
            {
                set(level, new BlockPos(x, floorY, z),
                        Math.floorMod(x, 8) == 0 && z == AXIS_Z
                                ? LIGHT : FLOOR);
                for (int y = LOWER_WALK_Y;
                     y <= LOWER_WALK_Y + 3; y++)
                {
                    set(level, new BlockPos(x, y, z), AIR);
                }
                set(level, new BlockPos(x, LOWER_WALK_Y + 4, z),
                        Math.floorMod(x, 6) == 0 && z == AXIS_Z
                                ? LIGHT : WALL);
            }
            for (int z : new int[] {AXIS_Z - 3, AXIS_Z + 3})
            {
                set(level, new BlockPos(x, floorY, z), structuralStructure());
                for (int y = LOWER_WALK_Y;
                     y <= LOWER_WALK_Y + 3; y++)
                {
                    boolean cageAperture = z == AXIS_Z - 3
                            && x >= 105 && x <= 111;
                    BlockState state = cageAperture
                            ? AIR
                            : y == LOWER_WALK_Y + 1
                            && Math.floorMod(x, 5) != 0
                            ? GLASS
                            : y == LOWER_WALK_Y + 2
                            ? ACCENT : WALL;
                    set(level, new BlockPos(x, y, z), state);
                }
                set(level, new BlockPos(
                        x, LOWER_WALK_Y + 4, z), WALL);
            }
            if (Math.floorMod(x - minX, 6) == 0)
            {
                for (int z = AXIS_Z - 3;
                     z <= AXIS_Z + 3; z++)
                {
                    set(level, new BlockPos(
                            x, floorY - 1, z), structuralStructure());
                }
            }
        }
    }

    /**
     * Builds only the fixed nine-by-nine shaft shell. The seven-by-seven
     * interior is kept clear so the real five-by-five cabin can traverse it.
     */
    private static void buildShaftSegment(
            ServerLevel level, int minY, int maxY)
    {
        for (int y = minY; y <= maxY; y++)
        {
            boolean band = Math.floorMod(
                    y - SHAFT_MIN_Y, 32) == 0;
            for (int dx = -SHAFT_RADIUS;
                 dx <= SHAFT_RADIUS; dx++)
            {
                for (int dz = -SHAFT_RADIUS;
                     dz <= SHAFT_RADIUS; dz++)
                {
                    BlockPos position = new BlockPos(
                            AXIS_X + dx, y, AXIS_Z + dz);
                    if (Math.abs(dx) <= SHAFT_CLEAR_RADIUS
                            && Math.abs(dz) <= SHAFT_CLEAR_RADIUS)
                    {
                        set(level, position, AIR);
                        continue;
                    }
                    boolean cardinalLight =
                            (dx == 0 || dz == 0)
                                    && Math.floorMod(
                                    y - SHAFT_MIN_Y, 16) == 8;
                    set(level, position,
                            cardinalLight ? LIGHT
                                    : band ? ACCENT : structuralStructure());
                }
            }
        }
    }

    /**
     * Replaces one clear road cell with a compact NERV transit pavilion. Its
     * west aperture opens directly onto the authored Tokyo-3 street at y=81.
     */
    private static void buildSurfacePavilion(ServerLevel level)
    {
        int minX = AXIS_X - 14;
        int maxX = AXIS_X + 6;
        int minZ = AXIS_Z - 6;
        int maxZ = AXIS_Z + 6;
        int floorY = UPPER_WALK_Y - 1;
        int roofY = UPPER_WALK_Y + 6;

        for (int x = minX; x <= maxX; x++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                boolean edge = x == minX || x == maxX
                        || z == minZ || z == maxZ;
                set(level, new BlockPos(x, floorY, z),
                        Math.floorMod(x + z, 9) == 0
                                ? LIGHT : FLOOR);
                for (int y = UPPER_WALK_Y; y < roofY; y++)
                {
                    boolean westEntrance = x == minX
                            && Math.abs(z - AXIS_Z) <= 2
                            && y <= UPPER_WALK_Y + 3;
                    if (!edge || westEntrance)
                    {
                        set(level, new BlockPos(x, y, z), AIR);
                    }
                    else
                    {
                        BlockState state =
                                y >= UPPER_WALK_Y + 1
                                        && y <= UPPER_WALK_Y + 3
                                        && Math.floorMod(x + z, 3) != 0
                                        ? GLASS
                                        : y == UPPER_WALK_Y + 4
                                        ? ACCENT : BLACK;
                        set(level, new BlockPos(x, y, z), state);
                    }
                }
                set(level, new BlockPos(x, roofY, z),
                        Math.floorMod(x + z, 7) == 0
                                ? LIGHT : BLACK);
            }
        }

        /*
         * Keep the street threshold obvious and step-free. The lift installer
         * later writes the inner interlocked door at x=126.
         */
        for (int x = minX - 2; x <= AXIS_X - 7; x++)
        {
            for (int z = AXIS_Z - 2; z <= AXIS_Z + 2; z++)
            {
                set(level, new BlockPos(x, floorY, z), FLOOR);
                set(level, new BlockPos(x, UPPER_WALK_Y, z), AIR);
                set(level, new BlockPos(
                        x, UPPER_WALK_Y + 1, z), AIR);
            }
        }
    }

    private static void set(
            ServerLevel level, BlockPos position, BlockState state)
    {
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, UPDATE);
        }
    }
}
