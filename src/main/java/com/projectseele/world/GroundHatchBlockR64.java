package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;

/**
 * The closed cover of a hatch that lies level with open ground: grass on top like the terrain around it, plating
 * underneath. A hatch is drawn by its door entity, which reaches a player at most 384 blocks away and only while
 * its chunk is loaded on the server. To be ground from any distance, in the far view and on a map, the closed
 * hatch has to be blocks.
 *
 * It is an ordinary solid block to everything that draws it: neighbours cull against it and the far view treats
 * it as opaque. Only the light engine sees through it, as it does through the barrier the cover stands in for:
 * opening or closing 27,000 cells over a deep shaft relights nothing.
 */
public final class GroundHatchBlockR64 extends Block
{
    public GroundHatchBlockR64(Properties properties)
    {
        super(properties);
    }

    @Override
    public int getLightBlock(BlockState state, BlockGetter level, BlockPos pos)
    {
        return 0;
    }

    @Override
    public boolean propagatesSkylightDown(BlockState state, BlockGetter level, BlockPos pos)
    {
        return true;
    }
}
