package com.projectseele.physics;

import java.util.function.Predicate;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.chunk.LevelChunkSection;
import net.minecraft.world.phys.AABB;

/**
 * Forge's per-tick fluid scan reads every block inside an entity's box and has
 * no side effects when none of them holds a fluid. For the giant bodies (EVAs,
 * Angels, vehicles, hangar machinery) that is thousands of lookups per tick;
 * the chunk-section palettes can prove the same emptiness in a few dozen.
 */
public final class FluidFreeVolume
{
    private static final Predicate<BlockState> HAS_FLUID = state -> !state.getFluidState().isEmpty();
    /** Below this many blocks the palette proof costs about as much as the scan itself. */
    private static final int MIN_BLOCKS = 32;

    private FluidFreeVolume()
    {
    }

    /** True only when the exact block range Forge would scan contains no fluid state at all. */
    public static boolean proven(Entity entity)
    {
        AABB box = entity.getBoundingBox().deflate(0.001D);
        int minX = Mth.floor(box.minX), maxX = Mth.ceil(box.maxX);
        int minY = Mth.floor(box.minY), maxY = Mth.ceil(box.maxY);
        int minZ = Mth.floor(box.minZ), maxZ = Mth.ceil(box.maxZ);
        if ((long) (maxX - minX) * (maxY - minY) * (maxZ - minZ) < MIN_BLOCKS) return false;
        Level level = entity.level();
        // Positions outside the build height always read as the empty fluid.
        int lowY = Math.max(minY, level.getMinBuildHeight());
        int highY = Math.min(maxY, level.getMaxBuildHeight());
        if (lowY >= highY) return false;
        int lowSection = level.getSectionIndex(lowY);
        int highSection = level.getSectionIndex(highY - 1);
        for (int chunkX = minX >> 4; chunkX <= (maxX - 1) >> 4; chunkX++)
        {
            for (int chunkZ = minZ >> 4; chunkZ <= (maxZ - 1) >> 4; chunkZ++)
            {
                // Never loads: an unloaded chunk leaves the decision to Forge.
                LevelChunk chunk = level.getChunkSource().getChunkNow(chunkX, chunkZ);
                if (chunk == null) return false;
                LevelChunkSection[] sections = chunk.getSections();
                for (int index = lowSection; index <= highSection; index++)
                {
                    LevelChunkSection section = sections[index];
                    // A palette lists every state its section can hold (and may
                    // keep stale ones), so "no entry has a fluid" is a proof.
                    if (!section.hasOnlyAir() && section.maybeHas(HAS_FLUID)) return false;
                }
            }
        }
        return true;
    }
}
