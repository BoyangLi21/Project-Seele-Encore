package com.projectseele.physics;

import net.minecraft.util.Mth;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraft.world.phys.AABB;

/** Conservative dry-volume rejection; unknown chunks always use vanilla. */
public final class FluidSectionPresenceR53
{
    public static boolean empty(Level level, AABB bounds)
    {
        int first = Math.max(0, level.getSectionIndex(Mth.floor(bounds.minY)));
        int last = Math.min(level.getSectionsCount()-1, level.getSectionIndex(Mth.ceil(bounds.maxY)-1));
        for(int x=Mth.floor(bounds.minX)>>4;x<=(Mth.ceil(bounds.maxX)-1)>>4;x++)
        {
            for(int z=Mth.floor(bounds.minZ)>>4;z<=(Mth.ceil(bounds.maxZ)-1)>>4;z++)
            {
                var chunk=level.getChunkSource().getChunk(x,z,ChunkStatus.FULL,false);
                if(chunk==null)return false;
                var sections=chunk.getSections();
                for(int index=first;index<=last;index++)
                    if(!sections[index].hasOnlyAir()
                            &&sections[index].maybeHas(state -> !state.getFluidState().isEmpty()))return false;
            }
        }
        return true;
    }

    private FluidSectionPresenceR53() {}
}
