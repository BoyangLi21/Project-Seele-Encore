package com.projectseele.world;

import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.NoiseColumn;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.LevelChunkSection;
import net.minecraft.world.level.chunk.PalettedContainer;

/** Extra solid foundation below the unchanged R50 noise/surface interval.
 * Build height is a dimension property; old noise context stays -672..320. */
public final class GeoFrontHeightR52
{
    public static final int MIN_Y=-960,LEGACY_MIN_Y=-672,MAX_Y_EXCLUSIVE=320;
    public static final int HEIGHT=MAX_Y_EXCLUSIVE-MIN_Y;
    private static BlockState foundation(int y)
    {return (y==MIN_Y?Blocks.BEDROCK:Blocks.DEEPSLATE).defaultBlockState();}
    static void fillFoundation(ChunkAccess chunk)
    {
        int from=Math.max(MIN_Y,chunk.getMinBuildHeight());int to=Math.min(LEGACY_MIN_Y,chunk.getMaxBuildHeight());
        if(from>=to)return;
        if((from&15)!=0||(to&15)!=0)throw new IllegalArgumentException("Complete aligned deep sections required");
        var sections=chunk.getSections();
        for(int y=from;y<to;y+=16)
        {
            int index=chunk.getSectionIndex(y);var previous=sections[index];
            var states=new PalettedContainer<>(Block.BLOCK_STATE_REGISTRY,Blocks.DEEPSLATE.defaultBlockState(),PalettedContainer.Strategy.SECTION_STATES);
            if(y==MIN_Y)for(int z=0;z<16;z++)for(int x=0;x<16;x++)states.set(x,0,z,Blocks.BEDROCK.defaultBlockState());
            // The native constructor recounts nonempty/ticking/fluid totals.
            // Biomes were already sampled by the original generator stage.
            sections[index]=new LevelChunkSection(states,previous.getBiomes());
        }
        // No old solid column can lose height. Update the new top once for
        // initially empty columns, without 73,728 block/heightmap callbacks.
        for(var entry:chunk.getHeightmaps())for(int z=0;z<16;z++)for(int x=0;x<16;x++)entry.getValue().update(x,to-1,z,foundation(to-1));
        chunk.setUnsaved(true);
    }
    static NoiseColumn extendColumn(NoiseColumn original,LevelHeightAccessor bounds)
    {
        int from=Math.max(MIN_Y,bounds.getMinBuildHeight()),to=bounds.getMaxBuildHeight();
        if(from>=LEGACY_MIN_Y||to<=from)return original;
        var states=new BlockState[to-from];
        for(int y=from;y<to;y++)states[y-from]=y<LEGACY_MIN_Y?foundation(y):original.getBlock(y);
        return new NoiseColumn(from,states);
    }
    private GeoFrontHeightR52(){}
}
