package com.projectseele.mixin;

import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.chunk.ChunkAccess;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Overwrite;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;

/** Every block read asks this through the level's dimension holder, and it cannot change for a chunk. */
@Mixin(ChunkAccess.class)
public abstract class ChunkAccessMinHeightMixin
{
    @Shadow @Final protected LevelHeightAccessor levelHeightAccessor;
    @Unique private int projectseele$minBuildHeight;
    @Unique private boolean projectseele$minBuildHeightKnown;

    /**
     * @author Project SEELE
     * @reason The same value as before without three indirections per block read.
     * Read lazily because the constructor already needs it while sizing the sections.
     */
    @Overwrite
    public int getMinBuildHeight()
    {
        if(!projectseele$minBuildHeightKnown)
        {
            projectseele$minBuildHeight=levelHeightAccessor.getMinBuildHeight();
            projectseele$minBuildHeightKnown=true;
        }
        return projectseele$minBuildHeight;
    }
}
