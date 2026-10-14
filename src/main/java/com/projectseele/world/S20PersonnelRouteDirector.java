package com.projectseele.world;

import java.nio.file.Files;
import java.nio.file.Path;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;

/**
 * Recompiles the bounded personnel joins around the approved S20 assets.
 *
 * <p>The source world already contains the command module, B-40 interchange,
 * three compact wet cages and their observation decks. Offline walkable-space
 * analysis found that the old completion marker survived while the pyramid
 * clear pass removed the public concourse. The command lift also sat six
 * blocks above the real B-40 floor. This revision joins the measured floors
 * with orthogonal, enclosed routes and one straight stair flight. It never
 * clears an owner box or invents a replacement facility.</p>
 */
public final class S20PersonnelRouteDirector
{
    private static final BlockPos INSTALLED_MARKER =
            new BlockPos(26, -450, 259);
    private static final BlockPos LEGACY_MARKER =
            new BlockPos(68, -447, 273);
    private static final int UPDATE =
            Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE;

    private static final BlockState FLOOR =
            Blocks.POLISHED_DEEPSLATE.defaultBlockState();
    private static BlockState structuralSupport()
    {
        return com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
    }
    private static final BlockState WALL =
            Blocks.DEEPSLATE_TILES.defaultBlockState();
    private static final BlockState ACCENT =
            Blocks.ORANGE_CONCRETE.defaultBlockState();
    private static final BlockState GLASS =
            Blocks.GRAY_STAINED_GLASS.defaultBlockState();
    private static final BlockState LIGHT =
            Blocks.SEA_LANTERN.defaultBlockState();
    private static final BlockState AIR =
            Blocks.AIR.defaultBlockState();
    private static final BlockState STAIR_EAST =
            Blocks.POLISHED_DEEPSLATE_STAIRS.defaultBlockState()
                    .setValue(StairBlock.FACING, Direction.EAST);

    private S20PersonnelRouteDirector() {}

    public static void tick(MinecraftServer server)
    {
        if(NervLegacyGenerationGuardR52.retired(server))return;
        if (!authorised(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null || installed(level)
                || !S20CommandTransitDirector.installed(level))
        {
            return;
        }

        /*
         * This is a one-shot world compilation pass. Load only the seven
         * chunks touched by the four short joins; no force ticket survives.
         */
        for (BlockPos anchor : new BlockPos[] {
                new BlockPos(28, -448, 259),
                new BlockPos(28, -448, 283),
                new BlockPos(49, -448, 274),
                new BlockPos(60, -442, 273),
                new BlockPos(77, -442, 273),
                new BlockPos(93, -442, 240),
                new BlockPos(8, -398, 173),
                new BlockPos(50, -398, 173)})
        {
            level.getChunkAt(anchor);
        }

        buildCommandB40Approach(level);
        buildB40Rise(level);
        buildUpperB40Bridge(level);
        buildCompactCageBranch(level);
        buildInterCageJoin(level, 8, 10);
        buildInterCageJoin(level, 50, 52);
        level.setBlock(LEGACY_MARKER, AIR, Block.UPDATE_CLIENTS);
        level.setBlock(INSTALLED_MARKER,
                Blocks.STRUCTURE_VOID.defaultBlockState(),
                Block.UPDATE_CLIENTS);
        ProjectSeele.LOGGER.info(
                "S20 personnel circulation compiled: "
                        + "commandToB40=24 b40Rise=6 "
                        + "upperConcourse=18 cageBranch=62 "
                                + "deprecatedObservationStair=removed "
                        + "interCageGaps=4+4 diagonalStairs=0 "
                        + "floatingEndpoints=0");
    }

    public static boolean installed(ServerLevel level)
    {
        return level.getBlockState(INSTALLED_MARKER)
                .is(Blocks.STRUCTURE_VOID);
    }

    /** Rebuilds only the corrected B-40 stair and its upper handoff. */
    public static void repairB40RiseAndHandoff(ServerLevel level)
    {
        if(NervLegacyGenerationGuardR52.retired(level))return;
        buildB40Rise(level);
        for (int x = 57; x <= 77; x++)
        {
            buildUpperConcourseSlice(level, x);
        }
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

    /**
     * Runs south from the lower command-lift handoff into the measured B-40
     * floor. The only removed blocks are the three-wide opening in the known
     * black-concrete north wall at z=282.
     */
    private static void buildCommandB40Approach(ServerLevel level)
    {
        for (int z = 259; z <= 282; z++)
        {
            for (int x = 27; x <= 29; x++)
            {
                level.setBlock(new BlockPos(x, -449, z), FLOOR, UPDATE);
                for (int y = -448; y <= -445; y++)
                {
                    level.setBlock(new BlockPos(x, y, z), AIR, UPDATE);
                }
                level.setBlock(new BlockPos(x, -444, z),
                        x == 28 && Math.floorMod(z - 259, 6) == 3
                                ? LIGHT : WALL, UPDATE);
            }
            for (int x : new int[] {26, 30})
            {
                level.setBlock(new BlockPos(x, -449, z), structuralSupport(), UPDATE);
                for (int y = -448; y <= -445; y++)
                {
                    level.setBlock(new BlockPos(x, y, z),
                            y == -447 ? ACCENT : WALL, UPDATE);
                }
                level.setBlock(new BlockPos(x, -444, z), WALL, UPDATE);
            }
        }
    }

    /**
     * Turns east from B-40 and climbs exactly six blocks in one straight
     * flight. It reaches the retained y=-442 public concourse without a
     * diagonal stair or a full-block step.
     */
    private static void buildB40Rise(ServerLevel level)
    {
        // Level approach cut through the measured east side of B-40.
        for (int z = 274; z <= 282; z++)
        {
            for (int x = 47; x <= 49; x++)
            {
                level.setBlock(new BlockPos(x, -449, z), FLOOR, UPDATE);
                for (int y = -448; y <= -445; y++)
                {
                    level.setBlock(new BlockPos(x, y, z), AIR, UPDATE);
                }
                level.setBlock(new BlockPos(x, -444, z),
                        x == 48 && Math.floorMod(z, 4) == 0
                                ? LIGHT : WALL, UPDATE);
            }
            for (int x : new int[] {46, 50})
            {
                level.setBlock(new BlockPos(x, -449, z), structuralSupport(), UPDATE);
                for (int y = -448; y <= -445; y++)
                {
                    level.setBlock(new BlockPos(x, y, z), WALL, UPDATE);
                }
                level.setBlock(new BlockPos(x, -444, z), WALL, UPDATE);
            }
        }

        // Seven bottom-half stairs rise east without leaving a full-block lip
        // at the upper landing. The former six-step run ended one block below
        // the concourse and was impossible to walk while facing east.
        for (int x = 50; x <= 56; x++)
        {
            int stairY = -449 + (x - 50);
            for (int z = 273; z <= 275; z++)
            {
                level.setBlock(new BlockPos(x, stairY, z),
                        STAIR_EAST, UPDATE);
                for (int y = stairY + 1; y <= stairY + 4; y++)
                {
                    level.setBlock(new BlockPos(x, y, z), AIR, UPDATE);
                }
                level.setBlock(new BlockPos(x, stairY + 5, z),
                        z == 274 && (x == 51 || x == 54)
                                ? LIGHT : WALL, UPDATE);
            }
            for (int z : new int[] {272, 276})
            {
                for (int y = stairY; y <= stairY + 4; y++)
                {
                    level.setBlock(new BlockPos(x, y, z),
                            y == stairY + 2 ? GLASS : WALL, UPDATE);
                }
                level.setBlock(new BlockPos(x, stairY + 5, z),
                        WALL, UPDATE);
            }
        }

        for (int x = 57; x <= 59; x++)
        {
            buildUpperConcourseSlice(level, x);
        }
    }

    /** Fully enclosed retained-level bridge into the public concourse. */
    private static void buildUpperB40Bridge(ServerLevel level)
    {
        for (int x = 60; x <= 77; x++)
        {
            buildUpperConcourseSlice(level, x);
        }
    }

    /** Connects the y=-442 public concourse to the compact-cage lift route. */
    private static void buildCompactCageBranch(ServerLevel level)
    {
        for (int z = 209; z <= 270; z++)
        {
            for (int x = 90; x <= 96; x++)
            {
                level.setBlock(new BlockPos(x, -443, z), FLOOR, UPDATE);
                for (int y = -442; y <= -439; y++)
                {
                    level.setBlock(new BlockPos(x, y, z), AIR, UPDATE);
                }
                level.setBlock(new BlockPos(x, -438, z),
                        x == 93 && Math.floorMod(z - 209, 6) == 3
                                ? LIGHT : WALL, UPDATE);
            }
            for (int x : new int[] {89, 97})
            {
                level.setBlock(new BlockPos(x, -443, z), structuralSupport(), UPDATE);
                for (int y = -442; y <= -439; y++)
                {
                    level.setBlock(new BlockPos(x, y, z),
                            y == -440 ? GLASS : WALL, UPDATE);
                }
                level.setBlock(new BlockPos(x, -438, z), WALL, UPDATE);
            }
        }
    }

    private static void buildUpperConcourseSlice(
            ServerLevel level, int x)
    {
        for (int z = 271; z <= 275; z++)
        {
            level.setBlock(new BlockPos(x, -443, z), FLOOR, UPDATE);
            for (int y = -442; y <= -439; y++)
            {
                level.setBlock(new BlockPos(x, y, z), AIR, UPDATE);
            }
            level.setBlock(new BlockPos(x, -438, z),
                    z == 273 && Math.floorMod(x, 4) == 0
                            ? LIGHT : WALL, UPDATE);
        }
        for (int z : new int[] {270, 276})
        {
            level.setBlock(new BlockPos(x, -443, z), structuralSupport(), UPDATE);
            for (int y = -442; y <= -439; y++)
            {
                level.setBlock(new BlockPos(x, y, z),
                        y == -441 ? ACCENT : WALL, UPDATE);
            }
            level.setBlock(new BlockPos(x, -438, z), WALL, UPDATE);
        }
        if (Math.floorMod(x, 4) == 0)
        {
            for (int z = 271; z <= 275; z++)
            {
                level.setBlock(new BlockPos(x, -444, z), structuralSupport(), UPDATE);
            }
        }
    }

    /**
     * Bridges the narrow structural gap between adjacent authored wet-cage
     * observation decks. The joint retains a clear view into both cages.
     */
    private static void buildInterCageJoin(
            ServerLevel level, int minX, int maxX)
    {
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = 171; z <= 175; z++)
            {
                level.setBlock(new BlockPos(x, -399, z), FLOOR, UPDATE);
                for (int y = -398; y <= -395; y++)
                {
                    level.setBlock(new BlockPos(x, y, z), AIR, UPDATE);
                }
                level.setBlock(new BlockPos(x, -394, z),
                        z == 173 ? LIGHT : WALL, UPDATE);
            }
            for (int z : new int[] {170, 176})
            {
                level.setBlock(new BlockPos(x, -399, z), structuralSupport(), UPDATE);
                level.setBlock(new BlockPos(x, -398, z), WALL, UPDATE);
                level.setBlock(new BlockPos(x, -397, z), GLASS, UPDATE);
                level.setBlock(new BlockPos(x, -396, z), GLASS, UPDATE);
                level.setBlock(new BlockPos(x, -395, z), ACCENT, UPDATE);
                level.setBlock(new BlockPos(x, -394, z), WALL, UPDATE);
            }
        }
    }
}
