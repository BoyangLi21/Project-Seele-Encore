package com.projectseele.physics;

import java.util.Map;
import java.util.concurrent.atomic.LongAdder;
import java.util.function.Predicate;
import java.util.stream.Stream;
import com.projectseele.ProjectSeele;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraft.world.phys.AABB;

/** Rejects a giant's empty fire scan using the current section palettes. */
public final class GiantMoveBlockQueryR53
{
    private static final boolean VERIFY=Boolean.getBoolean("projectseele.verifyGiantMoveQueryR53");
    private static final LongAdder queries=new LongAdder(),skipped=new LongAdder(),verified=new LongAdder();
    private static volatile boolean rejected;

    public static boolean noPaletteMatch(Level level,AABB bounds,Predicate<BlockState> predicate)
    {
        // Outside the build height and unavailable chunks retain the original
        // loaded-volume semantics. Never load a chunk to answer this query.
        if(!Double.isFinite(bounds.minX)||!Double.isFinite(bounds.maxX)
                ||!Double.isFinite(bounds.minY)||!Double.isFinite(bounds.maxY)
                ||!Double.isFinite(bounds.minZ)||!Double.isFinite(bounds.maxZ)
                ||bounds.minY<level.getMinBuildHeight()||bounds.maxY>=level.getMaxBuildHeight())
            return false;
        int first=level.getSectionIndex(Mth.floor(bounds.minY));
        int last=level.getSectionIndex(Mth.floor(bounds.maxY));
        for(int x=Mth.floor(bounds.minX)>>4;x<=Mth.floor(bounds.maxX)>>4;x++)
        {
            for(int z=Mth.floor(bounds.minZ)>>4;z<=Mth.floor(bounds.maxZ)>>4;z++)
            {
                var chunk=level.getChunkSource().getChunk(x,z,ChunkStatus.FULL,false);
                if(chunk==null)return false;
                var sections=chunk.getSections();
                for(int y=first;y<=last;y++)
                    if(sections[y].maybeHas(predicate))return false;
            }
        }
        return true;
    }

    public static boolean noneMatch(Entity entity,Stream<BlockState> original,Predicate<BlockState> predicate)
    {
        queries.increment();
        if(rejected||!noPaletteMatch(entity.level(),entity.getBoundingBox().deflate(1e-6),predicate))
            return original.noneMatch(predicate);
        skipped.increment();
        if(VERIFY&&skipped.sum()%64==0)
        {
            boolean expected=original.noneMatch(predicate);
            verified.increment();
            if(!expected)
            {
                rejected=true;
                ProjectSeele.LOGGER.error("Giant move palette rejection disagreed with native block stream; retaining native queries");
            }
            return expected;
        }
        original.close();
        return true;
    }

    public static Map<String,Object> diagnostics()
    {
        return Map.of("queries",queries.sum(),"palette_rejections",skipped.sum(),
                "native_comparisons",verified.sum(),"rejected",rejected);
    }

    private GiantMoveBlockQueryR53() {}
}
