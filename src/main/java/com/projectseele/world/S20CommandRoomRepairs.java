package com.projectseele.world;

import java.util.EnumSet;
import java.util.Set;

import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;

/**
 * Explicitly enumerated command-room repairs for the frozen R28 save.
 *
 * <p>R28 is a human-approved world: its blocks outrank any generator.  Every
 * write in this class therefore names one coordinate or one measured plane, is
 * applied at most once per server run, and only fires when the cell still
 * holds one of the states that were actually measured there.  If a human has
 * since changed a cell, this class leaves it alone instead of re-imposing its
 * own idea of the room.</p>
 */
public final class S20CommandRoomRepairs
{
    /**
     * The chair the user pointed at as the approved look.  Its real block
     * states are the template - nothing here invents a chair palette.  The
     * template faces +Z; every other seat is rotated to its own measured
     * facing rather than assuming the same one.
     */
    private static final BlockPos REFERENCE_SEAT =
            new BlockPos(28, -409, 288);
    private static final BlockPos REFERENCE_ARM =
            new BlockPos(27, -409, 288);
    private static final BlockPos REFERENCE_BANNER =
            new BlockPos(28, -408, 288);

    /**
     * Every seat in the command room, found by sweeping the whole authored
     * volume for the two seat blocks the room actually uses.  There are three
     * pods on the operator floor and ten more around the lower screen apron -
     * the first pass only knew about seven of them.
     *
     * <p>The Ikari chair at {@code (28,-406,277)} is deliberately absent: the
     * user keeps that one as the red stool.</p>
     */
    private static final BlockPos[] SEAT_CELLS = {
            new BlockPos(20, -422, 291), new BlockPos(22, -422, 292),
            new BlockPos(24, -422, 291), new BlockPos(32, -422, 291),
            new BlockPos(34, -422, 292), new BlockPos(36, -422, 291),
            new BlockPos(26, -424, 298), new BlockPos(30, -424, 298),
            new BlockPos(28, -424, 299),
            new BlockPos(9, -429, 332), new BlockPos(12, -429, 334),
            new BlockPos(15, -429, 328), new BlockPos(15, -429, 332),
            new BlockPos(17, -429, 330), new BlockPos(39, -429, 330),
            new BlockPos(41, -429, 328), new BlockPos(41, -429, 332),
            new BlockPos(44, -429, 334), new BlockPos(47, -429, 332)
    };

    /** Measured seat blocks: the authored copper slabs and earlier stools. */
    private static final Set<String> REPLACEABLE_SEATS = Set.of(
            "another_furniture:yellow_stool",
            "minecraft:waxed_exposed_cut_copper_slab");
    /** Measured armrests: jungle signs on the pods, bamboo on the template. */
    private static final Set<String> REPLACEABLE_ARMS = Set.of(
            "minecraft:air",
            "minecraft:jungle_wall_sign",
            "minecraft:bamboo_wall_sign");
    /** Measured upholstery banners, plus empty cells above bare seats. */
    private static final Set<String> REPLACEABLE_BANNERS = Set.of(
            "minecraft:air",
            "minecraft:light_gray_wall_banner",
            "minecraft:yellow_wall_banner");
    /** The redstone-sensitive backrest panels being retired. */
    private static final Set<String> REPLACEABLE_BACKS = Set.of(
            "minecraft:air",
            "minecraft:iron_trapdoor",
            "projectseele:command_seat_back");
    /** Blocks that identify which side of a seat the backrest is on. */
    private static final Set<String> BACKREST_MARKERS = Set.of(
            "minecraft:iron_trapdoor",
            "projectseele:command_seat_back");

    /**
     * Flat sections of the command-room shell that are missing whole bands.
     *
     * <p>Both side walls are solid out to z=351 at every height, then stop
     * dead over z 352..362 for y -419..-414 and again for y -402..-395; the
     * rear wall keeps a chevron at those same two levels but is open at both
     * ends.  Sampling outward through the openings finds nothing but empty
     * pyramid void, so they are holes in the shell rather than windows.</p>
     *
     * <p>{@code scanMin/scanMax} bound the search for the material to use:
     * each filled cell copies the nearest solid block in its own row, so the
     * existing horizontal banding continues instead of a flat grey patch.</p>
     */
    private record SealPlane(Direction.Axis axis, int constant,
                             int uMin, int uMax, int yMin, int yMax,
                             int scanMin, int scanMax) {}

    private static final SealPlane[] SEAL_PLANES = {
            new SealPlane(Direction.Axis.X, 6, 352, 362, -419, -395, 330, 366),
            new SealPlane(Direction.Axis.X, 50, 352, 362, -419, -395, 330, 366),
            new SealPlane(Direction.Axis.Z, 362, 6, 50, -419, -391, 0, 56)
    };

    private static boolean seatsApplied;
    private static final boolean[] PLANE_APPLIED =
            new boolean[SEAL_PLANES.length];

    private S20CommandRoomRepairs() {}

    public static void tick(MinecraftServer server)
    {
        if (NervLegacyGenerationGuardR52.retired(server)) return;
        if (!FacilityWorldPolicy.isS20Rebuild(server)
                || server.getTickCount() % 40 != 0 || allDone())
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return;
        }
        /*
         * Every repair is gated on its own chunks.  Chunk residency is the
         * trap here: a pass that runs while its target chunks are still
         * unloaded reads air everywhere, writes nothing and reports success.
         */
        if (!seatsApplied && level.hasChunkAt(REFERENCE_SEAT)
                && loaded(level, SEAT_CELLS))
        {
            seatsApplied = true;
            ProjectSeele.LOGGER.info(
                    "S20 command seats standardised: {} cells written",
                    applySeatStandard(level));
        }
        for (int index = 0; index < SEAL_PLANES.length; index++)
        {
            SealPlane plane = SEAL_PLANES[index];
            if (PLANE_APPLIED[index] || !planeLoaded(level, plane))
            {
                continue;
            }
            PLANE_APPLIED[index] = true;
            ProjectSeele.LOGGER.info(
                    "S20 shell sealed on {}={}: {} cells written",
                    plane.axis(), plane.constant(), sealPlane(level, plane));
        }
    }

    private static boolean allDone()
    {
        if (!seatsApplied)
        {
            return false;
        }
        for (boolean done : PLANE_APPLIED)
        {
            if (!done)
            {
                return false;
            }
        }
        return true;
    }

    private static boolean loaded(ServerLevel level, BlockPos[] cells)
    {
        for (BlockPos cell : cells)
        {
            if (!level.hasChunkAt(cell))
            {
                return false;
            }
        }
        return true;
    }

    private static boolean planeLoaded(ServerLevel level, SealPlane plane)
    {
        return level.hasChunkAt(planeCell(plane, plane.scanMin(), plane.yMin()))
                && level.hasChunkAt(
                        planeCell(plane, plane.scanMax(), plane.yMin()));
    }

    private static BlockPos planeCell(SealPlane plane, int u, int y)
    {
        return plane.axis() == Direction.Axis.X
                ? new BlockPos(plane.constant(), y, u)
                : new BlockPos(u, y, plane.constant());
    }

    // ------------------------------------------------------------------ seats

    private static int applySeatStandard(ServerLevel level)
    {
        if(java.nio.file.Files.isRegularFile(level.getServer().getWorldPath(
                net.minecraft.world.level.storage.LevelResource.ROOT).resolve("facility_chairs_r26.json")))return 0;
        BlockState seat = level.getBlockState(REFERENCE_SEAT);
        BlockState arm = level.getBlockState(REFERENCE_ARM);
        BlockState banner = level.getBlockState(REFERENCE_BANNER);
        if (seat.isAir())
        {
            ProjectSeele.LOGGER.warn(
                    "S20 seat template missing at {}; chairs left untouched",
                    REFERENCE_SEAT);
            return 0;
        }
        BlockState back = ModBlocks.COMMAND_SEAT_BACK.get().defaultBlockState();

        int written = 0;
        for (BlockPos cell : SEAT_CELLS)
        {
            Direction facing = seatFacing(level, cell);
            if (facing == null)
            {
                ProjectSeele.LOGGER.warn(
                        "S20 seat at {} has no single backrest side; skipped",
                        cell);
                continue;
            }
            BlockPos backCell = cell.relative(facing.getOpposite());
            written += place(level, cell, seat, REPLACEABLE_SEATS);
            // On the template each armrest sign faces the side it sits on and
            // the banner faces the same way as the occupant.
            for (Direction side : EnumSet.of(facing.getClockWise(),
                    facing.getCounterClockWise()))
            {
                written += place(level, cell.relative(side),
                        aim(arm, side), REPLACEABLE_ARMS);
            }
            written += place(level, cell.above(), aim(banner, facing),
                    REPLACEABLE_BANNERS);
            written += place(level, backCell, aim(back, facing)
                            .setValue(BlockStateProperties.DOUBLE_BLOCK_HALF,
                                    DoubleBlockHalf.LOWER),
                    REPLACEABLE_BACKS);
            written += place(level, backCell.above(), aim(back, facing)
                            .setValue(BlockStateProperties.DOUBLE_BLOCK_HALF,
                                    DoubleBlockHalf.UPPER),
                    REPLACEABLE_BACKS);
        }
        return written;
    }

    /**
     * Reads which way a seat looks from the side its backrest is on, rather
     * than assuming every chair in the room faces the screens.  The apron
     * seats face east and west.  Anything without exactly one backrest side is
     * not recognisably one of these chairs and is left alone.
     */
    private static Direction seatFacing(ServerLevel level, BlockPos cell)
    {
        Direction found = null;
        for (Direction side : Direction.Plane.HORIZONTAL)
        {
            String id = BuiltInRegistries.BLOCK.getKey(
                    level.getBlockState(cell.relative(side)).getBlock())
                    .toString();
            if (!BACKREST_MARKERS.contains(id))
            {
                continue;
            }
            if (found != null)
            {
                return null;
            }
            found = side;
        }
        return found == null ? null : found.getOpposite();
    }

    /** Points a template state at {@code facing} if it has a facing at all. */
    private static BlockState aim(BlockState template, Direction facing)
    {
        return template.hasProperty(HorizontalDirectionalBlock.FACING)
                ? template.setValue(
                        HorizontalDirectionalBlock.FACING, facing)
                : template;
    }

    // ------------------------------------------------------------------ shell

    private static int sealPlane(ServerLevel level, SealPlane plane)
    {
        int written = 0;
        for (int y = plane.yMin(); y <= plane.yMax(); y++)
        {
            for (int u = plane.uMin(); u <= plane.uMax(); u++)
            {
                BlockPos cell = planeCell(plane, u, y);
                if (!level.getBlockState(cell).isAir())
                {
                    continue;
                }
                BlockState material = rowMaterial(level, plane, u, y);
                if (material == null)
                {
                    continue;
                }
                level.setBlock(cell, material, Block.UPDATE_CLIENTS);
                written++;
            }
        }
        return written;
    }

    /**
     * Nearest solid block in the same row of the same plane.  The shell is
     * built as horizontal bands of one material each, so continuing the row is
     * what makes a patch invisible; a single hard-coded fill material would
     * stripe across four different courses.
     */
    private static BlockState rowMaterial(ServerLevel level, SealPlane plane,
                                          int u, int y)
    {
        int reach = plane.scanMax() - plane.scanMin();
        for (int distance = 1; distance <= reach; distance++)
        {
            for (int side = 0; side < 2; side++)
            {
                int probe = side == 0 ? u - distance : u + distance;
                if (probe < plane.scanMin() || probe > plane.scanMax())
                {
                    continue;
                }
                BlockState state = level.getBlockState(
                        planeCell(plane, probe, y));
                if (!state.isAir())
                {
                    return state;
                }
            }
        }
        return null;
    }

    /**
     * Writes {@code target} only when the cell still holds one of the states
     * measured there.  Anything else is a later human edit and wins.
     */
    private static int place(ServerLevel level, BlockPos cell,
                             BlockState target, Set<String> allowed)
    {
        BlockState current = level.getBlockState(cell);
        if (current == target)
        {
            return 0;
        }
        String id = BuiltInRegistries.BLOCK.getKey(current.getBlock())
                .toString();
        if (!allowed.contains(id))
        {
            return 0;
        }
        level.setBlock(cell, target, Block.UPDATE_CLIENTS);
        return 1;
    }
}
