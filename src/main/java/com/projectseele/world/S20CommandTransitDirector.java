package com.projectseele.world;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;

/**
 * Extends the authored S20 command-room rear passage to its physical lift.
 *
 * <p>The original NBT remains the visual and spatial authority. The measured
 * rear route passes through the birch door and ends on a three-block-wide
 * white floor at world z=302. This director fills only the three missing
 * centreline slices at z=259..261 and terminates at the independently
 * interlocked physical lift landing. It does not clear the NBT, build a long
 * corridor or create any display surface.</p>
 */
public final class S20CommandTransitDirector
{
    /** Direct placement measured from the blocks in the reference save. */
    private static final BlockPos COMMAND_TRANSFORM_ORIGIN =
            new BlockPos(2, -465, 223);

    /*
     * These local coordinates are read directly from nerv_command_left.nbt.
     * oldWorld = (2+localX, -465+localY, 263+localZ).
     */
    private static final BlockPos REAR_DOOR_LOWER =
            oldWorld(new BlockPos(26, 59, 49));
    private static final BlockPos REAR_DOOR_UPPER =
            oldWorld(new BlockPos(26, 60, 49));
    private static final List<BlockPos> ENDPOINT_FLOOR = List.of(
            oldWorld(new BlockPos(25, 58, 39)),
            oldWorld(new BlockPos(26, 58, 39)),
            oldWorld(new BlockPos(27, 58, 39)));
    private static final BlockPos ENDPOINT_LEFT_JAMB =
            oldWorld(new BlockPos(24, 58, 38));
    private static final BlockPos ENDPOINT_RIGHT_JAMB =
            oldWorld(new BlockPos(28, 58, 38));

    /*
     * The marker is below the new floor. It is outside the walkable volume
     * and was verified as air in the source NBT.
     */
    private static final BlockPos INSTALLED_MARKER =
            new BlockPos(32, -411, 259);

    private static final int NARROW_WEST_X = 26;
    private static final int NARROW_EAST_X = 30;
    private static final int FLOOR_Y = -407;
    private static final int SUPPORT_Y = -409;
    private static final int CEILING_Y = -403;
    private static final int NORTH_Z = 259;
    private static final int SOUTH_Z = 261;

    /*
     * Conservative world-space bounds around the two exact connected screen
     * components. The transit is far north of both; this assertion prevents a
     * future coordinate edit from silently reaching either measured mask.
     */
    private static final Box AMBER_SCREEN_GUARD =
            new Box(20, -431, 315, 36, -401, 331);
    private static final Box ORANGE_SCREEN_GUARD =
            new Box(20, -435, 313, 36, -419, 351);

    private static final BlockState FLOOR =
            Blocks.WHITE_CONCRETE.defaultBlockState();
    private static final BlockState WALL =
            Blocks.SMOOTH_STONE.defaultBlockState();
    private static final BlockState ACCENT =
            Blocks.BLACK_CONCRETE.defaultBlockState();
    private static final BlockState CEILING =
            Blocks.IRON_BLOCK.defaultBlockState();
    private static final BlockState LIGHT =
            Blocks.VERDANT_FROGLIGHT.defaultBlockState();
    private static final List<Write> WRITES = buildWrites();
    private static final List<BlockPos> REQUIRED_AIR =
            buildRequiredAir();

    private static boolean rejectionLogged;

    private S20CommandTransitDirector() {}

    /**
     * Runs only in the marker-authorised S20 rebuild and installs at most one
     * vestibule. Chunk loading remains player-driven.
     */
    public static void tick(MinecraftServer server)
    {
        if(NervLegacyGenerationGuardR52.retired(server))return;
        if (!isAuthorisedS20MarkerWorld(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null || installed(level))
        {
            return;
        }
        if (!level.hasChunkAt(REAR_DOOR_LOWER)
                || !level.hasChunkAt(INSTALLED_MARKER))
        {
            return;
        }
        /*
         * Presentation installation proves that the private measured NBT was
         * recognised before this secondary, non-visual connector may write.
         */
        if (!S20CommandPresentationDirector.presentationInstalled(level))
        {
            return;
        }
        install(level);
    }

    private static boolean isAuthorisedS20MarkerWorld(
            MinecraftServer server)
    {
        if (!FacilityWorldPolicy.isS20Rebuild(server))
        {
            return false;
        }
        Path root = server.getWorldPath(LevelResource.ROOT);
        return Files.isRegularFile(
                root.resolve(FacilityWorldPolicy.S20_MARKER));
    }

    public static boolean installed(ServerLevel level)
    {
        return level.getBlockState(INSTALLED_MARKER)
                .is(Blocks.STRUCTURE_VOID);
    }

    private static void install(ServerLevel level)
    {
        if (!authoredFingerprintMatches(level)
                || !targetVolumeIsSafe(level))
        {
            return;
        }
        for (Write write : WRITES)
        {
            level.setBlock(write.position(), write.state(),
                    Block.UPDATE_ALL);
        }
        level.setBlock(INSTALLED_MARKER,
                Blocks.STRUCTURE_VOID.defaultBlockState(),
                Block.UPDATE_CLIENTS);
        ProjectSeele.LOGGER.info(
                "S20 command rear lift vestibule installed: "
                        + "world=x[{},{}] y[{},{}] z[{},{}] "
                        + "walkable=3-wide "
                        + "liftSeal=independent authoredWrites=0 "
                        + "screensWritten=0 style=source-nbt",
                NARROW_WEST_X, NARROW_EAST_X, SUPPORT_Y, CEILING_Y,
                NORTH_Z, SOUTH_Z);
    }

    /**
     * Rejects renamed or contaminated rooms. No repair is attempted when one
     * of the measured authored anchors is missing.
     */
    private static boolean authoredFingerprintMatches(ServerLevel level)
    {
        if (!level.getBlockState(REAR_DOOR_LOWER)
                .is(Blocks.BIRCH_DOOR)
                || !level.getBlockState(REAR_DOOR_UPPER)
                .is(Blocks.BIRCH_DOOR))
        {
            reject("rear birch door fingerprint is absent");
            return false;
        }
        for (BlockPos floor : ENDPOINT_FLOOR)
        {
            if (!level.getBlockState(floor).is(Blocks.WHITE_CONCRETE))
            {
                reject("authored rear floor endpoint is absent at "
                        + floor);
                return false;
            }
        }
        if (!level.getBlockState(ENDPOINT_LEFT_JAMB)
                .is(Blocks.SMOOTH_STONE)
                || !level.getBlockState(ENDPOINT_RIGHT_JAMB)
                .is(Blocks.SMOOTH_STONE))
        {
            reject("authored rear endpoint jambs are absent");
            return false;
        }
        return true;
    }

    /**
     * Every planned block was air in the measured NBT. Existing exact target
     * states are accepted only to finish safely after an interrupted write.
     * Walkable headroom must remain air and is never cleared.
     */
    private static boolean targetVolumeIsSafe(ServerLevel level)
    {
        for (Write write : WRITES)
        {
            BlockState current = level.getBlockState(write.position());
            if (!current.isAir() && !current.equals(write.state()))
            {
                reject("target is not authored air at "
                        + write.position() + ": " + current);
                return false;
            }
        }
        for (BlockPos position : REQUIRED_AIR)
        {
            if (!level.getBlockState(position).isAir())
            {
                reject("walkable headroom is obstructed at "
                        + position);
                return false;
            }
        }
        BlockState marker = level.getBlockState(INSTALLED_MARKER);
        if (!marker.isAir()
                && !marker.is(Blocks.STRUCTURE_VOID))
        {
            reject("installation marker is obstructed");
            return false;
        }
        return true;
    }

    private static List<Write> buildWrites()
    {
        List<Write> writes = new ArrayList<>();
        for (int z = NORTH_Z; z <= SOUTH_Z; z++)
        {
            int westWall = NARROW_WEST_X;
            int eastWall = NARROW_EAST_X;
            int centre = (westWall + eastWall) / 2;

            /*
             * Reproduce the measured source cross-section exactly: smooth
             * stone / black / smooth stone below the walking plane, a white
             * floor, and smooth / black / smooth side bands above it.
             */
            add(writes, westWall, SUPPORT_Y, z, WALL);
            add(writes, eastWall, SUPPORT_Y, z, WALL);
            add(writes, westWall, SUPPORT_Y + 1, z, ACCENT);
            add(writes, eastWall, SUPPORT_Y + 1, z, ACCENT);
            add(writes, westWall, FLOOR_Y, z, WALL);
            add(writes, eastWall, FLOOR_Y, z, WALL);
            for (int x = westWall + 1; x < eastWall; x++)
            {
                add(writes, x, FLOOR_Y, z, FLOOR);
            }
            for (int y = FLOOR_Y + 1; y <= -404; y++)
            {
                BlockState state = y == -405 ? ACCENT : WALL;
                add(writes, westWall, y, z, state);
                add(writes, eastWall, y, z, state);
            }
            for (int x = westWall + 1; x < eastWall; x++)
            {
                add(writes, x, CEILING_Y, z,
                        x == centre && Math.floorMod(z, 2) == 1
                                ? LIGHT : CEILING);
            }
        }
        return List.copyOf(writes);
    }

    private static List<BlockPos> buildRequiredAir()
    {
        List<BlockPos> positions = new ArrayList<>();
        /*
         * The source passage has three clear blocks between its floor and
         * ceiling. The north section meets the physical landing threshold at
         * z=259; that landing owns the pressure doors and interlock.
         */
        for (int z = NORTH_Z; z <= SOUTH_Z; z++)
        {
            int westWall = NARROW_WEST_X;
            int eastWall = NARROW_EAST_X;
            for (int x = westWall + 1; x < eastWall; x++)
            {
                for (int y = FLOOR_Y + 1; y < CEILING_Y; y++)
                {
                    positions.add(new BlockPos(x, y, z));
                }
            }
        }
        return List.copyOf(positions);
    }

    private static void add(List<Write> writes, int x, int y, int z,
                            BlockState state)
    {
        BlockPos position = new BlockPos(x, y, z);
        if (AMBER_SCREEN_GUARD.contains(position)
                || ORANGE_SCREEN_GUARD.contains(position))
        {
            throw new IllegalStateException(
                    "S20 transit design overlaps an authored screen at "
                            + position);
        }
        writes.add(new Write(position, state));
    }

    private static BlockPos oldWorld(BlockPos local)
    {
        return COMMAND_TRANSFORM_ORIGIN.offset(
                local.getX(), local.getY(), local.getZ());
    }

    private static void reject(String reason)
    {
        if (!rejectionLogged)
        {
            rejectionLogged = true;
            ProjectSeele.LOGGER.error(
                    "S20 command rear vestibule rejected: {}", reason);
        }
    }

    private record Write(BlockPos position, BlockState state) {}

    private record Box(int minX, int minY, int minZ,
                       int maxX, int maxY, int maxZ)
    {
        boolean contains(BlockPos position)
        {
            return position.getX() >= this.minX
                    && position.getX() <= this.maxX
                    && position.getY() >= this.minY
                    && position.getY() <= this.maxY
                    && position.getZ() >= this.minZ
                    && position.getZ() <= this.maxZ;
        }
    }
}
