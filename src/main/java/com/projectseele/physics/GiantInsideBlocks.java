package com.projectseele.physics;

import com.projectseele.ProjectSeele;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import net.minecraft.CrashReport;
import net.minecraft.CrashReportCategory;
import net.minecraft.ReportedException;
import net.minecraft.core.BlockPos;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.chunk.LevelChunkSection;
import net.minecraft.world.phys.AABB;

/**
 * {@code Entity.checkInsideBlocks} for the giants: the same callbacks in the same order, read from the chunk sections.
 *
 * Vanilla asks the level for the block at every cell of the bounding box, every time the entity moves. An Angel's
 * box is twenty thousand cells and Unit-01's two thousand, nearly all of them air, and each question goes through
 * the chunk cache. Here the chunks are fetched once, a section with nothing but air is passed over a run at a time
 * (vanilla reads plain air from such a section too), and the three vanilla air blocks get no callback because theirs
 * does nothing. Every other block, a modded air block included, gets its callbacks as before, in x, y, z order.
 *
 * The first boxes are also walked the vanilla way and compared; a difference turns this off for the session.
 */
public final class GiantInsideBlocks
{
    /** {@code Entity.onInsideBlock}, which is protected; the mixin on Entity implements this. */
    public interface Host
    {
        void projectseele$insideBlock(BlockState state);
    }

    private interface Visitor
    {
        void block(BlockState state, BlockPos.MutableBlockPos at);
    }

    /** Smaller boxes stay on the vanilla path: there is nothing to gain below a few hundred cells. */
    private static final double GIANT_VOLUME = 512;
    private static final int UNTESTED = 0, TRUSTED = 1, REJECTED = -1;
    /** Boxes that must match before the vanilla walk is dropped, and blocks they must have shown between them. */
    private static final int COMPARED_BOXES = 40, COMPARED_BLOCKS = 200;
    /** Giants that touch nothing never show that many blocks; this many matching boxes are enough then. */
    private static final int COMPARED_BOXES_BARE = 2000;
    private static final long MIX = 0x9E3779B97F4A7C15L;
    private static volatile int state = UNTESTED;
    private static final AtomicInteger matched = new AtomicInteger();
    private static final AtomicLong matchedBlocks = new AtomicLong(), matchedCells = new AtomicLong();
    private static final ClassValue<Boolean> OURS = new ClassValue<>()
    {
        @Override protected Boolean computeValue(Class<?> type) { return type.getName().startsWith("com.projectseele."); }
    };

    private GiantInsideBlocks() {}

    /** Only this mod's own large entities: nobody else's entity has its block callbacks touched. */
    public static boolean applies(Entity entity)
    {
        if (state == REJECTED) return false;
        AABB box = entity.getBoundingBox();
        return (box.maxX - box.minX) * (box.maxY - box.minY) * (box.maxZ - box.minZ) >= GIANT_VOLUME && OURS.get(entity.getClass());
    }

    /** True when the box has been dealt with; false leaves it to vanilla. */
    public static boolean scan(Entity entity, Host host)
    {
        Level level = entity.level();
        if (level.isDebug()) return false;
        AABB box = entity.getBoundingBox();
        BlockPos first = BlockPos.containing(box.minX + 1.0E-7D, box.minY + 1.0E-7D, box.minZ + 1.0E-7D);
        BlockPos last = BlockPos.containing(box.maxX - 1.0E-7D, box.maxY - 1.0E-7D, box.maxZ - 1.0E-7D);
        // Vanilla does nothing either when a chunk under the box is not loaded.
        if (!level.hasChunksAt(first, last)) return true;
        int firstChunkX = first.getX() >> 4, firstChunkZ = first.getZ() >> 4;
        int columns = (last.getX() >> 4) - firstChunkX + 1, rows = (last.getZ() >> 4) - firstChunkZ + 1;
        LevelChunkSection[][] sections = new LevelChunkSection[columns * rows][];
        for (int x = 0; x < columns; x++) for (int z = 0; z < rows; z++)
        {
            if (!(level.getChunkSource().getChunk(firstChunkX + x, firstChunkZ + z, ChunkStatus.FULL, false) instanceof LevelChunk chunk)) return false;
            sections[x * rows + z] = chunk.getSections();
        }
        // Outside the build height vanilla reads void air, which gets no callback here.
        int minY = Math.max(first.getY(), level.getMinBuildHeight()), maxY = Math.min(last.getY(), level.getMaxBuildHeight() - 1);
        if (minY > maxY) return true;
        if (state == UNTESTED && !compare(level, first, last, minY, maxY, sections, firstChunkX, firstChunkZ, rows)) return false;
        walk(level, first, last, minY, maxY, sections, firstChunkX, firstChunkZ, rows, (found, at) ->
        {
            try
            {
                found.entityInside(level, at, entity);
                host.projectseele$insideBlock(found);
            }
            catch (Throwable failure)
            {
                CrashReport report = CrashReport.forThrowable(failure, "Colliding entity with block");
                CrashReportCategory category = report.addCategory("Block being collided with");
                CrashReportCategory.populateBlockDetails(category, level, at, found);
                throw new ReportedException(report);
            }
        });
        return true;
    }

    private static void walk(Level level, BlockPos first, BlockPos last, int minY, int maxY, LevelChunkSection[][] sections,
                             int firstChunkX, int firstChunkZ, int rows, Visitor visitor)
    {
        BlockPos.MutableBlockPos at = new BlockPos.MutableBlockPos();
        int firstZ = first.getZ(), lastZ = last.getZ();
        for (int x = first.getX(); x <= last.getX(); x++)
        {
            int column = ((x >> 4) - firstChunkX) * rows - firstChunkZ;
            for (int y = minY; y <= maxY; y++)
            {
                int index = level.getSectionIndex(y);
                for (int z = firstZ; z <= lastZ;)
                {
                    int end = Math.min(lastZ, z | 15);
                    // Read again for every run: a callback may have changed any section.
                    LevelChunkSection section = sections[column + (z >> 4)][index];
                    if (section.hasOnlyAir()) { z = end + 1; continue; }
                    for (; z <= end; z++)
                    {
                        BlockState found = section.getBlockState(x & 15, y & 15, z & 15);
                        if (found.is(Blocks.AIR) || found.is(Blocks.CAVE_AIR) || found.is(Blocks.VOID_AIR)) continue;
                        visitor.block(found, at.set(x, y, z));
                    }
                }
            }
        }
    }

    /** Both walks without the callbacks: the blocks that would get one, and their order, must be the same. */
    private static boolean compare(Level level, BlockPos first, BlockPos last, int minY, int maxY, LevelChunkSection[][] sections,
                                   int firstChunkX, int firstChunkZ, int rows)
    {
        long[] vanilla = new long[2], here = new long[2];
        BlockPos.MutableBlockPos at = new BlockPos.MutableBlockPos();
        for (int x = first.getX(); x <= last.getX(); x++)
            for (int y = first.getY(); y <= last.getY(); y++)
                for (int z = first.getZ(); z <= last.getZ(); z++)
                {
                    BlockState found = level.getBlockState(at.set(x, y, z));
                    if (found.is(Blocks.AIR) || found.is(Blocks.CAVE_AIR) || found.is(Blocks.VOID_AIR)) continue;
                    vanilla[0] = (vanilla[0] * MIX + at.asLong()) * MIX + System.identityHashCode(found);
                    vanilla[1]++;
                }
        walk(level, first, last, minY, maxY, sections, firstChunkX, firstChunkZ, rows, (found, where) ->
        {
            here[0] = (here[0] * MIX + where.asLong()) * MIX + System.identityHashCode(found);
            here[1]++;
        });
        if (vanilla[0] != here[0] || vanilla[1] != here[1])
        {
            if (state != REJECTED)
            {
                state = REJECTED;
                ProjectSeele.LOGGER.warn("Giant block scan disabled: {} blocks inside the box {} to {} against {} from the vanilla walk",
                        here[1], first.toShortString(), last.toShortString(), vanilla[1]);
            }
            return false;
        }
        long cells = matchedCells.addAndGet((long) (last.getX() - first.getX() + 1) * (last.getY() - first.getY() + 1) * (last.getZ() - first.getZ() + 1));
        long blocks = matchedBlocks.addAndGet(vanilla[1]);
        int boxes = matched.incrementAndGet();
        if ((boxes >= COMPARED_BOXES && blocks >= COMPARED_BLOCKS || boxes >= COMPARED_BOXES_BARE) && state == UNTESTED)
        {
            state = TRUSTED;
            ProjectSeele.LOGGER.info("Giant block scan verified over {} boxes, {} cells and {} blocks inside them", boxes, cells, blocks);
        }
        return true;
    }
}
