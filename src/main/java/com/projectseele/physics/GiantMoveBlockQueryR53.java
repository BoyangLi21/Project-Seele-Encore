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
        return Boolean.TRUE.equals(sectionNoneMatch(level,bounds,predicate,false));
    }

    private static Boolean sectionNoneMatch(Level level,AABB bounds,Predicate<BlockState> predicate,boolean inspectMatches)
    {
        if(!Double.isFinite(bounds.minX)||!Double.isFinite(bounds.maxX)
                ||!Double.isFinite(bounds.minY)||!Double.isFinite(bounds.maxY)
                ||!Double.isFinite(bounds.minZ)||!Double.isFinite(bounds.maxZ))return null;
        int minX=Mth.floor(bounds.minX),maxX=Mth.floor(bounds.maxX);
        int minY=Mth.floor(bounds.minY),maxY=Mth.floor(bounds.maxY);
        int minZ=Mth.floor(bounds.minZ),maxZ=Mth.floor(bounds.maxZ);
        var absent=net.minecraft.world.level.block.Blocks.VOID_AIR.defaultBlockState();
        if((minY<level.getMinBuildHeight()||maxY>=level.getMaxBuildHeight())&&predicate.test(absent))return false;
        minY=Math.max(minY,level.getMinBuildHeight());maxY=Math.min(maxY,level.getMaxBuildHeight()-1);
        if(minY>maxY)return true;
        int first=level.getSectionIndex(minY),last=level.getSectionIndex(maxY);
        for(int x=minX>>4;x<=maxX>>4;x++)for(int z=minZ>>4;z<=maxZ>>4;z++)
        {
            var chunk=level.getChunkSource().getChunk(x,z,ChunkStatus.FULL,false);
            // ClientLevel.hasChunk always returns true, but its unloaded read
            // goes through EmptyLevelChunk and returns VOID_AIR. Requesting
            // false here must not turn that cheap empty read into a full scan.
            if(chunk==null)
            {
                if(!level.isClientSide)return null;
                if(predicate.test(absent))return false;
                continue;
            }
            if(chunk instanceof net.minecraft.world.level.chunk.EmptyLevelChunk)
            {if(predicate.test(absent))return false;continue;}
            var sections=chunk.getSections();
            for(int index=first;index<=last;index++)
            {
                var section=sections[index];if(!section.maybeHas(predicate))continue;
                if(!inspectMatches)return false;
                int bottom=level.getSectionYFromSectionIndex(index)<<4;
                // Fire/lava positives only visit palette-positive sections,
                // clipped to the exact native inclusive BlockPos stream bounds.
                for(int by=Math.max(minY,bottom);by<=Math.min(maxY,bottom+15);by++)
                    for(int bz=Math.max(minZ,z<<4);bz<=Math.min(maxZ,(z<<4)+15);bz++)
                        for(int bx=Math.max(minX,x<<4);bx<=Math.min(maxX,(x<<4)+15);bx++)
                            if(predicate.test(section.getBlockState(bx&15,by&15,bz&15)))return false;
            }
        }
        return true;
    }

    public static boolean noneMatch(Entity entity,Stream<BlockState> original,Predicate<BlockState> predicate)
    {
        queries.increment();
        var level=entity.level();var bounds=entity.getBoundingBox().deflate(1e-6);
        // Preserve getBlockStatesIfLoaded's empty stream on the server and
        // outside the build range before considering any positive section.
        if(rejected||!level.hasChunksAt(Mth.floor(bounds.minX),Mth.floor(bounds.minY),Mth.floor(bounds.minZ),
                Mth.floor(bounds.maxX),Mth.floor(bounds.maxY),Mth.floor(bounds.maxZ)))return original.noneMatch(predicate);
        var result=sectionNoneMatch(level,bounds,predicate,true);
        if(result==null)return original.noneMatch(predicate);
        skipped.increment();
        if(VERIFY&&skipped.sum()%64==0)
        {
            boolean expected=original.noneMatch(predicate);verified.increment();
            if(expected!=result)
            {
                rejected=true;
                ProjectSeele.LOGGER.error("Giant move section query disagreed with native block stream; retaining native queries");
            }
            return expected;
        }
        original.close();return result;
    }

    public static Map<String,Object> diagnostics()
    {
        return Map.of("queries",queries.sum(),"palette_rejections",skipped.sum(),
                "native_comparisons",verified.sum(),"rejected",rejected);
    }

    private GiantMoveBlockQueryR53() {}
}
